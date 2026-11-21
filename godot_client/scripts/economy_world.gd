extends Control

const TITLE_COLOR := Color(0.94, 0.82, 0.56)
const MUTED_COLOR := Color(0.62, 0.68, 0.77)
const EXIT_MENU_SCRIPT := preload("res://scripts/exit_menu.gd")
const SERVER_STATUS_HUD_SCRIPT := preload("res://scripts/server_status_hud.gd")
const SCENE_TRANSITION := preload("res://scripts/scene_transition.gd")
const WORLD_AUDIO_SCRIPT := preload("res://scripts/world_audio.gd")
const CONTRIBUTION_DIALOG_SCRIPT := preload("res://scripts/material_contribution_dialog.gd")
const CURRENCY_SCRIPT := preload("res://scripts/currency_format.gd")
const LOCATION_CHAT_SCRIPT := preload("res://scripts/location_chat_panel.gd")
const CITY_MAP_SCRIPT := preload("res://scripts/economy_gate_city_map.gd")
const TRAVEL_MAP_SCRIPT := preload("res://scripts/economy_travel_map.gd")
const WORLD_MAP_SCENE := "res://scenes/world_entry.tscn"
const TRAVEL_REFRESH_SECONDS := 5.0
const CITY_MAP_HINT := "Колесо — масштаб, перетаскивание — перемещение. ПКМ по земле — пойти к точке, клик по зданию открывает его окно. «К герою» возвращает камеру к персонажу."
const TRAVEL_MAP_HINT := "Колесо — масштаб, перетаскивание — перемещение. Горожане и повозки обновляются примерно каждые 5 с."
const STATIC_BUILDING_VIEW_SCRIPT := preload("res://scripts/economy_static_building_view.gd")
const WORKSHOP_VIEW_SCRIPT := preload("res://scripts/economy_workshop_view.gd")
const WORKSHOP_ORDER_MESSAGE := "Заказ принят. Повозка появится в транспорте через 40 минут."
const CASTLE_VIEW_SCRIPT := preload("res://scripts/economy_castle_view.gd")
const TREASURY_DIALOG_SCRIPT := preload("res://scripts/treasury_transfer_dialog.gd")
const STORAGE_VIEW_SCRIPT := preload("res://scripts/economy_storage_view.gd")
const PRODUCTION_VIEW_SCRIPT := preload("res://scripts/economy_production_view.gd")
const PRODUCTION_RULES := preload("res://scripts/economy_production_rules.gd")
const PRODUCTION_UPGRADES := preload("res://scripts/economy_production_upgrades.gd")
const BUILDING_REFRESH_SECONDS := 5.0
const STABLE_VIEW_SCRIPT := preload("res://scripts/economy_stable_view.gd")
const FORGE_VIEW_SCRIPT := preload("res://scripts/economy_forge_view.gd")
const PROFILE_OVERLAY_SCRIPT := preload("res://scripts/character_profile_overlay.gd")
const PROFILE_RULES_SCRIPT := preload("res://scripts/character_profile_rules.gd")
const INVENTORY_VIEW_SCRIPT := preload("res://scripts/economy_inventory_view.gd")
const INVENTORY_ACTION_PATHS := {
	"move": "/api/inventory/move",
	"equip": "/api/equipment/equip",
	"unequip": "/api/equipment/unequip",
	"use": "/api/inventory/use",
	"drop": "/api/inventory/drop",
}
const CASTLE_ACTIONS := ["city", "citizen_assign", "citizen_recall", "treasury_deposit", "treasury_withdraw", "castle_upgrade"]
const CASTLE_SUCCESS_MESSAGES := {
	"citizen_assign": "Горожанин отправлен к месту работы.",
	"citizen_recall": "Горожанин возвращается в город.",
	"treasury_deposit": "Монеты внесены в казну.",
	"treasury_withdraw": "Монеты выданы из казны.",
	"castle_upgrade": "Улучшение замка начато.",
}
const STORAGE_BUILDINGS := ["barn", "warehouse"]
const WINDOW_SECTIONS := {
	"city": ["CastleView"],
	"building": ["EconomyStatus", "ProductionView"],
	"forge": ["ForgeView"],
	"tavern": ["EconomyStatus", "TavernControls"],
	"travelers": ["EconomyStatus", "TravelerControls"],
	"convoys": ["EconomyStatus", "ConvoyControls"],
	"static": ["StaticBuildingView"],
	"storage": ["StorageView"],
	"stable": ["StableView"],
	"workshop": ["WorkshopView"],
}
const CHAT_POLL_INTERVAL := 2.0
const TAVERN_BROKE_LINE := "ХАЛЯВЫ НЕТ! хочешь выпить — заплати!"
const TAVERN_FULL_HP_ERROR := "БАРМАН_ПОЛНОЕ_ЗДОРОВЬЕ"
const RESOURCE_LABELS := {
	"wheat": "Пшеница", "flax": "Лён", "cotton": "Хлопок", "wood": "Древесина", "berries": "Ягоды",
	"iron": "Железная руда", "stone": "Камень", "mithril": "Мифриловая руда", "obsidian": "Обсидиановая порода",
	"leather": "Кожа", "meat": "Мясо", "coal": "Уголь", "jet": "Гагат", "malachite": "Малахит", "topaz": "Топаз",
	"garnet": "Гранат", "emerald": "Изумруд", "ruby": "Рубин", "sapphire": "Сапфир", "diamond": "Алмаз",
	"board": "Доска", "iron_ingot": "Железо", "steel": "Сталь", "hard_leather": "Крепкая кожа",
	"thick_leather": "Толстая кожа", "cloth": "Ткань", "stone_block": "Каменный блок",
}
const BUILDINGS := {
	"farm": "Крестьянское поселение",
	"lumber_camp": "Лагерь лесорубов",
	"mountain_rift": "Горный разлом",
	"barnyard": "Скотный двор",
	"black_pit": "Чёрная яма",
	"barn": "Амбар",
	"warehouse": "Склад",
	"stable": "Конюшня",
}
const CART_GRADE_NAMES := {"1": "Лёгкая повозка", "2": "Крестьянский обоз"}
# Размеры окон в единицах Godot: Python px × 2/3 (база 1280×720 растягивается до 1920×1080).
const WINDOW_CONTENT_MARGIN := 40.0
const WINDOW_DIM_COLOR := Color8(8, 12, 18, 215)
const DEFAULT_WINDOW_SIZE := Vector2(940, 640)
const DEFAULT_WINDOW_BORDER := Color(0.85, 0.7, 0.35, 0.8)
const DEFAULT_WINDOW_BACKGROUND := Color(0.085, 0.095, 0.115, 0.98)

var _content: VBoxContainer
var _status: Label
var _details: Label
var _window_backdrop: ColorRect
var _window_title: Label
var _refresh_button: Button
var _window_style: StyleBoxFlat
var _building_window_title := ""
var _chat_panel
var _chat_timer: Timer
var _chat_enabled := false
var _chat_request_location := ""
var _chat_sent_recipient := 0
var _building_select: OptionButton
var _castle_view: VBoxContainer
var _contribution_dialog
var _treasury_dialog
var _pending_action := ""
var _exit_menu
var _exit_intent := ""
var _exit_queued := false
var _server_unreachable := false
var _server_status_hud
var _character_id := 0
var _view := "map"
var _selected_building := "farm"
var _static_building := ""
var _list_panel: PanelContainer
var _city_map_panel: PanelContainer
var _city_map
var _map_layer := "city"
var _map_title: Label
var _map_hint: Label
var _map_toggle: Button
var _travel_map
var _travel_timer: Timer
var _audio
var _city: Dictionary = {}
var _building: Dictionary = {}
var _storage_window: VBoxContainer
var _production_window: VBoxContainer
var _building_timer: Timer
var _pending_slot_index := -1
var _pending_hire_name := ""
var _forge_window: VBoxContainer
var _drinks: Array = []
var _tavern_tab := "drinks"
var _routes: Array = []
var _stable_window: VBoxContainer
var _workshop_view: VBoxContainer
var _profile_overlay
var _inventory_view
var _map_gate_pending := ""
var _hero_button: Button


