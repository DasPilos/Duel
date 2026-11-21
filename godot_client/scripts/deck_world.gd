extends Control

const TITLE_COLOR := Color(0.94, 0.82, 0.56)
const MUTED_COLOR := Color(0.62, 0.68, 0.77)
const EXIT_MENU_SCRIPT := preload("res://scripts/exit_menu.gd")
const SERVER_STATUS_HUD_SCRIPT := preload("res://scripts/server_status_hud.gd")
const SCENE_TRANSITION := preload("res://scripts/scene_transition.gd")
const DECK_SIZE := 22
const DECK_COPY_LIMIT := 2
const MAP_VIEW_SIZE := 11
const TAVERN_EXIT_TILE := Vector2i(6, 29)
const CARD_TOOLTIP_SCRIPT := preload("res://scripts/card_tooltip.gd")
const CARD_RULES := preload("res://scripts/card_tooltip_rules.gd")
const CHARACTER_RULES := preload("res://scripts/deck_character_rules.gd")
const ITEM_ICON_RULES := preload("res://scripts/deck_item_icon_rules.gd")
const INVENTORY_GRID_SCRIPT := preload("res://scripts/inventory_drag_view.gd")
const INVENTORY_RULES := preload("res://scripts/inventory_drag_rules.gd")
# Сетка рюкзака в пикселях Python; масштаб 2/3 — как у окна Экономики и карты мира.
const INVENTORY_GRID_SCALE := 2.0 / 3.0
# Строки списков рюкзака и сундука: 32 px, как иконки строк в Python (ui/city_storage_window.py).
const LIST_ICON_SIZE := 32
const COMPARISON_SCRIPT := preload("res://scripts/deck_character_comparison.gd")
const GUILD_WINDOW_SCRIPT := preload("res://scripts/deck_guild_window.gd")
const SUPPLIES_SHOP_WINDOW_SCRIPT := preload("res://scripts/deck_supplies_shop_window.gd")
const LIBRARY_WINDOW_SCRIPT := preload("res://scripts/deck_library_window.gd")
const TALENT_WINDOW_SCRIPT := preload("res://scripts/deck_talent_window.gd")
const TAVERN_SHOP_WINDOW_SCRIPT := preload("res://scripts/deck_tavern_shop_window.gd")
const GROUP_BATTLE_WINDOW_SCRIPT := preload("res://scripts/deck_group_battle_window.gd")
const GROUP_RULES := preload("res://scripts/deck_group_battle_rules.gd")
const PHASE_TRANSITION_SCRIPT := preload("res://scripts/deck_phase_transition.gd")
const DECK_QUEST_LOG_SCRIPT := preload("res://scripts/deck_quest_log.gd")
const DECK_CURRENCY := preload("res://scripts/deck_currency.gd")
const ARENA_WINDOW_SCRIPT := preload("res://scripts/deck_arena_window.gd")
const DUNGEON_VIEW_SCRIPT := preload("res://scripts/deck_dungeon_view.gd")
const DUNGEON_RULES := preload("res://scripts/deck_dungeon_rules.gd")
const MAP_RULES := preload("res://scripts/deck_world_map_rules.gd")
const WORLD_MAP_RENDERER_SCRIPT := preload("res://scripts/deck_world_map_renderer.gd")
const PRESENCE_VIEW_SCRIPT := preload("res://scripts/deck_presence_view.gd")
const PRESENCE_RULES := preload("res://scripts/deck_presence_rules.gd")
const SPRITES_SCRIPT := preload("res://scripts/deck_world_sprites.gd")
const PLAYER_SPRITE_RULES := preload("res://scripts/deck_player_sprite_rules.gd")
const BACKYARD_VIEW_SCRIPT := preload("res://scripts/deck_backyard_view.gd")
const BACKYARD_RULES := preload("res://scripts/deck_backyard_rules.gd")
const ROOM_VIEW_SCRIPT := preload("res://scripts/deck_room_view.gd")
const ROOM_RULES := preload("res://scripts/deck_room_rules.gd")
const PROFILE_OVERLAY_SCRIPT := preload("res://scripts/character_profile_overlay.gd")
const PROFILE_KEY_RULES := preload("res://scripts/deck_profile_key_rules.gd")
const DECK_AUDIO_SCRIPT := preload("res://scripts/deck_audio.gd")
# Экран боя: поле DeckBattleView сверху, полоса журнала и кнопок боя снизу.
const BATTLE_VIEW_SCRIPT := preload("res://scripts/deck_battle_view.gd")
const BATTLE_EFFECTS_SCRIPT := preload("res://scripts/deck_battle_effects.gd")
const COMMENTATOR_RULES := preload("res://scripts/deck_battle_commentator_rules.gd")
const BATTLE_BAR_HEIGHT := 120
const BATTLE_BUTTONS_WIDTH := 250
const BATTLE_LOG_FONT_SIZE := 13
const BATTLE_BAR_COLOR := Color(0.085, 0.095, 0.125)
const BATTLE_BACKDROP_COLOR := Color(0.055, 0.067, 0.09)
# Префиксы ошибок для запросов, результат которых показывается в окне мира.
const FAILURE_PREFIXES := {
	"guild_claim": "Не удалось сдать задание: ",
	"supplies_catalog": "Не удалось загрузить ассортимент: ",
	"supplies_buy": "Не удалось купить товар: ",
	"library_items": "Каталог предметов недоступен: ",
	"talent_character": "Не удалось обновить данные персонажа: ",
	"talent_choose": "Не удалось выбрать улучшение: ",
	"tavern_drinks": "Напитки не загружены: ",
	"create_group": "Не удалось создать сбор: ",
	"join_group": "Не удалось вступить в сбор: ",
	"leave_group": "Не удалось выйти из сбора: ",
	"arena_start": "Не удалось начать бой на арене: ",
	"arena_status": "Состояние арены не получено: ",
	"arena_active": "Состояние арены не получено: ",
	"arena_inventory": "Инвентарь для арены не загружен: ",
	"dungeon_enter": "Не удалось войти в подземелье: ",
	"dungeon_exit": "Подземелье не закрыто на сервере: ",
	"dungeon_supplies": "Ассортимент не загружен: ",
	"dungeon_cards": "Карты подземелья не загружены: ",
	"dungeon_buy_supply": "Покупка не выполнена: ",
	"dungeon_buy_card": "Покупка не выполнена: ",
	"dungeon_fountain": "Фонтан не сработал: ",
	"dungeon_chest": "Сундук не открыт: ",
	"room_equipment": "Экипировка не загружена: ",
	"room_chest1": "Сундук 1 не загружен: ",
	"room_chest2": "Сундук 2 не загружен: ",
	"room_decks": "Колоды не загружены: ",
}
# Встречи арены как ENCOUNTERS в deck/server/arena.py: клетка, радиус запуска и буква на карте.
const ARENA_ENCOUNTERS := {
	"kobold": {"tile": Vector2i(54, 12), "radius": 1, "marker": "K", "name": "Кобольд"},
	"kobold_camp": {"tile": Vector2i(62, 18), "radius": 2, "marker": "K", "name": "Лагерь кобольдов"},
	"kobold_camp_2": {"tile": Vector2i(46, 22), "radius": 2, "marker": "K", "name": "Лагерь кобольдов"},
	"ancient_ent": {"tile": Vector2i(42, 6), "radius": 1, "marker": "E", "name": "Древний ент"},
	"skeleton": {"tile": Vector2i(34, 55), "radius": 1, "marker": "X", "name": "Скелет"},
	"necromancer": {"tile": Vector2i(48, 58), "radius": 1, "marker": "N", "name": "Некромант"},
}

var _content: VBoxContainer
var _status: Label
var _list: VBoxContainer
var _card_select: ItemList
var _card_tooltip
var _card_hover_targets: Array[Dictionary] = []
var _comparison
var _comparison_offer: Dictionary = {}
var _guild_window
var _quest_log = DECK_QUEST_LOG_SCRIPT.new()
var _pending_guild_quest := ""
var _supplies_shop_window
var _pending_supply_name := ""
var _pending_talent_name := ""
var _library_window
var _talent_window
var _tavern_shop_window
var _group_battle_window
var _group_started_offer_id := ""
var _phase_transition
var _audio
var _queued_requests: Array[Dictionary] = []
var _quantity_select: SpinBox
var _deck_name: LineEdit
var _deck_summary: Label
var _pending_action := ""
var _exit_menu
var _exit_intent := ""
var _exit_queued := false
var _server_unreachable := false
var _server_status_hud
var _view := "home"
var _character_id := 0
var _collection: Array[Dictionary] = []
var _decks: Array[Dictionary] = []
var _shop: Array[Dictionary] = []
var _deck_counts: Dictionary = {}
var _social_timer: Timer
var _battle_timer: Timer
var _social_location := "world_map"
var _social_data: Dictionary = {}
var _chat_input: LineEdit
var _chat_draft := ""
var _chat_had_focus := false
var _inventory_state: Dictionary = {}
var _inventory_view := "backpack"
var _storage_items: Array = []
var _inventory_view_select: OptionButton
var _storage_destination_select: OptionButton
var _inventory_quantity_input: LineEdit
var _inventory_block: VBoxContainer
var _inventory_grid: INVENTORY_GRID_SCRIPT
var _inventory_action_button: Button
var _inventory_drop_button: Button
var _inventory_deposit_button: Button
var _inventory_message_label: Label
var _battle_state: Dictionary = {}
var _battle_result_data: Dictionary = {}
var _battle_screen: Control
var _battle_view
var _battle_effects
var _battle_latest: Dictionary = {}
var _battle_transition_seconds := 0.0
var _battle_display_serial := 0
var _battle_game_action: Dictionary = {}
var _battle_log: VBoxContainer
var _battle_buttons: VBoxContainer
var _battle_notice: Label
var _battle_rendered: Dictionary = {}
var _battle_commentary: Dictionary = {}
var _battle_burn_mode := false
var _terrain: Dictionary = {}
var _map_position := Vector2i(12, 36)
var _map_direction := "s"
# Фигурка скользит к центру плитки _map_slide_tile: _map_slide — её положение в тайлах; окно карты следует за камерой.
var _map_slide := Vector2(12.5, 36.5)
var _map_slide_tile := Vector2i(12, 36)
# Камера — центр окна карты в тайлах: догоняет фигурку в пути, пока follow включён; перетаскивание мышью и клавиши его выключают.
var _map_camera := Vector2(12.5, 36.5)
var _map_camera_follow := true
var _map_drag_camera := Vector2.ZERO
var _map_data_window := Rect2i()
var _map_s_blocked := false
var _arena_cards_before := false
var _blocked_source: Variant = null
var _blocked_tiles: Dictionary = {}
# Время кадров карты и остаток шага: общий для всех перерисовок карты, поэтому шаг не сбрасывает анимацию.
var _map_anim_time := 0.0
var _map_walk_seconds := 0.0
var _world_map
var _presence_view
var _map_tile_size := 48
var _map_width := 128
var _map_height := 256
var _checkpoint_pending := false
var _position_dirty := false
var _return_after_checkpoint := false
var _arena_window
var _arena_session_id := ""
var _arena_pending_source := ""
var _arena_alive: Dictionary = {}
var _arena_command_serial := 0
var _dungeon_view
var _dungeon_gate_timer: Timer
var _in_dungeon := false
var _dungeon_entering := false
var _dungeon_items: Array = []
var _dungeon_cards: Array = []
var _dungeon_catalog_parts := 0
var _dungeon_pending_buy := ""
var _dungeon_battle_outcome: Dictionary = {}
var _backyard_view
var _backyard_list_home: Control
var _backyard_list_separation := 8
var _backyard_selected_offer := ""
var _backyard_profile_snapshot: Dictionary = {}
var _room_view
var _room_list_home: Control
var _room_list_separation := 8
var _room_character_snapshot: Dictionary = {}
var _profile_host: Control
var _profile_overlay
var _profile_snapshot: Dictionary = {}


func _ready() -> void:
	ApiClient.request_completed.connect(_on_api_completed)
	ApiClient.request_completed.connect(_resume_queued_requests)
	_character_id = int(GameSession.character.get("id", 0))
	ApiClient.token = GameSession.world_token
	_build_screen()
	_build_backyard_view()
	_build_room_view()
	_build_profile_overlay()
	_build_battle_screen()
	_build_comparison()
	_build_guild_window()
	_build_supplies_shop_window()
	_build_library_window()
	_build_talent_window()
	_build_tavern_shop_window()
	_build_group_battle_window()
	_build_phase_transition()
	_build_audio()
	_build_dungeon_view()
	_build_arena_window()
	_build_exit_menu()
	_build_server_status_hud()
	get_tree().root.close_requested.connect(_on_close_requested)
	get_tree().set_auto_accept_quit(false)
	if _character_id <= 0:
		_status.text = "Не выбран персонаж. Вернитесь к списку персонажей."
		return
	var world_url := str(GameSession.world.get("server_url", "")).strip_edges()
	if world_url.is_empty() or not ApiClient.set_server_url(world_url):
		_status.text = "У мира Deck не настроен корректный адрес сервера."
		return
	_request("info", HTTPClient.METHOD_GET, "/api/deck/info")


func _exit_tree() -> void:
	if ApiClient.request_completed.is_connected(_on_api_completed):
		ApiClient.request_completed.disconnect(_on_api_completed)
	if ApiClient.request_completed.is_connected(_resume_queued_requests):
		ApiClient.request_completed.disconnect(_resume_queued_requests)
	if get_tree().root.close_requested.is_connected(_on_close_requested):
		get_tree().root.close_requested.disconnect(_on_close_requested)
	if ConnectionGuard.status_received.is_connected(_server_status_hud.apply_status):
		ConnectionGuard.status_received.disconnect(_server_status_hud.apply_status)
	get_tree().set_auto_accept_quit(true)


func _process(delta: float) -> void:
	_process_exit_queue()
	_sync_backyard_view()
	_sync_room_view()
	_sync_profile_host()
	_server_status_hud.set_blocked(_exit_menu.blocks_input())
	_update_card_hover(get_global_mouse_position())
	_advance_map_animation(delta)


func _advance_map_animation(delta: float) -> void:
	# Догон только в пути: таймер шага смотрим до уменьшения, как player_target в Python.
	var walking := _map_walk_seconds > 0.0
	_map_anim_time += delta
	_map_walk_seconds = maxf(0.0, _map_walk_seconds - delta)
	var camera_before := _map_camera
	var teleported := _sync_map_slide()
	# Скорость как player_speed в Python: тайл за WALK_STEP_SECONDS (32 / 220 с), у цели фигурка встаёт без перелёта.
	_map_slide = MAP_RULES.slide_toward(_map_slide, MAP_RULES.tile_center(_map_slide_tile), delta / PLAYER_SPRITE_RULES.WALK_STEP_SECONDS)
	_update_map_camera(delta, walking)
	if teleported and _social_location == "world_map" and _view == "home":
		_render_location()
	if is_instance_valid(_world_map) and _world_map.is_inside_tree():
		if not MAP_RULES.covers_view(_map_data_window, _map_camera, MAP_VIEW_SIZE):
			_refresh_world_map()
		_world_map.set_animation(_map_anim_time, _map_walk_seconds > 0.0)
		_world_map.set_view_center(_map_camera)
		_world_map.set_figure(_map_slide)
		_world_map.update_pointer(_world_map.get_local_mouse_position(), _presence_blocked())
	if _map_camera != camera_before and is_instance_valid(_presence_view) and _presence_view.is_inside_tree():
		_presence_view.refresh_positions()


# Перемещение без шага (телепорт, возврат на карту, вход) ставит фигурку на плитку сразу, как player_x в Python.
func _sync_map_slide() -> bool:
	if _map_position == _map_slide_tile:
		return false
	_map_slide_tile = _map_position
	_map_slide = MAP_RULES.tile_center(_map_position)
	_center_map_camera()
	return true


# Догон только в пути (walking) и пока follow включён, как в Python; клавиши скроллят камеру и выключают догон; зажим краями действует всегда.
func _update_map_camera(delta: float, walking: bool) -> void:
	if _map_camera_follow and walking:
		_map_camera = MAP_RULES.follow_camera(_map_camera, _map_slide, delta)
	_update_map_s_block()
	if _map_keys_allowed():
		var scroll: Dictionary = MAP_RULES.key_scroll(_map_keys_held(), delta, float(_map_tile_size), _map_s_blocked)
		var offset: Vector2 = scroll["offset"]
		_map_camera += offset
		if scroll["moved"]:
			_map_camera_follow = false
	_map_camera = _clamped_map_camera(_map_camera)


