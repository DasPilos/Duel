extends Control

# Экран боя Калоды: порт слоя отрисовки deck/ui/duel_renderer.py и deck/ui/renderers/card_area.py.
# set_snapshot(snapshot) принимает словарь снимка deck/server/battles.py:snapshot и ничего не отправляет.
# Нажатие карты эмитит card_pressed(zone, index): zone — "hand", "selected", "table" или "draw_choices";
# index — позиция в одноимённом списке снимка ("selected" — в списке ключей selected).
# Макет 1920x1080 масштабируется целиком под размер контрола через _canvas.scale.

signal card_pressed(zone: String, index: int)
signal card_hovered(card: Dictionary)

const RULES := preload("res://scripts/deck_battle_layout_rules.gd")
const CARD_VIEW_SCRIPT := preload("res://scripts/deck_battle_card_view.gd")
const MAGE_RULES := preload("res://scripts/deck_battle_mage_rules.gd")
const STATUS_RULES := preload("res://scripts/deck_battle_status_rules.gd")
const SMALL_FONT_SIZE := 18  # settings.SMALL_FONT_SIZE
const TITLE_FONT_SIZE := 22  # settings.FONT_SIZE
const RESULT_FONT_SIZE := 24  # settings.BIG_FONT_SIZE
const PILE_TITLE_FONT_SIZE := 16
const PILE_COUNT_FONT_SIZE := 72  # card_area.py: pile_count_font
const GLYPH_FONT_SIZE := 9  # class_identity.py: glyph font
const PILE_BADGE_SIZE := Vector2(72, 96)
const BAR_KEYS := ["hp", "mp", "resource"]
const CORNER_ALPHA := 200.0 / 255.0  # duel_renderer.py: overlay.fill((*background, 200))
const GLYPH_COLOR := Color8(250, 250, 250)
const TRANSPARENT := Color(0, 0, 0, 0)
const TIMER_BOX_HEIGHT := 22.0
const MAGE_TITLE_HEIGHT := 26.0
# duel_renderer.py: плашка статусов — под угловой карточкой (y + 174), от x + 10, шириной «ширина карточки - 20».
const STATUS_BLOCK_INSET := 10.0
const STATUS_BLOCK_TOP := 174.0
const STATUS_BLOCK_WIDTH := 290.0
const STATUS_BLOCK_MARGIN := 6.0
const STATUS_ROW_SEPARATION := 3
const STATUS_BLOCK_BACKGROUND := Color8(20, 24, 34, 220)
const STATUS_BLOCK_BORDER := Color8(100, 110, 125)
const STATUS_TOOLTIP_BACKGROUND := Color8(22, 25, 31)
const STATUS_TOOLTIP_BORDER := Color8(170, 150, 115)
const STATUS_TOOLTIP_TEXT := Color8(240, 235, 220)
const SUMMON_NAME_OFFSET := Vector2(7.0, 22.0)

var _built := false
var _canvas: Control
var _background_texture: TextureRect
var _background_fallback: ColorRect
var _table_texture: TextureRect
var _table_fallback: Panel
var _board_visible := false
var _piles := {}
var _fighters := {}
var _timer_bar: ProgressBar
var _timer_label: Label
var _draft_frame: Panel
var _draft_title: Label
var _draft_message: Label
var _draft_timer: Panel
var _draft_timer_label: Label
var _hit_overlay: TextureRect
var _result_panel: ColorRect
var _result_title: Label
var _result_winner: Label
var _cards := {}
var _draft_slot_keys: Array = []
var _battle_id: Variant = null
var _deck_count := -1
var _discard_count := -1
var _burn_mode := false
var _phase := ""
var _entries: Array = []
var _overlay_layer: Control
var _input_locked := false
var _timer_wanted := false
var _draft_timer_wanted := false
var _layout: Dictionary = RULES.STANDARD_LAYOUT
var _mage_layout := false
var _mage_title: Label
var _summons_panel: Panel
var _summons_title: Label
var _summons_more: Label
var _summon_rows: Array = []
var _status_tooltip: PanelContainer
var _status_tooltip_label: Label
var _status_tooltip_source: Label


func _ready() -> void:
	_build()


func _process(_delta: float) -> void:
	if _status_tooltip.visible:
		_place_status_tooltip()


func set_snapshot(snapshot: Dictionary) -> void:
	_build()
	var battle_id: Variant = snapshot.get("battle_id", null)
	if battle_id != _battle_id:
		_battle_id = battle_id
		_draft_slot_keys = []
	var model := RULES.build_draw_model(snapshot, {
		"project_dir": CARD_VIEW_SCRIPT.project_dir(),
		"draft_slot_keys": _draft_slot_keys,
	})
	_draft_slot_keys = model["draft_slot_keys"]
	_apply(model)


# Заглушка удара (duel_renderer.py:282-287). В assets/combat файла hit_placeholder.png нет, поэтому
# без текстуры оверлей не показывается, как в Python (hit_placeholder = None).
func set_hit_overlay_visible(value: bool) -> void:
	_build()
	_hit_overlay.visible = value and _hit_overlay.texture != null
	if _hit_overlay.visible:
		_canvas.move_child(_hit_overlay, -1)


# Счётчики колоды и сброса в снимке не приходят: без значений бейджи скрыты (отрицательное число).
func set_pile_counts(deck_count: int, discard_count: int) -> void:
	_build()
	_deck_count = deck_count
	_discard_count = discard_count
	_apply_pile_badges()


# Режим сжигания (battles.py: burn_card): в планировании карты руки и выбора нажимаются и без права выбора.
func set_burn_mode(value: bool) -> void:
	_build()
	_burn_mode = value
	_sync_cards(_entries)


func card_count() -> int:
	_build()
	return _cards.size()


