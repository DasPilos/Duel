extends Node

# Статусы, щит и призывы на плашках боя: тексты, цвета и порядок строк из правил, геометрия заливки щита и панели
# призывов, затем вид (плашки, полоса HP, панель призывов, подсказка). Поля снимка statuses, shield и summons
# добавляются к фикстуре боя в коде; сервер не нужен.
const RULES := preload("res://scripts/deck_battle_layout_rules.gd")
const STATUS := preload("res://scripts/deck_battle_status_rules.gd")
const VIEW_SCRIPT := preload("res://scripts/deck_battle_view.gd")
const FIXTURE_DIR := "res://tests/fixtures/deck_battle/"

var _failures: Array[String] = []
var _checks := 0
var _view


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var project_dir := ProjectSettings.globalize_path("res://")
	_check_status_text()
	_check_status_colors()
	_check_status_rows()
	_check_shield()
	_check_summons_rules()
	_check_model(project_dir)
	await _check_view()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_battle_status_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_status_text() -> void:
	_check(STATUS.status_text({"id": "damage_percent", "positive": true, "amount": 15, "turns": 2}) == "Урон +15% (2 х.)", "бафф: знак, число и ходы")
	_check(STATUS.status_text({"id": "mana_regen_debuff", "positive": false, "amount": 10, "turns": 3}) == "Восст. маны 10% (3 х.)", "дебафф: без знака плюс")
	_check(STATUS.status_text({"id": "mark_damage", "positive": false, "amount": 4, "turns": 1}) == "Метка уязвимости 4 урона (1 х.)", "метка уязвимости: слово «урона»")
	_check(STATUS.status_text({"id": "healing_blocked", "positive": false, "amount": 1, "turns": 2}) == "Запрет лечения 1 (2 х.)", "булев дебафф выводит 1, как Python")
	_check(STATUS.status_text({"id": "dodge_stun", "positive": false, "amount": null, "turns": 2}) == "Оглушение при уклонении (2 х.)", "бафф без числа: только название и ходы")
	_check(STATUS.status_text({"id": "guaranteed_crits", "positive": true, "stacks": 2}) == "Гарантированный крит x2", "счётчик со стаками")
	_check(STATUS.status_text({"id": "no_crit_attacks", "positive": false, "stacks": 1}) == "Атаки без крита x1", "счётчик «атаки без крита»")
	_check(STATUS.status_text({"id": "poison", "positive": false, "stacks": 3}) == "Яд x3 (2% HP при завершении хода)", "яд со стаками")
	_check(STATUS.status_text({"id": "bleed", "positive": false, "amount": 5, "turns": 2}) == "Кровотечение -5/ход (2 х.)", "кровотечение: урон за ход и ходы")
	_check(STATUS.status_text({"id": "regeneration", "positive": true, "amount": 10, "turns": 3}) == "Лечение 10 HP/ход (3 х.)", "регенерация")
	_check(STATUS.status_text({"id": "delayed_heal", "positive": true, "turns": 2}) == "Отложенное лечение (2 х.)", "отложенное лечение")
	_check(STATUS.status_text({"id": "delayed_hp_loss", "positive": false, "amount": 7, "turns": 1}) == "Отложенная потеря 7 HP (1 х.)", "отложенная потеря HP")
	_check(STATUS.status_text({"id": "stun", "positive": false, "turns": 1}) == "Оглушение (1 х.)", "оглушение")
	_check(STATUS.status_text({"id": "freeze", "positive": false, "turns": 2}) == "Заморозка (2 х.)", "заморозка")
	_check(STATUS.status_text({"id": "invulnerable", "positive": true}) == "Неуязвимость", "неуязвимость без ходов")
	_check(STATUS.status_text({"id": "skip_turn", "positive": false}) == "Пропуск следующего хода", "пропуск хода")
	_check(STATUS.status_text({"id": "mage_damage_bonus", "positive": true, "amount": 20, "turns": 2}) == "Магический урон +20% (2 х.)", "бонус магического урона")
	_check(STATUS.status_text({"id": "storm_cloud", "positive": true, "turns": 3}) == "Грозовая туча: 3 х.", "грозовая туча")
	_check(STATUS.status_text({"id": "reactive_blessing", "positive": true, "turns": 2}) == "Ответное благословение: 2 х.", "ответное благословение")
	_check(STATUS.status_text({"id": "fire", "positive": false, "stacks": 2, "turns": 3}) == "Огонь x2 (3 х.)", "стихия мага со стаками")
	_check(STATUS.status_text({"id": "water", "positive": false, "stacks": 1, "turns": 2}) == "Вода (2 х.)", "стихия без стаков")
	_check(STATUS.status_text({"id": "blinding", "positive": false, "stacks": 1, "turns": 1}) == "Blinding (1 х.)", "blinding выводится как в Python")
	_check(STATUS.status_text({"id": "some_new_key", "positive": true, "amount": 3}) == "Some new key: 3", "неизвестный бафф: вывод как у Python")
	_check(STATUS.status_description({"id": "stun", "positive": false}, "Оглушение (1 х.)", "") == "Оглушение (1 х.): оглушённая цель пропускает возможность разыграть карты.", "описание оглушения из Python")
	_check(STATUS.status_description({"id": "fire", "positive": false}, "Огонь (1 х.)", "") == "Активный эффект: Огонь (1 х.).", "статус без описания: «Активный эффект»")
	_check(STATUS.poison_description(3, "assassin") == "Яд: 3 стак(а/ов). В конце хода отравленной стороны наносит 2% максимального HP и снимает один стак. Ассасин, атакующий эту цель, получает за каждый стак +6% шанса крита и +12% критического урона.", "яд у ассасина: бонусы за стаки")
	_check(STATUS.poison_description(3, "warrior") == "Яд: 3 стак(а/ов). В конце хода отравленной стороны наносит 2% максимального HP и снимает один стак.", "яд без ассасина: без бонуса")


