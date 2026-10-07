"""Производственные здания (Крестьянское поселение, Лагерь лесорубов): общий справочник для сервера и клиента."""

import math

CYCLE_DURATION_SEC = 7200
# Стадии участка внутри цикла (по 30 минут)
PLOT_STAGE_COUNT = 4

# Ресурс: название и секунд на 1 единицу у одного горожанина
RESOURCES = {
    "wheat": {"label": "Пшеница", "timer_sec": 140},
    "flax": {"label": "Лён", "timer_sec": 480},
    "cotton": {"label": "Хлопок", "timer_sec": 980},
    "wood": {"label": "Древесина", "timer_sec": 240},
    "berries": {"label": "Ягоды", "timer_sec": 360},
    "iron": {"label": "Железная руда", "timer_sec": 300},
    "stone": {"label": "Камень", "timer_sec": 200},
    "mithril": {"label": "Мифриловая руда", "timer_sec": 900},
    "obsidian": {"label": "Обсидиановая порода", "timer_sec": 1400},
    "leather": {"label": "Кожа", "timer_sec": 460},
    "meat": {"label": "Мясо", "timer_sec": 680},
    "coal": {"label": "Уголь", "timer_sec": 600},
    # Драгоценные камни не добываются напрямую: выпадают с шансом вместе с углём; каждый весит 1 кг
    "jet": {"label": "Гагат", "weight_kg": 1},
    "malachite": {"label": "Малахит", "weight_kg": 1},
    "topaz": {"label": "Топаз", "weight_kg": 1},
    "garnet": {"label": "Гранат", "weight_kg": 1},
    "emerald": {"label": "Изумруд", "weight_kg": 1},
    "ruby": {"label": "Рубин", "weight_kg": 1},
    "sapphire": {"label": "Сапфир", "weight_kg": 1},
    "diamond": {"label": "Алмаз", "weight_kg": 1},
    # Обработанные материалы городского склада (пока не производятся)
    "board": {"label": "Доска"},
    "iron_ingot": {"label": "Железо"},
    "steel": {"label": "Сталь"},
    "hard_leather": {"label": "Крепкая кожа"},
    "thick_leather": {"label": "Толстая кожа"},
    "cloth": {"label": "Ткань"},
    "stone_block": {"label": "Каменный блок"},
}

PRODUCTION_ITEM_IDS = {
    "wheat": 63, "flax": 64, "cotton": 65, "wood": 60, "berries": 62,
    "iron": 10, "stone": 69, "mithril": 71, "obsidian": 72,
    "leather": 66, "meat": 67, "coal": 68,
    "jet": 80, "malachite": 81, "topaz": 82, "garnet": 83,
    "emerald": 84, "ruby": 85, "sapphire": 86, "diamond": 87,
}

# Уровень: общая вместимость склада и число горожан (одинаково для всех зданий)
BUILDING_LEVELS = {
    1: {"storage": 500, "max_workers": 2},
    2: {"storage": 800, "max_workers": 3},
    3: {"storage": 1000, "max_workers": 4},
    4: {"storage": 1400, "max_workers": 6},
    5: {"storage": 2000, "max_workers": 8},
    6: {"storage": 3000, "max_workers": 10},
    7: {"storage": 4500, "max_workers": 13},
    8: {"storage": 6000, "max_workers": 16},
    9: {"storage": 8000, "max_workers": 19},
    10: {"storage": 12000, "max_workers": 25},
}
MAX_BUILDING_LEVEL = max(BUILDING_LEVELS)

