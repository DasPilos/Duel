"""Серверная прокладка грунтовых дорог от нецентральных ворот Радбурга к загородным зданиям."""

import heapq
import math
import random
from functools import lru_cache

from core.city_progression import COUNTRY_BUILDING_UNLOCK_LEVELS, unlocked_country_buildings
from core.production_buildings import RESOURCES, building_resources
from server.structures import WORLD_OBJECTS
from server.world_map import OBSTACLES, TILE, _edge_distance, point_in_polygon

MAP_WIDTH_TILES = 512
MAP_HEIGHT_TILES = 256
ROAD_SPEED_SECONDS_PER_TILE = 60

# Главные восточные ворота ('east') намеренно исключены.
CITY_GATES = {
    "north": (67, 46),
    "west": (60, 53),
    "south": (67, 60),
}
COUNTRY_BUILDINGS = tuple(COUNTRY_BUILDING_UNLOCK_LEVELS)
FORCED_GATES = {"black_pit": "west"}
PRODUCTION_BUILDING_IDS = {"wheat_farm": "farm"}

_MOVES = (
    (-1, -1, math.sqrt(2)), (0, -1, 1), (1, -1, math.sqrt(2)),
    (-1, 0, 1), (1, 0, 1),
    (-1, 1, math.sqrt(2)), (0, 1, 1), (1, 1, math.sqrt(2)),
)


def _cell_rect(x, y):
    return x * TILE, y * TILE, TILE, TILE


