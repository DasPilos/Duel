import random


def roll_2d6():
    return random.randint(1, 6), random.randint(1, 6)


def clamp_chance(value, maximum=95.0):
    return max(0.0, min(maximum, value))


# Базовый шанс крита не зависит от статов — интуиция усиливает только урон крита.
BASE_CRITICAL_CHANCE = 5.0
# Базовый множитель урона крита без бонусов от интуиции.
BASE_CRITICAL_MULTIPLIER = 1.5
CRITICAL_DAMAGE_PER_INTUITION = 0.05
DODGE_CHANCE_PER_AGILITY = 2.0


def get_dodge_chance(attacker, defender):
    """Return the defender's dodge chance — depends on agility and class base dodge."""
    from kaloda.combat.character_stats import get_profession_data

    # Базовый уворот от ловкости
    dodge_from_agility = defender.agility * DODGE_CHANCE_PER_AGILITY

    # Добавить базовый уворот класса
    base_dodge = 0
    if hasattr(defender, 'profession_type') and defender.profession_type:
        prof_data = get_profession_data(defender.profession_type)
        if prof_data:
            base_dodge = prof_data.get("base_dodge", 0)

    equipment_dodge = 0
    if hasattr(defender, "equipment_stat_modifiers") and defender.equipment_stat_modifiers:
        equipment_dodge = float(defender.equipment_stat_modifiers.get("dodge", 0))

    total_dodge = dodge_from_agility + base_dodge + equipment_dodge
    return clamp_chance(total_dodge, 70.0)


def get_block_chance(defender):
    """Return the equipped block chance, capped like other defensive chances."""
    modifiers = getattr(defender, "equipment_stat_modifiers", {}) or {}
    return clamp_chance(float(modifiers.get("block", 0)), 70.0)


def get_critical_chance(attacker, defender):
    """Return class base critical chance; stats do not modify it."""
    if attacker is None:
        return clamp_chance(BASE_CRITICAL_CHANCE)
    from kaloda.combat.character_stats import get_profession_data

    profession = get_profession_data(getattr(attacker, "profession_type", None))
    base_chance = profession.get("base_crit", BASE_CRITICAL_CHANCE) if profession else BASE_CRITICAL_CHANCE
    return clamp_chance(base_chance)


def weapon_damage_range(equipment):
    """(мин, макс) урона надетого оружия или None. Урон хранится в effects["damage"] = [мин, макс]."""
    weapon = (equipment or {}).get("weapon") or {}
    damage = (weapon.get("effects") or {}).get("damage")
    if not damage or damage == [0, 0] or damage == (0, 0):
        shield = (equipment or {}).get("shield") or {}
        shield_damage = (shield.get("effects") or {}).get("damage")
        if shield_damage and shield_damage != [0, 0] and shield_damage != (0, 0):
            damage = shield_damage
    if not damage:
        return None
    if isinstance(damage, (int, float)):
        damage = (damage, damage)
    low, high = int(damage[0]), int(damage[-1])
    return min(low, high), max(low, high)


def weapon_fixed_damage(equipment):
    """Фиксированный урон оружия за удар: максимум диапазона, 0 без оружия"""
    damage = weapon_damage_range(equipment)
    return damage[1] if damage else 0


def get_critical_damage_multiplier(attacker):
    """Return the critical damage multiplier boosted by the attacker's own intuition."""
    from kaloda.combat.character_stats import get_profession_data

    profession = get_profession_data(getattr(attacker, "profession_type", None))
    class_bonus = profession.get("base_crit_damage_bonus", 0) if profession else 0
    return (
        BASE_CRITICAL_MULTIPLIER
        + class_bonus / 100
        + attacker.intuition * CRITICAL_DAMAGE_PER_INTUITION
    )
