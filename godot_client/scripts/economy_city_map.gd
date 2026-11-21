extends "res://scripts/economy_map_canvas.gd"
# Карта Радбурга поверх общего холста. Порядок слоёв как в city_scene.py draw(): фон, здания, дома,
# стены и ворота, игрок. Население и состояние здания показываются только подсказкой и бейджем замка;
# список во вкладках Экономики остаётся источником данных.

signal building_clicked(window_key: String)
signal gate_clicked(gate: Dictionary)
signal profile_requested
signal crystal_rest_requested

const RULES := preload("res://scripts/economy_city_layout_rules.gd")
const GATE_RULES := preload("res://scripts/economy_gate_rules.gd")
const TOWN_RULES := preload("res://scripts/world_map_town_rules.gd")
const TEXT_ZOOM := 0.3
const PLAYER_RADIUS := 6.0
const BADGE_BACKGROUND := Color(12.0 / 255.0, 16.0 / 255.0, 22.0 / 255.0, 0.88)
const DOOR_COLOR := Color(0.12, 0.08, 0.06)
const PLAYER_COLOR := Color(1.0, 0.84, 0.24)
const LABEL_COLOR := Color(0.92, 0.9, 0.84)
const GATE_HOVER_COLOR := Color(1.0, 0.95, 0.6)
const MAP_BADGE_BACKGROUND := Color8(12, 14, 18, 220)
const MAP_BADGE_TEXT := Color8(240, 240, 240)
const MAP_BADGE_BORDER_DEFAULT := Color8(220, 200, 160)
# Цвет рамки плашки каждого здания без наведения и выбора, как badge_col в scenes/city/rendering.py.
const MAP_BADGE_BORDERS := {
	"crystal_of_life": Color8(160, 230, 255),
	"main_castle": Color8(220, 200, 160),
	"tavern_building": Color8(230, 190, 140),
	"barn_building": Color8(225, 185, 130),
	"warehouse_building": Color8(190, 210, 235),
	"forge_building": Color8(235, 175, 120),
	"workshop_building": Color8(180, 215, 245),
	"barracks_building": Color8(180, 215, 245),
	"engineering_building": Color8(160, 215, 205),
	"university_building": Color8(180, 215, 245),
	"military_academy": Color8(230, 170, 150),
	"mage_school_building": Color8(205, 165, 240),
	"stable_building": Color8(211, 184, 140),
}
const PROFILE_RULES := preload("res://scripts/character_profile_rules.gd")
const WALK_RULES := preload("res://scripts/economy_city_walk_rules.gd")
const SPRITE_RULES := preload("res://scripts/economy_player_sprite_rules.gd")
const DECK_SPRITE := preload("res://scripts/deck_player_sprite_rules.gd")
const PLAYER_VIEW := preload("res://scripts/economy_city_player_sprite.gd")
const PRESENCE_RULES := preload("res://scripts/deck_presence_rules.gd")
const PROFESSION_ICON := preload("res://scripts/tower_hud_view.gd")
const CITY_LOCATION := "city"
const AFK_TINT := Color8(135, 139, 145)
const AFK_HEAD_COLOR := Color8(145, 149, 153)
const AFK_BODY_COLOR := Color8(100, 105, 112)
const AFK_NAME_COLOR := Color8(153, 157, 163)
const AFK_LABEL_FILL := Color8(20, 22, 26)
const AFK_LABEL_BORDER := Color8(105, 109, 115)
const AFK_LABEL_SIZE := 11
const PLAYER_PICK_OFFSET := Vector2(22.0, 58.0)
const PLAYER_PICK_SIZE := Vector2(44.0, 62.0)
const HUD_TEXT_COLOR := Color8(255, 200, 90)
const HUD_PANEL_COLOR := Color8(15, 18, 24, 215)
const HUD_BORDER_COLOR := Color8(220, 180, 70)
const PALISADE_DARK := Color8(74, 45, 27)
const PALISADE_LIGHT := Color8(153, 101, 54)
const PALISADE_POST := Color8(61, 38, 24)
const PALISADE_CAP := Color8(187, 130, 69)
const CONSTRUCTION_DARK := Color8(77, 48, 30)
const CONSTRUCTION_LIGHT := Color8(151, 97, 51)
const STONE_WALL_COLOR := Color8(120, 128, 128)
const STONE_WALL_DARK := Color8(60, 66, 67)

var _city: Dictionary = {}
var _building: Dictionary = {}
var _textures: Dictionary = {}
var _catalog_text := ""
var _assets_root := ""
var _hover_gate_id := ""
var _player: Vector2 = RULES.PLAYER_SPAWN_PX
var _direction: String = RULES.SPAWN_DIRECTION
var _path: Array = []
var _moving := false
var _walk_paused := false
var _follow_player := true
var _anim_time := 0.0
var _player_layer: PlayerLayer
var _sprite_root := ""
var _sprite_sets: Dictionary = {}
var _sprites_loaded := false
var _afk_players: Array = []
var _solids: Array[Rect2i] = []
var _solid_houses := -1
# Открыто ли окно здания; задаёт экономический мир, чтобы дверь не открывала окно повторно.
var window_is_open: Callable
var _gate_under_player := ""
var _hud_refresh := 0.0
var _active_entity: Dictionary = {}
var _active_notice := ""
var _active_notice_left := 0.0


