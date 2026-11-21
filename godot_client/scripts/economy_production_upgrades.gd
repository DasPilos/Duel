extends RefCounted

# Карточки улучшений Крестьянского поселения и Лагеря лесорубов: справочник из core/production_buildings.py
# и правила _draw_building_upgrade_cards из ui/production_building_window.py. В справочнике только поля,
# которые нужны карточкам; эффекты улучшений считает сервер. Сетевых вызовов здесь нет.

const CURRENCY := preload("res://scripts/currency_format.gd")

const BUILDING_FARM := "farm"
const BUILDING_LUMBER := "lumber_camp"
const STATUS_COMPLETE := "complete"
const STATUS_ACTIVE := "active"
const STATUS_REQUIREMENTS := "requirements"
const STATUS_FUNDS := "funds"
const STATUS_BUSY := "busy"
const STATUS_START := "start"

const FARM_UPGRADES := {
	"ration": {
		"name": "Самозахват",
		"requirement": "Нет",
		"result": "+1 место на первом поле пшеницы",
		"silver_cost": 30,
		"materials": {},
		"time_seconds": 30 * 60,
		"required_building_level": 1,
	},
	"wooden_plough": {
		"name": "Усиленный деревянный плуг",
		"requirement": "Нет",
		"result": "+5% к скорости производства пшеницы",
		"silver_cost": 20,
		"materials": {"wood": 100},
		"time_seconds": 60 * 60,
		"required_building_level": 1,
	},
	"farm_level_2": {
		"name": "Улучшить Крестьянское поселение",
		"requirement": "Самозахват и усиленный деревянный плуг",
		"result": "Крестьянское поселение — уровень 2",
		"silver_cost": 50,
		"materials": {"wood": 200},
		"time_seconds": 120 * 60,
		"required_building_level": 1,
		"required_farm_level": 1,
	},
	"plough_field_edge": {
		"name": "Перепахать окрайну",
		"requirement": "Крестьянское поселение — уровень 2",
		"result": "+2 места на втором поле пшеницы",
		"silver_cost": 80,
		"materials": {},
		"time_seconds": 140 * 60,
		"required_farm_level": 2,
	},
	"whetstone": {
		"name": "Точильный камень",
		"requirement": "Крестьянское поселение — уровень 2",
		"result": "+15% к производству пшеницы",
		"silver_cost": 90,
		"materials": {},
		"time_seconds": 140 * 60,
		"required_farm_level": 2,
	},
	"flax_field_sowing": {
		"name": "Засеять поле льна",
		"requirement": "Крестьянское поселение — уровень 2, Точильный камень",
		"result": "Крестьянское поселение — уровень 3",
		"gold_cost": 1,
		"materials": {},
		"time_seconds": 180 * 60,
		"required_farm_level": 2,
	},
}

const LUMBER_CAMP_UPGRADES := {
	"logging_expansion": {
		"name": "Расширение вырубки",
		"requirement": "Нет",
		"result": "+1 место на первом участке древесины",
		"silver_cost": 50,
		"materials": {},
		"time_seconds": 40 * 60,
		"required_building_level": 1,
	},
	"strong_handle": {
		"name": "Усиленная рукоять",
		"requirement": "Нет",
		"result": "+8% к скорости вырубки",
		"silver_cost": 70,
		"materials": {},
		"time_seconds": 60 * 60,
		"required_building_level": 1,
	},
	"lumber_camp_level_2": {
		"name": "Улучшить лесопилку",
		"requirement": "Расширение вырубки и усиленная рукоять",
		"result": "Лесопилка — уровень 2",
		"silver_cost": 50,
		"materials": {"wood": 300},
		"time_seconds": 140 * 60,
		"required_building_level": 1,
	},
}

# Предыдущие улучшения, которые карточка показывает как требование (таблица интерфейса Python).
const FARM_PREREQUISITES := {
	"farm_level_2": ["ration", "wooden_plough"],
	"flax_field_sowing": ["whetstone"],
}
const LUMBER_CAMP_PREREQUISITES := {
	"lumber_camp_level_2": ["logging_expansion", "strong_handle"],
}


