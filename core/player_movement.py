import heapq
import math

_SQRT2 = math.sqrt(2)
_NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))


def move_with_collision(x, y, vx, vy, step, is_blocked):
    """Сдвигает точку по осям, чтобы персонаж скользил вдоль препятствий. Возвращает (x, y, moved)."""
    moved = False
    if vx != 0:
        new_x = x + vx * step
        if not is_blocked(new_x, y):
            x = new_x
            moved = True
    if vy != 0:
        new_y = y + vy * step
        if not is_blocked(x, new_y):
            y = new_y
            moved = True
    return x, y, moved


def find_tile_path(start, goal, is_blocked, tile_size=32, max_nodes=2500):
    """A* по сетке тайлов от start до goal (мировые координаты).

    Возвращает список точек пути, последняя точка — goal. None, если цель заблокирована
    или путь не найден в пределах max_nodes раскрытых тайлов.
    is_blocked(x, y) проверяет точку мира; результаты кэшируются на время одного поиска.
    """
    start_node = (int(start[0] // tile_size), int(start[1] // tile_size))
    goal_node = (int(goal[0] // tile_size), int(goal[1] // tile_size))
    cache = {}

    def passable(node):
        if node not in cache:
            cache[node] = not is_blocked(node[0] * tile_size + tile_size / 2,
                                         node[1] * tile_size + tile_size / 2)
        return cache[node]

    if not passable(goal_node):
        return None
    if start_node == goal_node:
        return [tuple(goal)]

    def heuristic(node):
        dx = abs(node[0] - goal_node[0])
        dy = abs(node[1] - goal_node[1])
        return max(dx, dy) + (_SQRT2 - 1) * min(dx, dy)

    open_heap = [(heuristic(start_node), 0.0, start_node)]
    best_cost = {start_node: 0.0}
    parent = {}
    closed = set()
    expanded = 0
    while open_heap:
        _, cost, node = heapq.heappop(open_heap)
        if node in closed:
            continue
        if node == goal_node:
            nodes = [node]
            while nodes[-1] in parent:
                nodes.append(parent[nodes[-1]])
            nodes.reverse()
            path = [(n[0] * tile_size + tile_size / 2, n[1] * tile_size + tile_size / 2) for n in nodes[1:]]
            path[-1] = tuple(goal)
            return path
        closed.add(node)
        expanded += 1
        if expanded > max_nodes:
            return None
        for dx, dy in _NEIGHBORS:
            nb = (node[0] + dx, node[1] + dy)
            if nb in closed or not passable(nb):
                continue
            # Без срезания углов: по диагонали нельзя протискиваться между двумя блоками
            if dx and dy and (not passable((node[0] + dx, node[1])) or not passable((node[0], node[1] + dy))):
                continue
            new_cost = cost + (_SQRT2 if dx and dy else 1.0)
            if new_cost < best_cost.get(nb, math.inf):
                best_cost[nb] = new_cost
                parent[nb] = node
                heapq.heappush(open_heap, (new_cost + heuristic(nb), new_cost, nb))
    return None


def follow_path(x, y, path, step, is_blocked):
    """Двигает точку по списку точек path не дальше step px за кадр.

    Пройденные точки удаляются из path (список изменяется на месте).
    Возвращает (x, y, moved). Если путь перекрыт, точка останавливается.
    """
    moved = False
    budget = step
    while path and budget > 0:
        tx, ty = path[0]
        dist = math.hypot(tx - x, ty - y)
        if dist <= budget:
            if is_blocked(tx, ty):
                break
            x, y = tx, ty
            budget -= dist
            path.pop(0)
            moved = True
            continue
        x, y, step_moved = move_with_collision(x, y, (tx - x) / dist, (ty - y) / dist, budget, is_blocked)
        moved = moved or step_moved
        break
    return x, y, moved
