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
        "berries": 2,
        "meat": 3,
    },
    "warehouse": {
        "wood": 1,
        "board": 2,
        "flax": 2,
        "stone": 2,
        "iron": 2,
        "iron_ingot": 2,
        "stone_block": 2,
        "cotton": 3,
        "leather": 3,
        "hard_leather": 3,
        "thick_leather": 3,
        "cloth": 3,
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
    "berries": 2,
    "flax": 2,
    "iron": 2,
    "stone": 2,
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