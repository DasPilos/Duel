extends VBoxContainer

# Окно замка из ui/castle_window.py: вкладки ГУБЕРНАТОР, НАСЕЛЕНИЕ, КАЗНА, ЗАДАНИЯ, УЛУЧШЕНИЯ.
# Вид не делает HTTP. По action_requested родитель выполняет запрос и передаёт ответ в set_state / set_message.
#   "refresh" без payload: GET /api/castle/{character_id}/population; вид просит его раз в 5 с, пока окно открыто.
#   "assign_citizen" {citizen_id: int, worksite_key: String, slot_index: int}:
#       POST /api/castle/{character_id}/citizens/{citizen_id}/assign, тело {"building": worksite_key, "slot_index": slot_index}.
#   "recall_citizen" {citizen_id: int}: POST /api/castle/{character_id}/citizens/{citizen_id}/recall.
#   "treasury_deposit" и "treasury_withdraw" {maximum_copper: int}: родитель открывает диалог суммы;
#       maximum_copper — предел перевода в медях (личный взнос для пополнения, личный вклад для выдачи).
#   "upgrade_start" {upgrade_id: String}: POST /api/castle/{character_id}/upgrades/{upgrade_id}.
signal action_requested(action: String, payload: Dictionary)

# set_state(state) принимает объект "population" из ответа /api/castle/{id}/population (city_population.py, _payload()).
# Читаются поля: castle_name, castle_level, population, population_capacity, food_status, food_zone ("green", "yellow", "red"),
#   new_citizen_eta_seconds, satiated_eta_seconds, departure_eta_seconds (int или null),
#   city_resource_income_per_hour, city_resource_consumption_per_hour (ресурс → float), city_resource_trend (ресурс → строка),
#   city_resource_storage (древесина для улучшений), citizens (id, name, satiety, strong_hunger, satisfaction, work_status,
#   job_building, death_eta_seconds, travel_seconds_left, travel_direction), worksites (building, name, free_slots,
#   capacity, travel_seconds), treasury (copper, silver, gold), personal_treasury_copper, personal_treasury_text,
#   spendable_treasury_copper, personal_currency_copper, is_mayor, tax_tick_seconds_left, expected_tax_text,
#   upgrades (id, name, requirement, result, time_seconds, silver_cost, wood_cost, is_complete, is_active, seconds_left).
# Отсутствующее поле выводится как «—», статус по нему не строится.

# Размеры в единицах Godot: Python px × 2/3 (база 1280×720); шрифты 19 → 13, 16 → 11.
const WINDOW_SIZE := Vector2(720, 507)
const BORDER_COLOR := Color8(197, 164, 103)
const BACKGROUND_COLOR := Color8(24, 27, 25)
const DEFAULT_CASTLE_NAME := "Замок Радбурка"
const REFRESH_SECONDS := 5.0
const BODY_MIN_HEIGHT := 340.0
const CONFIRM_SIZE := Vector2(333, 140)
const CONFIRM_BUTTON_SIZE := Vector2(113, 24)
const CONFIRM_BUTTON_GAP := 29
const ACTION_BUTTON_SIZE := Vector2(147, 28)
const UPGRADE_BUTTON_SIZE := Vector2(140, 25)
const CITIZEN_BUTTON_SIZE := Vector2(88, 19)
const CITIZEN_NAME_INDENT := 12.0
const CITIZEN_NAME_WIDTH := 84.0
const CITIZEN_METER_WIDTH := 116.0
const CITIZEN_DEATH_WIDTH := 128.0
const SCROLL_CONTENT_RIGHT_MARGIN := 8
const METER_SIZE := Vector2(100, 5)
const WORKSITE_BUTTON_HEIGHT := 36.0
const GOVERNOR_RESOURCE_WIDTH := 200.0
const GOVERNOR_INCOME_WIDTH := 146.7
const GOVERNOR_CONSUMPTION_WIDTH := 180.0
const TREND_DOT_SIZE := 17.3
const COIN_DOT_SIZE := 14.0
const SCROLL_BAR_WIDTH := 7.0
const TABS := [
	["governor", "ГУБЕРНАТОР"],
	["population", "НАСЕЛЕНИЕ"],
	["treasury", "КАЗНА"],
	["tasks", "ЗАДАНИЯ"],
	["upgrades", "УЛУЧШЕНИЯ"],
]
# Подписи ресурсов как RESOURCE_LABELS в economy_world.gd (Python: core/production_buildings.py RESOURCES).
const RESOURCE_LABELS := {
	"wheat": "Пшеница", "flax": "Лён", "cotton": "Хлопок", "wood": "Древесина", "berries": "Ягоды",
	"iron": "Железная руда", "stone": "Камень", "mithril": "Мифриловая руда", "obsidian": "Обсидиановая порода",
	"leather": "Кожа", "meat": "Мясо", "coal": "Уголь", "jet": "Гагат", "malachite": "Малахит", "topaz": "Топаз",
	"garnet": "Гранат", "emerald": "Изумруд", "ruby": "Рубин", "sapphire": "Сапфир", "diamond": "Алмаз",
	"board": "Доска", "iron_ingot": "Железо", "steel": "Сталь", "hard_leather": "Крепкая кожа",
	"thick_leather": "Толстая кожа", "cloth": "Ткань", "stone_block": "Каменный блок",
}
const TREND_STYLES := {
	"deficit": [Color8(239, 83, 77), "Дефицит"],
	"surplus": [Color8(244, 195, 75), "Есть небольшой +"],
	"upgrade_ready": [Color8(104, 222, 133), "На ап города"],
}
const ZONE_COLORS := {
	"green": Color8(75, 190, 100),
	"yellow": Color8(232, 191, 67),
	"red": Color8(218, 69, 65),
}
const ZONE_DEFAULT_COLOR := Color8(225, 216, 187)
# Поле ETA и подпись таймера зоны, как в _draw_population (в подписи «сытое» пробел перед двоеточием, как в Python).
const ZONE_TIMERS := {
	"green": ["new_citizen_eta_seconds", "Новый горожанин прибудет через: "],
	"yellow": ["satiated_eta_seconds", "Население сытое : "],
	"red": ["departure_eta_seconds", "Горожанин покинет город : "],
}
const WORKSITE_LABELS := {
	"farm": "Ферма", "lumber_camp": "Лесопилка", "mountain_rift": "Рудник",
	"barnyard": "Зверинец", "black_pit": "Чёрная яма",
}
const WORK_COLORS := {
	"Свободен": Color8(120, 195, 230),
	"Занят": Color8(120, 215, 130),
	"В пути": Color8(90, 165, 245),
	"Возвращается": Color8(235, 170, 105),
	"В городе": Color8(220, 185, 115),
	"Ведёт повозку": Color8(215, 176, 112),
}
const WORK_DEFAULT_COLOR := Color8(200, 200, 200)

