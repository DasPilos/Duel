extends Control

# Вид комнаты персонажа Колоды: фон и раскладка deck/scenes/character_room.py. Вкладки «Экипировка», «Сундуки» и
# «Колоды», дверь в таверну, кнопка карточки (в Python — 📦) и область чата. Список мира переносится в область чата
# через dock_list, как на заднем дворе. Запросы и действия ведёт мир (deck_world.gd), сетевого кода здесь нет.

signal tab_selected(tab: String)
signal door_requested
signal stat_requested(stat_name: String, delta: int)
signal level_requested(delta: int)
signal backpack_requested

const RULES := preload("res://scripts/deck_room_rules.gd")
const PROFILE_OVERLAY_SCRIPT := preload("res://scripts/character_profile_overlay.gd")
const FALLBACK_COLOR := Color8(38, 27, 24)
const SHADE_COLOR := Color(0.0, 0.0, 0.0, 0.39)
const PANEL_COLOR := Color8(18, 22, 30, 226)
const PANEL_BORDER_COLOR := Color8(150, 120, 70)
const TITLE_COLOR := Color8(255, 220, 120)
const INFO_COLOR := Color8(200, 200, 200)
const SECTION_COLOR := Color8(220, 200, 150)
const SLOT_COLOR := Color8(200, 200, 200)
const ITEM_COLOR := Color8(150, 200, 255)
const BONUS_COLOR := Color8(100, 200, 100)
const EMPTY_COLOR := Color8(100, 100, 100)
const MUTED_COLOR := Color8(150, 150, 150)
const ERROR_COLOR := Color8(230, 140, 120)
const TAB_COLOR := Color8(80, 100, 140)
const TAB_ACTIVE_COLOR := Color8(100, 180, 255)
const TAVERN_COLOR := Color8(110, 75, 50)
const CARD_COLOR := Color8(100, 100, 120)
const CARD_BORDER_COLOR := Color8(150, 150, 170)
const WHITE := Color8(255, 255, 255)
const TAB_SIZE := Vector2(150.0, 40.0)
const TAVERN_SIZE := Vector2(240.0, 48.0)
const CONTENT_TOP := 190.0
const CONTENT_BOTTOM := 130.0
const CONTENT_RIGHT_RATIO := 0.6
const CHAT_MARGIN := 40.0
const SCROLL_BAR_WIDTH := 14.0
const SCROLL_TRACK_COLOR := Color8(44, 40, 34, 230)
const SCROLL_THUMB_COLOR := Color8(170, 135, 75)
const SCROLL_THUMB_HOVER_COLOR := Color8(220, 180, 100)

static var _background: Texture2D = null
static var _background_loaded := false

var _tab := RULES.TAB_EQUIPMENT
var _character: Dictionary = {}
var _equipment: Dictionary = {}
var _chests: Dictionary = {}
var _decks: Array = []
var _states: Dictionary = {}
var _info_label: Label
var _status_label: Label
var _tab_buttons: Dictionary = {}
var _content: VBoxContainer
var _scroll: ScrollContainer
var _chat_box: VBoxContainer
var _profile


