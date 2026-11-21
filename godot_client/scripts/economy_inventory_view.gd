extends Control

# Окно рюкзака Экономики — порт ui/inventory_window.py: сетка и «кукла» из inventory_drag_view.gd, панель деталей с
# кнопками действий, вес и сообщения. Окно модальное и затемняет экран, как в Python. Состояние приходит с
# /api/inventory/{id}. action_requested, refresh_requested и close_requested — контракт с economy_world.gd; сигналы
# намерений сетки повторяют его для следующего этапа интеграции.

signal action_requested(action: String, payload: Dictionary)
signal refresh_requested
signal close_requested
signal move_requested(from_slot: int, to_slot: int)
signal equip_requested(slot_index: int, slot: String)
signal unequip_requested(slot: String, target_slot: int)
signal use_requested(slot_index: int)
signal drop_requested(slot_index: int)

const CHARACTER_RULES := preload("res://scripts/character_profile_rules.gd")
const ITEM_ICON_RULES := preload("res://scripts/deck_item_icon_rules.gd")
const RULES := preload("res://scripts/inventory_drag_rules.gd")
const GRID_VIEW_SCRIPT := preload("res://scripts/inventory_drag_view.gd")
const TITLE_COLOR := Color(0.94, 0.82, 0.56)
const MUTED_COLOR := Color(0.62, 0.68, 0.77)
const BORDER_COLOR := Color(0.85, 0.7, 0.35, 0.8)
const BACKGROUND_COLOR := Color(0.085, 0.095, 0.115, 0.98)
const DETAILS_COLOR := Color8(40, 36, 40)
const SHADE_COLOR := Color(0.0, 0.0, 0.0, 0.59)
const DEFAULT_CAPACITY := 50
# Окно собрано в пикселях Python (1920×1080). Канвас Godot 1280×720 масштабирует его на 2/3, как карточка профиля.
const WINDOW_SIZE := Vector2(1168.0, 780.0)
const WINDOW_SCALE := 2.0 / 3.0
const WINDOW_MARGIN := 18.0
const GRID_POSITION := Vector2(24.0, 104.0)
const DETAILS_RECT := Rect2(24.0, 560.0, 1120.0, 180.0)
const DETAILS_TEXT_RECT := Rect2(152.0, 574.0, 568.0, 152.0)
const DETAILS_ICON_POSITION := Vector2(40.0, 574.0)
const DETAILS_ICON_SIZE := 96
const BUTTON_SIZE := Vector2(190.0, 40.0)
const ACTION_BUTTON_POSITION := Vector2(736.0, 684.0)
const DROP_BUTTON_POSITION := Vector2(938.0, 684.0)
const HINT := "Тащите предмет в слот экипировки · ПКМ — надеть / снять · Del — выбросить · Esc — закрыть"

var _window: Control
var _weight: Label
var _status: Label
var _grid: GRID_VIEW_SCRIPT
var _details_empty: Label
var _details_icon: TextureRect
var _details_text: VBoxContainer
var _action_button: Button
var _drop_button: Button
var _assets_root := ""


func _init() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	z_index = 40
	visible = false
	_assets_root = ITEM_ICON_RULES.default_assets_root(ProjectSettings.globalize_path("res://").trim_suffix("/"))
	var shade := ColorRect.new()
	shade.color = SHADE_COLOR
	shade.mouse_filter = Control.MOUSE_FILTER_STOP
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(shade)
	_window = Control.new()
	_window.size = WINDOW_SIZE
	_window.scale = Vector2(WINDOW_SCALE, WINDOW_SCALE)
	add_child(_window)
	resized.connect(_layout_window)
	_build_window()
	set_message("")


func is_open() -> bool:
	return visible


func open_panel() -> void:
	visible = true
	_layout_window()


func close_panel() -> void:
	visible = false
	_grid.reset_interaction()


