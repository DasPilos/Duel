extends RefCounted

# Раскладка и модель отрисовки боя Калоды. Чистые функции без сцены; сцена — deck_battle_view.gd.
# Источники Python: deck/settings.py (прямоугольники, тайминги), deck/ui/layout.py,
# deck/ui/renderers/card_area.py (card_rect 79-111, draft_slot_rect 121-149, draw 151-, draw_choice_area 902,
# _draw_card_in_rect 925, _draw_card_availability 967, _draw_card_costs 1237, колода и сброс 859-870),
# deck/ui/duel_renderer.py (фон 49-64, заглушка удара 282-287, draw_turn_timer 289-318,
# угловые карточки 455-535, статистика 761-800, заголовок результата 115-135).
# Снимок: deck/server/battles.py:snapshot (506-546). Ключ image_path у карты в снимке не приходит
# (_card_payload 174-185); если он есть, путь разрешается как в card_area.py:841-857.

const CHARACTER_RULES := preload("res://scripts/deck_character_rules.gd")
const MAGE_RULES := preload("res://scripts/deck_battle_mage_rules.gd")
const STATUS_RULES := preload("res://scripts/deck_battle_status_rules.gd")

const DESIGN_SIZE := Vector2(1920, 1080)  # core/settings.py:2-3
const CARD_SIZE := Vector2(150, 200)  # card_area.py:18-19
const CARD_GAP := 20  # card_area.py:20
const MIN_CARD_WIDTH := 50  # card_area.py:92-107 (max(50, ...))
const DRAFT_COLUMNS := 5  # card_area.py:21
const STARTING_DRAFT_COLUMNS := 11  # card_area.py:22
const STARTING_DRAFT_GAP := 8  # card_area.py:23
const STARTING_DRAFT_TOP_OFFSET := 48  # card_area.py:133
const MAX_HAND_SIZE := 7  # deck/combat/card_battle.py:30 (бонус таланта hand_size не приходит в снимке)

const CARD_TABLE_RECT := Rect2(160, 325, 1600, 430)  # deck/settings.py:CARD_TABLE_RECT
const PLAYER_HAND_RECT := Rect2(10, 850, 1900, 220)  # deck/settings.py:PLAYER_HAND_RECT
const ENEMY_HAND_RECT := Rect2(10, 10, 1900, 220)  # deck/settings.py:ENEMY_HAND_RECT
const PLAYER_SELECTED_RECT := Rect2(350, 535, 1200, 200)  # deck/settings.py:PLAYER_SELECTED_RECT
const ENEMY_SELECTED_RECT := Rect2(350, 325, 1200, 200)  # deck/settings.py:ENEMY_SELECTED_RECT
const DECK_RECT := Rect2(1584, 440, 150, 200)  # deck/settings.py:DECK_RECT
const DISCARD_RECT := Rect2(186, 440, 150, 200)  # deck/settings.py:DISCARD_RECT
const TURN_BAR_RECT := Rect2(820, 831, 280, 11)  # deck/settings.py:TURN_BAR_RECT
const HIT_OVERLAY_RECT := Rect2(896, 456, 128, 128)  # duel_renderer.py:285-287 (центр 960, 520)
const PILE_STACK_OFFSETS := [8, 5, 2]  # card_area.py:859-866
# Прямоугольники обычного стола: по ним строятся все поля; макет мага подставляется через layout_for_state.
const STANDARD_LAYOUT := {
	"card_table": CARD_TABLE_RECT,
	"player_hand": PLAYER_HAND_RECT,
	"enemy_hand": ENEMY_HAND_RECT,
	"player_selected": PLAYER_SELECTED_RECT,
	"enemy_selected": ENEMY_SELECTED_RECT,
	"deck": DECK_RECT,
	"discard": DISCARD_RECT,
	"turn_bar": TURN_BAR_RECT,
}

const CORNER_CARD_SIZE := Vector2(310, 170)  # duel_renderer.py:_draw_corner_fighter_card
const CORNER_CARD_TOP := 10  # duel_renderer.py:draw_battle_stats (y=10)
const CORNER_CARD_LEFT := 10  # duel_renderer.py:draw_battle_stats (x=10)
const CORNER_CARD_RIGHT_INSET := 320  # duel_renderer.py:draw_battle_stats (x=screen_width - 320)
const CORNER_INNER_INSET := 12  # duel_renderer.py:_draw_corner_fighter_card (inner_x = x + 12)
const CORNER_ICON_SIZE := 15  # deck/ui/class_identity.py:CLASS_ICON_SIZE
const CORNER_NAME_GAP := 6
const CORNER_NAME_TOP := 8
const CORNER_LEVEL_TOP := 28
const BAR_WIDTH := 280  # duel_renderer.py:_draw_corner_fighter_card (bar_width)
const BAR_HEIGHT := 11
const BAR_TOP := 62  # duel_renderer.py:BAR_TOP
const BAR_STEP := 36  # duel_renderer.py:BAR_STEP
const BAR_LABEL_LIFT := 15  # duel_renderer.py:_draw_resource_bar (y - 15)
const BAR_DROP := 4  # duel_renderer.py:_draw_resource_bar (y + 4)

