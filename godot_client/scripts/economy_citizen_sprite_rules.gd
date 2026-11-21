extends RefCounted

# Спрайт горожанина на карте путей, порт ui/map_travel.py:268-276. Кадр — player_frame(..., moving=True, run_fps=8.0)
# из scenes/player_sprites.py:262-280: бег из 3run, а если бег не загружен — стойка 2Idle (player_frames_for, 234-245).
# Высота кадра 90 px (PLAYER_SPRITE_HEIGHT, загрузка в world_map_scene.py:656). Кадры и направления читает
# deck_player_sprite_rules.gd из ../assets; здесь только выбор кадра, фигурка и прямоугольник выбора.
# Размер кадра не зависит от масштаба карты: Python блитит кадр без масштаба (map_travel.py:272, world_map_scene.py:3588),
# а масштаб мира там постоянный 1.0 (world_map_scene.py:492).
# Иконка горожанина у подписи (map_travel.py:280-296) — icon_origin и icon_geometry ниже.

const DECK_SPRITE := preload("res://scripts/deck_player_sprite_rules.gd")
const RUN_FOLDER := "3run"
const IDLE_FOLDER := "2Idle"
const SPRITE_HEIGHT := 90
const RUN_FPS := 8.0
# Крупнейший кадр — 74x90 (бег, направление e); прямоугольник покрывает его от ног вверх и по бокам, ноги внутри.
const CITIZEN_PICK_BOX := Rect2(-40.0, -96.0, 80.0, 104.0)
const ELLIPSE_SEGMENTS := 24
const CORNER_SEGMENTS := 4
# Иконка у подписи: IconCache.get("citizen", 32) не находит PNG ни в fighters/equipment/placeholders, ни в ui/currency,
# ни в item_icons, поэтому Python рисует её процедурно: IconCache._draw_procedural, ветка "citizen" (ui/inventory_window.py:154-159).
const ICON_SIZE := 32.0
const ICON_GAP := 4.0
const ICON_OUTLINE := Color8(40, 30, 25)
const ICON_BODY := Color8(157, 177, 143)


# Кадры по направлениям для горожан: бег, а если его нет — стойка.
static func frames_by_direction(assets_root: String) -> Dictionary:
	return frames_from_folders(assets_root.path_join(RUN_FOLDER), assets_root.path_join(IDLE_FOLDER))


static func frames_from_folders(run_folder: String, idle_folder: String) -> Dictionary:
	var run := DECK_SPRITE.directional_frames(run_folder, SPRITE_HEIGHT)
	if not run.is_empty():
		return run
	return DECK_SPRITE.directional_frames(idle_folder, SPRITE_HEIGHT)


# Кадр горожанина или null, если кадров нет; тогда рисуется фигурка. anim_time — секунды, как time.monotonic().
static func frame_for(frame_sets: Dictionary, direction: String, anim_time: float) -> Texture2D:
	var frames: Array = DECK_SPRITE.frames_for_direction(frame_sets, direction)
	if frames.is_empty():
		return null
	return frames[DECK_SPRITE.frame_index(anim_time, RUN_FPS, frames.size())]


# Фигурка запасного рендера относительно ног: тень-эллипс (sx-10, sy-3, 20, 7), голова r=6 в (sx, sy-20),
# тело (sx-5, sy-14, 10, 14) со скруглением 2 — map_travel.py:274-276.
static func figure_geometry(feet: Vector2) -> Dictionary:
	return {
		"shadow": Rect2(feet + Vector2(-10.0, -3.0), Vector2(20.0, 7.0)),
		"head": feet + Vector2(0.0, -20.0),
		"head_radius": 6.0,
		"body": Rect2(feet + Vector2(-5.0, -14.0), Vector2(10.0, 14.0)),
		"body_radius": 2.0,
	}


# Эллипс, вписанный в прямоугольник, как pygame.draw.ellipse.
static func ellipse_points(rect: Rect2) -> PackedVector2Array:
	var center := rect.get_center()
	var radii := rect.size * 0.5
	var points := PackedVector2Array()
	for index in range(ELLIPSE_SEGMENTS):
		var angle := TAU * float(index) / float(ELLIPSE_SEGMENTS)
		points.append(center + Vector2(cos(angle) * radii.x, sin(angle) * radii.y))
	return points


# Скруглённый прямоугольник, как pygame.draw.rect(border_radius=r); точки обходят контур по часовой стрелке на экране.
static func rounded_rect_points(rect: Rect2, radius: float) -> PackedVector2Array:
	var r := minf(radius, minf(rect.size.x, rect.size.y) * 0.5)
	var centers := [
		rect.position + Vector2(r, r),
		Vector2(rect.end.x - r, rect.position.y + r),
		rect.end - Vector2(r, r),
		Vector2(rect.position.x + r, rect.end.y - r),
	]
	var points := PackedVector2Array()
	for corner in range(4):
		var start := PI + float(corner) * PI * 0.5
		for step in range(CORNER_SEGMENTS + 1):
			var angle := start + PI * 0.5 * float(step) / float(CORNER_SEGMENTS)
			points.append(centers[corner] + Vector2(cos(angle), sin(angle)) * r)
	return points


# Левый верхний угол иконки: слева от подписи с зазором 4 px, центр по высоте совпадает с центром подписи (map_travel.py:281-282, 296).
static func icon_origin(label_rect: Rect2) -> Vector2:
	return Vector2(roundf(label_rect.position.x - ICON_SIZE - ICON_GAP), roundf(label_rect.get_center().y - ICON_SIZE * 0.5))


# Фигуры иконки от её левого верхнего угла, в пикселях иконки: голова — круг r=5 с обводкой и заливкой r=4 в (16, 9);
# тело — обводка (7, 15, 17, 13) со скруглением 4 и заливка (9, 16, 14, 12) со скруглением 3 (IconCache._draw_procedural).
static func icon_geometry(origin: Vector2) -> Dictionary:
	return {
		"head": origin + Vector2(16.0, 9.0),
		"head_outline_radius": 5.0,
		"head_radius": 4.0,
		"body_outline": Rect2(origin + Vector2(7.0, 15.0), Vector2(17.0, 13.0)),
		"body_outline_radius": 4.0,
		"body": Rect2(origin + Vector2(9.0, 16.0), Vector2(14.0, 12.0)),
		"body_radius": 3.0,
	}