func card_views() -> Array:
	_build()
	return _cards.values()


func card_view(zone: String, index: int):
	_build()
	return _cards.get("%s:%d" % [zone, index], null)


func bar_state(side: String, key: String) -> Dictionary:
	_build()
	var fighter: Dictionary = _fighters.get(side, {})
	var bars: Dictionary = fighter.get("bars", {})
	if not bars.has(key):
		return {}
	var bar: Dictionary = bars[key]
	var progress: ProgressBar = bar["bar"]
	var label: Label = bar["label"]
	return {"value": progress.value, "max_value": progress.max_value, "visible": progress.visible, "text": label.text}


func timer_state() -> Dictionary:
	_build()
	return {
		"visible": _timer_bar.visible,
		"value": _timer_bar.value,
		"max_value": _timer_bar.max_value,
		"text": _timer_label.text,
	}


func timer_fill_color() -> Color:
	_build()
	var style := _timer_bar.get_theme_stylebox("fill") as StyleBoxFlat
	return style.bg_color if style != null else TRANSPARENT


func fighter_texts(side: String) -> Dictionary:
	_build()
	var fighter: Dictionary = _fighters.get(side, {})
	var stats: Array = []
	for label in fighter.get("stat_labels", []):
		if label.visible:
			stats.append(label.text)
	var derived: Array = []
	for label in fighter.get("derived_labels", []):
		if label.visible:
			derived.append(label.text)
	return {
		"name": (fighter["name"] as Label).text if fighter.has("name") else "",
		"level": (fighter["level"] as Label).text if fighter.has("level") else "",
		"stats": stats,
		"derived": derived,
	}


func draft_texts() -> Dictionary:
	_build()
	return {
		"visible": _draft_frame.visible,
		"title": _draft_title.text,
		"message": _draft_message.text,
		"timer": _draft_timer_label.text,
	}


func result_texts() -> Dictionary:
	_build()
	return {"visible": _result_panel.visible, "title": _result_title.text, "winner": _result_winner.text}


func pile_title(which: String) -> String:
	_build()
	var pile: Dictionary = _piles.get(which, {})
	return (pile["title"] as Label).text if pile.has("title") else ""


func pile_count_text(which: String) -> String:
	_build()
	var pile: Dictionary = _piles.get(which, {})
	return (pile["count"] as Label).text if pile.has("count") else ""


func pile_count_visible(which: String) -> bool:
	_build()
	var pile: Dictionary = _piles.get(which, {})
	return (pile["badge"] as Control).visible if pile.has("badge") else false


func panel_visible(panel_name: String) -> bool:
	_build()
	match panel_name:
		"board":
			return _board_visible
		"table":
			return _table_texture.visible or _table_fallback.visible
		"result":
			return _result_panel.visible
		"timer":
			return _timer_bar.visible
		"draft":
			return _draft_frame.visible
		"hit":
			return _hit_overlay.visible
	return false


func has_background_texture() -> bool:
	_build()
	return _background_texture.texture != null


func has_table_texture() -> bool:
	_build()
	return _table_texture.texture != null


func hit_overlay_visible() -> bool:
	_build()
	return _hit_overlay.visible


func canvas_factor() -> float:
	_build()
	return _canvas.scale.x


# Слой поверх карт и панелей (в координатах макета): сюда визуал боя кладёт числа и полёты карт.
func overlay_layer() -> Control:
	_build()
	return _overlay_layer


# Во время анимаций боя карты не нажимаются, а таймеры скрыты: в Python ввод принимается только в планировании
# и драфте, а таймер рисуется только там.
func set_input_locked(value: bool) -> void:
	_build()
	_input_locked = value
	_timer_bar.visible = _timer_wanted and not value
	_timer_label.visible = _timer_wanted and not value
	_draft_timer.visible = _draft_timer_wanted and not value
	_draft_timer_label.visible = _draft_timer_wanted and not value
	_sync_cards(_entries)


func input_locked() -> bool:
	return _input_locked


# Макет стола текущего снимка: обычный или мага (по профессии бойца, см. deck_battle_mage_rules.gd).
func active_layout() -> Dictionary:
	_build()
	return _layout


func mage_layout() -> bool:
	_build()
	return _mage_layout


func mage_title_text() -> String:
	_build()
	return _mage_title.text


func mage_title_visible() -> bool:
	_build()
	return _mage_title.visible


# Прямоугольник карты на макете (источник полёта); пусто, если карты сейчас не показана.
func card_rect_of(zone: String, index: int) -> Rect2:
	var card = card_view(zone, index)
	if card == null:
		return Rect2()
	return Rect2(card.position, card.size)


func status_texts(side: String) -> Array:
	_build()
	var texts: Array = []
	for label in _fighters[side]["status_labels"]:
		if label.visible:
			texts.append(label.text)
	return texts


func status_colors(side: String) -> Array:
	_build()
	var colors: Array = []
	for label in _fighters[side]["status_labels"]:
		if label.visible:
			colors.append(label.get_theme_color("font_color"))
	return colors


func status_block_visible(side: String) -> bool:
	_build()
	return (_fighters[side]["status_block"] as Control).visible


func hover_status(side: String, index: int) -> void:
	_build()
	_on_status_hovered(_fighters[side]["status_labels"][index])


func unhover_status(side: String, index: int) -> void:
	_build()
	_on_status_unhovered(_fighters[side]["status_labels"][index])


func status_tooltip_text() -> String:
	_build()
	return _status_tooltip_label.text if _status_tooltip.visible else ""


func shield_overlay_visible(side: String) -> bool:
	_build()
	return (_fighters[side]["shield_overlay"] as Control).visible


