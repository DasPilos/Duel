extends Control

# Другие игроки на карте мира Deck: маркеры поверх карты и карточка при наведении.
# Порт draw_active_players, draw_afk_players, player_at и draw_player_hover_card из deck/ui/player_presence.py.
# Слой не принимает мышь: клик по игроку уходит на плитку под ним, как раньше (в Python клик по маркеру ничего не делает).
# Карточка лежит в CanvasLayer, чтобы её не обрезала карта; в Python она рисуется последней, поверх всего экрана.

const RULES := preload("res://scripts/deck_presence_rules.gd")
const PLAYER_RULES := preload("res://scripts/deck_player_sprite_rules.gd")
const CHARACTER_RULES := preload("res://scripts/deck_character_rules.gd")
const CARD_SCRIPT := preload("res://scripts/deck_character_card.gd")
const CARD_LAYER := 1
const CARD_MARGIN := Vector2(5.0, 10.0)
# Прозрачность фона карточки: 225 из 255, как overlay.fill в CharacterCard.draw.
const CARD_ALPHA := 225.0 / 255.0
const ELLIPSE_SEGMENTS := 20
const NAME_FONT_SIZE := 11
const GLYPH_FONT_SIZE := 9
const ICON_SIZE := 15.0
const ICON_GAP := 4.0
const LABEL_PAD_X := 4.0
const LABEL_PAD_Y := 2.0
const SHADOW_COLOR := Color8(16, 17, 20)
const ACTIVE_HEAD_COLOR := Color8(218, 190, 153)
const ACTIVE_BODY_COLOR := Color8(74, 126, 102)
const ACTIVE_NAME_COLOR := Color8(184, 224, 255)
const ACTIVE_LABEL_FILL := Color8(17, 23, 29)
const ACTIVE_LABEL_BORDER := Color8(79, 139, 179)
const AFK_TINT := Color8(135, 139, 145)
const AFK_HEAD_COLOR := Color8(145, 149, 153)
const AFK_BODY_COLOR := Color8(100, 105, 112)
const AFK_NAME_COLOR := Color8(153, 157, 163)
const AFK_LABEL_FILL := Color8(20, 22, 26)
const AFK_LABEL_BORDER := Color8(105, 109, 115)
const GLYPH_COLOR := Color8(250, 250, 250)

var _occupants: Array = []
var _own_id := ""
var _location := "world_map"
var _to_local := Callable()
var _idle: Dictionary = {}
var _active: Array = []
var _afk: Array = []
var _hovered: Dictionary = {}
var _hovered_key := ""
var _mouse := Vector2.ZERO
var _blocked := false
var _last_global := Vector2.INF
var _last_size := Vector2.INF
var _last_viewport := Vector2.INF
var _draws := 0
var _motions := 0
var _styles: Dictionary = {}
var _glyph_font: Font
var _card_layer: CanvasLayer
var _card


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_card_layer = CanvasLayer.new()
	_card_layer.layer = CARD_LAYER
	add_child(_card_layer)
	_card = CARD_SCRIPT.new()
	_card.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_ignore_mouse(_card)
	_card.visible = false
	_card_layer.add_child(_card)


# state: occupants (список social), own_id, location, world_to_local (Callable: мировая точка → окно карты),
# assets_root (по умолчанию ../assets, как у слоя фигурок).
func configure(state: Dictionary) -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_occupants = state.get("occupants", [])
	_own_id = str(state.get("own_id", ""))
	_location = str(state.get("location", "world_map"))
	_to_local = state.get("world_to_local", Callable())
	var root := str(state.get("assets_root", ""))
	if root.is_empty():
		root = PLAYER_RULES.assets_root(ProjectSettings.globalize_path("res://"))
	_idle = PLAYER_RULES.directional_frames(root.path_join(PLAYER_RULES.IDLE_FOLDER), PLAYER_RULES.PLAYER_TARGET_HEIGHT)
	_build_entries()
	queue_redraw()


# Окно карты скользит между плитками: позиции игроков пересчитываются на каждом кадре движения, без нового configure.
func refresh_positions() -> void:
	if not _to_local.is_valid():
		return
	_build_entries()
	_update_hover()
	queue_redraw()


# Мышь от deck_world.gd (InputEventMouseMotion). blocked — открыто окно поверх карты, наведения нет.
func forward_mouse_motion(point: Vector2, blocked: bool) -> void:
	_motions += 1
	_mouse = point
	_blocked = blocked
	_update_hover()


# Карта могла сдвинуться (прокрутка, перестройка, первая раскладка) без движения мыши: перерисовываем и проверяем наведение.
func _process(_delta: float) -> void:
	var viewport := get_viewport_rect().size
	if global_position == _last_global and size == _last_size and viewport == _last_viewport:
		return
	_last_global = global_position
	_last_size = size
	_last_viewport = viewport
	queue_redraw()
	_update_hover()


func _draw() -> void:
	_draws += 1
	var viewport := get_viewport_rect().size
	for entry in _active:
		if RULES.on_screen(_screen(entry), viewport):
			_draw_active(entry)
	for entry in _afk:
		if RULES.on_screen(_screen(entry), viewport):
			_draw_afk(entry)


