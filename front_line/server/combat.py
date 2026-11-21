"""Front Line-only equipment effects for melee combat."""

import math
import random

from combat import world_stats
from server.world_map import TILE

# Дальность в игре — единицы: 1 тайл = 100 ед. Пиксели существуют только внутри сервера и клиента.
RANGE_UNITS_PER_TILE = 100
BASE_ATTACK_RANGE_UNITS = {"warrior": 100, "archer": 500, "mage": 500}
RANGE_UNITS_PER_INTUITION = 5
BASE_INTUITION = 3
MOB_ATTACK_RANGE_UNITS = 100
# Радиус тела моба для дальности (ближе к видимому спрайту, чем радиус коллизий 16 px). Коллизии не меняются.
MOB_RANGE_HULL_PX = 20.0
HERO_BODY_RADIUS_PX = 10.0
# Скорость снаряда по классу, ед. в секунду: стрела лучника 600, сгусток мага 500.
PROJECTILE_SPEED_UNITS = {"archer": 600, "mage": 500}
PROJECTILE_SPEED_DEFAULT_UNITS = 600
# Снаряд, который не дошёл за это время, пропадает (сгусток взрывается на месте).
PROJECTILE_MAX_SECONDS = 3.0
# Поворот героя к цели перед ударом, рад/с: 180° — за ≈0,26 с.
HERO_TURN_RATE = 12.0
# Скорость героя Front Line относительно мирового расчёта (ближе к Dota 2).
HERO_MOVE_SPEED_SCALE = 0.6
# Броня: 8 за очко выносливости; снижение урона = k·A / (1 + k·A), k = 0,06 (при выносливости 4 ≈66%).
ARMOR_PER_ENDURANCE = 8
ARMOR_REDUCTION_RATE = 0.06
PROJECTILE_KIND = {"archer": "arrow", "mage": "orb"}
# Нижняя граница замаха и отката, сек. Без неё при очень высокой скорости атаки удар идёт каждый кадр,
# и стрелы летят пачкой. Анимация героя ускоряется до этого предела; скорость снарядов не меняется.
MIN_ATTACK_WINDUP = 0.05
# Допуск на конце замаха: цель у края дальности не даёт промах из-за сдвига на тик, px.
ATTACK_RANGE_BUFFER_PX = 8.0
# Базовый замах по классу, сек (до снижения интуицией). Анимация натяжения идёт на всё время замаха.
FRONT_LINE_BASE_WINDUP = {"warrior": 1.0, "archer": 1.4, "mage": 2.4}
# Автоатака Front Line выключена: герой бьёт только по приказу (клик по мобу или атака-движение).
AUTO_ATTACK_ENABLED = False
# Автоатака начинается только когда герой стоит: приказ движения важнее автоатаки, как в Dota 2.
AUTO_ATTACK_IDLE_SECONDS = 0.5
MIN_ATTACK_BACKSWING = 0.05
# Замах героев Front Line уменьшен в 2 раза, откат увеличен в 2 раза (решение владельца).
FRONT_LINE_WINDUP_SCALE = 0.5
FRONT_LINE_BACKSWING_SCALE = 2.0
# Взрыв мага: радиус 100 ед. (1 тайл) вокруг точки попадания, бьёт всех мобов в зоне, своих героев не задевает.
MAGE_AREA_RADIUS_UNITS = 50


def mob_range_hull_px(is_boss):
    return MOB_RANGE_HULL_PX * (4.0 if is_boss else 1.0)


def range_units_to_px(units):
    return float(units) * TILE / RANGE_UNITS_PER_TILE


def hero_attack_range_units(fighter):
    profession = getattr(fighter, "profession_type", "warrior")
    base = BASE_ATTACK_RANGE_UNITS.get(profession, BASE_ATTACK_RANGE_UNITS["warrior"])
    intuition = world_stats._stat(fighter, "intuition")
    return max(0, base + RANGE_UNITS_PER_INTUITION * (intuition - BASE_INTUITION))


def attack_distance_px(ax, ay, tx, ty, target_radius):
    """Расстояние от центра атакующего до края круглого тела цели."""
    return max(0.0, math.hypot(tx - ax, ty - ay) - target_radius)