# Камера на фигурке и догон снова включён: телепорт, Space и кнопка «К герою».
func _center_map_camera() -> void:
	_map_camera_follow = true
	_map_camera = _clamped_map_camera(_map_slide)


func _clamped_map_camera(camera: Vector2) -> Vector2:
	return MAP_RULES.clamp_camera(camera, Vector2.ZERO, Vector2(_map_width, _map_height), MAP_VIEW_SIZE)


func _map_keys_held() -> Dictionary:
	return {
		"left": Input.is_key_pressed(KEY_A) or Input.is_key_pressed(KEY_LEFT),
		"right": Input.is_key_pressed(KEY_D) or Input.is_key_pressed(KEY_RIGHT),
		"up": Input.is_key_pressed(KEY_W) or Input.is_key_pressed(KEY_UP),
		"down": Input.is_key_pressed(KEY_DOWN),
		"s": Input.is_key_pressed(KEY_S),
		"shift": Input.is_key_pressed(KEY_SHIFT),
	}


# Клавиши карты работают, пока она на экране: не открыты меню выхода или подземелье, и чат не получил фокус.
func _map_keys_allowed() -> bool:
	if not is_instance_valid(_world_map) or not _world_map.is_inside_tree() or _view != "home" or _in_dungeon or _exit_menu.blocks_input():
		return false
	var focus_owner := get_viewport().gui_get_focus_owner()
	return not (focus_owner is LineEdit)


# В бою S сбрасывает режим карт раньше, чем скролл читает клавиши. Поэтому S, нажатый в режиме карт, не скроллит до отпускания.
func _update_map_s_block() -> void:
	if not Input.is_key_pressed(KEY_S):
		_map_s_blocked = false
	elif _arena_cards_before or _arena_cards_mode():
		_map_s_blocked = true
	_arena_cards_before = _arena_cards_mode()


func _arena_cards_mode() -> bool:
	return is_instance_valid(_arena_window) and _arena_window.is_cards_mode()


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
	if intent == "quit":
		_exit_menu.begin_quit()
	else:
		_exit_menu.set_status("Сохраняем состояние…")
	_exit_queued = true
	_process_exit_queue()


func _process_exit_queue() -> void:
	if not _exit_queued or not _pending_action.is_empty():
		return
	_exit_queued = false
	_run_exit_step()


func _run_exit_step() -> void:
	_return_after_checkpoint = true
	_checkpoint_pending = true
	_save_location_checkpoint()


func _fail_exit(message: String) -> void:
	var intent := _exit_intent
	_exit_intent = ""
	_exit_queued = false
	if intent == "quit":
		_server_unreachable = true
		_exit_menu.open("Сервер недоступен: %s. Нажмите «Покинуть игру», чтобы закрыть клиент" % message)
	else:
		_exit_menu.open(message)


# Движение мыши проверяет наведение на других игроков на карте (player_at в Python); клики слой не перехватывает.
func _input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and is_instance_valid(_presence_view):
		_presence_view.forward_mouse_motion(get_global_mouse_position(), _presence_blocked())


func _unhandled_input(event: InputEvent) -> void:
	if _exit_menu.blocks_input():
		return
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_ESCAPE:
		# Поле чата с фокусом забирает Esc, как captures_keyboard() в deck/ui/chat/panel.py
		if not (_chat_input != null and _chat_input.has_focus()):
			_exit_menu.open()
		get_viewport().set_input_as_handled()
		return
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_I and _handle_profile_key():
		get_viewport().set_input_as_handled()
		return
	# Space центрирует камеру на фигурке, как в Python. Модальные окна его забирают, бой на арене — нет (как arena.handle_event).
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_SPACE and _map_keys_allowed() and not _window_open(false):
		_center_map_camera()
		get_viewport().set_input_as_handled()
		return


func _build_screen() -> void:
	var background := ColorRect.new()
	background.color = Color(0.055, 0.067, 0.09)
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(background)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(1080, 700)
	center.add_child(panel)
	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 10)
	panel.add_child(layout)
	var title := Label.new()
	title.text = "%s · Deck" % str(GameSession.world.get("name", "Мир"))
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_font_size_override("font_size", 28)
	title.add_theme_color_override("font_color", TITLE_COLOR)
	layout.add_child(title)
	_status = Label.new()
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.add_theme_color_override("font_color", MUTED_COLOR)
	layout.add_child(_status)
	var navigation := HBoxContainer.new()
	layout.add_child(navigation)
	_add_button(navigation, "Мир", _show_home)
	_add_button(navigation, "Таверна", _go_to_location.bind("tavern"))
	_add_button(navigation, "Комната", _go_to_location.bind("character_room"))
	_add_button(navigation, "Задний двор", _go_to_location.bind("backyard"))
	var account_navigation := HBoxContainer.new()
	layout.add_child(account_navigation)
	_add_button(account_navigation, "Коллекция", _load_collection)
	_add_button(account_navigation, "Колоды", _load_decks)
	_add_button(account_navigation, "Лавка карт", _load_shop)
	_add_button(account_navigation, "Рюкзак и сундуки", _show_inventory)
	_add_button(account_navigation, "К персонажам", _return_to_characters)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	layout.add_child(scroll)
	_list = VBoxContainer.new()
	_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_list.add_theme_constant_override("separation", 8)
	scroll.add_child(_list)
	_card_tooltip = CARD_TOOLTIP_SCRIPT.new()
	add_child(_card_tooltip)
	var notice := preload("res://scenes/connection_notice.tscn").instantiate()
	add_child(notice)
	notice.connection_restored.connect(_on_connection_restored)
	_social_timer = Timer.new()
	_social_timer.wait_time = 7.0
	_social_timer.timeout.connect(_refresh_social)
	add_child(_social_timer)
	_battle_timer = Timer.new()
	_battle_timer.wait_time = 2.0
	_battle_timer.timeout.connect(_refresh_battle)
	add_child(_battle_timer)


func _build_comparison() -> void:
	_comparison = COMPARISON_SCRIPT.new()
	add_child(_comparison)
	_comparison.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_comparison.stat_requested.connect(_on_comparison_stat_requested)
	_comparison.challenge_requested.connect(_on_comparison_challenge)


func _build_guild_window() -> void:
	_guild_window = GUILD_WINDOW_SCRIPT.new()
	add_child(_guild_window)
	_guild_window.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_guild_window.claim_requested.connect(_claim_guild_quest)


func _build_supplies_shop_window() -> void:
	_supplies_shop_window = SUPPLIES_SHOP_WINDOW_SCRIPT.new()
	add_child(_supplies_shop_window)
	_supplies_shop_window.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_supplies_shop_window.buy_requested.connect(_buy_supply_item)


func _build_library_window() -> void:
	_library_window = LIBRARY_WINDOW_SCRIPT.new()
	add_child(_library_window)
	_library_window.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)


func _build_talent_window() -> void:
	_talent_window = TALENT_WINDOW_SCRIPT.new()
	add_child(_talent_window)
	_talent_window.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_talent_window.choose_requested.connect(_choose_talent)


func _build_tavern_shop_window() -> void:
	_tavern_shop_window = TAVERN_SHOP_WINDOW_SCRIPT.new()
	add_child(_tavern_shop_window)
	_tavern_shop_window.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)


func _build_group_battle_window() -> void:
	_group_battle_window = GROUP_BATTLE_WINDOW_SCRIPT.new()
	add_child(_group_battle_window)
	_group_battle_window.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_group_battle_window.create_requested.connect(_create_group_battle)
	_group_battle_window.join_requested.connect(_join_group_battle)
	_group_battle_window.leave_requested.connect(_leave_group_battle)
	_group_battle_window.start_requested.connect(_start_group_battle)


func _build_phase_transition() -> void:
	_phase_transition = PHASE_TRANSITION_SCRIPT.new()
	add_child(_phase_transition)


func _build_audio() -> void:
	_audio = DECK_AUDIO_SCRIPT.new()
	add_child(_audio)


func _window_open(include_arena := true) -> bool:
	return _guild_window.is_open() or _supplies_shop_window.is_open() or _library_window.is_open() or _talent_window.is_open() or _tavern_shop_window.is_open() or (include_arena and _arena_window.is_open()) or _dungeon_view.is_open() or _group_battle_window.is_open()


func _open_supplies_shop() -> void:
	_supplies_shop_window.open(int(GameSession.character.get("coins", 0)))
	_request_when_idle("supplies_catalog", HTTPClient.METHOD_GET, "/api/deck/supplies-shop", {}, "supplies")


func _open_library() -> void:
	_library_window.open()
	_request_when_idle("library_items", HTTPClient.METHOD_GET, "/api/deck/items", {}, "library")


# Древо талантов: окно сразу показывает известные данные персонажа, затем уровень и таланты обновляются с сервера.
func _open_talent_tree() -> void:
	_talent_window.open(GameSession.character)
	if _character_id > 0:
		_request_when_idle("talent_character", HTTPClient.METHOD_GET, "/api/characters/%d" % _character_id, {}, "talents")


func _choose_talent(level: int, choice_id: String, option_name: String) -> void:
	_pending_talent_name = option_name
	_request_when_idle("talent_choose", HTTPClient.METHOD_POST, "/api/deck/talents/choose", {
		"character_id": _character_id,
		"level": level,
		"choice_id": choice_id,
	}, "talents")


func _finish_talent_choice(payload: Variant) -> void:
	var chosen_name := _pending_talent_name
	_pending_talent_name = ""
	if payload is Dictionary and payload.get("character") is Dictionary:
		_merge_talent_state(payload["character"])
		_talent_window.show_message("Выбрано: %s" % chosen_name)
	else:
		_talent_window.show_message("Не удалось выбрать улучшение: неверный ответ сервера", true)


# Из ответа берём только уровень и таланты: позиция на сервере может отставать от несохранённого шага.
func _merge_talent_state(character: Dictionary) -> void:
	for key in ["level", "talents"]:
		if character.has(key):
			GameSession.character[key] = character[key]
	_talent_window.set_character(GameSession.character)


# Лавка хозяина трактира: список напитков запрашивается при открытии и ждёт, если мир занят.
func _open_tavern_shop() -> void:
	_tavern_shop_window.open()
	_request_when_idle("tavern_drinks", HTTPClient.METHOD_GET, "/api/drinks", {}, "tavern")


func _build_dungeon_view() -> void:
	_dungeon_view = DUNGEON_VIEW_SCRIPT.new()
	add_child(_dungeon_view)
	_dungeon_view.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_dungeon_view.battle_requested.connect(_on_dungeon_battle_requested)
	_dungeon_view.merchant_requested.connect(_on_dungeon_merchant_requested)
	_dungeon_view.merchant_buy_requested.connect(_on_dungeon_merchant_buy)
	_dungeon_view.fountain_requested.connect(_on_dungeon_fountain_requested)
	_dungeon_view.chest_open_requested.connect(_on_dungeon_chest_requested)
	_dungeon_view.exit_requested.connect(_on_dungeon_exit_requested)
	_dungeon_gate_timer = Timer.new()
	_dungeon_gate_timer.one_shot = true
	_dungeon_gate_timer.wait_time = DUNGEON_RULES.GATE_SECONDS
	_dungeon_gate_timer.timeout.connect(_on_dungeon_gate_timeout)
	add_child(_dungeon_gate_timer)


# Вход открывается, если постоять на тайле входа GATE_SECONDS секунд, как _update_dungeon_gate в Python.
func _update_dungeon_gate() -> void:
	if _in_dungeon or _dungeon_entering or _view != "home" or not _outside_city_locations() or not DUNGEON_RULES.on_entrance(_map_position):
		_dungeon_gate_timer.stop()
		return
	if _dungeon_gate_timer.is_stopped():
		_dungeon_gate_timer.start()
		_status.text = "Вход в подземелье: стойте на месте…"


func _on_dungeon_gate_timeout() -> void:
	if _in_dungeon or _window_open() or not DUNGEON_RULES.on_entrance(_map_position):
		return
	_dungeon_entering = true
	_request_when_idle("dungeon_enter", HTTPClient.METHOD_POST, "/api/deck/dungeon/enter", {"character_id": _character_id})
	_status.text = "Входим в подземелье…"


func _handle_dungeon_payload(action: String, payload: Variant) -> void:
	var data: Dictionary = payload if payload is Dictionary else {}
	match action:
		"dungeon_enter":
			_dungeon_entering = false
			_in_dungeon = true
			_map_position = DUNGEON_RULES.APPROACH
			_dungeon_view.open_dungeon()
			_status.text = ""
		"dungeon_supplies":
			_dungeon_items = data.get("items", []) if data.get("items") is Array else []
			_dungeon_catalog_parts += 1
			_maybe_show_dungeon_merchant()
		"dungeon_cards":
			_dungeon_cards = data.get("cards", []) if data.get("cards") is Array else []
			_dungeon_catalog_parts += 1
			_maybe_show_dungeon_merchant()
		"dungeon_buy_supply", "dungeon_buy_card":
			_finish_dungeon_purchase(data)
		"dungeon_fountain":
			if data.get("character") is Dictionary:
				GameSession.character.merge(data["character"], true)
			_dungeon_view.fountain_result(true, "")
		"dungeon_chest":
			_finish_dungeon_chest(data)


func _handle_dungeon_failure(action: String, text: String) -> void:
	match action:
		"dungeon_enter":
			_dungeon_entering = false
			_status.text = text
		"dungeon_supplies", "dungeon_cards":
			_dungeon_view.merchant_result(text, true, "")
		"dungeon_buy_supply", "dungeon_buy_card":
			_dungeon_pending_buy = ""
			_dungeon_view.merchant_result(text, true, "")
		"dungeon_fountain":
			_dungeon_view.fountain_result(false, text)
		"dungeon_chest":
			_dungeon_view.chest_result(false, [], text)
		_:
			_status.text = text


func _on_dungeon_battle_requested(room: int, tile: Vector2i) -> void:
	_arena_pending_source = DUNGEON_RULES.battle_source(room)
	var position := DUNGEON_RULES.tile_pixel(tile, float(_map_tile_size))
	_request_when_idle("arena_start", HTTPClient.METHOD_POST, "/api/deck/arena/start", {
		"character_id": _character_id,
		"source": _arena_pending_source,
		"position_x": position.x,
		"position_y": position.y,
	})


# Итог боя комнаты: победа открывает проход, поражение и телепорт выводят из подземелья (по окончании окна).
func _apply_dungeon_battle_finish(finished: Dictionary) -> Dictionary:
	var room := int(str(finished.get("encounter_id", "")).trim_prefix("dungeon_room_"))
	var result := str(finished.get("result", ""))
	_dungeon_battle_outcome = {"room": room, "result": result}
	if result == "win":
		_dungeon_view.battle_won(room)
	else:
		_dungeon_view.battle_lost()
	finished["notes"] = []
	return finished


func _on_dungeon_merchant_requested() -> void:
	_dungeon_items = []
	_dungeon_cards = []
	_dungeon_catalog_parts = 0
	_request_when_idle("dungeon_supplies", HTTPClient.METHOD_GET, "/api/deck/supplies-shop", {}, "dungeon")
	_request_when_idle("dungeon_cards", HTTPClient.METHOD_GET, "/api/deck/dungeon/card-shop", {}, "dungeon")


func _maybe_show_dungeon_merchant() -> void:
	if _dungeon_catalog_parts < 2:
		return
	var items: Array = []
	for item in _dungeon_items:
		if item is Dictionary:
			items.append({"name": str(item.get("name", "")), "price_text": DECK_CURRENCY.format_coins(int(item.get("price", 0)))})
	var cards: Array = []
	for card in _dungeon_cards:
		if card is Dictionary:
			var available := bool(card.get("available", false))
			var price_text := DECK_CURRENCY.format_coins(int(card.get("price", 0))) if available else "временно недоступно"
			cards.append({"name": str(card.get("name", "")), "available": available, "price_text": price_text})
	_dungeon_view.show_merchant(items, cards, _coins_text())


