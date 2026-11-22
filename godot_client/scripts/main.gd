extends Control

const TITLE_COLOR := Color(0.94, 0.82, 0.56)
const MUTED_COLOR := Color(0.62, 0.68, 0.77)
const LOGIN_TEXT_COLOR := Color(0.96, 0.89, 0.75)
const LOGIN_SCALE := 0.588
const LOGIN_FONT_SCALE := 0.85
const LOGIN_PREFERENCES_PATH := "user://login_preferences.cfg"
const LOBBY_CHAT_SCRIPT := preload("res://scripts/lobby_chat_panel.gd")
const LOBBY_FORMAT := preload("res://scripts/lobby_format.gd")
const WORLD_CREATE_DIALOG_SCRIPT := preload("res://scripts/world_create_dialog.gd")
const LOBBY_ACCOUNT_CARD_SCRIPT := preload("res://scripts/lobby_account_card.gd")
const LOBBY_CONTEXT_MENU_SCRIPT := preload("res://scripts/lobby_context_menu.gd")
const AVATAR_CROP_DIALOG_SCRIPT := preload("res://scripts/avatar_crop_dialog.gd")
const EXIT_MENU_SCRIPT := preload("res://scripts/exit_menu.gd")
const SCENE_TRANSITION := preload("res://scripts/scene_transition.gd")
# Базовые единицы 1280×720: при окне 1920×1080 (масштаб 1.5) отступ около 10 px, панель миров 500×800 px.
const LOBBY_EDGE_MARGIN := 7.0
const LOBBY_WORLDS_SIZE := Vector2(333, 533)
const LOBBY_ACCOUNT_WIDTH := 240.0
const LOBBY_TOP_BAR_LEFT := 260.0
const LOBBY_TOP_BAR_RIGHT_GAP := 350.0
const LOBBY_AVATAR_SIZE := 150
const LOBBY_TEXT_COLOR := Color(0.9, 0.9, 0.92)
const MODE_NAMES := {
	"economy": "Economy",
	"deck": "Deck",
	"front_line": "Front Line",
}
const TITLE_BIOMES := [
	{"name": "Лесная долина", "video": preload("res://assets/ui/title_biomes/grassland.ogv")},
	{"name": "Зимний лес", "video": preload("res://assets/ui/title_biomes/winter.ogv")},
	{"name": "Пустынные руины", "video": preload("res://assets/ui/title_biomes/desert.ogv")},
	{"name": "Топкие земли", "video": preload("res://assets/ui/title_biomes/swamp.ogv")},
	{"name": "Каменистые земли", "video": preload("res://assets/ui/title_biomes/rocky.ogv")},
	{"name": "Земли нежити", "video": preload("res://assets/ui/title_biomes/undead.ogv")},
	{"name": "Проклятые земли", "video": preload("res://assets/ui/title_biomes/cursed.ogv")},
]

var _content: VBoxContainer
var _content_margin: MarginContainer
var _screen_center: CenterContainer
var _screen_panel: PanelContainer
var _screen_background: ColorRect
var _title_background_layers: Array[VideoStreamPlayer] = []
var _title_cycle_timer: Timer
var _title_transition: Tween
var _title_biome_index := -1
var _active_title_layer := 0
var _biome_caption: Label
var _base_panel_style: StyleBoxFlat
var _login_panel_style: StyleBoxFlat
var _login_theme_active := false
var _status: Label
var _server_input: LineEdit
var _server_version_label: Label
var _client_version_label: Label
var _version_check_timer: Timer
var _version_check_url := ""
var _checked_server_url := ""
var _server_compatible := false
var _auth_after_version := ""
var _username_input: LineEdit
var _password_input: LineEdit
var _login_button: Button
var _remember_username_check: Button
var _remember_password_check: Button
var _remembered_username := ""
var _remembered_password := ""
var _remember_username := false
var _remember_password := false
var _login_preferences_path := LOGIN_PREFERENCES_PATH
var _create_view
var _worlds: Array[Dictionary] = []
var _lobby_players: Array[Dictionary] = []
var _current_world: Dictionary = {}
var _selected_character: Dictionary = {}
var _pending_action := ""
var _hub_url := "http://127.0.0.1:8765"
var _active_character: Dictionary = {}
var _connection_overlay: ColorRect
var _connection_message: Label
var _connection_counter: Label
var _reload_button: Button
var _character_details: Label
var _delete_password_input: LineEdit
var _lobby_root: Control
var _lobby_status: Label
var _lobby_context_menu
var _worlds_list: VBoxContainer
var _worlds_panel: Control
var _worlds_scroll: ScrollContainer
var _lobby_chat
var _lobby_chat_messages: Array[Dictionary] = []
var _account_card
var _avatar_loaded := false
var _avatar_texture: Texture2D
var _pending_avatar_image: Image
var _avatar_dialog: FileDialog
var _avatar_crop_overlay: ColorRect
var _avatar_crop_dialog
var _world_dialog_overlay: Control
var _world_dialog
var _dialog_world_id := 0
var _account_current_password: LineEdit
var _account_new_password: LineEdit
var _account_confirm_password: LineEdit
var _account_game_nickname: LineEdit
var _lobby_timer: Timer
var _saved_maps: Array[Dictionary] = []
var _new_map_name_input: LineEdit
var _new_map_width: SpinBox
var _new_map_height: SpinBox
var _new_map_tile_size: OptionButton
var _new_map_mode: OptionButton
var _new_map_mode_note: Label
var _exit_menu
var _exit_intent := ""
var _exit_queued := false
var _server_unreachable := false


func _ready() -> void:
	ApiClient.request_completed.connect(_on_api_completed)
	_load_login_preferences()
	_build_shell()
	_build_exit_menu()
	_lobby_timer = Timer.new()
	_lobby_timer.wait_time = 5.0
	_lobby_timer.timeout.connect(_poll_lobby)
	add_child(_lobby_timer)
	_version_check_timer = Timer.new()
	_version_check_timer.one_shot = true
	_version_check_timer.wait_time = 0.5
	_version_check_timer.timeout.connect(_check_server_version)
	add_child(_version_check_timer)
	ConnectionGuard.connection_lost.connect(_on_connection_lost)
	ConnectionGuard.countdown_updated.connect(_on_countdown_updated)
	ConnectionGuard.connection_restored.connect(_on_connection_restored)
	ConnectionGuard.client_outdated.connect(_on_client_outdated)
	ConnectionGuard.session_invalid.connect(_on_session_invalid)
	ConnectionGuard.connection_expired.connect(_on_connection_expired)
	if not GameSession.token.is_empty():
		ApiClient.token = GameSession.token
		ApiClient.set_server_url(GameSession.hub_url)
		_hub_url = GameSession.hub_url
		if not GameSession.world.is_empty():
			_select_world(GameSession.world)
		else:
			_load_worlds()
	else:
		_show_login()


func _exit_tree() -> void:
	if _lobby_timer != null:
		_lobby_timer.stop()
	if get_tree().root.close_requested.is_connected(_on_close_requested):
		get_tree().root.close_requested.disconnect(_on_close_requested)
	get_tree().set_auto_accept_quit(true)
	if ApiClient.request_completed.is_connected(_on_api_completed):
		ApiClient.request_completed.disconnect(_on_api_completed)
	if ConnectionGuard.connection_lost.is_connected(_on_connection_lost):
		ConnectionGuard.connection_lost.disconnect(_on_connection_lost)
	if ConnectionGuard.countdown_updated.is_connected(_on_countdown_updated):
		ConnectionGuard.countdown_updated.disconnect(_on_countdown_updated)
	if ConnectionGuard.connection_restored.is_connected(_on_connection_restored):
		ConnectionGuard.connection_restored.disconnect(_on_connection_restored)
	if ConnectionGuard.client_outdated.is_connected(_on_client_outdated):
		ConnectionGuard.client_outdated.disconnect(_on_client_outdated)
	if ConnectionGuard.session_invalid.is_connected(_on_session_invalid):
		ConnectionGuard.session_invalid.disconnect(_on_session_invalid)
	if ConnectionGuard.connection_expired.is_connected(_on_connection_expired):
		ConnectionGuard.connection_expired.disconnect(_on_connection_expired)


