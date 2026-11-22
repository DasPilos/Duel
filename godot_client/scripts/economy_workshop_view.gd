extends VBoxContainer

# Мастерская из scenes/city/modals.py: вкладки, склад готовых изделий, заказы повозок и очередь работы.
# Вид не делает HTTP. По action_requested родитель выполняет запрос и передаёт ответ в set_state / set_message.
#   "refresh" без payload: GET /api/buildings/stable/{character_id}; вид просит его раз в 5 с, пока окно открыто.
#   "order_cart" с payload {"grade": 1}: POST /api/buildings/stable/{character_id}/cart/purchase, тело {"grade": 1}.
signal action_requested(action: String, payload: Dictionary)

# set_state(state) принимает тот же объект, что Python-клиент получает от get_building("stable", id)
# (поле "building" ответа; ответ POST cart/purchase содержит такой же объект):
#   server_time: float, unix-секунды; остаток заказа = finish_at - server_time - прошедшее время;
#   cart_progress.grades["1"].production_orders: [{order_id, grade, created_at, finish_at}], очередь повозок;
#   cart_progress.grades["1"].body_finish_at: float или null, запасной финиш, если списка заказов нет;
#   cart_progress.grades["1"].upgrades: {wheels, sides, axles}, уровни 0..3;
#   warehouse_storage: {wood: int, ...}, общий склад; нужна древесина;
#   treasury_silver_available: int, серебро, доступное из казны;
#   warehouse: [{item_name}], необязательно: готовые изделия. Python-клиент это поле не заполняет, склад пуст.

const WINDOW_TITLE := "Городская мастерская"
const SUBTITLE := "БРОННАЯ МАСТЕРСКАЯ РАДБУРГА • УРОВЕНЬ 1"
const WINDOW_SIZE := Vector2(1066, 600)
const BORDER_COLOR := Color8(111, 144, 159)
const BACKGROUND_COLOR := Color8(23, 25, 25)
# Панель процесса: 244 px Python при масштабе 1.5 (окно 1600×900 px = 1066×600 единиц).
const PROCESS_HEIGHT := 163.0
const SLOT_MIN_HEIGHT := 100.0
const WORK_MIN_WIDTH := 260.0
const QUEUE_LIMIT := 5
const REFRESH_SECONDS := 5.0
# Скорость пустой повозки при полной прочности (core/cart_progress.py), тайлов в час.
const CART_TILES_PER_HOUR := 1000.0
const METERS_PER_TILE := 10.0
const TABS := [
	["helmets", "ШЛЕМЫ"],
	["armor", "ДОСПЕХИ"],
	["gloves", "ПЕРЧАТКИ"],
	["plates", "ЛАТЫ"],
	["shoes", "ОБУВЬ"],
	["leatherworker", "КОЖЕВНИК"],
	["carts", "ПОВОЗКИ"],
	["upgrades", "УЛУЧШЕНИЯ"],
	["storage", "СКЛАД"],
]
const TAB_MESSAGES := {
	"helmets": "Раздел шлемов мастерской.",
	"armor": "Раздел доспехов и брони.",
	"gloves": "Раздел перчаток.",
	"plates": "Раздел латных комплектов.",
	"shoes": "Раздел обуви.",
	"leatherworker": "Кожевник: обработка кожи и кожаные изделия.",
	"upgrades": "Улучшения мастерской будут доступны после настройки требований.",
}
# Повозки из core/cart_progress.py: только поля, которые читает вид. Грейд 2 не изучен, поэтому в каталог не попадает.
const CART_GRADES := {
	"1": {
		"name": "Лёгкая повозка",
		"researched": true,
		"wood_cost": 100,
		"silver_cost": 10,
		"production_seconds": 2400,
		"base_capacity_kg": 300,
		"base_full_load_speed_penalty_percent": 70,
		"resource_slots": 1,
		"horse_count": 1,
		"villagers_required": 1,
		"load_kg_per_minute": 60,
		"unload_kg_per_minute": 40,
	},
	"2": {"name": "Крестьянский обоз", "researched": false},
}

