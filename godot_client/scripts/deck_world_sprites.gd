extends Control

# Фигурки карты мира Deck: персонаж и лагерь лесника поверх плиток и маркеров.
# Порт _draw_player_character и ветки lumber_camp из deck/scenes/world_map_scene.py; кадры и размеры — в deck_player_sprite_rules.gd.
# Слой не принимает мышь, поэтому клики по плиткам и маркерам под ним работают как раньше.

const RULES := preload("res://scripts/deck_player_sprite_rules.gd")
const ELLIPSE_SEGMENTS := 20
# Цвета pygame рисует непрозрачными: эллипс тени и подложки подписей без альфа-канала, как в Python.
const SHADOW_COLOR := Color(10 / 255.0, 12 / 255.0, 16 / 255.0)
const NAME_FONT_SIZE := 11
const NAME_TEXT_COLOR := Color(255 / 255.0, 235 / 255.0, 150 / 255.0)
const NAME_BG_COLOR := Color(15 / 255.0, 18 / 255.0, 24 / 255.0)
const NAME_BORDER_COLOR := Color(180 / 255.0, 150 / 255.0, 60 / 255.0)
const BADGE_FONT_SIZE := 13
const BADGE_TEXT_COLOR := Color(240 / 255.0, 240 / 255.0, 240 / 255.0)
const BADGE_BG_COLOR := Color(12 / 255.0, 14 / 255.0, 18 / 255.0)
const BADGE_BORDER_COLOR := Color(200 / 255.0, 190 / 255.0, 160 / 255.0)
const FOREST_FALLBACK_COLOR := Color(42 / 255.0, 60 / 255.0, 42 / 255.0)
const CAPE_COLOR := Color(34 / 255.0, 110 / 255.0, 55 / 255.0)
const BODY_COLOR := Color(85 / 255.0, 115 / 255.0, 145 / 255.0)
const BODY_BORDER_COLOR := Color(40 / 255.0, 60 / 255.0, 80 / 255.0)
const LEG_COLOR := Color(50 / 255.0, 65 / 255.0, 80 / 255.0)
const HEAD_COLOR := Color(220 / 255.0, 195 / 255.0, 160 / 255.0)
const HAT_COLOR := Color(215 / 255.0, 180 / 255.0, 75 / 255.0)
const FEATHER_COLOR := Color(40 / 255.0, 160 / 255.0, 70 / 255.0)

var _feet := Vector2.ZERO
var _direction := "s"
var _facing_right := true
var _player_name := "Герой"
var _forester: Dictionary = {}
var _forester_frames: Array = []
var _idle: Dictionary = {}
var _run: Dictionary = {}
var _anim_time := 0.0
var _walking := false
var _draws := 0
var _forester_hovered := false
var _tile_px := 48
var _forester_hover_style := _box_style(Color(0.0, 0.0, 0.0, 0.0), RULES.FORESTER_HOVER_COLOR, 6, 2)
var _hover_badge_style := _box_style(BADGE_BG_COLOR, RULES.FORESTER_HOVER_BADGE_COLOR, 3, 1)
var _name_style := _box_style(NAME_BG_COLOR, NAME_BORDER_COLOR, 3, 1)
var _badge_style := _box_style(BADGE_BG_COLOR, BADGE_BORDER_COLOR, 3, 1)
var _forest_style := _box_style(FOREST_FALLBACK_COLOR, FOREST_FALLBACK_COLOR, 6, 0)
var _body_style := _box_style(BODY_COLOR, BODY_BORDER_COLOR, 2, 1)
var _hat_style := _box_style(HAT_COLOR, HAT_COLOR, 2, 0)


# state: feet (точка ног игрока в координатах слоя), tile_px, direction, player_name,
# forester {rect, rotation, name} или пусто, anim_time, walking; assets_root по умолчанию — ../assets.
func configure(state: Dictionary) -> void:
	var root := str(state.get("assets_root", ""))
	if root.is_empty():
		root = RULES.assets_root(ProjectSettings.globalize_path("res://"))
	_feet = state.get("feet", Vector2.ZERO)
	_direction = str(state.get("direction", "s"))
	_facing_right = not _direction.contains("w")
	_player_name = str(state.get("player_name", "Герой"))
	_forester = state.get("forester", {})
	var tile_px := maxi(1, int(state.get("tile_px", 48)))
	_tile_px = tile_px
	_idle = RULES.directional_frames(root.path_join(RULES.IDLE_FOLDER), RULES.PLAYER_TARGET_HEIGHT)
	_run = RULES.directional_frames(root.path_join(RULES.RUN_FOLDER), RULES.PLAYER_TARGET_HEIGHT)
	_forester_frames = RULES.forester_frames(root.path_join(RULES.FORESTER_FILE), tile_px)
	set_animation(float(state.get("anim_time", 0.0)), bool(state.get("walking", false)))