const STATS_PANEL_HEIGHT := 200  # duel_renderer.py:STATS_PANEL_HEIGHT
const STATS_PANEL_BOTTOM_GAP := 30  # duel_renderer.py:draw_battle_stats (screen_height - 200 - 30)
const STATS_PANEL_MIN_WIDTH := 310  # duel_renderer.py:_stats_frame_geometry (default_width)
const STATS_MARGIN := 10  # duel_renderer.py:_stats_frame_geometry (margin)
const STATS_HAND_GAP := 6  # duel_renderer.py:_stats_frame_geometry (6)
const STATS_TEXT_INSET := 12  # duel_renderer.py:_draw_corner_stats (inner_x = x + 12)
const STATS_HEADER_TOP := 8
const STATS_ROW_TOP := 24  # duel_renderer.py:_draw_corner_stats (header_y + 24)
const STATS_ROW_HEIGHT := 22  # duel_renderer.py:STATS_ROW_HEIGHT
const STATS_DERIVED_COLUMN := 190  # duel_renderer.py:_draw_corner_stats (col2_x = inner_x + 190)

const TURN_DECISION_SECONDS := 60  # core/settings.py:TURN_DECISION_SECONDS
const FONT_NAME := "arial"  # core/settings.py:FONT_NAME
const TURN_WARNING_YELLOW_SECONDS := 30  # core/settings.py:TURN_WARNING_YELLOW_SECONDS
const TURN_WARNING_RED_SECONDS := 10  # core/settings.py:TURN_WARNING_RED_SECONDS
const DRAW_CHOICE_SECONDS := 15  # deck/settings.py:DRAW_CHOICE_SECONDS
const DRAFT_TIMEOUT_SECONDS := 90  # deck/settings.py:DRAFT_TIMEOUT_SECONDS

# Анимации боя (deck/settings.py) и всплывающие числа (deck/scenes/duel_resolver.py).
const ATTACK_ANIMATION_SECONDS := 0.5  # settings.py: ATTACK_ANIMATION_SECONDS (клэш)
const DAMAGE_ANIMATION_SECONDS := 1.0  # settings.py: DAMAGE_ANIMATION_SECONDS (урон)
const DECK_SHUFFLE_SECONDS := 2.0  # settings.py: DECK_SHUFFLE_SECONDS
const CARD_MOVE_SECONDS := 1.0  # settings.py: CARD_MOVE_SECONDS (раздача стартового драфта)
const PLAYER_DRAFT_PICK_MOVE_SECONDS := 0.5  # settings.py: PLAYER_DRAFT_PICK_MOVE_SECONDS
const TABLE_TO_HAND_MOVE_SECONDS := 0.5  # settings.py: TABLE_TO_HAND_MOVE_SECONDS (выбор соперника)
const DRAFT_CARD_DELAY_SECONDS := 0.03  # settings.py: DRAFT_CARD_DELAY_SECONDS
const DRAFT_REVEAL_START_DELAY_SECONDS := 1.0  # settings.py: DRAFT_REVEAL_START_DELAY_SECONDS
const DRAFT_INTRO_SECONDS := 2.0  # duel_scene.py: intro_table 1 с + intro_deck 1 с перед раздачей
const DRAFT_REVEAL_TAIL_SECONDS := 0.05  # duel_scene.py: запас в reveal_duration
const FLOATING_TEXT_SECONDS := 10.0  # duel_resolver.py: FLOATING_TEXT_DURATION = FPS * 10 при 60 FPS
const FLOATING_TEXT_LINE_HEIGHT := 30  # duel_resolver.py: FLOATING_TEXT_LINE_HEIGHT
const FLOATING_TEXT_PANEL_GAP := 18  # duel_resolver.py: FLOATING_TEXT_PANEL_GAP
const FLOATING_TEXT_FONT_SIZE := 24  # settings.py: BIG_FONT_SIZE (scene.big)
const FLOATING_CRITICAL_FONT_SIZE := 25  # duel_resolver.py: critical_font (BritannicBold нет, arial 25)
const FLOATING_IMAGE_LABEL_LIFT := 28  # duel_resolver.py: FloatingImage.draw, rect.bottom - 28
const FLOATING_TEXT_BOX := Vector2(320, 40)  # запас под подпись; подпись центрируется, как в Python
const TEXT_COLOR := Color8(230, 230, 230)  # core/settings.py: TEXT_COLOR (обычный урон)
const DAMAGE_COLOR := Color8(255, 60, 60)  # core/settings.py: DAMAGE_COLOR (крит, HP-N)
const DODGE_COLOR := Color8(150, 220, 255)  # core/settings.py: DODGE_COLOR (УВОРОТ, БЛОК, HP-0, +N%)
const EFFECT_TEXT_COLOR := Color8(255, 220, 120)  # duel_resolver.py: _add_floating_effect
const HEAL_TEXT_COLOR := Color8(110, 235, 120)  # duel_resolver.py: _add_floating_heal
const DAMAGE_RESULT_ASSET := "combat/damage_result.png"  # duel_resolver.py: _load_result_image
const DODGED_RESULT_ASSET := "combat/dodged_result.png"  # duel_resolver.py: _load_result_image