const SUBTITLE_COLOR := Color8(155, 191, 204)
const TEXT_COLOR := Color8(226, 218, 193)
const MUTED_COLOR := Color8(184, 191, 187)
const SPEC_COLOR := Color8(200, 207, 198)
const PRICE_CAPTION_COLOR := Color8(225, 195, 135)
const PRICE_VALUE_COLOR := Color8(225, 218, 193)
const PRODUCTION_COLOR := Color8(193, 208, 204)
const QUEUED_COLOR := Color8(221, 187, 120)
const DIVIDER_COLOR := Color8(72, 88, 92)
const CARD_BG := Color8(31, 37, 34)
const CARD_BORDER := Color8(68, 88, 76)
const CARD_DIVIDER := Color8(62, 78, 68)
const WOOD_SWATCH := Color8(138, 96, 56)
const SILVER_SWATCH := Color8(196, 202, 210)
const ORDER_BG := Color8(73, 105, 82)
const ORDER_HOVER_BG := Color8(88, 124, 97)
const ORDER_TEXT := Color8(230, 237, 220)
const ORDER_OFF_BG := Color8(56, 61, 57)
const ORDER_OFF_TEXT := Color8(150, 157, 151)
const TAB_BG := Color8(47, 51, 51)
const TAB_HOVER_BG := Color8(105, 138, 153)
const TAB_ACTIVE_BG := Color8(80, 111, 126)
const TAB_TEXT := Color8(178, 184, 181)
const TAB_ACTIVE_TEXT := Color8(230, 237, 235)
const MESSAGE_OK_COLOR := Color8(168, 214, 176)
const MESSAGE_ERROR_COLOR := Color8(232, 153, 123)
const EMPTY_BG := Color8(34, 37, 36)
const EMPTY_BORDER := Color8(86, 103, 104)
const EMPTY_TITLE_COLOR := Color8(222, 207, 168)
const GOODS_BG := Color8(26, 35, 28)
const GOODS_BORDER := Color8(60, 140, 80)
const GOODS_NAME_COLOR := Color8(231, 218, 187)
const GOODS_STATUS_COLOR := Color8(110, 220, 130)
const PROCESS_BG := Color8(28, 31, 31)
const PROCESS_BORDER := Color8(94, 132, 144)
const HEADER_BG := Color8(43, 53, 55)
const HEADER_TEXT_COLOR := Color8(201, 224, 229)
const TOTAL_TIME_COLOR := Color8(221, 205, 157)
const WORK_BG := Color8(34, 39, 39)
const WORK_BORDER := Color8(73, 94, 98)
const WORK_TITLE_COLOR := Color8(224, 217, 194)
const IDLE_TEXT_COLOR := Color8(218, 213, 197)
const WAIT_TEXT_COLOR := Color8(174, 181, 178)
const BAR_BG := Color8(20, 25, 25)
const BAR_FILL := Color8(77, 163, 103)
const PERCENT_COLOR := Color8(238, 244, 237)
const SLOT_CURRENT_BG := Color8(40, 51, 43)
const SLOT_CURRENT_BORDER := Color8(108, 168, 115)
const SLOT_QUEUED_BG := Color8(34, 42, 37)
const SLOT_QUEUED_BORDER := Color8(72, 100, 79)
const SLOT_EMPTY_BG := Color8(34, 38, 38)
const SLOT_EMPTY_BORDER := Color8(72, 85, 86)
const BADGE_BUSY_COLOR := Color8(159, 219, 164)
const BADGE_FREE_COLOR := Color8(160, 164, 158)
const SLOT_NAME_COLOR := Color8(223, 214, 190)
const SLOT_CAPTION_COLOR := Color8(166, 177, 170)
const SLOT_HINT_COLOR := Color8(143, 150, 146)

var _tab := "helmets"
var _server_time := 0.0
var _received_msec := 0
var _refresh_elapsed := 0.0
var _cart_progress: Dictionary = {}
var _warehouse_storage: Dictionary = {}
var _treasury_silver := 0
var _ready_goods: Array = []
var _queue: Array = []

