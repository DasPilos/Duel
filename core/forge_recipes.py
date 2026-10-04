"""Recipes and production times available from the Radburg forge."""

FORGE_QUEUE_LIMIT = 5

FORGE_TABS = (
    ("weapons", "ОРУЖИЕ"),
    ("shields", "ЩИТЫ"),
    ("helmets", "ШЛЕМЫ"),
    ("armor", "ДОСПЕХИ"),
    ("gloves", "ПЕРЧАТКИ"),
    ("plates", "ЛАТЫ"),
    ("shoes", "ОБУВЬ"),
    ("smelting", "ПЛАВИЛЬНЯ"),
    ("upgrades", "УЛУЧШЕНИЯ"),
    ("storage", "СКЛАД"),
)

# Inputs use catalog item IDs. Each recipe crafts one output item.
FORGE_RECIPES = {
    "weapons": (
        {"item_id": 90, "materials": {60: 5}, "cost_copper": 40, "duration_sec": 720},
        {"item_id": 91, "materials": {60: 5}, "cost_copper": 40, "duration_sec": 720},
        {"item_id": 92, "materials": {60: 5}, "cost_copper": 40, "duration_sec": 720},
        {"item_id": 93, "materials": {60: 5}, "cost_copper": 40, "duration_sec": 720},
        {"item_id": 23, "materials": {60: 5}, "cost_copper": 300, "duration_sec": 1080},
        {"item_id": 24, "materials": {60: 4}, "cost_copper": 300, "duration_sec": 960},
        {"item_id": 25, "materials": {60: 5}, "cost_copper": 300, "duration_sec": 960},
        {"item_id": 20, "materials": {73: 3}, "cost_copper": 0, "duration_sec": 1800},
        {"item_id": 22, "materials": {73: 2}, "cost_copper": 0, "duration_sec": 1200},
        {"item_id": 21, "materials": {74: 3}, "cost_copper": 0, "duration_sec": 3600},
    ),
    "shields": (
        {"item_id": 39, "materials": {60: 4}, "cost_copper": 0, "duration_sec": 1260},
        {"item_id": 38, "materials": {60: 4}, "cost_copper": 0, "duration_sec": 1500},
    ),
    "helmets": (),
    "armor": (),
    "gloves": (),
    "plates": (),
    "shoes": (),
    "smelting": (
        {"item_id": 73, "materials": {10: 1, 60: 1}, "cost_copper": 0, "duration_sec": 1800},
        {"item_id": 74, "materials": {73: 1, 68: 1}, "cost_copper": 0, "duration_sec": 2400},
    ),
    "upgrades": (),
    "storage": (),
}

MATERIAL_NAMES = {
    60: "Древесина",
    10: "Железная руда",
    68: "Уголь",
    73: "Железо",
    74: "Сталь",
}