func _check_status_colors() -> void:
	_check(STATUS.status_color({"id": "bleed", "positive": false}) == STATUS.BLEED_COLOR, "кровотечение: цвет как в Python")
	_check(STATUS.status_color({"id": "poison", "positive": false}) == STATUS.POISON_COLOR, "яд: зелёный цвет")
	_check(STATUS.status_color({"id": "guaranteed_dodges", "positive": true}) == STATUS.INVULNERABLE_COLOR, "гарантированное уклонение: цвет неуязвимости, как в Python")
	_check(STATUS.status_color({"id": "damage_percent", "positive": true}) == STATUS.POSITIVE_COLOR, "позитивный бафф: зелёный")
	_check(STATUS.status_color({"id": "outgoing_damage_flat", "positive": false}) == STATUS.NEGATIVE_COLOR, "негативный бафф: красный")
	_check(STATUS.status_color({"id": "fire", "positive": false}) == STATUS.MAGE_COLOR, "стихия мага: фиолетовый")


func _check_status_rows() -> void:
	var fighter := {
		"shield": 12,
		"statuses": [
			{"id": "bleed", "positive": false, "turns": 2, "amount": 5, "stacks": null},
			{"id": "damage_percent", "positive": true, "turns": 2, "amount": 15, "stacks": null},
			{"id": "poison", "positive": false, "turns": null, "amount": null, "stacks": 3},
		],
	}
	var rows := STATUS.status_rows(fighter, "")
	_check(_row_texts(rows) == ["Урон +15% (2 х.)", "Щит +12 HP", "Кровотечение -5/ход (2 х.)", "Яд x3 (2% HP при завершении хода)"], "плашка: позитив, щит, затем негатив")
	_check(str(rows[1]["id"]) == "shield" and bool(rows[1]["positive"]), "строка щита позитивна")
	_check(not str(rows[3]["description"]).contains("Ассасин"), "яд без ассасина: без бонуса в описании")
	_check(str(STATUS.status_rows(fighter, "assassin")[3]["description"]).contains("Ассасин"), "яд у ассасина: бонус в описании")
	_check(_row_texts(STATUS.status_rows({"shield": 5}, "")) == ["Щит +5 HP"], "щит без статусов: одна строка")
	_check(STATUS.status_rows({}, "").is_empty() and STATUS.status_rows({"statuses": "bad"}, "").is_empty(), "без статусов плашка пустая")


func _check_shield() -> void:
	_check(STATUS.shield_bar_suffix(12) == " + ЩИТ 12" and STATUS.shield_bar_suffix(0) == "", "подпись щита на полосе HP")
	var bar := Rect2(100, 50, 200, 20)
	_check(STATUS.shield_overlay_rect(bar, 80.0, 100.0, 10) == Rect2(260, 50, 20, 20), "щит ложится сразу после заполненной части")
	_check(STATUS.shield_overlay_rect(bar, 100.0, 100.0, 50) == Rect2(200, 50, 100, 20), "щит у полного HP прижат к правому краю полосы")
	_check(STATUS.shield_overlay_rect(bar, 50.0, 100.0, 1000) == bar, "щит больше полосы занимает её целиком")
	_check(STATUS.shield_overlay_rect(bar, 50.0, 100.0, 0).size == Vector2.ZERO and STATUS.shield_overlay_rect(bar, 50.0, 0.0, 10).size == Vector2.ZERO, "без щита или без максимума HP заливки нет")


