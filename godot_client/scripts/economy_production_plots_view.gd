extends Control

# Рисунок участков производственного окна: порт _draw_plots, _draw_digs, _draw_pen и _draw_rift из
# ui/production_building_window.py. Холст не делает запросов: клик и правый клик уходят родителю сигналами,
# состояние здания приходит через set_state. Текстуры и домики читаются из ../assets, как в других видах Godot.

signal plot_clicked(index: int)
signal plot_removed(index: int)

const RULES := preload("res://scripts/economy_production_rules.gd")
const REF := preload("res://scripts/economy_production_reference.gd")
const GEO := preload("res://scripts/economy_production_plot_geometry.gd")

const CANVAS_HEIGHT := 340.0
const MARGIN := 6.0
const FONT_SIZE := 11
const DIM_TINT := Color8(120, 120, 120)
const HOUSE_DIM := Color8(90, 90, 90)
const HOVER_BORDER := Color8(255, 240, 170)
const CAPTION_COLOR := Color8(250, 235, 190)
const FALLBACK_FIELD := Color8(90, 70, 40)
const FALLBACK_HOUSE := Color8(150, 105, 65)
const ORE_COLORS := {
	"iron": Color8(200, 120, 90),
	"stone": Color8(185, 185, 178),
	"mithril": Color8(150, 205, 245),
	"obsidian": Color8(140, 70, 190),
}

# Текстуры кэшируются на весь сеанс: окно перерисовывается при каждом ответе сервера.
static var _textures: Dictionary = {}

var _building := ""
var _character_id := 0
var _state: Dictionary = {}
var _layout_key := ""
var _area := Rect2()
var _groups: Array = []
var _plots: Array = []
var _hovered := -1


func _init() -> void:
	custom_minimum_size = Vector2(0.0, CANVAS_HEIGHT)
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	mouse_filter = Control.MOUSE_FILTER_STOP
	texture_repeat = CanvasItem.TEXTURE_REPEAT_ENABLED
	clip_contents = true
	resized.connect(queue_redraw)
	mouse_exited.connect(_on_mouse_exited)


func set_building(building: String) -> void:
	_building = building
	queue_redraw()


func set_state(state: Dictionary, character_id: int) -> void:
	_state = state
	_character_id = character_id
	queue_redraw()


func plot_count() -> int:
	return RULES.plot_groups(_building).size()


func plot_geometry() -> Array:
	_ensure_layout()
	return _plots


func plot_at(at: Vector2) -> int:
	_ensure_layout()
	for index in range(_plots.size()):
		var plot: Dictionary = _plots[index]
		if plot["rect"].has_point(at) and Geometry2D.is_point_in_polygon(at, plot["points"]):
			return index
	return -1


static func asset_path(asset_dir: String, file_name: String) -> String:
	var root := ProjectSettings.globalize_path("res://").path_join("../assets").simplify_path()
	return root.path_join("town").path_join(asset_dir).path_join(file_name)


func _draw() -> void:
	_ensure_layout()
	match _shape():
		"fields", "pie":
			_draw_textured_plots()
		"rift":
			_draw_rift()
		"pen":
			_draw_pen()
		"digs":
			_draw_digs()


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		var hovered := plot_at((event as InputEventMouseMotion).position)
		if hovered != _hovered:
			_hovered = hovered
			queue_redraw()
	elif event is InputEventMouseButton and (event as InputEventMouseButton).pressed:
		var button := event as InputEventMouseButton
		var index := plot_at(button.position)
		if index < 0:
			return
		if button.button_index == MOUSE_BUTTON_LEFT:
			accept_event()
			plot_clicked.emit(index)
		elif button.button_index == MOUSE_BUTTON_RIGHT:
			accept_event()
			plot_removed.emit(index)


func _get_tooltip(at_position: Vector2) -> String:
	var index := plot_at(at_position)
	return "" if index < 0 else RULES.plot_hint(_state, _building, index, _character_id)


func _on_mouse_exited() -> void:
	if _hovered != -1:
		_hovered = -1
		queue_redraw()


