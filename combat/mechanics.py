import random

def roll_2d6():
    return random.randint(1, 6), random.randint(1, 6)

def roll_critical_d8():
    return random.choice([1.5, 1.5, 2, 2, 2, 2, 3, 4])

def clamp_chance(value):
    return max(0.0, min(95.0, value))

def get_dodge_chance(attacker, defender):
    return clamp_chance(
        defender.agility * 5 - attacker.agility * 3 - attacker.endurance
    )

def get_critical_chance(attacker, defender):
    return clamp_chance(
        attacker.intuition * 5 - defender.intuition * 3 - defender.endurance
    )