func _ready() -> void:
	ApiClient.request_completed.connect(_on_api_completed)
	_character_id = int(GameSession.character.get("id", 0))
	ApiClient.token = GameSession.world_token
	_build_screen()
	_build_exit_menu()
	_build_server_status_hud()
	_build_building_timer()
	var entry_gate := GameSession.take_pending_city_gate()
	if not entry_gate.is_empty():
		_city_map.start_at_gate(entry_gate)
	get_tree().root.close_requested.connect(_on_close_requested)
	get_tree().set_auto_accept_quit(false)
	if _character_id <= 0:
		_status.text = "Не выбран персонаж. Вернитесь к списку персонажей."
		return
	var world_url := str(GameSession.world.get("server_url", "")).strip_edges()
	if world_url.is_empty() or not ApiClient.set_server_url(world_url):
		_status.text = "У мира Экономики не настроен корректный адрес сервера."
		return
	_chat_enabled = true
	_request_city_data()


func _exit_tree() -> void:
	if ApiClient.request_completed.is_connected(_on_api_completed):
		ApiClient.request_completed.disconnect(_on_api_completed)
	if get_tree().root.close_requested.is_connected(_on_close_requested):
		get_tree().root.close_requested.disconnect(_on_close_requested)
	if ConnectionGuard.status_received.is_connected(_server_status_hud.apply_status):
		ConnectionGuard.status_received.disconnect(_server_status_hud.apply_status)
	get_tree().set_auto_accept_quit(true)


func _process(_delta: float) -> void:
	_process_exit_queue()
	_start_map_transition_if_idle()
	_server_status_hud.set_blocked(_exit_menu.blocks_input())


func _unhandled_input(event: InputEvent) -> void:
	if _exit_menu.blocks_input():
		return
	var key := event as InputEventKey
	if key == null or not key.pressed or key.echo:
		return
	if key.keycode == KEY_ESCAPE:
		if _inventory_view.is_open():
			_close_inventory()
		elif _chat_panel.is_open():
			_chat_panel.close_panel()
		else:
			_exit_menu.open()
		get_viewport().set_input_as_handled()
		return
	if _chat_panel.is_open():
		return
	if key.keycode == KEY_I or key.keycode == KEY_C:
		_toggle_character_profile()
		get_viewport().set_input_as_handled()
		return
	if key.keycode == KEY_ENTER or key.keycode == KEY_KP_ENTER:
		_chat_panel.open_panel()
		get_viewport().set_input_as_handled()


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
	_request("return", HTTPClient.METHOD_POST, "/api/sessions/disconnect")


func _fail_exit(message: String) -> void:
	var intent := _exit_intent
	_exit_intent = ""
	_exit_queued = false
	if intent == "quit":
		_server_unreachable = true
		_exit_menu.open("Сервер недоступен: %s. Нажмите «Покинуть игру», чтобы закрыть клиент" % message)
	else:
		_exit_menu.open(message)


func _build_screen() -> void:
	var background := ColorRect.new()
	background.color = Color(0.055, 0.067, 0.09)
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(background)
	_build_city_map_panel(self)
	_window_backdrop = ColorRect.new()
	_window_backdrop.color = WINDOW_DIM_COLOR
	_window_backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_window_backdrop.visible = false
	add_child(_window_backdrop)
	var panel := PanelContainer.new()
	panel.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	panel.visible = false
	_window_style = StyleBoxFlat.new()
	_window_style.set_border_width_all(2)
	_window_style.set_corner_radius_all(8)
	_window_style.set_content_margin_all(12)
	panel.add_theme_stylebox_override("panel", _window_style)
	add_child(panel)
	_list_panel = panel
	var window_box := VBoxContainer.new()
	panel.add_child(window_box)
	var header := HBoxContainer.new()
	window_box.add_child(header)
	_window_title = Label.new()
	_window_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_window_title.add_theme_font_size_override("font_size", 22)
	_window_title.add_theme_color_override("font_color", TITLE_COLOR)
	header.add_child(_window_title)
	_refresh_button = Button.new()
	_refresh_button.text = "Обновить"
	_refresh_button.custom_minimum_size = Vector2(120, 36)
	_refresh_button.pressed.connect(_refresh_window)
	header.add_child(_refresh_button)
	var close_button := Button.new()
	close_button.text = "×"
	close_button.custom_minimum_size = Vector2(44, 36)
	close_button.pressed.connect(_close_window)
	header.add_child(close_button)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	window_box.add_child(scroll)
	_content = VBoxContainer.new()
	_content.add_theme_constant_override("separation", 10)
	_content.child_entered_tree.connect(_on_content_child_entered)
	scroll.add_child(_content)
	_apply_window_layout(DEFAULT_WINDOW_SIZE, DEFAULT_WINDOW_BORDER, DEFAULT_WINDOW_BACKGROUND)
	_status = Label.new()
	_status.name = "EconomyStatus"
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.add_theme_color_override("font_color", MUTED_COLOR)
	_content.add_child(_status)
	_details = Label.new()
	_details.name = "EconomyDetails"
	_details.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_details.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_content.add_child(_details)
	_castle_view = CASTLE_VIEW_SCRIPT.new()
	_castle_view.name = "CastleView"
	_castle_view.action_requested.connect(_on_castle_action)
	_content.add_child(_castle_view)
	_storage_window = STORAGE_VIEW_SCRIPT.new()
	_storage_window.name = "StorageView"
	_storage_window.action_requested.connect(_on_storage_view_action)
	_content.add_child(_storage_window)
	_production_window = PRODUCTION_VIEW_SCRIPT.new()
	_production_window.name = "ProductionView"
	_production_window.action_requested.connect(_on_production_view_action)
	_content.add_child(_production_window)
	_production_window.select_tab(PRODUCTION_RULES.TAB_PRODUCTION)
	_stable_window = STABLE_VIEW_SCRIPT.new()
	_stable_window.name = "StableView"
	_stable_window.action_requested.connect(_on_stable_view_action)
	_content.add_child(_stable_window)
	_forge_window = FORGE_VIEW_SCRIPT.new()
	_forge_window.name = "ForgeView"
	_forge_window.action_requested.connect(_on_forge_view_action)
	_content.add_child(_forge_window)
	_building_select = OptionButton.new()
	_building_select.name = "BuildingSelect"
	for key in BUILDINGS:
		_building_select.add_item(str(BUILDINGS[key]))
		_building_select.set_item_metadata(_building_select.item_count - 1, key)
	_content.add_child(_building_select)
	_building_select.item_selected.connect(_on_building_selected)
	_build_contribution_dialog()
	_build_treasury_dialog()
	_build_chat()
	_build_profile_overlay()
	_build_inventory_view()
	var notice := preload("res://scenes/connection_notice.tscn").instantiate()
	add_child(notice)
	notice.connection_restored.connect(_on_connection_restored)


func _apply_window_layout(window_size: Vector2, border: Color, background: Color) -> void:
	_list_panel.offset_left = -window_size.x / 2.0
	_list_panel.offset_right = window_size.x / 2.0
	_list_panel.offset_top = -window_size.y / 2.0
	_list_panel.offset_bottom = window_size.y / 2.0
	_window_style.border_color = border
	_window_style.bg_color = background
	_content.custom_minimum_size.x = window_size.x - WINDOW_CONTENT_MARGIN


func _apply_window_layout_for(view_name: String) -> void:
	match view_name:
		"city":
			_apply_window_layout(CASTLE_VIEW_SCRIPT.WINDOW_SIZE, CASTLE_VIEW_SCRIPT.BORDER_COLOR, CASTLE_VIEW_SCRIPT.BACKGROUND_COLOR)
		"workshop":
			_apply_window_layout(WORKSHOP_VIEW_SCRIPT.WINDOW_SIZE, WORKSHOP_VIEW_SCRIPT.BORDER_COLOR, WORKSHOP_VIEW_SCRIPT.BACKGROUND_COLOR)
		"storage":
			_apply_window_layout(STORAGE_VIEW_SCRIPT.WINDOW_SIZE, STORAGE_VIEW_SCRIPT.BORDER_COLOR, STORAGE_VIEW_SCRIPT.BACKGROUND_COLOR)
		"stable":
			_apply_window_layout(STABLE_VIEW_SCRIPT.WINDOW_SIZE, STABLE_VIEW_SCRIPT.BORDER_COLOR, STABLE_VIEW_SCRIPT.BACKGROUND_COLOR)
		"forge":
			_apply_window_layout(FORGE_VIEW_SCRIPT.WINDOW_SIZE, FORGE_VIEW_SCRIPT.BORDER_COLOR, FORGE_VIEW_SCRIPT.BACKGROUND_COLOR)
		"static":
			_apply_window_layout(STATIC_BUILDING_VIEW_SCRIPT.WINDOW_SIZE, STATIC_BUILDING_VIEW_SCRIPT.BORDER_COLOR, STATIC_BUILDING_VIEW_SCRIPT.BACKGROUND_COLOR)
		_:
			_apply_window_layout(DEFAULT_WINDOW_SIZE, DEFAULT_WINDOW_BORDER, DEFAULT_WINDOW_BACKGROUND)


