extends Node

const RULES := preload("res://scripts/deck_battle_layout_rules.gd")
const FIXTURE_DIR := "res://tests/fixtures/deck_battle/"
const FIXTURE_FILES := [
	"draft_starting.json",
	"draft_redraft.json",
	"planning_hand.json",
	"draw_choice.json",
	"outcome_win.json",
]
const SNAPSHOT_KEYS := [
	"battle_id", "group_id", "phase", "seconds_left", "timeout_count", "draft_mode", "turn", "side",
	"fighter", "opponent", "hand", "selected", "table", "draw_choices", "can_select", "confirmed",
	"opponent_confirmed", "opponent_draft_picks", "opponent_last_draft_picks", "last_exchange", "history",
	"outcome", "reward_card_keys",
]

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var project_dir := ProjectSettings.globalize_path("res://")
	_check_constants()
	_check_paths(project_dir)
	_check_hand_rows()
	_check_draft_rows()
	_check_draft_slot_keys()
	_check_panels()
	_check_timer()
	_check_bars_and_text()
	_check_characteristics()
	_check_fixtures(project_dir)
	_check_draw_model_edges(project_dir)
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_battle_layout_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_constants() -> void:
	_check(RULES.DESIGN_SIZE == Vector2(1920, 1080), "размер макета 1920x1080 (core/settings.py:2-3)")
	_check(RULES.CARD_SIZE == Vector2(150, 200), "размер карты 150x200 (card_area.py:17-18)")
	_check(RULES.CARD_TABLE_RECT == Rect2(160, 325, 1600, 430), "прямоугольник стола (deck/settings.py)")
	_check(RULES.TURN_BAR_RECT == Rect2(820, 831, 280, 11), "полоса таймера (deck/settings.py)")
	_check(RULES.DECK_RECT == Rect2(1584, 440, 150, 200), "прямоугольник колоды (deck/settings.py)")
	_check(RULES.DISCARD_RECT == Rect2(186, 440, 150, 200), "прямоугольник сброса (deck/settings.py)")
	_check(RULES.TURN_DECISION_SECONDS == 60, "таймер хода 60 с (core/settings.py:153)")
	_check(RULES.DRAW_CHOICE_SECONDS == 15, "таймер выбора карты 15 с (deck/settings.py:18)")
	_check(RULES.DRAFT_TIMEOUT_SECONDS == 90, "таймер драфта 90 с (deck/settings.py:17)")
	_check(RULES.TURN_WARNING_RED_SECONDS == 10 and RULES.TURN_WARNING_YELLOW_SECONDS == 30, "пороги таймера 10 и 30 с (core/settings.py:154-155)")
	_check(RULES.MAX_HAND_SIZE == 7, "размер руки 7 (deck/combat/card_battle.py:30)")
	_check(RULES.DRAFT_COLUMNS == 5 and RULES.STARTING_DRAFT_COLUMNS == 11, "колонки драфта 5 и 11 (card_area.py:21-22)")


