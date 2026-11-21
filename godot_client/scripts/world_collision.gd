extends RefCounted

# Коллизии и поиск пути персонажа Башни. Правила совпадают с сервером (tower/server/world_mobs.py:
# _terrain_blocked и _segment_clear), по которым сервер принимает ход, и с Python-клиентом
# (core/player_movement.py: find_tile_path, follow_path).

const TILE := 32
const FEET_W := 20
const FEET_H := 10
const MOB_W := 90
const MOB_H := 53
# Тело моба Front Line — квадрат со стороной в два радиуса расталкивания (front_line/server/world.py: _mob_body_rect).
const FRONT_LINE_MOB_RADIUS := 16.0
# Радиус тела моба для дальности атаки (совпадает с front_line/server/combat.py MOB_RANGE_HULL_PX).
const FRONT_LINE_MOB_HULL_RADIUS := 20.0
const FRONT_LINE_BOSS_SCALE := 4.0
const ANIMAL_W := 16
const ANIMAL_H := 8
const MASK_SIDE := 4
const MASK_CELL := 8
const MASK_BLOCKED := "0"
const MAX_SEARCH_NODES := 2500
const MOVE_SAMPLE_STEP := 8.0
const SQRT2 := 1.4142135623730951
const NEIGHBORS := [
	Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1),
	Vector2i(1, 1), Vector2i(1, -1), Vector2i(-1, 1), Vector2i(-1, -1),
]
const SAMPLE_FRACTIONS := [
	Vector2(0.5, 0.5), Vector2(0.25, 0.25), Vector2(0.5, 0.25), Vector2(0.75, 0.25), Vector2(0.25, 0.5),
	Vector2(0.75, 0.5), Vector2(0.25, 0.75), Vector2(0.5, 0.75), Vector2(0.75, 0.75),
]

var _world_size := Vector2.ZERO
var _blocked_tiles := {}
var _partial_masks := {}
var _obstacles: Array = []
var _solid_rects: Array = []


# Рельеф из /api/map/terrain: строки тайлов [y, x_начало, x_конец], маски [x, y, маска], полигоны препятствий.
func configure(terrain: Dictionary) -> void:
	var map_data: Variant = terrain.get("map", {})
	if map_data is Dictionary:
		_world_size = Vector2(
			float(int(map_data.get("tiles_w", 0)) * TILE),
			float(int(map_data.get("tiles_h", 0)) * TILE),
		)
	_blocked_tiles.clear()
	_partial_masks.clear()
	var tiles: Variant = terrain.get("tiles", {})
	if tiles is Dictionary:
		for key in ["forest", "water", "dry", "mountain", "impassable"]:
			_add_tile_rows(tiles.get(key, []))
		for entry in tiles.get("partial", []):
			if entry is Array and entry.size() >= 3:
				_partial_masks[Vector2i(int(entry[0]), int(entry[1]))] = str(entry[2])
	for prop in terrain.get("props", []):
		if prop is Dictionary:
			for tile in prop.get("tiles", []):
				if tile is Array and tile.size() >= 2:
					_blocked_tiles[Vector2i(int(tile[0]), int(tile[1]))] = true
	# Тайлы с маской проверяются по клеткам маски, а не целиком
	for tile in _partial_masks:
		_blocked_tiles.erase(tile)
	_build_obstacles(terrain.get("obstacles", []))


static func mob_rect(x: float, y: float) -> Array:
	return [int(x) - int(MOB_W / 2.0), int(y) - int(MOB_H / 2.0), MOB_W, MOB_H]


static func front_line_mob_rect(x: float, y: float, is_boss: bool) -> Array:
	var radius := FRONT_LINE_MOB_RADIUS * (FRONT_LINE_BOSS_SCALE if is_boss else 1.0)
	return [int(x - radius), int(y - radius), int(radius * 2.0), int(radius * 2.0)]


static func animal_rect(x: float, y: float) -> Array:
	return [int(x - ANIMAL_W / 2.0), int(y - ANIMAL_H / 2.0), ANIMAL_W, ANIMAL_H]


