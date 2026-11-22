extends Control

const TITLE_COLOR := Color(0.94, 0.82, 0.56)
const MUTED_COLOR := Color(0.62, 0.68, 0.77)
# Замеры: кадр длиннее этого порога печатается в консоль с разбивкой по участкам.
const PERF_FRAME_LOG_MS := 30.0
const EXIT_MENU_SCRIPT := preload("res://scripts/exit_menu.gd")
const SERVER_STATUS_HUD_SCRIPT := preload("res://scripts/server_status_hud.gd")
const HOTBAR_SCRIPT := preload("res://scripts/hotbar.gd")
const PROFILE_OVERLAY_SCRIPT := preload("res://scripts/character_profile_overlay.gd")
const PROFILE_RULES_SCRIPT := preload("res://scripts/character_profile_rules.gd")
const PLAYER_CLICK_RADIUS := 32.0
const COMBAT_LOG_SCRIPT := preload("res://scripts/combat_log.gd")
const SCENE_TRANSITION := preload("res://scripts/scene_transition.gd")
const WORLD_AUDIO_SCRIPT := preload("res://scripts/world_audio.gd")
const PRESENCE_RULES := preload("res://scripts/deck_presence_rules.gd")
const GATE_RULES := preload("res://scripts/economy_gate_rules.gd")
const TOWN_RULES := preload("res://scripts/world_map_town_rules.gd")
const TOWN_VIEW_SCRIPT := preload("res://scripts/world_map_town_view.gd")
const CITY_VISUAL_REFRESH_SECONDS := 10.0
const ECONOMY_CITY_SCENE := "res://scenes/economy_world.tscn"
const STATUS_NOTICE_SECONDS := 2.0
const OTHER_NAME_COLOR := Color8(184, 224, 255)
const OTHER_LABEL_FILL := Color8(17, 23, 29)
const OTHER_LABEL_BORDER := Color8(79, 139, 179)
const AFK_NAME_COLOR := Color8(153, 157, 163)
const AFK_LABEL_FILL := Color8(20, 22, 26)
const AFK_LABEL_BORDER := Color8(105, 109, 115)
const WORLD_COLLISION_SCRIPT := preload("res://scripts/world_collision.gd")
const TILE_SIZE := 16.0
const PLAYER_REPATH_INTERVAL := 0.3
# Зона клика по мобу Front Line: квадрат ±40 px от центра, как нарисованная крыса (тело для коллизий меньше).
const CLICK_HALF_FRONT_LINE := 40.0
const PLAYER_STALL_TIMEOUT := 0.4
# Во Front Line тело преследуемой крысы — препятствие для пути (как на сервере); в Tower оно исключается, как раньше.
# Путь погони перестраивается только когда цель ушла от точки прибытия дальше этого расстояния.
const CHASE_REPLAN_DISTANCE_PX := 24.0
# Точка прибытия погони не ближе этого расстояния к центру моба: ноги героя не задевают его тело (16 px + 10 px).
const CHASE_MIN_STAND_PX := 36.0
# Атака-движение и автоподбор: радиус поиска врага — дальность удара плюс запас.
const ATTACK_MOVE_ACQUIRE_MARGIN_PX := 32.0
const TOWER_TERRAIN_SCRIPT := preload("res://scripts/front_line_terrain_view.gd")
const FRONT_LINE_MAP_VIEW_SCRIPT := preload("res://scripts/front_line_map_view.gd")
const TOWER_ENTITY_SCRIPT := preload("res://scripts/tower_entity_view.gd")
const TOWER_ENTITY_RULES := preload("res://scripts/front_line_entity_rules.gd")
const TOWER_HUD_SCRIPT := preload("res://scripts/tower_hud_view.gd")
const FRONT_LINE_HUD_SCRIPT := preload("res://scripts/front_line_hud_view.gd")
const TOWER_HUB_RULES := preload("res://scripts/tower_hub_rules.gd")
const TOWER_HUB_VIEW_SCRIPT := preload("res://scripts/tower_hub_view.gd")
const TOWER_ROOM_RULES := preload("res://scripts/tower_room_rules.gd")
const TOWER_ROOM_VIEW_SCRIPT := preload("res://scripts/tower_room_view.gd")
# Экраны совпадают с зонами персонажа и локациями чата: "tavern", "character_room", "world_map".
const SCREEN_LOADING := ""
const SCREEN_HUB := "tavern"
const SCREEN_ROOM := "character_room"
const SCREEN_MAP := "world_map"
const CHECKPOINT_ACTION := "checkpoint"
const CHAT_TITLES := {"tavern": "Чат таверны", "character_room": "Чат комнаты", "world_map": "Чат мира"}
# Python рисует мир в 1920×1080 без масштаба; база Godot 1280×720 растягивается ×1.5, поэтому мир и HUD ×2/3.
const TOWER_WORLD_SCALE := 2.0 / 3.0
# Колёсико как в Dota 2: отдаление широкое, шаг мультипликативный (плавно и на любом уровне).
const FRONT_LINE_CAMERA_SCALE := 1.0
const FRONT_LINE_CAMERA_MIN_SCALE := 0.5
const FRONT_LINE_CAMERA_MAX_SCALE := 2.2
const FRONT_LINE_CAMERA_ZOOM_STEP := 1.1
const FRONT_LINE_CAMERA_EDGE_MARGIN := 24.0
const FRONT_LINE_CAMERA_EDGE_SPEED := 420.0
const TOWER_WORLD_BACKGROUND := Color8(20, 24, 28)
const CLICK_EFFECT_SECONDS := 0.35
const OVERHEAD_FONT_PY := 11.0
const OVERHEAD_LABEL_H_PY := 14.0
const PROFESSION_ICON_PY := 32.0
const PROFESSION_ICON_GAP_PY := 4.0
const CORPSE_LOOT_RANGE_TILES := 4.0  # 4 клетки по 16 px (как CORPSE_LOOT_RANGE на сервере)
const MAGIC_PREVIEW_CLASSES := ["warrior", "archer", "mage"]
const MAGIC_PREVIEW_CLASS_LABELS := ["Воин", "Лучник", "Маг"]
const MAGIC_PREVIEW_DIRECTION_LABELS := {"s": "вниз", "w": "влево", "e": "вправо", "n": "вверх"}
const CORPSE_WINDOW_SIZE_PY := Vector2(360.0, 190.0)
const MOB_HP_BAR_COLOR := Color8(200, 40, 40)
const PLAYER_HP_BAR_COLOR := Color8(190, 55, 55)
const PLAYER_MP_BAR_COLOR := Color8(60, 120, 220)
const HP_TEXT_COLOR := Color8(255, 110, 110)
const MP_TEXT_COLOR := Color8(120, 170, 255)
const NAME_TEXT_COLOR := Color8(255, 235, 150)
const CURRENCY_FORMAT := preload("res://scripts/currency_format.gd")
const INVENTORY_GRID_SCRIPT := preload("res://scripts/inventory_drag_view.gd")
const INVENTORY_RULES := preload("res://scripts/inventory_drag_rules.gd")
const CREATE_CHARACTER_VIEW_SCRIPT := preload("res://scripts/create_character_view.gd")
const MAGIC_CASTING_PREVIEW_SCRIPT := preload("res://scripts/magic_casting_preview.gd")
# Сетка рюкзака в пикселях Python 1120×440, как у карты мира: масштаб 2/3 вписывает её в базовые 1280×720.
const COMBAT_SYNC_SECONDS := 0.1
const WS_SYNC_SECONDS := 0.05
const WORLD_STREAM_PATH := "/api/world/stream"
const IDLE_SYNC_SECONDS := 0.1
const INVENTORY_GRID_SCALE := 2.0 / 3.0
const INVENTORY_PANEL_WIDTH := 772.0

var _status_box: VBoxContainer
var _status: Label
var _pending_action := ""
var _world_sync_timer: Timer
var _sync_accumulator := 0.0
var _movement_pending := false
var _resync_pending := false
var _desired_position := Vector2.ZERO
var _sent_position := Vector2.ZERO
var _move_target := Vector2.ZERO
var _has_move_target := false
var _move_path: Array = []
var _path_stall := 0.0
var _chase_goal_planned := Vector2.ZERO
# Приказы Front Line как в Dota 2: номер приказа отменяет замах на сервере; S — стоп; H — удержание;
# A — атака-движение. _wants_acquire — цель погибла, нужен ближайший враг в радиусе.
var _order_id := 0
var _hold_position := false
var _pending_stop := false
# Очки характеристик, которые игрок добавил в бою: уходят мировому серверу с ближайшей синхронизацией.
var _pending_stat_allocations: Array = []
# Канал мира: один запрос за раз, свой флаг; чат и карточка его не блокируют.
var _world_request_pending := false
var _world_action := ""
# Постоянные поля мобов, полученные однажды; сжатый снимок дополняет их.
var _mob_static: Dictionary = {}
# WebSocket мира: сервер сам присылает снимки, клиент шлёт положение и приказы по тому же соединению.
# Если соединение не поднялось, всё идёт по HTTP, как раньше.
var _ws: WebSocketPeer = null
var _ws_ready := false
var _ws_auth_sent := false
var _ws_retry := 0.0
var _command_id := 0
# Согласование позиции героя: при отказе сервера небольшое расхождение сходится плавно, большое — сразу.
const RECONCILE_SNAP_PX := 48.0
const RECONCILE_SPEED_FACTOR := 0.5
var _has_correction := false
var _correction_target := Vector2.ZERO
# Команды, отправленные по WebSocket и ещё не подтверждённые (id -> момент отправки, мс).
var _unacked_commands: Dictionary = {}
var _attack_move_armed := false
var _attack_move_active := false
var _attack_move_goal := Vector2.ZERO
var _wants_acquire := false
var _repath_timer := 0.0
var _collision = WORLD_COLLISION_SCRIPT.new()
var _map_tiles_w := 125
var _map_tiles_h := 125
var _front_line_zoom := FRONT_LINE_CAMERA_SCALE
var _camera_offset := Vector2.ZERO
var _camera_dragging := false
var _terrain_version: Variant = null
var _terrain_loaded := false
var _world_ready := false
var _selected_mob_id := ""
var _corpse_window_id := 0
var _pending_dash_target: Variant = null
var _audio
var _world_swing_id: Variant = null
var _harvest_target: Variant = null
var _crystal_tiles: Array = []
var _dash_aiming := false
var _combat_log
var _floating_events: Array[Dictionary] = []
var _inventory_state: Dictionary = {}
var _inventory_loaded := false
var _terrain_view = TOWER_TERRAIN_SCRIPT.new()
var _front_line_map_view = FRONT_LINE_MAP_VIEW_SCRIPT.new()
var _entity_view = TOWER_ENTITY_SCRIPT.new()
var _hud_view = TOWER_HUD_SCRIPT.new()
var _player_direction := "s"
var _player_moving_timer := 0.0
var _previous_position := Vector2.ZERO
var _click_effect_timer := 0.0
var _click_effect_world := Vector2.ZERO
var _inventory_panel: PanelContainer
var _inventory_list: VBoxContainer
var _inventory_status: Label
var _inventory_grid: INVENTORY_GRID_SCRIPT
var _inventory_grid_host: Control
var _inventory_weight: Label
var _inventory_scroll: ScrollContainer
var _inventory_actions: HBoxContainer
var _inventory_action_button: Button
var _inventory_drop_button: Button
var _inventory_deposit_button: Button
var _magic_casting_preview = MAGIC_CASTING_PREVIEW_SCRIPT.new()
var _magic_preview_visible := false
var _magic_preview_class_index := 0
var _magic_preview_level := 1
var _profile_overlay: PROFILE_OVERLAY_SCRIPT
var _inventory_view_select: OptionButton
var _inventory_view := "backpack"
var _storage_destination_select: OptionButton
var _storage_by_type: Dictionary = {}
var _request_storage_type := ""
var _request_queue: Array[Dictionary] = []
var _screen := SCREEN_LOADING
var _hub_view
var _room_view
var _chat_title: Label
var _storage_quantity_input: LineEdit
var _connection_overlay: ColorRect
var _connection_message: Label
var _connection_counter: Label
var _action_button: Button
var _login_button: Button
var _chat_timer: Timer
var _chat_panel: PanelContainer
var _chat_messages_list: VBoxContainer
var _chat_occupants_label: Label
var _chat_input: LineEdit
var _chat_target_select: OptionButton
var _chat_private_mode := false
var _chat_status: Label
var _chat_reason_input: LineEdit
var _chat_messages: Array[Dictionary] = []
var _chat_occupants: Array[Dictionary] = []
var _exit_menu
var _exit_intent := ""
var _exit_queued := false
var _server_unreachable := false
var _server_status_hud
var _hotbar
var _economy_map := false
var _economy_sync_failed := false
var _map_objects: Array = []
var _town_objects: Array = []
var _town_view = TOWN_VIEW_SCRIPT.new()
var _city_visual_state: Dictionary = {}
var _layout_city_level := 1
var _city_refresh_seconds := 0.0
var _town_active_id := ""
var _town_notice := ""
var _town_notice_seconds := 0.0
var _last_too_far_phrase := ""
var _leaving_to_city := false
var _city_gate_pending := ""
var _status_notice := ""
var _status_notice_seconds := 0.0
var _front_line_draft_overlay: ColorRect
var _front_line_draft_title: Label
var _front_line_draft_status: Label
var _front_line_draft_view
var _front_line_draft_notice := ""
var _front_line_report_overlay: CenterContainer
var _front_line_summary_overlay: CenterContainer
var _front_line_summary_title: Label
var _front_line_summary_info: Label
var _front_line_summary_grid: GridContainer
var _front_line_summary_button: Button
var _front_line_summary_key := ""
var _perf_sections: Dictionary = {}
var _front_line_report_title: Label
var _front_line_report_body: Label
var _front_line_countdown_label: Label
var _front_line_report_state := ""
var _front_line_report_seconds := 0.0
var _front_line_report_tween: Tween

func _ready() -> void:
	if _is_front_line_world():
		_hud_view = FRONT_LINE_HUD_SCRIPT.new()
	ApiClient.request_completed.connect(_on_api_completed)
	ApiClient.world_request_completed.connect(_on_world_request_completed)
	ApiClient.command_completed.connect(_on_command_completed)
	ConnectionGuard.connection_lost.connect(_on_connection_lost)
	ConnectionGuard.countdown_updated.connect(_on_countdown_updated)
	ConnectionGuard.connection_restored.connect(_on_connection_restored)
	ConnectionGuard.client_outdated.connect(_on_client_outdated)
	ConnectionGuard.session_invalid.connect(_on_session_invalid)
	ConnectionGuard.connection_expired.connect(_on_connection_expired)
	_build_screen()
	_build_exit_menu()
	_build_server_status_hud()
	_build_hotbar()
	_build_combat_log()
	get_tree().root.close_requested.connect(_on_close_requested)
	get_tree().set_auto_accept_quit(false)
	_show_session()
	var entry_gate := GameSession.take_pending_map_gate()
	if not entry_gate.is_empty():
		_enter_from_economy(entry_gate)
	_world_sync_timer = Timer.new()
	_world_sync_timer.wait_time = 1.0
	_world_sync_timer.timeout.connect(_sync_world)
	add_child(_world_sync_timer)
	_chat_timer = Timer.new()
	_chat_timer.wait_time = 2.0
	_chat_timer.timeout.connect(_poll_chat)
	add_child(_chat_timer)
	set_process(true)
	ApiClient.token = GameSession.world_token
	var world_url := str(GameSession.world.get("server_url", "")).strip_edges()
	if world_url.is_empty():
		world_url = GameSession.hub_url
	if not ApiClient.set_server_url(world_url):
		_status.text = "У выбранного мира неверный адрес сервера."
		return
	_refresh_character()


func _exit_tree() -> void:
	if ApiClient.request_completed.is_connected(_on_api_completed):
		ApiClient.request_completed.disconnect(_on_api_completed)
	if get_tree().root.close_requested.is_connected(_on_close_requested):
		get_tree().root.close_requested.disconnect(_on_close_requested)
	if ConnectionGuard.status_received.is_connected(_server_status_hud.apply_status):
		ConnectionGuard.status_received.disconnect(_server_status_hud.apply_status)
	get_tree().set_auto_accept_quit(true)
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
	if _world_sync_timer != null:
		_world_sync_timer.stop()
	if _chat_timer != null:
		_chat_timer.stop()


func _build_screen() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_build_social_views()
	_status_box = VBoxContainer.new()
	_status_box.add_theme_constant_override("separation", 6)
	_status_box.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM)
	_status_box.offset_left = -320.0
	_status_box.offset_right = 320.0
	_status_box.offset_top = -120.0
	_status_box.offset_bottom = -78.0
	_status_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_status_box)
	_build_front_line_report()

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
	overlay_panel.custom_minimum_size = Vector2(560, 240)
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

	_action_button = Button.new()
	_action_button.text = "Закрыть клиент"
	_action_button.custom_minimum_size.y = 42
	_action_button.visible = false
	_action_button.pressed.connect(_close_for_reload)
	overlay_content.add_child(_action_button)

	_login_button = Button.new()
	_login_button.text = "Вернуться ко входу"
	_login_button.custom_minimum_size.y = 42
	_login_button.visible = false
	_login_button.pressed.connect(_return_to_login)
	overlay_content.add_child(_login_button)
	_build_inventory_panel()
	_build_profile_overlay()
	_build_chat_panel()


func _show_session() -> void:
	for child in _status_box.get_children():
		_status_box.remove_child(child)
		child.queue_free()


	_status = Label.new()
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.custom_minimum_size.x = 320
	_status.add_theme_color_override("font_color", MUTED_COLOR)
	_status_box.add_child(_status)


func _build_inventory_panel() -> void:
	_inventory_panel = PanelContainer.new()
	_inventory_panel.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	_inventory_panel.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_inventory_panel.grow_vertical = Control.GROW_DIRECTION_BOTH
	_inventory_panel.custom_minimum_size = Vector2(INVENTORY_PANEL_WIDTH, 0)
	_inventory_panel.visible = false
	_inventory_panel.z_index = 5
	add_child(_inventory_panel)

	var panel_content := VBoxContainer.new()
	panel_content.add_theme_constant_override("separation", 8)
	_inventory_panel.add_child(panel_content)

	var header := HBoxContainer.new()
	panel_content.add_child(header)
	var title := Label.new()
	title.text = "Инвентарь и экипировка"
	title.add_theme_color_override("font_color", TITLE_COLOR)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(title)
	var close_cross := Button.new()
	close_cross.text = "×"
	close_cross.custom_minimum_size = Vector2(26.0, 26.0)
	close_cross.focus_mode = Control.FOCUS_NONE
	close_cross.add_theme_color_override("font_color", Color8(240, 200, 200))
	close_cross.add_theme_stylebox_override("normal", _cross_style())
	close_cross.add_theme_stylebox_override("hover", _cross_style())
	close_cross.pressed.connect(_close_inventory)
	header.add_child(close_cross)
	_inventory_view_select = OptionButton.new()
	_inventory_view_select.add_item("Рюкзак")
	_inventory_view_select.add_item("Сундук 1")
	_inventory_view_select.add_item("Сундук 2")
	_inventory_view_select.item_selected.connect(_on_inventory_view_selected)
	panel_content.add_child(_inventory_view_select)
	var storage_row := HBoxContainer.new()
	panel_content.add_child(storage_row)
	_storage_destination_select = OptionButton.new()
	_storage_destination_select.add_item("Класть в сундук 1")
	_storage_destination_select.add_item("Класть в сундук 2")
	_storage_destination_select.select(0)
	storage_row.add_child(_storage_destination_select)
	_storage_quantity_input = LineEdit.new()
	_storage_quantity_input.placeholder_text = "Количество для переноса (пусто — вся стопка)"
	_storage_quantity_input.max_length = 4
	_storage_quantity_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	storage_row.add_child(_storage_quantity_input)

	_inventory_weight = Label.new()
	_inventory_weight.add_theme_color_override("font_color", MUTED_COLOR)
	panel_content.add_child(_inventory_weight)

	_inventory_grid = INVENTORY_GRID_SCRIPT.new()
	_inventory_grid.set_bag_only(true)
	_inventory_grid_host = INVENTORY_GRID_SCRIPT.scaled_host(_inventory_grid, INVENTORY_GRID_SCALE)
	_inventory_grid_host.custom_minimum_size = _inventory_grid.custom_minimum_size * INVENTORY_GRID_SCALE
	panel_content.add_child(_inventory_grid_host)
	_inventory_grid.move_requested.connect(_on_inventory_move_requested)
	_inventory_grid.equip_requested.connect(_on_inventory_equip_requested)
	_inventory_grid.unequip_requested.connect(_on_inventory_unequip_requested)
	_inventory_grid.use_requested.connect(_on_inventory_use_requested)
	_inventory_grid.drop_requested.connect(_on_inventory_drop_requested)
	_inventory_grid.selection_changed.connect(_on_inventory_selection_changed)
	_inventory_grid.drop_confirm_changed.connect(_on_inventory_drop_confirm_changed)
	_inventory_grid.message_colored.connect(_on_inventory_grid_message)
	_inventory_grid.drop_outside_requested.connect(_on_inventory_drop_outside)

	_inventory_actions = HBoxContainer.new()
	panel_content.add_child(_inventory_actions)
	_inventory_action_button = _make_inventory_button("", _on_inventory_action_pressed)
	_inventory_drop_button = _make_inventory_button("Выбросить", _on_inventory_drop_pressed)
	_inventory_deposit_button = _make_inventory_button("В сундук", _on_inventory_deposit_pressed)

	_inventory_status = Label.new()
	_inventory_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_inventory_status.add_theme_color_override("font_color", MUTED_COLOR)
	panel_content.add_child(_inventory_status)

	_inventory_scroll = ScrollContainer.new()
	_inventory_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	panel_content.add_child(_inventory_scroll)

	_inventory_list = VBoxContainer.new()
	_inventory_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_inventory_list.add_theme_constant_override("separation", 5)
	_inventory_scroll.add_child(_inventory_list)



func _cross_style() -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color8(60, 36, 40)
	style.border_color = Color8(200, 70, 70)
	style.set_border_width_all(1)
	style.set_corner_radius_all(4)
	return style


func _close_inventory() -> void:
	_inventory_panel.visible = false
	_update_equipment_guide([])


# Выбран предмет рюкзака — на карточке подсвечивается слот, куда он надевается.
func _update_equipment_guide(target: Array) -> void:
	var slot := ""
	if _inventory_panel.visible and not target.is_empty() and str(target[0]) == INVENTORY_RULES.KIND_BAG:
		slot = INVENTORY_RULES.equip_slot_of(_inventory_grid.selected_item())
	_profile_overlay.set_guide_slot(slot)


