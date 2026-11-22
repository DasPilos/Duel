"""Настройки мобов по режимам игры: файл mob_modes/<режим>.json, в нём параметры каждого вида моба.

Редактор карт читает и пишет эти файлы, сервер будет читать их при появлении мобов в мире.
"""
import json
import os
import re
import tempfile
from pathlib import Path

from combat.character_stats import (
    BASE_STAT_VALUE,
    CREATION_ENDURANCE_VALUE,
    CREATION_FREE_POINTS,
    calculate_max_hp,
    calculate_max_mana,
    level_stat_points,
)
from combat.progression import LEVEL_CAP
from combat.world_stats import (
    BACKSWING_REDUCTION_PER_AGILITY,
    BASE_ATTACK_BACKSWING,
    BASE_ATTACK_WINDUP,
    BASE_MOVE_SPEED,
    MOVE_SPEED_PER_AGILITY,
    WINDUP_REDUCTION_PER_INTUITION,
)
from core.game_modes import is_mode

MODES_DIR = Path(__file__).resolve().parent.parent / "mob_modes"

STATES = ("aggressive", "neutral", "friendly")
STATE_LABELS = {"aggressive": "Агрессивный", "neutral": "Нейтральный", "friendly": "Дружественный"}
STATE_HINTS = {
    "aggressive": "Нападает на игрока, подошедшего на расстояние агрессии.",
    "neutral": "Не трогает игрока, пока тот не нападёт на него или на охраняемый им объект.",
    "friendly": "Не нападает. Помогает в бою, если бой с игроком начался в зоне патруля.",
}
STAT_LABELS = (
    ("strength", "Сила"),
    ("agility", "Ловкость"),
    ("intuition", "Интуиция"),
    ("wisdom", "Мудрость"),
    ("intellect", "Интеллект"),
    ("endurance", "Выносливость"),
)
STAT_SHORT = {
    "strength": "Сил", "agility": "Лов", "intuition": "Инту", "wisdom": "Муд", "intellect": "Инте", "endurance": "Вын",
}
# Первый уровень: пять характеристик по 3, выносливость 4, три свободных очка (как при создании персонажа).
# Каждый следующий уровень даёт +1 к выносливости и столько же свободных очков, сколько у персонажа (level_stat_points).
# Выносливость определяется уровнем и вручную не меняется, остальные пять характеристик поднимаются за свободные очки.
LEVEL_MIN = 1
STAT_MIN = BASE_STAT_VALUE
ALLOCATABLE_STATS = ("strength", "agility", "intuition", "wisdom", "intellect")
# Бес первого уровня: три свободных очка вложены в силу (+2) и ловкость (+1)
DEFAULT_STATS = {"strength": 5, "agility": 4, "intuition": 3, "wisdom": 3, "intellect": 3, "endurance": 4}

# Поле патруля: PATROL_SIZE × PATROL_SIZE тайлов, клетка (PATROL_ANCHOR, PATROL_ANCHOR) — точка появления моба.
PATROL_SIZE = 18
PATROL_ANCHOR = 9
DEFAULT_PATROL_RADIUS = 3
DEFAULT_AGGRO_TILES = 7.0  # как у мобов сейчас: три тайла и полтайла по 32 px, т.е. семь тайлов по 16 px

# ключ: (наименьшее, наибольшее)
LIMITS = {
    "move_speed": (0.0, 400.0),
    "windup": (0.05, 5.0),
    "backswing": (0.05, 5.0),
    "aggro_tiles": (0.0, 60.0),
    "respawn_seconds": (0.0, 86399.0),
    "reward_copper": (0.0, 1000000.0),
    "reward_xp": (0.0, 1000000.0),
}
# Респаун по умолчанию: столько же, сколько у мобов на сервере (server/world_mobs.py, MOB_RESPAWN_DELAY)
DEFAULT_RESPAWN_SECONDS = 30
# Награда по умолчанию: 30 медных монет на моба, делятся между игроками по доле урона
DEFAULT_REWARD_COPPER = 30
# Опыт по умолчанию: базовая награда моба, делится между игроками по доле урона
DEFAULT_REWARD_XP = 10
# Дальность атаки моба Front Line в единицах (1 тайл = 50 ед.). Только для режима front_line;
# в файлах Tower и Economy этого поля нет.
DEFAULT_ATTACK_RANGE_UNITS = 100
ATTACK_RANGE_LIMITS = (0, 1500)
# Характер боя моба Front Line: ближний бой, стрелок (стрела) или маг (сфера с уроном по области).
ATTACK_STYLES = ("warrior", "archer", "mage")
DEFAULT_ATTACK_STYLE = "warrior"
# Радиус урона мага, единиц (50 ед. = 1 тайл); по умолчанию как у героя-мага.
DEFAULT_AREA_RADIUS_UNITS = 50
AREA_RADIUS_LIMITS = (0, 500)

