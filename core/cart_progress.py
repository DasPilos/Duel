"""JSON-compatible wagon upgrade definitions and player progress defaults."""

CART_UPGRADE_NODES = {
    "wheels": {
        "name": "Укреплённые колёса",
        "effect": "−2 сек на тайл за уровень",
        "resources": ("wood", "iron_ingot"),
        "required_per_level": None,
    },
    "sides": {
        "name": "Вместительные борта",
        "effect": "+50 кг грузоподъёмности за уровень",
        "resources": ("board", "flax"),
        "required_per_level": None,
    },
    "axles": {
        "name": "Кованые оси",
        "effect": "−10 п.п. штрафа за уровень",
        "resources": ("steel", "leather"),
        "required_per_level": None,
    },
}

CART_GRADES = {
    "1": {
        "name": "Лёгкая повозка",
        "researched": True,
        "wood_cost": 100,
        "silver_cost": 10,
        "required_stable_level": 1,
        "body_cost_silver": 10,
        "base_capacity_kg": 300,
        "base_seconds_per_tile": 23.9473,
        "base_full_load_speed_penalty_percent": 70,
        "resource_slots": 1,
        "horse_count": 1,
        "villagers_required": 3,
        "load_kg_per_minute": 3,
        "load_kg_per_20_seconds": 1,
        "upgrade_limit": 3,
    },
    "2": {
        "name": "Крестьянский обоз",
        "researched": False,
        "blueprint_cost": None,
        "upgrade_limit": 3,
    },
}

DEFAULT_CART_PROGRESS = {
    "schema_version": 1,
    "selected_grade": 1,
    "grades": {
        "1": {
            "blueprint_owned": True,
            "body_owned": False,
            "wood_deposited": 0,
            "silver_deposited": 0,
            "upgrades": {"wheels": 0, "sides": 0, "axles": 0},
        },
        "2": {
            "blueprint_owned": False,
            "body_owned": False,
            "wood_deposited": 0,
            "silver_deposited": 0,
            "upgrades": {"wheels": 0, "sides": 0, "axles": 0},
        },
    },
}

WAREHOUSE_RESOURCE_LABELS = {
    "wood": "Древесина",
    "iron_ingot": "Железо",
    "board": "Доска",
    "flax": "Лён",
    "steel": "Сталь",
    "leather": "Кожа",
}

RESOURCE_ITEM_IDS = {
    "wood": 60,
    "iron_ingot": 73,
    "board": 61,
    "flax": 64,
    "steel": 74,
    "leather": 66,
}


def cart_stats(upgrades):
    """Calculate Grade 1 base stats from its three upgrade levels."""
    wheels = max(0, min(3, int(upgrades.get("wheels", 0))))
    sides = max(0, min(3, int(upgrades.get("sides", 0))))
    axles = max(0, min(3, int(upgrades.get("axles", 0))))
    return {
        "capacity_kg": CART_GRADES["1"]["base_capacity_kg"] + 50 * sides,
        "seconds_per_tile": CART_GRADES["1"]["base_seconds_per_tile"] - 2 * wheels,
        "empty_tiles_per_hour": round(3600 / (
            CART_GRADES["1"]["base_seconds_per_tile"] - 2 * wheels
        )),
        "full_load_speed_penalty_percent": CART_GRADES["1"]["base_full_load_speed_penalty_percent"] - 10 * axles,
    }


def grade_two_unlocked(progress):
    """Grade 2 blueprint becomes available after all Grade 1 branches reach 3/3."""
    upgrades = progress.get("grades", {}).get("1", {}).get("upgrades", {})
    return all(int(upgrades.get(node_id, 0)) >= 3 for node_id in CART_UPGRADE_NODES)