func _on_building_selected(index: int) -> void:
	_selected_building = str(_building_select.get_item_metadata(index))


func _request(action: String, method: HTTPClient.Method, path: String, body: Dictionary = {}) -> void:
	if not _pending_action.is_empty():
		_status.text = "Подождите завершения текущего запроса."
		return
	_pending_action = action
	ApiClient.request_json(method, path, body)


func _load_city() -> void:
	_set_view("city")
	_request_city_data()


func _request_city_data() -> void:
	_request("city", HTTPClient.METHOD_GET, "/api/castle/%d/population" % _character_id)


func _load_building() -> void:
	if STORAGE_BUILDINGS.has(_selected_building):
		_open_storage_window(_selected_building)
		return
	if _selected_building == "stable":
		_open_stable_window()
		return
	_set_view("building")
	_request_building_state()


func _request_building_state() -> void:
	_request("building", HTTPClient.METHOD_GET, "/api/buildings/%s/%d" % [_selected_building, _character_id])


func _load_forge() -> void:
	_set_view("forge")
	_request("forge", HTTPClient.METHOD_GET, "/api/forge/%d" % _character_id)


func _load_travelers() -> void:
	_set_view("travelers")
	_request("travelers", HTTPClient.METHOD_GET, "/api/world/traveling-citizens?character_id=%d" % _character_id)


func _load_convoys() -> void:
	_set_view("convoys")
	_request("convoys", HTTPClient.METHOD_GET, "/api/world/traveling-convoys?character_id=%d" % _character_id)


func _load_terrain_routes() -> void:
	_request("terrain_routes", HTTPClient.METHOD_GET, "/api/map/terrain")


func _forge_create_order(item_id: int) -> void:
	_request("forge_action", HTTPClient.METHOD_POST,
		"/api/forge/%d/orders" % _character_id, {"item_id": item_id})


func _forge_collect_order(order_id: int) -> void:
	_request("forge_action", HTTPClient.METHOD_POST,
		"/api/forge/%d/orders/%d/collect" % [_character_id, order_id])


func _stable_action(action: String, body: Dictionary) -> void:
	_request("stable_action", HTTPClient.METHOD_POST,
		"/api/buildings/stable/%d/%s" % [_character_id, action], body)


func _on_stable_view_action(action: String, payload: Dictionary) -> void:
	if action == "refresh":
		if _pending_action.is_empty():
			_request_building_state()
		return
	if not _pending_action.is_empty():
		_stable_window.set_message("Подождите завершения текущего запроса.", true)
		return
	match action:
		"dispatch":
			_stable_action("transport/dispatch", payload)
		"toggle_convoy_pin":
			_stable_toggle_convoy_pin(int(payload["convoy_id"]), bool(payload["pinned"]))
		"repair_cart":
			_stable_repair_cart(str(payload["cart_id"]))
		"rename_cart":
			_stable_action("cart/rename", payload)
		"set_auto_repair":
			_stable_action("cart/auto_repair", payload)
		"purchase_horse":
			_stable_purchase_horse(int(payload["slot_index"]))
		"purchase_cart":
			_stable_purchase_cart()
		"purchase_upgrade":
			_stable_purchase_upgrade(str(payload["upgrade_id"]))
		"start_upgrade":
			_start_upgrade()


func _stable_toggle_convoy_pin(convoy_id: int, pinned: bool) -> void:
	_stable_action("transport/pin", {"convoy_id": convoy_id, "pinned": not pinned})


func _stable_repair_cart(cart_id: String) -> void:
	_stable_action("cart/repair", {"cart_id": cart_id})


func _stable_purchase_horse(slot_index: int) -> void:
	_stable_action("horse/purchase", {"slot_index": slot_index})


func _stable_purchase_cart() -> void:
	_stable_action("cart/purchase", {"grade": 1})


func _stable_purchase_upgrade(upgrade_id: String) -> void:
	_stable_action("stall-upgrade/purchase", {"upgrade_id": upgrade_id})


func _build_treasury_dialog() -> void:
	_treasury_dialog = TREASURY_DIALOG_SCRIPT.new()
	_treasury_dialog.confirmed.connect(_on_treasury_confirmed)
	add_child(_treasury_dialog)


func _build_contribution_dialog() -> void:
	_contribution_dialog = CONTRIBUTION_DIALOG_SCRIPT.new()
	_contribution_dialog.confirmed.connect(_on_storage_confirmed)
	add_child(_contribution_dialog)


# Количество ограничивает серверный остаток здания и рюкзака; сервер проверяет его повторно при отправке.
func _open_storage_dialog(mode: String, resource: String) -> void:
	if not _pending_action.is_empty():
		_status.text = "Подождите завершения текущего запроса."
		return
	var label := str(RESOURCE_LABELS.get(resource, resource))
	if mode == "withdraw":
		var stock := int(_dictionary_or_empty(_building.get("storage", {})).get(resource, 0))
		var withdrawable := _offer_for(resource, "storage_withdrawable")
		_contribution_dialog.open("withdraw", resource, label, stock,
			int(withdrawable.get("max_withdraw", 0)), withdrawable,
			float(withdrawable.get("item_weight_kg", 0.0)))
		return
	var depositable := _offer_for(resource, "storage_depositable")
	_contribution_dialog.open("deposit", resource, label,
		int(depositable.get("in_backpack", 0)), int(depositable.get("max_deposit", 0)))


func _on_storage_view_action(action: String, payload: Dictionary) -> void:
	if not _pending_action.is_empty():
		_storage_window.set_message("Подождите завершения текущего запроса.")
		return
	match action:
		"storage_withdraw":
			_open_storage_dialog("withdraw", str(payload.get("resource", "")))
		"storage_deposit":
			_open_storage_dialog("deposit", str(payload.get("resource", "")))
		"upgrade_building":
			_start_upgrade()


func _on_forge_view_action(action: String, payload: Dictionary) -> void:
	if not _pending_action.is_empty():
		_forge_window.set_message("Подождите завершения текущего запроса.", true)
		return
	match action:
		"create_order":
			_forge_create_order(int(payload["item_id"]))
		"collect_order":
			_forge_collect_order(int(payload["order_id"]))


func _on_storage_confirmed(mode: String, resource: String, quantity: int) -> void:
	var request := _storage_action_request(mode, resource, quantity)
	var body: Dictionary = request["body"]
	_request("storage_action", HTTPClient.METHOD_POST, str(request["path"]), body)


func _storage_action_request(mode: String, resource: String, quantity: int) -> Dictionary:
	var action := "storage/withdraw" if mode == "withdraw" else "storage/deposit"
	return {
		"path": "/api/buildings/%s/%d/%s" % [_selected_building, _character_id, action],
		"body": {"resource": resource, "quantity": quantity},
	}


# Как refresh_carrying_state в Python-клиенте: переносимый вес и экипировка берутся из инвентаря.
func _sync_character_carrying(inventory: Dictionary) -> void:
	if GameSession.character.is_empty():
		return
	GameSession.character["carried_weight_kg"] = float(inventory.get("carried_weight_kg", 0.0))
	GameSession.character["equipment"] = _dictionary_or_empty(inventory.get("equipment", {})).duplicate(true)
	GameSession.character["equipment_bonuses"] = _dictionary_or_empty(inventory.get("bonuses", {})).duplicate(true)


func _offer_for(resource: String, key: String) -> Dictionary:
	return _dictionary_or_empty(_dictionary_or_empty(_building.get(key, {})).get(resource, {}))


