extends RefCounted
# Город Радбург на карте мира: объект town_radburg из terrain.objects (server/structures.py, WORLD_OBJECTS),
# геометрия draw_city_exterior (scenes/city/exterior.py), подпись, наведение и обводка из _draw_objects и
# _find_entity_at (scenes/world_map_scene.py). Все размеры в пикселях Python; масштаб мира задаёт вызывающий код.

const TILE_PX := 16
const TOWN_ID := "town_radburg"
const SCALE_REFERENCE_PX := 480.0
const HOVER_TOP_PX := 22.0
const BADGE_GAP_PX := 12.0
const BADGE_FONT_PX := 13
const BADGE_PAD_PX := Vector2(5.0, 2.0)
const BADGE_BACKGROUND := Color8(12, 14, 18)
const BADGE_TEXT := Color8(240, 240, 240)
const BADGE_DEFAULT := Color8(220, 200, 160)
const BADGE_HOVER := Color8(100, 200, 255)
const OUTLINE_BORDER_PX := 2
const OUTLINE_RADIUS_PX := 8
const OUTLINE_DEFAULT := Color8(100, 125, 155)
const OUTLINE_HOVER := Color8(80, 200, 255)
const HOUSE_SPOTS := [
	Vector2(0.17, 0.17), Vector2(0.83, 0.17), Vector2(0.17, 0.83), Vector2(0.83, 0.83),
	Vector2(0.50, 0.14), Vector2(0.50, 0.86), Vector2(0.14, 0.50), Vector2(0.86, 0.50),
	Vector2(0.27, 0.17), Vector2(0.73, 0.83),
]
# Окно активного объекта (active_window_rect, active_close_button, active_action_button в Python); величины в px Python.
const WINDOW_SIZE_PY := Vector2(365.0, 215.0)
const WINDOW_RIGHT_PY := 25.0
const WINDOW_BOTTOM_PY := 40.0
const CLOSE_RIGHT_PY := 36.0
const CLOSE_TOP_PY := 10.0
const CLOSE_SIZE_PY := 26.0
const ACTION_INSET_PY := 16.0
const ACTION_BOTTOM_PY := 48.0
const ACTION_HEIGHT_PY := 34.0
const ENTER_LABEL := "ВОЙТИ В ГОРОД"
const STATUS_TEXT := "● АКТИВЕН"
const IN_RANGE_TEXT := "● В радиусе действия (<= 1 тайл)"
const OUT_OF_RANGE_TEXT := "○ Слишком далеко"
const DESC_LINE_CHARS := 42
const RANGE_TILES := 2  # один тайл по старой сетке 32 px = две клетки по 16 px
const NOTICE_SECONDS := 2.2
const FLOATING_SECONDS := 1.9
const TOO_FAR_PHRASES := [
	"Слишком далеко", "Мне не достать", "Нужно подойти ближе", "Это далеко", "Не дотянуться",
	"Сначала надо подойти", "Слишком большое расстояние", "Я не достаю отсюда", "Надо подойти вплотную",
	"Туда отсюда не достать",
]
const ACTIVE_OUTLINE := Color8(255, 215, 60)
const ACTIVE_BORDER_PX := 3
const BADGE_ACTIVE := Color8(255, 215, 60)


static func town_objects(objects: Array) -> Array:
	var towns: Array = []
	for map_object in objects:
		if map_object is Dictionary and str(map_object.get("id", "")) == TOWN_ID:
			towns.append(map_object)
	return towns


static func object_rect(map_object: Dictionary) -> Rect2:
	return Rect2(
		float(map_object.get("tile_x", 0)) * TILE_PX,
		float(map_object.get("tile_y", 0)) * TILE_PX,
		float(map_object.get("tile_w", 1)) * TILE_PX,
		float(map_object.get("tile_h", 1)) * TILE_PX,
	)


# Область наведения как в _find_entity_at: тело объекта с подъёмом на 22 px вверх.
static func hover_rect(map_object: Dictionary) -> Rect2:
	var rect := object_rect(map_object)
	return Rect2(rect.position.x, rect.position.y - HOVER_TOP_PX, rect.size.x, rect.size.y + HOVER_TOP_PX)


