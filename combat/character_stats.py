BASE_STAT_VALUE = 2
STARTING_ENDURANCE_VALUE = 2
MIN_STAT_VALUE = 2
STARTING_STAT_POINTS = 6
ENDURANCE_HP_BONUS = 10
BASE_HP = 70
MANA_PER_INTELLECT = 5
# Все 7 характеристик персонажа: единая система для всех классов
STAT_NAMES = ("strength", "agility", "intuition", "wisdom", "intellect", "harmony", "endurance")
STAT_SUPPORT_STATS = {
    "strength": ("agility", "intuition"),
    "agility": ("strength", "intuition"),
    "intuition": ("strength", "agility"),
    "wisdom": ("intellect", "harmony"),
    "intellect": ("wisdom", "harmony"),
    "harmony": ("wisdom", "intellect"),
}
STAT_DEPENDENTS = {
    support: tuple(stat for stat, supports in STAT_SUPPORT_STATS.items() if support in supports)
    for support in STAT_SUPPORT_STATS
}

# Старые типы магов сводятся к единому классу при чтении сохранений.
LEGACY_PROFESSION_TYPES = {
    "battle_mage": "mage",
    "support_mage": "mage",
    "harmonist": "mage",
}


def normalize_profession_type(profession_type):
    return LEGACY_PROFESSION_TYPES.get(profession_type, profession_type)


def is_mage_class(profession_type):
    return normalize_profession_type(profession_type) == "mage"


# Маг появляется в начале боя с этим процентом маны и восстанавливает 8 + уровень в начале хода.
MAGE_START_MANA_PERCENT = 25
MAGE_MANA_REGEN_BASE = 8


# ===== КЛАССЫ ПЕРСОНАЖЕЙ =====
PROFESSIONS = {
    # Боец (Warrior) - физический класс с яростью
    "warrior": {
        "name": "Боец",
        "hp": BASE_HP,
        "mana": 5,
        "base_dodge": 0,
        "base_crit": 5,
        "base_crit_damage": 50,
        "unique_resource": "rage",
        "unique_resource_name": "Ярость",
        "unique_resource_base": 50,
        "unique_resource_level_bonus": 9,
    },
    # Лучник (Archer) - физический класс с меткостью
    "archer": {
        "name": "Лучник",
        "hp": 25,
        "mana": 15,
        "base_dodge": 10,
        "base_crit": 5,
        "base_crit_damage": 50,
        "unique_resource": "accuracy",
        "unique_resource_name": "Меткость",
        "unique_resource_base": 50,
        "unique_resource_level_bonus": 9,
    },
    # Асасин (Assassin) - физический класс с концентрацией
    "assassin": {
        "name": "Асасин",
        "hp": 15,
        "mana": 10,
        "base_dodge": 0,
        "base_crit": 13,
        "base_crit_damage": 80,
        "base_crit_damage_bonus": 30,
        "unique_resource": "concentration",
        "unique_resource_name": "Концентрация",
        "unique_resource_base": 50,
        "unique_resource_level_bonus": 9,
    },
    # Маг — единый магический класс
    "mage": {
        "name": "Маг",
        "hp": 10,
        "mana": 65,
        "base_mana": 65,
        "base_dodge": 0,
        "base_crit": 5,
        "base_crit_damage": 50,
        "unique_resource": "mana",
        "unique_resource_name": "Мана",
        "unique_resource_base": None,  # Рассчитывается из интеллекта
        "unique_resource_level_bonus": None,
    },
    "necromancer": {
        "name": "Некромант",
        "hp": 20,
        "mana": 25,
        "base_mana": 25,
        "base_dodge": 0,
        "base_crit": 5,
        "base_crit_damage": 50,
        "unique_resource": "necrotism",
        "unique_resource_name": "Некротизм",
        "unique_resource_base": 50,
        "unique_resource_level_bonus": 9,
    },
}

# Физические ресурсы восстанавливаются в конце хода.
UNIQUE_RESOURCE_RECOVERY = {
    "rage": 4,              # +4 ярости в конец хода
    "accuracy": 5,          # +5 меткости в конец хода
    "concentration": 9,     # +9 концентрации в конец хода
}

# Как получить уникальные ресурсы в бою
UNIQUE_RESOURCE_GAIN = {
    "rage": {
        "on_damage_taken": (10, 2),  # При получении 10+ урона: +10 + 2×уровень
    },
    "accuracy": {
        "on_dodge": (7, 1),  # При успешном уворотеuate: +7 + 1×уровень
    },
    "concentration": {
        "on_critical": (15, 0),  # За каждый критический удар: +15 концентрации
    },
}

# Тестовый персонаж без ограничений по статам/уровню — нужен для проверки игры на разных уровнях.
DEBUG_UNLIMITED_CHARACTER_IDS = {2}
DEBUG_UNLIMITED_STAT_POINTS = 999


