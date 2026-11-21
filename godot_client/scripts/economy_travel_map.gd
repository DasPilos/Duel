extends "res://scripts/economy_map_canvas.gd"
# Карта путей мира: дороги из /api/map/terrain, горожане и повозки в мировых пикселях (тайл 32 px).
# Это не сетка Радбурга: в Python фигуры рисуются на карте мира (scenes/world_map_scene.py:2546), а не в городе.

const RULES := preload("res://scripts/economy_travel_rules.gd")
const CITIZEN_RULES := preload("res://scripts/economy_citizen_sprite_rules.gd")
const DECK_SPRITE := preload("res://scripts/deck_player_sprite_rules.gd")
const ROAD_COLOR := Color(0.62, 0.5, 0.33, 0.9)
const GATE_COLOR := Color(1.0, 0.84, 0.24)
const LABEL_COLOR := Color(0.93, 0.84, 0.64)
const LABEL_SIZE := 11
const LABEL_LIFT := 30.0
const WORLD_BACKGROUND := Color(0.12, 0.2, 0.13)
const CART_SIZE := 22.0
const SPRITE_SPACING := 10.0
const CITIZEN_SHADOW := Color(13.0 / 255.0, 15.0 / 255.0, 17.0 / 255.0)
const CITIZEN_HEAD := Color(217.0 / 255.0, 188.0 / 255.0, 151.0 / 255.0)
const CITIZEN_BODY := Color(112.0 / 255.0, 133.0 / 255.0, 103.0 / 255.0)
# Выбор повозки относительно центра, как map_travel.py:180; горожане выбираются по CITIZEN_RULES.CITIZEN_PICK_BOX.
const PICK_BOX := Rect2(-34.0, -48.0, 68.0, 64.0)

var _routes: Array = []
var _citizens: Array = []
var _convoys: Array = []
var _entries: Array = []
var _citizen_entries: Array = []
var _citizen_frames: Dictionary = {}
var _citizen_frames_loaded := false
var _textures: Dictionary = {}
var _assets_root := ""
var _fitted := false
var _convoys_received_msec := 0


func _ready() -> void:
	draw_tiles = false
	background_color = WORLD_BACKGROUND
	set_map(RULES.WORLD_TILES, RULES.TILE_PX)
	_assets_root = RULES.assets_root(ProjectSettings.globalize_path("res://"))


func has_routes() -> bool:
	return not _routes.is_empty()


func entries() -> Array:
	return _entries


func set_routes(routes: Array) -> void:
	_routes = routes
	_rebuild()
	if not _fitted and not _routes.is_empty():
		_fitted = true
		fit_map()


func set_citizens(citizens: Array) -> void:
	_citizens = citizens
	_rebuild()


func set_convoys(convoys: Array) -> void:
	_convoys = convoys
	_convoys_received_msec = Time.get_ticks_msec()
	_rebuild()


# Вмещает маршруты и фигуры; до загрузки маршрутов — всю карту мира.
func fit_map() -> void:
	fit_world_rect(RULES.content_bounds(_routes, _entries))


func entry_at_screen(screen: Vector2) -> Dictionary:
	for entry in _entries:
		var is_wagon := str(entry.get("entity_kind", "")) == "wagon"
		var center := world_to_screen(RULES.display_position(entry))
		var box := PICK_BOX
		if not is_wagon:
			center = citizen_feet(entry)
			box = CITIZEN_RULES.CITIZEN_PICK_BOX
		if Rect2(center + box.position, box.size).has_point(screen):
			return entry
	return {}


func _rebuild() -> void:
	_citizen_entries = RULES.citizen_entries(_citizens)
	_refresh_entries()


# Повозки движутся между ответами сервера: ETA пересчитывается каждый кадр, как traveling_entities (map_travel.py:103).
# Раздвижка повозок выполняется там же, в конце traveling_entities (map_travel.py:124).
func _refresh_entries() -> void:
	var elapsed := maxf(0.0, float(Time.get_ticks_msec() - _convoys_received_msec) / 1000.0)
	_entries = _citizen_entries.duplicate()
	_entries.append_array(RULES.convoy_entries(_convoys, _routes, elapsed))
	RULES.separate_nearby_convoys(_entries, tile_px)
	queue_redraw()


