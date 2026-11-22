extends Control

# Карточки классов экрана создания из scenes/create_character_scene.py: тот же порядок, цвета, геометрия 450x1000
# (зазор 30, поля 15), подписи и спрайты из deck_class_card_rules.gd. Правила распределения повторяют
# combat/character_stats.py (creation_stats). Кнопки +/- есть только там, где сервер принимает поле stats
# (tower и economy, server/database.py create_character). Deck поле не читает (deck/server/main.py _create_character),
# поэтому его карточки показывают стартовые значения без кнопок и без очков.

signal create_requested
signal unavailable_profession_requested(profession: String)
signal profession_selected(profession: String)

const CLASS_RULES := preload("res://scripts/deck_class_card_rules.gd")
const DETAILS_RULES := preload("res://scripts/create_character_details_rules.gd")
const FRONT_LINE_SPRITES := preload("res://scripts/front_line_hero_sprite_rules.gd")
const PROFESSION_ORDER := ["warrior", "archer", "assassin", "mage"]
const NECROMANCER := "necromancer"
const DECK_MODE := "deck"
const STAT_CONTROL_MODES := ["economy", "front_line"]
const CREATION_STATS := ["strength", "agility", "intuition", "wisdom", "intellect"]
const BASE_STAT_VALUE := 3
const CREATION_ENDURANCE_VALUE := 4
const CREATION_FREE_POINTS := 3
# Стартовые значения Deck: deck/combat/character_stats.py, BASE_STAT_VALUE и STARTING_ENDURANCE_VALUE равны 2
const DECK_FIXED_STAT_VALUE := 2
const MAX_NAME_LENGTH := 15
# Строки блока характеристик, как STAT_ROWS в ui/character_profile.py
const STAT_ROWS := [
	["strength", "Сила"],
	["agility", "Ловкость"],
	["intuition", "Интуиция"],
	["wisdom", "Мудрость"],
	["intellect", "Интеллект"],
	["endurance", "Выносливость"],
]
# Геометрия из create_character_scene.py и ui/character_card.py в пикселях экрана 1920x1080
const CARD_WIDTH := 450.0
const CARD_HEIGHT := 1000.0
const CARD_GAP := 30.0
const CARD_MARGIN := 15.0
# Место над карточками: выбранная карточка поднимается на CARD_LIFT и увеличивается до CARD_SELECT_ZOOM.
const CARD_TOP_PAD := 48.0
const CARD_LIFT := 24.0
const CARD_SELECT_ZOOM := 1.04
const CARD_RADIUS := 10.0
const TEXT_LEFT := 20.0
# Имя сдвинуто вправо на иконку класса и зазор, как name_rect в Python (_draw_header)
const NAME_LEFT := TEXT_LEFT + DETAILS_RULES.ICON_SIZE + DETAILS_RULES.ICON_GAP
const NAME_TOP := 20.0
const LEVEL_TOP := 48.0
const TITLE_GAP := 15.0
# equipment_slots.area_center_y: (151 + 1000 - 180) / 2. Сетка слотов начинается на 180 px выше центра фигуры
const FIGURE_CENTER_Y := 485.5
const FIGURE_GRID_TOP := FIGURE_CENTER_Y - 180.0
const FIGURE_TITLE_FONT_SIZE := 28
const FIGURE_NOTE_FONT_SIZE := 16
const STAT_ROW_HEIGHT := 20.0
const STAT_BOTTOM_GAP := 32.0
const STAT_HEADER_GAP := 28.0
const STAT_CONTROL_TOP := 5.0
const STAT_CONTROL_SIZE := 13.0
const STAT_CONTROL_GAP := 6.0
const STAT_CONTROL_SHIFT_X := 70.0
const STAT_TEXT_PAD := 7.0
const STAT_SAMPLE_TEXT := "Выносливость: 30"
const NAME_FONT_SIZE := 18
const SMALL_FONT_SIZE := 18
const STAT_FONT_SIZE := 16
const TOP_BAR_HEIGHT := 42
const TOP_BAR_GAP := 10
const SELECTED_BORDER := Color8(100, 200, 100)
const CARD_BORDER := Color8(70, 140, 220)
const NAME_COLOR := Color8(240, 240, 245)
const PLACEHOLDER_COLOR := Color8(110, 115, 130)
const LEVEL_COLOR := Color8(210, 215, 225)
const CLASS_TEXT_COLOR := Color8(150, 180, 220)
const HEADING_COLOR := Color8(200, 200, 220)
const STAT_TEXT_COLOR := Color8(255, 255, 255)
const FREE_POINTS_COLOR := Color8(255, 220, 120)
const BUTTON_COLOR := Color8(235, 235, 235)
const BUTTON_TEXT_COLOR := Color8(30, 32, 45)
const MINUS_HOVER_COLOR := Color8(210, 80, 80)
const PLUS_HOVER_COLOR := Color8(120, 220, 120)
const NO_SPRITE_COLOR := Color8(170, 175, 185)
# Слоты, строки веса и полосы: цвета и размер подписей из equipment_slots.py, _draw_info_lines и _draw_resource
const DETAIL_FONT_SIZE := 16
const SLOT_BG := Color8(48, 44, 48)
const SLOT_HOVER := Color8(70, 64, 70)
const SLOT_BORDER := Color8(85, 78, 80)
const SLOT_LABEL_COLOR := Color8(150, 142, 130)
const SLOT_ALPHA := 0.65
const CHIP_BG := Color8(24, 29, 30)
const CHIP_BORDER := Color8(82, 88, 76)
const ATTACK_COLOR := Color8(235, 215, 150)
const MOVE_COLOR := Color8(150, 220, 255)
const REACH_COLOR := Color8(255, 190, 150)
const BAR_BG := Color8(40, 10, 10)
const HP_COLOR := Color8(210, 80, 80)
const MP_COLOR := Color8(60, 140, 220)