var _tab_buttons: Dictionary = {}
var _tab_scroll: ScrollContainer
var _tab_body: VBoxContainer
var _order_buttons: Dictionary = {}
var _message_label: Label
var _process_panel: PanelContainer
var _queue_title: Label
var _queue_total: Label
var _work_title: Label
var _work_time: Label
var _progress_box: Control
var _progress_bar: ProgressBar
var _progress_percent: Label
var _slot_panels: Array[PanelContainer] = []
var _slot_badges: Array[Label] = []
var _slot_bodies: Array[VBoxContainer] = []
var _slot_names: Array[Label] = []
var _slot_timers: Array[Label] = []
var _slot_hints: Array[Label] = []


func _init() -> void:
	add_theme_constant_override("separation", 8)
	# Родитель кладёт вид в ScrollContainer без растяжения, поэтому вид сам занимает доступную высоту окна
	# (600 − отступы 24 − шапка 36 − разделитель 4): панель процесса стоит внизу, вкладки растягиваются.
	custom_minimum_size.y = WINDOW_SIZE.y - 64.0
	_build_ui()


func window_title() -> String:
	return WINDOW_TITLE


func set_state(state: Dictionary) -> void:
	_server_time = float(state.get("server_time", Time.get_unix_time_from_system()))
	_received_msec = Time.get_ticks_msec()
	_cart_progress = _dict(state.get("cart_progress", {}))
	_warehouse_storage = _dict(state.get("warehouse_storage", {}))
	_treasury_silver = int(state.get("treasury_silver_available", 0))
	var goods: Variant = state.get("warehouse", [])
	_ready_goods = goods if goods is Array else []
	_queue = _build_queue(_cart_progress)
	_render_process()
	_render_tab()


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
	_apply_elapsed((Time.get_ticks_msec() - _received_msec) / 1000.0)


# Как format_forge_time в core/forge_recipes.py: часы, затем мм:сс.
static func format_time(seconds: int) -> String:
	var total := maxi(0, seconds)
	var hours := floori(float(total) / 3600.0)
	var minutes := floori(float(total % 3600) / 60.0)
	var secs := total % 60
	if hours > 0:
		return "%d ч %02d мин" % [hours, minutes]
	if minutes > 0:
		return "%02d:%02d" % [minutes, secs]
	return "00:%02d" % secs


# Как cart_stats в core/cart_progress.py при прочности 100%.
static func cart_stats(upgrades: Dictionary) -> Dictionary:
	var wheels := clampi(int(upgrades.get("wheels", 0)), 0, 3)
	var sides := clampi(int(upgrades.get("sides", 0)), 0, 3)
	var axles := clampi(int(upgrades.get("axles", 0)), 0, 3)
	var seconds_per_tile := maxf(0.25, 3600.0 / CART_TILES_PER_HOUR - wheels)
	return {
		"capacity_kg": int(CART_GRADES["1"]["base_capacity_kg"]) + 50 * sides,
		"empty_tiles_per_hour": _round_half_even(3600.0 / seconds_per_tile),
		"full_load_speed_penalty_percent": int(CART_GRADES["1"]["base_full_load_speed_penalty_percent"]) - 10 * axles,
	}


# round() в Python: половины округляются к чётному (22.5 -> 22), в отличие от round() в GDScript.
static func _round_half_even(value: float) -> int:
	var whole := floorf(value)
	var fraction := value - whole
	if fraction > 0.5 or (fraction == 0.5 and fmod(whole, 2.0) != 0.0):
		return int(whole) + 1
	return int(whole)


static func _box(bg: Color, border: Color, border_width: int, radius: int, margin: int) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = bg
	style.border_color = border
	style.set_border_width_all(border_width)
	style.set_corner_radius_all(radius)
	style.set_content_margin_all(margin)
	return style


static func _dict(value: Variant) -> Dictionary:
	return value if value is Dictionary else {}


