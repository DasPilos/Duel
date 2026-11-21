extends RefCounted

# Правила карты мира Deck: окно вокруг игрока, границы зон, цвета тайлов и подписи маркеров.
# Чистые функции без сцены: рисует deck_world_map_renderer.gd, ходьбу и проверки решает deck_world.gd.

const NO_TILE := Vector2i(-100000, -100000)
const VOID_COLOR := Color(20 / 255.0, 24 / 255.0, 28 / 255.0)
# Границы зон: те же прямоугольники, что проверяют _is_*_tile в deck_world.gd (deck/map_config.py).
const TAVERN_BOUNDS := Rect2i(4, 26, 5, 3)
const GUILD_BOUNDS := Rect2i(19, 26, 5, 3)
const SUPPLIES_BOUNDS := Rect2i(14, 26, 5, 3)
const LIBRARY_BOUNDS := Rect2i(19, 40, 5, 3)
const TALENT_BOUNDS := Rect2i(22, 37, 2, 2)
const CRYSTAL_ID := "crystal_of_life"
const FORESTER_ID := "lumber_camp"
# Камера догоняет фигурку долей min(1, 8 · dt), как camera_x += (player_x - camera_x) * min(1.0, 8.0 * dt) в Python.
const CAMERA_FOLLOW_SPEED := 8.0
# Перетаскивание карты начинается, когда мышь ушла от точки нажатия дальше чем на 4 px (как в world_map_scene.py).
const DRAG_THRESHOLD_PX := 4.0
# Скролл клавишами: 850 px в секунду, с Shift в 2.2 раза быстрее, как в world_map_scene.py.
const KEY_SCROLL_SPEED_PX := 850.0
const KEY_SCROLL_SHIFT_FACTOR := 2.2

# Земля, город и дороги как в deck/scenes/world_map_scene.py draw(): трава на севере, пустошь на юге.
const GRASS_COLORS := [Color(28 / 255.0, 42 / 255.0, 32 / 255.0), Color(31 / 255.0, 46 / 255.0, 35 / 255.0)]
const ROCK_COLORS := [Color(36 / 255.0, 32 / 255.0, 34 / 255.0), Color(40 / 255.0, 35 / 255.0, 38 / 255.0)]
const PAVING_COLORS := [Color(108 / 255.0, 108 / 255.0, 112 / 255.0), Color(116 / 255.0, 116 / 255.0, 120 / 255.0)]
const ROAD_COLORS := [Color(120 / 255.0, 96 / 255.0, 60 / 255.0), Color(128 / 255.0, 103 / 255.0, 65 / 255.0)]
const ROAD_EDGE_COLOR := Color(95 / 255.0, 74 / 255.0, 44 / 255.0)
const WALL_COLOR := Color(66 / 255.0, 66 / 255.0, 72 / 255.0)
const WALL_EDGE_COLOR := Color(28 / 255.0, 28 / 255.0, 32 / 255.0)
# Опубликованная карта: земля и наборы тайлов в цветах редактора (map_editor_minimap_rules.gd, CATEGORY_RGB).
const PUBLISHED_GROUND_COLORS := [Color(88 / 255.0, 132 / 255.0, 64 / 255.0), Color(94 / 255.0, 138 / 255.0, 69 / 255.0)]
const TILE_COLORS := {
	"floor": Color(104 / 255.0, 146 / 255.0, 76 / 255.0),
	"berry": Color(120 / 255.0, 150 / 255.0, 70 / 255.0),
	"water": Color(56 / 255.0, 104 / 255.0, 168 / 255.0),
	"impassable": Color(84 / 255.0, 84 / 255.0, 90 / 255.0),
	"mountain": Color(122 / 255.0, 122 / 255.0, 128 / 255.0),
	"dry": Color(34 / 255.0, 84 / 255.0, 46 / 255.0),
	"forest": Color(28 / 255.0, 76 / 255.0, 40 / 255.0),
	"stump": Color(92 / 255.0, 70 / 255.0, 48 / 255.0),
	"log": Color(100 / 255.0, 76 / 255.0, 52 / 255.0),
	"bridge": Color(142 / 255.0, 98 / 255.0, 58 / 255.0),
	"obstacle": Color(96 / 255.0, 92 / 255.0, 88 / 255.0),
}
const TILE_SET_ORDER := ["floor", "berry", "paths", "water", "impassable", "mountain", "dry", "forest"]

