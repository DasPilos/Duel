extends Control

# Одна карта боя. Лицо: арт из image_path, если файл существует, иначе цветная основа с текстом; рубашка для
# колоды, сброса и скрытых карт. Порт card_area.py: _draw_card_in_rect 925-965, _draw_card_availability 967-981,
# _draw_card_back 815-827, _draw_card_costs 1237-1247. Запросов нет: нажатие — card_pressed(zone, index),
# наведение — card_hovered(card), уход курсора — card_hovered({}).

signal card_pressed(zone: String, index: int)
signal card_hovered(card: Dictionary)

const RULES := preload("res://scripts/deck_battle_layout_rules.gd")
const NAME_FONT_SIZE := 18  # card_area.py: settings.SMALL_FONT_SIZE
const COST_FONT_SIZE := 16  # card_area.py: CARD_COST_FONT_SIZE
const FRAME_RADIUS := 6
const NAME_LINES := 3

static var _texture_cache: Dictionary = {}
static var _font: SystemFont = null

var zone := ""
var index := -1
var card: Dictionary = {}
var _hidden := false
var _flight_back := false
var _pressable := false
var _highlight := false
var _available := false
var _fill_color: Color = RULES.COLOR_CARD_FACE
var _face: Texture2D = null
var _name_label: Label
var _cost_label: Label
var _overlay: Control


func _init() -> void:
	size = RULES.CARD_SIZE
	mouse_filter = Control.MOUSE_FILTER_STOP
	texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	_name_label = Label.new()
	_name_label.add_theme_font_override("font", ui_font())
	_name_label.add_theme_font_size_override("font_size", NAME_FONT_SIZE)
	_name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_name_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_name_label.max_lines_visible = NAME_LINES
	_name_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_name_label.anchor_right = 1.0
	_name_label.anchor_bottom = 1.0
	_name_label.offset_left = 6.0
	_name_label.offset_top = 10.0
	_name_label.offset_right = -6.0
	_name_label.offset_bottom = -8.0
	add_child(_name_label)
	_cost_label = Label.new()
	_cost_label.add_theme_font_override("font", ui_font())
	_cost_label.add_theme_font_size_override("font_size", COST_FONT_SIZE)
	_cost_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_cost_label.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
	_cost_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_cost_label.anchor_top = 1.0
	_cost_label.anchor_right = 1.0
	_cost_label.anchor_bottom = 1.0
	_cost_label.offset_top = -32.0
	_cost_label.offset_bottom = -8.0
	add_child(_cost_label)
	_overlay = Control.new()
	_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_overlay.draw.connect(_draw_overlay)
	add_child(_overlay)
	gui_input.connect(_on_gui_input)
	mouse_entered.connect(_on_mouse_entered)
	mouse_exited.connect(_on_mouse_exited)


# entry — строка модели из RULES.card_entry / RULES.hidden_card_entry.
func configure(entry: Dictionary) -> void:
	zone = str(entry.get("zone", ""))
	index = int(entry.get("index", -1))
	var raw_card: Variant = entry.get("card", {})
	card = raw_card if raw_card is Dictionary else {}
	_hidden = bool(entry.get("hidden", false))
	_flight_back = false
	_pressable = bool(entry.get("pressable", false)) and not _hidden
	_highlight = bool(entry.get("highlight", false)) and not _hidden
	_available = bool(entry.get("available", false))
	_fill_color = _color_of(entry.get("fill_color", null), RULES.COLOR_CARD_FACE)
	var rect: Rect2 = entry.get("rect", Rect2(Vector2.ZERO, RULES.CARD_SIZE))
	position = rect.position
	size = rect.size
	mouse_filter = Control.MOUSE_FILTER_IGNORE if _hidden else Control.MOUSE_FILTER_STOP
	_face = null if _hidden else load_texture(str(entry.get("face_path", "")))
	_name_label.visible = not _hidden
	_cost_label.visible = not _hidden
	_name_label.text = str(card.get("name", card.get("key", "")))
	_name_label.add_theme_color_override("font_color", _color_of(entry.get("name_color", null), RULES.DEFAULT_NAME_COLOR))
	_cost_label.text = str(entry.get("cost_text", ""))
	_cost_label.add_theme_color_override("font_color", _color_of(entry.get("cost_color", null), RULES.DEFAULT_COST_COLOR))
	_overlay.visible = _highlight
	queue_redraw()
	_overlay.queue_redraw()


# Полёт карты (card_area.py:_draw_moving_card): rect уже масштабирован по ходу полёта; showing_back — рубашка.
# Полёт не принимает мышь и не подсвечивается.
func place_flight(rect: Rect2, showing_back: bool) -> void:
	position = rect.position
	size = rect.size
	_flight_back = showing_back
	_pressable = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_name_label.visible = not _hidden and not showing_back
	_cost_label.visible = not _hidden and not showing_back
	queue_redraw()
	_overlay.queue_redraw()


func is_showing_back() -> bool:
	return _hidden


