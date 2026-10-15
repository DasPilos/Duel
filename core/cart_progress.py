"""JSON-compatible wagon upgrade definitions and player progress defaults."""

import math

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
CART_BROKEN_REPAIR_WOOD = 70
CART_REPAIR_WOOD_PER_DURABILITY = 0.4
CART_SPEED_TILES_PER_HOUR_MAX = 500
CART_SPEED_TILES_PER_HOUR_MIN = 200
CART_SPEED_FLOOR_DURABILITY = 30
CART_METERS_PER_TILE = 20
CART_AUTO_REPAIR_RULES = {
    "always": {"threshold": 71, "wood_cost": 20},
    "economy": {"threshold": 50, "wood_cost": 25},
}

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


def cart_durability_band(durability):
    """Return the wear band name: broken, full, medium or good."""
    value = float(durability)
    if value <= 0:
        return "broken"
    if value <= 30:
        return "full"
    if value <= 70:
        return "medium"
    return "good"


def cart_wear_step_seconds(durability):
    """Seconds of work needed for one 1% durability step at this durability."""
    band = cart_durability_band(durability)
    if band == "good":
        return 20 * 60
    if band == "medium":
        return 30 * 60
    return 40 * 60


def cart_tiles_per_hour(durability):
    """Empty-cart speed: 500 tiles/h at 100% durability, 200 tiles/h at 30% and below."""
    value = min(CART_MAX_DURABILITY, max(CART_SPEED_FLOOR_DURABILITY, float(durability)))
    span = CART_MAX_DURABILITY - CART_SPEED_FLOOR_DURABILITY
    progress = (value - CART_SPEED_FLOOR_DURABILITY) / span
    return CART_SPEED_TILES_PER_HOUR_MIN + (
        CART_SPEED_TILES_PER_HOUR_MAX - CART_SPEED_TILES_PER_HOUR_MIN
    ) * progress


def tiles_to_km(tiles):
    """Display-only conversion: tiles (or tiles/h, read as km/h) to kilometres."""
    return float(tiles) * CART_METERS_PER_TILE / 1000


def cart_repair_wood_cost(durability):
    """Manual repair price: flat when broken, otherwise 0.4 wood per missing point (0 at full)."""
    if float(durability) <= 0:
        return CART_BROKEN_REPAIR_WOOD
    missing = CART_MAX_DURABILITY - float(durability)
    return int(math.ceil(round(missing * CART_REPAIR_WOOD_PER_DURABILITY, 6)))


def cart_apply_work(durability, carry_seconds, work_seconds,
                    repair_threshold=None, try_pay_repair=None):
    """Advance a cart through working time.

    Each 1% step takes the interval of the band the cart is in when the step starts.
    `carry_seconds` is progress already spent on the current step. When `repair_threshold`
    is set, the cart is restored to full durability the moment it drops below that value,
    provided `try_pay_repair()` succeeds (it pays the flat fee and returns True/False).
    Returns (durability, carry_seconds, repairs_done).
    """
    durability = min(float(CART_MAX_DURABILITY), max(0.0, float(durability)))
    carry = max(0.0, float(carry_seconds))
    remaining = max(0.0, float(work_seconds))
    repairs = 0

    def auto_repair_due():
        return (repair_threshold is not None and try_pay_repair is not None
                and 0 < durability < repair_threshold)

    if auto_repair_due() and try_pay_repair():
        durability, carry, repairs = float(CART_MAX_DURABILITY), 0.0, repairs + 1
    while durability > 0 and remaining > 0:
        step = min(1.0, durability)
        needed = cart_wear_step_seconds(durability) * step - carry
        if needed > remaining:
            carry += remaining
            remaining = 0.0
            break
        remaining -= needed
        durability = round(durability - step, 6)
        carry = 0.0
        if auto_repair_due() and try_pay_repair():
            durability, repairs = float(CART_MAX_DURABILITY), repairs + 1
    return round(durability, 6), round(carry, 4), repairs


def cart_stats(upgrades, durability=CART_MAX_DURABILITY):
    """Calculate Grade 1 stats from upgrade levels and current durability."""
    wheels = max(0, min(3, int(upgrades.get("wheels", 0))))
    sides = max(0, min(3, int(upgrades.get("sides", 0))))
    axles = max(0, min(3, int(upgrades.get("axles", 0))))
    tiles_per_hour = cart_tiles_per_hour(durability)
    seconds_per_tile = max(0.5, 3600 / tiles_per_hour - 2 * wheels)
    return {
        "capacity_kg": CART_GRADES["1"]["base_capacity_kg"] + 50 * sides,
        "seconds_per_tile": seconds_per_tile,
        "empty_tiles_per_hour": round(3600 / seconds_per_tile),
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