func _ready() -> void:
	set_map(RULES.GRID_TILES, RULES.TILE_PX)
	_assets_root = RULES.map_assets_root(ProjectSettings.globalize_path("res://"))
	_catalog_text = FileAccess.get_file_as_string(_assets_root.path_join(RULES.CATALOG_DIR).path_join(RULES.CATALOG_FILE))
	world_clicked.connect(_on_world_clicked)
	mouse_exited.connect(_on_mouse_exited)
	_sprite_root = SPRITE_RULES.assets_root(ProjectSettings.globalize_path("res://"))
	_player_layer = PlayerLayer.new()
	_player_layer.city_map = self
	add_child(_player_layer)



# Данные из вкладок Экономики: city — ответ населения, building — последнее состояние здания.
func set_city_state(city: Dictionary, building: Dictionary) -> void:
	_city = city
	_building = building
	queue_redraw()


func _tile_color(tile: Vector2i) -> Color:
	return RULES.ground_color(tile)


func _draw_content() -> void:
	for building in RULES.BUILDINGS:
		_draw_building(building)
	_draw_houses()
	_draw_walls()
	_draw_city_upgrade_construction()
	_draw_gates()
	_draw_badges()
	_draw_active_object_window()
	_draw_city_hud()


func _draw_building(building: Dictionary) -> void:
	var footprint := RULES.building_world_rect(building)
	match str(building["style"]):
		"crystal":
			_draw_crystal(footprint, building)
		"castle":
			_draw_castle(footprint, building)
		_:
			var texture := _sprite_texture(str(building["sprite"]))
			if texture != null:
				_draw_sprite(texture, footprint)
			else:
				_draw_block(footprint, building)


func _draw_sprite(texture: Texture2D, footprint: Rect2) -> void:
	var texture_size := texture.get_size()
	var fit := minf(footprint.size.x / texture_size.x, footprint.size.y / texture_size.y)
	var draw_size := texture_size * fit
	var top_left := Vector2(footprint.position.x + (footprint.size.x - draw_size.x) * 0.5, footprint.end.y - draw_size.y)
	draw_texture_rect(texture, Rect2(world_to_screen(top_left), draw_size * zoom), false)


func _draw_block(footprint: Rect2, building: Dictionary) -> void:
	var fill := RULES.rgb(building["fill"])
	var trim := RULES.rgb(building["trim"])
	var screen := _world_rect_to_screen(footprint)
	draw_rect(screen, fill)
	draw_rect(Rect2(screen.position, Vector2(screen.size.x, screen.size.y * 0.22)), fill.darkened(0.25))
	draw_rect(screen, trim, false, 1.0)
	var entrance: Vector2i = building["entrance"]
	draw_rect(_world_rect_to_screen(Rect2(Vector2(entrance * RULES.TILE_PX), Vector2.ONE * RULES.TILE_PX)), DOOR_COLOR)


func _draw_crystal(footprint: Rect2, building: Dictionary) -> void:
	var trim := RULES.rgb(building["trim"])
	var screen := _world_rect_to_screen(footprint)
	draw_rect(screen, RULES.rgb(building["fill"]))
	draw_rect(screen, trim, false, 1.0)
	var center := screen.get_center()
	draw_circle(center, screen.size.x * 0.33, Color(34.0 / 255.0, 52.0 / 255.0, 68.0 / 255.0))
	draw_arc(center, screen.size.x * 0.32, 0.0, TAU, 24, Color(80.0 / 255.0, 220.0 / 255.0, 1.0), 1.0)
	draw_circle(center, maxf(2.0, screen.size.x * 0.12), Color(80.0 / 255.0, 240.0 / 255.0, 1.0))


func _draw_castle(footprint: Rect2, building: Dictionary) -> void:
	var tile := float(RULES.TILE_PX)
	var fill := RULES.rgb(building["fill"])
	var trim := RULES.rgb(building["trim"])
	draw_rect(_world_rect_to_screen(footprint), fill)
	draw_rect(_world_rect_to_screen(footprint), trim, false, 1.0)
	var corner := Vector2(3.0 * tile, 3.0 * tile)
	var corners := [
		footprint.position,
		Vector2(footprint.end.x - corner.x, footprint.position.y),
		Vector2(footprint.position.x, footprint.end.y - corner.y),
		footprint.end - corner,
	]
	for corner_position: Vector2 in corners:
		var tower := _world_rect_to_screen(Rect2(corner_position, corner))
		draw_rect(tower, RULES.rgb([48, 58, 72]))
		draw_rect(tower, RULES.rgb([90, 115, 145]), false, 1.0)
	var keep_size := Vector2(5.0 * tile, 5.0 * tile)
	var keep := Rect2(footprint.get_center() - keep_size * 0.5, keep_size)
	draw_rect(_world_rect_to_screen(keep), RULES.rgb([42, 52, 66]))
	draw_rect(_world_rect_to_screen(keep), RULES.rgb([120, 145, 180]), false, 1.0)
	var gate := Rect2(Vector2(footprint.get_center().x - 1.5 * tile, footprint.end.y - 1.5 * tile), Vector2(3.0 * tile, 1.5 * tile))
	draw_rect(_world_rect_to_screen(gate), RULES.rgb([20, 24, 32]))
	draw_rect(_world_rect_to_screen(gate), RULES.rgb([220, 180, 80]), false, 1.0)