static func _dictionary_or_empty(value: Variant) -> Dictionary:
	if value is Dictionary:
		return value
	return {}


func _start_upgrade() -> void:
	_request("building_action", HTTPClient.METHOD_POST,
		"/api/buildings/%s/%d/upgrade/start" % [_selected_building, _character_id])


func _start_castle_upgrade(upgrade_id: String) -> void:
	_request("castle_upgrade", HTTPClient.METHOD_POST,
		"/api/castle/%d/upgrades/%s" % [_character_id, upgrade_id])


func _open_treasury_dialog(action: String, maximum: int) -> void:
	var mode := "deposit" if action == "treasury_deposit" else "withdraw"
	_treasury_dialog.open(mode, "copper", "", maximum, maximum)


func _on_treasury_confirmed(mode: String, _item_key: String, quantity: int) -> void:
	_request("treasury_" + mode, HTTPClient.METHOD_POST, "/api/castle/%d/treasury" % _character_id,
		{"direction": mode, "amount_copper": quantity})


func _on_castle_action(action: String, payload: Dictionary) -> void:
	if action == "refresh":
		if _pending_action.is_empty():
			_request_city_data()
		return
	if not _pending_action.is_empty():
		_castle_view.set_message("Подождите завершения текущего запроса.", true)
		return
	match action:
		"assign_citizen":
			_assign_citizen(int(payload["citizen_id"]), str(payload["worksite_key"]), int(payload["slot_index"]))
		"recall_citizen":
			_recall_citizen(int(payload["citizen_id"]))
		"treasury_deposit", "treasury_withdraw":
			_open_treasury_dialog(action, int(payload["maximum_copper"]))
		"upgrade_start":
			_start_castle_upgrade(str(payload["upgrade_id"]))


func _handle_castle_completed(action: String, success: bool, payload: Variant) -> void:
	if not success:
		_castle_view.set_message(str(payload), true)
		return
	if not payload is Dictionary or not payload.get("population") is Dictionary:
		_castle_view.set_message("Некорректный ответ API населения.", true)
		return
	_city = payload["population"]
	_castle_view.set_state(_city)
	_window_title.text = _castle_view.window_title()
	_city_map.set_city_state(_city, _building)
	if CASTLE_SUCCESS_MESSAGES.has(action):
		_castle_view.set_message(CASTLE_SUCCESS_MESSAGES[action], false)


func _assign_citizen(citizen_id: int, worksite: String, slot_index: int) -> void:
	_request("citizen_assign", HTTPClient.METHOD_POST,
		"/api/castle/%d/citizens/%d/assign" % [_character_id, citizen_id],
		{"building": worksite, "slot_index": slot_index})


func _recall_citizen(citizen_id: int) -> void:
	_request("citizen_recall", HTTPClient.METHOD_POST,
		"/api/castle/%d/citizens/%d/recall" % [_character_id, citizen_id])


func _toggle_player_work(slot_index: int) -> void:
	_request("building_action", HTTPClient.METHOD_POST,
		"/api/buildings/%s/%d/workers/player/toggle" % [_selected_building, _character_id],
		{"slot_index": slot_index})


func _fire_worker(slot_index: int) -> void:
	_request("building_action", HTTPClient.METHOD_POST,
		"/api/buildings/%s/%d/workers/fire" % [_selected_building, _character_id],
		{"slot_index": slot_index})


func _on_api_completed(success: bool, payload: Variant) -> void:
	var action := _pending_action
	_pending_action = ""
	if action.begins_with("chat_"):
		_handle_chat_completed(action, success, payload)
		return
	if action.begins_with("workshop_"):
		_handle_workshop_completed(action, success, payload)
		return
	if action.begins_with("inventory_"):
		_handle_inventory_completed(action, success, payload)
		return
	if action == "profile_update":
		_handle_profile_completed(success, payload)
		return
	if action in CASTLE_ACTIONS:
		_handle_castle_completed(action, success, payload)
		if action == "city" and success and not GameSession.character.has("carried_weight_kg"):
			_request_inventory()
		return
	if not success:
		if not _exit_intent.is_empty() and action == "return":
			_fail_exit(str(payload))
			return
		if action == "buy_drink":
			var error := _tavern_purchase_error(str(payload))
			if not error.is_empty():
				_status.text = error
			return
		if action == "drinks":
			_details.text = "Таверна · напитки не загружены."
		if action.begins_with("travel_"):
			_map_hint.text = "Пути мира: %s" % str(payload)
			return
		_status.text = str(payload)
		if action in ["building", "building_action", "storage_action", "stable_action", "terrain_routes", "forge", "forge_action", "building_hire_population", "building_citizen_assign", "building_citizen_recall"]:
			_set_window_error(str(payload))
		return
	if not action.begins_with("travel_"):
		_status.text = "Данные сервера обновлены."
	match action:
		"storage_action":
			if not payload is Dictionary or not payload.get("building") is Dictionary:
				_status.text = "Некорректный ответ API склада."
				return
			_show_building(payload["building"])
			_request("inventory_load", HTTPClient.METHOD_GET, "/api/inventory/%d" % _character_id)
		"terrain_routes":
			if not payload is Dictionary or not payload.get("terrain", {}) is Dictionary:
				_set_window_error("Некорректный ответ API карты.")
				return
			var roads: Variant = payload["terrain"].get("roads", {})
			if not roads is Dictionary or not roads.get("routes", []) is Array:
				_set_window_error("В ответе карты нет списка маршрутов.")
				return
			_routes = roads["routes"]
			_stable_window.set_routes(_routes, _city.get("city_resource_storage", {}))
		"building", "building_action":
			if not payload is Dictionary or not payload.get("building") is Dictionary:
				_status.text = "Некорректный ответ API здания."
				return
			_show_building(payload["building"])
			if action == "building_action":
				_production_window.set_message("")
		"building_hire_population":
			_handle_hire_population(payload)
		"building_citizen_assign":
			_handle_citizen_assign(payload)
		"building_citizen_recall":
			_handle_citizen_recall(payload)
		"stable_action":
			if not payload is Dictionary or not payload.get("building") is Dictionary:
				_status.text = "Некорректный ответ API конюшни."
				return
			if _view == "convoys":
				_building = payload["building"]
				_load_convoys()
			else:
				_show_building(payload["building"])
				if payload.has("convoy"):
					_stable_window.set_message("Повозка отправлена по маршруту.", false)
		"forge", "forge_action":
			if not payload is Dictionary:
				_set_window_error("Некорректный ответ API кузницы.")
				return
			_forge_window.set_state(payload)
		"drinks":
			if not payload is Dictionary or not payload.get("drinks", []) is Array:
				_status.text = "Некорректный ответ API таверны."
				return
			_drinks = payload["drinks"]
			if _view == "tavern":
				_render_tavern()
		"buy_drink":
			if not payload is Dictionary or not payload.get("character") is Dictionary:
				_status.text = "Сервер вернул некорректного персонажа."
				return
			GameSession.select_character(payload["character"])
			if _view == "tavern":
				_render_tavern()
		"travelers":
			_render_travelers(payload)
		"convoys":
			_render_convoys(payload)
		"travel_routes", "travel_citizens", "travel_convoys":
			_on_travel_completed(action, payload)
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
			_world_audio().fade_out_for_transition()
			SCENE_TRANSITION.run(get_tree(), func() -> void: get_tree().change_scene_to_file("res://scenes/main.tscn"))


func _format_seconds(seconds: int) -> String:
	var safe_seconds := maxi(0, seconds)
	var hours := floori(float(safe_seconds) / 3600.0)
	var minutes := floori(float(safe_seconds % 3600) / 60.0)
	var remainder := safe_seconds % 60
	if hours > 0:
		return "%d ч %02d мин" % [hours, minutes]
	if minutes > 0:
		return "%02d:%02d" % [minutes, remainder]
	return "00:%02d" % remainder