const BACKGROUND_ASSET := "combat/background.png"  # duel_renderer.py:51
const TABLE_ASSET := "combat/battle_table.png"  # card_area.py:64
const HIT_PLACEHOLDER_ASSET := "combat/hit_placeholder.png"  # duel_renderer.py:58 (файла в assets нет)
const CARD_BACK_ASSET := "cards/backs/card_back.png"  # card_area.py:70

const ZONE_HAND := "hand"
const ZONE_SELECTED := "selected"
const ZONE_TABLE := "table"
const ZONE_DRAW_CHOICES := "draw_choices"

const COLOR_BACKGROUND_FALLBACK := Color8(16, 18, 28)  # duel_renderer.py:draw (fill)
const COLOR_RESULT_BACKGROUND := Color8(25, 27, 38)  # duel_renderer.py:draw_result
const COLOR_TABLE_FALLBACK := Color8(27, 31, 43)  # card_area.py:157
const COLOR_TABLE_FRAME := Color8(125, 111, 76)  # card_area.py:168
const COLOR_CARD_BORDER := Color8(190, 170, 110)  # card_area.py:_draw_card_front_scaled / _draw_card_in_rect
const COLOR_CARD_FACE := Color8(48, 53, 70)
const COLOR_CARD_SELECTED := Color8(55, 135, 80)
const COLOR_CARD_AVAILABLE := Color8(45, 105, 68)
const COLOR_CARD_DIM := Color8(5, 7, 12, 105)  # card_area.py:_draw_card_availability
const COLOR_CARD_DIM_BORDER := Color8(90, 82, 75)
const COLOR_GLOW := Color8(80, 235, 125, 80)
const COLOR_AVAILABLE_BORDER := Color8(115, 255, 145)
const COLOR_MARKER_BACKGROUND := Color8(30, 52, 34)
const COLOR_BACK_FALLBACK := Color8(57, 63, 88)  # card_area.py:_draw_card_back (без картинки)
const COLOR_BACK_INNER := Color8(43, 48, 70)
const COLOR_PILE_TITLE := Color8(245, 225, 160)  # card_area.py:_draw_pile_count
const COLOR_PILE_BADGE := Color8(15, 17, 24, 205)
const COLOR_PILE_BADGE_BORDER := Color8(225, 200, 120)
const COLOR_TIMER_TRACK := Color8(55, 58, 68)  # duel_renderer.py:draw_turn_timer
const COLOR_TIMER_RED := Color8(220, 70, 70)
const COLOR_TIMER_YELLOW := Color8(230, 190, 70)
const COLOR_TIMER_GREEN := Color8(80, 200, 120)
const COLOR_TIMER_TEXT := Color8(245, 240, 225)
const COLOR_DRAFT_TITLE := Color8(230, 210, 150)  # card_area.py:draw (draft title)
const COLOR_DRAFT_MESSAGE := Color8(170, 170, 170)
const COLOR_DRAFT_TIMER := Color8(245, 225, 150)  # card_area.py:_draw_draft_timer
const COLOR_DRAFT_TIMER_BACKGROUND := Color8(25, 31, 34)
const COLOR_DRAFT_TIMER_BORDER := Color8(105, 150, 110)
const COLOR_PLAYER_BORDER := Color8(80, 180, 120)  # duel_renderer.py:draw_battle_stats
const COLOR_ENEMY_BORDER := Color8(210, 80, 80)
const COLOR_STATS_BACKGROUND := Color8(30, 32, 45, 200)  # duel_renderer.py:_draw_corner_stats
const COLOR_STAT_TEXT := Color8(215, 220, 225)
const COLOR_NAME_TEXT := Color8(240, 240, 245)
const COLOR_LEVEL_TEXT := Color8(210, 215, 225)
const COLOR_BAR_TEXT := Color8(220, 225, 235)
const COLOR_BAR_TRACK := Color8(50, 50, 50)
const COLOR_HP := Color8(210, 80, 80)
const COLOR_MP := Color8(60, 140, 220)
const COLOR_RESULT_WIN := Color8(110, 235, 120)  # duel_renderer.py:draw_result
const COLOR_RESULT_LOSS := Color8(235, 110, 100)
const COLOR_RESULT_DRAW := Color8(255, 220, 120)
const COLOR_RESULT_WINNER := Color8(220, 220, 225)
const DEFAULT_NAME_COLOR := Color8(245, 235, 210)  # card_area.py:_draw_card_in_rect
const DEFAULT_COST_COLOR := Color8(230, 220, 190)  # card_area.py:_draw_card_costs