func _build_ui() -> void:
	add_child(_text(SUBTITLE, SUBTITLE_COLOR, 13))
	var tab_row := HBoxContainer.new()
	tab_row.add_theme_constant_override("separation", 6)
	add_child(tab_row)
	var group := ButtonGroup.new()
	for entry in TABS:
		var key := str(entry[0])
		var button := Button.new()
		button.text = str(entry[1])
		button.toggle_mode = true
		button.button_group = group
		button.clip_text = true
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.custom_minimum_size = Vector2(0, 34)
		_style_tab_button(button)
		button.pressed.connect(_select_tab.bind(key))
		tab_row.add_child(button)
		_tab_buttons[key] = button
	add_child(_divider(DIVIDER_COLOR))
	_tab_scroll = ScrollContainer.new()
	_tab_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(_tab_scroll)
	_tab_body = VBoxContainer.new()
	_tab_body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_tab_body.add_theme_constant_override("separation", 10)
	_tab_scroll.add_child(_tab_body)
	_message_label = _text("", MESSAGE_OK_COLOR, 13)
	_message_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_message_label.visible = false
	add_child(_message_label)
	_build_process_panel()
	_render_process()
	_tab_buttons[_tab].button_pressed = true
	_render_tab()


func _build_process_panel() -> void:
	_process_panel = PanelContainer.new()
	_process_panel.custom_minimum_size = Vector2(0, PROCESS_HEIGHT)
	_process_panel.add_theme_stylebox_override("panel", _box(PROCESS_BG, PROCESS_BORDER, 2, 8, 6))
	add_child(_process_panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 6)
	_process_panel.add_child(box)

	var header := PanelContainer.new()
	header.add_theme_stylebox_override("panel", _box(HEADER_BG, HEADER_BG, 0, 5, 3))
	box.add_child(header)
	var header_row := HBoxContainer.new()
	header.add_child(header_row)
	_queue_title = _text("", HEADER_TEXT_COLOR, 12)
	_queue_title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_queue_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header_row.add_child(_queue_title)
	_queue_total = _text("", TOTAL_TIME_COLOR, 14)
	header_row.add_child(_queue_total)

	var body := HBoxContainer.new()
	body.add_theme_constant_override("separation", 8)
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	box.add_child(body)

	var work := PanelContainer.new()
	work.custom_minimum_size = Vector2(WORK_MIN_WIDTH, 0)
	work.size_flags_vertical = Control.SIZE_EXPAND_FILL
	work.add_theme_stylebox_override("panel", _box(WORK_BG, WORK_BORDER, 1, 6, 6))
	body.add_child(work)
	var work_box := VBoxContainer.new()
	work_box.add_theme_constant_override("separation", 4)
	work.add_child(work_box)
	_work_title = _text("", WORK_TITLE_COLOR, 14)
	_work_title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	work_box.add_child(_work_title)
	_work_time = _text("", QUEUED_COLOR, 12)
	_work_time.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	work_box.add_child(_work_time)
	_progress_box = Control.new()
	_progress_box.custom_minimum_size = Vector2(0, 20)
	work_box.add_child(_progress_box)
	_progress_bar = ProgressBar.new()
	_progress_bar.min_value = 0.0
	_progress_bar.max_value = 100.0
	_progress_bar.show_percentage = false
	_progress_bar.add_theme_stylebox_override("background", _box(BAR_BG, PROCESS_BORDER, 1, 4, 0))
	_progress_bar.add_theme_stylebox_override("fill", _box(BAR_FILL, BAR_FILL, 0, 4, 0))
	_progress_bar.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_progress_box.add_child(_progress_bar)
	_progress_percent = _text("", PERCENT_COLOR, 11)
	_progress_percent.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_progress_percent.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_progress_percent.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_progress_box.add_child(_progress_percent)

	var slots := HBoxContainer.new()
	slots.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	slots.size_flags_vertical = Control.SIZE_EXPAND_FILL
	slots.add_theme_constant_override("separation", 6)
	body.add_child(slots)
	for index in range(QUEUE_LIMIT):
		var slot := PanelContainer.new()
		slot.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		slot.size_flags_vertical = Control.SIZE_EXPAND_FILL
		slot.custom_minimum_size = Vector2(0, SLOT_MIN_HEIGHT)
		slots.add_child(slot)
		var slot_box := VBoxContainer.new()
		slot_box.add_theme_constant_override("separation", 2)
		slot.add_child(slot_box)
		var badge := _text("", BADGE_FREE_COLOR, 11)
		badge.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		slot_box.add_child(badge)
		var slot_body := VBoxContainer.new()
		slot_body.add_theme_constant_override("separation", 1)
		slot_box.add_child(slot_body)
		var name_label := _text("", SLOT_NAME_COLOR, 12)
		name_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		slot_body.add_child(name_label)
		slot_body.add_child(_text("До готовности:", SLOT_CAPTION_COLOR, 11))
		var timer := _text("", QUEUED_COLOR, 15)
		slot_body.add_child(timer)
		var hint := _text("До 5 заказов мастерской", SLOT_HINT_COLOR, 11)
		hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		slot_box.add_child(hint)
		_slot_panels.append(slot)
		_slot_badges.append(badge)
		_slot_bodies.append(slot_body)
		_slot_names.append(name_label)
		_slot_timers.append(timer)
		_slot_hints.append(hint)