func set_animation(anim_time: float, walking: bool) -> void:
	_anim_time = anim_time
	_walking = walking
	queue_redraw()


# Ноги фигурки в координатах слоя: у края карты камера зажата, и фигурка стоит не в центре окна.
func set_feet(feet: Vector2) -> void:
	if _feet != feet:
		_feet = feet
		queue_redraw()


# Лагерь лесника движется вместе с окном карты: прямоугольник присылает deck_world_map_renderer.gd.
func set_forester(view: Dictionary) -> void:
	_forester = view
	queue_redraw()


# Наведение задаёт renderer по указателю; окна, закрывающие карту, его отключают, как hovered_entity в Python.
func set_forester_hovered(hovered: bool) -> void:
	if _forester_hovered != hovered:
		_forester_hovered = hovered
		queue_redraw()


# Состояние для проверок: набор и номер кадра, скорость, прямоугольники фигурок.
func animation_state() -> Dictionary:
	var selection := _player_selection()
	var frames: Array = selection["frames"]
	var index := -1
	var player_rect := Rect2()
	if not frames.is_empty():
		index = RULES.frame_index(_anim_time, selection["fps"], frames.size())
		player_rect = RULES.player_frame_rect(_feet, Vector2i(frames[index].get_size()))
	var forester_rect: Rect2 = _forester.get("rect", Rect2())
	return {
		"walking": _walking,
		"direction": _direction,
		"anim_time": _anim_time,
		"fps": selection["fps"],
		"frame_count": frames.size(),
		"frame_index": index,
		"feet": _feet,
		"player_name": _player_name,
		"player_rect": player_rect,
		"forester_rect": forester_rect,
		"forester_frame_count": _forester_frames.size(),
		"forester_hovered": _forester_hovered,
		"forester_shadow_rect": _forester_shadow_rect(),
	}


func draw_count() -> int:
	return _draws


func _draw() -> void:
	_draws += 1
	_draw_forester()
	_draw_player()


# Бег при ходьбе, если бег загружен; иначе стойка. Скорость кадров как в _draw_player_character.
func _player_selection() -> Dictionary:
	var running := _walking and not _run.is_empty()
	var frames := RULES.frames_for_direction(_run if running else _idle, _direction)
	return {"frames": frames, "fps": RULES.RUN_FPS if running else RULES.IDLE_FPS}


func _draw_player() -> void:
	draw_colored_polygon(_ellipse(_feet + Vector2(0.0, 1.0), Vector2(14.0, 5.0)), SHADOW_COLOR)
	var selection := _player_selection()
	var frames: Array = selection["frames"]
	var name_bottom := 0.0
	if frames.is_empty():
		name_bottom = _draw_warrior()
	else:
		var frame: Texture2D = frames[RULES.frame_index(_anim_time, selection["fps"], frames.size())]
		var frame_rect := RULES.player_frame_rect(_feet, Vector2i(frame.get_size()))
		draw_texture_rect(frame, frame_rect, false)
		name_bottom = frame_rect.position.y - 4.0
	_draw_name(name_bottom)


func _draw_forester() -> void:
	if _forester.is_empty():
		return
	var rect: Rect2 = _forester["rect"]
	var shadow := _forester_shadow_rect()
	draw_colored_polygon(_ellipse(shadow.get_center(), shadow.size / 2.0), RULES.FORESTER_SHADOW_COLOR)
	if _forester_frames.is_empty():
		draw_style_box(_forest_style, rect)
	else:
		var frame: Texture2D = _forester_frames[RULES.forester_frame_index(_anim_time, _forester_frames.size())]
		_draw_rotated(frame, rect.position, rect.size, int(_forester.get("rotation", 0)))
	if _forester_hovered:
		draw_style_box(_forester_hover_style, rect)
	var badge_style: StyleBoxFlat = _hover_badge_style if _forester_hovered else null
	_draw_badge(RULES.forester_badge_text(str(_forester.get("name", ""))), Vector2(rect.get_center().x, rect.position.y - 10.0), badge_style)


# Тень под лагерем: эллипс как в world_map_scene.py, его прямоугольник считает RULES.forester_shadow_ellipse.
func _forester_shadow_rect() -> Rect2:
	if _forester.is_empty():
		return Rect2()
	return RULES.forester_shadow_ellipse(_forester["rect"], float(_tile_px))