const RESOURCE_BARS := {
	"rage": {"label": "Ярость", "color": Color8(200, 100, 80)},
	"accuracy": {"label": "Меткость", "color": Color8(105, 190, 105)},
	"concentration": {"label": "Концентрация", "color": Color8(180, 120, 200)},
}  # duel_renderer.py:RESOURCE_BARS
const RESOURCE_COST_LABELS := {
	"mana": "МАНА",
	"rage": "ЯР.",
	"accuracy": "МЕТ.",
	"concentration": "КОНЦ.",
	"unique": "РЕС.",
}  # card_area.py:RESOURCE_COST_LABELS
const RESOURCE_COST_COLORS := {
	"mana": Color8(115, 190, 240),
	"rage": Color8(235, 105, 95),
	"accuracy": Color8(135, 210, 130),
	"concentration": Color8(190, 145, 235),
	"unique": Color8(120, 220, 135),
}  # card_area.py:RESOURCE_COST_COLORS
const STAT_ROWS := [
	["strength", "Сила"],
	["agility", "Ловкость"],
	["intuition", "Интуиция"],
	["wisdom", "Мудрость"],
	["intellect", "Интеллект"],
	["harmony", "Гармония"],
	["endurance", "Выносливость"],
]  # duel_renderer.py:ALL_STATS
const DERIVED_ORDER := ["Урон", "Уворот", "Крит", "Маг Урон"]  # duel_renderer.py:_draw_corner_stats
const DERIVED_COLORS := {
	"Урон": Color8(255, 255, 255),
	"Уворот": Color8(150, 220, 255),
	"Крит": Color8(255, 90, 90),
	"Маг Урон": Color8(180, 140, 240),
}
const RESULT_TITLES := {"win": "ПОБЕДА", "loss": "ПОРАЖЕНИЕ", "draw": "НИЧЬЯ"}


static func project_root(project_dir: String) -> String:
	return project_dir.path_join("..").simplify_path()


static func assets_root(project_dir: String) -> String:
	return project_dir.path_join("../assets").simplify_path()


static func asset_path(project_dir: String, relative_path: String) -> String:
	return assets_root(project_dir).path_join(relative_path)


# Путь к картинке карты: относительный путь считается от корня Python-проекта (card_area.py:846-849).
static func resolve_image_path(image_path: String, project_dir: String) -> String:
	if image_path.is_empty():
		return ""
	if image_path.is_absolute_path():
		return image_path
	return project_root(project_dir).path_join(image_path).simplify_path()


static func row_card_rect(area: Rect2, count: int, index: int) -> Rect2:
	var spacing_total := CARD_GAP * maxi(0, count - 1)
	var width := mini(int(CARD_SIZE.x), maxi(MIN_CARD_WIDTH, (int(area.size.x) - spacing_total) / maxi(1, count)))
	var total_width := width * count + spacing_total
	var start_x := _center_x(area) - total_width / 2
	var height := mini(int(CARD_SIZE.y), int(area.size.y))
	return Rect2(start_x + index * (width + CARD_GAP), area.position.y, width, height)


static func draft_columns(draft_mode: String) -> int:
	return STARTING_DRAFT_COLUMNS if draft_mode == "starting" else DRAFT_COLUMNS


static func draft_slot_rect(draft_mode: String, index: int, table: Rect2 = CARD_TABLE_RECT) -> Rect2:
	var starting := draft_mode == "starting"
	var columns := draft_columns(draft_mode)
	var gap := STARTING_DRAFT_GAP if starting else CARD_GAP
	var width := int(CARD_SIZE.x)
	var height := int(CARD_SIZE.y)
	if starting:
		width = mini(int(CARD_SIZE.x), (int(table.size.x) - gap * (columns - 1)) / columns)
		height = roundi(float(width) * CARD_SIZE.y / CARD_SIZE.x)
	var total_width := columns * width + (columns - 1) * gap
	var left := _center_x(table) - total_width / 2
	var top := 0
	if starting:
		top = int(table.position.y) + STARTING_DRAFT_TOP_OFFSET
	else:
		top = _center_y(table) - (2 * height + gap) / 2
	var row := index / columns
	var column := index % columns
	return Rect2(left + column * (width + gap), top + row * (height + gap), width, height)


