extends RefCounted

# Ходьба по городу Экономики: порт core/player_movement.py (find_tile_path, follow_path) и проверки коллизии
# из scenes/city_scene.py _check_collision. Солидные прямоугольники передаются аргументом: RULES.solid_rects()
# отдаёт стены, непроходимые части зданий с сервера и дома текущего населения.

const RULES := preload("res://scripts/economy_city_layout_rules.gd")
const FEET_LEFT := 10.0
const FEET_UP := 6.0
const FEET_WIDTH := 20
const FEET_HEIGHT := 10
const MAX_NODES := 2500
const DIAGONAL_COST := 1.4142135623730951
const NEIGHBORS := [
	Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1),
	Vector2i(1, 1), Vector2i(1, -1), Vector2i(-1, 1), Vector2i(-1, -1),
]


# Ноги персонажа: как pygame.Rect(int(px - 10), int(py - 6), 20, 10) в _check_collision.
static func feet_rect(point: Vector2) -> Rect2i:
	return Rect2i(int(point.x - FEET_LEFT), int(point.y - FEET_UP), FEET_WIDTH, FEET_HEIGHT)


# Точка заблокирована, если ноги задевают солидный прямоугольник или выходят за карту не через ворота.
static func is_blocked(point: Vector2, solids: Array) -> bool:
	var tile := float(RULES.TILE_PX)
	var world := float(RULES.GRID_TILES.x * RULES.TILE_PX)
	if point.x >= world - 10.0:
		if point.y < 44.0 * tile or point.y > 56.0 * tile:
			return true
	elif point.x <= 10.0:
		if point.y < 47.0 * tile or point.y > 53.0 * tile:
			return true
	if point.y <= 6.0:
		if point.x < 47.0 * tile or point.x > 53.0 * tile:
			return true
	elif point.y >= world - 6.0:
		if point.x < 47.0 * tile or point.x > 53.0 * tile:
			return true
	var feet := feet_rect(point)
	for solid in solids:
		if _overlaps(feet, solid):
			return true
	return false


# A* по сетке тайлов, как find_tile_path: узлы — центры тайлов, диагональ без срезания углов,
# октильная эвристика, лимит MAX_NODES раскрытых узлов. Последняя точка пути — сама цель.
# Пустой массив, если цель заблокирована или путь не найден.
static func find_path(start: Vector2, goal: Vector2, solids: Array) -> Array:
	var tile := RULES.TILE_PX
	var start_node := Vector2i(floori(start.x / tile), floori(start.y / tile))
	var goal_node := Vector2i(floori(goal.x / tile), floori(goal.y / tile))
	var buckets := _tile_buckets(solids)
	var centers := {}
	if _node_center(goal_node, buckets, centers) == null:
		return []
	if start_node == goal_node:
		return [goal]
	var open_heap: Array = []
	var best_cost := {start_node: 0.0}
	var parent := {}
	var closed := {}
	_heap_push(open_heap, [_heuristic(start_node, goal_node), 0.0, start_node.x, start_node.y])
	var expanded := 0
	while not open_heap.is_empty():
		var entry: Array = _heap_pop(open_heap)
		var node := Vector2i(entry[2], entry[3])
		if closed.has(node):
			continue
		if node == goal_node:
			return _route(node, goal, parent, buckets, centers)
		closed[node] = true
		expanded += 1
		if expanded > MAX_NODES:
			return []
		var cost: float = entry[1]
		for offset in NEIGHBORS:
			var neighbor: Vector2i = node + offset
			if closed.has(neighbor) or _node_center(neighbor, buckets, centers) == null:
				continue
			var diagonal: bool = offset.x != 0 and offset.y != 0
			if diagonal and (_node_center(Vector2i(node.x + offset.x, node.y), buckets, centers) == null
					or _node_center(Vector2i(node.x, node.y + offset.y), buckets, centers) == null):
				continue
			var new_cost := cost + (DIAGONAL_COST if diagonal else 1.0)
			if new_cost < best_cost.get(neighbor, INF):
				best_cost[neighbor] = new_cost
				parent[neighbor] = node
				_heap_push(open_heap, [new_cost + _heuristic(neighbor, goal_node), new_cost, neighbor.x, neighbor.y])
	return []


