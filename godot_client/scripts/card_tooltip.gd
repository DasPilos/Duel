extends PanelContainer

# Подсказка карты как draw_card_tooltip из deck/ui/card_tooltip.py: ширина 420, рамка и сдвиг у курсора.

const CARD_RULES := preload("res://scripts/card_tooltip_rules.gd")
const WIDTH := 420.0
const PADDING := 12.0
const TITLE_COLOR := Color8(255, 235, 180)
const BODY_COLOR := Color8(230, 225, 238)
const BACKGROUND := Color8(28, 24, 38, 248)
const BORDER := Color8(185, 140, 220)

var _title: Label
var _body: Label
var _card_key := ""
var _card_name := ""


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	custom_minimum_size.x = WIDTH
	z_index = 40
	visible = false
	var style := StyleBoxFlat.new()
	style.bg_color = BACKGROUND
	style.border_color = BORDER
	style.set_border_width_all(2)
	style.set_corner_radius_all(6)
	style.set_content_margin_all(PADDING)
	add_theme_stylebox_override("panel", style)
	var layout := VBoxContainer.new()
	layout.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layout.add_theme_constant_override("separation", 6)
	add_child(layout)
	_title = Label.new()
	_title.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_title.add_theme_color_override("font_color", TITLE_COLOR)
	_title.add_theme_font_size_override("font_size", 17)
	layout.add_child(_title)
	_body = Label.new()
	_body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_body.custom_minimum_size.x = WIDTH - PADDING * 2.0
	_body.add_theme_color_override("font_color", BODY_COLOR)
	layout.add_child(_body)


func show_card(card: Dictionary) -> void:
	var card_key := str(card.get("key", ""))
	var card_name := str(card.get("name", card_key))
	if visible and card_key == _card_key and card_name == _card_name:
		return
	_card_key = card_key
	_card_name = card_name
	_title.text = card_name
	_body.text = "\n".join(PackedStringArray(CARD_RULES.tooltip_lines(card)))
	visible = true
	reposition(get_global_mouse_position())


func hide_card() -> void:
	visible = false
	_card_key = ""
	_card_name = ""


func reposition(mouse: Vector2) -> void:
	var screen := get_viewport().get_visible_rect().size
	global_position = CARD_RULES.tooltip_position(mouse, size, screen)


func _process(_delta: float) -> void:
	if visible:
		reposition(get_global_mouse_position())