func _init() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	visible = false
	resized.connect(queue_redraw)

	var title := _plain_label(RULES.TITLE_TEXT, TITLE_COLOR, 30)
	title.position = Vector2(40.0, 22.0)
	add_child(title)
	_info_label = _plain_label("", INFO_COLOR, 18)
	_info_label.position = Vector2(40.0, 66.0)
	add_child(_info_label)

	var tabs := HBoxContainer.new()
	tabs.position = Vector2(40.0, 104.0)
	tabs.add_theme_constant_override("separation", 8)
	add_child(tabs)
	for tab in RULES.TAB_ORDER:
		var tab_button := Button.new()
		tab_button.text = str(RULES.TAB_TITLES[tab])
		tab_button.toggle_mode = true
		tab_button.custom_minimum_size = TAB_SIZE
		_style_tab(tab_button)
		tab_button.pressed.connect(_on_tab_pressed.bind(tab))
		tabs.add_child(tab_button)
		_tab_buttons[tab] = tab_button

	_status_label = _plain_label("", MUTED_COLOR, 16)
	_status_label.position = Vector2(40.0, 152.0)
	add_child(_status_label)

	var panel := PanelContainer.new()
	panel.anchor_right = CONTENT_RIGHT_RATIO
	panel.anchor_bottom = 1.0
	panel.offset_left = 40.0
	panel.offset_top = CONTENT_TOP
	panel.offset_right = -16.0
	panel.offset_bottom = -CONTENT_BOTTOM
	panel.add_theme_stylebox_override("panel", _panel_style())
	add_child(panel)
	_scroll = ScrollContainer.new()
	_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	# Полоса видна всегда: по длине ползунка понятно, сколько ещё можно прокрутить.
	_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_SHOW_ALWAYS
	_style_scroll_bar(_scroll.get_v_scroll_bar())
	panel.add_child(_scroll)
	_content = VBoxContainer.new()
	_content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_content.add_theme_constant_override("separation", 8)
	_scroll.add_child(_content)

	var chat_panel := PanelContainer.new()
	chat_panel.anchor_left = CONTENT_RIGHT_RATIO
	chat_panel.anchor_right = 1.0
	chat_panel.anchor_bottom = 1.0
	chat_panel.offset_left = 16.0
	chat_panel.offset_top = CONTENT_TOP
	chat_panel.offset_right = -CHAT_MARGIN
	chat_panel.offset_bottom = -CHAT_MARGIN
	chat_panel.add_theme_stylebox_override("panel", _panel_style())
	add_child(chat_panel)
	var chat_scroll := ScrollContainer.new()
	chat_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	chat_panel.add_child(chat_scroll)
	_chat_box = VBoxContainer.new()
	_chat_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	chat_scroll.add_child(_chat_box)

	var tavern := Button.new()
	tavern.text = RULES.TAVERN_TEXT
	tavern.focus_mode = Control.FOCUS_NONE
	tavern.anchor_top = 1.0
	tavern.anchor_bottom = 1.0
	tavern.offset_left = 40.0
	tavern.offset_top = -TAVERN_SIZE.y - 32.0
	tavern.offset_right = 40.0 + TAVERN_SIZE.x
	tavern.offset_bottom = -32.0
	_style_button(tavern, TAVERN_COLOR)
	tavern.pressed.connect(door_requested.emit)
	add_child(tavern)

	var card := Button.new()
	card.focus_mode = Control.FOCUS_NONE
	card.tooltip_text = RULES.CARD_TOOLTIP
	card.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
	card.offset_left = -70.0
	card.offset_top = 10.0
	card.offset_right = -20.0
	card.offset_bottom = 60.0
	for style_name in ["normal", "hover", "pressed", "focus"]:
		card.add_theme_stylebox_override(style_name, _box_style(CARD_COLOR, CARD_BORDER_COLOR, 2))
	card.pressed.connect(_on_card_pressed)
	add_child(card)
	var icon := Control.new()
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	icon.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	icon.draw.connect(_draw_card_icon.bind(icon))
	card.add_child(icon)

	_profile = PROFILE_OVERLAY_SCRIPT.new()
	_profile.stat_requested.connect(stat_requested.emit)
	_profile.level_requested.connect(level_requested.emit)
	_profile.backpack_requested.connect(backpack_requested.emit)
	add_child(_profile)
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


func set_active(active: bool) -> void:
	visible = active


func set_message(text: String) -> void:
	if _status_label.text != text:
		_status_label.text = text


func set_character(character: Dictionary) -> void:
	_character = character.duplicate(true)
	_info_label.text = RULES.character_line(_character)
	if _profile.is_open():
		_profile.update_profile(_character.duplicate(true))


func is_profile_open() -> bool:
	return _profile.is_open()


func current_tab() -> String:
	return _tab


