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
        "sprite_key": "light",
        "wood_cost": 100,
        "silver_cost": 10,
        "production_seconds": 40 * 60,
        "required_stable_level": 1,
        "body_cost_silver": 10,
        "base_capacity_kg": 300,
        "base_seconds_per_tile": 7.2,
        "base_full_load_speed_penalty_percent": 70,
        "resource_slots": 1,
        "horse_count": 1,
        "villagers_required": 1,
        "load_kg_per_minute": 60,
        "unload_kg_per_minute": 40,
        "load_kg_per_20_seconds": 20,
        "upgrade_limit": 3,
    },
    "2": {
        "name": "Крестьянский обоз",
        "researched": False,
        "sprite_key": "peasant",
        "blueprint_cost": None,
        "upgrade_limit": 3,
    },
}

CART_MAX_DURABILITY = 100
CART_WOOD_MAINTENANCE_PER_HOUR = 2
CART_REPAIR_WOOD_PER_DURABILITY = 1

DEFAULT_CART_PROGRESS = {
    "schema_version": 1,
    "selected_grade": 1,
    "grades": {
        "1": {
            "blueprint_owned": True,
            "body_owned": False,
            "body_count": 0,
            "body_finish_at": None,
            "production_orders": [],
            "wood_deposited": 0,
            "silver_deposited": 0,
            "upgrades": {"wheels": 0, "sides": 0, "axles": 0},
        },
        "2": {
            "blueprint_owned": False,
            "body_owned": False,
            "body_count": 0,
            "body_finish_at": None,
            "production_orders": [],
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
    "berries": 62,
    "wheat": 63,
    "meat": 67,
    "wood": 60,
    "coal": 68,
    "stone": 69,
    "iron": 10,
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


def cart_load_speed_ratio(load_weight_kg, capacity_kg, penalty_percent):
    """Return remaining speed as a linear fraction of the cart's empty speed."""
    capacity = max(1.0, float(capacity_kg))
    load_ratio = min(1.0, max(0.0, float(load_weight_kg) / capacity))
    return max(0.1, 1.0 - float(penalty_percent) * load_ratio / 100.0)


def grade_two_unlocked(progress):
    """Grade 2 blueprint becomes available after all Grade 1 branches reach 3/3."""
    upgrades = progress.get("grades", {}).get("1", {}).get("upgrades", {})
    return all(int(upgrades.get(node_id, 0)) >= 3 for node_id in CART_UPGRADE_NODES)