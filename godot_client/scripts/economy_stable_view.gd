extends VBoxContainer

# Конюшня из ui/stable_window.py: вкладки ТРАНСПОРТ, МАРШРУТЫ, ПОВОЗКИ, СТОЙЛО, УЛУЧШЕНИЯ.
# Вид не делает HTTP. По action_requested родитель выполняет запрос и передаёт ответ в set_state, set_routes, set_message.
#   "refresh" без payload: GET /api/buildings/stable/{character_id}; вид просит его раз в 5 с, пока окно открыто.
#   "dispatch" {cart_id: String, horse_ids: Array[int], driver_citizen_id: int, destination_building_id: String,
#       resource_ids: Array[String], pinned: bool}: POST /api/buildings/stable/{character_id}/transport/dispatch, тело = payload.
#   "toggle_convoy_pin" {convoy_id: int, pinned: bool}: pinned — текущее состояние рейса; родитель шлёт
#       POST .../transport/pin с телом {convoy_id, pinned: not pinned}.
#   "repair_cart" {cart_id: String}: POST .../cart/repair, тело = payload.
#   "rename_cart" {cart_id: String, name: String}: POST .../cart/rename, тело = payload; пустое имя сбрасывает имя.
#   "set_auto_repair" {cart_id: String, mode: null | "always" | "economy"}: POST .../cart/auto_repair, тело = payload.
#   "purchase_cart" {}: POST .../cart/purchase, тело {"grade": 1}.
#   "purchase_horse" {slot_index: int}: POST .../horse/purchase, тело = payload.
#   "purchase_upgrade" {upgrade_id: String}: POST .../stall-upgrade/purchase, тело = payload.
#   "start_upgrade" {}: POST .../upgrade/start (улучшение здания на вкладке УЛУЧШЕНИЯ → КОНЮШНЯ).
signal action_requested(action: String, payload: Dictionary)

# set_state(state) принимает поле "building" ответа GET /api/buildings/stable/{id} (api.py) или тот же объект из ответа POST.
# Читаются: level, server_time, stall_capacity, stall_capacity_bonus, occupied_stalls, feed_consumption_kg_per_hour,
#   feed_resource_label, horse_price_next_silver, treasury_silver_available, treasury_copper, warehouse_storage.wood,
#   stall_slots (slot_index, unlocked, unlock_level, horse), available_carts, available_cart_drivers, transport_convoys,
#   stall_upgrades (словарь), upgrade (улучшение здания, null на максимуме), cart_progress.grades["1"]
#   (upgrades, production_orders, body_finish_at).
# set_routes(routes, city_resource_storage): routes — terrain.roads.routes из GET /api/map/terrain;
#   city_resource_storage — city_resource_storage из GET /api/castle/{id}/population: в рейс предлагаются только ресурсы города.

const WINDOW_TITLE := "Конюшня"
# Размеры в единицах Godot: Python px × 2/3 (база 1280×720); шрифты 20 → 13, 16 → 11 (минимум 11).
const WINDOW_SIZE := Vector2(1066, 600)
const BORDER_COLOR := Color8(191, 155, 91)
const BACKGROUND_COLOR := Color8(25, 27, 25)
const REFRESH_SECONDS := 5.0
const BODY_MIN_HEIGHT := 400.0
const ROUTE_LIST_WIDTH := 333.0
const UPGRADE_LIST_WIDTH := 227.0
const SCROLL_BAR_WIDTH := 7.0
const CART_METERS_PER_TILE := 20.0
const QUEUE_LIMIT := 5
const CART_NAME_LIMIT := 24
# Цена и срок лёгкой повозки не приходят в состоянии сервера (core/cart_progress.py CART_GRADES), поэтому они заданы здесь.
const CART_WOOD_COST := 100
const CART_SILVER_COST := 10
const CART_ORDER_TEXT := "ИЗГОТОВИТЬ · %d дерева · %d серебра · 40 мин"
# Запасная цена лошади из stable_window.py; сервер присылает horse_price_next_silver, и он в приоритете.
const HORSE_PRICE_FALLBACK_SILVER := 50
const SELL_UNAVAILABLE_TEXT := "Продажа лошадей недоступна: сервер конюшни не принимает такое действие."
const TRIP_WIDTHS := [0.0, 110.0, 190.0, 120.0, 84.0, 80.0]
const STALL_WIDTHS := [40.0, 0.0, 170.0, 110.0, 200.0]
const TABS := [
	["transport", "ТРАНСПОРТ"],
	["routes", "МАРШРУТЫ"],
	["carts", "ПОВОЗКИ"],
	["stalls", "СТОЙЛО"],
	["upgrades", "УЛУЧШЕНИЯ"],
]
const UPGRADE_TABS := [
	["transport", "ТРАНСПОРТ"],
	["stalls", "СТОЙЛО"],
	["building", "КОНЮШНЯ"],
]
# Узлы улучшения повозки из core/cart_progress.py: [id, название, эффект, ресурсы].
const CART_UPGRADE_NODES := [
	["wheels", "Укреплённые колёса", "−2 сек на тайл за уровень", ["wood", "iron_ingot"]],
	["sides", "Вместительные борта", "+50 кг грузоподъёмности за уровень", ["board", "flax"]],
	["axles", "Кованые оси", "−10 п.п. штрафа за уровень", ["steel", "leather"]],
]
const CART_RESOURCE_LABELS := {
	"wood": "Древесина", "iron_ingot": "Железо", "board": "Доска", "flax": "Лён", "steel": "Сталь", "leather": "Кожа",
}
const BUILDING_UPGRADE_ENTRIES := [
	["Уровень здания", "Стоимость: материалы   Эффект: уровень"],
	["Вместимость стойл", "Стоимость: материалы   Эффект: +2 места/уровень"],
	["Разгрузочные рампы", "Стоимость: —   Эффект: —"],
]
const STAGE_DEFAULT_LABELS := ["Следует туда", "Погрузка", "Следует в город", "Разгрузка"]
const STAGE_STYLES := {
	"complete": [Color8(47, 49, 47), Color8(143, 148, 143)],
	"current": [Color8(42, 77, 48), Color8(139, 224, 145)],
	"future": [Color8(38, 52, 71), Color8(139, 190, 231)],
	"total": [Color8(48, 46, 40), Color8(214, 195, 157)],
}
const WEAR_COLORS := {
	"broken": Color8(22, 22, 22), "full": Color8(226, 86, 77), "medium": Color8(235, 190, 77), "good": Color8(101, 210, 125),
}