def is_debug_unlimited(character_id):
    try:
        return int(character_id) in DEBUG_UNLIMITED_CHARACTER_IDS
    except (TypeError, ValueError):
        return False


# ===== ФУНКЦИИ ДЛЯ РАБОТЫ С КЛАССАМИ И РЕСУРСАМИ =====

def get_profession_data(profession_type):
    """Получить данные профессии. Вернет dict или None если профессия не существует."""
    return PROFESSIONS.get(normalize_profession_type(profession_type))


def is_valid_profession(profession_type):
    """Проверить что профессия существует."""
    return normalize_profession_type(profession_type) in PROFESSIONS


def get_profession_names():
    """Получить список всех профессий (ключей)."""
    return list(PROFESSIONS.keys())


def calculate_max_unique_resource(profession_type, level, intellect=None):
    """
    Рассчитать максимальное значение уникального ресурса для профессии и уровня.
    Для маны использует intellect, для остального - уровень.
    """
    data = get_profession_data(profession_type)
    if not data:
        return 0

    resource_type = data["unique_resource"]

    # Для маны рассчитываем через интеллект
    if resource_type == "mana":
        if intellect is None:
            intellect = BASE_STAT_VALUE  # Если не указан, берем базовое значение
        return calculate_max_mana(intellect, profession_type)

    # Для остальных ресурсов (ярость, меткость, концентрация)
    base = data["unique_resource_base"]
    level_bonus = data["unique_resource_level_bonus"]
    if base is None or level_bonus is None:
        return 0

    return base + (level_bonus * max(0, level - 1))


def level_stat_points(level):
    """Return free points granted on reaching a level."""
    return 4


def total_stat_points(level):
    """Return all free points available at the specified level."""
    return STARTING_STAT_POINTS + sum(level_stat_points(value) for value in range(2, int(level) + 1))


def minimum_endurance(level):
    """Return the endurance granted at character creation and each level-up."""
    return STARTING_ENDURANCE_VALUE + max(0, int(level) - 1)


def stat_support_requirement(stat_value):
    """Return the required value of each supporting stat at this stat value."""
    return max(0, int(stat_value) // 2)


def stat_supports_met(stats, stat_name):
    """Whether both linked stats meet the progression gate for the requested stat."""
    supports = STAT_SUPPORT_STATS.get(stat_name)
    if supports is None:
        return True
    required = stat_support_requirement(stats[stat_name])
    return all(int(stats.get(support, MIN_STAT_VALUE)) >= required for support in supports)


def calculate_max_hp(level, endurance, profession_type="warrior"):
    """Return class base health plus the endurance health bonus."""
    base_hp = get_profession_data(profession_type)
    base_hp = base_hp.get("hp", BASE_HP) if base_hp else BASE_HP
    return base_hp + ENDURANCE_HP_BONUS * int(endurance)


def calculate_max_mana(intellect, profession_type=None):
    """Return the maximum mana pool: class base mana plus intellect bonus."""
    data = get_profession_data(profession_type) if profession_type else None
    base_mana = data.get("base_mana", 0) if data else 0
    return base_mana + MANA_PER_INTELLECT * int(intellect)


def adjust_stats(stats, stat_points, hp, max_hp, level, stat_name, delta, character_id=None, profession_type="warrior"):
    """Return updated stat state, or None when the requested change is invalid."""
    if stat_name not in stats or delta not in (-1, 1):
        return None
    unlimited = is_debug_unlimited(character_id)
    # Запретить увеличение выносливости вручную - она повышается только при повышении уровня
    if stat_name == "endurance" and delta > 0:
        return None
    if delta > 0 and stat_points <= 0 and not unlimited:
        return None
    minimum_value = 0 if unlimited else (minimum_endurance(level) if stat_name == "endurance" else MIN_STAT_VALUE)
    if delta < 0 and stats[stat_name] <= minimum_value:
        return None

    updated_stats = dict(stats)
    updated_stats[stat_name] += delta
    if not unlimited:
        if delta > 0 and not stat_supports_met(updated_stats, stat_name):
            return None
        if delta < 0 and any(
            not stat_supports_met(updated_stats, dependent)
            for dependent in STAT_DEPENDENTS.get(stat_name, ())
        ):
            return None
    updated_max_hp = calculate_max_hp(level, updated_stats["endurance"], profession_type)
    updated_hp = int(hp)
    if stat_name == "endurance" and delta > 0:
        updated_hp += updated_max_hp - int(max_hp)

    return {
        "stats": updated_stats,
        "stat_points": DEBUG_UNLIMITED_STAT_POINTS if unlimited else int(stat_points) - delta,
        "hp": min(updated_hp, updated_max_hp),
        "max_hp": updated_max_hp,
    }
