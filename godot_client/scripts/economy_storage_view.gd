extends VBoxContainer

signal action_requested(action: String, payload: Dictionary)

# Амбар и склад из ui/city_storage_window.py: вкладки СКЛАД и УЛУЧШЕНИЕ, заполненность каждого товара и улучшение здания.
# Вид не делает HTTP. По action_requested родитель открывает диалог количества или запускает улучшение:
#   "storage_withdraw" с payload {"resource": String, "quantity": int}; quantity — запас товара в здании, верхняя граница диалога;
#   "storage_deposit" с payload {"resource": String}; количество выбирается в диалоге из рюкзака;
#   "upgrade_building" с payload {}; родитель запускает улучшение.

# set_state(state) принимает поле "building" ответа GET /api/buildings/{barn|warehouse}/{id}:
#   building: "barn" или "warehouse"; по нему берутся название окна и единица измерения;
#   level: уровень, подпись «Уровень N»;
#   storage: {resource: int, ..., limit: int}; limit — вместимость каждого товара на текущем уровне;
#   storage_depositable: {resource: {max_deposit: int, ...}}; кнопка ВНЕСТИ показывается, если max_deposit > 0;
#   city_upgrade.charging_resources: [resource], необязательно; шкалы этих товаров мигают;
#   upgrade: {next_level, time_seconds, materials: [{name, required, deposited, in_warehouse, remaining}], ready, in_progress, seconds_left} или null на максимальном уровне;
#   upgrade.storage_limit: int, необязательно; вместимость следующего уровня. В ответе сервера этого поля пока нет, поэтому строка вместимости не выводится.