const TITLE_COLOR := Color8(222, 204, 166)
const SUBTITLE_COLOR := Color8(208, 196, 166)
const TEXT_COLOR := Color8(225, 211, 179)
const DETAIL_TITLE_COLOR := Color8(235, 220, 186)
const DETAIL_COLOR := Color8(192, 188, 171)
const NAME_COLOR := Color8(226, 218, 190)
const VALUE_COLOR := Color8(205, 199, 182)
const ROUTE_TEXT_COLOR := Color8(174, 180, 181)
const MUTED_COLOR := Color8(156, 153, 140)
const SUMMARY_TEXT_COLOR := Color8(220, 213, 192)
const DIVIDER_COLOR := Color8(98, 91, 75)
const MESSAGE_OK_COLOR := Color8(168, 214, 176)
const MESSAGE_ERROR_COLOR := Color8(232, 130, 110)
const PANEL_BG := Color8(31, 34, 30)
const PANEL_BORDER := Color8(80, 78, 64)
const TAB_BG := Color8(48, 51, 48)
const TAB_ACTIVE_BG := Color8(105, 91, 64)
const TAB_HOVER_BG := Color8(128, 108, 69)
const BUTTON_TEXT_COLOR := Color8(255, 255, 255)
const HEADER_BG := Color8(52, 53, 45)
const HEADER_TEXT_COLOR := Color8(205, 193, 164)
const ROW_BG := Color8(41, 43, 37)
const ROW_ALT_BG := Color8(35, 38, 33)
const ROW_BORDER := Color8(78, 77, 65)
const SUMMARY_BG := Color8(39, 42, 37)
const SUMMARY_BORDER := Color8(75, 77, 65)
const SELECT_ACTIVE_BG := Color8(62, 59, 46)
const SELECT_ACTIVE_BORDER := Color8(169, 143, 92)
const STATUS_OK_COLOR := Color8(163, 190, 143)
const STATUS_BUSY_COLOR := Color8(97, 165, 208)
const STATUS_WAIT_COLOR := Color8(204, 163, 92)
const STATUS_BROKEN_COLOR := Color8(223, 94, 83)
const WEAR_TRACK_BG := Color8(23, 26, 24)
const METER_BG := Color8(95, 98, 91)
const SATIETY_LOW_COLOR := Color8(226, 66, 58)
const SATIETY_MID_COLOR := Color8(232, 184, 48)
const SATIETY_OK_COLOR := Color8(72, 174, 95)
const HORSE_STATUS_COLOR := Color8(154, 187, 138)
const FREE_STALL_COLOR := Color8(148, 166, 137)
const EMPTY_STALL_COLOR := Color8(156, 153, 140)
const LOCKED_COLOR := Color8(150, 145, 130)
const STALL_FULL_COLOR := Color8(231, 112, 94)
const FEED_COLOR := Color8(201, 192, 166)
const SELL_BG := Color8(78, 62, 48)
const SELL_TEXT_COLOR := Color8(132, 120, 102)
const BUY_BG := Color8(59, 92, 53)
const BUY_OFF_BG := Color8(47, 48, 44)
const BUY_TEXT_COLOR := Color8(220, 215, 190)
const BUY_OFF_TEXT_COLOR := Color8(135, 137, 128)
const PIN_ON_BG := Color8(66, 105, 70)
const PIN_OFF_BG := Color8(49, 52, 47)
const PIN_ON_TEXT_COLOR := Color8(225, 236, 216)
const PIN_OFF_TEXT_COLOR := Color8(185, 182, 166)
const AUTO_ON_BG := Color8(62, 128, 66)
const AUTO_OFF_BG := Color8(72, 74, 68)
const REPAIR_BG := Color8(102, 69, 47)
const REPAIR_TEXT_COLOR := Color8(238, 219, 181)
const ORDER_BG := Color8(68, 132, 76)
const ORDER_OFF_BG := Color8(49, 51, 46)
const ORDER_TEXT_COLOR := Color8(223, 212, 177)
const CARD_BG := Color8(39, 42, 37)
const CARD_BORDER := Color8(75, 77, 65)
const CARD_TITLE_COLOR := Color8(224, 211, 178)
const CARD_TEXT_COLOR := Color8(175, 183, 158)
const CARD_COST_COLOR := Color8(198, 190, 168)
const INSTALLED_COLOR := Color8(142, 190, 130)
const IN_PROGRESS_COLOR := Color8(230, 194, 120)
const BUILDING_LEVEL_COLOR := Color8(255, 225, 130)
const BUILDING_PROGRESS_COLOR := Color8(120, 190, 240)
const SHORTAGE_COLOR := Color8(232, 130, 110)
const SCROLL_TRACK_BG := Color8(29, 34, 32)
const SCROLL_TRACK_BORDER := Color8(70, 78, 73)
const SCROLL_THUMB := Color8(104, 126, 110)
const SCROLL_THUMB_ACTIVE := Color8(154, 174, 157)
const CURRENCY_SCRIPT := preload("res://scripts/currency_format.gd")

var _upgrade_tab := "transport"
var _state: Dictionary = {}
var _routes: Array = []
var _city_resources: Dictionary = {}
var _selected_route := 0
var _selected_cart_node := "wheels"
var _received_msec := 0
var _refresh_elapsed := 0.0
var _clocks: Array = []

var _subtitle: Label
var _message_label: Label
var _tab_buttons: Dictionary = {}
var _tab_panels: Dictionary = {}
var _upgrade_buttons: Dictionary = {}
var _summary_labels: Array[Label] = []
var _trip_rows: VBoxContainer
var _dispatch_panel: PanelContainer
var _cart_select: OptionButton
var _route_select: OptionButton
var _driver_select: OptionButton
var _horse_box: VBoxContainer
var _horse_selects: Array[OptionButton] = []
var _resource_box: VBoxContainer
var _resource_selects: Array[OptionButton] = []
var _pin_check: CheckBox
var _route_list: VBoxContainer
var _route_detail: VBoxContainer
var _cart_rows: VBoxContainer
var _rename_select: OptionButton
var _rename_input: LineEdit
var _order_button: Button
var _production_label: Label
var _stall_summary: Label
var _feed_label: Label
var _stall_rows: VBoxContainer
var _upgrade_list: VBoxContainer
var _upgrade_details: VBoxContainer


func _init() -> void:
	add_theme_constant_override("separation", 6)
	_build_ui()


func window_title() -> String:
	return WINDOW_TITLE


func set_state(state: Dictionary) -> void:
	_state = state
	_received_msec = Time.get_ticks_msec()
	_clocks.clear()
	_subtitle.text = "Уровень %s" % _count_text(state.get("level"))
	_fill_transport()
	_fill_carts()
	_fill_stalls()
	_fill_upgrades()
	_fill_dispatch()
	_tick_clocks()


func set_routes(routes: Array, city_resource_storage: Dictionary) -> void:
	_routes = routes
	_city_resources = city_resource_storage
	_selected_route = clampi(_selected_route, 0, maxi(0, _routes.size() - 1))
	_fill_routes()
	_fill_dispatch()


func set_message(text: String, is_error: bool) -> void:
	_message_label.text = text
	_message_label.add_theme_color_override("font_color", MESSAGE_ERROR_COLOR if is_error else MESSAGE_OK_COLOR)
	_message_label.visible = not text.is_empty()


func _process(delta: float) -> void:
	if not is_visible_in_tree():
		return
	_refresh_elapsed += delta
	if _refresh_elapsed >= REFRESH_SECONDS:
		_refresh_elapsed = 0.0
		action_requested.emit("refresh", {})
	_tick_clocks()


# Как format_hms в ui/time_format.py: ЧЧ:ММ:СС, отрицательные значения считаются нулём.
static func format_hms(seconds: int) -> String:
	var total := maxi(0, seconds)
	return "%02d:%02d:%02d" % [floori(float(total) / 3600.0), floori(float(total % 3600) / 60.0), total % 60]


static func _satiety_color(satiety: int) -> Color:
	if satiety <= 10:
		return SATIETY_LOW_COLOR
	if satiety <= 30:
		return SATIETY_MID_COLOR
	return SATIETY_OK_COLOR


static func _status_color(status: String, broken: bool) -> Color:
	if broken:
		return STATUS_BROKEN_COLOR
	if status == "В пути":
		return STATUS_BUSY_COLOR
	if status == "Ожидает разгрузки":
		return STATUS_WAIT_COLOR
	return STATUS_OK_COLOR


# Как _cart_block_message в stable_window.py: почему выбранная повозка не готова к рейсу.
func _cart_block_message(cart: Dictionary) -> String:
	var status := _text_or(cart.get("status"), "Свободна")
	if status != "Свободна":
		return "Повозка сейчас: %s." % status
	if _available_horses().is_empty():
		return "Для рейса нужна свободная отдыхающая лошадь."
	if _array(_state, "available_cart_drivers").is_empty():
		return "Для рейса нужен свободный сытый участник экипажа."
	return "Выбранная повозка пока не готова к отправке."


# Как traveling в _draw_transport (stable_window.py): рейсы, которые ждут разгрузки, в счёт «В пути» не входят.
static func _is_traveling(convoy: Dictionary) -> bool:
	var status := _text_or(convoy.get("status"), "")
	var phase := _text_or(convoy.get("phase"), "")
	var stalled := status == "Ожидает разгрузки" or status == "Ожидает места для разгрузки"
	return (not stalled and phase in ["outbound", "returning"]) or status == "В пути"


static func _trip_entries(carts: Array, convoys: Array) -> Array:
	var convoy_by_cart: Dictionary = {}
	for convoy in convoys:
		if convoy is Dictionary:
			convoy_by_cart[_text_or(convoy.get("cart_id"), "")] = convoy
	var entries: Array = []
	var cart_ids: Dictionary = {}
	for cart in carts:
		if cart is Dictionary:
			var cart_id := _text_or(cart.get("id"), "")
			cart_ids[cart_id] = true
			entries.append({"cart": cart, "convoy": convoy_by_cart.get(cart_id, {})})
	for convoy in convoys:
		if convoy is Dictionary and not cart_ids.has(_text_or(convoy.get("cart_id"), "")):
			entries.append({"cart": {}, "convoy": convoy})
	return entries


