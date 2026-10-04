"""Shared PNG icon lookup for item and resource labels across UI panels."""

from ui.inventory_window import IconCache


RESOURCE_ICON_KEYS = {
    "wheat": "material_wheat",
    "flax": "material_flax",
    "cotton": "material_cotton",
    "wood": "material_wood",
    "berries": "material_berry",
    "iron": "material_iron_ore",
    "iron_ore": "material_iron_ore",
    "stone": "material_stone",
    "mithril": "material_mithril_ore",
    "obsidian": "material_obsidian_ore",
    "leather": "material_leather",
    "meat": "material_meat",
    "coal": "material_coal",
    "jet": "material_jet",
    "malachite": "material_malachite",
    "topaz": "material_topaz",
    "garnet": "material_garnet",
    "emerald": "material_emerald",
    "ruby": "material_ruby",
    "sapphire": "material_sapphire",
    "diamond": "material_diamond",
    "board": "material_board",
    "iron_ingot": "material_iron",
    "steel": "material_steel",
    "hard_leather": "material_tough_leather",
    "thick_leather": "material_thick_leather",
    "cloth": "material_cloth",
    "stone_block": "material_stone_block",
    "copper": "copper",
    "silver": "silver",
    "gold": "gold",
    "древесина": "material_wood",
    "доска": "material_board",
    "пшеница": "material_wheat",
    "лен": "material_flax",
    "хлопок": "material_cotton",
    "кожа": "material_leather",
    "мясо": "material_meat",
    "уголь": "material_coal",
    "камень": "material_stone",
    "руда": "material_iron_ore",
    "железо": "material_iron",
    "сталь": "material_steel",
    "медь": "copper",
    "серебро": "silver",
    "серебра": "silver",
    "золото": "gold",
}

ITEM_ID_ICON_KEYS = {
    1: "potion_blue", 2: "potion_red", 3: "potion_orange",
    10: "material_iron_ore", 11: "herb", 12: "bone", 13: "crystal",
    20: "right_hand_steel_sword", 21: "right_hand_steel_sword", 22: "right_hand_steel_sword",
    23: "weapon_club", 24: "weapon_bow", 25: "weapon_staff",
    30: "body_steel_breastplate", 31: "body_steel_breastplate", 32: "head_iron_helmet",
    33: "back_blue_cloak", 34: "belt_bronze_belt", 35: "hands_steel_gauntlets",
    36: "legs_steel_greaves", 37: "feet_iron_boots", 38: "left_hand_round_shield",
    39: "shield_wooden",
    40: "rings_gold_rings", 41: "neck_sapphire_pendant", 42: "ears_gold_earrings",
    50: "scroll", 51: "scroll", 60: "material_wood", 61: "material_board",
    62: "material_berry", 63: "material_wheat", 64: "material_flax", 65: "material_cotton",
    66: "material_leather", 67: "material_meat", 68: "material_coal", 69: "material_stone",
    71: "material_mithril_ore", 72: "material_obsidian_ore", 73: "material_iron",
    74: "material_steel", 75: "material_tough_leather", 76: "material_thick_leather",
    77: "material_cloth", 78: "material_stone_block", 80: "material_jet",
    81: "material_malachite", 82: "material_topaz", 83: "material_garnet",
    84: "material_emerald", 85: "material_ruby", 86: "material_sapphire", 87: "material_diamond",
    90: "tool_sickle", 91: "tool_axe", 92: "tool_pickaxe", 93: "tool_butcher_knife",
}

BUILDING_ICON_KEYS = {
    "crystal_of_life": "building_crystal_of_life",
    "main_castle": "building_main_castle",
    "tavern_building": "building_tavern_building",
    "barn_building": "building_barn_building",
    "warehouse_building": "building_warehouse_building",
    "forge_building": "building_forge_building",
    "workshop_building": "building_workshop_building",
    "barracks_building": "building_barracks_building",
    "engineering_building": "building_engineering_building",
    "university_building": "building_university_building",
    "military_academy": "building_military_academy",
    "mage_school_building": "building_mage_school_building",
    "stable_building": "building_stable_building",
    "lumber_camp": "building_lumber_camp",
    "town_radburg": "building_town_radburg",
    "wheat_farm": "building_wheat_farm",
    "mountain_rift": "building_mountain_rift",
    "barnyard": "building_barnyard",
    "black_pit": "building_black_pit",
    "farm": "building_wheat_farm",
    "barn": "building_barn_building",
    "warehouse": "building_warehouse_building",
    "stable": "building_stable_building",
}

BUILDING_ICON_KEYS = {
    "crystal_of_life": "building_crystal_of_life",
    "main_castle": "building_main_castle",
    "tavern_building": "building_tavern_building",
    "barn_building": "building_barn_building",
    "warehouse_building": "building_warehouse_building",
    "forge_building": "building_forge_building",
    "workshop_building": "building_workshop_building",
    "barracks_building": "building_barracks_building",
    "engineering_building": "building_engineering_building",
    "university_building": "building_university_building",
    "military_academy": "building_military_academy",
    "mage_school_building": "building_mage_school_building",
    "stable_building": "building_stable_building",
    "lumber_camp": "building_lumber_camp",
    "town_radburg": "building_town_radburg",
    "wheat_farm": "building_wheat_farm",
    "mountain_rift": "building_mountain_rift",
    "barnyard": "building_barnyard",
    "black_pit": "building_black_pit",
    "farm": "building_wheat_farm",
    "barn": "building_barn_building",
    "warehouse": "building_warehouse_building",
    "stable": "building_stable_building",
}

_ICON_CACHE = IconCache()


def icon_key(item_or_key):
    if isinstance(item_or_key, tuple):
        item_or_key = item_or_key[-1]
    if isinstance(item_or_key, dict):
        key = item_or_key.get("icon") or item_or_key.get("id") or item_or_key.get("item_id") or ""
    elif isinstance(item_or_key, int):
        return ITEM_ID_ICON_KEYS.get(item_or_key, "")
    else:
        key = item_or_key or ""
    if isinstance(key, int):
        return ITEM_ID_ICON_KEYS.get(key, "")
    key_str = str(key)
    if key_str in RESOURCE_ICON_KEYS:
        return RESOURCE_ICON_KEYS[key_str]
    lower = key_str.lower()
    if lower in RESOURCE_ICON_KEYS:
        return RESOURCE_ICON_KEYS[lower]
    return key_str


def draw_item_icon(screen, item_or_key, position, size=24):
    key = icon_key(item_or_key)
    if not key:
        return None
    icon = _ICON_CACHE.get(key, size)
    screen.blit(icon, position)
    return icon


def draw_building_icon(screen, object_id, position, size=32):
    key = BUILDING_ICON_KEYS.get(str(object_id))
    if not key:
        return None
    icon = _ICON_CACHE.get(key, size)
    screen.blit(icon, position)
    return icon


def draw_building_icon(screen, object_id, position, size=32):
    key = BUILDING_ICON_KEYS.get(str(object_id))
    if not key:
        return None
    icon = _ICON_CACHE.get(key, size)
    screen.blit(icon, position)
    return icon