const STORAGE_METER_SCRIPT := preload("res://scripts/storage_meter.gd")
const WINDOW_SIZE := Vector2(600, 507)
const BORDER_COLOR := Color8(220, 185, 70)
const BACKGROUND_COLOR := Color8(24, 26, 18)
const BUILDINGS := {
	"barn": {"name": "Амбар", "unit": "продукции"},
	"warehouse": {"name": "Склад", "unit": "материалов"},
}
const TABS := [
	["storage", "СКЛАД"],
	["upgrade", "УЛУЧШЕНИЕ"],
]
# Товары из core/production_buildings.py в порядке Python; цветная метка заменяет иконку, которой в Godot нет.
const GOODS := {
	"berries": {"name": "Ягоды", "color": Color8(120, 60, 140)},
	"wheat": {"name": "Пшеница", "color": Color8(214, 178, 72)},
	"meat": {"name": "Мясо", "color": Color8(170, 40, 40)},
	"wood": {"name": "Древесина", "color": Color8(139, 94, 52)},
	"board": {"name": "Доска", "color": Color8(186, 130, 72)},
	"flax": {"name": "Лён", "color": Color8(214, 205, 150)},
	"cotton": {"name": "Хлопок", "color": Color8(236, 236, 226)},
	"leather": {"name": "Кожа", "color": Color8(160, 100, 60)},
	"coal": {"name": "Уголь", "color": Color8(60, 60, 64)},
	"stone": {"name": "Камень", "color": Color8(128, 128, 124)},
	"iron": {"name": "Железная руда", "color": Color8(140, 90, 70)},
	"mithril": {"name": "Мифриловая руда", "color": Color8(70, 170, 200)},
	"obsidian": {"name": "Обсидиановая порода", "color": Color8(110, 70, 140)},
	"iron_ingot": {"name": "Железо", "color": Color8(190, 196, 204)},
	"steel": {"name": "Сталь", "color": Color8(150, 190, 220)},
	"hard_leather": {"name": "Крепкая кожа", "color": Color8(120, 74, 44)},
	"thick_leather": {"name": "Толстая кожа", "color": Color8(150, 96, 60)},
	"cloth": {"name": "Ткань", "color": Color8(120, 150, 190)},
	"stone_block": {"name": "Каменный блок", "color": Color8(150, 150, 150)},
	"jet": {"name": "Гагат", "color": Color8(40, 40, 50)},
	"malachite": {"name": "Малахит", "color": Color8(40, 160, 110)},
	"topaz": {"name": "Топаз", "color": Color8(240, 180, 50)},
	"garnet": {"name": "Гранат", "color": Color8(150, 30, 50)},
	"emerald": {"name": "Изумруд", "color": Color8(40, 190, 100)},
	"ruby": {"name": "Рубин", "color": Color8(210, 40, 60)},
	"sapphire": {"name": "Сапфир", "color": Color8(50, 90, 210)},
	"diamond": {"name": "Алмаз", "color": Color8(220, 240, 250)},
}
const UNKNOWN_SWATCH := Color8(120, 120, 120)
const TAB_SIZE := Vector2(127, 20)
const TAB_BG := Color8(47, 51, 51)
const TAB_HOVER_BG := Color8(105, 138, 153)
const TAB_ACTIVE_BG := Color8(80, 111, 126)
const TAB_TEXT := Color8(178, 184, 181)
const TAB_ACTIVE_TEXT := Color8(230, 237, 235)
const SUBTITLE_COLOR := Color8(215, 205, 170)
const TITLE_COLOR := Color8(255, 225, 130)
const DIVIDER_COLOR := Color8(100, 90, 55)
const HEADER_BG := Color8(44, 46, 34)
const ROW_ODD_BG := Color8(32, 34, 26)
const ROW_EVEN_BG := Color8(38, 40, 30)
const ROW_HEIGHT := 24.0
const TABLE_MAX_HEIGHT := 300.0
const NAME_WIDTH := 152.0
const AMOUNT_WIDTH := 88.0
const WITHDRAW_WIDTH := 64.0
const DEPOSIT_WIDTH := 70.0
const NAME_COLOR := Color8(215, 215, 205)
const AMOUNT_COLOR := Color8(235, 235, 225)
const WITHDRAW_BG := Color8(69, 98, 72)
const DEPOSIT_BG := Color8(68, 112, 60)
const ACTION_TEXT := Color8(235, 245, 230)
const ACTION_HOVER_BG := Color8(110, 190, 255)
const ERROR_COLOR := Color8(240, 150, 120)
const MAX_LEVEL_COLOR := Color8(195, 195, 175)
const CAPTION_COLOR := Color8(190, 195, 180)
const NOTE_COLOR := Color8(220, 210, 170)
const MATERIAL_DONE_COLOR := Color8(140, 230, 140)
const MATERIAL_PENDING_COLOR := Color8(230, 200, 120)
const BUILDING_COLOR := Color8(120, 190, 240)
const UPGRADE_SIZE := Vector2(167, 28)
const UPGRADE_BG := Color8(80, 140, 85)
const UPGRADE_HOVER_BG := Color8(110, 180, 110)
const UPGRADE_OFF_BG := Color8(55, 55, 60)
const UPGRADE_OFF_TEXT := Color8(150, 150, 155)

var _tab := "storage"
var _building := ""
var _storage: Dictionary = {}
var _depositable: Dictionary = {}
var _charging: Array = []
var _upgrade: Dictionary = {}
var _seconds_left := 0
var _elapsed := 0.0
var _tab_buttons: Dictionary = {}
var _subtitle: Label
var _message_label: Label
var _body: VBoxContainer
var _table_scroll: ScrollContainer
var _rows: VBoxContainer
var _clock_label: Label


func _init() -> void:
	add_theme_constant_override("separation", 6)
	_build_ui()


func window_title() -> String:
	return str(_building_info().get("name", ""))


func set_state(state: Dictionary) -> void:
	_building = str(state.get("building", ""))
	_subtitle.text = "Уровень %d" % int(state.get("level", 1))
	_storage = _dict(state.get("storage", {}))
	_depositable = _dict(state.get("storage_depositable", {}))
	_charging = _array(_dict(state.get("city_upgrade", {})).get("charging_resources", []))
	_upgrade = _dict(state.get("upgrade", {}))
	var seconds_left: Variant = _upgrade.get("seconds_left")
	_seconds_left = int(seconds_left) if seconds_left != null else 0
	_elapsed = 0.0
	_render_tab()


func set_message(text: String) -> void:
	_message_label.text = text
	_message_label.visible = not text.is_empty()


func _process(delta: float) -> void:
	_elapsed += delta
	_update_clock()