static func _crew_text(cart: Dictionary, convoy: Dictionary) -> String:
	if convoy.is_empty():
		return "Экипаж — / лошадей: 0/%d" % _int_of(cart.get("horse_slots"))
	var names := PackedStringArray()
	for horse in _array(convoy, "horses"):
		if horse is Dictionary:
			names.append(_text_or(horse.get("name"), "Лошадь"))
	return "%s / %s" % [_text_or(convoy.get("driver_name"), "—"), ", ".join(names) if not names.is_empty() else "—"]


static func _cart_entries(carts: Array, with_status: bool) -> Array:
	var entries: Array = [_entry("Выберите повозку", "")]
	for cart in carts:
		if cart is Dictionary:
			var label := _text_or(cart.get("name"), "Повозка")
			if with_status:
				label = "%s · %s" % [label, _text_or(cart.get("status"), "")]
			entries.append(_entry(label, _text_or(cart.get("id"), "")))
	return entries


static func _queue_size(progress: Dictionary) -> int:
	var count := 0
	var grades := _dict(progress, "grades")
	for key in grades:
		count += _array(_dict(grades, str(key)), "production_orders").size()
	return count


static func _unlocked_count(slots: Array) -> int:
	var count := 0
	for slot in slots:
		if slot is Dictionary and bool(slot.get("unlocked", false)):
			count += 1
	return count


static func _distance_km(route: Dictionary) -> float:
	return _float_of(route.get("distance_tiles")) * CART_METERS_PER_TILE / 1000.0


static func _resource_labels(route: Dictionary) -> String:
	var labels := PackedStringArray()
	for resource in _array(route, "resources"):
		if resource is Dictionary:
			labels.append(_text_or(resource.get("label"), _text_or(resource.get("id"), "")))
	return " · ".join(labels)


static func _option_matches(option: OptionButton, entries: Array) -> bool:
	if option.item_count != entries.size():
		return false
	for index in entries.size():
		var entry: Dictionary = entries[index]
		if option.get_item_text(index) != str(entry["text"]) or option.get_item_metadata(index) != entry["value"]:
			return false
	return true


static func _selected_value(option: OptionButton) -> Variant:
	return null if option.selected < 0 else option.get_item_metadata(option.selected)


static func _selected_text(option: OptionButton) -> String:
	var value: Variant = _selected_value(option)
	return "" if value == null else str(value)


static func _selected_int(option: OptionButton) -> int:
	var value: Variant = _selected_value(option)
	return 0 if value == null else int(value)


static func _entry(text: String, value: Variant) -> Dictionary:
	return {"text": text, "value": value}


static func _find(items: Array, key: String, value: String) -> Dictionary:
	for item in items:
		if item is Dictionary and _text_or(item.get(key), "") == value:
			return item
	return {}


static func _array(source: Dictionary, key: String) -> Array:
	var value: Variant = source.get(key)
	return value if value is Array else []


static func _dict(source: Dictionary, key: String) -> Dictionary:
	var value: Variant = source.get(key)
	return value if value is Dictionary else {}


static func _count_text(value: Variant) -> String:
	return "—" if value == null else "%d" % int(value)


static func _text_or(value: Variant, fallback: String) -> String:
	var text := "" if value == null else str(value)
	return fallback if text.is_empty() else text


# JSON в Godot 4 отдаёт все числа как float; целые выводятся без «.0», как у Python.
static func _number_text(value: Variant, fallback: String) -> String:
	if value == null:
		return fallback
	var number := float(value)
	return "%d" % int(number) if is_equal_approx(number, roundf(number)) else str(number)


static func _int_of(value: Variant) -> int:
	return 0 if value == null else int(value)


static func _float_of(value: Variant) -> float:
	return 0.0 if value == null else float(value)


func _available_horses() -> Array:
	var horses: Array = []
	for slot in _array(_state, "stall_slots"):
		if slot is Dictionary and bool(slot.get("unlocked", false)) and slot.get("horse") is Dictionary:
			var horse: Dictionary = slot["horse"]
			if bool(horse.get("can_travel", false)):
				horses.append(horse)
	return horses


func _horse_price() -> int:
	var price: Variant = _state.get("horse_price_next_silver")
	return HORSE_PRICE_FALLBACK_SILVER if price == null else int(price)


func _route_at(index: int) -> Dictionary:
	var item: Variant = _routes[index]
	return item if item is Dictionary else {}


func _clock(label: Label, seconds: int, prefix := "") -> void:
	label.text = prefix + format_hms(seconds)
	_clocks.append({"label": label, "seconds": seconds, "prefix": prefix})


# Таймеры идут между ответами сервера; «осталось» округляется вверх, как ceil() на сервере.
func _tick_clocks() -> void:
	var elapsed := (Time.get_ticks_msec() - _received_msec) / 1000.0
	var live: Array = []
	for clock in _clocks:
		var label: Variant = clock["label"]
		if not is_instance_valid(label):
			continue
		live.append(clock)
		(label as Label).text = str(clock["prefix"]) + format_hms(ceili(maxf(0.0, float(clock["seconds"]) - elapsed)))
	_clocks = live


func _build_ui() -> void:
	_subtitle = _text("Уровень —", SUBTITLE_COLOR, 13)
	add_child(_subtitle)
	var tab_row := HBoxContainer.new()
	tab_row.add_theme_constant_override("separation", 5)
	add_child(tab_row)
	var group := ButtonGroup.new()
	for entry in TABS:
		var key := str(entry[0])
		var button := _tab_button(str(entry[1]), group)
		button.pressed.connect(_select_tab.bind(key))
		tab_row.add_child(button)
		_tab_buttons[key] = button
	add_child(_divider(DIVIDER_COLOR))
	var body := Control.new()
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body.custom_minimum_size = Vector2(0.0, BODY_MIN_HEIGHT)
	add_child(body)
	_add_tab("transport", body, _build_transport())
	_add_tab("routes", body, _build_routes())
	_add_tab("carts", body, _build_carts())
	_add_tab("stalls", body, _build_stalls())
	_add_tab("upgrades", body, _build_upgrades())
	_message_label = _text("", MESSAGE_OK_COLOR, 11)
	_message_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_message_label.visible = false
	add_child(_message_label)
	_select_tab("transport")


func _add_tab(key: String, body: Control, content: Control) -> void:
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_style_scroll(scroll)
	scroll.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	scroll.visible = false
	body.add_child(scroll)
	scroll.add_child(content)
	_tab_panels[key] = scroll


func _select_tab(key: String) -> void:
	(_tab_buttons[key] as Button).button_pressed = true
	for panel_key in _tab_panels:
		(_tab_panels[panel_key] as ScrollContainer).visible = panel_key == key
	(_tab_panels[key] as ScrollContainer).scroll_vertical = 0


func _build_transport() -> Control:
	var page := VBoxContainer.new()
	page.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	page.add_theme_constant_override("separation", 8)
	var trips := _content(_panel("Транспортные рейсы", page))
	var summary := HBoxContainer.new()
	summary.add_theme_constant_override("separation", 6)
	trips.add_child(summary)
	for index in 3:
		var cell := PanelContainer.new()
		cell.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		cell.custom_minimum_size = Vector2(0.0, 25.0)
		cell.add_theme_stylebox_override("panel", _box(SUMMARY_BG, SUMMARY_BORDER, 1, 4, 4))
		var label := _text("", SUMMARY_TEXT_COLOR, 13)
		label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		cell.add_child(label)
		summary.add_child(cell)
		_summary_labels.append(label)
	var table := PanelContainer.new()
	table.add_theme_stylebox_override("panel", _box(ROW_BG, ROW_BORDER, 1, 4, 0))
	trips.add_child(table)
	var table_box := VBoxContainer.new()
	table_box.add_theme_constant_override("separation", 0)
	table.add_child(table_box)
	table_box.add_child(_header(["Повозка / маршрут", "Груз", "Лошади", "Статус", "Повтор", "Осталось"], TRIP_WIDTHS, 5))
	_trip_rows = VBoxContainer.new()
	_trip_rows.add_theme_constant_override("separation", 2)
	table_box.add_child(_trip_rows)
	var toggle := _button("Собрать экипаж", TAB_BG, BUTTON_TEXT_COLOR, 160.0)
	toggle.pressed.connect(_toggle_dispatch)
	trips.add_child(toggle)

	_dispatch_panel = _panel("", page)
	_dispatch_panel.visible = false
	var form := _content(_dispatch_panel)
	_cart_select = _option()
	_cart_select.item_selected.connect(_on_dispatch_option_changed)
	form.add_child(_form_row("Повозка", _cart_select))
	_route_select = _option()
	_route_select.item_selected.connect(_on_dispatch_option_changed)
	form.add_child(_form_row("Пункт назначения", _route_select))
	_driver_select = _option()
	form.add_child(_form_row("Кучер", _driver_select))
	_horse_box = VBoxContainer.new()
	_horse_box.add_theme_constant_override("separation", 4)
	form.add_child(_horse_box)
	_resource_box = VBoxContainer.new()
	_resource_box.add_theme_constant_override("separation", 4)
	form.add_child(_resource_box)
	_pin_check = CheckBox.new()
	_pin_check.text = "Повторять маршрут до отмены"
	_pin_check.add_theme_font_size_override("font_size", 11)
	form.add_child(_pin_check)
	var send := _button("ОТПРАВИТЬ В РЕЙС", ORDER_BG, ORDER_TEXT_COLOR, 180.0)
	send.pressed.connect(_on_dispatch_pressed)
	form.add_child(send)
	return page


