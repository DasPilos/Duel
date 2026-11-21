extends Control

var editor: Node


func _draw() -> void:
	if editor != null:
		editor._draw_map_canvas(self)


func _gui_input(event: InputEvent) -> void:
	if editor == null:
		return
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				if event.double_click and not editor._minimap_contains(event.position):
					editor._handle_canvas_double_click(event.position)
				elif not editor._minimap_press(event.position):
					editor._begin_canvas_stroke(event.position, MOUSE_BUTTON_LEFT)
			elif not editor._minimap_release():
				editor._end_canvas_stroke(MOUSE_BUTTON_LEFT)
			accept_event()
		elif event.button_index == MOUSE_BUTTON_RIGHT:
			if event.pressed:
				if not editor._minimap_contains(event.position):
					editor._begin_canvas_stroke(event.position, MOUSE_BUTTON_RIGHT)
			else:
				editor._end_canvas_stroke(MOUSE_BUTTON_RIGHT)
			accept_event()
		elif event.button_index == MOUSE_BUTTON_WHEEL_UP and event.pressed:
			editor._change_zoom(1, event.position)
			accept_event()
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN and event.pressed:
			editor._change_zoom(-1, event.position)
			accept_event()
		elif event.button_index == MOUSE_BUTTON_MIDDLE:
			editor._set_pan_drag(event.pressed, event.position)
			accept_event()
	elif event is InputEventMouseMotion:
		editor._update_canvas_hover(event.position)
		if editor._minimap_drag_active():
			editor._minimap_drag(event.position)
		elif event.button_mask & MOUSE_BUTTON_MASK_LEFT:
			editor._paint_canvas_drag_at(event.position)
		elif event.button_mask & MOUSE_BUTTON_MASK_RIGHT:
			editor._erase_canvas_drag_at(event.position)
		elif event.button_mask & MOUSE_BUTTON_MASK_MIDDLE:
			editor._pan_canvas(event.relative)
		accept_event()
