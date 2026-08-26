import math


LEVEL_CAP = 30
WIN_XP_BASE = 20
DRAW_XP_BASE = 8
LOSS_XP_BASE = 5


def xp_to_next(level):
    """Return XP required to advance from level, or 0 at the level cap."""
    level = int(level)
    if level >= LEVEL_CAP:
        return 0
    if level <= 20:
        return math.floor(140 + 45 * level + 5 * level * (level - 1))
    return xp_to_next(20) + 90 * (level - 20)


def _tier_multiplier(level_difference):
    if level_difference >= 3:
        return 1.35
    if level_difference >= 1:
        return 1.15
    if level_difference == 0:
        return 1.0
    if level_difference >= -2:
        return 0.55
    if level_difference >= -5:
        return 0.20
    return 0.0


def battle_xp(player_level, opponent_level, outcome):
    """Return XP for a win, draw, or loss against an opponent."""
    base_xp = {"win": WIN_XP_BASE, "draw": DRAW_XP_BASE, "loss": LOSS_XP_BASE}.get(outcome)
    if base_xp is None:
        raise ValueError("Unknown battle outcome")
    if int(player_level) >= LEVEL_CAP:
        return 0
    return int(round(base_xp * _tier_multiplier(int(opponent_level) - int(player_level))))


def apply_xp(fighter, amount, restore_hp=False):
    """Apply XP and level-ups, optionally restoring HP outside combat."""
    if fighter.level >= LEVEL_CAP:
        fighter.xp = 0
        return 0
    fighter.xp += max(0, int(amount))
    levels_gained = 0
    while fighter.level < LEVEL_CAP:
        threshold = xp_to_next(fighter.level)
        if fighter.xp < threshold:
            break
        current_hp = fighter.hp
        fighter.xp -= threshold
        fighter.level += 1
        fighter.stat_points += 6
        fighter.recalculate_parameters()
        fighter.hp = fighter.max_hp if restore_hp else min(current_hp, fighter.max_hp)
        levels_gained += 1
    if fighter.level >= LEVEL_CAP:
        fighter.level = LEVEL_CAP
        fighter.xp = 0
    return levels_gained