func _draw_houses() -> void:
	var tile := float(RULES.TILE_PX)
	for index in range(_house_count()):
		var lot: Array = RULES.HOUSE_LOTS[index]
		var origin := Vector2(float(lot[0]) * tile, float(lot[1]) * tile)
		var width := float(lot[2]) * tile
		var depth := float(lot[3]) * tile
		var floors := int(lot[4])
		var floor_height := maxf(15.0, tile / 2.0)
		var body_height := depth + float(floors - 1) * floor_height
		var roof_height := maxf(4.0, floor_height / 2.0)
		var body := Rect2(origin.x + 4.0, origin.y + depth - body_height, width - 8.0, body_height)
		var roof_top := body.position.y - roof_height
		var wall_color := RULES.rgb(RULES.HOUSE_WALLS[index % RULES.HOUSE_WALLS.size()])
		var roof_color := RULES.rgb(RULES.HOUSE_ROOFS[index % RULES.HOUSE_ROOFS.size()])
		draw_rect(_world_rect_to_screen(body), wall_color)
		draw_rect(_world_rect_to_screen(body), Color(61.0 / 255.0, 48.0 / 255.0, 38.0 / 255.0), false, 1.0)
		var roof := PackedVector2Array([
			world_to_screen(Vector2(body.position.x - 5.0, body.position.y + 2.0)),
			world_to_screen(Vector2(body.get_center().x, roof_top)),
			world_to_screen(Vector2(body.end.x + 5.0, body.position.y + 2.0)),
		])
		draw_colored_polygon(roof, roof_color)
		draw_rect(_world_rect_to_screen(Rect2(body.get_center().x - 5.0, body.end.y - 20.0, 10.0, 20.0)), Color(62.0 / 255.0, 41.0 / 255.0, 30.0 / 255.0))


func _draw_walls() -> void:
	var city_upgrade := _city_upgrade_state()
	if int(city_upgrade.get("city_level", 1)) >= 2:
		return
	var stone := Color8(40, 48, 60)
	var stone_dark := Color8(65, 80, 100)
	var merlon_color := Color8(25, 30, 38)
	for wall in RULES.WALL_RECTS:
		var screen := _rect_i_to_screen(wall)
		draw_rect(screen, stone)
		draw_rect(screen, stone_dark, false, 1.0)
		_draw_merlons(screen, merlon_color)
	for tower in RULES.TOWER_RECTS:
		var screen := _rect_i_to_screen(tower)
		draw_rect(screen, stone)
		draw_rect(screen, stone_dark, false, 1.0)
		_draw_merlons(screen, merlon_color)


func _city_upgrade_state() -> Dictionary:
	var value: Variant = _city.get("city_upgrade", {})
	return value if value is Dictionary else {}


func city_wall_plan() -> Dictionary:
	return TOWN_RULES.wall_plan(_city_upgrade_state())


func _draw_city_upgrade_construction() -> void:
	var plan := city_wall_plan()
	match str(plan.get("kind", "level1")):
		"stone":
			for section in RULES.PALISADE_SECTIONS:
				_draw_stone_wall_section(section, "stone")
		"completed":
			for section in RULES.PALISADE_SECTIONS:
				_draw_palisade_section(section, true)
		"upgrade":
			var stages: Array = plan.get("stages", [])
			for index in mini(stages.size(), RULES.PALISADE_SECTIONS.size()):
				_draw_stone_wall_section(RULES.PALISADE_SECTIONS[index], str(stages[index]))
		"level1":
			if bool(plan.get("trench", false)):
				for section in RULES.PALISADE_SECTIONS:
					_draw_trench(section)
				return
			var completed: Array = plan.get("completed", [])
			for index in completed:
				if int(index) >= 0 and int(index) < RULES.PALISADE_SECTIONS.size():
					_draw_palisade_section(RULES.PALISADE_SECTIONS[int(index)], true)
			for index in plan.get("work_sides", []):
				if int(index) >= 0 and int(index) < RULES.PALISADE_SECTIONS.size():
					_draw_palisade_section(RULES.PALISADE_SECTIONS[int(index)], false)


func _draw_stone_wall_section(section: Array, stage: String) -> void:
	if stage == "wood":
		_draw_palisade_section(section, true)
		return
	for segment in section:
		var start: Vector2 = segment[0]
		var finish: Vector2 = segment[1]
		var horizontal := absf(finish.x - start.x) >= absf(finish.y - start.y)
		if stage == "building":
			_draw_palisade_section([[start, finish]], false)
		draw_line(world_to_screen(start), world_to_screen(finish),
			Color8(96, 104, 104) if stage == "building" else STONE_WALL_COLOR,
			8.0 if stage == "building" else 14.0)
		draw_line(world_to_screen(start), world_to_screen(finish), STONE_WALL_DARK, 2.0)
		var length := start.distance_to(finish)
		for distance in range(0, int(length) + 1, 40):
			var point := start.lerp(finish, minf(1.0, float(distance) / maxf(1.0, length)))
			var screen := world_to_screen(point)
			if horizontal:
				draw_rect(Rect2(screen.x - 4.0, screen.y - 16.0, 8.0, 6.0), STONE_WALL_DARK)
			else:
				draw_rect(Rect2(screen.x - 16.0, screen.y - 4.0, 6.0, 8.0), STONE_WALL_DARK)


