"""Форма нового предмета из редактора карт: проверка значений и сборка записи каталога предметов.

Одна и та же проверка выполняется в редакторе (до отправки) и на сервере (перед записью в базу).
Поля, которых нет в бою, сохраняются в эффектах, но пока ничего не меняют: см. server/world_mobs.py.
"""
from core import item_icons, mob_modes

FORM_STATS = tuple(key for key, _label in mob_modes.STAT_LABELS)
STAT_LABEL = dict(mob_modes.STAT_LABELS)
MAX_NAME = 64
MAX_STAT = 50
MAX_LEVEL = 50
MAX_PERCENT = 100
MAX_HP = 10_000
MAX_DAMAGE = 999
MAX_ATTACK_DISTANCE = 100
MAX_AURA_RADIUS = 3000
MAX_PRICE = 1_000_000_000
# Первый id для предметов, созданных в редакторе: id до 100 заняты каталогом в server/items_database.py
CUSTOM_ITEM_FIRST_ID = 1000
DEFAULT_CRIT_POWER = 50
AURA_TYPES = {"none": "Нет", "vampirism": "Вампиризм"}
AURA_TARGETS = {"allies": "Союзники", "enemies": "Враги"}
# Ring 1 and ring 2 are character loadout positions, not separate item types.
ITEM_FORM_SLOTS = tuple(slot for slot in mob_modes.MOB_EQUIPMENT_SLOTS if slot != "ring_2")

# Значения формы по умолчанию (в редакторе это то, что видит художник при открытии окна)
DEFAULT_FORM = {
    "name": "",
    "slot": "weapon",
    "two_handed": False,
    "windup_percent": 0,
    "recovery_percent": 0,
    "move_speed_percent": 0,
    "price": 0,
    "damage_min": 0,
    "damage_max": 0,
    "attack_range": 0,
    "attack_area": 0,
    "lifesteal_percent": 0,
    "aura_type": "none",
    "aura_target": "allies",
    "aura_radius_px": 0,
    "aura_lifesteal_percent": 0,
    "level": 1,
    "requirements": {stat: 0 for stat in FORM_STATS},
    "bonuses": {stat: 0 for stat in FORM_STATS},
    "dodge": 0,
    "anti_dodge": 0,
    "crit": 0,
    "anti_crit": 0,
    "crit_power": DEFAULT_CRIT_POWER,
    "block": 0,
    "hp": 0,
    "mp": 0,
    "magic_damage": 0,
    "icon": None,
}


def default_form():
    return {
        **DEFAULT_FORM,
        "requirements": dict(DEFAULT_FORM["requirements"]),
        "bonuses": dict(DEFAULT_FORM["bonuses"]),
    }


def _int_in(form, key, low, high, label):
    try:
        value = int(form[key])
    except (TypeError, ValueError):
        raise ValueError(f"{label}: нужно целое число") from None
    if not low <= value <= high:
        raise ValueError(f"{label}: от {low} до {high}")
    return value


