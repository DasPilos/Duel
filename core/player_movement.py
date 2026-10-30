import heapq
import math

_SQRT2 = math.sqrt(2)
_NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
# Доли тайла, где проверяем ход в частично проходимом тайле: центр первым, затем сетка 3×3
_SAMPLE_FRACTIONS = ((0.5, 0.5), (0.25, 0.25), (0.5, 0.25), (0.75, 0.25), (0.25, 0.5),
                     (0.75, 0.5), (0.25, 0.75), (0.5, 0.75), (0.75, 0.75))


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


def find_tile_path(start, goal, is_blocked, tile_size=32, max_nodes=2500, partial_tiles=None):
    """A* по сетке тайлов от start до goal (мировые координаты).

    Возвращает список точек пути, последняя точка — goal. None, если цель заблокирована
    или путь не найден в пределах max_nodes раскрытых тайлов.
    is_blocked(x, y) проверяет точку мира; результаты кэшируются на время одного поиска.
    partial_tiles — тайлы с частичной проходимостью: в них проходимым считается любой тайл-участок.
    """
    start_node = (int(start[0] // tile_size), int(start[1] // tile_size))
    goal_node = (int(goal[0] // tile_size), int(goal[1] // tile_size))
    points = {}

    def free_point(node):
        """Первая свободная точка тайла (центр, если он свободен) или None."""
        if node not in points:
            partial = bool(partial_tiles) and node in partial_tiles
            fractions = _SAMPLE_FRACTIONS if partial else _SAMPLE_FRACTIONS[:1]
            points[node] = None
            for fx, fy in fractions:
                point = (node[0] * tile_size + fx * tile_size, node[1] * tile_size + fy * tile_size)
                if not is_blocked(*point):
                    points[node] = point
                    break
        return points[node]

    def passable(node):
        return free_point(node) is not None

    if not passable(goal_node):
        return None
    if start_node == goal_node:
        return [tuple(goal)]
    goal_point = tuple(goal)
    if bool(partial_tiles) and goal_node in partial_tiles and is_blocked(*goal_point):
        goal_point = free_point(goal_node)

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
            path = [free_point(n) for n in nodes[1:]]
            path[-1] = goal_point
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