func shield_overlay_rect(side: String) -> Rect2:
	_build()
	var overlay := _fighters[side]["shield_overlay"] as Control
	return Rect2(overlay.position, overlay.size)


func summons_panel_visible() -> bool:
	_build()
	return _summons_panel.visible


func summons_panel_rect() -> Rect2:
	_build()
	return Rect2(_summons_panel.position, _summons_panel.size)


func summon_rows() -> Array:
	_build()
	var rows: Array = []
	for pair in _summon_rows:
		if (pair["name"] as Label).visible:
			rows.append({"name": (pair["name"] as Label).text, "details": (pair["details"] as Label).text})
	return rows


func summons_more_text() -> String:
	_build()
	return _summons_more.text if _summons_more.visible else ""


func _build() -> void:
	if _built:
		return
	_built = true
	texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	resized.connect(_fit_canvas)
	_canvas = Control.new()
	_canvas.size = RULES.DESIGN_SIZE
	_canvas.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_canvas)
	_build_background()
	_build_table()
	_build_piles()
	_build_summons()
	_build_fighters()
	_build_timer()
	_build_draft()
	_build_hit_overlay()
	_build_result()
	_build_overlay()
	_build_mage()
	_build_status_tooltip()
	_place_layout(RULES.STANDARD_LAYOUT, false)
	_fit_canvas()


func _build_background() -> void:
	var texture := CARD_VIEW_SCRIPT.load_texture(_asset(RULES.BACKGROUND_ASSET))
	_background_fallback = _add_static(ColorRect.new(), Rect2(Vector2.ZERO, RULES.DESIGN_SIZE)) as ColorRect
	_background_fallback.color = RULES.COLOR_BACKGROUND_FALLBACK
	_background_fallback.visible = texture == null
	_background_texture = _add_static(TextureRect.new(), Rect2(Vector2.ZERO, RULES.DESIGN_SIZE)) as TextureRect
	_background_texture.texture = texture
	_background_texture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_background_texture.stretch_mode = TextureRect.STRETCH_SCALE
	_background_texture.visible = texture != null


func _build_table() -> void:
	var texture := CARD_VIEW_SCRIPT.load_texture(_asset(RULES.TABLE_ASSET))
	_table_fallback = _add_static(Panel.new(), Rect2()) as Panel
	_table_fallback.add_theme_stylebox_override("panel", CARD_VIEW_SCRIPT.flat_box(RULES.COLOR_TABLE_FALLBACK, TRANSPARENT, 0, 8, true))
	_table_texture = _add_static(TextureRect.new(), Rect2()) as TextureRect
	_table_texture.texture = texture
	_table_texture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_table_texture.stretch_mode = TextureRect.STRETCH_SCALE
	_table_texture.visible = false


func _build_piles() -> void:
	for which in ["deck", "discard"]:
		var backs: Array = []
		for _offset in RULES.PILE_STACK_OFFSETS:
			var back = CARD_VIEW_SCRIPT.new()
			_canvas.add_child(back)
			backs.append(back)
		var title := _label(Vector2.ZERO, PILE_TITLE_FONT_SIZE, RULES.COLOR_PILE_TITLE, Vector2.ZERO)
		title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		var badge := _add_static(Panel.new(), Rect2()) as Panel
		badge.add_theme_stylebox_override("panel", CARD_VIEW_SCRIPT.flat_box(RULES.COLOR_PILE_BADGE, RULES.COLOR_PILE_BADGE_BORDER, 2, 8, true))
		var count := _label(Vector2.ZERO, PILE_COUNT_FONT_SIZE, Color.WHITE, Vector2.ZERO)
		count.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		count.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		_piles[which] = {"title": title, "backs": backs, "badge": badge, "count": count}