def validate_form(form):
    """Проверяет значения формы и возвращает их в нормальном виде. Ошибка — ValueError с текстом для художника.

    Поля, которых нет в форме, берутся из значений по умолчанию."""
    if not isinstance(form, dict):
        raise ValueError("Форма предмета должна быть объектом")
    defaults = default_form()
    form = {
        **defaults, **form,
        "requirements": {**defaults["requirements"], **(form.get("requirements") or {})},
        "bonuses": {**defaults["bonuses"], **(form.get("bonuses") or {})},
    }
    name = str(form.get("name", "")).strip()
    if not name:
        raise ValueError("Укажите название предмета")
    if len(name) > MAX_NAME:
        raise ValueError(f"Название длиннее {MAX_NAME} символов")
    slot = "ring" if form.get("slot") == "ring_2" else form.get("slot")
    if slot not in ITEM_FORM_SLOTS:
        raise ValueError("Выберите слот экипировки")
    if form.get("aura_type") not in AURA_TYPES:
        raise ValueError("Выберите тип ауры")
    if form.get("aura_target") not in AURA_TARGETS:
        raise ValueError("Выберите цель ауры")
    icon = form.get("icon") or None
    if icon is not None and not item_icons.is_known_icon(icon):
        raise ValueError("Иконка не найдена в базе иконок")
    clean = {
        "name": name,
        "slot": slot,
        "icon": icon,
        "aura_type": form["aura_type"],
        "aura_target": form["aura_target"],
        "two_handed": bool(form.get("two_handed")),
        "windup_percent": _int_in(form, "windup_percent", -90, 200, "Скорость замаха, %"),
        "recovery_percent": _int_in(form, "recovery_percent", -90, 200, "Восстановление, %"),
        "move_speed_percent": _int_in(form, "move_speed_percent", -90, 200, "Скорость передвижения, %"),
        "price": _int_in(form, "price", 0, MAX_PRICE, "Цена"),
        "damage_min": _int_in(form, "damage_min", 0, MAX_DAMAGE, "Урон от"),
        "damage_max": _int_in(form, "damage_max", 0, MAX_DAMAGE, "Урон до"),
        "attack_range": _int_in(form, "attack_range", 0, MAX_ATTACK_DISTANCE, "Дальность атаки, клеток"),
        "attack_area": _int_in(form, "attack_area", 0, MAX_ATTACK_DISTANCE, "Площадь атаки, клеток"),
        "lifesteal_percent": _int_in(form, "lifesteal_percent", 0, MAX_PERCENT, "Вампиризм, %"),
        "aura_radius_px": _int_in(form, "aura_radius_px", 0, MAX_AURA_RADIUS, "Радиус ауры, пикселей"),
        "aura_lifesteal_percent": _int_in(
            form, "aura_lifesteal_percent", 0, MAX_PERCENT, "Вампиризм ауры, %"
        ),
        "level": _int_in(form, "level", 1, MAX_LEVEL, "Уровень"),
        "crit_power": _int_in(form, "crit_power", 0, 500, "Сила крита, %"),
        "hp": _int_in(form, "hp", 0, MAX_HP, "ХП"),
        "mp": _int_in(form, "mp", 0, MAX_HP, "МП"),
        "magic_damage": _int_in(form, "magic_damage", 0, MAX_DAMAGE, "Маг урон"),
    }
    if clean["damage_min"] > clean["damage_max"]:
        raise ValueError("Урон «от» не может быть больше «до»")
    for key, label in (
        ("dodge", "Уворот, %"), ("anti_dodge", "Анти уворот, %"), ("crit", "Крит, %"),
        ("anti_crit", "Крит антикрит, %"), ("block", "Блок, %"),
    ):
        clean[key] = _int_in(form, key, 0, MAX_PERCENT, label)
    for group in ("requirements", "bonuses"):
        values = form.get(group) or {}
        clean[group] = {}
        for stat in FORM_STATS:
            clean[group][stat] = _int_in(values, stat, 0, MAX_STAT, f"{STAT_LABEL[stat]}")
    return clean


def build_item(form, item_id):
    """Запись предмета для items_catalog: поля таблицы, effects_json и bonuses_json по соглашению каталога."""
    clean = validate_form(form)
    requirements = {stat: value for stat, value in clean["requirements"].items() if value}
    if clean["level"] > 1:
        requirements["level"] = clean["level"]
    effects = {}
    if requirements:
        effects["requirements"] = requirements
    if clean["damage_max"]:
        effects["damage"] = [clean["damage_min"], clean["damage_max"]]
    if clean["two_handed"]:
        effects["two_handed"] = True
    for key in ("windup_percent", "recovery_percent", "move_speed_percent", "attack_range", "attack_area",
                "lifesteal_percent", "anti_dodge", "crit", "anti_crit", "crit_power", "magic_damage"):
        if clean[key] and not (key == "crit_power" and clean[key] == DEFAULT_CRIT_POWER):
            effects[key] = clean[key]
    if clean["aura_type"] != "none":
        effects["aura"] = {
            "type": clean["aura_type"],
            "target": clean["aura_target"],
            "radius_px": clean["aura_radius_px"],
            "lifesteal_percent": clean["aura_lifesteal_percent"],
        }
    for key in ("dodge", "block"):
        if clean[key]:
            effects[key] = clean[key]
    bonuses = {stat: value for stat, value in clean["bonuses"].items() if value}
    for key in ("hp", "mp", "dodge", "block"):
        if clean[key]:
            bonuses[key] = clean[key]
    return {
        "id": item_id,
        "name": clean["name"],
        "item_type": "equipment",
        "rarity": "common",
        "weight": 1.0,
        "price": clean["price"],
        "description": "Создан в редакторе карт",
        "can_use": 0,
        "effects": effects or None,
        "bonuses": bonuses or None,
        "icon": clean["icon"],
        "equip_slot": clean["slot"],
    }
