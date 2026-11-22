"""Проверка карт редактора перед публикацией и рельеф опубликованной карты мира."""
from combat.progression import LEVEL_CAP
from core import crystal_growth
from core.map_catalog import (
    DEFAULT_MAP_SIZE, MAP_SIZE_MAX, MAP_SIZE_MIN, WATER_ANIMAL_KEYS, catalog_definitions,
    water_decor_requires_water_keys,
)
from core.npc_catalog import NPC_CATALOG
from core.mob_catalog import MOB_KEYS
from core.tile_mask import load_partial_masks

LAYERS = ("ground", "overlay", "elevation", "relief", "infra", "object")
# Тайлы и объекты из листов художника (godot_client/assets/base_tails) сохраняются ключом «atlas|лист|…».
# Они не в каталоге: сервер проверяет формат и слой, а тип рельефа определяет Front Line по имени листа.
ATLAS_KEY_PREFIX = "atlas|"
GROUND_LAYERS = ("ground", "overlay", "elevation", "relief", "infra")


def atlas_item(key, layer):
    """Элемент каталога для ключа листа художника: один тайл, тип по слою."""
    parts = key[len(ATLAS_KEY_PREFIX):].split("|")
    if len(parts) not in (3, 5, 6) or not all(parts):
        raise ValueError(f"Неверный ключ тайла «{key}»")
    return {
        "item_key": key,
        "kind": "ground" if layer in GROUND_LAYERS else "object",
        "category": "atlas",
        "footprint_w": 1,
        "footprint_h": 1,
        "blocks": False,
    }


def _catalog_item(by_key, key, layer):
    item = by_key.get(key)
    if item is None and key.startswith(ATLAS_KEY_PREFIX):
        item = atlas_item(key, layer)
        by_key[key] = item
    return item
NPC_KEYS = frozenset(npc["key"] for npc in NPC_CATALOG)
MAX_MOB_SPAWN_COUNT = 500
MAX_MOB_SPAWN_INTERVAL_SECONDS = 86_399
MAX_MOB_SPAWN_START_DELAY_SECONDS = 604_800
MAX_MOB_SPAWN_WAVES = 50
MAX_MOB_SPAWN_REWARD = 1_000_000
MAX_BOSS_SPAWN_HP = 1_000_000
MAX_BOSS_SPAWN_MP = 1_000_000
MAX_BOSS_SPELL_SLOTS = 3
MAX_BOSS_SPELL_RANGE = 100
MAX_BOSS_SPELL_DAMAGE = 1_000_000
MAX_BOSS_SPELL_COOLDOWN_SECONDS = 86_399
MAX_BOSS_SPELL_AREA = 100
MAX_BOSS_SPELL_MANA_COST = 1_000_000
MAX_BOSS_DROP_SLOTS = 5
DEFAULT_TAVERN_HP = 1000
MAX_TAVERN_HP = 1_000_000


def check_map_size(map_w, map_h):
    """Размер карты в тайлах: целые числа от MAP_SIZE_MIN до MAP_SIZE_MAX."""
    for side in (map_w, map_h):
        if not isinstance(side, int) or isinstance(side, bool) or not MAP_SIZE_MIN <= side <= MAP_SIZE_MAX:
            raise ValueError(f"Размер карты: от {MAP_SIZE_MIN} до {MAP_SIZE_MAX} тайлов по каждой стороне")
    return map_w, map_h