# Предмет отпущен вне рюкзака: надеваем, если отпущен над нужной ячейкой карточки персонажа.
func _on_inventory_drop_outside(source: Array, global_point: Vector2) -> void:
	var slot: String = _profile_overlay.equipment_slot_at_global(global_point)
	if slot.is_empty():
		_inventory_status.text = "Чтобы надеть предмет, перетащите его на ячейку экипировки на карточке персонажа (клавиша I)."
		return
	var item := _inventory_grid.item_at(source)
	_inventory_grid.apply_decision(INVENTORY_RULES.drop_decision(source, [INVENTORY_RULES.KIND_EQUIP, slot], item))


func _make_inventory_button(text: String, callback: Callable) -> Button:
	var button := Button.new()
	button.text = text
	button.focus_mode = Control.FOCUS_NONE
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.pressed.connect(callback)
	_inventory_actions.add_child(button)
	return button


func _build_profile_overlay() -> void:
	_profile_overlay = PROFILE_OVERLAY_SCRIPT.new()
	_profile_overlay.stat_requested.connect(_on_profile_stat_requested)
	_profile_overlay.level_requested.connect(_on_profile_level_requested)
	_profile_overlay.backpack_requested.connect(_toggle_inventory)
	add_child(_profile_overlay)


func _toggle_character_profile() -> void:
	if _profile_overlay.is_open():
		_profile_overlay.close()
	else:
		_open_profile_overlay()


func _open_profile_overlay() -> void:
	if GameSession.character.is_empty():
		return
	_profile_overlay.open(_live_profile())


func _is_player_point(point: Vector2) -> bool:
	return point.distance_to(size * 0.5) <= PLAYER_CLICK_RADIUS


# Живые HP и MP берём из мира; сервер уже включает бонус экипировки в максимум HP.
func _live_profile() -> Dictionary:
	var profile: Dictionary = GameSession.character.duplicate(true)
	var live: Variant = GameSession.world_snapshot.get("player", {})
	if live is Dictionary:
		for key in ["hp", "mp", "max_hp", "max_mp"]:
			if live.has(key):
				profile[key] = live[key]
		profile["max_hp_includes_equipment"] = live.has("max_hp")
	return profile


func _render_character_profile() -> void:
	if _profile_overlay.is_open():
		_profile_overlay.update_profile(_live_profile())
	_render_social_views()


func _on_profile_stat_requested(stat_name: String, delta: int) -> void:
	var change: Dictionary = PROFILE_RULES_SCRIPT.adjust_stat(_profile_overlay.current_profile(), stat_name, delta)
	if change.is_empty():
		_status.text = "Эту характеристику сейчас нельзя изменить."
		return
	if _is_front_line_world():
		# Во Front Line очки растут за уровни в самом мире и в базу не пишутся: тратим их через синхронизацию мира,
		# а не через запись карточки (та блокировала синхронизацию и откатывала значение).
		if delta < 0:
			_status.text = "В бою характеристики только повышаются."
			return
		_pending_stat_allocations.append(stat_name)
		_send_order()
		return
	_save_profile_change({"stats": change["stats"], "stat_points": change["stat_points"]})


func _on_profile_level_requested(delta: int) -> void:
	var change: Dictionary = PROFILE_RULES_SCRIPT.adjust_level(_profile_overlay.current_profile(), delta)
	if change.is_empty():
		_status.text = "Уровень сейчас нельзя изменить."
		return
	_save_profile_change({"level": change["level"], "stats": change["stats"]})


func _save_profile_change(body: Dictionary) -> void:
	if not _pending_action.is_empty():
		_status.text = "Подождите завершения текущего запроса."
		return
	_pending_action = "profile_update"
	_status.text = "Сохраняем карточку персонажа на сервере…"
	ApiClient.request_json(HTTPClient.METHOD_PUT, "/api/characters/%d" % int(GameSession.character.get("id", 0)), body)


func _build_chat_panel() -> void:
	_chat_panel = PanelContainer.new()
	# Левый край и ширина CHAT_DIALOG_RECT из Python (451 px, 760 px) в базовых единицах; высота прежняя, т.к. вкладки, список и поля ввода не ужимаются.
	var chat_left := 451.0 * TOWER_WORLD_SCALE
	var chat_width := 760.0 * TOWER_WORLD_SCALE
	_chat_panel.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	_chat_panel.offset_left = chat_left
	_chat_panel.offset_right = chat_left + chat_width
	_chat_panel.offset_top = -354.0
	_chat_panel.offset_bottom = -4.0
	_chat_panel.custom_minimum_size = Vector2(chat_width, 350.0)
	_chat_panel.visible = false
	# Выше хотбара (z 90), как в Python, где диалог чата рисуется поверх панелей.
	_chat_panel.z_index = 95
	add_child(_chat_panel)
	var layout := VBoxContainer.new()
	_chat_panel.add_child(layout)
	_chat_title = Label.new()
	_chat_title.text = CHAT_TITLES[SCREEN_MAP]
	_chat_title.add_theme_color_override("font_color", TITLE_COLOR)
	layout.add_child(_chat_title)
	var chat_controls := HBoxContainer.new()
	layout.add_child(chat_controls)
	var public_chat := Button.new()
	public_chat.text = "Общий"
	public_chat.pressed.connect(_set_chat_mode.bind(false))
	chat_controls.add_child(public_chat)
	var private_chat := Button.new()
	private_chat.text = "Личный"
	private_chat.pressed.connect(_set_chat_mode.bind(true))
	chat_controls.add_child(private_chat)
	_chat_target_select = OptionButton.new()
	_chat_target_select.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_chat_target_select.item_selected.connect(_on_chat_target_selected)
	chat_controls.add_child(_chat_target_select)
	_chat_occupants_label = Label.new()
	_chat_occupants_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_chat_occupants_label.add_theme_color_override("font_color", MUTED_COLOR)
	layout.add_child(_chat_occupants_label)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	layout.add_child(scroll)
	_chat_messages_list = VBoxContainer.new()
	_chat_messages_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(_chat_messages_list)
	_chat_status = Label.new()
	_chat_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_chat_status.add_theme_color_override("font_color", MUTED_COLOR)
	layout.add_child(_chat_status)
	_chat_reason_input = LineEdit.new()
	_chat_reason_input.placeholder_text = "Причина жалобы (для кнопки жалобы)"
	_chat_reason_input.max_length = 200
	layout.add_child(_chat_reason_input)
	_chat_input = LineEdit.new()
	_chat_input.placeholder_text = "Сообщение…"
	_chat_input.max_length = 300
	_chat_input.text_submitted.connect(_send_chat_message)
	layout.add_child(_chat_input)
	var close_button := Button.new()
	close_button.text = "Закрыть чат"
	close_button.pressed.connect(_close_chat)
	layout.add_child(close_button)


func _close_chat() -> void:
	_chat_panel.visible = false


func _set_chat_mode(private_mode: bool) -> void:
	_chat_private_mode = private_mode
	_render_chat()


func _on_chat_target_selected(_index: int) -> void:
	if _chat_private_mode:
		_chat_status.text = "Личный диалог с выбранным игроком."


func _toggle_chat() -> void:
	_chat_panel.visible = not _chat_panel.visible
	if _chat_panel.visible:
		_inventory_panel.visible = false
		_poll_chat()


# Присутствие обновляется всегда, как PresenceState в Python: на карте с позицией и только после первого снимка мира.
func _chat_poll_allowed() -> bool:
	if _screen == SCREEN_LOADING or not _exit_intent.is_empty():
		return false
	if _screen == SCREEN_MAP and not _world_ready:
		return false
	if not _pending_action.is_empty() or _connection_overlay.visible:
		return false
	return int(GameSession.character.get("id", 0)) > 0


func _poll_chat() -> void:
	if not _chat_poll_allowed():
		return
	var on_map := _screen == SCREEN_MAP
	var character_id := int(GameSession.character.get("id", 0))
	var query := "location=%s&character_id=%d" % [_chat_location(), character_id]
	if on_map:
		var player: Dictionary = GameSession.world_snapshot.get("player", {})
		query += "&position_x=%s&position_y=%s" % [
			str(player.get("x", _desired_position.x)).uri_encode(),
			str(player.get("y", _desired_position.y)).uri_encode(),
		]
	_pending_action = "chat_snapshot"
	ApiClient.request_json(HTTPClient.METHOD_GET, "/api/social/snapshot?" + query)


func _send_chat_message(_submitted_text: String) -> void:
	if not _chat_panel.visible or not _pending_action.is_empty():
		return
	var text := _chat_input.text.strip_edges()
	if text.is_empty():
		return
	_pending_action = "chat_send"
	var target_id := _selected_chat_target_id() if _chat_private_mode else 0
	if _chat_private_mode and target_id <= 0:
		_pending_action = ""
		_chat_status.text = "Выберите игрока для личного сообщения."
		return
	ApiClient.request_json(HTTPClient.METHOD_POST, "/api/chat/messages", {
		"character_id": int(GameSession.character.get("id", 0)),
		"location": _chat_location(),
		"text": text,
		"recipient_id": target_id if target_id > 0 else null,
	})


func _selected_chat_target_id() -> int:
	if _chat_target_select == null or _chat_target_select.item_count == 0 or _chat_target_select.selected < 0:
		return 0
	return int(_chat_target_select.get_item_metadata(_chat_target_select.selected))


func _optional_id(value: Variant) -> int:
	return 0 if value == null else int(value)


func _chat_message_action(action: String, message: Dictionary) -> void:
	if not _pending_action.is_empty():
		_chat_status.text = "Подождите завершения текущего запроса."
		return
	var message_id := int(message.get("id", 0))
	if message_id <= 0:
		_chat_status.text = "У сообщения отсутствует идентификатор."
		return
	var payload := {"character_id": int(GameSession.character.get("id", 0))}
	var path := ""
	match action:
		"report":
			var reason := _chat_reason_input.text.strip_edges()
			if reason.is_empty():
				_chat_status.text = "Укажите причину жалобы."
				return
			path = "/api/chat/report"
			payload["message_id"] = message_id
			payload["reason"] = reason
		"delete":
			if not _is_chat_moderator():
				_chat_status.text = "Удалять сообщения может только модератор."
				return
			path = "/api/chat/delete"
			payload["message_id"] = message_id
		"mute":
			var muted_id := int(message.get("sender_id", 0))
			if muted_id <= 0 or muted_id == int(GameSession.character.get("id", 0)):
				return
			path = "/api/chat/mute"
			payload["muted_character_id"] = muted_id
			payload["seconds"] = 600
		_:
			return
	_pending_action = "chat_" + action
	ApiClient.request_json(HTTPClient.METHOD_POST, path, payload)


func _is_chat_moderator() -> bool:
	var role := str(GameSession.user.get("role", ""))
	return role == "moderator" or role == "admin"


func _render_chat() -> void:
	for child in _chat_messages_list.get_children():
		child.queue_free()
	var previous_target_id := _selected_chat_target_id()
	_chat_target_select.clear()
	_chat_target_select.add_item("Выбрать игрока")
	_chat_target_select.set_item_metadata(0, 0)
	var target_index := 0
	for occupant in _chat_occupants:
		var occupant_id := int(occupant.get("character_id", 0))
		if occupant_id <= 0 or occupant_id == int(GameSession.character.get("id", 0)):
			continue
		_chat_target_select.add_item(str(occupant.get("name", occupant.get("username", "Игрок"))))
		_chat_target_select.set_item_metadata(_chat_target_select.item_count - 1, occupant_id)
		if occupant_id == previous_target_id:
			target_index = _chat_target_select.item_count - 1
	_chat_target_select.select(target_index)
	_chat_target_select.visible = _chat_private_mode
	for message in _chat_messages:
		var recipient_id := _optional_id(message.get("recipient_id"))
		var own_id := int(GameSession.character.get("id", 0))
		var is_private := recipient_id > 0
		if (_chat_private_mode and not is_private) or (not _chat_private_mode and is_private):
			continue
		if is_private and own_id not in [_optional_id(message.get("sender_id")), recipient_id]:
			continue
		var row := VBoxContainer.new()
		var line := Label.new()
		line.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		line.text = "[%s] %s: %s" % [
			str(message.get("time_text", "")),
			str(message.get("sender", "Игрок")),
			str(message.get("text", "")),
		]
		row.add_child(line)
		var actions := HBoxContainer.new()
		var report_button := Button.new()
		report_button.text = "Пожаловаться"
		report_button.pressed.connect(_chat_message_action.bind("report", message))
		actions.add_child(report_button)
		var sender_id := int(message.get("sender_id", 0))
		if sender_id > 0 and sender_id != own_id:
			var mute_button := Button.new()
			mute_button.text = "Игнорировать 10 мин."
			mute_button.pressed.connect(_chat_message_action.bind("mute", message))
			actions.add_child(mute_button)
		if _is_chat_moderator():
			var delete_button := Button.new()
			delete_button.text = "Удалить"
			delete_button.pressed.connect(_chat_message_action.bind("delete", message))
			actions.add_child(delete_button)
		row.add_child(actions)
		_chat_messages_list.add_child(row)
	var names: Array[String] = []
	for occupant in _chat_occupants:
		names.append(str(occupant.get("name", occupant.get("username", "Игрок"))))
	_chat_occupants_label.text = "В мире: " + (", ".join(names) if not names.is_empty() else "пока никого")


func _toggle_inventory() -> void:
	_inventory_panel.visible = not _inventory_panel.visible
	if _inventory_panel.visible:
		_chat_panel.visible = false
	if _inventory_panel.visible and not _inventory_loaded:
		_request_inventory_state()
	_update_equipment_guide(_inventory_grid.selected_target())


func _on_inventory_view_selected(index: int) -> void:
	_inventory_view = ["backpack", "chest1", "chest2"][index]
	if _inventory_view == "backpack":
		_render_inventory()
	else:
		_request_storage_state(_inventory_view)


func _request_storage_state(storage_type: String) -> void:
	var character_id := int(GameSession.character.get("id", 0))
	_set_inventory_message("Загружаем содержимое сундука…")
	_request_when_idle("storage_load", HTTPClient.METHOD_GET, "/api/storage/%d/%s" % [character_id, storage_type], {}, storage_type)


func _request_storage_transfer(direction: String, slot_index: int, storage_item_id: int, stack_quantity: int) -> void:
	var quantity := stack_quantity
	if not _storage_quantity_input.text.strip_edges().is_empty():
		quantity = int(_storage_quantity_input.text)
	if quantity <= 0 or quantity > stack_quantity:
		_set_inventory_message("Введите количество от 1 до размера выбранной стопки.")
		return
	var storage_type := _inventory_view
	if direction == "deposit":
		storage_type = "chest1" if _storage_destination_select.selected == 0 else "chest2"
	elif storage_type == "backpack":
		_set_inventory_message("Сначала выберите сундук для получения предметов.")
		return
	_send_storage_transfer(direction, storage_type, quantity, slot_index, storage_item_id)


func _send_storage_transfer(direction: String, storage_type: String, quantity: int, slot_index: int, storage_item_id: int) -> void:
	if not _pending_action.is_empty():
		_set_inventory_message("Подождите завершения текущего запроса.")
		return
	var payload := {
		"character_id": int(GameSession.character.get("id", 0)),
		"storage_type": storage_type,
		"direction": direction,
		"quantity": quantity,
	}
	if direction == "deposit":
		payload["slot_index"] = slot_index
	else:
		payload["storage_item_id"] = storage_item_id
	_pending_action = "storage_transfer"
	_request_storage_type = storage_type
	_set_inventory_message("Перемещаем предметы…")
	ApiClient.request_json(HTTPClient.METHOD_POST, "/api/storage/transfer", payload)


# Сообщения инвентаря и сундуков видны и в панели рюкзака, и в комнате.
func _set_inventory_message(text: String, is_error := false) -> void:
	_show_inventory_message(text, INVENTORY_RULES.BAD_COLOR if is_error else MUTED_COLOR)


func _show_inventory_message(text: String, color: Color) -> void:
	_inventory_status.text = text
	_inventory_status.add_theme_color_override("font_color", color)
	_room_view.set_status(text)


func _request_inventory_state() -> void:
	if not _pending_action.is_empty():
		_inventory_status.text = "Подождите завершения текущего запроса."
		return
	var character_id := int(GameSession.character.get("id", 0))
	if character_id <= 0:
		_inventory_status.text = "Сначала выберите персонажа."
		return
	_pending_action = "inventory_load"
	_inventory_status.text = "Загружаем инвентарь…"
	ApiClient.request_json(HTTPClient.METHOD_GET, "/api/inventory/%d" % character_id)


func _request_inventory_action(action: String, payload: Dictionary) -> void:
	if not _pending_action.is_empty():
		_set_inventory_message("Подождите завершения текущего запроса.", true)
		_inventory_grid.resolve_action(false)
		return
	payload["character_id"] = int(GameSession.character.get("id", 0))
	_pending_action = "inventory_action"
	ApiClient.request_json(HTTPClient.METHOD_POST, action, payload)


func _render_inventory() -> void:
	for child in _inventory_list.get_children():
		_inventory_list.remove_child(child)
		child.queue_free()

	var backpack := _inventory_view == "backpack"
	_inventory_grid_host.visible = backpack
	_inventory_weight.visible = backpack
	_inventory_actions.visible = backpack
	_inventory_scroll.visible = not backpack
	_storage_destination_select.visible = backpack
	_storage_quantity_input.visible = true
	_inventory_status.add_theme_color_override("font_color", MUTED_COLOR)
	if not backpack:
		var chest_items: Array = _chest_items(_inventory_view)
		_inventory_status.text = "%s · %d / %d ячеек" % [
			_inventory_view,
			chest_items.size(),
			80 if _inventory_view == "chest1" else 100,
		]
		var storage_items: Variant = chest_items
		if storage_items.is_empty():
			var empty_storage := Label.new()
			empty_storage.text = "Сундук пуст."
			_inventory_list.add_child(empty_storage)
		else:
			for storage_item in storage_items:
				if not storage_item is Dictionary:
					continue
				var storage_label := Label.new()
				storage_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
				storage_label.text = "%s ×%d · ячейка %d" % [
					str(storage_item.get("name", "Предмет")),
					int(storage_item.get("quantity", 1)),
					int(storage_item.get("slot_index", 0)) + 1,
				]
				var storage_row := HBoxContainer.new()
				storage_row.add_child(storage_label)
				var withdraw_button := Button.new()
				withdraw_button.text = "В рюкзак"
				withdraw_button.pressed.connect(_request_storage_transfer.bind(
					"withdraw",
					-1,
					int(storage_item.get("id", 0)),
					int(storage_item.get("quantity", 1)),
				))
				storage_row.add_child(withdraw_button)
				_inventory_list.add_child(storage_row)
		return

	_render_backpack()


func _render_backpack() -> void:
	var inventory: Variant = _inventory_state.get("inventory", [])
	var equipment: Variant = _inventory_state.get("equipment", {})
	var capacity := int(_inventory_state.get("capacity", 50))
	_inventory_status.text = ""
	_inventory_weight.text = "Вес: %.1f кг · Ячейки: %d / %d" % [
		float(_inventory_state.get("carried_weight_kg", 0.0)),
		inventory.size() if inventory is Array else 0,
		capacity,
	]
	_inventory_grid.set_items(
		inventory if inventory is Array else [],
		equipment if equipment is Dictionary else {},
		capacity,
	)
	_refresh_inventory_actions()


func _refresh_inventory_actions() -> void:
	var target: Array = _inventory_grid.selected_target()
	var item: Dictionary = _inventory_grid.selected_item()
	var action := INVENTORY_RULES.action_label(target, item)
	_inventory_action_button.text = action
	_inventory_action_button.visible = not action.is_empty()
	var bag_item := not target.is_empty() and str(target[0]) == INVENTORY_RULES.KIND_BAG and not item.is_empty()
	_inventory_drop_button.visible = bag_item
	_inventory_drop_button.text = "Точно?" if _inventory_grid.drop_confirm_active() else "Выбросить"
	_inventory_deposit_button.visible = bag_item


func _on_inventory_action_pressed() -> void:
	_inventory_grid.quick_action(_inventory_grid.selected_target())


func _on_inventory_drop_pressed() -> void:
	_inventory_grid.request_drop(_inventory_grid.selected_target())


func _on_inventory_deposit_pressed() -> void:
	var target: Array = _inventory_grid.selected_target()
	var item: Dictionary = _inventory_grid.selected_item()
	if item.is_empty() or str(target[0]) != INVENTORY_RULES.KIND_BAG:
		return
	_request_storage_transfer("deposit", int(item.get("slot_index", -1)), -1, int(item.get("quantity", 1)))


func _on_inventory_move_requested(from_slot: int, to_slot: int) -> void:
	_request_inventory_action("/api/inventory/move", {"from_slot": from_slot, "to_slot": to_slot})


func _on_inventory_equip_requested(slot_index: int, slot: String) -> void:
	_request_inventory_action("/api/equipment/equip", INVENTORY_RULES.equip_body(slot_index, slot))


func _on_inventory_unequip_requested(slot: String, target_slot: int) -> void:
	_request_inventory_action("/api/equipment/unequip", INVENTORY_RULES.unequip_body(slot, target_slot))


func _on_inventory_use_requested(slot_index: int) -> void:
	_request_inventory_action("/api/inventory/use", {"slot_index": slot_index})


func _on_inventory_drop_requested(slot_index: int) -> void:
	_request_inventory_action("/api/inventory/drop", {"slot_index": slot_index})


func _on_inventory_grid_message(text: String, color: Color) -> void:
	_show_inventory_message(text, color)


func _on_inventory_selection_changed(target: Array) -> void:
	_refresh_inventory_actions()
	_update_equipment_guide(target)


func _on_inventory_drop_confirm_changed(_active: bool) -> void:
	_refresh_inventory_actions()


func _refresh_character() -> void:
	if not _pending_action.is_empty():
		return
	var character_id := int(GameSession.character.get("id", 0))
	if character_id <= 0:
		_status.text = "Не выбран персонаж. Вернитесь к списку персонажей."
		return
	_pending_action = "character"
	_status.text = "Загружаем состояние персонажа…"
	ApiClient.request_json(HTTPClient.METHOD_GET, "/api/characters/%d" % character_id)


func _build_social_views() -> void:
	_hub_view = TOWER_HUB_VIEW_SCRIPT.new()
	_hub_view.visible = false
	add_child(_hub_view)
	_hub_view.room_requested.connect(_go_to_screen.bind(SCREEN_ROOM))
	_hub_view.street_requested.connect(_go_to_screen.bind(SCREEN_MAP))
	_hub_view.bartender_requested.connect(_on_hub_bartender_requested)
	_room_view = TOWER_ROOM_VIEW_SCRIPT.new()
	_room_view.visible = false
	add_child(_room_view)
	_room_view.door_requested.connect(_go_to_screen.bind(SCREEN_HUB))
	_room_view.inventory_requested.connect(_toggle_inventory)
	_room_view.tab_selected.connect(_on_room_tab_selected)
	_room_view.withdraw_requested.connect(_on_room_withdraw_requested)


