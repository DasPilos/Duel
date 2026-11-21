extends Node

const VIEW_SCRIPT := preload("res://scripts/create_character_view.gd")
const CLASS_RULES := preload("res://scripts/deck_class_card_rules.gd")
const FRONT_LINE_SPRITES := preload("res://scripts/front_line_hero_sprite_rules.gd")

var _failures: Array[String] = []
var _checks := 0
var _requested := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_rules()
	_check_creation_stats()
	await _check_view()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("create_character_view_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)


func _check_rules() -> void:
	var four: Array[String] = ["warrior", "archer", "assassin", "mage"]
	var five: Array[String] = ["warrior", "archer", "assassin", "mage", "necromancer"]
	_check(VIEW_SCRIPT.professions_for_mode("tower") == four, "tower: четыре класса в порядке Python")
	_check(VIEW_SCRIPT.professions_for_mode("economy") == four, "economy: четыре класса в порядке Python")
	_check(VIEW_SCRIPT.professions_for_mode("front_line") == four, "Front Line: четыре класса в порядке Python")
	_check(VIEW_SCRIPT.professions_for_mode("deck") == five, "deck: некромант последним")
	_check(VIEW_SCRIPT.professions_for_mode("") == four, "неизвестный режим: без некроманта")
	_check(VIEW_SCRIPT.stat_controls_for_mode("tower") and VIEW_SCRIPT.stat_controls_for_mode("economy") and VIEW_SCRIPT.stat_controls_for_mode("front_line"), "tower, economy и Front Line принимают stats")
	_check(not VIEW_SCRIPT.stat_controls_for_mode("deck") and not VIEW_SCRIPT.stat_controls_for_mode(""), "deck и неизвестный режим без stats")
	var titles := {"warrior": "ВОИН", "archer": "ЛУЧНИК", "assassin": "АСАСИН", "mage": "МАГ", "necromancer": "НЕКРОМАНТ"}
	for profession in titles:
		_check(CLASS_RULES.class_title(profession) == titles[profession], "подпись класса: %s" % profession)
	# card_bg из scenes/create_character_scene.py CLASS_INFO
	var backgrounds := {
		"warrior": Color8(110, 34, 38),
		"archer": Color8(34, 96, 48),
		"assassin": Color8(88, 44, 120),
		"mage": Color8(36, 62, 130),
	}
	for profession in backgrounds:
		_check(CLASS_RULES.card_background(profession) == backgrounds[profession], "цвет карточки как card_bg в Python: %s" % profession)
	_check(CLASS_RULES.card_background("necromancer") == Color8(37, 54, 42), "фон некроманта из палитры Deck")
	_check(CLASS_RULES.card_background("dragon") == Color(0, 0, 0, 0), "неизвестный класс без фона")
	_check(CLASS_RULES.class_sprite_file("necromancer").is_empty(), "у некроманта нет спрайта")
	_check(not CLASS_RULES.class_sprite_file("mage").is_empty(), "у мага есть спрайт")
	for profession in ["warrior", "archer", "mage"]:
		_check(FRONT_LINE_SPRITES.frame_texture(profession, "idle", "s", 0) != null, "спрайт Front Line загружается: %s" % profession)
	var attack_frames := {"warrior": 8, "archer": 8, "mage": 7}
	for profession in attack_frames:
		_check(FRONT_LINE_SPRITES.frame_count(profession, "attack") == attack_frames[profession]
			and FRONT_LINE_SPRITES.frame_texture(profession, "attack", "e", 4) != null,
			"лист атаки героя Front Line без теней и атак на бегу: %s" % profession)


# Ожидаемые значения получены из combat/character_stats.py creation_stats на тех же входах.
func _check_creation_stats() -> void:
	var base := {"strength": 3, "agility": 3, "intuition": 3, "wisdom": 3, "intellect": 3, "endurance": 4}
	var empty: Dictionary = VIEW_SCRIPT.creation_stats({})
	_check(bool(empty["ok"]) and empty["stats"] == base and int(empty["free_points"]) == 3, "пустое распределение: база 3, выносливость 4, очков 3")
	var spent_three: Dictionary = VIEW_SCRIPT.creation_stats({"strength": 5, "agility": 4})
	_check(bool(spent_three["ok"]) and int(spent_three["free_points"]) == 0, "сила 5 и ловкость 4 тратят все три очка")
	_check(spent_three["stats"] == base.merged({"strength": 5, "agility": 4}, true), "сила 5 и ловкость 4: значения как в Python")
	var one_stat: Dictionary = VIEW_SCRIPT.creation_stats({"strength": 6})
	_check(bool(one_stat["ok"]) and int(one_stat["free_points"]) == 0 and one_stat["stats"] == base.merged({"strength": 6}, true), "сила 6 тратит три очка")
	var two_stats: Dictionary = VIEW_SCRIPT.creation_stats({"strength": 4, "intellect": 4})
	_check(bool(two_stats["ok"]) and int(two_stats["free_points"]) == 1 and two_stats["stats"] == base.merged({"strength": 4, "intellect": 4}, true), "сила 4 и интеллект 4 оставляют один очко")
	var single: Dictionary = VIEW_SCRIPT.creation_stats({"intuition": 5})
	_check(bool(single["ok"]) and int(single["free_points"]) == 1 and single["stats"] == base.merged({"intuition": 5}, true), "интуиция 5 оставляет один очко")
	var rejected := [
		{"strength": 7},
		{"strength": 5, "intellect": 4, "intuition": 4},
		{"strength": 2},
		{"strength": null},
		{"strength": 4.0},
		{"strength": true},
		{"endurance": 5},
		{"harmony": 3},
	]
	for allocation in rejected:
		var result: Dictionary = VIEW_SCRIPT.creation_stats(allocation)
		_check(not bool(result["ok"]) and str(result["error"]) != "", "отклонено как в Python: %s" % str(allocation))
	_check(str(VIEW_SCRIPT.creation_stats({"strength": 7})["error"]) == "Свободных очков при создании только 3", "перерасход: текст как в Python")


func _check_view() -> void:
	var view = VIEW_SCRIPT.new()
	view.create_requested.connect(_on_create_requested)
	add_child(view)
	await get_tree().process_frame

	view.configure("tower")
	view.set_card_scale(1.0)
	var four: Array[String] = ["warrior", "archer", "assassin", "mage"]
	_check(view.professions() == four, "tower: карточки в порядке Python")
	_check(view.card_layout_size() == Vector2(1920, 1048), "tower: ряд 1920 px как у Python, над карточками место под подъём")
	_check(view.card_rect("warrior") == Rect2(15, 48, 450, 1000), "воин: поле 15, размер 450x1000, сверху отступ 48")
	var chosen := view.selected_profession()
	var other := "mage" if chosen != "mage" else "warrior"
	var chosen_center := view.card_rect(chosen).get_center()
	_check(view.card_visual_point(chosen, chosen_center).y < chosen_center.y and is_equal_approx(view.card_visual_point(chosen, chosen_center).x, chosen_center.x), "выбранная карточка поднята вверх без сдвига по горизонтали")
	var other_center := view.card_rect(other).get_center()
	_check(view.card_visual_point(other, other_center) == other_center, "невыбранная карточка стоит на месте")
	_check(view.card_rect("archer").position.x == 495.0 and view.card_rect("mage").position.x == 1455.0, "зазор карточек 30 px")
	view.set_card_scale(0.5)
	_check(view.card_rect("archer") == Rect2(247.5, 24, 225, 500), "масштаб 0.5 сохраняет порядок и пропорции")
	view.set_card_scale(1.0)
	_check(view.selected_profession() == "warrior", "по умолчанию выбран воин")
	var tower_plus_point: Vector2 = view.stat_control_rect("warrior", "strength", 1).get_center()

	view.click_at(view.card_rect("archer").get_center())
	_check(view.selected_profession() == "archer", "клик по карточке выбирает класс")
	view.click_at(view.card_visual_point("archer", view.stat_control_rect("archer", "strength", 1).get_center()))
	_check(view.selected_profession() == "archer" and view.allocation_for("archer")["strength"] == 4, "плюс у лучника тратит очко")
	_check(view.free_points("archer") == 2 and view.allocation_for("warrior")["strength"] == 3, "очки считаются отдельно для каждого класса")
	view.click_at(view.card_visual_point("archer", view.stat_control_rect("archer", "strength", -1).get_center()))
	_check(view.allocation_for("archer")["strength"] == 3 and view.free_points("archer") == 3, "минус возвращает очко")
	_check(view.stat_control_at("warrior", view.stat_control_rect("warrior", "agility", 1).get_center()) == {"stat": "agility", "delta": 1}, "попадание в плюс ловкости")
	var below_intellect := view.stat_control_rect("warrior", "intellect", -1).position + Vector2(1, 20)
	_check(view.stat_control_at("warrior", below_intellect).is_empty(), "у выносливости кнопок нет")

	view.click_at(view.card_rect("warrior").get_center())
	for _step in range(3):
		view.click_at(view.card_visual_point("warrior", view.stat_control_rect("warrior", "strength", 1).get_center()))
	_check(view.allocation_for("warrior")["strength"] == 6 and view.free_points("warrior") == 0, "три очка тратятся на силу")
	view.click_at(view.card_visual_point("warrior", view.stat_control_rect("warrior", "strength", 1).get_center()))
	_check(view.allocation_for("warrior")["strength"] == 6, "перерасход отклонён кликом")
	_check(not view.adjust_stat("warrior", "strength", 1), "перерасход отклонён вызовом")
	_check(not view.adjust_stat("warrior", "agility", -1), "ниже базовых 3 не опускается")
	_check(view.displayed_stat("warrior", "endurance") == 4, "выносливость фиксирована на 4")

	view.set_character_name("  Тест  ")
	var body: Dictionary = view.request_body()
	_check(body == {
		"name": "Тест",
		"profession_type": "warrior",
		"stats": {"strength": 6, "agility": 3, "intuition": 3, "wisdom": 3, "intellect": 3},
	}, "тело запроса tower: имя без пробелов, абсолютные значения без выносливости")
	_check(JSON.stringify(body).find(".") == -1, "в JSON нет дробных чисел")
	view.set_character_name("   ")
	_check(view.character_name().is_empty() and str(view.request_body()["name"]).is_empty(), "пустое имя видно вызывающему")
	view.set_character_name("Тест")
	view._name_input.text_submitted.emit("Тест")
	view._create_button.pressed.emit()
	_check(_requested == 2, "Enter в поле и кнопка «Создать» отправляют запрос")
	await get_tree().process_frame

	view.configure("deck")
	var five: Array[String] = ["warrior", "archer", "assassin", "mage", "necromancer"]
	_check(view.professions() == five, "deck: некромант добавлен последним")
	_check(view.card_rect("necromancer").position.x == 1935.0, "некромант стоит на пятом месте")
	_check(view.card_layout_size() == Vector2(2400, 1048), "deck: ряд из пяти карточек")
	_check(not view.card_has_sprite("necromancer") and view.card_has_sprite("mage"), "спрайт нет только у некроманта")
	_check(not view.adjust_stat("warrior", "strength", 1), "в Deck кнопок нет")
	_check(view.stat_control_at("warrior", tower_plus_point).is_empty(), "в Deck кнопок нет")
	_check(view.displayed_stat("archer", "strength") == 2 and view.displayed_stat("archer", "endurance") == 2, "стартовые значения Deck: 2")
	view.click_at(view.card_rect("necromancer").get_center())
	_check(view.selected_profession() == "necromancer", "некромант выбирается кликом")
	view.set_character_name("Тест")
	_check(view.request_body() == {"name": "Тест", "profession_type": "necromancer"}, "тело Deck без stats")
	view.click_at(view.card_rect("mage").get_center())
	_check(view.request_body() == {"name": "Тест", "profession_type": "mage"}, "тело Deck для мага без stats")
	view.configure("front_line")
	_check(view.details_for("archer")["reach_text"] == "Дальность атаки: 500" and view.details_for("warrior")["reach_text"] == "Дальность атаки: 100", "Front Line: дальность атаки одним числом в единицах")
	_check(view.details_for("mage")["reach_text"] == "Дальность атаки: 500", "маг: дальность 500 ед.")
	var plus_point: Vector2 = view.stat_control_rect("warrior", "strength", 1).get_center()
	_check(view.stat_control_at("warrior", plus_point).is_empty(), "драфт: до подтверждения кнопки характеристик закрыты")
	view.play_selection_intro()
	view._process(1.5)
	_check(view.stat_control_at("warrior", plus_point).is_empty() and view.intro_progress() < 1.0, "во время анимации выбора характеристики ещё закрыты")
	view._process(1.6)
	_check(not view.stat_control_at("warrior", plus_point).is_empty(), "после трёх секунд анимации характеристики открываются")
	var unavailable_count := [0]
	view.unavailable_profession_requested.connect(func(_profession: String) -> void:
		unavailable_count[0] += 1
	)
	view.click_at(view.card_rect("assassin").get_center())
	_check(not view.profession_is_available("assassin"), "асасин недоступен в Front Line")
	_check(view.selected_profession() == "warrior" and unavailable_count[0] == 1, "клик по асасину не меняет класс и сообщает о недоступности")
	await get_tree().process_frame
	await get_tree().process_frame

	view.queue_free()


func _on_create_requested() -> void:
	_requested += 1