func _select_tab(key: String) -> void:
	_tab = key
	(_tab_buttons[key] as Button).button_pressed = true
	_tab_scroll.scroll_vertical = 0
	_render_tab()


func _render_tab() -> void:
	_clear(_tab_body)
	_order_buttons.clear()
	if _tab == "carts":
		_render_carts()
	elif _tab == "storage":
		_render_storage()
	else:
		_render_placeholder(_tab)


func _render_carts() -> void:
	var grid := GridContainer.new()
	grid.columns = 2
	grid.add_theme_constant_override("h_separation", 10)
	grid.add_theme_constant_override("v_separation", 10)
	_tab_body.add_child(grid)
	var grades: Dictionary = _dict(_cart_progress.get("grades", {}))
	for key in CART_GRADES.keys():
		var config: Dictionary = CART_GRADES[key]
		if not bool(config.get("researched", false)) or int(config.get("production_seconds", 0)) <= 0:
			continue
		var grade := int(key)
		grid.add_child(_cart_card(grade, config, _dict(grades.get(str(grade), {}))))


func _cart_card(grade: int, config: Dictionary, grade_state: Dictionary) -> PanelContainer:
	var stats := cart_stats(_dict(grade_state.get("upgrades", {})))
	var orders: Array = grade_state.get("production_orders", [])
	var wood_cost := int(config["wood_cost"])
	var silver_cost := int(config["silver_cost"])
	var wood_available := int(_warehouse_storage.get("wood", 0))
	var can_order := _queue.size() < QUEUE_LIMIT and wood_available >= wood_cost and _treasury_silver >= silver_cost

	var card := PanelContainer.new()
	card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	card.custom_minimum_size = Vector2(400, 0)
	card.add_theme_stylebox_override("panel", _box(CARD_BG, CARD_BORDER, 1, 7, 10))
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 6)
	card.add_child(box)

	var head := HBoxContainer.new()
	box.add_child(head)
	var title := _text(str(config["name"]), TEXT_COLOR, 16)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(title)
	if not orders.is_empty():
		head.add_child(_text("В очереди: %d" % orders.size(), QUEUED_COLOR, 13))
	box.add_child(_divider(CARD_DIVIDER))

	var specs := GridContainer.new()
	specs.columns = 2
	specs.add_theme_constant_override("h_separation", 12)
	box.add_child(specs)
	for line in _spec_lines(config, stats):
		specs.add_child(_text(line, SPEC_COLOR, 13))

	var price := HBoxContainer.new()
	price.add_theme_constant_override("separation", 6)
	box.add_child(price)
	price.add_child(_text("Цена:", PRICE_CAPTION_COLOR, 13))
	price.add_child(_swatch(WOOD_SWATCH, "Древесина"))
	price.add_child(_text("%d/%d" % [wood_available, wood_cost], PRICE_VALUE_COLOR, 13))
	price.add_child(_swatch(SILVER_SWATCH, "Серебро"))
	price.add_child(_text("%d/%d" % [_treasury_silver, silver_cost], PRICE_VALUE_COLOR, 13))

	var footer := HBoxContainer.new()
	box.add_child(footer)
	var production := _text("Производство: %s" % _production_text(int(config["production_seconds"])), PRODUCTION_COLOR, 13)
	production.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	footer.add_child(production)
	var order_button := Button.new()
	order_button.text = "Заказать"
	order_button.custom_minimum_size = Vector2(110, 30)
	order_button.disabled = not can_order
	_style_order_button(order_button)
	order_button.pressed.connect(_on_order_pressed.bind(grade))
	footer.add_child(order_button)
	_order_buttons[grade] = order_button
	return card