func _build_shell() -> void:
	for index in range(2):
		var title_layer := VideoStreamPlayer.new()
		title_layer.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		title_layer.expand = true
		title_layer.loop = true
		title_layer.volume_db = -80.0
		title_layer.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		title_layer.mouse_filter = Control.MOUSE_FILTER_IGNORE
		title_layer.visible = false
		title_layer.modulate.a = 0.0
		add_child(title_layer)
		_title_background_layers.append(title_layer)

	_screen_background = ColorRect.new()
	_screen_background.color = Color(0.055, 0.067, 0.09)
	_screen_background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_screen_background.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_screen_background)

	_screen_center = CenterContainer.new()
	_screen_center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_screen_center)

	_client_version_label = Label.new()
	_client_version_label.text = "Клиент %s · API %d" % [
		ApiClient.CLIENT_VERSION,
		ApiClient.PROTOCOL_VERSION,
	]
	_client_version_label.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	_client_version_label.offset_left = 16
	_client_version_label.offset_top = -30
	_client_version_label.offset_right = 260
	_client_version_label.offset_bottom = -10
	_client_version_label.add_theme_color_override("font_color", Color(0.82, 0.84, 0.88))
	_client_version_label.visible = false
	add_child(_client_version_label)

	_biome_caption = Label.new()
	_biome_caption.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT)
	_biome_caption.offset_left = -300
	_biome_caption.offset_top = -42
	_biome_caption.offset_right = -28
	_biome_caption.offset_bottom = -18
	_biome_caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_biome_caption.add_theme_color_override("font_color", Color(0.91, 0.87, 0.76))
	_biome_caption.add_theme_color_override("font_outline_color", Color(0.03, 0.04, 0.05, 0.9))
	_biome_caption.add_theme_constant_override("outline_size", 4)
	_biome_caption.add_theme_font_size_override("font_size", 15)
	_biome_caption.visible = false
	add_child(_biome_caption)

	_title_cycle_timer = Timer.new()
	_title_cycle_timer.wait_time = 10.0
	_title_cycle_timer.timeout.connect(_advance_title_background)
	add_child(_title_cycle_timer)

	_screen_panel = PanelContainer.new()
	_screen_panel.custom_minimum_size = Vector2(560, 0)
	_base_panel_style = StyleBoxFlat.new()
	_base_panel_style.bg_color = Color(0.075, 0.07, 0.065, 0.97)
	_base_panel_style.border_color = Color(0.27, 0.22, 0.16)
	_base_panel_style.set_border_width_all(1)
	_base_panel_style.set_corner_radius_all(3)
	_login_panel_style = StyleBoxFlat.new()
	_login_panel_style.bg_color = Color(0.075, 0.078, 0.085, 0.99)
	_login_panel_style.border_color = Color(0.48, 0.36, 0.19)
	_login_panel_style.set_border_width_all(1)
	_login_panel_style.set_corner_radius_all(8)
	_login_panel_style.shadow_color = Color(0, 0, 0, 0.52)
	_login_panel_style.shadow_size = 18
	_login_panel_style.shadow_offset = Vector2(0, 8)
	_screen_panel.add_theme_stylebox_override("panel", _base_panel_style)
	_screen_center.add_child(_screen_panel)

	_content_margin = MarginContainer.new()
	_content_margin.add_theme_constant_override("margin_left", 22)
	_content_margin.add_theme_constant_override("margin_top", 22)
	_content_margin.add_theme_constant_override("margin_right", 22)
	_content_margin.add_theme_constant_override("margin_bottom", 22)
	_screen_panel.add_child(_content_margin)
	_content = VBoxContainer.new()
	_content.add_theme_constant_override("separation", 14)
	_content_margin.add_child(_content)

	_status = Label.new()
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.add_theme_color_override("font_color", MUTED_COLOR)
	_content.add_child(_status)

	_connection_overlay = ColorRect.new()
	_connection_overlay.color = Color(0.025, 0.03, 0.045, 0.94)
	_connection_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_connection_overlay.visible = false
	_connection_overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	_connection_overlay.z_index = 100
	add_child(_connection_overlay)

	var overlay_center := CenterContainer.new()
	overlay_center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_connection_overlay.add_child(overlay_center)

	var overlay_panel := PanelContainer.new()
	overlay_panel.custom_minimum_size = Vector2(560, 220)
	overlay_center.add_child(overlay_panel)

	var overlay_content := VBoxContainer.new()
	overlay_content.add_theme_constant_override("separation", 18)
	overlay_panel.add_child(overlay_content)

	_connection_message = Label.new()
	_connection_message.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_connection_message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_connection_message.add_theme_font_size_override("font_size", 22)
	overlay_content.add_child(_connection_message)

	_connection_counter = Label.new()
	_connection_counter.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_connection_counter.add_theme_font_size_override("font_size", 34)
	_connection_counter.add_theme_color_override("font_color", TITLE_COLOR)
	overlay_content.add_child(_connection_counter)

	_reload_button = Button.new()
	_reload_button.text = "Закрыть клиент"
	_reload_button.custom_minimum_size.y = 42
	_reload_button.visible = false
	_reload_button.pressed.connect(_close_for_reload)
	overlay_content.add_child(_reload_button)


func _start_title_background_rotation() -> void:
	if _title_biome_index < 0:
		_title_biome_index = randi_range(0, TITLE_BIOMES.size() - 1)
	var initial_layer := _title_background_layers[_active_title_layer]
	initial_layer.stream = TITLE_BIOMES[_title_biome_index]["video"]
	initial_layer.modulate = Color.WHITE
	initial_layer.visible = true
	initial_layer.play()
	_title_background_layers[1 - _active_title_layer].visible = false
	_biome_caption.text = str(TITLE_BIOMES[_title_biome_index]["name"])
	_title_cycle_timer.start()


func _advance_title_background() -> void:
	if TITLE_BIOMES.size() < 2:
		return
	var next_biome_index := randi_range(0, TITLE_BIOMES.size() - 2)
	if next_biome_index >= _title_biome_index:
		next_biome_index += 1

	var next_layer_index := 1 - _active_title_layer
	var current_layer := _title_background_layers[_active_title_layer]
	var next_layer := _title_background_layers[next_layer_index]
	next_layer.stop()
	next_layer.stream = TITLE_BIOMES[next_biome_index]["video"]
	next_layer.modulate = Color(1.0, 1.0, 1.0, 0.0)
	next_layer.visible = true
	next_layer.play()

	_title_transition = create_tween().set_parallel(true)
	var fade_out := _title_transition.tween_property(current_layer, "modulate:a", 0.0, 1.5)
	fade_out.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	var fade_in := _title_transition.tween_property(next_layer, "modulate:a", 1.0, 1.5)
	fade_in.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	_title_transition.finished.connect(_finish_title_background_transition.bind(next_biome_index, next_layer_index), CONNECT_ONE_SHOT)


func _finish_title_background_transition(biome_index: int, layer_index: int) -> void:
	var old_layer := _title_background_layers[_active_title_layer]
	old_layer.stop()
	old_layer.stream = null
	old_layer.visible = false
	_title_biome_index = biome_index
	_active_title_layer = layer_index
	_biome_caption.text = str(TITLE_BIOMES[_title_biome_index]["name"])


func _clear_content() -> void:
	DisplaySettings.set_settings_button_visible(false)
	_client_version_label.visible = false
	_screen_center.visible = true
	_close_avatar_crop()
	if _lobby_root != null and is_instance_valid(_lobby_root):
		remove_child(_lobby_root)
		_lobby_root.queue_free()
	_lobby_root = null
	_lobby_chat = null
	_lobby_context_menu = null
	_lobby_status = null
	_worlds_list = null
	_worlds_panel = null
	_worlds_scroll = null
	_account_card = null
	if _version_check_timer != null:
		_version_check_timer.stop()
	_login_theme_active = false
	_screen_background.color = Color(0.055, 0.067, 0.09)
	_title_cycle_timer.stop()
	if _title_transition != null and _title_transition.is_running():
		_title_transition.kill()
	for index in range(_title_background_layers.size()):
		var layer := _title_background_layers[index]
		layer.stop()
		layer.stream = null
		layer.visible = false
		layer.modulate = Color.WHITE if index == _active_title_layer else Color(1.0, 1.0, 1.0, 0.0)
	_biome_caption.visible = false
	_screen_panel.custom_minimum_size = Vector2(560, 0)
	_screen_panel.add_theme_stylebox_override("panel", _base_panel_style)
	_content_margin.add_theme_constant_override("margin_left", 22)
	_content_margin.add_theme_constant_override("margin_top", 22)
	_content_margin.add_theme_constant_override("margin_right", 22)
	_content_margin.add_theme_constant_override("margin_bottom", 22)
	_content.add_theme_constant_override("separation", 14)
	_status.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	_status.add_theme_font_size_override("font_size", 16)
	_status.add_theme_color_override("font_color", MUTED_COLOR)
	for child in _content.get_children():
		if child == _status:
			_content.remove_child(_status)
		else:
			_content.remove_child(child)
			child.queue_free()
	_status.text = ""


func _finish_screen() -> void:
	_content.add_child(_status)


func _add_title(text: String) -> void:
	var label := Label.new()
	label.text = text
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", roundi(34 * LOGIN_FONT_SCALE) if _login_theme_active else 30)
	label.add_theme_color_override("font_color", TITLE_COLOR)
	if _login_theme_active:
		label.add_theme_color_override("font_outline_color", Color(0.055, 0.045, 0.035))
		label.add_theme_constant_override("outline_size", roundi(3 * LOGIN_FONT_SCALE))
	_content.add_child(label)


func _add_note(text: String) -> void:
	var label := Label.new()
	label.text = text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER if _login_theme_active else HORIZONTAL_ALIGNMENT_LEFT
	label.add_theme_font_size_override("font_size", roundi(17 * LOGIN_FONT_SCALE) if _login_theme_active else 16)
	label.add_theme_color_override("font_color", Color(0.77, 0.72, 0.64) if _login_theme_active else MUTED_COLOR)
	_content.add_child(label)


func _new_input(placeholder: String, secret := false, container: Control = null) -> LineEdit:
	var input := LineEdit.new()
	input.placeholder_text = placeholder
	input.secret = secret
	input.custom_minimum_size.y = roundi(46 * LOGIN_SCALE) if _login_theme_active else 42
	if _login_theme_active:
		input.add_theme_stylebox_override("normal", _login_style(Color(0.105, 0.11, 0.125), Color(0.27, 0.28, 0.30)))
		input.add_theme_stylebox_override("focus", _login_style(Color(0.12, 0.12, 0.13), Color(0.78, 0.58, 0.28)))
		input.add_theme_color_override("font_color", LOGIN_TEXT_COLOR)
		input.add_theme_color_override("font_placeholder_color", Color(0.61, 0.62, 0.65))
		input.add_theme_color_override("caret_color", TITLE_COLOR)
		input.add_theme_font_size_override("font_size", roundi(17 * LOGIN_FONT_SCALE))
	var target: Control = _content if container == null else container
	target.add_child(input)
	return input


func _new_spinbox(minimum: float, maximum: float, initial_value: float) -> SpinBox:
	var spinbox := SpinBox.new()
	spinbox.min_value = minimum
	spinbox.max_value = maximum
	spinbox.step = 1
	spinbox.value = initial_value
	spinbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	return spinbox


func _labeled_control(label_text: String, control: Control) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	var label := Label.new()
	label.text = label_text
	row.add_child(label)
	row.add_child(control)
	return row


func _new_button(text: String, callback: Callable, container: Control = null) -> Button:
	var button := Button.new()
	button.text = text
	button.custom_minimum_size.y = roundi(48 * LOGIN_SCALE) if _login_theme_active else 42
	if _login_theme_active:
		var primary := text == "Войти"
		button.add_theme_stylebox_override("normal", _login_style(Color(0.31, 0.22, 0.11) if primary else Color(0.14, 0.15, 0.17), Color(0.70, 0.50, 0.24) if primary else Color(0.32, 0.32, 0.34)))
		button.add_theme_stylebox_override("hover", _login_style(Color(0.43, 0.30, 0.14) if primary else Color(0.19, 0.20, 0.22), Color(0.94, 0.70, 0.34)))
		button.add_theme_stylebox_override("pressed", _login_style(Color(0.23, 0.17, 0.10) if primary else Color(0.11, 0.12, 0.14), Color(0.78, 0.58, 0.28)))
		button.add_theme_stylebox_override("focus", _login_style(Color(0.31, 0.22, 0.11) if primary else Color(0.14, 0.15, 0.17), Color(0.94, 0.76, 0.43)))
		button.add_theme_color_override("font_color", LOGIN_TEXT_COLOR)
		button.add_theme_color_override("font_hover_color", Color(1.0, 0.95, 0.82))
		button.add_theme_color_override("font_pressed_color", LOGIN_TEXT_COLOR)
		button.add_theme_font_size_override("font_size", roundi(18 * LOGIN_FONT_SCALE))
	button.pressed.connect(callback)
	var target: Control = _content if container == null else container
	target.add_child(button)
	return button