# Порт card_area.py:113-119: новые карты сбрасывают слоты, убранные карты оставляют пустой слот.
static func draft_slot_keys(previous_keys: Array, table_keys: Array) -> Array:
	for key in table_keys:
		if not previous_keys.has(key):
			return table_keys.duplicate()
	var slots: Array = []
	for key in previous_keys:
		slots.append(key if table_keys.has(key) else null)
	return slots


static func draw_choice_area(side: String, layout: Dictionary = STANDARD_LAYOUT) -> Rect2:
	var base: Rect2 = layout["enemy_selected"] if side == "enemy" else layout["player_selected"]
	return Rect2(base.position.x, base.position.y + 24, base.size.x, base.size.y - 24)


static func corner_card_rect(side: String) -> Rect2:
	var left: float = DESIGN_SIZE.x - CORNER_CARD_RIGHT_INSET if side == "enemy" else float(CORNER_CARD_LEFT)
	return Rect2(left, CORNER_CARD_TOP, CORNER_CARD_SIZE.x, CORNER_CARD_SIZE.y)


static func stats_panel_rect(side: String, hand_limit: int = MAX_HAND_SIZE, layout: Dictionary = STANDARD_LAYOUT) -> Rect2:
	var panel_top := DESIGN_SIZE.y - STATS_PANEL_HEIGHT - STATS_PANEL_BOTTOM_GAP
	var limit := maxi(1, hand_limit)
	if side == "enemy":
		var last_card := row_card_rect(layout["enemy_hand"], limit, limit - 1)
		var left := last_card.end.x + STATS_HAND_GAP
		return Rect2(left, panel_top, maxf(STATS_PANEL_MIN_WIDTH, DESIGN_SIZE.x - STATS_MARGIN - left), STATS_PANEL_HEIGHT)
	var first_card := row_card_rect(layout["player_hand"], limit, 0)
	var width := maxf(STATS_PANEL_MIN_WIDTH, first_card.position.x - STATS_HAND_GAP - STATS_MARGIN)
	return Rect2(STATS_MARGIN, panel_top, width, STATS_PANEL_HEIGHT)


static func pile_rect(which: String, layout: Dictionary = STANDARD_LAYOUT) -> Rect2:
	var rect: Rect2 = layout["discard"] if which == "discard" else layout["deck"]
	return rect


# Макет стола по профессии бойца: маг получает прямоугольники mage_battle_scene.py.
static func layout_for_state(state: Dictionary) -> Dictionary:
	return MAGE_RULES.LAYOUT if MAGE_RULES.is_mage(state) else STANDARD_LAYOUT


static func timer_total_seconds(phase: String) -> int:
	if phase == "planning":
		return TURN_DECISION_SECONDS
	if phase == "draw":
		return DRAW_CHOICE_SECONDS
	if phase == "draft":
		return DRAFT_TIMEOUT_SECONDS
	return 0


static func timer_fraction(seconds_left: int, total_seconds: int) -> float:
	if total_seconds <= 0:
		return 0.0
	return clampf(float(maxi(0, seconds_left)) / float(total_seconds), 0.0, 1.0)


static func timer_color(seconds_left: int) -> Color:
	if seconds_left <= TURN_WARNING_RED_SECONDS:
		return COLOR_TIMER_RED
	if seconds_left <= TURN_WARNING_YELLOW_SECONDS:
		return COLOR_TIMER_YELLOW
	return COLOR_TIMER_GREEN


static func timer_label(phase: String, seconds_left: int) -> String:
	if phase == "draw":
		return "ВЫБОР КАРТЫ: %d СЕК" % maxi(0, seconds_left)
	return "ВАШ ХОД"


static func draft_timer_text(seconds_left: int) -> String:
	return "ОСТАЛОСЬ %d СЕК" % maxi(0, seconds_left)


static func bar_fraction(current: float, maximum: float) -> float:
	if maximum <= 0.0:
		return 0.0
	return clampf(current / maximum, 0.0, 1.0)


static func resource_bar_spec(unique_resource_type: String) -> Dictionary:
	if not RESOURCE_BARS.has(unique_resource_type):
		return {}
	return (RESOURCE_BARS[unique_resource_type] as Dictionary).duplicate()


static func card_fill_color(selected: bool, available: bool) -> Color:
	if selected:
		return COLOR_CARD_SELECTED
	if available:
		return COLOR_CARD_AVAILABLE
	return COLOR_CARD_FACE