# Слоты экипировки моба, которые художник задаёт в редакторе карт (id предмета из базы или None)
# Слоты куклы — те же, что у персонажа (server/items_database.py EQUIPMENT_SLOTS)
MOB_EQUIPMENT_SLOTS = (
    "head", "ears", "neck", "back", "body", "hands",
    "belt", "legs", "feet", "weapon", "shield", "ring", "ring_2",
)


def item_fits_mob(item, stats, level):
    """Подходит ли предмет виду моба: требования из effects.requirements — характеристики и уровень (по умолчанию 1)."""
    requirements = dict((item.get("effects") or {}).get("requirements") or {})
    if int(requirements.pop("level", 1)) > level:
        return False
    return all(stats.get(stat, 0) >= int(value) for stat, value in requirements.items())


def item_slot(slot):
    """Слот предмета для слота куклы: два кольца в базе — один слот «ring»."""
    return "ring" if slot == "ring_2" else slot


def drop_unfit_equipment(equipment, items, stats, level):
    """Снимает предметы, которые не подходят виду по текущим характеристикам и уровню. Предметы вне списка items
    (например, при недоступном сервере) не трогаются: их проверит сервер при сборке мобов."""
    known = {int(item["id"]): item for item in items}
    result = {}
    for slot, item_id in equipment.items():
        item = known.get(item_id) if item_id is not None else None
        result[slot] = None if item is not None and not item_fits_mob(item, stats, level) else item_id
    return result


def format_hms(seconds):
    """Секунды в виде ЧЧ:ММ:СС, например 30 -> 00:00:30."""
    seconds = int(seconds)
    return f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"


class ModeFileError(ValueError):
    """Файл настроек режима нельзя прочитать или записать."""


def _folder(folder):
    return MODES_DIR if folder is None else Path(folder)


def _patrol_offsets_in_radius(radius):
    return [
        [dx, dy]
        for dy in range(-PATROL_ANCHOR, PATROL_SIZE - PATROL_ANCHOR)
        for dx in range(-PATROL_ANCHOR, PATROL_SIZE - PATROL_ANCHOR)
        if dx * dx + dy * dy <= radius * radius
    ]


def endurance_for_level(level):
    """Выносливость моба на уровне: 4 на первом, затем +1 за уровень."""
    return CREATION_ENDURANCE_VALUE + int(level) - 1


def free_points_for_level(level):
    """Все свободные очки характеристик на уровне: 3 на первом, затем по таблице уровней персонажа."""
    return CREATION_FREE_POINTS + sum(level_stat_points(value) for value in range(2, int(level) + 1))


def spent_points(stats):
    """Сколько очков вложено в пять характеристик сверх базы."""
    return sum(int(stats[key]) - BASE_STAT_VALUE for key in ALLOCATABLE_STATS)


def free_points(level, stats):
    """Сколько свободных очков ещё можно вложить."""
    return free_points_for_level(level) - spent_points(stats)


def default_settings(kind=None):
    """Настройки по умолчанию: скорости и замах считаются по формулам мира из характеристик."""
    stats = dict(DEFAULT_STATS)
    return {
        "level": LEVEL_MIN,
        "max_hp": calculate_max_hp(LEVEL_MIN, stats["endurance"]),
        "max_mp": calculate_max_mana(stats["intellect"]),
        "move_speed": BASE_MOVE_SPEED + MOVE_SPEED_PER_AGILITY * stats["agility"],
        "windup": round(max(0.05, BASE_ATTACK_WINDUP - WINDUP_REDUCTION_PER_INTUITION * stats["intuition"]), 2),
        "backswing": round(max(0.05, BASE_ATTACK_BACKSWING - BACKSWING_REDUCTION_PER_AGILITY * stats["agility"]), 2),
        "aggro_tiles": DEFAULT_AGGRO_TILES,
        "respawn_seconds": DEFAULT_RESPAWN_SECONDS,
        "reward_copper": DEFAULT_REWARD_COPPER,
        "reward_xp": DEFAULT_REWARD_XP,
        "equipment": {slot: None for slot in MOB_EQUIPMENT_SLOTS},
        "state": "aggressive",
        "stats": stats,
        "patrol": _patrol_offsets_in_radius(DEFAULT_PATROL_RADIUS),
    }