func _build_routes() -> Control:
	var page := HBoxContainer.new()
	page.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	page.add_theme_constant_override("separation", 12)
	var left := _panel("Загородные объекты", page)
	left.custom_minimum_size.x = ROUTE_LIST_WIDTH
	var list_scroll := ScrollContainer.new()
	list_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_style_scroll(list_scroll)
	list_scroll.custom_minimum_size = Vector2(0.0, 300.0)
	_content(left).add_child(list_scroll)
	_route_list = VBoxContainer.new()
	_route_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_route_list.add_theme_constant_override("separation", 5)
	list_scroll.add_child(_route_list)
	var right := _panel("Настройка рейса", page)
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_route_detail = VBoxContainer.new()
	_route_detail.add_theme_constant_override("separation", 6)
	_content(right).add_child(_route_detail)
	return page


func _build_carts() -> Control:
	var page := VBoxContainer.new()
	page.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	page.add_theme_constant_override("separation", 8)
	var box := _content(_panel("Состояние повозок", page))
	_cart_rows = VBoxContainer.new()
	_cart_rows.add_theme_constant_override("separation", 4)
	box.add_child(_cart_rows)
	var rename := HBoxContainer.new()
	rename.add_theme_constant_override("separation", 6)
	box.add_child(rename)
	_rename_select = _option()
	_rename_select.custom_minimum_size.x = 200.0
	rename.add_child(_rename_select)
	_rename_input = LineEdit.new()
	_rename_input.placeholder_text = "Новое имя повозки"
	_rename_input.max_length = CART_NAME_LIMIT
	_rename_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_rename_input.add_theme_font_size_override("font_size", 11)
	rename.add_child(_rename_input)
	var rename_button := _button("ПЕРЕИМЕНОВАТЬ", TAB_BG, BUTTON_TEXT_COLOR, 140.0)
	rename_button.pressed.connect(_on_rename_pressed)
	rename.add_child(rename_button)
	_order_button = _button(CART_ORDER_TEXT % [CART_WOOD_COST, CART_SILVER_COST], ORDER_BG, ORDER_TEXT_COLOR, 0.0)
	_order_button.pressed.connect(_on_order_pressed)
	box.add_child(_order_button)
	_production_label = _text("", CARD_TEXT_COLOR, 11)
	box.add_child(_production_label)
	return page


func _build_stalls() -> Control:
	var page := VBoxContainer.new()
	page.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	page.add_theme_constant_override("separation", 8)
	var box := _content(_panel("Стойла", page))
	_stall_summary = _text("", TEXT_COLOR, 13)
	box.add_child(_stall_summary)
	_feed_label = _text("", FEED_COLOR, 11)
	box.add_child(_feed_label)
	box.add_child(_header(["№", "Лошадь / кличка / порода", "Сытность", "Статус", "Действие"], STALL_WIDTHS, 4))
	_stall_rows = VBoxContainer.new()
	_stall_rows.add_theme_constant_override("separation", 2)
	box.add_child(_stall_rows)
	return page


func _build_upgrades() -> Control:
	var page := VBoxContainer.new()
	page.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	page.add_theme_constant_override("separation", 8)
	var subtabs := HBoxContainer.new()
	subtabs.add_theme_constant_override("separation", 5)
	page.add_child(subtabs)
	var group := ButtonGroup.new()
	for entry in UPGRADE_TABS:
		var key := str(entry[0])
		var button := _tab_button(str(entry[1]), group)
		button.pressed.connect(_select_upgrade_tab.bind(key))
		subtabs.add_child(button)
		_upgrade_buttons[key] = button
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	page.add_child(row)
	var left := _panel("Развитие конюшни", row)
	left.custom_minimum_size.x = UPGRADE_LIST_WIDTH
	_upgrade_list = VBoxContainer.new()
	_upgrade_list.add_theme_constant_override("separation", 5)
	_content(left).add_child(_upgrade_list)
	var right := _panel("Параметры улучшений", row)
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_upgrade_details = VBoxContainer.new()
	_upgrade_details.add_theme_constant_override("separation", 8)
	_content(right).add_child(_upgrade_details)
	return page


func _fill_transport() -> void:
	var carts := _array(_state, "available_carts")
	var convoys := _array(_state, "transport_convoys")
	var ready := 0
	for cart in carts:
		if cart is Dictionary and bool(cart.get("can_travel", false)):
			ready += 1
	var traveling := 0
	for convoy in convoys:
		if convoy is Dictionary and _is_traveling(convoy):
			traveling += 1
	_summary_labels[0].text = "Повозок в городе: %d" % carts.size()
	_summary_labels[1].text = "Готово к рейсу: %d" % ready
	_summary_labels[2].text = "В пути: %d" % traveling
	_clear(_trip_rows)
	var entries := _trip_entries(carts, convoys)
	if entries.is_empty():
		_trip_rows.add_child(_centered_text("Пока нет купленных повозок"))
	for index in entries.size():
		var entry: Dictionary = entries[index]
		_trip_rows.add_child(_trip_row(entry["cart"], entry["convoy"], index))


func _trip_row(cart: Dictionary, convoy: Dictionary, index: int) -> PanelContainer:
	var has_convoy := not convoy.is_empty()
	var background := ROW_BG if index % 2 == 0 else ROW_ALT_BG
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", _box(background, background, 0, 0, 6))
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 3)
	panel.add_child(box)
	var line := HBoxContainer.new()
	line.add_theme_constant_override("separation", 8)
	box.add_child(line)

	var title_box := VBoxContainer.new()
	title_box.add_theme_constant_override("separation", 0)
	var cart_name: Variant = cart.get("name", convoy.get("cart_name"))
	title_box.add_child(_text(_text_or(cart_name, "Повозка"), NAME_COLOR, 11))
	title_box.add_child(_text("Маршрут: %s" % _text_or(convoy.get("destination_name"), "не выбран"), ROUTE_TEXT_COLOR, 11))
	line.add_child(_column(title_box, 0.0))

	var capacity: Variant = cart.get("capacity_kg") if not cart.is_empty() else convoy.get("capacity_kg")
	line.add_child(_cell("%s / %s кг" % [_number_text(convoy.get("cargo_kg"), "0"), _number_text(capacity, "—")], TRIP_WIDTHS[1], VALUE_COLOR))
	line.add_child(_cell(_crew_text(cart, convoy), TRIP_WIDTHS[2], VALUE_COLOR))
	var status := _text_or(convoy.get("status"), "В пути") if has_convoy else _text_or(cart.get("status"), "Свободна")
	line.add_child(_cell(status, TRIP_WIDTHS[3], VALUE_COLOR))
	if has_convoy:
		var pinned := bool(convoy.get("pinned", false))
		var pin := _button("Закреплён" if pinned else "Закрепить", PIN_ON_BG if pinned else PIN_OFF_BG,
			PIN_ON_TEXT_COLOR if pinned else PIN_OFF_TEXT_COLOR, TRIP_WIDTHS[4])
		pin.pressed.connect(_on_pin_pressed.bind(_int_of(convoy.get("id")), pinned))
		line.add_child(pin)
	else:
		line.add_child(_cell("", TRIP_WIDTHS[4], VALUE_COLOR))
	var seconds: Variant = convoy.get("cycle_seconds_remaining")
	if seconds == null:
		seconds = convoy.get("seconds_remaining")
	var time_label := _cell("—" if seconds == null else format_hms(int(seconds)), TRIP_WIDTHS[5], VALUE_COLOR)
	time_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	if seconds != null:
		_clock(time_label, int(seconds))
	line.add_child(time_label)
	box.add_child(_timeline(_array(convoy, "route_stages"), convoy.get("cycle_seconds_remaining")))
	return panel