func _build_fighters() -> void:
	for side in ["player", "enemy"]:
		var corner_rect := RULES.corner_card_rect(side)
		var border: Color = RULES.COLOR_PLAYER_BORDER if side == "player" else RULES.COLOR_ENEMY_BORDER
		var inner_x := corner_rect.position.x + RULES.CORNER_INNER_INSET
		var icon_rect := Rect2(inner_x, corner_rect.position.y + RULES.CORNER_NAME_TOP, RULES.CORNER_ICON_SIZE, RULES.CORNER_ICON_SIZE)
		var nodes := {}
		nodes["corner"] = _add_static(Panel.new(), corner_rect)
		nodes["icon"] = _add_static(Panel.new(), icon_rect)
		nodes["glyph"] = _label(icon_rect.position, GLYPH_FONT_SIZE, GLYPH_COLOR, icon_rect.size)
		(nodes["glyph"] as Label).horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		(nodes["glyph"] as Label).vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		nodes["name"] = _label(Vector2(inner_x + RULES.CORNER_ICON_SIZE + RULES.CORNER_NAME_GAP, corner_rect.position.y + RULES.CORNER_NAME_TOP), SMALL_FONT_SIZE, RULES.COLOR_NAME_TEXT)
		nodes["level"] = _label(Vector2(inner_x, corner_rect.position.y + RULES.CORNER_LEVEL_TOP), SMALL_FONT_SIZE, RULES.COLOR_LEVEL_TEXT)
		var bars := {}
		for bar_index in range(BAR_KEYS.size()):
			var offset_y := RULES.BAR_TOP + bar_index * RULES.BAR_STEP
			var bar_label := _label(Vector2(inner_x, corner_rect.position.y + offset_y - RULES.BAR_LABEL_LIFT), SMALL_FONT_SIZE, RULES.COLOR_BAR_TEXT)
			var bar := ProgressBar.new()
			bar.show_percentage = false
			_add_static(bar, Rect2(Vector2(inner_x, corner_rect.position.y + offset_y + RULES.BAR_DROP), Vector2(RULES.BAR_WIDTH, RULES.BAR_HEIGHT)))
			bars[BAR_KEYS[bar_index]] = {"label": bar_label, "bar": bar}
		nodes["bars"] = bars
		nodes["shield_overlay"] = _add_static(ColorRect.new(), Rect2())
		(nodes["shield_overlay"] as ColorRect).color = STATUS_RULES.SHIELD_OVERLAY_COLOR
		(nodes["shield_overlay"] as ColorRect).visible = false
		nodes["stats_panel"] = _add_static(Panel.new(), Rect2())
		nodes["stats_header"] = _label(Vector2.ZERO, SMALL_FONT_SIZE, border)
		var stat_labels: Array = []
		for _row in range(RULES.STAT_ROWS.size()):
			stat_labels.append(_label(Vector2.ZERO, SMALL_FONT_SIZE, RULES.COLOR_STAT_TEXT))
		nodes["stat_labels"] = stat_labels
		var derived_labels: Array = []
		for _row in range(RULES.DERIVED_ORDER.size()):
			derived_labels.append(_label(Vector2.ZERO, SMALL_FONT_SIZE, RULES.COLOR_STAT_TEXT))
		nodes["derived_labels"] = derived_labels
		var status_block := _add_static(PanelContainer.new(), Rect2(corner_rect.position.x + STATUS_BLOCK_INSET, corner_rect.position.y + STATUS_BLOCK_TOP, STATUS_BLOCK_WIDTH, 0.0)) as PanelContainer
		status_block.custom_minimum_size.x = STATUS_BLOCK_WIDTH
		var block_style := CARD_VIEW_SCRIPT.flat_box(STATUS_BLOCK_BACKGROUND, STATUS_BLOCK_BORDER, 1, 5, true)
		block_style.set_content_margin_all(STATUS_BLOCK_MARGIN)
		status_block.add_theme_stylebox_override("panel", block_style)
		status_block.mouse_filter = Control.MOUSE_FILTER_IGNORE
		status_block.visible = false
		var status_box := VBoxContainer.new()
		status_box.add_theme_constant_override("separation", STATUS_ROW_SEPARATION)
		status_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
		status_block.add_child(status_box)
		nodes["status_block"] = status_block
		nodes["status_box"] = status_box
		nodes["status_labels"] = []
		_fighters[side] = nodes


func _build_timer() -> void:
	var timer_bar := ProgressBar.new()
	timer_bar.show_percentage = false
	_timer_bar = _add_static(timer_bar, Rect2()) as ProgressBar
	_timer_bar.add_theme_stylebox_override("background", CARD_VIEW_SCRIPT.flat_box(RULES.COLOR_TIMER_TRACK, TRANSPARENT, 0, 5, true))
	_timer_bar.add_theme_stylebox_override("fill", CARD_VIEW_SCRIPT.flat_box(RULES.COLOR_TIMER_GREEN, TRANSPARENT, 0, 5, true))
	_timer_bar.visible = false
	_timer_label = _label(Vector2.ZERO, SMALL_FONT_SIZE, RULES.COLOR_TIMER_TEXT, Vector2.ZERO)
	_timer_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_timer_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_timer_label.visible = false


func _build_draft() -> void:
	_draft_frame = _add_static(Panel.new(), Rect2()) as Panel
	_draft_frame.add_theme_stylebox_override("panel", CARD_VIEW_SCRIPT.flat_box(TRANSPARENT, RULES.COLOR_TABLE_FRAME, 2, 8, false))
	_draft_title = _label(Vector2.ZERO, TITLE_FONT_SIZE, RULES.COLOR_DRAFT_TITLE)
	# Подсказка выровнена по правому краю слева от значка таймера: в Python она уходила под значок.
	_draft_message = _label(Vector2.ZERO, SMALL_FONT_SIZE, RULES.COLOR_DRAFT_MESSAGE, Vector2.ZERO)
	_draft_message.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_draft_timer = _add_static(Panel.new(), Rect2()) as Panel
	_draft_timer.add_theme_stylebox_override("panel", CARD_VIEW_SCRIPT.flat_box(RULES.COLOR_DRAFT_TIMER_BACKGROUND, RULES.COLOR_DRAFT_TIMER_BORDER, 1, 5, true))
	_draft_timer_label = _label(Vector2.ZERO, SMALL_FONT_SIZE, RULES.COLOR_DRAFT_TIMER, Vector2.ZERO)
	_draft_timer_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_draft_timer_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_draft_frame.visible = false
	_draft_title.visible = false
	_draft_message.visible = false
	_draft_timer.visible = false
	_draft_timer_label.visible = false


func _build_hit_overlay() -> void:
	_hit_overlay = _add_static(TextureRect.new(), RULES.HIT_OVERLAY_RECT) as TextureRect
	_hit_overlay.texture = CARD_VIEW_SCRIPT.load_texture(_asset(RULES.HIT_PLACEHOLDER_ASSET))
	_hit_overlay.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_hit_overlay.stretch_mode = TextureRect.STRETCH_SCALE
	_hit_overlay.visible = false


func _build_result() -> void:
	_result_panel = _add_static(ColorRect.new(), Rect2(Vector2.ZERO, RULES.DESIGN_SIZE)) as ColorRect
	_result_panel.color = RULES.COLOR_RESULT_BACKGROUND
	_result_panel.visible = false
	_result_title = _label(Vector2(0.0, 25.0), RESULT_FONT_SIZE, RULES.COLOR_DRAFT_TITLE, Vector2(RULES.DESIGN_SIZE.x, 30.0))
	_result_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_result_title.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_result_title.visible = false
	_result_winner = _label(Vector2(860.0, 80.0), SMALL_FONT_SIZE, RULES.COLOR_RESULT_WINNER, Vector2(400.0, 24.0))
	_result_winner.visible = false