func _on_dungeon_merchant_buy(kind: String, index: int) -> void:
	if kind == "supply":
		var item: Dictionary = _dungeon_items[index]
		_dungeon_pending_buy = str(item.get("name", ""))
		_request_when_idle("dungeon_buy_supply", HTTPClient.METHOD_POST, "/api/deck/supplies-shop/buy", {
			"character_id": _character_id,
			"item_id": int(item.get("item_id", 0)),
		}, "dungeon")
	else:
		var card: Dictionary = _dungeon_cards[index]
		_dungeon_pending_buy = str(card.get("name", ""))
		_request_when_idle("dungeon_buy_card", HTTPClient.METHOD_POST, "/api/deck/dungeon/card-shop/buy", {
			"character_id": _character_id,
			"card_key": str(card.get("key", "")),
		}, "dungeon")


func _finish_dungeon_purchase(data: Dictionary) -> void:
	var purchased := _dungeon_pending_buy
	_dungeon_pending_buy = ""
	if not data.get("character") is Dictionary:
		_dungeon_view.merchant_result("Покупка не выполнена: неверный ответ сервера", true, "")
		return
	GameSession.character.merge(data["character"], true)
	_dungeon_view.merchant_result("Куплено: %s" % purchased, false, _coins_text())


func _coins_text() -> String:
	return "У вас: %s" % DECK_CURRENCY.format_coins(int(GameSession.character.get("coins", 0)))


# Фонтан полностью восстанавливает здоровье и ману и сохраняет их, как _use_dungeon_fountain в Python.
func _on_dungeon_fountain_requested() -> void:
	var character := GameSession.character
	_request_when_idle("dungeon_fountain", HTTPClient.METHOD_PUT, "/api/characters/%d" % _character_id, {
		"hp": int(character.get("max_hp", 100)),
		"mp": int(character.get("max_mp", character.get("mp", 0))),
	}, "dungeon")


func _on_dungeon_chest_requested(request_id: String) -> void:
	_request_when_idle("dungeon_chest", HTTPClient.METHOD_POST, "/api/deck/dungeon/treasure", {
		"character_id": _character_id,
		"request_id": request_id,
	}, "dungeon")


func _finish_dungeon_chest(data: Dictionary) -> void:
	if not data.get("rewards") is Array:
		_dungeon_view.chest_result(false, [], "Сундук не открыт: неверный ответ сервера")
		return
	if data.get("character") is Dictionary:
		GameSession.character.merge(data["character"], true)
	var rewards: Array = []
	for reward in data["rewards"]:
		rewards.append(str(reward))
	_dungeon_view.chest_result(true, rewards, "")


func _on_dungeon_exit_requested() -> void:
	_leave_dungeon("")


# Выход из подземелья: квест «Зачистить подземелье» засчитывается только с открытым сундуком, как exit_dungeon в Python.
func _leave_dungeon(message: String) -> void:
	var treasure: bool = _dungeon_view.treasure_opened()
	_dungeon_view.close_dungeon()
	_in_dungeon = false
	_dungeon_gate_timer.stop()
	_map_position = DUNGEON_RULES.APPROACH
	_request_when_idle("dungeon_exit", HTTPClient.METHOD_POST, "/api/deck/dungeon/exit", {"character_id": _character_id})
	var notes := PackedStringArray()
	if treasure:
		for quest_id in _quest_log.record_progress("dungeon_clear"):
			var quest := DECK_QUEST_LOG_SCRIPT.quest_by_id(str(quest_id))
			notes.append("Задание «%s» выполнено — сдайте в гильдии" % str(quest.get("title", quest_id)))
	if not notes.is_empty():
		_status.text = "\n".join(notes)
	elif not message.is_empty():
		_status.text = message
	_save_location_checkpoint()
	_render_location()


func _build_arena_window() -> void:
	_arena_window = ARENA_WINDOW_SCRIPT.new()
	add_child(_arena_window)
	_arena_window.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_arena_window.command_requested.connect(_on_arena_command_requested)
	_arena_window.finished_confirmed.connect(_on_arena_finish_confirmed)


func _outside_city_locations() -> bool:
	return not _terrain.has("published")


# Живая встреча на тайле: по ней рисуется буква и разрешён запуск боя.
func _arena_source_at(tile: Vector2i) -> String:
	if not _outside_city_locations():
		return ""
	for source in ARENA_ENCOUNTERS:
		if ARENA_ENCOUNTERS[source]["tile"] == tile and bool(_arena_alive.get(source, true)):
			return str(source)
	return ""


# Бой начинается, когда игрок подходит к противнику ближе радиуса, как _check_kobold_encounter в Python.
func _check_arena_encounter() -> bool:
	if _window_open() or not _outside_city_locations() or not _arena_pending_source.is_empty():
		return false
	for source in ARENA_ENCOUNTERS:
		var encounter: Dictionary = ARENA_ENCOUNTERS[source]
		if not bool(_arena_alive.get(source, true)):
			continue
		var tile: Vector2i = encounter["tile"]
		var distance := maxi(absi(_map_position.x - tile.x), absi(_map_position.y - tile.y))
		if distance <= int(encounter["radius"]):
			_start_arena(str(source))
			return true
	return false


# Сервер проверяет позицию персонажа, поэтому сначала сохраняем её, а запуск боя ждёт в очереди.
func _start_arena(source: String) -> void:
	_arena_pending_source = source
	_save_location_checkpoint()
	_request_when_idle("arena_start", HTTPClient.METHOD_POST, "/api/deck/arena/start", {
		"character_id": _character_id,
		"source": source,
	})
	_status.text = "Бой на арене: %s…" % str(ARENA_ENCOUNTERS[source]["name"])


func _refresh_arena() -> void:
	if _character_id <= 0:
		return
	_request_when_idle("arena_status", HTTPClient.METHOD_GET, "/api/deck/arena/status?character_id=%d" % _character_id)
	_request_when_idle("arena_active", HTTPClient.METHOD_GET, "/api/deck/arena/active?character_id=%d" % _character_id)


func _open_arena(view: Dictionary) -> void:
	_arena_session_id = str(view.get("session_id", ""))
	_arena_window.open(view, [])
	_request_when_idle("arena_inventory", HTTPClient.METHOD_GET, "/api/inventory/%d" % _character_id, {}, "arena")


func _close_arena(message: String) -> void:
	_arena_window.close()
	_arena_session_id = ""
	if not message.is_empty():
		_status.text = message
	if _view == "home":
		_render_location()
	_refresh_arena()


# Каждая команда получает своё имя запроса: очередь не склеивает одинаковые действия.
func _on_arena_command_requested(command: Dictionary) -> void:
	_arena_command_serial += 1
	_request_when_idle("arena_cmd_%d" % _arena_command_serial, HTTPClient.METHOD_POST, "/api/deck/arena/action", {
		"character_id": _character_id,
		"session_id": _arena_session_id,
		"command": command,
	}, "arena")


func _on_arena_finish_confirmed(_finished: Dictionary) -> void:
	var outcome := _dungeon_battle_outcome
	_dungeon_battle_outcome = {}
	_close_arena("")
	if outcome.is_empty():
		return
	if str(outcome["result"]) == "win":
		_dungeon_view.set_suspended(false)
	else:
		_leave_dungeon("Вы покинули подземелье.")


func _handle_arena_payload(action: String, payload: Variant) -> void:
	var data: Dictionary = payload if payload is Dictionary else {}
	match action:
		"arena_status":
			_apply_arena_status(data)
		"arena_start":
			var dungeon_battle := _arena_pending_source.begins_with("dungeon_")
			_arena_pending_source = ""
			if data.get("arena") is Dictionary:
				if dungeon_battle:
					_dungeon_view.set_suspended(true)
				_open_arena(data["arena"])
			else:
				if dungeon_battle:
					_dungeon_view.battle_start_failed("Сервер не вернул состояние боя.")
				_status.text = "Сервер не вернул состояние боя."
		"arena_active":
			_apply_arena_active(data.get("arena"))
		"arena_inventory":
			if data.get("inventory") is Array:
				_arena_window.set_inventory(data["inventory"])
		_:
			_handle_arena_command(data)


func _handle_arena_failure(action: String, text: String) -> void:
	if action == "arena_start":
		if _arena_pending_source.begins_with("dungeon_"):
			_dungeon_view.battle_start_failed(text)
		_arena_pending_source = ""
	if action.begins_with("arena_cmd_") and _arena_window.is_open():
		_arena_window.receive_error(text)
		_request_when_idle("arena_active", HTTPClient.METHOD_GET, "/api/deck/arena/active?character_id=%d" % _character_id)
		return
	_status.text = text


func _apply_arena_status(data: Dictionary) -> void:
	var encounters: Variant = data.get("encounters")
	if not encounters is Array:
		return
	_arena_alive.clear()
	for entry in encounters:
		if entry is Dictionary:
			_arena_alive[str(entry.get("source", ""))] = bool(entry.get("alive", true))
	if _view == "home" and _social_location == "world_map":
		_render_location()


# Активный бой после входа в мир или после ошибки команды: открываем окно или синхронизируем его состояние.
func _apply_arena_active(view: Variant) -> void:
	if view is Dictionary and not (view as Dictionary).is_empty():
		if _arena_window.is_open():
			_arena_session_id = str(view.get("session_id", ""))
			_arena_window.apply_state(view)
		else:
			_open_arena(view)
	elif _arena_window.is_open():
		_close_arena("Бой на арене завершён.")


func _handle_arena_command(data: Dictionary) -> void:
	var response: Variant = data.get("arena")
	if not response is Dictionary:
		_arena_window.receive_error("Сервер не вернул состояние боя.")
		return
	var result: Dictionary = response
	var finished: Variant = result.get("finished")
	if finished is Dictionary and not (finished as Dictionary).is_empty():
		result["finished"] = _apply_arena_finish(finished)
	_arena_window.receive_response(result)


# Итог боя: персонаж и место приходят с сервера, квесты обновляются локально, как _finish_arena в Python.
func _apply_arena_finish(finished: Dictionary) -> Dictionary:
	var character: Variant = finished.get("character")
	if character is Dictionary:
		GameSession.select_character(character)
		_sync_map_from_character()
	var source := str(finished.get("encounter_id", ""))
	if source.begins_with("dungeon_"):
		return _apply_dungeon_battle_finish(finished)
	var notes: Array = []
	if str(finished.get("result", "")) == "win":
		for quest_id in _record_arena_quests(finished):
			var quest := DECK_QUEST_LOG_SCRIPT.quest_by_id(str(quest_id))
			notes.append("Задание «%s» выполнено — сдайте в гильдии" % str(quest.get("title", quest_id)))
	finished["notes"] = notes
	return finished


func _record_arena_quests(finished: Dictionary) -> Array:
	var source := str(finished.get("encounter_id", ""))
	match source:
		"kobold", "kobold_camp", "kobold_camp_2":
			return _quest_log.record_progress("kobold", int(finished.get("enemy_count", 1)))
		"ancient_ent":
			return _quest_log.record_progress("ancient_ent")
		"skeleton", "necromancer":
			return _quest_log.record_progress(source)
	return []


func _sync_map_from_character() -> void:
	var saved_x: Variant = GameSession.character.get("position_x")
	var saved_y: Variant = GameSession.character.get("position_y")
	if saved_x != null and saved_y != null:
		_map_position = Vector2i(floori(float(saved_x) / _map_tile_size), floori(float(saved_y) / _map_tile_size))
	var direction := str(GameSession.character.get("position_direction", _map_direction))
	if direction in ["n", "ne", "e", "se", "s", "sw", "w", "nw"]:
		_map_direction = direction


# Запрос ждёт, пока освободится мир: например, каталог при входе на тайл, когда идёт чекпоинт позиции.
# owner — окно, для которого нужен запрос; если окно уже закрыто, запрос не отправляется.
func _request_when_idle(action: String, method: HTTPClient.Method, path: String, body := {}, owner := "") -> void:
	for index in range(_queued_requests.size() - 1, -1, -1):
		if _queued_requests[index]["action"] == action:
			_queued_requests.remove_at(index)
	_queued_requests.append({"action": action, "method": method, "path": path, "body": body, "owner": owner})
	_flush_queued_requests()


func _flush_queued_requests() -> void:
	while _pending_action.is_empty() and not _queued_requests.is_empty():
		var item: Dictionary = _queued_requests.pop_front()
		if _owner_is_open(str(item["owner"])):
			_request(str(item["action"]), item["method"], str(item["path"]), item["body"])
			return


func _owner_is_open(owner: String) -> bool:
	match owner:
		"supplies":
			return _supplies_shop_window.is_open()
		"library":
			return _library_window.is_open()
		"talents":
			return _talent_window.is_open()
		"tavern":
			return _tavern_shop_window.is_open()
		"arena":
			return _arena_window.is_open()
		"dungeon":
			return _dungeon_view.is_open()
		"inventory":
			return _view == "inventory"
	return true


func _resume_queued_requests(_success: bool, _payload: Variant) -> void:
	_flush_queued_requests()


func _buy_supply_item(item_id: int, item_name: String) -> void:
	if _character_id <= 0:
		_supplies_shop_window.show_message("Персонаж не загружен", true)
		return
	if not _pending_action.is_empty():
		_supplies_shop_window.show_message("Подождите завершения текущего запроса.", true)
		return
	_pending_supply_name = item_name
	_supplies_shop_window.show_message("Покупаем…")
	_request("supplies_buy", HTTPClient.METHOD_POST, "/api/deck/supplies-shop/buy", {
		"character_id": _character_id,
		"item_id": item_id,
	})


func _finish_supply_purchase(payload: Variant) -> void:
	var item_name := _pending_supply_name
	_pending_supply_name = ""
	if not payload is Dictionary:
		_supplies_shop_window.show_message("Не удалось купить товар: неверный ответ сервера", true)
		return
	var character: Variant = payload.get("character")
	if character is Dictionary:
		GameSession.character.merge(character, true)
	_supplies_shop_window.set_balance(int(GameSession.character.get("coins", 0)))
	_supplies_shop_window.show_message("Куплено: %s" % item_name)


func _add_button(parent: Node, text: String, callback: Callable) -> Button:
	var button := Button.new()
	button.text = text
	button.custom_minimum_size.y = 40
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.focus_mode = Control.FOCUS_NONE
	button.pressed.connect(callback)
	parent.add_child(button)
	return button


func _add_note(text: String) -> Label:
	var note := Label.new()
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	note.text = text
	_list.add_child(note)
	return note


func _bind_card_hover(control: Control, card: Dictionary) -> void:
	_card_hover_targets.append({"control": control, "card": card})


func _request(action: String, method: HTTPClient.Method, path: String, body: Dictionary = {}) -> void:
	if not _pending_action.is_empty():
		_status.text = "Подождите завершения текущего запроса."
		return
	_pending_action = action
	ApiClient.request_json(method, path, body)


func _clear_list() -> void:
	_card_hover_targets.clear()
	for child in _list.get_children():
		_list.remove_child(child)
		if child == _inventory_block:
			_park_inventory_block()
		else:
			child.queue_free()


func _show_home() -> void:
	_go_to_location("world_map")


# Без затемнения: первая загрузка, закрытие рюкзака и повторный показ локации. Переходы идут через _go_to_location.
func _enter_location(location: String) -> void:
	if _battle_is_active():
		_status.text = "Сначала завершите текущий бой."
		return
	_audio.change_location(_social_location, location)
	_show_location(location)


# Смена локации с затемнением, как DeckWorld.go() в Python: музыка гаснет сразу, локация меняется после затемнения.
func _go_to_location(location: String) -> void:
	if _battle_is_active():
		_status.text = "Сначала завершите текущий бой."
		return
	if location == _social_location and _view != "battle":
		_enter_location(location)
		return
	if SCENE_TRANSITION.run(get_tree(), _show_location.bind(location)) != null:
		_audio.change_location(_social_location, location)


func _show_location(location: String) -> void:
	if location == "world_map" and _social_location == "tavern" and not _terrain.has("published"):
		_map_position = TAVERN_EXIT_TILE
	_group_battle_window.close()
	# Возврат из рюкзака продолжает визит в комнату: вкладка, данные и карточка сохраняются, как в Python.
	var back_from_inventory := _view == "inventory" and _social_location == location
	var previous_location := _social_location
	_social_location = location
	_view = "home" if location == "world_map" else location
	if previous_location != location:
		_profile_overlay.close()
	GameSession.character["zone"] = location
	_checkpoint_pending = true
	if location == "character_room" and not back_from_inventory:
		_room_view.reset()
	_render_location()
	_save_location_checkpoint()
	if location == "character_room":
		_request_room_tab(_room_view.current_tab())
	if location == "world_map":
		_refresh_arena()