func _render_travelers(payload: Variant) -> void:
	_details.text = "Горожане в пути"
	_remove_named_content("TravelerControls")
	var rows := VBoxContainer.new()
	rows.name = "TravelerControls"
	var citizens: Variant = payload.get("citizens", []) if payload is Dictionary else []
	if not citizens is Array or citizens.is_empty():
		_add_empty_row(rows, "Сейчас горожан в пути нет.")
	else:
		for citizen in citizens:
			if not citizen is Dictionary:
				continue
			var label := Label.new()
			label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			label.text = "%s · %s · %s · осталось %s" % [
				str(citizen.get("name", "Горожанин")),
				str(BUILDINGS.get(str(citizen.get("job_building", "")), citizen.get("job_building", ""))),
				"Возвращается" if str(citizen.get("travel_direction", "")) == "returning" else "Едет на работу",
				_format_seconds(int(citizen.get("travel_seconds_left", citizen.get("eta_seconds", 0)))),
			]
			rows.add_child(label)
	_content.add_child(rows)


func _render_convoys(payload: Variant) -> void:
	_details.text = "Активные повозки мира"
	_remove_named_content("ConvoyControls")
	var rows := VBoxContainer.new()
	rows.name = "ConvoyControls"
	var convoys: Variant = payload.get("convoys", []) if payload is Dictionary else []
	if not convoys is Array or convoys.is_empty():
		_add_empty_row(rows, "Активных рейсов нет.")
	else:
		for convoy in convoys:
			if not convoy is Dictionary:
				continue
			var row := HBoxContainer.new()
			var label := Label.new()
			label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			label.text = "%s · %s → %s · возница: %s · %s · %s" % [
				str(convoy.get("cart_name", CART_GRADE_NAMES.get(str(convoy.get("cart_grade", 1)), "Повозка"))),
				str(convoy.get("cart_id", "")),
				str(convoy.get("destination_name", convoy.get("route_name", "Маршрут"))),
				str(convoy.get("driver_name", "Горожанин")),
				str(convoy.get("status", convoy.get("phase", "В пути"))),
				"закреплён" if bool(convoy.get("pinned", false)) else "разовый рейс",
			]
			row.add_child(label)
			var pin := Button.new()
			pin.text = "Открепить" if bool(convoy.get("pinned", false)) else "Закрепить"
			pin.pressed.connect(_stable_toggle_convoy_pin.bind(
				int(convoy.get("id", 0)), bool(convoy.get("pinned", false))))
			row.add_child(pin)
			rows.add_child(row)
	_content.add_child(rows)


func _remove_named_content(child_name: String) -> void:
	for child in _content.get_children():
		if child.name == child_name:
			_content.remove_child(child)
			child.queue_free()


func _add_empty_row(parent: Node, text: String) -> void:
	var label := Label.new()
	label.text = text
	parent.add_child(label)


func _set_window_error(text: String) -> void:
	if _view == "storage":
		_storage_window.set_message(text)
	elif _view == "building":
		_production_window.set_message(text)
	elif _view == "stable":
		_stable_window.set_message(text, true)
	elif _view == "forge":
		_forge_window.set_message(text, true)


func _show_building(state: Dictionary) -> void:
	_building = state
	if STORAGE_BUILDINGS.has(_selected_building):
		_storage_window.set_state(_building)
		_storage_window.set_message("")
		_window_title.text = _storage_window.window_title()
		return
	if _selected_building == "stable":
		_stable_window.set_state(_building)
		_window_title.text = _stable_window.window_title()
		if _routes.is_empty() and _pending_action.is_empty():
			_load_terrain_routes()
		return
	_render_building()


func _render_building() -> void:
	_production_window.set_character_id(_character_id)
	_production_window.set_state(_building)
	_window_title.text = _production_window.window_title()


# Действия производственного окна: вид уже спросил подтверждение, здесь — запросы к серверу, как в Python.
func _on_production_view_action(action: String, payload: Dictionary) -> void:
	if action == "refresh":
		if _pending_action.is_empty():
			_request_building_state()
		return
	if not _pending_action.is_empty():
		_production_window.set_message(PRODUCTION_RULES.MSG_BUSY)
		return
	var slot_index := int(payload.get("slot_index", -1))
	match action:
		"storage_withdraw":
			_open_storage_dialog("withdraw", str(payload.get("resource", "")))
		"storage_deposit":
			_open_storage_dialog("deposit", str(payload.get("resource", "")))
		"upgrade_building":
			_start_upgrade()
		"production_upgrade":
			_start_production_upgrade(str(payload.get("upgrade_id", "")))
		"hire":
			_hire_worker(slot_index)
		"fire":
			_fire_slot(slot_index)
		"player":
			_toggle_player_slot(slot_index)


# Карточка улучшения фермы или лесопилки: POST .../farm/upgrade или .../lumber-camp/upgrade с upgrade_id.
func _start_production_upgrade(upgrade_id: String) -> void:
	_request("building_action", HTTPClient.METHOD_POST,
		"/api/buildings/%s/%d/%s" % [_selected_building, _character_id, PRODUCTION_UPGRADES.action_path(_selected_building)],
		{"upgrade_id": upgrade_id})


# Найм как hire_worker() в Python: свежий список горожан, первый подходящий, затем назначение на место.
func _hire_worker(slot_index: int) -> void:
	_pending_slot_index = slot_index
	_request("building_hire_population", HTTPClient.METHOD_GET, "/api/castle/%d/population" % _character_id)


func _handle_hire_population(payload: Variant) -> void:
	if not payload is Dictionary or not payload.get("population") is Dictionary:
		_production_window.set_message(PRODUCTION_RULES.MSG_BAD_POPULATION)
		return
	var population: Dictionary = payload["population"]
	_city = population
	var citizen := PRODUCTION_RULES.hire_candidate(population.get("citizens", []))
	if citizen.is_empty():
		_production_window.set_message(PRODUCTION_RULES.MSG_NO_CITIZENS)
		return
	_pending_hire_name = str(citizen.get("name", ""))
	_request("building_citizen_assign", HTTPClient.METHOD_POST,
		"/api/castle/%d/citizens/%d/assign" % [_character_id, int(citizen.get("id", 0))],
		{"building": _selected_building, "slot_index": _pending_slot_index})


func _handle_citizen_assign(payload: Variant) -> void:
	_store_population(payload)
	_production_window.set_message(PRODUCTION_RULES.hired_text(_pending_hire_name))
	_request_building_state()


# Горожанина возвращают в город (recall), остальных снимают через workers/fire, как fire_worker() в Python.
func _fire_slot(slot_index: int) -> void:
	var citizen := PRODUCTION_RULES.citizen_id(PRODUCTION_RULES.slot_at(_building, slot_index).get("worker_id"))
	if citizen < 0:
		_fire_worker(slot_index)
		return
	_request("building_citizen_recall", HTTPClient.METHOD_POST,
		"/api/castle/%d/citizens/%d/recall" % [_character_id, citizen])


func _handle_citizen_recall(payload: Variant) -> void:
	_store_population(payload)
	_production_window.set_message(PRODUCTION_RULES.MSG_RECALLED)
	_request_building_state()


func _store_population(payload: Variant) -> void:
	if payload is Dictionary and payload.get("population") is Dictionary:
		_city = payload["population"]


func _on_city_crystal_rest_requested() -> void:
	_city_map.set_active_notice("Сервер Экономики не поддерживает восстановление у Кристалла Жизни.")


# Как в Python: встать на добычу нельзя, если игрок нигде не работает, а склад полон по ресурсам места.
func _toggle_player_slot(slot_index: int) -> void:
	if PRODUCTION_RULES.player_confirm_blocked(_building, slot_index):
		_production_window.set_message(PRODUCTION_RULES.MSG_STORAGE_FULL)
		return
	_toggle_player_work(slot_index)


# Как _refresh_if_due в Python: пока окно здания или склада открыто, состояние перечитывается каждые 5 секунд.
func _on_building_timer() -> void:
	if (_view == "building" or _view == "storage") and _pending_action.is_empty() and not _exit_queued:
		_request_building_state()


func _build_building_timer() -> void:
	_building_timer = Timer.new()
	_building_timer.wait_time = BUILDING_REFRESH_SECONDS
	_building_timer.timeout.connect(_on_building_timer)
	add_child(_building_timer)
	_building_timer.start()


func _world_audio():
	if _audio == null:
		_audio = WORLD_AUDIO_SCRIPT.new()
		add_child(_audio)
	return _audio