# Цвета как в Python: ошибка — RED, остальное по умолчанию — TEXT_DIM; успех передаёт сетка своим цветом.
func set_message(text: String, is_error := false, color: Color = RULES.TEXT_DIM_COLOR) -> void:
	_status.text = text
	_status.add_theme_color_override("font_color", RULES.BAD_COLOR if is_error else color)


func _on_grid_message(text: String, color: Color) -> void:
	set_message(text, false, color)


# Ответ сервера на действие из сетки: успех показывает текст действия, ошибка его отменяет.
func resolve_action(success: bool) -> void:
	_grid.resolve_action(success)


# carry_capacity — грузоподъёмность персонажа из профиля; цвет веса берётся по доле загрузки, как на карточке.
func set_state(state: Dictionary, carry_capacity: int) -> void:
	var carried := float(state.get("carried_weight_kg", 0.0))
	var inventory: Array = state["inventory"] if state.get("inventory") is Array else []
	var equipment: Dictionary = state["equipment"] if state.get("equipment") is Dictionary else {}
	var capacity := int(state.get("capacity", DEFAULT_CAPACITY))
	_weight.text = "Переносимый вес: %.1f / %d кг · Ячейки: %d / %d" % [carried, carry_capacity, inventory.size(), capacity]
	_weight.add_theme_color_override("font_color", CHARACTER_RULES.load_color(carried, float(carry_capacity)))
	_grid.set_items(inventory, equipment, capacity)


func _build_window() -> void:
	var background := Panel.new()
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	background.add_theme_stylebox_override("panel", _box_style(BACKGROUND_COLOR, BORDER_COLOR, 3, 14))
	_window.add_child(background)
	_add_label("Инвентарь и экипировка", Rect2(28.0, 22.0, 600.0, 36.0), 30, TITLE_COLOR)
	_status = _add_label("", Rect2(200.0, 22.0, 760.0, 30.0), 18, MUTED_COLOR, HORIZONTAL_ALIGNMENT_RIGHT)
	_weight = _add_label("", Rect2(28.0, 66.0, 1112.0, 28.0), 18, MUTED_COLOR)
	_add_button("Обновить", Rect2(970.0, 14.0, 130.0, 40.0), func() -> void: refresh_requested.emit())
	_add_button("×", Rect2(1112.0, 14.0, 40.0, 40.0), func() -> void: close_requested.emit())
	_grid = GRID_VIEW_SCRIPT.new()
	_grid.position = GRID_POSITION
	_window.add_child(_grid)
	_grid.move_requested.connect(_on_grid_move)
	_grid.equip_requested.connect(_on_grid_equip)
	_grid.unequip_requested.connect(_on_grid_unequip)
	_grid.use_requested.connect(_on_grid_use)
	_grid.drop_requested.connect(_on_grid_drop)
	_grid.selection_changed.connect(_on_grid_selection_changed)
	_grid.drop_confirm_changed.connect(_on_drop_confirm_changed)
	_grid.message_colored.connect(_on_grid_message)
	_build_details()
	_add_label(HINT, Rect2(24.0, 748.0, 1120.0, 24.0), 16, MUTED_COLOR, HORIZONTAL_ALIGNMENT_CENTER)


func _build_details() -> void:
	var details := Panel.new()
	details.position = DETAILS_RECT.position
	details.size = DETAILS_RECT.size
	details.add_theme_stylebox_override("panel", _box_style(DETAILS_COLOR, Color(0.0, 0.0, 0.0, 0.0), 0, 10))
	_window.add_child(details)
	_details_empty = _add_label("Выберите предмет, чтобы увидеть подробности", DETAILS_RECT, 20, MUTED_COLOR, HORIZONTAL_ALIGNMENT_CENTER)
	_details_empty.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_details_icon = ITEM_ICON_RULES.new_icon_rect(DETAILS_ICON_SIZE)
	_details_icon.position = DETAILS_ICON_POSITION
	_window.add_child(_details_icon)
	_details_text = VBoxContainer.new()
	_details_text.position = DETAILS_TEXT_RECT.position
	_details_text.size = DETAILS_TEXT_RECT.size
	_details_text.clip_contents = true
	_details_text.add_theme_constant_override("separation", 2)
	_window.add_child(_details_text)
	_action_button = _add_button("Надеть", Rect2(ACTION_BUTTON_POSITION, BUTTON_SIZE), _on_action_pressed)
	_drop_button = _add_button("Выбросить", Rect2(DROP_BUTTON_POSITION, BUTTON_SIZE), _on_drop_pressed)