# Как format_duration в ui/production_building_window.py: часы и минуты, без секунд.
static func format_duration(seconds: int) -> String:
	var total := maxi(0, seconds)
	var hours := floori(float(total) / 3600.0)
	var minutes := floori(float(total % 3600) / 60.0)
	if hours > 0:
		return "%d ч %d мин" % [hours, minutes]
	return "%d мин" % minutes


# Как format_clock в ui/production_building_window.py.
static func format_clock(seconds: int) -> String:
	var total := maxi(0, seconds)
	var hours := floori(float(total) / 3600.0)
	var minutes := floori(float(total % 3600) / 60.0)
	return "%d ч %02d м %02d с" % [hours, minutes, total % 60]


func _build_ui() -> void:
	_subtitle = _text("", SUBTITLE_COLOR, 13)
	add_child(_subtitle)
	var tab_row := HBoxContainer.new()
	tab_row.add_theme_constant_override("separation", 4)
	add_child(tab_row)
	var group := ButtonGroup.new()
	for entry in _tab_entries():
		var key := str(entry[0])
		var button := Button.new()
		button.text = str(entry[1])
		button.toggle_mode = true
		button.button_group = group
		button.clip_text = true
		button.custom_minimum_size = TAB_SIZE
		button.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
		_style_tab_button(button)
		button.pressed.connect(_select_tab.bind(key))
		tab_row.add_child(button)
		_tab_buttons[key] = button
	_message_label = _text("", ERROR_COLOR, 11)
	_message_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_message_label.visible = false
	add_child(_message_label)
	add_child(_divider(DIVIDER_COLOR))
	_body = VBoxContainer.new()
	_body.add_theme_constant_override("separation", 6)
	add_child(_body)
	(_tab_buttons[_tab] as Button).button_pressed = true
	_render_tab()


# Производственное окно добавляет свою первую вкладку через этот метод.
func _tab_entries() -> Array:
	return TABS


func select_tab(key: String) -> void:
	_select_tab(key)


func _select_tab(key: String) -> void:
	_tab = key
	(_tab_buttons[key] as Button).button_pressed = true
	_render_tab()


func _render_tab() -> void:
	_clock_label = null
	_clear(_body)
	if _tab == "upgrade":
		_render_upgrade()
	else:
		_render_storage()


func _render_storage() -> void:
	var table := PanelContainer.new()
	table.add_theme_stylebox_override("panel", _box(Color(0.0, 0.0, 0.0, 0.0), DIVIDER_COLOR, 1, 0, 0.0, 0.0))
	_body.add_child(table)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 0)
	table.add_child(column)
	var header := PanelContainer.new()
	header.add_theme_stylebox_override("panel", _box(HEADER_BG, HEADER_BG, 0, 0, 8.0, 2.0))
	header.add_child(_text("Товары:", TITLE_COLOR, 13))
	column.add_child(header)
	_table_scroll = ScrollContainer.new()
	_table_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	column.add_child(_table_scroll)
	_rows = VBoxContainer.new()
	_rows.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_rows.add_theme_constant_override("separation", 0)
	_table_scroll.add_child(_rows)
	var goods := _goods()
	for index in range(goods.size()):
		_rows.add_child(_goods_row(goods[index], index))
	_table_scroll.custom_minimum_size.y = minf(goods.size() * ROW_HEIGHT, TABLE_MAX_HEIGHT)


# Товары из state: сначала известные в порядке Python, затем неизвестные ключи; служебный limit пропускается.
func _goods() -> Array[String]:
	var keys: Array[String] = []
	for resource in GOODS:
		if _storage.has(resource):
			keys.append(str(resource))
	for resource in _storage:
		if str(resource) != "limit" and not keys.has(str(resource)):
			keys.append(str(resource))
	return keys