func _check_paths(project_dir: String) -> void:
	_check(RULES.assets_root("E:/python/game/godot_client") == "E:/python/game/assets", "корень ассетов: ../assets от godot_client")
	_check(RULES.assets_root("E:/python/game/godot_client/") == "E:/python/game/assets", "корень ассетов со слешем в конце")
	_check(RULES.project_root("E:/python/game/godot_client") == "E:/python/game", "корень Python-проекта")
	_check(RULES.asset_path("E:/python/game/godot_client", RULES.TABLE_ASSET) == "E:/python/game/assets/combat/battle_table.png", "путь стола")
	_check(RULES.asset_path("E:/python/game/godot_client", RULES.CARD_BACK_ASSET) == "E:/python/game/assets/cards/backs/card_back.png", "путь рубашки карты")
	_check(RULES.asset_path("E:/python/game/godot_client", RULES.BACKGROUND_ASSET) == "E:/python/game/assets/combat/background.png", "путь фона")
	_check(RULES.asset_path("E:/python/game/godot_client", RULES.HIT_PLACEHOLDER_ASSET) == "E:/python/game/assets/combat/hit_placeholder.png", "путь заглушки удара")
	_check(FileAccess.file_exists(RULES.asset_path(project_dir, RULES.TABLE_ASSET)), "battle_table.png читается из ../assets")
	_check(FileAccess.file_exists(RULES.asset_path(project_dir, RULES.BACKGROUND_ASSET)), "background.png читается из ../assets")
	_check(FileAccess.file_exists(RULES.asset_path(project_dir, RULES.CARD_BACK_ASSET)), "card_back.png читается из ../assets")
	var table := Image.load_from_file(RULES.asset_path(project_dir, RULES.TABLE_ASSET))
	_check(table != null and table.get_size() == Vector2i(1600, 430), "battle_table.png 1600x430 совпадает с прямоугольником стола (blit без масштаба)")
	_check(RULES.resolve_image_path("", project_dir) == "", "пустой image_path даёт пустой путь (текстовое лицо)")
	_check(RULES.resolve_image_path("assets/cards/faces/deaf_defense.png", project_dir).ends_with("/assets/cards/faces/deaf_defense.png"), "image_path от корня Python-проекта")
	_check(RULES.resolve_image_path("E:/somewhere/card.png", project_dir) == "E:/somewhere/card.png", "абсолютный image_path не меняется")
	_check(RULES.resolve_image_path("assets/cards/faces/deaf_defense.png", project_dir).ends_with("/assets/cards/faces/deaf_defense.png"), "относительный image_path собирается по правилу card_area.py:846-849")


func _check_hand_rows() -> void:
	var hand := RULES.PLAYER_HAND_RECT
	_check(RULES.row_card_rect(hand, 7, 0) == Rect2(375, 850, 150, 200), "рука 7 карт: первая карта x=375 (центр 960)")
	_check(RULES.row_card_rect(hand, 7, 6) == Rect2(1395, 850, 150, 200), "рука 7 карт: последняя карта x=1395, шаг 170")
	var first := RULES.row_card_rect(hand, 7, 0)
	var last := RULES.row_card_rect(hand, 7, 6)
	_check((first.position.x + last.end.x) / 2.0 == 960.0, "рука центрирована на 960")
	_check(RULES.row_card_rect(hand, 1, 0) == Rect2(885, 850, 150, 200), "одна карта в руке по центру")
	_check(RULES.row_card_rect(hand, 2, 0) == Rect2(800, 850, 150, 200), "две карты: первая x=800")
	_check(RULES.row_card_rect(hand, 2, 1) == Rect2(970, 850, 150, 200), "две карты: вторая x=970")
	_check(RULES.row_card_rect(RULES.ENEMY_HAND_RECT, 7, 0) == Rect2(375, 10, 150, 200), "рука противника сверху")
	_check(RULES.row_card_rect(RULES.PLAYER_SELECTED_RECT, 2, 0) == Rect2(790, 535, 150, 200), "выбранные карты: центр области 950")
	_check(RULES.row_card_rect(RULES.PLAYER_SELECTED_RECT, 2, 1) == Rect2(960, 535, 150, 200), "выбранные карты: вторая x=960")
	_check(RULES.draw_choice_area("player") == Rect2(350, 559, 1200, 176), "область выбора добора: сдвиг +24, высота -24")
	_check(RULES.draw_choice_area("enemy") == Rect2(350, 349, 1200, 176), "область выбора добора противника")
	_check(RULES.row_card_rect(RULES.draw_choice_area("player"), 3, 0) == Rect2(705, 559, 150, 176), "три карты добора: высота 176")
	_check(RULES.row_card_rect(hand, 0, 0).size.x == 150.0, "пустой ряд не делит на ноль")