def validate_cells(cells, catalog, map_w, map_h):
    """Проверяет клетки карты и возвращает их в виде кортежей для записи в базу.

    Слои ground, overlay, elevation, relief и infra: по одной клетке на тайл, в каждом лежат тайлы земли;
    возвышенность и рельеф отделены от подложки, а infra рисуется поверх них. Слой object: занятые клетки объектов
    не должны пересекаться и не выходить за край карты.
    """
    if not isinstance(cells, list):
        raise ValueError("Карта должна быть списком клеток")
    by_key = {item["item_key"]: item for item in catalog}
    anchors = set()
    occupied = set()
    result = []
    for cell in cells:
        layer = str(cell.get("layer", ""))
        key = str(cell.get("key", ""))
        x, y = int(cell.get("x", -1)), int(cell.get("y", -1))
        item = _catalog_item(by_key, key, layer)
        if item is None:
            raise ValueError(f"Элемента «{key}» нет в каталоге")
        if (
            layer not in LAYERS
            or item["kind"] != ("ground" if layer in ("overlay", "elevation", "relief", "infra") else layer)
        ):
            raise ValueError(f"Элемент «{key}» нельзя ставить на слой «{layer}»")
        if (layer, x, y) in anchors:
            raise ValueError(f"Клетка ({x}, {y}) уже занята на слое «{layer}»")
        anchors.add((layer, x, y))
        footprint = [(x + dx, y + dy) for dx in range(item["footprint_w"]) for dy in range(item["footprint_h"])]
        for fx, fy in footprint:
            if not (0 <= fx < map_w and 0 <= fy < map_h):
                raise ValueError(f"Элемент «{key}» выходит за край карты")
        if layer == "object":
            if any(tile in occupied for tile in footprint):
                raise ValueError(f"Элемент «{key}» в ({x}, {y}) пересекается с другим объектом")
            occupied.update(footprint)
        result.append((layer, x, y, key))
    water_tiles = {
        (x, y)
        for layer, x, y, key in result
        if layer == "ground"
        and by_key[key].get("category") == "water"
    }
    infra_tiles = {(x, y) for layer, x, y, _ in result if layer == "infra"}
    water_tiles.difference_update(infra_tiles)
    water_effect_keys = water_decor_requires_water_keys()
    for layer, x, y, key in result:
        if (
            layer == "overlay"
            and (
                by_key[key].get("category") == "water"
                or key in water_effect_keys
            )
            and (x, y) not in water_tiles
        ):
            raise ValueError("Водные эффекты можно размещать только на тайлах воды")
        if layer == "object" and key in WATER_ANIMAL_KEYS:
            footprint = [
                (x + dx, y + dy)
                for dx in range(by_key[key]["footprint_w"])
                for dy in range(by_key[key]["footprint_h"])
            ]
            if not all(tile in water_tiles for tile in footprint):
                raise ValueError("Водных животных можно размещать только на тайлах воды")
    return result


def validate_mobs(mobs, map_w, map_h):
    """Расстановка NPC: список (вид, x, y) для записи в базу. Вид — из каталога NPC, один NPC на клетку, клетка внутри карты."""
    if mobs is None:
        return []
    if not isinstance(mobs, list):
        raise ValueError("NPC должны быть списком")
    kinds = {npc["key"] for npc in NPC_CATALOG}
    result, taken = [], set()
    for mob in mobs:
        if not isinstance(mob, dict):
            raise ValueError("Каждый NPC — объект с полями kind, x, y")
        kind = str(mob.get("kind", ""))
        x, y = int(mob.get("x", -1)), int(mob.get("y", -1))
        if kind not in kinds:
            raise ValueError(f"NPC «{kind}» нет в каталоге")
        if not (0 <= x < map_w and 0 <= y < map_h):
            raise ValueError(f"NPC «{kind}» стоит за краем карты")
        if (x, y) in taken:
            raise ValueError(f"На клетке ({x}, {y}) уже стоит NPC")
        taken.add((x, y))
        result.append((kind, x, y))
    return result