# Маркеры-кнопки: цвета подписей из deck/scenes/world_map_scene.py (_draw_*_label и _draw_badge).
const ZONE_ORDER := ["tavern", "guild", "supplies", "library", "talent"]
const ZONE_MARKERS := {
	"tavern": {"symbol": "T", "color": Color(225 / 255.0, 170 / 255.0, 110 / 255.0), "alpha": 0.6},
	"guild": {"symbol": "G", "color": Color(235 / 255.0, 200 / 255.0, 70 / 255.0), "alpha": 0.6},
	"supplies": {"symbol": "S", "color": Color(105 / 255.0, 185 / 255.0, 245 / 255.0), "alpha": 0.6},
	"library": {"symbol": "L", "color": Color(150 / 255.0, 150 / 255.0, 175 / 255.0), "alpha": 0.5},
	"talent": {"symbol": "Д", "color": Color(155 / 255.0, 210 / 255.0, 125 / 255.0), "alpha": 0.5},
}
const DUNGEON_MARKER := {
	"symbol": "D",
	"color": Color(20 / 255.0, 20 / 255.0, 24 / 255.0),
	"border": Color(104 / 255.0, 105 / 255.0, 112 / 255.0),
	"alpha": 1.0,
	"tooltip": "Вход в подземелье: стойте на нём 5 секунд",
}
const ARENA_COLORS := {
	"K": Color(220 / 255.0, 90 / 255.0, 70 / 255.0),
	"E": Color(220 / 255.0, 150 / 255.0, 75 / 255.0),
	"X": Color(190 / 255.0, 185 / 255.0, 160 / 255.0),
	"N": Color(175 / 255.0, 110 / 255.0, 195 / 255.0),
}


# Левый верхний тайл окна: игрок в центре, как MAP_VIEW_SIZE в deck_world.gd.
static func window_origin(center: Vector2i, view_size: int) -> Vector2i:
	return center - Vector2i.ONE * (maxi(view_size, 1) >> 1)


static func tile_rect(tile: Vector2i, origin: Vector2i, cell: float) -> Rect2:
	return Rect2(Vector2(tile - origin) * cell, Vector2.ONE * cell)


# Центр плитки в координатах тайлов: фигурка стоит по центру плитки, как feet в deck_world_sprites.gd.
static func tile_center(tile: Vector2i) -> Vector2:
	return Vector2(tile) + Vector2.ONE * 0.5


# Левый верхний угол окна в дробных тайлах: окно центрировано на center.
static func view_origin(center: Vector2, view_size: int) -> Vector2:
	return center - Vector2.ONE * (maxf(view_size, 1) / 2.0)


# Шаг фигурки к цели не длиннее max_step тайлов; у цели она встаёт точно, без перелёта, как player_target в Python.
static func slide_toward(current: Vector2, target: Vector2, max_step: float) -> Vector2:
	var offset := target - current
	var distance := offset.length()
	var step := maxf(max_step, 0.0)
	if distance <= step:
		return target
	return current + offset * (step / distance)


# Догон камеры за фигуркой: за шаг камера проходит min(1, 8 · dt) разницы, как в Python.
static func follow_camera(camera: Vector2, target: Vector2, delta: float) -> Vector2:
	return camera + (target - camera) * minf(1.0, CAMERA_FOLLOW_SPEED * maxf(delta, 0.0))


# Зажим камеры краями мира, как _clamp_camera в Python: половина окна не выходит за границы карты.
static func clamp_camera(camera: Vector2, world_min: Vector2, world_max: Vector2, view_size: int) -> Vector2:
	var half := Vector2.ONE * (maxf(view_size, 1) / 2.0)
	return Vector2(
		maxf(world_min.x + half.x, minf(world_max.x - half.x, camera.x)),
		maxf(world_min.y + half.y, minf(world_max.y - half.y, camera.y)),
	)


static func drag_passed(offset_px: Vector2) -> bool:
	return absf(offset_px.x) > DRAG_THRESHOLD_PX or absf(offset_px.y) > DRAG_THRESHOLD_PX