def _number(settings, key):
    low, high = LIMITS[key]
    try:
        value = float(settings[key])
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"Параметр «{key}» должен быть числом") from None
    if not low <= value <= high:
        raise ValueError(f"Параметр «{key}»: от {low:g} до {high:g}")
    return round(value, 2)


def _validate_equipment(equipment):
    """Экипировка моба: слот → id предмета из базы или None. Тип предмета сервер проверяет по каталогу."""
    if equipment is None:
        equipment = {}
    if not isinstance(equipment, dict):
        raise ValueError("Экипировка должна быть словарём слот → предмет")
    unknown = set(equipment) - set(MOB_EQUIPMENT_SLOTS)
    if unknown:
        raise ValueError(f"Неизвестный слот экипировки: {', '.join(sorted(unknown))}")
    result = {}
    for slot in MOB_EQUIPMENT_SLOTS:
        item_id = equipment.get(slot)
        if item_id is None:
            result[slot] = None
            continue
        try:
            value = int(item_id)
        except (TypeError, ValueError):
            raise ValueError(f"Предмет в слоте «{slot}» должен быть номером из базы предметов") from None
        if value <= 0:
            raise ValueError(f"Предмет в слоте «{slot}» должен быть номером из базы предметов")
        result[slot] = value
    return result


DAMAGE_LIMIT = 1000


def _damage_pair(settings):
    values = []
    for key in ("damage_min", "damage_max"):
        raw = settings.get(key, 0)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or raw != int(raw):
            raise ValueError(f"Параметр «{key}» должен быть целым числом")
        if not 0 <= raw <= DAMAGE_LIMIT:
            raise ValueError(f"Урон: от 0 до {DAMAGE_LIMIT}")
        values.append(int(raw))
    if values[0] > values[1]:
        raise ValueError("Урон: минимум не больше максимума")
    return values[0], values[1]


def _attack_range(settings):
    raw = settings.get("attack_range", DEFAULT_ATTACK_RANGE_UNITS)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError("Параметр «attack_range» должен быть числом")
    low, high = ATTACK_RANGE_LIMITS
    if not low <= raw <= high:
        raise ValueError(f"Дальность атаки: от {low} до {high} ед. (50 ед. = 1 тайл)")
    return int(round(raw))


def _attack_style(settings):
    raw = settings.get("attack_style", DEFAULT_ATTACK_STYLE)
    if raw not in ATTACK_STYLES:
        raise ValueError("Характер боя: воин, лучник или маг")
    return raw


def _area_radius(settings):
    raw = settings.get("area_radius", DEFAULT_AREA_RADIUS_UNITS)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError("Параметр «area_radius» должен быть числом")
    low, high = AREA_RADIUS_LIMITS
    if not low <= raw <= high:
        raise ValueError(f"Радиус урона: от {low} до {high} ед. (50 ед. = 1 тайл)")
    return int(round(raw))


