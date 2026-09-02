from types import SimpleNamespace

from combat.character_stats import adjust_stats, calculate_max_hp, is_debug_unlimited, minimum_endurance
from combat.mechanics import get_critical_chance, get_dodge_chance


DEFAULT_STATS = {
    "strength": 5,
    "agility": 5,
    "intuition": 5,
    "endurance": 5,
}


def normalize_character_profile(profile, *, title=None, kind="player"):
    """Приводит данные персонажа из UI, сети или боя к единому формату."""
    data = profile or {}
    if hasattr(data, "stats") and not isinstance(data, dict):
        profile_dict = {
            "id": getattr(data, "id", getattr(data, "character_id", None)),
            "character_id": getattr(data, "character_id", getattr(data, "id", None)),
            "name": getattr(data, "name", "Персонаж"),
            "level": getattr(data, "level", 1),
            "xp": getattr(data, "xp", 0),
            "hp": getattr(data, "hp", 0),
            "max_hp": getattr(data, "max_hp", 0),
            "mp": getattr(data, "mp", 0),
            "max_mp": getattr(data, "max_mp", 0),
            "stats": dict(getattr(data, "stats", {})),
            "stat_points": getattr(data, "stat_points", 0),
            "copper": getattr(data, "copper", 0),
            "silver": getattr(data, "silver", 0),
            "gold": getattr(data, "gold", 0),
            "inventory": dict(getattr(data, "inventory", {})),
            "kind": kind,
        }
    elif isinstance(data, dict):
        profile_dict = {
            "id": data.get("id", data.get("character_id", None)),
            "character_id": data.get("character_id", data.get("id", None)),
            "name": data.get("name", "Персонаж"),
            "level": int(data.get("level", 1)),
            "xp": data.get("xp", 0),
            "hp": data.get("hp", data.get("current_hp", 0)),
            "max_hp": data.get("max_hp", data.get("hp_max", 0)),
            "mp": data.get("mp", data.get("current_mp", 0)),
            "max_mp": data.get("max_mp", data.get("mp_max", 0)),
            "stats": dict(data.get("stats", {})),
            "stat_points": data.get("stat_points", 0),
            "copper": int(data.get("copper", 0)),
            "silver": int(data.get("silver", 0)),
            "gold": int(data.get("gold", 0)),
            "inventory": dict(data.get("inventory", {})),
            "kind": kind,
        }
    else:
        profile_dict = {
            "id": None,
            "character_id": None,
            "name": "Персонаж",
            "level": 1,
            "xp": 0,
            "hp": 0,
            "max_hp": 0,
            "mp": 0,
            "max_mp": 0,
            "stats": {},
            "stat_points": 0,
            "copper": 0,
            "silver": 0,
            "gold": 0,
            "inventory": {},
            "kind": kind,
        }

    profile_dict["max_hp"] = max(int(profile_dict["max_hp"]), 1)
    profile_dict["max_mp"] = max(int(profile_dict["max_mp"]), 1)
    profile_dict["hp"] = min(int(profile_dict["hp"]), profile_dict["max_hp"])
    profile_dict["mp"] = min(int(profile_dict["mp"]), profile_dict["max_mp"])
    profile_dict["title"] = title
    if not profile_dict["stats"]:
        profile_dict["stats"] = dict(DEFAULT_STATS)

    return profile_dict


def profile_from_fighter(fighter):
    """Создаёт профиль карточки из действующего бойца без привязки к рендеру."""
    return {
        "id": getattr(fighter, "id", None),
        "character_id": getattr(fighter, "character_id", getattr(fighter, "id", None)),
        "name": getattr(fighter, "name", "Персонаж"),
        "level": getattr(fighter, "level", 1),
        "xp": getattr(fighter, "xp", 0),
        "hp": getattr(fighter, "hp", 0),
        "max_hp": getattr(fighter, "max_hp", 0),
        "mp": getattr(fighter, "mp", 0),
        "max_mp": getattr(fighter, "max_mp", 0),
        "stats": getattr(fighter, "stats", {}),
        "stat_points": getattr(fighter, "stat_points", 0),
    }


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
    profile["stats"]["endurance"] = max(profile["stats"].get("endurance", 0), minimum_endurance(new_level))
    profile["max_hp"] = calculate_max_hp(new_level, profile["stats"]["endurance"])
    profile["hp"] = profile["max_hp"]
    return True


def derived_values(profile, opponent):
    """Возвращает значения боя для отображения в карточке персонажа."""
    if opponent is None:
        return {"Урон": "--", "Уворот": "--", "Крит": "--", "HP": profile["max_hp"]}

    opponent = normalize_character_profile(opponent)
    fighter = SimpleNamespace(**profile["stats"])
    enemy = SimpleNamespace(**opponent["stats"])
    return {
        "Урон": max(1, int(fighter.strength * 2 - enemy.endurance * 0.5)),
        "Уворот": f"{int(get_dodge_chance(enemy, fighter))}%",
        "Крит": f"{int(get_critical_chance(fighter, enemy))}%",
        "HP": profile["max_hp"],
    }
