extends RefCounted

# Геометрия и правила HUD башни: порт scenes/world_map_scene.py (_draw_player_panel, _draw_minimap, _draw_coords_box,
# _build_minimap, _tiles_word) и ui/hotbar.py. Python рассчитан на окно 1920×1080, базовый вид Godot — 1280×720,
# поэтому размеры ниже уже умножены на 2/3 и округлены, как в hotbar.gd (43, 4, 7). В комментарии — исходное значение Python.

const TILE_SIZE := 32.0
const DEFAULT_GRID := Vector2i(125, 125)

const MINIMAP_HEIGHT := 128  # Python 192
const MINIMAP_MARGIN := 3  # Python 5

const PANEL_MARGIN := 3  # Python 5
const PANEL_GAP := 4  # Python 6
const PORTRAIT_SIZE := 85  # Python 128
const PORTRAIT_FIT := 80  # Python 128 - 8
const ICON_SIZE := 21  # Python 32 (ui/profession_icons.py)
const BAR_WIDTH := 160  # Python 240
const BAR_HEIGHT := 9  # Python 14
const BAR_INDENT := 3  # Python 4 между портретом и полосками
const BAR_STEP := 12  # Python bar_h + gap * 3
const LABEL_GAP := 1  # Python text_h + 2

const COORDS_LINES := 2
const COORDS_LINE_HEIGHT := 18  # высота строки шрифта 13 px в Godot
const COORDS_PAD_X := 11  # Python 16
const COORDS_PAD_Y := 6  # Python 9
const COORDS_WIDTH := 300  # резерв под самую длинную строку; Python подгоняет ширину под текст

const HOTBAR_COUNT := 10
const HOTBAR_SLOT := 43  # Python 64
const HOTBAR_GAP := 4  # Python 6
const HOTBAR_BOTTOM_MARGIN := 7  # Python 10

const DEFAULT_NAME := "Герой"


# Python round(): при ровном .5 берётся ближайшее чётное число.
static func py_round(value: float) -> int:
	var floor_value := floorf(value)
	var fraction := value - floor_value
	var result := floor_value
	if fraction > 0.5 or (fraction == 0.5 and fposmod(floor_value, 2.0) == 1.0):
		result += 1.0
	return int(result)


static func tiles_word(count: int) -> String:
	var last_two := posmod(count, 100)
	if last_two >= 11 and last_two <= 14:
		return "тайлов"
	var last := posmod(count, 10)
	if last == 1:
		return "тайл"
	if last >= 2 and last <= 4:
		return "тайла"
	return "тайлов"


static func tiles_label(count: int) -> String:
	return "%d %s" % [count, tiles_word(count)]


static func display_name(character: Dictionary) -> String:
	var value: Variant = character.get("name")
	if value == null or str(value).is_empty():
		return DEFAULT_NAME
	return str(value)


static func hp_label(value: float, maximum: float) -> String:
	return "%d/%d ХП" % [int(value), int(maximum)]


static func mp_label(value: float, maximum: float) -> String:
	return "%d/%d МП" % [int(value), int(maximum)]


# Делитель не меньше 1, как max(1, maximum) в Python.
static func bar_ratio(value: float, maximum: float) -> float:
	return clampf(value / maxf(1.0, maximum), 0.0, 1.0)


static func bar_fill_width(width: float, ratio: float) -> float:
	return float(int(width * ratio))


# Подгонка портрета по большей стороне, как в _draw_player_panel: минимум 1 px по каждой стороне.
static func fit_size(source: Vector2, fit: float) -> Vector2:
	if source.x <= 0.0 or source.y <= 0.0:
		return Vector2.ZERO
	var scale := minf(fit / source.x, fit / source.y)
	return Vector2(maxf(1.0, float(py_round(source.x * scale))), maxf(1.0, float(py_round(source.y * scale))))


static func fit_font_size(text_width: float, available: float, base_size: int) -> int:
	if text_width <= available or text_width <= 0.0:
		return base_size
	return maxi(8, floori(float(base_size) * available / text_width))


static func player_panel_rect() -> Rect2:
	return Rect2(
		PANEL_MARGIN,
		PANEL_MARGIN,
		PORTRAIT_SIZE + PANEL_GAP + BAR_INDENT + BAR_WIDTH,
		ICON_SIZE + PANEL_GAP + PORTRAIT_SIZE,
	)


static func minimap_size(height: int, grid: Vector2i) -> Vector2i:
	var width := maxi(1, py_round(float(height) * float(grid.x) / float(maxi(1, grid.y))))
	return Vector2i(width, height)


static func minimap_rect(view_size: Vector2, grid: Vector2i) -> Rect2:
	var size := Vector2(minimap_size(MINIMAP_HEIGHT, grid))
	return Rect2(MINIMAP_MARGIN, view_size.y - MINIMAP_MARGIN - size.y, size.x, size.y)


# Строка координат стоит над миникартой, левый край совпадает с ней (Python: bottomleft = (margin, minimap_top - margin)).
static func coords_rect(minimap: Rect2) -> Rect2:
	var height := COORDS_LINES * COORDS_LINE_HEIGHT + 2 * COORDS_PAD_Y
	return Rect2(minimap.position.x, minimap.position.y - MINIMAP_MARGIN - height, COORDS_WIDTH, height)