func feet_rect(x: float, y: float) -> Array:
	return [int(x - FEET_W / 2.0), int(y - FEET_H / 2.0 + 1.0), FEET_W, FEET_H]


# Точка заблокирована рельефом или одним из динамических прямоугольников (живые мобы и животные).
func point_blocked(point: Vector2, dynamic_rects: Array) -> bool:
	if terrain_blocked(point.x, point.y):
		return true
	var feet := feet_rect(point.x, point.y)
	for rect in dynamic_rects:
		if _rects_collide(feet, rect):
			return true
	return false


func terrain_blocked(x: float, y: float) -> bool:
	if x - FEET_W / 2.0 < 0.0 or x + FEET_W / 2.0 > _world_size.x \
			or y - FEET_H / 2.0 < 0.0 or y + FEET_H / 2.0 > _world_size.y:
		return true
	if _rect_touches_blocked_tile(feet_rect(x, y)):
		return true
	if _solid_rects_block(x, y):
		return true
	var ix := int(x)
	var iy := int(y)
	var point := Vector2(x, y)
	for obstacle in _obstacles:
		if not _in_rect(ix, iy, obstacle["bounds"]):
			continue
		if not _point_in_polygon(point, obstacle["points"]):
			continue
		var in_passage := false
		for passage in obstacle["passages"]:
			if _in_rect(ix, iy, passage):
				in_passage = true
				break
		if not in_passage:
			return true
	return false


# Отрезок пути свободен, если каждые MOVE_SAMPLE_STEP пикселей персонаж не упирается в препятствие.
func segment_clear(from: Vector2, to: Vector2, dynamic_rects: Array) -> bool:
	var steps := maxi(1, ceili(from.distance_to(to) / MOVE_SAMPLE_STEP))
	for index in range(1, steps + 1):
		if point_blocked(from.lerp(to, float(index) / float(steps)), dynamic_rects):
			return false
	return true


# Путь по тайлам от start до goal. Пустой массив — цель недостижима в пределах MAX_SEARCH_NODES.
func find_path(start: Vector2, goal: Vector2, dynamic_rects: Array) -> Array:
	var start_node := Vector2i(floori(start.x / TILE), floori(start.y / TILE))
	var goal_node := Vector2i(floori(goal.x / TILE), floori(goal.y / TILE))
	var cache := {}
	if _free_point(goal_node, cache, dynamic_rects) == null:
		return []
	if start_node == goal_node:
		return [goal]
	var goal_point := goal
	if point_blocked(goal, dynamic_rects):
		goal_point = _free_point(goal_node, cache, dynamic_rects)
	var open: Array = []
	var best_cost := {start_node: 0.0}
	var parent := {}
	var closed := {}
	var expanded := 0
	_heap_push(open, [_heuristic(start_node, goal_node), 0.0, start_node.x, start_node.y])
	while not open.is_empty():
		var entry: Array = _heap_pop(open)
		var node := Vector2i(entry[2], entry[3])
		if closed.has(node):
			continue
		if node == goal_node:
			return _build_path(node, parent, goal_point, cache, dynamic_rects)
		closed[node] = true
		expanded += 1
		if expanded > MAX_SEARCH_NODES:
			return []
		var cost: float = entry[1]
		for offset in NEIGHBORS:
			var next_node: Vector2i = node + offset
			if closed.has(next_node) or _free_point(next_node, cache, dynamic_rects) == null:
				continue
			var diagonal: bool = offset.x != 0 and offset.y != 0
			# Без срезания углов: по диагонали нельзя протискиваться между двумя блоками
			if diagonal and (
				_free_point(Vector2i(node.x + offset.x, node.y), cache, dynamic_rects) == null
				or _free_point(Vector2i(node.x, node.y + offset.y), cache, dynamic_rects) == null
			):
				continue
			var new_cost := cost + (SQRT2 if diagonal else 1.0)
			if new_cost < float(best_cost.get(next_node, INF)):
				best_cost[next_node] = new_cost
				parent[next_node] = node
				_heap_push(open, [new_cost + _heuristic(next_node, goal_node), new_cost, next_node.x, next_node.y])
	return []