func _login_style(background: Color, border: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = background
	style.border_color = border
	style.set_border_width_all(roundi(2 * LOGIN_SCALE))
	style.set_corner_radius_all(roundi(3 * LOGIN_SCALE))
	style.content_margin_left = roundi(12 * LOGIN_SCALE)
	style.content_margin_top = roundi(8 * LOGIN_SCALE)
	style.content_margin_right = roundi(12 * LOGIN_SCALE)
	style.content_margin_bottom = roundi(8 * LOGIN_SCALE)
	return style


func _show_login() -> void:
	ApiClient.token = ""
	_connection_overlay.visible = false
	_clear_content()
	_client_version_label.visible = true
	DisplaySettings.set_settings_button_visible(true)
	_start_title_background_rotation()
	_screen_background.color = Color(0.025, 0.032, 0.045, 0.34)
	_biome_caption.visible = true
	_login_theme_active = true
	_screen_panel.custom_minimum_size = Vector2(roundi(560 * LOGIN_SCALE), 0)
	_screen_panel.add_theme_stylebox_override("panel", _login_panel_style)
	_content_margin.add_theme_constant_override("margin_left", roundi(36 * LOGIN_SCALE))
	_content_margin.add_theme_constant_override("margin_top", roundi(30 * LOGIN_SCALE))
	_content_margin.add_theme_constant_override("margin_right", roundi(36 * LOGIN_SCALE))
	_content_margin.add_theme_constant_override("margin_bottom", roundi(30 * LOGIN_SCALE))
	_content.add_theme_constant_override("separation", roundi(11 * LOGIN_SCALE))
	_add_title("Multiverse of Games")
	_server_input = _new_input("Адрес Python-сервера")
	_server_input.text = ApiClient.base_url
	_server_input.text_changed.connect(_schedule_server_version_check)
	var server_row := HBoxContainer.new()
	server_row.add_theme_constant_override("separation", roundi(6 * LOGIN_SCALE))
	_content.add_child(server_row)
	_server_version_label = Label.new()
	_server_version_label.text = "Версия сервера: проверка подключения…"
	_server_version_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_server_version_label.add_theme_font_size_override("font_size", roundi(14 * LOGIN_FONT_SCALE))
	_server_version_label.add_theme_color_override("font_color", MUTED_COLOR)
	server_row.add_child(_server_version_label)
	_new_button("Проверить подключение", _check_server_version, server_row)
	var username_row := HBoxContainer.new()
	username_row.add_theme_constant_override("separation", 0)
	_content.add_child(username_row)
	_username_input = _new_input("Имя пользователя", false, username_row)
	_username_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_username_input.text = _remembered_username if _remember_username else ""
	_remember_username_check = _new_remember_button(
		"Сохранить имя пользователя на этом устройстве",
		_remember_username
	)
	username_row.add_child(_remember_username_check)

	var password_row := HBoxContainer.new()
	password_row.add_theme_constant_override("separation", 0)
	_content.add_child(password_row)
	_password_input = _new_input("Пароль", true, password_row)
	_password_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_password_input.text = _remembered_password if _remember_password else ""
	_remember_password_check = _new_remember_button(
		"Сохранить пароль на этом устройстве",
		_remember_password
	)
	password_row.add_child(_remember_password_check)
	_remember_username_check.toggled.connect(_on_login_preference_changed.bind(_remember_username_check))
	_remember_password_check.toggled.connect(_on_login_preference_changed.bind(_remember_password_check))
	_username_input.text_changed.connect(_on_login_credential_edited)
	_password_input.text_changed.connect(_on_login_credential_edited)
	_login_button = _new_button("Войти", _login)
	_new_button("Создать аккаунт", _register)
	_status.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_status.add_theme_font_size_override("font_size", roundi(14 * LOGIN_FONT_SCALE))
	_status.add_theme_color_override("font_color", Color(0.72, 0.65, 0.54))
	_finish_screen()
	_schedule_server_version_check()


func _new_remember_button(tooltip: String, is_pressed: bool) -> Button:
	var button := Button.new()
	button.toggle_mode = true
	button.button_pressed = is_pressed
	button.text = "✓" if is_pressed else ""
	button.tooltip_text = tooltip
	var input_height := roundi(46 * LOGIN_SCALE)
	button.custom_minimum_size = Vector2(input_height, input_height)
	button.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	button.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	button.add_theme_font_size_override("font_size", roundi(11 * LOGIN_FONT_SCALE))
	button.add_theme_color_override("font_color", Color(0.91, 1.0, 0.93))
	button.add_theme_color_override("font_hover_color", Color.WHITE)
	button.add_theme_color_override("font_pressed_color", Color.WHITE)
	_update_remember_button_style(button, is_pressed)
	return button


func _update_remember_button_style(button: Button, is_pressed: bool) -> void:
	var normal := StyleBoxFlat.new()
	normal.bg_color = Color(0.10, 0.11, 0.13) if not is_pressed else Color(0.10, 0.48, 0.25)
	normal.border_color = Color(0.42, 0.43, 0.46) if not is_pressed else Color(0.30, 0.91, 0.48)
	normal.set_border_width_all(1)
	normal.set_corner_radius_all(2)
	var hover := normal.duplicate() as StyleBoxFlat
	hover.bg_color = Color(0.15, 0.16, 0.18) if not is_pressed else Color(0.14, 0.62, 0.31)
	var pressed := normal.duplicate() as StyleBoxFlat
	pressed.bg_color = Color(0.08, 0.09, 0.10) if not is_pressed else Color(0.08, 0.40, 0.21)
	button.add_theme_stylebox_override("normal", normal)
	button.add_theme_stylebox_override("hover", hover)
	button.add_theme_stylebox_override("pressed", pressed)
	button.add_theme_stylebox_override("focus", normal)


func _begin_auth(action: String) -> void:
	if not ApiClient.set_server_url(_server_input.text):
		_show_status("Укажите полный адрес сервера, например http://127.0.0.1:8765.")
		return
	_hub_url = ApiClient.base_url
	var username := _username_input.text.strip_edges()
	var password := _password_input.text
	if username.is_empty() or password.is_empty():
		_show_status("Введите имя пользователя и пароль.")
		return
	_save_login_preferences()
	if _checked_server_url != _hub_url or not _server_compatible:
		_set_login_button_state("Проверяем сервер…", true)
		_auth_after_version = action
		_check_server_version()
		return
	_send_auth_request(action)


func _send_auth_request(action: String) -> void:
	if action == "register":
		_pending_action = action
		_set_login_button_state("Создаём аккаунт…", true)
		_show_status("Создаём аккаунт…")
		ApiClient.request_json(HTTPClient.METHOD_POST, "/api/register", {
			"username": _username_input.text.strip_edges(),
			"password": _password_input.text,
		}, false)
	else:
		_pending_action = action
		_set_login_button_state("Входим…", true)
		_show_status("Выполняется вход…")
		ApiClient.request_json(HTTPClient.METHOD_POST, "/api/login", {
			"username": _username_input.text.strip_edges(),
			"password": _password_input.text,
		}, false)


func _set_login_button_state(text: String, disabled: bool) -> void:
	if _login_button != null and is_instance_valid(_login_button):
		_login_button.text = text
		_login_button.disabled = disabled


func _reset_login_button() -> void:
	_set_login_button_state("Войти", false)


func _schedule_server_version_check(_text: String = "") -> void:
	_server_compatible = false
	_checked_server_url = ""
	if _server_version_label != null:
		_server_version_label.text = "Версия сервера: проверка подключения…"
	if _version_check_timer != null:
		_version_check_timer.start()


func _check_server_version() -> void:
	if not is_instance_valid(_server_input) or not ApiClient.set_server_url(_server_input.text):
		_server_compatible = false
		_checked_server_url = ""
		if is_instance_valid(_server_version_label):
			_server_version_label.text = "Укажите полный адрес сервера."
		if not _auth_after_version.is_empty():
			_auth_after_version = ""
			_reset_login_button()
			_show_status("Не удалось проверить сервер. Проверьте адрес.")
		return
	if not _pending_action.is_empty():
		_version_check_timer.start()
		return
	_hub_url = ApiClient.base_url
	_server_compatible = false
	_checked_server_url = ""
	_server_version_label.text = "Версия сервера: проверка подключения…"
	_version_check_url = _hub_url
	_pending_action = "server_version_auth" if not _auth_after_version.is_empty() else "server_version"
	_show_status("Проверяем сервер и совместимость версий…")
	var path := "/api/version?app=client&version=%s&protocol=%d" % [
		ApiClient.CLIENT_VERSION,
		ApiClient.PROTOCOL_VERSION,
	]
	ApiClient.request_json(HTTPClient.METHOD_GET, path, {}, false)


func _handle_server_version_response(payload: Variant) -> void:
	if _version_check_url != _server_input.text.strip_edges().trim_suffix("/"):
		_schedule_server_version_check()
		return
	if not payload is Dictionary:
		_server_compatible = false
		if is_instance_valid(_server_version_label):
			_server_version_label.text = "Сервер вернул неверные данные о версии."
		_show_status("Не удалось проверить совместимость с сервером.")
		_auth_after_version = ""
		_reset_login_button()
		return
	var compatibility: Variant = payload.get("compatibility", {})
	var server_version := str(payload.get("server_version", ""))
	var protocol := int(payload.get("protocol_version", 0))
	if server_version.is_empty() or not compatibility is Dictionary \
		or not compatibility.has("compatible"):
		_server_compatible = false
		if is_instance_valid(_server_version_label):
			_server_version_label.text = "Сервер не предоставил сведения о версии."
		_show_status("Обновите сервер: версия API не поддерживается.")
		_auth_after_version = ""
		_reset_login_button()
		return
	_server_compatible = compatibility.get("compatible") == true
	_checked_server_url = _version_check_url
	if is_instance_valid(_server_version_label):
		_server_version_label.text = "Сервер %s · API %d%s" % [
			server_version,
			protocol,
			"" if _server_compatible else " · требуется обновление",
		]
	if _server_compatible:
		_show_status("Подключение работает. Версии совместимы.")
		var auth_action := _auth_after_version
		_auth_after_version = ""
		if not auth_action.is_empty():
			_send_auth_request(auth_action)
	else:
		_show_status(str(compatibility.get("reason", "Версии приложения и сервера несовместимы.")))
		_auth_after_version = ""
		_reset_login_button()


func _login() -> void:
	_begin_auth("login")


func _register() -> void:
	_begin_auth("register")


func _load_login_preferences() -> void:
	var config := ConfigFile.new()
	var error := config.load(_login_preferences_path)
	if error == ERR_FILE_NOT_FOUND:
		return
	if error != OK:
		push_error("Не удалось загрузить сохранённые данные входа: %s" % error_string(error))
		return
	_remember_username = bool(config.get_value("login", "remember_username", false))
	_remember_password = bool(config.get_value("login", "remember_password", false))
	_remembered_username = str(config.get_value("login", "username", "")) if _remember_username else ""
	_remembered_password = str(config.get_value("login", "password", "")) if _remember_password else ""
	if _remember_username_check != null and is_instance_valid(_remember_username_check):
		_remember_username_check.set_block_signals(true)
		_remember_username_check.button_pressed = _remember_username
		_remember_username_check.set_block_signals(false)
	if _remember_password_check != null and is_instance_valid(_remember_password_check):
		_remember_password_check.set_block_signals(true)
		_remember_password_check.button_pressed = _remember_password
		_remember_password_check.set_block_signals(false)
	if _username_input != null and is_instance_valid(_username_input):
		_username_input.text = _remembered_username
	if _password_input != null and is_instance_valid(_password_input):
		_password_input.text = _remembered_password


func _save_login_preferences() -> void:
	if _remember_username_check != null and is_instance_valid(_remember_username_check):
		_remember_username = _remember_username_check.button_pressed
	if _remember_password_check != null and is_instance_valid(_remember_password_check):
		_remember_password = _remember_password_check.button_pressed
	if _username_input != null and is_instance_valid(_username_input):
		_remembered_username = _username_input.text.strip_edges() if _remember_username else ""
	if _password_input != null and is_instance_valid(_password_input):
		_remembered_password = _password_input.text if _remember_password else ""

	var config := ConfigFile.new()
	config.set_value("login", "remember_username", _remember_username)
	config.set_value("login", "username", _remembered_username)
	config.set_value("login", "remember_password", _remember_password)
	config.set_value("login", "password", _remembered_password)
	var error := config.save(_login_preferences_path)
	if error != OK:
		push_error("Не удалось сохранить настройки входа: %s" % error_string(error))
		_show_status("Не удалось сохранить настройки входа.")


func _on_login_preference_changed(pressed: bool, button: Button) -> void:
	button.text = "✓" if pressed else ""
	_update_remember_button_style(button, pressed)
	_save_login_preferences()


func _on_login_credential_edited(_text: String) -> void:
	if _remember_username or _remember_password:
		_save_login_preferences()


func _show_worlds() -> void:
	_clear_content()
	_close_world_dialog()
	_close_avatar_crop()
	_screen_center.visible = false
	_lobby_root = Control.new()
	_lobby_root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_lobby_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_lobby_root)

	_lobby_root.add_child(_build_account_block())
	_lobby_root.add_child(_build_lobby_top_bar())
	_lobby_root.add_child(_build_lobby_worlds_panel())

	_lobby_chat = LOBBY_CHAT_SCRIPT.new()
	_lobby_chat.set_identity(int(GameSession.user.get("id", 0)))
	_lobby_chat.message_submitted.connect(_on_lobby_chat_message_submitted)
	_lobby_chat.player_menu_requested.connect(_on_lobby_player_menu_requested)
	_lobby_root.add_child(_lobby_chat)
	_lobby_chat.set_messages(_lobby_chat_messages)

	_lobby_context_menu = LOBBY_CONTEXT_MENU_SCRIPT.new()
	_lobby_context_menu.entry_chosen.connect(_on_lobby_menu_entry_chosen)
	_lobby_root.add_child(_lobby_context_menu)

	_render_lobby()
	_render_worlds()
	_finish_screen()
	_lobby_timer.start()