# Экран после выбора персонажа: карта, комната или таверна по сохранённой зоне (см. tower_hub_rules.gd).
func _enter_screen(screen: String) -> void:
	_set_screen(screen)
	_status.text = ""
	match screen:
		SCREEN_MAP:
			_status.text = "Загружаем карту мира…"
			if _is_front_line_world():
				# До первого снимка карта не показывается: драфт закрывает мир, пока состояние матча неизвестно.
				_show_front_line_loading_cover()
			_request_when_idle("terrain", HTTPClient.METHOD_GET, "/api/map/terrain")
			# Экипировка нужна звуку удара; Python подгружает её при создании WorldMapScene (refresh_carrying_state).
			_request_when_idle("equipment_load", HTTPClient.METHOD_GET, "/api/inventory/%d" % int(GameSession.character.get("id", 0)))
		SCREEN_ROOM:
			_room_view.set_tab(TOWER_ROOM_RULES.TAB_EQUIPMENT)
			_request_chests()
		SCREEN_HUB:
			_hub_view.set_status("")
	_render_social_views()


# Переход сохраняет зону экрана, который покидаем: таверна, комната или карта с позицией.
# Как transition.start в main.py: музыка таверны гаснет сразу, экран меняется после затемнения.
func _go_to_screen(screen: String) -> void:
	if screen == _screen or not _exit_intent.is_empty() or SCENE_TRANSITION.is_running(get_tree()):
		return
	if _screen != SCREEN_LOADING:
		_request_when_idle(CHECKPOINT_ACTION, HTTPClient.METHOD_PUT, _character_path(), _checkpoint_body())
	if _screen == SCREEN_HUB:
		_world_audio().fade_out_for_transition()
	SCENE_TRANSITION.run(get_tree(), _enter_screen.bind(screen))


# Вход с улицы Радбурга: карта начинается у того же входа, что и WorldMapScene(spawn_gate=...) в main.py.
func _enter_from_economy(gate_id: String) -> void:
	var spawn := GATE_RULES.map_spawn(gate_id)
	_economy_map = true
	_desired_position = spawn["position"]
	_previous_position = _desired_position
	_player_direction = str(spawn["direction"])


# Сервер Экономики не отдаёт /api/world/sync (economy/server/api.py): как в Python, ошибка показывается один раз,
# дальше молчим. Ходьба продолжается, синхронизация повторяется таймером.
func _handle_economy_sync_failure(action: String, message: String) -> void:
	if action == "world_resync":
		_resync_pending = false
		_connection_overlay.visible = false
	if not _economy_sync_failed:
		_economy_sync_failed = true
		_show_status_notice(message)
	if _world_sync_timer.is_stopped():
		_world_sync_timer.start()


# Сообщение на две секунды, как action_notice в Python; потом очищается, если его уже сменили.
func _show_status_notice(text: String) -> void:
	_status.text = text
	_status_notice = text
	_status_notice_seconds = STATUS_NOTICE_SECONDS


func _tick_status_notice(delta: float) -> void:
	if _status_notice_seconds <= 0.0:
		return
	_status_notice_seconds -= delta
	if _status_notice_seconds <= 0.0 and _status.text == _status_notice:
		_status.text = ""


# Шаг на вход Радбурга на карте: переход в город у того же входа, как CityScene(gate=city_gate) в main.py.
func _check_city_entrance() -> void:
	if not _economy_map or _leaving_to_city or not _exit_intent.is_empty():
		return
	var entrance := GATE_RULES.entrance_at_tile(_map_objects, _player_tile())
	if entrance.is_empty():
		return
	_leaving_to_city = true
	_city_gate_pending = entrance
	_clear_move_path()
	_start_city_transition_if_idle()


# Переход ждёт, пока закроется запрос карты: иначе город получит «Запрос уже выполняется».
func _start_city_transition_if_idle() -> void:
	if _city_gate_pending.is_empty():
		return
	if not _exit_intent.is_empty() or SCENE_TRANSITION.is_running(get_tree()):
		_city_gate_pending = ""
		return
	if not _pending_action.is_empty():
		return
	GameSession.pending_city_gate = _city_gate_pending
	_city_gate_pending = ""
	_world_audio().fade_out_for_transition()
	SCENE_TRANSITION.run(get_tree(), func() -> void: get_tree().change_scene_to_file(ECONOMY_CITY_SCENE))


func _world_audio():
	if _audio == null:
		_audio = WORLD_AUDIO_SCRIPT.new()
		add_child(_audio)
	return _audio


func _set_screen(screen: String) -> void:
	var previous := _screen
	_screen = screen
	_chat_title.text = CHAT_TITLES.get(_chat_location(), CHAT_TITLES[SCREEN_MAP])
	var on_map := screen == SCREEN_MAP
	_hub_view.visible = screen == SCREEN_HUB
	_room_view.visible = screen == SCREEN_ROOM
	_status_box.visible = not (on_map and _is_front_line_world())
	_hotbar.visible = on_map and not _is_front_line_world()
	_combat_log.visible = on_map
	if not on_map:
		_world_sync_timer.stop()
		_clear_move_path()
		_dash_aiming = false
		_world_audio().set_running(false)
	else:
		_world_swing_id = null
		if _is_front_line_world():
			_dash_aiming = false
	if previous == SCREEN_HUB and screen != SCREEN_HUB:
		_world_audio().fade_out_for_transition()
	if screen == SCREEN_HUB and previous != SCREEN_HUB:
		_world_audio().play_tavern()
	if screen != SCREEN_LOADING and _chat_timer.is_stopped():
		_chat_timer.start()
	queue_redraw()


func _render_social_views() -> void:
	_hub_view.set_character_text(TOWER_ROOM_RULES.character_line(GameSession.character))
	_room_view.set_character(GameSession.character)
	_room_view.set_equipment(_current_equipment())
	_room_view.set_chests(_storage_by_type)


# Замах меняет swing_id; первый снимок его только запоминает, как в Python.
func _update_swing_sound(player: Dictionary) -> void:
	var swing_id: Variant = player.get("swing_id")
	if swing_id == null:
		return
	if _world_swing_id != null and swing_id != _world_swing_id:
		_world_audio().play_swing(_current_equipment().get("weapon"))
	_world_swing_id = swing_id


# Надетое берём из данных персонажа; если их нет, используем последний ответ инвентаря.
func _current_equipment() -> Dictionary:
	var equipment: Variant = GameSession.character.get("equipment")
	if equipment is Dictionary:
		return equipment
	var inventory_equipment: Variant = _inventory_state.get("equipment")
	return inventory_equipment if inventory_equipment is Dictionary else {}


func _chest_items(storage_type: String) -> Array:
	var items: Variant = _storage_by_type.get(storage_type, [])
	return items if items is Array else []


# Локация чата и присутствия совпадает с экраном: "tavern", "character_room" или "world_map".
func _chat_location() -> String:
	return SCREEN_MAP if _screen == SCREEN_LOADING else _screen


func _character_path() -> String:
	return "/api/characters/%d" % int(GameSession.character.get("id", 0))


func _checkpoint_body() -> Dictionary:
	return TOWER_HUB_RULES.checkpoint_body(_screen, _desired_position, _player_direction, _world_ready)


# Запросы без действия игрока (чекпоинты, карта, сундуки) ждут, пока освободится общий канал запросов.
func _request_when_idle(action: String, method: int, path: String, body: Dictionary = {}, storage_type: String = "") -> void:
	_request_queue.append({"action": action, "method": method, "path": path, "body": body, "storage_type": storage_type})
	_flush_request_queue()


func _flush_request_queue() -> void:
	if not _exit_intent.is_empty():
		return
	while not _request_queue.is_empty() and _pending_action.is_empty():
		var item: Dictionary = _request_queue.pop_front()
		_pending_action = str(item["action"])
		_request_storage_type = str(item["storage_type"])
		ApiClient.request_json(int(item["method"]), str(item["path"]), item["body"])


func _request_chests() -> void:
	for storage_type in TOWER_ROOM_RULES.CHEST_TYPES:
		_request_storage_state(str(storage_type))


func _on_room_tab_selected(tab: String) -> void:
	if tab == TOWER_ROOM_RULES.TAB_CHESTS:
		_request_chests()


func _on_room_withdraw_requested(storage_type: String, item: Dictionary) -> void:
	_send_storage_transfer("withdraw", storage_type, int(item.get("quantity", 1)), -1, int(item.get("id", 0)))


func _on_hub_bartender_requested() -> void:
	_hub_view.set_status(TOWER_HUB_RULES.BARTENDER_UNAVAILABLE)


func _update_player_facing(delta: float) -> void:
	if not _world_ready:
		_previous_position = _desired_position
		return
	var step := _desired_position - _previous_position
	if step.length_squared() > 0.01:
		_player_direction = TOWER_ENTITY_RULES.facing_direction(step)
		_player_moving_timer = 0.15
	_previous_position = _desired_position
	_player_moving_timer = maxf(0.0, _player_moving_timer - delta)


func _process(delta: float) -> void:
	var started := _perf_begin()
	_perf_sections.clear()
	_process_frame(delta)
	var script_ms := float(Time.get_ticks_usec() - started) / 1000.0
	if delta * 1000.0 >= PERF_FRAME_LOG_MS:
		_perf_report_frame(delta, script_ms)


# Замеры: время участка в миллисекундах (Time.get_ticks_usec — микросекунды).
func _perf_begin() -> int:
	return Time.get_ticks_usec()


func _perf_end(label: String, started_usec: int) -> void:
	var elapsed := float(Time.get_ticks_usec() - started_usec) / 1000.0
	_perf_sections[label] = float(_perf_sections.get(label, 0.0)) + elapsed


func _perf_log_slow(label: String, started_usec: int) -> void:
	var elapsed := float(Time.get_ticks_usec() - started_usec) / 1000.0
	if elapsed >= PERF_FRAME_LOG_MS:
		print("[perf] %s: %.1f мс" % [label, elapsed])


func _perf_report_frame(delta: float, script_ms: float) -> void:
	var parts := PackedStringArray()
	for label in _perf_sections.keys():
		var ms := float(_perf_sections[label])
		if ms >= 0.5:
			parts.append("%s %.1f мс" % [label, ms])
	var details := "; ".join(parts) if not parts.is_empty() else "отмеченных участков нет"
	# Все узлы сцены: монитор движка (_process всех узлов, физика, число вызовов отрисовки).
	var all_process_ms := Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0
	var physics_ms := Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0
	var draw_calls := int(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME))
	print("[perf] кадр %.1f мс, скрипт мира %.1f мс, _process всех узлов %.1f мс, физика %.1f мс, вызовов отрисовки %d: %s" % [
		delta * 1000.0, script_ms, all_process_ms, physics_ms, draw_calls, details,
	])


func _process_frame(delta: float) -> void:
	_ensure_world_stream(delta)
	_update_floating_events(delta)
	_update_player_facing(delta)
	_click_effect_timer = maxf(0.0, _click_effect_timer - delta)
	_tick_front_line_report(delta)
	_update_front_line_cursor()
	_tick_status_notice(delta)
	_tick_town_notice(delta)
	if _world_ready:
		queue_redraw()
	_process_exit_queue()
	_tick_city_visual(delta)
	_flush_request_queue()
	_start_city_transition_if_idle()
	_server_status_hud.set_blocked(_exit_menu.blocks_input() or _connection_overlay.visible)
	_hotbar.set_dash_state(float(GameSession.world_snapshot.get("player", {}).get("dash_cooldown", 0.0)), _dash_aiming)
	if _profile_overlay.is_open():
		_profile_overlay.update_profile(_live_profile())
	if _screen == SCREEN_MAP and _world_ready and _is_front_line_world() \
			and not _connection_overlay.visible and not _exit_menu.blocks_input():
		_update_front_line_camera(delta)
	if _screen != SCREEN_MAP or not _world_ready or _connection_overlay.visible or _exit_menu.blocks_input() or _leaving_to_city:
		_world_audio().set_running(false)
		return
	var player_state: Dictionary = GameSession.world_snapshot.get("player", {})
	if bool(player_state.get("dash_active", false)):
		_world_audio().set_running(false)
		return
	var speed := _move_speed(player_state)
	var position_before := _desired_position
	if _has_correction:
		var offset := _correction_target - _desired_position
		var correction_step := _move_speed(player_state) * delta * RECONCILE_SPEED_FACTOR
		if offset.length() <= correction_step:
			_desired_position = _correction_target
			_has_correction = false
		else:
			_desired_position += offset.normalized() * correction_step
	# Во время замаха герой стоит на месте: ввод и путь не применяются (сервер тоже не принимает позицию).
	var winding_up := float(player_state.get("windup", 0.0)) > 0.0
	var movement := Vector2.ZERO if winding_up else _keyboard_movement()
	if winding_up:
		_clear_move_path()
	if movement.length_squared() > 0.0:
		_clear_move_path()
		_desired_position += movement * speed * delta
		_desired_position.x = clampf(_desired_position.x, 0.0, _map_tiles_w * TILE_SIZE)
		_desired_position.y = clampf(_desired_position.y, 0.0, _map_tiles_h * TILE_SIZE)
		_movement_pending = true
		queue_redraw()
	else:
		var chase_started := _perf_begin()
		_update_chase_path(delta, player_state)
		_follow_move_path(delta, speed)
		_perf_end("путь погони", chase_started)
	_world_audio().set_running(_desired_position != position_before)
	_sync_accumulator += delta
	if _movement_pending and _sync_accumulator >= 0.18:
		_sync_accumulator = 0.0
		_send_world_sync()
		queue_redraw()
	elif _sync_accumulator >= _sync_interval(player_state):
		_sync_accumulator = 0.0
		_send_world_sync()
	_check_city_entrance()


# Пока кто-то в замахе или откате (герой или моб в последнем снимке), снимки идут чаще, иначе удар
# видно с задержкой до секунды и анимация атаки не совпадает с уроном.
func _sync_interval(player_state: Dictionary) -> float:
	if _ws_ready:
		return WS_SYNC_SECONDS
	if float(player_state.get("windup", 0.0)) > 0.0 or float(player_state.get("backswing", 0.0)) > 0.0:
		return COMBAT_SYNC_SECONDS
	for mob_variant in GameSession.world_snapshot.get("mobs", []):
		if mob_variant is Dictionary and (float(mob_variant.get("windup", 0.0)) > 0.0 or float(mob_variant.get("backswing", 0.0)) > 0.0):
			return COMBAT_SYNC_SECONDS
	return IDLE_SYNC_SECONDS


# Скорость ходьбы: снимок мира задаёт move_speed; без снимка (Экономика) — формула Python get_move_speed с множителем груза.
func _move_speed(player_state: Dictionary) -> float:
	if not _economy_map or player_state.has("move_speed"):
		return float(player_state.get("move_speed", 120.0))
	return PROFILE_RULES_SCRIPT.move_speed_for(
		PROFILE_RULES_SCRIPT.effective_stats(GameSession.character),
		PROFILE_RULES_SCRIPT.character_movement_multiplier(GameSession.character),
	)


func _keyboard_movement() -> Vector2:
	# Во Front Line герой управляется только мышью, как в Dota 2: клавиши движения отключены.
	if _is_front_line_world():
		return Vector2.ZERO
	var movement := Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	movement += Vector2(
		float(Input.is_key_pressed(KEY_D)) - float(Input.is_key_pressed(KEY_A)),
		float(Input.is_key_pressed(KEY_S)) - float(Input.is_key_pressed(KEY_W)),
	)
	return movement.limit_length(1.0)


func _update_chase_path(delta: float, player_state: Dictionary) -> void:
	if _selected_mob_id.is_empty():
		_idle_orders(player_state)
		return
	var mob := _find_mob(_selected_mob_id)
	if mob.is_empty():
		_selected_mob_id = ""
		_clear_move_path()
		_wants_acquire = true
		_idle_orders(player_state)
		return
	# Удержание (H): герой не идёт к цели, бьёт только то, что в дальности.
	if _hold_position:
		_clear_move_path()
		return
	# Как в Dota 2: во время замаха герой стоит, после выстрела (откат) может идти к цели дальше.
	if float(player_state.get("windup", 0.0)) > 0.0:
		_clear_move_path()
		return
	var mob_position := Vector2(float(mob.get("x", 0.0)), float(mob.get("y", 0.0)))
	if _distance_to_mob_body(mob_position, mob) <= maxf(float(player_state.get("reach", 0.0)), 0.0):
		_clear_move_path()
		return
	_repath_timer -= delta
	if _repath_timer <= 0.0:
		_repath_timer = PLAYER_REPATH_INTERVAL
		var goal := _chase_goal(mob_position, mob, float(player_state.get("reach", 0.0)))
		if _move_path.is_empty() or goal.distance_to(_chase_goal_planned) > CHASE_REPLAN_DISTANCE_PX:
			_chase_goal_planned = goal
			_move_path = _collision.find_path(_desired_position, goal, _dynamic_rects(_chase_block_id()))
			_path_stall = 0.0


# Во Front Line путь ведёт не в центр моба: там часто стоит сосед или препятствие, и путь пустой.
# Герой идёт на свободную точку у тела моба со стороны героя, на дистанции удара.
func _chase_goal(mob_position: Vector2, mob: Dictionary, reach: float) -> Vector2:
	var to_hero := _desired_position - mob_position
	if not _is_front_line_world() or to_hero.length() <= 0.001:
		return mob_position
	var hull := WORLD_COLLISION_SCRIPT.FRONT_LINE_MOB_HULL_RADIUS
	if bool(mob.get("is_boss", false)):
		hull *= WORLD_COLLISION_SCRIPT.FRONT_LINE_BOSS_SCALE
	var stand_distance := maxf(hull + maxf(reach, 0.0) * 0.75, CHASE_MIN_STAND_PX)
	var rects := _dynamic_rects(str(mob.get("id", "")))
	for turn in [0.0, 0.5, -0.5, 1.0, -1.0, 1.5, -1.5]:
		var candidate := mob_position + Vector2.from_angle(to_hero.angle() + turn) * stand_distance
		if not _collision.point_blocked(candidate, rects):
			return candidate
	return mob_position


func _chase_block_id() -> String:
	return "" if _is_front_line_world() else _selected_mob_id


func _find_mob(mob_id: String) -> Dictionary:
	for mob_variant in GameSession.world_snapshot.get("mobs", []):
		if mob_variant is Dictionary and str(mob_variant.get("id", "")) == mob_id and str(mob_variant.get("state", "")) != "dead":
			return mob_variant
	return {}


# Front Line: расстояние от центра героя до края круглого тела моба, как front_line/server/combat.py attack_distance_px.
# Остальные режимы сохраняют прямоугольник спрайта.
# Круг дальности при зажатом Alt и полёт стрел/снарядов героя Front Line. Стрелы приходят в снимке
# (player.projectiles), полёт считается по локальным часам от первого кадра, в котором стрела видна.
const PROJECTILE_ARROW_LENGTH := 18.0
const PROJECTILE_ORB_RADIUS := 6.0
const PROJECTILE_CHEST_OFFSET := 18.0
# Радиус взрыва мага: 50 ед. = 16 px (front_line/server/combat.py MAGE_AREA_RADIUS_UNITS).
const PROJECTILE_AREA_PX := 16.0
const EXPLOSION_SECONDS := 0.35
# Снаряд, который не попал за это время, пропадает (совпадает с PROJECTILE_MAX_SECONDS на сервере).
const SHOT_MAX_SECONDS := 3.0
var _cursor_kind_shown := ""
var _cursor_textures := {}
# Полёты стрел и сгустков: id -> старт по времени, путь, цель. _shots_done — уже отыгранные id.
var _shots := {}
var _shots_done := {}
var _explosions: Array = []


# Отладка настройки режима: постоянно видны контейнеры и радиусы атаки.
# Зелёный прямоугольник — тело для столкновений (у героя ноги, у моба тело блокировки), голубой круг — радиус атаки героя,
# красный круг — радиус атаки моба. Размеры в мировых единицах (тайл 16 px).
const DEBUG_CONTAINERS := true

func _draw_debug_containers(player_state: Dictionary, mobs: Array) -> void:
	if not DEBUG_CONTAINERS or not _is_front_line_world():
		return
	var feet: Array = _collision.feet_rect(_desired_position.x, _desired_position.y)
	draw_rect(Rect2(feet[0], feet[1], feet[2], feet[3]), Color(0.2, 1.0, 0.3, 0.95), false, 1.0)
	var reach := float(player_state.get("reach", 0.0))
	if reach > 0.0:
		draw_arc(_desired_position, reach, 0.0, TAU, 72, Color(0.35, 0.85, 1.0, 0.8), 1.0)
	for mob_variant in mobs:
		if not mob_variant is Dictionary or str(mob_variant.get("state", "")) == "dead":
			continue
		var mob: Dictionary = mob_variant
		var mob_x := float(mob.get("x", 0.0))
		var mob_y := float(mob.get("y", 0.0))
		var body: Array = WORLD_COLLISION_SCRIPT.front_line_mob_rect(mob_x, mob_y, bool(mob.get("is_boss", false)))
		draw_rect(Rect2(body[0], body[1], body[2], body[3]), Color(0.2, 1.0, 0.3, 0.95), false, 1.0)
		var mob_reach := float(mob.get("attack_range_px", 0.0))
		if mob_reach > 0.0:
			draw_arc(Vector2(mob_x, mob_y), mob_reach, 0.0, TAU, 48, Color(1.0, 0.3, 0.3, 0.8), 1.0)


