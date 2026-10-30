from types import SimpleNamespace

from kaloda.combat.character_stats import (
    adjust_stats,
    calculate_max_hp,
    is_debug_unlimited,
    minimum_endurance,
    normalize_profession_type,
)
from kaloda.combat.mechanics import (
    get_critical_chance,
    get_critical_damage_multiplier,
    get_dodge_chance,
    weapon_damage_range,
)


DEFAULT_STATS = {
    "strength": 2,
    "agility": 2,
    "intuition": 2,
    "wisdom": 2,
    "intellect": 2,
    "harmony": 2,
    "endurance": 2,
}

DERIVED_COLORS = {
    "Урон": (255, 255, 255),
    "Маг Урон": (190, 150, 255),
    "Уворот": (150, 220, 255),
    "Крит": (255, 90, 90),
    "HP": (110, 235, 120),
    "Блок": (150, 210, 255),
}

STAT_ROWS = (
    ("strength", "Сила", "Урон"),
    ("agility", "Ловкость", "Уворот"),
    ("intuition", "Интуиция", "Крит"),
    ("wisdom", "Мудрость", "Маг Урон"),
    ("intellect", "Интеллект", None),
    ("harmony", "Гармония", None),
    ("endurance", "Выносливость", "Блок"),
)


def normalize_character_profile(profile, *, title=None, kind="player"):
    """Приводит данные персонажа из UI, сети или боя к единому формату."""
    data = profile or {}
    if hasattr(data, "stats") and not isinstance(data, dict):
        profile_dict = {
            "id": getattr(data, "id", getattr(data, "character_id", None)),
            "character_id": getattr(data, "character_id", getattr(data, "id", None)),
            "type": getattr(data, "type", "warrior"),
            "profession_type": getattr(data, "profession_type", getattr(data, "type", "warrior")),
            "name": getattr(data, "name", "Персонаж"),
            "level": getattr(data, "level", 1),
            "xp": getattr(data, "xp", 0),
            "hp": getattr(data, "hp", 0),
            "max_hp": getattr(data, "max_hp", 0),
            "mp": getattr(data, "mp", 0),
            "max_mp": getattr(data, "max_mp", 0),
            "stats": dict(getattr(data, "stats", {})),
            "stat_points": getattr(data, "stat_points", 0),
            "coins": getattr(data, "coins", 0),
            "inventory": dict(getattr(data, "inventory", {})),
            "equipment": dict(getattr(data, "equipment", {})),
            "equipment_bonuses": dict(getattr(data, "equipment_stat_modifiers", {})),
            "max_hp_includes_equipment": True,
            "kind": kind,
        }
    elif isinstance(data, dict):
        profile_dict = {
            "id": data.get("id", data.get("character_id", None)),
            "character_id": data.get("character_id", data.get("id", None)),
            "type": data.get("type", "warrior"),
            "profession_type": data.get("profession_type", data.get("type", "warrior")),
            "name": data.get("name", "Персонаж"),
            "level": int(data.get("level", 1)),
            "xp": data.get("xp", 0),
            "hp": data.get("hp", data.get("current_hp", 0)),
            "max_hp": data.get("max_hp", data.get("hp_max", 0)),
            "mp": data.get("mp", data.get("current_mp", 0)),
            "max_mp": data.get("max_mp", data.get("mp_max", 0)),
            "stats": dict(data.get("stats", {})),
            "stat_points": data.get("stat_points", 0),
            "coins": int(data.get("coins", 0)),
            "inventory": dict(data.get("inventory", {})),
            "equipment": dict(data.get("equipment", {})),
            "equipment_bonuses": dict(data.get("equipment_bonuses", {})),
            "max_hp_includes_equipment": bool(data.get("max_hp_includes_equipment", False)),
            "kind": kind,
        }
    else:
        profile_dict = {
            "id": None,
            "character_id": None,
            "type": "warrior",
            "profession_type": "warrior",
            "name": "Персонаж",
            "level": 1,
            "xp": 0,
            "hp": 0,
            "max_hp": 0,
            "mp": 0,
            "max_mp": 0,
            "stats": {},
            "stat_points": 0,
            "coins": 0,
            "inventory": {},
            "equipment": {},
            "equipment_bonuses": {},
            "max_hp_includes_equipment": False,
            "kind": kind,
        }

    profile_dict["max_hp"] = max(int(profile_dict["max_hp"]), 1)
    profile_dict["type"] = normalize_profession_type(profile_dict["type"])
    profile_dict["profession_type"] = normalize_profession_type(profile_dict["profession_type"])
    profile_dict["max_mp"] = max(int(profile_dict["max_mp"]), 1)
    profile_dict["hp"] = min(int(profile_dict["hp"]), profile_dict["max_hp"])
    profile_dict["mp"] = min(int(profile_dict["mp"]), profile_dict["max_mp"])
    profile_dict["title"] = title
    if not profile_dict["stats"]:
        profile_dict["stats"] = dict(DEFAULT_STATS)
    if profile_dict["type"] == "assassin":
        old_max_hp = int(profile_dict["max_hp"])
        old_hp = int(profile_dict["hp"])
        assassin_max_hp = calculate_max_hp(
            profile_dict["level"],
            profile_dict["stats"].get("endurance", minimum_endurance(profile_dict["level"])),
            "assassin",
        )
        if profile_dict["max_hp_includes_equipment"]:
            assassin_max_hp += int(profile_dict["equipment_bonuses"].get("hp", 0))
        profile_dict["max_hp"] = max(1, assassin_max_hp)
        if old_max_hp > 0 and old_hp < old_max_hp:
            profile_dict["hp"] = int(old_hp * profile_dict["max_hp"] / old_max_hp)
        else:
            profile_dict["hp"] = profile_dict["max_hp"]
        profile_dict["hp"] = min(max(0, profile_dict["hp"]), profile_dict["max_hp"])

    return profile_dict