func _ensure_layout() -> void:
	if not RULES.has_plot_view(_building):
		_plots = []
		_groups = []
		return
	var area := Rect2(Vector2(MARGIN, MARGIN), Vector2(maxf(1.0, size.x - MARGIN * 2.0), maxf(1.0, size.y - MARGIN * 2.0)))
	var level := int(_state.get("level", 1))
	var max_workers := int(RULES.level_info(_building, level).get("max_workers", 0))
	var key := "%s|%s|%d" % [_building, str(area.size), max_workers]
	if key == _layout_key:
		return
	_layout_key = key
	_area = area
	_groups = RULES.plot_groups(_building)
	_plots = GEO.build(_shape(), area, _groups, max_workers)


func _view() -> Dictionary:
	return REF.BUILDINGS.get(_building, {})


func _shape() -> String:
	return str(_view().get("shape", ""))


func _asset_dir() -> String:
	return str(_view().get("asset_dir", ""))


func _slots_or_empty(index: int) -> Array:
	var slots: Variant = RULES.plot_slots(_state, _building, index)
	return slots if slots is Array else []


static func _lit_list(count: int) -> Array:
	var lit: Array = []
	for _i in range(count):
		lit.append(true)
	return lit


func _draw_textured_plots() -> void:
	var stage := RULES.stage_index(_state)
	if _shape() == "pie":
		for plot in _plots:
			draw_colored_polygon(plot["points"], Color8(22, 40, 22))
			_draw_closed_outline(plot["points"], Color8(16, 30, 16), 6.0)
	for index in range(_plots.size()):
		var plot: Dictionary = _plots[index]
		var slots: Variant = RULES.plot_slots(_state, _building, index)
		if not slots is Array:
			_draw_locked(plot, RULES.plot_lock_caption(_building, index),
				Color8(42, 42, 40), Color8(75, 75, 68), Color8(130, 130, 120))
			continue
		var workers := RULES.count_occupied(slots)
		var group: Dictionary = _groups[index]
		var texture := _texture(_asset_dir(), RULES.texture_file(str(group["resource"]), stage if workers > 0 else 0))
		_draw_textured_polygon(plot, texture, Color.WHITE if workers > 0 else DIM_TINT, FALLBACK_FIELD)
		var border := HOVER_BORDER if index == _hovered else (Color8(235, 200, 95) if workers > 0 else Color8(130, 110, 75))
		_draw_closed_outline(plot["points"], border, 2.0)
		_draw_house_row(plot["center"].x, plot["house_y"], _lit_list(workers), GEO.HOUSE_SIZE + 4.0)


func _draw_textured_polygon(plot: Dictionary, texture: Texture2D, tint: Color, fallback: Color) -> void:
	var points: PackedVector2Array = plot["points"]
	if texture == null:
		draw_colored_polygon(points, fallback * tint)
		return
	var origin: Vector2 = plot["rect"].position
	var tile := texture.get_size()
	var uvs := PackedVector2Array()
	var colors := PackedColorArray()
	for point in points:
		uvs.append((point - origin) / tile)
		colors.append(tint)
	draw_polygon(points, colors, uvs, texture)


func _draw_locked(plot: Dictionary, caption: String, fill: Color, border: Color, text_color: Color) -> void:
	draw_colored_polygon(plot["points"], fill)
	_draw_closed_outline(plot["points"], border, 2.0)
	_draw_text(caption, plot["center"], text_color, 0)


func _draw_house_row(center_x: float, house_y: float, lit: Array, step: float) -> void:
	var start_x := center_x - lit.size() * step / 2.0
	for number in range(lit.size()):
		_draw_house(Vector2(start_x + number * step, house_y), bool(lit[number]))


func _draw_house(at: Vector2, lit: bool) -> void:
	var texture := _texture(_asset_dir(), "house.png")
	if texture == null:
		draw_rect(Rect2(at + Vector2(5.25, 10.5), Vector2(17.5, 15.75)), FALLBACK_HOUSE)
		return
	draw_texture_rect(texture, Rect2(at, Vector2(GEO.HOUSE_SIZE, GEO.HOUSE_SIZE)), false, Color.WHITE if lit else HOUSE_DIM)