static func card_name_color(resource_type: String) -> Color:
	return RESOURCE_COST_COLORS.get(resource_type, DEFAULT_NAME_COLOR)


static func card_cost_color(resource_type: String) -> Color:
	return RESOURCE_COST_COLORS.get(resource_type, DEFAULT_COST_COLOR)


# card_area.py:_draw_card_costs: "{стоимость} {метка}"; у необротного ресурса Некроманта метка другая.
static func card_cost_text(card: Dictionary, player_unique_type: String) -> String:
	var resource := str(card.get("resource_type", ""))
	var label := str(RESOURCE_COST_LABELS.get(resource, ""))
	if resource == "unique" and player_unique_type == "necrotism":
		label = "НЕКРОТИЗМА"
	return ("%d %s" % [_int_of(card.get("resource_cost", 0)), label]).strip_edges()


static func card_entry(zone: String, index: int, card: Dictionary, rect: Rect2, state: Dictionary, project_dir: String, unique_type: String) -> Dictionary:
	var resource := str(card.get("resource_type", ""))
	var selected := bool(state.get("selected", false))
	var available := bool(state.get("available", false))
	return {
		"zone": zone,
		"index": index,
		"rect": rect,
		"card": card,
		"hidden": false,
		"selected": selected,
		"available": available,
		"highlight": bool(state.get("highlight", false)),
		"pressable": bool(state.get("pressable", false)),
		"face_path": resolve_image_path(str(card.get("image_path", "")), project_dir),
		"fill_color": card_fill_color(selected, available),
		"name_color": card_name_color(resource),
		"cost_text": card_cost_text(card, unique_type),
		"cost_color": card_cost_color(resource),
	}


static func hidden_card_entry(rect: Rect2) -> Dictionary:
	return {
		"zone": "",
		"index": -1,
		"rect": rect,
		"card": {},
		"hidden": true,
		"selected": false,
		"available": false,
		"highlight": false,
		"pressable": false,
		"face_path": "",
		"fill_color": COLOR_CARD_FACE,
		"name_color": DEFAULT_NAME_COLOR,
		"cost_text": "",
		"cost_color": DEFAULT_COST_COLOR,
	}


static func characteristics(fighter: Dictionary) -> Dictionary:
	var stat_rows: Array = []
	var derived_rows: Array = []
	if fighter.is_empty():
		return {"stats": stat_rows, "derived": derived_rows}
	var stats := _dict_of(fighter.get("stats", {}))
	for pair in STAT_ROWS:
		var stat_key := str(pair[0])
		var stat_label := str(pair[1])
		stat_rows.append({
			"key": stat_key,
			"text": "%s: %d" % [stat_label, _int_of(stats.get(stat_key, 0))],
		})
	var derived := CHARACTER_RULES.derived_values(CHARACTER_RULES.normalize_profile(fighter))
	for key in DERIVED_ORDER:
		if derived.has(key):
			derived_rows.append({
				"key": key,
				"text": "%s: %s" % [key, str(derived[key])],
				"color": DERIVED_COLORS[key],
			})
	return {"stats": stat_rows, "derived": derived_rows}


static func fighter_panel(side: String, fighter: Dictionary, layout: Dictionary = STANDARD_LAYOUT, attacker_type: String = "") -> Dictionary:
	var profession := str(fighter.get("type", "warrior"))
	var palette := CHARACTER_RULES.class_palette(profession)
	var bars: Array = [
		_bar_entry("hp", "HP", _int_of(fighter.get("hp", 0)), _int_of(fighter.get("max_hp", 0)), COLOR_HP, BAR_TOP),
		_bar_entry("mp", "MP", _int_of(fighter.get("mp", 0)), _int_of(fighter.get("max_mp", 0)), COLOR_MP, BAR_TOP + BAR_STEP),
	]
	var resource := resource_bar_spec(str(fighter.get("unique_resource_type", "")))
	if not resource.is_empty():
		bars.append(_bar_entry(
			"resource",
			str(resource["label"]),
			_int_of(fighter.get("unique_resource", 0)),
			_int_of(fighter.get("unique_resource_max", 0)),
			resource["color"],
			BAR_TOP + 2 * BAR_STEP,
		))
	var shield := _int_of(fighter.get("shield", 0))
	bars[0]["text"] = str(bars[0]["text"]) + STATUS_RULES.shield_bar_suffix(shield)
	var corner := corner_card_rect(side)
	var hp_bar := Rect2(corner.position.x + CORNER_INNER_INSET, corner.position.y + BAR_TOP + BAR_DROP, BAR_WIDTH, BAR_HEIGHT)
	return {
		"side": side,
		"rect": corner,
		"border_color": COLOR_PLAYER_BORDER if side == "player" else COLOR_ENEMY_BORDER,
		"palette": palette,
		"glyph": str(palette.get("glyph", "")),
		"name": str(fighter.get("name", "")),
		"level_text": "" if fighter.is_empty() else "Уровень %d" % _int_of(fighter.get("level", 0)),
		"bars": bars,
		"shield": shield,
		"shield_rect": STATUS_RULES.shield_overlay_rect(
			hp_bar, float(_int_of(fighter.get("hp", 0))), float(_int_of(fighter.get("max_hp", 0))), shield,
		),
		"status_rows": STATUS_RULES.status_rows(fighter, attacker_type),
		"stats_rect": stats_panel_rect(side, MAX_HAND_SIZE, layout),
		"characteristics": characteristics(fighter),
	}