func _check_summons_rules() -> void:
	var discard := Rect2(1300, 400, 170, 300)
	var spirit := {"kind": "spirit", "name": "Лесной дух", "hp": 12, "max_hp": 15, "turns": 2}
	var golem := {"kind": "golem", "name": "Каменный голем", "hp": 30, "max_hp": 40, "turns": null}
	var second_golem := {"kind": "golem", "name": "Голем B", "hp": 5, "max_hp": 10, "turns": null}
	var panel := STATUS.summon_panel([spirit], [golem, second_golem], discard)
	var rows: Array = panel["rows"]
	_check(bool(panel["visible"]) and str(panel["title"]) == "ПРИЗЫВЫ", "панель призывов: заголовок ПРИЗЫВЫ")
	_check(rows.size() == 2 and str(rows[0]["name"]) == "Игрок: Лесной дух" and str(rows[0]["details"]) == "HP 12/15, 2 хода", "первые два призыва: дух игрока с ходами")
	_check(str(rows[1]["name"]) == "Противник: Каменный голем" and str(rows[1]["details"]) == "HP 30/40", "второй призыв: голем соперника без ходов")
	_check(str(panel["more"]) == "и ещё 1", "третий призыв скрыт: «и ещё 1»")
	_check(panel["rect"] == Rect2(1116, 708, 176, 124), "панель слева от сброса и под ним; высота 22 + 2 x 40 + 22")
	var single := STATUS.summon_panel([], [golem], discard)
	_check(str(single["more"]) == "" and (single["rect"] as Rect2).size.y == 62.0, "один призыв: без «и ещё», высота 22 + 40")
	_check(not bool(STATUS.summon_panel([], [], discard)["visible"]), "без призывов панели нет")
	var low := STATUS.summon_panel([spirit], [], Rect2(1300, 1000, 170, 300))
	_check((low["rect"] as Rect2).end.y == 1080.0, "панель не выходит за нижний край экрана")
	_check(STATUS.summon_details({"hp": 4, "max_hp": 10}) == "HP 4/10" and STATUS.summon_details({"hp": 4, "max_hp": 10, "turns": 3}) == "HP 4/10, 3 хода", "детали призыва: ходы только если есть")


func _check_model(project_dir: String) -> void:
	var model := RULES.build_draw_model(_battle_fields(), {"project_dir": project_dir})
	var fighters: Dictionary = model["fighters"]
	var player: Dictionary = fighters["player"]
	var enemy: Dictionary = fighters["enemy"]
	_check(_row_texts(player["status_rows"]) == ["Урон +15% (2 х.)", "Щит +12 HP", "Кровотечение -5/ход (2 х.)"], "модель: плашка игрока")
	_check(_row_texts(enemy["status_rows"]) == ["Неуязвимость", "Яд x3 (2% HP при завершении хода)"], "модель: плашка соперника, неуязвимость первой")
	_check(str(player["bars"][0]["text"]) == "HP: 106/120 + ЩИТ 12" and str(enemy["bars"][0]["text"]) == "HP: 35/40", "модель: подпись щита только у игрока")
	_check((player["shield_rect"] as Rect2).size.x > 0.0 and (enemy["shield_rect"] as Rect2).size == Vector2.ZERO, "модель: заливка щита только у игрока")
	var summons: Dictionary = model["summons"]
	var summon_rows: Array = summons["rows"]
	_check(bool(summons["visible"]) and str(summon_rows[0]["name"]) == "Игрок: Лесной дух" and str(summon_rows[1]["name"]) == "Противник: Каменный голем", "модель: призывы игрока, затем соперника")
	_check(str(summons["more"]) == "и ещё 2", "модель: «и ещё 2» для двух скрытых призывов")
	var plain := RULES.build_draw_model(_fixture("planning_hand.json"), {"project_dir": project_dir})
	var plain_player: Dictionary = plain["fighters"]["player"]
	_check((plain_player["status_rows"] as Array).is_empty() and not bool(plain["summons"]["visible"]), "модель без полей: ни плашек, ни призывов")
	_check(str(plain_player["bars"][0]["text"]) == "HP: 106/120", "модель без щита: подпись HP без изменений")