const TITLE_COLOR := Color8(243, 218, 158)
const SUBTITLE_COLOR := Color8(220, 209, 184)
const DIVIDER_COLOR := Color8(86, 80, 62)
const RULE_COLOR := Color8(83, 81, 68)
const FRAME_COLOR := Color8(197, 164, 103)
const TEXT_COLOR := Color8(220, 215, 197)
const EMPTY_COLOR := Color8(190, 190, 180)
const PLACEHOLDER_COLOR := Color8(205, 199, 185)
const MESSAGE_ERROR_COLOR := Color8(242, 170, 115)
const MESSAGE_OK_COLOR := Color8(168, 214, 176)
const BUTTON_TEXT_COLOR := Color8(255, 255, 255)
const TAB_BG := Color8(45, 49, 46)
const TAB_HOVER_BG := Color8(128, 108, 69)
const TAB_ACTIVE_BG := Color8(104, 88, 58)
const ROW_BG := Color8(33, 37, 35)
const ROW_ALT_BG := Color8(38, 42, 39)
const NAME_COLOR := Color8(226, 225, 211)
const SATIETY_LOW_COLOR := Color8(226, 66, 58)
const SATIETY_MID_COLOR := Color8(232, 184, 48)
const SATIETY_OK_COLOR := Color8(72, 174, 95)
const STARVING_COLOR := Color8(15, 15, 15)
const METER_BG := Color8(95, 98, 91)
const ASSIGN_BG := Color8(73, 104, 75)
const HOME_BG := Color8(75, 74, 62)
const CITIZEN_HOVER_BG := Color8(96, 135, 93)
const WORKSITE_CAPTION_COLOR := Color8(228, 215, 178)
const WORKSITE_FREE_BG := Color8(62, 90, 65)
const WORKSITE_FREE_HOVER_BG := Color8(83, 125, 86)
const WORKSITE_FULL_BG := Color8(48, 50, 47)
const WORKSITE_BORDER := Color8(92, 105, 91)
const WORKSITE_NAME_COLOR := Color8(230, 225, 205)
const WORKSITE_COUNT_COLOR := Color8(202, 211, 195)
const SCROLL_TRACK_BG := Color8(29, 34, 32)
const SCROLL_TRACK_BORDER := Color8(70, 78, 73)
const SCROLL_THUMB := Color8(104, 126, 110)
const SCROLL_THUMB_ACTIVE := Color8(154, 174, 157)
const CONFIRM_BG := Color8(17, 21, 19)
const CONFIRM_DETAIL_COLOR := Color8(205, 199, 185)
const CONFIRM_OK_BG := Color8(65, 105, 68)
const CONFIRM_OK_HOVER_BG := Color8(83, 132, 85)
const CONFIRM_CANCEL_BG := Color8(86, 59, 51)
const CONFIRM_CANCEL_HOVER_BG := Color8(127, 71, 61)
const COIN_COLORS := {
	"copper": Color8(176, 112, 64),
	"silver": Color8(196, 202, 210),
	"gold": Color8(226, 186, 88),
}
const COIN_TEXT_COLOR := Color8(232, 225, 205)
const WOOD_COLOR := Color8(138, 96, 56)
const PERSONAL_COLOR := Color8(224, 211, 178)
const TAX_COLOR := Color8(190, 205, 184)
const DEPOSIT_BG := Color8(64, 105, 68)
const DEPOSIT_HOVER_BG := Color8(83, 132, 85)
const WITHDRAW_BG := Color8(75, 82, 64)
const WITHDRAW_HOVER_BG := Color8(105, 115, 77)
const UPGRADE_BG := Color8(34, 39, 31)
const UPGRADE_READY_BORDER := Color8(108, 137, 82)
const UPGRADE_LOCKED_BORDER := Color8(77, 78, 66)
const UPGRADE_NAME_COLOR := Color8(232, 218, 184)
const REQUIREMENT_COLOR := Color8(161, 201, 148)
const RESULT_COLOR := Color8(197, 207, 190)
const UPGRADE_TIME_COLOR := Color8(180, 194, 176)
const PRICE_COLOR := Color8(224, 214, 188)
const DONE_COLOR := Color8(143, 208, 139)
const TIMER_COLOR := Color8(132, 193, 231)
const START_BG := Color8(75, 125, 70)
const START_TEXT_COLOR := Color8(240, 238, 220)
const LOCKED_BG := Color8(49, 51, 46)
const LOCKED_TEXT_COLOR := Color8(140, 142, 132)
const CURRENCY_SCRIPT := preload("res://scripts/currency_format.gd")

var _tab := "governor"
var _state: Dictionary = {}
var _castle_name := DEFAULT_CASTLE_NAME
var _received_msec := 0
var _refresh_elapsed := 0.0
var _selected_citizen_id := -1
var _pending: Dictionary = {}
var _travel_labels: Array = []
var _tab_buttons: Dictionary = {}
var _tab_panels: Dictionary = {}
var _subtitle: Label
var _body: Control
var _message_label: Label
var _confirm_blocker: Control
var _confirm_panel: PanelContainer
var _confirm_title: Label
var _confirm_detail: Label
var _confirm_ok: Button
var _governor_rows: VBoxContainer
var _summary_label: Label
var _zone_timer: Label
var _citizen_scroll: ScrollContainer
var _citizen_rows: VBoxContainer
var _worksite_section: VBoxContainer
var _worksite_row: HBoxContainer
var _coin_row: HBoxContainer
var _mayor_label: Label
var _personal_label: Label
var _tax_label: Label
var _upgrade_cards: VBoxContainer