static func result_panel(outcome: String, side: String, fighter: Dictionary, opponent: Dictionary) -> Dictionary:
	var title := str(RESULT_TITLES.get(outcome, "БОЙ ОКОНЧЕН"))
	var title_color: Color = COLOR_RESULT_DRAW
	if outcome == "win":
		title_color = COLOR_RESULT_WIN
	elif outcome == "loss":
		title_color = COLOR_RESULT_LOSS
	var own_name := str(fighter.get("name", "")) if side == "player" else str(opponent.get("name", ""))
	var other_name := str(opponent.get("name", "")) if side == "player" else str(fighter.get("name", ""))
	var winner := "Ничья"
	if outcome == "win" and not own_name.is_empty():
		winner = own_name
	elif outcome == "loss" and not other_name.is_empty():
		winner = other_name
	return {
		"title": title,
		"title_color": title_color,
		"winner_text": "Победитель: %s" % winner,
	}


static func build_draw_model(snapshot: Dictionary, options: Dictionary = {}) -> Dictionary:
	var layout := layout_for_state(snapshot)
	var project_dir := str(options.get("project_dir", ""))
	var phase := str(snapshot.get("phase", ""))
	var side := str(snapshot.get("side", "player"))
	var fighter := _dict_of(snapshot.get("fighter", {}))
	var opponent := _dict_of(snapshot.get("opponent", {}))
	var draft_mode := str(snapshot.get("draft_mode", ""))
	var confirmed := bool(snapshot.get("confirmed", false))
	var hand := _array_of(snapshot.get("hand", []))
	var table := _array_of(snapshot.get("table", []))
	var draw_choices := _array_of(snapshot.get("draw_choices", []))
	var selected_keys := _string_list(snapshot.get("selected", []))
	var can_select_keys := _string_list(snapshot.get("can_select", []))
	var unique_type := str(fighter.get("unique_resource_type", ""))
	var seconds_left := _int_of(snapshot.get("seconds_left", 0))
	var slots := _array_of(options.get("draft_slot_keys", []))
	var cards: Array = []
	var is_result := phase == "result"
	var shows_hand := phase == "planning" or phase == "draw" or phase == "draft"

	if phase == "draft":
		slots = draft_slot_keys(slots, _keys_of(table))
		var used_table := {}
		for slot_index in range(slots.size()):
			if slots[slot_index] == null:
				continue
			var table_index := _index_of_key(table, str(slots[slot_index]), used_table)
			if table_index < 0:
				continue
			used_table[table_index] = true
			cards.append(card_entry(
				ZONE_TABLE,
				table_index,
				_dict_of(table[table_index]),
				draft_slot_rect(draft_mode, slot_index, layout["card_table"]),
				{"pressable": true},
				project_dir,
				unique_type,
			))

	if shows_hand:
		var taken_hand := _selected_hand_indices(hand, selected_keys) if phase == "planning" else {}
		var visible_hand: Array = []
		for index_in_hand in range(hand.size()):
			if not taken_hand.has(index_in_hand):
				visible_hand.append(index_in_hand)
		for position in range(visible_hand.size()):
			var hand_index: int = visible_hand[position]
			var hand_card := _dict_of(hand[hand_index])
			var card_key := str(hand_card.get("key", ""))
			var highlight := phase == "planning" or phase == "draw"
			# Сервер хранит выбор ключом: вторая копия уже выбранной карты видна, но выбрать её нельзя.
			var key_chosen := phase == "planning" and selected_keys.has(card_key)
			var available := highlight and can_select_keys.has(card_key) and not key_chosen
			var selected := phase == "draft" or (phase == "draw" and selected_keys.has(card_key))
			cards.append(card_entry(
				ZONE_HAND,
				hand_index,
				hand_card,
				row_card_rect(layout["player_hand"], visible_hand.size(), position),
				{
					"selected": selected,
					"available": available,
					"highlight": highlight,
					"pressable": phase == "planning" and available and not confirmed,
				},
				project_dir,
				unique_type,
			))

	if phase == "planning":
		var found: Array = []
		var used_hand := {}
		for key_index in range(selected_keys.size()):
			var found_index := _index_of_key(hand, selected_keys[key_index], used_hand)
			if found_index < 0:
				continue
			used_hand[found_index] = true
			found.append([key_index, found_index])
		for position in range(found.size()):
			var pair: Array = found[position]
			cards.append(card_entry(
				ZONE_SELECTED,
				int(pair[0]),
				_dict_of(hand[int(pair[1])]),
				row_card_rect(layout["player_selected"], found.size(), position),
				{"selected": true, "pressable": not confirmed},
				project_dir,
				unique_type,
			))

	if phase == "draw":
		var choice_area := draw_choice_area("player", layout)
		for choice_index in range(draw_choices.size()):
			cards.append(card_entry(
				ZONE_DRAW_CHOICES,
				choice_index,
				_dict_of(draw_choices[choice_index]),
				row_card_rect(choice_area, draw_choices.size(), choice_index),
				{"pressable": true},
				project_dir,
				unique_type,
			))

	var timer_visible := phase == "planning" or phase == "draw"
	var timer_total := timer_total_seconds(phase)
	var redraft := draft_mode == "redraft"
	return {
		"phase": phase,
		"show_board": not is_result,
		"show_result": is_result,
		"result": result_panel(str(snapshot.get("outcome", "")), side, fighter, opponent) if is_result else {},
		"show_timer": timer_visible,
		"timer": {
			"seconds_left": maxi(0, seconds_left),
			"total": timer_total,
			"fraction": timer_fraction(seconds_left, timer_total),
			"color": timer_color(seconds_left),
			"label": timer_label(phase, seconds_left),
		},
		"show_draft": phase == "draft",
		"draft": {
			"title": "ПОВТОРНЫЙ ДРАФТ" if redraft else "СТАРТОВЫЙ ДРАФТ",
			"message": "Выберите две карты" if redraft else "Выберите две стартовые карты",
			"timer_text": draft_timer_text(seconds_left),
		},
		"piles": {
			"deck": {"rect": pile_rect("deck", layout), "title": "ВАША КОЛОДА"},
			"discard": {"rect": pile_rect("discard", layout), "title": "ВАШ СБРОС"},
		},
		"fighters": {
			"player": fighter_panel("player", fighter, layout, str(opponent.get("type", ""))),
			"enemy": fighter_panel("enemy", opponent, layout, str(fighter.get("type", ""))),
		},
		"summons": STATUS_RULES.summon_panel(_array_of(fighter.get("summons", [])), _array_of(opponent.get("summons", [])), layout["discard"]),
		"cards": cards,
		"draft_slot_keys": slots,
		"layout": layout,
		"mage": MAGE_RULES.is_mage(snapshot),
		"background_path": asset_path(project_dir, BACKGROUND_ASSET),
		"table_path": asset_path(project_dir, TABLE_ASSET),
	}