# Скролл камеры клавишами в тайлах за кадр: блок «Скролл карты стрелками / WASD» из Python. held — удержанные left, right,
# up, down (стрелка вниз), s (буква S), shift. S не скроллит, пока s_cancels. moved — удержана хоть одна клавиша направления,
# даже если противоположные нажаты вместе: тогда догон выключается, как в Python.
static func key_scroll(held: Dictionary, delta: float, tile_px: float, s_cancels: bool) -> Dictionary:
	var speed := KEY_SCROLL_SPEED_PX * maxf(delta, 0.0) / maxf(tile_px, 1.0)
	if bool(held.get("shift", false)):
		speed *= KEY_SCROLL_SHIFT_FACTOR
	var left := bool(held.get("left", false))
	var right := bool(held.get("right", false))
	var up := bool(held.get("up", false))
	var down := (bool(held.get("s", false)) and not s_cancels) or bool(held.get("down", false))
	# Направление целыми шагами по осям: противоположные клавиши дают ровно ноль.
	var direction := Vector2(_axis(right, left), _axis(down, up))
	return {"offset": direction * speed, "moved": left or right or up or down}


static func _axis(positive: bool, negative: bool) -> float:
	return (1.0 if positive else 0.0) - (1.0 if negative else 0.0)


# Окно данных покрывает все плитки окна камеры: renderer рисует view_size + 1 плитку по каждой оси.
static func covers_view(data: Rect2i, view_center: Vector2, view_size: int) -> bool:
	var origin := view_origin(view_center, view_size)
	var first := Vector2i(floori(origin.x), floori(origin.y))
	var last := first + Vector2i.ONE * view_size
	return first.x >= data.position.x and first.y >= data.position.y and last.x < data.end.x and last.y < data.end.y


# Координаты мира (position_x, position_y) в окне: origin — левый верхний угол окна в дробных тайлах.
static func world_to_view(world: Vector2, origin: Vector2, tile_px: float) -> Vector2:
	var tile := maxf(1.0, tile_px)
	return (world / tile - origin) * tile


# Окно данных — плитки, маркеры и препятствия — для логического тайла и для окна, которое сейчас скользит.
# Запас в одну плитку по краям: край окна не пропадает во время шага.
static func data_window(tile: Vector2i, slide_center: Vector2, view_size: int) -> Rect2i:
	var logical := Rect2i(window_origin(tile, view_size), Vector2i.ONE * view_size)
	var origin := view_origin(slide_center, view_size)
	var visual := Rect2i(Vector2i(int(floor(origin.x)), int(floor(origin.y))), Vector2i.ONE * view_size)
	# Окно фигурки нужно, пока она рядом с окном камеры: далеко ушедшая камера не тянет данные через всю карту.
	if logical.intersects(visual):
		return logical.merge(visual).grow(1)
	return visual.grow(1)


static func in_map(tile: Vector2i, map_size: Vector2i) -> bool:
	return tile.x >= 0 and tile.y >= 0 and tile.x < map_size.x and tile.y < map_size.y


# Четыре соседних тайла: по ним игрок может шагнуть (логика absi(dx) + absi(dy) == 1).
static func is_neighbour(tile: Vector2i, center: Vector2i) -> bool:
	var offset := tile - center
	return absi(offset.x) + absi(offset.y) == 1


static func is_published(terrain: Dictionary) -> bool:
	return terrain.has("published")


static func checker(colors: Array, tile: Vector2i) -> Color:
	return colors[posmod(tile.x + tile.y, 2)]


static func ground_color(published: bool, tile: Vector2i, map_size: Vector2i) -> Color:
	if published:
		return checker(PUBLISHED_GROUND_COLORS, tile)
	return checker(GRASS_COLORS if tile.y < (map_size.y >> 1) else ROCK_COLORS, tile)


static func tile_color(kind: String) -> Color:
	return TILE_COLORS.get(kind, VOID_COLOR)


static func text_color_for(fill: Color) -> Color:
	return Color(0.08, 0.09, 0.1) if fill.get_luminance() > 0.5 else Color(0.94, 0.94, 0.94)


# Маркер клетки по фактам о ней: приоритет тот же, что в старой сетке символов (зоны, стена, подземелье, арена).
# Игрока здесь нет: его фигурку рисует deck_world_sprites.gd поверх маркеров.
# Твёрдые тайлы без зоны маркера не получают: их рисуют как препятствие и кристалл.
static func marker_for(facts: Dictionary) -> Dictionary:
	for zone in ZONE_ORDER:
		if bool(facts.get(zone, false)):
			return _marker(zone, ZONE_MARKERS[zone])
	if bool(facts.get("solid", false)):
		return {}
	if bool(facts.get("dungeon", false)):
		return _marker("dungeon", DUNGEON_MARKER)
	var arena: Variant = facts.get("arena", {})
	if arena is Dictionary and not arena.is_empty():
		var symbol := str(arena.get("marker", ""))
		return {
			"kind": "arena",
			"symbol": symbol,
			"color": ARENA_COLORS.get(symbol, Color(0.5, 0.5, 0.5)),
			"alpha": 1.0,
			"disabled": false,
			"tooltip": "%s — бой на арене" % str(arena.get("name", "")),
		}
	return {}