func _show_inventory() -> void:
	if _battle_is_active():
		_status.text = "Нельзя открыть инвентарь во время боя."
		return
	_view = "inventory"
	_request_when_idle("inventory_load", HTTPClient.METHOD_GET, "/api/inventory/%d" % _character_id, {}, "inventory")


func _render_location() -> void:
	_sync_backyard_view()
	_sync_room_view()
	_sync_profile_host()
	if _social_location == "backyard":
		if _view == "backyard":
			_render_backyard()
		return
	_chat_draft = _chat_input.text if _chat_input != null else ""
	_chat_had_focus = _chat_input != null and _chat_input.has_focus()
	_clear_list()
	_chat_input = null
	# Комната персонажа показывает свой вид (deck_room_view.gd), поэтому в списке остаётся только чат.
	if _social_location != "character_room":
		_add_note("%s · уровень %d · здоровье %s/%s · мана %s/%s" % [
			str(GameSession.character.get("name", "Персонаж")),
			int(GameSession.character.get("level", 1)),
			str(GameSession.character.get("hp", "—")),
			str(GameSession.character.get("max_hp", "—")),
			str(GameSession.character.get("mp", "—")),
			str(GameSession.character.get("max_mp", "—")),
		])
	match _social_location:
		"world_map":
			_add_note("Карта мира · WASD и стрелки двигают камеру, Space — камера на фигурке, ходьба — кликом по соседней плитке или кнопками со стрелками. Подойдите к T (таверна), G (гильдия), S (магазин припасов), L (библиотека) или Д (древо талантов).")
			_render_world_map()
		"tavern":
			_add_note("Таверна — общий узел мира. Из неё можно перейти в комнату персонажа или на задний двор; хозяин трактира показывает напитки.")
			_add_button(_list, "Хозяин трактира — напитки", _open_tavern_shop)
			_add_button(_list, "Выйти на городской тракт", _go_to_location.bind("world_map"))
			_add_button(_list, "В комнату персонажа", _go_to_location.bind("character_room"))
			_add_button(_list, "На задний двор", _go_to_location.bind("backyard"))
	_render_social()


# Комната персонажа: вид deck_room_view.gd с вкладками, мир грузит разделы. Список мира (чат) переезжает в вид,
# как на заднем дворе. Разделы идут через очередь запросов, чтобы не мешать другим действиям мира.
func _build_room_view() -> void:
	_room_view = ROOM_VIEW_SCRIPT.new()
	add_child(_room_view)
	_room_list_home = _list.get_parent() as Control
	_room_list_separation = _list.get_theme_constant("separation")
	_room_view.tab_selected.connect(_request_room_tab)
	_room_view.door_requested.connect(_go_to_location.bind("tavern"))
	_room_view.stat_requested.connect(_on_comparison_stat_requested)
	_room_view.level_requested.connect(_on_backyard_level_requested)
	_room_view.backpack_requested.connect(_show_inventory)


func _sync_room_view() -> void:
	var active := _social_location == "character_room" and _view == "character_room"
	if active:
		_room_view.dock_list(_list)
	else:
		_room_view.undock_list(_list, _room_list_home, _room_list_separation)
	_room_view.set_active(active)
	if not active:
		return
	_room_view.set_message(_status.text)
	if GameSession.character != _room_character_snapshot:
		_room_character_snapshot = GameSession.character.duplicate(true)
		_room_view.set_character(_room_character_snapshot)


# Карточка персонажа на карте и в таверне, как оверлей DeckWorld в Python. Хост прячет карточку, пока открыт рюкзак,
# а при уходе с карты, из таверны и рюкзака закрывает её: в Python новый экран создаёт новую карточку.
func _build_profile_overlay() -> void:
	_profile_host = Control.new()
	_profile_host.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_profile_host.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_profile_host)
	_profile_overlay = PROFILE_OVERLAY_SCRIPT.new()
	_profile_overlay.stat_requested.connect(_on_comparison_stat_requested)
	_profile_overlay.level_requested.connect(_on_backyard_level_requested)
	_profile_overlay.backpack_requested.connect(_show_inventory)
	_profile_host.add_child(_profile_overlay)


func _sync_profile_host() -> void:
	if _view != "home" and _view != "tavern" and _view != "inventory":
		_profile_overlay.close()
	var shown := _view == "home" or _view == "tavern"
	if _profile_host.visible != shown:
		_profile_host.visible = shown
	if _profile_overlay.is_open() and GameSession.character != _profile_snapshot:
		_profile_snapshot = GameSession.character.duplicate(true)
		_profile_overlay.update_profile(_profile_snapshot)


# I как DeckWorld.handle_event в Python: рюкзак закрывается, на карте, в таверне и в комнате переключает карточку.
func _handle_profile_key() -> bool:
	var focus_owner := get_viewport().gui_get_focus_owner()
	var action: String = PROFILE_KEY_RULES.action_for(_view, _social_location, focus_owner is LineEdit, not GameSession.character.is_empty())
	match action:
		PROFILE_KEY_RULES.CLOSE_BACKPACK:
			_enter_location(_social_location)
		PROFILE_KEY_RULES.TOGGLE:
			_toggle_profile()
		_:
			return false
	return true


func _toggle_profile() -> void:
	var opened := false
	if _social_location == "character_room":
		opened = _room_view.toggle_profile()
	else:
		opened = _toggle_world_profile()
	if opened:
		_request_profile_equipment()


func _toggle_world_profile() -> bool:
	if _profile_overlay.is_open():
		_profile_overlay.close()
		return false
	_profile_snapshot = GameSession.character.duplicate(true)
	_profile_overlay.open(_profile_snapshot)
	return true


# Экипировка карточки: один запрос, когда в персонаже её ещё нет, как refresh_equipment_state() в Python.
func _request_profile_equipment() -> void:
	if _character_id <= 0 or GameSession.character.has("equipment") or _pending_action == "profile_equipment":
		return
	_request_when_idle("profile_equipment", HTTPClient.METHOD_GET, "/api/inventory/%d" % _character_id)


# Экипировка и бонусы из ответа /api/inventory/{id}: поля те же, что у refresh_equipment_state() в Python.
func _store_equipment(state: Dictionary) -> void:
	var equipment: Variant = state.get("equipment", {})
	var bonuses: Variant = state.get("bonuses", {})
	GameSession.character["equipment"] = equipment.duplicate(true) if equipment is Dictionary else {}
	GameSession.character["equipment_bonuses"] = bonuses.duplicate(true) if bonuses is Dictionary else {}


func _request_room_tab(tab: String) -> void:
	if _view != "character_room":
		return
	for section in ROOM_RULES.sections_for_tab(tab):
		_request_room_section(str(section))


func _request_room_section(section: String) -> void:
	if not ROOM_RULES.needs_load(_room_view.section_state(section)):
		return
	_room_view.set_section_state(section, ROOM_RULES.STATE_LOADING)
	_request_when_idle(ROOM_RULES.section_action(section), HTTPClient.METHOD_GET, ROOM_RULES.section_path(section, _character_id))


func _apply_room_payload(action: String, payload: Variant) -> void:
	var section := ROOM_RULES.section_from_action(action)
	var data: Variant = ROOM_RULES.section_payload(section, payload)
	if data == null:
		_room_view.set_section_state(section, ROOM_RULES.STATE_FAILED)
		_status.text = "Сервер вернул некорректные данные комнаты."
		return
	_room_view.set_section_data(section, data)


func _show_battle_state() -> void:
	_render_battle()
	if str(_battle_state.get("phase", "")) == "result":
		_battle_timer.stop()
	else:
		_battle_timer.start()


# Ответ или опрос боя. Музыка и звуки идут от прихода снимка, как раньше; переход фазы запускается только после
# ответа на действие. Показ и очередь шагов ведёт DeckBattleEffects (submit): снимок может показаться позже.
func _receive_battle(latest: Dictionary, previous_phase: String, action: String) -> void:
	_battle_latest = latest
	var next_phase := str(latest.get("phase", ""))
	var transition := "" if action == "battle_active" else PHASE_TRANSITION_SCRIPT.transition_kind(previous_phase, next_phase)
	_audio.on_battle_update(latest)
	if transition.is_empty():
		if not _phase_transition.is_active():
			_audio.sync_battle_music(latest)
	else:
		_battle_transition_seconds = _audio.fade_out_for_transition()
	if next_phase == "result":
		_battle_timer.stop()
	else:
		_battle_timer.start()
	var context := {"action": "", "card_key": "", "allow_transition": action != "battle_active"}
	if action == "battle_action" and not _battle_game_action.is_empty():
		context["action"] = str(_battle_game_action.get("action", ""))
		context["card_key"] = str(_battle_game_action.get("card_key", ""))
	_battle_game_action = {}
	_battle_effects.submit(latest, _battle_state, context)


# Показ состояния из очереди: без перехода сразу; с переходом фазы — после затемнения, как раньше.
func _on_battle_display_requested(state: Dictionary, transition: String) -> void:
	_battle_display_serial += 1
	if transition.is_empty() or _phase_transition.is_active():
		_apply_battle_display(state)
		_battle_effects.display_done()
		return
	_phase_transition.play(_finish_battle_transition.bind(state, _battle_display_serial), _battle_transition_seconds)


# Колбэк устаревшего перехода (его сменил более новый показ) ничего не меняет.
func _finish_battle_transition(state: Dictionary, serial: int) -> void:
	if serial != _battle_display_serial:
		return
	if _view == "battle" and str(state.get("battle_id", "")) == str(_battle_latest.get("battle_id", "")):
		_audio.sync_battle_music(_battle_latest)
		_apply_battle_display(state)
	_battle_effects.display_done()


func _apply_battle_display(state: Dictionary) -> void:
	_battle_state = state
	_show_battle_state()


func _battle_is_active() -> bool:
	return _view == "battle" and str(_battle_state.get("phase", "")) != "result"


# Вход в бой с затемнением, как go("duel") в Python; если переход уже идёт, бой откроется под его кадром.
func _start_battle_transition(battle: Dictionary, action: String) -> void:
	if SCENE_TRANSITION.run(get_tree(), _open_battle_after_fade.bind(battle, action)) == null:
		_open_battle(battle, action)


# Опрос активного боя мог открыть его раньше: тогда ответ на старт уже устарел.
func _open_battle_after_fade(battle: Dictionary, action: String) -> void:
	if _view != "battle":
		_open_battle(battle, action)


func _open_battle(battle: Dictionary, action: String) -> void:
	var previous_phase := str(_battle_state.get("phase", "")) if _view == "battle" else ""
	_battle_result_data.clear()
	_view = "battle"
	_social_timer.stop()
	_receive_battle(battle, previous_phase, action)


func _start_duel(offer_id: String) -> void:
	if offer_id.is_empty():
		_status.text = "Сервер не вернул идентификатор принятого вызова."
		return
	_social_timer.stop()
	_request("battle_start", HTTPClient.METHOD_POST, "/api/deck/battle/start", {
		"character_id": _character_id,
		"offer_id": offer_id,
	})


func _refresh_battle() -> void:
	if _view != "battle" or not _pending_action.is_empty():
		return
	_request("battle_active", HTTPClient.METHOD_GET,
		"/api/deck/battle/active?character_id=%d" % _character_id)


func _battle_action(action: String, card_key := "") -> void:
	var battle_id := str(_battle_state.get("battle_id", ""))
	if battle_id.is_empty():
		_report_status("battle_action", "Сервер не вернул идентификатор боя.", true)
		return
	_audio.on_battle_action(action)
	if _pending_action.is_empty():
		_battle_game_action = {"action": action, "card_key": card_key}
	_battle_request("battle_action", HTTPClient.METHOD_POST, "/api/deck/battle/action", {
		"character_id": _character_id,
		"battle_id": battle_id,
		"action": action,
		"card_key": card_key,
	})


# Запрос кнопки боя: при занятом соединении сообщение видно на экране боя, а не в скрытой строке статуса.
func _battle_request(action: String, method: HTTPClient.Method, path: String, body: Dictionary) -> void:
	if not _pending_action.is_empty():
		_report_status(action, "Подождите завершения текущего запроса.", true)
		return
	_request(action, method, path, body)


func _finish_battle() -> void:
	var battle_id := str(_battle_state.get("battle_id", ""))
	_battle_request("battle_finish", HTTPClient.METHOD_POST, "/api/deck/battle/finish", {
		"character_id": _character_id,
		"battle_id": battle_id,
	})


# Экран боя: поле и карты рисует DeckBattleView; под полем — журнал того, что макет не показывает, и кнопки боя.
# Список мира не очищается: его узлы (чат, ввод) нужны после боя, поэтому он только скрывается.
func _render_battle() -> void:
	_card_hover_targets.clear()
	(_list.get_parent() as Control).visible = false
	get_viewport().gui_release_focus()
	_battle_screen.visible = true
	_battle_rendered = _battle_state
	var phase := str(_battle_state.get("phase", ""))
	var fighter: Dictionary = _battle_state.get("fighter", {})
	var confirmed := bool(_battle_state.get("confirmed", false))
	_battle_burn_mode = _battle_burn_mode and phase == "planning" and not confirmed
	var busy: bool = _battle_effects.is_busy()
	_battle_view.set_burn_mode(_battle_burn_mode)
	_battle_view.set_input_locked(busy)
	_battle_view.set_snapshot(_battle_state)
	for card_view in _battle_view.card_views():
		_bind_card_hover(card_view, card_view.card)
	_battle_clear_bar()
	_add_battle_note("%s · %s · ход %d" % [
		str(fighter.get("name", "Вы")),
		"драфт" if phase == "draft" else phase,
		int(_battle_state.get("turn", 0)),
	])
	if busy and phase != "draft":
		_add_battle_note("Розыгрыш хода…")
	elif phase == "draw":
		_add_battle_note("Выберите карту для добора.")
	elif phase == "planning":
		_add_battle_note("До автоматического действия: %d сек." % int(_battle_state.get("seconds_left", 0)))
		if confirmed:
			_add_battle_note("Ход подтверждён. Ожидаем соперника…")
		else:
			_add_battle_note("Выберите до двух карт, затем подтвердите ход. Можно сжечь одну карту для восстановления ресурса.")
			if _battle_burn_mode:
				_add_battle_note("Сжигание: нажмите карту руки или выбора, которую нужно сжечь.")
			_add_button(_battle_buttons, "Подтвердить ход", _battle_action.bind("confirm", ""))
			_add_button(_battle_buttons, "Отменить сжигание" if _battle_burn_mode else "Сжечь карту", _toggle_battle_burn)
	elif phase == "result":
		if _battle_result_data.is_empty():
			_add_battle_note("Бой завершён сервером. Сохраняем результат и награды…")
			_add_button(_battle_buttons, "Получить итог боя", _finish_battle)
		else:
			_add_battle_note("HP после боя: %s · MP: %s" % [
				str(_battle_result_data.get("character", {}).get("hp", "")),
				str(_battle_result_data.get("character", {}).get("mp", "")),
			])
			var reward: Variant = _battle_result_data.get("reward")
			if reward is Dictionary and not reward.is_empty():
				_add_battle_note("Награда: %s" % str(reward.get("name", reward.get("key", "карта"))))
			var group_result: Variant = _battle_result_data.get("group")
			if group_result is Dictionary:
				if str(group_result.get("status", "")) == "completed":
					var team_scores: Array = group_result.get("team_scores", [0, 0])
					_add_battle_note("Командный итог · счёт %s : %s" % [
						str(team_scores[0] if team_scores.size() > 0 else 0),
						str(team_scores[1] if team_scores.size() > 1 else 0),
					])
				else:
					_add_battle_note("Командный матч продолжается: ждём остальные парные дуэли.")
			_add_button(_battle_buttons, "Вернуться на задний двор", _return_from_battle)
	var commentary_lines := (_battle_commentary.get("lines", []) as Array).size()
	_battle_commentary = COMMENTATOR_RULES.next_log(_battle_commentary, _battle_state)
	var lines: Array = _battle_commentary.get("lines", [])
	for line in lines:
		_add_battle_commentary(line)
	if lines.size() != commentary_lines:
		_scroll_battle_log_to_end()


