extends RefCounted

# Справочник производственных зданий из core/production_buildings.py и ui/production_building_window.py.
# Сервер эти таблицы не присылает: базовые таймеры, уровни для следующего улучшения, порядок участков и бонус угольной копи.
# Всё, что меняется в игре (уровень, места, стадия, таймеры с бонусом), берётся из состояния здания.

const PLOT_STAGE_COUNT := 4
const BONUS_SLOT_BASE := 1000
const FARM_EXTRA_SLOT_BASE := 2000
const FARM_EXTRA_SLOT_STRIDE := 100
const FARM_EXTRA_WORKERS_LEVEL := 2

# RESOURCES[...]["label"]; самоцветы здесь нужны для текста бонуса.
const RESOURCE_LABELS := {
	"wheat": "Пшеница", "flax": "Лён", "cotton": "Хлопок", "wood": "Древесина", "berries": "Ягоды",
	"iron": "Железная руда", "stone": "Камень", "mithril": "Мифриловая руда", "obsidian": "Обсидиановая порода",
	"leather": "Кожа", "meat": "Мясо", "coal": "Уголь",
	"jet": "Гагат", "malachite": "Малахит", "topaz": "Топаз", "garnet": "Гранат",
	"emerald": "Изумруд", "ruby": "Рубин", "sapphire": "Сапфир", "diamond": "Алмаз",
}

# RESOURCES[...]["timer_sec"]: базовый цикл одной единицы. У самоцветов цикла нет.
const RESOURCE_TIMERS := {
	"wheat": 140, "flax": 480, "cotton": 980, "wood": 240, "berries": 360, "iron": 300,
	"stone": 200, "mithril": 900, "obsidian": 1400, "leather": 460, "meat": 680, "coal": 600,
}

# BUILDING_LEVELS: склад каждого товара и число горожан по уровням.
const BUILDING_LEVELS := {
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

# У Чёрной копи своя таблица горожан.
const BLACK_PIT_LEVELS := {
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
}

# Участки в порядке открытия: [уровень открытия, мест, ресурс или [ресурсы], вид участка].
# shape — форма на холсте; group_by_kind — один участок на вид (прииски, загон), как в Python.
const BUILDINGS := {
	"farm": {
		"shape": "fields", "asset_dir": "farm", "group_by_kind": false,
		"plot_names": {"wheat/field": "Поле", "flax/field": "Поле", "cotton/field": "Поле"},
		"plots": [
			[1, 2, "wheat", "field"], [2, 2, "wheat", "field"], [3, 1, "flax", "field"],
			[4, 1, "wheat", "field"], [4, 1, "flax", "field"], [5, 2, "wheat", "field"],
			[6, 2, "flax", "field"], [7, 3, "cotton", "field"], [8, 3, "wheat", "field"],
			[9, 3, "flax", "field"], [10, 3, "cotton", "field"], [10, 3, "flax", "field"],
		],
	},
	"lumber_camp": {
		"shape": "pie", "asset_dir": "lumber_camp", "group_by_kind": false,
		"plot_names": {"wood/edge": "Край леса", "berries/edge": "Опушка", "wood/inner": "Чаща", "berries/inner": "Большая поляна"},
		"plots": [
			[1, 2, "wood", "edge"], [2, 1, "wood", "edge"], [3, 1, "berries", "edge"],
			[4, 1, "wood", "edge"], [4, 1, "berries", "edge"], [5, 2, "wood", "edge"],
			[6, 2, "wood", "edge"], [7, 3, "wood", "inner"], [8, 3, "berries", "inner"],
			[9, 3, "wood", "inner"], [10, 3, "berries", "inner"], [10, 3, "wood", "inner"],
		],
	},
	"mountain_rift": {
		"shape": "rift", "asset_dir": "mountain_rift", "group_by_kind": true,
		"plot_names": {
			"iron_mine": "Прииск железа", "stone_mine": "Прииск камня",
			"mithril_mine": "Прииск мифрила", "obsidian_mine": "Прииск обсидиана",
		},
		"plots": [
			[1, 2, "stone", "stone_mine"], [2, 2, "iron", "iron_mine"], [3, 1, "stone", "stone_mine"],
			[4, 2, "iron", "iron_mine"], [5, 2, "iron", "iron_mine"], [6, 2, "stone", "stone_mine"],
			[7, 3, "mithril", "mithril_mine"], [8, 2, "iron", "iron_mine"], [8, 1, "stone", "stone_mine"],
			[9, 2, "iron", "iron_mine"], [9, 1, "stone", "stone_mine"],
			[10, 3, "obsidian", "obsidian_mine"], [10, 3, "mithril", "mithril_mine"],
		],
	},
	"barnyard": {
		"shape": "pen", "asset_dir": "farm", "group_by_kind": true,
		"plot_names": {"pen": "Загон"},
		"plots": [
			[1, 2, ["leather", "meat"], "pen"], [2, 1, ["leather", "meat"], "pen"], [3, 1, ["leather", "meat"], "pen"],
			[4, 2, ["leather", "meat"], "pen"], [5, 2, ["leather", "meat"], "pen"], [6, 2, ["leather", "meat"], "pen"],
			[7, 3, ["leather", "meat"], "pen"], [8, 3, ["leather", "meat"], "pen"], [9, 3, ["leather", "meat"], "pen"],
			[10, 6, ["leather", "meat"], "pen"],
		],
	},
	"black_pit": {
		"shape": "digs", "asset_dir": "farm", "group_by_kind": false,
		"plot_names": {"coal/dig": "Копанка"},
		"plots": [
			[1, 2, "coal", "dig"], [2, 1, "coal", "dig"], [3, 1, "coal", "dig"], [4, 1, "coal", "dig"],
			[5, 2, "coal", "dig"], [6, 3, "coal", "dig"], [7, 3, "coal", "dig"], [8, 3, "coal", "dig"],
			[9, 3, "coal", "dig"], [10, 6, "coal", "dig"],
		],
	},
}

# Бонус угольной копи: шанс самоцвета за единицу угля и веса самоцветов по уровням.
const BONUSES := {
	"black_pit": {
		"unit_bonus_chance": {
			3: 0.0043, 4: 0.0069, 5: 0.0106, 6: 0.0145, 7: 0.0184, 8: 0.0237, 9: 0.0292, 10: 0.0351,
		},
		"weights": {
			3: {"jet": 100},
			4: {"jet": 65, "malachite": 35},
			5: {"jet": 45, "malachite": 35, "topaz": 20},
			6: {"jet": 33, "malachite": 29, "topaz": 23, "garnet": 15},
			7: {"jet": 25, "malachite": 24, "topaz": 22, "garnet": 17, "emerald": 12},
			8: {"jet": 19, "malachite": 19, "topaz": 19, "garnet": 17, "emerald": 15, "ruby": 11},
			9: {"jet": 14, "malachite": 15, "topaz": 16, "garnet": 16, "emerald": 15, "ruby": 14, "sapphire": 10},
			10: {"jet": 11, "malachite": 12, "topaz": 13, "garnet": 14, "emerald": 14, "ruby": 14, "sapphire": 14, "diamond": 8},
		},
	},
}
