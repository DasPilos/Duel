extends RefCounted
# Слой путей мира для карты Экономики: порт ui/map_travel.py (карта мира Python, scenes/world_map_scene.py:2546).
# Поля ответов сервера Экономики, которые читает слой:
#   горожанин — city_population.py:512-524: id:512 name:514 job_building:515 travel_direction:516
#     travel_seconds_left:518 eta_seconds:519 position_x:520 position_y:521 position_direction:522
#     route_name:523 movement_text:524 (позиция приходит с сервера, клиент её не пересчитывает);
#   повозка — transport.py:1152-1178: id:1152 cart_id:1152 cart_grade:1153 cart_name:1154 cart_sprite_key:1155
#     destination_building_id:1159 destination_name:1160 route_name:1160 driver_name:1162 horses:1163 pinned:1167
#     phase:1169 status:1169 movement_text:1172 direction:1173 travel_seconds:1173 seconds_remaining:1174
#     progress_percent:1174 position_x:1176 position_y:1176 position_direction:1177.
#   маршруты — /api/map/terrain (api.py:49), terrain.roads.routes из world_roads.py roads_payload:
#     building_id, name, gate_id, tiles ([x, y], первый тайл — ворота).
# Порт из map_travel.py: ROAD_BUILDING_IDS 16-22; _route_progress_percent 39-46; route_position 49-75;
#   _route 78-81; traveling_entities 84-126 (повозки — позиция по прогрессу на маршруте, горожане — позиция сервера);
#   _separate_nearby_convoys 128-165 и display_position (точка отрисовки и выбора, map_travel.py:177-178, 250-251);
#   _transport_sprite 185-204 и draw_convoy_sprite_group 230-244 (имена спрайтов, поворот, раскладка повозки);
#   иконка повозки у подписи 280-296 (cart_icon_name, cart_icon_rect).
# Мир: тайл 16 px (core/tile.py), карта 1024x512 (server/world_map.py), это не сетка Радбурга 200x200.

const TILE_PX := 16
const WORLD_TILES := Vector2i(1024, 512)
const CONVOY_CLOSE_TILES := 3.0
const CONVOY_LANE_TILES := 1.8
const DEFAULT_SPRITE_KEY := "light"
const CART_ICON_SIZE := 32.0
const CART_ICON_GAP := 4.0
const ROAD_BUILDING_IDS := {
	"farm": "wheat_farm",
	"lumber_camp": "lumber_camp",
	"mountain_rift": "mountain_rift",
	"barnyard": "barnyard",
	"black_pit": "black_pit",
}
const DIRECTION_VECTORS := {
	"n": Vector2(0.0, -1.0), "ne": Vector2(0.707, -0.707), "e": Vector2(1.0, 0.0), "se": Vector2(0.707, 0.707),
	"s": Vector2(0.0, 1.0), "sw": Vector2(-0.707, 0.707), "w": Vector2(-1.0, 0.0), "nw": Vector2(-0.707, -0.707),
}


static func assets_root(project_dir: String) -> String:
	return project_dir.path_join("../assets").simplify_path()


static func transport_sprite_path(root: String, sprite_name: String) -> String:
	return root.path_join("ui/transport").path_join(sprite_name + ".png")


# Имена спрайтов повозки, как draw_convoy_sprite_group: cart_{key}, harness_{key}, horse, driver.
static func sprite_names(sprite_key: String) -> Dictionary:
	var key := sprite_key if not sprite_key.is_empty() else DEFAULT_SPRITE_KEY
	return {"wagon": "cart_" + key, "harness": "harness_" + key, "horse": "horse", "driver": "driver"}


# Иконка повозки у подписи (map_travel.py:280-296): cart_{ключ}. Пустой ключ — иконки нет, в отличие от спрайтов повозки.
static func cart_icon_name(sprite_key: String) -> String:
	return "" if sprite_key.is_empty() else "cart_" + sprite_key


# Иконка 32 px левее подписи с зазором 4 px и центром по высоте подписи.
static func cart_icon_rect(label: Rect2) -> Rect2:
	return Rect2(label.position.x - CART_ICON_SIZE - CART_ICON_GAP, label.get_center().y - CART_ICON_SIZE * 0.5,
		CART_ICON_SIZE, CART_ICON_SIZE)


# Угол поворота спрайта в радианах; как _transport_sprite: atan2(dx, -dy), по часовой стрелке на экране.
static func rotation_for(vector: Vector2) -> float:
	return atan2(vector.x, -vector.y)


static func route_for_building(routes: Array, building_id: String) -> Dictionary:
	var route_id := str(ROAD_BUILDING_IDS.get(building_id, building_id))
	for route in routes:
		if route is Dictionary and str(route.get("building_id", "")) == route_id:
			return route
	return {}