def projectile_kind(profession):
    return PROJECTILE_KIND.get(profession, "")


def projectile_speed_px(profession=None):
    units = PROJECTILE_SPEED_UNITS.get(profession, PROJECTILE_SPEED_DEFAULT_UNITS)
    return range_units_to_px(units)


def area_radius_px():
    return range_units_to_px(MAGE_AREA_RADIUS_UNITS)


def _effect_total(fighter, effect_name):
    total = 0
    for item in (getattr(fighter, "equipment", {}) or {}).values():
        if not isinstance(item, dict):
            continue
        effects = item.get("effects") or {}
        if isinstance(effects, dict):
            total += int(effects.get(effect_name, 0))
    return total


def _critical_multiplier(attacker):
    power = 0
    for item in (getattr(attacker, "equipment", {}) or {}).values():
        if not isinstance(item, dict):
            continue
        effects = item.get("effects") or {}
        if isinstance(effects, dict) and "crit_power" in effects:
            power += int(effects["crit_power"]) - 50
    return max(1.0, world_stats.CRIT_DAMAGE_MULTIPLIER + power / 100.0)


def damage_after_armor(base, armor):
    """Урон после брони в процентах с убывающей отдачей; при попадании не меньше 1."""
    if base <= 0:
        return 0
    reduction = ARMOR_REDUCTION_RATE * armor / (1 + ARMOR_REDUCTION_RATE * armor)
    return max(1, int(round(base * (1 - reduction))))


def resolve_melee_attack(attacker, defender, rng=None, defender_facing=None, attack_vector=None):
    rng = rng or random
    result = {
        "outcome": "hit",
        "damage": 0,
        "critical": False,
        "base_damage": 0,
        "defense": 0,
        "reach": world_stats.get_attack_reach(attacker),
    }

    dodge_chance = (
        world_stats.get_world_dodge_chance(defender, attacker)
        + float((getattr(defender, "equipment_stat_modifiers", {}) or {}).get("dodge", 0))
        - _effect_total(attacker, "anti_dodge")
    )
    if rng.uniform(0, 100) < max(0.0, min(world_stats.MAX_DODGE_CHANCE, dodge_chance)):
        result["outcome"] = "dodge"
        return result

    base_damage = world_stats.get_world_base_damage(attacker, rng)
    result["base_damage"] = base_damage
    crit_chance = (
        world_stats.get_world_crit_chance(attacker, defender)
        + _effect_total(attacker, "crit")
        - _effect_total(defender, "anti_crit")
    )
    critical = rng.uniform(0, 100) < max(0.0, min(world_stats.MAX_CRIT_CHANCE, crit_chance))
    result["critical"] = critical

    block_roll = rng.uniform(0, 100) < world_stats.get_block_chance(defender)
    from_front = (
        defender_facing is None
        or attack_vector is None
        or world_stats.is_attack_from_front(defender_facing, attack_vector)
    )
    if block_roll and from_front:
        result["outcome"] = "block"
        return result
    if critical:
        base_damage = math.ceil(base_damage * _critical_multiplier(attacker))

    defense = world_stats.get_defense(defender)
    result["defense"] = defense
    result["damage"] = damage_after_armor(base_damage, defense * ARMOR_PER_ENDURANCE)
    return result


def lifesteal_percent(fighter):
    return min(100, max(0, _effect_total(fighter, "lifesteal_percent")))


def aura_lifesteal_percent(fighter, target, distance):
    percent = 0
    for item in (getattr(fighter, "equipment", {}) or {}).values():
        if not isinstance(item, dict):
            continue
        effects = item.get("effects") or {}
        aura = effects.get("aura", {}) if isinstance(effects, dict) else {}
        if not isinstance(aura, dict) or aura.get("type") != "vampirism" or aura.get("target") != target:
            continue
        if distance <= int(aura.get("radius_px", 0)):
            percent += int(aura.get("lifesteal_percent", 0))
    return min(100, max(0, percent))


def apply_lifesteal(fighter, damage, percent):
    healed = min(
        max(0, int(fighter.max_hp) - int(fighter.hp)),
        max(0, int(damage * min(100, max(0, percent)) / 100)),
    )
    fighter.hp += healed
    return healed