static func _bar_entry(key: String, label: String, current: int, maximum: int, color: Color, offset_y: int) -> Dictionary:
	return {
		"key": key,
		"text": "%s: %d/%d" % [label, current, maximum],
		"value": current,
		"max": maximum,
		"fraction": bar_fraction(float(current), float(maximum)),
		"color": color,
		"offset_y": offset_y,
	}


static func _center_x(area: Rect2) -> int:
	return int(area.position.x) + int(area.size.x) / 2


static func _center_y(area: Rect2) -> int:
	return int(area.position.y) + int(area.size.y) / 2


static func _index_of_key(cards: Array, key: String, used: Dictionary) -> int:
	for index in range(cards.size()):
		if not used.has(index) and str(_dict_of(cards[index]).get("key", "")) == key:
			return index
	return -1


# Каждый выбранный ключ занимает первую свободную карту руки с этим ключом: копии одной карты различаются местом.
static func _selected_hand_indices(hand: Array, selected_keys: Array) -> Dictionary:
	var taken := {}
	for key in selected_keys:
		var found := _index_of_key(hand, str(key), taken)
		if found >= 0:
			taken[found] = true
	return taken


static func _keys_of(cards: Array) -> Array:
	var keys: Array = []
	for card in cards:
		keys.append(str(_dict_of(card).get("key", "")))
	return keys


static func _string_list(value: Variant) -> Array:
	var result: Array = []
	for item in _array_of(value):
		result.append(str(item))
	return result


static func _dict_of(value: Variant) -> Dictionary:
	if value is Dictionary:
		return value
	return {}


static func _array_of(value: Variant) -> Array:
	if value is Array:
		return value
	return []


static func _int_of(value: Variant) -> int:
	if value is int or value is float:
		return int(value)
	if value is String and (value as String).is_valid_int():
		return int(value)
	return 0