def profile_from_fighter(fighter):
    """Создаёт профиль карточки из действующего бойца без привязки к рендеру."""
    return {
        "id": getattr(fighter, "id", None),
        "character_id": getattr(fighter, "character_id", getattr(fighter, "id", None)),
        "name": getattr(fighter, "name", "Персонаж"),
        "type": getattr(fighter, "profession_type", "warrior"),
        "profession_type": getattr(fighter, "profession_type", "warrior"),
        "level": getattr(fighter, "level", 1),
        "xp": getattr(fighter, "xp", 0),
        "hp": getattr(fighter, "hp", 0),
        "max_hp": getattr(fighter, "max_hp", 0),
        "mp": getattr(fighter, "mp", 0),
        "max_mp": getattr(fighter, "max_mp", 0),
        "stats": getattr(fighter, "stats", {}),
        "stat_points": getattr(fighter, "stat_points", 0),
        "equipment": dict(getattr(fighter, "equipment", {})),
        "equipment_bonuses": dict(getattr(fighter, "equipment_stat_modifiers", {})),
        "max_hp_includes_equipment": True,
    }


def effective_stats(profile):
    stats = dict(profile.get("stats", {}))
    for stat_name, value in (profile.get("equipment_bonuses") or {}).items():
        if stat_name in stats:
            stats[stat_name] = int(stats[stat_name]) + int(value)
    return stats


def displayed_hp_values(profile):
    base_max_hp = int(profile.get("max_hp", 1))
    hp_bonus = 0 if profile.get("max_hp_includes_equipment") else int(
        (profile.get("equipment_bonuses") or {}).get("hp", 0)
    )
    maximum = max(1, base_max_hp + hp_bonus)
    current = int(profile.get("hp", 0))
    if hp_bonus > 0 and current >= base_max_hp:
        current += hp_bonus
    return min(current, maximum), maximum


def adjust_profile_stat(profile, stat_name, delta):
    """Меняет одну характеристику профиля и возвращает успешность операции."""
    updated_state = adjust_stats(
        profile["stats"],
        profile["stat_points"],
        profile["hp"],
        profile["max_hp"],
        profile["level"],
        stat_name,
        delta,
        character_id=profile.get("character_id", profile.get("id")),
    )
    if updated_state is None:
        return False

    profile["stats"].update(updated_state.pop("stats"))
    profile.update(updated_state)
    return True


def adjust_profile_level(profile, delta):
    """Напрямую меняет уровень тестового персонажа, минуя начисление опыта."""
    if not is_debug_unlimited(profile.get("character_id", profile.get("id"))):
        return False
    new_level = max(1, min(1000, int(profile["level"]) + delta))
    if new_level == profile["level"]:
        return False
    profile["level"] = new_level
    profile["max_hp"] = calculate_max_hp(new_level, profile["stats"]["endurance"])
    profile["hp"] = profile["max_hp"]
    return True


def derived_values(profile, opponent=None):
    """Возвращает значения боя для отображения в карточке персонажа."""
    fighter_stats = effective_stats(profile)
    for stat_name, default in DEFAULT_STATS.items():
        fighter_stats.setdefault(stat_name, default)
    fighter = SimpleNamespace(
        **fighter_stats,
        profession_type=profile.get("profession_type", profile.get("type", "warrior")),
        equipment_stat_modifiers=profile.get("equipment_bonuses", {}),
    )
    weapon_damage = weapon_damage_range(profile.get("equipment"))

    def damage_with_weapon(base_damage):
        base_damage = max(1, int(base_damage))
        if weapon_damage is None:
            return base_damage
        minimum, maximum = weapon_damage
        minimum += base_damage
        maximum += base_damage
        return minimum if minimum == maximum else f"{minimum}-{maximum}"

    magic_damage = None
    if normalize_profession_type(fighter.profession_type) in {"mage", "necromancer"}:
        fighter_stats.setdefault("wisdom", 2)
        fighter.wisdom = fighter_stats["wisdom"]
        magic_damage = damage_with_weapon(fighter.wisdom)

    if opponent is None:
        base_damage = max(1, int(fighter.strength))
        values = {
            "Урон": damage_with_weapon(base_damage),
            "Уворот": f"{int(get_dodge_chance(None, fighter))}%",
            "Крит": (
                f"{int(get_critical_chance(fighter, None))}% × "
                f"{int(get_critical_damage_multiplier(fighter) * 100)}%"
            ),
            "HP": displayed_hp_values(profile)[1],
        }
        if magic_damage is not None:
            values["Маг Урон"] = magic_damage
        return values

    opponent = normalize_character_profile(opponent)
    enemy_stats = effective_stats(opponent)
    for stat_name, default in DEFAULT_STATS.items():
        enemy_stats.setdefault(stat_name, default)
    enemy = SimpleNamespace(
        **enemy_stats,
        profession_type=opponent.get("profession_type", opponent.get("type", "warrior")),
        equipment_stat_modifiers=opponent.get("equipment_bonuses", {}),
    )
    values = {
        "Урон": max(1, int(fighter.strength * 2 - enemy.endurance * 0.5)),
        "Уворот": f"{int(get_dodge_chance(enemy, fighter))}%",
        "Крит": (
            f"{int(get_critical_chance(fighter, enemy))}% × "
            f"{int(get_critical_damage_multiplier(fighter) * 100)}%"
        ),
        "HP": displayed_hp_values(profile)[1],
    }
    if magic_damage is not None:
        values["Маг Урон"] = magic_damage
    return values