func draw_count() -> int:
	return _draws


func motion_count() -> int:
	return _motions


func active_names() -> Array:
	return _names(_active)


func afk_names() -> Array:
	return _names(_afk)


func hovered_name() -> String:
	return RULES.display_name(_hovered) if not _hovered.is_empty() else ""


func card_visible() -> bool:
	return _card.visible


func card_node():
	return _card


# Экранная точка маркера игрока по character_id; Vector2.INF, если маркера нет.
func screen_of(character_id: Variant) -> Vector2:
	for entry in _active + _afk:
		if RULES.id_text((entry["occupant"] as Dictionary).get("character_id")) == RULES.id_text(character_id):
			return _screen(entry)
	return Vector2.INF


func _build_entries() -> void:
	_active = []
	_afk = []
	if not _to_local.is_valid():
		return
	for occupant in RULES.active_occupants(_occupants, _location, _own_id):
		_active.append(_entry(occupant))
	for occupant in RULES.afk_occupants(_occupants, _location):
		_afk.append(_entry(occupant))


func _entry(occupant: Dictionary) -> Dictionary:
	var world := Vector2(float(occupant.get("position_x", 0.0)), float(occupant.get("position_y", 0.0)))
	var direction := RULES.direction_of(occupant)
	return {
		"occupant": occupant,
		"local": _to_local.call(world),
		"direction": direction,
		"frames": _idle.get(direction, []),
	}


func _screen(entry: Dictionary) -> Vector2:
	var local: Vector2 = entry["local"]
	return local + global_position


func _names(entries: Array) -> Array:
	var names: Array = []
	for entry in entries:
		names.append(RULES.display_name(entry["occupant"]))
	return names


# Активный игрок: спрайт стойки первого кадра направления (ноги в точке мира), подпись над ним.
# Без кадров — фолбэк из фигур, как в Python.
func _draw_active(entry: Dictionary) -> void:
	var local: Vector2 = entry["local"]
	var frames: Array = entry["frames"]
	var name_bottom := local.y - 44.0
	if frames.is_empty():
		_draw_fallback(local, ACTIVE_HEAD_COLOR, ACTIVE_BODY_COLOR)
	else:
		var sprite: Texture2D = frames[0]
		var rect := PLAYER_RULES.player_frame_rect(local, Vector2i(sprite.get_size()))
		draw_texture_rect(sprite, rect, false)
		name_bottom = rect.position.y - 4.0
	var occupant: Dictionary = entry["occupant"]
	_draw_name_box(RULES.display_name(occupant), local.x, name_bottom, ACTIVE_NAME_COLOR, _style(ACTIVE_LABEL_FILL, ACTIVE_LABEL_BORDER, 3, 1))


# AFK: спрайт с множителем (135, 139, 145), подпись «(АФК)» с иконкой класса слева.
func _draw_afk(entry: Dictionary) -> void:
	var local: Vector2 = entry["local"]
	var frames: Array = entry["frames"]
	var name_bottom := local.y - 44.0
	if frames.is_empty():
		_draw_fallback(local, AFK_HEAD_COLOR, AFK_BODY_COLOR)
	else:
		var sprite: Texture2D = frames[0]
		var rect := PLAYER_RULES.player_frame_rect(local, Vector2i(sprite.get_size()))
		draw_texture_rect(sprite, rect, false, AFK_TINT)
		name_bottom = rect.position.y - 4.0
	var occupant: Dictionary = entry["occupant"]
	_draw_afk_label(occupant, local.x, name_bottom)


func _draw_fallback(local: Vector2, head: Color, body: Color) -> void:
	draw_colored_polygon(_ellipse(local + Vector2(0.0, 1.0), Vector2(14.0, 5.0)), SHADOW_COLOR)
	draw_circle(local + Vector2(0.0, -28.0), 7.0, head)
	draw_style_box(_style(body, body, 3, 0), Rect2(local.x - 6.0, local.y - 21.0, 12.0, 17.0))


func _draw_name_box(text: String, center_x: float, bottom: float, text_color: Color, box: StyleBoxFlat) -> void:
	var font := ThemeDB.fallback_font
	var text_size := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, NAME_FONT_SIZE)
	var text_rect := Rect2(Vector2(center_x - text_size.x / 2.0, bottom - text_size.y), text_size)
	draw_style_box(box, text_rect.grow_individual(LABEL_PAD_X, LABEL_PAD_Y, LABEL_PAD_X, LABEL_PAD_Y))
	draw_string(font, text_rect.position + Vector2(0.0, font.get_ascent(NAME_FONT_SIZE)), text, HORIZONTAL_ALIGNMENT_LEFT, -1, NAME_FONT_SIZE, text_color)