func _draw_digs() -> void:
	draw_rect(_area, Color8(60, 56, 52))
	var stage := RULES.stage_index(_state)
	var factor := GEO.scale_for(_area)
	for index in range(_plots.size()):
		var plot: Dictionary = _plots[index]
		var slots: Variant = RULES.plot_slots(_state, _building, index)
		if not slots is Array:
			_draw_locked(plot, RULES.plot_lock_caption(_building, index),
				Color8(44, 42, 40), Color8(78, 74, 68), Color8(130, 126, 120))
			continue
		var workers := RULES.count_occupied(slots)
		var group: Dictionary = _groups[index]
		var rect: Rect2 = plot["rect"]
		var rng := _rng(index)
		draw_colored_polygon(plot["points"], Color8(24, 23, 25))
		for _i in range(int(rect.size.x * rect.size.y / 500.0)):
			var at := Vector2(rng.randf_range(rect.position.x, rect.end.x), rng.randf_range(rect.position.y, rect.end.y))
			if Geometry2D.is_point_in_polygon(at, plot["points"]):
				draw_circle(at, float(rng.randi_range(2, 4)), Color8(44, 44, 48))
		var border := HOVER_BORDER if index == _hovered else (Color8(200, 170, 90) if workers > 0 else Color8(110, 100, 86))
		_draw_closed_outline(plot["points"], border, 3.0)
		_draw_cart(plot["center"], (36.0 + 10.0 * int(group["places"])) * factor, stage if workers > 0 else 0)
		_draw_house_row(plot["center"].x, plot["house_y"], _lit_list(workers), GEO.HOUSE_SIZE + 4.0)


# Вагонетка по стадии цикла: 0 пустая, 1 наполовину, 2 полная, 3 полная с горкой (_draw_cart в Python).
func _draw_cart(center: Vector2, width: float, stage: int) -> void:
	var half_w := width / 2.0
	var half_h := width * 0.25
	var top := center.y - half_h
	var bottom := center.y + half_h
	var inset := 6.0 * GEO.scale_for(_area)
	var coal := Color8(12, 12, 14)
	var body := PackedVector2Array([
		Vector2(center.x - half_w, top), Vector2(center.x + half_w, top),
		Vector2(center.x + half_w - inset, bottom), Vector2(center.x - half_w + inset, bottom),
	])
	draw_colored_polygon(body, Color8(132, 98, 64))
	if stage >= 1:
		var level_y := center.y if stage == 1 else top + 3.0
		draw_colored_polygon(PackedVector2Array([
			Vector2(center.x - half_w + 3.0, level_y), Vector2(center.x + half_w - 3.0, level_y),
			Vector2(center.x + half_w - 7.0, bottom - 2.0), Vector2(center.x - half_w + 7.0, bottom - 2.0),
		]), coal)
		var offset := -half_w + 8.0
		while offset < half_w - 6.0:
			draw_circle(Vector2(center.x + offset, level_y + 2.0), 1.0, Color8(90, 90, 100))
			offset += 7.0
	if stage == 3:
		var heap := PackedVector2Array([
			Vector2(center.x - half_w + 2.0, top + 2.0), Vector2(center.x, top - half_h - 6.0),
			Vector2(center.x + half_w - 2.0, top + 2.0),
		])
		draw_colored_polygon(heap, coal)
		_draw_closed_outline(heap, Color8(90, 90, 100), 1.0)
	_draw_closed_outline(body, Color8(84, 58, 34), 3.0)
	draw_line(Vector2(center.x - half_w, top), Vector2(center.x + half_w, top), Color8(170, 170, 176), 2.0)
	for wheel_x in [center.x - width / 3.0, center.x + width / 3.0]:
		var wheel := Vector2(wheel_x, bottom + 4.0)
		var radius := maxf(4.0, width / 9.0)
		draw_circle(wheel, radius, Color8(40, 36, 34))
		draw_arc(wheel, radius, 0.0, TAU, 16, Color8(110, 100, 90), 2.0)