func _check_draft_rows() -> void:
	_check(RULES.draft_columns("starting") == 11 and RULES.draft_columns("redraft") == 5, "колонки драфта по режиму")
	_check(RULES.draft_slot_rect("starting", 0) == Rect2(161, 373, 138, 184), "стартовый драфт: слот 0 (ширина 138, высота round(138*200/150)=184)")
	_check(RULES.draft_slot_rect("starting", 10) == Rect2(1621, 373, 138, 184), "стартовый драфт: слот 10 в первом ряду")
	_check(RULES.draft_slot_rect("starting", 11) == Rect2(161, 565, 138, 184), "стартовый драфт: слот 11 начинает второй ряд")
	_check(RULES.draft_slot_rect("starting", 21).end.y <= RULES.CARD_TABLE_RECT.end.y, "стартовый драфт на 22 слота влезает в стол")
	_check(RULES.draft_slot_rect("redraft", 0) == Rect2(545, 330, 150, 200), "повторный драфт: слот 0 по центру стола")
	_check(RULES.draft_slot_rect("redraft", 4) == Rect2(1225, 330, 150, 200), "повторный драфт: пятая колонка")
	_check(RULES.draft_slot_rect("redraft", 5) == Rect2(545, 550, 150, 200), "повторный драфт: второй ряд через зазор 20")


func _check_draft_slot_keys() -> void:
	var fresh := RULES.draft_slot_keys([], ["a", "b"])
	_check(fresh == ["a", "b"], "новый драфт: слоты в порядке стола")
	var kept := RULES.draft_slot_keys(["a", "b", "c"], ["a", "c"])
	_check(kept.size() == 3 and kept[0] == "a" and kept[1] == null and kept[2] == "c", "убранная карта оставляет пустой слот")
	var reset := RULES.draft_slot_keys(["a", null, "c"], ["a", "c", "d"])
	_check(reset == ["a", "c", "d"], "появилась новая карта: слоты пересобираются")
	var emptied := RULES.draft_slot_keys([null, null], [])
	_check(emptied.size() == 2 and emptied[0] == null, "пустой стол сохраняет размер слотов")


func _check_panels() -> void:
	_check(RULES.corner_card_rect("player") == Rect2(10, 10, 310, 170), "угловая карточка игрока (duel_renderer: x=10, y=10)")
	_check(RULES.corner_card_rect("enemy") == Rect2(1600, 10, 310, 170), "угловая карточка противника: x=W-320")
	_check(RULES.stats_panel_rect("player") == Rect2(10, 850, 359, 200), "панель характеристик игрока: ширина до первой карты руки")
	_check(RULES.stats_panel_rect("enemy") == Rect2(1551, 850, 359, 200), "панель характеристик противника: от последней карты руки + 6")
	_check(RULES.stats_panel_rect("player", 9).size.x == 310.0, "минимальная ширина панели характеристик 310")
	_check(RULES.pile_rect("deck") == RULES.DECK_RECT and RULES.pile_rect("discard") == RULES.DISCARD_RECT, "колода и сброс по прямоугольникам")


func _check_timer() -> void:
	_check(RULES.timer_total_seconds("planning") == 60, "таймер хода: 60 с")
	_check(RULES.timer_total_seconds("draw") == 15, "таймер выбора: 15 с")
	_check(RULES.timer_total_seconds("draft") == 90, "таймер драфта: 90 с")
	_check(RULES.timer_total_seconds("result") == 0, "в результате таймера нет")
	_check(is_equal_approx(RULES.timer_fraction(42, 60), 0.7), "доля таймера 42/60 = 0.7")
	_check(RULES.timer_fraction(90, 60) == 1.0, "доля таймера ограничена единицей")
	_check(RULES.timer_fraction(-3, 60) == 0.0, "отрицательные секунды дают 0")
	_check(RULES.timer_fraction(5, 0) == 0.0, "нулевой общий таймер не делит на ноль")
	_check(RULES.timer_color(10) == RULES.COLOR_TIMER_RED, "10 с и меньше: красный")
	_check(RULES.timer_color(11) == RULES.COLOR_TIMER_YELLOW and RULES.timer_color(30) == RULES.COLOR_TIMER_YELLOW, "11-30 с: жёлтый")
	_check(RULES.timer_color(31) == RULES.COLOR_TIMER_GREEN, "больше 30 с: зелёный")
	_check(RULES.timer_label("planning", 42) == "ВАШ ХОД", "подпись хода")
	_check(RULES.timer_label("draw", 9) == "ВЫБОР КАРТЫ: 9 СЕК", "подпись выбора карты")
	_check(RULES.draft_timer_text(75) == "ОСТАЛОСЬ 75 СЕК", "подпись таймера драфта")