func _draw_palisade_section(section: Array, complete: bool) -> void:
	for segment in section:
		var start: Vector2 = segment[0]
		var finish: Vector2 = segment[1]
		var horizontal := absf(finish.x - start.x) >= absf(finish.y - start.y)
		var length := start.distance_to(finish)
		if complete:
			var dark_offset := Vector2(0.0, -12.0) if horizontal else Vector2(12.0, 0.0)
			var light_offset := Vector2(0.0, -4.0) if horizontal else Vector2(4.0, 0.0)
			draw_line(world_to_screen(start) + dark_offset, world_to_screen(finish) + dark_offset, PALISADE_DARK, 6.0)
			draw_line(world_to_screen(start) + light_offset, world_to_screen(finish) + light_offset, PALISADE_LIGHT, 4.0)
			for distance in range(0, int(length) + 1, 56):
				var post := world_to_screen(start.lerp(finish, minf(1.0, float(distance) / maxf(1.0, length))))
				var post_rect := Rect2(post.x - 3.0, post.y - 15.0, 7.0, 24.0) if horizontal \
					else Rect2(post.x - 15.0, post.y - 3.0, 24.0, 7.0)
				var cap_rect := Rect2(post.x - 3.0, post.y - 15.0, 7.0, 5.0) if horizontal \
					else Rect2(post.x - 15.0, post.y - 3.0, 5.0, 7.0)
				draw_rect(post_rect, PALISADE_POST)
				draw_rect(cap_rect, PALISADE_CAP)
			continue
		for distance in range(12, int(length), 72):
			var pile := world_to_screen(start.lerp(finish, float(distance) / maxf(1.0, length)))
			if horizontal:
				draw_line(pile + Vector2(-13.0, 4.0), pile + Vector2(13.0, -3.0), CONSTRUCTION_DARK, 5.0)
				draw_line(pile + Vector2(-12.0, -1.0), pile + Vector2(11.0, -8.0), CONSTRUCTION_LIGHT, 4.0)
			else:
				draw_line(pile + Vector2(4.0, -13.0), pile + Vector2(-3.0, 13.0), CONSTRUCTION_DARK, 5.0)
				draw_line(pile + Vector2(-1.0, -12.0), pile + Vector2(-8.0, 11.0), CONSTRUCTION_LIGHT, 4.0)


func _draw_trench(section: Array) -> void:
	for segment in section:
		var start: Vector2 = segment[0]
		var finish: Vector2 = segment[1]
		var length := start.distance_to(finish)
		for distance in range(0, int(length), 88):
			var first := start.lerp(finish, float(distance) / maxf(1.0, length))
			var second := start.lerp(finish, minf(1.0, float(distance + 40) / maxf(1.0, length)))
			var p1 := world_to_screen(first)
			var p2 := world_to_screen(second)
			draw_line(p1, p2, Color8(74, 54, 37), 5.0)
			draw_line(p1, p2, Color8(133, 91, 55), 2.0)


func _draw_city_hud() -> void:
	var upgrade_items: Array = [_city_upgrade_state()]
	var castle_upgrades: Variant = _city.get("castle_upgrades_active", [])
	if castle_upgrades is Array:
		upgrade_items.append_array(castle_upgrades)
	var font := ThemeDB.fallback_font
	var top := 20.0
	for item in upgrade_items:
		if not item is Dictionary or not bool(item.get("active", false)) or item.get("finish_at", null) == null:
			continue
		var seconds_left := maxi(0, ceili(float(item["finish_at"]) - Time.get_unix_time_from_system()))
		var hours := floori(float(seconds_left) / 3600.0)
		var minutes := floori(float(seconds_left % 3600) / 60.0)
		var seconds := seconds_left % 60
		var name := str(item.get("upgrade_name", "Улучшение"))
		var text := "%s · осталось %02d:%02d:%02d" % [name, hours, minutes, seconds]
		var text_size := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 12)
		var box := Rect2(size.x - 20.0 - text_size.x - 16.0, top, text_size.x + 16.0, text_size.y + 8.0)
		draw_rect(box, HUD_PANEL_COLOR)
		draw_rect(box, HUD_BORDER_COLOR, false, 1.0)
		draw_string(font, Vector2(box.position.x + 8.0, box.position.y + 4.0 + font.get_ascent(12)),
			text, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, HUD_TEXT_COLOR)
		top = box.end.y + 6.0

	var mouse_world := screen_to_world(get_local_mouse_position())
	var hero_tile := RULES.tile_of(_player)
	var cursor_tile := RULES.tile_of(mouse_world)
	var coords := "Герой: [%d, %d]  |  Курсор: [%d, %d]" % [
		hero_tile.x, hero_tile.y, cursor_tile.x, cursor_tile.y,
	]
	var coords_size := font.get_string_size(coords, HORIZONTAL_ALIGNMENT_LEFT, -1, 12)
	var coords_bottom := size.y - 20.0
	if not _active_entity.is_empty():
		coords_bottom = _active_window_layout()["window"].position.y - 8.0
	var coords_box := Rect2(size.x - 20.0 - coords_size.x - 16.0, coords_bottom - coords_size.y - 18.0,
		coords_size.x + 16.0, coords_size.y + 8.0)
	draw_rect(coords_box, HUD_PANEL_COLOR)
	draw_rect(coords_box, HUD_BORDER_COLOR, false, 1.0)
	draw_string(font, coords_box.position + Vector2(8.0, 4.0 + font.get_ascent(12)),
		coords, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color8(255, 215, 120))


func _active_window_layout() -> Dictionary:
	var ui_scale := 2.0 / 3.0
	return TOWN_RULES.window_layout(TOWN_RULES.window_rect(size, ui_scale), ui_scale)