func _goods_row(resource: String, index: int) -> PanelContainer:
	var good: Dictionary = GOODS.get(resource, {"name": resource, "color": UNKNOWN_SWATCH})
	var amount := int(_storage.get(resource, 0))
	var limit := int(_storage.get("limit", 0))
	var background := ROW_ODD_BG if index % 2 == 1 else ROW_EVEN_BG
	var row := PanelContainer.new()
	row.custom_minimum_size.y = ROW_HEIGHT
	row.add_theme_stylebox_override("panel", _box(background, background, 0, 0, 8.0, 0.0))
	var line := HBoxContainer.new()
	line.add_theme_constant_override("separation", 6)
	row.add_child(line)
	var swatch := ColorRect.new()
	swatch.color = good["color"]
	swatch.custom_minimum_size = Vector2(14, 14)
	swatch.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	line.add_child(swatch)
	var name_label := _text(str(good["name"]), NAME_COLOR, 13)
	name_label.custom_minimum_size.x = NAME_WIDTH
	name_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	line.add_child(name_label)
	var meter := STORAGE_METER_SCRIPT.new()
	meter.custom_minimum_size = Vector2(60, 12)
	meter.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	meter.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	meter.set_values(amount, limit, _charging.has(resource))
	line.add_child(meter)
	var amount_label := _text("%d / %d" % [amount, limit], AMOUNT_COLOR, 13)
	amount_label.custom_minimum_size.x = AMOUNT_WIDTH
	amount_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	amount_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	line.add_child(amount_label)
	line.add_child(_action_slot("ВЗЯТЬ", WITHDRAW_WIDTH, WITHDRAW_BG, amount > 0,
		_on_withdraw_pressed.bind(resource, amount)))
	line.add_child(_action_slot("ВНЕСТИ", DEPOSIT_WIDTH, DEPOSIT_BG, _max_deposit(resource) > 0,
		_on_deposit_pressed.bind(resource)))
	return row


func _max_deposit(resource: String) -> int:
	return int(_dict(_depositable.get(resource, {})).get("max_deposit", 0))


# Слот фиксированной ширины: без кнопки строки остаются выровненными, как в Python.
func _action_slot(text: String, width: float, color: Color, shown: bool, callback: Callable) -> Control:
	var slot := Control.new()
	slot.custom_minimum_size = Vector2(width, ROW_HEIGHT)
	slot.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	if shown:
		var button := Button.new()
		button.text = text
		button.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		_style_button(button, color, ACTION_HOVER_BG, ACTION_TEXT)
		button.pressed.connect(callback)
		slot.add_child(button)
	return slot


func _on_withdraw_pressed(resource: String, amount: int) -> void:
	action_requested.emit("storage_withdraw", {"resource": resource, "quantity": amount})


func _on_deposit_pressed(resource: String) -> void:
	action_requested.emit("storage_deposit", {"resource": resource})


func _render_upgrade() -> void:
	if _upgrade.is_empty():
		_body.add_child(_text("Здание достигло максимального уровня", MAX_LEVEL_COLOR, 13))
		return
	_body.add_child(_text("Улучшение до уровня %d — время стройки %s" % [
		int(_upgrade.get("next_level", 0)),
		format_duration(int(_upgrade.get("time_seconds", 0))),
	], TITLE_COLOR, 13))
	var description := _upgrade_description()
	if not description.is_empty():
		_body.add_child(_text(description, CAPTION_COLOR, 11))
	var storage_limit: Variant = _upgrade.get("storage_limit")
	if storage_limit != null:
		_body.add_child(_text("Вместимость каждого товара: %d %s" % [
			int(storage_limit),
			str(_building_info().get("unit", "")),
		], CAPTION_COLOR, 11))
	_body.add_child(_text("Материалы списываются с общего склада", NOTE_COLOR, 11))
	for material_variant in _array(_upgrade.get("materials", [])):
		_body.add_child(_material_label(_dict(material_variant)))
	if bool(_upgrade.get("in_progress", false)):
		_clock_label = _text("", BUILDING_COLOR, 13)
		_body.add_child(_clock_label)
		_update_clock()
		return
	var button := Button.new()
	button.text = "УЛУЧШИТЬ"
	button.custom_minimum_size = UPGRADE_SIZE
	button.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	button.disabled = not bool(_upgrade.get("ready", false))
	_style_button(button, UPGRADE_BG, UPGRADE_HOVER_BG, Color.WHITE)
	button.add_theme_stylebox_override("disabled", _box(UPGRADE_OFF_BG, UPGRADE_OFF_BG, 0, 5, 6.0, 4.0))
	button.add_theme_color_override("font_disabled_color", UPGRADE_OFF_TEXT)
	button.pressed.connect(_on_upgrade_pressed.bind(button))
	_body.add_child(button)