func _set_view(view_name: String) -> void:
	var previous_view := _view
	var previous_location := _chat_location()
	_view = view_name
	if previous_view == "tavern" and view_name != "tavern":
		_world_audio().fade_out_for_transition()
	elif view_name == "tavern" and previous_view != "tavern":
		_world_audio().play_tavern()
	if view_name != "tavern":
		_remove_named_content("TavernControls")
	if _chat_location() != previous_location:
		_chat_panel.clear_messages()
	var window_open := view_name != "map"
	_list_panel.visible = window_open
	_window_backdrop.visible = window_open
	_window_title.text = _window_title_for(view_name)
	_refresh_button.visible = view_name != "static"
	_apply_window_layout_for(view_name)
	_apply_window_sections()
	if not window_open:
		_apply_map_layer()
	_update_walk_pause()


# Карта города занимает весь экран; окна управления открываются поверх неё.
# Вторая вкладка панели — пути мира (повозки и горожане), переключается кнопкой в шапке.
func _build_city_map_panel(parent: Node) -> void:
	_city_map_panel = PanelContainer.new()
	_city_map_panel.name = "EconomyCityMapPanel"
	_city_map_panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	parent.add_child(_city_map_panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 8)
	_city_map_panel.add_child(box)
	var header := HBoxContainer.new()
	box.add_child(header)
	_map_title = Label.new()
	_map_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_map_title.add_theme_font_size_override("font_size", 22)
	_map_title.add_theme_color_override("font_color", TITLE_COLOR)
	header.add_child(_map_title)
	_map_toggle = Button.new()
	_map_toggle.custom_minimum_size = Vector2(140, 36)
	_map_toggle.pressed.connect(_toggle_map_layer)
	header.add_child(_map_toggle)
	var fit_button := Button.new()
	fit_button.text = "Вся карта"
	fit_button.custom_minimum_size = Vector2(140, 36)
	fit_button.pressed.connect(_fit_active_map)
	header.add_child(fit_button)
	_hero_button = Button.new()
	_hero_button.text = "К герою"
	_hero_button.custom_minimum_size = Vector2(140, 36)
	_hero_button.pressed.connect(_center_city_on_hero)
	header.add_child(_hero_button)
	for nav_entry in [["Горожане в пути", _load_travelers], ["Повозки", _load_convoys], ["К персонажам", _return_to_characters]]:
		var nav_button := Button.new()
		nav_button.text = nav_entry[0]
		nav_button.custom_minimum_size = Vector2(150, 36)
		nav_button.pressed.connect(nav_entry[1])
		header.add_child(nav_button)
	_city_map = CITY_MAP_SCRIPT.new()
	_city_map.custom_minimum_size = Vector2(900, 480)
	_city_map.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_city_map.building_clicked.connect(_on_city_map_building_clicked)
	_city_map.gate_clicked.connect(_on_city_map_gate_clicked)
	_city_map.profile_requested.connect(_open_profile_overlay)
	_city_map.crystal_rest_requested.connect(_on_city_crystal_rest_requested)
	_city_map.window_is_open = _is_city_window_open
	box.add_child(_city_map)
	_travel_map = TRAVEL_MAP_SCRIPT.new()
	_travel_map.custom_minimum_size = Vector2(900, 480)
	_travel_map.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_travel_map.visible = false
	box.add_child(_travel_map)
	_map_hint = Label.new()
	_map_hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_map_hint.add_theme_color_override("font_color", MUTED_COLOR)
	box.add_child(_map_hint)
	_travel_timer = Timer.new()
	_travel_timer.wait_time = TRAVEL_REFRESH_SECONDS
	_travel_timer.timeout.connect(_refresh_travel_layer)
	add_child(_travel_timer)
	_travel_timer.start()
	_apply_map_layer()


func _close_window() -> void:
	# Как «ПОКИНУТЬ» в Python: с производственного места нельзя уйти, пока игрок работает.
	if _view == "building" and PRODUCTION_RULES.player_is_working(_building, _character_id):
		_production_window.set_message(PRODUCTION_RULES.MSG_LEAVE_BLOCKED)
		return
	if _view == "tavern":
		_leave_tavern()
		return
	_set_view("map")


func _refresh_window() -> void:
	match _view:
		"city":
			_load_city()
		"building":
			_load_building()
		"storage", "stable":
			_request_building_state()
		"forge":
			_load_forge()
		"tavern":
			_load_tavern()
		"travelers":
			_load_travelers()
		"convoys":
			_load_convoys()
		"workshop":
			_request_workshop_refresh()



func _on_city_map_building_clicked(economy_key: String) -> void:
	if not _pending_action.is_empty():
		_status.text = "Подождите завершения текущего запроса."
		return
	match economy_key:
		"castle":
			_load_city()
		"forge":
			_load_forge()
		"tavern":
			_enter_tavern()
		"barracks", "engineering", "university", "academy", "mage_school":
			_open_static_building(economy_key)
		"workshop":
			_open_workshop_window()
		"barn", "warehouse":
			_open_storage_window(economy_key)
		"stable":
			_open_stable_window()


func _open_storage_window(building_key: String) -> void:
	_selected_building = building_key
	_sync_building_select(building_key)
	_set_view("storage")
	_request_building_state()


func _open_stable_window() -> void:
	_selected_building = "stable"
	_sync_building_select("stable")
	_set_view("stable")
	_request_building_state()


func _open_static_building(building_key: String) -> void:
	_remove_named_content("StaticBuildingView")
	var view: VBoxContainer = STATIC_BUILDING_VIEW_SCRIPT.new()
	view.name = "StaticBuildingView"
	view.setup(building_key)
	view.back_requested.connect(_close_window)
	_content.add_child(view)
	_building_window_title = view.window_title()
	_static_building = building_key
	_set_view("static")


func _open_workshop_window() -> void:
	_remove_named_content("WorkshopView")
	var view: VBoxContainer = WORKSHOP_VIEW_SCRIPT.new()
	view.name = "WorkshopView"
	view.action_requested.connect(_on_workshop_action)
	_content.add_child(view)
	_workshop_view = view
	_building_window_title = view.window_title()
	_set_view("workshop")
	_request_workshop_refresh()


func _request_workshop_refresh() -> void:
	_request("workshop_refresh", HTTPClient.METHOD_GET, "/api/buildings/stable/%d" % _character_id)


func _on_workshop_action(action: String, payload: Dictionary) -> void:
	if action == "refresh":
		_request_workshop_refresh()
		return
	if action != "order_cart":
		return
	if not _pending_action.is_empty():
		_workshop_view.set_message("Подождите завершения текущего запроса.", true)
		return
	_request("workshop_order", HTTPClient.METHOD_POST,
		"/api/buildings/stable/%d/cart/purchase" % _character_id, {"grade": int(payload.get("grade", 1))})


func _handle_workshop_completed(action: String, success: bool, payload: Variant) -> void:
	if not is_instance_valid(_workshop_view):
		return
	if not success:
		_workshop_view.set_message(str(payload), true)
		return
	if not payload is Dictionary or not payload.get("building") is Dictionary:
		_workshop_view.set_message("Некорректный ответ API мастерской.", true)
		return
	_workshop_view.set_state(payload["building"])
	if action == "workshop_order":
		_workshop_view.set_message(WORKSHOP_ORDER_MESSAGE, false)


func _sync_building_select(building_key: String) -> void:
	for index in range(_building_select.item_count):
		if str(_building_select.get_item_metadata(index)) == building_key:
			_building_select.select(index)


func _window_title_for(view_name: String) -> String:
	match view_name:
		"city":
			return _castle_view.window_title()
		"building", "static", "workshop":
			return _building_window_title
		"storage":
			return _storage_window.window_title()
		"stable":
			return _stable_window.window_title()
		"forge":
			return _forge_window.window_title()
		"tavern":
			return "Таверна"
		"travelers":
			return "Горожане в пути"
		"convoys":
			return "Повозки"
	return ""


func _apply_window_sections() -> void:
	for child in _content.get_children():
		if child is CanvasItem:
			child.visible = _is_section_visible(str(child.name))


func _on_content_child_entered(child: Node) -> void:
	if child is CanvasItem:
		child.visible = _is_section_visible(str(child.name))


func _is_section_visible(section_name: String) -> bool:
	return WINDOW_SECTIONS.get(_view, []).has(section_name)


func _toggle_map_layer() -> void:
	_map_layer = "city" if _map_layer == "travel" else "travel"
	_apply_map_layer()