func _draw_active_object_window() -> void:
	if _active_entity.is_empty():
		return
	var layout := _active_window_layout()
	var window: Rect2 = layout["window"]
	var font := ThemeDB.fallback_font
	draw_rect(window, Color8(15, 20, 28, 245))
	draw_rect(window, Color8(220, 185, 60), false, 2.0)
	var scale := 2.0 / 3.0
	var title := str(_active_entity.get("name", "Объект"))
	draw_string(font, window.position + Vector2(14.0, 27.0) * scale, title,
		HORIZONTAL_ALIGNMENT_LEFT, window.size.x - 56.0 * scale, roundi(20.0 * scale), Color8(255, 225, 120))
	draw_string(font, window.position + Vector2(14.0, 52.0) * scale, TOWN_RULES.STATUS_TEXT,
		HORIZONTAL_ALIGNMENT_LEFT, -1, roundi(13.0 * scale), Color8(80, 255, 120))
	var close: Rect2 = layout["close"]
	draw_rect(close, Color8(45, 30, 35))
	draw_rect(close, Color8(220, 100, 100), false, 1.0)
	draw_string(font, close.position + Vector2(7.0, 18.0) * scale, "×",
		HORIZONTAL_ALIGNMENT_LEFT, -1, roundi(16.0 * scale), Color.WHITE)
	draw_line(window.position + Vector2(14.0, 62.0) * scale,
		Vector2(window.end.x - 14.0 * scale, window.position.y + 62.0 * scale), Color8(50, 65, 80), 1.0)
	var in_range := _active_entity_in_range()
	var range_text := "● Ваш персонаж" if str(_active_entity.get("id", "")) == "player" else TOWN_RULES.range_text(in_range)
	var range_color := Color8(100, 220, 255) if str(_active_entity.get("id", "")) == "player" \
		else Color8(80, 255, 120) if in_range else Color8(160, 160, 160)
	draw_string(font, window.position + Vector2(14.0, 82.0) * scale, range_text,
		HORIZONTAL_ALIGNMENT_LEFT, window.size.x - 28.0 * scale, roundi(11.0 * scale), range_color)
	var description := str(_active_entity.get("desc", ""))
	var description_lines: Array = TOWN_RULES.description_lines(description)
	for index in description_lines.size():
		draw_string(font, window.position + Vector2(14.0, (101.0 + index * 14.0) * scale),
			str(description_lines[index]), HORIZONTAL_ALIGNMENT_LEFT,
			window.size.x - 28.0 * scale, roundi(11.0 * scale), Color8(210, 215, 220))
	if not _active_notice.is_empty():
		draw_string(font, layout["action"].position + Vector2(8.0, 20.0) * scale, _active_notice,
			HORIZONTAL_ALIGNMENT_CENTER, layout["action"].size.x - 16.0 * scale, roundi(11.0 * scale), Color8(255, 120, 100))
		return
	var action: Rect2 = layout["action"]
	var action_label := "ИНФОРМАЦИЯ" if str(_active_entity.get("id", "")) == "player" else "ПРИКОСНУТЬСЯ К КРИСТАЛЛУ"
	var action_color := Color8(45, 80, 130) if in_range or str(_active_entity.get("id", "")) == "player" else Color8(55, 55, 60)
	draw_rect(action, action_color)
	draw_rect(action, Color8(220, 180, 70), false, 1.0)
	draw_string(font, action.position + Vector2(4.0, 22.0) * scale, action_label,
		HORIZONTAL_ALIGNMENT_CENTER, action.size.x - 8.0 * scale, roundi(11.0 * scale), Color.WHITE)


func _active_entity_in_range() -> bool:
	var entity_id := str(_active_entity.get("id", ""))
	if entity_id == "player":
		return true
	var building := RULES.building_by_id(entity_id)
	if building.is_empty():
		return false
	var bounds: Rect2i = building["rect"]
	var tile := RULES.tile_of(_player)
	var dx := 0 if tile.x >= bounds.position.x and tile.x < bounds.end.x else \
		bounds.position.x - tile.x if tile.x < bounds.position.x else tile.x - bounds.end.x + 1
	var dy := 0 if tile.y >= bounds.position.y and tile.y < bounds.end.y else \
		bounds.position.y - tile.y if tile.y < bounds.position.y else tile.y - bounds.end.y + 1
	return maxi(dx, dy) <= 1


func set_active_notice(notice: String) -> void:
	_active_notice = notice
	_active_notice_left = 2.5
	queue_redraw()


# Зубцы вдоль длинной стороны прямоугольника (для башен — по верхнему краю).
func _draw_merlons(screen: Rect2, color: Color) -> void:
	var along_x := screen.size.x >= screen.size.y
	var length := screen.size.x if along_x else screen.size.y
	var thickness := screen.size.y if along_x else screen.size.x
	var step := maxf(3.0, thickness * 0.5)
	var cap := maxf(1.0, thickness * 0.2)
	var offset := 0.0
	while offset + step * 0.5 <= length:
		if along_x:
			draw_rect(Rect2(screen.position.x + offset, screen.position.y - cap, step * 0.5, cap), color)
		else:
			draw_rect(Rect2(screen.position.x - cap, screen.position.y + offset, cap, step * 0.5), color)
		offset += step


func _draw_gates() -> void:
	for gate in RULES.GATES:
		var screen := _world_rect_to_screen(RULES.gate_world_rect(gate))
		draw_rect(screen, RULES.rgb(RULES.GATE_FILL))
		if str(gate["id"]) == _hover_gate_id:
			draw_rect(screen, Color(GATE_HOVER_COLOR.r, GATE_HOVER_COLOR.g, GATE_HOVER_COLOR.b, 0.25))
			draw_rect(screen, GATE_HOVER_COLOR, false, 3.0)
		else:
			draw_rect(screen, RULES.rgb(gate["border"]), false, 1.0)



# Герой рисуется на слое поверх карты: слой перерисовывается каждый кадр, тайлы — только при смене камеры или данных.
func _draw_player(canvas: Control) -> void:
	var feet := world_to_screen(_player)
	var frame := _player_frame()
	PLAYER_VIEW.draw_shadow(canvas, feet, zoom)
	if frame == null:
		_draw_player_marker(canvas, feet)
	else:
		PLAYER_VIEW.draw_frame(canvas, feet, zoom, frame)
	PLAYER_VIEW.draw_name(canvas, feet, zoom, GameSession.character)


