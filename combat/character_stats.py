BASE_STAT_VALUE = 3
STARTING_ENDURANCE_VALUE = 3
MIN_STAT_VALUE = 3
STARTING_STAT_POINTS = 5
ENDURANCE_HP_BONUS = 10
MANA_PER_INTELLECT = 5
# Все 7 характеристик персонажа: единая система для всех 6 классов
STAT_NAMES = ("strength", "agility", "intuition", "wisdom", "intellect", "harmony", "endurance")

# ===== 6 КЛАССОВ ПЕРСОНАЖЕЙ =====
PROFESSIONS = {
    # Боец (Warrior) - физический класс с яростью
    "warrior": {
        "name": "Боец",
        "hp": 70,
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
        "hp": 35,
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
        "hp": 40,
        "mana": 10,
        "base_dodge": 0,
        "base_crit": 5,
        "base_crit_damage": 80,
        "unique_resource": "concentration",
        "unique_resource_name": "Концентрация",
        "unique_resource_base": 50,
        "unique_resource_level_bonus": 9,
    },
    # Боевой маг (Battle Mage) - магический класс с маной
    "battle_mage": {
        "name": "Боевой маг",
        "hp": 50,
        "mana": 20,
        "base_dodge": 0,
        "base_crit": 5,
        "base_crit_damage": 50,
        "unique_resource": "mana",
        "unique_resource_name": "Мана",
        "unique_resource_base": None,  # Рассчитывается из интеллекта
        "unique_resource_level_bonus": None,
    },
    # Маг поддержки (Support Mage) - магический класс с маной
    "support_mage": {
        "name": "Маг поддержки",
        "hp": 30,
        "mana": 45,
        "base_dodge": 0,
        "base_crit": 5,
        "base_crit_damage": 50,
        "unique_resource": "mana",
        "unique_resource_name": "Мана",
        "unique_resource_base": None,  # Рассчитывается из интеллекта
        "unique_resource_level_bonus": None,
    },
    # Гармонист (Harmonist) - магический класс с маной
    "harmonist": {
        "name": "Гармонист",
        "hp": 35,
        "mana": 35,
        "base_dodge": 0,
        "base_crit": 5,
        "base_crit_damage": 50,
        "unique_resource": "mana",
        "unique_resource_name": "Мана",
        "unique_resource_base": None,  # Рассчитывается из интеллекта
        "unique_resource_level_bonus": None,
    },
}

# Уникальные ресурсы (ярость, меткость, концентрация) восстанавливаются в конце хода
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
        "on_critical": (15, 1),  # При крит ударе: +15 + 1×уровень
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
    return PROFESSIONS.get(profession_type)


def is_valid_profession(profession_type):
    """Проверить что профессия существует."""
    return profession_type in PROFESSIONS


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
        return calculate_max_mana(intellect)

    # Для остальных ресурсов (ярость, меткость, концентрация)
    base = data["unique_resource_base"]
    level_bonus = data["unique_resource_level_bonus"]
    if base is None or level_bonus is None:
        return 0

    return base + (level_bonus * max(0, level - 1))


def level_stat_points(level):
    """Return free points granted on reaching a level."""
    return 3


def total_stat_points(level):
    """Return all free points available at the specified level."""
    return STARTING_STAT_POINTS + sum(level_stat_points(value) for value in range(2, int(level) + 1))


def minimum_endurance(level):
    """Return endurance permanently granted by the character level."""
    return STARTING_ENDURANCE_VALUE + max(0, int(level) - 1)


def calculate_max_hp(level, endurance):
    """Return the maximum health determined by level and endurance."""
    return ENDURANCE_HP_BONUS * int(endurance)


def calculate_max_mana(intellect):
    """Return the maximum mana pool determined by intellect."""
    return MANA_PER_INTELLECT * int(intellect)


def adjust_stats(stats, stat_points, hp, max_hp, level, stat_name, delta, character_id=None):
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
    updated_max_hp = calculate_max_hp(level, updated_stats["endurance"])
    updated_hp = int(hp)
    if stat_name == "endurance" and delta > 0:
        updated_hp += updated_max_hp - int(max_hp)

    return {
        "stats": updated_stats,
        "stat_points": DEBUG_UNLIMITED_STAT_POINTS if unlimited else int(stat_points) - delta,
        "hp": min(updated_hp, updated_max_hp),
        "max_hp": updated_max_hp,
    }