func _build_account_block() -> Control:
	var block := VBoxContainer.new()
	block.position = Vector2(LOBBY_EDGE_MARGIN, LOBBY_EDGE_MARGIN)
	block.custom_minimum_size = Vector2(LOBBY_ACCOUNT_WIDTH, 0)
	block.add_theme_constant_override("separation", 4)
	var card_row := HBoxContainer.new()
	card_row.add_theme_constant_override("separation", 8)
	block.add_child(card_row)
	_account_card = LOBBY_ACCOUNT_CARD_SCRIPT.new()
	_account_card.menu_requested.connect(_on_avatar_menu_requested)
	_account_card.set_avatar(_avatar_texture)
	card_row.add_child(_account_card)
	var info := VBoxContainer.new()
	info.add_theme_constant_override("separation", 2)
	card_row.add_child(info)
	info.add_child(_lobby_label("Уровень 0", 11, TITLE_COLOR))
	info.add_child(_lobby_label(str(GameSession.user.get("username", "Игрок")), 12, LOBBY_TEXT_COLOR))
	info.add_child(_lobby_label(_role_title(), 10, MUTED_COLOR))
	_lobby_button("Настройка аккаунта", _show_account, block, 22)
	if _is_map_moderator():
		_lobby_button("Редактор карт", _show_map_editor_menu, block, 22)
	return block


func _role_title() -> String:
	match str(GameSession.user.get("role", "user")):
		"admin":
			return "администратор"
		"moderator":
			return "модератор"
		_:
			return "игрок"


func _build_lobby_top_bar() -> Control:
	var bar := VBoxContainer.new()
	bar.anchor_right = 1.0
	bar.offset_left = LOBBY_TOP_BAR_LEFT
	bar.offset_top = LOBBY_EDGE_MARGIN
	bar.offset_right = -LOBBY_TOP_BAR_RIGHT_GAP
	bar.add_theme_constant_override("separation", 2)
	var header := HBoxContainer.new()
	header.add_theme_constant_override("separation", 6)
	bar.add_child(header)
	var title := _lobby_label("Лобби", 13, TITLE_COLOR)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(title)
	_lobby_button("Обновить миры", _request_world_list, header, 22)
	_lobby_button("Выйти", _logout, header, 22)
	_lobby_status = _lobby_label("", 10, MUTED_COLOR)
	_lobby_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	bar.add_child(_lobby_status)
	return bar


func _build_lobby_worlds_panel() -> Control:
	var panel := _lobby_card()
	_worlds_panel = panel
	panel.anchor_left = 1.0
	panel.anchor_right = 1.0
	var panel_width := minf(
		LOBBY_WORLDS_SIZE.x,
		maxf(180.0, get_viewport_rect().size.x - LOBBY_EDGE_MARGIN * 2.0),
	)
	panel.offset_left = -panel_width - LOBBY_EDGE_MARGIN
	panel.offset_right = -LOBBY_EDGE_MARGIN
	panel.offset_top = LOBBY_EDGE_MARGIN
	panel.offset_bottom = LOBBY_EDGE_MARGIN + _worlds_panel_height()
	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 6)
	panel.add_child(layout)
	var heading := _lobby_label("Игровые миры", 13, TITLE_COLOR)
	heading.custom_minimum_size.y = 20
	layout.add_child(heading)
	_worlds_scroll = ScrollContainer.new()
	_worlds_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_worlds_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	_worlds_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_worlds_scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	layout.add_child(_worlds_scroll)
	_worlds_list = VBoxContainer.new()
	_worlds_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_worlds_list.add_theme_constant_override("separation", 4)
	_worlds_scroll.add_child(_worlds_list)
	if _is_map_moderator():
		_lobby_button("Запустить новый мир", _open_world_dialog, layout, 26)
	return panel


func _worlds_panel_height() -> float:
	var footer_height := 38.0 if _is_map_moderator() else 0.0
	var content_height := 72.0 + float(_worlds.size()) * 76.0 + footer_height
	return minf(LOBBY_WORLDS_SIZE.y, maxf(170.0, content_height))


func _lobby_card() -> PanelContainer:
	var panel := PanelContainer.new()
	panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	panel.add_theme_stylebox_override("panel", _lobby_card_style())
	return panel


func _lobby_card_style() -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.085, 0.09, 0.105, 0.96)
	style.border_color = Color(0.3, 0.25, 0.18)
	style.set_border_width_all(1)
	style.set_corner_radius_all(4)
	style.set_content_margin_all(6)
	return style


func _lobby_label(text: String, font_size: int, color: Color) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	return label


func _lobby_button(text: String, callback: Callable, container: Control, height: int) -> Button:
	var button := Button.new()
	button.text = text
	button.custom_minimum_size.y = height
	button.add_theme_font_size_override("font_size", 10)
	button.pressed.connect(callback)
	container.add_child(button)
	return button


func _render_lobby() -> void:
	if _lobby_chat_visible():
		_lobby_chat.set_players(_lobby_players)


func _render_worlds() -> void:
	if _worlds_list == null or not is_instance_valid(_worlds_list):
		return
	for child in _worlds_list.get_children():
		_worlds_list.remove_child(child)
		child.queue_free()
	for world in _worlds:
		_worlds_list.add_child(_build_world_row(world))
	if is_instance_valid(_worlds_panel):
		_worlds_panel.offset_bottom = LOBBY_EDGE_MARGIN + _worlds_panel_height()