func _check_bars_and_text() -> void:
	_check(RULES.bar_fraction(70, 70) == 1.0 and RULES.bar_fraction(35, 70) == 0.5, "доля полосы HP/MP")
	_check(RULES.bar_fraction(5, 0) == 0.0 and RULES.bar_fraction(-1, 10) == 0.0 and RULES.bar_fraction(20, 10) == 1.0, "доля полосы ограничена 0..1")
	var rage := RULES.resource_bar_spec("rage")
	_check(rage.get("label") == "Ярость" and rage.get("color") == Color8(200, 100, 80), "полоса ярости: подпись и цвет (duel_renderer.py:RESOURCE_BARS)")
	_check(RULES.resource_bar_spec("concentration").get("label") == "Концентрация", "полоса концентрации")
	_check(RULES.resource_bar_spec("mana").is_empty() and RULES.resource_bar_spec("necrotism").is_empty(), "мана и некротизм не получают третью полосу")
	_check(RULES.card_cost_text({"resource_type": "unique", "resource_cost": 14}, "necrotism") == "14 НЕКРОТИЗМА", "стоимость Некроманта: метка НЕКРОТИЗМА")
	_check(RULES.card_cost_text({"resource_type": "unique", "resource_cost": 0}, "mana") == "0 РЕС.", "обычная уникальная метка РЕС.")
	_check(RULES.card_cost_text({"resource_type": "mana", "resource_cost": 6}, "mana") == "6 МАНА", "стоимость маной")
	_check(RULES.card_name_color("rage") == RULES.RESOURCE_COST_COLORS["rage"], "цвет названия по ресурсу")
	_check(RULES.card_name_color("zzz") == RULES.DEFAULT_NAME_COLOR, "неизвестный ресурс: цвет по умолчанию")
	_check(RULES.card_fill_color(true, true) == RULES.COLOR_CARD_SELECTED, "выбранная карта: цвет выбора")
	_check(RULES.card_fill_color(false, true) == RULES.COLOR_CARD_AVAILABLE, "доступная карта: цвет доступности")
	_check(RULES.card_fill_color(false, false) == RULES.COLOR_CARD_FACE, "обычная карта: цвет лица")


func _check_characteristics() -> void:
	var fighter := _fixture("planning_hand.json")["fighter"] as Dictionary
	var panel := RULES.fighter_panel("player", fighter)
	var stats: Array = panel["characteristics"]["stats"]
	_check(stats.size() == 7, "семь характеристик (duel_renderer.py:ALL_STATS)")
	_check(stats[0]["text"] == "Сила: 6" and stats[6]["text"] == "Выносливость: 5", "подписи характеристик по Python: %s | %s" % [stats[0]["text"], stats[6]["text"]])
	var derived: Array = panel["characteristics"]["derived"]
	var keys: Array = []
	for row in derived:
		keys.append(row["key"])
	_check(keys == ["Урон", "Уворот", "Крит"], "воин: Урон, Уворот, Крит; Маг Урон не показывается")
	_check(derived[0]["text"] == "Урон: 6", "Урон = сила 6 (без оружия, как в снимке)")
	_check(derived[1]["text"] == "Уворот: 6%", "Уворот = ловкость 3 * 2")
	_check(derived[2]["text"] == "Крит: 5% × 170%", "Крит: базовый 5% и множитель 1.5 + интуиция 4 * 0.05")
	var mage := _fixture("draft_redraft.json")["fighter"] as Dictionary
	var mage_keys: Array = []
	for row in RULES.fighter_panel("player", mage)["characteristics"]["derived"]:
		mage_keys.append(row["key"])
	_check(mage_keys.has("Маг Урон"), "маг: показывается Маг Урон")
	var bars: Array = panel["bars"]
	_check(bars.size() == 3 and bars[2]["text"] == "Ярость: 68/68", "воин: полоса ярости 68/68")
	var mage_bars: Array = RULES.fighter_panel("enemy", _fixture("planning_hand.json")["opponent"])["bars"]
	_check(mage_bars.size() == 2 and mage_bars[0]["text"] == "HP: 35/40", "маг: две полосы HP и MP")
	_check(is_equal_approx(float(bars[0]["fraction"]), 106.0 / 120.0), "доля HP воина 106/120")
	_check(RULES.characteristics({}).get("stats", [1]).is_empty(), "пустой боец: характеристик нет")