var _professions: Array[String] = []
var _stat_controls := false
var _stats_unlocked := true
var _intro_active := false
var _intro_done := false
var _intro_elapsed := 0.0
var _intro_profession := ""
var _selected := ""
var _extra: Dictionary = {}
var _card_scale := 1.0
var _textures: Dictionary = {}
var _base_image: Image
var _base_loaded := false
var _name_input: LineEdit
var _create_button: Button
var _scroll: ScrollContainer
var _canvas: Control
var _icons: Dictionary = {}
var _unavailable_professions: Array[String] = []
var _front_line_draft := false
# Слой анимации выбора: поверх сцены, не обрезается прокруткой карточек.
var _cards_surface: Control
var _intro_layer: CanvasLayer
var _intro_veil: ColorRect
var _intro_card: Control
var _focus_active := false
var _focus_position := Vector2.ZERO
var _focus_scale := Vector2.ONE


func _init() -> void:
	_build_ui()
	configure("")


# Анимация выбора в драфте Front Line: выбранная карточка делает три оборота и приближается, остальные затушёваны.
const INTRO_SECONDS := 3.0
const INTRO_TURNS := 3.0
const INTRO_FILL := 0.9  # выбранная карточка в фокусе занимает столько высоты экрана
const INTRO_MAX_ZOOM := 2.0
const INTRO_BLUR_LOD := 3.0  # сила размытия сцены за карточкой
const INTRO_VEIL := Color(0.05, 0.06, 0.09, 0.6)
const INTRO_VEIL_SHADER := "res://shaders/draft_veil.gdshader"
signal intro_finished

# Режим мира задаёт набор классов и наличие кнопок +/-: Necromancer есть только в Deck.
func configure(mode: String) -> void:
	_stat_controls = stat_controls_for_mode(mode)
	_front_line_draft = mode == "front_line"
	# В драфте Front Line характеристики меняются только после анимации выбора.
	_stats_unlocked = not _front_line_draft
	_intro_active = false
	_intro_done = false
	_intro_profession = ""
	set_process(false)
	_textures.clear()
	_unavailable_professions.clear()
	if _front_line_draft:
		_unavailable_professions.append("assassin")
	_professions.assign(professions_for_mode(mode))
	_extra.clear()
	for profession in _professions:
		_extra[profession] = _zero_extra()
	_selected = _professions[0]
	_refresh_layout()


# Масштаб в базовых единицах Godot: окно 1920x1080 показывает базу 1280x720 (1.5 px на единицу).
# 2/3 даёт карточки 450x1000 px, как в Python на 1920x1080. Ряд, который шире панели, прокручивается внутри view.
func set_card_scale(value: float) -> void:
	_card_scale = clampf(value, 0.3, 2.0)
	_refresh_layout()


static func professions_for_mode(mode: String) -> Array[String]:
	var result: Array[String] = []
	result.assign(PROFESSION_ORDER)
	if mode == DECK_MODE:
		result.append(NECROMANCER)
	return result


static func stat_controls_for_mode(mode: String) -> bool:
	return STAT_CONTROL_MODES.has(mode)


func configure_for_draft(character_name_value: String) -> void:
	_name_input.text = character_name_value
	_name_input.visible = false
	_create_button.text = "Подтвердить выбор"


func set_submit_enabled(enabled: bool) -> void:
	_create_button.disabled = not enabled


# Тот же расчёт, что creation_stats в combat/character_stats.py: абсолютные значения, не ниже базовых, не больше 3 очков.
static func creation_stats(allocation: Dictionary) -> Dictionary:
	for key in allocation.keys():
		if not CREATION_STATS.has(str(key)):
			return _creation_error("Очки можно распределять только в базовые характеристики")
	var stats := {}
	var spent := 0
	for stat in CREATION_STATS:
		var value: Variant = allocation.get(stat, BASE_STAT_VALUE)
		if typeof(value) != TYPE_INT or int(value) < BASE_STAT_VALUE:
			return _creation_error("Характеристика не может быть ниже базовой")
		stats[stat] = int(value)
		spent += int(value) - BASE_STAT_VALUE
	if spent > CREATION_FREE_POINTS:
		return _creation_error("Свободных очков при создании только %d" % CREATION_FREE_POINTS)
	stats["endurance"] = CREATION_ENDURANCE_VALUE
	return {"ok": true, "stats": stats, "free_points": CREATION_FREE_POINTS - spent, "error": ""}