# Горожане анимированы по времени, поэтому карта перерисовывается каждый кадр, пока видна и есть горожане или повозки.
func _process(_delta: float) -> void:
	if not is_visible_in_tree():
		return
	if not _convoys.is_empty():
		_refresh_entries()
	elif not _citizen_entries.is_empty():
		queue_redraw()


func _get_tooltip(at_position: Vector2) -> String:
	var entry := entry_at_screen(at_position)
	if entry.is_empty():
		return ""
	return "\n".join(RULES.tooltip_lines(entry))


func _draw_content() -> void:
	for route in _routes:
		if route is Dictionary:
			_draw_route(route)
	for entry in _entries:
		if str(entry.get("entity_kind", "")) == "wagon":
			_draw_wagon(entry)
		else:
			_draw_citizen(entry)


func _draw_route(route: Dictionary) -> void:
	var tiles: Array = route.get("tiles", [])
	var world_points := RULES.route_points(tiles)
	if world_points.size() < 2:
		return
	var points := PackedVector2Array()
	for point in world_points:
		points.append(world_to_screen(point))
	draw_polyline(points, ROAD_COLOR, 3.0)
	draw_rect(Rect2(points[0] - Vector2(5.0, 5.0), Vector2(10.0, 10.0)), GATE_COLOR)
	draw_string(ThemeDB.fallback_font, points[-1] + Vector2(8.0, -8.0), str(route.get("name", "Маршрут")),
		HORIZONTAL_ALIGNMENT_LEFT, -1, 12, LABEL_COLOR)


func _draw_wagon(entry: Dictionary) -> void:
	var center := world_to_screen(RULES.display_position(entry))
	var direction := str(entry.get("position_direction", "s"))
	var vector: Vector2 = RULES.DIRECTION_VECTORS.get(direction, Vector2(0.0, 1.0))
	var sprite_key := str(entry.get("cart_sprite_key", ""))
	var names := RULES.sprite_names(sprite_key)
	var wagon_center := center - vector * SPRITE_SPACING
	var horse_center := center + vector * SPRITE_SPACING
	_draw_sprite(str(names["wagon"]), CART_SIZE, wagon_center, vector)
	_draw_sprite(str(names["harness"]), CART_SIZE, center, vector)
	_draw_sprite(str(names["horse"]), CART_SIZE, horse_center, vector)
	_draw_sprite(str(names["driver"]), maxf(10.0, floorf(CART_SIZE / 2.0)), wagon_center, vector)
	var label_text := str(entry.get("cart_name", "Повозка"))
	var label := _label_rect(label_text, center)
	var icon := _cart_icon_texture(sprite_key)
	if icon != null:
		draw_texture_rect(icon, RULES.cart_icon_rect(label), false)
	_draw_label(label_text, label)


# Горожанин: кадр бега по position_direction, ноги в точке экрана (map_travel.py:269-272); без кадров — фигурка (273-276);
# подпись и иконка слева от неё — 280-296.
func _draw_citizen(entry: Dictionary) -> void:
	var feet := citizen_feet(entry)
	var direction := str(entry.get("position_direction", "s"))
	var frame := CITIZEN_RULES.frame_for(citizen_frames(), direction, Time.get_ticks_msec() / 1000.0)
	if frame != null:
		draw_texture_rect(frame, DECK_SPRITE.player_frame_rect(feet, Vector2i(frame.get_size())), false)
	else:
		_draw_citizen_figure(feet)
	var label_text := str(entry.get("name", "Горожанин"))
	var label := _label_rect(label_text, feet)
	_draw_citizen_icon(CITIZEN_RULES.icon_origin(label))
	_draw_label(label_text, label)


