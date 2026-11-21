extends Node

const EXIT_MENU_SCRIPT := preload("res://scripts/exit_menu.gd")
const MENU_ACTIONS := ["НАСТРОЙКИ", "ПОКИНУТЬ ИГРУ", "ВЫЙТИ В ЛОББИ", "ПРОДОЛЖИТЬ"]

var _failures: Array[String] = []
var _quit_requests := 0
var _lobby_requests := 0
var _quit_ready_count := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var menu = EXIT_MENU_SCRIPT.new()
	add_child(menu)
	menu.quit_requested.connect(func() -> void: _quit_requests += 1)
	menu.lobby_requested.connect(func() -> void: _lobby_requests += 1)
	menu.quit_ready.connect(func() -> void: _quit_ready_count += 1)

	_check(not menu.is_open() and not menu.blocks_input(), "меню закрыто по умолчанию")

	menu.open()
	_check(menu.is_open() and menu.blocks_input(), "open показывает меню")
	_check(_button_texts(menu._main_box) == MENU_ACTIONS, "главная страница содержит 4 пункта меню")
	_press_escape()
	_check(not menu.is_open(), "Esc закрывает меню")

	menu.open()
	_check(_press(menu._main_box, "НАСТРОЙКИ"), "есть пункт НАСТРОЙКИ")
	_check(menu._settings_box.visible and not menu._main_box.visible, "НАСТРОЙКИ открывает страницу-заглушку")
	_press_escape()
	_check(menu.is_open() and menu._main_box.visible, "Esc на странице настроек возвращает на главную")
	_check(_press(menu._main_box, "ПРОДОЛЖИТЬ") and not menu.is_open(), "ПРОДОЛЖИТЬ закрывает меню")

	menu.open("Тестовая ошибка")
	_check(menu._message.visible and menu._message.text == "Тестовая ошибка", "ошибка выводится в меню")
	_check(_press(menu._main_box, "ВЫЙТИ В ЛОББИ") and _lobby_requests == 1, "ВЫЙТИ В ЛОББИ шлёт lobby_requested")
	menu.set_status("Сохраняем состояние…")
	_check(_button(menu._main_box, "ПОКИНУТЬ ИГРУ").disabled, "во время запроса кнопки заблокированы")
	menu.open()
	_check(not _button(menu._main_box, "ПОКИНУТЬ ИГРУ").disabled, "open снова разблокирует кнопки")

	_check(_press(menu._main_box, "ПОКИНУТЬ ИГРУ") and _quit_requests == 1, "ПОКИНУТЬ ИГРУ шлёт quit_requested")
	menu.begin_quit()
	_check(menu.is_quitting() and menu.blocks_input() and not menu.is_open(), "begin_quit блокирует ввод")
	_check(menu._countdown.visible and menu._countdown.text == "Выход через 5...", "отсчёт начинается с 5 секунд")
	_press_escape()
	_check(menu.is_quitting(), "Esc во время выхода не отменяет его")
	menu.close()
	_check(menu.is_quitting(), "close во время выхода не прерывает его")
	menu._process(2.0)
	_check(menu._countdown.text == "Выход через 3...", "через 2 секунды отсчёт показывает 3")
	menu._process(3.0)
	_check(_quit_ready_count == 0, "без подтверждения отключения выход не выдаётся даже после отсчёта")
	menu.mark_disconnected()
	_check(_quit_ready_count == 1, "после отключения и окончания отсчёта выдаётся quit_ready")
	menu.mark_disconnected()
	menu._process(1.0)
	_check(_quit_ready_count == 1, "quit_ready выдаётся только один раз")

	menu.open()
	menu.begin_quit()
	menu.mark_disconnected()
	_check(_quit_ready_count == 1, "раннее подтверждение не выдаёт выход до конца отсчёта")
	menu._process(5.0)
	_check(_quit_ready_count == 2, "подтверждение, полученное раньше, выдаёт выход по окончании отсчёта")

	menu.open()
	menu.begin_quit()
	menu.open("Сервер недоступен: тест")
	_check(not menu.is_quitting() and menu.is_open(), "ошибка отменяет выход и снова открывает меню")
	_check(menu._message.text == "Сервер недоступен: тест", "текст ошибки виден после отмены выхода")
	menu._process(5.0)
	_check(_quit_ready_count == 2, "отменённый выход не выдаёт quit_ready")

	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("exit_menu_smoke_test: OK")
	get_tree().quit(code)


func _check(condition: bool, message: String) -> void:
	if not condition:
		_failures.append(message)


func _button(box: Node, text: String) -> Button:
	for child in box.get_children():
		if child is Button and child.text == text:
			return child
	return null


func _press(box: Node, text: String) -> bool:
	var button := _button(box, text)
	if button == null or button.disabled:
		return false
	button.pressed.emit()
	return true


func _button_texts(box: Node) -> Array:
	var texts: Array = []
	for child in box.get_children():
		if child is Button:
			texts.append(child.text)
	return texts


func _press_escape() -> void:
	var event := InputEventKey.new()
	event.keycode = KEY_ESCAPE
	event.physical_keycode = KEY_ESCAPE
	event.pressed = true
	get_viewport().push_input(event)