static func assets_root() -> String:
	return CLASS_RULES.default_assets_root(ProjectSettings.globalize_path("res://").trim_suffix("/"))


static func _creation_error(message: String) -> Dictionary:
	return {"ok": false, "stats": {}, "free_points": 0, "error": message}


static func _zero_extra() -> Dictionary:
	var result := {}
	for stat in CREATION_STATS:
		result[stat] = 0
	return result


func selected_profession() -> String:
	return _selected


func professions() -> Array[String]:
	var result: Array[String] = []
	result.assign(_professions)
	return result


func profession_is_available(profession: String) -> bool:
	return not _unavailable_professions.has(profession)


func character_name() -> String:
	return _name_input.text.strip_edges()


func set_character_name(value: String) -> void:
	_name_input.text = value
	_canvas.queue_redraw()


# Абсолютные значения распределяемых характеристик, как CreateCharacterScene.allocation в Python.
func allocation_for(profession: String) -> Dictionary:
	var result := {}
	var extra: Dictionary = _extra.get(profession, {})
	for stat in CREATION_STATS:
		result[stat] = BASE_STAT_VALUE + int(extra.get(stat, 0))
	return result


func free_points(profession: String) -> int:
	var result := creation_stats(allocation_for(profession))
	return int(result["free_points"])


# Значение, которое показывает карточка: у tower и economy считается по правилам создания, у Deck стартовое.
func displayed_stat(profession: String, stat: String) -> int:
	if not _stat_controls:
		return DECK_FIXED_STAT_VALUE
	var result := creation_stats(allocation_for(profession))
	return int(result["stats"].get(stat, 0))


func card_has_sprite(profession: String) -> bool:
	return not CLASS_RULES.class_sprite_file(profession).is_empty()


# Тело запроса POST /api/characters: stats добавляется только для режимов, где сервер его принимает.
func request_body() -> Dictionary:
	var body := {"name": character_name(), "profession_type": _selected}
	if _stat_controls:
		body["stats"] = allocation_for(_selected)
	return body


# Прямоугольник карточки в координатах холста (сам холст прокручивается).
func card_rect(profession: String) -> Rect2:
	var index := _professions.find(profession)
	if index < 0:
		return Rect2()
	return Rect2(_card_origin(index) * _card_scale, Vector2(CARD_WIDTH, CARD_HEIGHT) * _card_scale)


# Смещение и масштаб карточки на холсте: выбранная поднимается и чуть увеличивается относительно своего центра.
func _card_placement(profession: String) -> Dictionary:
	var index := maxi(0, _professions.find(profession))
	var selected := profession == _selected
	var zoom := CARD_SELECT_ZOOM if selected else 1.0
	var pivot := (_card_origin(index) + Vector2(CARD_WIDTH, CARD_HEIGHT) / 2.0) * _card_scale
	var lift := Vector2(0.0, -CARD_LIFT * _card_scale) if selected else Vector2.ZERO
	return {"zoom": zoom, "offset": pivot * (1.0 - zoom) + lift}


# Где базовая точка карточки видна на экране: выбранная поднята и увеличена, остальные на месте.
func card_visual_point(profession: String, base_point: Vector2) -> Vector2:
	var placement := _card_placement(profession)
	return placement["offset"] + base_point * float(placement["zoom"])


# Точка на экране (с учётом подъёма и увеличения) переводится в базовые координаты карточки, как card_rect.
func card_base_point(profession: String, screen_point: Vector2) -> Vector2:
	var placement := _card_placement(profession)
	return (screen_point - placement["offset"]) / float(placement["zoom"])


func card_layout_size() -> Vector2:
	return _canvas.custom_minimum_size


# Строки карточки по текущему распределению: как _card_profile в Python, поэтому меняются вместе с очками.
func details_for(profession: String) -> Dictionary:
	if _stat_controls:
		var result := creation_stats(allocation_for(profession))
		var details := DETAILS_RULES.tower_details(result["stats"])
		if _front_line_draft:
			var intuition := int(result["stats"].get("intuition", 0))
			details["reach_text"] = "Дальность атаки: %d" % DETAILS_RULES.front_line_attack_range(profession, intuition)
		return details
	return DETAILS_RULES.deck_details(profession)


# Прямоугольник слота в координатах холста, как card_rect.
func slot_rect(profession: String, slot: String) -> Rect2:
	var index := _professions.find(profession)
	var rects := DETAILS_RULES.slot_rects()
	if index < 0 or not rects.has(slot):
		return Rect2()
	return _to_canvas(rects[slot], _card_origin(index))