func _check_fixtures(project_dir: String) -> void:
	for file_name in FIXTURE_FILES:
		var data := _fixture(file_name)
		var has_all := true
		for key in SNAPSHOT_KEYS:
			if not data.has(key):
				has_all = false
		_check(has_all, "фикстура %s содержит все 23 ключа снимка" % file_name)
	var planning := _fixture("planning_hand.json")
	var model := RULES.build_draw_model(planning, {"project_dir": project_dir})
	_check(model["phase"] == "planning" and model["show_board"] and model["show_timer"], "планирование: доска и таймер видны")
	_check(model["timer"]["total"] == 60 and is_equal_approx(float(model["timer"]["fraction"]), 0.7), "планирование: таймер 42 из 60")
	_check(model["timer"]["label"] == "ВАШ ХОД" and model["timer"]["color"] == RULES.COLOR_TIMER_GREEN, "планирование: подпись и зелёный цвет")
	var zones := _zone_counts(model["cards"])
	_check(zones == {"hand": 5, "selected": 2}, "планирование: рука без выбранных (5) и два выбранных")
	var pressable := 0
	var unavailable_pressable := false
	for entry in model["cards"]:
		if entry["pressable"]:
			pressable += 1
		if entry["zone"] == "hand" and entry["index"] == 6 and entry["pressable"]:
			unavailable_pressable = true
	_check(pressable == 6 and not unavailable_pressable, "планирование: нажимаются 4 доступные карты руки и 2 выбранные")
	var selected_entry: Dictionary = {}
	for entry in model["cards"]:
		if entry["zone"] == "selected" and entry["index"] == 1:
			selected_entry = entry
	_check(selected_entry.get("rect") == Rect2(960, 535, 150, 200), "планирование: вторая выбранная карта на месте x=960")
	_check(selected_entry.get("fill_color") == RULES.COLOR_CARD_SELECTED, "планирование: выбранная карта цвета выбора")
	_check(model["table_path"].ends_with("/assets/combat/battle_table.png"), "планирование: путь стола из ../assets")

	var planning_confirmed := planning.duplicate(true)
	planning_confirmed["confirmed"] = true
	var confirmed_model := RULES.build_draw_model(planning_confirmed, {"project_dir": project_dir})
	var any_pressable := false
	for entry in confirmed_model["cards"]:
		if entry["pressable"]:
			any_pressable = true
	_check(not any_pressable, "подтверждённый ход: ни одна карта не нажимается")

	var starting := _fixture("draft_starting.json")
	var starting_model := RULES.build_draw_model(starting, {"project_dir": project_dir})
	_check(starting_model["draft"]["title"] == "СТАРТОВЫЙ ДРАФТ" and starting_model["draft"]["message"] == "Выберите две стартовые карты", "стартовый драфт: заголовок и подсказка")
	_check(starting_model["draft"]["timer_text"] == "ОСТАЛОСЬ 75 СЕК" and starting_model["show_draft"], "стартовый драфт: таймер 75 с")
	var starting_zones := _zone_counts(starting_model["cards"])
	_check(starting_zones == {"table": 20, "hand": 2}, "стартовый драфт: 20 карт на столе и 2 взятые")
	_check(not starting_model["show_timer"], "в драфте полоски хода нет")
	var first_table: Dictionary = {}
	for entry in starting_model["cards"]:
		if entry["zone"] == "table" and entry["index"] == 0:
			first_table = entry
	_check(first_table.get("rect") == RULES.draft_slot_rect("starting", 0), "стартовый драфт: первая карта в слоте 0")
	_check(starting_model["draft_slot_keys"].size() == 20, "стартовый драфт: слоты сохраняются для следующего кадра")

	var redraft := _fixture("draft_redraft.json")
	var redraft_model := RULES.build_draw_model(redraft, {"project_dir": project_dir})
	_check(redraft_model["draft"]["title"] == "ПОВТОРНЫЙ ДРАФТ" and redraft_model["draft"]["message"] == "Выберите две карты", "повторный драфт: заголовок и подсказка")
	_check(_zone_counts(redraft_model["cards"]) == {"table": 6, "hand": 7}, "повторный драфт: 6 карт на столе и 7 в руке")

	var draw := _fixture("draw_choice.json")
	var draw_model := RULES.build_draw_model(draw, {"project_dir": project_dir})
	_check(draw_model["timer"]["total"] == 15 and is_equal_approx(float(draw_model["timer"]["fraction"]), 9.0 / 15.0), "выбор карты: таймер 9 из 15")
	_check(draw_model["timer"]["color"] == RULES.COLOR_TIMER_RED and draw_model["timer"]["label"] == "ВЫБОР КАРТЫ: 9 СЕК", "выбор карты: красный порог и подпись")
	_check(_zone_counts(draw_model["cards"]) == {"hand": 7, "draw_choices": 3}, "выбор карты: 7 карт руки и 3 варианта")

	var outcome := _fixture("outcome_win.json")
	var outcome_model := RULES.build_draw_model(outcome, {"project_dir": project_dir})
	_check(outcome_model["show_result"] and not outcome_model["show_board"], "результат: доска скрыта")
	_check(outcome_model["result"]["title"] == "ПОБЕДА" and outcome_model["result"]["title_color"] == RULES.COLOR_RESULT_WIN, "результат: победа зелёным")
	_check(outcome_model["result"]["winner_text"] == "Победитель: Тестовый Некромант", "результат: победитель — боец игрока")
	_check(outcome_model["cards"].is_empty() and not outcome_model["show_timer"], "результат: карт и таймера нет")