# Двигает точку по path не дальше step px за кадр, как follow_path. Пройденные точки удаляются из path на месте.
# Возвращает {"position": Vector2, "moved": bool}; если путь перекрыт, точка останавливается.
static func follow_path(position: Vector2, path: Array, step: float, solids: Array) -> Dictionary:
	var moved := false
	var budget := step
	var point := position
	while not path.is_empty() and budget > 0.0:
		var target: Vector2 = path[0]
		var distance := point.distance_to(target)
		if distance <= budget:
			if is_blocked(target, solids):
				break
			point = target
			budget -= distance
			path.remove_at(0)
			moved = true
			continue
		var stepped := _move_with_collision(point, (target - point) / distance, budget, solids)
		point = stepped["position"]
		moved = moved or bool(stepped["moved"])
		break
	return {"position": point, "moved": moved}


# Сдвиг по осям, чтобы персонаж скользил вдоль препятствий, как move_with_collision.
static func _move_with_collision(point: Vector2, direction: Vector2, step: float, solids: Array) -> Dictionary:
	var moved := false
	var result := point
	if direction.x != 0.0:
		var next_x := result.x + direction.x * step
		if not is_blocked(Vector2(next_x, result.y), solids):
			result.x = next_x
			moved = true
	if direction.y != 0.0:
		var next_y := result.y + direction.y * step
		if not is_blocked(Vector2(result.x, next_y), solids):
			result.y = next_y
			moved = true
	return {"position": result, "moved": moved}


static func _overlaps(first: Rect2i, second: Rect2i) -> bool:
	if first.size.x <= 0 or first.size.y <= 0 or second.size.x <= 0 or second.size.y <= 0:
		return false
	return first.position.x < second.end.x and second.position.x < first.end.x \
		and first.position.y < second.end.y and second.position.y < first.end.y


# Центр тайла, если в нём можно стоять; null — тайл вне карты или заблокирован. Ноги в центре тайла лежат внутри
# пикселей этого тайла, поэтому проверяются только солидные прямоугольники его клетки. Результаты кэшируются на поиск.
static func _node_center(node: Vector2i, buckets: Dictionary, centers: Dictionary) -> Variant:
	if centers.has(node):
		return centers[node]
	var center: Variant = null
	var grid := RULES.GRID_TILES
	if node.x >= 0 and node.y >= 0 and node.x < grid.x and node.y < grid.y:
		var point := Vector2(node * RULES.TILE_PX) + Vector2.ONE * (RULES.TILE_PX * 0.5)
		if not _blocked_in_tile(point, buckets.get(node, [])):
			center = point
	centers[node] = center
	return center


static func _blocked_in_tile(point: Vector2, candidates: Array) -> bool:
	var feet := feet_rect(point)
	for solid in candidates:
		if _overlaps(feet, solid):
			return true
	return false


# Солидные прямоугольники по клеткам, которые они задевают (правая и нижняя границы пикселей не входят).
static func _tile_buckets(solids: Array) -> Dictionary:
	var buckets := {}
	var tile := float(RULES.TILE_PX)
	for solid in solids:
		var rect: Rect2i = solid
		if rect.size.x <= 0 or rect.size.y <= 0:
			continue
		var first := Vector2i(floori(rect.position.x / tile), floori(rect.position.y / tile))
		var last := Vector2i(floori((rect.end.x - 1) / tile), floori((rect.end.y - 1) / tile))
		for y in range(first.y, last.y + 1):
			for x in range(first.x, last.x + 1):
				var key := Vector2i(x, y)
				if not buckets.has(key):
					buckets[key] = []
				buckets[key].append(rect)
	return buckets


static func _heuristic(node: Vector2i, goal: Vector2i) -> float:
	var dx := absi(node.x - goal.x)
	var dy := absi(node.y - goal.y)
	return float(maxi(dx, dy)) + (DIAGONAL_COST - 1.0) * float(mini(dx, dy))


static func _route(end_node: Vector2i, goal: Vector2, parent: Dictionary, buckets: Dictionary, centers: Dictionary) -> Array:
	var nodes: Array[Vector2i] = [end_node]
	while parent.has(nodes[-1]):
		nodes.append(parent[nodes[-1]])
	nodes.reverse()
	var path: Array = []
	for index in range(1, nodes.size()):
		path.append(_node_center(nodes[index], buckets, centers))
	path[-1] = goal
	return path


# Куча по ключу [f, g, x, y], как очередь heapq в Python: сравнение по f, затем по g и координатам узла.
static func _heap_push(heap: Array, entry: Array) -> void:
	heap.append(entry)
	var index := heap.size() - 1
	while index > 0:
		var parent_index := (index - 1) >> 1
		if not _less(heap[index], heap[parent_index]):
			break
		var swap = heap[index]
		heap[index] = heap[parent_index]
		heap[parent_index] = swap
		index = parent_index


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


static func _less(first: Array, second: Array) -> bool:
	for index in range(3):
		if first[index] != second[index]:
			return first[index] < second[index]
	return first[3] < second[3]
