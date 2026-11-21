extends Node

# Режим мага боя: макет стола выбирается по профессии бойца (как сцена мага в Python), заголовок как в
# mage_battle_scene.py. Проверки идут по фикстурам боя; сервер не нужен.
const RULES := preload("res://scripts/deck_battle_layout_rules.gd")
const MAGE := preload("res://scripts/deck_battle_mage_rules.gd")
const VIEW_SCRIPT := preload("res://scripts/deck_battle_view.gd")
const VISUAL := preload("res://scripts/deck_battle_visual_state.gd")
const FIXTURE_DIR := "res://tests/fixtures/deck_battle/"

var _failures: Array[String] = []
var _checks := 0
var _view


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var project_dir := ProjectSettings.globalize_path("res://")
	_check_switch()
	_check_layout_rects()
	_check_model(project_dir)
	_check_title()
	await _check_view()
	_check_flights_and_numbers(project_dir)
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_battle_mage_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_switch() -> void:
	var data := _fixture("planning_hand.json")
	data["fighter"]["type"] = "mage"
	_check(MAGE.is_mage(data), "профессия mage: макет мага")
	data["fighter"]["type"] = "battle_mage"
	_check(MAGE.is_mage(data), "устаревший battle_mage тоже маг")
	data["fighter"]["type"] = "harmonist"
	_check(MAGE.is_mage(data), "harmonist тоже маг (PROFESSION_CARD_GROUPS)")
	data["fighter"]["type"] = "warrior"
	_check(not MAGE.is_mage(data), "воин: обычный макет")
	_check(not MAGE.is_mage({"phase": "planning"}) and not MAGE.is_mage({"fighter": "bad"}), "без бойца обычный макет")
	_check(RULES.layout_for_state(data) == RULES.STANDARD_LAYOUT, "воин получает обычный макет стола")
	data["fighter"]["type"] = "mage"
	_check(RULES.layout_for_state(data) == MAGE.LAYOUT, "маг получает макет mage_battle_scene.py")
	data["fighter"]["type"] = "warrior"
	data["opponent"]["type"] = "mage"
	_check(not MAGE.is_mage(data), "соперник-маг не переводит воина в макет мага")
	data["fighter"]["type"] = "mage"
	data["opponent"]["type"] = "warrior"
	_check(MAGE.is_mage(data), "маг-игрок получает макет мага при любом сопернике")


func _check_layout_rects() -> void:
	_check(MAGE.LAYOUT["card_table"] == Rect2(20, 170, 1880, 520), "стол мага 1880x520 (mage_battle_scene.py)")
	_check(MAGE.LAYOUT["deck"] == Rect2(1675, 285, 170, 300) and MAGE.LAYOUT["discard"] == Rect2(75, 285, 170, 300), "колода и сброс мага")
	_check(MAGE.LAYOUT["turn_bar"] == Rect2(810, 715, 300, 18), "полоса хода мага по центру")
	var player_hand: Rect2 = MAGE.LAYOUT["player_hand"]
	_check(RULES.row_card_rect(player_hand, 7, 0) == Rect2(375, 850, 150, 180), "рука мага: карты 150x180, первая x=375")
	var enemy_hand: Rect2 = MAGE.LAYOUT["enemy_hand"]
	_check(RULES.row_card_rect(enemy_hand, 7, 6) == Rect2(1370, 20, 140, 130), "рука соперника мага: карты 140x130, последняя x=1370")
	_check(RULES.stats_panel_rect("player", 7, MAGE.LAYOUT) == Rect2(10, 850, 359, 200), "панель характеристик игрока в макете мага")
	_check(RULES.stats_panel_rect("enemy", 7, MAGE.LAYOUT) == Rect2(1516, 850, 394, 200), "панель соперника в макете мага от его руки")
	var table: Rect2 = MAGE.LAYOUT["card_table"]
	_check(RULES.draft_slot_rect("starting", 0, table) == Rect2(95, 218, 150, 200), "стартовый драфт мага: слот 0")
	_check(RULES.draft_slot_rect("starting", 11, table) == Rect2(95, 426, 150, 200), "стартовый драфт мага: слот 11 во втором ряду")
	_check(RULES.draw_choice_area("player", MAGE.LAYOUT) == Rect2(390, 544, 1140, 96), "область выбора добора мага")
	_check(RULES.pile_rect("deck", MAGE.LAYOUT) == MAGE.LAYOUT["deck"] and RULES.pile_rect("discard") == RULES.DISCARD_RECT, "колода по макету, обычный сброс по умолчанию")