# Двигает точку по path не дальше step пикселей; пройденные точки удаляются из path.
func follow_path(position: Vector2, path: Array, step: float, dynamic_rects: Array) -> Dictionary:
	var moved := false
	var budget := step
	var current := position
	while not path.is_empty() and budget > 0.0:
		var target: Vector2 = path[0]
		var distance := current.distance_to(target)
		if distance <= budget:
			if point_blocked(target, dynamic_rects):
				break
			current = target
			budget -= distance
			path.pop_front()
			moved = true
			continue
		var step_result := _move_with_collision(current, (target - current) / distance, budget, dynamic_rects)
		current = step_result["position"]
		moved = moved or bool(step_result["moved"])
		break
	return {"position": current, "moved": moved}


func _move_with_collision(position: Vector2, direction: Vector2, step: float, dynamic_rects: Array) -> Dictionary:
	var current := position
	var moved := false
	if direction.x != 0.0:
		var next_x := current.x + direction.x * step
		if not point_blocked(Vector2(next_x, current.y), dynamic_rects):
			current.x = next_x
			moved = true
	if direction.y != 0.0:
		var next_y := current.y + direction.y * step
		if not point_blocked(Vector2(current.x, next_y), dynamic_rects):
			current.y = next_y
			moved = true
	return {"position": current, "moved": moved}


func _free_point(node: Vector2i, cache: Dictionary, dynamic_rects: Array) -> Variant:
	if cache.has(node):
		return cache[node]
	var fractions := SAMPLE_FRACTIONS if _partial_masks.has(node) else SAMPLE_FRACTIONS.slice(0, 1)
	var result: Variant = null
	for fraction in fractions:
		var point := Vector2(node.x * TILE + fraction.x * TILE, node.y * TILE + fraction.y * TILE)
		if not point_blocked(point, dynamic_rects):
			result = point
			break
	cache[node] = result
	return result


func _build_path(goal_node: Vector2i, parent: Dictionary, goal_point: Vector2, cache: Dictionary, dynamic_rects: Array) -> Array:
	var nodes: Array = [goal_node]
	while parent.has(nodes.back()):
		nodes.append(parent[nodes.back()])
	nodes.reverse()
	var path: Array = []
	for index in range(1, nodes.size()):
		path.append(_free_point(nodes[index], cache, dynamic_rects))
	if path.is_empty():
		return [goal_point]
	path[path.size() - 1] = goal_point
	return path


func _heuristic(node: Vector2i, goal_node: Vector2i) -> float:
	var dx := absf(float(node.x - goal_node.x))
	var dy := absf(float(node.y - goal_node.y))
	return maxf(dx, dy) + (SQRT2 - 1.0) * minf(dx, dy)


func _build_obstacles(obstacles: Variant) -> void:
	_obstacles.clear()
	if not obstacles is Array:
		return
	for obstacle in obstacles:
		if not obstacle is Dictionary or not obstacle.get("points", []) is Array:
			continue
		var points := PackedVector2Array()
		for point in obstacle["points"]:
			if point is Array and point.size() >= 2:
				points.append(Vector2(float(point[0]), float(point[1])))
		if points.is_empty():
			continue
		var low := points[0]
		var high := points[0]
		for point in points:
			low = low.min(point)
			high = high.max(point)
		# Рамка считается по точкам, как _build_obstacle_shapes на сервере
		var bounds := [low.x, low.y, high.x - low.x + 1.0, high.y - low.y + 1.0]
		var passages: Array = []
		for passage in obstacle.get("passages", []):
			if passage is Array and passage.size() >= 4:
				passages.append([float(passage[0]), float(passage[1]), float(passage[2]), float(passage[3])])
		_obstacles.append({"points": points, "bounds": bounds, "passages": passages})


func _add_tile_rows(rows: Variant) -> void:
	if not rows is Array:
		return
	for row in rows:
		if row is Array and row.size() >= 3:
			for tile_x in range(int(row[1]), int(row[2]) + 1):
				_blocked_tiles[Vector2i(tile_x, int(row[0]))] = true