# Прогресс в процентах: поле progress_percent сервера, а если его нет — из ETA и длительности (map_travel.py:39-46).
static func progress_percent(entity: Dictionary) -> int:
	var progress: Variant = entity.get("progress_percent", null)
	if progress == null:
		var total := maxi(1, int(entity.get("travel_seconds", entity.get("total_seconds", 1))))
		var eta := maxi(0, int(entity.get("eta_seconds", entity.get("seconds_remaining", 0))))
		var outbound := str(entity.get("direction", "outbound")) == "outbound"
		progress = 100.0 * (1.0 - float(eta) / total) if outbound else 100.0 * float(eta) / total
	return clampi(roundi(float(progress)), 0, 100)


static func route_points(tiles: Array, tile_px: int = TILE_PX) -> PackedVector2Array:
	var points := PackedVector2Array()
	for tile in tiles:
		var values: Array = tile
		points.append(Vector2((float(values[0]) + 0.5) * tile_px, (float(values[1]) + 0.5) * tile_px))
	return points


# Точка на ломаной маршрута по доле пути 0..1 (map_travel.py:49-75): {x, y, direction} или пустой словарь.
static func route_position(tiles: Array, progress: float, tile_px: int = TILE_PX) -> Dictionary:
	var points := route_points(tiles, tile_px)
	if points.is_empty():
		return {}
	if points.size() == 1:
		return {"x": points[0].x, "y": points[0].y, "direction": "s"}
	var total := 0.0
	for index in range(points.size() - 1):
		total += points[index].distance_to(points[index + 1])
	if total <= 0.0:
		return {"x": points[0].x, "y": points[0].y, "direction": "s"}
	var distance := clampf(progress, 0.0, 1.0) * total
	for index in range(points.size() - 1):
		var start := points[index]
		var end := points[index + 1]
		var length := start.distance_to(end)
		if distance <= length:
			var fraction := 0.0 if length == 0.0 else distance / length
			var delta := end - start
			var point := start + delta * fraction
			return {"x": point.x, "y": point.y, "direction": direction_of(delta)}
		distance -= length
	return {"x": points[-1].x, "y": points[-1].y, "direction": "s"}


static func direction_of(delta: Vector2) -> String:
	if absf(delta.x) > absf(delta.y) * 2.0:
		return "e" if delta.x > 0.0 else "w"
	if absf(delta.y) > absf(delta.x) * 2.0:
		return "s" if delta.y > 0.0 else "n"
	if delta.x != 0.0 and delta.y != 0.0:
		return ("s" if delta.y > 0.0 else "n") + ("e" if delta.x > 0.0 else "w")
	return "s"


# Горожане с позицией сервера; без position_x или position_y запись пропускается, как в map_travel.py:88-89.
static func citizen_entries(citizens: Array) -> Array:
	var entries: Array = []
	for citizen in citizens:
		if not citizen is Dictionary:
			continue
		if citizen.get("position_x", null) == null or citizen.get("position_y", null) == null:
			continue
		var entry: Dictionary = citizen.duplicate()
		entry["entity_kind"] = "citizen"
		entry["eta_seconds"] = int(entry.get("eta_seconds", entry.get("travel_seconds_left", 0)))
		entries.append(entry)
	return entries


# Повозки на маршрутах: ETA уменьшается на время, прошедшее с ответа сервера (map_travel.py:97-106).
static func convoy_entries(convoys: Array, routes: Array, elapsed_seconds: float) -> Array:
	var entries: Array = []
	for convoy in convoys:
		if not convoy is Dictionary:
			continue
		var destination := str(convoy.get("destination_building_id", convoy.get("building_id", "")))
		var route := route_for_building(routes, destination)
		if route.is_empty() or (route.get("tiles", []) as Array).is_empty():
			continue
		var eta := maxi(0, int(float(convoy.get("seconds_remaining", 0)) - maxf(0.0, elapsed_seconds)))
		var with_eta: Dictionary = convoy.duplicate()
		with_eta["seconds_remaining"] = eta
		var progress := progress_percent(with_eta)
		var position := route_position(route["tiles"], float(progress) / 100.0)
		if position.is_empty():
			continue
		var direction := str(convoy.get("direction", "outbound"))
		var entry: Dictionary = convoy.duplicate()
		entry["entity_kind"] = "wagon"
		entry["position_x"] = position["x"]
		entry["position_y"] = position["y"]
		entry["position_direction"] = position["direction"]
		entry["eta_seconds"] = eta
		entry["progress_percent"] = progress
		entry["route_name"] = str(convoy.get("route_name", route.get("name", "Маршрут")))
		entry["movement_text"] = str(convoy.get("movement_text", convoy.get("status",
			"Едет к загородному объекту" if direction == "outbound" else "Возвращается в город")))
		entries.append(entry)
	return entries


# Точка отрисовки и выбора горожанина или повозки: display_position после раздвижки, иначе position (map_travel.py:177-178, 250-251).
static func display_position(entry: Dictionary) -> Vector2:
	if entry.has("display_position_x") and entry.has("display_position_y"):
		return Vector2(float(entry["display_position_x"]), float(entry["display_position_y"]))
	return Vector2(float(entry["position_x"]), float(entry["position_y"]))