func _spec_lines(config: Dictionary, stats: Dictionary) -> Array[String]:
	var kmh := _round_half_even(float(stats["empty_tiles_per_hour"]) * METERS_PER_TILE / 1000.0)
	var lines: Array[String] = []
	lines.append("Грузоподъёмность: %d кг" % int(stats["capacity_kg"]))
	lines.append("Кучер: %d" % int(config["villagers_required"]))
	lines.append("Слот для товаров: %d" % int(config["resource_slots"]))
	lines.append("Упряжка: %d" % int(config["horse_count"]))
	lines.append("Погрузка: %d кг/мин" % int(config["load_kg_per_minute"]))
	lines.append("Разгрузка: %d кг/мин" % int(config["unload_kg_per_minute"]))
	lines.append("Скорость без груза: %d км/ч" % kmh)
	lines.append("Полная загрузка: штраф -%d%%" % int(stats["full_load_speed_penalty_percent"]))
	return lines


func _production_text(seconds: int) -> String:
	return "40 минут" if seconds == 2400 else format_time(seconds)


func _on_order_pressed(grade: int) -> void:
	var button: Button = _order_buttons.get(grade)
	if button == null or button.disabled:
		return
	action_requested.emit("order_cart", {"grade": grade})


func _render_storage() -> void:
	if _ready_goods.is_empty():
		var center := CenterContainer.new()
		_tab_body.add_child(center)
		var empty := PanelContainer.new()
		empty.custom_minimum_size = Vector2(420, 150)
		empty.add_theme_stylebox_override("panel", _box(EMPTY_BG, EMPTY_BORDER, 1, 8, 16))
		center.add_child(empty)
		var empty_box := VBoxContainer.new()
		empty_box.alignment = BoxContainer.ALIGNMENT_CENTER
		empty_box.add_theme_constant_override("separation", 12)
		empty.add_child(empty_box)
		var title := _text("СКЛАД ГОТОВОЙ ПРОДУКЦИИ ПУСТ", EMPTY_TITLE_COLOR, 16)
		title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		empty_box.add_child(title)
		var message := _text("Готовые изделия мастерской будут храниться здесь.", MUTED_COLOR, 13)
		message.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		empty_box.add_child(message)
		return
	var grid := GridContainer.new()
	grid.columns = 4
	grid.add_theme_constant_override("h_separation", 12)
	grid.add_theme_constant_override("v_separation", 12)
	_tab_body.add_child(grid)
	for goods_variant in _ready_goods:
		var goods := _dict(goods_variant)
		var card := PanelContainer.new()
		card.custom_minimum_size = Vector2(190, 80)
		card.add_theme_stylebox_override("panel", _box(GOODS_BG, GOODS_BORDER, 1, 8, 10))
		var card_box := VBoxContainer.new()
		card.add_child(card_box)
		card_box.add_child(_text(str(goods.get("item_name", "Изделие мастерской")), GOODS_NAME_COLOR, 16))
		card_box.add_child(_text("ГОТОВО К ВЫДАЧЕ", GOODS_STATUS_COLOR, 11))
		grid.add_child(card)


func _render_placeholder(key: String) -> void:
	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 28)
	margin.add_theme_constant_override("margin_top", 16)
	_tab_body.add_child(margin)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 8)
	margin.add_child(box)
	box.add_child(_text(_tab_title(key), TEXT_COLOR, 16))
	var message := _text(str(TAB_MESSAGES.get(key, "Раздел готовится.")), MUTED_COLOR, 13)
	message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(message)