func _apply_map_layer() -> void:
	var travel := _map_layer == "travel"
	_city_map.visible = not travel
	_travel_map.visible = travel
	_hero_button.visible = not travel
	_map_title.text = "Пути мира · повозки и горожане" if travel else "Радбург · карта города"
	_map_toggle.text = "Город" if travel else "Пути мира"
	_map_hint.text = TRAVEL_MAP_HINT if travel else CITY_MAP_HINT
	_update_walk_pause()
	if travel:
		_refresh_travel_layer()


func _fit_active_map() -> void:
	if _map_layer == "travel":
		_travel_map.fit_map()
	else:
		_city_map.fit_map()


# Пути мира читаются только на открытой карте и при свободном соединении: один запрос за раз, списки не трогаем.
func _refresh_travel_layer() -> void:
	if _view != "map" or _map_layer != "travel" or _character_id <= 0 or not _pending_action.is_empty():
		return
	if _travel_map.has_routes():
		_request_travel_citizens()
	else:
		_request("travel_routes", HTTPClient.METHOD_GET, "/api/map/terrain")


func _request_travel_citizens() -> void:
	_request("travel_citizens", HTTPClient.METHOD_GET, "/api/world/traveling-citizens?character_id=%d" % _character_id)


# Цепочка ответов: маршруты (один раз), затем горожане и повозки. Ветки не пишут в _content, _details и _status.
func _on_travel_completed(action: String, payload: Variant) -> void:
	if _view != "map" or _map_layer != "travel":
		return
	if action == "travel_routes":
		var terrain: Variant = payload.get("terrain", {}) if payload is Dictionary else {}
		var roads: Variant = terrain.get("roads", {}) if terrain is Dictionary else {}
		if not roads is Dictionary or not roads.get("routes", null) is Array:
			_map_hint.text = "Пути мира: в ответе карты нет маршрутов."
			return
		_travel_map.set_routes(roads["routes"])
		_request_travel_citizens()
	elif action == "travel_citizens":
		if not payload is Dictionary or not payload.get("citizens", null) is Array:
			_map_hint.text = "Пути мира: некорректный ответ горожан."
			return
		_travel_map.set_citizens(payload["citizens"])
		_request("travel_convoys", HTTPClient.METHOD_GET, "/api/world/traveling-convoys?character_id=%d" % _character_id)
	else:
		if not payload is Dictionary or not payload.get("convoys", null) is Array:
			_map_hint.text = "Пути мира: некорректный ответ повозок."
			return
		_travel_map.set_convoys(payload["convoys"])


func _on_city_map_gate_clicked(gate: Dictionary) -> void:
	if not _exit_intent.is_empty() or not _map_gate_pending.is_empty():
		return
	_map_gate_pending = str(gate.get("id", "east"))
	_start_map_transition_if_idle()


# Карта открывается, когда закрыт запрос города: иначе новая сцена получит «Запрос уже выполняется».
func _start_map_transition_if_idle() -> void:
	if _map_gate_pending.is_empty():
		return
	if not _exit_intent.is_empty() or SCENE_TRANSITION.is_running(get_tree()):
		_map_gate_pending = ""
		return
	if not _pending_action.is_empty():
		return
	GameSession.pending_map_gate = _map_gate_pending
	_map_gate_pending = ""
	_world_audio().fade_out_for_transition()
	SCENE_TRANSITION.run(get_tree(), func() -> void: get_tree().change_scene_to_file(WORLD_MAP_SCENE))


# Окно здания уже открыто: дверь на карте города не открывает его второй раз (как *_menu_open в city_scene.py).
func _is_city_window_open(window_key: String) -> bool:
	match window_key:
		"tavern":
			return _view == "tavern"
		"forge":
			return _view == "forge"
		"workshop":
			return _view == "workshop"
		"barn", "warehouse":
			return _view == "storage" and _selected_building == window_key
		"barracks", "engineering", "university", "academy", "mage_school":
			return _view == "static" and _static_building == window_key
	return false


func _build_chat() -> void:
	_chat_panel = LOCATION_CHAT_SCRIPT.new()
	_chat_panel.z_index = 6
	_chat_panel.message_submitted.connect(_on_chat_message_submitted)
	add_child(_chat_panel)
	_chat_timer = Timer.new()
	_chat_timer.wait_time = CHAT_POLL_INTERVAL
	_chat_timer.timeout.connect(_poll_chat)
	add_child(_chat_timer)
	_chat_timer.start()


# Чат привязан к локации, как в Python: город — «city», таверна — «tavern».
func _chat_location() -> String:
	return "tavern" if _view == "tavern" else "city"


# Опрос снимка локации одновременно обновляет присутствие игрока на сервере.
func _poll_chat() -> void:
	if not _chat_enabled or not _pending_action.is_empty() or _character_id <= 0:
		return
	_chat_request_location = _chat_location()
	_request("chat_snapshot", HTTPClient.METHOD_GET,
		"/api/social/snapshot?location=%s&character_id=%d" % [_chat_request_location, _character_id])


func _on_chat_message_submitted(text: String, recipient_id: int) -> void:
	if not _pending_action.is_empty():
		_chat_panel.set_status("Подождите завершения текущего запроса.")
		return
	_chat_sent_recipient = recipient_id
	_chat_panel.set_status("Отправляем сообщение…", false)
	_request("chat_send", HTTPClient.METHOD_POST, "/api/chat/messages", {
		"character_id": _character_id,
		"location": _chat_location(),
		"text": text,
		"recipient_id": recipient_id if recipient_id > 0 else null,
	})


func _handle_chat_completed(action: String, success: bool, payload: Variant) -> void:
	if not success:
		_chat_panel.set_status(str(payload))
		return
	if action == "chat_snapshot":
		_apply_chat_snapshot(payload)
		return
	_chat_panel.mark_sent(_chat_sent_recipient)
	_poll_chat()


func _apply_chat_snapshot(payload: Variant) -> void:
	if not payload is Dictionary or not payload.get("messages", []) is Array or not payload.get("occupants", []) is Array:
		_chat_panel.set_status("Некорректный ответ чата.")
		return
	if _chat_request_location != _chat_location():
		return
	_chat_panel.apply_snapshot(payload["messages"], payload["occupants"], _character_id)
	if _city_map != null:
		_city_map.set_afk_players(payload["occupants"])


func _load_tavern() -> void:
	_set_view("tavern")
	_details.text = "Таверна · загрузка напитков…"
	_request("drinks", HTTPClient.METHOD_GET, "/api/drinks")


# Вход в таверну с улицы города и выход из неё: переход с затемнением, как CityScene ↔ TavernScene в main.py.
func _enter_tavern() -> void:
	SCENE_TRANSITION.run(get_tree(), _load_tavern)


func _leave_tavern() -> void:
	_world_audio().fade_out_for_transition()
	SCENE_TRANSITION.run(get_tree(), _set_view.bind("map"))


func _select_tavern_tab(tab: String) -> void:
	_tavern_tab = tab
	_render_tavern()


func _render_tavern() -> void:
	var character := GameSession.character
	_details.text = "Таверна · Хозяин трактира\nВаши средства: %s\nЗдоровье: %s / %s" % [
		CURRENCY_SCRIPT.format_amount(CURRENCY_SCRIPT.total_copper(character)),
		str(character.get("hp", "—")),
		str(character.get("max_hp", "—")),
	]
	_remove_named_content("TavernControls")
	var box := VBoxContainer.new()
	box.name = "TavernControls"
	box.add_theme_constant_override("separation", 6)
	_content.add_child(box)
	# Список напитков ставится под кнопками разделов: после городских блоков его не видно без прокрутки.
	_content.move_child(box, _details.get_index() + 1)
	var tabs := HBoxContainer.new()
	box.add_child(tabs)
	_add_tavern_tab(tabs, "НАПИТКИ", "drinks")
	_add_tavern_tab(tabs, "СКУПКА", "sell")
	if _tavern_tab == "sell":
		_add_tavern_title(box, "Скупка")
		# В Python-клиенте обработка скупки ещё не написана, поэтому вкладка только повторяет подсказку.
		_add_empty_row(box, "Кликните на предмет в рюкзаке")
		return
	_add_tavern_title(box, "Напитки бара")
	if _drinks.is_empty():
		_add_empty_row(box, "В баре нет напитков.")
		return
	for drink in _drinks:
		if drink is Dictionary:
			box.add_child(_drink_button(drink))
	_add_empty_row(box, "Двойной клик по напитку — купить. Описание показывается при наведении.")