func _build_world_row(world: Dictionary) -> Control:
	var is_open := bool(world.get("is_open", false))
	var row := PanelContainer.new()
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.custom_minimum_size.x = 0.0
	row.add_theme_stylebox_override("panel", _lobby_card_style())
	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 4)
	row.add_child(layout)
	var heading := HBoxContainer.new()
	heading.add_theme_constant_override("separation", 6)
	layout.add_child(heading)
	var mode := str(world.get("mode", ""))
	var title_text := "%s · %s" % [str(world.get("name", "Мир")), str(MODE_NAMES.get(mode, mode))]
	if bool(world.get("test_only", false)):
		title_text += " · тестовый"
	var title := _lobby_label(title_text, 11, TITLE_COLOR if is_open else MUTED_COLOR)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title.custom_minimum_size.x = 0.0
	title.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	title.tooltip_text = title_text
	heading.add_child(title)
	var status := LOBBY_FORMAT.world_status_text(world)
	var status_label := _lobby_label(status, 10, _status_color(status))
	status_label.size_flags_horizontal = Control.SIZE_SHRINK_END
	heading.add_child(status_label)
	var details := _lobby_label("%s\nОнлайн: %d · %s" % [
		LOBBY_FORMAT.world_started_text(world).capitalize(),
		int(world.get("online_players", 0)),
		LOBBY_FORMAT.world_end_text(world),
	], 10, MUTED_COLOR)
	details.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	details.custom_minimum_size.x = 0.0
	details.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	layout.add_child(details)
	var actions := HBoxContainer.new()
	actions.alignment = BoxContainer.ALIGNMENT_END
	layout.add_child(actions)
	var server_url := _world_server_url(world)
	if is_open and not server_url.is_empty():
		var enter_button := _lobby_button("Войти", _select_world.bind(world), actions, 24)
		enter_button.custom_minimum_size.x = 82
	elif is_open and _can_start_world(world):
		var start_button := _lobby_button("Запустить", _start_world.bind(world), actions, 24)
		start_button.custom_minimum_size.x = 82
	return row


func _status_color(status: String) -> Color:
	if status == "работает":
		return Color(0.55, 0.9, 0.6)
	if status == "закрыт":
		return Color(0.9, 0.45, 0.4)
	return Color(0.95, 0.75, 0.4)


func _can_start_world(world: Dictionary) -> bool:
	return _is_admin() or (_is_map_moderator() and bool(world.get("test_only", false)))


func _lobby_chat_visible() -> bool:
	return _lobby_chat != null and is_instance_valid(_lobby_chat)


func _set_lobby_chat_status(text: String, is_error := true) -> void:
	if _lobby_chat_visible():
		_lobby_chat.set_status(text, is_error)


func _on_lobby_chat_message_submitted(text: String, recipient_user_id: int) -> void:
	if not _pending_action.is_empty():
		_set_lobby_chat_status("Подождите завершения текущего запроса.")
		return
	_pending_action = "lobby_chat_send"
	_set_lobby_chat_status("Отправляем сообщение…", false)
	ApiClient.set_server_url(_hub_url)
	ApiClient.token = GameSession.token
	var body := {"text": text}
	if recipient_user_id > 0:
		body["recipient_user_id"] = recipient_user_id
	ApiClient.request_json(HTTPClient.METHOD_POST, "/api/lobby/chat", body)


func _open_avatar_picker() -> void:
	if _avatar_dialog == null:
		_avatar_dialog = FileDialog.new()
		_avatar_dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
		_avatar_dialog.access = FileDialog.ACCESS_FILESYSTEM
		_avatar_dialog.title = "Фото аккаунта: PNG %d × %d px или больше" % [LOBBY_AVATAR_SIZE, LOBBY_AVATAR_SIZE]
		_avatar_dialog.filters = PackedStringArray(["*.png, *.jpg, *.jpeg, *.webp ; Изображения"])
		_avatar_dialog.file_selected.connect(_on_avatar_file_selected)
		add_child(_avatar_dialog)
	_avatar_dialog.popup_centered_ratio(0.6)


func _on_avatar_file_selected(path: String) -> void:
	if _request_is_pending():
		return
	var image := Image.load_from_file(path)
	if image == null or image.is_empty():
		_show_status("Не удалось открыть изображение. Выберите PNG, JPG или WebP.")
		return
	image.convert(Image.FORMAT_RGBA8)
	var size_message := _avatar_size_message(image.get_width(), image.get_height())
	if not size_message.is_empty():
		_show_status(size_message)
		return
	if image.get_width() == LOBBY_AVATAR_SIZE and image.get_height() == LOBBY_AVATAR_SIZE:
		_upload_avatar(image)
		return
	_open_avatar_crop(image)


# Пустая строка значит, что размер подходит. Большее фото обрабатывается в диалоге обрезки.
func _avatar_size_message(width: int, height: int) -> String:
	if width < LOBBY_AVATAR_SIZE or height < LOBBY_AVATAR_SIZE:
		return "Фото %d × %d px слишком маленькое. Нужно не меньше %d × %d px." % [
			width, height, LOBBY_AVATAR_SIZE, LOBBY_AVATAR_SIZE,
		]
	return ""


func _open_avatar_crop(image: Image) -> void:
	_close_avatar_crop()
	_avatar_crop_overlay = ColorRect.new()
	_avatar_crop_overlay.color = Color(0.02, 0.025, 0.035, 0.78)
	_avatar_crop_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_avatar_crop_overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	_avatar_crop_overlay.z_index = 60
	add_child(_avatar_crop_overlay)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_avatar_crop_overlay.add_child(center)
	_avatar_crop_dialog = AVATAR_CROP_DIALOG_SCRIPT.new()
	_avatar_crop_dialog.setup(image)
	_avatar_crop_dialog.confirmed.connect(_on_avatar_crop_confirmed)
	_avatar_crop_dialog.cancelled.connect(_close_avatar_crop)
	center.add_child(_avatar_crop_dialog)


func _on_avatar_crop_confirmed(result: Image) -> void:
	_close_avatar_crop()
	_upload_avatar(result)


func _close_avatar_crop() -> void:
	if _avatar_crop_overlay != null and is_instance_valid(_avatar_crop_overlay):
		_avatar_crop_overlay.queue_free()
	_avatar_crop_overlay = null
	_avatar_crop_dialog = null


func _upload_avatar(image: Image) -> void:
	if _request_is_pending():
		return
	_pending_avatar_image = image
	_pending_action = "avatar_save"
	_show_status("Сохраняем фото аккаунта…")
	ApiClient.set_server_url(_hub_url)
	ApiClient.token = GameSession.token
	ApiClient.request_json(HTTPClient.METHOD_POST, "/api/account/avatar", {
		"png_base64": Marshalls.raw_to_base64(image.save_png_to_buffer()),
	})


func _on_avatar_menu_requested(global_point: Vector2) -> void:
	_lobby_context_menu.open_at(global_point, [
		{"id": "avatar_info", "text": "Можно поставить PNG %d × %d px" % [LOBBY_AVATAR_SIZE, LOBBY_AVATAR_SIZE], "label": true},
		{"id": "avatar_change", "text": "Сменить аватар"},
	])


func _on_lobby_player_menu_requested(player: Dictionary, global_point: Vector2) -> void:
	var is_self := int(player.get("user_id", 0)) == int(GameSession.user.get("id", 0))
	_lobby_context_menu.open_at(global_point, [
		{"id": "whisper", "text": "Отправить личное сообщение", "disabled": is_self},
		{"id": "invite", "text": "Пригласить в команду", "disabled": true},
		{"id": "trade", "text": "Предложить обмен", "disabled": true},
	], {"username": str(player.get("username", ""))})


func _on_lobby_menu_entry_chosen(entry_id: String, payload: Dictionary) -> void:
	if entry_id == "whisper" and _lobby_chat_visible():
		_lobby_chat.start_private_message(str(payload.get("username", "")))
	elif entry_id == "avatar_change":
		_open_avatar_picker()


func _request_avatar() -> void:
	ApiClient.set_server_url(_hub_url)
	ApiClient.token = GameSession.token
	_pending_action = "avatar_load"
	ApiClient.request_json(HTTPClient.METHOD_GET, "/api/account/avatar")


func _apply_avatar(texture: Texture2D) -> void:
	_avatar_texture = texture
	if _account_card != null and is_instance_valid(_account_card):
		_account_card.set_avatar(texture)


func _decode_avatar(encoded: String) -> Image:
	var image := Image.new()
	if image.load_png_from_buffer(Marshalls.base64_to_raw(encoded)) != OK:
		return null
	return image


func _poll_lobby_extras() -> void:
	if not _avatar_loaded:
		_request_avatar()
	else:
		_poll_worlds_quiet()


func _poll_worlds_quiet() -> void:
	if not _pending_action.is_empty() or not GameSession.world_token.is_empty():
		return
	ApiClient.set_server_url(_hub_url)
	ApiClient.token = GameSession.token
	_pending_action = "worlds_quiet"
	ApiClient.request_json(HTTPClient.METHOD_GET, "/api/worlds")


func _open_world_dialog() -> void:
	if _request_is_pending():
		_show_status("Подождите завершения текущего запроса.")
		return
	_close_world_dialog()
	_lobby_timer.stop()
	_world_dialog_overlay = ColorRect.new()
	_world_dialog_overlay.color = Color(0.02, 0.025, 0.035, 0.78)
	_world_dialog_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_world_dialog_overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	_world_dialog_overlay.z_index = 50
	add_child(_world_dialog_overlay)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_world_dialog_overlay.add_child(center)
	_world_dialog = WORLD_CREATE_DIALOG_SCRIPT.new()
	center.add_child(_world_dialog)
	_world_dialog.setup(_is_admin(), MODE_NAMES)
	_world_dialog.mode_selected.connect(_request_dialog_maps)
	_world_dialog.launch_requested.connect(_launch_world_from_dialog)
	_world_dialog.close_requested.connect(_on_world_dialog_close_requested)
	_request_dialog_maps(_world_dialog.current_mode())


func _request_dialog_maps(mode: String) -> void:
	if _request_is_pending():
		_set_dialog_status("Подождите завершения текущего запроса и выберите режим ещё раз.")
		return
	_pending_action = "world_dialog_maps"
	ApiClient.set_server_url(_hub_url)
	ApiClient.token = GameSession.token
	ApiClient.request_json(HTTPClient.METHOD_GET, "/api/map/saved?mode=" + mode.uri_encode())


func _launch_world_from_dialog(saved_id: int, world_name: String, test: bool) -> void:
	if _request_is_pending():
		_set_dialog_status("Подождите завершения текущего запроса.")
		return
	_set_dialog_busy(true)
	_set_dialog_status("Создаём мир…", false)
	_pending_action = "world_dialog_create"
	ApiClient.set_server_url(_hub_url)
	ApiClient.token = GameSession.token
	ApiClient.request_json(HTTPClient.METHOD_POST, "/api/worlds/create", {
		"saved_id": saved_id,
		"name": world_name,
		"test": test,
	})


