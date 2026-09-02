import random


def roll_2d6():
    return random.randint(1, 6), random.randint(1, 6)


def clamp_chance(value, maximum=95.0):
    return max(0.0, min(maximum, value))


def get_dodge_chance(attacker, defender):
    return clamp_chance(
        defender.agility * 5 - attacker.agility * 3,
        70.0,
    )


def get_critical_chance(attacker, defender):
    """Return critical chance after the defender's anti-critical reduction."""
    return clamp_chance(
        attacker.intuition * 5 - defender.intuition * 3
    )
