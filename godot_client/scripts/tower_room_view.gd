extends Control

# Вид комнаты персонажа Tower: фон assets/town/character_room, вкладки «Экипировка» и «Сундуки», кнопки «Рюкзак»
# и «Вернуться в таверну» (дверь). Данные приходят из world_entry.gd, тексты и порядок строк — из tower_room_rules.gd.

signal tab_selected(tab: String)
signal door_requested
signal inventory_requested
signal withdraw_requested(storage_type: String, item: Dictionary)

const RULES := preload("res://scripts/tower_room_rules.gd")
const FALLBACK_COLOR := Color8(38, 27, 24)
const SHADE_COLOR := Color(0.0, 0.0, 0.0, 0.39)
const TITLE_COLOR := Color8(255, 220, 120)
const MUTED_COLOR := Color8(200, 200, 205)
const SECTION_COLOR := Color8(220, 200, 150)
const TEXT_COLOR := Color8(228, 228, 234)
const EMPTY_COLOR := Color8(140, 140, 150)
const PANEL_COLOR := Color8(18, 22, 30, 226)
const PANEL_BORDER_COLOR := Color8(150, 120, 70)
const BUTTON_FILL := Color8(24, 29, 38, 226)
const BUTTON_HOVER_FILL := Color8(44, 52, 64, 236)
const BUTTON_ACTIVE_FILL := Color8(92, 72, 40, 240)
const BUTTON_BORDER_COLOR := Color8(190, 150, 80)
const TAB_SIZE := Vector2(150.0, 36.0)
const BACKPACK_SIZE := Vector2(120.0, 36.0)
const DOOR_SIZE := Vector2(220.0, 40.0)
const CONTENT_LEFT := 40.0
const CONTENT_RIGHT := 600.0
const CONTENT_TOP := 164.0
const CONTENT_BOTTOM_MARGIN := 150.0

static var _background: Texture2D = null
static var _background_loaded := false

var _tab := RULES.TAB_EQUIPMENT
var _equipment: Dictionary = {}
var _chests: Dictionary = {}
var _character_label: Label
var _status: Label
var _tab_buttons: Dictionary = {}
var _content: VBoxContainer


func _init() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	resized.connect(queue_redraw)

	var title := Label.new()
	title.text = "КОМНАТА ПЕРСОНАЖА"
	title.position = Vector2(40.0, 24.0)
	title.add_theme_font_size_override("font_size", 26)
	title.add_theme_color_override("font_color", TITLE_COLOR)
	add_child(title)

	_character_label = Label.new()
	_character_label.position = Vector2(40.0, 60.0)
	_character_label.add_theme_color_override("font_color", MUTED_COLOR)
	add_child(_character_label)

	var tabs := HBoxContainer.new()
	tabs.position = Vector2(40.0, 96.0)
	tabs.add_theme_constant_override("separation", 8)
	add_child(tabs)
	for tab in [RULES.TAB_EQUIPMENT, RULES.TAB_CHESTS]:
		var tab_button := Button.new()
		tab_button.text = str(RULES.TAB_TITLES[tab])
		tab_button.toggle_mode = true
		tab_button.custom_minimum_size = TAB_SIZE
		_style_button(tab_button)
		tab_button.pressed.connect(_on_tab_pressed.bind(tab))
		tabs.add_child(tab_button)
		_tab_buttons[tab] = tab_button
	var backpack := Button.new()
	backpack.text = "Рюкзак"
	backpack.custom_minimum_size = BACKPACK_SIZE
	_style_button(backpack)
	backpack.pressed.connect(_on_backpack_pressed)
	tabs.add_child(backpack)

	_status = Label.new()
	_status.position = Vector2(40.0, 138.0)
	_status.add_theme_color_override("font_color", MUTED_COLOR)
	add_child(_status)

	var panel := PanelContainer.new()
	panel.set_anchors_and_offsets_preset(Control.PRESET_LEFT_WIDE)
	panel.offset_left = CONTENT_LEFT
	panel.offset_top = CONTENT_TOP
	panel.offset_right = CONTENT_RIGHT
	panel.offset_bottom = -CONTENT_BOTTOM_MARGIN
	panel.add_theme_stylebox_override("panel", _panel_style())
	add_child(panel)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	panel.add_child(scroll)
	_content = VBoxContainer.new()
	_content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_content.add_theme_constant_override("separation", 6)
	scroll.add_child(_content)

	var door := Button.new()
	door.text = "Вернуться в таверну"
	door.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	door.offset_left = CONTENT_LEFT
	door.offset_top = -128.0
	door.offset_right = CONTENT_LEFT + DOOR_SIZE.x
	door.offset_bottom = -128.0 + DOOR_SIZE.y
	_style_button(door)
	door.pressed.connect(_on_door_pressed)
	add_child(door)

	set_tab(_tab)