# Игроки в AFK на карте города, как draw_afk_players в CityScene (ui/afk_presence.py); активных игроков город не рисует.
func set_afk_players(occupants: Array) -> void:
	_afk_players = PRESENCE_RULES.afk_occupants(occupants, CITY_LOCATION)
	queue_redraw()


func afk_player_count() -> int:
	return _afk_players.size()


func _afk_frame(occupant: Dictionary) -> Texture2D:
	return _character_frame(occupant, false, PRESENCE_RULES.direction_of(occupant), 0.0)


func _draw_afk_players(canvas: Control) -> void:
	for occupant in _afk_players:
		var feet := world_to_screen(Vector2(float(occupant["position_x"]), float(occupant["position_y"])))
		var frame := _afk_frame(occupant)
		if frame == null:
			canvas.draw_circle(feet + Vector2(0.0, -28.0 * zoom), 7.0 * zoom, AFK_HEAD_COLOR)
			canvas.draw_rect(Rect2(feet.x - 6.0 * zoom, feet.y - 21.0 * zoom, 12.0 * zoom, 17.0 * zoom), AFK_BODY_COLOR)
			_draw_afk_label(canvas, occupant, Vector2(feet.x, feet.y - 44.0 * zoom))
			continue
		# Спрайт AFK без тени и без сдвига: midbottom в точке ног, как в ветке спрайта draw_afk_players.
		var frame_size := frame.get_size() * zoom
		canvas.draw_texture_rect(frame, Rect2(feet - Vector2(frame_size.x * 0.5, frame_size.y), frame_size), false, AFK_TINT)
		_draw_afk_label(canvas, occupant, Vector2(feet.x, feet.y - frame_size.y))


# Подпись «имя (АФК)» серым с иконкой профессии, как в draw_afk_players.
func _draw_afk_label(canvas: Control, occupant: Dictionary, top_center: Vector2) -> void:
	var font := ThemeDB.fallback_font
	var text := PRESENCE_RULES.afk_label(occupant)
	var width := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, AFK_LABEL_SIZE).x
	var box := Rect2(top_center.x - width * 0.5 - 6.0, top_center.y - AFK_LABEL_SIZE - 10.0, width + 12.0, AFK_LABEL_SIZE + 8.0)
	canvas.draw_rect(box, AFK_LABEL_FILL)
	canvas.draw_rect(box, AFK_LABEL_BORDER, false, 1.0)
	var icon: Texture2D = PROFESSION_ICON.profession_icon(PRESENCE_RULES.class_type(occupant))
	if icon != null:
		canvas.draw_texture_rect(icon, Rect2(box.position.x - 36.0, box.get_center().y - 16.0, 32.0, 32.0), false)
	canvas.draw_string(font, Vector2(top_center.x - width * 0.5, box.position.y + AFK_LABEL_SIZE + 1.0), text, HORIZONTAL_ALIGNMENT_LEFT, -1, AFK_LABEL_SIZE, AFK_NAME_COLOR)


func _player_frame() -> Texture2D:
	return _character_frame(GameSession.character, _moving, _direction, _anim_time)


# Кадр персонажа как player_frame в Python: воин — кадры воина, остальные — стойка и бег 2Idle/3run; null, если кадров нет.
func _character_frame(character: Dictionary, moving: bool, direction: String, anim_time: float) -> Texture2D:
	if SPRITE_RULES.is_warrior(character):
		return SPRITE_RULES.frame_for(SPRITE_RULES.warrior_frame_sets(_sprite_root), moving, direction, anim_time)
	if not _sprites_loaded:
		_sprite_sets = SPRITE_RULES.frame_sets(_sprite_root)
		_sprites_loaded = true
	return SPRITE_RULES.frame_for(_sprite_sets, moving, direction, anim_time)


# Запасной рендер без кадров (спрайты не загрузились): маркер, при ходьбе — кольцо. Подпись — плашка ника.
func _draw_player_marker(canvas: Control, center: Vector2) -> void:
	canvas.draw_circle(center, PLAYER_RADIUS, PLAYER_COLOR)
	canvas.draw_arc(center, PLAYER_RADIUS + 1.5, 0.0, TAU, 24, Color(0.06, 0.07, 0.1), 1.5)
	if _moving:
		canvas.draw_arc(center, PLAYER_RADIUS + 5.0, 0.0, TAU, 24, PLAYER_COLOR, 1.0)


func _draw_badges() -> void:
	if zoom >= TEXT_ZOOM:
		for building in RULES.BUILDINGS:
			var footprint := RULES.building_world_rect(building)
			var building_id := str(building["id"])
			var top := world_to_screen(Vector2(footprint.get_center().x, footprint.position.y))
			_draw_map_badge(RULES.building_badge_text(building), top + Vector2(0.0, -RULES.badge_gap(building_id)),
				MAP_BADGE_BORDERS.get(building_id, MAP_BADGE_BORDER_DEFAULT))
	if _city.has("population"):
		var castle_rect := RULES.building_world_rect(RULES.building_by_id("main_castle"))
		var text := "Население %d / %d" % [int(_city.get("population", 0)), int(_city.get("population_capacity", 0))]
		_draw_badge(text, world_to_screen(castle_rect.get_center()))


func _draw_badge(text: String, center: Vector2) -> void:
	var font := ThemeDB.fallback_font
	var text_size := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 12)
	var box_size := text_size + Vector2(12.0, 6.0)
	var box := Rect2(center - box_size * 0.5, box_size)
	draw_rect(box, BADGE_BACKGROUND)
	draw_rect(box, PLAYER_COLOR, false, 1.0)
	draw_string(font, box.position + Vector2(6.0, box_size.y - 5.0), text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 12, LABEL_COLOR)