func _init() -> void:
	add_theme_constant_override("separation", 6)
	_build_ui()


func window_title() -> String:
	return _castle_name


func set_state(state: Dictionary) -> void:
	_state = state
	_castle_name = _text_or(state.get("castle_name"), DEFAULT_CASTLE_NAME)
	_subtitle.text = "Уровень %s" % _count_text(state.get("castle_level"))
	_clear_invalid_selection()
	_fill_governor()
	_fill_population()
	_fill_treasury()
	_fill_upgrades()
	_received_msec = Time.get_ticks_msec()
	_update_travel_labels()


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
	_update_travel_labels()


# Как format_hms в ui/time_format.py: ЧЧ:ММ:СС, отрицательные значения считаются нулём.
static func format_hms(seconds: int) -> String:
	var total := maxi(0, seconds)
	var hours := floori(float(total) / 3600.0)
	var minutes := floori(float(total % 3600) / 60.0)
	return "%02d:%02d:%02d" % [hours, minutes, total % 60]


# Как _citizen_is_free в ui/castle_window.py.
static func _citizen_is_free(citizen: Dictionary) -> bool:
	return (_text_or(citizen.get("job_building"), "").is_empty()
		and _text_or(citizen.get("travel_direction"), "").is_empty()
		and _text_or(citizen.get("work_status"), "") == "Свободен"
		and _text_or(citizen.get("satisfaction"), "") == "satisfied")


# Как sorted(..., key=not free) в castle_window.py: свободные первыми, порядок внутри групп сохраняется.
static func _sorted_citizens(citizens: Array) -> Array:
	var free_first: Array = []
	var busy: Array = []
	for citizen_variant in citizens:
		if citizen_variant is Dictionary:
			var citizen: Dictionary = citizen_variant
			if _citizen_is_free(citizen):
				free_first.append(citizen)
			else:
				busy.append(citizen)
	return free_first + busy


static func _satiety_color(satiety: int) -> Color:
	if satiety <= 10:
		return SATIETY_LOW_COLOR
	if satiety <= 30:
		return SATIETY_MID_COLOR
	return SATIETY_OK_COLOR


static func _occupancy_text(site: Dictionary, free_count: int) -> String:
	var capacity: Variant = site.get("capacity")
	var occupied := "—" if capacity == null else str(maxi(0, int(capacity) - free_count))
	return "Свободно: %d · занято: %s" % [free_count, occupied]


# Скорость ресурса: null, если словаря нет; иначе значение или 0, как dict.get(resource, 0) в Python.
static func _rate(rates: Variant, resource: String) -> Variant:
	if rates is Dictionary:
		var values: Dictionary = rates
		return float(values.get(resource, 0.0))
	return null


static func _trend_value(trends: Variant, resource: String) -> Variant:
	if trends is Dictionary:
		var values: Dictionary = trends
		return values.get(resource)
	return null


static func _rate_text(value: Variant) -> String:
	if value == null:
		return "—"
	return ("%.1f" % float(value)).replace(".", ",") + " в час"


static func _resource_keys(income: Variant, consumption: Variant) -> Array:
	var keys: Array = []
	for source in [income, consumption]:
		if source is Dictionary:
			for key in source.keys():
				if not keys.has(key):
					keys.append(key)
	return keys


# Монеты как draw_treasury_coins в ui/catalog_icons.py: [золото, серебро, медь]; пусто, если суммы нет.
static func _coin_parts(copper: Variant) -> Array:
	if copper == null:
		return []
	var value := maxi(0, int(copper))
	var gold := floori(float(value) / CURRENCY_SCRIPT.COPPER_PER_GOLD)
	var silver := floori(float(value % CURRENCY_SCRIPT.COPPER_PER_GOLD) / CURRENCY_SCRIPT.COPPER_PER_SILVER)
	return [gold, silver, value % CURRENCY_SCRIPT.COPPER_PER_SILVER]


# Как в castle_window.py: казна переводится в серебро (// 100), нужны серебро и древесина.
static func _can_afford(upgrade: Dictionary, copper: Variant, wood: Variant) -> bool:
	var silver_cost: Variant = upgrade.get("silver_cost")
	var wood_cost: Variant = upgrade.get("wood_cost")
	if copper == null or wood == null or silver_cost == null or wood_cost == null:
		return false
	var silver := floori(float(int(copper)) / CURRENCY_SCRIPT.COPPER_PER_SILVER)
	return silver >= int(silver_cost) and int(wood) >= int(wood_cost)


static func _array(source: Dictionary, key: String) -> Array:
	var value: Variant = source.get(key)
	return value if value is Array else []


static func _dict(source: Dictionary, key: String) -> Dictionary:
	var value: Variant = source.get(key)
	return value if value is Dictionary else {}


static func _count_text(value: Variant) -> String:
	return "—" if value == null else "%d" % int(value)


static func _text_or_dash(value: Variant) -> String:
	return "—" if value == null else str(value)


# В GDScript «or» возвращает bool, поэтому значение с запасным вариантом берётся через эти функции.
static func _text_or(value: Variant, fallback: String) -> String:
	var text := "" if value == null else str(value)
	return fallback if text.is_empty() else text


static func _int_or(value: Variant, fallback: int) -> int:
	return fallback if value == null else int(value)


static func _hms_text(value: Variant) -> String:
	return "--:--:--" if value == null else format_hms(int(value))


func _build_ui() -> void:
	_subtitle = _text("Уровень —", SUBTITLE_COLOR, 13)
	add_child(_subtitle)
	var tab_row := HBoxContainer.new()
	tab_row.add_theme_constant_override("separation", 5)
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
		button.custom_minimum_size = Vector2(0, 23)
		_style_tab_button(button)
		button.pressed.connect(_select_tab.bind(key))
		tab_row.add_child(button)
		_tab_buttons[key] = button
	add_child(_divider(DIVIDER_COLOR))
	_body = Control.new()
	_body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_body.custom_minimum_size = Vector2(0, BODY_MIN_HEIGHT)
	add_child(_body)
	_add_tab_panel("governor", _build_governor_panel())
	_add_tab_panel("population", _build_population_panel())
	_add_tab_panel("treasury", _build_treasury_panel())
	_add_tab_panel("tasks", _build_tasks_panel())
	_add_tab_panel("upgrades", _build_upgrades_panel())
	_build_confirm()
	_message_label = _text("", MESSAGE_OK_COLOR, 11)
	_message_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_message_label.visible = false
	add_child(_message_label)
	_select_tab(_tab)