func _set_dialog_status(text: String, is_error := true) -> void:
	if _world_dialog != null and is_instance_valid(_world_dialog):
		_world_dialog.set_status(text, is_error)


func _set_dialog_busy(busy: bool) -> void:
	if _world_dialog != null and is_instance_valid(_world_dialog):
		_world_dialog.set_busy(busy)


func _on_world_dialog_close_requested() -> void:
	_close_world_dialog()
	if _lobby_chat_visible():
		_lobby_timer.start()


func _close_world_dialog() -> void:
	if _world_dialog_overlay != null and is_instance_valid(_world_dialog_overlay):
		_world_dialog_overlay.queue_free()
	_world_dialog_overlay = null
	_world_dialog = null
	_dialog_world_id = 0


func _world_server_url(world: Dictionary) -> String:
	var value: Variant = world.get("server_url", "")
	return str(value).strip_edges() if value is String else ""


func _is_admin() -> bool:
	return str(GameSession.user.get("role", "")) == "admin"


func _is_map_moderator() -> bool:
	var role := str(GameSession.user.get("role", ""))
	return role == "moderator" or role == "admin"


func _show_map_editor_menu() -> void:
	_clear_content()
	_add_title("Редактор карт")
	_add_note("Выберите, начать новую карту или продолжить работу с сохранённой.")
	_new_button("Создать новую карту", _show_new_map_setup)
	_new_button("Загрузить карту для редактирования", _load_editor_saved_maps)
	_new_button("Назад в лобби", _show_worlds)
	_finish_screen()


func _show_new_map_setup() -> void:
	_clear_content()
	_add_title("Новая карта")
	_new_map_name_input = _new_input("Название карты")
	var size_row := HBoxContainer.new()
	size_row.add_theme_constant_override("separation", 10)
	_content.add_child(size_row)
	_new_map_width = _new_spinbox(16, 1600, 64)
	_new_map_height = _new_spinbox(16, 1600, 64)
	size_row.add_child(_labeled_control("Ширина (клетки)", _new_map_width))
	size_row.add_child(_labeled_control("Высота (клетки)", _new_map_height))
	var tile_row := HBoxContainer.new()
	tile_row.add_theme_constant_override("separation", 10)
	_content.add_child(tile_row)
	var tile_label := Label.new()
	tile_label.text = "Шаг тайлов"
	tile_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	tile_row.add_child(tile_label)
	_new_map_tile_size = OptionButton.new()
	_new_map_tile_size.add_item("16×16")
	_new_map_tile_size.set_item_metadata(0, 16)
	_new_map_tile_size.add_item("32×32")
	_new_map_tile_size.set_item_metadata(1, 32)
	_new_map_tile_size.set_item_disabled(1, true)
	_new_map_tile_size.select(0)
	tile_row.add_child(_new_map_tile_size)
	var mode_row := HBoxContainer.new()
	mode_row.add_theme_constant_override("separation", 10)
	_content.add_child(mode_row)
	var mode_label := Label.new()
	mode_label.text = "Режим игры"
	mode_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	mode_row.add_child(mode_label)
	_new_map_mode = OptionButton.new()
	for mode_key in ["front_line", "economy", "deck"]:
		var mode_info := WorldModeRegistry.describe(mode_key)
		_new_map_mode.add_item(str(mode_info.get("name", mode_key)))
		_new_map_mode.set_item_metadata(_new_map_mode.item_count - 1, mode_key)
	_new_map_mode.select(0)
	_new_map_mode.item_selected.connect(_update_new_map_mode_note)
	mode_row.add_child(_new_map_mode)
	_new_map_mode_note = Label.new()
	_new_map_mode_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_content.add_child(_new_map_mode_note)
	_update_new_map_mode_note(_new_map_mode.selected)
	_new_button("Создать карту", _create_new_map)
	_new_button("Назад", _show_map_editor_menu)
	_finish_screen()


func _update_new_map_mode_note(selected_index: int) -> void:
	if _new_map_mode_note == null or _new_map_mode == null:
		return
	var mode := str(_new_map_mode.get_item_metadata(selected_index))
	match mode:
		"deck":
			_new_map_mode_note.text = "Карты Deck сохраняются через сервер режима; создание и сохранение Deck-карт из лобби пока не подключено."
		"front_line":
			_new_map_mode_note.text = "Карта коридора сохранится для Front Line. Настройка волн и игровой режим будут добавлены отдельно."
		_:
			_new_map_mode_note.text = "Режим сохранится вместе с картой. Настройки инструментов редактора для режимов пока общие."


func _create_new_map() -> void:
	var map_name := _new_map_name_input.text.strip_edges()
	if map_name.is_empty():
		_show_status("Введите название карты.")
		return
	GameSession.map_editor_setup = {
		"name": map_name,
		"map_w": int(_new_map_width.value),
		"map_h": int(_new_map_height.value),
		"tile_size": int(_new_map_tile_size.get_item_metadata(_new_map_tile_size.selected)),
		"mode": str(_new_map_mode.get_item_metadata(_new_map_mode.selected)),
	}
	_open_map_editor()


func _load_editor_saved_maps() -> void:
	if _request_is_pending():
		return
	if GameSession.token.is_empty() or not ApiClient.set_server_url(_hub_url):
		_show_status("Не удалось подключиться к центральному серверу для загрузки карт.")
		return
	_lobby_timer.stop()
	ApiClient.token = GameSession.token
	_pending_action = "editor_saved_maps"
	_show_status("Загружаем сохранённые карты…")
	ApiClient.request_json(HTTPClient.METHOD_GET, "/api/map/saved")


func _show_editor_saved_maps() -> void:
	_clear_content()
	_add_title("Загрузить карту")
	_add_note("Выберите сохранённую карту для редактирования.")
	if _saved_maps.is_empty():
		_add_note("Сохранённых карт пока нет.")
	else:
		for saved_map in _saved_maps:
			var map_id := int(saved_map.get("id", 0))
			if map_id <= 0:
				continue
			var map_name := str(saved_map.get("name", "Без названия"))
			var dimensions := "%s×%s" % [
				str(saved_map.get("map_w", "?")),
				str(saved_map.get("map_h", "?")),
			]
			var mode_key := str(saved_map.get("mode", "front_line"))
			var mode_name := str(WorldModeRegistry.describe(mode_key).get("name", mode_key))
			_new_button(
				"%s · %s · %s" % [map_name, mode_name, dimensions],
				_open_saved_map_for_editing.bind(map_id, mode_key),
			)
	_new_button("Назад", _show_map_editor_menu)
	_finish_screen()


func _open_saved_map_for_editing(saved_id: int, editor_mode: String) -> void:
	GameSession.map_editor_setup = {
		"saved_id": saved_id,
		"mode": editor_mode,
	}
	_open_map_editor(saved_id, editor_mode)


func _open_map_editor(saved_id: int = 0, editor_mode: String = "") -> void:
	if _request_is_pending():
		return
	if not _is_map_moderator():
		_show_status("Редактор карт доступен только модераторам и администраторам.")
		return
	if GameSession.world_token.is_empty():
		if GameSession.token.is_empty() or not ApiClient.set_server_url(_hub_url):
			_show_status("Войдите в аккаунт, чтобы открыть редактор карт.")
			return
		ApiClient.token = GameSession.token
		_lobby_timer.stop()
	else:
		var world_url := str(GameSession.world.get("server_url", "")).strip_edges()
		if not ApiClient.set_server_url(world_url):
			_show_status("У выбранного мира неверный адрес сервера.")
			return
		ApiClient.token = GameSession.world_token
	SCENE_TRANSITION.run(get_tree(), _change_to_map_editor)


func _change_to_map_editor() -> void:
	var error := get_tree().change_scene_to_file("res://scenes/map_editor.tscn")
	if error != OK:
		GameSession.map_editor_setup.clear()
		_show_status("Не удалось открыть редактор карт: %s" % error_string(error))


func _start_world(world: Dictionary) -> void:
	if _request_is_pending():
		return
	_lobby_timer.stop()
	_pending_action = "world_start"
	_show_status("Запускаем сервер мира…")
	ApiClient.set_server_url(_hub_url)
	ApiClient.token = GameSession.token
	ApiClient.request_json(HTTPClient.METHOD_POST, "/api/worlds/start", {
		"world_id": int(world.get("id", 0)),
	})


func _poll_lobby() -> void:
	if not _pending_action.is_empty() or not GameSession.world_token.is_empty() or not _exit_intent.is_empty():
		return
	ApiClient.set_server_url(_hub_url)
	ApiClient.token = GameSession.token
	_pending_action = "lobby"
	ApiClient.request_json(HTTPClient.METHOD_GET, "/api/lobby")


func _poll_lobby_chat() -> void:
	if not GameSession.world_token.is_empty() or not _exit_intent.is_empty():
		return
	ApiClient.set_server_url(_hub_url)
	ApiClient.token = GameSession.token
	_pending_action = "lobby_chat"
	ApiClient.request_json(HTTPClient.METHOD_GET, "/api/lobby/chat")


func _show_account() -> void:
	if _request_is_pending():
		return
	_lobby_timer.stop()
	_clear_content()
	_add_title("Управление аккаунтом")
	_add_note("Имя: %s · роль: %s" % [
		str(GameSession.user.get("username", "Игрок")),
		str(GameSession.user.get("role", "user")),
	])
	var game_nickname := str(GameSession.user.get("game_nickname", ""))
	_add_note("Игровой псевдоним: %s" % (game_nickname if not game_nickname.is_empty() else "не задан"))
	_account_game_nickname = _new_input("Игровой псевдоним (2–24 символа)")
	_account_game_nickname.text = game_nickname
	_new_button("Сохранить игровой псевдоним", _change_game_nickname)
	_add_note("Смена пароля завершит остальные активные сессии аккаунта.")
	_account_current_password = _new_input("Текущий пароль", true)
	_account_new_password = _new_input("Новый пароль (6–128 символов)", true)
	_account_confirm_password = _new_input("Повторите новый пароль", true)
	_new_button("Сменить пароль", _change_account_password)
	_new_button("Назад в лобби", _request_world_list)
	_finish_screen()