func stat_control_rect(profession: String, stat: String, delta: int) -> Rect2:
	var index := _professions.find(profession)
	var row := _stat_index(stat)
	if index < 0 or row < 0:
		return Rect2()
	var pair: Array[Rect2] = _stat_control_rects(row)
	return _to_canvas(pair[0] if delta < 0 else pair[1], _card_origin(index))


# Возвращает {"stat": имя, "delta": 1 или -1} для кнопки под точкой, иначе пустой словарь. Плюс проверяется раньше минуса.
func stat_control_at(profession: String, position: Vector2) -> Dictionary:
	if not _stat_controls or not _stats_unlocked:
		return {}
	for stat in CREATION_STATS:
		for delta: int in [1, -1]:
			if stat_control_rect(profession, stat, delta).has_point(position):
				return {"stat": stat, "delta": delta}
	return {}


func adjust_stat(profession: String, stat: String, delta: int) -> bool:
	if not _stat_controls or not _stats_unlocked or not CREATION_STATS.has(stat) or not _extra.has(profession):
		return false
	var extra: Dictionary = _extra[profession]
	if delta > 0:
		if free_points(profession) <= 0:
			return false
		extra[stat] = int(extra[stat]) + 1
	elif delta < 0:
		if int(extra[stat]) <= 0:
			return false
		extra[stat] = int(extra[stat]) - 1
	else:
		return false
	_canvas.queue_redraw()
	return true


# Клик по карточке выбирает класс; клик по кнопке на карточке дополнительно меняет характеристику (как в Python).
func click_at(position: Vector2) -> void:
	if _intro_active:
		return
	for profession in _professions:
		var local := card_base_point(profession, position)
		if not card_rect(profession).has_point(local):
			continue
		if not profession_is_available(profession):
			unavailable_profession_requested.emit(profession)
			return
		# Выбор подтверждён и герой в фокусе: другие карточки и их характеристики не меняются.
		if _focus_active:
			return
		_selected = profession
		profession_selected.emit(profession)
		var control := stat_control_at(profession, local)
		if not control.is_empty():
			adjust_stat(profession, str(control["stat"]), int(control["delta"]))
		_canvas.queue_redraw()
		return


func _build_ui() -> void:
	var layout := VBoxContainer.new()
	layout.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	layout.add_theme_constant_override("separation", TOP_BAR_GAP)
	add_child(layout)

	var top_bar := HBoxContainer.new()
	top_bar.add_theme_constant_override("separation", 10)
	layout.add_child(top_bar)
	_name_input = LineEdit.new()
	_name_input.placeholder_text = "Имя персонажа"
	_name_input.max_length = MAX_NAME_LENGTH
	_name_input.custom_minimum_size = Vector2(0, TOP_BAR_HEIGHT)
	_name_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_name_input.text_changed.connect(_on_name_changed)
	_name_input.text_submitted.connect(_on_name_submitted)
	top_bar.add_child(_name_input)
	_create_button = Button.new()
	_create_button.text = "Создать персонажа"
	_create_button.custom_minimum_size = Vector2(190, TOP_BAR_HEIGHT)
	_create_button.pressed.connect(_on_create_pressed)
	top_bar.add_child(_create_button)

	_scroll = ScrollContainer.new()
	_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	layout.add_child(_scroll)
	_canvas = Control.new()
	_canvas.mouse_filter = Control.MOUSE_FILTER_PASS
	# Проект по умолчанию использует ближайшего соседа; для фигур нужна фильтрация с мипмапами при уменьшении.
	_canvas.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	_canvas.draw.connect(_paint_cards)
	_canvas.gui_input.connect(_on_canvas_gui_input)
	_scroll.add_child(_canvas)
	_cards_surface = _canvas
	_build_intro_layers()
	visibility_changed.connect(_on_visibility_changed)


func _refresh_layout() -> void:
	var count := _professions.size()
	var width := CARD_MARGIN * 2.0 + count * CARD_WIDTH + maxi(0, count - 1) * CARD_GAP
	_canvas.custom_minimum_size = Vector2(width, CARD_HEIGHT + CARD_TOP_PAD) * _card_scale
	custom_minimum_size = Vector2(0, TOP_BAR_HEIGHT + TOP_BAR_GAP + (CARD_HEIGHT + CARD_TOP_PAD) * _card_scale)
	_canvas.queue_redraw()


func _on_canvas_gui_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		_canvas.queue_redraw()
		return
	var mouse := event as InputEventMouseButton
	if mouse == null or not mouse.pressed or mouse.button_index != MOUSE_BUTTON_LEFT:
		return
	if _name_input.has_focus():
		_name_input.release_focus()
	click_at(mouse.position)
	_canvas.accept_event()


func _on_name_changed(_text: String) -> void:
	_canvas.queue_redraw()


func _on_name_submitted(_text: String) -> void:
	create_requested.emit()


func _on_create_pressed() -> void:
	create_requested.emit()


func _paint_cards() -> void:
	for profession in _professions:
		if _is_lifted(profession):
			continue
		_paint_card(profession)