# Процедурный чиби-воин, когда кадров нет (фолбэк _draw_player_character). Возвращает y для подписи.
func _draw_warrior() -> float:
	var bob := int(sin(_anim_time * 14.0) * 2.5) if _walking else int(sin(_anim_time * 4.0))
	var leg_offset := int(sin(_anim_time * 14.0) * 2.0) if _walking else 0
	var cy := _feet.y + bob
	var sx := _feet.x
	var facing := 1.0 if _facing_right else -1.0
	draw_colored_polygon(PackedVector2Array([
		Vector2(sx - 5.0 * facing, cy - 4.0),
		Vector2(sx - 12.0 * facing, cy + 8.0),
		Vector2(sx - 4.0 * facing, cy + 9.0),
	]), CAPE_COLOR)
	draw_style_box(_body_style, Rect2(sx - 6.0, cy - 6.0, 12.0, 13.0))
	draw_rect(Rect2(sx - 5.0, cy + 7.0 - leg_offset, 4.0, 5.0), LEG_COLOR)
	draw_rect(Rect2(sx + 1.0, cy + 7.0 + leg_offset, 4.0, 5.0), LEG_COLOR)
	draw_circle(Vector2(sx, cy - 11.0), 6.0, HEAD_COLOR)
	draw_style_box(_hat_style, Rect2(sx - 6.0, cy - 17.0, 12.0, 7.0))
	draw_line(Vector2(sx - 2.0 * facing, cy - 17.0), Vector2(sx - 6.0 * facing, cy - 22.0), FEATHER_COLOR, 2.0)
	return cy - 23.0


# Подпись над персонажем: нижний край на bottom_y, по центру над ногами.
func _draw_name(bottom_y: float) -> void:
	var font := ThemeDB.fallback_font
	var text_size := font.get_string_size(_player_name, HORIZONTAL_ALIGNMENT_LEFT, -1, NAME_FONT_SIZE)
	var text_rect := Rect2(Vector2(_feet.x - text_size.x / 2.0, bottom_y - text_size.y), text_size)
	draw_style_box(_name_style, text_rect.grow_individual(4.0, 1.0, 4.0, 1.0))
	draw_string(font, text_rect.position + Vector2(0.0, font.get_ascent(NAME_FONT_SIZE)), _player_name, HORIZONTAL_ALIGNMENT_LEFT, -1, NAME_FONT_SIZE, NAME_TEXT_COLOR)


# Плашка как _draw_badge в Python: текст по центру над bottom_center, подложка на 5 px по бокам и 2 px сверху и снизу.
func _draw_badge(text: String, bottom_center: Vector2, style: StyleBoxFlat = null) -> void:
	var font := ThemeDB.fallback_font
	var text_size := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, BADGE_FONT_SIZE)
	var text_rect := Rect2(Vector2(bottom_center.x - text_size.x / 2.0, bottom_center.y - text_size.y), text_size)
	draw_style_box(style if style != null else _badge_style, text_rect.grow_individual(5.0, 2.0, 5.0, 2.0))
	draw_string(font, text_rect.position + Vector2(0.0, font.get_ascent(BADGE_FONT_SIZE)), text, HORIZONTAL_ALIGNMENT_LEFT, -1, BADGE_FONT_SIZE, BADGE_TEXT_COLOR)


# Поворот как pygame.transform.rotate: против часовой стрелки, холст поворачивается вокруг своего центра.
func _draw_rotated(texture: Texture2D, top_left: Vector2, frame_size: Vector2, degrees: int) -> void:
	if degrees == 0:
		draw_texture_rect(texture, Rect2(top_left, frame_size), false)
		return
	draw_set_transform(top_left + RULES.rotated_bounds(frame_size, degrees) / 2.0, -deg_to_rad(float(degrees)), Vector2.ONE)
	draw_texture_rect(texture, Rect2(-frame_size / 2.0, frame_size), false)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)


func _ellipse(center: Vector2, radius: Vector2) -> PackedVector2Array:
	var points := PackedVector2Array()
	for index in ELLIPSE_SEGMENTS:
		var angle := TAU * index / ELLIPSE_SEGMENTS
		points.append(center + Vector2(cos(angle) * radius.x, sin(angle) * radius.y))
	return points


static func _box_style(fill: Color, border: Color, radius: int, border_width: int) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = fill
	style.border_color = border
	style.set_border_width_all(border_width)
	style.set_corner_radius_all(radius)
	return style