def validate_spawns(spawns, map_w, map_h, *, include_settings=False, mode="front_line"):
    """Проверяет точки игроков и настроенные точки мобов для сохранённой карты."""
    if spawns is None:
        return []
    if not isinstance(spawns, list):
        raise ValueError("Точки спауна должны быть списком")
    result, taken = [], set()
    objective_seen = False
    for spawn in spawns:
        if not isinstance(spawn, dict):
            raise ValueError("Каждая точка спауна — объект с полями x, y")
        spawn_type = spawn.get("type", "hero")
        if spawn_type == "objective":
            if mode != "front_line":
                raise ValueError("Настройки главной цели доступны только в режиме Front Line")
            if objective_seen:
                raise ValueError("Для карты можно задать только одну главную цель")
            settings = spawn.get("settings", {})
            if not isinstance(settings, dict):
                raise ValueError("Настройки таверны должны быть объектом")
            max_hp = _bounded_spawn_setting(
                settings, "max_hp", "Здоровье таверны", MAX_TAVERN_HP,
                minimum=1, default=DEFAULT_TAVERN_HP,
            )
            result.append({"type": "objective", "settings": {"max_hp": max_hp}})
            objective_seen = True
            continue
        try:
            x, y = int(spawn.get("x", -1)), int(spawn.get("y", -1))
        except (TypeError, ValueError):
            raise ValueError("Координаты спауна должны быть целыми числами")
        if not (0 <= x < map_w and 0 <= y < map_h):
            raise ValueError(f"Точка спауна ({x}, {y}) за краем карты")
        if (x, y) in taken:
            raise ValueError(f"Точка спауна ({x}, {y}) задана дважды")
        taken.add((x, y))
        if spawn_type not in ("hero", "mob"):
            raise ValueError("Неизвестный тип спауна")
        normalized = {"x": x, "y": y}
        if "name" in spawn:
            name = spawn["name"]
            if not isinstance(name, str) or not 1 <= len(name.strip()) <= 32:
                raise ValueError("Название точки спауна должно содержать от 1 до 32 символов")
            normalized["name"] = name.strip()
        if spawn_type == "mob":
            if not include_settings:
                raise ValueError("Настроенные спауны мобов пока нельзя публиковать в игровой мир")
            settings = spawn.get("settings")
            if not isinstance(settings, dict):
                raise ValueError("Настройки спауна мобов должны быть объектом")
            raw_waves = settings.get("waves")
            if raw_waves is None:
                raw_waves = [settings]
            if not isinstance(raw_waves, list) or not 1 <= len(raw_waves) <= MAX_MOB_SPAWN_WAVES:
                raise ValueError(f"Количество волн должно быть от 1 до {MAX_MOB_SPAWN_WAVES}")
            normalized_waves = []
            allowed_mob_keys = MOB_KEYS if mode == "front_line" else NPC_KEYS
            for wave_index, wave_settings in enumerate(raw_waves, 1):
                if not isinstance(wave_settings, dict):
                    raise ValueError(f"Настройки волны {wave_index} должны быть объектом")
                if mode != "front_line" and ("target" in wave_settings or "boss" in wave_settings):
                    raise ValueError("Настройки цели и босса доступны только в режиме Front Line")
                level = _bounded_spawn_setting(wave_settings, "level", "Уровень спауна", LEVEL_CAP)
                count = _bounded_spawn_setting(wave_settings, "count", "Количество мобов", MAX_MOB_SPAWN_COUNT)
                interval = _bounded_spawn_setting(
                    wave_settings, "interval_seconds", "Интервал появления", MAX_MOB_SPAWN_INTERVAL_SECONDS,
                )
                start_after = _bounded_spawn_setting(
                    wave_settings, "start_after_seconds", "Время старта волны",
                    MAX_MOB_SPAWN_START_DELAY_SECONDS, minimum=0,
                    default=0,
                )
                reward_xp = _non_negative_spawn_setting(
                    wave_settings, "reward_xp", 10, "Опыт за убийство", MAX_MOB_SPAWN_REWARD,
                )
                reward_copper = _non_negative_spawn_setting(
                    wave_settings, "reward_copper", 10, "Медь за убийство", MAX_MOB_SPAWN_REWARD,
                )
                mob_key = wave_settings.get("mob_key")
                if not isinstance(mob_key, str) or not mob_key.strip():
                    raise ValueError(
                        f"Для волны {wave_index} не сохранён выбор моба. "
                        "Откройте настройки точки появления, выберите моба в поле «Моб» "
                        "и нажмите «Сохранить»."
                    )
                if mob_key not in allowed_mob_keys:
                    mode_name = "Front Line" if mode == "front_line" else mode
                    raise ValueError(
                        f"Моб «{mob_key}» для волны {wave_index} отсутствует в каталоге режима "
                        f"«{mode_name}»"
                    )
                squad_min = _bounded_spawn_setting(
                    wave_settings, "squad_min", "Отряд: минимум", MAX_MOB_SPAWN_COUNT, default=1,
                )
                squad_max = _bounded_spawn_setting(
                    wave_settings, "squad_max", "Отряд: максимум", MAX_MOB_SPAWN_COUNT, default=squad_min,
                )
                if squad_max < squad_min:
                    raise ValueError("Отряд: максимум не меньше минимума")
                normalized_wave = {
                    "level": level,
                    "mob_key": mob_key,
                    "count": count,
                    "interval_seconds": interval,
                    "start_after_seconds": start_after,
                    "squad_min": squad_min,
                    "squad_max": squad_max,
                    "reward_xp": reward_xp,
                    "reward_copper": reward_copper,
                }
                if mode == "front_line":
                    target = wave_settings.get("target", "objective")
                    if target not in ("objective", "characters", "both"):
                        raise ValueError("Цель спауна должна быть основной целью, персонажами или обоими вариантами")
                    normalized_wave["target"] = target
                    normalized_wave["boss"] = _validate_boss_settings(
                        wave_settings.get("boss", {}),
                        wave_index,
                    )
                normalized_waves.append(normalized_wave)
            normalized.update({
                "type": "mob",
                "settings": {"waves": normalized_waves},
            })
        result.append(normalized)
    return result