func _draw_afk_label(occupant: Dictionary, center_x: float, name_bottom: float) -> void:
	var font := ThemeDB.fallback_font
	var text := RULES.afk_label(occupant)
	var text_size := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, NAME_FONT_SIZE)
	var group_left := center_x - (ICON_SIZE + ICON_GAP + text_size.x) / 2.0
	var label_rect := Rect2(group_left + ICON_SIZE + ICON_GAP, name_bottom - text_size.y, text_size.x, text_size.y)
	var icon_rect := Rect2(group_left, name_bottom - text_size.y + (text_size.y - ICON_SIZE) / 2.0, ICON_SIZE, ICON_SIZE)
	draw_style_box(_style(AFK_LABEL_FILL, AFK_LABEL_BORDER, 3, 1), label_rect.merge(icon_rect).grow_individual(LABEL_PAD_X, LABEL_PAD_Y, LABEL_PAD_X, LABEL_PAD_Y))
	_draw_class_icon(icon_rect, RULES.class_type(occupant))
	draw_string(font, label_rect.position + Vector2(0.0, font.get_ascent(NAME_FONT_SIZE)), text, HORIZONTAL_ALIGNMENT_LEFT, -1, NAME_FONT_SIZE, AFK_NAME_COLOR)


# Значок класса как class_icon в deck/ui/class_identity.py: квадрат 15 px с фоном класса, рамкой и буквой.
func _draw_class_icon(rect: Rect2, profession: String) -> void:
	var palette := CHARACTER_RULES.class_palette(profession)
	draw_style_box(_style(palette["icon_background"], palette["accent"], 3, 1), rect)
	var font := _glyph()
	var glyph := str(palette["glyph"])
	var glyph_size := font.get_string_size(glyph, HORIZONTAL_ALIGNMENT_LEFT, -1, GLYPH_FONT_SIZE)
	var line_height := font.get_ascent(GLYPH_FONT_SIZE) + font.get_descent(GLYPH_FONT_SIZE)
	var baseline := rect.position.y + (rect.size.y - line_height) / 2.0 + font.get_ascent(GLYPH_FONT_SIZE)
	draw_string(font, Vector2(rect.get_center().x - glyph_size.x / 2.0, baseline), glyph, HORIZONTAL_ALIGNMENT_LEFT, -1, GLYPH_FONT_SIZE, GLYPH_COLOR)


func _glyph() -> Font:
	if _glyph_font == null:
		var bold := FontVariation.new()
		bold.base_font = ThemeDB.fallback_font
		bold.variation_embolden = 0.6
		_glyph_font = bold
	return _glyph_font


func _update_hover() -> void:
	var hovered: Dictionary = {}
	if not _blocked and RULES.contains(Rect2(Vector2.ZERO, size), _mouse - global_position):
		hovered = RULES.player_at(_hit_entries(), _mouse)
	_set_hovered(hovered)


func _hit_entries() -> Array:
	var entries: Array = []
	for entry in _active:
		entries.append({"occupant": entry["occupant"], "screen": _screen(entry)})
	return entries


func _set_hovered(occupant: Dictionary) -> void:
	var key := "" if occupant.is_empty() else RULES.id_text(occupant.get("character_id"))
	if key == _hovered_key:
		return
	_hovered_key = key
	_hovered = occupant
	if occupant.is_empty():
		_card.visible = false
		return
	_show_card(occupant)


# Карточка персонажа с полями из RULES.card_profile; рамка и фон — палитра класса, как в CharacterCard.draw.
func _show_card(occupant: Dictionary) -> void:
	var profile := CHARACTER_RULES.normalize_profile(RULES.card_profile(occupant), "", "player")
	var palette := CHARACTER_RULES.class_palette(str(profile["type"]))
	_card.set_profile(profile, "", palette["accent"], false, null)
	_card.add_theme_stylebox_override("panel", _card_style(palette))
	var card_size: Vector2 = _card.get_combined_minimum_size()
	_card.size = card_size
	_card.position = Vector2(get_viewport_rect().size.x - card_size.x - CARD_MARGIN.x, CARD_MARGIN.y)
	_card.visible = true


func _card_style(palette: Dictionary) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color(palette["background"], CARD_ALPHA)
	style.border_color = palette["accent"]
	style.set_border_width_all(2)
	style.set_corner_radius_all(8)
	style.set_content_margin_all(6)
	return style


func _style(fill: Color, border: Color, radius: int, border_width: int) -> StyleBoxFlat:
	var key := "%s|%s|%d|%d" % [fill.to_html(), border.to_html(), radius, border_width]
	if not _styles.has(key):
		var style := StyleBoxFlat.new()
		style.bg_color = fill
		style.border_color = border
		style.set_border_width_all(border_width)
		style.set_corner_radius_all(radius)
		_styles[key] = style
	return _styles[key]


func _ellipse(center: Vector2, radius: Vector2) -> PackedVector2Array:
	var points := PackedVector2Array()
	for index in ELLIPSE_SEGMENTS:
		var angle := TAU * index / ELLIPSE_SEGMENTS
		points.append(center + Vector2(cos(angle) * radius.x, sin(angle) * radius.y))
	return points


func _ignore_mouse(node: Node) -> void:
	for child in node.get_children():
		if child is Control:
			child.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_ignore_mouse(child)