func _draw_citizen_figure(feet: Vector2) -> void:
	var figure := CITIZEN_RULES.figure_geometry(feet)
	draw_colored_polygon(CITIZEN_RULES.ellipse_points(figure["shadow"]), CITIZEN_SHADOW)
	draw_circle(figure["head"], figure["head_radius"], CITIZEN_HEAD)
	draw_colored_polygon(CITIZEN_RULES.rounded_rect_points(figure["body"], figure["body_radius"]), CITIZEN_BODY)


# Ноги горожанина в целых пикселях экрана: world_to_screen отдаёт int() (world_map_scene.py:1222-1223).
func citizen_feet(entry: Dictionary) -> Vector2:
	var point := world_to_screen(Vector2(float(entry["position_x"]), float(entry["position_y"])))
	return Vector2(float(int(point.x)), float(int(point.y)))


# Кадры горожан по направлениям; грузятся при первом показе, PNG декодируются один раз (кэш — deck_player_sprite_rules.gd).
func citizen_frames() -> Dictionary:
	if not _citizen_frames_loaded:
		_citizen_frames = CITIZEN_RULES.frames_by_direction(_assets_root)
		_citizen_frames_loaded = true
	return _citizen_frames


# Подпись центрируется над точкой, как midbottom=(sx, sy-28) в map_travel.py:280. Godot при width=-1 выравнивает по левому
# краю, поэтому левый край берётся из ширины текста; прямоугольник по метрикам шрифта нужен иконке горожанина.
func _label_rect(label_text: String, anchor: Vector2) -> Rect2:
	var font := ThemeDB.fallback_font
	var width := font.get_string_size(label_text, HORIZONTAL_ALIGNMENT_LEFT, -1, LABEL_SIZE).x
	return Rect2(anchor.x - width * 0.5, anchor.y - LABEL_LIFT - font.get_ascent(LABEL_SIZE), width, font.get_height(LABEL_SIZE))


func _draw_label(label_text: String, box: Rect2) -> void:
	var font := ThemeDB.fallback_font
	draw_string(font, box.position + Vector2(0.0, font.get_ascent(LABEL_SIZE)), label_text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, LABEL_SIZE, LABEL_COLOR)


# Иконка горожанина слева от подписи (map_travel.py:280-296); рисуется до подписи, как в Python.
func _draw_citizen_icon(origin: Vector2) -> void:
	var icon := CITIZEN_RULES.icon_geometry(origin)
	draw_circle(icon["head"], icon["head_outline_radius"], CITIZEN_RULES.ICON_OUTLINE)
	draw_circle(icon["head"], icon["head_radius"], CITIZEN_RULES.ICON_BODY)
	draw_colored_polygon(CITIZEN_RULES.rounded_rect_points(icon["body_outline"], icon["body_outline_radius"]), CITIZEN_RULES.ICON_OUTLINE)
	draw_colored_polygon(CITIZEN_RULES.rounded_rect_points(icon["body"], icon["body_radius"]), CITIZEN_RULES.ICON_BODY)


# Спрайт поворачивается по направлению движения; размер — в пикселях экрана, как в Python.
func _draw_sprite(sprite_name: String, size_px: float, center: Vector2, vector: Vector2) -> void:
	var texture := _texture(sprite_name)
	if texture == null:
		return
	draw_set_transform(center, RULES.rotation_for(vector), Vector2.ONE)
	draw_texture_rect(texture, Rect2(Vector2(-size_px, -size_px) * 0.5, Vector2(size_px, size_px)), false)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)


func _texture(sprite_name: String) -> Texture2D:
	if not _textures.has(sprite_name):
		var path := RULES.transport_sprite_path(_assets_root, sprite_name)
		var image: Image = Image.load_from_file(path) if FileAccess.file_exists(path) else null
		_textures[sprite_name] = ImageTexture.create_from_image(image) if image != null and not image.is_empty() else null
	return _textures[sprite_name]


# Иконка повозки у подписи; без ключа или картинки её нет, подпись остаётся на месте (map_travel.py:280-296).
func _cart_icon_texture(sprite_key: String) -> Texture2D:
	var sprite_name := RULES.cart_icon_name(sprite_key)
	return _texture(sprite_name) if not sprite_name.is_empty() else null