# Прямоугольники solid_rects города. Python применяет их к объектам карты в _check_collision (hydrate_structures
# превращает их в pygame.Rect). Здесь берутся только объекты, которые рисуются: остальные пока без коллизии.
static func solid_rects(objects: Array) -> Array:
	var rects: Array = []
	for map_object in town_objects(objects):
		for rect in map_object.get("solid_rects", []):
			if rect is Array and rect.size() >= 4:
				rects.append([int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])])
	return rects


static func city_level(visual: Dictionary) -> int:
	return maxi(1, int(visual.get("city_level", 1)))


# Ярусы отрисовки стен и жилых домов: 1 или 2, как city_visual_tier в scenes/city/sprite_modules.py.
static func tier(level: int) -> int:
	return clampi(level, 1, 2)


static func badge_text(level: int) -> String:
	return "Город Радбург · ур. %d" % level


static func scale_for(rect: Rect2) -> float:
	return maxf(0.2, minf(rect.size.x, rect.size.y) / SCALE_REFERENCE_PX)


static func inset_for(unit: float) -> int:
	return maxi(3, roundi(12.0 * unit))


# Внутренняя область: rect.inflate(-2 * inset, -2 * inset) из pygame, центр сохраняется.
static func bounds_for(rect: Rect2, inset: int) -> Rect2:
	return Rect2(rect.position + Vector2(inset, inset), rect.size - Vector2(2 * inset, 2 * inset))


# Ворота в порядке scenes/city/exterior.py: север, юг, запад, восток.
static func gate_rects(bounds: Rect2, unit: float) -> Array:
	var width := maxi(8, roundi(48.0 * unit))
	var height := maxi(6, roundi(24.0 * unit))
	var mid_x := center_x(bounds)
	var mid_y := center_y(bounds)
	var across := floori(width / 2.0)
	return [
		Rect2(mid_x - across, bounds.position.y - 1.0, width, height),
		Rect2(mid_x - across, bounds.end.y - height + 1.0, width, height),
		Rect2(bounds.position.x - 1.0, mid_y - across, height, width),
		Rect2(bounds.end.x - height + 1.0, mid_y - across, height, width),
	]


# Угловые башни: левый верх, правый верх, левый низ, правый низ.
static func tower_rects(bounds: Rect2, unit: float) -> Array:
	var size := maxi(12, roundi(72.0 * unit))
	return [
		Rect2(bounds.position.x, bounds.position.y, size, size),
		Rect2(bounds.end.x - size, bounds.position.y, size, size),
		Rect2(bounds.position.x, bounds.end.y - size, size, size),
		Rect2(bounds.end.x - size, bounds.end.y - size, size, size),
	]


static func house_rects(bounds: Rect2, level_tier: int, unit: float) -> Array:
	var size := maxi(7, roundi(42.0 * unit))
	var count := 4 if level_tier == 1 else 7
	var across := floorf(size / 2.0)
	var rects: Array = []
	for index in count:
		var spot: Vector2 = HOUSE_SPOTS[index]
		var center := Vector2(
			roundf(bounds.position.x + bounds.size.x * spot.x),
			roundf(bounds.position.y + bounds.size.y * spot.y),
		)
		rects.append(Rect2(center.x - across, center.y - across, size, size))
	return rects


# Донжон в центре: pygame keep.center = bounds.center, размер min(w, h) * 0.38.
static func keep_rect(bounds: Rect2) -> Rect2:
	var size := maxi(24, roundi(minf(bounds.size.x, bounds.size.y) * 0.38))
	var across := floorf(size / 2.0)
	return Rect2(center_x(bounds) - across, center_y(bounds) - across, size, size)


# Какие стены рисовать по city_visual_state (порядок веток draw_city_exterior):
# stone — уровень 3 и выше; upgrade — стадии 2→3 (stone, building, wood по сторонам);
# completed — ярус 2 без улучшения; level1 — ярус 1 с завершёнными сторонами, траншеей и бревнами.
static func wall_plan(visual: Dictionary) -> Dictionary:
	var level := city_level(visual)
	var level_tier := tier(level)
	var active := bool(visual.get("active", false))
	var phase := mini(3, int(visual.get("phase_index", 0))) if active else -1
	if level >= 3:
		return {"kind": "stone", "tier": level_tier}
	if active and level == 2:
		var stages: Array = []
		for side in 4:
			stages.append("stone" if side < phase else ("building" if side == phase else "wood"))
		return {"kind": "upgrade", "tier": level_tier, "stages": stages}
	if level_tier >= 2:
		return {"kind": "completed", "tier": level_tier}
	var completed: Array = []
	if active and phase == 2:
		completed = [1, 2]
	elif active and phase == 3:
		completed = [1, 2, 3]
	var work_sides: Array = []
	if active and phase != 0:
		for side in 4:
			if not completed.has(side):
				work_sides.append(side)
	return {
		"kind": "level1",
		"tier": 1,
		"completed": completed,
		"trench": active and phase == 0,
		"work_sides": work_sides,
	}


