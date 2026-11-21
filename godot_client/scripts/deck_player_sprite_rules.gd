extends RefCounted

# Спрайты персонажа и лесника на карте мира Deck, порт deck/scenes/world_map_scene.py:
#   _load_player_directional_sprites (323-380): стойка assets/2Idle (4 кадра) и бег assets/3run (6 кадров) по 8 направлениям,
#     кадры по имени без *apng.png и *spritesheet.png, высота 56 px, ширина по обрезке первого кадра;
#   _vector_to_direction (395), _draw_player_character (2893): бег при ходьбе 10 кадров/с, стойка 4 кадра/с;
#   _load_forester_sprite (295): три среза forester's1.png 238x330 со сдвигами -240, 0, 239, масштаб 10 тайлов.
# Файлы читаются из ../assets относительно godot_client и не копируются. Готовые текстуры кэшируются статически,
# как в deck_item_icon_rules.gd, иначе каждый шаг по карте заново декодировал бы PNG.

const DIRECTIONS := ["n", "ne", "e", "se", "s", "sw", "w", "nw"]
const IDLE_FOLDER := "2Idle"
const RUN_FOLDER := "3run"
const PLAYER_TARGET_HEIGHT := 56
const IDLE_FPS := 4.0
const RUN_FPS := 10.0
# player_speed = 220 * tile_size / 32 (world_map_scene.py:185): тайл любого размера проходится за 32 / 220 с.
const WALK_STEP_SECONDS := 32.0 / 220.0
const SKIPPED_SUFFIXES := ["apng.png", "spritesheet.png"]
const FORESTER_FILE := "forester's1.png"
const FORESTER_TILES := 10
const FORESTER_FRAME_SIZE := Vector2i(238, 330)
const FORESTER_SHEET_ORIGIN := Vector2i(237, 85)
const FORESTER_SHIFTS := [-240, 0, 239]
const FORESTER_FRAME_SECONDS := 0.35
# Тень и подсветка лагеря лесника из world_map_scene.py (lumber_camp): цвета pygame без альфа-канала.
const FORESTER_SHADOW_COLOR := Color(16 / 255.0, 24 / 255.0, 16 / 255.0)
const FORESTER_HOVER_COLOR := Color(80 / 255.0, 200 / 255.0, 255 / 255.0)
const FORESTER_HOVER_BADGE_COLOR := Color(100 / 255.0, 200 / 255.0, 255 / 255.0)

static var _directional_cache: Dictionary = {}
static var _forester_cache: Dictionary = {}


static func assets_root(project_dir: String) -> String:
	return project_dir.path_join("../assets").simplify_path()


# Одно из 8 направлений по вектору движения; экранный y направлен вниз, 90° — s.
static func direction_for(delta: Vector2) -> String:
	var angle := rad_to_deg(atan2(delta.y, delta.x))
	if -22.5 <= angle and angle < 22.5:
		return "e"
	if 22.5 <= angle and angle < 67.5:
		return "se"
	if 67.5 <= angle and angle < 112.5:
		return "s"
	if 112.5 <= angle and angle < 157.5:
		return "sw"
	if angle >= 157.5 or angle < -157.5:
		return "w"
	if -157.5 <= angle and angle < -112.5:
		return "nw"
	if -112.5 <= angle and angle < -67.5:
		return "n"
	return "ne"


# Номер кадра персонажа: int(player_anim_timer * fps) % len(frames).
static func frame_index(anim_time: float, fps: float, count: int) -> int:
	return int(anim_time * fps) % maxi(1, count)


# Номер кадра лесника: int(player_anim_timer / 0.35) % len(forester_frames).
static func forester_frame_index(anim_time: float, count: int) -> int:
	return int(anim_time / FORESTER_FRAME_SECONDS) % maxi(1, count)


# Кадры направления; если его нет, первый загруженный набор, как next(iter(frames_dict.values())).
static func frames_for_direction(frames_by_direction: Dictionary, direction: String) -> Array:
	if frames_by_direction.has(direction):
		return frames_by_direction[direction]
	for key in frames_by_direction:
		return frames_by_direction[key]
	return []


# Кадр персонажа: ноги в точке feet, как get_rect(midbottom=(sx, sy)); половина ширины берётся целой, как в pygame.
static func player_frame_rect(feet: Vector2, frame_size: Vector2i) -> Rect2:
	return Rect2(feet.x - float(frame_size.x / 2), feet.y - float(frame_size.y), frame_size.x, frame_size.y)


static func forester_badge_text(forester_name: String) -> String:
	return "🌲 %s [%dx%d]" % [forester_name, FORESTER_TILES, FORESTER_TILES]


