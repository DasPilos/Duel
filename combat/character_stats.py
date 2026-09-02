BASE_STAT_VALUE = 3
STARTING_ENDURANCE_VALUE = 4
MIN_STAT_VALUE = 3
STARTING_STAT_POINTS = 3
ENDURANCE_HP_BONUS = 10
# Тестовый персонаж без ограничений по статам/уровню — нужен для проверки игры на разных уровнях.
DEBUG_UNLIMITED_CHARACTER_IDS = {2}
DEBUG_UNLIMITED_STAT_POINTS = 999


def is_debug_unlimited(character_id):
    try:
        return int(character_id) in DEBUG_UNLIMITED_CHARACTER_IDS
    except (TypeError, ValueError):
        return False


def level_stat_points(level):
    """Return free points granted on reaching a level."""
    return 3


def total_stat_points(level):
    """Return all free points available at the specified level."""
    return STARTING_STAT_POINTS + sum(level_stat_points(value) for value in range(2, int(level) + 1))


def minimum_endurance(level):
    """Return endurance permanently granted by the character level."""
    return STARTING_ENDURANCE_VALUE + max(0, int(level) - 1)


def calculate_max_hp(level, endurance):
    """Return the maximum health determined by level and endurance."""
    return ENDURANCE_HP_BONUS * int(endurance)


def adjust_stats(stats, stat_points, hp, max_hp, level, stat_name, delta, character_id=None):
    """Return updated stat state, or None when the requested change is invalid."""
    if stat_name not in stats or delta not in (-1, 1):
        return None
    unlimited = is_debug_unlimited(character_id)
    # Запретить увеличение выносливости вручную - она повышается только при повышении уровня
    if stat_name == "endurance" and delta > 0:
        return None
    if delta > 0 and stat_points <= 0 and not unlimited:
        return None
    minimum_value = 0 if unlimited else (minimum_endurance(level) if stat_name == "endurance" else MIN_STAT_VALUE)
    if delta < 0 and stats[stat_name] <= minimum_value:
        return None

    updated_stats = dict(stats)
    updated_stats[stat_name] += delta
    updated_max_hp = calculate_max_hp(level, updated_stats["endurance"])
    updated_hp = int(hp)
    if stat_name == "endurance" and delta > 0:
        updated_hp += updated_max_hp - int(max_hp)

    return {
        "stats": updated_stats,
        "stat_points": DEBUG_UNLIMITED_STAT_POINTS if unlimited else int(stat_points) - delta,
        "hp": min(updated_hp, updated_max_hp),
        "max_hp": updated_max_hp,
    }
