extends SceneTree

# Проверка плавающего блока редактора: перемещение, размер, закрепление, свёртывание.

const FLOATING_PANEL_SCRIPT = preload("res://scripts/editor_floating_panel.gd")

var _failures := 0


func _init() -> void:
	var area := Control.new()
	area.size = Vector2(800, 600)
	root.add_child(area)
	var panel: Control = FLOATING_PANEL_SCRIPT.new()
	panel.set_title("Тест")
	area.add_child(panel)
	panel.position = Vector2(100, 100)
	panel.size = Vector2(200, 200)
	var content := Label.new()
	content.text = "содержимое"
	panel.set_content(content)
	_check(content.get_parent() != null and content.get_parent() != panel, "содержимое переносится в тело блока")
	_check(content.anchor_right == 1.0 and content.anchor_bottom == 1.0, "содержимое растягивается на тело блока")

	# Перемещение за заголовок и ограничение областью родителя.
	panel._move_by(Vector2(50, 20))
	_check(panel.position == Vector2(150, 120), "блок двигается на смещение")
	panel._move_by(Vector2(5000, 5000))
	_check(panel.position.x <= area.size.x - 60.0 and panel.position.y <= area.size.y - 26.0, "блок не уходит за область")
	panel._move_by(Vector2(-5000, -5000))
	_check(panel.position.y >= 0.0 and panel.position.x >= 60.0 - panel.size.x, "блок не уходит за левый и верхний край")

	# Закрепление запрещает перемещение (через обработчик заголовка) и размер (через уголок).
	panel._toggle_pinned()
	_check(panel.pinned, "блок закреплён")
	_check(not panel._grip.visible, "уголок размера скрыт у закреплённого блока")
	var before := panel.position
	panel._on_header_input(_mouse_button(true))
	panel._on_header_input(_mouse_motion(Vector2(40, 40)))
	_check(panel.position == before, "закреплённый блок не двигается")
	panel._toggle_pinned()
	_check(not panel.pinned and panel._grip.visible, "блок откреплён, уголок снова виден")

	# Свёртывание оставляет только заголовок; развёртывание возвращает высоту.
	var expanded_height := panel.size.y
	panel._toggle_collapsed()
	_check(panel.collapsed and panel.size.y == panel.TITLE_HEIGHT, "свёрнутый блок показывает только заголовок")
	_check(not panel._body.visible, "тело скрыто при свёртывании")
	panel._toggle_collapsed()
	_check(not panel.collapsed and panel.size.y == expanded_height, "развёрнутый блок возвращает высоту")
	_check(panel._body.visible, "тело снова видно")

	# Состояние сохраняется и восстанавливается без потерь.
	panel.position = Vector2(120, 40)
	panel.size = Vector2(260, 330)
	panel.panel_key = "palette"
	var state: Dictionary = panel.get_state()
	var restored: Control = FLOATING_PANEL_SCRIPT.new()
	area.add_child(restored)
	restored.apply_state({"key": "palette", "x": 120, "y": 40, "w": 260, "h": 330, "pinned": true, "collapsed": false, "expanded_height": 330})
	_check(restored.pinned and restored.position == Vector2(120, 40) and restored.size == Vector2(260, 330), "состояние восстанавливается")
	_check(state["key"] == "palette" and state["w"] == 260.0, "состояние содержит ключ и размер")
	restored.apply_state({"w": 10, "h": 10})
	_check(restored.size.x >= restored.MIN_SIZE.x and restored.size.y >= restored.MIN_SIZE.y, "слишком маленький размер из файла ограничивается")
	var emitted := [false]
	restored.layout_changed.connect(func() -> void: emitted[0] = true)
	restored._toggle_collapsed()
	_check(emitted[0], "сигнал об изменении раскладки отправляется")
	print("editor floating panel checks failures=%d" % _failures)
	quit(_failures)


func _mouse_button(pressed: bool) -> InputEventMouseButton:
	var event := InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = pressed
	return event


func _mouse_motion(relative: Vector2) -> InputEventMouseMotion:
	var event := InputEventMouseMotion.new()
	event.relative = relative
	return event


func _check(condition: bool, message: String) -> void:
	if not condition:
		_failures += 1
		print("FAIL: %s" % message)