static func center_x(rect: Rect2) -> int:
	return floori(rect.position.x + floorf(rect.size.x / 2.0))


static func center_y(rect: Rect2) -> int:
	return floori(rect.position.y + floorf(rect.size.y / 2.0))


# Окно справа снизу с отступами как active_window_rect в Python (WIDTH - 390, HEIGHT - 255).
static func window_rect(view_size: Vector2, ui_scale: float) -> Rect2:
	var window_size := WINDOW_SIZE_PY * ui_scale
	return Rect2(
		view_size.x - WINDOW_RIGHT_PY * ui_scale - window_size.x,
		view_size.y - WINDOW_BOTTOM_PY * ui_scale - window_size.y,
		window_size.x,
		window_size.y,
	)


static func window_layout(window: Rect2, ui_scale: float) -> Dictionary:
	var close_size := CLOSE_SIZE_PY * ui_scale
	return {
		"window": window,
		"close": Rect2(window.end.x - CLOSE_RIGHT_PY * ui_scale, window.position.y + CLOSE_TOP_PY * ui_scale, close_size, close_size),
		"action": Rect2(
			window.position.x + ACTION_INSET_PY * ui_scale,
			window.end.y - ACTION_BOTTOM_PY * ui_scale,
			window.size.x - 2.0 * ACTION_INSET_PY * ui_scale,
			ACTION_HEIGHT_PY * ui_scale,
		),
	}


# Радиус действия как _is_within_one_tile для объектов с входами: не дальше одного тайла от любой клетки ворот.
static func within_one_tile(town: Dictionary, player_tile: Vector2i) -> bool:
	for entrance in town.get("entrances", []):
		if not entrance is Dictionary:
			continue
		for tile in entrance.get("tiles", []):
			if tile is Array and tile.size() >= 2:
				var distance := maxi(absi(player_tile.x - int(tile[0])), absi(player_tile.y - int(tile[1])))
				if distance <= RANGE_TILES:
					return true
	return false


# Ворота, к которым ближе всего персонаж (_get_nearest_gate в Python); без данных — восток.
static func nearest_gate(town: Dictionary, player_position: Vector2) -> String:
	var best_gate := "east"
	var best_distance := INF
	for entrance in town.get("entrances", []):
		if not entrance is Dictionary:
			continue
		var approach: Variant = entrance.get("approach_pos")
		if approach is Array and approach.size() >= 2:
			var distance := Vector2(float(approach[0]), float(approach[1])).distance_to(player_position)
			if distance < best_distance:
				best_distance = distance
				best_gate = str(entrance.get("id", "east"))
	return best_gate


static func range_text(in_range: bool) -> String:
	return IN_RANGE_TEXT if in_range else OUT_OF_RANGE_TEXT


static func title_text(town: Dictionary) -> String:
	return str(town.get("name", "Объект"))


static func type_text(town: Dictionary) -> String:
	return "Тип: %s" % str(town.get("type", "Объект"))


# Описание как в Python: две строки по 42 символа, дальше текст не выводится.
static func description_lines(desc: String) -> Array:
	if desc.length() <= DESC_LINE_CHARS:
		return [desc]
	return [desc.substr(0, DESC_LINE_CHARS), desc.substr(DESC_LINE_CHARS, DESC_LINE_CHARS)]


# Фразы отказа без повтора предыдущей, как в _on_too_far.
static func too_far_choices(last_phrase: String) -> Array:
	var choices: Array = []
	for phrase in TOO_FAR_PHRASES:
		if phrase != last_phrase:
			choices.append(phrase)
	return choices if not choices.is_empty() else TOO_FAR_PHRASES.duplicate()