# Описание следующего уровня под заголовком улучшения; производственное окно переопределяет его production_desc.
func _upgrade_description() -> String:
	return ""


func _material_label(material: Dictionary) -> Label:
	var deposited := int(material.get("deposited", 0))
	var in_warehouse := int(material.get("in_warehouse", 0))
	var required := int(material.get("required", 0))
	var remaining := int(material.get("remaining", required - deposited))
	var credit := ", ранее оплачено %d" % deposited if deposited > 0 else ""
	var done := deposited + in_warehouse >= required
	return _text("%s: склад %d/%d%s" % [str(material.get("name", "")), in_warehouse, remaining, credit],
		MATERIAL_DONE_COLOR if done else MATERIAL_PENDING_COLOR, 11)


func _on_upgrade_pressed(button: Button) -> void:
	if button.disabled:
		return
	action_requested.emit("upgrade_building", {})


func _update_clock() -> void:
	if _clock_label != null:
		_clock_label.text = "Идёт стройка: осталось %s" % format_clock(int(_seconds_left - _elapsed))


func _building_info() -> Dictionary:
	return _dict(BUILDINGS.get(_building, {}))


func _style_tab_button(button: Button) -> void:
	button.add_theme_stylebox_override("normal", _box(TAB_BG, TAB_BG, 0, 5, 6.0, 2.0))
	button.add_theme_stylebox_override("hover", _box(TAB_HOVER_BG, TAB_HOVER_BG, 0, 5, 6.0, 2.0))
	button.add_theme_stylebox_override("pressed", _box(TAB_ACTIVE_BG, TAB_ACTIVE_BG, 0, 5, 6.0, 2.0))
	button.add_theme_stylebox_override("hover_pressed", _box(TAB_ACTIVE_BG, TAB_ACTIVE_BG, 0, 5, 6.0, 2.0))
	button.add_theme_stylebox_override("focus", _box(TAB_BG, TAB_BG, 0, 5, 6.0, 2.0))
	button.add_theme_color_override("font_color", TAB_TEXT)
	button.add_theme_color_override("font_hover_color", TAB_ACTIVE_TEXT)
	button.add_theme_color_override("font_pressed_color", TAB_ACTIVE_TEXT)
	button.add_theme_color_override("font_hover_pressed_color", TAB_ACTIVE_TEXT)
	button.add_theme_color_override("font_focus_color", TAB_TEXT)
	button.add_theme_font_size_override("font_size", 11)


func _style_button(button: Button, bg: Color, hover_bg: Color, text_color: Color) -> void:
	button.add_theme_stylebox_override("normal", _box(bg, bg, 0, 5, 6.0, 4.0))
	button.add_theme_stylebox_override("hover", _box(hover_bg, hover_bg, 0, 5, 6.0, 4.0))
	button.add_theme_stylebox_override("pressed", _box(hover_bg, hover_bg, 0, 5, 6.0, 4.0))
	button.add_theme_stylebox_override("focus", _box(bg, bg, 0, 5, 6.0, 4.0))
	button.add_theme_color_override("font_color", text_color)
	button.add_theme_color_override("font_hover_color", text_color)
	button.add_theme_color_override("font_pressed_color", text_color)
	button.add_theme_color_override("font_focus_color", text_color)
	button.add_theme_font_size_override("font_size", 11)


static func _box(bg: Color, border: Color, border_width: int, radius: int, margin_x: float, margin_y: float) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = bg
	style.border_color = border
	style.set_border_width_all(border_width)
	style.set_corner_radius_all(radius)
	style.content_margin_left = margin_x
	style.content_margin_right = margin_x
	style.content_margin_top = margin_y
	style.content_margin_bottom = margin_y
	return style


static func _dict(value: Variant) -> Dictionary:
	return value if value is Dictionary else {}


static func _array(value: Variant) -> Array:
	return value if value is Array else []


static func _text(value: String, color: Color, font_size: int) -> Label:
	var label := Label.new()
	label.text = value
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	return label


static func _divider(color: Color) -> ColorRect:
	var rule := ColorRect.new()
	rule.color = color
	rule.custom_minimum_size = Vector2(0, 1)
	return rule


static func _clear(container: Node) -> void:
	for child in container.get_children():
		container.remove_child(child)
		child.queue_free()