RECIPE_DETAILS = {
    90: {
        "item_id": 90, "name": "Старый серп", "icon": "tool_sickle", "category": "weapons",
        "slot": "ПЛ рука", "req": "Сила 4", "damage": "1-1", "recipe_str": "Древесина ×5, медь ×40",
        "weight_str": "1", "buffs": "добыча пшеницы + 20%", "stats": "-", "deck": "-",
        "duration_str": "12 м", "price_str": "1 Серебро",
        "materials": {60: 5}, "cost_copper": 40, "duration_sec": 720,
    },
    91: {
        "item_id": 91, "name": "Топор лесоруба", "icon": "tool_axe", "category": "weapons",
        "slot": "ПЛ рука", "req": "Сила 4", "damage": "1-1", "recipe_str": "Древесина ×5, медь ×40",
        "weight_str": "1", "buffs": "добыча древесыны + 20%", "stats": "-", "deck": "-",
        "duration_str": "12 м", "price_str": "1 Серебро",
        "materials": {60: 5}, "cost_copper": 40, "duration_sec": 720,
    },
    92: {
        "item_id": 92, "name": "Кирка", "icon": "tool_pickaxe", "category": "weapons",
        "slot": "ПЛ рука", "req": "Сила 4", "damage": "1-1", "recipe_str": "Древесина ×5, медь ×40",
        "weight_str": "1", "buffs": "добыча железной руды, угля, Камня + 20%", "stats": "-", "deck": "-",
        "duration_str": "12 м", "price_str": "1 Серебро",
        "materials": {60: 5}, "cost_copper": 40, "duration_sec": 720,
    },
    93: {
        "item_id": 93, "name": "Разделочный нож", "icon": "tool_butcher_knife", "category": "weapons",
        "slot": "ПЛ рука", "req": "Сила 4", "damage": "1-1", "recipe_str": "Древесина ×5, медь ×40",
        "weight_str": "1", "buffs": "добыча Кожи, Мяса + 20%", "stats": "-", "deck": "-",
        "duration_str": "12 м", "price_str": "1 Серебро",
        "materials": {60: 5}, "cost_copper": 40, "duration_sec": 720,
    },
    23: {
        "item_id": 23, "name": "Дубина", "icon": "weapon_club", "category": "weapons",
        "slot": "П рука", "req": "Сила 6", "damage": "3-10", "recipe_str": "Древесина ×5, Серебра ×3",
        "weight_str": "5", "buffs": "-", "stats": "HP +20", "deck": "-",
        "duration_str": "18 м", "price_str": "5 Серебро",
        "materials": {60: 5}, "cost_copper": 300, "duration_sec": 1080,
    },
    24: {
        "item_id": 24, "name": "Простой лук", "icon": "weapon_bow", "category": "weapons",
        "slot": "П рука", "req": "Ловкость: 6", "damage": "4-8", "recipe_str": "Древесина ×4, Серебра ×3",
        "weight_str": "1", "buffs": "Уворот: +5%", "stats": "Сила +2", "deck": "-",
        "duration_str": "16 м", "price_str": "4 Серебро",
        "materials": {60: 4}, "cost_copper": 300, "duration_sec": 960,
    },
    25: {
        "item_id": 25, "name": "Деревный посох", "icon": "weapon_staff", "category": "weapons",
        "slot": "П рука", "req": "Ловкость: 6 Интелект: 4", "damage": "1-4", "recipe_str": "Древесина ×5, Серебра ×3",
        "weight_str": "2", "buffs": "MP +30", "stats": "-", "deck": "-",
        "duration_str": "16 м", "price_str": "5 Серебро",
        "materials": {60: 5}, "cost_copper": 300, "duration_sec": 960,
    },
    39: {
        "item_id": 39, "name": "Деревянный щит", "icon": "shield_wooden", "category": "shields",
        "slot": "Л рука", "req": "Сила 4", "damage": "0", "recipe_str": "Древесина ×4",
        "weight_str": "3", "buffs": "Блок: 5%", "stats": "HP +20", "deck": "-",
        "duration_str": "21 м", "price_str": "3 Серебра",
        "materials": {60: 4}, "cost_copper": 0, "duration_sec": 1260,
    },
    20: {
        "item_id": 20, "name": "Железный меч", "icon": "right_hand_steel_sword", "category": "weapons",
        "slot": "П рука", "req": "Сила 5", "damage": "5-7", "recipe_str": "Железо ×3",
        "weight_str": "2", "buffs": "-", "stats": "Сила +1", "deck": "-",
        "duration_str": "30 м", "price_str": "15 Серебра",
        "materials": {73: 3}, "cost_copper": 0, "duration_sec": 1800,
    },
    22: {
        "item_id": 22, "name": "Кинжал", "icon": "right_hand_steel_sword", "category": "weapons",
        "slot": "П рука", "req": "Ловкость 5", "damage": "3-5", "recipe_str": "Железо ×2",
        "weight_str": "1", "buffs": "-", "stats": "Ловкость +1", "deck": "-",
        "duration_str": "20 м", "price_str": "10 Серебра",
        "materials": {73: 2}, "cost_copper": 0, "duration_sec": 1200,
    },
    21: {
        "item_id": 21, "name": "Стальной меч", "icon": "right_hand_steel_sword", "category": "weapons",
        "slot": "П рука", "req": "Сила 7", "damage": "7-10", "recipe_str": "Сталь ×3",
        "weight_str": "1.8", "buffs": "-", "stats": "Сила +2, Интуиция +1", "deck": "-",
        "duration_str": "60 м", "price_str": "35 Серебра",
        "materials": {74: 3}, "cost_copper": 0, "duration_sec": 3600,
    },
    38: {
        "item_id": 38, "name": "Круглый щит", "icon": "shield_wooden", "category": "shields",
        "slot": "Л рука", "req": "Сила 5", "damage": "0", "recipe_str": "Древесина ×4",
        "weight_str": "3.5", "buffs": "Блок: 8%", "stats": "Выносливость +2", "deck": "-",
        "duration_str": "25 м", "price_str": "18 Серебра",
        "materials": {60: 4}, "cost_copper": 0, "duration_sec": 1500,
    },
    73: {
        "item_id": 73, "name": "Железо", "icon": "material_iron", "category": "smelting",
        "slot": "Материал", "req": "-", "damage": "-", "recipe_str": "Руда ×1, Древесина ×1",
        "weight_str": "6", "buffs": "Грубая переплавка", "stats": "-", "deck": "-",
        "duration_str": "30 м", "price_str": "1 Серебро",
        "materials": {10: 1, 60: 1}, "cost_copper": 0, "duration_sec": 1800,
    },
    74: {
        "item_id": 74, "name": "Сталь", "icon": "material_steel", "category": "smelting",
        "slot": "Материал", "req": "-", "damage": "-", "recipe_str": "Железо ×1, Уголь ×1",
        "weight_str": "7", "buffs": "Переплавка с углем", "stats": "-", "deck": "-",
        "duration_str": "40 м", "price_str": "50 Серебра",
        "materials": {73: 1, 68: 1}, "cost_copper": 0, "duration_sec": 2400,
    },
}

def format_forge_time(seconds):
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, sec = divmod(remainder, 60)
    if hours:
        return f"{hours} ч {minutes:02d} мин"
    if minutes:
        return f"{minutes:02d}:{sec:02d}"
    return f"00:{sec:02d}"

RECIPE_BY_ITEM = {
    recipe["item_id"]: recipe
    for recipes in FORGE_RECIPES.values()
    for recipe in recipes
}
