extends Control

# Диалог взноса из ui/material_contribution_dialog.py: количество выбирается ползунком (клик или протяжка
# по дорожке), в режиме «Забрать» показывается вес после забора. Режим «contribute» повторяет Python-диалог,
# но в Godot пока не используется: Python-клиент не выводит взносы в улучшения, повозки и стойла.

signal confirmed(mode: String, item_key: String, quantity: int)

const Rules := preload("res://scripts/character_profile_rules.gd")

const PANEL_SIZE := Vector2(560.0, 260.0)
# Координаты внутри панели, как track_rect, cancel_button и confirm_button в Python.
const TRACK_RECT := Rect2(28.0, 120.0, 504.0, 8.0)
const TRACK_GRAB_MARGIN := 12.0
const KNOB_RADIUS := 11.0
const WEIGHT_Y := 145.0
const NOTE_Y_WITHDRAW := 170.0
const NOTE_Y := 151.0
const CANCEL_RECT := Rect2(282.0, 202.0, 112.0, 36.0)
const CONFIRM_RECT := Rect2(408.0, 202.0, 128.0, 36.0)
const SHADE_COLOR := Color(0.0, 0.0, 0.0, 0.667)
const PANEL_COLOR := Color8(30, 33, 29)
const BORDER_COLOR := Color8(177, 147, 91)
const TRACK_COLOR := Color8(68, 72, 63)
const FILL_COLOR := Color8(145, 174, 104)
const KNOB_COLOR := Color8(229, 215, 182)
const KNOB_OUTLINE_COLOR := Color8(91, 88, 72)
const TITLE_COLOR := Color8(230, 215, 184)
const INFO_COLOR := Color8(190, 187, 170)
const CHOSEN_COLOR := Color8(224, 211, 178)
const NOTE_COLOR := Color8(186, 191, 174)
const CANCEL_COLOR := Color8(58, 55, 49)
const CONFIRM_COLOR := Color8(74, 126, 69)
const CONFIRM_OFF_COLOR := Color8(51, 54, 48)
const CONFIRM_TEXT_COLOR := Color8(238, 235, 217)
const CONFIRM_OFF_TEXT_COLOR := Color8(142, 144, 134)
const TITLES := {"withdraw": "Забрать", "deposit": "Пополнение склада"}
const NOTES := {
	"withdraw": "Выбранное количество будет помещено в рюкзак",
	"deposit": "Выбранное количество поступит в общий запас здания",
}
const CONTRIBUTE_NOTE := "Внесённые материалы пойдут на улучшение здания"

var _mode := "deposit"
var _item_key := ""
var _label := ""
var _available := 0
var _maximum := 0
var _quantity := 0
var _carried_weight_kg := 0.0
var _carry_capacity_kg := 0.0
var _item_weight_kg := 0.0
var _dragging := false
var _frame: Control
var _title: Label
var _available_label: Label
var _chosen_label: Label
var _weight_label: Label
var _note_label: Label
var _cancel_button: Button
var _confirm_button: Button


func _init() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	z_index = 150
	visible = false
	resized.connect(_layout)
	_frame = Control.new()
	_frame.size = PANEL_SIZE
	_frame.custom_minimum_size = PANEL_SIZE
	_frame.mouse_filter = Control.MOUSE_FILTER_STOP
	_frame.draw.connect(_draw_frame)
	_frame.gui_input.connect(_on_frame_gui_input)
	add_child(_frame)
	_title = _make_label(Vector2(24.0, 20.0), TITLE_COLOR, 512.0)
	_available_label = _make_label(Vector2(24.0, 76.0), INFO_COLOR, 0.0)
	_chosen_label = _make_label(Vector2(24.0, 76.0), CHOSEN_COLOR, 512.0)
	_chosen_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_weight_label = _make_label(Vector2(24.0, WEIGHT_Y), INFO_COLOR, 0.0)
	_note_label = _make_label(Vector2(24.0, NOTE_Y), NOTE_COLOR, 0.0)
	_cancel_button = _make_button("ОТМЕНА", CANCEL_RECT, CANCEL_COLOR, CONFIRM_TEXT_COLOR, CANCEL_COLOR, CONFIRM_TEXT_COLOR)
	_cancel_button.pressed.connect(close)
	_confirm_button = _make_button("ВНЕСТИ", CONFIRM_RECT, CONFIRM_COLOR, CONFIRM_TEXT_COLOR, CONFIRM_OFF_COLOR, CONFIRM_OFF_TEXT_COLOR)
	_confirm_button.pressed.connect(_on_confirm_pressed)