# Слой визуала создаётся последним и поднимается наверх в _apply, поэтому числа и полёты видны над картами.
func _build_overlay() -> void:
	_overlay_layer = Control.new()
	_overlay_layer.size = RULES.DESIGN_SIZE
	_overlay_layer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_canvas.add_child(_overlay_layer)


# Панель призывов у сброса (duel_renderer.py:_draw_summons_near_discard): фон и заголовок, строки создаются по мере нужды.
func _build_summons() -> void:
	_summons_panel = _add_static(Panel.new(), Rect2()) as Panel
	_summons_panel.add_theme_stylebox_override("panel", CARD_VIEW_SCRIPT.flat_box(STATUS_RULES.SUMMON_BACKGROUND, STATUS_RULES.SUMMON_BORDER, 1, 5, true))
	_summons_panel.visible = false
	_summons_title = _label(Vector2.ZERO, SMALL_FONT_SIZE, STATUS_RULES.SUMMON_TITLE_COLOR, Vector2.ZERO)
	_summons_title.text = STATUS_RULES.SUMMON_TITLE
	_summons_title.visible = false
	_summons_more = _label(Vector2.ZERO, SMALL_FONT_SIZE, STATUS_RULES.SUMMON_MORE_COLOR, Vector2.ZERO)
	_summons_more.visible = false


# Подсказка статуса (duel_renderer.py:_draw_status_tooltip): поверх поля, у курсора.
func _build_status_tooltip() -> void:
	_status_tooltip = PanelContainer.new()
	var style := CARD_VIEW_SCRIPT.flat_box(STATUS_TOOLTIP_BACKGROUND, STATUS_TOOLTIP_BORDER, 1, 5, true)
	style.set_content_margin_all(8.0)
	_status_tooltip.add_theme_stylebox_override("panel", style)
	_status_tooltip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_status_tooltip.visible = false
	_status_tooltip_label = Label.new()
	_status_tooltip_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status_tooltip_label.custom_minimum_size.x = STATUS_RULES.TOOLTIP_WIDTH
	_status_tooltip_label.add_theme_font_override("font", CARD_VIEW_SCRIPT.ui_font())
	_status_tooltip_label.add_theme_font_size_override("font_size", SMALL_FONT_SIZE)
	_status_tooltip_label.add_theme_color_override("font_color", STATUS_TOOLTIP_TEXT)
	_status_tooltip_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_status_tooltip.add_child(_status_tooltip_label)
	_overlay_layer.add_child(_status_tooltip)


func _apply_status_rows(side: String, rows: Array, shown: bool) -> void:
	var nodes: Dictionary = _fighters[side]
	var block := nodes["status_block"] as PanelContainer
	var box := nodes["status_box"] as VBoxContainer
	var labels: Array = nodes["status_labels"]
	while labels.size() < rows.size():
		var label := Label.new()
		label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		label.add_theme_font_override("font", CARD_VIEW_SCRIPT.ui_font())
		label.add_theme_font_size_override("font_size", SMALL_FONT_SIZE)
		label.mouse_filter = Control.MOUSE_FILTER_STOP
		label.mouse_entered.connect(_on_status_hovered.bind(label))
		label.mouse_exited.connect(_on_status_unhovered.bind(label))
		box.add_child(label)
		labels.append(label)
	for index in range(labels.size()):
		var label := labels[index] as Label
		var row_shown := shown and index < rows.size()
		label.visible = row_shown
		if row_shown:
			var row: Dictionary = rows[index]
			label.text = str(row["text"])
			label.add_theme_color_override("font_color", row["color"])
			label.set_meta("description", str(row["description"]))
	block.visible = shown and not rows.is_empty()
	if _status_tooltip.visible:
		if _status_tooltip_source.visible:
			_status_tooltip_label.text = str(_status_tooltip_source.get_meta("description", ""))
		else:
			_hide_status_tooltip()


func _apply_summons(panel: Dictionary, shown: bool) -> void:
	var rows: Array = panel.get("rows", []) if shown else []
	var panel_shown := shown and bool(panel.get("visible", false))
	_summons_panel.visible = panel_shown
	_summons_title.visible = panel_shown
	while _summon_rows.size() < rows.size():
		var name_label := _label(Vector2.ZERO, SMALL_FONT_SIZE, STATUS_RULES.SUMMON_NAME_COLOR, Vector2.ZERO)
		name_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		_summon_rows.append({
			"name": name_label,
			"details": _label(Vector2.ZERO, SMALL_FONT_SIZE, STATUS_RULES.SUMMON_DETAILS_COLOR, Vector2.ZERO),
		})
	var rect: Rect2 = panel.get("rect", Rect2())
	for index in range(_summon_rows.size()):
		var pair: Dictionary = _summon_rows[index]
		var row_shown := panel_shown and index < rows.size()
		(pair["name"] as Label).visible = row_shown
		(pair["details"] as Label).visible = row_shown
		if not row_shown:
			continue
		var row: Dictionary = rows[index]
		var row_top := rect.position.y + SUMMON_NAME_OFFSET.y + index * STATUS_RULES.SUMMON_ROW_HEIGHT
		(pair["name"] as Label).text = str(row["name"])
		_place_label(pair["name"], Rect2(rect.position.x + SUMMON_NAME_OFFSET.x, row_top, rect.size.x - 14.0, 0.0))
		(pair["details"] as Label).text = str(row["details"])
		_place_label(pair["details"], Rect2(rect.position.x + SUMMON_NAME_OFFSET.x, row_top + STATUS_RULES.SUMMON_DETAILS_OFFSET, rect.size.x - 14.0, 0.0))
	if not panel_shown:
		_summons_more.visible = false
		return
	_place_rect(_summons_panel, rect)
	_place_label(_summons_title, Rect2(rect.position.x + 7.0, rect.position.y + 4.0, rect.size.x - 14.0, STATUS_RULES.SUMMON_TITLE_HEIGHT))
	var more := str(panel.get("more", ""))
	_summons_more.visible = not more.is_empty()
	_summons_more.text = more
	_place_label(_summons_more, Rect2(rect.position.x + 7.0, rect.end.y - STATUS_RULES.SUMMON_MORE_HEIGHT, rect.size.x - 14.0, STATUS_RULES.SUMMON_MORE_HEIGHT))