func _draw() -> void:
	var texture := background_texture()
	if texture == null:
		draw_rect(Rect2(Vector2.ZERO, size), FALLBACK_COLOR)
	else:
		draw_texture_rect(texture, Rect2(Vector2.ZERO, size), false)
	draw_rect(Rect2(Vector2.ZERO, size), SHADE_COLOR)


static func background_texture() -> Texture2D:
	if not _background_loaded:
		_background_loaded = true
		var path := ProjectSettings.globalize_path("res://").path_join("../assets/town/character_room/background.png").simplify_path()
		if FileAccess.file_exists(path):
			var image := Image.load_from_file(path)
			if image != null and not image.is_empty():
				_background = ImageTexture.create_from_image(image)
	return _background


func set_character(character: Dictionary) -> void:
	_character_label.text = RULES.character_line(character)


func set_equipment(equipment: Dictionary) -> void:
	_equipment = equipment.duplicate(true)
	if _tab == RULES.TAB_EQUIPMENT:
		_refresh_content()


func set_chests(chests: Dictionary) -> void:
	_chests = chests.duplicate(true)
	if _tab == RULES.TAB_CHESTS:
		_refresh_content()


func set_tab(tab: String) -> void:
	if not RULES.is_tab(tab):
		return
	_tab = tab
	for key in _tab_buttons:
		var tab_button: Button = _tab_buttons[key]
		tab_button.button_pressed = key == tab
	_refresh_content()


func current_tab() -> String:
	return _tab


func set_status(text: String) -> void:
	_status.text = text


func _on_tab_pressed(tab: String) -> void:
	set_tab(tab)
	tab_selected.emit(tab)


func _on_backpack_pressed() -> void:
	inventory_requested.emit()


func _on_door_pressed() -> void:
	door_requested.emit()


func _on_withdraw_pressed(storage_type: String, item: Dictionary) -> void:
	withdraw_requested.emit(storage_type, item)


func _refresh_content() -> void:
	for child in _content.get_children():
		_content.remove_child(child)
		child.queue_free()
	if _tab == RULES.TAB_EQUIPMENT:
		_build_equipment()
	else:
		_build_chests()


func _build_equipment() -> void:
	_add_title("Надето")
	for row in RULES.equipment_rows(_equipment):
		_add_text(str(row["text"]), TEXT_COLOR if bool(row["filled"]) else EMPTY_COLOR)
	_add_text(RULES.EQUIPMENT_HINT, MUTED_COLOR)


func _build_chests() -> void:
	for storage_type in RULES.CHEST_TYPES:
		var items: Array = _chests.get(storage_type, [])
		_add_title(RULES.chest_title(str(storage_type), items.size()))
		if items.is_empty():
			_add_text(RULES.EMPTY_CHEST_TEXT, EMPTY_COLOR)
		for item in items:
			if item is Dictionary:
				_add_storage_row(str(storage_type), item)


func _add_storage_row(storage_type: String, item: Dictionary) -> void:
	var row := HBoxContainer.new()
	var label := Label.new()
	label.text = RULES.storage_item_text(item)
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.add_theme_color_override("font_color", TEXT_COLOR)
	row.add_child(label)
	var withdraw := Button.new()
	withdraw.text = "В рюкзак"
	_style_button(withdraw)
	withdraw.pressed.connect(_on_withdraw_pressed.bind(storage_type, item))
	row.add_child(withdraw)
	_content.add_child(row)


func _add_title(text: String) -> void:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", 18)
	label.add_theme_color_override("font_color", SECTION_COLOR)
	_content.add_child(label)


func _add_text(text: String, color: Color) -> void:
	var label := Label.new()
	label.text = text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.add_theme_color_override("font_color", color)
	_content.add_child(label)


func _style_button(button: Button) -> void:
	button.focus_mode = Control.FOCUS_NONE
	button.add_theme_stylebox_override("normal", _button_style(BUTTON_FILL))
	button.add_theme_stylebox_override("hover", _button_style(BUTTON_HOVER_FILL))
	button.add_theme_stylebox_override("pressed", _button_style(BUTTON_ACTIVE_FILL))
	button.add_theme_stylebox_override("hover_pressed", _button_style(BUTTON_ACTIVE_FILL))
	button.add_theme_stylebox_override("focus", _button_style(BUTTON_FILL))


func _button_style(fill: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = fill
	style.border_color = BUTTON_BORDER_COLOR
	style.set_border_width_all(1)
	style.set_corner_radius_all(6)
	style.set_content_margin_all(6.0)
	return style


func _panel_style() -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = PANEL_COLOR
	style.border_color = PANEL_BORDER_COLOR
	style.set_border_width_all(1)
	style.set_corner_radius_all(6)
	style.set_content_margin_all(12.0)
	return style