# Полноэкранный слой боя поверх мира; вид сам масштабируется под область над полосой.
func _build_battle_screen() -> void:
	_battle_screen = Control.new()
	add_child(_battle_screen)
	_battle_screen.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_battle_screen.visible = false
	var backdrop := ColorRect.new()
	backdrop.color = BATTLE_BACKDROP_COLOR
	backdrop.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_battle_screen.add_child(backdrop)
	backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_battle_view = BATTLE_VIEW_SCRIPT.new()
	_battle_screen.add_child(_battle_view)
	_battle_view.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_battle_view.offset_bottom = -BATTLE_BAR_HEIGHT
	_battle_view.set_hit_overlay_visible(false)
	_battle_view.set_pile_counts(-1, -1)
	_battle_view.card_pressed.connect(_on_battle_card_pressed)
	_battle_view.card_hovered.connect(_on_battle_card_hovered)
	_battle_effects = BATTLE_EFFECTS_SCRIPT.new()
	_battle_screen.add_child(_battle_effects)
	_battle_effects.attach(_battle_view)
	_battle_effects.display_requested.connect(_on_battle_display_requested)
	var bar := PanelContainer.new()
	_battle_screen.add_child(bar)
	bar.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	bar.offset_top = -BATTLE_BAR_HEIGHT
	var bar_style := StyleBoxFlat.new()
	bar_style.bg_color = BATTLE_BAR_COLOR
	bar_style.set_content_margin_all(8)
	bar.add_theme_stylebox_override("panel", bar_style)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	bar.add_child(row)
	var log_column := VBoxContainer.new()
	log_column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(log_column)
	_battle_notice = Label.new()
	_battle_notice.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_battle_notice.add_theme_font_size_override("font_size", BATTLE_LOG_FONT_SIZE)
	_battle_notice.add_theme_color_override("font_color", MUTED_COLOR)
	_battle_notice.visible = false
	log_column.add_child(_battle_notice)
	var log_scroll := ScrollContainer.new()
	log_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	log_column.add_child(log_scroll)
	_battle_log = VBoxContainer.new()
	_battle_log.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_battle_log.add_theme_constant_override("separation", 2)
	log_scroll.add_child(_battle_log)
	_battle_buttons = VBoxContainer.new()
	_battle_buttons.custom_minimum_size.x = BATTLE_BUTTONS_WIDTH
	row.add_child(_battle_buttons)


func _battle_clear_bar() -> void:
	for container in [_battle_log, _battle_buttons]:
		for child in container.get_children():
			container.remove_child(child)
			child.queue_free()


func _add_battle_note(text: String) -> void:
	var note := Label.new()
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	note.add_theme_font_size_override("font_size", BATTLE_LOG_FONT_SIZE)
	note.text = text
	_battle_log.add_child(note)


# Строка комментатора: цвета исходов нужны, поэтому строка идёт в RichTextLabel (BBCode из правил комментатора).
func _add_battle_commentary(line: Array) -> void:
	var note := RichTextLabel.new()
	note.bbcode_enabled = true
	note.fit_content = true
	note.scroll_active = false
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	note.mouse_filter = Control.MOUSE_FILTER_IGNORE
	note.add_theme_font_size_override("normal_font_size", BATTLE_LOG_FONT_SIZE)
	note.text = COMMENTATOR_RULES.line_bbcode(line)
	_battle_log.add_child(note)


# Новая строка комментатора видна сразу: журнал прокручивается к концу, когда раскладка успела обновиться.
func _scroll_battle_log_to_end() -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	if not is_instance_valid(_battle_log):
		return
	var scroll := _battle_log.get_parent() as ScrollContainer
	if scroll != null:
		scroll.scroll_vertical = int(scroll.get_v_scroll_bar().max_value)


# Нажатие карты боя: зона и индекс из DeckBattleView переводятся в ключ по отрисованному снимку и уходят
# в те же обработчики, что раньше вызывали кнопки «Выбрать», «Снять выбор», «Сжечь» и выбор в драфте.
func _on_battle_card_pressed(zone: String, index: int) -> void:
	var card_key := _battle_card_key(zone, index)
	if card_key.is_empty():
		return
	if _battle_burn_mode and (zone == "hand" or zone == "selected"):
		_battle_burn_mode = false
		_render_battle()
		_battle_action("burn", card_key)
		return
	match zone:
		"hand":
			_battle_action("select", card_key)
		"selected":
			_battle_action("deselect", card_key)
		"table":
			_battle_action("pick_starting" if str(_battle_rendered.get("draft_mode", "")) == "starting" else "pick_redraft", card_key)
		"draw_choices":
			_battle_action("choose_draw", card_key)


func _battle_card_key(zone: String, index: int) -> String:
	var cards: Variant = _battle_rendered.get(zone, [])
	if not cards is Array or index < 0 or index >= cards.size():
		return ""
	var item: Variant = cards[index]
	return str(item.get("key", "")) if item is Dictionary else str(item)


func _toggle_battle_burn() -> void:
	_battle_burn_mode = not _battle_burn_mode
	_render_battle()


# Подсказка карты боя: сигнал вида и опрос наведения (_bind_card_hover) показывают одну и ту же карту.
func _on_battle_card_hovered(card: Dictionary) -> void:
	if card.is_empty():
		_card_tooltip.hide_card()
	else:
		_card_tooltip.show_card(card)


func _return_from_battle() -> void:
	_battle_timer.stop()
	if _battle_is_active():
		_status.text = "Сначала завершите текущий бой."
		return
	SCENE_TRANSITION.run(get_tree(), _leave_battle_view)


func _leave_battle_view() -> void:
	_enter_location("backyard")
	(_list.get_parent() as Control).visible = true
	_battle_state.clear()
	_battle_commentary = {}
	_battle_effects.clear()
	_battle_latest = {}
	_battle_game_action = {}
	_battle_burn_mode = false
	_battle_notice.text = ""
	_battle_notice.visible = false
	_battle_screen.visible = false


func _render_world_map() -> void:
	_add_note("Позиция: %d, %d · вы — фигурка персонажа (стойка и бег) · T таверна · G гильдия · S припасы · L библиотека · Д древо талантов · стены, кристалл и препятствия рисуются фигурами" % [
		_map_position.x,
		_map_position.y,
	])
	if _outside_city_locations():
		_add_note("Бой на арене: K — кобольды, E — древний ент, X — скелет, N — некромант. Подойдите вплотную — бой начнётся сам. D — вход в подземелье: стойте на нём 5 секунд.")
	var controls := HBoxContainer.new()
	_list.add_child(controls)
	_add_button(controls, "↑", _move_world.bind(0, -1))
	_add_button(controls, "←", _move_world.bind(-1, 0))
	_add_button(controls, "↓", _move_world.bind(0, 1))
	_add_button(controls, "→", _move_world.bind(1, 0))
	_add_button(controls, "К герою", _center_map_camera)
	var world_map = WORLD_MAP_RENDERER_SCRIPT.new()
	world_map.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	_list.add_child(world_map)
	world_map.tile_clicked.connect(_on_world_map_tile_clicked)
	world_map.view_drag_started.connect(_on_world_map_drag_started)
	world_map.view_dragged.connect(_on_world_map_dragged)
	_world_map = world_map
	_refresh_world_map()


# Плитки и маркеры строятся под окно камеры. Карта остаётся той же, поэтому перетаскивание не прерывается при перестройке.
func _refresh_world_map() -> void:
	var state := _world_map_state()
	_map_data_window = state["data_window"]
	_world_map.configure(state)
	# Слой других игроков лежит внутри слоя фигурок: он рисуется поверх фигурки игрока, как draw_active_players в Python,
	# а у карты остаются прежние дочерние узлы.
	if is_instance_valid(_presence_view):
		_presence_view.queue_free()
	_presence_view = PRESENCE_VIEW_SCRIPT.new()
	_figures_layer(_world_map).add_child(_presence_view)
	_presence_view.configure({
		"occupants": _social_data.get("occupants", []),
		"own_id": str(_character_id),
		"location": "world_map",
		"world_to_local": _map_world_to_local,
	})


func _figures_layer(world_map: Control) -> Node:
	for child in world_map.get_children():
		if child.get_script() == SPRITES_SCRIPT:
			return child
	return world_map


# Мировые координаты игроков (position_x, position_y из social) в окно карты: то же окно и тайл, что у фигурки.
func _map_world_to_local(world: Vector2) -> Vector2:
	return MAP_RULES.world_to_view(world, MAP_RULES.view_origin(_map_camera, MAP_VIEW_SIZE), float(_map_tile_size))


# Наведение на игрока отключено, пока окно закрывает карту (в Python: открытые окна и интерфейс боя).
func _presence_blocked() -> bool:
	return _exit_menu.blocks_input() or _window_open() or _comparison.visible


# Состояние для deck_world_map_renderer.gd: маркеры букв, твёрдые тайлы, соседние тайлы для шага и фигурка игрока.
func _world_map_state() -> Dictionary:
	_sync_map_slide()
	var markers := {}
	var solid: Array[Vector2i] = []
	var steppable: Array[Vector2i] = []
	var map_size := Vector2i(_map_width, _map_height)
	var data_window := MAP_RULES.data_window(_map_position, _map_camera, MAP_VIEW_SIZE)
	for y in range(data_window.position.y, data_window.end.y):
		for x in range(data_window.position.x, data_window.end.x):
			var tile := Vector2i(x, y)
			var blocked := _is_world_tile_solid(tile)
			var arena_source := _arena_source_at(tile)
			var marker := MAP_RULES.marker_for({
				"tavern": _is_tavern_tile(tile),
				"guild": _is_guild_tile(tile),
				"supplies": _is_supplies_shop_tile(tile),
				"library": _is_library_tile(tile),
				"talent": _is_talent_tile(tile),
				"solid": blocked,
				"dungeon": _outside_city_locations() and DUNGEON_RULES.on_entrance(tile),
				"arena": ARENA_ENCOUNTERS.get(arena_source, {}),
			})
			if not marker.is_empty():
				markers[tile] = marker
			if blocked:
				solid.append(tile)
			if MAP_RULES.is_neighbour(tile, _map_position) and MAP_RULES.in_map(tile, map_size) and (not blocked or _is_tavern_tile(tile)):
				steppable.append(tile)
	return {
		"terrain": _terrain,
		"center": _map_position,
		"view_center": _map_camera,
		"figure": _map_slide,
		"data_window": data_window,
		"view_size": MAP_VIEW_SIZE,
		"map_size": map_size,
		"tile_px": float(_map_tile_size),
		"markers": markers,
		"solid": solid,
		"steppable": steppable,
		"anim_time": _map_anim_time,
		"walking": _map_walk_seconds > 0.0,
		"direction": _map_direction,
		"player_name": str(GameSession.character.get("name", "Герой")),
	}


# Клик по соседнему свободному тайлу делает шаг; дальние и твёрдые тайлы игнорируются, как отключённые кнопки раньше.
func _on_world_map_tile_clicked(tile: Vector2i) -> void:
	if not MAP_RULES.is_neighbour(tile, _map_position):
		return
	if _is_world_tile_solid(tile) and not _is_tavern_tile(tile):
		return
	var step := tile - _map_position
	_move_world(step.x, step.y)


func _on_world_map_drag_started() -> void:
	_map_drag_camera = _map_camera


# Перетаскивание: камера от точки нажатия на смещение мыши в тайлах; догон выключается, как в Python.
func _on_world_map_dragged(offset: Vector2) -> void:
	_map_camera_follow = false
	_map_camera = _clamped_map_camera(_map_drag_camera - offset)


func _move_world(dx: int, dy: int) -> void:
	if _view != "home":
		return
	var next_tile := _map_position + Vector2i(dx, dy)
	if next_tile.x < 0 or next_tile.y < 0 or next_tile.x >= _map_width or next_tile.y >= _map_height:
		return
	if _is_world_tile_solid(next_tile) and not _is_tavern_tile(next_tile):
		_status.text = "Путь перекрыт препятствием."
		return
	var previous_tile := _map_position
	_map_position = next_tile
	_map_slide_tile = next_tile
	_map_direction = PLAYER_SPRITE_RULES.direction_for(Vector2(dx, dy))
	_map_walk_seconds = PLAYER_SPRITE_RULES.WALK_STEP_SECONDS
	_map_camera_follow = true
	GameSession.character["zone"] = "world_map"
	GameSession.character["position_x"] = float(_map_position.x * _map_tile_size + _map_tile_size / 2)
	GameSession.character["position_y"] = float(_map_position.y * _map_tile_size + _map_tile_size / 2)
	GameSession.character["position_direction"] = _map_direction
	_position_dirty = true
	if _is_tavern_tile(_map_position):
		_go_to_location("tavern")
		return
	_render_location()
	queue_redraw()
	_update_dungeon_gate()
	if _check_arena_encounter():
		return
	if _is_guild_tile(_map_position) and not _is_guild_tile(previous_tile):
		_guild_window.open(_quest_log)
	elif _is_supplies_shop_tile(_map_position) and not _is_supplies_shop_tile(previous_tile):
		_open_supplies_shop()
	elif _is_library_tile(_map_position) and not _is_library_tile(previous_tile):
		_open_library()
	elif _is_talent_tile(_map_position) and not _is_talent_tile(previous_tile):
		_open_talent_tree()


func _is_tavern_tile(tile: Vector2i) -> bool:
	return not _terrain.has("published") and MAP_RULES.TAVERN_BOUNDS.has_point(tile)


# Гильдия: тайлы X 19..23, Y 26..28 (deck/map_config.py GUILD_BOUNDS). Окно открывается при входе извне.
func _is_guild_tile(tile: Vector2i) -> bool:
	return not _terrain.has("published") and MAP_RULES.GUILD_BOUNDS.has_point(tile)


# Магазин припасов: тайлы X 14..18, Y 26..28 (deck/map_config.py SUPPLIES_SHOP_BOUNDS).
func _is_supplies_shop_tile(tile: Vector2i) -> bool:
	return not _terrain.has("published") and MAP_RULES.SUPPLIES_BOUNDS.has_point(tile)


# Библиотека: тайлы X 19..23, Y 40..42 (deck/map_config.py LIBRARY_BOUNDS).
func _is_library_tile(tile: Vector2i) -> bool:
	return not _terrain.has("published") and MAP_RULES.LIBRARY_BOUNDS.has_point(tile)


# Древо талантов: тайлы X 22..23, Y 37..38 (deck/ui/world_map_scene.py _talent_tree_object).
func _is_talent_tile(tile: Vector2i) -> bool:
	return not _terrain.has("published") and MAP_RULES.TALENT_BOUNDS.has_point(tile)


func _is_city_wall(tile: Vector2i) -> bool:
	var city: Variant = _terrain.get("city_area", {})
	if not city is Dictionary:
		return false
	for wall in city.get("wall_tiles", []):
		if wall is Array and wall.size() >= 2 and int(wall[0]) == tile.x and int(wall[1]) == tile.y:
			return true
	return false


func _is_crystal_tile(tile: Vector2i) -> bool:
	for map_object in _terrain.get("objects", []):
		if not map_object is Dictionary:
			continue
		var left := int(map_object.get("tile_x", -1))
		var top := int(map_object.get("tile_y", -1))
		var width := int(map_object.get("tile_w", 1))
		var height := int(map_object.get("tile_h", 1))
		if tile.x >= left and tile.x < left + width and tile.y >= top and tile.y < top + height:
			return true
	return false


func _is_world_tile_solid(tile: Vector2i) -> bool:
	if _is_city_wall(tile):
		return true
	if _is_in_solid_rects(tile, _terrain.get("obstacles", [])):
		return true
	for map_object in _terrain.get("objects", []):
		if not map_object is Dictionary:
			continue
		var left := int(map_object.get("tile_x", -1))
		var top := int(map_object.get("tile_y", -1))
		var width := int(map_object.get("tile_w", 1))
		var height := int(map_object.get("tile_h", 1))
		if tile.x >= left and tile.x < left + width and tile.y >= top and tile.y < top + height:
			return true
		if _is_in_solid_rects(tile, map_object.get("solid_rects", [])):
			return true
	var published: Variant = _terrain.get("tiles", {})
	if published is Dictionary:
		if not is_same(published, _blocked_source):
			_blocked_source = published
			_blocked_tiles = _published_blocked_tiles(published)
		return _blocked_tiles.has(tile)
	return false