func _check_model(project_dir: String) -> void:
	var data := _fixture("planning_hand.json")
	data["fighter"]["type"] = "mage"
	var model := RULES.build_draw_model(data, {"project_dir": project_dir})
	_check(bool(model["mage"]) and model["layout"] == MAGE.LAYOUT, "модель мага: флаг и макет")
	var piles: Dictionary = model["piles"]
	_check((piles["deck"]["rect"] as Rect2) == MAGE.LAYOUT["deck"] and (piles["discard"]["rect"] as Rect2) == MAGE.LAYOUT["discard"], "модель мага: колода и сброс по макету")
	var player_hand: Rect2 = MAGE.LAYOUT["player_hand"]
	var hand_card: Dictionary = {}
	for entry in model["cards"]:
		if entry["zone"] == "hand" and entry["index"] == 2:
			hand_card = entry
	_check(hand_card.get("rect") == RULES.row_card_rect(player_hand, 5, 0), "модель мага: карта руки в ряду макета мага")
	var standard := RULES.build_draw_model(_fixture("planning_hand.json"), {"project_dir": project_dir})
	_check(not bool(standard["mage"]) and standard["layout"] == RULES.STANDARD_LAYOUT, "воин: обычная модель")


func _check_title() -> void:
	_check(MAGE.title_visible("planning") and MAGE.title_visible("draw") and not MAGE.title_visible("result"), "заголовок скрыт только на результате")


func _check_view() -> void:
	_view = VIEW_SCRIPT.new()
	_view.size = RULES.DESIGN_SIZE
	add_child(_view)
	await get_tree().process_frame
	var planning := _fixture("planning_hand.json")
	planning["fighter"]["type"] = "mage"
	_view.set_snapshot(planning)
	_check(_view.mage_layout() and _view.active_layout() == MAGE.LAYOUT, "вид: макет мага по профессии бойца")
	_check(_view.mage_title_visible() and _view.mage_title_text() == "МАГИЧЕСКАЯ ДУЭЛЬ", "вид: заголовок мага")
	_check(_view.card_view("hand", 2).position == RULES.row_card_rect(MAGE.LAYOUT["player_hand"], 5, 0).position, "вид: рука стоит в ряду макета мага")
	_check(_view.card_view("hand", 2).size == Vector2(150, 180), "вид: карта руки мага 150x180")
	_view.set_input_locked(true)
	_check(_view.mage_title_visible(), "вид: заголовок мага виден и во время розыгрыша")
	_view.set_input_locked(false)
	var finished := _fixture("outcome_win.json")
	finished["fighter"]["type"] = "mage"
	_view.set_snapshot(finished)
	_check(not _view.mage_title_visible(), "вид: на результате заголовок скрыт")
	var draft := _fixture("draft_starting.json")
	draft["fighter"]["type"] = "mage"
	_view.set_snapshot(draft)
	_check(_view.mage_title_visible(), "вид: заголовок мага в драфте")
	_check(_view.card_view("table", 0).position == RULES.draft_slot_rect("starting", 0, MAGE.LAYOUT["card_table"]).position, "вид: слоты драфта в столе мага")
	_view.set_snapshot(_fixture("planning_hand.json"))
	_check(not _view.mage_layout() and not _view.mage_title_visible(), "вид: воин возвращает обычный макет без заголовка")
	_check(_view.active_layout() == RULES.STANDARD_LAYOUT and _view.card_view("hand", 2).position == RULES.row_card_rect(RULES.PLAYER_HAND_RECT, 5, 0).position, "вид: рука снова стоит по обычному макету")


func _check_flights_and_numbers(project_dir: String) -> void:
	var draft := _fixture("draft_starting.json")
	draft["fighter"]["type"] = "mage"
	var flights := VISUAL.reveal_flights(draft, project_dir)
	var slot_center := RULES.draft_slot_rect("starting", 3, MAGE.LAYOUT["card_table"]).get_center()
	var deck_center := (MAGE.LAYOUT["deck"] as Rect2).get_center()
	_check((flights[3]["to"] as Vector2).is_equal_approx(slot_center) and (flights[0]["from"] as Vector2).is_equal_approx(deck_center), "полёт карт мага: из колоды мага в слот стола мага")
	var exchange := [{"side": "player", "card": "Удар", "damage": 5, "critical": false, "dodged": false, "healed": 0}]
	var mage_specs := VISUAL.floating_specs(exchange, [], MAGE.LAYOUT)
	var standard_specs := VISUAL.floating_specs(exchange, [])
	_check(mage_specs.size() == 1 and standard_specs.size() == 1, "число урона: одна подпись")
	_check(float(mage_specs[0]["x"]) == 1713.0 and float(standard_specs[0]["x"]) == 1730.0, "числа урона соперника стоят над панелью его макета (1713 у мага, 1730 обычно)")
	_check(str(mage_specs[0]["text"]) == "-5 HP", "текст числа не зависит от макета")


func _fixture(file_name: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(FIXTURE_DIR + file_name))
	return parsed if parsed is Dictionary else {}


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)