# Участки в порядке открытия: (уровень открытия, мест под горожан, ресурс, вид участка).
# Сумма мест, открытых к уровню, равна max_workers этого уровня.
BUILDINGS = {
    "farm": {
        "name": "Крестьянское поселение",
        "plots": (
            (1, 2, "wheat", "field"),
            (2, 1, "wheat", "field"),
            (3, 1, "flax", "field"),
            (4, 1, "wheat", "field"), (4, 1, "flax", "field"),
            (5, 2, "wheat", "field"),
            (6, 2, "flax", "field"),
            (7, 3, "cotton", "field"),
            (8, 3, "wheat", "field"),
            (9, 3, "flax", "field"),
            (10, 3, "cotton", "field"), (10, 3, "flax", "field"),
        ),
    },
    "lumber_camp": {
        "name": "Лагерь лесорубов",
        "plots": (
            (1, 2, "wood", "edge"),
            (2, 1, "wood", "edge"),
            (3, 1, "berries", "edge"),
            (4, 1, "wood", "edge"), (4, 1, "berries", "edge"),
            (5, 2, "wood", "edge"),
            (6, 2, "wood", "edge"),
            (7, 3, "wood", "inner"),
            (8, 3, "berries", "inner"),
            (9, 3, "wood", "inner"),
            (10, 3, "berries", "inner"), (10, 3, "wood", "inner"),
        ),
    },
    # У разлома четыре прииска (вид участка = прииск): уровни добавляют места в те же прииски
    "mountain_rift": {
        "name": "Горный разлом",
        "plots": (
            (1, 2, "iron", "iron_mine"),
            (2, 1, "stone", "stone_mine"),
            (3, 1, "stone", "stone_mine"),
            (4, 2, "iron", "iron_mine"),
            (5, 2, "iron", "iron_mine"),
            (6, 2, "stone", "stone_mine"),
            (7, 3, "mithril", "mithril_mine"),
            (8, 2, "iron", "iron_mine"), (8, 1, "stone", "stone_mine"),
            (9, 2, "iron", "iron_mine"), (9, 1, "stone", "stone_mine"),
            (10, 3, "obsidian", "obsidian_mine"), (10, 3, "mithril", "mithril_mine"),
        ),
    },
    # Один загон, растущий с уровнем; каждый горожанин даёт и кожу, и мясо
    "barnyard": {
        "name": "Скотный двор",
        "plots": tuple(
            (level, places, ("leather", "meat"), "pen")
            for level, places in ((1, 2), (2, 1), (3, 1), (4, 2), (5, 2), (6, 2), (7, 3), (8, 3), (9, 3), (10, 6))
        ),
    },
    # Угольная шахта: своя таблица уровней, каждый уровень открывает копанку на добавленные места.
    # С 3 уровня раз в цикл отгрузки копь целиком может найти один камень; вид — по весам уровня.
    "black_pit": {
        "name": "Чёрная копь",
        "levels": {
            1: {"storage": 500, "max_workers": 2},
            2: {"storage": 800, "max_workers": 3},
            3: {"storage": 1000, "max_workers": 4},
            4: {"storage": 1400, "max_workers": 5},
            5: {"storage": 2000, "max_workers": 7},
            6: {"storage": 3000, "max_workers": 10},
            7: {"storage": 4500, "max_workers": 13},
            8: {"storage": 6000, "max_workers": 16},
            9: {"storage": 8000, "max_workers": 19},
            10: {"storage": 12000, "max_workers": 25},
        },
        "plots": tuple(
            (level, places, "coal", "dig")
            for level, places in ((1, 2), (2, 1), (3, 1), (4, 1), (5, 2), (6, 3), (7, 3), (8, 3), (9, 3), (10, 6))
        ),
        "bonus": {
            "from": "coal",
            "unit_bonus_chance": {
                3: 0.0043, 4: 0.0069, 5: 0.0106, 6: 0.0145,
                7: 0.0184, 8: 0.0237, 9: 0.0292, 10: 0.0351,
            },
            "weights": {
                3: {"jet": 100},
                4: {"jet": 65, "malachite": 35},
                5: {"jet": 45, "malachite": 35, "topaz": 20},
                6: {"jet": 33, "malachite": 29, "topaz": 23, "garnet": 15},
                7: {"jet": 25, "malachite": 24, "topaz": 22, "garnet": 17, "emerald": 12},
                8: {"jet": 19, "malachite": 19, "topaz": 19, "garnet": 17, "emerald": 15, "ruby": 11},
                9: {"jet": 14, "malachite": 15, "topaz": 16, "garnet": 16, "emerald": 15, "ruby": 14, "sapphire": 10},
                10: {
                    "jet": 11, "malachite": 12, "topaz": 13, "garnet": 14, "emerald": 14, "ruby": 14,
                    "sapphire": 14, "diamond": 8,
                },
            },
        },
    },
    # Городские хранилища: без горожан, общая вместимость на список товаров, 5 уровней
    "barn": {
        "name": "Амбар",
        "unit": "продукции",
        "stored": ("berries", "wheat", "meat"),
        "levels": {level: {"storage": storage, "max_workers": 0} for level, storage in
                   ((1, 1000), (2, 1500), (3, 2000), (4, 2700), (5, 4000))},
        "plots": (),
    },
    "warehouse": {
        "name": "Склад",
        "unit": "материалов",
        "stored": (
            "wood", "board", "flax", "cotton", "leather", "coal", "stone", "iron", "mithril", "obsidian",
            "iron_ingot", "steel", "hard_leather", "thick_leather", "cloth", "stone_block",
        ),
        "levels": {level: {"storage": storage, "max_workers": 0} for level, storage in
                   ((1, 2000), (2, 3000), (3, 5000), (4, 7000), (5, 10000))},
        "plots": (),
    },
    # Стойла — общий ресурс фракции; +2 места на каждое улучшение здания.
    "stable": {
        "name": "Конюшня",
        "unit": "стойл",
        "feed_resource": "wheat",
        "feed_kg_per_horse_hour": 2,
        "horse_base_price_silver": 10,
        "horse_price_growth_percent": 0,
        "upgrade_time_hours": 5,
        "stall_upgrades": {
            "wooden_stalls": {
                "name": "Приставные деревянные денники",
                "horse_capacity": 1,
                "wood_item_id": 60,
                "wood_cost": 300,
                "silver_cost": 50,
                "time_seconds": 10800,
            },
            "hayloft": {
                "name": "Внешний сеновал",
                "horse_capacity": 1,
                "wood_item_id": 60,
                "wood_cost": 300,
                "silver_cost": 50,
                "time_seconds": 10800,
            },
        },
        "levels": {
            level: {"storage": 0, "max_workers": 0, "stall_capacity": 4 + (level - 1) * 2}
            for level in range(1, 11)
        },
        "stored": (),
        "plots": (),
    },
}

