extends RefCounted

const HERO_ROOT := "res://assets/base_tails/Герои"
const FRAME_SIZE := 64

static var _sheet_paths: Dictionary = {}
static var _sheets: Dictionary = {}
static var _textures: Dictionary = {}
static var _filled_frames: Dictionary = {}


static func frame_count(profession: String, state: String) -> int:
	var sheet: Image = _load_sheet(profession, _action(state))
	return sheet.get_width() / FRAME_SIZE if sheet != null else 0


# Число кадров строки направления с видимыми пикселями. В листах покоя у некоторых классов строка
# «вверх» (спиной к камере) заполнена не полностью: пустые кадры делали героя невидимым на время цикла.
static func row_frame_count(profession: String, state: String, direction: String) -> int:
	return filled_frames(profession, _action(state), _direction_row(direction)).size()


# Индексы кадров строки, в которых есть видимые пиксели.
static func filled_frames(profession: String, action: String, row: int) -> Array:
	var key := "%s|%s|%d" % [profession, action, row]
	if _filled_frames.has(key):
		return _filled_frames[key]
	var result: Array = []
	var sheet: Image = _load_sheet(profession, action)
	if sheet != null:
		for index in range(sheet.get_width() / FRAME_SIZE):
			var cell := sheet.get_region(Rect2i(index * FRAME_SIZE, row * FRAME_SIZE, FRAME_SIZE, FRAME_SIZE))
			if cell.get_used_rect().has_area():
				result.append(index)
	_filled_frames[key] = result
	return result


static func frame_texture(profession: String, state: String, direction: String, frame_index: int) -> Texture2D:
	var action := _action(state)
	var row := _direction_row(direction)
	var frames := filled_frames(profession, action, row)
	if frames.is_empty():
		return null
	var column: int = frames[posmod(frame_index, frames.size())]
	var cache_key := "%s|%s|%d|%d" % [profession, action, row, column]
	if _textures.has(cache_key):
		return _textures[cache_key]
	var sheet: Image = _load_sheet(profession, action)
	if sheet == null:
		_textures[cache_key] = null
		return null
	var image := sheet.get_region(Rect2i(column * FRAME_SIZE, row * FRAME_SIZE, FRAME_SIZE, FRAME_SIZE))
	var texture := ImageTexture.create_from_image(image)
	_textures[cache_key] = texture
	return texture


static func _action(state: String) -> String:
	return state if state in ["run", "attack"] else "idle"


static func _load_sheet(profession: String, action: String) -> Image:
	var cache_key := "%s|%s" % [profession, action]
	if _sheets.has(cache_key):
		return _sheets[cache_key]
	var image: Image
	var path := _animation_path(profession, action)
	if not path.is_empty():
		image = Image.new()
		if image.load(ProjectSettings.globalize_path(path)) != OK:
			push_error("Не удалось загрузить спрайт героя Front Line: " + path)
			image = null
		elif image.get_height() != FRAME_SIZE * 4 or image.get_width() % FRAME_SIZE != 0:
			push_error("Неверный формат спрайта героя Front Line: " + path)
			image = null
	else:
		push_error("Не найден спрайт героя Front Line: %s (%s)" % [profession, action])
	_sheets[cache_key] = image
	return image


static func _animation_path(profession: String, action: String) -> String:
	var cache_key := "%s|%s" % [profession, action]
	if _sheet_paths.has(cache_key):
		return str(_sheet_paths[cache_key])
	var level_pattern := ""
	match profession:
		"warrior":
			level_pattern = "(?i)^Swordsman_lvl1$"
		"archer":
			# Уровни лучника 1–9 лежат в трёх паках (1–3, 4–6, 7–9): берётся самый низкий уровень.
			level_pattern = "(?i)^Archer_Lvl\\d+$"
		"mage":
			level_pattern = "(?i)^Mage_1lvl$"
		_:
			_sheet_paths[cache_key] = ""
			return ""
	var root := HERO_ROOT.path_join(profession if profession != "warrior" else "swordsman")
	var root_directory := DirAccess.open(root)
	if root_directory == null:
		_sheet_paths[cache_key] = ""
		return ""
	var level_regex := RegEx.new()
	level_regex.compile(level_pattern)
	var number_regex := RegEx.new()
	number_regex.compile("\\d+")
	# Кандидаты: [номер уровня, путь к листу]. Выбирается наименьший уровень.
	var candidates: Array = []
	for pack_folder in root_directory.get_directories():
		if pack_folder.begins_with(".") or pack_folder == "__MACOSX":
			continue
		var png_path := root.path_join(pack_folder).path_join("PNG")
		var png_directory := DirAccess.open(png_path)
		if png_directory == null:
			continue
		for level_folder in png_directory.get_directories():
			if level_regex.search(level_folder) == null:
				continue
			var number_match := number_regex.search(level_folder)
			var level := int(number_match.get_string()) if number_match != null else 0
			var level_path := png_path.path_join(level_folder)
			for shadow_folder in ["With_shadow", "Without_shadow", ""]:
				var animation_directory := DirAccess.open(
					level_path if shadow_folder.is_empty() else level_path.path_join(shadow_folder),
				)
				if animation_directory == null:
					continue
				var found := false
				for file_name in animation_directory.get_files():
					var lower_name := file_name.to_lower()
					if file_name.get_extension().to_lower() == "png" 							and not file_name.begins_with("._") 							and not lower_name.begins_with("shadow") 							and lower_name.contains(action) 							and (action != "run" or not lower_name.contains("attack")) 							and (action != "attack" or not (
								lower_name.contains("run_attack") or lower_name.contains("walk_attack")
							)):
						candidates.append([level, (level_path.path_join(shadow_folder).path_join(file_name)
							if not shadow_folder.is_empty() else level_path.path_join(file_name))])
						found = true
				if found:
					break
	var path := ""
	if not candidates.is_empty():
		candidates.sort_custom(func(a: Array, b: Array) -> bool:
			return a[0] < b[0] or (a[0] == b[0] and str(a[1]) < str(b[1])))
		path = str(candidates[0][1])
	_sheet_paths[cache_key] = path
	return path


static func _direction_row(direction: String) -> int:
	if direction.contains("n") or direction == "up":
		return 3
	if direction.contains("w") or direction == "left":
		return 1
	if direction.contains("e") or direction == "right":
		return 2
	return 0
