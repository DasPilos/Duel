extends RefCounted

# Контуры участков производственного окна: порт plot_geometry и *_geometry из ui/production_building_window.py.
# Координаты локальные для холста. Пиксельные размеры Python (разлом, загон, копанки, тележка) умножаются
# на масштаб области, потому что холст ниже окна Python. Участок: points — полигон, rect — габарит,
# center — точка внутри, house_y — ряд домиков, tent — палатка разлома.

const PY_AREA_WIDTH := 1380.0
const PY_AREA_HEIGHT := 806.0
const HOUSE_SIZE := 28.0
const INNER_RADIUS := 0.58
const PIE_GAP := 0.012

# Положение полей (доли области): x, y, ширина, высота.
const FARM_FIELD_LAYOUT := [
	[0.42, 0.36, 0.15, 0.22],
	[0.60, 0.38, 0.11, 0.17],
	[0.28, 0.40, 0.11, 0.17],
	[0.43, 0.08, 0.11, 0.17],
	[0.45, 0.68, 0.11, 0.17],
	[0.24, 0.06, 0.15, 0.22],
	[0.59, 0.06, 0.15, 0.22],
	[0.23, 0.64, 0.18, 0.28],
	[0.60, 0.64, 0.18, 0.28],
	[0.02, 0.08, 0.18, 0.30],
	[0.80, 0.10, 0.18, 0.30],
	[0.02, 0.52, 0.18, 0.30],
]

# Центры копанок Чёрной копи (доли области) в порядке открытия.
const DIG_LAYOUT := [
	[0.50, 0.50], [0.33, 0.42], [0.66, 0.40], [0.42, 0.76], [0.62, 0.74],
	[0.20, 0.72], [0.82, 0.68], [0.22, 0.22], [0.80, 0.24], [0.50, 0.17],
]

# Прииски вдоль ущелья: [доля пути от входа, сторона: -1 северо-запад, +1 юго-восток].
const RIFT_MINE_LAYOUT := {
	"iron_mine": [0.22, -1],
	"stone_mine": [0.34, 1],
	"mithril_mine": [0.62, -1],
	"obsidian_mine": [0.8, 1],
}


static func scale_for(area: Rect2) -> float:
	return minf(area.size.x / PY_AREA_WIDTH, area.size.y / PY_AREA_HEIGHT)


# shape — форма из справочника; max_workers — горожане текущего уровня (нужны загону).
static func build(shape: String, area: Rect2, groups: Array, max_workers: int) -> Array:
	match shape:
		"pie":
			return _pie(area, groups)
		"rift":
			return _rift(area, groups)
		"pen":
			return _pen(area, groups, max_workers)
		"digs":
			return _digs(area, groups)
	return _fields(area, groups)


static func rift_axis(area: Rect2) -> Dictionary:
	var start := Vector2(area.position.x + area.size.x * 0.06, area.end.y - area.size.y * 0.02)
	var finish := Vector2(area.end.x - area.size.x * 0.08, area.position.y + area.size.y * 0.1)
	var along := (finish - start).normalized()
	return {"start": start, "end": finish, "along": along, "normal": Vector2(-along.y, along.x)}


