"""Боевые формулы карты мира: игрок и скелет."""

import math
import random

BASE_ATTACK_REACH = 45.0
REACH_PER_INTUITION = 1.0

BASE_MOVE_SPEED = 160.0
MOVE_SPEED_PER_AGILITY = 5.0

DODGE_PER_AGILITY = 5.0
DODGE_REDUCTION_PER_OPPONENT_AGILITY = 3.0
MAX_DODGE_CHANCE = 70.0

CRIT_PER_INTUITION = 5.0
CRIT_REDUCTION_PER_OPPONENT_INTUITION = 3.0
MAX_CRIT_CHANCE = 95.0
CRIT_DAMAGE_MULTIPLIER = 1.5

DAMAGE_PER_STRENGTH = 2
HP_PER_ENDURANCE = 12
DEFENSE_PER_ENDURANCE = 1
HP_REGEN_PER_ENDURANCE = 1.0 / 3.0
DAMAGE_PER_WISDOM = 2
MANA_PER_INTELLECT = 6
MANA_REGEN_PER_INTELLECT = 1.0
MAX_BLOCK_CHANCE = 70.0

BASE_ATTACK_WINDUP = 0.5  # замах до удара, сек
WINDUP_REDUCTION_PER_INTUITION = 0.02
BASE_ATTACK_BACKSWING = 0.5  # откат после удара, сек
BACKSWING_REDUCTION_PER_AGILITY = 0.02


def _stat(fighter, name):
    return int(getattr(fighter, name, 0) or 0)


def _weapon_range(fighter):
    return fighter.weapon_damage or (0, 0)


def get_block_chance(defender):
    """Шанс блока от экипировки защитника, не выше 70%."""
    modifiers = getattr(defender, "equipment_stat_modifiers", {}) or {}
    return max(0.0, min(MAX_BLOCK_CHANCE, float(modifiers.get("block", 0))))


def get_attack_reach(fighter):
    """Дальность удара в пикселях: база 45 + 1 за очко интуиции."""
    return BASE_ATTACK_REACH + REACH_PER_INTUITION * _stat(fighter, "intuition")


def get_attack_windup(fighter):
    """Замах до удара: 0.5 с минус 0.02 с за очко интуиции, не меньше 0."""
    return max(0.0, BASE_ATTACK_WINDUP - WINDUP_REDUCTION_PER_INTUITION * _stat(fighter, "intuition"))


def get_attack_backswing(fighter):
    """Откат после удара: 0.5 с минус 0.02 с за очко ловкости, не меньше 0."""
    return max(0.0, BASE_ATTACK_BACKSWING - BACKSWING_REDUCTION_PER_AGILITY * _stat(fighter, "agility"))


def get_move_speed(fighter, carry_multiplier=1.0):
    """Скорость передвижения в пикселях/с с учётом веса переноски."""
    speed = BASE_MOVE_SPEED + MOVE_SPEED_PER_AGILITY * _stat(fighter, "agility")
    return speed * float(carry_multiplier)


def get_world_dodge_chance(defender, attacker):
    """Шанс уворота защитника: 5% за ловкость защитника минус 3% за ловкость атакующего."""
    chance = (
        DODGE_PER_AGILITY * _stat(defender, "agility")
        - DODGE_REDUCTION_PER_OPPONENT_AGILITY * _stat(attacker, "agility")
    )
    return max(0.0, min(MAX_DODGE_CHANCE, chance))


def get_own_dodge_percent(fighter):
    """Уворот без соперника (для панели): 5% за очко ловкости, не выше 70%."""
    return max(0.0, min(MAX_DODGE_CHANCE, DODGE_PER_AGILITY * _stat(fighter, "agility")))


def get_own_crit_percent(fighter):
    """Крит без соперника (для панели): 5% за очко интуиции, не выше 95%."""
    return max(0.0, min(MAX_CRIT_CHANCE, CRIT_PER_INTUITION * _stat(fighter, "intuition")))


def get_world_crit_chance(attacker, defender):
    """Шанс крита атакующего: 5% за интуицию минус 3% за интуицию защитника."""
    chance = (
        CRIT_PER_INTUITION * _stat(attacker, "intuition")
        - CRIT_REDUCTION_PER_OPPONENT_INTUITION * _stat(defender, "intuition")
    )
    return max(0.0, min(MAX_CRIT_CHANCE, chance))