# Карточка выбранного класса во время анимации и в фокусе рисуется в слое поверх сцены.
func _is_lifted(profession: String) -> bool:
	return (_intro_active or _focus_active) and profession == _intro_profession


func _paint_card(profession: String) -> void:
	var origin := _card_origin(_professions.find(profession))
	var selected := profession == _selected
	var placement := _card_placement(profession)
	if _is_lifted(profession):
		_paint_intro_transform(profession, origin, placement)
	else:
		_canvas.draw_set_transform(placement["offset"], 0.0, Vector2.ONE * float(placement["zoom"]))
	var style := StyleBoxFlat.new()
	style.bg_color = CLASS_RULES.card_background(profession)
	style.set_corner_radius_all(roundi(CARD_RADIUS * _card_scale))
	style.set_border_width_all(maxi(1, roundi((3.0 if selected else 2.0) * _card_scale)))
	style.border_color = SELECTED_BORDER if selected else CARD_BORDER
	_canvas.draw_style_box(style, card_rect(profession))
	var details := details_for(profession)
	_paint_header(profession, origin, details)
	_paint_figure(profession, origin)
	_paint_slots(origin)
	if _stat_controls:
		_paint_info_lines(origin, details)
	_paint_stats(profession, origin)
	if not profession_is_available(profession):
		_paint_unavailable_card(profession, origin)
	_canvas.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)


# Прогресс анимации 0..1 для выбранной карточки.
func intro_progress() -> float:
	return clampf(_intro_elapsed / INTRO_SECONDS, 0.0, 1.0)


# Выбранная карточка едет от своего места к центру экрана, три раза поворачивается и увеличивается.
# Рисуется в слое поверх сцены, поэтому её не обрезает прокрутка. После анимации остаётся в центре (фокус):
# характеристики меняются только там.
func _paint_intro_transform(_profession: String, origin: Vector2, placement: Dictionary) -> void:
	var progress := intro_progress()
	var ease_t := 1.0 - pow(1.0 - progress, 3.0)
	var base_zoom := float(placement["zoom"])
	var pivot := (origin + Vector2(CARD_WIDTH, CARD_HEIGHT) / 2.0) * _card_scale
	var start_center: Vector2 = _cards_surface.get_global_transform() * (placement["offset"] + pivot * base_zoom)
	var viewport_size := get_viewport().get_visible_rect().size
	var fit_zoom := minf(viewport_size.y * INTRO_FILL / (CARD_HEIGHT * _card_scale), INTRO_MAX_ZOOM)
	var zoom := lerpf(base_zoom, fit_zoom, ease_t)
	var turn := absf(cos(progress * INTRO_TURNS * TAU))
	var scale_vector := Vector2(zoom * maxf(0.04, turn), zoom)
	var center: Vector2 = start_center.lerp(viewport_size / 2.0, ease_t)
	var offset: Vector2 = center - scale_vector * pivot
	_intro_card.draw_set_transform(offset, 0.0, scale_vector)
	_focus_position = offset
	_focus_scale = scale_vector


# Слой: затемнённая размытая сцена и карточка поверх неё. Создаётся один раз.
func _build_intro_layers() -> void:
	_intro_layer = CanvasLayer.new()
	_intro_layer.layer = 20
	_intro_layer.visible = false
	add_child(_intro_layer)

	_intro_veil = ColorRect.new()
	_intro_veil.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_intro_veil.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var veil_material := ShaderMaterial.new()
	veil_material.shader = load(INTRO_VEIL_SHADER)
	_intro_veil.material = veil_material
	_intro_layer.add_child(_intro_veil)

	_intro_card = Control.new()
	_intro_card.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_intro_card.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_intro_card.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	_intro_card.draw.connect(_paint_intro_card)
	_intro_layer.add_child(_intro_card)


func _paint_intro_card() -> void:
	if not _intro_active and not _focus_active:
		return
	var saved := _canvas
	_canvas = _intro_card
	_paint_card(_intro_profession)
	_canvas = saved


# Запускает анимацию выбора один раз: до её конца характеристики нельзя менять.
func play_selection_intro() -> void:
	if not _front_line_draft or _intro_active or _intro_done:
		return
	_intro_profession = _selected
	_intro_active = true
	_intro_elapsed = 0.0
	_stats_unlocked = false
	_intro_layer.visible = true
	set_process(true)
	_update_veil(0.0)
	_canvas.queue_redraw()


func _process(delta: float) -> void:
	if not _intro_active:
		set_process(false)
		return
	_intro_elapsed += delta
	var progress := intro_progress()
	_update_veil(progress)
	if progress >= 1.0:
		_intro_active = false
		_intro_done = true
		_stats_unlocked = true
		_focus_active = true
		set_process(false)
		intro_finished.emit()
	_canvas.queue_redraw()
	_intro_card.queue_redraw()


func _update_veil(progress: float) -> void:
	var amount := 1.0 - pow(1.0 - progress, 2.0)
	var veil_material := _intro_veil.material as ShaderMaterial
	veil_material.set_shader_parameter("blur_lod", amount * INTRO_BLUR_LOD)
	veil_material.set_shader_parameter(
		"veil_color", Color(INTRO_VEIL.r, INTRO_VEIL.g, INTRO_VEIL.b, INTRO_VEIL.a * amount)
	)