# Пять ячеек как в _draw_transport: четыре этапа рейса и итог «До завершения».
func _timeline(stages: Array, total_seconds: Variant) -> HBoxContainer:
	var strip := HBoxContainer.new()
	strip.add_theme_constant_override("separation", 3)
	for index in 5:
		var stage: Dictionary = {}
		if index < stages.size() and stages[index] is Dictionary:
			stage = stages[index]
		var is_total := index == 4
		var colors: Array = STAGE_STYLES["total"] if is_total else STAGE_STYLES.get(_text_or(stage.get("state"), "future"), STAGE_STYLES["future"])
		var background: Color = colors[0]
		var foreground: Color = colors[1]
		var cell := PanelContainer.new()
		cell.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		cell.add_theme_stylebox_override("panel", _box(background, background.lightened(0.2), 1, 3, 2))
		var box := VBoxContainer.new()
		box.add_theme_constant_override("separation", 0)
		cell.add_child(box)
		var title := _text("До завершения" if is_total else _text_or(stage.get("label"), STAGE_DEFAULT_LABELS[index]), foreground, 11)
		title.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		box.add_child(title)
		var seconds: Variant = total_seconds if is_total else stage.get("seconds")
		var clock := _text("—", foreground, 11)
		box.add_child(clock)
		if seconds != null:
			_clock(clock, int(seconds))
		strip.add_child(cell)
	return strip


func _fill_dispatch() -> void:
	var carts := _array(_state, "available_carts")
	_fill_option(_cart_select, _cart_entries(carts, true))
	var route_entries: Array = [_entry("Выберите пункт назначения", "")]
	for index in _routes.size():
		var route := _route_at(index)
		if not route.is_empty():
			route_entries.append(_entry(_text_or(route.get("name"), "Маршрут"), _text_or(route.get("building_id"), "")))
	_fill_option(_route_select, route_entries)
	var driver_entries: Array = [_entry("Выберите кучера", 0)]
	for driver in _array(_state, "available_cart_drivers"):
		if driver is Dictionary:
			driver_entries.append(_entry("%s · сытость %d%%" % [_text_or(driver.get("name"), "Горожанин"), _int_of(driver.get("satiety"))],
				_int_of(driver.get("id"))))
	_fill_option(_driver_select, driver_entries)
	var cart := _find(carts, "id", _selected_text(_cart_select))
	_sync_slots(_horse_box, _horse_selects, _int_of(cart.get("horse_slots")), "Лошадь")
	_sync_slots(_resource_box, _resource_selects, _int_of(cart.get("resource_slots")), "Груз")
	var horse_entries: Array = [_entry("Выберите лошадь", 0)]
	for horse in _available_horses():
		horse_entries.append(_entry("%s · %s" % [_text_or(horse.get("name"), "Лошадь"), _text_or(horse.get("breed"), "")], _int_of(horse.get("id"))))
	for select in _horse_selects:
		_fill_option(select, horse_entries)
	var resource_entries := _resource_entries(_selected_text(_route_select))
	for select in _resource_selects:
		_fill_option(select, resource_entries)


func _resource_entries(route_id: String) -> Array:
	var entries: Array = [_entry("Выберите груз", "")]
	for resource in _array(_find(_routes, "building_id", route_id), "resources"):
		if resource is Dictionary:
			var resource_id := _text_or(resource.get("id"), "")
			if _city_resources.has(resource_id):
				entries.append(_entry(_text_or(resource.get("label"), resource_id), resource_id))
	return entries


# Список пересобирается только при изменении: выбор пользователя сохраняется между обновлениями состояния.
func _fill_option(option: OptionButton, entries: Array) -> void:
	if _option_matches(option, entries):
		return
	var previous: Variant = _selected_value(option)
	option.clear()
	var selected := 0
	for index in entries.size():
		var entry: Dictionary = entries[index]
		option.add_item(str(entry["text"]))
		option.set_item_metadata(index, entry["value"])
		if entry["value"] == previous:
			selected = index
	if not entries.is_empty():
		option.select(selected)


func _sync_slots(box: VBoxContainer, selects: Array[OptionButton], count: int, caption: String) -> void:
	if selects.size() == count:
		return
	_clear(box)
	selects.clear()
	for index in count:
		var option := _option()
		box.add_child(_form_row("%s %d" % [caption, index + 1], option))
		selects.append(option)


func _on_dispatch_option_changed(_index: int) -> void:
	_fill_dispatch()


func _toggle_dispatch() -> void:
	_dispatch_panel.visible = not _dispatch_panel.visible


# Проверки и тексты как в _transport_block_reasons (stable_window.py).
func _on_dispatch_pressed() -> void:
	if _routes.is_empty():
		set_message("Нет доступных серверных маршрутов.", true)
		return
	var cart_id := _selected_text(_cart_select)
	var cart := _find(_array(_state, "available_carts"), "id", cart_id)
	if cart.is_empty():
		set_message("Выберите повозку.", true)
		return
	if not bool(cart.get("dispatch_available", false)):
		set_message(_cart_block_message(cart), true)
		return
	var driver_id := _selected_int(_driver_select)
	if driver_id <= 0:
		set_message("Выберите свободного горожанина-кучера.", true)
		return
	var route_id := _selected_text(_route_select)
	if route_id.is_empty():
		set_message("Выберите пункт назначения.", true)
		return
	var horse_ids: Array[int] = []
	for index in _horse_selects.size():
		var horse_id := _selected_int(_horse_selects[index])
		if horse_id <= 0:
			set_message("Выберите свободную отдыхающую лошадь %d." % (index + 1), true)
			return
		if horse_ids.has(horse_id):
			set_message("Выберите разных лошадей для повозки.", true)
			return
		horse_ids.append(horse_id)
	var resource_ids: Array[String] = []
	for index in _resource_selects.size():
		var option := _resource_selects[index]
		if option.item_count <= 1:
			set_message("Для этой повозки нет полного набора доступных грузовых ресурсов.", true)
			return
		var resource_id := _selected_text(option)
		if resource_id.is_empty():
			set_message("Выберите груз для слота %d." % (index + 1), true)
			return
		resource_ids.append(resource_id)
	set_message("", false)
	action_requested.emit("dispatch", {
		"cart_id": cart_id,
		"horse_ids": horse_ids,
		"driver_citizen_id": driver_id,
		"destination_building_id": route_id,
		"resource_ids": resource_ids,
		"pinned": _pin_check.button_pressed,
	})


func _on_pin_pressed(convoy_id: int, pinned: bool) -> void:
	action_requested.emit("toggle_convoy_pin", {"convoy_id": convoy_id, "pinned": pinned})


func _fill_routes() -> void:
	_clear(_route_list)
	_clear(_route_detail)
	if _routes.is_empty():
		_route_list.add_child(_centered_text("Нет данных о загородных маршрутах"))
		return
	for index in _routes.size():
		var route := _route_at(index)
		var title := "%s · %.2f км" % [_text_or(route.get("name"), "Маршрут"), _distance_km(route)]
		_route_list.add_child(_select_card(title, _resource_labels(route), index == _selected_route, _select_route.bind(index)))
	var selected := _route_at(_selected_route)
	_route_detail.add_child(_text(_text_or(selected.get("name"), "Маршрут"), DETAIL_TITLE_COLOR, 13))
	_route_detail.add_child(_text("Расстояние: %.2f км" % _distance_km(selected), DETAIL_COLOR, 11))
	_route_detail.add_child(_header(["Ресурс"], [0.0], -1))
	var resources := VBoxContainer.new()
	resources.add_theme_constant_override("separation", 3)
	for resource in _array(selected, "resources"):
		if resource is Dictionary:
			resources.add_child(_text(_text_or(resource.get("label"), _text_or(resource.get("id"), "")), VALUE_COLOR, 11))
	_route_detail.add_child(resources)


func _select_route(index: int) -> void:
	_selected_route = index
	_fill_routes()


