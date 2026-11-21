extends Node

const RULES := preload("res://scripts/create_character_details_rules.gd")
const VIEW_SCRIPT := preload("res://scripts/create_character_view.gd")
const FIXTURE_PATH := "res://tests/create_character_details_fixture.json"
const TOWER_PROFESSIONS := ["warrior", "archer", "assassin", "mage"]
const SLOT_KEYS := ["ears", "head", "neck", "back", "body", "ring", "hands", "shield", "belt", "weapon", "ring_2", "legs", "feet"]

var _failures: Array[String] = []
var _checks := 0
var _fixture: Dictionary = {}


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(FIXTURE_PATH))
	if parsed is Dictionary:
		_fixture = parsed
		_check_layout()
		_check_tower_rules()
		_check_deck_rules()
		_check_icons()
		await _check_view()
	else:
		_check(false, "фикстура из Python читается")
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("create_character_details_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)


func _rect_matches(rect: Rect2, values: Array) -> bool:
	return rect == Rect2(float(values[0]), float(values[1]), float(values[2]), float(values[3]))


func _color_from(values: Array) -> Color:
	return Color8(int(values[0]), int(values[1]), int(values[2]))


func _check_layout() -> void:
	var layout: Dictionary = _fixture["layout"]
	var slots: Dictionary = layout["slots"]
	var rects := RULES.slot_rects()
	_check(rects.size() == SLOT_KEYS.size() and slots.size() == SLOT_KEYS.size(), "слотов тринадцать, как в equipment_slots.SLOT_LAYOUT")
	var slots_match := true
	for slot in SLOT_KEYS:
		slots_match = slots_match and rects.has(slot) and _rect_matches(rects[slot], slots[slot])
	_check(slots_match, "прямоугольники слотов совпадают с Python slot_rects")
	_check(_rect_matches(RULES.HP_BAR, layout["hp_bar"]), "полоса HP совпадает с _draw_resource в Python")
	_check(_rect_matches(RULES.MP_BAR, layout["mp_bar"]), "полоса MP совпадает с _draw_resource в Python")
	_check(RULES.info_top(rects) == float(layout["info_top"]), "строки веса начинаются на 6 px ниже слота обуви")
	_check(float(layout["card_width"]) == VIEW_SCRIPT.CARD_WIDTH and float(layout["card_height"]) == VIEW_SCRIPT.CARD_HEIGHT, "карточка 450x1000")
	_check(int(layout["icon_box"][2]) == RULES.ICON_SIZE and int(layout["icon_box"][3]) == RULES.ICON_SIZE, "иконка класса 32x32")
	_check(float(layout["icon_box"][0]) == VIEW_SCRIPT.TEXT_LEFT, "иконка стоит у левого края текста")
	_check(float(layout["name_left"]) == VIEW_SCRIPT.NAME_LEFT and float(layout["name_top"]) == VIEW_SCRIPT.NAME_TOP, "имя сдвинуто на иконку и зазор, как в Python")


# Значения Tower сверяются с фикстурой, которую создал Python: тексты, числа и цвета строк.
func _tower_mismatch(details: Dictionary, expected: Dictionary) -> String:
	var texts: Dictionary = expected["texts"]
	var colors: Dictionary = expected["colors"]
	if int(details["hp"]) != int(expected["hp"]) or int(details["max_hp"]) != int(expected["max_hp"]):
		return " (HP %s/%s)" % [details["hp"], details["max_hp"]]
	if int(details["mp"]) != int(expected["mp"]) or int(details["max_mp"]) != int(expected["max_mp"]):
		return " (MP %s/%s)" % [details["mp"], details["max_mp"]]
	if int(details["capacity_kg"]) != int(expected["capacity_kg"]) or not is_equal_approx(float(details["carried_kg"]), float(expected["carried_kg"])):
		return " (вес)"
	if not is_equal_approx(float(details["attack_seconds"]), float(expected["attack_seconds"])):
		return " (скорость атаки)"
	if int(details["move_speed"]) != int(expected["move_speed"]):
		return " (скорость передвижения)"
	if not is_equal_approx(float(details["reach"]), float(expected["reach"])):
		return " (дальность удара)"
	if str(details["hp_text"]) != str(texts["hp"]) or str(details["mp_text"]) != str(texts["mp"]):
		return " (подписи HP и MP)"
	if str(details["weight_text"]) != str(texts["weight"]) or str(details["attack_text"]) != str(texts["attack"]):
		return " (подписи веса и атаки)"
	if str(details["move_text"]) != str(texts["move"]) or str(details["reach_text"]) != str(texts["reach"]):
		return " (подписи скорости и дальности)"
	if details["weight_color"] != _color_from(expected["load_color"]):
		return " (цвет нагрузки)"
	if VIEW_SCRIPT.ATTACK_COLOR != _color_from(colors["attack"]) or VIEW_SCRIPT.MOVE_COLOR != _color_from(colors["move"]):
		return " (цвета скорости)"
	if VIEW_SCRIPT.REACH_COLOR != _color_from(colors["reach"]):
		return " (цвет дальности)"
	return ""


func _check_tower_rules() -> void:
	for item in _fixture["tower"]:
		var expected: Dictionary = item
		var details := RULES.tower_details(expected["stats"])
		var mismatch := _tower_mismatch(details, expected)
		_check(mismatch.is_empty(), "Tower %s %s: как в Python%s" % [expected["profession"], str(expected["allocation"]), mismatch])


func _deck_mismatch(details: Dictionary, expected: Dictionary) -> String:
	var texts: Dictionary = expected["texts"]
	if int(details["hp"]) != int(expected["hp"]) or int(details["max_hp"]) != int(expected["max_hp"]):
		return " (HP %s/%s)" % [details["hp"], details["max_hp"]]
	if int(details["mp"]) != int(expected["mp"]) or int(details["max_mp"]) != int(expected["max_mp"]):
		return " (MP %s/%s)" % [details["mp"], details["max_mp"]]
	if str(details["hp_text"]) != str(texts["hp"]) or str(details["mp_text"]) != str(texts["mp"]):
		return " (подписи)"
	return ""


func _check_deck_rules() -> void:
	for item in _fixture["deck"]:
		var expected: Dictionary = item
		var details := RULES.deck_details(str(expected["profession"]))
		var mismatch := _deck_mismatch(details, expected)
		_check(mismatch.is_empty(), "Deck %s: HP и мана как в Python%s" % [expected["profession"], mismatch])
		_check(not details.has("weight_text") and not details.has("reach_text"), "Deck %s: строк веса и скорости нет" % expected["profession"])


func _check_icons() -> void:
	var root := VIEW_SCRIPT.assets_root()
	for profession in TOWER_PROFESSIONS:
		var path := RULES.class_icon_path(root, profession)
		var image := Image.load_from_file(path) if not path.is_empty() else null
		_check(not path.is_empty() and FileAccess.file_exists(path) and image != null and not image.is_empty(), "иконка класса читается: %s" % profession)
	_check(RULES.class_icon_path(root, "warrior") == root + "/ui/professions/warrior.png", "путь иконки ведёт в ../assets/ui/professions")
	_check(RULES.class_icon_path(root, "necromancer").is_empty(), "у некроманта иконки нет, как в Python")
	_check(RULES.class_icon_path("", "warrior").is_empty(), "без корня ассетов пути нет")


func _check_view() -> void:
	var view = VIEW_SCRIPT.new()
	add_child(view)
	await get_tree().process_frame
	view.set_card_scale(1.0)

	view.configure("tower")
	for item in _fixture["tower"]:
		var expected: Dictionary = item
		var profession := str(expected["profession"])
		view.configure("tower")
		for stat in expected["allocation"]:
			for _point in range(int(expected["allocation"][stat]) - 3):
				view.adjust_stat(profession, str(stat), 1)
		var mismatch := _tower_mismatch(view.details_for(profession), expected)
		var free_ok := view.free_points(profession) == int(expected["free_points"])
		_check(mismatch.is_empty() and free_ok, "карточка Tower %s %s пересчитана по очкам%s" % [profession, str(expected["allocation"]), mismatch])

	view.configure("tower")
	var reach_before := str(view.details_for("archer")["reach_text"])
	var attack_before := str(view.details_for("archer")["attack_text"])
	view.adjust_stat("archer", "intuition", 1)
	_check(reach_before == "Дальность удара: 48 px" and str(view.details_for("archer")["reach_text"]) == "Дальность удара: 49 px", "дальность удара растёт на 1 при +1 интуиции")
	_check(attack_before == "Скорость атаки: 0.88 с" and str(view.details_for("archer")["attack_text"]) == "Скорость атаки: 0.86 с", "скорость атаки пересчитывается при +1 интуиции")

	view.configure("deck")
	for item in _fixture["deck"]:
		var expected: Dictionary = item
		var details: Dictionary = view.details_for(str(expected["profession"]))
		var mismatch := _deck_mismatch(details, expected)
		_check(mismatch.is_empty() and not details.has("weight_text"), "карточка Deck %s: HP и мана как в Python%s" % [expected["profession"], mismatch])

	view.configure("tower")
	var warrior_card := view.card_rect("warrior")
	var inside := true
	for slot in SLOT_KEYS:
		inside = inside and warrior_card.encloses(view.slot_rect("warrior", slot))
	_check(inside, "все слоты лежат внутри карточки")
	_check(view.slot_rect("warrior", "feet").position == Vector2(207.0, 697.0), "слот обуви у воина: x 207, y 697 (649 + отступ 48)")
	view.set_card_scale(0.5)
	_check(view.slot_rect("warrior", "feet").position == Vector2(103.5, 348.5), "слоты масштабируются вместе с карточкой")
	_check(view.slot_rect("warrior", "unknown").size == Vector2.ZERO, "неизвестный слот пустой")

	view.queue_free()