func _on_status_hovered(label: Label) -> void:
	_status_tooltip_source = label
	_status_tooltip_label.text = str(label.get_meta("description", ""))
	_status_tooltip.visible = true
	_place_status_tooltip()


func _on_status_unhovered(label: Label) -> void:
	if _status_tooltip_source == label:
		_hide_status_tooltip()


func _hide_status_tooltip() -> void:
	_status_tooltip_source = null
	_status_tooltip.visible = false


# Подсказка у курсора в координатах макета; у правого и нижнего края уходит внутрь экрана.
func _place_status_tooltip() -> void:
	var tooltip_size := _status_tooltip.get_combined_minimum_size()
	var origin := _canvas.get_local_mouse_position() + Vector2(14.0, 14.0)
	origin.x = clampf(origin.x, 0.0, RULES.DESIGN_SIZE.x - tooltip_size.x)
	origin.y = clampf(origin.y, 0.0, RULES.DESIGN_SIZE.y - tooltip_size.y)
	_status_tooltip.position = origin


func _build_mage() -> void:
	_mage_title = _overlay_label(MAGE_RULES.TITLE_TEXT, MAGE_RULES.TITLE_FONT_SIZE, MAGE_RULES.TITLE_COLOR, HORIZONTAL_ALIGNMENT_CENTER)
	_mage_title.visible = false


func _overlay_label(text: String, font_size: int, color: Color, alignment: HorizontalAlignment) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_override("font", CARD_VIEW_SCRIPT.ui_font())
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	label.horizontal_alignment = alignment
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_overlay_layer.add_child(label)
	return label


# Поля, которые зависят от макета стола (стол, колода, сброс, панели характеристик, полоса хода, драфт, заголовок
# мага), ставятся здесь. Остальные узлы стоят на фиксированных местах и сюда не входят.
func _place_layout(layout: Dictionary, mage: bool) -> void:
	_layout = layout
	_mage_layout = mage
	var table: Rect2 = layout["card_table"]
	_place_rect(_table_fallback, table)
	_place_rect(_table_texture, table)
	_place_piles()
	_place_stats()
	var turn_bar: Rect2 = layout["turn_bar"]
	_place_rect(_timer_bar, turn_bar)
	_place_label(_timer_label, Rect2(turn_bar.position.x, turn_bar.get_center().y - TIMER_BOX_HEIGHT / 2.0, turn_bar.size.x, TIMER_BOX_HEIGHT))
	_place_draft(table)
	_place_mage()


func _place_rect(node: Control, rect: Rect2) -> void:
	node.position = rect.position
	node.size = rect.size


func _place_label(label: Label, rect: Rect2) -> void:
	label.position = rect.position
	label.size = rect.size


func _place_piles() -> void:
	for which in ["deck", "discard"]:
		var rect := RULES.pile_rect(which, _layout)
		var pile: Dictionary = _piles[which]
		var backs: Array = pile["backs"]
		for index in range(backs.size()):
			var offset := float(RULES.PILE_STACK_OFFSETS[index])
			backs[index].configure(RULES.hidden_card_entry(Rect2(rect.position - Vector2(offset, offset), rect.size)))
		_place_label(pile["title"], Rect2(rect.position.x, rect.position.y - 28.0, rect.size.x, 20.0))
		var badge_origin := Vector2(rect.get_center().x - PILE_BADGE_SIZE.x / 2.0, rect.position.y + 42.0 - PILE_BADGE_SIZE.y / 2.0)
		_place_rect(pile["badge"], Rect2(badge_origin, PILE_BADGE_SIZE))
		_place_label(pile["count"], Rect2(badge_origin, PILE_BADGE_SIZE))


func _place_stats() -> void:
	for side in ["player", "enemy"]:
		var nodes: Dictionary = _fighters[side]
		var stats_rect := RULES.stats_panel_rect(side, RULES.MAX_HAND_SIZE, _layout)
		var text_x := stats_rect.position.x + RULES.STATS_TEXT_INSET
		var rows_top := stats_rect.position.y + RULES.STATS_HEADER_TOP + RULES.STATS_ROW_TOP
		_place_rect(nodes["stats_panel"], stats_rect)
		_place_label(nodes["stats_header"], Rect2(text_x, stats_rect.position.y + RULES.STATS_HEADER_TOP, 0.0, 0.0))
		var stat_labels: Array = nodes["stat_labels"]
		for row in range(stat_labels.size()):
			_place_label(stat_labels[row], Rect2(text_x, rows_top + row * RULES.STATS_ROW_HEIGHT, 0.0, 0.0))
		var derived_labels: Array = nodes["derived_labels"]
		for row in range(derived_labels.size()):
			_place_label(derived_labels[row], Rect2(text_x + RULES.STATS_DERIVED_COLUMN, rows_top + row * RULES.STATS_ROW_HEIGHT, 0.0, 0.0))