func _add_tab_panel(key: String, panel: Control) -> void:
	panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	panel.visible = false
	_body.add_child(panel)
	_tab_panels[key] = panel


func _select_tab(key: String) -> void:
	_tab = key
	(_tab_buttons[key] as Button).button_pressed = true
	for panel_key in _tab_panels:
		(_tab_panels[panel_key] as Control).visible = panel_key == key
	_hide_confirm()
	_selected_citizen_id = -1
	_citizen_scroll.scroll_vertical = 0
	_refresh_worksites()


func _build_governor_panel() -> Control:
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 0)
	var header := HBoxContainer.new()
	box.add_child(header)
	header.add_child(_cell("Ресурс", GOVERNOR_RESOURCE_WIDTH, TITLE_COLOR, 11))
	header.add_child(_cell("Доход в час", GOVERNOR_INCOME_WIDTH, TITLE_COLOR, 11))
	header.add_child(_cell("Расход в час", GOVERNOR_CONSUMPTION_WIDTH, TITLE_COLOR, 11))
	header.add_child(_text("Тенденция", TITLE_COLOR, 11))
	box.add_child(_divider(RULE_COLOR))
	_governor_rows = VBoxContainer.new()
	box.add_child(_governor_rows)
	return box


func _build_population_panel() -> Control:
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 4)
	_summary_label = _text("", ZONE_DEFAULT_COLOR, 13)
	box.add_child(_summary_label)
	_zone_timer = _text("", ZONE_DEFAULT_COLOR, 11)
	box.add_child(_zone_timer)
	var frame := PanelContainer.new()
	frame.size_flags_vertical = Control.SIZE_EXPAND_FILL
	frame.add_theme_stylebox_override("panel", _box(Color(0, 0, 0, 0), FRAME_COLOR, 1, 3, 4))
	box.add_child(frame)
	_citizen_scroll = ScrollContainer.new()
	_citizen_scroll.custom_minimum_size = Vector2(0, 120)
	_citizen_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_style_scroll(_citizen_scroll)
	frame.add_child(_citizen_scroll)
	_citizen_rows = VBoxContainer.new()
	_citizen_rows.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_citizen_rows.add_theme_constant_override("separation", 3)
	_add_scroll_content(_citizen_scroll, _citizen_rows)
	_worksite_section = VBoxContainer.new()
	_worksite_section.add_theme_constant_override("separation", 4)
	box.add_child(_worksite_section)
	_worksite_section.add_child(_text("Куда отправить:", WORKSITE_CAPTION_COLOR, 11))
	_worksite_row = HBoxContainer.new()
	_worksite_row.add_theme_constant_override("separation", 5)
	_worksite_section.add_child(_worksite_row)
	return box


func _build_treasury_panel() -> Control:
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 4)
	var top := HBoxContainer.new()
	top.add_theme_constant_override("separation", 14)
	top.add_child(_text("Городская казна:", TITLE_COLOR, 13))
	_coin_row = HBoxContainer.new()
	_coin_row.add_theme_constant_override("separation", 22)
	top.add_child(_coin_row)
	box.add_child(top)
	_mayor_label = _text("Ты мэр города: можешь тратить всю казну на улучшения", TITLE_COLOR, 11)
	box.add_child(_mayor_label)
	_personal_label = _text("", PERSONAL_COLOR, 11)
	box.add_child(_personal_label)
	_tax_label = _text("", TAX_COLOR, 11)
	box.add_child(_tax_label)
	var gap := Control.new()
	gap.custom_minimum_size = Vector2(0, 10)
	box.add_child(gap)
	var buttons := HBoxContainer.new()
	buttons.add_theme_constant_override("separation", 8)
	box.add_child(buttons)
	var deposit := _button("ПОПОЛНИТЬ КАЗНУ", ACTION_BUTTON_SIZE, DEPOSIT_BG, DEPOSIT_HOVER_BG, BUTTON_TEXT_COLOR, 11)
	deposit.pressed.connect(_on_treasury_pressed.bind("treasury_deposit"))
	buttons.add_child(deposit)
	var withdraw := _button("ВЗЯТЬ С КАЗНЫ", ACTION_BUTTON_SIZE, WITHDRAW_BG, WITHDRAW_HOVER_BG, BUTTON_TEXT_COLOR, 11)
	withdraw.pressed.connect(_on_treasury_pressed.bind("treasury_withdraw"))
	buttons.add_child(withdraw)
	return box


func _build_tasks_panel() -> Control:
	var center := CenterContainer.new()
	center.add_child(_text("Заданий пока нет.", PLACEHOLDER_COLOR, 13))
	return center


func _build_upgrades_panel() -> Control:
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 6)
	box.add_child(_text("Улучшения замка", TITLE_COLOR, 13))
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_style_scroll(scroll)
	box.add_child(scroll)
	_upgrade_cards = VBoxContainer.new()
	_upgrade_cards.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_upgrade_cards.add_theme_constant_override("separation", 7)
	_add_scroll_content(scroll, _upgrade_cards)
	return box