# Плитки опубликованной карты, которые блокируют ходьбу; набор строится один раз на каждый набор тайлов.
func _published_blocked_tiles(published: Dictionary) -> Dictionary:
	var blocked := {}
	for terrain_name in ["impassable", "water", "mountain"]:
		for blocked_tile in published.get(terrain_name, []):
			if blocked_tile is Array and blocked_tile.size() >= 2:
				blocked[Vector2i(int(blocked_tile[0]), int(blocked_tile[1]))] = true
	return blocked


func _is_in_solid_rects(tile: Vector2i, rects: Variant) -> bool:
	if not rects is Array:
		return false
	var pixel_x := tile.x * _map_tile_size + _map_tile_size / 2.0
	var pixel_y := tile.y * _map_tile_size + _map_tile_size / 2.0
	for rect in rects:
		if rect is Array and rect.size() >= 4:
			if pixel_x >= float(rect[0]) and pixel_x < float(rect[0]) + float(rect[2]) \
					and pixel_y >= float(rect[1]) and pixel_y < float(rect[1]) + float(rect[3]):
				return true
	return false


func _refresh_social() -> void:
	if not _pending_action.is_empty():
		return
	if _view not in ["home", "tavern", "character_room", "backyard"]:
		return
	if _position_dirty:
		_checkpoint_pending = true
		_save_location_checkpoint()
		return
	var location := _social_location
	var path := "/api/deck/social/snapshot?location=%s&character_id=%d" % [
		location.uri_encode(),
		_character_id,
	]
	_request("social_snapshot", HTTPClient.METHOD_GET, path)


func _save_location_checkpoint() -> void:
	if not _pending_action.is_empty():
		_checkpoint_pending = true
		return
	# В бою сохраняем локацию, где он начался: служебное имя экрана «battle» на сервер не уходит.
	var location := _social_location if _view == "battle" else ("world_map" if _view == "home" else _view)
	GameSession.character["zone"] = location
	var body := {"zone": location}
	if location == "world_map":
		body["position_x"] = float(_map_position.x * _map_tile_size + _map_tile_size / 2)
		body["position_y"] = float(_map_position.y * _map_tile_size + _map_tile_size / 2)
		body["position_direction"] = _map_direction
	_pending_action = "checkpoint"
	_checkpoint_pending = false
	_position_dirty = false
	ApiClient.request_json(
		HTTPClient.METHOD_PUT,
		"/api/characters/%d" % _character_id,
		body,
	)


func _render_social() -> void:
	if _view == "backyard":
		_render_backyard()
		return
	if _view not in ["home", "tavern", "character_room", "backyard"]:
		return
	var occupants: Array = _social_data.get("occupants", [])
	_add_note("Игроки рядом: %d" % occupants.size())
	for occupant in occupants:
		if not occupant is Dictionary:
			continue
		var character_id := str(occupant.get("character_id", ""))
		var name := str(occupant.get("name", occupant.get("username", "Игрок")))
		var row := HBoxContainer.new()
		_list.add_child(row)
		var details := Label.new()
		details.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		details.text = "%s · ур. %s · HP %s/%s%s" % [
			name,
			str(occupant.get("level", "?")),
			str(occupant.get("hp", "?")),
			str(occupant.get("max_hp", "?")),
			" · не в сети" if bool(occupant.get("afk", false)) else "",
		]
		row.add_child(details)

	_add_note("Сообщения · %s" % _social_location)
	var messages: Array = _social_data.get("messages", [])
	var first_message := maxi(0, messages.size() - 8)
	for index in range(first_message, messages.size()):
		var message: Variant = messages[index]
		if message is Dictionary:
			_add_note("%s: %s" % [
				str(message.get("sender", message.get("name", "Игрок"))),
				str(message.get("text", "")),
			])
	if messages.is_empty():
		_add_note("Пока нет сообщений.")
	var chat_row := HBoxContainer.new()
	_list.add_child(chat_row)
	_chat_input = LineEdit.new()
	_chat_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_chat_input.placeholder_text = "Написать в канал этой локации"
	_chat_input.max_length = 500
	_chat_input.text = _chat_draft
	_chat_input.text_submitted.connect(_send_chat_message)
	chat_row.add_child(_chat_input)
	var send_button := Button.new()
	send_button.text = "Отправить"
	send_button.pressed.connect(_send_chat_button)
	chat_row.add_child(send_button)
	if _chat_had_focus:
		_chat_input.call_deferred("grab_focus")


# Задний двор: вид deck_backyard_view.gd рисует раскладку Python. Кнопки ведут к действиям, которые уже были в мире:
# заявка, отмена, сравнение, вступление в сбор, стенка на стенку, вызов, чат. Запросы не меняются.
func _build_backyard_view() -> void:
	_backyard_view = BACKYARD_VIEW_SCRIPT.new()
	add_child(_backyard_view)
	_backyard_list_home = _list.get_parent() as Control
	_backyard_list_separation = _list.get_theme_constant("separation")
	_backyard_view.tavern_requested.connect(_go_to_location.bind("tavern"))
	_backyard_view.profile_requested.connect(_open_backyard_profile)
	_backyard_view.duel_requested.connect(_on_backyard_duel_pressed)
	_backyard_view.accept_requested.connect(_on_backyard_accept_pressed)
	_backyard_view.duel_row_pressed.connect(_on_backyard_duel_row_pressed)
	_backyard_view.group_row_pressed.connect(_join_group_battle)
	_backyard_view.compare_requested.connect(_on_backyard_duel_row_pressed)
	_backyard_view.accept_offer_requested.connect(_respond_duel_offer.bind(true))
	_backyard_view.decline_offer_requested.connect(_respond_duel_offer.bind(false))
	_backyard_view.challenge_requested.connect(_challenge_character)
	_backyard_view.chat_send_requested.connect(_send_chat_message)
	_backyard_view.profile_stat_requested.connect(_on_comparison_stat_requested)
	_backyard_view.profile_level_requested.connect(_on_backyard_level_requested)


# Список мира переносится в вид только на заднем дворе: там его кнопка стенки стоит на месте кнопки Python.
func _sync_backyard_view() -> void:
	if _social_location == "backyard":
		_backyard_view.dock_list(_list)
	else:
		if _chat_input != null and _chat_input == _backyard_view.chat_input():
			_chat_input = null
		_backyard_view.undock_list(_list, _backyard_list_home, _backyard_list_separation)
	_backyard_view.set_active(_social_location == "backyard" and _view == "backyard")
	_backyard_view.set_message(_status.text)
	if _backyard_view.is_profile_open() and GameSession.character != _backyard_profile_snapshot:
		_backyard_profile_snapshot = GameSession.character.duplicate(true)
		_backyard_view.update_profile(_backyard_profile_snapshot)


func _render_backyard() -> void:
	_sync_backyard_view()
	_clear_list()
	var model := _backyard_model()
	_chat_input = _backyard_view.chat_input()
	_list.add_child(_backyard_view.build_layer(model))
	var own_group: Dictionary = model["own_group"]
	var group_button := _add_button(_list, BACKYARD_RULES.group_button_title(own_group), _on_backyard_group_pressed)
	_backyard_view.style_group_button(group_button, not own_group.is_empty())


func _backyard_model() -> Dictionary:
	var now := Time.get_unix_time_from_system()
	var own_id := str(_character_id)
	var my_application: Dictionary = BACKYARD_RULES.active_application(_social_data.get("my_application"), now)
	var group_offers := _group_offers()
	return {
		"now": now,
		"own_id": own_id,
		"my_application": my_application,
		"duel_offers": BACKYARD_RULES.duel_offers(_social_data.get("offers", []), my_application, own_id, str(GameSession.character.get("name", ""))),
		"selected_offer_id": _backyard_selected_offer,
		"group_offers": group_offers,
		"own_group": BACKYARD_RULES.own_group(group_offers, str(_character_id)),
		"occupants": _social_data.get("occupants", []),
		"messages": _social_data.get("messages", []),
	}


func _own_duel_application() -> Dictionary:
	return BACKYARD_RULES.active_application(_social_data.get("my_application"), Time.get_unix_time_from_system())


func _on_backyard_duel_pressed() -> void:
	if not BACKYARD_RULES.own_group(_group_offers(), str(_character_id)).is_empty():
		_status.text = BACKYARD_RULES.DUEL_GUARD
		return
	if _own_duel_application().is_empty():
		_create_duel_application()
	else:
		_cancel_duel_application()


func _on_backyard_group_pressed() -> void:
	var own_group: Dictionary = BACKYARD_RULES.own_group(_group_offers(), str(_character_id))
	if not own_group.is_empty():
		if not _pending_action.is_empty():
			_status.text = "Подождите завершения текущего запроса."
			return
		_leave_group_battle(str(own_group.get("id", "")))
		return
	if not _own_duel_application().is_empty():
		_status.text = BACKYARD_RULES.GROUP_GUARD
		return
	_open_group_battle_window()


func _on_backyard_accept_pressed() -> void:
	var model := _backyard_model()
	var incoming: Dictionary = BACKYARD_RULES.incoming_offer(_backyard_selected_offer, model["duel_offers"], model["my_application"], str(_character_id))
	if incoming.is_empty():
		_status.text = BACKYARD_RULES.NO_INCOMING_TEXT
		return
	_respond_duel_offer(str(incoming.get("id", "")), true)


# Клик по строке заявки открывает сравнение, как в Python; свою заявку вызвать нельзя.
func _on_backyard_duel_row_pressed(offer: Dictionary) -> void:
	_backyard_selected_offer = "" if BACKYARD_RULES.is_own_offer(offer, str(_character_id)) else str(offer.get("id", ""))
	_backyard_view.set_model(_backyard_model())
	_open_comparison(offer)


func _on_backyard_level_requested(_delta: int) -> void:
	_status.text = BACKYARD_RULES.LEVEL_LOCKED_TEXT


func _open_backyard_profile() -> void:
	if GameSession.character.is_empty():
		return
	_backyard_profile_snapshot = GameSession.character.duplicate(true)
	_backyard_view.open_profile(_backyard_profile_snapshot)


func _send_chat_button() -> void:
	if _chat_input != null:
		_send_chat_message(_chat_input.text)


func _send_chat_message(text: String) -> void:
	var cleaned := text.strip_edges()
	if cleaned.is_empty():
		return
	_request("send_chat", HTTPClient.METHOD_POST, "/api/chat/messages", {
		"character_id": _character_id,
		"location": _social_location,
		"text": cleaned,
	})


func _challenge_character(target_id: String) -> void:
	if target_id.is_empty():
		return
	_request("challenge", HTTPClient.METHOD_POST, "/api/deck/social/duel-offers", {
		"character_id": _character_id,
		"location": "backyard",
		"target_id": target_id,
	})


func _respond_duel_offer(offer_id: String, accepted: bool, action := "respond_duel") -> void:
	if offer_id.is_empty():
		return
	_request(action, HTTPClient.METHOD_POST, "/api/deck/social/duel-offers/respond", {
		"character_id": _character_id,
		"offer_id": offer_id,
		"accepted": accepted,
	})


func _open_comparison(offer: Dictionary) -> void:
	_comparison_offer = offer.duplicate(true)
	_comparison.open(GameSession.character, _comparison_opponent(offer))
	if not _pending_action.is_empty():
		_comparison.set_status("Снаряжение не загружено: дождитесь завершения запроса и откройте сравнение снова.", true)
		return
	_comparison.set_status("Загружаем снаряжение…", false)
	_request("comparison_inventory", HTTPClient.METHOD_GET, "/api/inventory/%d" % _character_id)


# Соперник — персонаж из списка игроков рядом с той же id, что у отправителя заявки (как chat.occupants в Python).
func _comparison_opponent(offer: Dictionary) -> Dictionary:
	var sender_id := str(offer.get("sender_id", ""))
	for occupant in _social_data.get("occupants", []):
		if occupant is Dictionary and str(occupant.get("character_id", "")) == sender_id:
			return occupant
	return {"name": str(offer.get("sender", offer.get("sender_name", "Игрок"))), "level": 1, "stats": {}}


func _on_comparison_stat_requested(stat_name: String, delta: int) -> void:
	if not _pending_action.is_empty():
		_comparison.set_status("Подождите завершения текущего запроса.", true)
		return
	var profile := CHARACTER_RULES.comparison_adjust(GameSession.character, stat_name, delta)
	if profile.is_empty():
		_comparison.set_status("Эту характеристику сейчас нельзя изменить.", true)
		return
	_comparison.set_status("Сохраняем характеристики…", false)
	_request("comparison_save", HTTPClient.METHOD_PUT, "/api/characters/%d" % _character_id, {
		"stats": profile["stats"],
		"stat_points": profile["stat_points"],
		"hp": profile["hp"],
		"max_hp": profile["max_hp"],
		"mp": profile["mp"],
		"max_mp": profile["max_mp"],
	})


func _on_comparison_challenge() -> void:
	var own_application: Variant = _social_data.get("my_application")
	if own_application is Dictionary and not own_application.is_empty():
		_comparison.set_status("Пока активна ваша заявка, бросить вызов нельзя", true)
		return
	var offer_id := str(_comparison_offer.get("id", ""))
	if offer_id.is_empty():
		_comparison.set_status("Заявка соперника не найдена.", true)
		return
	if not _pending_action.is_empty():
		_comparison.set_status("Подождите завершения текущего запроса.", true)
		return
	_comparison.set_status("Принимаем заявку соперника…", false)
	_respond_duel_offer(offer_id, true, "comparison_challenge")


func _claim_guild_quest(quest_id: String) -> void:
	if not _pending_action.is_empty():
		_guild_window.show_message("Подождите завершения текущего запроса.", true)
		return
	_pending_guild_quest = quest_id
	_guild_window.show_message("Сдаём задание…")
	_request("guild_claim", HTTPClient.METHOD_POST, "/api/deck/guild/quest-reward", {
		"character_id": _character_id,
		"quest_id": quest_id,
		"request_id": _new_request_id(),
	})


func _finish_guild_claim(payload: Variant) -> void:
	var quest_id := _pending_guild_quest
	_pending_guild_quest = ""
	if not payload is Dictionary:
		_guild_window.show_message("Не удалось сдать задание: неверный ответ сервера", true)
		return
	var character: Variant = payload.get("character")
	if character is Dictionary:
		GameSession.character.merge(character, true)
	_quest_log.claim(quest_id)
	_guild_window.refresh()
	if bool(payload.get("already_claimed", false)):
		_guild_window.show_message("Это задание уже было сдано")
	else:
		_guild_window.show_message("Получено: %s" % DECK_CURRENCY.format_coins(int(payload.get("reward_coins", 0))))


func _new_request_id() -> String:
	return Crypto.new().generate_random_bytes(16).hex_encode()


func _close_comparison() -> void:
	_comparison.close()


# Ошибки запросов окон показываются в самом окне, остальные — в строке статуса экрана.
func _report_status(action: String, text: String, is_error := false) -> void:
	if action.begins_with("comparison_") and _comparison.visible:
		_comparison.set_status(text, is_error)
	elif action.begins_with("guild_") and _guild_window.is_open():
		_guild_window.show_message(text, is_error)
	elif action.begins_with("supplies_") and _supplies_shop_window.is_open():
		_supplies_shop_window.show_message(text, is_error)
	elif action.begins_with("library_") and _library_window.is_open():
		_library_window.show_items_message(text)
	elif action.begins_with("talent_") and _talent_window.is_open():
		_talent_window.show_message(text, is_error)
	elif action.begins_with("tavern_") and _tavern_shop_window.is_open():
		_tavern_shop_window.show_message(text, is_error)
	elif action in ["create_group", "join_group", "leave_group"] and _group_battle_window.is_open():
		_group_battle_window.set_busy(false)
		_group_battle_window.show_message(text, is_error)
	elif action.begins_with("battle_") and _battle_screen.visible:
		_battle_notice.text = text
		_battle_notice.visible = true
	else:
		_status.text = text


func _create_duel_application() -> void:
	_request("create_application", HTTPClient.METHOD_POST, "/api/deck/social/duel-applications", {
		"character_id": _character_id,
		"location": "backyard",
		"ttl": 300,
	})


func _cancel_duel_application() -> void:
	_request("cancel_application", HTTPClient.METHOD_POST, "/api/deck/social/duel-applications/cancel", {
		"character_id": _character_id,
		"location": "backyard",
	})


func _create_group_battle(participants_value: int, ttl: int) -> void:
	var problem: String = GROUP_RULES.validate_choice(participants_value, ttl)
	if not problem.is_empty():
		_group_battle_window.show_message(problem, true)
		return
	_group_request("create_group", HTTPClient.METHOD_POST, "/api/deck/social/group-battles", {
		"character_id": _character_id,
		"location": "backyard",
		"ttl": ttl,
		"max_participants": participants_value,
	})


