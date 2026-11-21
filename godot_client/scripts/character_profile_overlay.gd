extends Control

# Оверлей профиля из ui/character_profile_overlay.py: карточка слева, справа от неё кнопка «РЮКЗАК»
# и кнопки слотов 2–9, которые в Python пока ничего не делают.

signal stat_requested(stat_name: String, delta: int)
signal level_requested(delta: int)
signal backpack_requested

const CARD_SCRIPT := preload("res://scripts/character_card.gd")

const DESIGN_SIZE := Vector2(1920.0, 1080.0)
const PANEL_SCALE := 2.0 / 3.0
const CARD_POSITION := Vector2(5.0, 10.0)
const BACKPACK_RECT := Rect2(445.0, 10.0, 130.0, 40.0)
const SLOT_BUTTON_X := 445.0
const SLOT_BUTTON_TOP := 60.0
const SLOT_BUTTON_STEP := 45.0
const SLOT_BUTTON_SIZE := Vector2(100.0, 40.0)
const BACKPACK_COLOR := Color8(210, 100, 90)

var _root: Control
var _card: CARD_SCRIPT
var _backpack_button: Button


func _init() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	z_index = 60
	visible = false
	_root = Control.new()
	_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.size = DESIGN_SIZE
	_root.scale = Vector2(PANEL_SCALE, PANEL_SCALE)
	add_child(_root)
	_card = CARD_SCRIPT.new()
	_card.position = CARD_POSITION
	_card.stat_requested.connect(_on_card_stat_requested)
	_card.level_requested.connect(_on_card_level_requested)
	_card.close_requested.connect(close)
	_root.add_child(_card)
	_backpack_button = _make_button("РЮКЗАК", BACKPACK_RECT, true)
	_backpack_button.pressed.connect(backpack_requested.emit)
	_root.add_child(_backpack_button)
	for index in range(1, 9):
		var top := SLOT_BUTTON_TOP + (index + 1) * SLOT_BUTTON_STEP
		_root.add_child(_make_button(str(index + 1), Rect2(Vector2(SLOT_BUTTON_X, top), SLOT_BUTTON_SIZE), false))


func is_open() -> bool:
	return visible


func open(profile: Dictionary) -> void:
	_card.set_profile(profile)
	visible = true


func update_profile(profile: Dictionary) -> void:
	_card.set_profile(profile)


func current_profile() -> Dictionary:
	return _card.current_profile()


func close() -> void:
	visible = false


# Слот-ориентир для выбранного предмета рюкзака (зелёная рамка на карточке).
func set_guide_slot(slot: String) -> void:
	_card.set_guide_slot(slot)


# Ключ слота экипировки карточки под точкой экрана; пусто, если карточка закрыта или точка мимо слота.
func equipment_slot_at_global(global_point: Vector2) -> String:
	if not visible:
		return ""
	var local := _card.get_global_transform_with_canvas().affine_inverse() * global_point
	if not Rect2(Vector2.ZERO, _card.size).has_point(local):
		return ""
	return _card.slot_key_at(local)


func _on_card_stat_requested(stat_name: String, delta: int) -> void:
	stat_requested.emit(stat_name, delta)


func _on_card_level_requested(delta: int) -> void:
	level_requested.emit(delta)


func _make_button(text: String, rect: Rect2, enabled: bool) -> Button:
	var button := Button.new()
	button.text = text
	button.position = rect.position
	button.size = rect.size
	button.disabled = not enabled
	button.focus_mode = Control.FOCUS_NONE
	button.add_theme_font_size_override("font_size", 18)
	if enabled:
		button.add_theme_stylebox_override("normal", _button_style(BACKPACK_COLOR))
		button.add_theme_stylebox_override("hover", _button_style(BACKPACK_COLOR.lightened(0.15)))
		button.add_theme_stylebox_override("pressed", _button_style(BACKPACK_COLOR.darkened(0.15)))
	return button


func _button_style(color: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.set_corner_radius_all(4)
	return style