def _bounded_spawn_setting(settings, key, label, maximum, minimum=1, default=None):
    value = settings.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        raise ValueError(f"{label} должен быть целым числом от {minimum} до {maximum}")
    return value


def _non_negative_spawn_setting(settings, key, default, label, maximum):
    value = settings.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= maximum:
        raise ValueError(f"{label} должен быть целым числом от 0 до {maximum}")
    return value


def _validate_boss_settings(value, wave_index):
    if not isinstance(value, dict):
        raise ValueError(f"Настройки босса волны {wave_index} должны быть объектом")
    enabled = value.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ValueError(f"Параметр босса волны {wave_index} должен быть логическим")
    boss = {
        "enabled": enabled,
        "max_hp": _bounded_spawn_setting(
            value, "max_hp", f"ХП босса волны {wave_index}", MAX_BOSS_SPAWN_HP,
            default=1000,
        ),
        "max_mp": _bounded_spawn_setting(
            value, "max_mp", f"МП босса волны {wave_index}", MAX_BOSS_SPAWN_MP,
            minimum=0, default=0,
        ),
        "reward_xp": _non_negative_spawn_setting(
            value, "reward_xp", 100, f"Опыт за босса волны {wave_index}", MAX_MOB_SPAWN_REWARD,
        ),
    }
    raw_slots = value.get("spell_slots", [])
    if not isinstance(raw_slots, list) or len(raw_slots) > MAX_BOSS_SPELL_SLOTS:
        raise ValueError(f"У босса должно быть не больше {MAX_BOSS_SPELL_SLOTS} слотов заклинаний")
    slots = []
    for slot_index in range(MAX_BOSS_SPELL_SLOTS):
        slot = raw_slots[slot_index] if slot_index < len(raw_slots) else {}
        if not isinstance(slot, dict):
            raise ValueError(f"Слот заклинаний босса {slot_index + 1} должен быть объектом")
        spell_key = slot.get("spell_key", "")
        if not isinstance(spell_key, str) or len(spell_key) > 64:
            raise ValueError(f"Идентификатор заклинания в слоте {slot_index + 1} некорректен")
        slots.append({
            "spell_key": spell_key,
            "range": _bounded_spawn_setting(
                slot, "range", f"Дальность заклинания в слоте {slot_index + 1}",
                MAX_BOSS_SPELL_RANGE, minimum=0, default=3,
            ),
            "damage": _bounded_spawn_setting(
                slot, "damage", f"Урон заклинания в слоте {slot_index + 1}",
                MAX_BOSS_SPELL_DAMAGE, minimum=0, default=10,
            ),
            "cooldown_seconds": _bounded_spawn_setting(
                slot, "cooldown_seconds", f"Перезарядка слота {slot_index + 1}",
                MAX_BOSS_SPELL_COOLDOWN_SECONDS, minimum=0, default=5,
            ),
            "area_radius": _bounded_spawn_setting(
                slot, "area_radius", f"Радиус заклинания в слоте {slot_index + 1}",
                MAX_BOSS_SPELL_AREA, minimum=0, default=1,
            ),
            "mana_cost": _bounded_spawn_setting(
                slot, "mana_cost", f"Затраты МП в слоте {slot_index + 1}",
                MAX_BOSS_SPELL_MANA_COST, minimum=0, default=5,
            ),
        })
    boss["spell_slots"] = slots
    boss["drop_slots"] = _validate_boss_drop_slots(value.get("drop_slots", []), wave_index)
    return boss


