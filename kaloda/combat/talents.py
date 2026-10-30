from kaloda.combat.character_stats import (
    BASE_STAT_VALUE,
    STAT_NAMES,
    calculate_max_hp,
    calculate_max_mana,
    calculate_max_unique_resource,
    get_profession_data,
    normalize_profession_type,
)


def _choice(choice_id, name, description, **effects):
    return {
        "id": choice_id,
        "name": name,
        "description": description,
        "effects": effects,
    }


def _choice_level(level, left, right):
    return {"level": level, "options": [left, right]}


def _passive(level, name, description, **effects):
    return {
        "level": level,
        "passive": True,
        "name": name,
        "description": description,
        "effects": effects,
    }


def _class_tree(hp_bonus, resource_name, resource_max_name, passive, level_9_hp):
    return [
        _choice_level(
            1,
            _choice("hp", f"+{hp_bonus} к максимальному HP", f"Увеличивает максимальное здоровье на {hp_bonus}.", max_hp=hp_bonus),
            _choice("stats", "+1 ко всем характеристикам", "Увеличивает каждую из семи характеристик на 1.", all_stats=1),
        ),
        _choice_level(
            2,
            _choice("regen_2", f"+2 к восстановлению {resource_name}", f"Восстановление {resource_name} в ход увеличивается на 2.", resource_regen=2),
            _choice("burn_20", f"Сжигание карты: +20% {resource_max_name}", f"Сжигание карты восстанавливает дополнительные 20% максимального {resource_name}.", burn_percent=20),
        ),
        passive,
        _choice_level(
            4,
            _choice("mana_15", "+15 к максимальной мане", "Увеличивает максимальную ману на 15.", max_mana=15),
            _choice("stats_2", "+2 ко всем характеристикам", "Увеличивает каждую из семи характеристик на 2.", all_stats=2),
        ),
        _choice_level(
            5,
            _choice("move_1", "+1 к дальности передвижения", "Дальность передвижения увеличивается с 3 до 4 гексов.", move_range=1),
            _choice("regen_3", f"+3 к восстановлению {resource_name}", f"Восстановление {resource_name} в ход увеличивается на 3.", resource_regen=3),
        ),
        _choice_level(
            6,
            _choice("hand_1", "+1 карта в руке", "Максимальное количество карт в руке увеличивается на 1.", hand_size=1),
            _choice("draft_1", "+1 карта при первом драфте", "При первом драфте выбирается на одну случайную карту больше.", starting_draft_cards=1),
        ),
        _choice_level(
            7,
            _choice("resource_25", f"+25 к максимуму {resource_name}", f"Максимальный запас {resource_name} увеличивается на 25.", max_resource=25),
            _choice("stats_4", "+4 ко всем характеристикам", "Увеличивает каждую из семи характеристик на 4.", all_stats=4),
        ),
        _choice_level(
            8,
            _choice("regen_4", f"+4 к восстановлению {resource_name}", f"Восстановление {resource_name} в ход увеличивается на 4.", resource_regen=4),
            _choice("burn_25", f"Сжигание карты: +25% {resource_max_name}", f"Сжигание карты восстанавливает дополнительные 25% максимального {resource_name}.", burn_percent=25),
        ),
        _choice_level(
            9,
            _choice("hp_9", f"+{level_9_hp} к максимальному HP", f"Увеличивает максимальное здоровье на {level_9_hp}.", max_hp=level_9_hp),
            _choice("mana_20", "+20 к максимальной мане", "Увеличивает максимальную ману на 20.", max_mana=20),
        ),
        _choice_level(
            10,
            _choice("resource_50", f"+50 к максимуму {resource_name}", f"Максимальный запас {resource_name} увеличивается на 50.", max_resource=50),
            _choice("stats_5", "+5 ко всем характеристикам", "Увеличивает каждую из семи характеристик на 5.", all_stats=5),
        ),
    ]