# Фон разлома в локальных координатах: гора, ущелье и валуны. Порядок команд повторяет _rift_backdrop в Python.
static func rift_backdrop(size: Vector2) -> Array:
	var commands: Array = []
	var rng := _rng("rift".hash())
	var ridge := PackedVector2Array([Vector2(0.0, size.y)])
	for step in range(13):
		ridge.append(Vector2(size.x * step / 12.0,
			size.y * (0.05 + 0.18 * absf(sin(step * 1.7))) + rng.randf_range(0.0, 30.0)))
	ridge.append(Vector2(size.x, size.y))
	commands.append({"type": "polygon", "points": ridge, "color": Color8(74, 68, 64)})
	for _i in range(60):
		var x := rng.randf_range(0.0, size.x)
		var y := rng.randf_range(size.y * 0.25, size.y)
		var width := rng.randf_range(30.0, 90.0)
		var shade := rng.randi_range(-14, 13)
		commands.append({"type": "polygon", "color": Color8(78 + shade, 72 + shade, 68 + shade),
			"points": PackedVector2Array([Vector2(x - width, y), Vector2(x - width * 0.2, y - width * 0.7), Vector2(x + width, y)])})
	var axis := rift_axis(Rect2(Vector2.ZERO, size))
	var start: Vector2 = axis["start"]
	var finish: Vector2 = axis["end"]
	var normal: Vector2 = axis["normal"]
	var left_edge := PackedVector2Array()
	var right_edge := PackedVector2Array()
	for step in range(25):
		var along_t := step / 24.0
		var half := 95.0 - 55.0 * along_t + rng.randf_range(-10.0, 10.0)
		var spine := start.lerp(finish, along_t)
		left_edge.append(spine - normal * half)
		right_edge.append(spine + normal * (half + rng.randf_range(-8.0, 8.0)))
	var canyon := left_edge.duplicate()
	for index in range(right_edge.size() - 1, -1, -1):
		canyon.append(right_edge[index])
	var shadow := PackedVector2Array()
	for point in canyon:
		shadow.append(point + normal * 18.0)
	commands.append({"type": "polygon", "points": shadow, "color": Color8(34, 28, 26)})
	commands.append({"type": "polygon", "points": canyon, "color": Color8(112, 92, 68)})
	commands.append({"type": "line", "points": left_edge, "color": Color8(44, 38, 34), "width": 4.0})
	commands.append({"type": "line", "points": right_edge, "color": Color8(44, 38, 34), "width": 4.0})
	for _i in range(40):
		var t := rng.randf_range(0.02, 0.98)
		var offset := rng.randf_range(-40.0, 40.0) * (1.0 - t * 0.6)
		commands.append({"type": "circle", "center": start.lerp(finish, t) + normal * offset,
			"radius": float(rng.randi_range(3, 7)), "color": Color8(90, 76, 58)})
	return commands


static func _fields(area: Rect2, groups: Array) -> Array:
	var plots: Array = []
	for index in range(mini(groups.size(), FARM_FIELD_LAYOUT.size())):
		var layout: Array = FARM_FIELD_LAYOUT[index]
		var field := Rect2(area.position + Vector2(layout[0] * area.size.x, layout[1] * area.size.y),
			Vector2(layout[2] * area.size.x, layout[3] * area.size.y))
		var rng := _rng(index * 7 + 3)
		var points := PackedVector2Array()
		for step in range(10):
			var angle := TAU * step / 10.0 + rng.randf_range(-0.12, 0.12)
			var radius := rng.randf_range(0.86, 1.0)
			points.append(field.get_center() + Vector2(
				_signed_pow(cos(angle)) * field.size.x / 2.0 * radius,
				_signed_pow(sin(angle)) * field.size.y / 2.0 * radius))
		plots.append(_plot(points, field.get_center(), field.end.y + 2.0))
	return plots


static func _pie(area: Rect2, groups: Array) -> Array:
	var center := area.get_center()
	var radius := Vector2(PY_AREA_WIDTH * 0.36, PY_AREA_HEIGHT * 0.47) * scale_for(area)
	var rng := _rng("pie".hash())
	var phases := [rng.randf_range(0.0, TAU), rng.randf_range(0.0, TAU), rng.randf_range(0.0, TAU)]
	var plots: Array = []
	plots.resize(groups.size())
	for item in _pie_slices(groups, "edge", -PI / 2.0):
		var arc := _arc(item[1], item[2], 18.0)
		var points := PackedVector2Array()
		for angle in arc:
			points.append(_polar(center, radius, angle, _edge(angle, phases)))
		arc.reverse()
		for angle in arc:
			points.append(_polar(center, radius, angle, _inner(angle, phases) + 0.02))
		var mid: float = (item[1] + item[2]) / 2.0
		var mid_point := _polar(center, radius, mid, (_edge(mid, phases) + _inner(mid, phases)) / 2.0)
		plots[item[0]] = _plot(points, mid_point, floorf(mid_point.y) + 14.0)
	for item in _pie_slices(groups, "inner", -PI / 2.0 + 0.3):
		var arc := _arc(item[1], item[2], 14.0)
		var mid: float = (item[1] + item[2]) / 2.0
		var points := PackedVector2Array([_polar(center, radius, mid, 0.05)])
		for angle in arc:
			points.append(_polar(center, radius, angle, _inner(angle, phases) - 0.02))
		var mid_point := _polar(center, radius, mid, INNER_RADIUS * 0.55)
		plots[item[0]] = _plot(points, mid_point, floorf(mid_point.y) + 14.0)
	return plots