func _add_label(text: String, rect: Rect2, font_size: int, color: Color, alignment: HorizontalAlignment = HORIZONTAL_ALIGNMENT_LEFT) -> Label:
	var label := Label.new()
	label.text = text
	label.position = rect.position
	label.size = rect.size
	label.horizontal_alignment = alignment
	label.clip_text = true
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	_window.add_child(label)
	return label


func _add_button(text: String, rect: Rect2, callback: Callable) -> Button:
	var button := Button.new()
	button.text = text
	button.position = rect.position
	button.size = rect.size
	button.focus_mode = Control.FOCUS_NONE
	button.add_theme_font_size_override("font_size", 18)
	button.pressed.connect(callback)
	_window.add_child(button)
	return button


func _layout_window() -> void:
	var scaled := WINDOW_SIZE * WINDOW_SCALE
	_window.position = Vector2(size.x - scaled.x - WINDOW_MARGIN, (size.y - scaled.y) / 2.0)


func _on_grid_selection_changed(_target: Array) -> void:
	_refresh_details()


func _on_drop_confirm_changed(_active: bool) -> void:
	_refresh_details()


func _refresh_details() -> void:
	var target: Array = _grid.selected_target()
	var item: Dictionary = _grid.selected_item()
	_clear_details_text()
	_details_empty.visible = item.is_empty()
	ITEM_ICON_RULES.apply_icon(_details_icon, _assets_root, ITEM_ICON_RULES.item_key(item), DETAILS_ICON_SIZE)
	var action := RULES.action_label(target, item)
	_action_button.text = action
	_action_button.visible = not action.is_empty()
	_drop_button.visible = not target.is_empty() and str(target[0]) == RULES.KIND_BAG
	_drop_button.text = "Точно?" if _grid.drop_confirm_active() else "Выбросить"
	if item.is_empty():
		return
	var lines := RULES.item_lines(item)
	for index in lines.size():
		var label := Label.new()
		label.text = str(lines[index][0])
		label.add_theme_color_override("font_color", lines[index][1])
		label.add_theme_font_size_override("font_size", 20 if index == 0 else 16)
		label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		_details_text.add_child(label)


func _clear_details_text() -> void:
	for child in _details_text.get_children():
		_details_text.remove_child(child)
		child.queue_free()


func _on_action_pressed() -> void:
	if _grid.selected_item().is_empty():
		return
	_grid.quick_action(_grid.selected_target())


func _on_drop_pressed() -> void:
	_grid.request_drop(_grid.selected_target())


func _on_grid_move(from_slot: int, to_slot: int) -> void:
	move_requested.emit(from_slot, to_slot)
	action_requested.emit("move", {"from_slot": from_slot, "to_slot": to_slot})


func _on_grid_equip(slot_index: int, slot: String) -> void:
	equip_requested.emit(slot_index, slot)
	action_requested.emit("equip", RULES.equip_body(slot_index, slot))


func _on_grid_unequip(slot: String, target_slot: int) -> void:
	unequip_requested.emit(slot, target_slot)
	action_requested.emit("unequip", RULES.unequip_body(slot, target_slot))


func _on_grid_use(slot_index: int) -> void:
	use_requested.emit(slot_index)
	action_requested.emit("use", {"slot_index": slot_index})


func _on_grid_drop(slot_index: int) -> void:
	drop_requested.emit(slot_index)
	action_requested.emit("drop", {"slot_index": slot_index})


func _box_style(bg: Color, border: Color, border_width: int, radius: int) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = bg
	style.border_color = border
	style.set_border_width_all(border_width)
	style.set_corner_radius_all(radius)
	return style