TALENT_TREES = {
    "necromancer": _class_tree(
        5,
        "некротизма",
        "некротизма",
        _passive(
            3,
            "Усиление призывов",
            "Призываемые существа получают +1 к максимальному HP за каждое очко интеллекта "
            "и +1 к урону за каждые 4 очка мудрости.",
            summon_hp_per_intellect=1,
            summon_damage_per_4_wisdom=1,
        ),
        15,
    ),
    "warrior": _class_tree(
        12,
        "ярости",
        "ярости",
        _passive(
            3,
            "Крепкая хватка",
            "Каждое очко силы дополнительно увеличивает максимальное HP на 2.",
            strength_max_hp=2,
        ),
        30,
    ),
    "archer": _class_tree(
        7,
        "меткости",
        "меткости",
        _passive(
            3,
            "Дальнобойность",
            "За каждые 10 максимальной меткости дальность атак от 2 гексов увеличивается на 1.",
            attack_range_per_10_accuracy=1,
        ),
        22,
    ),
    "assassin": _class_tree(
        6,
        "концентрации",
        "концентрации",
        _passive(
            3,
            "Кровавый крит",
            "Критические атаки восстанавливают здоровье в размере 25% нанесённого урона.",
            critical_healing_percent=25,
        ),
        18,
    ),
    "mage": _class_tree(
        4,
        "маны",
        "маны",
        _passive(
            3,
            "Магическое мастерство",
            "Каждое очко мудрости увеличивает максимальную ману на 2; "
            "каждые 3 очка интеллекта добавляют 1 магического урона.",
            wisdom_max_mana=2,
            intellect_magic_damage_per_3=1,
        ),
        15,
    ),
}


def talent_tree_for(profession_type):
    profession_type = normalize_profession_type(str(profession_type or "warrior"))
    return TALENT_TREES.get(profession_type, TALENT_TREES["warrior"])


def talent_option(profession_type, level, choice_id):
    entry = next(
        (item for item in talent_tree_for(profession_type) if item["level"] == int(level)),
        None,
    )
    if entry is None or entry.get("passive"):
        return None
    return next(
        (option for option in entry["options"] if option["id"] == str(choice_id)),
        None,
    )


def talent_effects(profession_type, choices, level):
    tree = talent_tree_for(profession_type)
    bonuses = {
        "all_stats": 0,
        "max_hp": 0,
        "max_mana": 0,
        "max_resource": 0,
        "resource_regen": 0,
        "burn_percent": 0,
        "move_range": 0,
        "hand_size": 0,
        "starting_draft_cards": 0,
        "summon_hp_per_intellect": 0,
        "summon_damage_per_4_wisdom": 0,
        "strength_max_hp": 0,
        "attack_range_per_10_accuracy": 0,
        "critical_healing_percent": 0,
        "wisdom_max_mana": 0,
        "intellect_magic_damage_per_3": 0,
    }
    choices = choices if isinstance(choices, dict) else {}
    for entry in tree:
        if entry["level"] > int(level):
            continue
        effects = entry.get("effects")
        if effects is None:
            option = talent_option(
                profession_type,
                entry["level"],
                choices.get(str(entry["level"]), choices.get(entry["level"])),
            )
            effects = option["effects"] if option is not None else {}
        for key, amount in effects.items():
            if key == "all_stats":
                bonuses[key] += int(amount)
            elif key in bonuses:
                bonuses[key] += int(amount)
    return bonuses


def class_stat_bonuses(profession_type, choices, level):
    amount = talent_effects(profession_type, choices, level)["all_stats"]
    return {stat: amount for stat in STAT_NAMES}


def derived_talent_values(profession_type, level, stats, choices):
    profession_type = normalize_profession_type(str(profession_type or "warrior"))
    effects = talent_effects(profession_type, choices, level)
    stats = stats if isinstance(stats, dict) else {}
    effective_stats = {
        stat: int(stats.get(stat, BASE_STAT_VALUE)) + effects["all_stats"]
        for stat in STAT_NAMES
    }
    max_hp = (
        calculate_max_hp(
            int(level), effective_stats["endurance"], profession_type
        )
        + effects["max_hp"]
        + effects["strength_max_hp"] * effective_stats["strength"]
    )
    max_mana = (
        calculate_max_mana(effective_stats["intellect"], profession_type)
        + effects["max_mana"]
        + effects["wisdom_max_mana"] * effective_stats["wisdom"]
    )
    unique_resource = get_profession_data(profession_type)["unique_resource"]
    if unique_resource == "mana":
        max_mana += effects["max_resource"]
        max_resource = max_mana
    else:
        max_resource = (
            calculate_max_unique_resource(
                profession_type, int(level), effective_stats["intellect"]
            )
            + effects["max_resource"]
        )
    return {
        "effects": effects,
        "effective_stats": effective_stats,
        "max_hp": max_hp,
        "max_mp": max_mana,
        "max_resource": max_resource,
    }