func _check_draw_model_edges(project_dir: String) -> void:
	var empty_model := RULES.build_draw_model({}, {})
	_check(empty_model["cards"].is_empty() and not empty_model["show_timer"] and not empty_model["show_draft"], "пустой снимок: без карт, таймера и драфта")
	_check(empty_model["fighters"]["player"]["bars"].size() == 2, "пустой снимок: полосы HP и MP с нулями")
	var planning_only := RULES.build_draw_model({"phase": "planning"}, {"project_dir": project_dir})
	_check(planning_only["timer"]["seconds_left"] == 0 and planning_only["timer"]["label"] == "ВАШ ХОД", "частичный снимок: таймер на нуле")
	var loss := RULES.build_draw_model({"phase": "result", "outcome": "loss", "side": "player", "opponent": {"name": "Враг"}}, {"project_dir": project_dir})
	_check(loss["result"]["title"] == "ПОРАЖЕНИЕ" and loss["result"]["winner_text"] == "Победитель: Враг", "поражение: победитель — противник")
	var draw_result := RULES.build_draw_model({"phase": "result", "outcome": "draw"}, {"project_dir": project_dir})
	_check(draw_result["result"]["winner_text"] == "Победитель: Ничья", "ничья: победитель не назван")
	var junk := RULES.build_draw_model({"phase": "planning", "hand": [1, "x"], "can_select": ["a"], "selected": "bad"}, {"project_dir": project_dir})
	_check(junk["cards"].size() == 2, "мусор в руке не ломает модель")
	var previous := ["keep"]
	var no_draft := RULES.build_draw_model({"phase": "planning", "table": [{"key": "k"}]}, {"draft_slot_keys": previous})
	_check(no_draft["draft_slot_keys"] == previous, "вне драфта слоты не меняются")


func _fixture(file_name: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(FIXTURE_DIR + file_name))
	return parsed if parsed is Dictionary else {}


func _zone_counts(cards: Array) -> Dictionary:
	var counts: Dictionary = {}
	for entry in cards:
		var zone := str(entry["zone"])
		counts[zone] = int(counts.get(zone, 0)) + 1
	return counts


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)