func _draw_front_line_range_and_shots(player_state: Dictionary, mobs: Array, now_sec: float) -> void:
	if not _is_front_line_world():
		return
	# Радиус атаки героя рисуется постоянно (см. _draw_debug_containers).
	# Снаряды из снимка: если события выстрела не пришло (потеряно или снимок раньше), снаряд стартует с его позиции.
	for projectile_variant in player_state.get("projectiles", []):
		if not projectile_variant is Dictionary:
			continue
		var projectile: Dictionary = projectile_variant
		var snapshot_id := int(projectile.get("id", 0))
		if _shots.has(snapshot_id) or _shots_done.has(snapshot_id):
			continue
		_shots[snapshot_id] = _new_shot(projectile, now_sec)
	for shot_id in _shots.keys():
		var shot: Dictionary = _shots[shot_id]
		if now_sec - float(shot["born"]) > SHOT_MAX_SECONDS:
			_shots.erase(shot_id)
			continue
		# Снаряд летит к текущей позиции цели с собственной скоростью, как на сервере.
		var pos: Vector2 = shot["pos"]
		var target := _shot_target_position(str(shot["target"]), mobs, shot["last"])
		shot["last"] = target
		var dt := clampf(now_sec - float(shot["last_time"]), 0.0, 0.1)
		shot["last_time"] = now_sec
		var to_target := target - pos
		var distance := to_target.length()
		if distance > 0.0:
			pos += to_target / distance * minf(float(shot["speed"]) * dt, distance)
		shot["pos"] = pos
		var direction := to_target.normalized() if distance > 0.0 else Vector2.RIGHT
		if str(shot["kind"]) == "orb":
			draw_circle(pos, PROJECTILE_ORB_RADIUS, Color(0.5, 0.75, 1.0, 0.85))
		else:
			draw_line(pos - direction * PROJECTILE_ARROW_LENGTH, pos, Color(0.92, 0.9, 0.8), 2.0)
			draw_circle(pos, 2.5, Color(0.7, 0.7, 0.7))
	var still_exploding: Array = []
	for explosion_variant in _explosions:
		var explosion: Dictionary = explosion_variant
		var age := (now_sec - float(explosion["start"])) / EXPLOSION_SECONDS
		if age >= 1.0:
			continue
		var fade := 1.0 - age
		draw_circle(explosion["pos"], PROJECTILE_AREA_PX * (0.4 + 0.6 * age), Color(0.5, 0.75, 1.0, 0.35 * fade))
		draw_arc(explosion["pos"], PROJECTILE_AREA_PX, 0.0, TAU, 32, Color(0.6, 0.85, 1.0, 0.8 * fade), 2.0)
		still_exploding.append(explosion)
	_explosions = still_exploding
	_draw_hover_highlight(mobs)


# Подсветка врага под курсором: красная рамка. Выбранная цель уже обведена жёлтым.
func _draw_hover_highlight(mobs: Array) -> void:
	var hovered := _mob_at(_screen_to_world(get_viewport().get_mouse_position()))
	if hovered.is_empty() or hovered == _selected_mob_id:
		return
	for mob_variant in mobs:
		if mob_variant is Dictionary and str(mob_variant.get("id", "")) == hovered:
			var mob_position := Vector2(float(mob_variant.get("x", 0.0)), float(mob_variant.get("y", 0.0)))
			draw_arc(mob_position, 24.0, 0.0, TAU, 24, Color(1.0, 0.3, 0.3, 0.9), 2.0)
			return


# Выстрел от события выстрела: снаряд стартует в груди героя и летит с сервера-скоростью.
func _on_projectile_event(event: Dictionary, now_sec: float) -> void:
	var shot_id := int(event.get("id", 0))
	if shot_id <= 0 or _shots.has(shot_id) or _shots_done.has(shot_id):
		return
	_shots[shot_id] = _new_shot(event, now_sec)


# Попадание с сервера: снаряд пропадает, сгусток мага взрывается в точке попадания.
func _on_projectile_hit(event: Dictionary, now_sec: float) -> void:
	var shot_id := int(event.get("id", 0))
	_shots.erase(shot_id)
	_shots_done[shot_id] = true
	if _shots_done.size() > 200:
		_shots_done.clear()
	if str(event.get("kind", "")) == "orb":
		_explosions.append({
			"pos": Vector2(float(event.get("x", 0.0)), float(event.get("y", 0.0))),
			"start": now_sec,
		})


func _new_shot(data: Dictionary, now_sec: float) -> Dictionary:
	var origin := Vector2.ZERO
	var from_array: Variant = data.get("from", null)
	if from_array is Array and from_array.size() >= 2:
		origin = Vector2(float(from_array[0]), float(from_array[1]) - PROJECTILE_CHEST_OFFSET)
	var pos_array: Variant = data.get("pos", null)
	if pos_array is Array and pos_array.size() >= 2:
		# Позиция из снимка: серверная точка ног, поднимаем к груди.
		origin = Vector2(float(pos_array[0]), float(pos_array[1]) - PROJECTILE_CHEST_OFFSET)
	return {
		"pos": origin,
		"speed": maxf(1.0, float(data.get("speed", 192.0))),
		"kind": str(data.get("kind", "")),
		"target": str(data.get("target", "")),
		"last": origin,
		"last_time": now_sec,
		"born": now_sec,
	}


func _shot_target_position(target_id: String, mobs: Array, last: Vector2) -> Vector2:
	for mob_variant in mobs:
		if mob_variant is Dictionary and str(mob_variant.get("id", "")) == target_id:
			return Vector2(float(mob_variant.get("x", 0.0)), float(mob_variant.get("y", 0.0)))
	# Выстрел моба целится в героя: его позиция из снимка.
	if target_id == str(int(GameSession.character.get("id", 0))):
		var player_state: Dictionary = GameSession.world_snapshot.get("player", {})
		return Vector2(float(player_state.get("x", last.x)), float(player_state.get("y", last.y)))
	return last


# Курсор Front Line: прицел в режиме атаки-движения (A), красный знак над врагом; иначе обычный.
func _update_front_line_cursor() -> void:
	var kind := "default"
	if _is_front_line_world() and _screen == SCREEN_MAP and _world_ready:
		if _attack_move_armed:
			kind = "attack_move"
		elif not _mob_at(_screen_to_world(get_viewport().get_mouse_position())).is_empty():
			kind = "attack"
	if kind == _cursor_kind_shown:
		return
	_cursor_kind_shown = kind
	if kind == "default":
		Input.set_custom_mouse_cursor(null)
		return
	Input.set_custom_mouse_cursor(_cursor_texture(kind), Input.CURSOR_ARROW, Vector2(12, 12))


func _cursor_texture(kind: String) -> Texture2D:
	if _cursor_textures.has(kind):
		return _cursor_textures[kind]
	var image := Image.create(24, 24, false, Image.FORMAT_RGBA8)
	image.fill(Color(0.0, 0.0, 0.0, 0.0))
	var color := Color(1.0, 0.3, 0.3, 1.0) if kind == "attack" else Color(0.95, 0.85, 0.4, 1.0)
	for index in range(4, 20):
		image.set_pixel(index, 12, color)
		image.set_pixel(12, index, color)
	var texture := ImageTexture.create_from_image(image)
	_cursor_textures[kind] = texture
	return texture


func _distance_to_mob_body(mob_position: Vector2, mob: Dictionary = {}) -> float:
	if bool(mob.get("front_line", false)):
		var body_radius := WORLD_COLLISION_SCRIPT.FRONT_LINE_MOB_HULL_RADIUS
		if bool(mob.get("is_boss", false)):
			body_radius *= WORLD_COLLISION_SCRIPT.FRONT_LINE_BOSS_SCALE
		return maxf(0.0, _desired_position.distance_to(mob_position) - body_radius)
	var half := Vector2(WORLD_COLLISION_SCRIPT.MOB_W / 2.0, WORLD_COLLISION_SCRIPT.MOB_H / 2.0)
	var nearest := Vector2(
		clampf(_desired_position.x, mob_position.x - half.x, mob_position.x + half.x),
		clampf(_desired_position.y, mob_position.y - half.y, mob_position.y + half.y),
	)
	return _desired_position.distance_to(nearest)


# Живые мобы и животные, которые персонаж не может пройти; цель погони не считается препятствием.
func _dynamic_rects(exclude_mob_id: String) -> Array:
	var rects: Array = []
	for mob_variant in GameSession.world_snapshot.get("mobs", []):
		if not mob_variant is Dictionary or str(mob_variant.get("state", "")) == "dead":
			continue
		if str(mob_variant.get("id", "")) == exclude_mob_id:
			continue
		var mob_x := float(mob_variant.get("x", 0.0))
		var mob_y := float(mob_variant.get("y", 0.0))
		if bool(mob_variant.get("front_line", false)):
			rects.append(WORLD_COLLISION_SCRIPT.front_line_mob_rect(mob_x, mob_y, bool(mob_variant.get("is_boss", false))))
		else:
			rects.append(WORLD_COLLISION_SCRIPT.mob_rect(mob_x, mob_y))
	for animal_variant in GameSession.world_snapshot.get("animals", []):
		if animal_variant is Dictionary:
			rects.append(WORLD_COLLISION_SCRIPT.animal_rect(float(animal_variant.get("x", 0.0)), float(animal_variant.get("y", 0.0))))
	return rects


func _follow_move_path(delta: float, speed: float) -> void:
	if _move_path.is_empty():
		return
	var result: Dictionary = _collision.follow_path(_desired_position, _move_path, speed * delta, _dynamic_rects(_chase_block_id()))
	if bool(result["moved"]):
		_desired_position = result["position"]
		_movement_pending = true
		_path_stall = 0.0
		queue_redraw()
	else:
		_path_stall += delta
		if _path_stall >= PLAYER_STALL_TIMEOUT:
			_clear_move_path()
	if _move_path.is_empty():
		_has_move_target = false
		if _attack_move_active and _selected_mob_id.is_empty():
			_attack_move_active = false


func _set_move_path(goal: Vector2) -> bool:
	_click_effect_world = goal
	_click_effect_timer = CLICK_EFFECT_SECONDS
	var path: Array = _collision.find_path(_desired_position, goal, _dynamic_rects(""))
	if path.is_empty():
		_clear_move_path()
		return false
	_move_path = path
	_move_target = path[path.size() - 1]
	_has_move_target = true
	_path_stall = 0.0
	return true


# Без выбранной цели: атака-движение ведёт к точке и подбирает врага. Без неё после смерти цели герой никого не выбирает.
func _idle_orders(player_state: Dictionary) -> void:
	if not _is_front_line_world() or _hold_position:
		return
	if _wants_acquire:
		_wants_acquire = false
		if not _attack_move_active:
			return
	if not _attack_move_active or float(player_state.get("windup", 0.0)) > 0.0:
		return
	if not _acquire_nearest(player_state).is_empty():
		return
	if _move_path.is_empty():
		_move_path = _collision.find_path(_desired_position, _attack_move_goal, _dynamic_rects(""))
		if _move_path.is_empty():
			_attack_move_active = false


# Ближайший живой моб в радиусе удара плюс запас; возвращает его id или пустую строку.
func _acquire_nearest(player_state: Dictionary) -> String:
	var reach := float(player_state.get("reach", 0.0))
	var best := ""
	var best_distance := INF
	for mob_variant in GameSession.world_snapshot.get("mobs", []):
		if not mob_variant is Dictionary or str(mob_variant.get("state", "")) == "dead":
			continue
		var mob_position := Vector2(float(mob_variant.get("x", 0.0)), float(mob_variant.get("y", 0.0)))
		var distance := _distance_to_mob_body(mob_position, mob_variant)
		if distance <= reach + ATTACK_MOVE_ACQUIRE_MARGIN_PX and distance < best_distance:
			best = str(mob_variant.get("id", ""))
			best_distance = distance
	if not best.is_empty():
		_selected_mob_id = best
		_clear_move_path()
		_repath_timer = 0.0
	return best


# Моб под курсором (как ЛКМ по врагу): пустая строка, если врага нет.
func _mob_at(clicked_world: Vector2) -> String:
	var click_half := CLICK_HALF_FRONT_LINE / _world_scale()
	var best := ""
	var best_distance := INF
	for mob_variant in GameSession.world_snapshot.get("mobs", []):
		if not mob_variant is Dictionary or str(mob_variant.get("state", "")) == "dead":
			continue
		var mob_position := Vector2(float(mob_variant.get("x", 0.0)), float(mob_variant.get("y", 0.0)))
		if absf(clicked_world.x - mob_position.x) <= click_half and absf(clicked_world.y - mob_position.y) <= click_half:
			var distance := clicked_world.distance_to(mob_position)
			if distance < best_distance:
				best = str(mob_variant.get("id", ""))
				best_distance = distance
	return best


# Приказ атаки: новый номер приказа отменяет замах на сервере, удержание сохраняется.
func _issue_attack(mob_id: String) -> void:
	_attack_move_armed = false
	_attack_move_active = false
	_wants_acquire = false
	_selected_mob_id = mob_id
	_harvest_target = null
	_clear_move_path()
	_repath_timer = 0.0
	_order_id += 1
	_status.text = "Цель: %s" % mob_id
	_send_order()
	_send_world_sync()
	queue_redraw()


# Приказ движения снимает удержание и атаку-движение.
func _issue_move(goal: Vector2) -> bool:
	_selected_mob_id = ""
	_attack_move_active = false
	_wants_acquire = false
	_hold_position = false
	_order_id += 1
	var moved := _set_move_path(goal)
	_send_order()
	_send_world_sync()
	queue_redraw()
	return moved


func _issue_attack_move(goal: Vector2) -> bool:
	var moved := _issue_move(goal)
	_attack_move_active = moved
	_attack_move_goal = goal
	return moved


# S: стоп — цель, путь, атака-движение и удержание сбрасываются; новый приказ отменяет замах.
func _issue_stop() -> void:
	_selected_mob_id = ""
	_attack_move_armed = false
	_attack_move_active = false
	_wants_acquire = false
	_hold_position = false
	_clear_move_path()
	_order_id += 1
	_pending_stop = true
	_status.text = "Стоп."
	_send_order()
	_send_world_sync()
	queue_redraw()


# H: удержание позиции — шаги не принимаются, бьёт то, что в дальности.
func _toggle_hold() -> void:
	_hold_position = not _hold_position
	_attack_move_armed = false
	_attack_move_active = false
	_clear_move_path()
	_status.text = "Удержание позиции." if _hold_position else "Удержание снято."
	_send_order()
	_send_world_sync()
	queue_redraw()


func _clear_move_path() -> void:
	_move_path = []
	_has_move_target = false
	_path_stall = 0.0


func _unhandled_input(event: InputEvent) -> void:
	if _exit_menu.blocks_input() or _connection_overlay.visible:
		return
	var on_map := _screen == SCREEN_MAP
	if on_map and event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_L and not _chat_panel.visible:
		_combat_log.toggle_full()
		get_viewport().set_input_as_handled()
		return
	if on_map and _combat_log.captures_keyboard():
		if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_ESCAPE:
			_combat_log.close_full()
			get_viewport().set_input_as_handled()
		return
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_ESCAPE:
		if _inventory_panel.visible:
			_toggle_inventory()
		elif _chat_panel.visible:
			_close_chat()
		elif not _town_active_id.is_empty():
			_close_town_window()
		else:
			_exit_menu.open()
		get_viewport().set_input_as_handled()
		return
	var social_ready := _screen == SCREEN_HUB or _screen == SCREEN_ROOM or (on_map and _world_ready)
	if not social_ready:
		return
	if event is InputEventKey and event.pressed and not event.echo:
		if (event.keycode == KEY_I or event.keycode == KEY_C) and not _chat_panel.visible:
			_toggle_character_profile()
			get_viewport().set_input_as_handled()
			return
		if (event.keycode == KEY_ENTER or event.keycode == KEY_KP_ENTER) and not _chat_panel.visible:
			_toggle_chat()
			get_viewport().set_input_as_handled()
			return
		if not on_map:
			return
		if not _is_front_line_world():
			if _handle_magic_preview_key(event.keycode):
				get_viewport().set_input_as_handled()
				return
			if event.keycode == KEY_R:
				_toggle_dash_aim()
				return
			var slot: int = _hotbar.key_slot(event.keycode)
			if slot >= 0:
				_hotbar.flash(slot)
				if slot == 0:
					_toggle_dash_aim()
				return
	if _profile_overlay.is_open() and event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		get_viewport().set_input_as_handled()
		return
	if not on_map:
		return
	if _is_front_line_world():
		if event is InputEventKey and event.pressed and not event.echo \
				and (event.keycode == KEY_F1 or event.keycode == KEY_SPACE):
			_camera_offset = Vector2.ZERO
			queue_redraw()
			get_viewport().set_input_as_handled()
			return
		if event is InputEventKey and event.pressed and not event.echo:
			if event.keycode == KEY_S:
				_issue_stop()
				get_viewport().set_input_as_handled()
				return
			if event.keycode == KEY_H:
				_toggle_hold()
				get_viewport().set_input_as_handled()
				return
			if event.keycode == KEY_A:
				_attack_move_armed = true
				_status.text = "Атака-движение: ЛКМ по точке или по врагу, ПКМ — отмена."
				get_viewport().set_input_as_handled()
				return
		if event is InputEventMouseButton:
			if event.button_index == MOUSE_BUTTON_MIDDLE:
				if not event.pressed or not _is_ui_point(event.position):
					_camera_dragging = event.pressed
				get_viewport().set_input_as_handled()
				return
			if event.pressed and not _is_ui_point(event.position):
				if event.button_index == MOUSE_BUTTON_WHEEL_UP:
					_set_front_line_zoom(_front_line_zoom * FRONT_LINE_CAMERA_ZOOM_STEP)
					get_viewport().set_input_as_handled()
					return
				if event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
					_set_front_line_zoom(_front_line_zoom / FRONT_LINE_CAMERA_ZOOM_STEP)
					get_viewport().set_input_as_handled()
					return
		if event is InputEventMouseMotion and _camera_dragging:
			_camera_offset -= event.relative / _front_line_zoom
			queue_redraw()
			get_viewport().set_input_as_handled()
			return
	if event is InputEventMouseButton and event.pressed and event.double_click and event.button_index == MOUSE_BUTTON_LEFT and not _is_ui_point(event.position) and _is_player_point(event.position):
		_open_profile_overlay()
		get_viewport().set_input_as_handled()
		return
	if not event is InputEventMouseButton or not event.pressed:
		return
	if event.button_index != MOUSE_BUTTON_LEFT and event.button_index != MOUSE_BUTTON_RIGHT:
		return
	if event.button_index == MOUSE_BUTTON_LEFT and _corpse_window_contains(event.position):
		_handle_corpse_window_click(event.position)
		get_viewport().set_input_as_handled()
		return
	if event.button_index == MOUSE_BUTTON_LEFT and _town_window_contains(event.position):
		_handle_town_window_click(event.position)
		get_viewport().set_input_as_handled()
		return
	if _is_ui_point(event.position):
		return
	var clicked_world := _screen_to_world(event.position)
	if _dash_aiming:
		if event.button_index == MOUSE_BUTTON_RIGHT:
			_dash_aiming = false
			_status.text = "Прицеливание рывка отменено."
			return
		_dash_aiming = false
		if clicked_world.distance_to(_desired_position) < 8.0:
			_status.text = "Для рывка выберите направление подальше."
			return
		_selected_mob_id = ""
		_clear_move_path()
		_pending_dash_target = {"x": clicked_world.x, "y": clicked_world.y}
		_status.text = "Отправляем рывок на сервер…"
		if _dash_can_start():
			_world_audio().play_dash()
		_send_world_sync()
		return
	if event.button_index == MOUSE_BUTTON_RIGHT:
		var crystal_tile := _crystal_tile_at(clicked_world)
		if crystal_tile.x >= 0 and crystal_tile.y >= 0:
			_harvest_target = [crystal_tile.x, crystal_tile.y]
			_selected_mob_id = ""
			if _start_harvest_path(crystal_tile):
				_status.text = "Добываем кристалл на клетке %d, %d." % [crystal_tile.x, crystal_tile.y]
			else:
				_harvest_target = null
				_status.text = "К кристаллу нельзя подойти."
			_send_world_sync()
			queue_redraw()
			return
		if _is_front_line_world():
			if _attack_move_armed:
				_attack_move_armed = false
				_status.text = "Атака-движение отменена."
				queue_redraw()
				return
			var enemy_id := _mob_at(clicked_world)
			if not enemy_id.is_empty():
				_issue_attack(enemy_id)
				return
		_harvest_target = null
		var ground_target := Vector2(
			clampf(clicked_world.x, 0.0, _map_tiles_w * TILE_SIZE),
			clampf(clicked_world.y, 0.0, _map_tiles_h * TILE_SIZE),
		)
		if not _issue_move(ground_target):
			_status.text = "Туда нельзя пройти."
		queue_redraw()
		return
	var selected := ""
	var front_line := _is_front_line_world()
	var click_half := (CLICK_HALF_FRONT_LINE if front_line else 18.0) / _world_scale()
	var nearest_distance := INF
	if event.button_index == MOUSE_BUTTON_LEFT and _is_front_line_world():
		var item_drop_id := _item_drop_at(clicked_world)
		if not item_drop_id.is_empty():
			_loot_item_drop(item_drop_id)
			return
	var corpse_id := _corpse_at(clicked_world)
	if corpse_id > 0:
		_selected_mob_id = ""
		_close_town_window()
		_open_corpse_window(corpse_id)
		queue_redraw()
		return
	for mob_variant in GameSession.world_snapshot.get("mobs", []):
		if not mob_variant is Dictionary or str(mob_variant.get("state", "")) == "dead":
			continue
		var mob_position := Vector2(float(mob_variant.get("x", 0.0)), float(mob_variant.get("y", 0.0)))
		var distance: float = clicked_world.distance_to(mob_position)
		var hit := distance < click_half
		if front_line:
			hit = absf(clicked_world.x - mob_position.x) <= click_half and absf(clicked_world.y - mob_position.y) <= click_half
		if hit and distance < nearest_distance:
			nearest_distance = distance
			selected = str(mob_variant.get("id", ""))
	if selected.is_empty():
		var town := _town_at(clicked_world)
		if not town.is_empty():
			_open_town_window(town)
			if event.double_click:
				_trigger_town_action()
			queue_redraw()
			return
		if _is_front_line_world():
			_close_town_window()
			_harvest_target = null
			var ground_target := Vector2(
				clampf(clicked_world.x, 0.0, _map_tiles_w * TILE_SIZE),
				clampf(clicked_world.y, 0.0, _map_tiles_h * TILE_SIZE),
			)
			var moved := _issue_attack_move(ground_target) if _attack_move_armed else _issue_move(ground_target)
			_attack_move_armed = false
			_status.text = "Двигаемся к выбранной точке." if moved else "Туда нельзя пройти."
			queue_redraw()
			return
	_close_town_window()
	if _is_front_line_world() and not selected.is_empty():
		_issue_attack(selected)
		return
	_selected_mob_id = selected
	_harvest_target = null
	_clear_move_path()
	_repath_timer = 0.0
	_status.text = "Цель: %s" % selected if not selected.is_empty() else "Цель снята."
	_send_world_sync()
	queue_redraw()


# Звук рывка играет, только если рывок запускается: те же проверки, что в _fire_dash() в Python.
func _dash_can_start() -> bool:
	var player_state: Dictionary = GameSession.world_snapshot.get("player", {})
	return not bool(player_state.get("dash_active", false)) and float(player_state.get("windup", 0.0)) <= 0.0 and float(player_state.get("dash_cooldown", 0.0)) <= 0.0