# Подтверждение 500×210 px из castle_window.py: блокирует клики под собой, тексты заполняет _show_confirm.
func _build_confirm() -> void:
	_confirm_blocker = Control.new()
	_confirm_blocker.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_confirm_blocker.mouse_filter = Control.MOUSE_FILTER_STOP
	_confirm_blocker.visible = false
	_body.add_child(_confirm_blocker)
	_confirm_panel = PanelContainer.new()
	_confirm_panel.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	_confirm_panel.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_confirm_panel.grow_vertical = Control.GROW_DIRECTION_BOTH
	_confirm_panel.custom_minimum_size = CONFIRM_SIZE
	_confirm_panel.add_theme_stylebox_override("panel", _box(CONFIRM_BG, FRAME_COLOR, 2, 8, 10))
	_confirm_panel.visible = false
	_body.add_child(_confirm_panel)
	var box := VBoxContainer.new()
	box.alignment = BoxContainer.ALIGNMENT_CENTER
	box.add_theme_constant_override("separation", 8)
	_confirm_panel.add_child(box)
	_confirm_title = _text("", TITLE_COLOR, 13)
	_confirm_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(_confirm_title)
	_confirm_detail = _text("", CONFIRM_DETAIL_COLOR, 11)
	_confirm_detail.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(_confirm_detail)
	var buttons := HBoxContainer.new()
	buttons.alignment = BoxContainer.ALIGNMENT_CENTER
	buttons.add_theme_constant_override("separation", CONFIRM_BUTTON_GAP)
	box.add_child(buttons)
	_confirm_ok = _button("ОТПРАВИТЬ", CONFIRM_BUTTON_SIZE, CONFIRM_OK_BG, CONFIRM_OK_HOVER_BG, BUTTON_TEXT_COLOR, 11)
	_confirm_ok.pressed.connect(_on_confirm_pressed)
	buttons.add_child(_confirm_ok)
	var cancel := _button("ОТМЕНА", CONFIRM_BUTTON_SIZE, CONFIRM_CANCEL_BG, CONFIRM_CANCEL_HOVER_BG, BUTTON_TEXT_COLOR, 11)
	cancel.pressed.connect(_hide_confirm)
	buttons.add_child(cancel)


func _fill_governor() -> void:
	_clear(_governor_rows)
	var income: Variant = _state.get("city_resource_income_per_hour")
	var consumption: Variant = _state.get("city_resource_consumption_per_hour")
	var trends: Variant = _state.get("city_resource_trend")
	var resources := _resource_keys(income, consumption)
	if resources.is_empty():
		_governor_rows.add_child(_text("Нет текущего движения ресурсов.", EMPTY_COLOR, 11))
		return
	for resource_variant in resources:
		var resource := str(resource_variant)
		_governor_rows.add_child(_governor_row(resource, _rate(income, resource),
			_rate(consumption, resource), _trend_value(trends, resource)))


func _governor_row(resource: String, income: Variant, consumption: Variant, trend: Variant) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.custom_minimum_size = Vector2(0, 31)
	row.add_child(_cell(str(RESOURCE_LABELS.get(resource, resource)), GOVERNOR_RESOURCE_WIDTH, TEXT_COLOR, 13))
	row.add_child(_cell(_rate_text(income), GOVERNOR_INCOME_WIDTH, TEXT_COLOR, 13))
	row.add_child(_cell(_rate_text(consumption), GOVERNOR_CONSUMPTION_WIDTH, TEXT_COLOR, 13))
	row.add_child(_trend_cell(trend))
	return row


func _trend_cell(trend: Variant) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 5)
	var style: Array = TREND_STYLES.get(str(trend), []) if trend is String else []
	if style.is_empty():
		row.add_child(_text("—", EMPTY_COLOR, 11))
		return row
	row.add_child(_dot(style[0], TREND_DOT_SIZE))
	row.add_child(_text(str(style[1]), style[0], 11))
	return row


func _fill_population() -> void:
	var zone := _text_or(_state.get("food_zone"), "")
	var zone_color: Color = ZONE_COLORS.get(zone, ZONE_DEFAULT_COLOR)
	var summary := "Население %s / %s" % [_count_text(_state.get("population")), _count_text(_state.get("population_capacity"))]
	var food_status := _text_or(_state.get("food_status"), "")
	if not food_status.is_empty():
		summary += " (%s)" % food_status
	_summary_label.text = summary
	_summary_label.add_theme_color_override("font_color", zone_color)
	_fill_zone_timer(zone, zone_color)
	_fill_citizen_rows()
	_refresh_worksites()


func _fill_zone_timer(zone: String, zone_color: Color) -> void:
	var timer: Array = ZONE_TIMERS.get(zone, [])
	_zone_timer.visible = not timer.is_empty()
	if timer.is_empty():
		return
	_zone_timer.text = str(timer[1]) + _hms_text(_state.get(str(timer[0])))
	_zone_timer.add_theme_color_override("font_color", zone_color)


func _fill_citizen_rows() -> void:
	_clear(_citizen_rows)
	_travel_labels.clear()
	var citizens := _sorted_citizens(_array(_state, "citizens"))
	for index in range(citizens.size()):
		_citizen_rows.add_child(_citizen_row(citizens[index], index))


func _citizen_row(citizen: Dictionary, index: int) -> PanelContainer:
	var row := PanelContainer.new()
	var background := ROW_ALT_BG if index % 2 == 1 else ROW_BG
	row.add_theme_stylebox_override("panel", _box(background, background, 0, 0, 1))
	var line := HBoxContainer.new()
	line.add_theme_constant_override("separation", 0)
	row.add_child(line)
	line.add_child(_spacer(CITIZEN_NAME_INDENT))
	line.add_child(_cell(_text_or_dash(citizen.get("name")), CITIZEN_NAME_WIDTH, NAME_COLOR, 11))
	line.add_child(_satiety_column(citizen))
	line.add_child(_death_cell(citizen))
	line.add_child(_work_cell(citizen))
	line.add_child(_citizen_button(citizen))
	return row


func _satiety_column(citizen: Dictionary) -> VBoxContainer:
	var column := VBoxContainer.new()
	column.custom_minimum_size = Vector2(CITIZEN_METER_WIDTH, 0.0)
	column.add_theme_constant_override("separation", 2)
	var satiety: Variant = citizen.get("satiety")
	var meter_text := "—"
	var color := EMPTY_COLOR
	var meter := 0
	if satiety != null:
		var value := int(satiety)
		if value == 0:
			meter = _int_or(citizen.get("strong_hunger"), 0)
			meter_text = "Сильный голод %d%%" % meter
			color = STARVING_COLOR
		else:
			meter = value
			meter_text = "Сытность %d%%" % value
			color = _satiety_color(value)
	column.add_child(_text(meter_text, color, 11))
	var bar := ProgressBar.new()
	bar.show_percentage = false
	bar.min_value = 0.0
	bar.max_value = 100.0
	bar.value = float(meter)
	bar.custom_minimum_size = METER_SIZE
	bar.add_theme_stylebox_override("background", _box(METER_BG, METER_BG, 0, 2, 0))
	bar.add_theme_stylebox_override("fill", _box(color, color, 0, 2, 0))
	column.add_child(bar)
	return column