# В фокусе клик по характеристикам карточки меняет их; клик вне карточки возвращает её в ряд.
# Фокус выбранной карточки: клик внутри неё меняет её характеристики; клик мимо проходит дальше,
# фокус остаётся, и «Подтвердить выбор» работает.
func _input(event: InputEvent) -> void:
	if not _focus_active or not is_visible_in_tree():
		return
	var mouse := event as InputEventMouseButton
	if mouse == null or not mouse.pressed or mouse.button_index != MOUSE_BUTTON_LEFT:
		return
	var local := (mouse.position - _focus_position) / _focus_scale
	if not card_rect(_intro_profession).has_point(local):
		return
	get_viewport().set_input_as_handled()
	var control := stat_control_at(_intro_profession, local)
	if not control.is_empty():
		adjust_stat(_intro_profession, str(control["stat"]), int(control["delta"]))
	_intro_card.queue_redraw()


func _end_focus() -> void:
	_focus_active = false
	_intro_card.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_intro_layer.visible = false
	_canvas.queue_redraw()


func _on_visibility_changed() -> void:
	if not is_visible_in_tree() and _intro_layer != null:
		_intro_layer.visible = false
		_focus_active = false
		_intro_card.mouse_filter = Control.MOUSE_FILTER_IGNORE


func _paint_unavailable_card(profession: String, origin: Vector2) -> void:
	_canvas.draw_rect(card_rect(profession), Color(0.35, 0.36, 0.39, 0.78))
	var center := (origin + Vector2(CARD_WIDTH / 2.0, FIGURE_CENTER_Y)) * _card_scale
	_draw_centered("В разработке", center, Color8(205, 205, 210), FIGURE_TITLE_FONT_SIZE)
	_draw_centered("Выбор недоступен", center + Vector2(0, 30 * _card_scale), Color8(170, 172, 180), FIGURE_NOTE_FONT_SIZE)


func _paint_header(profession: String, origin: Vector2, details: Dictionary) -> void:
	var icon_box := Rect2(
		Vector2(TEXT_LEFT, NAME_TOP + _design_height(NAME_FONT_SIZE) / 2.0 - DETAILS_RULES.ICON_SIZE / 2.0),
		Vector2(DETAILS_RULES.ICON_SIZE, DETAILS_RULES.ICON_SIZE),
	)
	_canvas.draw_style_box(_box_style(CHIP_BG, CHIP_BORDER, 4.0, 1.0), _to_canvas(icon_box, origin))
	var icon := _icon_texture(profession)
	if icon != null:
		_canvas.draw_texture_rect(icon, _to_canvas(icon_box, origin), false)
	var entered_name := character_name()
	if entered_name.is_empty():
		_draw_text("Имя персонажа", origin + Vector2(NAME_LEFT, NAME_TOP), PLACEHOLDER_COLOR, NAME_FONT_SIZE)
	else:
		_draw_text(entered_name, origin + Vector2(NAME_LEFT, NAME_TOP), NAME_COLOR, NAME_FONT_SIZE)
	_draw_text("Уровень 1", origin + Vector2(TEXT_LEFT, LEVEL_TOP), LEVEL_COLOR, SMALL_FONT_SIZE)
	var title_x := TEXT_LEFT + _design_width("Уровень 1", SMALL_FONT_SIZE) + TITLE_GAP
	_draw_text(CLASS_RULES.class_title(profession), origin + Vector2(title_x, LEVEL_TOP), CLASS_TEXT_COLOR, SMALL_FONT_SIZE)
	_paint_resource(origin, DETAILS_RULES.HP_BAR, str(details["hp_text"]), _ratio(details["hp"], details["max_hp"]), HP_COLOR)
	_paint_resource(origin, DETAILS_RULES.MP_BAR, str(details["mp_text"]), _ratio(details["mp"], details["max_mp"]), MP_COLOR)


func _paint_figure(profession: String, origin: Vector2) -> void:
	var texture := _figure_texture(profession)
	if texture == null:
		var center := (origin + Vector2(CARD_WIDTH / 2.0, FIGURE_CENTER_Y)) * _card_scale
		_draw_centered(CLASS_RULES.class_title(profession), center, NAME_COLOR, FIGURE_TITLE_FONT_SIZE)
		_draw_centered("без спрайта", center + Vector2(0, 36 * _card_scale), NO_SPRITE_COLOR, FIGURE_NOTE_FONT_SIZE)
		return
	# Сетка слотов Python (406 px по высоте) задаёт масштаб и центр фигуры, как в deck_character_card.gd
	var grid_size := Vector2(CARD_WIDTH, CLASS_RULES.PY_SLOT_GRID_SPAN) * _card_scale
	var figure := CLASS_RULES.figure_rect(grid_size, texture.get_size(), CLASS_RULES.sprite_offset_x(profession))
	figure.position += (origin + Vector2(0.0, FIGURE_GRID_TOP)) * _card_scale
	_canvas.draw_texture_rect(texture, figure, false)