# Очередь как в _refresh_workshop_state (scenes/city_scene.py): заказы всех грейдов по времени финиша.
func _build_queue(progress: Dictionary) -> Array:
	var entries: Array = []
	var grades: Dictionary = _dict(progress.get("grades", {}))
	for grade_key in grades.keys():
		var grade_progress: Dictionary = _dict(grades[grade_key])
		var orders: Array = grade_progress.get("production_orders", []).duplicate()
		if orders.is_empty() and grade_progress.get("body_finish_at") != null:
			orders = [{"finish_at": grade_progress["body_finish_at"]}]
		for order_variant in orders:
			var order: Dictionary = order_variant
			var order_grade := int(order.get("grade", str(grade_key).to_int()))
			var config: Dictionary = _dict(CART_GRADES.get(str(order_grade), {}))
			entries.append({
				"seq": entries.size(),
				"order_id": order.get("order_id"),
				"grade": order_grade,
				"item_name": str(config.get("name", "Повозка")),
				"finish_at": float(order["finish_at"]),
				"duration_seconds": int(config.get("production_seconds", 2400)),
				"seconds_left": 0,
			})
	var by_finish := func(a: Dictionary, b: Dictionary) -> bool:
		if a["finish_at"] == b["finish_at"]:
			return int(a["seq"]) < int(b["seq"])
		return float(a["finish_at"]) < float(b["finish_at"])
	entries.sort_custom(by_finish)
	return entries


func _render_process() -> void:
	_queue_title.text = "ПРОЦЕСС РАБОТЫ МАСТЕРСКОЙ • ОЧЕРЕДЬ: %d / %d (МАКС. 5 ЗАКАЗОВ)" % [_queue.size(), QUEUE_LIMIT]
	var idle := _queue.is_empty()
	_work_title.add_theme_color_override("font_color", IDLE_TEXT_COLOR if idle else WORK_TITLE_COLOR)
	_work_time.add_theme_color_override("font_color", WAIT_TEXT_COLOR if idle else QUEUED_COLOR)
	for index in range(QUEUE_LIMIT):
		var filled := index < _queue.size()
		_slot_panels[index].add_theme_stylebox_override("panel", _slot_style(filled and index == 0, filled))
		_slot_badges[index].text = _slot_badge_text(index, filled)
		_slot_badges[index].add_theme_color_override("font_color", BADGE_BUSY_COLOR if filled else BADGE_FREE_COLOR)
		_slot_bodies[index].visible = filled
		_slot_hints[index].visible = not filled
		if filled:
			var order: Dictionary = _queue[index]
			_slot_names[index].text = str(order["item_name"])
	_apply_elapsed(0.0)


func _slot_badge_text(index: int, filled: bool) -> String:
	if not filled:
		return "[%d] СВОБОДНЫЙ СЛОТ" % (index + 1)
	return "[%d] %s" % [index + 1, "В ПРОИЗВОДСТВЕ" if index == 0 else "В ОЧЕРЕДИ"]


func _slot_style(current: bool, filled: bool) -> StyleBoxFlat:
	if current:
		return _box(SLOT_CURRENT_BG, SLOT_CURRENT_BORDER, 2, 6, 6)
	if filled:
		return _box(SLOT_QUEUED_BG, SLOT_QUEUED_BORDER, 1, 6, 6)
	return _box(SLOT_EMPTY_BG, SLOT_EMPTY_BORDER, 1, 6, 6)