func _fill_carts() -> void:
	var carts := _array(_state, "available_carts")
	_clear(_cart_rows)
	if carts.is_empty():
		_cart_rows.add_child(_text("Пока нет изготовленных повозок.", MUTED_COLOR, 11))
	for index in carts.size():
		var cart: Variant = carts[index]
		if cart is Dictionary:
			_cart_rows.add_child(_cart_row(cart, index))
	_fill_option(_rename_select, _cart_entries(carts, false))
	var progress := _dict(_state, "cart_progress")
	var grade := _dict(_dict(progress, "grades"), "1")
	_production_label.text = ""
	var orders := _array(grade, "production_orders")
	var finish: Variant = grade.get("body_finish_at")
	if not orders.is_empty() and finish != null:
		var seconds_left := maxi(0, int(float(finish) - _float_of(_state.get("server_time"))))
		_production_label.text = "Лёгкая повозка изготавливается: %d мин." % floori(float(seconds_left) / 60.0)
	var wood := _int_of(_dict(_state, "warehouse_storage").get("wood"))
	var silver := _int_of(_state.get("treasury_silver_available"))
	var can_order := _queue_size(progress) < QUEUE_LIMIT and wood >= CART_WOOD_COST and silver >= CART_SILVER_COST
	_paint_button(_order_button, ORDER_BG if can_order else ORDER_OFF_BG, ORDER_TEXT_COLOR)
	_order_button.disabled = not can_order


func _cart_row(cart: Dictionary, index: int) -> PanelContainer:
	var cart_id := _text_or(cart.get("id"), "")
	var maximum := maxf(1.0, _float_of(cart.get("max_durability", 100.0)))
	var durability := clampf(_float_of(cart.get("durability", maximum)), 0.0, maximum)
	var status := _text_or(cart.get("status"), "Свободна")
	var background := ROW_BG if index % 2 == 0 else ROW_ALT_BG
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", _box(background, background, 0, 4, 6))
	var line := HBoxContainer.new()
	line.add_theme_constant_override("separation", 12)
	panel.add_child(line)

	var name_box := VBoxContainer.new()
	name_box.add_theme_constant_override("separation", 1)
	name_box.add_child(_text(_text_or(cart.get("name"), "Повозка"), TEXT_COLOR, 13))
	name_box.add_child(_text(status, _status_color(status, bool(cart.get("broken", false))), 11))
	line.add_child(_column(name_box, 170.0))

	var wear_box := VBoxContainer.new()
	wear_box.add_theme_constant_override("separation", 2)
	wear_box.add_child(_text("Износ", VALUE_COLOR, 11))
	var wear := ProgressBar.new()
	wear.min_value = 0.0
	wear.max_value = maximum
	wear.value = durability
	wear.show_percentage = false
	wear.custom_minimum_size = Vector2(150.0, 6.0)
	var wear_color: Color = WEAR_COLORS.get(_text_or(cart.get("wear_band"), "good"), WEAR_COLORS["good"])
	wear.add_theme_stylebox_override("fill", _box(wear_color, wear_color, 0, 2, 0))
	wear.add_theme_stylebox_override("background", _box(WEAR_TRACK_BG, CARD_BORDER, 0, 2, 0))
	wear_box.add_child(wear)
	line.add_child(wear_box)

	var auto_repair := _text_or(cart.get("auto_repair"), "")
	line.add_child(_auto_repair_button(cart_id, "always", "Всегда хорошо", auto_repair == "always"))
	line.add_child(_auto_repair_button(cart_id, "economy", "Экономный ремонт", auto_repair == "economy"))
	if durability < maximum:
		var repair := _button("РЕМОНТ · %d древесины" % _int_of(cart.get("repair_wood_cost")), REPAIR_BG, REPAIR_TEXT_COLOR, 0.0)
		repair.pressed.connect(_on_repair_pressed.bind(cart_id))
		line.add_child(repair)
	return panel


func _auto_repair_button(cart_id: String, mode: String, label: String, active: bool) -> Button:
	var button := _button(label, AUTO_ON_BG if active else AUTO_OFF_BG, BUTTON_TEXT_COLOR, 110.0)
	button.pressed.connect(_on_auto_repair_pressed.bind(cart_id, mode, active))
	return button


# Как в _draw_carts: повторное нажатие на активный режим его выключает (mode = null).
func _on_auto_repair_pressed(cart_id: String, mode: String, active: bool) -> void:
	var next_mode: Variant = null if active else mode
	action_requested.emit("set_auto_repair", {"cart_id": cart_id, "mode": next_mode})


func _on_repair_pressed(cart_id: String) -> void:
	action_requested.emit("repair_cart", {"cart_id": cart_id})


func _on_rename_pressed() -> void:
	var cart_id := _selected_text(_rename_select)
	if cart_id.is_empty():
		set_message("Выберите повозку.", true)
		return
	action_requested.emit("rename_cart", {"cart_id": cart_id, "name": _rename_input.text.strip_edges()})


func _on_order_pressed() -> void:
	action_requested.emit("purchase_cart", {})


func _fill_stalls() -> void:
	var slots := _array(_state, "stall_slots")
	var occupied := _int_of(_state.get("occupied_stalls"))
	var capacity_value: Variant = _state.get("stall_capacity")
	var capacity := _unlocked_count(slots) if capacity_value == null else int(capacity_value)
	_stall_summary.text = "Стойла: занято %d / %d мест" % [occupied, capacity]
	_stall_summary.add_theme_color_override("font_color", STALL_FULL_COLOR if occupied >= capacity else TEXT_COLOR)
	_feed_label.text = "Расход корма: -%s кг %s / час" % [
		_number_text(_state.get("feed_consumption_kg_per_hour"), "0"),
		_text_or(_state.get("feed_resource_label"), "Пшеница"),
	]
	_clear(_stall_rows)
	var price := _horse_price()
	var can_afford := _int_of(_state.get("treasury_silver_available")) >= price
	for slot in slots:
		if slot is Dictionary:
			_stall_rows.add_child(_stall_row(slot, price, can_afford))


func _stall_row(slot: Dictionary, price: int, can_afford: bool) -> PanelContainer:
	var slot_index := _int_of(slot.get("slot_index"))
	var background := ROW_BG if slot_index % 2 == 0 else ROW_ALT_BG
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", _box(background, background, 0, 0, 6))
	var line := HBoxContainer.new()
	line.add_theme_constant_override("separation", 8)
	panel.add_child(line)
	line.add_child(_cell("%02d" % (slot_index + 1), STALL_WIDTHS[0], VALUE_COLOR))
	if not bool(slot.get("unlocked", false)):
		line.add_child(_cell("Доступно на %s уровне Конюшни" % _number_text(slot.get("unlock_level"), "—"), STALL_WIDTHS[1], LOCKED_COLOR))
		return panel
	var horse_value: Variant = slot.get("horse")
	if horse_value is Dictionary:
		var horse: Dictionary = horse_value
		line.add_child(_cell("%s / %s" % [_text_or(horse.get("name"), "Без клички"), _text_or(horse.get("breed"), "Порода не указана")],
			STALL_WIDTHS[1], NAME_COLOR))
		line.add_child(_satiety_cell(_int_of(horse.get("satiety"))))
		line.add_child(_cell(_text_or(horse.get("status"), ""), STALL_WIDTHS[3], HORSE_STATUS_COLOR))
		var sell := _button("ПРОДАТЬ ЛОШАДЬ", SELL_BG, SELL_TEXT_COLOR, STALL_WIDTHS[4])
		sell.disabled = true
		sell.tooltip_text = SELL_UNAVAILABLE_TEXT
		line.add_child(sell)
		return panel
	line.add_child(_cell("Пустое стойло", STALL_WIDTHS[1], EMPTY_STALL_COLOR))
	line.add_child(_spacer(STALL_WIDTHS[2]))
	line.add_child(_cell("Свободно", STALL_WIDTHS[3], FREE_STALL_COLOR))
	line.add_child(_buy_cell(slot_index, price, can_afford))
	return panel


func _satiety_cell(satiety: int) -> VBoxContainer:
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 2)
	box.custom_minimum_size.x = STALL_WIDTHS[2]
	var color := _satiety_color(satiety)
	box.add_child(_text("Сытность %d%%" % satiety, color, 11))
	var meter := ProgressBar.new()
	meter.min_value = 0.0
	meter.max_value = 100.0
	meter.value = clampf(float(satiety), 0.0, 100.0)
	meter.show_percentage = false
	meter.custom_minimum_size = Vector2(0.0, 5.0)
	meter.add_theme_stylebox_override("background", _box(METER_BG, METER_BG, 0, 2, 0))
	meter.add_theme_stylebox_override("fill", _box(color, color, 0, 2, 0))
	box.add_child(meter)
	return box