# Прямоугольники зданий карты (solid_rects); задаёт вызывающий код, Башня их не получает.
func set_solid_rects(rects: Array) -> void:
	_solid_rects = rects


# Ноги как в _check_collision (scenes/world_map_scene.py): pygame.Rect(int(x - 10), int(y - 6), 20, 10), а не как у сервера.
func _solid_rects_block(x: float, y: float) -> bool:
	if _solid_rects.is_empty():
		return false
	var feet := [int(x - FEET_W / 2.0), int(y - 6.0), FEET_W, FEET_H]
	for rect in _solid_rects:
		if _rects_collide(feet, rect):
			return true
	return false


func _rect_touches_blocked_tile(rect: Array) -> bool:
	if _blocked_tiles.is_empty() and _partial_masks.is_empty():
		return false
	var left: int = rect[0]
	var top: int = rect[1]
	var right: int = left + int(rect[2])
	var bottom: int = top + int(rect[3])
	for tile_y in range(_tile_index(top), _tile_index(bottom - 1) + 1):
		for tile_x in range(_tile_index(left), _tile_index(right - 1) + 1):
			var tile := Vector2i(tile_x, tile_y)
			if _partial_masks.has(tile):
				if _mask_blocks_rect(_partial_masks[tile], tile_x, tile_y, left, top, right, bottom):
					return true
			elif _blocked_tiles.has(tile):
				return true
	return false


func _mask_blocks_rect(mask: String, tile_x: int, tile_y: int, left: int, top: int, right: int, bottom: int) -> bool:
	var origin_x := tile_x * TILE
	var origin_y := tile_y * TILE
	for row in range(MASK_SIDE):
		var cell_top := origin_y + row * MASK_CELL
		if cell_top >= bottom or cell_top + MASK_CELL <= top:
			continue
		for column in range(MASK_SIDE):
			if mask.substr(row * MASK_SIDE + column, 1) != MASK_BLOCKED:
				continue
			var cell_left := origin_x + column * MASK_CELL
			if cell_left < right and cell_left + MASK_CELL > left:
				return true
	return false


func _tile_index(value: int) -> int:
	return floori(float(value) / TILE)


static func _in_rect(x: int, y: int, rect: Array) -> bool:
	return x >= rect[0] and x < rect[0] + rect[2] and y >= rect[1] and y < rect[1] + rect[3]


static func _rects_collide(a: Array, b: Array) -> bool:
	return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


static func _point_in_polygon(point: Vector2, polygon: PackedVector2Array) -> bool:
	var inside := false
	var count := polygon.size()
	for index in range(count):
		var first := polygon[index]
		var second := polygon[(index + 1) % count]
		if (first.y > point.y) != (second.y > point.y) \
				and point.x < (second.x - first.x) * (point.y - first.y) / (second.y - first.y) + first.x:
			inside = not inside
	return inside


static func _less(a: Array, b: Array) -> bool:
	if a[0] != b[0]:
		return a[0] < b[0]
	if a[1] != b[1]:
		return a[1] < b[1]
	if a[2] != b[2]:
		return a[2] < b[2]
	return a[3] < b[3]


static func _heap_push(heap: Array, item: Array) -> void:
	heap.append(item)
	var index := heap.size() - 1
	while index > 0:
		var parent := (index - 1) >> 1
		if not _less(heap[index], heap[parent]):
			break
		var swap = heap[index]
		heap[index] = heap[parent]
		heap[parent] = swap
		index = parent


static func _heap_pop(heap: Array) -> Array:
	var top: Array = heap[0]
	var last: Array = heap.pop_back()
	if heap.is_empty():
		return top
	heap[0] = last
	var index := 0
	while true:
		var left := index * 2 + 1
		var right := left + 1
		var smallest := index
		if left < heap.size() and _less(heap[left], heap[smallest]):
			smallest = left
		if right < heap.size() and _less(heap[right], heap[smallest]):
			smallest = right
		if smallest == index:
			break
		var swap = heap[index]
		heap[index] = heap[smallest]
		heap[smallest] = swap
		index = smallest
	return top