func set_tab(tab: String) -> void:
	if not RULES.is_tab(tab):
		return
	_tab = tab
	for key in _tab_buttons:
		(_tab_buttons[key] as Button).button_pressed = key == tab
	_refresh_content()


# Новый визит в комнату: разделы снова не загружены, открывается вкладка «Экипировка», карточка закрывается — как в Python,
# где комната создаётся заново.
func reset() -> void:
	if _profile.is_open():
		_profile.close()
	_equipment = {}
	_chests = {}
	_decks = []
	_states = {}
	set_tab(RULES.TAB_EQUIPMENT)


func section_state(section: String) -> String:
	return str(_states.get(section, RULES.STATE_IDLE))


func set_section_state(section: String, state: String) -> void:
	_states[section] = state
	_refresh_content()


func set_section_data(section: String, data: Variant) -> void:
	if section == RULES.SECTION_EQUIPMENT:
		_equipment = (data as Dictionary).duplicate(true)
	elif section == RULES.SECTION_DECKS:
		_decks = (data as Array).duplicate(true)
	else:
		_chests[section] = (data as Array).duplicate(true)
	_states[section] = RULES.STATE_READY
	_refresh_content()


# Список мира переезжает в область чата комнаты; обратно его возвращает undock_list.
func dock_list(list: Control) -> void:
	if list.get_parent() == _chat_box:
		return
	list.reparent(_chat_box, false)


func undock_list(list: Control, home: Control, separation: int) -> void:
	if list.get_parent() != _chat_box:
		return
	list.reparent(home, false)
	list.add_theme_constant_override("separation", separation)


func _on_tab_pressed(tab: String) -> void:
	set_tab(tab)
	tab_selected.emit(tab)


func _on_card_pressed() -> void:
	if not _character.is_empty():
		_profile.open(_character.duplicate(true))


# I открывает ту же карточку, что кнопка карточки; возвращает true, если карточка открылась.
func toggle_profile() -> bool:
	if _profile.is_open():
		_profile.close()
		return false
	_on_card_pressed()
	return _profile.is_open()


func _refresh_content() -> void:
	for child in _content.get_children():
		_content.remove_child(child)
		child.queue_free()
	if _tab == RULES.TAB_EQUIPMENT:
		_build_equipment()
	elif _tab == RULES.TAB_CHESTS:
		_build_chests()
	else:
		_build_decks()


func _build_equipment() -> void:
	_add_title(RULES.EQUIPMENT_TITLE)
	if _add_pending(RULES.SECTION_EQUIPMENT):
		return
	if _equipment.is_empty():
		_add_text(RULES.EQUIPMENT_EMPTY_TEXT, MUTED_COLOR)
		return
	for row in RULES.equipment_rows(_equipment):
		_add_equipment_row(row)


func _add_equipment_row(row: Dictionary) -> void:
	var line := HBoxContainer.new()
	line.add_theme_constant_override("separation", 16)
	var slot := _plain_label(str(row["label"]), SLOT_COLOR, 18)
	slot.custom_minimum_size = Vector2(150.0, 0.0)
	line.add_child(slot)
	var details := VBoxContainer.new()
	details.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	line.add_child(details)
	var item_color := EMPTY_COLOR if bool(row["empty"]) else ITEM_COLOR
	details.add_child(_label(str(row["name"]), item_color, 18))
	var bonuses := str(row["bonuses"])
	if not bonuses.is_empty():
		details.add_child(_label(bonuses, BONUS_COLOR, 16))
	_content.add_child(line)


func _build_chests() -> void:
	_add_title(RULES.CHESTS_TITLE)
	for section in [RULES.SECTION_CHEST1, RULES.SECTION_CHEST2]:
		_add_text(RULES.chest_title(section), SECTION_COLOR, 18)
		if _add_pending(section):
			continue
		var items: Array = _chests.get(section, [])
		if items.is_empty():
			_add_text(RULES.CHEST_EMPTY_TEXT, MUTED_COLOR)
		for line in RULES.storage_lines(items):
			_add_text(line, MUTED_COLOR)


