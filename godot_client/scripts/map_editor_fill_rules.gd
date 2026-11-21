extends RefCounted


static func fill(cells: Dictionary, map_size: Vector2i, seed: Vector2i, key: String) -> Array[Vector2i]:
	var filled: Array[Vector2i] = []
	if not _inside(seed, map_size):
		return filled
	var target := str(cells.get(cell_key(seed), ""))
	if target == key:
		return filled
	var visited := {seed: true}
	var queue: Array[Vector2i] = [seed]
	var head := 0
	while head < queue.size():
		var cell := queue[head]
		head += 1
		filled.append(cell)
		for neighbour in [cell + Vector2i.RIGHT, cell + Vector2i.LEFT, cell + Vector2i.DOWN, cell + Vector2i.UP]:
			if visited.has(neighbour) or not _inside(neighbour, map_size):
				continue
			if str(cells.get(cell_key(neighbour), "")) != target:
				continue
			visited[neighbour] = true
			queue.append(neighbour)
	for cell in filled:
		cells[cell_key(cell)] = key
	return filled


static func cell_key(cell: Vector2i) -> String:
	return "%d:%d" % [cell.x, cell.y]


static func _inside(cell: Vector2i, map_size: Vector2i) -> bool:
	return cell.x >= 0 and cell.y >= 0 and cell.x < map_size.x and cell.y < map_size.y
