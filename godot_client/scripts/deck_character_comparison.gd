extends Control

# Окно сравнения персонажей из deck/ui/character_comparison.py: слева персонаж игрока с правкой характеристик,
# справа соперник из заявки. Внизу «БРОСИТЬ ВЫЗОВ» и «ЗАКРЫТЬ»; закрывается кнопкой или клавишей Esc.

signal stat_requested(stat_name: String, delta: int)
signal challenge_requested

const RULES := preload("res://scripts/deck_character_rules.gd")
const CARD_SCRIPT := preload("res://scripts/deck_character_card.gd")
const PLAYER_BORDER := Color8(80, 180, 120)
const ENEMY_BORDER := Color8(210, 100, 90)
const ERROR_COLOR := Color8(255, 150, 140)
const INFO_COLOR := Color8(200, 235, 205)
const TITLE_COLOR := Color8(240, 210, 150)
const WINDOW_COLOR := Color8(22, 20, 30, 250)
const WINDOW_BORDER := Color8(120, 110, 150)
const TOOLTIP_COLOR := Color8(28, 24, 38, 248)
const TOOLTIP_BORDER := Color8(185, 140, 220)
const TOOLTIP_WIDTH := 260.0

var _player_card
var _opponent_card
var _status: Label
var _challenge_button: Button
var _close_button: Button
var _tooltip: PanelContainer
var _tooltip_box: VBoxContainer
var _tooltip_item := ""
var _player_raw: Dictionary = {}
var _opponent_raw: Dictionary = {}


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	visible = false
	var backdrop := ColorRect.new()
	backdrop.color = Color(0, 0, 0, 0.72)
	backdrop.mouse_filter = Control.MOUSE_FILTER_STOP
	backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(backdrop)
	var center := CenterContainer.new()
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	var window := PanelContainer.new()
	window.add_theme_stylebox_override("panel", _box_style(WINDOW_COLOR, WINDOW_BORDER, 8, 10))
	center.add_child(window)
	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 6)
	window.add_child(layout)
	var title := Label.new()
	title.text = "СРАВНЕНИЕ ПЕРСОНАЖЕЙ"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_font_size_override("font_size", 15)
	title.add_theme_color_override("font_color", TITLE_COLOR)
	layout.add_child(title)
	var cards := HBoxContainer.new()
	cards.add_theme_constant_override("separation", 12)
	layout.add_child(cards)
	_player_card = CARD_SCRIPT.new()
	_player_card.stat_requested.connect(_relay_stat)
	cards.add_child(_player_card)
	_opponent_card = CARD_SCRIPT.new()
	cards.add_child(_opponent_card)
	_status = Label.new()
	_status.custom_minimum_size.y = 18
	_status.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_status.add_theme_font_size_override("font_size", 13)
	layout.add_child(_status)
	var buttons := HBoxContainer.new()
	buttons.alignment = BoxContainer.ALIGNMENT_CENTER
	buttons.add_theme_constant_override("separation", 12)
	layout.add_child(buttons)
	_challenge_button = Button.new()
	_challenge_button.text = "БРОСИТЬ ВЫЗОВ"
	_challenge_button.custom_minimum_size = Vector2(170, 32)
	_challenge_button.pressed.connect(func() -> void: challenge_requested.emit())
	buttons.add_child(_challenge_button)
	_close_button = Button.new()
	_close_button.text = "ЗАКРЫТЬ"
	_close_button.custom_minimum_size = Vector2(120, 32)
	_close_button.pressed.connect(close)
	buttons.add_child(_close_button)
	_tooltip = PanelContainer.new()
	_tooltip.custom_minimum_size.x = TOOLTIP_WIDTH
	_tooltip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_tooltip.visible = false
	_tooltip.add_theme_stylebox_override("panel", _box_style(TOOLTIP_COLOR, TOOLTIP_BORDER, 6, 8))
	add_child(_tooltip)
	_tooltip_box = VBoxContainer.new()
	_tooltip_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_tooltip.add_child(_tooltip_box)


func open(player: Dictionary, opponent: Dictionary) -> void:
	show_profiles(player, opponent)
	set_status("", false)
	visible = true


func show_profiles(player: Dictionary, opponent: Dictionary) -> void:
	_player_raw = player.duplicate(true)
	_opponent_raw = opponent.duplicate(true)
	_render()


func update_player(player: Dictionary) -> void:
	_player_raw = player.duplicate(true)
	_render()


func set_status(text: String, is_error := false) -> void:
	_status.text = text
	_status.add_theme_color_override("font_color", ERROR_COLOR if is_error else INFO_COLOR)


func close() -> void:
	visible = false
	_hide_tooltip()


func _render() -> void:
	_player_card.set_profile(
		RULES.normalize_profile(_player_raw, "ИГРОК", "player"),
		"ИГРОК",
		PLAYER_BORDER,
		true,
		_derived_opponent(_player_raw, _opponent_raw),
	)
	_opponent_card.set_profile(
		RULES.normalize_profile(_opponent_raw, "ПРОТИВНИК", "enemy"),
		"ПРОТИВНИК",
		ENEMY_BORDER,
		false,
		_derived_opponent(_opponent_raw, _player_raw),
	)


# Порт CharacterComparison._draw_card: маг считается без соперника, остальные получают соперника-воина.
func _derived_opponent(card_raw: Dictionary, other_raw: Dictionary) -> Variant:
	if RULES.is_mage_profile(card_raw) or not RULES.is_warrior_profile(other_raw):
		return null
	return other_raw


func _relay_stat(stat_name: String, delta: int) -> void:
	stat_requested.emit(stat_name, delta)


func _process(_delta: float) -> void:
	if not visible:
		return
	var mouse := get_global_mouse_position()
	var item: Dictionary = _player_card.slot_item_at(mouse)
	if item.is_empty():
		item = _opponent_card.slot_item_at(mouse)
	if item.is_empty():
		_hide_tooltip()
		return
	if str(item.get("name", "")) != _tooltip_item:
		_show_tooltip(item)
	_tooltip.global_position = _tooltip_position(mouse)


func _show_tooltip(item: Dictionary) -> void:
	_tooltip_item = str(item.get("name", ""))
	for child in _tooltip_box.get_children():
		_tooltip_box.remove_child(child)
		child.queue_free()
	for line in RULES.equipment_tooltip_lines(item):
		var label := Label.new()
		label.text = str(line[0])
		label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		label.custom_minimum_size.x = TOOLTIP_WIDTH - 16.0
		label.add_theme_font_size_override("font_size", 13)
		label.add_theme_color_override("font_color", line[1])
		label.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_tooltip_box.add_child(label)
	_tooltip.visible = true


func _hide_tooltip() -> void:
	_tooltip.visible = false
	_tooltip_item = ""


func _tooltip_position(mouse: Vector2) -> Vector2:
	var screen := get_viewport_rect().size
	var tooltip_size := _tooltip.size
	var target := mouse + Vector2(16, 16)
	target.x = clampf(target.x, 6.0, maxf(6.0, screen.x - tooltip_size.x - 6.0))
	target.y = clampf(target.y, 6.0, maxf(6.0, screen.y - tooltip_size.y - 6.0))
	return target


func _box_style(background: Color, border: Color, radius: int, margin: int) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = background
	style.border_color = border
	style.set_border_width_all(2)
	style.set_corner_radius_all(radius)
	style.set_content_margin_all(margin)
	return style
