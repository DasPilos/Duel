extends RefCounted

# Иконки предметов Deck. Ключ — поле "icon" предмета с сервера (имя файла без .png).
# Порядок поиска как в Python: слои экипировки из assets/fighters/equipment/placeholders (их рисует
# deck/ui/inventory_window.py IconCache), затем assets/item_icons (core/item_icons.py). Файлы не копируются
# в проект. Пустой ключ или отсутствующий файл дают null без ошибки: текст предмета остаётся как был.

const PROJECT_ASSETS_RELATIVE := "../assets"
const PLACEHOLDERS_RELATIVE := "fighters/equipment/placeholders"
const ITEM_ICONS_RELATIVE := "item_icons"
# ICON_KEY_RE из core/item_icons.py: строчные латинские буквы, цифры и подчёркивание, до 64 символов.
const KEY_PATTERN := "^[a-z0-9][a-z0-9_]{0,63}$"
# IconCache._build в Python вписывает обрезанный рисунок в квадрат, занимая 84 % его стороны.
const FIT_RATIO := 0.84

static var _key_regex: RegEx
static var _cropped: Dictionary = {}
static var _textures: Dictionary = {}


static func default_assets_root(project_dir: String) -> String:
	return project_dir.path_join(PROJECT_ASSETS_RELATIVE).simplify_path()


static func is_valid_key(key: String) -> bool:
	if key.is_empty():
		return false
	if _key_regex == null:
		_key_regex = RegEx.create_from_string(KEY_PATTERN)
	return _key_regex.search(key) != null


# Ключ иконки предмета; пустая строка, если поля нет или оно равно null.
static func item_key(item: Variant) -> String:
	if item is Dictionary:
		var raw: Variant = item.get("icon")
		if raw is String or raw is StringName:
			return str(raw)
	return ""


# Путь к PNG или пустая строка: ключ невалиден либо файла нет ни в одной из папок.
static func icon_path(assets_root: String, key: String) -> String:
	if assets_root.is_empty() or not is_valid_key(key):
		return ""
	for folder in [PLACEHOLDERS_RELATIVE, ITEM_ICONS_RELATIVE]:
		var path := assets_root.path_join(folder).path_join(key + ".png")
		if FileAccess.file_exists(path):
			return path
	return ""


# Размер рисунка внутри квадрата box: длинная сторона занимает FIT_RATIO квадрата, как в Python.
static func fitted_size(content: Vector2i, box: int) -> Vector2i:
	var longest := maxi(content.x, content.y)
	if longest <= 0 or box <= 0:
		return Vector2i.ZERO
	var scale := float(box) * FIT_RATIO / float(longest)
	return Vector2i(maxi(1, int(content.x * scale)), maxi(1, int(content.y * scale)))


# Текстура иконки для квадрата box или null. Каждый PNG читается один раз; готовые текстуры кэшируются по размеру.
static func icon_texture(assets_root: String, key: String, box: int) -> Texture2D:
	var path := icon_path(assets_root, key)
	if path.is_empty() or box <= 0:
		return null
	var cache_key := "%s|%d" % [path, box]
	if not _textures.has(cache_key):
		_textures[cache_key] = _build_texture(path, box)
	return _textures[cache_key]


# Квадратный TextureRect; без текстуры он скрыт и не занимает места в контейнере.
static func new_icon_rect(box: int) -> TextureRect:
	var rect := TextureRect.new()
	rect.custom_minimum_size = Vector2(box, box)
	rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	rect.stretch_mode = TextureRect.STRETCH_KEEP_CENTERED
	rect.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	rect.visible = false
	return rect


static func apply_icon(rect: TextureRect, assets_root: String, key: String, box: int) -> void:
	var texture := icon_texture(assets_root, key, box)
	rect.texture = texture
	rect.visible = texture != null


static func _build_texture(path: String, box: int) -> Texture2D:
	var cropped := _cropped_image(path)
	if cropped == null:
		return null
	var size := fitted_size(Vector2i(cropped.get_width(), cropped.get_height()), box)
	var scaled := cropped.get_region(Rect2i(Vector2i.ZERO, cropped.get_size()))
	scaled.resize(size.x, size.y, Image.INTERPOLATE_LANCZOS)
	return ImageTexture.create_from_image(scaled)


static func _cropped_image(path: String) -> Image:
	if not _cropped.has(path):
		_cropped[path] = _load_cropped(path)
	return _cropped[path]


# Обрезка по непрозрачным пикселям, как get_bounding_rect() в Python.
static func _load_cropped(path: String) -> Image:
	var source := Image.load_from_file(path)
	if source == null or source.is_empty():
		return null
	source.convert(Image.FORMAT_RGBA8)
	var used := source.get_used_rect()
	if used.size.x <= 0 or used.size.y <= 0:
		return null
	return source.get_region(used)
