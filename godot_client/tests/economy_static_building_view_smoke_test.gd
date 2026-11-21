extends Node

const STATIC_SCRIPT := preload("res://scripts/economy_static_building_view.gd")
const KEYS := ["barracks", "engineering", "university", "academy", "mage_school"]
const BARRACKS_TITLE := "ГОРОДСКИЕ КАЗАРМЫ (УРОВЕНЬ 1)"

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_constants()
	_check_every_building()
	_check_barracks_texts()
	_check_back_button()
	_check_no_emoji()
	await _check_layout_budget()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("economy_static_building_view_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_constants() -> void:
	_check(STATIC_SCRIPT.WINDOW_SIZE == Vector2(453, 333), "размер окна казарм 453×333 (Python 680×500)")
	_check(STATIC_SCRIPT.BORDER_COLOR == Color8(80, 150, 230), "рамка окна как в Python")
	_check(STATIC_SCRIPT.BACKGROUND_COLOR == Color8(22, 26, 32), "фон окна как в Python")


func _check_every_building() -> void:
	for key in KEYS:
		var view = _new_view(key)
		var modal: Dictionary = STATIC_SCRIPT.MODALS[key]
		_check(view.window_title() == str(modal["title"]), "заголовок окна %s" % key)
		var texts := _texts(view)
		_check(texts.has(str(modal["subtitle"])), "подзаголовок %s" % key)
		for row in modal["rows"]:
			_check(texts.has(str(row[0])) and texts.has(str(row[1])), "строка возможностей %s: %s" % [key, row[0]])
		_check(texts.has("ВЕРНУТЬСЯ В ГОРОД"), "кнопка возврата в городе для %s" % key)
		_drop(view)


func _check_barracks_texts() -> void:
	var view = _new_view("barracks")
	var texts := _texts(view)
	_check(view.window_title() == BARRACKS_TITLE, "заголовок казарм как в Python")
	_check(texts.has("[ ВОЕННЫЙ ГАРНИЗОН РАДБУРГА • 9х13 ТАЙЛОВ • ВХОД: 84/43 ]"), "подзаголовок казарм как в Python")
	_check(texts.has("Гарнизон на боевом дежурстве: Солдаты содержатся и несут службу на стенах"),
		"плашка казарм с заглавной буквой как в Python")
	_check(texts.has("Содержание и численность солдат гарнизона:"), "заголовок блока солдат как в Python")
	_check(texts.has("Регулярные солдаты гарнизона:") and texts.has("120 / 200 бойцов (пехотинцы, мечники, копейщики)"),
		"первая строка солдат как в Python")
	_check(texts.has("Увеличит вместимость до 500 бойцов и откроет наём тяжелых рыцарей"),
		"последняя строка солдат как в Python")
	_drop(view)


func _check_back_button() -> void:
	var view = _new_view("barracks")
	var pressed := [0]
	view.back_requested.connect(func() -> void: pressed[0] += 1)
	var button := _find_button(view, "ВЕРНУТЬСЯ В ГОРОД")
	_check(button != null and button.custom_minimum_size == Vector2(187, 29), "кнопка возврата 187×29 (Python 280×44)")
	if button != null:
		button.pressed.emit()
	_check(pressed[0] == 1, "кнопка возврата шлёт back_requested один раз")
	_drop(view)


func _check_no_emoji() -> void:
	for key in KEYS:
		var view = _new_view(key)
		var emoji_found := false
		for text in _texts(view):
			for index in range(text.length()):
				var code := text.unicode_at(index)
				if code >= 0x1F000 or (code >= 0x2600 and code <= 0x27BF) or code == 0xFE0F:
					emoji_found = true
		_check(not emoji_found, "в окне %s нет эмодзи (шрифт Godot их не выводит)" % key)
		_drop(view)


func _check_layout_budget() -> void:
	for key in KEYS:
		var view = _new_view(key)
		_check(view.get_combined_minimum_size().x <= 413.0, "ширина вида %s вмещается в окно" % key)
		view.custom_minimum_size.x = 413.0
		await get_tree().process_frame
		await get_tree().process_frame
		var minimum: Vector2 = view.get_combined_minimum_size()
		_check(minimum.y <= 269.0, "высота вида %s вмещается в окно без прокрутки: %.0f" % [key, minimum.y])
		_drop(view)


func _new_view(key: String):
	var view = STATIC_SCRIPT.new()
	view.setup(key)
	add_child(view)
	return view


func _drop(view) -> void:
	remove_child(view)
	view.free()


func _find_button(node: Node, text: String) -> Button:
	if node is Button and (node as Button).text == text:
		return node as Button
	for child in node.get_children():
		var found := _find_button(child, text)
		if found != null:
			return found
	return null


func _texts(root: Node) -> Array[String]:
	var found: Array[String] = []
	_collect_texts(root, found)
	return found


func _collect_texts(node: Node, found: Array[String]) -> void:
	if node is Label:
		found.append((node as Label).text)
	elif node is Button:
		found.append((node as Button).text)
	for child in node.get_children():
		_collect_texts(child, found)


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)