func _change_account_password() -> void:
	if _request_is_pending():
		return
	if _account_current_password.text.is_empty() or _account_new_password.text.is_empty():
		_show_status("Введите текущий и новый пароль.")
		return
	if _account_new_password.text != _account_confirm_password.text:
		_show_status("Новые пароли не совпадают.")
		return
	var new_password_length := _account_new_password.text.length()
	if new_password_length < 6 or new_password_length > 128:
		_show_status("Новый пароль должен содержать 6–128 символов.")
		return
	_pending_action = "account_password"
	_show_status("Меняем пароль…")
	ApiClient.set_server_url(_hub_url)
	ApiClient.token = GameSession.token
	ApiClient.request_json(HTTPClient.METHOD_POST, "/api/account/password", {
		"current_password": _account_current_password.text,
		"new_password": _account_new_password.text,
	})


func _change_game_nickname() -> void:
	if _request_is_pending():
		return
	var nickname := _account_game_nickname.text.strip_edges()
	if nickname.length() < 2 or nickname.length() > 24:
		_show_status("Игровой псевдоним должен содержать 2–24 символа.")
		return
	_pending_action = "account_game_nickname"
	_show_status("Сохраняем игровой псевдоним…")
	ApiClient.set_server_url(_hub_url)
	ApiClient.token = GameSession.token
	ApiClient.request_json(HTTPClient.METHOD_POST, "/api/account/game-nickname", {
		"game_nickname": nickname,
	})


func _select_world(world: Dictionary) -> void:
	if _request_is_pending():
		return
	var world_url := _world_server_url(world)
	if int(world.get("id", 0)) <= 0 or world_url.is_empty():
		_show_status("У мира не настроен сервер. Попробуйте позже.")
		return
	_lobby_timer.stop()
	_current_world = world
	GameSession.select_world(world)
	if not ApiClient.set_server_url(_hub_url):
		_show_status("Не удалось подключиться к центральному серверу.")
		return
	ApiClient.token = GameSession.token
	_pending_action = "connect_world"
	_show_status("Подключаемся к миру…")
	ApiClient.request_json(
		HTTPClient.METHOD_POST,
		"/api/worlds/%d/connect" % int(world.get("id", 0)),
	)


func _use_world_session(payload: Dictionary) -> void:
	var world_url := str(_current_world.get("server_url", "")).strip_edges()
	var world_token := str(payload.get("token", ""))
	if world_token.is_empty():
		_show_status("Центральный сервер не выдал сессию игрового мира.")
		return
	if not ApiClient.set_server_url(world_url):
		_show_status("У выбранного мира неверный адрес сервера.")
		return
	GameSession.world_token = world_token
	ApiClient.token = world_token
	_load_characters()


func _show_characters(characters: Array) -> void:
	_lobby_timer.stop()
	_clear_content()
	_selected_character.clear()
	var world_title := str(_current_world.get("name", "Мир"))
	var mode := str(_current_world.get("mode", ""))
	var mode_info := WorldModeRegistry.describe(mode)
	if not mode.is_empty():
		world_title += " · " + str(mode_info["name"])
	_add_title(world_title)
	_add_note("Выберите персонажа или создайте нового. Правила выбранного режима рассчитывает сервер.")
	if _is_map_moderator():
		_new_button("Открыть редактор карт", _open_map_editor)
	var module_ready := bool(mode_info.get("module_ready", false))
	if not module_ready:
		_add_note("Клиентский модуль этого режима ещё не подключён. Выбор персонажа станет доступен после его добавления.")
	for character in characters:
		var character_name := str(character.get("name", "Персонаж"))
		var profession := str(character.get("profession_type", ""))
		var summary := "%s · %s · ур. %s · HP %s/%s" % [
			character_name,
			profession,
			str(character.get("level", 1)),
			str(character.get("hp", "—")),
			str(character.get("max_hp", "—")),
		]
		_new_button(summary, _preview_character.bind(character))
	_character_details = Label.new()
	_character_details.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_character_details.custom_minimum_size.y = 80
	_character_details.add_theme_color_override("font_color", MUTED_COLOR)
	_content.add_child(_character_details)
	var enter_button := _new_button("Продолжить выбранным персонажем", _enter_selected_character)
	enter_button.disabled = not module_ready
	_new_button("Удалить выбранного персонажа", _delete_selected_character)
	_delete_password_input = _new_input("Пароль для подтверждения удаления", true)
	_delete_password_input.visible = false
	if characters.is_empty():
		_add_note("В этом аккаунте пока нет персонажей.")
	_new_button("Создать персонажа", _show_create_character)
	_new_button("Назад к мирам", _load_worlds)
	_finish_screen()


# Карточки классов занимают 960x500 базовых единиц (масштаб 0.5), а список персонажей не умещается с ними
# на высоту 720 базовых единиц, поэтому создание идёт на отдельном экране панели, как CreateCharacterScene в Python.
func _show_create_character() -> void:
	_clear_content()
	_screen_panel.custom_minimum_size = Vector2(1040, 0)
	_create_view = preload("res://scripts/create_character_view.gd").new()
	_create_view.configure(str(_current_world.get("mode", "")))
	_create_view.set_card_scale(0.5)
	_create_view.create_requested.connect(_create_character)
	_content.add_child(_create_view)
	_new_button("Назад к персонажам", _load_characters)
	_finish_screen()


func _preview_character(character: Dictionary) -> void:
	_selected_character = character.duplicate(true)
	var stats: Variant = character.get("stats", {})
	var details := "%s · уровень %s · опыт %s\nЗдоровье: %s/%s · мана: %s/%s\nСила %s · Ловкость %s · Интуиция %s · Выносливость %s" % [
		str(character.get("profession_type", "Персонаж")),
		str(character.get("level", 1)),
		str(character.get("xp", 0)),
		str(character.get("hp", "—")),
		str(character.get("max_hp", "—")),
		str(character.get("mp", "—")),
		str(character.get("max_mp", "—")),
		str(stats.get("strength", "—")) if stats is Dictionary else "—",
		str(stats.get("agility", "—")) if stats is Dictionary else "—",
		str(stats.get("intuition", "—")) if stats is Dictionary else "—",
		str(stats.get("endurance", "—")) if stats is Dictionary else "—",
	]
	_character_details.text = details
	_delete_password_input.visible = true


func _enter_selected_character() -> void:
	if _selected_character.is_empty():
		_show_status("Сначала выберите персонажа.")
		return
	_select_character(_selected_character)


func _delete_selected_character() -> void:
	if _selected_character.is_empty():
		_show_status("Сначала выберите персонажа.")
		return
	var password := _delete_password_input.text
	if password.is_empty():
		_show_status("Введите пароль для подтверждения удаления.")
		return
	_pending_action = "delete_character"
	_show_status("Удаляем персонажа…")
	ApiClient.request_json(
		HTTPClient.METHOD_POST,
		"/api/characters/%d/delete" % int(_selected_character.get("id", 0)),
		{"password": password},
	)


func _select_character(character: Dictionary) -> void:
	var mode_info := WorldModeRegistry.describe(str(_current_world.get("mode", "")))
	var scene_path := str(mode_info.get("scene_path", ""))
	if scene_path.is_empty():
		_show_status("Клиентский модуль этого игрового режима ещё не подключён.")
		return
	_active_character = character.duplicate(true)
	GameSession.select_character(character)
	ConnectionGuard.start(ApiClient.base_url, ApiClient.token, int(character.get("id", 0)))
	if not ResourceLoader.exists(scene_path):
		ConnectionGuard.stop()
		_show_status("Не удалось открыть сцену игрового режима: %s" % error_string(ERR_FILE_NOT_FOUND))
		return
	SCENE_TRANSITION.run(get_tree(), func() -> void: get_tree().change_scene_to_file(scene_path))


func _create_character() -> void:
	var body: Dictionary = _create_view.request_body()
	if str(body["name"]).is_empty():
		_show_status("Введите имя персонажа.")
		return
	_pending_action = "create_character"
	_show_status("Создаём персонажа…")
	ApiClient.request_json(HTTPClient.METHOD_POST, "/api/characters", body)


func _load_worlds() -> void:
	if not GameSession.world_token.is_empty():
		ApiClient.set_server_url(str(_current_world.get("server_url", "")))
		ApiClient.token = GameSession.world_token
		_pending_action = "leave_world_to_lobby"
		_show_status("Завершаем сессию мира…")
		ApiClient.request_json(HTTPClient.METHOD_POST, "/api/sessions/disconnect")
		return
	_request_world_list()


func _request_world_list() -> void:
	if _request_is_pending():
		return
	_lobby_timer.stop()
	ApiClient.set_server_url(_hub_url)
	ApiClient.token = GameSession.token
	_pending_action = "worlds"
	_show_status("Загружаем миры…")
	ApiClient.request_json(HTTPClient.METHOD_GET, "/api/worlds")


func _load_characters() -> void:
	_pending_action = "characters"
	_show_status("Загружаем персонажей…")
	ApiClient.request_json(HTTPClient.METHOD_GET, "/api/characters")


func _logout() -> void:
	if _request_is_pending():
		return
	if ApiClient.token.is_empty():
		_finish_logout()
		return
	var action := "logout_world" if not GameSession.world_token.is_empty() else "logout_central"
	if action == "logout_central":
		ApiClient.set_server_url(_hub_url)
		ApiClient.token = GameSession.token
	_pending_action = action
	_show_status("Завершаем сессию на сервере…")
	ApiClient.request_json(HTTPClient.METHOD_POST, "/api/sessions/disconnect")


func _finish_logout() -> void:
	ConnectionGuard.stop()
	_active_character.clear()
	ApiClient.token = ""
	ApiClient.set_server_url(_hub_url)
	GameSession.clear()
	_worlds.clear()
	_current_world.clear()
	_lobby_players.clear()
	_lobby_chat_messages.clear()
	_avatar_loaded = false
	_avatar_texture = null
	_close_world_dialog()
	# Поля входа не очищаем: clear() шлёт text_changed и стёр бы сохранённый пароль, а _show_login заполнит их из настроек.
	_show_login()


func _process(_delta: float) -> void:
	_process_exit_queue()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_ESCAPE and _exit_menu_allowed():
		_exit_menu.open()
		get_viewport().set_input_as_handled()


func _exit_menu_allowed() -> bool:
	if GameSession.token.is_empty() or _connection_overlay.visible or _exit_menu.blocks_input():
		return false
	if get_viewport().gui_get_focus_owner() is LineEdit:
		return false
	for overlay in [_world_dialog_overlay, _avatar_crop_overlay, _avatar_dialog, _lobby_context_menu]:
		if overlay != null and is_instance_valid(overlay) and overlay.visible:
			return false
	return true


