"""Character carried-weight display and movement rules."""

from combat.character_stats import calculate_carry_capacity


GREEN = (115, 215, 125)
NEUTRAL = (220, 210, 190)
YELLOW = (245, 205, 80)
RED = (235, 95, 85)


def carried_weight_kg(inventory=(), equipment=None):
    """Sum backpack and equipped item weights, skipping two-handed display shadows."""
    total = 0.0
    for item in inventory or ():
        total += float(item.get("weight", 0) or 0) * int(item.get("quantity", 1) or 1)
    for item in (equipment or {}).values():
        if item.get("_two_handed_shadow"):
            continue
        total += float(item.get("weight", 0) or 0)
    return round(total, 2)


def load_ratio(carried_kg, capacity_kg):
    capacity = max(0.0, float(capacity_kg or 0))
    if capacity == 0:
        return 0.0
    return max(0.0, float(carried_kg or 0)) / capacity


def load_color(carried_kg, capacity_kg):
    ratio = load_ratio(carried_kg, capacity_kg)
    if ratio <= 0.30:
        return GREEN
    if ratio > 0.80:
        return RED
    if ratio > 0.60:
        return YELLOW
    return NEUTRAL


def movement_speed_multiplier(carried_kg, capacity_kg):
    ratio = load_ratio(carried_kg, capacity_kg)
    if ratio > 0.80:
        return 0.30
    if ratio > 0.60:
        return 0.50
    if ratio > 0.30:
        return 0.70
    return 1.0


def character_carry_capacity(character):
    character = character or {}
    stats = character.get("stats", {})
    bonuses = character.get("equipment_bonuses", {})
    strength = int(stats.get("strength", 0)) + int(bonuses.get("strength", 0))
    endurance = int(stats.get("endurance", 0)) + int(bonuses.get("endurance", 0))
    return calculate_carry_capacity(strength, endurance)


def character_movement_speed_multiplier(character):
    character = character or {}
    return movement_speed_multiplier(
        character.get("carried_weight_kg", 0),
        character_carry_capacity(character),
    )