func _toggle_dash_aim() -> void:
	var player_state: Dictionary = GameSession.world_snapshot.get("player", {})
	if _dash_aiming:
		_dash_aiming = false
		_status.text = "Прицеливание рывка отменено."
	elif float(player_state.get("dash_cooldown", 0.0)) > 0.0:
		_status.text = "Рывок перезаряжается: %d сек." % int(ceil(float(player_state.get("dash_cooldown", 0.0))))
	elif bool(player_state.get("dash_active", false)) or float(player_state.get("windup", 0.0)) > 0.0:
		_status.text = "Сейчас нельзя использовать рывок."
	else:
		_dash_aiming = true
		_status.text = "Выберите ЛКМ направление рывка (Esc — отмена)."


func _sync_world() -> void:
	if _screen != SCREEN_MAP or not _exit_intent.is_empty() or GameSession.character.is_empty():
		return
	if _resync_pending:
		_request_world_resync()
	elif _world_ready:
		_send_world_sync()


func _request_world_resync() -> void:
	if _world_request_pending or GameSession.character.is_empty():
		return
	if ApiClient.request_world_json(HTTPClient.METHOD_POST, "/api/world/sync", {
		"character_id": int(GameSession.character.get("id", 0)),
		"since": int(GameSession.world_snapshot.get("seq", 0)),
		"resync": true,
	}):
		_world_request_pending = true
		_world_action = "world_resync"


func _has_known_position(player_state: Dictionary) -> bool:
	if _is_coordinate(player_state.get("x")) and _is_coordinate(player_state.get("y")):
		return true
	return _is_coordinate(GameSession.character.get("position_x")) and _is_coordinate(GameSession.character.get("position_y"))


func _is_coordinate(value: Variant) -> bool:
	return TOWER_HUB_RULES.is_coordinate(value)


func _send_world_sync() -> void:
	if GameSession.character.is_empty():
		return
	var player_state: Dictionary = GameSession.world_snapshot.get("player", {})
	if not _world_ready and not _has_known_position(player_state):
		# Персонаж без сохранённой позиции: сервер выберет точку появления в resync.
		_request_world_resync()
		return
	if not _movement_pending and not _world_ready:
		_desired_position = Vector2(
			float(player_state.get("x", GameSession.character.get("position_x", 0.0))),
			float(player_state.get("y", GameSession.character.get("position_y", 0.0))),
		)
	_sent_position = _desired_position
	var dash_target: Variant = _pending_dash_target
	if _ws_ready and _ws != null:
		# Канал WebSocket: положение и разовые действия; снимки сервер присылает сам.
		_ws.send_text(JSON.stringify({"type": "sync", "payload": {
			"x": _sent_position.x,
			"y": _sent_position.y,
			"dash_target": dash_target,
			"harvest_target": _harvest_target,
			"resync": _resync_pending,
		}}))
		_pending_dash_target = null
		_resync_pending = false
		return
	if _world_request_pending:
		return
	if _resync_pending:
		_request_world_resync()
		return
	if ApiClient.request_world_json(HTTPClient.METHOD_POST, "/api/world/sync", {
		"character_id": int(GameSession.character.get("id", 0)),
		"x": _sent_position.x,
		"y": _sent_position.y,
		"since": int(GameSession.world_snapshot.get("seq", 0)),
		"dash_target": dash_target,
		"harvest_target": _harvest_target,
	}):
		_world_request_pending = true
		_world_action = "world_sync"
		_pending_dash_target = null


# Соединение WebSocket: подключение в мире, авторизация, приём снимков и повтор после обрыва.
func _ensure_world_stream(delta: float) -> void:
	if _ws != null:
		_ws.poll()
		var state := _ws.get_ready_state()
		if state == WebSocketPeer.STATE_OPEN:
			if not _ws_auth_sent:
				_ws_auth_sent = true
				_ws.send_text(JSON.stringify({
					"type": "auth",
					"token": ApiClient.token,
					"character_id": int(GameSession.character.get("id", 0)),
				}))
			while _ws.get_available_packet_count() > 0:
				_handle_world_stream_text(_ws.get_packet().get_string_from_utf8())
			for command_id in _unacked_commands.keys():
				if Time.get_ticks_msec() - int(_unacked_commands[command_id]) > 2000:
					_unacked_commands.erase(command_id)
					_status.text = "Приказ не подтверждён сервером."
		elif state == WebSocketPeer.STATE_CLOSED:
			_close_world_stream()
			_ws_retry = 5.0
		return
	_ws_retry = maxf(0.0, _ws_retry - delta)
	if _ws_retry > 0.0 or not _world_ready or _screen != SCREEN_MAP or GameSession.character.is_empty():
		return
	_ws = WebSocketPeer.new()
	if _ws.connect_to_url(_world_stream_url()) != OK:
		_close_world_stream()
		_ws_retry = 5.0


func _world_stream_url() -> String:
	var base := ApiClient.base_url
	if base.begins_with("https://"):
		base = "wss://" + base.substr(8)
	elif base.begins_with("http://"):
		base = "ws://" + base.substr(7)
	return base + WORLD_STREAM_PATH


func _close_world_stream() -> void:
	if _ws != null:
		_ws.close()
	_ws = null
	_ws_ready = false
	_ws_auth_sent = false


func _handle_world_stream_text(text: String) -> void:
	var parsed: Variant = JSON.parse_string(text)
	if not parsed is Dictionary:
		return
	match str(parsed.get("type", "")):
		"ready":
			_ws_ready = true
		"snapshot":
			_dispatch_api_result("world_sync", true, parsed.get("data", {}))
		"ack":
			_unacked_commands.erase(int(parsed.get("id", -1)))
		"error":
			if parsed.has("id"):
				# Ошибка команды: соединение остаётся, сообщаем игроку.
				_unacked_commands.erase(int(parsed.get("id", -1)))
				_status.text = str(parsed.get("error", ""))
				return
			_status.text = str(parsed.get("error", ""))
			_close_world_stream()
			_ws_retry = 5.0


func _send_order() -> void:
	if GameSession.character.is_empty():
		return
	var body := {
		"character_id": int(GameSession.character.get("id", 0)),
		"attack_target": _selected_mob_id if not _selected_mob_id.is_empty() else null,
		"order_id": _order_id,
		"hold": _hold_position,
		"stop": _pending_stop,
		"allocate_stats": _pending_stat_allocations.duplicate(),
	}
	_pending_stop = false
	_pending_stat_allocations.clear()
	if _ws_ready and _ws != null:
		_command_id += 1
		_unacked_commands[_command_id] = Time.get_ticks_msec()
		_ws.send_text(JSON.stringify({"type": "command", "id": _command_id, "payload": body}))
		return
	ApiClient.request_command("/api/world/command", body)


# Сжатый снимок: постоянные поля моба приходят один раз, дальше только меняющиеся. Складываем их по id.
func _expand_world_snapshot(payload: Variant) -> Variant:
	if not payload is Dictionary or not payload.get("mobs") is Array:
		return payload
	var expanded: Array = []
	var seen := {}
	for entry_variant in payload["mobs"]:
		if not entry_variant is Dictionary:
			continue
		var entry: Dictionary = entry_variant
		var mob_id := str(entry.get("id", ""))
		if bool(entry.get("compact", false)):
			var base: Variant = _mob_static.get(mob_id)
			if not base is Dictionary:
				# Постоянных полей нет (например, после переподключения): запросим полный снимок.
				_resync_pending = true
				continue
			var merged: Dictionary = (base as Dictionary).duplicate()
			merged.merge(entry, true)
			merged.erase("compact")
			expanded.append(merged)
		else:
			_mob_static[mob_id] = entry.duplicate()
			expanded.append(entry)
		seen[mob_id] = true
	for cached_id in _mob_static.keys():
		if not seen.has(cached_id):
			_mob_static.erase(cached_id)
	var result: Dictionary = (payload as Dictionary).duplicate()
	result["mobs"] = expanded
	return result


func _crystal_tile_at(world_position: Vector2) -> Vector2i:
	var tile := Vector2i(floori(world_position.x / TILE_SIZE), floori(world_position.y / TILE_SIZE))
	for crystal in _crystal_tiles:
		if crystal is Array and crystal.size() >= 2 and int(crystal[0]) == tile.x and int(crystal[1]) == tile.y:
			return tile
	return Vector2i(-1, -1)


func _start_harvest_path(tile: Vector2i) -> bool:
	if _is_adjacent_to_crystal(tile):
		_clear_move_path()
		return true
	for neighbor in _crystal_neighbor_tiles(tile):
		if _set_move_path(Vector2((neighbor.x + 0.5) * TILE_SIZE, (neighbor.y + 0.5) * TILE_SIZE)):
			return true
	_clear_move_path()
	return false


func _is_adjacent_to_crystal(tile: Vector2i) -> bool:
	var player_tile := _player_tile()
	return maxi(absi(player_tile.x - tile.x), absi(player_tile.y - tile.y)) == 1


func _player_tile() -> Vector2i:
	return Vector2i(floori(_desired_position.x / TILE_SIZE), floori(_desired_position.y / TILE_SIZE))


# Соседние клетки кристалла, ближе к персонажу — раньше; первая достижимая становится целью пути.
func _crystal_neighbor_tiles(tile: Vector2i) -> Array[Vector2i]:
	var player_tile := _player_tile()
	var neighbors: Array[Vector2i] = []
	for dy in [-1, 0, 1]:
		for dx in [-1, 0, 1]:
			if dx != 0 or dy != 0:
				neighbors.append(Vector2i(tile.x + dx, tile.y + dy))
	neighbors.sort_custom(func(a: Vector2i, b: Vector2i) -> bool:
		return (a - player_tile).length_squared() < (b - player_tile).length_squared()
	)
	return neighbors


func _corpse_at(world_position: Vector2) -> int:
	for corpse in GameSession.world_snapshot.get("corpses", []):
		if not corpse is Dictionary:
			continue
		var corpse_position := Vector2(float(corpse.get("x", 0.0)), float(corpse.get("y", 0.0)))
		if Rect2(corpse_position - Vector2(14.0, 20.0), Vector2(28.0, 20.0)).has_point(world_position):
			return int(corpse.get("id", 0))
	return 0


func _is_front_line_world() -> bool:
	return str(GameSession.world.get("mode", "")) == "front_line"


func _item_drop_at(world_position: Vector2) -> String:
	for drop in GameSession.world_snapshot.get("item_drops", []):
		if not drop is Dictionary:
			continue
		var drop_position := Vector2(float(drop.get("x", 0.0)), float(drop.get("y", 0.0)))
		if Rect2(drop_position - Vector2(12.0, 12.0), Vector2(24.0, 24.0)).has_point(world_position):
			return str(drop.get("id", ""))
	return ""


func _loot_item_drop(drop_id: String) -> void:
	if drop_id.is_empty() or not _pending_action.is_empty():
		return
	_pending_action = "item_drop_loot"
	_status.text = "Подбираем предмет…"
	ApiClient.request_json(HTTPClient.METHOD_POST, "/api/world/item-drop/loot", {
		"character_id": int(GameSession.character.get("id", 0)),
		"drop_id": drop_id,
	})


func _update_corpse_window(corpses: Variant) -> void:
	if _corpse_window_id <= 0:
		return
	if corpses is Array:
		for corpse in corpses:
			if corpse is Dictionary and int(corpse.get("id", 0)) == _corpse_window_id:
				return
	_corpse_window_id = 0


func _corpse_by_id(corpse_id: int) -> Dictionary:
	for corpse in GameSession.world_snapshot.get("corpses", []):
		if corpse is Dictionary and int(corpse.get("id", 0)) == corpse_id:
			return corpse
	return {}


func _corpse_distance_tiles(corpse: Dictionary) -> float:
	var corpse_position := Vector2(float(corpse.get("x", 0.0)), float(corpse.get("y", 0.0)))
	return corpse_position.distance_to(_desired_position) / TILE_SIZE


func _open_corpse_window(corpse_id: int) -> void:
	var corpse := _corpse_by_id(corpse_id)
	if corpse.is_empty():
		return
	if _corpse_distance_tiles(corpse) > CORPSE_LOOT_RANGE_TILES:
		_status.text = "Подойдите ближе к трупу"
		return
	_corpse_window_id = corpse_id


func _loot_corpse_window() -> void:
	if _corpse_window_id <= 0 or not _pending_action.is_empty():
		return
	_pending_action = "corpse_loot"
	_status.text = "Забираем монеты с трупа…"
	ApiClient.request_json(HTTPClient.METHOD_POST, "/api/world/corpse/loot", {
		"character_id": int(GameSession.character.get("id", 0)),
		"corpse_id": _corpse_window_id,
	})


func _corpse_window_rects() -> Dictionary:
	var k := TOWER_WORLD_SCALE
	var window_size := CORPSE_WINDOW_SIZE_PY * k
	var window := Rect2(size * 0.5 - window_size * 0.5, window_size)
	var close := Rect2(window.end.x - 36.0 * k, window.position.y + 10.0 * k, 26.0 * k, 26.0 * k)
	var loot_size := Vector2(200.0, 40.0) * k
	var loot := Rect2(Vector2(window.get_center().x - loot_size.x * 0.5, window.end.y - 16.0 * k - loot_size.y), loot_size)
	return {"window": window, "close": close, "loot": loot}


func _corpse_window_contains(point: Vector2) -> bool:
	return _corpse_window_id > 0 and (_corpse_window_rects()["window"] as Rect2).has_point(point)


func _handle_corpse_window_click(point: Vector2) -> void:
	var rects := _corpse_window_rects()
	if (rects["close"] as Rect2).has_point(point):
		_corpse_window_id = 0
	elif (rects["loot"] as Rect2).has_point(point):
		_loot_corpse_window()
	queue_redraw()


func _tiles_word(count: int) -> String:
	var last_two := count % 100
	if last_two >= 11 and last_two <= 14:
		return "тайлов"
	var last := count % 10
	if last == 1:
		return "тайл"
	if last >= 2 and last <= 4:
		return "тайла"
	return "тайлов"


func _box_style(fill: Color, border: Color, radius_py: float) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = fill
	style.border_color = border
	style.set_border_width_all(1)
	style.set_corner_radius_all(roundi(radius_py * TOWER_WORLD_SCALE))
	return style


func _draw_text_at(text: String, top_left: Vector2, font_size: int, color: Color) -> void:
	draw_string(ThemeDB.fallback_font, Vector2(top_left.x, top_left.y + font_size * 0.9), text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, color)


func _draw_corpse_window(corpse: Dictionary) -> void:
	var k := TOWER_WORLD_SCALE
	var rects := _corpse_window_rects()
	var window: Rect2 = rects["window"]
	var mouse := get_local_mouse_position()
	draw_style_box(_box_style(Color8(15, 20, 28, 245), Color8(220, 185, 60), 8.0), window)
	_draw_text_at("Труп игрока", window.position + Vector2(14.0, 12.0) * k, roundi(20.0 * k), Color8(255, 225, 120))
	var close: Rect2 = rects["close"]
	draw_style_box(_box_style(Color8(180, 50, 50) if close.has_point(mouse) else Color8(45, 30, 35), Color8(220, 100, 100), 4.0), close)
	var inset := close.size * 0.3
	draw_line(close.position + inset, close.end - inset, Color.WHITE, 1.5)
	draw_line(Vector2(close.end.x - inset.x, close.position.y + inset.y), Vector2(close.position.x + inset.x, close.end.y - inset.y), Color.WHITE, 1.5)
	draw_line(window.position + Vector2(14.0, 44.0) * k, Vector2(window.end.x - 14.0 * k, window.position.y + 44.0 * k), Color8(50, 65, 80), 1.0)
	var distance := roundi(_corpse_distance_tiles(corpse))
	var wallet := CURRENCY_FORMAT.format_amount(CURRENCY_FORMAT.total_copper(GameSession.character))
	_draw_text_at("В трупе монет: %s" % CURRENCY_FORMAT.format_amount(int(corpse.get("copper", 0))), window.position + Vector2(14.0, 56.0) * k, roundi(16.0 * k), Color8(255, 225, 120))
	_draw_text_at("Ваш кошелёк: %s" % wallet, window.position + Vector2(14.0, 82.0) * k, roundi(16.0 * k), Color8(200, 220, 240))
	_draw_text_at("Расстояние: %d %s" % [distance, _tiles_word(distance)], window.position + Vector2(14.0, 108.0) * k, roundi(16.0 * k), Color8(160, 175, 190))
	var loot: Rect2 = rects["loot"]
	var loot_fill := Color8(110, 190, 255) if loot.has_point(mouse) else Color8(40, 90, 50)
	draw_style_box(_box_style(loot_fill, loot_fill, 10.0), loot)
	_draw_text_centered("Забрать все", Vector2(loot.get_center().x, loot.get_center().y + 4.0), roundi(16.0 * k), Color.WHITE)


func _build_combat_log() -> void:
	_combat_log = COMBAT_LOG_SCRIPT.new()
	_combat_log.visible = false
	add_child(_combat_log)


func _build_hotbar() -> void:
	_hotbar = HOTBAR_SCRIPT.new()
	_hotbar.visible = false
	add_child(_hotbar)


func _build_server_status_hud() -> void:
	_server_status_hud = SERVER_STATUS_HUD_SCRIPT.new()
	_server_status_hud.restart_requested.connect(_on_exit_restart_requested)
	ConnectionGuard.status_received.connect(_server_status_hud.apply_status)
	add_child(_server_status_hud)


func _on_exit_restart_requested() -> void:
	_start_exit("restart")


func _restart_client() -> void:
	OS.create_process(OS.get_executable_path(), OS.get_cmdline_args())
	get_tree().quit()


func _build_exit_menu() -> void:
	_exit_menu = EXIT_MENU_SCRIPT.new()
	_exit_menu.lobby_requested.connect(_on_exit_lobby_requested)
	_exit_menu.quit_requested.connect(_on_exit_quit_requested)
	_exit_menu.quit_ready.connect(_on_exit_quit_ready)
	add_child(_exit_menu)


func _on_close_requested() -> void:
	if _connection_overlay.visible:
		get_tree().quit()
		return
	if _exit_intent.is_empty() and not _exit_menu.is_quitting():
		_exit_menu.open()


func _on_exit_lobby_requested() -> void:
	_start_exit("lobby")


func _on_exit_quit_requested() -> void:
	if _server_unreachable:
		get_tree().quit()
		return
	_start_exit("quit")


func _on_exit_quit_ready() -> void:
	ConnectionGuard.stop()
	get_tree().quit()


func _start_exit(intent: String) -> void:
	if not _exit_intent.is_empty():
		return
	_exit_intent = intent
	_request_queue.clear()
	if intent == "quit":
		_exit_menu.begin_quit()
	else:
		_exit_menu.set_status("Сохраняем состояние…")
	_exit_queued = true
	_process_exit_queue()


func _process_exit_queue() -> void:
	if not _exit_queued or not _pending_action.is_empty() or _world_request_pending:
		return
	_exit_queued = false
	_run_exit_step()


# Перед выходом сохраняем зону текущего экрана, как checkpoint_for_scene в Python, и только потом покидаем мир.
func _run_exit_step() -> void:
	_close_world_stream()
	var character_id := int(GameSession.character.get("id", 0))
	if character_id > 0 and _screen != SCREEN_LOADING:
		_pending_action = "exit_checkpoint"
		ApiClient.request_json(HTTPClient.METHOD_PUT, _character_path(), _checkpoint_body())
		return
	_send_world_leave()


func _send_world_leave() -> void:
	var character_id := int(GameSession.character.get("id", 0))
	if character_id > 0:
		_pending_action = "world_leave"
		ApiClient.request_json(HTTPClient.METHOD_POST, "/api/world/leave", {"character_id": character_id})
		return
	_pending_action = "world_leave_disconnect"
	ApiClient.request_json(HTTPClient.METHOD_POST, "/api/sessions/disconnect")


func _send_world_disconnect() -> void:
	_pending_action = "world_leave_disconnect"
	ApiClient.request_json(HTTPClient.METHOD_POST, "/api/sessions/disconnect", {
		"character_id": int(GameSession.character.get("id", 0)),
	})


func _fail_exit(message: String) -> void:
	var intent := _exit_intent
	_exit_intent = ""
	_exit_queued = false
	if intent == "quit":
		_server_unreachable = true
		_exit_menu.open("Сервер недоступен: %s. Нажмите «Покинуть игру», чтобы закрыть клиент" % message)
	else:
		_exit_menu.open(message)


func _on_connection_lost(seconds_remaining: int) -> void:
	_connection_overlay.visible = true
	_connection_message.text = "Связь с сервером потеряна. Переподключаемся и синхронизируем персонажа."
	_connection_counter.text = "%d сек." % seconds_remaining


func _on_countdown_updated(seconds_remaining: int) -> void:
	if _connection_overlay.visible:
		_connection_counter.text = "%d сек." % seconds_remaining


func _on_connection_restored(character: Dictionary) -> void:
	GameSession.select_character(character)
	if _screen != SCREEN_MAP:
		_connection_overlay.visible = false
		_request_when_idle("character", HTTPClient.METHOD_GET, _character_path())
		return
	_connection_message.text = "Связь восстановлена. Получаем актуальное состояние мира…"
	_connection_counter.text = ""
	_resync_pending = true
	_movement_pending = false
	_selected_mob_id = ""
	_clear_move_path()
	_pending_dash_target = null
	_dash_aiming = false
	if _pending_action.is_empty():
		_request_world_resync()
	elif _world_sync_timer.is_stopped():
		_world_sync_timer.start()


func _on_client_outdated() -> void:
	_connection_overlay.visible = true
	_connection_message.text = "Сервер обновлён. Эта версия клиента устарела; закройте её и запустите актуальную."
	_connection_counter.text = ""
	_action_button.visible = true


func _on_session_invalid(message: String) -> void:
	_connection_overlay.visible = true
	_connection_message.text = message
	_connection_counter.text = ""
	_login_button.visible = true


func _on_connection_expired() -> void:
	get_tree().quit()


func _close_for_reload() -> void:
	get_tree().quit()


func _return_to_login() -> void:
	ConnectionGuard.stop()
	ApiClient.set_server_url(GameSession.hub_url)
	GameSession.clear()
	ApiClient.token = ""
	_world_audio().fade_out_for_transition()
	SCENE_TRANSITION.run(get_tree(), func() -> void: get_tree().change_scene_to_file("res://scenes/main.tscn"))


func _on_api_completed(success: bool, payload: Variant) -> void:
	var api_started := _perf_begin()
	var api_action := _pending_action
	_handle_api_result(success, payload)
	_flush_request_queue()
	_perf_log_slow("ответ сервера (%s)" % api_action, api_started)


func _handle_api_result(success: bool, payload: Variant) -> void:
	var action := _pending_action
	_pending_action = ""
	_dispatch_api_result(action, success, payload)