func _check_view() -> void:
	_view = VIEW_SCRIPT.new()
	_view.size = RULES.DESIGN_SIZE
	add_child(_view)
	await get_tree().process_frame
	_view.set_snapshot(_fixture("planning_hand.json"))
	_check(not _view.status_block_visible("player") and not _view.status_block_visible("enemy"), "вид: без статусов плашек нет")
	_check(not _view.shield_overlay_visible("player") and not _view.summons_panel_visible(), "вид: без щита и призывов их нет")
	var data := _battle_fields()
	_view.set_snapshot(data)
	_check(_view.status_texts("player") == ["Урон +15% (2 х.)", "Щит +12 HP", "Кровотечение -5/ход (2 х.)"], "вид: плашка игрока со щитом")
	_check(_view.status_texts("enemy") == ["Неуязвимость", "Яд x3 (2% HP при завершении хода)"], "вид: плашка соперника")
	_check(_view.status_block_visible("player") and _view.status_block_visible("enemy"), "вид: обе плашки показаны")
	var colors: Array = _view.status_colors("player")
	_check(colors.size() == 3 and (colors[1] as Color) == STATUS.SHIELD_COLOR and (colors[2] as Color) == STATUS.BLEED_COLOR, "вид: цвета щита и кровотечения")
	_check(str(_view.bar_state("player", "hp")["text"]) == "HP: 106/120 + ЩИТ 12", "вид: подпись HP со щитом")
	var fighter: Dictionary = data["fighter"]
	_check(_view.shield_overlay_visible("player") and not _view.shield_overlay_visible("enemy"), "вид: заливка щита только у игрока")
	_check(_view.shield_overlay_rect("player").is_equal_approx(RULES.fighter_panel("player", fighter)["shield_rect"]), "вид: заливка щита по полосе HP")
	_check(_view.summons_panel_visible() and _view.summons_panel_rect().size == Vector2(176, 124), "вид: панель призывов шириной 176")
	_check(_view.summon_rows() == [{"name": "Игрок: Лесной дух", "details": "HP 12/15"}, {"name": "Противник: Каменный голем", "details": "HP 30/40"}], "вид: строки призывов")
	_check(_view.summons_more_text() == "и ещё 2", "вид: «и ещё 2»")
	_view.hover_status("player", 1)
	_check(_view.status_tooltip_text() == "Активный эффект: Щит +12 HP.", "вид: подсказка щита при наведении")
	_view.hover_status("player", 2)
	_check(_view.status_tooltip_text() == "Кровотечение -5/ход (2 х.): цель теряет указанное количество HP каждый ход до окончания эффекта.", "вид: подсказка кровотечения")
	_view.unhover_status("player", 2)
	_check(_view.status_tooltip_text() == "", "вид: подсказка скрыта при уходе курсора")
	_view.hover_status("enemy", 1)
	data["opponent"]["statuses"][0]["stacks"] = 4
	_view.set_snapshot(data)
	_check(_view.status_tooltip_text() == STATUS.poison_description(4, "warrior"), "вид: подсказка яда обновляется по новому снимку")
	_view.unhover_status("enemy", 1)
	_view.set_snapshot(_fixture("planning_hand.json"))
	_check(not _view.status_block_visible("player") and not _view.shield_overlay_visible("player") and not _view.summons_panel_visible(), "вид: снимок без полей всё скрывает")


func _battle_fields() -> Dictionary:
	var data := _fixture("planning_hand.json")
	data["fighter"]["shield"] = 12
	data["fighter"]["statuses"] = [
		{"id": "damage_percent", "positive": true, "turns": 2, "amount": 15, "stacks": null},
		{"id": "bleed", "positive": false, "turns": 2, "amount": 5, "stacks": null},
	]
	data["fighter"]["summons"] = [
		{"kind": "spirit", "name": "Лесной дух", "hp": 12, "max_hp": 15, "turns": null},
	]
	data["opponent"]["statuses"] = [
		{"id": "poison", "positive": false, "turns": null, "amount": null, "stacks": 3},
		{"id": "invulnerable", "positive": true, "turns": null, "amount": null, "stacks": null},
	]
	data["opponent"]["summons"] = [
		{"kind": "golem", "name": "Каменный голем", "hp": 30, "max_hp": 40, "turns": null},
		{"kind": "golem", "name": "Голем B", "hp": 5, "max_hp": 10, "turns": null},
		{"kind": "golem", "name": "Голем C", "hp": 8, "max_hp": 8, "turns": null},
	]
	return data


func _fixture(file_name: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(FIXTURE_DIR + file_name))
	return parsed if parsed is Dictionary else {}


func _row_texts(rows: Array) -> Array:
	var texts: Array = []
	for row in rows:
		texts.append(row["text"])
	return texts


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)