def _rects_intersect(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


@lru_cache(maxsize=1)
def _blocked_cells(clearance_obstacle_ids=()):
    clearance_obstacle_ids = frozenset(clearance_obstacle_ids)
    blocked = set()
    for obstacle in OBSTACLES:
        xs = [point[0] for point in obstacle["points"]]
        ys = [point[1] for point in obstacle["points"]]
        clearance = 2 * TILE if obstacle["id"] in clearance_obstacle_ids else 0
        x_start = max(0, (min(xs) - clearance) // TILE)
        x_end = min(MAP_WIDTH_TILES - 1, (max(xs) + clearance) // TILE)
        y_start = max(0, (min(ys) - clearance) // TILE)
        y_end = min(MAP_HEIGHT_TILES - 1, (max(ys) + clearance) // TILE)
        passages = obstacle.get("passages", [])
        for tile_y in range(y_start, y_end + 1):
            for tile_x in range(x_start, x_end + 1):
                center = (tile_x * TILE + TILE // 2, tile_y * TILE + TILE // 2)
                inside = point_in_polygon(center, obstacle["points"]) and not any(
                    passage[0] <= center[0] < passage[0] + passage[2]
                    and passage[1] <= center[1] < passage[1] + passage[3]
                    for passage in passages
                )
                near = clearance and _edge_distance(center[0], center[1], obstacle["points"]) < clearance
                if inside or near:
                    blocked.add((tile_x, tile_y))

    solids = [rect for obj in WORLD_OBJECTS for rect in obj.get("solid_rects", [])]
    for rect in solids:
        x, y, width, height = rect
        for tile_y in range(max(0, y // TILE), min(MAP_HEIGHT_TILES, (y + height + TILE - 1) // TILE)):
            for tile_x in range(max(0, x // TILE), min(MAP_WIDTH_TILES, (x + width + TILE - 1) // TILE)):
                if _rects_intersect(_cell_rect(tile_x, tile_y), rect):
                    blocked.add((tile_x, tile_y))
    return frozenset(blocked)


def _heuristic(a, b):
    dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
    return max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)


def _path_distance(path):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:]))


def _find_path(start, goal, blocked, route_seed):
    if start in blocked or goal in blocked:
        return None
    queue = [(0.0, 0.0, start)]
    came_from = {start: None}
    costs = {start: 0.0}
    directions = {start: None}
    roughness = {}

    while queue:
        _priority, current_cost, current = heapq.heappop(queue)
        if current_cost != costs.get(current):
            continue
        if current == goal:
            path = []
            while current is not None:
                path.append(current)
                current = came_from[current]
            return list(reversed(path))

        previous_direction = directions[current]
        for dx, dy, step_cost in _MOVES:
            neighbor = current[0] + dx, current[1] + dy
            if not (0 <= neighbor[0] < MAP_WIDTH_TILES and 0 <= neighbor[1] < MAP_HEIGHT_TILES):
                continue
            if neighbor in blocked:
                continue
            if dx and dy and ((current[0] + dx, current[1]) in blocked or (current[0], current[1] + dy) in blocked):
                continue
            direction = (dx, dy)
            bend_cost = 0.10 if previous_direction is not None and previous_direction != direction else 0
            if neighbor not in roughness:
                roughness[neighbor] = random.Random(route_seed ^ (neighbor[0] * 73856093) ^ (neighbor[1] * 19349663)).random() * 0.11
            next_cost = current_cost + step_cost + bend_cost + roughness[neighbor]
            if next_cost >= costs.get(neighbor, float("inf")):
                continue
            costs[neighbor] = next_cost
            came_from[neighbor] = current
            directions[neighbor] = direction
            heapq.heappush(queue, (next_cost + _heuristic(neighbor, goal), next_cost, neighbor))
    return None


def _nearest_passable(point, blocked):
    goal = int(point[0] // TILE), int(point[1] // TILE)
    if goal not in blocked:
        return goal
    for radius in range(1, 8):
        candidates = []
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if max(abs(dx), abs(dy)) != radius:
                    continue
                cell = goal[0] + dx, goal[1] + dy
                if 0 <= cell[0] < MAP_WIDTH_TILES and 0 <= cell[1] < MAP_HEIGHT_TILES and cell not in blocked:
                    candidates.append(cell)
        if candidates:
            return min(candidates, key=lambda cell: (cell[0] - goal[0]) ** 2 + (cell[1] - goal[1]) ** 2)
    return None


@lru_cache(maxsize=1)
def build_country_roads():
    """Для каждого загородного строения выбирает кратчайший маршрут от ближайших нецентральных ворот."""
    blocked = _blocked_cells()
    objects = {obj["id"]: obj for obj in WORLD_OBJECTS}
    routes = []
    all_tiles = set()
    for building_id in COUNTRY_BUILDINGS:
        route_blocked = (
            _blocked_cells(("lake_1", "forest_1", "mountains_1"))
            if building_id == "wheat_farm" else blocked
        )
        building = objects[building_id]
        target = _nearest_passable(building["approach_pos"], route_blocked)
        candidates = []
        if target is None:
            raise RuntimeError(f"Нет проходимого подхода к {building_id}")
        allowed_gates = (FORCED_GATES[building_id],) if building_id in FORCED_GATES else tuple(CITY_GATES)
        for gate_id in allowed_gates:
            gate_tile = CITY_GATES[gate_id]
            route_seed = sum((index + 1) * ord(char) for index, char in enumerate(building_id + gate_id))
            path = _find_path(gate_tile, target, route_blocked, route_seed)
            if path:
                candidates.append((_path_distance(path), gate_id, path))
        if not candidates:
            raise RuntimeError(f"Нет маршрута от нецентральных ворот к {building_id}")
        _length, gate_id, path = min(candidates, key=lambda item: item[0])
        all_tiles.update(path)
        entrance = tuple(building.get("entrance_tile", path[-1]))
        distance_tiles = _path_distance(path) + math.hypot(entrance[0] - path[-1][0], entrance[1] - path[-1][1])
        routes.append({
            "building_id": building_id,
            "name": building["name"],
            "gate_id": gate_id,
            "tiles": [list(tile) for tile in path],
            "distance_tiles": round(distance_tiles, 2),
            "distance_pixels": round(distance_tiles * TILE),
            "resources": [
                {"id": resource, "label": RESOURCES[resource]["label"]}
                for resource in building_resources(PRODUCTION_BUILDING_IDS.get(building_id, building_id))
            ],
        })
    return tuple(routes), tuple(sorted(all_tiles, key=lambda tile: (tile[1], tile[0])))


def roads_payload(city_level=1):
    routes, tiles = build_country_roads()
    unlocked = set(unlocked_country_buildings(city_level))
    routes = tuple(route for route in routes if route["building_id"] in unlocked)
    tiles = tuple(sorted({tuple(tile) for route in routes for tile in route["tiles"]},
                         key=lambda tile: (tile[1], tile[0])))
    return {
        "routes": [dict(route) for route in routes],
        "tiles": [list(tile) for tile in tiles],
        "travel_seconds": len(tiles) * ROAD_SPEED_SECONDS_PER_TILE,
    }


def route_position(building_id, progress, city_level=1):
    route = next(
        (route for route in roads_payload(city_level)["routes"]
         if route["building_id"] == building_id),
        None,
    )
    if route is None or not route["tiles"]:
        return None
    points = [((tile[0] + 0.5) * TILE, (tile[1] + 0.5) * TILE)
              for tile in route["tiles"]]
    if len(points) == 1:
        return points[0][0], points[0][1], "s"

    segments = [(start, end, math.dist(start, end))
                for start, end in zip(points, points[1:])]
    total = sum(length for _start, _end, length in segments)
    if total <= 0:
        return points[0][0], points[0][1], "s"
    distance = max(0.0, min(1.0, float(progress))) * total
    for start, end, length in segments:
        if distance <= length:
            fraction = 0.0 if length == 0 else distance / length
            dx, dy = end[0] - start[0], end[1] - start[1]
            if abs(dx) > abs(dy) * 2:
                direction = "e" if dx > 0 else "w"
            elif abs(dy) > abs(dx) * 2:
                direction = "s" if dy > 0 else "n"
            elif dx and dy:
                direction = ("s" if dy > 0 else "n") + ("e" if dx > 0 else "w")
            else:
                direction = "s"
            return start[0] + dx * fraction, start[1] + dy * fraction, direction
        distance -= length
    return points[-1][0], points[-1][1], "s"