func _add_tavern_tab(parent: Node, text: String, tab: String) -> void:
	var button := Button.new()
	button.text = text
	button.disabled = _tavern_tab == tab
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.pressed.connect(_select_tavern_tab.bind(tab))
	parent.add_child(button)


func _add_tavern_title(parent: Node, text: String) -> void:
	var title := Label.new()
	title.text = text
	title.add_theme_font_size_override("font_size", 20)
	parent.add_child(title)


func _drink_button(drink: Dictionary) -> Button:
	var price := int(drink.get("price_copper", 0))
	var drink_id := int(drink.get("id", 0))
	var button := Button.new()
	button.text = "%s — %s" % [str(drink.get("name", "Напиток")), CURRENCY_SCRIPT.format_amount(price)]
	button.tooltip_text = str(drink.get("description", ""))
	button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	button.custom_minimum_size.y = 40
	button.gui_input.connect(_on_drink_gui_input.bind(drink_id, price))
	return button


# Как в Python: одиночный клик только выбирает напиток, покупка — двойным кликом.
func _on_drink_gui_input(event: InputEvent, drink_id: int, price: int) -> void:
	var mouse := event as InputEventMouseButton
	if mouse != null and mouse.pressed and mouse.double_click and mouse.button_index == MOUSE_BUTTON_LEFT:
		_buy_drink(drink_id, price)


func _buy_drink(drink_id: int, price: int) -> void:
	if not CURRENCY_SCRIPT.has_enough_copper(GameSession.character, price):
		_status.text = TAVERN_BROKE_LINE
		return
	_request("buy_drink", HTTPClient.METHOD_POST, "/api/character/buy_drink", {
		"character_id": _character_id,
		"drink_id": drink_id,
	})


# Как в Python: при полном здоровье ошибку не показываем, реплику бармена сервер уже записал в чат таверны.
func _tavern_purchase_error(message: String) -> String:
	if message.contains(TAVERN_FULL_HP_ERROR):
		return ""
	return "Ошибка покупки: %s" % message


func _return_to_characters() -> void:
	_request("return", HTTPClient.METHOD_POST, "/api/sessions/disconnect")


func _build_profile_overlay() -> void:
	_profile_overlay = PROFILE_OVERLAY_SCRIPT.new()
	_profile_overlay.stat_requested.connect(_on_profile_stat_requested)
	_profile_overlay.level_requested.connect(_on_profile_level_requested)
	_profile_overlay.backpack_requested.connect(_open_inventory)
	add_child(_profile_overlay)


func _build_inventory_view() -> void:
	_inventory_view = INVENTORY_VIEW_SCRIPT.new()
	_inventory_view.action_requested.connect(_on_inventory_action_requested)
	_inventory_view.refresh_requested.connect(_request_inventory)
	_inventory_view.close_requested.connect(_close_inventory)
	add_child(_inventory_view)


# I и C открывают карточку персонажа, как в Tower. Esc карточку не закрывает, как в Python.
func _toggle_character_profile() -> void:
	if _profile_overlay.is_open():
		_profile_overlay.close()
	else:
		_open_profile_overlay()


func _open_profile_overlay() -> void:
	if GameSession.character.is_empty():
		return
	_profile_overlay.open(GameSession.character.duplicate(true))
	if not GameSession.character.has("equipment"):
		_request_inventory()


func _render_character_profile() -> void:
	if _profile_overlay.is_open():
		_profile_overlay.update_profile(GameSession.character.duplicate(true))


func _on_profile_stat_requested(stat_name: String, delta: int) -> void:
	var change: Dictionary = PROFILE_RULES_SCRIPT.adjust_stat(_profile_overlay.current_profile(), stat_name, delta)
	if change.is_empty():
		_show_profile_message("Эту характеристику сейчас нельзя изменить.")
		return
	_save_profile_change({"stats": change["stats"], "stat_points": change["stat_points"]})


func _on_profile_level_requested(delta: int) -> void:
	var change: Dictionary = PROFILE_RULES_SCRIPT.adjust_level(_profile_overlay.current_profile(), delta)
	if change.is_empty():
		_show_profile_message("Уровень сейчас нельзя изменить.")
		return
	_save_profile_change({"level": change["level"], "stats": change["stats"]})


func _save_profile_change(body: Dictionary) -> void:
	_request("profile_update", HTTPClient.METHOD_PUT, "/api/characters/%d" % _character_id, body)


func _handle_profile_completed(success: bool, payload: Variant) -> void:
	if not success:
		_show_profile_message(str(payload))
		return
	if not payload is Dictionary or not payload.get("character") is Dictionary:
		_show_profile_message("Сервер вернул некорректную карточку персонажа.")
		return
	GameSession.select_character(payload["character"])
	_render_character_profile()
	_show_profile_message("Характеристика обновлена сервером.")


func _show_profile_message(text: String) -> void:
	_status.text = text
	_map_hint.text = text


func _open_inventory() -> void:
	if GameSession.character.is_empty() or _character_id <= 0:
		return
	_inventory_view.open_panel()
	_request_inventory()


func _close_inventory() -> void:
	_inventory_view.close_panel()


func _request_inventory() -> void:
	if _character_id <= 0:
		return
	if not _pending_action.is_empty():
		_inventory_view.set_message("Подождите завершения текущего запроса.", true)
		return
	_inventory_view.set_message("Загружаем инвентарь…")
	_request("inventory_load", HTTPClient.METHOD_GET, "/api/inventory/%d" % _character_id)


func _on_inventory_action_requested(action: String, payload: Dictionary) -> void:
	if not INVENTORY_ACTION_PATHS.has(action):
		return
	if not _pending_action.is_empty():
		_inventory_view.set_message("Подождите завершения текущего запроса.", true)
		_inventory_view.resolve_action(false)
		return
	var body := payload.duplicate()
	body["character_id"] = _character_id
	_request("inventory_action", HTTPClient.METHOD_POST, str(INVENTORY_ACTION_PATHS[action]), body)


# Ответ /api/inventory/{id} или действия: рюкзак, экипировка и вес. Персонаж из ответа действия заменяет текущего,
# поэтому сначала он, потом переносимый вес и экипировка из инвентаря (как refresh_carrying_state в Python).
# Текст действия окно показывает только после успешного ответа, поэтому resolve_action вызывается здесь.
func _handle_inventory_completed(action: String, success: bool, payload: Variant) -> void:
	if not success:
		_inventory_view.set_message(str(payload), true)
		_status.text = str(payload)
		if action == "inventory_action":
			_inventory_view.resolve_action(false)
		return
	if not payload is Dictionary or not payload.get("inventory", []) is Array:
		_inventory_view.set_message("Некорректный ответ API инвентаря.", true)
		_status.text = "Некорректный ответ API инвентаря."
		if action == "inventory_action":
			_inventory_view.resolve_action(false)
		return
	_status.text = "Данные сервера обновлены."
	if action == "inventory_action" and payload.get("character") is Dictionary:
		GameSession.select_character(payload["character"])
	_sync_character_carrying(payload)
	_inventory_view.set_state(payload, PROFILE_RULES_SCRIPT.carry_capacity(GameSession.character))
	if action == "inventory_action":
		_inventory_view.resolve_action(true)
	else:
		_inventory_view.set_message("Инвентарь обновлён.")
	_render_character_profile()


# Как _any_modal_open в city_scene.py: открытое окно здания или карта путей останавливают героя.
func _update_walk_pause() -> void:
	if _city_map != null:
		_city_map.set_walk_paused(_view != "map" or _map_layer != "city")


func _center_city_on_hero() -> void:
	_city_map.center_on_player()


func _on_connection_restored(character: Dictionary) -> void:
	GameSession.select_character(character)
	match _view:
		"building":
			_load_building()
		"forge":
			_load_forge()
		"travelers":
			_load_travelers()
		"convoys":
			_load_convoys()
		"tavern":
			_load_tavern()
		"city":
			_load_city()
		_:
			_request_city_data()