def validate_settings(settings, mode=None):
    """Проверяет настройки моба и возвращает их в нормальном виде. Ошибка — ValueError с текстом для художника."""
    if not isinstance(settings, dict):
        raise ValueError("Настройки моба должны быть словарём")
    unlimited_stats = mode == "front_line"
    result = {key: _number(settings, key) for key in LIMITS}
    result["respawn_seconds"] = int(result["respawn_seconds"])
    result["reward_copper"] = int(result["reward_copper"])
    result["reward_xp"] = int(result["reward_xp"])
    for key, minimum in (("max_hp", 1), ("max_mp", 0)):
        if key not in settings and not unlimited_stats:
            result[key] = default_settings()[key]
            continue
        try:
            value = int(settings[key])
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ValueError(f"Параметр «{key}» должен быть целым числом") from None
        if isinstance(settings[key], bool) or value != settings[key] or value < minimum:
            raise ValueError(f"Параметр «{key}» должен быть целым числом не меньше {minimum}")
        result[key] = value
    result["equipment"] = _validate_equipment(settings.get("equipment"))
    if unlimited_stats:
        result["attack_range"] = _attack_range(settings)
        result["damage_min"], result["damage_max"] = _damage_pair(settings)
        result["attack_style"] = _attack_style(settings)
        result["area_radius"] = _area_radius(settings)
    try:
        level = int(settings["level"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("Уровень должен быть целым числом") from None
    if level < LEVEL_MIN or (not unlimited_stats and level > LEVEL_CAP):
        raise ValueError(f"Уровень: от {LEVEL_MIN} до {LEVEL_CAP}")
    result["level"] = level
    state = settings.get("state")
    if state not in STATES:
        raise ValueError(f"Состояние должно быть одним из: {', '.join(STATES)}")
    result["state"] = state
    stats = settings.get("stats")
    if not isinstance(stats, dict):
        raise ValueError("Характеристики должны быть словарём")
    result["stats"] = {}
    for key, label in STAT_LABELS:
        try:
            value = int(stats[key])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"Характеристика «{label}» должна быть целым числом") from None
        if unlimited_stats and value < 0:
            raise ValueError(f"Характеристика «{label}» не ниже 0")
        if not unlimited_stats and key == "endurance":
            if value != endurance_for_level(level):
                raise ValueError(f"Выносливость на уровне {level} равна {endurance_for_level(level)}")
        elif not unlimited_stats and value < STAT_MIN:
            raise ValueError(f"Характеристика «{label}» не ниже {STAT_MIN}")
        result["stats"][key] = value
    spent, total = spent_points(result["stats"]), free_points_for_level(level)
    if not unlimited_stats and spent > total:
        raise ValueError(f"Вложено {spent} очков характеристик, на уровне {level} доступно {total}")
    patrol = settings.get("patrol")
    if not isinstance(patrol, list):
        raise ValueError("Патруль должен быть списком клеток")
    low, high = -PATROL_ANCHOR, PATROL_SIZE - PATROL_ANCHOR - 1
    cells = set()
    for cell in patrol:
        try:
            dx, dy = int(cell[0]), int(cell[1])
        except (TypeError, ValueError, IndexError):
            raise ValueError("Клетка патруля: пара чисел [dx, dy]") from None
        if not (low <= dx <= high and low <= dy <= high):
            raise ValueError(f"Клетка патруля ({dx}, {dy}) вне поля {PATROL_SIZE}×{PATROL_SIZE}")
        cells.add((dx, dy))
    result["patrol"] = [list(cell) for cell in sorted(cells, key=lambda c: (c[1], c[0]))]
    return result


def mode_file(mode, folder=None):
    return _folder(folder) / f"{mode}.json"


def _read_file(mode, folder):
    path = mode_file(mode, folder)
    if not path.is_file():
        return {"mode": mode, "mobs": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ModeFileError(f"Файл {path.name} не прочитан: {error}") from error
    if not isinstance(data, dict) or not isinstance(data.get("mobs", {}), dict):
        raise ModeFileError(f"Файл {path.name} имеет неверный формат")
    data.setdefault("mobs", {})
    return data


def load_mob_settings(mode, kind, folder=None):
    """Настройки вида моба в режиме: значения из файла поверх настроек по умолчанию."""
    if not is_mode(mode):
        raise ModeFileError(f"Неизвестный режим «{mode}»")
    stored = _read_file(mode, folder)["mobs"].get(kind, {})
    merged = default_settings(kind)
    if isinstance(stored, dict):
        allowed = set(merged) | (
            {"attack_range", "damage_min", "damage_max", "attack_style", "area_radius"}
            if mode == "front_line" else set()
        )
        merged.update({key: value for key, value in stored.items() if key in allowed})
    try:
        return validate_settings(merged, mode=mode)
    except ValueError as error:
        raise ModeFileError(f"Настройки «{kind}» в {mode}.json неверны: {error}") from error


def save_mob_settings(mode, kind, settings, folder=None):
    """Записывает настройки вида моба в файл режима, не трогая остальных мобов. Возвращает записанные настройки."""
    if not is_mode(mode):
        raise ModeFileError(f"Неизвестный режим «{mode}»")
    checked = validate_settings(settings, mode=mode)
    data = _read_file(mode, folder)
    data["mode"] = mode
    data["mobs"][kind] = checked
    path = mode_file(mode, folder)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        text = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True)
        # Клетка патруля [dx, dy] занимает одну строку, чтобы файл читался и давал короткие diff в git
        text = re.sub(r"\[\s+(-?\d+),\s+(-?\d+)\s+\]", r"[\1, \2]", text)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
            file.write(text + "\n")
        os.replace(temp_name, path)
    except OSError as error:
        raise ModeFileError(f"Файл {path.name} не записан: {error}") from error
    return checked