func _paint_stats(profession: String, origin: Vector2) -> void:
	var header_y := _stat_row_top(0) - STAT_HEADER_GAP
	_draw_text("ХАРАКТЕРИСТИКИ", origin + Vector2(TEXT_LEFT, header_y), HEADING_COLOR, STAT_FONT_SIZE)
	if _stat_controls:
		var points_text := "Свободные очки: %d" % free_points(profession)
		var points_x := CARD_WIDTH - TEXT_LEFT - _design_width(points_text, STAT_FONT_SIZE)
		_draw_text(points_text, origin + Vector2(points_x, header_y), FREE_POINTS_COLOR, STAT_FONT_SIZE)
	for index in range(STAT_ROWS.size()):
		var stat := str(STAT_ROWS[index][0])
		var label := str(STAT_ROWS[index][1])
		var row_text := "%s: %d" % [label, displayed_stat(profession, stat)]
		_draw_text(row_text, origin + Vector2(TEXT_LEFT, _stat_row_top(index)), STAT_TEXT_COLOR, STAT_FONT_SIZE)
		if _stat_controls and _stats_unlocked and CREATION_STATS.has(stat):
			_paint_stat_button(profession, stat, -1)
			_paint_stat_button(profession, stat, 1)


func _paint_stat_button(profession: String, stat: String, delta: int) -> void:
	var rect := stat_control_rect(profession, stat, delta)
	var hovered := rect.has_point(_canvas.get_local_mouse_position())
	var style := StyleBoxFlat.new()
	if hovered:
		style.bg_color = MINUS_HOVER_COLOR if delta < 0 else PLUS_HOVER_COLOR
	else:
		style.bg_color = BUTTON_COLOR
	style.set_corner_radius_all(roundi(3.0 * _card_scale))
	_canvas.draw_style_box(style, rect)
	_draw_centered("-" if delta < 0 else "+", rect.get_center(), BUTTON_TEXT_COLOR, STAT_FONT_SIZE)


func _paint_slots(origin: Vector2) -> void:
	var rects := DETAILS_RULES.slot_rects()
	var mouse := _canvas.get_local_mouse_position()
	for entry in DETAILS_RULES.SLOT_LAYOUT:
		var rect := _to_canvas(rects[str(entry[0])], origin)
		var fill := SLOT_HOVER if rect.has_point(mouse) else SLOT_BG
		_canvas.draw_style_box(_box_style(Color(fill, SLOT_ALPHA), SLOT_BORDER, 6.0, 2.0), rect)
		_draw_centered(str(entry[1]), rect.get_center(), SLOT_LABEL_COLOR, DETAIL_FONT_SIZE)


# Строки веса, скорости и дальности под слотом обуви, как _draw_info_lines в Python: плашка по центру карточки.
func _paint_info_lines(origin: Vector2, details: Dictionary) -> void:
	var lines := [
		[str(details["weight_text"]), details["weight_color"]],
		[str(details["attack_text"]), ATTACK_COLOR],
		[str(details["move_text"]), MOVE_COLOR],
		[str(details["reach_text"]), REACH_COLOR],
	]
	var top := DETAILS_RULES.info_top(DETAILS_RULES.slot_rects())
	for line in lines:
		var text: String = line[0]
		var box_size := Vector2(
			_design_width(text, DETAIL_FONT_SIZE) + 2.0 * DETAILS_RULES.CHIP_PAD_X,
			_design_height(DETAIL_FONT_SIZE) + 2.0 * DETAILS_RULES.CHIP_PAD_Y,
		)
		var box := Rect2(Vector2(CARD_WIDTH / 2.0 - box_size.x / 2.0, top), box_size)
		var canvas_box := _to_canvas(box, origin)
		_canvas.draw_style_box(_box_style(CHIP_BG, CHIP_BORDER, 4.0, 1.0), canvas_box)
		_draw_centered(text, canvas_box.get_center(), line[1], DETAIL_FONT_SIZE)
		top = box.end.y + DETAILS_RULES.CHIP_GAP


# Полоска с подписью над ней, как _draw_resource в Python: подпись на 2 px выше полоски.
func _paint_resource(origin: Vector2, bar: Rect2, text: String, ratio: float, color: Color) -> void:
	var label_top := bar.position.y - _design_height(SMALL_FONT_SIZE) - 2.0
	_draw_text(text, origin + Vector2(bar.position.x, label_top), LEVEL_COLOR, SMALL_FONT_SIZE)
	var rect := _to_canvas(bar, origin)
	_canvas.draw_rect(rect, BAR_BG)
	_canvas.draw_rect(Rect2(rect.position, Vector2(rect.size.x * ratio, rect.size.y)), color)


func _ratio(value: Variant, maximum: Variant) -> float:
	return clampf(float(int(value)) / float(maxi(1, int(maximum))), 0.0, 1.0)