func _death_cell(citizen: Dictionary) -> Label:
	var satiety: Variant = citizen.get("satiety")
	var death_eta: Variant = citizen.get("death_eta_seconds")
	var death_text := ""
	if satiety != null and int(satiety) <= 10 and death_eta != null:
		death_text = "Смерть через %s" % format_hms(int(death_eta))
	return _cell(death_text, CITIZEN_DEATH_WIDTH, SATIETY_LOW_COLOR, 11)


func _work_cell(citizen: Dictionary) -> Label:
	var status := _text_or(citizen.get("work_status"), "")
	var worksite := str(WORKSITE_LABELS.get(_text_or(citizen.get("job_building"), ""), ""))
	var prefix := status if worksite.is_empty() else "%s · %s" % [worksite, status]
	var label := _cell(prefix, 0.0, WORK_COLORS.get(status, WORK_DEFAULT_COLOR), 11)
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var seconds: Variant = citizen.get("travel_seconds_left")
	if not _text_or(citizen.get("travel_direction"), "").is_empty() and seconds != null:
		_travel_labels.append({"label": label, "prefix": prefix, "seconds": float(seconds)})
	return label


# Таймер пути идёт между обновлениями, как в Python: остаток = travel_seconds_left − прошедшее время.
func _update_travel_labels() -> void:
	var elapsed := (Time.get_ticks_msec() - _received_msec) / 1000.0
	for entry in _travel_labels:
		var label: Label = entry["label"]
		var seconds := maxi(0, int(float(entry["seconds"]) - elapsed))
		label.text = "%s %s" % [entry["prefix"], format_hms(seconds)]


func _citizen_button(citizen: Dictionary) -> Button:
	var citizen_id := int(citizen.get("id", -1))
	var is_convoy := _text_or(citizen.get("work_status"), "") == "Ведёт повозку"
	var has_job := not _text_or(citizen.get("job_building"), "").is_empty()
	var label := "В РЕЙСЕ" if is_convoy else ("ДОМОЙ" if has_job else "НАЗНАЧИТЬ")
	if _text_or(citizen.get("travel_direction"), "") == "returning":
		label = "В ПУТИ ДОМОЙ"
	var background := ASSIGN_BG if label == "НАЗНАЧИТЬ" else HOME_BG
	var button := _button(label, CITIZEN_BUTTON_SIZE, background, CITIZEN_HOVER_BG, BUTTON_TEXT_COLOR, 11)
	button.disabled = is_convoy
	if not is_convoy:
		button.pressed.connect(_on_citizen_action.bind(citizen_id))
	return button


func _on_citizen_action(citizen_id: int) -> void:
	var citizen := _find_citizen(citizen_id)
	if citizen.is_empty():
		return
	var job := _text_or(citizen.get("job_building"), "")
	if not job.is_empty():
		if _text_or(citizen.get("travel_direction"), "") == "returning":
			set_message("Горожанин уже возвращается в город.", true)
		else:
			_show_confirm({"kind": "recall", "citizen_id": citizen_id})
	elif _citizen_is_free(citizen):
		_selected_citizen_id = citizen_id
		_refresh_worksites()
	else:
		set_message("Горожанин сейчас не свободен.", true)


# Варианты работы берутся из поля worksites ответа; кнопки видны, пока выбран свободный горожанин.
func _refresh_worksites() -> void:
	_worksite_section.visible = _selected_citizen_id >= 0
	_clear(_worksite_row)
	if not _worksite_section.visible:
		return
	for site in _array(_state, "worksites"):
		if site is Dictionary:
			_worksite_row.add_child(_worksite_button(site))


func _worksite_button(site: Dictionary) -> Button:
	var free_slots := _array(site, "free_slots")
	var has_free := not free_slots.is_empty()
	var background := WORKSITE_FREE_BG if has_free else WORKSITE_FULL_BG
	var hover := WORKSITE_FREE_HOVER_BG if has_free else WORKSITE_FULL_BG
	var button := Button.new()
	button.custom_minimum_size = Vector2(0, WORKSITE_BUTTON_HEIGHT)
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.focus_mode = Control.FOCUS_NONE
	button.add_theme_stylebox_override("normal", _box(background, WORKSITE_BORDER, 1, 6, 0))
	button.add_theme_stylebox_override("hover", _box(hover, WORKSITE_BORDER, 1, 6, 0))
	button.add_theme_stylebox_override("pressed", _box(hover, WORKSITE_BORDER, 1, 6, 0))
	var captions := VBoxContainer.new()
	captions.alignment = BoxContainer.ALIGNMENT_CENTER
	captions.mouse_filter = Control.MOUSE_FILTER_IGNORE
	captions.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	button.add_child(captions)
	var name_label := _text(_text_or_dash(site.get("name")), WORKSITE_NAME_COLOR, 11)
	name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	captions.add_child(name_label)
	var count_label := _text(_occupancy_text(site, free_slots.size()), WORKSITE_COUNT_COLOR, 11)
	count_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	captions.add_child(count_label)
	button.pressed.connect(_on_worksite_pressed.bind(_text_or(site.get("building"), "")))
	return button


func _on_worksite_pressed(building: String) -> void:
	var site := _find_worksite(building)
	var free_slots := _array(site, "free_slots")
	if site.is_empty() or free_slots.is_empty():
		set_message("Нет свободных рабочих мест на этом объекте.", true)
		return
	_show_confirm({
		"kind": "assign",
		"citizen_id": _selected_citizen_id,
		"worksite_key": building,
		"slot_index": int(free_slots[0]),
	})