static func has_cards(building: String) -> bool:
	return building == BUILDING_FARM or building == BUILDING_LUMBER


static func upgrades_of(building: String) -> Dictionary:
	if building == BUILDING_FARM:
		return FARM_UPGRADES
	if building == BUILDING_LUMBER:
		return LUMBER_CAMP_UPGRADES
	return {}


static func progress_of(state: Dictionary, building: String) -> Dictionary:
	var key := "lumber_camp_upgrades" if building == BUILDING_LUMBER else "farm_upgrades"
	return _dict(state.get(key, {}))


# Путь действия, как в Python: у лесопилки дефис, у фермы косая черта.
static func action_path(building: String) -> String:
	return "lumber-camp/upgrade" if building == BUILDING_LUMBER else "farm/upgrade"


static func spendable_copper(state: Dictionary) -> int:
	var fallback := int(state.get("treasury_silver_available", 0)) * CURRENCY.COPPER_PER_SILVER
	return int(state.get("spendable_treasury_copper", fallback))


# Карточка видна на своём уровне здания; у лесопилки завершённые улучшения остаются видимыми.
static func available(building: String, building_level: int, completed: Dictionary) -> Array:
	var level_key := _level_key(building)
	var upgrades := upgrades_of(building)
	var cards: Array = []
	for upgrade_id in upgrades:
		var upgrade: Dictionary = upgrades[upgrade_id]
		var on_level := int(upgrade.get(level_key, 1)) == building_level
		var kept := building == BUILDING_LUMBER and bool(completed.get(upgrade_id, false))
		if on_level or kept:
			cards.append([str(upgrade_id), upgrade])
	return cards


static func requirements_met(building: String, upgrade_id: String, upgrade: Dictionary, building_level: int, completed: Dictionary) -> bool:
	if building_level < int(upgrade.get(_level_key(building), 1)):
		return false
	for required_id in _prerequisites_of(building, upgrade_id):
		if not bool(completed.get(required_id, false)):
			return false
	return true


static func price_copper(upgrade: Dictionary) -> int:
	if upgrade.has("gold_cost"):
		return int(upgrade["gold_cost"]) * CURRENCY.COPPER_PER_GOLD
	return int(upgrade.get("silver_cost", 0)) * CURRENCY.COPPER_PER_SILVER


static func price_text(upgrade: Dictionary) -> String:
	if upgrade.has("gold_cost"):
		return "/ %d золота" % int(upgrade["gold_cost"])
	return "/ %d серебра" % int(upgrade.get("silver_cost", 0))


static func funds_available(upgrade: Dictionary, copper: int, warehouse: Dictionary) -> bool:
	if copper < price_copper(upgrade):
		return false
	var materials := _dict(upgrade.get("materials", {}))
	for resource in materials:
		if int(warehouse.get(resource, 0)) < int(materials[resource]):
			return false
	return true


# Статус карточки в порядке проверок Python: установлено, идёт, требования, деньги, занято, можно начать.
static func card_status(upgrade_id: String, upgrade: Dictionary, building: String, building_level: int, progress: Dictionary, warehouse: Dictionary, copper: int) -> String:
	var completed := _dict(progress.get("completed", {}))
	if bool(completed.get(upgrade_id, false)):
		return STATUS_COMPLETE
	var active: Variant = progress.get("active_upgrade_id")
	if active != null and str(active) == upgrade_id:
		return STATUS_ACTIVE
	if not requirements_met(building, upgrade_id, upgrade, building_level, completed):
		return STATUS_REQUIREMENTS
	if not funds_available(upgrade, copper, warehouse):
		return STATUS_FUNDS
	if active != null:
		return STATUS_BUSY
	return STATUS_START


static func _level_key(building: String) -> String:
	return "required_building_level" if building == BUILDING_LUMBER else "required_farm_level"


static func _prerequisites_of(building: String, upgrade_id: String) -> Array:
	var table := LUMBER_CAMP_PREREQUISITES if building == BUILDING_LUMBER else FARM_PREREQUISITES
	var names: Variant = table.get(upgrade_id, [])
	return names if names is Array else []


static func _dict(value: Variant) -> Dictionary:
	return value if value is Dictionary else {}