# Вид каждой клетки опубликованного рельефа и дорог: поздние наборы перекрывают ранние (деревья над скалой, скала над водой).
static func tile_kinds(terrain: Dictionary, window: Rect2i) -> Dictionary:
	var kinds := {}
	var roads: Variant = terrain.get("roads", {})
	if roads is Dictionary:
		_add_tiles(kinds, roads.get("tiles", []), "road", window)
	var tiles: Variant = terrain.get("tiles", {})
	if tiles is Dictionary:
		for set_name in TILE_SET_ORDER:
			var kind: String = "road" if set_name == "paths" else str(set_name)
			_add_tiles(kinds, tiles.get(set_name, []), kind, window)
	for prop in _array(terrain.get("props")):
		if prop is Dictionary:
			_add_tiles(kinds, prop.get("tiles", []), str(prop.get("type", "")), window)
	for bridge in _array(terrain.get("bridges")):
		if bridge is Dictionary:
			_add_tiles(kinds, bridge.get("tiles", []), "bridge", window)
	return kinds


# Объекты карты: кристалл из payload, лагерь лесника (kind forester, его рисует слой фигурок),
# а зоны библиотеки и древа — только на неопубликованной карте.
static func objects_for(terrain: Dictionary) -> Array:
	var objects: Array = []
	for map_object in _array(terrain.get("objects")):
		if not map_object is Dictionary:
			continue
		var rect := Rect2i(
			int(map_object.get("tile_x", -1)),
			int(map_object.get("tile_y", -1)),
			int(map_object.get("tile_w", 1)),
			int(map_object.get("tile_h", 1)),
		)
		if rect.size.x <= 0 or rect.size.y <= 0:
			continue
		var entry := {"kind": "block", "rect": rect}
		var id := str(map_object.get("id", ""))
		if id == CRYSTAL_ID:
			entry["kind"] = "crystal"
		elif id == FORESTER_ID:
			entry["kind"] = "forester"
			entry["name"] = str(map_object.get("name", ""))
			entry["rotation"] = posmod(int(map_object.get("rotation", 0)), 360)
		objects.append(entry)
	if not is_published(terrain):
		objects.append({"kind": "library", "rect": LIBRARY_BOUNDS})
		objects.append({"kind": "talent", "rect": TALENT_BOUNDS})
	return objects


static func city_bounds(terrain: Dictionary) -> Rect2i:
	var city: Variant = terrain.get("city_area")
	if is_published(terrain) or not city is Dictionary:
		return Rect2i()
	var bounds: Variant = city.get("bounds", [])
	if bounds is Array and bounds.size() >= 4:
		return Rect2i(int(bounds[0]), int(bounds[1]), int(bounds[2]), int(bounds[3]))
	return Rect2i()


static func wall_tiles(terrain: Dictionary) -> Dictionary:
	var walls := {}
	var city: Variant = terrain.get("city_area")
	if is_published(terrain) or not city is Dictionary:
		return walls
	for wall in _array(city.get("wall_tiles")):
		var tile := tile_from(wall)
		if tile != NO_TILE:
			walls[tile] = true
	return walls


static func tile_from(entry: Variant) -> Vector2i:
	if entry is Array and entry.size() >= 2:
		return Vector2i(int(entry[0]), int(entry[1]))
	return NO_TILE


static func _array(value: Variant) -> Array:
	return value if value is Array else []


static func _marker(kind: String, config: Dictionary) -> Dictionary:
	var marker := config.duplicate()
	marker["kind"] = kind
	marker["tooltip"] = str(config.get("tooltip", ""))
	marker["alpha"] = float(config.get("alpha", 1.0))
	marker["disabled"] = bool(config.get("disabled", false))
	return marker


static func _add_tiles(kinds: Dictionary, entries: Variant, kind: String, window: Rect2i) -> void:
	for entry in _array(entries):
		var tile := tile_from(entry)
		if tile != NO_TILE and window.has_point(tile):
			kinds[tile] = kind