func is_flight_back() -> bool:
	return _flight_back


func is_pressable() -> bool:
	return _pressable


func is_highlighted() -> bool:
	return _highlight


func is_available() -> bool:
	return _available


func has_art() -> bool:
	return _face != null


func fill_color() -> Color:
	return _fill_color


func name_text() -> String:
	return _name_label.text


func cost_text() -> String:
	return _cost_label.text


static func project_dir() -> String:
	return ProjectSettings.globalize_path("res://")


# Шрифт Python-клиента (core/settings.py FONT_NAME = "arial"); без него Godot берёт шрифт по умолчанию.
static func ui_font() -> Font:
	if _font == null:
		_font = SystemFont.new()
		_font.font_names = PackedStringArray([RULES.FONT_NAME])
	return _font


# Кэш по пути: одна и та же картинка не грузится дважды; нет файла или не читается — null.
static func load_texture(path: String) -> Texture2D:
	if path.is_empty() or not FileAccess.file_exists(path):
		return null
	if _texture_cache.has(path):
		return _texture_cache[path]
	var image := Image.load_from_file(path)
	var texture: Texture2D = null
	if image != null and not image.is_empty():
		image.convert(Image.FORMAT_RGBA8)
		image.generate_mipmaps()
		texture = ImageTexture.create_from_image(image)
	_texture_cache[path] = texture
	return texture


static func flat_box(background: Color, border: Color, border_width: int, radius: int, draw_center: bool) -> StyleBoxFlat:
	return _box(background, border, border_width, radius, draw_center)


static func _box(background: Color, border: Color, border_width: int, radius: int, draw_center: bool) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = background
	style.draw_center = draw_center
	style.border_color = border
	style.set_border_width_all(border_width)
	style.set_corner_radius_all(radius)
	return style


static func _color_of(value: Variant, fallback: Color) -> Color:
	return value if value is Color else fallback


func _draw() -> void:
	var rect := Rect2(Vector2.ZERO, size)
	if _hidden or _flight_back:
		_draw_back(rect)
		return
	if _face != null:
		draw_texture_rect(_face, rect, false)
	else:
		draw_style_box(_box(_fill_color, Color(0, 0, 0, 0), 0, FRAME_RADIUS, true), rect)
	draw_style_box(_box(Color(0, 0, 0, 0), RULES.COLOR_CARD_BORDER, 2, FRAME_RADIUS, false), rect)


func _draw_back(rect: Rect2) -> void:
	var back := load_texture(RULES.asset_path(project_dir(), RULES.CARD_BACK_ASSET))
	if back != null:
		draw_texture_rect(back, rect, false)
		draw_style_box(_box(Color(0, 0, 0, 0), RULES.COLOR_CARD_BORDER, 2, FRAME_RADIUS, false), rect)
		return
	draw_style_box(_box(RULES.COLOR_BACK_FALLBACK, RULES.COLOR_CARD_BORDER, 2, FRAME_RADIUS, true), rect)
	var inner := rect.grow(-6.0)
	draw_style_box(_box(Color(0, 0, 0, 0), RULES.COLOR_BACK_INNER, 2, 4, false), inner)
	if rect.size.x > 12.0:
		draw_line(inner.position, inner.end, RULES.COLOR_CARD_BORDER)
		draw_line(Vector2(inner.end.x, inner.position.y), Vector2(inner.position.x, inner.end.y), RULES.COLOR_CARD_BORDER)


func _draw_overlay() -> void:
	if not _highlight:
		return
	var rect := Rect2(Vector2.ZERO, size)
	if _available:
		_overlay.draw_style_box(_box(Color(0, 0, 0, 0), RULES.COLOR_GLOW, 4, 8, false), rect.grow(4.0))
		_overlay.draw_style_box(_box(Color(0, 0, 0, 0), RULES.COLOR_AVAILABLE_BORDER, 2, 8, false), rect.grow(2.0))
		var marker := Vector2(rect.end.x - 13.0, rect.position.y + 14.0)
		_overlay.draw_circle(marker, 7.0, RULES.COLOR_MARKER_BACKGROUND)
		_overlay.draw_circle(marker, 5.0, RULES.COLOR_AVAILABLE_BORDER)
		return
	_overlay.draw_rect(rect, RULES.COLOR_CARD_DIM, true)
	_overlay.draw_style_box(_box(Color(0, 0, 0, 0), RULES.COLOR_CARD_DIM_BORDER, 2, FRAME_RADIUS, false), rect)


func _on_gui_input(event: InputEvent) -> void:
	var button := event as InputEventMouseButton
	if button == null or not button.pressed or button.button_index != MOUSE_BUTTON_LEFT:
		return
	if not _pressable:
		return
	accept_event()
	card_pressed.emit(zone, index)


func _on_mouse_entered() -> void:
	if not _hidden and not card.is_empty():
		card_hovered.emit(card)


func _on_mouse_exited() -> void:
	card_hovered.emit({})