func _draw_pen() -> void:
	draw_rect(_area, Color8(52, 78, 40))
	if _plots.is_empty():
		return
	var plot: Dictionary = _plots[0]
	var pen: Rect2 = plot["rect"]
	var slots := _slots_or_empty(0)
	var workers := RULES.count_occupied(slots)
	var rng := _rng(7)
	draw_rect(pen, Color8(112, 112, 58))
	for _i in range(int(pen.size.x * pen.size.y / 900.0)):
		var at := Vector2(rng.randf_range(pen.position.x, pen.end.x), rng.randf_range(pen.position.y, pen.end.y))
		draw_circle(at, float(rng.randi_range(2, 5)), Color8(128, 104, 64))
	for number in range(workers * 2):
		var x := rng.randf_range(pen.position.x + 30.0, maxf(pen.position.x + 31.0, pen.end.x - 40.0))
		var y := rng.randf_range(pen.position.y + 24.0, maxf(pen.position.y + 25.0, pen.end.y - 20.0))
		var spotted := number % 2 == 0
		var body := Color8(240, 238, 230) if spotted else Color8(130, 88, 58)
		draw_colored_polygon(_ellipse(Vector2(x, y), 18.0, 10.0), body)
		draw_circle(Vector2(x + 19.0, y - 5.0), 8.0, body)
		for leg in [-12.0, -4.0, 6.0, 12.0]:
			draw_line(Vector2(x + leg, y + 8.0), Vector2(x + leg, y + 15.0), Color8(60, 46, 36), 3.0)
		if spotted:
			draw_circle(Vector2(x - 5.0, y - 2.0), 6.0, Color8(30, 28, 26))
	var fence := HOVER_BORDER if _hovered == 0 else Color8(150, 108, 62)
	for offset in [6.0, 16.0]:
		draw_rect(pen.grow(-offset / 2.0), fence, false, 3.0)
	var post := Color8(98, 68, 38)
	var x_post := pen.position.x
	while x_post <= pen.end.x:
		draw_rect(Rect2(x_post - 3.0, pen.position.y - 4.0, 7.0, 14.0), post)
		draw_rect(Rect2(x_post - 3.0, pen.end.y - 10.0, 7.0, 14.0), post)
		x_post += 34.0
	var y_post := pen.position.y
	while y_post <= pen.end.y:
		draw_rect(Rect2(pen.position.x - 4.0, y_post - 3.0, 14.0, 7.0), post)
		draw_rect(Rect2(pen.end.x - 10.0, y_post - 3.0, 14.0, 7.0), post)
		y_post += 34.0
	var lit: Array = []
	for slot in slots:
		lit.append(bool(slot.get("occupied", false)))
	_draw_house_row(pen.get_center().x, plot["house_y"], lit, GEO.HOUSE_SIZE + 6.0)
	_draw_text("Загон · горожан %d/%d" % [workers, slots.size()],
		Vector2(pen.get_center().x, pen.position.y - 6.0), CAPTION_COLOR, 2)


func _draw_rift() -> void:
	draw_set_transform(_area.position)
	for command in GEO.rift_backdrop(_area.size):
		match command["type"]:
			"polygon":
				draw_colored_polygon(command["points"], command["color"])
			"line":
				draw_polyline(command["points"], command["color"], command["width"], true)
			"circle":
				draw_circle(command["center"], command["radius"], command["color"])
	draw_set_transform(Vector2.ZERO)
	var factor := GEO.scale_for(_area)
	for index in range(_plots.size()):
		var plot: Dictionary = _plots[index]
		var group: Dictionary = _groups[index]
		var slots: Variant = RULES.plot_slots(_state, _building, index)
		if not slots is Array:
			_draw_locked(plot, RULES.plot_lock_caption(_building, index),
				Color8(52, 50, 48), Color8(84, 80, 74), Color8(140, 136, 128))
			continue
		var workers := RULES.count_occupied(slots)
		var center: Vector2 = plot["center"]
		draw_colored_polygon(plot["points"], Color8(98, 90, 82))
		var border := HOVER_BORDER if index == _hovered else (Color8(235, 200, 95) if workers > 0 else Color8(140, 124, 100))
		_draw_closed_outline(plot["points"], border, 2.0)
		_draw_mine(center, index, ORE_COLORS[str(group["resource"])], factor)
		if workers > 0:
			draw_circle(center + Vector2(0.0, 12.0 * factor), 5.0, Color8(255, 190, 90))
		_draw_tent(plot["tent"], "%d/%d" % [workers, slots.size()], factor)
		_draw_text(RULES.plot_name(_building, group), center + Vector2(0.0, 40.0), CAPTION_COLOR, 1)