func _place_draft(table: Rect2) -> void:
	_place_rect(_draft_frame, table)
	_place_label(_draft_title, Rect2(table.position.x + 20.0, table.position.y + 12.0, 0.0, 0.0))
	_place_label(_draft_message, Rect2(table.end.x - 540.0, table.position.y + 16.0, 300.0, 24.0))
	var badge_rect := Rect2(table.end.x - 210.0, table.position.y + 8.0, 200.0, 26.0)
	_place_rect(_draft_timer, badge_rect)
	_place_label(_draft_timer_label, Rect2(badge_rect.position, Vector2(badge_rect.size.x - 8.0, badge_rect.size.y)))


# Заголовок мага сверху по центру (mage_battle_scene.py: draw).
func _place_mage() -> void:
	_place_label(_mage_title, Rect2(0.0, 12.0, RULES.DESIGN_SIZE.x, MAGE_TITLE_HEIGHT))


# Заголовок мага виден только в макете мага, на доске и вне результата.
func _apply_mage() -> void:
	_mage_title.visible = _mage_layout and _board_visible and MAGE_RULES.title_visible(_phase)


func _apply(model: Dictionary) -> void:
	_phase = str(model.get("phase", ""))
	_board_visible = bool(model.get("show_board", false))
	var mage := bool(model.get("mage", false))
	if mage != _mage_layout:
		_place_layout(model.get("layout", RULES.STANDARD_LAYOUT), mage)
	_table_texture.visible = _board_visible and _table_texture.texture != null
	_table_fallback.visible = _board_visible and _table_texture.texture == null
	var piles: Dictionary = model.get("piles", {})
	for which in _piles.keys():
		var pile: Dictionary = _piles[which]
		var pile_model: Dictionary = piles.get(which, {})
		(pile["title"] as Label).text = str(pile_model.get("title", ""))
		(pile["title"] as Label).visible = _board_visible
		for back in pile["backs"]:
			back.visible = _board_visible
	_apply_pile_badges()
	var fighters: Dictionary = model.get("fighters", {})
	for side in ["player", "enemy"]:
		_apply_fighter(side, fighters.get(side, {}))
	_apply_summons(model.get("summons", {}), _board_visible)
	_apply_timer(model.get("timer", {}), bool(model.get("show_timer", false)))
	_apply_draft(model.get("draft", {}), bool(model.get("show_draft", false)))
	var showing_result := bool(model.get("show_result", false))
	_result_panel.visible = showing_result
	_result_title.visible = showing_result
	_result_winner.visible = showing_result
	if showing_result:
		var result: Dictionary = model.get("result", {})
		_result_title.text = str(result.get("title", ""))
		_result_title.add_theme_color_override("font_color", _color_of(result.get("title_color", null), RULES.COLOR_RESULT_DRAW))
		_result_winner.text = str(result.get("winner_text", ""))
	_sync_cards(model.get("cards", []))
	_overlay_layer.visible = not showing_result
	_canvas.move_child(_overlay_layer, -1)
	_apply_mage()


func _apply_pile_badges() -> void:
	var counts := {"deck": _deck_count, "discard": _discard_count}
	for which in _piles.keys():
		var pile: Dictionary = _piles[which]
		var count: int = counts[which]
		var badge := pile["badge"] as Control
		var count_label := pile["count"] as Label
		badge.visible = _board_visible and count >= 0
		count_label.visible = badge.visible
		count_label.text = str(count)


func _apply_fighter(side: String, model: Dictionary) -> void:
	var nodes: Dictionary = _fighters[side]
	var board := _board_visible
	var palette: Dictionary = model.get("palette", {})
	var background := _color_of(palette.get("background", null), RULES.COLOR_BACKGROUND_FALLBACK)
	var accent := _color_of(palette.get("accent", null), RULES.COLOR_PLAYER_BORDER)
	var icon_background := _color_of(palette.get("icon_background", null), RULES.COLOR_BACKGROUND_FALLBACK)
	var border := _color_of(model.get("border_color", null), RULES.COLOR_PLAYER_BORDER)
	var corner := nodes["corner"] as Control
	corner.add_theme_stylebox_override("panel", CARD_VIEW_SCRIPT.flat_box(Color(background.r, background.g, background.b, CORNER_ALPHA), accent, 2, 8, true))
	corner.visible = board
	var icon := nodes["icon"] as Control
	icon.add_theme_stylebox_override("panel", CARD_VIEW_SCRIPT.flat_box(icon_background, accent, 1, 3, true))
	icon.visible = board
	var glyph := nodes["glyph"] as Label
	glyph.text = str(model.get("glyph", ""))
	glyph.visible = board
	var name_label := nodes["name"] as Label
	name_label.text = str(model.get("name", ""))
	name_label.visible = board
	var level_label := nodes["level"] as Label
	level_label.text = str(model.get("level_text", ""))
	level_label.visible = board
	var present := {}
	for bar_model in model.get("bars", []):
		var key := str(bar_model["key"])
		present[key] = true
		var bar_nodes: Dictionary = nodes["bars"][key]
		var progress := bar_nodes["bar"] as ProgressBar
		_set_bar(progress, int(bar_model["value"]), int(bar_model["max"]), _color_of(bar_model.get("color", null), RULES.COLOR_HP))
		(bar_nodes["label"] as Label).text = str(bar_model["text"])
	var bars: Dictionary = nodes["bars"]
	for key in bars.keys():
		var shown := board and present.has(key)
		var node_pair: Dictionary = bars[key]
		(node_pair["bar"] as Control).visible = shown
		(node_pair["label"] as Control).visible = shown
	var shield_rect: Rect2 = model.get("shield_rect", Rect2())
	var shield_overlay := nodes["shield_overlay"] as ColorRect
	_place_rect(shield_overlay, shield_rect)
	shield_overlay.visible = board and shield_rect.size.x > 0.0
	_apply_status_rows(side, model.get("status_rows", []), board)
	var stats_panel := nodes["stats_panel"] as Control
	stats_panel.add_theme_stylebox_override("panel", CARD_VIEW_SCRIPT.flat_box(RULES.COLOR_STATS_BACKGROUND, border, 2, 8, true))
	stats_panel.visible = board
	var header := nodes["stats_header"] as Label
	header.text = "ХАРАКТЕРИСТИКИ"
	header.add_theme_color_override("font_color", border)
	header.visible = board
	var characteristics: Dictionary = model.get("characteristics", {})
	var stat_rows: Array = characteristics.get("stats", [])
	var stat_labels: Array = nodes["stat_labels"]
	for row in range(stat_labels.size()):
		var stat_label := stat_labels[row] as Label
		stat_label.visible = board and row < stat_rows.size()
		if stat_label.visible:
			stat_label.text = str(stat_rows[row]["text"])
	var derived_rows: Array = characteristics.get("derived", [])
	var derived_labels: Array = nodes["derived_labels"]
	for row in range(derived_labels.size()):
		var derived_label := derived_labels[row] as Label
		derived_label.visible = board and row < derived_rows.size()
		if derived_label.visible:
			derived_label.text = str(derived_rows[row]["text"])
			derived_label.add_theme_color_override("font_color", _color_of(derived_rows[row].get("color", null), RULES.COLOR_STAT_TEXT))