func _build_decks() -> void:
	_add_title(RULES.DECKS_TITLE)
	if _add_pending(RULES.SECTION_DECKS):
		return
	if _decks.is_empty():
		_add_text(RULES.DECKS_EMPTY_TEXT, MUTED_COLOR)
		return
	for index in _decks.size():
		var deck: Variant = _decks[index]
		if deck is Dictionary:
			_add_text(RULES.deck_title(deck, index), SECTION_COLOR, 18)
			_add_text(RULES.deck_info_text(deck), MUTED_COLOR, 16)


# Пока раздел не загружен, вместо его содержимого выводится состояние. Возвращает true, если содержимого нет.
func _add_pending(section: String) -> bool:
	var state := section_state(section)
	if state == RULES.STATE_READY:
		return false
	if state == RULES.STATE_FAILED:
		_add_text(RULES.FAILED_TEXT, ERROR_COLOR)
	else:
		_add_text(RULES.LOADING_TEXT, MUTED_COLOR)
	return true


func _add_title(text: String) -> void:
	_add_text(text, SECTION_COLOR, 24)


func _add_text(text: String, color: Color, font_size := 18) -> void:
	_content.add_child(_label(text, color, font_size))


func _plain_label(text: String, color: Color, font_size: int) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_color_override("font_color", color)
	label.add_theme_font_size_override("font_size", font_size)
	return label


func _label(text: String, color: Color, font_size: int) -> Label:
	var label := _plain_label(text, color, font_size)
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	return label


func _style_scroll_bar(bar: VScrollBar) -> void:
	bar.custom_minimum_size = Vector2(SCROLL_BAR_WIDTH, 0.0)
	bar.add_theme_stylebox_override("scroll", _box_style(SCROLL_TRACK_COLOR))
	bar.add_theme_stylebox_override("grabber", _box_style(SCROLL_THUMB_COLOR))
	bar.add_theme_stylebox_override("grabber_highlight", _box_style(SCROLL_THUMB_HOVER_COLOR))
	bar.add_theme_stylebox_override("grabber_pressed", _box_style(SCROLL_THUMB_HOVER_COLOR))


func _style_tab(button: Button) -> void:
	_style_button(button, TAB_COLOR)
	button.add_theme_stylebox_override("pressed", _box_style(TAB_ACTIVE_COLOR))
	button.add_theme_stylebox_override("hover_pressed", _box_style(TAB_ACTIVE_COLOR))


func _style_button(button: Button, color: Color) -> void:
	button.add_theme_stylebox_override("normal", _box_style(color))
	button.add_theme_stylebox_override("hover", _box_style(color.lightened(0.15)))
	button.add_theme_stylebox_override("pressed", _box_style(color.darkened(0.15)))
	button.add_theme_stylebox_override("focus", _box_style(color))
	button.add_theme_color_override("font_color", WHITE)
	button.add_theme_font_size_override("font_size", 18)


func _box_style(color: Color, border := Color(0.0, 0.0, 0.0, 0.0), border_width := 0) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.set_corner_radius_all(6)
	style.set_border_width_all(border_width)
	style.border_color = border
	return style


func _panel_style() -> StyleBoxFlat:
	var style := _box_style(PANEL_COLOR, PANEL_BORDER_COLOR, 1)
	style.set_content_margin_all(12.0)
	return style


# Иконка «рюкзака» на кнопке карточки: та же, что на заднем дворе.
func _draw_card_icon(icon: Control) -> void:
	icon.draw_rect(Rect2(14.0, 20.0, 22.0, 18.0), Color8(176, 132, 78))
	icon.draw_rect(Rect2(14.0, 20.0, 22.0, 18.0), Color8(110, 80, 45), false, 1.5)
	icon.draw_rect(Rect2(14.0, 14.0, 22.0, 7.0), Color8(200, 160, 100))
	icon.draw_rect(Rect2(24.0, 14.0, 2.0, 24.0), Color8(230, 205, 150))