func _buy_cell(slot_index: int, price: int, can_afford: bool) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	row.custom_minimum_size.x = STALL_WIDTHS[4]
	var buy := _button("КУПИТЬ", BUY_BG if can_afford else BUY_OFF_BG, BUY_TEXT_COLOR if can_afford else BUY_OFF_TEXT_COLOR, 82.0)
	buy.disabled = not can_afford
	buy.pressed.connect(_on_purchase_horse.bind(slot_index))
	row.add_child(buy)
	var price_text := CURRENCY_SCRIPT.format_amount(price * CURRENCY_SCRIPT.COPPER_PER_SILVER)
	row.add_child(_text(price_text, BUY_TEXT_COLOR if can_afford else BUY_OFF_TEXT_COLOR, 11))
	return row


func _on_purchase_horse(slot_index: int) -> void:
	action_requested.emit("purchase_horse", {"slot_index": slot_index})


func _fill_upgrades() -> void:
	for key in _upgrade_buttons:
		(_upgrade_buttons[key] as Button).button_pressed = key == _upgrade_tab
	_clear(_upgrade_list)
	_clear(_upgrade_details)
	var upgrades := _dict(_state, "stall_upgrades")
	if _upgrade_tab == "building":
		for entry in BUILDING_UPGRADE_ENTRIES:
			_upgrade_list.add_child(_entry_row(str(entry[0]), str(entry[1])))
		_fill_building_upgrade()
	elif _upgrade_tab == "stalls":
		for upgrade_id in upgrades:
			var upgrade_value: Variant = upgrades[upgrade_id]
			if upgrade_value is Dictionary:
				var upgrade: Dictionary = upgrade_value
				var price := CURRENCY_SCRIPT.format_amount(_int_of(upgrade.get("silver_cost")) * CURRENCY_SCRIPT.COPPER_PER_SILVER)
				_upgrade_list.add_child(_entry_row(_text_or(upgrade.get("name"), str(upgrade_id)),
					"Древесина: %d   Цена: %s   +%d место" % [_int_of(upgrade.get("wood_cost")), price, _int_of(upgrade.get("horse_capacity"))]))
		_fill_stall_upgrades(upgrades)
	else:
		for node in CART_UPGRADE_NODES:
			_upgrade_list.add_child(_entry_row(str(node[1]), "Эффект: %s" % str(node[2])))
		_fill_cart_upgrades()


func _fill_building_upgrade() -> void:
	_upgrade_details.add_child(_text("Вместимость сейчас: %d стойла" % _int_of(_state.get("stall_capacity")), TEXT_COLOR, 13))
	var upgrade_value: Variant = _state.get("upgrade")
	if not upgrade_value is Dictionary:
		_upgrade_details.add_child(_text("Максимальный уровень здания", MUTED_COLOR, 13))
		return
	var upgrade: Dictionary = upgrade_value
	_upgrade_details.add_child(_text("Улучшение до уровня %d" % _int_of(upgrade.get("next_level")), BUILDING_LEVEL_COLOR, 13))
	_upgrade_details.add_child(_text("Оплата списывается из общего склада при покупке", CARD_TEXT_COLOR, 11))
	for material in _array(upgrade, "materials"):
		if material is Dictionary:
			_upgrade_details.add_child(_material_row(material))
	if bool(upgrade.get("in_progress", false)):
		var clock := _text("", BUILDING_PROGRESS_COLOR, 13)
		_upgrade_details.add_child(clock)
		_clock(clock, _int_of(upgrade.get("seconds_left")), "Идёт улучшение: осталось ")
		return
	var ready := bool(upgrade.get("ready", false))
	var start := _button("ОПЛАТИТЬ И УЛУЧШИТЬ" if ready else "НЕДОСТАТОЧНО РЕСУРСОВ", ORDER_BG if ready else ORDER_OFF_BG,
		ORDER_TEXT_COLOR if ready else BUY_OFF_TEXT_COLOR, 220.0)
	start.disabled = not ready
	start.pressed.connect(_on_start_upgrade)
	_upgrade_details.add_child(start)


func _material_row(material: Dictionary) -> HBoxContainer:
	var required := _int_of(material.get("required"))
	var deposited := _int_of(material.get("deposited"))
	var in_warehouse := _int_of(material.get("in_warehouse"))
	var text := "%s: склад %d/%d" % [_text_or(material.get("name"), "Материал"), in_warehouse, _int_of(material.get("remaining"))]
	if deposited > 0:
		text += ", ранее оплачено %d" % deposited
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	row.add_child(_column(_text(text, VALUE_COLOR, 11), 0.0))
	if deposited + in_warehouse < required:
		row.add_child(_text("недостаточно", SHORTAGE_COLOR, 11))
	return row


func _on_start_upgrade() -> void:
	action_requested.emit("start_upgrade", {})


func _fill_stall_upgrades(upgrades: Dictionary) -> void:
	_upgrade_details.add_child(_text("Вместимость: %d мест (+%d от улучшений)" % [
		_int_of(_state.get("stall_capacity")), _int_of(_state.get("stall_capacity_bonus")),
	], TEXT_COLOR, 13))
	for upgrade_id in upgrades:
		var upgrade_value: Variant = upgrades[upgrade_id]
		if upgrade_value is Dictionary:
			_upgrade_details.add_child(_stall_upgrade_card(str(upgrade_id), upgrade_value))


func _stall_upgrade_card(upgrade_id: String, upgrade: Dictionary) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", _box(CARD_BG, CARD_BORDER, 1, 4, 8))
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 3)
	panel.add_child(box)
	box.add_child(_text(_text_or(upgrade.get("name"), upgrade_id), CARD_TITLE_COLOR, 13))
	box.add_child(_text("Увеличивает вместимость стойла на %d лошадь" % _int_of(upgrade.get("horse_capacity")), CARD_TEXT_COLOR, 11))
	box.add_child(_text("Древесина: склад %d/%d" % [_int_of(upgrade.get("wood_in_warehouse")), _int_of(upgrade.get("wood_remaining"))],
		CARD_COST_COLOR, 11))
	var treasury := CURRENCY_SCRIPT.format_amount(_int_of(upgrade.get("treasury_copper")))
	box.add_child(_text("Казна: %s / %d серебра" % [treasury, _int_of(upgrade.get("silver_remaining"))], CARD_COST_COLOR, 11))
	var status_row := HBoxContainer.new()
	status_row.add_theme_constant_override("separation", 8)
	box.add_child(status_row)
	if bool(upgrade.get("purchased", false)):
		if bool(upgrade.get("in_progress", false)):
			var clock := _text("", IN_PROGRESS_COLOR, 11)
			status_row.add_child(_column(clock, 0.0))
			_clock(clock, _int_of(upgrade.get("seconds_left")), "Идёт улучшение: осталось ")
		else:
			status_row.add_child(_column(_text("УСТАНОВЛЕНО", INSTALLED_COLOR, 11), 0.0))
		return panel
	status_row.add_child(_column(_text("Оплата при покупке · установка %s" % format_hms(_int_of(upgrade.get("time_seconds"))),
		CARD_TEXT_COLOR, 11), 0.0))
	var can_buy := bool(upgrade.get("can_purchase", false))
	var buy := _button("КУПИТЬ И УСТАНОВИТЬ" if can_buy else "НЕДОСТАТОЧНО", ORDER_BG if can_buy else ORDER_OFF_BG,
		ORDER_TEXT_COLOR if can_buy else BUY_OFF_TEXT_COLOR, 190.0)
	buy.disabled = not can_buy
	buy.pressed.connect(_on_purchase_upgrade.bind(upgrade_id))
	status_row.add_child(buy)
	return panel


func _on_purchase_upgrade(upgrade_id: String) -> void:
	action_requested.emit("purchase_upgrade", {"upgrade_id": upgrade_id})