# Плашка подписи здания, как draw_map_badge в Python: текст по центру, низ плашки на 2 px ниже bottom_center.
func _draw_map_badge(text: String, bottom_center: Vector2, border: Color) -> void:
	var font := _map_badge_font()
	var text_size := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, RULES.BADGE_FONT_SIZE)
	var box := RULES.badge_rect(text_size, bottom_center)
	draw_rect(box, MAP_BADGE_BACKGROUND)
	draw_rect(box, border, false, 1.0)
	draw_string(font, box.position + Vector2(RULES.BADGE_PAD_X, RULES.BADGE_PAD_Y + font.get_ascent(RULES.BADGE_FONT_SIZE)),
		text, HORIZONTAL_ALIGNMENT_LEFT, -1, RULES.BADGE_FONT_SIZE, MAP_BADGE_TEXT)


var _map_badge_font_cache: Font


# Шрифт плашек в Python — 13 px жирный; жирность задаётся так же, как в tower_hud_view.gd.
func _map_badge_font() -> Font:
	if _map_badge_font_cache == null:
		var bold := FontVariation.new()
		bold.base_font = ThemeDB.fallback_font
		bold.variation_embolden = 0.6
		_map_badge_font_cache = bold
	return _map_badge_font_cache


func _get_tooltip(at_position: Vector2) -> String:
	var gate := _gate_at_screen(at_position)
	if not gate.is_empty():
		return GATE_RULES.tooltip(gate)
	var feet := world_to_screen(_player)
	if Rect2(feet - PLAYER_PICK_OFFSET, PLAYER_PICK_SIZE).has_point(at_position):
		return "Вы здесь · %s" % ("Бежит" if _moving else "В покое")
	var world := screen_to_world(at_position)
	var building := RULES.building_at_world(world)
	if building.is_empty():
		return ""
	return "\n".join(RULES.tooltip_lines(building, _city, _building))


func _gui_input(event: InputEvent) -> void:
	var button := event as InputEventMouseButton
	if button != null and button.pressed:
		if button.button_index == MOUSE_BUTTON_RIGHT:
			order_walk(screen_to_world(button.position))
			accept_event()
			return
		if button.button_index == MOUSE_BUTTON_WHEEL_UP or button.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			_follow_player = false
	var motion := event as InputEventMouseMotion
	if motion != null and motion.relative != Vector2.ZERO and (motion.button_mask & MOUSE_BUTTON_MASK_LEFT) != 0:
		_follow_player = false
	super._gui_input(event)
	if motion != null:
		queue_redraw()
		var hovered := str(_gate_at_screen(motion.position).get("id", ""))
		if hovered != _hover_gate_id:
			_hover_gate_id = hovered
			queue_redraw()


func _on_mouse_exited() -> void:
	if not _hover_gate_id.is_empty():
		_hover_gate_id = ""
		queue_redraw()


func _gate_at_screen(screen: Vector2) -> Dictionary:
	return GATE_RULES.gate_at_world(RULES.GATES, screen_to_world(screen))


func _on_world_clicked(world: Vector2) -> void:
	var screen := world_to_screen(world)
	if not _active_entity.is_empty():
		var layout := _active_window_layout()
		var window: Rect2 = layout["window"]
		if window.has_point(screen):
			if (layout["close"] as Rect2).has_point(screen):
				_active_entity.clear()
				_active_notice = ""
				_active_notice_left = 0.0
				queue_redraw()
			elif (layout["action"] as Rect2).has_point(screen):
				_trigger_active_object_action()
			return
	var gate := GATE_RULES.gate_at_world(RULES.GATES, world)
	if not gate.is_empty():
		gate_clicked.emit(gate)
		return
	if Rect2(world_to_screen(_player) - PLAYER_PICK_OFFSET, PLAYER_PICK_SIZE).has_point(screen):
		var name := str(GameSession.character.get("name", "Герой"))
		_active_entity = {
			"id": "player", "name": name, "desc": "Ваш главный герой. Статус: %s." % ("Бежит" if _moving else "В покое"),
		}
		_active_notice = ""
		_active_notice_left = 0.0
		queue_redraw()
		return
	var building := RULES.building_at_world(world)
	if str(building.get("id", "")) == "crystal_of_life":
		_active_entity = {
			"id": "crystal_of_life", "name": "Кристалл Жизни",
			"desc": "Кристалл Жизни полностью восстанавливает здоровье и ману.",
		}
		_active_notice = ""
		_active_notice_left = 0.0
		queue_redraw()
		return
	if not _active_entity.is_empty():
		_active_entity.clear()
		_active_notice = ""
		_active_notice_left = 0.0
	var key := RULES.window_key_at_world(world)
	if not key.is_empty():
		building_clicked.emit(key)
	queue_redraw()
	# Левая кнопка на пустой земле героя не трогает: путь строит только правая (_gui_input), как в city_scene.py.


func _trigger_active_object_action() -> void:
	if str(_active_entity.get("id", "")) == "player":
		profile_requested.emit()
		return
	if not _active_entity_in_range():
		set_active_notice("Подойдите ближе к Кристаллу Жизни")
		return
	crystal_rest_requested.emit()


# Путь по клеткам без солидных частей зданий, стен и домов (ПКМ в city_scene.py → find_tile_path).
# Пустой путь, если точка недостижима: тогда герой стоит, как в Python.
func order_walk(target: Vector2) -> bool:
	_follow_player = true
	_path = WALK_RULES.find_path(_player, target, _solid_rects())
	_moving = false
	return not _path.is_empty()


