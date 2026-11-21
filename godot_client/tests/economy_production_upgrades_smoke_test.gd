extends Node

# Карточки улучшений фермы и лесопилки (economy_production_upgrades.gd): видимость по уровню,
# требования, цена и деньги, статус кнопки в порядке проверок Python, путь действия. Сетевых вызовов нет.
const UPGRADES := preload("res://scripts/economy_production_upgrades.gd")

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_buildings_and_paths()
	_check_availability()
	_check_progress_and_money()
	_check_requirements_and_funds()
	_check_card_status()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("economy_production_upgrades_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _ids(cards: Array) -> Array:
	var ids: Array = []
	for card in cards:
		ids.append(str(card[0]))
	return ids


func _check_buildings_and_paths() -> void:
	_check(UPGRADES.has_cards("farm"), "у фермы есть карточки")
	_check(UPGRADES.has_cards("lumber_camp"), "у лесопилки есть карточки")
	_check(not UPGRADES.has_cards("mountain_rift"), "у горного разлома карточек нет, там свой блок УЛУЧШИТЬ")
	_check(UPGRADES.action_path("farm") == "farm/upgrade", "путь фермы farm/upgrade")
	_check(UPGRADES.action_path("lumber_camp") == "lumber-camp/upgrade", "путь лесопилки lumber-camp/upgrade")


func _check_availability() -> void:
	_check(_ids(UPGRADES.available("farm", 1, {})) == ["ration", "wooden_plough", "farm_level_2"],
		"на 1 уровне фермы три карточки в порядке справочника")
	_check(_ids(UPGRADES.available("farm", 2, {})) == ["plough_field_edge", "whetstone", "flax_field_sowing"],
		"на 2 уровне фермы три карточки 2 уровня")
	_check(UPGRADES.available("farm", 3, {}).is_empty(), "на 3 уровне фермы карточек нет")
	_check(_ids(UPGRADES.available("lumber_camp", 1, {})) == ["logging_expansion", "strong_handle", "lumber_camp_level_2"],
		"на 1 уровне лесопилки три карточки")
	_check(_ids(UPGRADES.available("lumber_camp", 2, {"logging_expansion": true})) == ["logging_expansion"],
		"на 2 уровне лесопилки остаётся только завершённое улучшение")
	_check(UPGRADES.available("lumber_camp", 2, {}).is_empty(), "на 2 уровне лесопилки без завершённых карточек нет")


func _check_progress_and_money() -> void:
	var state := {"farm_upgrades": {"completed": {"ration": true}}}
	_check(UPGRADES.progress_of(state, "farm").get("completed", {}).get("ration", false) == true,
		"прогресс фермы читается из farm_upgrades")
	_check(UPGRADES.progress_of(state, "lumber_camp").is_empty(), "прогресс лесопилки пустой без lumber_camp_upgrades")
	_check(UPGRADES.spendable_copper({"spendable_treasury_copper": 1234}) == 1234, "деньги берутся из spendable_treasury_copper")
	_check(UPGRADES.spendable_copper({"treasury_silver_available": 5}) == 500, "без меди серебро переводится в медь")
	_check(UPGRADES.spendable_copper({"spendable_treasury_copper": 77, "treasury_silver_available": 5}) == 77,
		"серверное значение меди важнее серебра")
	_check(UPGRADES.price_copper({"silver_cost": 30}) == 3000, "цена 30 серебра = 3000 меди")
	_check(UPGRADES.price_copper({"gold_cost": 1}) == 10000, "цена 1 золота = 10000 меди")
	_check(UPGRADES.price_text({"silver_cost": 30}) == "/ 30 серебра", "подпись цены в серебре как в Python")
	_check(UPGRADES.price_text({"gold_cost": 1}) == "/ 1 золота", "подпись цены в золоте как в Python")


func _check_requirements_and_funds() -> void:
	var farm: Dictionary = UPGRADES.FARM_UPGRADES
	var lumber: Dictionary = UPGRADES.LUMBER_CAMP_UPGRADES
	_check(not UPGRADES.requirements_met("farm", "farm_level_2", farm["farm_level_2"], 1, {}),
		"улучшение 2 уровня без ромашки и плуга не открыто")
	_check(UPGRADES.requirements_met("farm", "farm_level_2", farm["farm_level_2"], 1,
		{"ration": true, "wooden_plough": true}), "оба предыдущих улучшения дают доступ")
	_check(not UPGRADES.requirements_met("farm", "farm_level_2", farm["farm_level_2"], 1, {"ration": true}),
		"одного предыдущего улучшения мало")
	_check(UPGRADES.requirements_met("farm", "flax_field_sowing", farm["flax_field_sowing"], 2, {"whetstone": true}),
		"лён требует 2 уровня и точильный камень")
	_check(not UPGRADES.requirements_met("farm", "flax_field_sowing", farm["flax_field_sowing"], 1, {"whetstone": true}),
		"лён на 1 уровне недоступен")
	_check(UPGRADES.requirements_met("lumber_camp", "lumber_camp_level_2", lumber["lumber_camp_level_2"], 1,
		{"logging_expansion": true, "strong_handle": true}), "лесопилка 2 уровня открыта после двух улучшений")
	_check(not UPGRADES.requirements_met("lumber_camp", "lumber_camp_level_2", lumber["lumber_camp_level_2"], 1,
		{"strong_handle": true}), "лесопилка 2 уровня без расширения вырубки закрыта")
	_check(UPGRADES.funds_available(farm["wooden_plough"], 2000, {"wood": 100}), "2000 меди и 100 древесины хватает")
	_check(not UPGRADES.funds_available(farm["wooden_plough"], 1999, {"wood": 100}), "1999 меди не хватает")
	_check(not UPGRADES.funds_available(farm["wooden_plough"], 2000, {"wood": 99}), "99 древесины не хватает")
	_check(not UPGRADES.funds_available(farm["flax_field_sowing"], 9999, {}), "лён за золото: 9999 меди мало")
	_check(UPGRADES.funds_available(farm["flax_field_sowing"], 10000, {}), "лён за золото: 10000 меди хватает")


func _check_card_status() -> void:
	var farm: Dictionary = UPGRADES.FARM_UPGRADES
	var lumber: Dictionary = UPGRADES.LUMBER_CAMP_UPGRADES
	var idle := {"completed": {}, "active_upgrade_id": null}
	var rich := 100000
	_check(UPGRADES.card_status("ration", farm["ration"], "farm", 1, idle, {}, rich) == UPGRADES.STATUS_START,
		"первое улучшение без требований можно начать")
	_check(UPGRADES.card_status("farm_level_2", farm["farm_level_2"], "farm", 1, idle, {"wood": 200}, rich)
		== UPGRADES.STATUS_REQUIREMENTS, "без предыдущих улучшений статус СНАЧАЛА ПРЕДЫДУЩИЕ")
	var ready := {"completed": {"ration": true, "wooden_plough": true}, "active_upgrade_id": null}
	_check(UPGRADES.card_status("farm_level_2", farm["farm_level_2"], "farm", 1, ready, {"wood": 200}, rich)
		== UPGRADES.STATUS_START, "с предыдущими улучшениями и ресурсами статус НАЧАТЬ")
	_check(UPGRADES.card_status("wooden_plough", farm["wooden_plough"], "farm", 1, idle, {"wood": 99}, rich)
		== UPGRADES.STATUS_FUNDS, "мало древесины — статус НЕДОСТАТОЧНО")
	var busy := {"completed": {}, "active_upgrade_id": "ration"}
	_check(UPGRADES.card_status("ration", farm["ration"], "farm", 1, busy, {}, rich) == UPGRADES.STATUS_ACTIVE,
		"активное улучшение показывает таймер")
	_check(UPGRADES.card_status("wooden_plough", farm["wooden_plough"], "farm", 1, busy, {"wood": 100}, rich)
		== UPGRADES.STATUS_BUSY, "другое улучшение при активном — ИДЁТ УЛУЧШЕНИЕ")
	var done := {"completed": {"ration": true}, "active_upgrade_id": "ration"}
	_check(UPGRADES.card_status("ration", farm["ration"], "farm", 1, done, {}, rich) == UPGRADES.STATUS_COMPLETE,
		"завершённое улучшение важнее активного")
	_check(UPGRADES.card_status("lumber_camp_level_2", lumber["lumber_camp_level_2"], "lumber_camp", 1, idle,
		{"wood": 300}, 5000) == UPGRADES.STATUS_REQUIREMENTS, "лесопилка 2 уровня без требований закрыта")
	var lumber_ready := {"completed": {"logging_expansion": true, "strong_handle": true}, "active_upgrade_id": null}
	_check(UPGRADES.card_status("lumber_camp_level_2", lumber["lumber_camp_level_2"], "lumber_camp", 1, lumber_ready,
		{"wood": 300}, 5000) == UPGRADES.STATUS_START, "лесопилка 2 уровня открывается и стоит 50 серебра и 300 древесины")
