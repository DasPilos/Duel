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
DEFAULT_AGGRO_TILES = 3.5  # как у мобов сейчас: три тайла и полтайла

# ключ: (наименьшее, наибольшее)
LIMITS = {
    "move_speed": (0.0, 400.0),
    "windup": (0.05, 5.0),
    "backswing": (0.05, 5.0),
    "aggro_tiles": (0.0, 30.0),
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


def validate_settings(settings):
    """Проверяет настройки моба и возвращает их в нормальном виде. Ошибка — ValueError с текстом для художника."""
    if not isinstance(settings, dict):
        raise ValueError("Настройки моба должны быть словарём")
    result = {key: _number(settings, key) for key in LIMITS}
    result["respawn_seconds"] = int(result["respawn_seconds"])
    result["reward_copper"] = int(result["reward_copper"])
    result["reward_xp"] = int(result["reward_xp"])
    result["equipment"] = _validate_equipment(settings.get("equipment"))
    try:
        level = int(settings["level"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("Уровень должен быть целым числом") from None
    if not LEVEL_MIN <= level <= LEVEL_CAP:
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
        if key == "endurance":
            if value != endurance_for_level(level):
                raise ValueError(f"Выносливость на уровне {level} равна {endurance_for_level(level)}")
        elif value < STAT_MIN:
            raise ValueError(f"Характеристика «{label}» не ниже {STAT_MIN}")
        result["stats"][key] = value
    spent, total = spent_points(result["stats"]), free_points_for_level(level)
    if spent > total:
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
        merged.update({key: value for key, value in stored.items() if key in merged})
    try:
        return validate_settings(merged)
    except ValueError as error:
        raise ModeFileError(f"Настройки «{kind}» в {mode}.json неверны: {error}") from error


def save_mob_settings(mode, kind, settings, folder=None):
    """Записывает настройки вида моба в файл режима, не трогая остальных мобов. Возвращает записанные настройки."""
    if not is_mode(mode):
        raise ModeFileError(f"Неизвестный режим «{mode}»")
    checked = validate_settings(settings)
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
