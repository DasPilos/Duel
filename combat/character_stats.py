BASE_STAT_VALUE = 5
MIN_STAT_VALUE = 4
STARTING_STAT_POINTS = 6
BASE_HP = 100
LEVEL_HP_BONUS = 20
ENDURANCE_HP_BONUS = 14


def calculate_max_hp(level, endurance):
    """Return the maximum health determined by level and endurance."""
    return BASE_HP + LEVEL_HP_BONUS * (int(level) - 1) + ENDURANCE_HP_BONUS * int(endurance)


def adjust_stats(stats, stat_points, hp, max_hp, level, stat_name, delta):
    """Return updated stat state, or None when the requested change is invalid."""
    if stat_name not in stats or delta not in (-1, 1):
        return None
    if delta > 0 and stat_points <= 0:
        return None
    if delta < 0 and stats[stat_name] <= MIN_STAT_VALUE:
        return None

    updated_stats = dict(stats)
    updated_stats[stat_name] += delta
    updated_max_hp = calculate_max_hp(level, updated_stats["endurance"])
    updated_hp = int(hp)
    if stat_name == "endurance" and delta > 0:
        updated_hp += updated_max_hp - int(max_hp)

    return {
        "stats": updated_stats,
        "stat_points": int(stat_points) - delta,
        "hp": min(updated_hp, updated_max_hp),
        "max_hp": updated_max_hp,
    }