# Раздвижка повозок, летящих рядом (map_travel.py:128-165): якорь кластера — первая ещё не разведённая повозка списка,
# соседи — повозки того же destination_building_id в радиусе 1.5 тайла от якоря (не цепочкой). Пишет display_position_x/y
# в записи повозок; горожане и одиночные повозки не меняются.
static func separate_nearby_convoys(entries: Array, tile_px: int = TILE_PX) -> void:
	var convoys: Array = []
	for entry in entries:
		if entry is Dictionary and str(entry.get("entity_kind", "")) == "wagon":
			convoys.append(entry)
	var close_distance := maxf(1.0, float(tile_px) * CONVOY_CLOSE_TILES)
	var lane_spacing := maxf(1.0, float(tile_px) * CONVOY_LANE_TILES)
	var remaining: Array[int] = []
	for index in range(convoys.size()):
		remaining.append(index)
	while not remaining.is_empty():
		var anchor_index: int = remaining[0]
		var anchor: Dictionary = convoys[anchor_index]
		var cluster: Array[int] = []
		for index in remaining:
			if index == anchor_index or _is_near(convoys[index], anchor, close_distance):
				cluster.append(index)
		var rest: Array[int] = []
		for index in remaining:
			if not cluster.has(index):
				rest.append(index)
		remaining = rest
		if cluster.size() >= 2:
			_lay_out_cluster(convoys, cluster, anchor, lane_spacing)


static func _is_near(convoy: Dictionary, anchor: Dictionary, limit: float) -> bool:
	if convoy.get("destination_building_id") != anchor.get("destination_building_id"):
		return false
	var dx := float(convoy["position_x"]) - float(anchor["position_x"])
	var dy := float(convoy["position_y"]) - float(anchor["position_y"])
	return sqrt(dx * dx + dy * dy) <= limit


# Полосы кластера поперёк направления якоря (map_travel.py:156-165); порядок полос — по str(id), как sort в Python.
static func _lay_out_cluster(convoys: Array, cluster: Array[int], anchor: Dictionary, lane_spacing: float) -> void:
	var vector: Vector2 = DIRECTION_VECTORS.get(str(anchor.get("position_direction", "s")), Vector2(0.0, 1.0))
	var across := Vector2(-vector.y, vector.x)
	cluster.sort_custom(func(a: int, b: int) -> bool:
		var key_a := str(convoys[a].get("id", a))
		var key_b := str(convoys[b].get("id", b))
		if key_a == key_b:
			return a < b
		return key_a.casecmp_to(key_b) < 0)
	var midpoint := float(cluster.size() - 1) / 2.0
	for lane in range(cluster.size()):
		var entry: Dictionary = convoys[cluster[lane]]
		var offset := (float(lane) - midpoint) * lane_spacing
		entry["display_position_x"] = float(entry["position_x"]) + across.x * offset
		entry["display_position_y"] = float(entry["position_y"]) + across.y * offset


static func tooltip_lines(entry: Dictionary) -> PackedStringArray:
	if str(entry.get("entity_kind", "")) == "citizen":
		return PackedStringArray([
			str(entry.get("name", "Горожанин")),
			str(entry.get("movement_text", "В пути")),
			"Маршрут: " + str(entry.get("route_name", "—")),
			"Осталось: " + format_seconds(int(entry.get("eta_seconds", 0))),
		])
	var horses := PackedStringArray()
	for horse in entry.get("horses", []):
		if horse is Dictionary:
			horses.append(str(horse.get("name", "Лошадь")))
	return PackedStringArray([
		str(entry.get("cart_name", "Повозка")),
		str(entry.get("movement_text", "В пути")),
		"Маршрут: " + str(entry.get("route_name", "—")),
		"Экипаж: " + str(entry.get("driver_name", "—")),
		"Лошади: " + (", ".join(horses) if not horses.is_empty() else "—"),
		"Осталось: " + format_seconds(int(entry.get("eta_seconds", 0))),
	])


static func format_seconds(seconds: int) -> String:
	var safe := maxi(0, seconds)
	var hours := safe / 3600
	var minutes := (safe % 3600) / 60
	var remainder := safe % 60
	if hours > 0:
		return "%d ч %02d мин" % [hours, minutes]
	if minutes > 0:
		return "%02d:%02d" % [minutes, remainder]
	return "00:%02d" % remainder


# Прямоугольник мира, который вмещает все маршруты и фигуры, с отступом в два тайла.
static func content_bounds(routes: Array, entries: Array) -> Rect2:
	var points := PackedVector2Array()
	for route in routes:
		if route is Dictionary:
			points.append_array(route_points(route.get("tiles", []) as Array))
	for entry in entries:
		points.append(Vector2(float(entry.get("position_x", 0.0)), float(entry.get("position_y", 0.0))))
	if points.is_empty():
		return Rect2(Vector2.ZERO, Vector2(WORLD_TILES * TILE_PX))
	var low := points[0]
	var high := points[0]
	for point in points:
		low = Vector2(minf(low.x, point.x), minf(low.y, point.y))
		high = Vector2(maxf(high.x, point.x), maxf(high.y, point.y))
	return Rect2(low, high - low).grow(TILE_PX * 12.0)