func _apply_timer(timer: Dictionary, shown: bool) -> void:
	_timer_wanted = shown
	_timer_bar.visible = shown and not _input_locked
	_timer_label.visible = shown and not _input_locked
	if not shown:
		return
	_timer_bar.max_value = maxi(1, int(timer.get("total", 0)))
	_timer_bar.value = float(int(timer.get("seconds_left", 0)))
	_timer_bar.add_theme_stylebox_override("fill", CARD_VIEW_SCRIPT.flat_box(_color_of(timer.get("color", null), RULES.COLOR_TIMER_GREEN), TRANSPARENT, 0, 5, true))
	_timer_label.text = str(timer.get("label", ""))


func _apply_draft(draft: Dictionary, shown: bool) -> void:
	_draft_timer_wanted = shown
	_draft_frame.visible = shown
	_draft_title.visible = shown
	_draft_message.visible = shown
	_draft_timer.visible = shown and not _input_locked
	_draft_timer_label.visible = shown and not _input_locked
	if not shown:
		return
	_draft_title.text = str(draft.get("title", ""))
	_draft_message.text = str(draft.get("message", ""))
	_draft_timer_label.text = str(draft.get("timer_text", ""))


func _sync_cards(entries: Array) -> void:
	_entries = entries
	var keep := {}
	for entry in entries:
		var entry_dict: Dictionary = entry
		var card_id := "%s:%d" % [str(entry_dict["zone"]), int(entry_dict["index"])]
		keep[card_id] = true
		var view = _cards.get(card_id, null)
		if view == null:
			view = CARD_VIEW_SCRIPT.new()
			_canvas.add_child(view)
			view.card_pressed.connect(_on_card_pressed)
			view.card_hovered.connect(_on_card_hovered)
			_cards[card_id] = view
		view.configure(_pressable_in_burn_mode(entry_dict))
	for card_id in _cards.keys():
		if keep.has(card_id):
			continue
		var stale = _cards[card_id]
		_cards.erase(card_id)
		_canvas.remove_child(stale)
		stale.queue_free()


func _pressable_in_burn_mode(entry: Dictionary) -> Dictionary:
	if _input_locked:
		var locked := entry.duplicate()
		locked["pressable"] = false
		return locked
	var zone := str(entry.get("zone", ""))
	if not _burn_mode or _phase != "planning" or bool(entry.get("hidden", false)) or (zone != "hand" and zone != "selected"):
		return entry
	var burnable := entry.duplicate()
	burnable["pressable"] = true
	return burnable


func _on_card_pressed(zone: String, index: int) -> void:
	card_pressed.emit(zone, index)


func _on_card_hovered(card: Dictionary) -> void:
	card_hovered.emit(card)


func _set_bar(bar: ProgressBar, current: int, maximum: int, color: Color) -> void:
	bar.max_value = maxi(1, maximum)
	bar.value = float(current)
	bar.add_theme_stylebox_override("background", CARD_VIEW_SCRIPT.flat_box(RULES.COLOR_BAR_TRACK, TRANSPARENT, 0, 2, true))
	bar.add_theme_stylebox_override("fill", CARD_VIEW_SCRIPT.flat_box(color, TRANSPARENT, 0, 2, true))


func _fit_canvas() -> void:
	if _canvas == null:
		return
	if size.x <= 0.0 or size.y <= 0.0:
		_canvas.scale = Vector2.ONE
		_canvas.position = Vector2.ZERO
		return
	var factor := minf(size.x / RULES.DESIGN_SIZE.x, size.y / RULES.DESIGN_SIZE.y)
	_canvas.scale = Vector2(factor, factor)
	_canvas.position = ((size - RULES.DESIGN_SIZE * factor) * 0.5).floor()


func _add_static(node: Control, rect: Rect2) -> Control:
	node.position = rect.position
	node.size = rect.size
	node.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_canvas.add_child(node)
	return node


func _label(origin: Vector2, font_size: int, color: Color, label_size: Vector2 = Vector2.ZERO) -> Label:
	var label := Label.new()
	label.position = origin
	label.size = label_size
	label.add_theme_font_override("font", CARD_VIEW_SCRIPT.ui_font())
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_canvas.add_child(label)
	return label


func _asset(relative_path: String) -> String:
	return RULES.asset_path(CARD_VIEW_SCRIPT.project_dir(), relative_path)


static func _color_of(value: Variant, fallback: Color) -> Color:
	return value if value is Color else fallback