def _validate_boss_drop_slots(raw_slots, wave_index):
    if not isinstance(raw_slots, list) or len(raw_slots) > MAX_BOSS_DROP_SLOTS:
        raise ValueError(f"У босса должно быть не больше {MAX_BOSS_DROP_SLOTS} слотов предметов")
    from server.items_database import CATALOG

    known_item_ids = {item[0] for item in CATALOG}
    slots = []
    total_chance = 0
    for slot_index in range(MAX_BOSS_DROP_SLOTS):
        slot = raw_slots[slot_index] if slot_index < len(raw_slots) else {}
        if not isinstance(slot, dict):
            raise ValueError(f"Слот предметов босса {slot_index + 1} должен быть объектом")
        item_id = slot.get("item_id", 0)
        if item_id is None or item_id == "" or (
            isinstance(item_id, int) and not isinstance(item_id, bool) and item_id == 0
        ):
            item_id = 0
        elif not isinstance(item_id, int) or isinstance(item_id, bool) or item_id not in known_item_ids:
            raise ValueError(f"Предмет в слоте босса {slot_index + 1} отсутствует в каталоге")
        chance = _bounded_spawn_setting(
            slot, "chance_percent", f"Шанс предмета в слоте босса {slot_index + 1}",
            100, minimum=0, default=0,
        )
        if not item_id and chance:
            raise ValueError(f"Выберите предмет в слоте босса {slot_index + 1}")
        total_chance += chance
        slots.append({"item_id": item_id, "chance_percent": chance})
    if total_chance > 100:
        raise ValueError("Сумма шансов выпадения предметов босса не должна превышать 100%")
    return slots


def validate_crystals(crystals, catalog, loot_item_ids):
    """Настройки роста и добычи кристаллов карты по цветам каталога; формат — core.crystal_growth.validate_settings."""
    return crystal_growth.validate_settings(
        crystals, crystal_growth.crystal_colors(item["item_key"] for item in catalog), loot_item_ids)