# Вход в шахту: тёмная арка в деревянной крепи и вкрапления руды.
func _draw_mine(center: Vector2, index: int, ore: Color, factor: float) -> void:
	var arch := Rect2(center + Vector2(-34.0, -40.0) * factor, Vector2(68.0, 70.0) * factor)
	var dark := Color8(18, 14, 12)
	var mid_y := arch.get_center().y
	draw_colored_polygon(_ellipse(arch.get_center(), arch.size.x / 2.0, arch.size.y / 2.0), dark)
	draw_rect(Rect2(arch.position.x, mid_y, arch.size.x, arch.size.y / 2.0), dark)
	var post := Color8(120, 84, 46)
	draw_line(Vector2(arch.position.x, mid_y - 6.0 * factor), Vector2(arch.position.x, arch.end.y), post, 3.0)
	draw_line(Vector2(arch.end.x, mid_y - 6.0 * factor), Vector2(arch.end.x, arch.end.y), post, 3.0)
	draw_line(Vector2(arch.position.x - 6.0 * factor, mid_y - 8.0 * factor),
		Vector2(arch.end.x + 6.0 * factor, mid_y - 8.0 * factor), Color8(140, 98, 54), 3.0)
	var rng := _rng(index)
	for _i in range(14):
		var angle := rng.randf_range(0.0, TAU)
		var distance := rng.randf_range(55.0, 110.0) * factor
		draw_circle(center + Vector2(cos(angle) * distance, sin(angle) * distance * 0.65), float(rng.randi_range(3, 5)), ore)


func _draw_tent(at: Vector2, text: String, factor: float) -> void:
	var roof := PackedVector2Array([at + Vector2(-24.0, 14.0) * factor, at + Vector2(0.0, -20.0) * factor, at + Vector2(24.0, 14.0) * factor])
	draw_colored_polygon(roof, Color8(196, 168, 116))
	_draw_closed_outline(roof, Color8(110, 84, 52), 2.0)
	draw_colored_polygon(PackedVector2Array([
		at + Vector2(-7.0, 14.0) * factor, at + Vector2(0.0, -2.0) * factor, at + Vector2(7.0, 14.0) * factor,
	]), Color8(60, 44, 30))
	var font := get_theme_default_font()
	var text_size := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE)
	var box := Rect2(at.x - (text_size.x + 10.0) / 2.0, at.y + 17.0 * factor, text_size.x + 10.0, text_size.y + 4.0)
	draw_rect(box, Color8(24, 20, 16))
	draw_rect(box, Color8(180, 150, 90), false, 1.0)
	_draw_text(text, box.get_center(), Color8(255, 240, 190), 0)


# anchor: 0 — центр, 1 — верх по центру, 2 — низ по центру.
func _draw_text(text: String, at: Vector2, color: Color, anchor: int) -> void:
	var font := get_theme_default_font()
	var text_size := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE)
	var ascent := font.get_ascent(FONT_SIZE)
	var descent := font.get_descent(FONT_SIZE)
	var baseline := at.y - descent
	if anchor == 0:
		baseline = at.y - (ascent + descent) / 2.0 + ascent
	elif anchor == 1:
		baseline = at.y + ascent
	draw_string(font, Vector2(at.x - text_size.x / 2.0, baseline), text, HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE, color)


func _draw_closed_outline(points: PackedVector2Array, color: Color, width: float) -> void:
	var closed := points.duplicate()
	closed.append(points[0])
	draw_polyline(closed, color, width, true)


func _texture(asset_dir: String, file_name: String) -> Texture2D:
	return _texture_at(asset_path(asset_dir, file_name))


static func _texture_at(path: String) -> Texture2D:
	if not _textures.has(path):
		var texture: Texture2D = null
		if FileAccess.file_exists(path):
			var image := Image.load_from_file(path)
			if image != null and not image.is_empty():
				texture = ImageTexture.create_from_image(image)
		_textures[path] = texture
	return _textures[path]


static func _ellipse(center: Vector2, radius_x: float, radius_y: float) -> PackedVector2Array:
	var points := PackedVector2Array()
	for step in range(20):
		var angle := TAU * step / 20.0
		points.append(center + Vector2(cos(angle) * radius_x, sin(angle) * radius_y))
	return points


static func _rng(seed_value: int) -> RandomNumberGenerator:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	return rng