static func _rift(area: Rect2, groups: Array) -> Array:
	var factor := scale_for(area)
	var axis := rift_axis(area)
	var start: Vector2 = axis["start"]
	var finish: Vector2 = axis["end"]
	var along: Vector2 = axis["along"]
	var normal: Vector2 = axis["normal"]
	var plots: Array = []
	for index in range(groups.size()):
		var layout: Array = RIFT_MINE_LAYOUT[groups[index]["kind"]]
		var side: float = layout[1]
		var point := start.lerp(finish, layout[0]) + normal * side * 230.0 * factor
		point.x = clampf(point.x, area.position.x + 180.0 * factor, area.end.x - 180.0 * factor)
		point.y = clampf(point.y, area.position.y + 130.0 * factor, area.end.y - 130.0 * factor)
		var rng := _rng(index * 11 + 5)
		var points := PackedVector2Array()
		for step in range(14):
			var angle := TAU * step / 14.0
			points.append(point + Vector2(cos(angle) * 165.0, sin(angle) * 115.0) * rng.randf_range(0.82, 1.0) * factor)
		var plot := _plot(points, point, point.y + 40.0 * factor)
		plot["tent"] = point + (-normal * side * 70.0 + along * 95.0) * factor
		plots.append(plot)
	return plots


# Загон: площадь пропорциональна горожанам текущего уровня; на 10 уровне почти всё поле.
static func _pen(area: Rect2, groups: Array, max_workers: int) -> Array:
	var factor := 0.92 * sqrt(float(max_workers) / maxf(1.0, float(groups[0]["places"])))
	var field := Rect2(area.position, Vector2(area.size.x, area.size.y - HOUSE_SIZE - 16.0))
	var pen_size := Vector2(int(field.size.x * factor), int(field.size.y * factor))
	var pen := Rect2(field.get_center() - pen_size / 2.0, pen_size)
	var points := PackedVector2Array([pen.position, Vector2(pen.end.x, pen.position.y), pen.end, Vector2(pen.position.x, pen.end.y)])
	return [_plot(points, pen.get_center(), pen.end.y + 8.0)]


static func _digs(area: Rect2, groups: Array) -> Array:
	var factor := scale_for(area)
	var plots: Array = []
	for index in range(mini(groups.size(), DIG_LAYOUT.size())):
		var layout: Array = DIG_LAYOUT[index]
		var center := area.position + Vector2(layout[0] * area.size.x, layout[1] * area.size.y)
		var rx := 62.0 * sqrt(float(groups[index]["places"])) * factor
		var ry := rx * 0.6
		var rng := _rng(index * 13 + 1)
		var points := PackedVector2Array()
		for step in range(12):
			var angle := TAU * step / 12.0
			points.append(center + Vector2(cos(angle) * rx, sin(angle) * ry) * rng.randf_range(0.82, 1.0))
		plots.append(_plot(points, center, floorf(center.y + ry) + 4.0))
	return plots


# Дуги вида: доля круга пропорциональна местам; возвращает [индекс группы, начало, конец].
static func _pie_slices(groups: Array, kind: String, start_angle: float) -> Array:
	var indices: Array = []
	var total := 0.0
	for index in range(groups.size()):
		if str(groups[index]["kind"]) == kind:
			indices.append(index)
			total += float(groups[index]["places"])
	var slices: Array = []
	var angle := start_angle
	for index in indices:
		var span := TAU * float(groups[index]["places"]) / total
		slices.append([index, angle + PIE_GAP, angle + span - PIE_GAP])
		angle += span
	return slices


static func _arc(start_angle: float, end_angle: float, density: float) -> Array:
	var steps := maxi(6, int((end_angle - start_angle) * density))
	var arc: Array = []
	for step in range(steps + 1):
		arc.append(start_angle + (end_angle - start_angle) * step / steps)
	return arc


static func _polar(center: Vector2, radius: Vector2, angle: float, factor: float) -> Vector2:
	return center + Vector2(cos(angle) * radius.x, sin(angle) * radius.y) * factor


static func _edge(angle: float, phases: Array) -> float:
	return 0.92 + 0.06 * sin(3.0 * angle + phases[0]) + 0.04 * sin(5.0 * angle + phases[1]) + 0.025 * sin(9.0 * angle + phases[2])


static func _inner(angle: float, phases: Array) -> float:
	return INNER_RADIUS + 0.03 * sin(4.0 * angle + phases[1])


static func _plot(points: PackedVector2Array, center: Vector2, house_y: float) -> Dictionary:
	var low := points[0]
	var high := points[0]
	for point in points:
		low = low.min(point)
		high = high.max(point)
	return {"points": points, "rect": Rect2(low, high - low + Vector2(2.0, 2.0)), "center": center, "house_y": house_y}


static func _rng(seed_value: int) -> RandomNumberGenerator:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	return rng


static func _signed_pow(value: float) -> float:
	return signf(value) * pow(absf(value), 0.55)