# Запрос из окна сбора: пока он идёт, кнопки окна заблокированы.
func _group_request(action: String, method: HTTPClient.Method, path: String, body: Dictionary = {}) -> void:
	if not _pending_action.is_empty():
		_group_battle_window.show_message("Подождите завершения текущего запроса.", true)
		return
	_group_battle_window.set_busy(true)
	_request(action, method, path, body)


func _join_group_battle(offer_id: String) -> void:
	if offer_id.is_empty():
		return
	_group_request("join_group", HTTPClient.METHOD_POST, "/api/deck/social/group-battles/%s/join" % offer_id.uri_encode(), {
		"character_id": _character_id,
		"location": "backyard",
	})


func _start_group_battle(offer_id: String) -> void:
	if offer_id.is_empty():
		return
	_group_started_offer_id = offer_id
	_group_battle_window.close()
	_social_timer.stop()
	_request("battle_start", HTTPClient.METHOD_POST, "/api/deck/battle/start", {
		"character_id": _character_id,
		"group_id": offer_id,
	})


func _leave_group_battle(offer_id: String) -> void:
	if offer_id.is_empty():
		return
	_group_request("leave_group", HTTPClient.METHOD_POST, "/api/deck/social/group-battles/%s/leave" % offer_id.uri_encode(), {
		"character_id": _character_id,
	})


func _group_offers() -> Array:
	var offers: Variant = _social_data.get("group_offers", [])
	return offers if offers is Array else []


func _open_group_battle_window() -> void:
	if _battle_is_active():
		_status.text = "Сначала завершите текущий бой."
		return
	_group_battle_window.open(_character_id)
	_group_battle_window.set_state(_group_offers(), _character_id)
	_refresh_social()


func _refresh_group_battle_window() -> void:
	if _group_battle_window.is_open():
		_group_battle_window.set_state(_group_offers(), _character_id)


# Своя заявка собрана в команды: бой этого сбора запускается один раз; повторно — кнопкой в окне.
func _maybe_start_ready_group_battle() -> bool:
	if _view != "backyard" or not _pending_action.is_empty() or _battle_is_active():
		return false
	var own: Dictionary = GROUP_RULES.own_offer(_group_offers(), _character_id)
	if not GROUP_RULES.start_available(own, _character_id):
		return false
	var offer_id := str(own.get("id", ""))
	if offer_id == _group_started_offer_id:
		return false
	_start_group_battle(offer_id)
	return true


func _load_collection() -> void:
	if _battle_is_active():
		_status.text = "Сначала завершите текущий бой."
		return
	_view = "collection"
	_request("collection", HTTPClient.METHOD_GET, "/api/deck/card-collection/%d" % _character_id)


func _load_decks() -> void:
	if _battle_is_active():
		_status.text = "Сначала завершите текущий бой."
		return
	_view = "decks"
	_request("decks", HTTPClient.METHOD_GET, "/api/deck/decks/%d" % _character_id)


func _load_shop() -> void:
	if _battle_is_active():
		_status.text = "Сначала завершите текущий бой."
		return
	_view = "shop"
	_request("shop", HTTPClient.METHOD_GET, "/api/deck/card-shop")


func _render_collection() -> void:
	_clear_list()
	if _collection.is_empty():
		_add_note("Коллекция пока пуста.")
		return
	for card in _collection:
		var note := _add_note("%s · %s · %s ×%d · редкость %s · стоимость %s" % [
			str(card.get("name", card.get("key", "Карта"))),
			str(card.get("group_name", "")),
			str(card.get("key", "")),
			int(card.get("quantity", 0)),
			CARD_RULES.rarity_label(str(card.get("rarity", ""))),
			str(card.get("price_coins", 0)),
		])
		_bind_card_hover(note, card)


func _render_decks() -> void:
	_clear_list()
	if _decks.is_empty():
		_add_note("Сохранённых колод пока нет.")
	else:
		for deck in _decks:
			var row := HBoxContainer.new()
			_list.add_child(row)
			var details := Label.new()
			details.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			details.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			details.text = "%s%s · %d карт · %s" % [
				str(deck.get("name", "Колода")),
				" · активная" if bool(deck.get("is_active", false)) else "",
				_count_deck_cards(deck.get("cards", {})),
				JSON.stringify(deck.get("cards", {})),
			]
			row.add_child(details)
			if not bool(deck.get("is_active", false)):
				var activate_button := Button.new()
				activate_button.text = "Выбрать"
				activate_button.pressed.connect(_activate_deck.bind(int(deck.get("id", 0))))
				row.add_child(activate_button)
			var remove_button := Button.new()
			remove_button.text = "Удалить"
			remove_button.pressed.connect(_delete_deck.bind(int(deck.get("id", 0))))
			row.add_child(remove_button)
	_add_deck_builder()


func _add_deck_builder() -> void:
	_deck_counts.clear()
	_deck_name = LineEdit.new()
	_deck_name.placeholder_text = "Название новой колоды"
	_deck_name.max_length = 32
	_list.add_child(_deck_name)
	_card_select = ItemList.new()
	_card_select.select_mode = ItemList.SELECT_SINGLE
	_card_select.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_card_select.custom_minimum_size.y = 220
	for card in _collection:
		var key := str(card.get("key", ""))
		if key.is_empty():
			continue
		var index := _card_select.add_item("%s · %s (есть %d)" % [
			str(card.get("name", key)),
			key,
			int(card.get("quantity", 0)),
		])
		_card_select.set_item_metadata(index, key)
	_card_select.item_selected.connect(_on_deck_card_selected)
	_list.add_child(_card_select)
	_card_hover_targets.append({"control": _card_select, "list": true})
	_quantity_select = SpinBox.new()
	_quantity_select.min_value = 1
	_quantity_select.max_value = DECK_COPY_LIMIT
	_quantity_select.value = 1
	_list.add_child(_quantity_select)
	if _card_select.item_count > 0:
		_card_select.select(0)
		_on_deck_card_selected(0)
	_add_button(_list, "Добавить выбранные копии", _add_cards_to_deck)
	_add_button(_list, "Убрать одну выбранную копию", _remove_card_from_deck)
	_deck_summary = Label.new()
	_deck_summary.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_list.add_child(_deck_summary)
	_add_button(_list, "Сохранить колоду", _create_deck)
	_update_deck_summary()


func _add_cards_to_deck() -> void:
	var selected := _card_select.get_selected_items()
	if selected.is_empty():
		_status.text = "Коллекция не содержит доступных карт."
		return
	var card_key := str(_card_select.get_item_metadata(selected[0]))
	var card := _find_collection_card(card_key)
	var current := int(_deck_counts.get(card_key, 0))
	var quantity := int(_quantity_select.value)
	if current + quantity > mini(int(card.get("quantity", 0)), DECK_COPY_LIMIT):
		_status.text = "В колоду нельзя добавить больше копий, чем есть в коллекции или разрешено правилами."
		return
	_deck_counts[card_key] = current + quantity
	_update_deck_summary()


func _on_deck_card_selected(index: int) -> void:
	if index < 0 or index >= _card_select.item_count:
		return
	var card := _find_collection_card(str(_card_select.get_item_metadata(index)))
	_quantity_select.max_value = maxf(1.0, minf(float(card.get("quantity", 1)), DECK_COPY_LIMIT))
	_quantity_select.value = minf(_quantity_select.value, _quantity_select.max_value)


func _remove_card_from_deck() -> void:
	var selected := _card_select.get_selected_items()
	if selected.is_empty():
		return
	var card_key := str(_card_select.get_item_metadata(selected[0]))
	var current := int(_deck_counts.get(card_key, 0))
	if current <= 1:
		_deck_counts.erase(card_key)
	else:
		_deck_counts[card_key] = current - 1
	_update_deck_summary()


func _update_card_hover(mouse: Vector2) -> void:
	var card := _hovered_card(mouse)
	if card.is_empty():
		_card_tooltip.hide_card()
	else:
		_card_tooltip.show_card(card)


func _hovered_card(mouse: Vector2) -> Dictionary:
	var area: Control = _battle_screen if _battle_screen.visible else (_list.get_parent() as Control)
	if _exit_menu.blocks_input() or not area.get_global_rect().has_point(mouse):
		return {}
	for target in _card_hover_targets:
		var control: Control = target["control"]
		if not is_instance_valid(control) or not control.is_visible_in_tree() or not control.get_global_rect().has_point(mouse):
			continue
		if target.has("list"):
			var index: int = control.get_item_at_position(mouse - control.get_global_position(), true)
			if index < 0:
				return {}
			return _find_collection_card(str(control.get_item_metadata(index)))
		return target["card"]
	return {}


func _find_collection_card(card_key: String) -> Dictionary:
	for card in _collection:
		if str(card.get("key", "")) == card_key:
			return card
	return {}


func _update_deck_summary() -> void:
	var total := _count_deck_cards(_deck_counts)
	_deck_summary.text = "Состав: %d / %d карт\n%s" % [
		total,
		DECK_SIZE,
		JSON.stringify(_deck_counts),
	]


func _count_deck_cards(cards: Variant) -> int:
	var total := 0
	if cards is Dictionary:
		for quantity in cards.values():
			total += int(quantity)
	elif cards is Array:
		total = cards.size()
	return total


func _create_deck() -> void:
	var name := _deck_name.text.strip_edges()
	if name.is_empty():
		_status.text = "Введите название колоды."
		return
	if _count_deck_cards(_deck_counts) != DECK_SIZE:
		_status.text = "В колоде должно быть ровно %d карт." % DECK_SIZE
		return
	_request("create_deck", HTTPClient.METHOD_POST, "/api/deck/decks", {
		"character_id": _character_id,
		"name": name,
		"cards": _deck_counts.duplicate(true),
	})


func _delete_deck(deck_id: int) -> void:
	if deck_id <= 0:
		return
	_request("delete_deck", HTTPClient.METHOD_DELETE, "/api/deck/decks/%d" % deck_id,
		{"character_id": _character_id})


func _activate_deck(deck_id: int) -> void:
	if deck_id <= 0:
		return
	_request("activate_deck", HTTPClient.METHOD_POST,
		"/api/deck/decks/%d/activate" % deck_id,
		{"character_id": _character_id})


func _render_shop() -> void:
	_clear_list()
	if _shop.is_empty():
		_add_note("Сервер не вернул карточный ассортимент.")
		return
	for card in _shop:
		if not card is Dictionary:
			continue
		var row := HBoxContainer.new()
		_list.add_child(row)
		var details := Label.new()
		details.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		details.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		details.text = "%s · %s · %s монет" % [
			str(card.get("name", card.get("key", "Карта"))),
			str(card.get("group_name", "")),
			str(card.get("price_coins", 0)),
		]
		row.add_child(details)
		_bind_card_hover(details, card)
		var buy_button := Button.new()
		buy_button.text = "Купить"
		buy_button.pressed.connect(_buy_card.bind(str(card.get("key", ""))))
		row.add_child(buy_button)


func _render_inventory() -> void:
	_clear_list()
	_add_note("Предметы персонажа · рюкзак, сундуки и переносы между ними.")
	var controls := HBoxContainer.new()
	_list.add_child(controls)
	_inventory_view_select = OptionButton.new()
	_inventory_view_select.add_item("Рюкзак")
	_inventory_view_select.add_item("Сундук 1")
	_inventory_view_select.add_item("Сундук 2")
	_inventory_view_select.selected = ["backpack", "chest1", "chest2"].find(_inventory_view)
	_inventory_view_select.item_selected.connect(_on_inventory_view_selected)
	controls.add_child(_inventory_view_select)
	_storage_destination_select = OptionButton.new()
	_storage_destination_select.add_item("Переносить в сундук 1")
	_storage_destination_select.add_item("Переносить в сундук 2")
	_storage_destination_select.visible = _inventory_view == "backpack"
	controls.add_child(_storage_destination_select)
	_inventory_quantity_input = LineEdit.new()
	_inventory_quantity_input.placeholder_text = "Количество (пусто — вся стопка)"
	_inventory_quantity_input.custom_minimum_size.x = 220
	controls.add_child(_inventory_quantity_input)
	_add_button(_list, "Назад в игру", _enter_location.bind(_social_location))

	if _inventory_view == "backpack":
		var inventory: Variant = _inventory_state.get("inventory", [])
		var equipment: Variant = _inventory_state.get("equipment", {})
		var capacity := int(_inventory_state.get("capacity", 50))
		_add_note("Рюкзак · вес %.1f кг · ячеек %d / %d" % [
			float(_inventory_state.get("carried_weight_kg", 0.0)),
			inventory.size() if inventory is Array else 0,
			capacity,
		])
		if not inventory is Array or inventory.is_empty():
			_add_note("Рюкзак пуст.")
		_ensure_inventory_block()
		_inventory_grid.set_items(
			inventory if inventory is Array else [],
			equipment if equipment is Dictionary else {},
			capacity,
		)
		_attach_inventory_block()
		_refresh_inventory_actions()
		return

	_add_note("%s · %d / %d ячеек" % [
		"Сундук 1" if _inventory_view == "chest1" else "Сундук 2",
		_storage_items.size(),
		80 if _inventory_view == "chest1" else 100,
	])
	if _storage_items.is_empty():
		_add_note("Сундук пуст.")
		return
	for storage_item_variant in _storage_items:
		if not storage_item_variant is Dictionary:
			continue
		var storage_item: Dictionary = storage_item_variant
		var storage_row := HBoxContainer.new()
		_list.add_child(storage_row)
		storage_row.add_child(_item_icon(storage_item))
		var storage_label := Label.new()
		storage_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		storage_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		storage_label.text = "%s ×%d · ячейка %d" % [
			str(storage_item.get("name", "Предмет")),
			int(storage_item.get("quantity", 1)),
			int(storage_item.get("slot_index", 0)) + 1,
		]
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


# Блок рюкзака создаётся один раз: сетка хранит выбор и ожидание ответа между перерисовками списка.
func _ensure_inventory_block() -> void:
	if _inventory_block != null:
		return
	_inventory_block = VBoxContainer.new()
	_inventory_block.add_theme_constant_override("separation", 6)
	_inventory_grid = INVENTORY_GRID_SCRIPT.new()
	_inventory_block.add_child(INVENTORY_GRID_SCRIPT.scaled_host(_inventory_grid, INVENTORY_GRID_SCALE))
	_inventory_grid.move_requested.connect(_on_inventory_move_requested)
	_inventory_grid.equip_requested.connect(_on_inventory_equip_requested)
	_inventory_grid.unequip_requested.connect(_on_inventory_unequip_requested)
	_inventory_grid.use_requested.connect(_on_inventory_use_requested)
	_inventory_grid.drop_requested.connect(_on_inventory_drop_requested)
	_inventory_grid.selection_changed.connect(_on_inventory_selection_changed)
	_inventory_grid.drop_confirm_changed.connect(_on_inventory_drop_confirm_changed)
	_inventory_grid.message_colored.connect(_on_inventory_grid_message)
	var actions := HBoxContainer.new()
	_inventory_block.add_child(actions)
	_inventory_action_button = _add_button(actions, "", _on_inventory_action_pressed)
	_inventory_drop_button = _add_button(actions, "Выбросить", _on_inventory_drop_pressed)
	_inventory_deposit_button = _add_button(actions, "В сундук", _on_inventory_deposit_pressed)
	_inventory_message_label = Label.new()
	_inventory_message_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_inventory_block.add_child(_inventory_message_label)
	_park_inventory_block()


# Список очищается при каждой перерисовке, поэтому блок уходит к корню экрана и возвращается обратно.
func _park_inventory_block() -> void:
	_inventory_block.visible = false
	add_child(_inventory_block)


func _attach_inventory_block() -> void:
	remove_child(_inventory_block)
	_list.add_child(_inventory_block)
	_inventory_block.visible = true


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
	_request_storage_transfer("deposit", int(item.get("slot_index", -1)), 0, int(item.get("quantity", 1)))


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
	_inventory_message(text, false, color)


func _on_inventory_selection_changed(_target: Array) -> void:
	_refresh_inventory_actions()


func _on_inventory_drop_confirm_changed(_active: bool) -> void:
	_refresh_inventory_actions()


