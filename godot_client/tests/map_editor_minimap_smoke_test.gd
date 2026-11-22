extends Node

const MINIMAP_RULES = preload("res://scripts/map_editor_minimap_rules.gd")


class MinimapEditor extends "res://scripts/map_editor.gd":
	func _ready() -> void:
		_mode = "economy"
		_build_ui()


var editor: MinimapEditor
var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _run() -> void:
	editor = MinimapEditor.new()
	editor.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(editor)
	await get_tree().process_frame
	editor._catalog_by_key = {
		"grass": {"item_key": "grass", "kind": "ground", "category": "grass"},
		"pond": {"item_key": "pond", "kind": "ground", "category": "water"},
		"rock": {"item_key": "rock", "kind": "object", "category": "rock"},
	}
	editor._map_width.value = 32
	editor._map_height.value = 16
	_check_rules()
	_check_image()
	_check_editor_state()
	_check_click_and_drag()
	_check_toggle()
	await _check_draw()
	_finish()


func _finish() -> void:
	if is_instance_valid(editor):
		editor.free()
	for failure in _failures:
		push_error(failure)
	if _failures.is_empty():
		print("map_editor_minimap_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(0 if _failures.is_empty() else 1)


func _category_for_test(key: String) -> String:
	return "water" if key == "pond" else "grass"


func _cell_position(cell: Vector2i) -> Vector2:
	return editor._pan + (Vector2(cell) + Vector2(0.5, 0.5)) * editor.TILE_SIZE * editor._zoom


func _click(cell: Vector2i, button: MouseButton) -> void:
	editor._begin_canvas_stroke(_cell_position(cell), button)
	editor._end_canvas_stroke(button)


func _press(keycode: Key) -> void:
	var event := InputEventKey.new()
	event.keycode = keycode
	event.physical_keycode = keycode
	event.pressed = true
	editor._unhandled_key_input(event)


func _button_event(position: Vector2, pressed: bool) -> InputEventMouseButton:
	var event := InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = pressed
	event.position = position
	return event


func _motion_event(position: Vector2) -> InputEventMouseMotion:
	var event := InputEventMouseMotion.new()
	event.position = position
	event.button_mask = MOUSE_BUTTON_MASK_LEFT
	return event


func _check_rules() -> void:
	_check(MINIMAP_RULES.size_for(Vector2i(128, 256), 170.0).is_equal_approx(Vector2(85.0, 170.0)), "Миникарта сохраняет пропорции карты")
	var rect := MINIMAP_RULES.rect_for(Vector2(400.0, 300.0), Vector2i(64, 64))
	_check(rect.size.is_equal_approx(Vector2(105.0, 105.0)) and rect.end.is_equal_approx(Vector2(388.0, 288.0)), "Миникарта стоит в правом нижнем углу и не больше трети холста")
	_check(MINIMAP_RULES.rect_for(Vector2(400.0, 300.0), Vector2i(0, 5)).size == Vector2.ZERO, "Пустая карта не даёт миникарту")
	var mini := Rect2(Vector2(10.0, 20.0), Vector2(64.0, 64.0))
	_check(MINIMAP_RULES.tile_at(Vector2(10.5, 20.5), mini, Vector2i(64, 64)) == Vector2i(0, 0), "Клик у левого верхнего угла попадает в клетку (0, 0)")
	_check(MINIMAP_RULES.tile_at(Vector2(40.2, 60.9), mini, Vector2i(64, 64)) == Vector2i(30, 40), "Клик на миникарте переводится в клетку карты")
	_check(MINIMAP_RULES.tile_at(Vector2(9999.0, -50.0), mini, Vector2i(64, 64)) == Vector2i(63, 0), "Клик за пределами миникарты зажимается по краю карты")
	var view := MINIMAP_RULES.view_rect(Vector2.ZERO, 16.0, Vector2(160.0, 160.0), Vector2i(64, 64), mini)
	_check(view.is_equal_approx(Rect2(10.0, 20.0, 10.0, 10.0)), "Рамка показывает видимую часть карты")
	view = MINIMAP_RULES.view_rect(Vector2(-160.0, -160.0), 16.0, Vector2(160.0, 160.0), Vector2i(64, 64), mini)
	_check(view.is_equal_approx(Rect2(20.0, 30.0, 10.0, 10.0)), "Рамка сдвигается вместе с камерой")
	view = MINIMAP_RULES.view_rect(Vector2(-100000.0, 0.0), 16.0, Vector2(160.0, 160.0), Vector2i(64, 64), mini)
	_check(view.size.x == 0.0 and view.position.x == 74.0, "Рамка не выходит за пределы карты")
	var pan := MINIMAP_RULES.pan_for_center(Vector2i(10, 20), Vector2(400.0, 300.0), 16.0)
	_check(pan.is_equal_approx(Vector2(200.0 - 10.5 * 16.0, 150.0 - 20.5 * 16.0)), "Центрирование ставит выбранную клетку в середину холста")
	_check(MINIMAP_RULES.color_for_category("water") == Color8(56, 104, 168), "Цвета категорий взяты из палитры Python")
	_check(MINIMAP_RULES.color_for_category("") == MINIMAP_RULES.MINI_UNKNOWN, "Неизвестная категория показывается серым")
	_check(MINIMAP_RULES.atlas_category("Почва") == "ground" and MINIMAP_RULES.atlas_category("Облака") == "", "Листы атласа получают категорию или остаются без цвета")


func _check_image() -> void:
	var layer := {"id": 1, "type": "tile", "cells": {"3:4": "pond", "9:9": "grass", "40:40": "pond", "bad": "pond"}}
	var image := MINIMAP_RULES.build_image(Vector2i(32, 16), [layer], Callable(self, "_category_for_test"))
	_check(image.get_size() == Vector2i(32, 16), "Изображение миникарты повторяет размер карты")
	_check(image.get_pixel(3, 4).is_equal_approx(MINIMAP_RULES.color_for_category("water")), "Клетка с водой окрашивается цветом воды")
	_check(image.get_pixel(9, 9).is_equal_approx(MINIMAP_RULES.color_for_category("grass")), "Клетка с травой окрашивается цветом травы")
	_check(image.get_pixel(0, 0).is_equal_approx(MINIMAP_RULES.MINI_EMPTY), "Пустая клетка остаётся тёмной")


func _check_editor_state() -> void:
	editor._create_default_layers()
	editor._render_layers()
	editor._layers[0]["cells"] = {"3:4": "pond", "5:5": "grass"}
	editor._layers[1]["cells"] = {"7:7": "rock"}
	_check(not editor._minimap_visible and not editor._minimap_button.button_pressed, "Миникарта скрыта по умолчанию, чтобы не закрывать карту")
	editor._toggle_minimap()
	_check(editor._minimap_visible and editor._minimap_button.button_pressed, "Миникарту можно включить кнопкой")
	editor._refresh_minimap_texture(editor._map_size())
	var image := editor._minimap_texture.get_image()
	_check(image.get_pixel(3, 4).is_equal_approx(MINIMAP_RULES.color_for_category("water")), "Миникарта рисует землю цветом категории")
	_check(image.get_pixel(7, 7).is_equal_approx(MINIMAP_RULES.color_for_category("rock")), "Объекты тоже попадают на миникарту")
	_check(not editor._minimap_dirty, "После перестройки миникарта больше не помечена устаревшей")
	editor._layers[0]["visible"] = false
	editor._minimap_dirty = true
	editor._refresh_minimap_texture(editor._map_size())
	_check(editor._minimap_texture.get_image().get_pixel(3, 4).is_equal_approx(MINIMAP_RULES.MINI_EMPTY), "Скрытый слой не попадает на миникарту")
	editor._layers[0]["visible"] = true
	editor._select_tool("brush")
	editor._selected_item_key = "grass"
	_click(Vector2i(10, 10), MOUSE_BUTTON_LEFT)
	_check(editor._minimap_dirty, "Мазок помечает миникарту устаревшей")
	editor._refresh_minimap_texture(editor._map_size())
	_check(editor._minimap_texture.get_image().get_pixel(10, 10).is_equal_approx(MINIMAP_RULES.color_for_category("grass")), "Миникарта обновляется после мазка")
	editor._undo_last_action()
	editor._refresh_minimap_texture(editor._map_size())
	_check(editor._minimap_texture.get_image().get_pixel(10, 10).is_equal_approx(MINIMAP_RULES.MINI_EMPTY), "Отмена обновляет миникарту")
	editor._map_width.value = 20
	editor._refresh_minimap_texture(editor._map_size())
	_check(editor._minimap_texture.get_size() == Vector2(20, 16), "Смена размера карты перестраивает миникарту")


func _check_click_and_drag() -> void:
	editor._zoom = 1.0
	editor._pan = Vector2.ZERO
	var canvas_size: Vector2 = editor._canvas.size
	_check(canvas_size.x > 100.0 and canvas_size.y > 100.0, "Холст имеет размер для проверки миникарты")
	var map_size: Vector2i = editor._map_size()
	var rect := editor._minimap_rect()
	var center := rect.get_center()
	_check(editor._minimap_contains(center) and not editor._minimap_contains(Vector2(5.0, 5.0)), "Попадание в миникарту и мимо неё определяется верно")
	var target := MINIMAP_RULES.tile_at(center, rect, map_size)
	editor._canvas._gui_input(_button_event(center, true))
	_check(editor._minimap_drag_active() and editor._stroke_button == MOUSE_BUTTON_NONE, "Нажатие на миникарту начинает перемещение камеры, а не мазок")
	var expected := MINIMAP_RULES.pan_for_center(target, canvas_size, editor.TILE_SIZE * editor._zoom)
	_check(editor._pan.is_equal_approx(expected), "Клик по миникарте центрирует камеру на выбранной клетке")
	var on_canvas := editor._pan + (Vector2(target) + Vector2(0.5, 0.5)) * editor.TILE_SIZE * editor._zoom
	_check(on_canvas.is_equal_approx(canvas_size / 2.0), "Выбранная клетка оказывается в середине холста")
	var corner := rect.position + Vector2(1.0, 1.0)
	editor._canvas._gui_input(_motion_event(corner))
	_check(editor._pan.is_equal_approx(MINIMAP_RULES.pan_for_center(Vector2i(0, 0), canvas_size, editor.TILE_SIZE * editor._zoom)), "Перетаскивание по миникарте двигает камеру")
	editor._canvas._gui_input(_button_event(corner, false))
	_check(not editor._minimap_drag_active() and editor._stroke_button == MOUSE_BUTTON_NONE, "Отпускание завершает перемещение без мазка")
	_check(not editor._layers[0]["cells"].has("0:0"), "Клик по миникарте не рисует на карте")
	var painted := Vector2i(4, 4)
	editor._selected_item_key = "grass"
	editor._canvas._gui_input(_button_event(_cell_position(painted), true))
	editor._canvas._gui_input(_button_event(_cell_position(painted), false))
	_check(editor._layers[0]["cells"].get("4:4") == "grass", "Клик вне миникарты по-прежнему рисует на холсте")
	var right_on_minimap := InputEventMouseButton.new()
	right_on_minimap.button_index = MOUSE_BUTTON_RIGHT
	right_on_minimap.pressed = true
	right_on_minimap.position = center
	editor._canvas._gui_input(right_on_minimap)
	_check(editor._stroke_button == MOUSE_BUTTON_NONE, "Правая кнопка на миникарте не стирает клетки под ней")
	editor._canvas._gui_input(_button_event(center, false))


func _check_toggle() -> void:
	var rect := editor._minimap_rect()
	var center := rect.get_center()
	_press(KEY_M)
	_check(not editor._minimap_visible and not editor._minimap_button.button_pressed and not editor._minimap_contains(center), "Клавиша M прячет миникарту и отжимает кнопку")
	_check(not editor._minimap_press(center), "Скрытая миникарта не реагирует на нажатие")
	_press(KEY_M)
	_check(editor._minimap_visible and editor._minimap_button.button_pressed, "Повторное M показывает миникарту")
	editor._minimap_button.pressed.emit()
	_check(not editor._minimap_visible, "Кнопка «Миникарта» скрывает её")
	editor._minimap_button.pressed.emit()
	_check(editor._minimap_visible, "Кнопка «Миникарта» снова показывает её")


func _check_draw() -> void:
	editor._canvas.queue_redraw()
	await get_tree().process_frame
	await get_tree().process_frame
	_check(editor._minimap_texture != null and not editor._minimap_dirty, "Холст с миникартой отрисовывается без ошибок")
