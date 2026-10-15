MAX_CITY_LEVEL = 5
CITY_POPULATION_CAPACITY_BY_LEVEL = {1: 10, 2: 14, 3: 20, 4: 28, 5: 40}

COUNTRY_BUILDING_UNLOCK_LEVELS = {
    "wheat_farm": 1,
    "lumber_camp": 1,
    "mountain_rift": 2,
    "barnyard": 3,
    "black_pit": 4,
}

CITY_STORAGE_RESOURCE_UNLOCK_LEVELS = {
    "barn": {
        "wheat": 1,
        "berries": 3,
        "meat": 3,
    },
    "warehouse": {
        "wood": 1,
        "flax": 3,
        "stone": 2,
        "iron": 3,
        "leather": 3,
        "coal": 4,
        "mithril": 4,
        "obsidian": 4,
        "steel": 4,
        "jet": 4,
        "malachite": 4,
        "topaz": 4,
        "garnet": 4,
        "emerald": 4,
        "ruby": 4,
        "sapphire": 4,
        "diamond": 4,
    },
}

CITY_UPGRADE_RESOURCE_UNLOCK_LEVELS = {
    "wheat": 1,
    "wood": 1,
    "stone": 2,
    "berries": 3,
    "flax": 3,
    "iron": 3,
    "cotton": 3,
    "leather": 3,
    "meat": 3,
    "coal": 4,
    "mithril": 4,
    "obsidian": 4,
}


def unlocked_country_buildings(city_level):
    level = max(1, int(city_level))
    return tuple(
        building for building, unlock_level in COUNTRY_BUILDING_UNLOCK_LEVELS.items()
        if unlock_level <= level
    )


def city_storage_resources(building, city_level, all_resources):
    unlocks = CITY_STORAGE_RESOURCE_UNLOCK_LEVELS.get(building)
    if unlocks is None:
        return tuple(all_resources)
    level = max(1, int(city_level))
    return tuple(resource for resource in all_resources if unlocks.get(resource, level + 1) <= level)


def city_upgrade_resources(city_level):
    level = max(1, int(city_level))
    return tuple(
        resource for resource, unlock_level in CITY_UPGRADE_RESOURCE_UNLOCK_LEVELS.items()
        if unlock_level <= level
    )


def city_population_capacity(city_level, capacity_bonus=0):
    level = min(MAX_CITY_LEVEL, max(1, int(city_level)))
    base_capacity = CITY_POPULATION_CAPACITY_BY_LEVEL[level]
    return base_capacity + max(0, int(capacity_bonus))