def get_world_base_damage(fighter, rng=None):
    """Базовый урон удара: 2 за очко силы плюс случайный урон оружия."""
    strength_damage = DAMAGE_PER_STRENGTH * _stat(fighter, "strength")
    low, high = _weapon_range(fighter)
    if low == high or rng is None:
        weapon_damage = high
    else:
        weapon_damage = rng.randint(low, high)
    return strength_damage + weapon_damage


def get_defense(fighter):
    """Защита: 1 единица снижает входящий урон на 1 (равна выносливости)."""
    return DEFENSE_PER_ENDURANCE * _stat(fighter, "endurance")


def get_world_max_hp(fighter, equipment_hp=0):
    """Максимум HP: 12 за очко выносливости плюс бонус экипировки."""
    return HP_PER_ENDURANCE * _stat(fighter, "endurance") + int(equipment_hp)


def get_hp_regen_per_second(fighter):
    """Регенерация HP в секунду: 1 HP за 3 секунды на каждое очко выносливости."""
    return HP_REGEN_PER_ENDURANCE * _stat(fighter, "endurance")


def get_world_max_mana(fighter, equipment_mp=0):
    """Максимум маны: 6 за очко интеллекта плюс бонус экипировки."""
    return MANA_PER_INTELLECT * _stat(fighter, "intellect") + int(equipment_mp)


def get_mana_regen_per_second(fighter):
    """Регенерация маны: 1 в секунду на каждое очко интеллекта."""
    return MANA_REGEN_PER_INTELLECT * _stat(fighter, "intellect")


def get_world_magic_damage(fighter):
    """Магический урон: 2 за очко мудрости (формула; магических атак на карте пока нет)."""
    return DAMAGE_PER_WISDOM * _stat(fighter, "wisdom")


BLOCK_FRONT_HALF_ANGLE = math.radians(67.5)  # передний сектор: взгляд ±1 направление из 8 (±67.5°)


def is_attack_from_front(defender_facing, attack_vector):
    """True, если атака пришла в лицо или с двух боковых направлений (3 из 8 направлений).

    defender_facing — угол взгляда защитника (радианы, atan2);
    attack_vector — (dx, dy) от защитника к атакующему.
    """
    dx, dy = attack_vector
    if not dx and not dy:
        return True
    diff = math.atan2(dy, dx) - defender_facing
    diff = (diff + math.pi) % (2 * math.pi) - math.pi
    return abs(diff) <= BLOCK_FRONT_HALF_ANGLE + 1e-9


def resolve_world_melee_attack(attacker, defender, rng=None, defender_facing=None, attack_vector=None):
    """Удар ближнего боя на карте мира.

    Порядок: уворот → блок (только спереди и не-крит) → урон → защита.
    Блок срабатывает, только если переданы взгляд защитника и вектор атаки и удар пришёл
    в переднюю зону (3 из 8 направлений). Крит ×1.5 к базовому урону;
    при блоке крит наносит половину урона.
    """
    rng = rng or random
    result = {
        "outcome": "hit",
        "damage": 0,
        "critical": False,
        "base_damage": 0,
        "defense": 0,
        "reach": get_attack_reach(attacker),
    }

    if rng.uniform(0, 100) < get_world_dodge_chance(defender, attacker):
        result["outcome"] = "dodge"
        return result

    base_damage = get_world_base_damage(attacker, rng)
    result["base_damage"] = base_damage
    critical = rng.uniform(0, 100) < get_world_crit_chance(attacker, defender)
    result["critical"] = critical

    # Шанс блока бросаем всегда, чтобы число случайных вызовов не зависело от направления
    block_roll = rng.uniform(0, 100) < get_block_chance(defender)
    from_front = (
        defender_facing is None
        or attack_vector is None
        or is_attack_from_front(defender_facing, attack_vector)
    )
    blocked = block_roll and from_front
    if blocked:
        if not critical:
            result["outcome"] = "block"
            return result
        base_damage = math.ceil(base_damage * CRIT_DAMAGE_MULTIPLIER / 2)
    elif critical:
        base_damage = math.ceil(base_damage * CRIT_DAMAGE_MULTIPLIER)

    defense = get_defense(defender)
    result["defense"] = defense
    result["damage"] = max(0, base_damage - defense)
    return result