func _on_world_request_completed(success: bool, payload: Variant) -> void:
	var world_started := _perf_begin()
	var action := _world_action
	_world_action = ""
	_world_request_pending = false
	_dispatch_api_result(action, success, payload)
	_perf_log_slow("ответ мира (%s)" % action, world_started)


func _on_command_completed(success: bool, payload: Variant) -> void:
	if not success:
		_status.text = str(payload)


func _dispatch_api_result(action: String, success: bool, payload: Variant) -> void:
	if not success:
		if not _exit_intent.is_empty() and action in ["exit_checkpoint", "world_leave", "world_leave_disconnect"]:
			if _economy_map and action == "world_leave":
				_send_world_disconnect()
				return
			_fail_exit(str(payload))
			return
		# Ошибки обновления города молчат, как в Python (_refresh_city_visual_state).
		if action == "equipment_load" or action in ["city_population", "city_terrain"]:
			return
		if _economy_map and action in ["world_sync", "world_resync"]:
			_handle_economy_sync_failure(action, str(payload))
			return
		if action in ["inventory_load", "inventory_action", "storage_load", "storage_transfer"]:
			_set_inventory_message(str(payload), action == "inventory_action")
			if action == "inventory_action":
				_inventory_grid.resolve_action(false)
		elif action == "front_line_draft_submit":
			_status.text = str(payload)
			if _front_line_draft_status != null and is_instance_valid(_front_line_draft_status):
				_front_line_draft_status.text = str(payload)
			if _front_line_draft_view != null and is_instance_valid(_front_line_draft_view):
				_front_line_draft_view.set_submit_enabled(true)
		elif action.begins_with("chat_"):
			_chat_status.text = str(payload)
		else:
			_status.text = str(payload)
		if action == "world_resync":
			_connection_message.text = "Связь восстановлена. Повторно запрашиваем состояние мира…"
		if action == "world_sync" or action == "world_resync":
			if _world_sync_timer.is_stopped():
				_world_sync_timer.start()
		if action.begins_with("chat_"):
			if _chat_timer.is_stopped():
				_chat_timer.start()
		return
	match action:
		"character":
			if not payload is Dictionary or not payload.get("character") is Dictionary:
				_status.text = "Сервер вернул некорректное состояние персонажа."
				return
			GameSession.select_character(payload["character"])
			_render_character_profile()
			if _screen != SCREEN_LOADING:
				return
			_enter_screen(SCREEN_MAP if _economy_map else TOWER_HUB_RULES.entry_zone(GameSession.world, GameSession.character))
		"terrain":
			if not payload is Dictionary or not payload.get("terrain") is Dictionary:
				_status.text = "Сервер вернул некорректные данные карты."
				return
			_apply_terrain(payload["terrain"])
			_pending_action = ""
			if _economy_map:
				_world_ready = true
				_status.text = ""
			_send_world_sync()
			_chat_timer.start()
		"city_population":
			if payload is Dictionary and payload.get("population") is Dictionary:
				_apply_city_population(payload["population"])
		"city_terrain":
			if payload is Dictionary and payload.get("terrain") is Dictionary:
				_apply_terrain(payload["terrain"])
		"terrain_refresh":
			if not payload is Dictionary or not payload.get("terrain") is Dictionary:
				_status.text = "Сервер вернул некорректные данные обновлённой карты."
				_world_sync_timer.start()
				return
			_apply_terrain(payload["terrain"])
			_world_sync_timer.start()
		"world_sync", "world_resync":
			payload = _expand_world_snapshot(payload)
			if not payload is Dictionary or not payload.get("player") is Dictionary:
				_status.text = "Сервер вернул некорректный снимок мира."
				if action == "world_resync":
					_resync_pending = true
					_world_sync_timer.start()
				return
			var is_resync := action == "world_resync"
			_economy_sync_failed = false
			var first_snapshot := not _world_ready
			if is_resync:
				var authoritative_player: Dictionary = payload["player"]
				_desired_position = Vector2(
					float(authoritative_player.get("x", 0.0)),
					float(authoritative_player.get("y", 0.0)),
				)
				_sent_position = _desired_position
				_movement_pending = false
				_resync_pending = false
				_clear_move_path()
			elif not bool(payload.get("accepted", false)):
				var rejected_player: Dictionary = payload["player"]
				var server_position := Vector2(
					float(rejected_player.get("x", _sent_position.x)),
					float(rejected_player.get("y", _sent_position.y)),
				)
				if _desired_position.distance_to(server_position) > RECONCILE_SNAP_PX:
					_desired_position = server_position
					_has_correction = false
				else:
					_correction_target = server_position
					_has_correction = true
				_movement_pending = false
				_clear_move_path()
				_repath_timer = 0.0
			elif first_snapshot:
				var initial_player: Dictionary = payload["player"]
				_desired_position = Vector2(float(initial_player.get("x", 0.0)), float(initial_player.get("y", 0.0)))
				_movement_pending = false
			elif _reconcile_front_line_draft_spawn(payload):
				pass
			else:
				_movement_pending = _desired_position.distance_to(_sent_position) > 1.0
			GameSession.update_world_snapshot(payload)
			_sync_front_line_hero_type(payload.get("player", {}))
			var harvest_target_before_sync: Variant = _harvest_target
			var harvest_state: Variant = payload["player"].get("harvest")
			if harvest_state is Dictionary:
				_harvest_target = [int(harvest_state.get("x", -1)), int(harvest_state.get("y", -1))]
			elif _harvest_target != null:
				_harvest_target = null
			_update_corpse_window(payload.get("corpses", []))
			_world_ready = true
			_update_swing_sound(payload["player"])
			_apply_world_events(payload.get("events", []), harvest_target_before_sync)
			_update_world_status(payload)
			if is_resync:
				_connection_overlay.visible = false
				if not first_snapshot:
					_status.text = "Связь восстановлена. Состояние мира синхронизировано с сервером."
			if _terrain_loaded and _terrain_version != payload.get("terrain_version"):
				_pending_action = "terrain_refresh"
				ApiClient.request_json(HTTPClient.METHOD_GET, "/api/map/terrain")
			else:
				_world_sync_timer.start()
			queue_redraw()
		"item_drop_loot":
			_status.text = "Предмет подобран."
			_send_world_sync()
		"exit_checkpoint":
			_send_world_leave()
		"world_leave":
			_send_world_disconnect()
		"world_leave_disconnect":
			ConnectionGuard.stop()
			if _exit_intent == "quit":
				_exit_menu.mark_disconnected()
				return
			if _exit_intent == "restart":
				_restart_client()
				return
			GameSession.leave_world()
			ApiClient.set_server_url(GameSession.hub_url)
			ApiClient.token = GameSession.token
			_world_audio().fade_out_for_transition()
			SCENE_TRANSITION.run(get_tree(), func() -> void: get_tree().change_scene_to_file("res://scenes/main.tscn"))
		"chat_snapshot":
			if not payload is Dictionary or not payload.get("messages", []) is Array or not payload.get("occupants", []) is Array:
				_chat_occupants_label.text = "Сервер вернул неверные данные чата."
				return
			_chat_messages.clear()
			for message in payload["messages"]:
				if message is Dictionary:
					_chat_messages.append(message)
			_chat_occupants.clear()
			for occupant in payload["occupants"]:
				if occupant is Dictionary:
					_chat_occupants.append(occupant)
			_render_chat()
			if not _chat_timer.is_stopped():
				_chat_timer.start()
		"chat_send":
			_chat_input.clear()
			_chat_status.text = ""
			_poll_chat()
		"chat_report":
			_chat_reason_input.clear()
			_chat_status.text = "Жалоба отправлена модераторам."
			_poll_chat()
		"chat_delete":
			_chat_status.text = "Сообщение удалено модератором."
			_poll_chat()
		"chat_mute":
			_chat_status.text = "Игрок добавлен в игнор на 10 минут."
		"profile_update":
			if not payload is Dictionary or not payload.get("character") is Dictionary:
				_status.text = "Сервер вернул некорректную карточку персонажа."
				return
			GameSession.select_character(payload["character"])
			_render_character_profile()
			_status.text = "Характеристика обновлена сервером."
		"front_line_draft_submit":
			if not payload is Dictionary or not payload.get("draft") is Dictionary:
				_status.text = "Сервер вернул некорректное подтверждение драфта."
				if _front_line_draft_view != null and is_instance_valid(_front_line_draft_view):
					_front_line_draft_view.set_submit_enabled(true)
				return
			var draft: Dictionary = payload["draft"]
			if _front_line_draft_status != null and is_instance_valid(_front_line_draft_status):
				_front_line_draft_status.text = "Выбор сохранён. Игроки выбрали %d из %d. Можно изменить выбор до конца драфта." % [
					int(draft.get("players_ready", 0)),
					int(draft.get("players_total", 0)),
				]
			if _front_line_draft_view != null and is_instance_valid(_front_line_draft_view):
				_front_line_draft_view.set_submit_enabled(true)
		"corpse_loot":
			if not payload is Dictionary or not payload.get("corpses", []) is Array:
				_status.text = "Сервер вернул некорректное состояние трупов."
				return
			var currency: Variant = payload.get("currency", {})
			if currency is Dictionary:
				GameSession.character.merge(currency, true)
			var snapshot := GameSession.world_snapshot.duplicate(true)
			snapshot["corpses"] = payload["corpses"]
			GameSession.update_world_snapshot(snapshot)
			_corpse_window_id = 0
			_render_character_profile()
			_status.text = "Монеты с трупа добавлены в кошелёк."
			queue_redraw()
		"storage_load":
			if not payload is Dictionary or not payload.get("storage", []) is Array:
				_set_inventory_message("Сервер вернул некорректное содержимое сундука.")
				return
			_storage_by_type[_request_storage_type] = payload["storage"]
			_render_inventory()
			_room_view.set_status("")
			_render_social_views()
		"equipment_load":
			if not payload is Dictionary or not payload.get("equipment", {}) is Dictionary:
				return
			_inventory_state = payload.duplicate(true)
			_render_inventory()
		"inventory_load", "inventory_action", "storage_transfer":
			if not payload is Dictionary or not payload.get("inventory", []) is Array or not payload.get("equipment", {}) is Dictionary:
				_set_inventory_message("Сервер вернул некорректное состояние инвентаря.", action == "inventory_action")
				if action == "inventory_action":
					_inventory_grid.resolve_action(false)
				return
			_inventory_state = payload.duplicate(true)
			if action == "storage_transfer":
				if not payload.get("storage", []) is Array:
					_set_inventory_message("Сервер не вернул обновлённое содержимое сундука.")
					return
				_storage_by_type[_request_storage_type] = payload["storage"]
				_storage_quantity_input.clear()
			_inventory_loaded = true
			var updated_character: Variant = payload.get("character")
			if updated_character is Dictionary:
				GameSession.select_character(updated_character)
				_render_character_profile()
			_render_inventory()
			if action == "inventory_action":
				_inventory_grid.resolve_action(true)
			_render_social_views()
			if action == "inventory_action" and _screen == SCREEN_MAP:
				if _inventory_view != "backpack":
					_request_storage_state(_inventory_view)
				elif _resync_pending:
					_request_world_resync()
				else:
					_send_world_sync()


func _apply_terrain(terrain: Dictionary) -> void:
	_collision.configure(terrain)
	var map_data: Variant = terrain.get("map", {})
	if map_data is Dictionary:
		_map_tiles_w = maxi(1, int(map_data.get("tiles_w", _map_tiles_w)))
		_map_tiles_h = maxi(1, int(map_data.get("tiles_h", _map_tiles_h)))
		_terrain_version = map_data.get("version")
	var tiles: Variant = terrain.get("tiles", {})
	if tiles is Dictionary:
		_terrain_loaded = true
	else:
		_status.text = "Данные карты без слоёв terrain."
	var objects: Variant = terrain.get("objects", [])
	_map_objects = objects if objects is Array else []
	_town_objects = TOWN_RULES.town_objects(_map_objects) if _economy_map else []
	_collision.set_solid_rects(TOWN_RULES.solid_rects(_town_objects))
	var city_state: Variant = terrain.get("city_visual_state", {})
	_city_visual_state = city_state if city_state is Dictionary else {"city_level": 1, "active": false}
	_layout_city_level = TOWN_RULES.city_level(_city_visual_state)
	var crystals: Variant = terrain.get("crystals", [])
	_crystal_tiles = crystals.duplicate(true) if crystals is Array else []
	_terrain_view.configure(terrain)
	_front_line_map_view.configure(
		terrain.get("front_line_map", {}) if _is_front_line_world() else {},
	)
	_hud_view.configure_minimap(terrain)
	queue_redraw()


# Уровень и фаза города: первый запрос сразу после загрузки карты, дальше каждые 10 с (_refresh_city_visual_state в Python).
func _tick_city_visual(delta: float) -> void:
	if not _economy_map or not _world_ready or _leaving_to_city:
		return
	_city_refresh_seconds -= delta
	if _city_refresh_seconds > 0.0:
		return
	_city_refresh_seconds = CITY_VISUAL_REFRESH_SECONDS
	var character_id := int(GameSession.character.get("id", 0))
	if character_id > 0:
		_request_when_idle("city_population", HTTPClient.METHOD_GET, "/api/castle/%d/population" % character_id)


# city_upgrade; без city_level берётся castle_level. Смена уровня перечитывает терейн, как _apply_city_layout в Python.
func _apply_city_population(population: Dictionary) -> void:
	var visual: Dictionary = {}
	var upgrade: Variant = population.get("city_upgrade", {})
	if upgrade is Dictionary:
		visual = upgrade.duplicate(true)
	if not visual.has("city_level"):
		visual["city_level"] = int(population.get("castle_level", 1))
	_city_visual_state = visual
	queue_redraw()
	if TOWN_RULES.city_level(visual) != _layout_city_level:
		_request_when_idle("city_terrain", HTTPClient.METHOD_GET, "/api/map/terrain")


func _draw() -> void:
	var draw_started := _perf_begin()
	_draw_scene_frame()
	_perf_log_slow("отрисовка мира", draw_started)


func _draw_scene_frame() -> void:
	var view_size := size
	if view_size.x <= 0.0 or view_size.y <= 0.0:
		return
	draw_rect(Rect2(Vector2.ZERO, view_size), TOWER_WORLD_BACKGROUND)
	if _screen != SCREEN_MAP:
		return
	var scale_factor := _world_scale()
	var center := _camera_position()
	var screen_center := view_size * 0.5
	var offset := screen_center - center * scale_factor
	var visible := Rect2(center - screen_center / scale_factor, view_size / scale_factor)
	var hovered_town := _hovered_town_id()
	var now_msec := Time.get_ticks_msec()
	var anim_time := float(now_msec) / 1000.0
	var player_state: Dictionary = GameSession.world_snapshot.get("player", {})
	var character: Dictionary = GameSession.character
	var player := player_state.duplicate()
	player["type"] = str(player_state.get("type", character.get("type", "")))
	player["front_line"] = str(GameSession.world.get("mode", "")) == "front_line"
	var character_name := str(character.get("name", ""))
	var game_nickname := str(GameSession.user.get("game_nickname", "")).strip_edges()
	player["name"] = game_nickname if player["front_line"] and not game_nickname.is_empty() else character_name
	var front_line_state: Variant = GameSession.world_snapshot.get("front_line", {})
	player["visible"] = not player["front_line"] or not front_line_state is Dictionary \
		or bool(front_line_state.get("hero_visible", true))
	player["x"] = _desired_position.x
	player["y"] = _desired_position.y
	var mobs: Array = GameSession.world_snapshot.get("mobs", [])
	var animals: Array = GameSession.world_snapshot.get("animals", [])
	var corpses: Array = GameSession.world_snapshot.get("corpses", [])
	var item_drops: Array = GameSession.world_snapshot.get("item_drops", [])
	var moving := _player_moving_timer > 0.0

	# Мировой слой рисуется в координатах Python (пиксели, тайл 32) через преобразование камеры.
	draw_set_transform(offset, 0.0, Vector2(scale_factor, scale_factor))
	var foreground: Array = []
	if _terrain_view.is_configured():
		foreground = _terrain_view.draw(self, visible, now_msec)
	if _is_front_line_world():
		_front_line_map_view.draw(self, visible)
	_draw_city_objects(visible, hovered_town, _town_active_id)
	if _is_front_line_world():
		_draw_front_line_buildings(GameSession.world_snapshot.get("front_line", {}))
	_entity_view.draw_corpses(self, corpses, _corpse_window_id, visible)
	if _is_front_line_world():
		for drop in item_drops:
			if not drop is Dictionary:
				continue
			var drop_position := Vector2(float(drop.get("x", 0.0)), float(drop.get("y", 0.0)))
			draw_circle(drop_position, 8.0, Color8(255, 215, 72))
			draw_circle(drop_position, 3.0, Color8(255, 250, 210))
			draw_string(
				ThemeDB.fallback_font,
				drop_position + Vector2(12.0, 4.0),
				str(drop.get("name", "Предмет")),
				HORIZONTAL_ALIGNMENT_LEFT,
				-1,
				12,
				Color8(255, 238, 170),
			)
	_entity_view.draw_actors(self, mobs, animals, player, _player_direction, anim_time, moving, _selected_mob_id, now_msec, foreground)
	if bool(player["visible"]):
		_draw_other_players()
	if _has_move_target:
		draw_arc(_move_target, 8.0, 0.0, TAU, 24, Color(0.4, 0.86, 0.95), 2.0)
	for trail_variant in GameSession.world_snapshot.get("trails", []):
		if trail_variant is Dictionary:
			var trail_alpha := clampf(float(trail_variant.get("ttl", 0.0)) / 5.0, 0.0, 1.0)
			draw_circle(Vector2(float(trail_variant.get("x", 0.0)), float(trail_variant.get("y", 0.0))), 5.0, Color(0.38, 0.78, 0.94, trail_alpha * 0.7))
	_draw_front_line_range_and_shots(player_state, mobs, anim_time)
	_draw_debug_containers(player_state, mobs)
	draw_set_transform_matrix(Transform2D.IDENTITY)

	# Подписи, полоски и эффекты рисуются в экранных координатах; размеры Python переводятся множителем 2/3.
	var ui_scale := TOWER_WORLD_SCALE
	_draw_city_badges(offset, scale_factor, ui_scale, visible, hovered_town, _town_active_id)
	for label in _entity_view.mob_overheads(mobs, _selected_mob_id, now_msec):
		_draw_mob_label(label, offset, scale_factor, ui_scale)
	if bool(player["visible"]):
		_draw_player_label(_entity_view.player_overhead(player, _player_direction, anim_time, moving), offset, scale_factor, ui_scale)
		_draw_other_player_labels(offset, scale_factor, ui_scale)
	for label in _entity_view.corpse_overheads(corpses, _corpse_window_id, visible):
		var corpse_color := Color8(255, 215, 60) if bool(label["selected"]) else Color8(190, 190, 200)
		_draw_text_centered(str(label["text"]), offset + (label["anchor"] as Vector2) * scale_factor - Vector2(0.0, 4.0 * ui_scale), roundi(OVERHEAD_FONT_PY * ui_scale), corpse_color)
	var harvest: Variant = player_state.get("harvest")
	if TOWER_ENTITY_RULES.harvest_visible(harvest):
		var tile_center := offset + TOWER_ENTITY_RULES.harvest_center(harvest) * scale_factor
		_entity_view.draw_harvest_progress(self, harvest, tile_center, scale_factor)
	if _click_effect_timer > 0.0:
		_entity_view.draw_click_effect(self, offset + _click_effect_world * scale_factor, _click_effect_timer)
	for popup in _floating_events:
		var popup_position := offset + Vector2(float(popup.get("x", 0.0)), float(popup.get("y", 0.0))) * scale_factor
		var age_ratio := 1.0 - float(popup.get("ttl", 0.0)) / float(popup.get("duration", 1.0))
		popup_position.y -= age_ratio * 26.0 * ui_scale
		var popup_color: Color = popup.get("color", Color.WHITE)
		draw_string(ThemeDB.fallback_font, popup_position, str(popup.get("text", "")), HORIZONTAL_ALIGNMENT_CENTER, -1, 15, popup_color)

	var hud: Dictionary = _hud_view.layout(view_size)
	var level := int(player_state.get("level", character.get("level", 1)))
	var fighter := {
		"hp": float(player_state.get("hp", 0.0)),
		"max_hp": float(player_state.get("max_hp", 1.0)),
		"mp": float(player_state.get("mp", 0.0)),
		"max_mp": float(player_state.get("max_mp", 1.0)),
		"level": level,
		"xp": int(player_state.get("xp", character.get("xp", 0))),
		"xp_to_next": int(player_state.get("xp_to_next", PROFILE_RULES_SCRIPT.xp_to_next(level))),
	}
	_hud_view.draw_player_panel(self, hud["player_panel"], character, fighter, _entity_view.player_portrait_texture(_player_direction))
	var minimap_mobs: Array = mobs if _is_front_line_world() else []
	_hud_view.draw_minimap(self, hud["minimap"], _desired_position, corpses, minimap_mobs)
	_hud_view.draw_coords(self, hud["coords"], _screen_to_world(get_local_mouse_position()), _desired_position)
	if _corpse_window_id > 0:
		var open_corpse := _corpse_by_id(_corpse_window_id)
		if not open_corpse.is_empty():
			_draw_corpse_window(open_corpse)
	_draw_town_window()
	_draw_magic_casting_preview(view_size)


# Главные здания Front Line: спрайт замка по кадрам (анимация) и полоска здоровья над ним.
# Таверна больше не рисуется: главная цель — здания из раздела «Главные здания» редактора.
const FRONT_LINE_BUILDING_FRAMES := {
	"castle_8": [
		"res://assets/map/main_buildings/castle_anim_1.png", "res://assets/map/main_buildings/castle_anim_2.png",
		"res://assets/map/main_buildings/castle_anim_3.png", "res://assets/map/main_buildings/castle_anim_4.png",
		"res://assets/map/main_buildings/castle_anim_5.png", "res://assets/map/main_buildings/castle_anim_6.png",
		"res://assets/map/main_buildings/castle_anim_7.png", "res://assets/map/main_buildings/castle_anim_8.png",
	],
	"castle_5": [
		"res://assets/map/main_buildings/main_castle_anim_1.png", "res://assets/map/main_buildings/main_castle_anim_2.png",
		"res://assets/map/main_buildings/main_castle_anim_3.png", "res://assets/map/main_buildings/main_castle_anim_4.png",
		"res://assets/map/main_buildings/main_castle_anim_5.png",
	],
}
const FRONT_LINE_BUILDING_FOOTPRINT_TILES := 5
const FRONT_LINE_BUILDING_FRAME_MS := 150
const FRONT_LINE_TILE_PX := 16.0