def terrain_from_cells(cells, catalog, masks=None):
    """Переводит клетки карты в наборы тайлов для рельефа; None, если клеток нет.

    Ягоды и пол не ставятся на воду, дорогу и мост.
    Сухой лес (old_tree) попадает в dry и блокирует ход.
    Пни, брёвна и мосты передаются списками объектов.
    Блокирующие тайлы каталога (blocks) попадают в impassable, кроме мостов.
    Элемент с маской (masks: ключ → маска 4×4) не блокирует тайл целиком: его проходимость задаёт маска.
    Тайл с блокирующим объектом без маски остаётся непроходимым целиком.
    """
    masks = masks or {}
    if not cells:
        return None
    # Тайл overlay (например, мост) заменяет проходимость земли под собой. Infra лежит поверх ландшафта,
    # но вода под infra становится проходимой, как мост.
    overlay_tiles = {
        (cell["x"], cell["y"])
        for cell in cells
        if cell["layer"] in ("overlay", "elevation", "relief")
    }
    infra_tiles = {(cell["x"], cell["y"]) for cell in cells if cell["layer"] == "infra"}
    by_key = {item["item_key"]: item for item in catalog}
    water, paths, forest, dry, mountain = set(), set(), set(), set(), set()
    berry, floor = set(), set()
    props, bridges, bridge_tiles = [], [], set()
    impassable, solid, partial, wildlife_blocked = set(), set(), {}, set()
    animals = []
    crystals = {}
    for cell in cells:
        item = _catalog_item(by_key, cell["key"], cell["layer"])
        if item is None:
            continue
        x, y = cell["x"], cell["y"]
        under_infra_water = (x, y) in infra_tiles and item["category"] == "water"
        if cell["layer"] == "ground" and ((x, y) in overlay_tiles or under_infra_water):
            continue
        if cell["layer"] == "overlay" and under_infra_water:
            continue
        footprint = [(x + dx, y + dy) for dx in range(item["footprint_w"]) for dy in range(item["footprint_h"])]
        category = item["category"]
        mask = masks.get(cell["key"])
        if mask is not None:
            partial.update(dict.fromkeys(footprint, mask))
        elif item["blocks"]:
            impassable.update(footprint)
            solid.update(footprint)
            if category not in ("animal", "water"):
                wildlife_blocked.update(footprint)
        if cell["layer"] in ("ground", "overlay", "elevation", "relief", "infra"):
            if category == "water":
                water.add((x, y))
            elif category == "road":
                paths.add((x, y))
            elif category == "berry":
                berry.add((x, y))
            elif category == "floor":
                floor.add((x, y))
            elif category == "rock":
                mountain.add((x, y))
        elif category == "tree":
            forest.add((x, y))
        elif category == "old_tree":
            dry.add((x, y))
        elif category == "crystal":
            color, stage = crystal_growth.parse_crystal_key(cell["key"])
            crystals[(x, y)] = {"color": color, "stage": stage}
        elif category == "animal":
            animals.append({"key": cell["key"], "x": x, "y": y})
        elif category == "rock":
            mountain.add((x, y))
        elif category in ("stump", "log"):
            props.append({"type": category, "tiles": [list(tile) for tile in footprint]})
        elif category == "bridge":
            bridges.append({"tiles": [list(tile) for tile in footprint]})
            bridge_tiles.update(footprint)
    ground_free = bridge_tiles | paths | water
    partial_tiles = {tile: mask for tile, mask in partial.items() if tile not in solid}
    animals.sort(key=lambda animal: (animal["y"], animal["x"], animal["key"]))
    for index, animal in enumerate(animals):
        animal["id"] = f"animal_{index}_{animal['key']}"
    return {
        "water": frozenset(water - bridge_tiles),
        "paths": frozenset(paths),
        "forest": frozenset(forest),
        "dry": frozenset(dry),
        "mountain": frozenset(mountain),
        "berry": frozenset(berry - ground_free),
        "floor": frozenset(floor - ground_free),
        "props": props,
        "bridges": bridges,
        "impassable": frozenset(impassable - bridge_tiles - {(animal["x"], animal["y"]) for animal in animals}),
        "wildlife_blocked": frozenset(wildlife_blocked),
        "animals": animals,
        "partial": partial_tiles,
        "crystals": crystals,
    }


def load_published_map(database, published=None):
    """Опубликованная карта текущего мира: (рельеф, сведения о публикации) или (None, None), если карты нет."""
    if published is None:
        published = database.published_map()
    if published is None:
        return None, None
    return terrain_from_cells(database.map_live_cells(), database.map_catalog(), load_partial_masks()), published
