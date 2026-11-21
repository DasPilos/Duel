extends Control

const SCENE_TRANSITION := preload("res://scripts/scene_transition.gd")

signal connection_restored(character: Dictionary)
signal session_invalid

var _overlay: ColorRect
var _message: Label
var _counter: Label
var _close_button: Button
var _login_button: Button


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_build()
	ConnectionGuard.connection_lost.connect(_on_connection_lost)
	ConnectionGuard.countdown_updated.connect(_on_countdown_updated)
	ConnectionGuard.connection_restored.connect(_on_connection_restored)
	ConnectionGuard.client_outdated.connect(_on_client_outdated)
	ConnectionGuard.session_invalid.connect(_on_session_invalid)
	ConnectionGuard.connection_expired.connect(_on_connection_expired)


func _exit_tree() -> void:
	if ConnectionGuard.connection_lost.is_connected(_on_connection_lost):
		ConnectionGuard.connection_lost.disconnect(_on_connection_lost)
	if ConnectionGuard.countdown_updated.is_connected(_on_countdown_updated):
		ConnectionGuard.countdown_updated.disconnect(_on_countdown_updated)
	if ConnectionGuard.connection_restored.is_connected(_on_connection_restored):
		ConnectionGuard.connection_restored.disconnect(_on_connection_restored)
	if ConnectionGuard.client_outdated.is_connected(_on_client_outdated):
		ConnectionGuard.client_outdated.disconnect(_on_client_outdated)
	if ConnectionGuard.session_invalid.is_connected(_on_session_invalid):
		ConnectionGuard.session_invalid.disconnect(_on_session_invalid)
	if ConnectionGuard.connection_expired.is_connected(_on_connection_expired):
		ConnectionGuard.connection_expired.disconnect(_on_connection_expired)


func _build() -> void:
	_overlay = ColorRect.new()
	_overlay.color = Color(0.025, 0.03, 0.045, 0.94)
	_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_overlay.visible = false
	_overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	_overlay.z_index = 100
	add_child(_overlay)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_overlay.add_child(center)
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(560, 220)
	center.add_child(panel)
	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 14)
	panel.add_child(layout)
	_message = Label.new()
	_message.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_message.add_theme_font_size_override("font_size", 22)
	layout.add_child(_message)
	_counter = Label.new()
	_counter.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_counter.add_theme_font_size_override("font_size", 34)
	layout.add_child(_counter)
	_close_button = Button.new()
	_close_button.text = "Закрыть клиент"
	_close_button.visible = false
	_close_button.pressed.connect(func() -> void: get_tree().quit())
	layout.add_child(_close_button)
	_login_button = Button.new()
	_login_button.text = "Вернуться ко входу"
	_login_button.visible = false
	_login_button.pressed.connect(_return_to_login)
	layout.add_child(_login_button)


func _on_connection_lost(seconds_remaining: int) -> void:
	_overlay.visible = true
	_message.text = "Связь с сервером потеряна. Переподключаемся и обновляем состояние персонажа."
	_counter.text = "%d сек." % seconds_remaining
	_close_button.visible = false
	_login_button.visible = false


func _on_countdown_updated(seconds_remaining: int) -> void:
	if _overlay.visible:
		_counter.text = "%d сек." % seconds_remaining


func _on_connection_restored(character: Dictionary) -> void:
	_overlay.visible = false
	connection_restored.emit(character)


func _on_client_outdated() -> void:
	_overlay.visible = true
	_message.text = "Сервер обновлён, эта версия клиента устарела. Закройте её и запустите актуальную версию."
	_counter.text = ""
	_close_button.visible = true
	_login_button.visible = false


func _on_session_invalid(message: String) -> void:
	_overlay.visible = true
	_message.text = message
	_counter.text = ""
	_close_button.visible = false
	_login_button.visible = true


func _on_connection_expired() -> void:
	get_tree().quit()


func _return_to_login() -> void:
	ConnectionGuard.stop()
	ApiClient.set_server_url(GameSession.hub_url)
	ApiClient.token = ""
	GameSession.clear()
	session_invalid.emit()
	SCENE_TRANSITION.run(get_tree(), func() -> void: get_tree().change_scene_to_file("res://scenes/main.tscn"))