func _draw_front_line_buildings(front_line_value: Variant) -> void:
	if not front_line_value is Dictionary or int(front_line_value.get("map_id", 0)) <= 0:
		return
	var buildings: Variant = front_line_value.get("buildings", [])
	if not buildings is Array:
		return
	var frame_index := int(Time.get_ticks_msec() / FRONT_LINE_BUILDING_FRAME_MS)
	var width := float(FRONT_LINE_BUILDING_FOOTPRINT_TILES) * FRONT_LINE_TILE_PX
	for building_value in buildings:
		if not building_value is Dictionary:
			continue
		var building: Dictionary = building_value
		var paths: Array = FRONT_LINE_BUILDING_FRAMES.get(str(building.get("sprite", "castle_8")), FRONT_LINE_BUILDING_FRAMES["castle_8"])
		var texture := load(str(paths[posmod(frame_index, paths.size())])) as Texture2D
		var origin := Vector2(float(building.get("x", 0)), float(building.get("y", 0))) * FRONT_LINE_TILE_PX
		var height := width
		if texture != null:
			height = width * float(texture.get_height()) / float(texture.get_width())
			draw_texture_rect(texture, Rect2(origin.x, origin.y + width - height, width, height), false)
		var max_hp := maxi(1, int(building.get("max_hp", 1)))
		var hp := clampi(int(building.get("hp", 0)), 0, max_hp)
		var bar_width := minf(160.0, width * 0.8)
		var bar_position := Vector2(origin.x + (width - bar_width) * 0.5, origin.y + width - height - 14.0)
		draw_rect(Rect2(bar_position, Vector2(bar_width, 8.0)), Color8(35, 29, 28))
		var fill_color := Color8(194, 62, 53) if hp * 4 <= max_hp else Color8(84, 193, 111)
		draw_rect(Rect2(bar_position, Vector2(bar_width * float(hp) / float(max_hp), 8.0)), fill_color)

func _handle_magic_preview_key(keycode: Key) -> bool:
	if not bool(GameSession.world.get("test_only", false)):
		return false
	if _chat_panel.visible or _inventory_panel.visible or _profile_overlay.is_open() or not _town_active_id.is_empty():
		return false
	if keycode == KEY_T:
		_magic_preview_visible = not _magic_preview_visible
		if _magic_preview_visible:
			_magic_preview_class_index = _magic_preview_class_index_for(str(GameSession.character.get("type", "")))
		return true
	if keycode == KEY_0:
		if not _magic_preview_visible:
			_magic_preview_class_index = _magic_preview_class_index_for(str(GameSession.character.get("type", "")))
		_magic_preview_class_index = posmod(_magic_preview_class_index + 1, MAGIC_PREVIEW_CLASSES.size())
		_magic_preview_visible = true
		return true
	if keycode >= KEY_1 and keycode <= KEY_9:
		_magic_preview_level = keycode - KEY_0
		_magic_preview_class_index = _magic_preview_class_index_for(str(GameSession.character.get("type", ""))) if not _magic_preview_visible else _magic_preview_class_index
		_magic_preview_visible = true
		return true
	return false


func _magic_preview_class_index_for(profession: String) -> int:
	match profession.to_lower():
		"archer":
			return 1
		"mage":
			return 2
		_:
			return 0


func _draw_magic_casting_preview(view_size: Vector2) -> void:
	if not _magic_preview_visible or not bool(GameSession.world.get("test_only", false)) or _screen != SCREEN_MAP:
		return
	var profession: String = MAGIC_PREVIEW_CLASSES[_magic_preview_class_index]
	var panel := Rect2(Vector2((view_size.x - 240.0) * 0.5, view_size.y - 195.0), Vector2(240.0, 130.0))
	draw_rect(panel, Color(0.06, 0.07, 0.09, 0.94))
	draw_rect(panel, Color8(194, 157, 88), false, 2.0)
	draw_string(ThemeDB.fallback_font, panel.position + Vector2(10.0, 19.0), "%s — заклинание %d" % [MAGIC_PREVIEW_CLASS_LABELS[_magic_preview_class_index], _magic_preview_level], HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color8(255, 224, 153))
	var frame_index := int(Time.get_ticks_msec() / 120) % 5
	var texture: Texture2D = _magic_casting_preview.frame_texture(profession, _magic_preview_level, _player_direction, frame_index)
	if texture != null:
		draw_texture_rect(texture, Rect2(panel.position + Vector2(80.0, 24.0), Vector2(80.0, 80.0)), false)
	else:
		draw_string(ThemeDB.fallback_font, panel.position + Vector2(42.0, 69.0), "Анимация недоступна", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color8(255, 120, 120))
	draw_string(ThemeDB.fallback_font, panel.position + Vector2(10.0, 122.0), "1–9 уровень · 0 класс · T закрыть  ·  %s" % MAGIC_PREVIEW_DIRECTION_LABELS.get(_player_direction, "вниз"), HORIZONTAL_ALIGNMENT_LEFT, -1, 11, MUTED_COLOR)


func _draw_mob_label(label: Dictionary, offset: Vector2, scale_factor: float, ui_scale: float) -> void:
	var anchor: Vector2 = offset + (label["anchor"] as Vector2) * scale_factor
	var bar_size: Vector2 = (label["bar_size"] as Vector2) * ui_scale
	var gap := float(label["gap"]) * ui_scale
	var bar := Rect2(anchor.x - bar_size.x * 0.5, anchor.y - gap - bar_size.y, bar_size.x, bar_size.y)
	if bool(label["selected"]):
		var outline: Rect2 = label["outline"]
		draw_rect(Rect2(offset + outline.position * scale_factor, outline.size * scale_factor), Color(1.0, 0.82, 0.28), false, 2.0)
	_draw_overhead_bar(bar, float(label["hp_ratio"]), MOB_HP_BAR_COLOR)
	_draw_text_centered(str(label["hp_text"]), Vector2(anchor.x, bar.position.y - 3.0 * ui_scale), roundi(OVERHEAD_FONT_PY * ui_scale), HP_TEXT_COLOR)


# Город Радбург на карте Экономики: только объекты из terrain.objects, Башня их не получает (_town_objects пуст).
func _draw_city_objects(view_rect: Rect2, hovered_town: String, active_town: String) -> void:
	for town in _town_objects:
		var rect := TOWN_RULES.object_rect(town)
		if rect.intersects(view_rect):
			var town_id := str(town.get("id", ""))
			_town_view.draw_town(self, rect, _city_visual_state, town_id == hovered_town, town_id == active_town)


# Плашка над городом: низ текста на 12 px Python выше верхнего края, как _draw_badge в world_map_scene.py.
func _draw_city_badges(offset: Vector2, scale_factor: float, ui_scale: float, view_rect: Rect2, hovered_town: String, active_town: String) -> void:
	for town in _town_objects:
		var rect := TOWN_RULES.object_rect(town)
		if not rect.intersects(view_rect):
			continue
		var town_id := str(town.get("id", ""))
		var top_center := offset + Vector2(rect.get_center().x, rect.position.y) * scale_factor
		var anchor := top_center - Vector2(0.0, TOWN_RULES.BADGE_GAP_PX * ui_scale)
		var border: Color = TOWN_RULES.BADGE_ACTIVE if town_id == active_town else (TOWN_RULES.BADGE_HOVER if town_id == hovered_town else TOWN_RULES.BADGE_DEFAULT)
		_town_view.draw_badge(self, anchor, TOWN_RULES.badge_text(TOWN_RULES.city_level(_city_visual_state)), border, ui_scale)


# Наведение как в _find_entity_at: не в верхней полосе (m_pos[1] <= 75 в Python) и не над панелями интерфейса.
func _hovered_town_id() -> String:
	if _town_objects.is_empty():
		return ""
	var local_mouse := get_local_mouse_position()
	if local_mouse.y <= 75.0 * TOWER_WORLD_SCALE or _is_ui_point(local_mouse):
		return ""
	return str(_town_at(_screen_to_world(local_mouse)).get("id", ""))


# Окно активного объекта Экономики: клик выбирает город, кнопка ведёт в город (_trigger_active_action в Python).
func _town_entry() -> Dictionary:
	return _town_objects[0] if not _town_objects.is_empty() else {}


func _town_at(world_point: Vector2) -> Dictionary:
	for town in _town_objects:
		if TOWN_RULES.hover_rect(town).has_point(world_point):
			return town
	return {}


func _town_window_layout() -> Dictionary:
	return TOWN_RULES.window_layout(TOWN_RULES.window_rect(size, TOWER_WORLD_SCALE), TOWER_WORLD_SCALE)


func _town_window_contains(point: Vector2) -> bool:
	return not _town_active_id.is_empty() and (_town_window_layout()["window"] as Rect2).has_point(point)


func _open_town_window(town: Dictionary) -> void:
	_town_active_id = str(town.get("id", ""))
	_selected_mob_id = ""
	queue_redraw()


func _close_town_window() -> void:
	if _town_active_id.is_empty():
		return
	_town_active_id = ""
	_town_notice = ""
	_town_notice_seconds = 0.0
	queue_redraw()


func _handle_town_window_click(point: Vector2) -> void:
	var layout := _town_window_layout()
	if (layout["close"] as Rect2).has_point(point):
		_close_town_window()
	elif (layout["action"] as Rect2).has_point(point):
		_trigger_town_action()
	queue_redraw()


# Рядом с воротами — переход в город через ближайшие ворота тем же переходом, что и шаг на вход; далеко — фраза отказа.
func _trigger_town_action() -> void:
	var town := _town_entry()
	if town.is_empty() or _leaving_to_city or not _exit_intent.is_empty():
		return
	if not TOWN_RULES.within_one_tile(town, _player_tile()):
		_show_too_far_notice()
		return
	_leaving_to_city = true
	_city_gate_pending = TOWN_RULES.nearest_gate(town, _desired_position)
	_clear_move_path()
	_start_city_transition_if_idle()


# Фраза над персонажем и на кнопке на 2,2 с, как _on_too_far в Python.
func _show_too_far_notice() -> void:
	var choices: Array = TOWN_RULES.too_far_choices(_last_too_far_phrase)
	var phrase := str(choices[randi() % choices.size()])
	_last_too_far_phrase = phrase
	_town_notice = phrase
	_town_notice_seconds = TOWN_RULES.NOTICE_SECONDS
	_add_floating_event({"x": _desired_position.x, "y": _desired_position.y - 34.0}, phrase, Color8(255, 110, 90), TOWN_RULES.FLOATING_SECONDS)
	queue_redraw()


func _tick_town_notice(delta: float) -> void:
	if _town_notice_seconds <= 0.0:
		return
	_town_notice_seconds -= delta
	if _town_notice_seconds <= 0.0:
		_town_notice = ""
		queue_redraw()


func _draw_town_window() -> void:
	var town := _town_entry()
	if _town_active_id.is_empty() or town.is_empty():
		return
	_town_view.draw_window(self, _town_window_layout(), town, TOWN_RULES.within_one_tile(town, _player_tile()), _town_notice, get_local_mouse_position(), TOWER_WORLD_SCALE)


# Другие игроки на карте, как draw_active_players и draw_afk_players в Python: активные (не AFK) и AFK с позицией.
func _other_players() -> Dictionary:
	var own_id := PRESENCE_RULES.id_text(GameSession.character.get("id", 0))
	var afk: Array = []
	for occupant in PRESENCE_RULES.afk_occupants(_chat_occupants, "world_map"):
		if not PRESENCE_RULES.is_own(occupant, own_id):
			afk.append(occupant)
	return {
		"active": PRESENCE_RULES.active_occupants(_chat_occupants, "world_map", own_id),
		"afk": afk,
	}


func _draw_other_players() -> void:
	var front_line := str(GameSession.world.get("mode", "")) == "front_line"
	var others := _other_players()
	for occupant in others["active"]:
		var player: Dictionary = occupant.duplicate()
		player["front_line"] = front_line
		_entity_view.draw_other_player(self, player, PRESENCE_RULES.direction_of(occupant), false)
	for occupant in others["afk"]:
		var player: Dictionary = occupant.duplicate()
		player["front_line"] = front_line
		_entity_view.draw_other_player(self, player, PRESENCE_RULES.direction_of(occupant), true)


func _draw_other_player_labels(offset: Vector2, scale_factor: float, ui_scale: float) -> void:
	var others := _other_players()
	for occupant in others["active"]:
		_draw_other_player_label(occupant, false, offset, scale_factor, ui_scale)
	for occupant in others["afk"]:
		_draw_other_player_label(occupant, true, offset, scale_factor, ui_scale)


# Подпись над спрайтом без полосок: имя и иконка профессии; у AFK — «(АФК)» серым.
func _draw_other_player_label(occupant: Dictionary, afk: bool, offset: Vector2, scale_factor: float, ui_scale: float) -> void:
	var feet := offset + Vector2(float(occupant["position_x"]), float(occupant["position_y"])) * scale_factor
	var font_size := roundi(OVERHEAD_FONT_PY * ui_scale)
	var name_bottom := feet.y - 90.0 * scale_factor - 4.0 * ui_scale
	var text := PRESENCE_RULES.afk_label(occupant) if afk else PRESENCE_RULES.display_name(occupant)
	var name_width := ThemeDB.fallback_font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x
	var box_height := (OVERHEAD_LABEL_H_PY + 2.0) * ui_scale
	var box := Rect2(feet.x - (name_width + 8.0 * ui_scale) * 0.5, name_bottom + ui_scale - box_height, name_width + 8.0 * ui_scale, box_height)
	var fill := AFK_LABEL_FILL if afk else OTHER_LABEL_FILL
	var border := AFK_LABEL_BORDER if afk else OTHER_LABEL_BORDER
	draw_style_box(_box_style(fill, border, 3.0), box)
	var icon: Texture2D = TOWER_HUD_SCRIPT.profession_icon(PRESENCE_RULES.class_type(occupant))
	if icon != null:
		var icon_size := PROFESSION_ICON_PY * ui_scale
		var icon_gap := PROFESSION_ICON_GAP_PY * ui_scale
		draw_texture_rect(icon, Rect2(box.position.x - icon_gap - icon_size, box.get_center().y - icon_size * 0.5, icon_size, icon_size), false)
	_draw_text_centered(text, Vector2(feet.x, name_bottom - 2.0 * ui_scale), font_size, AFK_NAME_COLOR if afk else OTHER_NAME_COLOR)


func _draw_player_label(label: Dictionary, offset: Vector2, scale_factor: float, ui_scale: float) -> void:
	# Снизу вверх, как в Python: полоска МП с подписью, над ней ХП с подписью, сверху ник с иконкой профессии.
	var feet: Vector2 = offset + (label["feet"] as Vector2) * scale_factor
	var bar_size: Vector2 = (label["bar_size"] as Vector2) * ui_scale
	var font_size := roundi(OVERHEAD_FONT_PY * ui_scale)
	var mp_top := offset.y + float(label["mp_bar_bottom"]) * scale_factor - bar_size.y
	_draw_overhead_bar(Rect2(feet.x - bar_size.x * 0.5, mp_top, bar_size.x, bar_size.y), float(label["mp_ratio"]), PLAYER_MP_BAR_COLOR)
	_draw_text_centered(str(label["mp_text"]), Vector2(feet.x, mp_top - 3.0 * ui_scale), font_size, MP_TEXT_COLOR)
	var hp_top := mp_top - (OVERHEAD_LABEL_H_PY + 13.0) * ui_scale
	_draw_overhead_bar(Rect2(feet.x - bar_size.x * 0.5, hp_top, bar_size.x, bar_size.y), float(label["hp_ratio"]), PLAYER_HP_BAR_COLOR)
	_draw_text_centered(str(label["hp_text"]), Vector2(feet.x, hp_top - 3.0 * ui_scale), font_size, HP_TEXT_COLOR)
	var name_bottom := hp_top - (OVERHEAD_LABEL_H_PY + 3.0) * ui_scale
	var name_text := str(label["name"])
	var name_width := ThemeDB.fallback_font.get_string_size(name_text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x
	var box_height := (OVERHEAD_LABEL_H_PY + 2.0) * ui_scale
	var box := Rect2(feet.x - (name_width + 8.0 * ui_scale) * 0.5, name_bottom + ui_scale - box_height, name_width + 8.0 * ui_scale, box_height)
	draw_style_box(_box_style(Color8(15, 18, 24, 210), Color8(180, 150, 60), 3.0), box)
	var icon: Texture2D = TOWER_HUD_SCRIPT.profession_icon(str(label["profession"]))
	if icon != null:
		var icon_size := PROFESSION_ICON_PY * ui_scale
		var icon_gap := PROFESSION_ICON_GAP_PY * ui_scale
		draw_texture_rect(icon, Rect2(box.position.x - icon_gap - icon_size, box.get_center().y - icon_size * 0.5, icon_size, icon_size), false)
	_draw_text_centered(name_text, Vector2(feet.x, name_bottom - 2.0 * ui_scale), font_size, NAME_TEXT_COLOR)


func _draw_overhead_bar(rect: Rect2, ratio: float, fill: Color) -> void:
	draw_rect(rect, Color8(40, 10, 10))
	draw_rect(Rect2(rect.position, Vector2(rect.size.x * clampf(ratio, 0.0, 1.0), rect.size.y)), fill)


func _draw_text_centered(text: String, baseline: Vector2, font_size: int, color: Color) -> void:
	draw_string(ThemeDB.fallback_font, baseline - Vector2(100.0, 0.0), text, HORIZONTAL_ALIGNMENT_CENTER, 200.0, font_size, color)


func _camera_position() -> Vector2:
	var target := _desired_position + (_camera_offset if _is_front_line_world() else Vector2.ZERO)
	if not _world_ready:
		var player: Dictionary = GameSession.world_snapshot.get("player", {})
		target = Vector2(
			float(player.get("x", _map_tiles_w * TILE_SIZE * 0.5)),
			float(player.get("y", _map_tiles_h * TILE_SIZE * 0.5)),
		)
	# Как _clamp_camera в Python: камера не выходит за край карты, а маленькая карта центрируется.
	var half := size / (2.0 * _world_scale())
	var map_size := Vector2(_map_tiles_w, _map_tiles_h) * TILE_SIZE
	for axis in 2:
		if map_size[axis] > half[axis] * 2.0:
			target[axis] = clampf(target[axis], half[axis], map_size[axis] - half[axis])
		else:
			target[axis] = map_size[axis] * 0.5
	return target


func _world_scale() -> float:
	return _front_line_zoom if _is_front_line_world() else TOWER_WORLD_SCALE


func _set_front_line_zoom(value: float) -> void:
	_front_line_zoom = clampf(value, FRONT_LINE_CAMERA_MIN_SCALE, FRONT_LINE_CAMERA_MAX_SCALE)
	queue_redraw()


func _update_front_line_camera(delta: float) -> void:
	if _camera_dragging or _chat_panel.visible or _inventory_panel.visible \
			or _profile_overlay.is_open():
		return
	var mouse := get_local_mouse_position()
	if mouse.x < 0.0 or mouse.y < 0.0 or mouse.x >= size.x or mouse.y >= size.y or _is_ui_point(mouse):
		return
	var margin := FRONT_LINE_CAMERA_EDGE_MARGIN
	var direction := Vector2(
		float(mouse.x >= size.x - margin) - float(mouse.x <= margin),
		float(mouse.y >= size.y - margin) - float(mouse.y <= margin),
	).limit_length(1.0)
	if direction == Vector2.ZERO:
		return
	_camera_offset += direction * FRONT_LINE_CAMERA_EDGE_SPEED * delta / _front_line_zoom
	queue_redraw()


func _is_ui_point(point: Vector2) -> bool:
	if _corpse_window_contains(point) or _town_window_contains(point):
		return true
	var hud: Dictionary = _hud_view.layout(size)
	for key in ["player_panel", "minimap", "coords"]:
		if (hud[key] as Rect2).has_point(point):
			return true
	if hud.has("minimap_frame") and (hud["minimap_frame"] as Rect2).has_point(point):
		return true
	return _status_box.visible and _status_box.get_global_rect().has_point(point)


func _screen_to_world(screen_position: Vector2) -> Vector2:
	var screen_center := size * 0.5
	return _camera_position() + (screen_position - screen_center) / _world_scale()


func _update_floating_events(delta: float) -> void:
	var changed := false
	for index in range(_floating_events.size() - 1, -1, -1):
		var popup := _floating_events[index]
		popup["ttl"] = float(popup.get("ttl", 0.0)) - delta
		if float(popup["ttl"]) <= 0.0:
			_floating_events.remove_at(index)
		changed = true
	if changed:
		queue_redraw()


func _add_floating_event(event: Dictionary, text: String, color: Color, duration := 1.2) -> void:
	_floating_events.append({
		"x": float(event.get("x", 0.0)),
		"y": float(event.get("y", 0.0)),
		"text": text,
		"color": color,
		"ttl": duration,
		"duration": duration,
	})


func _update_world_status(snapshot: Dictionary) -> void:
	var player: Dictionary = snapshot.get("player", {})
	var mobs: Array = snapshot.get("mobs", [])
	var target_exists := false
	for mob in mobs:
		if mob is Dictionary and str(mob.get("id", "")) == _selected_mob_id and str(mob.get("state", "")) != "dead":
			target_exists = true
			break
	if not target_exists:
		if not _selected_mob_id.is_empty():
			_wants_acquire = true
		_selected_mob_id = ""
	var x := float(player.get("x", 0.0))
	var y := float(player.get("y", 0.0))
	var hp := str(player.get("hp", "—"))
	var max_hp := str(player.get("max_hp", "—"))
	var mp := str(player.get("mp", "—"))
	var max_mp := str(player.get("max_mp", "—"))
	var dash_cooldown := float(player.get("dash_cooldown", 0.0))
	var harvest: Variant = player.get("harvest")
	var harvest_label := "нет"
	if harvest is Dictionary:
		var progress := float(harvest.get("progress", 0.0))
		var total := float(harvest.get("total", 0.0))
		harvest_label = "%.1f / %.1f сек." % [progress, total]
	var target_label := "нет"
	if not _selected_mob_id.is_empty():
		target_label = _selected_mob_id
	var dash_label := "готов" if dash_cooldown <= 0.0 else "%d сек." % int(ceil(dash_cooldown))
	if _dash_aiming:
		dash_label = "выберите направление"
	var front_line: Variant = snapshot.get("front_line")
	if front_line is Dictionary and _is_front_line_world():
		_update_front_line_draft(front_line)
		_update_front_line_report(front_line)
		_update_front_line_summary(front_line)
		var objective_value: Variant = front_line.get("objective", {})
		var wave_value: Variant = front_line.get("wave", {})
		var objective: Dictionary = objective_value if objective_value is Dictionary else {}
		var wave: Dictionary = wave_value if wave_value is Dictionary else {}
		var living_mobs := 0
		for mob in mobs:
			if mob is Dictionary and float(mob.get("hp", 0.0)) > 0.0:
				living_mobs += 1
		_status.text = "Главные здания: %d / %d · мобов на карте: %d · волна: %d" % [
			int(objective.get("alive", 0)),
			int(objective.get("total", 0)),
			living_mobs,
			int(wave.get("number", 0)),
		]
		return
	if front_line is Dictionary:
		_update_front_line_draft(front_line)
	_status.text = "Позиция: %.0f, %.0f\nЗдоровье: %s / %s · Мана: %s / %s\nПротивники: %d · Цель: %s\nДобыча: %s · Рывок: %s" % [
		x, y, hp, max_hp, mp, max_mp, mobs.size(), target_label, harvest_label, dash_label,
	]


func _build_front_line_report() -> void:
	_front_line_report_overlay = CenterContainer.new()
	_front_line_report_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_front_line_report_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_front_line_report_overlay.z_index = 70
	_front_line_report_overlay.visible = false
	add_child(_front_line_report_overlay)

	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(460.0, 0.0)
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.035, 0.055, 0.075, 0.88)
	style.border_color = Color(0.82, 0.68, 0.39, 0.9)
	style.set_border_width_all(1)
	style.set_corner_radius_all(10)
	style.shadow_color = Color(0.0, 0.0, 0.0, 0.35)
	style.shadow_size = 12
	style.content_margin_left = 24.0
	style.content_margin_right = 24.0
	style.content_margin_top = 18.0
	style.content_margin_bottom = 18.0
	panel.add_theme_stylebox_override("panel", style)
	_front_line_report_overlay.add_child(panel)

	var content := VBoxContainer.new()
	content.add_theme_constant_override("separation", 8)
	panel.add_child(content)
	var eyebrow := Label.new()
	eyebrow.text = "ОТЧЁТ МАТЧА"
	eyebrow.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	eyebrow.add_theme_font_size_override("font_size", 11)
	eyebrow.add_theme_color_override("font_color", Color(0.72, 0.77, 0.82))
	content.add_child(eyebrow)
	_front_line_report_title = Label.new()
	_front_line_report_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_front_line_report_title.add_theme_font_size_override("font_size", 25)
	_front_line_report_title.add_theme_color_override("font_color", TITLE_COLOR)
	content.add_child(_front_line_report_title)
	var divider := HSeparator.new()
	content.add_child(divider)
	_front_line_report_body = Label.new()
	_front_line_report_body.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_front_line_report_body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_front_line_report_body.add_theme_font_size_override("font_size", 16)
	_front_line_report_body.add_theme_color_override("font_color", Color(0.88, 0.91, 0.94))
	content.add_child(_front_line_report_body)
	_front_line_countdown_label = Label.new()
	_front_line_countdown_label.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_front_line_countdown_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_front_line_countdown_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_front_line_countdown_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_front_line_countdown_label.add_theme_font_size_override("font_size", 176)
	_front_line_countdown_label.add_theme_color_override("font_color", Color(0.93, 0.9, 0.8, 0.42))
	_front_line_countdown_label.visible = false
	_front_line_countdown_label.z_index = 69
	add_child(_front_line_countdown_label)
	_build_front_line_summary()