func _show_confirm(pending: Dictionary) -> void:
	_pending = pending
	var citizen := _find_citizen(int(pending["citizen_id"]))
	var citizen_name := _text_or(citizen.get("name"), "горожанина")
	if pending["kind"] == "assign":
		var site := _find_worksite(str(pending["worksite_key"]))
		_confirm_title.text = "Отправить %s на работу?" % citizen_name
		_confirm_detail.text = "%s · путь в одну сторону: %s" % [_text_or(site.get("name"), ""), _hms_text(site.get("travel_seconds"))]
		_confirm_ok.text = "ОТПРАВИТЬ"
	else:
		var home := _find_worksite(_text_or(citizen.get("job_building"), ""))
		_confirm_title.text = "Вернуть %s в город?" % citizen_name
		_confirm_detail.text = "Путь домой: %s" % _hms_text(home.get("travel_seconds"))
		_confirm_ok.text = "ВЕРНУТЬ"
	_confirm_blocker.visible = true
	_confirm_panel.visible = true


func _hide_confirm() -> void:
	_pending = {}
	_confirm_blocker.visible = false
	_confirm_panel.visible = false


func _on_confirm_pressed() -> void:
	var pending := _pending
	_hide_confirm()
	if pending["kind"] == "assign":
		action_requested.emit("assign_citizen", {
			"citizen_id": pending["citizen_id"],
			"worksite_key": pending["worksite_key"],
			"slot_index": pending["slot_index"],
		})
	else:
		action_requested.emit("recall_citizen", {"citizen_id": pending["citizen_id"]})


func _clear_invalid_selection() -> void:
	var citizen := _find_citizen(_selected_citizen_id)
	if citizen.is_empty() or not _citizen_is_free(citizen):
		_selected_citizen_id = -1


func _fill_treasury() -> void:
	_clear(_coin_row)
	var treasury := _dict(_state, "treasury")
	for key in ["copper", "silver", "gold"]:
		_coin_row.add_child(_coin_entry(COIN_COLORS[key], _count_text(treasury.get(key)), 13))
	_mayor_label.visible = _state.get("is_mayor") == true
	_personal_label.text = "Твой вклад: %s (можно забрать только свой вклад)" % _text_or_dash(_state.get("personal_treasury_text"))
	_tax_label.text = "До сбора налогов: %s (ожидается: %s)" % [
		_hms_text(_state.get("tax_tick_seconds_left")), _text_or_dash(_state.get("expected_tax_text")),
	]


# Максимум перевода как в castle_window.py: взнос — personal_currency_copper, выдача — personal_treasury_copper.
func _on_treasury_pressed(action: String) -> void:
	var key := "personal_currency_copper" if action == "treasury_deposit" else "personal_treasury_copper"
	var maximum := _int_or(_state.get(key), 0)
	if maximum <= 0:
		set_message("Нет доступных монет для перевода.", true)
		return
	action_requested.emit(action, {"maximum_copper": maximum})


func _fill_upgrades() -> void:
	_clear(_upgrade_cards)
	var copper: Variant = _state.get("spendable_treasury_copper", _state.get("personal_treasury_copper"))
	var wood: Variant = _dict(_state, "city_resource_storage").get("wood")
	for upgrade in _array(_state, "upgrades"):
		if upgrade is Dictionary:
			_upgrade_cards.add_child(_upgrade_card(upgrade, copper, wood))


func _upgrade_card(upgrade: Dictionary, copper: Variant, wood: Variant) -> PanelContainer:
	var is_complete: bool = upgrade.get("is_complete") == true
	var is_active: bool = upgrade.get("is_active") == true
	var can_start := not is_complete and not is_active and _can_afford(upgrade, copper, wood)
	var card := PanelContainer.new()
	card.add_theme_stylebox_override("panel", _box(UPGRADE_BG, UPGRADE_READY_BORDER if can_start else UPGRADE_LOCKED_BORDER, 1, 8, 8))
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 3)
	card.add_child(box)
	box.add_child(_text(_text_or_dash(upgrade.get("name")), UPGRADE_NAME_COLOR, 13))
	box.add_child(_text("Требование: %s" % _text_or_dash(upgrade.get("requirement")), REQUIREMENT_COLOR, 11))
	box.add_child(_text("Результат: %s" % _text_or_dash(upgrade.get("result")), RESULT_COLOR, 11))
	box.add_child(_text("Время улучшения: %s" % _hms_text(upgrade.get("time_seconds")), UPGRADE_TIME_COLOR, 11))
	var footer := HBoxContainer.new()
	footer.add_theme_constant_override("separation", 12)
	box.add_child(footer)
	footer.add_child(_price_row(upgrade, copper, wood))
	var filler := Control.new()
	filler.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	footer.add_child(filler)
	footer.add_child(_upgrade_status(upgrade, is_complete, is_active, can_start, _text_or(upgrade.get("id"), "")))
	return card


func _price_row(upgrade: Dictionary, copper: Variant, wood: Variant) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	row.add_child(_text("Твой вклад:", PRICE_COLOR, 11))
	row.add_child(_coins_row(copper))
	row.add_child(_text("/ %s серебра" % _count_text(upgrade.get("silver_cost")), PRICE_COLOR, 11))
	row.add_child(_dot(WOOD_COLOR, COIN_DOT_SIZE))
	row.add_child(_text("%s/%s древесины" % [_count_text(wood), _count_text(upgrade.get("wood_cost"))], PRICE_COLOR, 11))
	return row


func _coins_row(copper: Variant) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	var parts := _coin_parts(copper)
	var keys := ["gold", "silver", "copper"]
	for index in range(keys.size()):
		var amount := "—" if parts.is_empty() else str(parts[index])
		row.add_child(_coin_entry(COIN_COLORS[keys[index]], amount, 11))
	return row


func _coin_entry(color: Color, value_text: String, font_size: int) -> HBoxContainer:
	var entry := HBoxContainer.new()
	entry.add_theme_constant_override("separation", 5)
	entry.add_child(_dot(color, COIN_DOT_SIZE))
	entry.add_child(_text(value_text, COIN_TEXT_COLOR, font_size))
	return entry


func _upgrade_status(upgrade: Dictionary, is_complete: bool, is_active: bool, can_start: bool, upgrade_id: String) -> Control:
	if is_complete:
		return _status_label("УСТАНОВЛЕНО", DONE_COLOR)
	if is_active:
		return _status_label("Осталось: %s" % _hms_text(upgrade.get("seconds_left")), TIMER_COLOR)
	var background := START_BG if can_start else LOCKED_BG
	var text_color := START_TEXT_COLOR if can_start else LOCKED_TEXT_COLOR
	var button := _button("НАЧАТЬ" if can_start else "НЕДОСТАТОЧНО", UPGRADE_BUTTON_SIZE, background, background, text_color, 11)
	button.disabled = not can_start
	button.pressed.connect(_on_upgrade_pressed.bind(upgrade_id))
	return button


