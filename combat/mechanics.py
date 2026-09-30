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
    from combat.character_stats import get_profession_data

    # Базовый уворот от ловкости
    dodge_from_agility = defender.agility * DODGE_CHANCE_PER_AGILITY

    # Добавить базовый уворот класса
    base_dodge = 0
    if hasattr(defender, 'profession_type') and defender.profession_type:
        prof_data = get_profession_data(defender.profession_type)
        if prof_data:
            base_dodge = prof_data.get("base_dodge", 0)

    total_dodge = dodge_from_agility + base_dodge
    return clamp_chance(total_dodge, 70.0)


def get_critical_chance(attacker, defender):
    """Return the base critical chance — no longer affected by either fighter's stats."""
    return clamp_chance(BASE_CRITICAL_CHANCE)


def weapon_damage_range(equipment):
    """(мин, макс) урона надетого оружия или None. Урон хранится в effects["damage"] = [мин, макс]."""
    weapon = (equipment or {}).get("weapon") or {}
    damage = (weapon.get("effects") or {}).get("damage")
    if not damage:
        return None
    if isinstance(damage, (int, float)):
        damage = (damage, damage)
    low, high = int(damage[0]), int(damage[-1])
    return min(low, high), max(low, high)


def get_critical_damage_multiplier(attacker):
    """Return the critical damage multiplier boosted by the attacker's own intuition."""
    return BASE_CRITICAL_MULTIPLIER + attacker.intuition * CRITICAL_DAMAGE_PER_INTUITION