func _build_front_line_summary() -> void:
	_front_line_summary_overlay = CenterContainer.new()
	_front_line_summary_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_front_line_summary_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_front_line_summary_overlay.z_index = 71
	_front_line_summary_overlay.visible = false
	add_child(_front_line_summary_overlay)

	var panel := PanelContainer.new()
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.035, 0.055, 0.075, 0.92)
	style.border_color = Color(0.82, 0.68, 0.39, 0.9)
	style.set_border_width_all(1)
	style.set_corner_radius_all(10)
	style.content_margin_left = 24.0
	style.content_margin_right = 24.0
	style.content_margin_top = 18.0
	style.content_margin_bottom = 18.0
	panel.add_theme_stylebox_override("panel", style)
	_front_line_summary_overlay.add_child(panel)

	var content := VBoxContainer.new()
	content.add_theme_constant_override("separation", 10)
	panel.add_child(content)

	_front_line_summary_title = Label.new()
	_front_line_summary_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_front_line_summary_title.add_theme_font_size_override("font_size", 22)
	_front_line_summary_title.add_theme_color_override("font_color", TITLE_COLOR)
	content.add_child(_front_line_summary_title)

	_front_line_summary_info = Label.new()
	_front_line_summary_info.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_front_line_summary_info.add_theme_font_size_override("font_size", 14)
	_front_line_summary_info.add_theme_color_override("font_color", Color(0.88, 0.91, 0.94))
	content.add_child(_front_line_summary_info)

	_front_line_summary_grid = GridContainer.new()
	_front_line_summary_grid.columns = 7
	_front_line_summary_grid.add_theme_constant_override("h_separation", 18)
	_front_line_summary_grid.add_theme_constant_override("v_separation", 4)
	content.add_child(_front_line_summary_grid)

	_front_line_summary_button = Button.new()
	_front_line_summary_button.text = "Вернуться в лобби"
	_front_line_summary_button.custom_minimum_size = Vector2(260.0, 42.0)
	_front_line_summary_button.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	_front_line_summary_button.pressed.connect(_on_front_line_summary_lobby_pressed)
	content.add_child(_front_line_summary_button)


# Итоги раунда показываем после баннера результата и держим, пока игрок не выйдет в лобби.
func _update_front_line_summary(front_line: Dictionary) -> void:
	if _front_line_summary_overlay == null or not is_instance_valid(_front_line_summary_overlay):
		return
	var state := str(front_line.get("state", ""))
	var summary_value: Variant = front_line.get("match_summary", {})
	var summary: Dictionary = summary_value if summary_value is Dictionary else {}
	var is_result := state == "victory" or state == "lost"
	var showing := is_result and not summary.is_empty() and not _front_line_report_overlay.visible
	_front_line_summary_overlay.visible = showing
	_front_line_summary_button.disabled = not _exit_intent.is_empty()
	if not showing:
		return
	var key := JSON.stringify(summary)
	if key == _front_line_summary_key:
		return
	_front_line_summary_key = key
	_fill_front_line_summary(summary)


func _fill_front_line_summary(summary: Dictionary) -> void:
	var victory := str(summary.get("result", "")) == "victory"
	_front_line_summary_title.text = "ПОБЕДА ГЕРОЕВ" if victory else "ПОРАЖЕНИЕ"
	_front_line_summary_info.text = "Продержались: %s · Мобов побеждено: %d · Всего урона: %d · Главные здания: %d / %d HP" % [
		_format_front_line_duration(int(summary.get("duration_seconds", 0))),
		int(summary.get("mobs_killed", 0)),
		int(summary.get("total_damage", 0)),
		int(summary.get("objective_alive", 0)),
		int(summary.get("objective_total", 0)),
	]
	for child in _front_line_summary_grid.get_children():
		_front_line_summary_grid.remove_child(child)
		child.queue_free()
	for header in ["Герой", "Урон", "Доля", "Получено", "Убийства", "Опыт", "Смерти"]:
		_front_line_summary_grid.add_child(_summary_cell(header, Color(0.72, 0.77, 0.82)))
	var own_id := int(GameSession.character.get("id", 0))
	var players_value: Variant = summary.get("players", [])
	if not players_value is Array:
		return
	for entry_value in players_value:
		if not entry_value is Dictionary:
			continue
		var entry: Dictionary = entry_value
		var color := Color(0.98, 0.86, 0.5) if int(entry.get("character_id", -1)) == own_id else Color(0.9, 0.92, 0.95)
		var hero_name := str(entry.get("name", "")).strip_edges()
		if hero_name.is_empty():
			hero_name = "Герой"
		_front_line_summary_grid.add_child(_summary_cell(hero_name, color))
		_front_line_summary_grid.add_child(_summary_cell(str(int(entry.get("damage_dealt", 0))), color))
		_front_line_summary_grid.add_child(_summary_cell("%.1f%%" % float(entry.get("damage_share", 0.0)), color))
		_front_line_summary_grid.add_child(_summary_cell(str(int(entry.get("damage_taken", 0))), color))
		_front_line_summary_grid.add_child(_summary_cell(str(int(entry.get("kills", 0))), color))
		_front_line_summary_grid.add_child(_summary_cell(str(int(entry.get("xp", 0))), color))
		_front_line_summary_grid.add_child(_summary_cell(str(int(entry.get("deaths", 0))), color))


func _summary_cell(text: String, color: Color) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", 14)
	label.add_theme_color_override("font_color", color)
	return label


func _on_front_line_summary_lobby_pressed() -> void:
	_start_exit("lobby")


func _update_front_line_report(front_line: Dictionary) -> void:
	var state := str(front_line.get("state", "waiting"))
	var countdown_active := bool(front_line.get("round_countdown_active", false))
	_front_line_countdown_label.visible = countdown_active
	_front_line_countdown_label.text = str(maxi(
		0,
		int(front_line.get("round_countdown_seconds", 0)),
	))
	var map_name := str(front_line.get("map_name", "")).strip_edges()
	if map_name.is_empty():
		map_name = "Карта не выбрана"
	var size_text := "%d × %d" % [
		int(front_line.get("map_width", 0)),
		int(front_line.get("map_height", 0)),
	]
	var objective: Variant = front_line.get("objective", {})
	var objective_text := "—"
	if objective is Dictionary and not objective.is_empty():
		objective_text = "%d / %d" % [
			int(objective.get("alive", 0)),
			int(objective.get("total", 0)),
		]
	var details := [
		"Карта: %s · %s" % [map_name, size_text],
		"Цель: главные здания · %s" % objective_text,
	]
	var title := "FRONT LINE"
	match state:
		"map_unavailable":
			title = "НУЖНА КАРТА"
			details = ["Сохраните карту в режиме Front Line.", "Матч не начнётся на карте другого режима."]
		"waiting":
			details.append("Игроков в очереди: %d · старт через %s" % [
				int(front_line.get("players_waiting", 0)),
				_format_front_line_duration(int(front_line.get("starts_in_seconds", 0))),
			])
		"character_draft":
			title = "ВЫБОР ГЕРОЕВ"
			details.append("Готовы: %d из %d · осталось %s" % [
				int(front_line.get("draft_players_ready", 0)),
				int(front_line.get("draft_players_total", 0)),
				_format_front_line_duration(int(front_line.get("draft_seconds_remaining", 0))),
			])
		"awaiting_wave_draft":
			title = "ПОДГОТОВКА К ВОЛНЕ"
			details.append("Раунд начнётся через %s." % _format_front_line_duration(
				int(front_line.get("wave_draft_seconds_remaining", 0)),
			))
		"running":
			title = "ЗАЩИТА НАЧАЛАСЬ"
			var wave: Variant = front_line.get("wave", {})
			if wave is Dictionary and not wave.is_empty():
				details.append("Волна %d · мобов живо: %d / %d" % [
					int(wave.get("number", 0)),
					int(wave.get("mobs_alive", 0)),
					int(wave.get("mobs_total", 0)),
				])
			details.append("Время матча: %s" % _format_front_line_duration(
				int(front_line.get("elapsed_seconds", 0)),
			))
		"victory":
			title = "ПОБЕДА ГЕРОЕВ"
			details.append("Все волны и боссы побеждены.")
		"lost":
			title = "ПОРАЖЕНИЕ"
			details.append("Таверна разрушена.")
	_front_line_report_title.text = title
	_front_line_report_body.text = "\n".join(details)
	if countdown_active:
		_front_line_report_state = state
		_front_line_report_seconds = 0.0
		_front_line_report_overlay.visible = false
	elif state != _front_line_report_state:
		_front_line_report_state = state
		_front_line_report_seconds = 7.0
		if _front_line_report_tween != null and _front_line_report_tween.is_running():
			_front_line_report_tween.kill()
		_front_line_report_overlay.modulate.a = 1.0
		_front_line_report_overlay.visible = true


func _tick_front_line_report(delta: float) -> void:
	if _front_line_report_seconds <= 0.0 or not is_instance_valid(_front_line_report_overlay):
		return
	_front_line_report_seconds = maxf(0.0, _front_line_report_seconds - delta)
	if _front_line_report_seconds > 0.0 or not _front_line_report_overlay.visible:
		return
	_front_line_report_tween = create_tween()
	_front_line_report_tween.tween_property(
		_front_line_report_overlay,
		"modulate:a",
		0.0,
		0.8,
	)
	_front_line_report_tween.tween_callback(func() -> void:
		_front_line_report_overlay.visible = false
	)


func _update_front_line_draft(front_line: Dictionary) -> void:
	if str(GameSession.world.get("mode", "")) != "front_line":
		return
	# Значения выбора героя применяются только во время драфта: позже характеристики и очки ведёт мир,
	# и старый снимок драфта не должен откатывать добавленные в бою очки на каждой синхронизации.
	var draft_character: Variant = front_line.get("draft_character", {})
	if str(front_line.get("state", "")) == "character_draft" and draft_character is Dictionary and not draft_character.is_empty():
		var updated_character := GameSession.character.duplicate(true)
		for key in ["stats", "stat_points", "hp", "max_hp", "mp", "max_mp"]:
			if draft_character.has(key):
				updated_character[key] = draft_character[key]
		updated_character["type"] = str(draft_character.get("type", "warrior"))
		updated_character["profession_type"] = str(draft_character.get("type", "warrior"))
		GameSession.select_character(updated_character)
	if str(front_line.get("state", "")) != "character_draft":
		if _front_line_draft_overlay != null and is_instance_valid(_front_line_draft_overlay):
			_front_line_draft_overlay.queue_free()
		_front_line_draft_overlay = null
		_front_line_draft_title = null
		_front_line_draft_status = null
		_front_line_draft_view = null
		return
	_ensure_front_line_draft_overlay()
	_front_line_draft_title.text = "Выбор героя · %s" % _format_front_line_duration(
		int(front_line.get("draft_seconds_remaining", 0)),
	)
	var selected := bool(front_line.get("draft_selected", false))
	_front_line_draft_status.text = "Выберите героя для этого матча. Класс и характеристики действуют только до завершения партии.\nГотовы: %d из %d. Асасин недоступен: в разработке. Если не подтвердить выбор до конца времени, класс будет выбран случайно.%s%s" % [
		int(front_line.get("draft_players_ready", 0)),
		int(front_line.get("draft_players_total", 0)),
		"\nВаш выбор сохранён; его можно изменить до конца драфта." if selected else "",
		"\n" + _front_line_draft_notice if not _front_line_draft_notice.is_empty() else "",
	]
	if _front_line_draft_view != null and is_instance_valid(_front_line_draft_view):
		_front_line_draft_view.set_submit_enabled(_pending_action != "front_line_draft_submit")


func _reconcile_front_line_draft_spawn(snapshot: Dictionary) -> bool:
	if not _is_front_line_world():
		return false
	var previous_front_line: Variant = GameSession.world_snapshot.get("front_line", {})
	var current_front_line: Variant = snapshot.get("front_line", {})
	if not previous_front_line is Dictionary or not current_front_line is Dictionary \
			or str(previous_front_line.get("state", "")) != "character_draft" \
			or str(current_front_line.get("state", "")) == "character_draft":
		return false
	var player: Variant = snapshot.get("player", {})
	if not player is Dictionary or not player.has("x") or not player.has("y"):
		return false
	_desired_position = Vector2(float(player["x"]), float(player["y"]))
	_sent_position = _desired_position
	_movement_pending = false
	_clear_move_path()
	return true


func _format_front_line_duration(seconds: int) -> String:
	var total := maxi(0, seconds)
	return "%02d:%02d:%02d" % [
		floori(float(total) / 3600.0),
		floori(float(total % 3600) / 60.0),
		total % 60,
	]


func _show_front_line_loading_cover() -> void:
	_ensure_front_line_draft_overlay()
	_front_line_draft_title.text = "Подключаемся к матчу…"
	_front_line_draft_status.text = "Загружаем состояние матча."
	_front_line_draft_view.set_submit_enabled(false)


func _ensure_front_line_draft_overlay() -> void:
	if _front_line_draft_overlay != null and is_instance_valid(_front_line_draft_overlay):
		return
	_front_line_draft_overlay = ColorRect.new()
	_front_line_draft_overlay.color = Color(0.02, 0.025, 0.04, 1.0)
	_front_line_draft_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_front_line_draft_overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	_front_line_draft_overlay.z_index = 80
	add_child(_front_line_draft_overlay)

	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_front_line_draft_overlay.add_child(center)

	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(940, 570)
	center.add_child(panel)

	var content := VBoxContainer.new()
	content.add_theme_constant_override("separation", 10)
	panel.add_child(content)

	_front_line_draft_title = Label.new()
	_front_line_draft_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_front_line_draft_title.add_theme_font_size_override("font_size", 28)
	_front_line_draft_title.add_theme_color_override("font_color", TITLE_COLOR)
	content.add_child(_front_line_draft_title)

	_front_line_draft_status = Label.new()
	_front_line_draft_status.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_front_line_draft_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_front_line_draft_status.add_theme_color_override("font_color", MUTED_COLOR)
	content.add_child(_front_line_draft_status)

	_front_line_draft_view = CREATE_CHARACTER_VIEW_SCRIPT.new()
	_front_line_draft_view.configure("front_line")
	_front_line_draft_view.configure_for_draft(str(GameSession.character.get("name", "")))
	_front_line_draft_view.set_card_scale(0.42)
	_front_line_draft_view.create_requested.connect(_submit_front_line_character_draft)
	_front_line_draft_view.unavailable_profession_requested.connect(_on_front_line_unavailable_profession)
	_front_line_draft_view.profession_selected.connect(_on_front_line_profession_selected)
	content.add_child(_front_line_draft_view)


func _on_front_line_unavailable_profession(profession: String) -> void:
	if profession == "assassin":
		_front_line_draft_notice = "Асасин пока недоступен: в разработке."
		if _front_line_draft_status != null:
			_front_line_draft_status.text = _front_line_draft_notice


func _on_front_line_profession_selected(_profession: String) -> void:
	_front_line_draft_notice = ""


func _submit_front_line_character_draft() -> void:
	if _pending_action != "" or _front_line_draft_view == null:
		return
	var choice: Dictionary = _front_line_draft_view.request_body()
	_pending_action = "front_line_draft_submit"
	_front_line_draft_view.set_submit_enabled(false)
	# Анимация выбора: три оборота выбранной карточки; характеристики откроются после неё.
	_front_line_draft_view.play_selection_intro()
	_front_line_draft_status.text = "Отправляем ваш выбор героя…"
	ApiClient.request_json(HTTPClient.METHOD_POST, "/api/front-line/character-draft", {
		"character_id": int(GameSession.character.get("id", 0)),
		"profession_type": str(choice.get("profession_type", "")),
		"stats": choice.get("stats", {}),
	})


# Класс героя приходит в снимке игрока: драфт завершается на сервере, и клиент узнаёт выбор уже после его конца.
func _sync_front_line_hero_type(player_payload: Variant) -> void:
	if not _is_front_line_world() or not player_payload is Dictionary:
		return
	var hero_type := str(player_payload.get("type", ""))
	if hero_type.is_empty() or hero_type == str(GameSession.character.get("type", "")):
		return
	var updated_character := GameSession.character.duplicate(true)
	updated_character["type"] = hero_type
	updated_character["profession_type"] = hero_type
	GameSession.select_character(updated_character)
	_render_character_profile()


func _apply_world_events(events: Variant, harvest_target_before_sync: Variant = null) -> void:
	if not events is Array:
		return
	for event in events:
		if not event is Dictionary:
			continue
		var event_type := str(event.get("type", ""))
		var line := ""
		var color := Color(0.9, 0.9, 0.9)
		match event_type:
			"projectile":
				_on_projectile_event(event, float(Time.get_ticks_msec()) / 1000.0)
				continue
			"projectile_hit":
				_on_projectile_hit(event, float(Time.get_ticks_msec()) / 1000.0)
				continue
			"log", "notice", "message":
				line = str(event.get("text", ""))
				if event_type == "notice":
					color = Color(1.0, 0.86, 0.56)
				elif event_type == "message":
					color = Color(1.0, 0.92, 0.72)
				var harvested_target: Variant = harvest_target_before_sync if harvest_target_before_sync is Array else _harvest_target
				if event_type == "notice" and line.begins_with("Добыто кристаллов") and harvested_target is Array:
					var harvested_tile := Vector2i(int(harvested_target[0]), int(harvested_target[1]))
					_crystal_tiles = _crystal_tiles.filter(func(crystal: Variant) -> bool:
						return not crystal is Array or crystal.size() < 2 or int(crystal[0]) != harvested_tile.x or int(crystal[1]) != harvested_tile.y
					)
					if _harvest_target is Array and int(_harvest_target[0]) == harvested_tile.x and int(_harvest_target[1]) == harvested_tile.y:
						_harvest_target = null
				if event_type == "message":
					_add_floating_event(event, line, Color(1.0, 0.92, 0.72), 2.0)
			"number":
				var critical := bool(event.get("critical", false))
				var damage_value := str(int(event.get("value", 0)))  # JSON отдаёт числа как float: показываем целое
				# В журнал не пишем: строка «Вы нанесли ... урона» уже содержит то же число.
				_add_floating_event(event, damage_value, Color(1.0, 0.28, 0.22) if critical else Color.WHITE)
			"label":
				var outcomes := {"miss": "Промах", "dodge": "Уворот", "block": "Блок"}
				# В журнал не пишем: промах, уворот и блок сервер записывает отдельной строкой с именами.
				var outcome_text := str(outcomes.get(str(event.get("outcome", "")), "Атака не прошла"))
				_add_floating_event(event, outcome_text, Color(0.86, 0.84, 0.78))
			"currency":
				var currency: Variant = event.get("currency", {})
				if currency is Dictionary:
					GameSession.character.merge(currency, true)
					line = "Баланс обновлён"
			"progress":
				var character_update: Variant = event.get("character", {})
				if character_update is Dictionary:
					GameSession.character.merge(character_update, true)
					line = "Персонаж получил опыт"
			"whirl":
				_world_audio().play_whirl()
		# В боевом логе только урон (нанесённый и полученный) и добыча.
		var log_text := _combat_log_text(event_type, line)
		if not log_text.is_empty():
			_combat_log.add(log_text, color)


# Строка для боевого лога или пустая: урон из строк боя, добыча из уведомлений о гибели моба и кристаллах.
func _combat_log_text(event_type: String, line: String) -> String:
	if event_type == "log":
		return line if line.contains("урона") else ""
	if event_type == "notice":
		var loot_parts := PackedStringArray()
		for part in line.split(". "):
			if part.begins_with("Добыча") or part.begins_with("Добыто"):
				loot_parts.append(part)
		return ". ".join(loot_parts)
	return ""
