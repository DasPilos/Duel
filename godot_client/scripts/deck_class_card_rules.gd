extends RefCounted

# Данные карточек классов из scenes/create_character_scene.py: подпись, спрайт из assets/classes, сдвиг фигуры и фон.
# Экран создания карточек: create_character_view.gd. Карточка персонажа Deck берёт только геометрию базовой фигуры
# (figure_rect, как draw_paperdoll в ui/equipment_slots.py), спрайты классов на ней не показываются.

const CHARACTER_RULES := preload("res://scripts/deck_character_rules.gd")
const PROJECT_ASSETS_RELATIVE := "../assets"
const CLASS_ART_DIR := "classes"
const BASE_FIGURE_PATH := "fighters/base/fighter.png"
# Подписи, сдвиги фигуры и иконки (ui/professions) из CreateCharacterScene.CLASS_INFO. У некроманта в Python нет карточки класса,
# поэтому подпись взята из PROFESSIONS, а спрайта нет.
const CLASS_INFO := {
	"warrior": {"title": "ВОИН", "sprite": "warrior.png", "icon": "warrior.png", "sprite_offset_x": -20, "card_bg": Color8(110, 34, 38)},
	"archer": {"title": "ЛУЧНИК", "sprite": "archer.png", "icon": "archer.png", "sprite_offset_x": 10, "card_bg": Color8(34, 96, 48)},
	"assassin": {"title": "АСАСИН", "sprite": "assassin.png", "icon": "assassin.png", "sprite_offset_x": 0, "card_bg": Color8(88, 44, 120)},
	"mage": {"title": "МАГ", "sprite": "mage.png", "icon": "mage.png", "sprite_offset_x": -10, "card_bg": Color8(36, 62, 130)},
	# Фон у некроманта из deck/ui/class_identity.py (палитра Deck), в Python карточки класса нет.
	"necromancer": {"title": "НЕКРОМАНТ", "sprite": "", "icon": "", "sprite_offset_x": 0, "card_bg": Color8(37, 54, 42)},
}
# settings.FIGHTER_SPRITE_SCALE. Сетка слотов куклы в Python 406 px по высоте, центр фигуры на 23 px выше её центра.
const PY_FIGURE_SCALE := 0.48
const PY_SLOT_GRID_SPAN := 406.0
const PY_FIGURE_CENTER_SHIFT_Y := -23.0


static func normalize_class(profession_type: String) -> String:
	return CHARACTER_RULES.normalize_profession_type(profession_type)


static func class_title(profession_type: String) -> String:
	return str(_class_info(profession_type).get("title", ""))


static func class_sprite_file(profession_type: String) -> String:
	return str(_class_info(profession_type).get("sprite", ""))


static func sprite_offset_x(profession_type: String) -> int:
	return int(_class_info(profession_type).get("sprite_offset_x", 0))


static func card_background(profession_type: String) -> Color:
	return _class_info(profession_type).get("card_bg", Color(0.0, 0.0, 0.0, 0.0))


static func default_assets_root(project_dir: String) -> String:
	return project_dir.path_join(PROJECT_ASSETS_RELATIVE).simplify_path()


static func class_art_path(assets_root: String, profession_type: String) -> String:
	var file_name := class_sprite_file(profession_type)
	if assets_root.is_empty() or file_name.is_empty():
		return ""
	return assets_root.path_join(CLASS_ART_DIR).path_join(file_name)


static func base_figure_path(assets_root: String) -> String:
	return assets_root.path_join(BASE_FIGURE_PATH)


# Ширина фигуры после подгонки по высоте эталона, высота равна высоте эталона (как в fit_figure_to).
static func fitted_figure_size(source_box: Rect2i, reference_box: Rect2i) -> Vector2i:
	if source_box.size.y <= 0 or reference_box.size.y <= 0:
		return Vector2i.ZERO
	var ratio := float(reference_box.size.y) / float(source_box.size.y)
	return Vector2i(maxi(1, roundi(source_box.size.x * ratio)), reference_box.size.y)


# Холст размером с эталон: фигура подогнана по высоте, стоит на ногах эталона и по центру его фигуры.
# Меняет source на месте: переводит его в RGBA8.
static func fit_figure(source: Image, reference_size: Vector2i, reference_box: Rect2i) -> Image:
	source.convert(Image.FORMAT_RGBA8)
	var source_box := source.get_used_rect()
	var figure_size := fitted_figure_size(source_box, reference_box)
	if figure_size == Vector2i.ZERO:
		return source
	var figure := source.get_region(source_box)
	figure.resize(figure_size.x, figure_size.y, Image.INTERPOLATE_BILINEAR)
	var canvas := Image.create(reference_size.x, reference_size.y, false, Image.FORMAT_RGBA8)
	canvas.fill(Color(0, 0, 0, 0))
	var left := reference_box.position.x + floori(reference_box.size.x / 2.0) - floori(figure_size.x / 2.0)
	var top := reference_box.end.y - figure_size.y
	canvas.blit_rect(figure, Rect2i(Vector2i.ZERO, figure_size), Vector2i(left, top))
	return canvas


# Прямоугольник холста фигуры в координатах куклы, где grid_size — размер сетки слотов в Godot.
# Все размеры Python масштабируются по высоте сетки, сдвиг по X берётся из sprite_offset_x.
static func figure_rect(grid_size: Vector2, canvas_size: Vector2, offset_x: int) -> Rect2:
	var ratio := grid_size.y / PY_SLOT_GRID_SPAN
	var canvas := canvas_size * (PY_FIGURE_SCALE * ratio)
	var center := Vector2(grid_size.x / 2.0 + offset_x * ratio, grid_size.y / 2.0 + PY_FIGURE_CENTER_SHIFT_Y * ratio)
	return Rect2(center - canvas / 2.0, canvas)


static func _class_info(profession_type: String) -> Dictionary:
	return CLASS_INFO.get(normalize_class(profession_type), {})