func _build_exit_menu() -> void:
	_exit_menu = EXIT_MENU_SCRIPT.new()
	_exit_menu.lobby_requested.connect(_on_exit_lobby_requested)
	_exit_menu.quit_requested.connect(_on_exit_quit_requested)
	_exit_menu.quit_ready.connect(_on_exit_quit_ready)
	add_child(_exit_menu)
	get_tree().root.close_requested.connect(_on_close_requested)
	get_tree().set_auto_accept_quit(false)


func _on_close_requested() -> void:
	if GameSession.token.is_empty() or _connection_overlay.visible:
		get_tree().quit()
		return
	if _exit_intent.is_empty() and not _exit_menu.is_quitting():
		_exit_menu.open()


# В лобби аккаунт остаётся в системе: «Выйти в лобби» только обновляет список миров.
func _on_exit_lobby_requested() -> void:
	_exit_menu.close()
	_load_worlds()


func _on_exit_quit_requested() -> void:
	if _server_unreachable:
		get_tree().quit()
		return
	if not _exit_intent.is_empty():
		return
	_exit_intent = "quit"
	_exit_menu.begin_quit()
	_exit_queued = true
	_process_exit_queue()


func _on_exit_quit_ready() -> void:
	ConnectionGuard.stop()
	get_tree().quit()


func _process_exit_queue() -> void:
	if not _exit_queued or not _pending_action.is_empty():
		return
	_exit_queued = false
	ApiClient.set_server_url(_hub_url)
	ApiClient.token = GameSession.token
	_pending_action = "exit_disconnect"
	ApiClient.request_json(HTTPClient.METHOD_POST, "/api/sessions/disconnect")


func _on_exit_request_completed(success: bool, payload: Variant) -> void:
	if not success:
		_exit_intent = ""
		_server_unreachable = true
		_exit_menu.open("Сервер недоступен: %s. Нажмите «Покинуть игру», чтобы закрыть клиент" % str(payload))
		return
	ConnectionGuard.stop()
	_exit_menu.mark_disconnected()


func _show_status(message: String) -> void:
	_status.text = message
	if _lobby_status != null and is_instance_valid(_lobby_status):
		_lobby_status.text = message


func _request_is_pending() -> bool:
	if _pending_action.is_empty():
		return false
	_show_status("Подождите завершения текущего запроса.")
	return true


func _on_connection_lost(seconds_remaining: int) -> void:
	_connection_overlay.visible = true
	_connection_message.text = "Связь с сервером потеряна. Клиент пытается переподключиться и синхронизировать персонажа."
	_connection_counter.text = "%d сек." % seconds_remaining


func _on_countdown_updated(seconds_remaining: int) -> void:
	if _connection_overlay.visible:
		_connection_counter.text = "%d сек." % seconds_remaining


func _on_connection_restored(character: Dictionary) -> void:
	_active_character = character.duplicate(true)
	_connection_overlay.visible = false
	_show_status("Соединение восстановлено. Состояние персонажа обновлено с сервера.")


func _on_client_outdated() -> void:
	_connection_overlay.visible = true
	_connection_message.text = "Сервер обновлён, эта версия клиента устарела. Закройте клиент и запустите актуальную версию."
	_connection_counter.text = ""
	_reload_button.visible = true


func _on_session_invalid(message: String) -> void:
	_finish_logout()
	_show_status(message)


func _on_connection_expired() -> void:
	get_tree().quit()


func _close_for_reload() -> void:
	get_tree().quit()


func _on_api_completed(success: bool, payload: Variant) -> void:
	var action := _pending_action
	_pending_action = ""
	if action == "exit_disconnect":
		_on_exit_request_completed(success, payload)
		return
	if not success:
		if action == "server_version" or action == "server_version_auth":
			if _version_check_url != _server_input.text.strip_edges().trim_suffix("/"):
				_schedule_server_version_check()
				return
			_server_compatible = false
			_checked_server_url = ""
			if is_instance_valid(_server_version_label):
				_server_version_label.text = "Сервер недоступен или не поддерживает проверку версии."
			_auth_after_version = ""
		if action == "login" or action == "register" or action == "server_version_auth":
			_reset_login_button()
		_show_status(str(payload))
		if action == "lobby" or action == "lobby_chat" or action == "worlds_quiet" or action == "avatar_load":
			if _lobby_timer != null and not _lobby_timer.is_stopped():
				_lobby_timer.start()
		if action == "lobby_chat_send":
			_set_lobby_chat_status(str(payload))
		if action.begins_with("world_dialog"):
			_set_dialog_status(str(payload))
			_set_dialog_busy(false)
		return

	if action == "server_version" or action == "server_version_auth":
		_handle_server_version_response(payload)
		return

	match action:
		"register":
			_pending_action = "login"
			_set_login_button_state("Входим…", true)
			_show_status("Аккаунт создан. Выполняем вход…")
			ApiClient.request_json(HTTPClient.METHOD_POST, "/api/login", {
				"username": _username_input.text.strip_edges(),
				"password": _password_input.text,
			}, false)
		"login":
			if not payload is Dictionary or not payload.has("token"):
				_reset_login_button()
				_show_status("Сервер не вернул токен входа.")
				return
			ApiClient.token = str(payload["token"])
			GameSession.authenticate(ApiClient.base_url, ApiClient.token, payload.get("user", {}))
			_show_worlds()
			_load_worlds()
		"worlds", "worlds_quiet":
			_worlds.clear()
			if payload is Dictionary and payload.get("worlds", []) is Array:
				for world in payload["worlds"]:
					if world is Dictionary:
						_worlds.append(world)
			if _lobby_chat_visible() and _worlds_list != null and is_instance_valid(_worlds_list):
				_render_worlds()
				if action == "worlds":
					_lobby_timer.start()
					_poll_lobby()
			elif action == "worlds":
				_show_worlds()
				_poll_lobby()
		"lobby":
			_lobby_players.clear()
			if payload is Dictionary and payload.get("players", []) is Array:
				for player in payload["players"]:
					if player is Dictionary:
						_lobby_players.append(player)
			_render_lobby()
			_poll_lobby_chat()
		"lobby_chat":
			_lobby_chat_messages.clear()
			if payload is Dictionary and payload.get("messages", []) is Array:
				for message in payload["messages"]:
					if message is Dictionary:
						_lobby_chat_messages.append(message)
			if _lobby_chat_visible():
				_lobby_chat.set_messages(_lobby_chat_messages)
			_poll_lobby_extras()
		"lobby_chat_send":
			if _lobby_chat_visible():
				_lobby_chat.clear_input()
				_lobby_chat.set_status("")
			_poll_lobby_chat()
		"avatar_load":
			_avatar_loaded = true
			var encoded: Variant = payload.get("png_base64") if payload is Dictionary else null
			if encoded is String and not str(encoded).is_empty():
				var image := _decode_avatar(str(encoded))
				if image != null:
					_apply_avatar(ImageTexture.create_from_image(image))
			_poll_worlds_quiet()
		"avatar_save":
			_avatar_loaded = true
			if _pending_avatar_image != null:
				_apply_avatar(ImageTexture.create_from_image(_pending_avatar_image))
			_pending_avatar_image = null
			_show_status("Фото аккаунта сохранено.")
		"world_dialog_maps":
			var maps: Array = []
			if payload is Dictionary and payload.get("saved_maps", []) is Array:
				for saved_map in payload["saved_maps"]:
					if saved_map is Dictionary:
						maps.append(saved_map)
			if _world_dialog != null and is_instance_valid(_world_dialog):
				_world_dialog.show_maps(maps)
		"world_dialog_create":
			_dialog_world_id = int(payload.get("world_id", 0)) if payload is Dictionary else 0
			if _dialog_world_id <= 0:
				_set_dialog_status("Сервер не вернул созданный мир.")
				_set_dialog_busy(false)
				return
			_pending_action = "world_dialog_start"
			_set_dialog_status("Запускаем сервер мира…", false)
			ApiClient.request_json(HTTPClient.METHOD_POST, "/api/worlds/start", {"world_id": _dialog_world_id})
		"world_dialog_start":
			_close_world_dialog()
			_show_status("Мир запускается. Список миров обновляется…")
			_request_world_list()
		"account_password":
			if payload is Dictionary and payload.get("user", {}) is Dictionary:
				GameSession.user = payload["user"].duplicate(true)
			_show_account()
			_show_status("Пароль изменён. Остальные активные сессии завершены.")
		"account_game_nickname":
			if not payload is Dictionary or not payload.get("user", {}) is Dictionary:
				_show_status("Сервер вернул некорректный игровой псевдоним.")
				return
			GameSession.user = payload["user"].duplicate(true)
			_show_account()
			_show_status("Игровой псевдоним сохранён. Он будет отображаться над героем в Front Line.")
		"connect_world":
			if not payload is Dictionary:
				_show_status("Центральный сервер вернул неверную сессию мира.")
				return
			_use_world_session(payload)
		"world_start":
			_show_status("Запуск запрошен. Обновляем список миров…")
			_request_world_list()
		"editor_saved_maps":
			if not payload is Dictionary or not payload.get("saved_maps", []) is Array:
						_show_status("Сервер вернул неверный список сохранённых карт.")
						return
			_saved_maps.clear()
			for saved_map in payload["saved_maps"]:
						if saved_map is Dictionary:
							_saved_maps.append(saved_map)
			_show_editor_saved_maps()
		"leave_world_to_lobby":
			GameSession.leave_world()
			_request_world_list()
		"characters":
			var characters: Array = payload.get("characters", []) if payload is Dictionary else []
			if str(_current_world.get("mode", "")) == "front_line":
				if characters.is_empty():
					_show_status("Для входа во Front Line нужен профиль персонажа аккаунта.")
					return
				_select_character(characters[0])
				return
			_show_characters(characters)
		"create_character":
			_load_characters()
		"delete_character":
			_selected_character.clear()
			_delete_password_input.clear()
			_load_characters()
		"logout_world":
			ApiClient.set_server_url(_hub_url)
			ApiClient.token = GameSession.token
			_pending_action = "logout_central"
			ApiClient.request_json(HTTPClient.METHOD_POST, "/api/sessions/disconnect")
		"logout_central":
			_finish_logout()
		_:
			_show_status("Ответ получен.")