# Размер холста после поворота, как у pygame.transform.rotate; при 180° совпадает с исходным.
static func rotated_bounds(size: Vector2, degrees: int) -> Vector2:
	var radians := deg_to_rad(float(degrees))
	var cosine := absf(cos(radians))
	var sine := absf(sin(radians))
	return Vector2(size.x * cosine + size.y * sine, size.x * sine + size.y * cosine)


# Имена кадров папки: *.png без apng и spritesheet, по возрастанию имени.
static func frame_names(folder: String) -> PackedStringArray:
	var names := PackedStringArray()
	if not DirAccess.dir_exists_absolute(folder):
		return names
	for file_name in DirAccess.get_files_at(folder):
		if file_name.get_extension().to_lower() != "png" or _is_skipped(file_name):
			continue
		names.append(file_name)
	names.sort()
	return names


# Кадры по направлениям: {"n": [ImageTexture, ...], ...}. Высота target_height, ширина — из обрезки первого кадра.
static func directional_frames(folder: String, target_height: int) -> Dictionary:
	var key := "%s|%d" % [folder, target_height]
	if not _directional_cache.has(key):
		_directional_cache[key] = _load_directional_frames(folder, target_height)
	return _directional_cache[key]


# Границы непрозрачного содержимого файла, как get_bounding_rect() в pygame.
static func used_rect(path: String) -> Rect2i:
	var image := _load_rgba(path)
	return image.get_used_rect() if image != null else Rect2i()


# Эллипс тени под лагерем как pygame.draw.ellipse(sx + 20, sy + 180, obj_w - 40, 120); k = tile_px / 48.
static func forester_shadow_ellipse(rect: Rect2, tile_px: float) -> Rect2:
	var k := tile_px / 48.0
	return Rect2(rect.position + Vector2(20.0, 180.0) * k, Vector2(rect.size.x - 40.0 * k, 120.0 * k))


# Срез кадра лесника 238x330 со сдвигом по x. Вне листа пиксели остаются прозрачными, как при blit в pygame.
static func forester_slice(sheet: Image, shift: int) -> Image:
	var frame := Image.create_empty(FORESTER_FRAME_SIZE.x, FORESTER_FRAME_SIZE.y, false, Image.FORMAT_RGBA8)
	var source := Rect2i(FORESTER_SHEET_ORIGIN + Vector2i(shift, 0), FORESTER_FRAME_SIZE)
	var visible := source.intersection(Rect2i(Vector2i.ZERO, sheet.get_size()))
	if visible.has_area():
		frame.blit_rect(sheet, visible, visible.position - source.position)
	return frame


# Три кадра лесника в масштабе 10 тайлов (10 * tile_size) или пустой массив, если файла нет.
static func forester_frames(sheet_path: String, tile_px: int) -> Array:
	var side := FORESTER_TILES * maxi(1, tile_px)
	var key := "%s|%d" % [sheet_path, side]
	if not _forester_cache.has(key):
		_forester_cache[key] = _build_forester_frames(sheet_path, side)
	return _forester_cache[key]


static func _load_directional_frames(folder: String, target_height: int) -> Dictionary:
	var frames := {}
	for direction in DIRECTIONS:
		var direction_folder := folder.path_join(direction)
		var names := frame_names(direction_folder)
		if names.is_empty():
			continue
		var sample := _load_rgba(direction_folder.path_join(names[0]))
		if sample == null:
			continue
		var crop := sample.get_used_rect()
		if crop.size.y <= 0:
			continue
		var target_width := maxi(1, int(crop.size.x * (float(target_height) / float(crop.size.y))))
		var target := Vector2i(target_width, target_height)
		var textures: Array = []
		for file_name in names:
			var image := sample if file_name == names[0] else _load_rgba(direction_folder.path_join(file_name))
			if image != null:
				textures.append(_scaled_texture(image, crop, target))
		if not textures.is_empty():
			frames[direction] = textures
	return frames


static func _build_forester_frames(sheet_path: String, side: int) -> Array:
	var frames: Array = []
	var sheet := _load_rgba(sheet_path)
	if sheet == null:
		return frames
	for shift in FORESTER_SHIFTS:
		var frame := forester_slice(sheet, shift)
		frame.resize(side, side, Image.INTERPOLATE_LANCZOS)
		frames.append(ImageTexture.create_from_image(frame))
	return frames


static func _scaled_texture(image: Image, crop: Rect2i, target: Vector2i) -> ImageTexture:
	var part := image.get_region(crop)
	part.resize(target.x, target.y, Image.INTERPOLATE_LANCZOS)
	return ImageTexture.create_from_image(part)


static func _load_rgba(path: String) -> Image:
	if not FileAccess.file_exists(path):
		return null
	var image := Image.load_from_file(path)
	if image == null or image.is_empty():
		return null
	image.convert(Image.FORMAT_RGBA8)
	return image


static func _is_skipped(file_name: String) -> bool:
	for suffix in SKIPPED_SUFFIXES:
		if file_name.ends_with(suffix):
			return true
	return false