func _on_upgrade_pressed(upgrade_id: String) -> void:
	action_requested.emit("upgrade_start", {"upgrade_id": upgrade_id})


func _status_label(value: String, color: Color) -> Label:
	var label := _text(value, color, 11)
	label.custom_minimum_size = UPGRADE_BUTTON_SIZE
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	return label


func _find_citizen(citizen_id: int) -> Dictionary:
	for citizen in _array(_state, "citizens"):
		if citizen is Dictionary and int(citizen.get("id", -1)) == citizen_id:
			return citizen
	return {}


func _find_worksite(building: String) -> Dictionary:
	for site in _array(_state, "worksites"):
		if site is Dictionary and _text_or(site.get("building"), "") == building:
			return site
	return {}


func _style_tab_button(button: Button) -> void:
	button.add_theme_stylebox_override("normal", _box(TAB_BG, TAB_BG, 0, 6, 4))
	button.add_theme_stylebox_override("hover", _box(TAB_HOVER_BG, TAB_HOVER_BG, 0, 6, 4))
	button.add_theme_stylebox_override("pressed", _box(TAB_ACTIVE_BG, TAB_ACTIVE_BG, 0, 6, 4))
	button.add_theme_stylebox_override("hover_pressed", _box(TAB_HOVER_BG, TAB_HOVER_BG, 0, 6, 4))
	button.add_theme_stylebox_override("focus", _box(TAB_BG, TAB_BG, 0, 6, 4))
	button.add_theme_color_override("font_color", BUTTON_TEXT_COLOR)
	button.add_theme_color_override("font_hover_color", BUTTON_TEXT_COLOR)
	button.add_theme_color_override("font_pressed_color", BUTTON_TEXT_COLOR)
	button.add_theme_color_override("font_hover_pressed_color", BUTTON_TEXT_COLOR)
	button.add_theme_color_override("font_focus_color", BUTTON_TEXT_COLOR)
	button.add_theme_font_size_override("font_size", 11)


func _button(text: String, minimum: Vector2, background: Color, hover: Color, text_color: Color, font_size: int) -> Button:
	var button := Button.new()
	button.text = text
	button.custom_minimum_size = minimum
	button.focus_mode = Control.FOCUS_NONE
	button.add_theme_stylebox_override("normal", _box(background, background, 0, 6, 3))
	button.add_theme_stylebox_override("hover", _box(hover, hover, 0, 6, 3))
	button.add_theme_stylebox_override("pressed", _box(hover, hover, 0, 6, 3))
	button.add_theme_stylebox_override("disabled", _box(background, background, 0, 6, 3))
	button.add_theme_color_override("font_color", text_color)
	button.add_theme_color_override("font_hover_color", text_color)
	button.add_theme_color_override("font_pressed_color", text_color)
	button.add_theme_color_override("font_disabled_color", text_color)
	button.add_theme_font_size_override("font_size", font_size)
	return button


func _style_scroll(scroll: ScrollContainer) -> void:
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	var bar := scroll.get_v_scroll_bar()
	bar.custom_minimum_size = Vector2(SCROLL_BAR_WIDTH, 0.0)
	bar.add_theme_stylebox_override("scroll", _box(SCROLL_TRACK_BG, SCROLL_TRACK_BORDER, 1, 4, 0))
	bar.add_theme_stylebox_override("grabber", _box(SCROLL_THUMB, SCROLL_THUMB, 0, 4, 0))
	bar.add_theme_stylebox_override("grabber_highlight", _box(SCROLL_THUMB_ACTIVE, SCROLL_THUMB_ACTIVE, 0, 4, 0))
	bar.add_theme_stylebox_override("grabber_pressed", _box(SCROLL_THUMB_ACTIVE, SCROLL_THUMB_ACTIVE, 0, 4, 0))


# Отступ справа, чтобы полоса прокрутки не перекрывала строки и карточки.
func _add_scroll_content(scroll: ScrollContainer, content: Control) -> void:
	var margin := MarginContainer.new()
	margin.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	margin.add_theme_constant_override("margin_right", SCROLL_CONTENT_RIGHT_MARGIN)
	margin.add_child(content)
	scroll.add_child(margin)


func _text(value: String, color: Color, font_size: int) -> Label:
	var label := Label.new()
	label.text = value
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	return label


func _cell(value: String, width: float, color: Color, font_size: int) -> Label:
	var label := _text(value, color, font_size)
	label.custom_minimum_size = Vector2(width, 0.0)
	label.clip_text = true
	return label


func _spacer(width: float) -> Control:
	var spacer := Control.new()
	spacer.custom_minimum_size = Vector2(width, 0.0)
	spacer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return spacer


# Кружок как световой индикатор тенденции из castle_window.py и монета-заглушка вместо иконки.
func _dot(color: Color, diameter: float) -> Control:
	var dot := Control.new()
	dot.custom_minimum_size = Vector2(diameter, diameter)
	dot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	dot.draw.connect(_draw_dot.bind(dot, color))
	return dot


func _draw_dot(dot: Control, color: Color) -> void:
	var center := dot.size * 0.5
	var radius := dot.size.x * 0.5
	dot.draw_circle(center, radius * 0.92, Color(color, 0.21))
	dot.draw_circle(center, radius * 0.46, color)


func _box(bg: Color, border: Color, border_width: int, radius: int, margin: int) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = bg
	style.border_color = border
	style.set_border_width_all(border_width)
	style.set_corner_radius_all(radius)
	style.set_content_margin_all(margin)
	return style


func _divider(color: Color) -> ColorRect:
	var rule := ColorRect.new()
	rule.color = color
	rule.custom_minimum_size = Vector2(0, 1)
	return rule


func _clear(container: Node) -> void:
	for child in container.get_children():
		container.remove_child(child)
		child.queue_free()