# elapsed — секунды с момента set_state; остаток каждого заказа пересчитывается как в update() Python-клиента.
func _apply_elapsed(elapsed: float) -> void:
	var total := 0
	for entry in _queue:
		var order: Dictionary = entry
		order["seconds_left"] = maxi(0, int(float(order["finish_at"]) - _server_time - elapsed))
		total += int(order["seconds_left"])
	_queue_total.text = "ОБЩЕЕ ВРЕМЯ: %s" % format_time(total)
	for index in range(mini(_queue.size(), QUEUE_LIMIT)):
		var slot_order: Dictionary = _queue[index]
		_slot_timers[index].text = format_time(int(slot_order["seconds_left"]))
	if _queue.is_empty():
		_work_title.text = "Мастерская свободна"
		_work_time.text = "Ожидает заказа на производство."
		_progress_box.visible = false
		return
	var current: Dictionary = _queue[0]
	var seconds := int(current["seconds_left"])
	var duration := maxi(1, int(current["duration_seconds"]))
	var done := clampi(duration - seconds, 0, duration)
	var ratio := float(done) / float(duration)
	_work_title.text = "В ПРОИЗВОДСТВЕ: %s" % str(current["item_name"])
	_work_time.text = "До готовности: %s" % format_time(seconds)
	_progress_box.visible = true
	_progress_bar.value = ratio * 100.0
	_progress_percent.text = "%d%%" % floori(ratio * 100.0)


func _style_tab_button(button: Button) -> void:
	button.add_theme_stylebox_override("normal", _box(TAB_BG, TAB_BG, 0, 5, 6))
	button.add_theme_stylebox_override("hover", _box(TAB_HOVER_BG, TAB_HOVER_BG, 0, 5, 6))
	button.add_theme_stylebox_override("pressed", _box(TAB_ACTIVE_BG, TAB_ACTIVE_BG, 0, 5, 6))
	button.add_theme_stylebox_override("hover_pressed", _box(TAB_ACTIVE_BG, TAB_ACTIVE_BG, 0, 5, 6))
	button.add_theme_stylebox_override("focus", _box(TAB_BG, TAB_BG, 0, 5, 6))
	button.add_theme_color_override("font_color", TAB_TEXT)
	button.add_theme_color_override("font_hover_color", TAB_ACTIVE_TEXT)
	button.add_theme_color_override("font_pressed_color", TAB_ACTIVE_TEXT)
	button.add_theme_color_override("font_hover_pressed_color", TAB_ACTIVE_TEXT)
	button.add_theme_color_override("font_focus_color", TAB_TEXT)
	button.add_theme_font_size_override("font_size", 12)


func _style_order_button(button: Button) -> void:
	button.add_theme_stylebox_override("normal", _box(ORDER_BG, ORDER_BG, 0, 5, 4))
	button.add_theme_stylebox_override("hover", _box(ORDER_HOVER_BG, ORDER_HOVER_BG, 0, 5, 4))
	button.add_theme_stylebox_override("pressed", _box(ORDER_HOVER_BG, ORDER_HOVER_BG, 0, 5, 4))
	button.add_theme_stylebox_override("focus", _box(ORDER_BG, ORDER_BG, 0, 5, 4))
	button.add_theme_stylebox_override("disabled", _box(ORDER_OFF_BG, ORDER_OFF_BG, 0, 5, 4))
	button.add_theme_color_override("font_color", ORDER_TEXT)
	button.add_theme_color_override("font_hover_color", ORDER_TEXT)
	button.add_theme_color_override("font_pressed_color", ORDER_TEXT)
	button.add_theme_color_override("font_focus_color", ORDER_TEXT)
	button.add_theme_color_override("font_disabled_color", ORDER_OFF_TEXT)
	button.add_theme_font_size_override("font_size", 13)


func _tab_title(key: String) -> String:
	for entry in TABS:
		if str(entry[0]) == key:
			return str(entry[1])
	return ""


func _text(value: String, color: Color, font_size: int) -> Label:
	var label := Label.new()
	label.text = value
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	return label


func _swatch(color: Color, hint: String) -> ColorRect:
	var swatch := ColorRect.new()
	swatch.color = color
	swatch.custom_minimum_size = Vector2(16, 16)
	swatch.tooltip_text = hint
	return swatch


func _divider(color: Color) -> ColorRect:
	var rule := ColorRect.new()
	rule.color = color
	rule.custom_minimum_size = Vector2(0, 1)
	return rule


func _clear(container: Node) -> void:
	for child in container.get_children():
		container.remove_child(child)
		child.queue_free()