func _icon_texture(profession: String) -> Texture2D:
	if not _icons.has(profession):
		var texture: Texture2D = null
		var path := DETAILS_RULES.class_icon_path(assets_root(), profession)
		if not path.is_empty():
			var image := Image.load_from_file(path)
			if image != null and not image.is_empty():
				image.convert(Image.FORMAT_RGBA8)
				var icon_size := Vector2i(DETAILS_RULES.ICON_SIZE, DETAILS_RULES.ICON_SIZE)
				if image.get_size() != icon_size:
					image.resize(icon_size.x, icon_size.y, Image.INTERPOLATE_BILINEAR)
				image.generate_mipmaps()
				texture = ImageTexture.create_from_image(image)
		_icons[profession] = texture
	return _icons[profession]


func _box_style(bg: Color, border: Color, radius: float, border_width: float) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = bg
	style.border_color = border
	style.set_corner_radius_all(roundi(radius * _card_scale))
	style.set_border_width_all(maxi(1, roundi(border_width * _card_scale)))
	return style


func _design_height(design_size: int) -> float:
	return get_theme_default_font().get_height(design_size)


# Текст рисуется от верхнего левого угла в координатах карточки (design px), как draw_text в Python.
func _draw_text(text: String, design_position: Vector2, color: Color, design_size: int) -> void:
	var font := get_theme_default_font()
	var font_size := roundi(design_size * _card_scale)
	var top_left := design_position * _card_scale
	_canvas.draw_string(font, top_left + Vector2(0, font.get_ascent(font_size)), text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, color)


# center в координатах холста (px), размер шрифта в design px.
func _draw_centered(text: String, center: Vector2, color: Color, design_size: int) -> void:
	var font := get_theme_default_font()
	var font_size := roundi(design_size * _card_scale)
	var width := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x
	var top := center.y - font.get_height(font_size) / 2.0
	_canvas.draw_string(font, Vector2(center.x - width / 2.0, top + font.get_ascent(font_size)), text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, color)


func _design_width(text: String, design_size: int) -> float:
	return get_theme_default_font().get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, design_size).x


func _card_origin(index: int) -> Vector2:
	return Vector2(CARD_MARGIN + index * (CARD_WIDTH + CARD_GAP), CARD_TOP_PAD)


func _stat_row_top(index: int) -> float:
	return CARD_HEIGHT - STAT_BOTTOM_GAP - (STAT_ROWS.size() - 1 - index) * STAT_ROW_HEIGHT


func _stat_index(stat: String) -> int:
	for index in range(STAT_ROWS.size()):
		if str(STAT_ROWS[index][0]) == stat:
			return index
	return -1


# Кнопки «−» и «+» в локальных координатах карточки, как CharacterCard._stat_control_rects в Python.
func _stat_control_rects(row: int) -> Array[Rect2]:
	var text_right := TEXT_LEFT + _design_width(STAT_SAMPLE_TEXT, SMALL_FONT_SIZE) + STAT_TEXT_PAD + STAT_CONTROL_SHIFT_X
	var top := _stat_row_top(row) + STAT_CONTROL_TOP
	var minus := Rect2(text_right + STAT_CONTROL_GAP, top, STAT_CONTROL_SIZE, STAT_CONTROL_SIZE)
	var plus := Rect2(minus.end.x + STAT_CONTROL_GAP, top, STAT_CONTROL_SIZE, STAT_CONTROL_SIZE)
	var result: Array[Rect2] = [minus, plus]
	return result


func _to_canvas(local: Rect2, origin: Vector2) -> Rect2:
	return Rect2((origin + local.position) * _card_scale, local.size * _card_scale)


func _figure_texture(profession: String) -> Texture2D:
	if _textures.has(profession):
		return _textures[profession]
	var texture: Texture2D = null
	var base := _base_figure()
	var path := CLASS_RULES.class_art_path(assets_root(), profession)
	if base != null and _front_line_draft:
		var hero_sprite: Texture2D = FRONT_LINE_SPRITES.frame_texture(profession, "idle", "s", 2)
		if hero_sprite != null:
			var source := hero_sprite.get_image()
			var fitted := CLASS_RULES.fit_figure(source, base.get_size(), base.get_used_rect())
			fitted.generate_mipmaps()
			texture = ImageTexture.create_from_image(fitted)
	if texture == null and base != null and not path.is_empty():
		var source := Image.load_from_file(path)
		if source != null and not source.is_empty():
			var fitted := CLASS_RULES.fit_figure(source, base.get_size(), base.get_used_rect())
			fitted.generate_mipmaps()
			texture = ImageTexture.create_from_image(fitted)
	_textures[profession] = texture
	return texture


func _base_figure() -> Image:
	if not _base_loaded:
		_base_loaded = true
		var image := Image.load_from_file(CLASS_RULES.base_figure_path(assets_root()))
		if image != null and not image.is_empty():
			image.convert(Image.FORMAT_RGBA8)
			_base_image = image
	return _base_image