# Действия рюкзака идут тем же общим каналом запросов, что и остальные окна; ответ закрывает их через resolve_action.
func _request_inventory_action(path: String, body: Dictionary) -> void:
	if not _pending_action.is_empty():
		_inventory_message("Подождите завершения текущего запроса.", true)
		_inventory_grid.resolve_action(false)
		return
	body["character_id"] = _character_id
	_request("inventory_action", HTTPClient.METHOD_POST, path, body)


func _inventory_message(text: String, is_error := false, color := MUTED_COLOR) -> void:
	_inventory_message_label.text = text
	_inventory_message_label.add_theme_color_override("font_color", INVENTORY_RULES.BAD_COLOR if is_error else color)


func _item_icon(item: Dictionary) -> TextureRect:
	var icon := ITEM_ICON_RULES.new_icon_rect(LIST_ICON_SIZE)
	var assets_root := ITEM_ICON_RULES.default_assets_root(ProjectSettings.globalize_path("res://"))
	ITEM_ICON_RULES.apply_icon(icon, assets_root, ITEM_ICON_RULES.item_key(item), LIST_ICON_SIZE)
	return icon


func _on_inventory_view_selected(index: int) -> void:
	var views := ["backpack", "chest1", "chest2"]
	if index < 0 or index >= views.size():
		return
	_inventory_view = views[index]
	if _inventory_view == "backpack":
		_render_inventory()
	else:
		_request("storage_load", HTTPClient.METHOD_GET,
			"/api/storage/%d/%s" % [_character_id, _inventory_view])


func _request_storage_transfer(direction: String, slot_index: int, storage_item_id: int, stack_quantity: int) -> void:
	var quantity := stack_quantity
	if _inventory_quantity_input != null and not _inventory_quantity_input.text.strip_edges().is_empty():
		if not _inventory_quantity_input.text.is_valid_int():
			_status.text = "Введите целое количество предметов."
			return
		quantity = int(_inventory_quantity_input.text)
	if quantity <= 0 or quantity > stack_quantity:
		_status.text = "Количество должно быть от 1 до размера стопки."
		return
	var storage_type := _inventory_view
	if direction == "deposit":
		storage_type = "chest1" if _storage_destination_select.selected == 0 else "chest2"
	elif storage_type == "backpack":
		_status.text = "Сначала выберите сундук для получения предметов."
		return
	var payload := {
		"character_id": _character_id,
		"storage_type": storage_type,
		"direction": direction,
		"quantity": quantity,
	}
	if direction == "deposit":
		payload["slot_index"] = slot_index
	else:
		payload["storage_item_id"] = storage_item_id
	_request("storage_transfer", HTTPClient.METHOD_POST, "/api/storage/transfer", payload)


func _buy_card(card_key: String) -> void:
	if card_key.is_empty():
		return
	_request("buy_card", HTTPClient.METHOD_POST, "/api/deck/card-shop/buy", {
		"character_id": _character_id,
		"card_key": card_key,
	})


func _on_api_completed(success: bool, payload: Variant) -> void:
	var action := _pending_action
	_pending_action = ""
	if _checkpoint_pending:
		_save_location_checkpoint()
		if action == "checkpoint":
			return
	if not success:
		if not _exit_intent.is_empty() and action in ["checkpoint", "return"]:
			_return_after_checkpoint = false
			if action == "checkpoint":
				_position_dirty = true
			_fail_exit(str(payload))
			return
		var failure_text := str(payload)
		if FAILURE_PREFIXES.has(action):
			failure_text = str(FAILURE_PREFIXES[action]) + failure_text
		if action.begins_with(ROOM_RULES.ACTION_PREFIX):
			_room_view.set_section_state(ROOM_RULES.section_from_action(action), ROOM_RULES.STATE_FAILED)
		if action == "inventory_action":
			_inventory_message(failure_text, true)
			_inventory_grid.resolve_action(false)
			return
		if action == "profile_equipment":
			GameSession.character["equipment"] = {}
			return
		if action == "guild_claim":
			_pending_guild_quest = ""
		elif action == "supplies_buy":
			_pending_supply_name = ""
		elif action == "talent_choose":
			_pending_talent_name = ""
		if action.begins_with("arena_"):
			_handle_arena_failure(action, failure_text)
			return
		if action.begins_with("dungeon_"):
			_handle_dungeon_failure(action, failure_text)
			return
		_report_status(action, failure_text, true)
		if action == "checkpoint":
			_position_dirty = true
		return
	if action.begins_with("arena_"):
		_handle_arena_payload(action, payload)
		return
	if action.begins_with("dungeon_"):
		_handle_dungeon_payload(action, payload)
		return
	if action.begins_with(ROOM_RULES.ACTION_PREFIX):
		_apply_room_payload(action, payload)
		return
	match action:
		"info":
			if not payload is Dictionary or str(payload.get("game", "")) != "deck":
				_status.text = "Адрес мира не подтверждён сервером Deck."
				return
			_status.text = "Загружаем рельеф мира Deck…"
			_request("terrain", HTTPClient.METHOD_GET, "/api/deck/map/terrain")
		"terrain":
			if not payload is Dictionary or not payload.get("terrain", {}) is Dictionary:
				_status.text = "Сервер не вернул данные карты Deck."
				return
			_terrain = payload["terrain"]
			_map_tile_size = maxi(1, int(_terrain.get("tile_size", 48)))
			_map_width = maxi(1, int(_terrain.get("width_tiles", 128)))
			_map_height = maxi(1, int(_terrain.get("height_tiles", 256)))
			_set_initial_map_position()
			var saved_zone := str(GameSession.character.get("zone", "world_map"))
			if saved_zone not in ["tavern", "character_room", "backyard"]:
				saved_zone = "world_map"
			_enter_location(saved_zone)
			_social_timer.start()
			_status.text = "Подключен Deck · карта загружена."
		"checkpoint":
			if payload is Dictionary and payload.get("character", {}) is Dictionary:
				GameSession.select_character(payload["character"])
			if _return_after_checkpoint:
				_return_after_checkpoint = false
				_request("return", HTTPClient.METHOD_POST, "/api/sessions/disconnect")
			else:
				_refresh_social()
		"social_snapshot":
			_social_data = payload if payload is Dictionary else {}
			_refresh_group_battle_window()
			var group_battle_started := _maybe_start_ready_group_battle()
			if not group_battle_started and _view in ["home", "tavern", "character_room", "backyard"]:
				_render_location()
			if not group_battle_started and _view == "backyard":
				_request("battle_active", HTTPClient.METHOD_GET,
					"/api/deck/battle/active?character_id=%d" % _character_id)
		"send_chat":
			if _chat_input != null:
				_chat_input.clear()
			_status.text = "Сообщение отправлено."
			_refresh_social()
		"challenge":
			var accepted := payload is Dictionary and bool(payload.get("accepted", false))
			var challenge_offer: Dictionary = payload.get("offer", {}) if payload is Dictionary else {}
			if accepted:
				_status.text = "Вызов принят. Запускаем бой…"
				_start_duel(str(challenge_offer.get("id", "")))
			else:
				_status.text = "Вызов отправлен; ожидаем ответа соперника."
				_refresh_social()
		"comparison_inventory":
			if payload is Dictionary:
				_store_equipment(payload)
				_comparison.update_player(GameSession.character)
				_comparison.set_status("", false)
			else:
				_comparison.set_status("Не удалось загрузить снаряжение.", true)
		"profile_equipment":
			if payload is Dictionary:
				_store_equipment(payload)
			else:
				GameSession.character["equipment"] = {}
		"comparison_save":
			if payload is Dictionary and payload.get("character") is Dictionary:
				var saved: Dictionary = payload["character"].duplicate(true)
				for key in ["equipment", "equipment_bonuses", "carried_weight_kg"]:
					if not saved.has(key) and GameSession.character.has(key):
						saved[key] = GameSession.character[key]
				GameSession.select_character(saved)
				_comparison.update_player(GameSession.character)
				_comparison.set_status("Характеристики сохранены.", false)
		"respond_duel", "comparison_challenge":
			var response_offer: Dictionary = payload.get("offer", {}) if payload is Dictionary else {}
			if str(response_offer.get("status", "")) == "accepted":
				_close_comparison()
				_status.text = "Вызов принят. Запускаем бой…"
				_start_duel(str(response_offer.get("id", "")))
			else:
				_report_status(action, "Ответ на заявку отправлен.")
				_refresh_social()
		"guild_claim":
			_finish_guild_claim(payload)
		"supplies_catalog":
			if payload is Dictionary and payload.get("items") is Array:
				_supplies_shop_window.set_items(payload["items"])
			else:
				_supplies_shop_window.show_message("Не удалось загрузить ассортимент: неверный ответ сервера", true)
		"supplies_buy":
			_finish_supply_purchase(payload)
		"library_items":
			if payload is Dictionary and payload.get("items") is Array:
				_library_window.set_items(payload["items"])
			else:
				_library_window.show_items_message("Каталог предметов недоступен: неверный ответ сервера")
		"talent_character":
			if payload is Dictionary and payload.get("character") is Dictionary:
				_merge_talent_state(payload["character"])
				_talent_window.show_message("")
			else:
				_talent_window.show_message("Не удалось обновить данные персонажа: неверный ответ сервера", true)
		"talent_choose":
			_finish_talent_choice(payload)
		"tavern_drinks":
			if payload is Dictionary and payload.get("drinks") is Array:
				_tavern_shop_window.set_drinks(payload["drinks"])
			else:
				_tavern_shop_window.show_message("Напитки не загружены: неверный ответ сервера", true)
		"create_application":
			_status.text = "Заявка на поединок опубликована."
			_refresh_social()
		"cancel_application":
			_status.text = "Заявка на поединок отменена."
			_refresh_social()
		"create_group":
			_group_battle_window.set_busy(false)
			_status.text = "Групповая заявка создана."
			_group_battle_window.show_message("Сбор создан: ждём участников.", false)
			_refresh_social()
		"join_group":
			_group_battle_window.set_busy(false)
			var group_offer: Dictionary = payload.get("offer", {}) if payload is Dictionary else {}
			if str(group_offer.get("status", "")) == "ready":
				_status.text = "Команды сформированы. Запускаем командный матч…"
				_start_group_battle(str(group_offer.get("id", "")))
			else:
				_status.text = "Вы присоединились к групповой заявке."
				_group_battle_window.show_message("Вы присоединились к сбору.", false)
				_refresh_social()
		"leave_group":
			var left_offer: Dictionary = payload.get("offer", {}) if payload is Dictionary else {}
			_status.text = "Групповая заявка отменена." if str(left_offer.get("status", "")) == "cancelled" else "Вы вышли из групповой заявки."
			_group_battle_window.set_busy(false)
			_group_battle_window.show_message(_status.text, false)
			_refresh_social()
		"battle_start", "battle_action":
			if not payload is Dictionary or not payload.get("battle", {}) is Dictionary:
				_report_status(action, "Сервер не вернул состояние боя.", true)
				return
			if action == "battle_start" and _view != "battle":
				_start_battle_transition(payload["battle"], action)
				return
			_open_battle(payload["battle"], action)
		"battle_active":
			if not payload is Dictionary or not payload.get("battle", {}) is Dictionary:
				return
			_view = "battle"
			_social_timer.stop()
			_receive_battle(payload["battle"], "", action)
		"battle_finish":
			if not payload is Dictionary or not payload.get("character", {}) is Dictionary:
				_report_status(action, "Сервер не вернул сохранённый результат боя.", true)
				return
			GameSession.select_character(payload["character"])
			_battle_result_data = payload
			_battle_state["phase"] = "result"
			_battle_timer.stop()
			_audio.sync_battle_music(_battle_state)
			_render_battle()
		"inventory_action":
			if not payload is Dictionary or not payload.get("inventory", []) is Array or not payload.get("equipment", {}) is Dictionary:
				_inventory_message("Сервер вернул некорректное состояние рюкзака.", true)
				_inventory_grid.resolve_action(false)
				return
			_inventory_state = payload.duplicate(true)
			if _view == "inventory":
				_render_inventory()
			_inventory_grid.resolve_action(true)
		"inventory_load", "storage_transfer":
			if not payload is Dictionary or not payload.get("inventory", []) is Array:
				_status.text = "Сервер вернул некорректное состояние рюкзака."
				return
			_inventory_state = payload.duplicate(true)
			if action == "storage_transfer":
				if not payload.get("storage", []) is Array:
					_status.text = "Сервер не вернул обновлённое содержимое сундука."
					return
				_storage_items = payload["storage"]
				_status.text = "Предметы перемещены."
			_render_inventory()
		"storage_load":
			if not payload is Dictionary or not payload.get("storage", []) is Array:
				_status.text = "Сервер вернул некорректное содержимое сундука."
				return
			_storage_items = payload["storage"]
			_render_inventory()
		"collection":
			_collection.clear()
			if payload is Dictionary and payload.get("collection", []) is Array:
				for card in payload["collection"]:
					if card is Dictionary:
						_collection.append(card)
			_render_collection()
		"decks":
			_decks.clear()
			if payload is Dictionary and payload.get("decks", []) is Array:
				for deck in payload["decks"]:
					if deck is Dictionary:
						_decks.append(deck)
			_collection.clear()
			_status.text = "Загружаем коллекцию для конструктора колод…"
			_request("deck_collection", HTTPClient.METHOD_GET, "/api/deck/card-collection/%d" % _character_id)
		"deck_collection":
			_collection.clear()
			if payload is Dictionary and payload.get("collection", []) is Array:
				for card in payload["collection"]:
					if card is Dictionary:
						_collection.append(card)
			_render_decks()
		"shop":
			_shop.clear()
			if payload is Dictionary and payload.get("cards", []) is Array:
				for card in payload["cards"]:
					if card is Dictionary:
						_shop.append(card)
			_render_shop()
		"buy_card":
			_status.text = "Покупка выполнена."
			_load_shop()
		"create_deck":
			_status.text = "Колода сохранена."
			_load_decks()
		"delete_deck":
			_status.text = "Колода удалена."
			_load_decks()
		"activate_deck":
			_status.text = "Активная колода изменена."
			_decks.clear()
			if payload is Dictionary and payload.get("decks", []) is Array:
				for deck in payload["decks"]:
					if deck is Dictionary:
						_decks.append(deck)
			_render_decks()
		"return":
			ConnectionGuard.stop()
			if _exit_intent == "quit":
				_exit_menu.mark_disconnected()
				return
			if _exit_intent == "restart":
				_restart_client()
				return
			GameSession.clear_character()
			ApiClient.set_server_url(GameSession.hub_url)
			ApiClient.token = GameSession.token
			SCENE_TRANSITION.run(get_tree(), func() -> void: get_tree().change_scene_to_file("res://scenes/main.tscn"))


func _return_to_characters() -> void:
	if _battle_is_active():
		_status.text = "Сначала завершите текущий бой."
		return
	_return_after_checkpoint = true
	_checkpoint_pending = true
	_save_location_checkpoint()


func _set_initial_map_position() -> void:
	_map_direction = str(GameSession.character.get("position_direction", "s"))
	if _map_direction not in ["n", "ne", "e", "se", "s", "sw", "w", "nw"]:
		_map_direction = "s"
	if str(GameSession.character.get("zone", "")) == "world_map":
		var saved_x: Variant = GameSession.character.get("position_x")
		var saved_y: Variant = GameSession.character.get("position_y")
		if saved_x != null and saved_y != null:
			_map_position = Vector2i(
				floori(float(saved_x) / _map_tile_size),
				floori(float(saved_y) / _map_tile_size),
			)
			return
	_map_position = Vector2i(_map_width >> 1, _map_height >> 1)
	for map_object in _terrain.get("objects", []):
		if not map_object is Dictionary:
			continue
		var approach: Variant = map_object.get("approach_pos")
		if approach is Array and approach.size() >= 2:
			_map_position = Vector2i(
				floori(float(approach[0]) / _map_tile_size),
				floori(float(approach[1]) / _map_tile_size),
			)
			return


func _on_connection_restored(character: Dictionary) -> void:
	GameSession.select_character(character)
	match _view:
		"battle":
			_refresh_battle()
		"inventory":
			_request("inventory_load", HTTPClient.METHOD_GET, "/api/inventory/%d" % _character_id)
		"collection":
			_load_collection()
		"decks":
			_load_decks()
		"shop":
			_load_shop()
		_:
			_enter_location(_social_location)
