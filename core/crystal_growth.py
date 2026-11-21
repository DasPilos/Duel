"""Рост и добыча кристаллов: ключи стадий, настройки карты, время и количество лута."""
import re

CRYSTAL_STAGES = 4
CRYSTAL_ITEM_ID = 14
GROW_SECONDS_MAX = 30 * 24 * 3600
HARVEST_SECONDS_MAX = 3600
LOOT_MAX = 99
LOOT_FIELDS = (("loot_start", "Лут при появлении"), ("loot_next", "Лут на последней стадии"))
DEFAULT_SETTINGS = {"grow_seconds": 600, "loot_start": 1, "loot_next": 3, "harvest_seconds": 5, "loot_item_id": CRYSTAL_ITEM_ID}

_KEY_PATTERN = re.compile(r"^crystal_(.+)_([1-4])$")


def parse_crystal_key(key):
    """(цвет, стадия) для ключа вида crystal_<цвет>_<стадия>; None для прочих ключей."""
    match = _KEY_PATTERN.match(str(key))
    if match is None:
        return None
    return match.group(1), int(match.group(2))


def parse_duration(text):
    """Время из строки ч:мм:сс (или мм:сс, или сс) в секунды. Минуты и секунды меньше 60, если они не первые."""
    parts = str(text).strip().split(":")
    if not 1 <= len(parts) <= 3 or not all(part.strip().isdigit() for part in parts):
        raise ValueError("Время: формат ч:мм:сс")
    values = [int(part) for part in parts]
    if len(values) > 1 and any(value >= 60 for value in values[1:]):
        raise ValueError("Минуты и секунды меньше 60")
    seconds = 0
    for value in values:
        seconds = seconds * 60 + value
    return seconds


def format_duration(seconds):
    """Секунды в строку ч:мм:сс."""
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"


def crystal_colors(keys):
    """Цвета кристаллов, встречающиеся в ключах каталога, по алфавиту."""
    colors = {parsed[0] for parsed in (parse_crystal_key(key) for key in keys) if parsed is not None}
    return sorted(colors)


def _check_int(value, low, high, title):
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise ValueError(f"{title}: целое число от {low} до {high}")
    return value


def validate_settings(raw, colors, loot_item_ids=None):
    """Настройки кристаллов карты: {цвет: {grow_seconds, loot_start, loot_next, harvest_seconds, loot_item_id}}.

    Цвета, которых нет в raw, получают значения по умолчанию. Неизвестный цвет — ошибка.
    loot_item_ids — допустимые предметы добычи (материалы каталога); None — не проверять.
    """
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("Настройки кристаллов должны быть объектом")
    known = set(colors)
    result = {}
    for color, values in raw.items():
        if color not in known:
            raise ValueError(f"Кристалла цвета «{color}» нет в каталоге")
        if not isinstance(values, dict):
            raise ValueError(f"Настройки кристалла «{color}» должны быть объектом")
        loot_item_id = _check_int(values.get("loot_item_id", CRYSTAL_ITEM_ID), 1, 10**9, "Предмет добычи")
        if loot_item_ids is not None and loot_item_id not in loot_item_ids:
            raise ValueError(f"Предмет добычи кристалла «{color}» должен быть материалом из каталога")
        result[color] = {
            "grow_seconds": _check_int(values.get("grow_seconds"), 1, GROW_SECONDS_MAX, "Время созревания"),
            "loot_start": _check_int(values.get("loot_start"), 1, LOOT_MAX, "Лут при появлении"),
            "loot_next": _check_int(values.get("loot_next"), 1, LOOT_MAX, "Лут на последней стадии"),
            "harvest_seconds": _check_int(values.get("harvest_seconds"), 1, HARVEST_SECONDS_MAX, "Время добычи"),
            "loot_item_id": loot_item_id,
        }
    for color in result:
        check_loot_order(result, colors, color, result[color])
    return result


def _neighbours(settings, colors, color):
    """Ближайшие настроенные цвета перед и после color в порядке colors (сам color не учитывается)."""
    index = colors.index(color)
    before = next((item for item in reversed(colors[:index]) if item in settings), None)
    after = next((item for item in colors[index + 1:] if item in settings), None)
    return before, after


def check_loot_order(settings, colors, color, values):
    """Лут кристалла не может быть меньше, чем у предыдущего настроенного цвета, и больше, чем у следующего."""
    before, after = _neighbours(settings, colors, color)
    for key, title in LOOT_FIELDS:
        value = values[key]
        if before is not None and value < settings[before][key]:
            raise ValueError(
                f"{title} у «{color}» ({value}) не может быть меньше, чем у «{before}» ({settings[before][key]})")
        if after is not None and value > settings[after][key]:
            raise ValueError(
                f"{title} у «{color}» ({value}) не может быть больше, чем у «{after}» ({settings[after][key]})")


def crystal_unlocked(settings, colors, color):
    """Кристалл можно настраивать, когда настроен предыдущий по порядку цвет (первый всегда доступен)."""
    index = colors.index(color)
    return index == 0 or colors[index - 1] in (settings or {})


def settings_for(settings, color):
    """Настройки цвета из карты или значения по умолчанию."""
    return {**DEFAULT_SETTINGS, **(settings or {}).get(color, {})}


def loot_amount(settings, stage):
    """Количество кристаллов при добыче на стадии stage: от loot_start на первой стадии до loot_next на последней."""
    if not 1 <= stage <= CRYSTAL_STAGES:
        raise ValueError("Стадия кристалла: от 1 до 4")
    start, end = settings["loot_start"], settings["loot_next"]
    steps = CRYSTAL_STAGES - 1
    return round(start + (end - start) * (stage - 1) / steps)