static func hotbar_rect(view_size: Vector2) -> Rect2:
	var total := HOTBAR_COUNT * HOTBAR_SLOT + (HOTBAR_COUNT - 1) * HOTBAR_GAP
	var left := floorf((view_size.x - total) / 2.0)
	var top := view_size.y - HOTBAR_BOTTOM_MARGIN - HOTBAR_SLOT
	return Rect2(left, top, total, HOTBAR_SLOT)


static func hotbar_slot_rects(hotbar: Rect2) -> Array[Rect2]:
	var result: Array[Rect2] = []
	for index in HOTBAR_COUNT:
		result.append(Rect2(
			hotbar.position.x + index * (HOTBAR_SLOT + HOTBAR_GAP),
			hotbar.position.y,
			HOTBAR_SLOT,
			HOTBAR_SLOT,
		))
	return result


static func layout(view_size: Vector2, grid: Vector2i) -> Dictionary:
	var minimap := minimap_rect(view_size, grid)
	return {
		"player_panel": player_panel_rect(),
		"minimap": minimap,
		"coords": coords_rect(minimap),
		"hotbar": hotbar_rect(view_size),
	}


static func tile_scale(size: Vector2i, grid: Vector2i) -> Vector2:
	return Vector2(float(size.x) / float(grid.x), float(size.y) / float(grid.y))


# Прямоугольник тайла в пикселях миникарты: не меньше 1 px, края берутся обрезкой, как в _minimap_tile_rect.
static func minimap_tile_rect(tile: Vector2i, scale: Vector2) -> Rect2i:
	var left := int(tile.x * scale.x)
	var top := int(tile.y * scale.y)
	var right := maxi(left + 1, int((tile.x + 1) * scale.x))
	var bottom := maxi(top + 1, int((tile.y + 1) * scale.y))
	return Rect2i(left, top, right - left, bottom - top)


static func world_to_minimap(world: Vector2, rect: Rect2, world_size: Vector2) -> Vector2:
	return rect.position + world * (rect.size / world_size)


static func corpse_distance_tiles(corpse_world: Vector2, player_world: Vector2) -> float:
	return corpse_world.distance_to(player_world) / TILE_SIZE


static func coords_lines(cursor_world: Vector2, player_world: Vector2) -> PackedStringArray:
	var cursor_tile := Vector2i(floori(cursor_world.x / TILE_SIZE), floori(cursor_world.y / TILE_SIZE))
	var player_tile := Vector2i(floori(player_world.x / TILE_SIZE), floori(player_world.y / TILE_SIZE))
	return PackedStringArray([
		"Курсор: X=%d, Y=%d (тайл: %d, %d)" % [int(cursor_world.x), int(cursor_world.y), cursor_tile.x, cursor_tile.y],
		"Персонаж: X=%d, Y=%d (тайл: %d, %d)" % [int(player_world.x), int(player_world.y), player_tile.x, player_tile.y],
	])


# Строки Python-рядов [y, x_начало, x_конец] (включительно) → тайлы Vector2i(x, y).
static func tiles_from_rows(rows: Variant) -> Array[Vector2i]:
	var result: Array[Vector2i] = []
	if not rows is Array:
		return result
	for row in rows:
		if row is Array and row.size() >= 3:
			for tile_x in range(int(row[1]), int(row[2]) + 1):
				result.append(Vector2i(tile_x, int(row[0])))
	return result


# Пары [x, y] → тайлы Vector2i(x, y).
static func tiles_from_pairs(pairs: Variant) -> Array[Vector2i]:
	var result: Array[Vector2i] = []
	if not pairs is Array:
		return result
	for pair in pairs:
		if pair is Array and pair.size() >= 2:
			result.append(Vector2i(int(pair[0]), int(pair[1])))
	return result


# Заливка многоугольника как pygame.draw.polygon: вершины обрезаются до целых, для строки row берутся пересечения
# рёбер с полуоткрытым условием, пары x заливаются включительно. Контур pygame по краю не повторяется,
# поэтому отличия от Python — только пограничные пиксели.
static func polygon_row_spans(vertices: PackedVector2Array, row: int) -> Array[Vector2i]:
	var spans: Array[Vector2i] = []
	var count := vertices.size()
	var crossings: Array[float] = []
	for index in count:
		var start := vertices[(index + count - 1) % count]
		var finish := vertices[index]
		var start_y := int(start.y)
		var finish_y := int(finish.y)
		if (start_y < row and finish_y >= row) or (finish_y < row and start_y >= row):
			var start_x := float(int(start.x))
			var finish_x := float(int(finish.x))
			crossings.append(start_x + float(row - start_y) * (finish_x - start_x) / float(finish_y - start_y))
	crossings.sort()
	for pair in range(0, crossings.size() - 1, 2):
		spans.append(Vector2i(int(crossings[pair]), int(crossings[pair + 1])))
	return spans