# Шаг по пути за кадр: 220 px/с, умноженные на множитель груза (player_speed и update() в city_scene.py).
# После шага, как в update() city_scene.py, проверяются ворота и двери; на паузе (открыто окно) герой стоит.
func step_walk(delta: float) -> bool:
	if _walk_paused:
		_moving = false
		return false
	var moved := false
	if not _path.is_empty():
		var step := RULES.WALK_SPEED_PX * PROFILE_RULES.character_movement_multiplier(GameSession.character) * delta
		var previous := _player
		var result: Dictionary = WALK_RULES.follow_path(_player, _path, step, _solid_rects())
		_player = result["position"]
		moved = bool(result["moved"])
		if not moved:
			_path.clear()
		elif _player != previous:
			_direction = DECK_SPRITE.direction_for(_player - previous)
	_moving = moved and not _path.is_empty()
	_check_gate()
	_check_door()
	return moved


# Ворота под героем: заметка о переходе показывается один раз при входе. Путь не меняется: перехода на карту мира нет.
func _check_gate() -> void:
	var gate := GATE_RULES.gate_at_world(RULES.GATES, _player)
	var gate_id := str(gate.get("id", ""))
	if gate_id == _gate_under_player:
		return
	_gate_under_player = gate_id
	if not gate.is_empty():
		gate_clicked.emit(gate)


# Двери как в update() city_scene.py: герой на тайле двери открывает окно, если оно не открыто, и выталкивается
# к точке у двери. Путь не сбрасывается, как move_path в Python; пока окно открыто, дверь не срабатывает.
func _check_door() -> void:
	var door := RULES.door_at_tile(RULES.tile_of(_player))
	if door.is_empty():
		return
	var window := str(door["window"])
	if _is_window_open(window):
		return
	building_clicked.emit(window)
	_player = RULES.tile_center(door["push"])
	_moving = false


func _is_window_open(window_key: String) -> bool:
	return window_is_open.is_valid() and bool(window_is_open.call(window_key))


# Пока открыто окно здания или видна карта путей, герой стоит; путь сохраняется и продолжится после закрытия, как в Python.
func set_walk_paused(paused: bool) -> void:
	_walk_paused = paused
	if paused:
		_moving = false


func is_walking() -> bool:
	return _moving


func player_position() -> Vector2:
	return _player


func walk_path() -> Array:
	return _path.duplicate()


func center_on_player() -> void:
	_follow_player = true
	_update_camera()
	queue_redraw()


func _process(delta: float) -> void:
	_anim_time += delta
	var player_before := _player
	step_walk(delta)
	if _player != player_before:
		queue_redraw()
	if _active_notice_left > 0.0:
		_active_notice_left = maxf(0.0, _active_notice_left - delta)
		if _active_notice_left == 0.0:
			_active_notice = ""
			queue_redraw()
	var camera_before := camera_center
	_update_camera()
	if not camera_center.is_equal_approx(camera_before):
		queue_redraw()
	if _has_active_upgrade():
		_hud_refresh += delta
		if _hud_refresh >= 1.0:
			_hud_refresh = 0.0
			queue_redraw()
	_player_layer.queue_redraw()


func _has_active_upgrade() -> bool:
	if bool(_city_upgrade_state().get("active", false)):
		return true
	var upgrades: Variant = _city.get("castle_upgrades_active", [])
	if upgrades is Array:
		for item in upgrades:
			if item is Dictionary and bool(item.get("active", false)) and item.get("finish_at", null) != null:
				return true
	return false


# Камера: вся карта видна — стоит по центру; иначе следует за героем, пока игрок не тянет карту или не крутит колесо.
func _update_camera() -> void:
	if not _follow_player:
		return
	camera_center = map_size_px() * 0.5 if _whole_map_visible() else _player
	_clamp_camera()


func _whole_map_visible() -> bool:
	if size.x <= 0.0 or size.y <= 0.0:
		return false
	var shown := map_size_px() * zoom
	return shown.x <= size.x + 0.5 and shown.y <= size.y + 0.5


# Солидные прямоугольники кэшируются до смены числа домов.
func _solid_rects() -> Array[Rect2i]:
	var houses := _house_count()
	if houses != _solid_houses:
		_solids = RULES.solid_rects(houses)
		_solid_houses = houses
	return _solids


# Рисуются и становятся солидными первые population участков домов (_draw_citizen_houses, _citizen_house_solid_rects).
func _house_count() -> int:
	return clampi(int(_city.get("population", RULES.DEFAULT_HOUSE_COUNT)), 0, RULES.HOUSE_LOTS.size())


# Слой героя поверх карты: без приёма мыши, рисует героя через city_map._draw_player.
class PlayerLayer extends Control:
	var city_map

	func _init() -> void:
		set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		city_map._draw_player(self)
		city_map._draw_afk_players(self)



func _world_rect_to_screen(world_rect: Rect2) -> Rect2:
	return Rect2(world_to_screen(world_rect.position), world_rect.size * zoom)


func _rect_i_to_screen(world_rect: Rect2i) -> Rect2:
	return _world_rect_to_screen(Rect2(Vector2(world_rect.position), Vector2(world_rect.size)))


func _sprite_texture(sprite_key: String) -> Texture2D:
	if sprite_key.is_empty() or _catalog_text.is_empty():
		return null
	if not _textures.has(sprite_key):
		var asset := RULES.catalog_asset(_catalog_text, sprite_key)
		var image: Image = null
		if not asset.is_empty():
			image = Image.load_from_file(_assets_root.path_join(asset))
		_textures[sprite_key] = ImageTexture.create_from_image(image) if image != null and not image.is_empty() else null
	return _textures[sprite_key]