func _fill_cart_upgrades() -> void:
	var grade := _dict(_dict(_state, "cart_progress"), "grades")
	var levels := _dict(_dict(grade, "1"), "upgrades")
	var nodes := HBoxContainer.new()
	nodes.add_theme_constant_override("separation", 6)
	_upgrade_details.add_child(nodes)
	var selected: Array = []
	for node in CART_UPGRADE_NODES:
		var node_id := str(node[0])
		var title := "%s · %d/3" % [str(node[1]), _int_of(levels.get(node_id))]
		nodes.add_child(_select_card(title, str(node[2]), node_id == _selected_cart_node, _select_cart_node.bind(node_id)))
		if node_id == _selected_cart_node:
			selected = node
	if selected.is_empty():
		return
	var box := _content(_panel("Материалы для улучшения", _upgrade_details))
	box.add_child(_text(str(selected[1]), TEXT_COLOR, 13))
	var warehouse := _dict(_state, "warehouse_storage")
	for resource in selected[3]:
		box.add_child(_text("%s · На складе: %d" % [CART_RESOURCE_LABELS.get(resource, resource), _int_of(warehouse.get(resource))], VALUE_COLOR, 11))


func _select_cart_node(node_id: String) -> void:
	_selected_cart_node = node_id
	_fill_upgrades()


func _select_upgrade_tab(key: String) -> void:
	_upgrade_tab = key
	_fill_upgrades()


static func _tab_button(text: String, group: ButtonGroup) -> Button:
	var button := Button.new()
	button.text = text
	button.toggle_mode = true
	button.button_group = group
	button.focus_mode = Control.FOCUS_NONE
	button.clip_text = true
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.custom_minimum_size = Vector2(0.0, 22.0)
	button.add_theme_stylebox_override("normal", _box(TAB_BG, TAB_BG, 0, 5, 4))
	button.add_theme_stylebox_override("hover", _box(TAB_HOVER_BG, TAB_HOVER_BG, 0, 5, 4))
	button.add_theme_stylebox_override("pressed", _box(TAB_ACTIVE_BG, TAB_ACTIVE_BG, 0, 5, 4))
	button.add_theme_stylebox_override("hover_pressed", _box(TAB_ACTIVE_BG, TAB_ACTIVE_BG, 0, 5, 4))
	button.add_theme_stylebox_override("focus", _box(TAB_BG, TAB_BG, 0, 5, 4))
	for color_key in ["font_color", "font_hover_color", "font_pressed_color", "font_hover_pressed_color", "font_focus_color"]:
		button.add_theme_color_override(color_key, BUTTON_TEXT_COLOR)
	button.add_theme_font_size_override("font_size", 11)
	return button


static func _button(text: String, background: Color, text_color: Color, minimum_width: float) -> Button:
	var button := Button.new()
	button.text = text
	button.focus_mode = Control.FOCUS_NONE
	button.custom_minimum_size = Vector2(minimum_width, 22.0)
	button.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	_paint_button(button, background, text_color)
	return button


static func _paint_button(button: Button, background: Color, text_color: Color) -> void:
	var hover := background.lightened(0.12)
	button.add_theme_stylebox_override("normal", _box(background, background, 0, 5, 4))
	button.add_theme_stylebox_override("hover", _box(hover, hover, 0, 5, 4))
	button.add_theme_stylebox_override("pressed", _box(background.darkened(0.1), background.darkened(0.1), 0, 5, 4))
	button.add_theme_stylebox_override("disabled", _box(background, background, 0, 5, 4))
	button.add_theme_stylebox_override("focus", _box(background, background, 0, 5, 4))
	for color_key in ["font_color", "font_hover_color", "font_pressed_color", "font_disabled_color", "font_focus_color"]:
		button.add_theme_color_override(color_key, text_color)
	button.add_theme_font_size_override("font_size", 11)


static func _flat_button(text: String) -> Button:
	var button := Button.new()
	button.text = text
	button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	button.focus_mode = Control.FOCUS_NONE
	var transparent := _box(Color(0.0, 0.0, 0.0, 0.0), Color(0.0, 0.0, 0.0, 0.0), 0, 0, 0)
	button.add_theme_stylebox_override("normal", transparent)
	button.add_theme_stylebox_override("focus", transparent)
	button.add_theme_stylebox_override("hover", _box(Color(1.0, 1.0, 1.0, 0.06), Color(0.0, 0.0, 0.0, 0.0), 0, 0, 0))
	button.add_theme_stylebox_override("pressed", _box(Color(1.0, 1.0, 1.0, 0.1), Color(0.0, 0.0, 0.0, 0.0), 0, 0, 0))
	for color_key in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color"]:
		button.add_theme_color_override(color_key, NAME_COLOR)
	button.add_theme_font_size_override("font_size", 11)
	return button


static func _select_card(title: String, detail: String, active: bool, callback: Callable) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var border := SELECT_ACTIVE_BORDER if active else ROW_BORDER
	panel.add_theme_stylebox_override("panel", _box(SELECT_ACTIVE_BG if active else ROW_BG, border, 1, 4, 4))
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 1)
	panel.add_child(box)
	var button := _flat_button(title)
	button.pressed.connect(callback)
	box.add_child(button)
	var detail_label := _text(detail, ROUTE_TEXT_COLOR, 11)
	detail_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(detail_label)
	return panel


static func _entry_row(title: String, detail: String) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", _box(ROW_BG, ROW_BORDER, 1, 4, 6))
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 2)
	panel.add_child(box)
	box.add_child(_text(title, NAME_COLOR, 11))
	var detail_label := _text(detail, DETAIL_COLOR, 11)
	detail_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(detail_label)
	return panel


static func _panel(title: String, parent: Node) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", _box(PANEL_BG, PANEL_BORDER, 1, 4, 10))
	parent.add_child(panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 6)
	panel.add_child(box)
	if not title.is_empty():
		box.add_child(_text(title, TITLE_COLOR, 13))
	return panel


static func _content(panel: PanelContainer) -> VBoxContainer:
	return panel.get_child(0) as VBoxContainer


static func _header(titles: Array, widths: Array, right_index: int) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", _box(HEADER_BG, HEADER_BG, 0, 0, 6))
	var line := HBoxContainer.new()
	line.add_theme_constant_override("separation", 8)
	panel.add_child(line)
	for index in titles.size():
		var label := _cell(str(titles[index]), float(widths[index]), HEADER_TEXT_COLOR)
		if index == right_index:
			label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		line.add_child(label)
	return panel


static func _form_row(caption: String, control: Control) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	var label := _text(caption, VALUE_COLOR, 11)
	label.custom_minimum_size.x = 120.0
	row.add_child(label)
	control.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(control)
	return row


static func _option() -> OptionButton:
	var option := OptionButton.new()
	option.add_theme_font_size_override("font_size", 11)
	option.get_popup().add_theme_font_size_override("font_size", 11)
	return option


static func _text(value: String, color: Color, font_size: int) -> Label:
	var label := Label.new()
	label.text = value
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	return label


static func _centered_text(value: String) -> Label:
	var label := _text(value, MUTED_COLOR, 11)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	return label


static func _cell(value: String, width: float, color: Color) -> Label:
	var label := _text(value, color, 11)
	label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	return _column(label, width) as Label


static func _column(control: Control, width: float) -> Control:
	if width > 0.0:
		control.custom_minimum_size.x = width
	else:
		control.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	return control


static func _spacer(width: float) -> Control:
	var spacer := Control.new()
	spacer.custom_minimum_size = Vector2(width, 0.0)
	spacer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return spacer


static func _box(bg: Color, border: Color, border_width: int, radius: int, margin: int) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = bg
	style.border_color = border
	style.set_border_width_all(border_width)
	style.set_corner_radius_all(radius)
	style.set_content_margin_all(margin)
	return style


static func _divider(color: Color) -> ColorRect:
	var rule := ColorRect.new()
	rule.color = color
	rule.custom_minimum_size = Vector2(0, 1)
	return rule


static func _style_scroll(scroll: ScrollContainer) -> void:
	var bar := scroll.get_v_scroll_bar()
	bar.custom_minimum_size = Vector2(SCROLL_BAR_WIDTH, 0.0)
	bar.add_theme_stylebox_override("scroll", _box(SCROLL_TRACK_BG, SCROLL_TRACK_BORDER, 1, 4, 0))
	bar.add_theme_stylebox_override("grabber", _box(SCROLL_THUMB, SCROLL_THUMB, 0, 4, 0))
	bar.add_theme_stylebox_override("grabber_highlight", _box(SCROLL_THUMB_ACTIVE, SCROLL_THUMB_ACTIVE, 0, 4, 0))
	bar.add_theme_stylebox_override("grabber_pressed", _box(SCROLL_THUMB_ACTIVE, SCROLL_THUMB_ACTIVE, 0, 4, 0))


static func _clear(container: Node) -> void:
	for child in container.get_children():
		container.remove_child(child)
		child.queue_free()