func open(mode: String, item_key: String, label: String, available: int, remaining: int,
		weight_state: Dictionary = {}, item_weight_kg: float = 0.0) -> void:
	_mode = mode
	_item_key = item_key
	_label = label
	_available = maxi(0, available)
	_maximum = mini(_available, maxi(0, remaining))
	_quantity = 0
	_carried_weight_kg = float(weight_state.get("carried_weight_kg", 0.0))
	_carry_capacity_kg = float(weight_state.get("carry_capacity_kg", 0.0))
	_item_weight_kg = maxf(0.0, item_weight_kg)
	_dragging = false
	visible = true
	_layout()
	_refresh()
	queue_redraw()


func close() -> void:
	visible = false
	_dragging = false


func is_open() -> bool:
	return visible


func quantity() -> int:
	return _quantity


func maximum() -> int:
	return _maximum


# Цвет строки веса: красный от грузоподъёмности, жёлтый выше 80 %, как в Python-диалоге.
static func weight_color(resulting: float, capacity: float) -> Color:
	if capacity > 0.0 and resulting >= capacity:
		return Rules.RED
	if capacity > 0.0 and resulting / capacity > 0.8:
		return Rules.YELLOW
	return Rules.GREEN


# Числа в формате Python «:g» (шесть значащих цифр, без хвостовых нулей): 12.0 → «12», 58.5 → «58.5».
# Экспоненциальная запись очень больших чисел не воспроизводится: веса диалога её не требуют.
static func format_g(value: float) -> String:
	if value == 0.0:
		return "0"
	var magnitude := int(floor(log(absf(value)) / log(10.0)))
	var decimals := maxi(0, 5 - magnitude)
	var text := ("%%.%df" % decimals) % value
	if text.contains("."):
		text = text.rstrip("0").rstrip(".")
	return text


func _layout() -> void:
	_frame.position = ((size - PANEL_SIZE) * 0.5).floor()


func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), SHADE_COLOR)


func _gui_input(event: InputEvent) -> void:
	var mouse_button := event as InputEventMouseButton
	if mouse_button == null or not mouse_button.pressed or mouse_button.button_index != MOUSE_BUTTON_LEFT:
		return
	if not _frame.get_rect().has_point(mouse_button.position):
		close()


func _on_frame_gui_input(event: InputEvent) -> void:
	var mouse_button := event as InputEventMouseButton
	if mouse_button != null and mouse_button.button_index == MOUSE_BUTTON_LEFT:
		if mouse_button.pressed:
			if TRACK_RECT.grow(TRACK_GRAB_MARGIN).has_point(mouse_button.position):
				_dragging = true
				_set_quantity_from_x(mouse_button.position.x)
				_frame.accept_event()
		else:
			_dragging = false
		return
	var motion := event as InputEventMouseMotion
	if motion != null and _dragging:
		_set_quantity_from_x(motion.position.x)


func _set_quantity_from_x(x: float) -> void:
	if _maximum <= 0:
		_quantity = 0
	else:
		var ratio := (x - TRACK_RECT.position.x) / maxf(1.0, TRACK_RECT.size.x)
		_quantity = Rules.python_round(clampf(ratio, 0.0, 1.0) * _maximum)
	_refresh()