# Материалы улучшения (id предмета в каталоге) — пока тестовые количества
UPGRADE_TEST_MATERIALS = {60: 5, 69: 5, 73: 5, 61: 5, 78: 5}  # древесина, камень, железо, доска, каменный блок
UPGRADE_TIME_HOURS = {1: 2, 2: 4, 3: 8, 4: 16, 5: 24, 6: 32, 7: 40, 8: 48, 9: 56}


def building_level_info(level, building=None):
    """Склад и число горожан на уровне; у здания может быть своя таблица (levels)."""
    table = BUILDINGS[building].get("levels", BUILDING_LEVELS) if building in BUILDINGS else BUILDING_LEVELS
    return table.get(int(level), table[1])


def bonus_resources(building):
    """Ресурсы случайной добычи здания в порядке появления по уровням."""
    bonus = BUILDINGS[building].get("bonus")
    if not bonus:
        return ()
    return tuple(dict.fromkeys(gem for level in sorted(bonus["weights"]) for gem in bonus["weights"][level]))


def building_config(building):
    if building not in BUILDINGS:
        raise ValueError("Неизвестное здание")
    return BUILDINGS[building]


def horse_purchase_price_silver(owned_count):
    """Price each next horse at 40% more than the previous whole-silver price."""
    price = BUILDINGS["stable"]["horse_base_price_silver"]
    growth = 100 + BUILDINGS["stable"]["horse_price_growth_percent"]
    for _ in range(max(0, int(owned_count))):
        price = math.ceil(price * growth / 100)
    return price


def _plot_resources(plot):
    """Ресурсы участка: строка или кортеж, если каждый горожанин даёт несколько ресурсов сразу."""
    return (plot[2],) if isinstance(plot[2], str) else tuple(plot[2])


def building_resources(building):
    """Ресурсы здания в порядке первого появления на участках (плюс случайная добыча)."""
    config = building_config(building)
    resources = list(config.get("stored", ()))
    resources.extend(resource for plot in config["plots"] for resource in _plot_resources(plot))
    resources.extend(bonus_resources(building))
    return tuple(dict.fromkeys(resources))


def plot_slot_ranges(building):
    """Для каждого участка — индексы слотов горожан, которые на нём работают."""
    ranges = []
    start = 0
    for _level, places, _resource, _kind in building_config(building)["plots"]:
        ranges.append(range(start, start + places))
        start += places
    return ranges


def slot_resources(building, slot_index):
    for plot, slots in zip(building_config(building)["plots"], plot_slot_ranges(building)):
        if slot_index in slots:
            return _plot_resources(plot)
    raise ValueError("Недопустимый слот горожанина")


def slot_resource(building, slot_index):
    return slot_resources(building, slot_index)[0]


def plot_stage(cycle_start_time, now, cycle_duration=CYCLE_DURATION_SEC):
    elapsed = max(0.0, float(now) - float(cycle_start_time))
    return min(PLOT_STAGE_COUNT - 1, int(elapsed / (cycle_duration / PLOT_STAGE_COUNT)))


def max_building_level(building=None):
    table = BUILDINGS[building].get("levels", BUILDING_LEVELS) if building in BUILDINGS else BUILDING_LEVELS
    return max(table)


def upgrade_requirements(level, building=None):
    """Что нужно для улучшения с уровня level на следующий; None на максимуме здания."""
    if int(level) >= max_building_level(building):
        return None
    time_hours = UPGRADE_TIME_HOURS[int(level)]
    if building in BUILDINGS:
        time_hours = BUILDINGS[building].get("upgrade_time_hours", time_hours)
    return {
        "materials": dict(UPGRADE_TEST_MATERIALS),
        "time_seconds": time_hours * 3600,
    }