func _on_confirm_pressed() -> void:
	if _quantity <= 0:
		return
	var mode := _mode
	var item_key := _item_key
	var quantity_to_confirm := _quantity
	close()
	confirmed.emit(mode, item_key, quantity_to_confirm)


func _refresh() -> void:
	var withdraw := _mode == "withdraw"
	_title.text = "%s: %s" % [str(TITLES.get(_mode, "Взнос")), _label]
	var available_text := "%s: %d" % ["На складе" if withdraw else "В рюкзаке", _available]
	if withdraw:
		available_text += " · можно взять сейчас: %d" % _maximum
	_available_label.text = available_text
	var chosen_total := _available if withdraw else _maximum
	_chosen_label.text = "%s: %d / %d" % ["Забрать" if withdraw else "Внести", _quantity, chosen_total]
	_weight_label.visible = withdraw
	if withdraw:
		var resulting := _carried_weight_kg + _quantity * _item_weight_kg
		_weight_label.text = "Вес после забора: %s / %s кг" % [format_g(resulting), format_g(_carry_capacity_kg)]
		_weight_label.add_theme_color_override("font_color", weight_color(resulting, _carry_capacity_kg))
	_note_label.text = str(NOTES.get(_mode, CONTRIBUTE_NOTE))
	_note_label.position.y = NOTE_Y_WITHDRAW if withdraw else NOTE_Y
	_confirm_button.text = "ЗАБРАТЬ" if withdraw else "ВНЕСТИ"
	_confirm_button.disabled = _quantity <= 0
	_frame.queue_redraw()


func _progress() -> float:
	if _maximum <= 0:
		return 0.0
	return float(_quantity) / float(_maximum)


func _draw_frame() -> void:
	var panel_rect := Rect2(Vector2.ZERO, PANEL_SIZE)
	_frame.draw_rect(panel_rect, PANEL_COLOR)
	_frame.draw_rect(panel_rect, BORDER_COLOR, false, 2.0)
	_frame.draw_rect(TRACK_RECT, TRACK_COLOR)
	var progress := _progress()
	var fill_width := roundf(TRACK_RECT.size.x * progress)
	if fill_width > 0.0:
		_frame.draw_rect(Rect2(TRACK_RECT.position, Vector2(fill_width, TRACK_RECT.size.y)), FILL_COLOR)
	var knob := Vector2(TRACK_RECT.position.x + roundf(TRACK_RECT.size.x * progress), TRACK_RECT.get_center().y)
	_frame.draw_circle(knob, KNOB_RADIUS, KNOB_COLOR)
	_frame.draw_arc(knob, KNOB_RADIUS, 0.0, TAU, 32, KNOB_OUTLINE_COLOR, 1.0)


func _make_label(at: Vector2, color: Color, min_width: float) -> Label:
	var label := Label.new()
	label.position = at
	label.custom_minimum_size = Vector2(min_width, 0.0)
	label.add_theme_color_override("font_color", color)
	_frame.add_child(label)
	return label


func _make_button(text: String, rect: Rect2, color: Color, text_color: Color,
		disabled_color: Color, disabled_text_color: Color) -> Button:
	var button := Button.new()
	button.text = text
	button.position = rect.position
	button.size = rect.size
	button.focus_mode = Control.FOCUS_NONE
	button.add_theme_color_override("font_color", text_color)
	button.add_theme_color_override("font_disabled_color", disabled_text_color)
	button.add_theme_stylebox_override("normal", _button_style(color))
	button.add_theme_stylebox_override("hover", _button_style(color.lightened(0.12)))
	button.add_theme_stylebox_override("pressed", _button_style(color.darkened(0.12)))
	button.add_theme_stylebox_override("disabled", _button_style(disabled_color))
	_frame.add_child(button)
	return button


static func _button_style(color: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.set_corner_radius_all(4)
	return style
