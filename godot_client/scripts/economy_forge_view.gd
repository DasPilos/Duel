extends VBoxContainer

# Кузница из scenes/city/modals.py (_draw_forge_modal): вкладки, рецепты 4×2 со скроллом, процесс работы и склад.
# Вид не делает HTTP. По action_requested родитель выполняет запрос и передаёт ответ в set_state / set_message.
#   "create_order" с payload {"item_id": int}: POST /api/forge/{id}/orders, тело {"item_id": N}.
#   "collect_order" с payload {"order_id": int}: POST /api/forge/{id}/orders/{order_id}/collect, тело не нужно.
signal action_requested(action: String, payload: Dictionary)

# set_state(state) принимает ответ GET /api/forge/{id}, тот же объект, что Python-клиент получает от get_forge_state:
#   queue: [{order_id, item_id, item_name, owner_name, status: "working" | "queued", duration_seconds, seconds_left}];
#   queue_count, queue_limit: int (по умолчанию len(queue) и 5); warehouse: [{order_id, item_name, description, weight}].
# Необязательные ключи. Без них кнопка ВЫКОВАТЬ доступна, кроме случая полной очереди:
#   inventory: [{item_id, quantity}] из /api/inventory/{id}; если есть, проверяются материалы рецепта;
#   character: {copper, silver, gold}; если есть, проверяется цена рецепта в меди;
#   level: int, уровень кузницы в подзаголовке (по умолчанию 1).

const WINDOW_TITLE := "Кузница"
# Python 1600×900 px × 2/3: размер окна, которое задаёт родитель (вместе с его шапкой).
const WINDOW_SIZE := Vector2(1066, 600)
const BORDER_COLOR := Color8(255, 140, 50)
const BACKGROUND_COLOR := Color8(24, 20, 20)
const CURRENCY_SCRIPT := preload("res://scripts/currency_format.gd")
# format_time мастерской совпадает с format_forge_time из core/forge_recipes.py.
const WORKSHOP_VIEW_SCRIPT := preload("res://scripts/economy_workshop_view.gd")
const QUEUE_LIMIT := 5
const QUEUE_SLOTS := 5
const MESSAGE_SECONDS := 4.0
const MISSING_VALUE := "—"
const FONT_LARGE := 16
const FONT_MEDIUM := 13
const FONT_SMALL := 11
const TAB_HEIGHT := 23
const BUTTON_HEIGHT := 24
const CARD_WIDTH := 244
const CARD_HEIGHT := 157
const CARD_GAP_X := 10
const CARD_GAP_Y := 9
const GRID_COLUMNS := 4
const GRID_HEIGHT := CARD_HEIGHT * 2 + CARD_GAP_Y
const INFO_BUTTON_WIDTH := 70
const WORK_WIDTH := 290
const SLOT_WIDTH := 120
const BLOCK_MARGIN_X := 147
const BLOCK_MARGIN_TOP := 40
const POPUP_SIZE := Vector2(387, 347)
const POPUP_LABEL_WIDTH := 144
const POPUP_CRAFT_WIDTH := 173
const POPUP_CANCEL_WIDTH := 160

# Вкладки в порядке Python (FORGE_TABS). Вкладка без рецептов показывает «РАЗДЕЛ ЗАКРЫТ».
const FORGE_TABS := [
	["weapons", "ОРУЖИЕ"],
	["shields", "ЩИТЫ"],
	["helmets", "ШЛЕМЫ"],
	["armor", "ДОСПЕХИ"],
	["gloves", "ПЕРЧАТКИ"],
	["plates", "ЛАТЫ"],
	["shoes", "ОБУВЬ"],
	["smelting", "ПЛАВИЛЬНЯ"],
	["upgrades", "УЛУЧШЕНИЯ"],
	["storage", "СКЛАД"],
]
# Рецепты из core/forge_recipes.py. materials: {id предмета: количество}, copper: цена в меди, seconds: время.
const FORGE_RECIPES := [
	{"id": 90, "name": "Старый серп", "materials": {60: 5}, "copper": 40, "seconds": 720},
	{"id": 91, "name": "Топор лесоруба", "materials": {60: 5}, "copper": 40, "seconds": 720},
	{"id": 92, "name": "Кирка", "materials": {60: 5}, "copper": 40, "seconds": 720},
	{"id": 93, "name": "Разделочный нож", "materials": {60: 5}, "copper": 40, "seconds": 720},
	{"id": 23, "name": "Дубина", "materials": {60: 5}, "copper": 300, "seconds": 1080},
	{"id": 24, "name": "Простой лук", "materials": {60: 4}, "copper": 300, "seconds": 960},
	{"id": 25, "name": "Деревянный посох", "materials": {60: 5}, "copper": 300, "seconds": 960},
	{"id": 20, "name": "Железный меч", "materials": {73: 3}, "copper": 0, "seconds": 1800},
	{"id": 22, "name": "Кинжал", "materials": {73: 2}, "copper": 0, "seconds": 1200},
	{"id": 21, "name": "Стальной меч", "materials": {74: 3}, "copper": 0, "seconds": 3600},
	{"id": 39, "name": "Деревянный щит", "materials": {60: 4}, "copper": 0, "seconds": 1260},
	{"id": 38, "name": "Круглый щит", "materials": {60: 4}, "copper": 0, "seconds": 1500},
	{"id": 73, "name": "Железо", "materials": {10: 1, 60: 1}, "copper": 0, "seconds": 1800},
	{"id": 74, "name": "Сталь", "materials": {73: 1, 68: 1}, "copper": 0, "seconds": 2400},
]
const FORGE_RECIPE_CATEGORIES := {
	90: "weapons", 91: "weapons", 92: "weapons", 93: "weapons",
	23: "weapons", 24: "weapons", 25: "weapons", 20: "weapons",
	22: "weapons", 21: "weapons", 39: "shields", 38: "shields",
	73: "smelting", 74: "smelting",
}
const FORGE_MATERIAL_NAMES := {60: "Древесина", 10: "Железная руда", 68: "Уголь", 73: "Железо", 74: "Сталь"}
const POPUP_FIELDS := ["Слот", "Требование:", "Урон:", "Рецепт:", "Вес (кг)", "Бафы", "Характеристика", "Изготовления:", "Цена:"]

const SUBTITLE_COLOR := Color8(220, 185, 140)
const MESSAGE_OK_COLOR := Color8(120, 240, 120)
const MESSAGE_ERROR_COLOR := Color8(255, 100, 90)
const DIVIDER_COLOR := Color8(90, 60, 50)
const TAB_BG := Color8(49, 44, 39)
const TAB_TEXT := Color8(190, 177, 157)
const TAB_ACTIVE_BG := Color8(140, 75, 35)
const TAB_ACTIVE_TEXT := Color8(255, 225, 175)
const CARD_BG := Color8(33, 27, 26)
const CARD_BORDER := Color8(82, 65, 58)
const CARD_RULE_COLOR := Color8(75, 58, 52)
const CARD_TITLE_COLOR := Color8(255, 230, 150)
const REQUIREMENT_COLOR := Color8(255, 215, 120)
const DAMAGE_COLOR := Color8(255, 205, 110)
const EMPTY_VALUE_COLOR := Color8(175, 170, 165)
const INFO_BG := Color8(55, 48, 44)
const INFO_HOVER_BG := Color8(75, 65, 60)
const INFO_TEXT := Color8(220, 210, 190)
const INFO_HOVER_TEXT := Color8(255, 230, 180)
const BUTTON_TEXT := Color8(255, 255, 255)
const CRAFT_BG := Color8(150, 75, 30)
const CRAFT_HOVER_BG := Color8(195, 100, 40)
const QUEUE_FULL_BG := Color8(55, 45, 45)
const QUEUE_FULL_TEXT := Color8(170, 140, 140)
const NO_MATERIALS_BG := Color8(50, 40, 40)
const NO_MATERIALS_TEXT := Color8(190, 110, 110)
const OVERLAY_COLOR := Color8(0, 0, 0, 190)
const POPUP_BG := Color8(26, 20, 20, 254)
const POPUP_BORDER := Color8(255, 150, 60)
const POPUP_RULE_COLOR := Color8(90, 65, 55)
const POPUP_TITLE_COLOR := Color8(255, 225, 120)
const POPUP_SUBTITLE_COLOR := Color8(200, 185, 170)
const POPUP_ROW_EVEN := Color8(34, 27, 26)
const POPUP_ROW_ODD := Color8(42, 33, 31)
const POPUP_LABEL_COLOR := Color8(205, 195, 185)
const POPUP_VALUE_COLOR := Color8(255, 230, 160)
const PANEL_BG := Color8(28, 22, 22)
const PANEL_BORDER := Color8(215, 115, 45)
const HEADER_BG := Color8(48, 32, 28)
const HEADER_TEXT_COLOR := Color8(255, 215, 130)
const TOTAL_COLOR := Color8(255, 230, 160)
const WORK_BG := Color8(38, 29, 27)
const WORK_BORDER := Color8(120, 80, 65)
const WORK_TITLE_COLOR := Color8(255, 225, 120)
const IDLE_TITLE_COLOR := Color8(225, 210, 190)
const HINT_COLOR := Color8(180, 170, 160)
const OWNER_COLOR := Color8(160, 205, 245)
const TIME_COLOR := Color8(255, 195, 100)
const BAR_BG := Color8(18, 14, 14)
const BAR_FILL := Color8(245, 135, 45)
const BAR_BORDER := Color8(160, 100, 70)
const SLOT_CURRENT_BG := Color8(52, 35, 30)
const SLOT_CURRENT_BORDER := Color8(245, 130, 50)
const SLOT_QUEUED_BG := Color8(40, 32, 30)
const SLOT_QUEUED_BORDER := Color8(115, 90, 80)
const SLOT_FREE_BG := Color8(32, 27, 27)
const SLOT_FREE_BORDER := Color8(75, 64, 62)
const SLOT_RULE_COLOR := Color8(85, 68, 62)
const BADGE_CURRENT_COLOR := Color8(255, 185, 85)
const BADGE_QUEUED_COLOR := Color8(190, 180, 170)
const BADGE_FREE_COLOR := Color8(135, 125, 120)
const SLOT_NAME_COLOR := Color8(245, 235, 215)
const SLOT_TIMER_COLOR := Color8(255, 205, 110)
const FREE_TEXT_COLOR := Color8(160, 150, 145)
const FREE_HINT_COLOR := Color8(140, 130, 125)
const BLOCK_BG := Color8(34, 28, 28)
const BLOCK_BORDER := Color8(100, 75, 65)
const BLOCK_TEXT_COLOR := Color8(215, 210, 200)
const EMPTY_TITLE_COLOR := Color8(255, 215, 120)
const CLOSED_TITLE_COLOR := Color8(255, 200, 120)
const READY_BG := Color8(26, 35, 28)
const READY_BORDER := Color8(60, 140, 80)
const READY_RULE_COLOR := Color8(60, 95, 70)
const READY_BADGE_COLOR := Color8(110, 230, 130)
const READY_DESC_COLOR := Color8(210, 225, 210)
const READY_WEIGHT_COLOR := Color8(180, 200, 180)
const READY_NOTE_COLOR := Color8(150, 220, 170)
const COLLECT_BG := Color8(45, 125, 65)
const COLLECT_HOVER_BG := Color8(65, 160, 85)

enum CraftState { READY, QUEUE_FULL, NO_MATERIALS }

var _tab := "weapons"
var _level := 1
var _queue: Array = []
var _queue_count := 0
var _queue_limit := QUEUE_LIMIT
var _warehouse: Array = []
var _elapsed := 0.0
var _has_inventory := false
var _inventory_counts: Dictionary = {}
var _has_character := false
var _character: Dictionary = {}
var _info_recipe_id := -1
var _message_left := 0.0

var _subtitle: Label
var _message_label: Label
var _tab_buttons: Dictionary = {}
var _tab_scroll: ScrollContainer
var _tab_body: VBoxContainer
var _craft_buttons: Dictionary = {}
var _info_buttons: Dictionary = {}
var _collect_buttons: Dictionary = {}
var _queue_title: Label
var _queue_total: Label
var _work_title: Label
var _work_owner: Label
var _work_time: Label
var _work_hint: Label
var _progress_box: Control
var _progress_bar: ProgressBar
var _progress_percent: Label
var _slots: Array[Dictionary] = []
var _overlay: Control
var _popup_title: Label
var _popup_values: Dictionary = {}
var _popup_craft: Button


func _init() -> void:
	add_theme_constant_override("separation", 4)
	_build_ui()
	visibility_changed.connect(_on_visibility_changed)


func _exit_tree() -> void:
	_close_info()


func window_title() -> String:
	return WINDOW_TITLE


func set_state(state: Dictionary) -> void:
	_level = int(state.get("level", 1))
	_queue = _list(state.get("queue", []))
	_queue_limit = int(state.get("queue_limit", QUEUE_LIMIT))
	_queue_count = int(state.get("queue_count", _queue.size()))
	_warehouse = _list(state.get("warehouse", []))
	_has_inventory = state.has("inventory")
	_inventory_counts = _count_items(state.get("inventory", []))
	_has_character = state.has("character")
	_character = _dict(state.get("character", {}))
	_elapsed = 0.0
	_subtitle.text = "ОРУЖЕЙНАЯ КУЗНИЦА • УРОВЕНЬ %d" % _level
	(_tab_buttons["storage"] as Button).text = "СКЛАД (%d)" % _warehouse.size() if not _warehouse.is_empty() else "СКЛАД"
	_render_tab()
	if _info_recipe_id >= 0:
		_render_info()
	_render_process()
	_render_clock()


func set_message(text: String, is_error: bool) -> void:
	_message_label.text = text
	_message_label.add_theme_color_override("font_color", MESSAGE_ERROR_COLOR if is_error else MESSAGE_OK_COLOR)
	_message_label.visible = not text.is_empty()
	_message_left = MESSAGE_SECONDS


func _process(delta: float) -> void:
	if not is_visible_in_tree():
		return
	_elapsed += delta
	if _message_label.visible:
		_message_left -= delta
		if _message_left <= 0.0:
			_message_label.visible = false
	_render_clock()


func _on_visibility_changed() -> void:
	if not visible:
		_close_info()


static func _dict(value: Variant) -> Dictionary:
	return value if value is Dictionary else {}


static func _list(value: Variant) -> Array:
	return value if value is Array else []


static func _box(bg: Color, border: Color, border_width: int, radius: int, margin: int) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = bg
	style.border_color = border
	style.set_border_width_all(border_width)
	style.set_corner_radius_all(radius)
	style.set_content_margin_all(margin)
	return style


static func _count_items(items: Variant) -> Dictionary:
	var counts := {}
	for entry in _list(items):
		var item := _dict(entry)
		var item_id := int(item.get("item_id", 0))
		counts[item_id] = int(counts.get(item_id, 0)) + int(item.get("quantity", 0))
	return counts


static func _recipe(recipe_id: int) -> Dictionary:
	for recipe in FORGE_RECIPES:
		if int(recipe["id"]) == recipe_id:
			return recipe
	return {}


static func _recipes_for(tab: String) -> Array:
	var found: Array = []
	for recipe in FORGE_RECIPES:
		if str(FORGE_RECIPE_CATEGORIES.get(int(recipe["id"]), "")) == tab:
			found.append(recipe)
	return found


static func _tab_label(key: String) -> String:
	for entry in FORGE_TABS:
		if str(entry[0]) == key:
			return str(entry[1])
	return ""


func _build_ui() -> void:
	var header := HBoxContainer.new()
	add_child(header)
	_subtitle = _text("", SUBTITLE_COLOR, FONT_SMALL)
	header.add_child(_subtitle)
	var gap := Control.new()
	gap.custom_minimum_size = Vector2(70, 0)
	header.add_child(gap)
	_message_label = _text("", MESSAGE_OK_COLOR, FONT_SMALL)
	_message_label.visible = false
	header.add_child(_message_label)

	var tab_row := HBoxContainer.new()
	tab_row.add_theme_constant_override("separation", 5)
	add_child(tab_row)
	var group := ButtonGroup.new()
	for entry in FORGE_TABS:
		var key := str(entry[0])
		var button := Button.new()
		button.text = str(entry[1])
		button.toggle_mode = true
		button.button_group = group
		button.clip_text = true
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.custom_minimum_size = Vector2(0, TAB_HEIGHT)
		_style_tab(button)
		button.pressed.connect(_select_tab.bind(key))
		tab_row.add_child(button)
		_tab_buttons[key] = button
	add_child(_divider(DIVIDER_COLOR))

	_tab_scroll = ScrollContainer.new()
	_tab_scroll.custom_minimum_size = Vector2(0, GRID_HEIGHT)
	_tab_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	add_child(_tab_scroll)
	_tab_body = VBoxContainer.new()
	_tab_body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_tab_scroll.add_child(_tab_body)

	_build_process_panel()
	(_tab_buttons["weapons"] as Button).button_pressed = true
	_render_tab()


func _build_process_panel() -> void:
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", _box(PANEL_BG, PANEL_BORDER, 1, 8, 5))
	add_child(panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 3)
	panel.add_child(box)

	var header := PanelContainer.new()
	header.add_theme_stylebox_override("panel", _box(HEADER_BG, HEADER_BG, 0, 5, 5))
	box.add_child(header)
	var header_row := HBoxContainer.new()
	header.add_child(header_row)
	_queue_title = _text("", HEADER_TEXT_COLOR, FONT_MEDIUM)
	_queue_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header_row.add_child(_queue_title)
	_queue_total = _text("", TOTAL_COLOR, FONT_MEDIUM)
	header_row.add_child(_queue_total)

	var body := HBoxContainer.new()
	body.add_theme_constant_override("separation", 6)
	box.add_child(body)
	body.add_child(_build_work_block())
	for index in range(QUEUE_SLOTS):
		body.add_child(_build_slot())


func _build_work_block() -> PanelContainer:
	var work := PanelContainer.new()
	work.custom_minimum_size = Vector2(WORK_WIDTH, 0)
	work.add_theme_stylebox_override("panel", _box(WORK_BG, WORK_BORDER, 1, 5, 8))
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 3)
	work.add_child(box)
	_work_title = _text("", WORK_TITLE_COLOR, FONT_MEDIUM)
	box.add_child(_work_title)
	_work_owner = _text("", OWNER_COLOR, FONT_SMALL)
	box.add_child(_work_owner)
	_work_time = _text("", TIME_COLOR, FONT_MEDIUM)
	box.add_child(_work_time)
	_progress_box = Control.new()
	_progress_box.custom_minimum_size = Vector2(0, 18)
	box.add_child(_progress_box)
	_progress_bar = ProgressBar.new()
	_progress_bar.min_value = 0.0
	_progress_bar.max_value = 100.0
	_progress_bar.show_percentage = false
	_progress_bar.add_theme_stylebox_override("background", _box(BAR_BG, BAR_BORDER, 1, 4, 0))
	_progress_bar.add_theme_stylebox_override("fill", _box(BAR_FILL, BAR_FILL, 0, 4, 0))
	_progress_bar.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_progress_box.add_child(_progress_bar)
	_progress_percent = _text("", BUTTON_TEXT, FONT_SMALL)
	_progress_percent.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_progress_percent.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_progress_percent.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_progress_box.add_child(_progress_percent)
	_work_hint = _text("Выберите рецепт в верхнем меню и нажмите «ВЫКОВАТЬ».", HINT_COLOR, FONT_SMALL)
	_work_hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(_work_hint)
	return work


func _build_slot() -> PanelContainer:
	var slot := PanelContainer.new()
	slot.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	slot.custom_minimum_size = Vector2(SLOT_WIDTH, 0)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 1)
	slot.add_child(box)
	var badge := _text("", BADGE_FREE_COLOR, FONT_SMALL)
	box.add_child(badge)
	var busy := VBoxContainer.new()
	busy.add_theme_constant_override("separation", 1)
	box.add_child(busy)
	var name_label := _text("", SLOT_NAME_COLOR, FONT_MEDIUM)
	busy.add_child(name_label)
	var owner := _text("", OWNER_COLOR, FONT_SMALL)
	busy.add_child(owner)
	busy.add_child(_divider(SLOT_RULE_COLOR))
	busy.add_child(_text("Время до готовности:", HINT_COLOR, FONT_SMALL))
	var timer := _text("", SLOT_TIMER_COLOR, FONT_MEDIUM)
	busy.add_child(timer)
	var free := VBoxContainer.new()
	free.add_theme_constant_override("separation", 1)
	box.add_child(free)
	free.add_child(_text("Свободно для заказа", FREE_TEXT_COLOR, FONT_SMALL))
	free.add_child(_text("до 5 заказов кузнецу", FREE_HINT_COLOR, FONT_SMALL))
	_slots.append({"panel": slot, "badge": badge, "busy": busy, "free": free, "name": name_label, "owner": owner, "timer": timer})
	return slot


# Окно рецепта поверх всего экрана, как у Python. Пока оно открыто, висит на корне окна: внутри прокрутки
# родителя Godot отдавал бы щелчки содержимому прокрутки, а не затемнению.
func _open_info(recipe_id: int) -> void:
	_close_info()
	_info_recipe_id = recipe_id
	_overlay = _build_info_overlay()
	get_tree().root.add_child(_overlay)
	# Фокус остаётся на кнопке за затемнением: Enter не должен её нажимать.
	get_viewport().gui_release_focus()
	_render_info()


func _close_info() -> void:
	_info_recipe_id = -1
	if _overlay != null:
		_overlay.queue_free()
		_overlay = null
		_popup_values.clear()


func _build_info_overlay() -> Control:
	var overlay := Control.new()
	overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	var dim := ColorRect.new()
	dim.color = OVERLAY_COLOR
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	dim.mouse_filter = Control.MOUSE_FILTER_STOP
	dim.gui_input.connect(_on_dim_input)
	overlay.add_child(dim)

	var popup := PanelContainer.new()
	popup.custom_minimum_size = POPUP_SIZE
	popup.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	popup.grow_horizontal = Control.GROW_DIRECTION_BOTH
	popup.grow_vertical = Control.GROW_DIRECTION_BOTH
	popup.mouse_filter = Control.MOUSE_FILTER_STOP
	popup.add_theme_stylebox_override("panel", _box(POPUP_BG, POPUP_BORDER, 2, 8, 12))
	overlay.add_child(popup)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 2)
	popup.add_child(box)
	_popup_title = _text("", POPUP_TITLE_COLOR, FONT_LARGE)
	box.add_child(_popup_title)
	box.add_child(_text("Информация о предмете кузницы", POPUP_SUBTITLE_COLOR, FONT_SMALL))
	box.add_child(_divider(POPUP_RULE_COLOR))
	for index in range(POPUP_FIELDS.size()):
		var field := str(POPUP_FIELDS[index])
		var row := PanelContainer.new()
		var row_bg := POPUP_ROW_EVEN if index % 2 == 0 else POPUP_ROW_ODD
		var row_style := _box(row_bg, row_bg, 0, 3, 4)
		row_style.content_margin_left = 9.0
		row_style.content_margin_right = 9.0
		row.add_theme_stylebox_override("panel", row_style)
		box.add_child(row)
		var row_box := HBoxContainer.new()
		row.add_child(row_box)
		var label := _text(field, POPUP_LABEL_COLOR, FONT_SMALL)
		label.custom_minimum_size = Vector2(POPUP_LABEL_WIDTH, 0)
		row_box.add_child(label)
		var value := _text("", POPUP_VALUE_COLOR, FONT_SMALL)
		value.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row_box.add_child(value)
		_popup_values[field] = value

	box.add_child(_spacer())
	var buttons := HBoxContainer.new()
	buttons.add_theme_constant_override("separation", 13)
	box.add_child(buttons)
	_popup_craft = Button.new()
	_popup_craft.custom_minimum_size = Vector2(POPUP_CRAFT_WIDTH, 25)
	_popup_craft.pressed.connect(_on_popup_craft_pressed)
	buttons.add_child(_popup_craft)
	var cancel := Button.new()
	cancel.text = "ОТМЕНА"
	cancel.custom_minimum_size = Vector2(POPUP_CANCEL_WIDTH, 25)
	_style_button(cancel, INFO_BG, INFO_HOVER_BG, BUTTON_TEXT, BUTTON_TEXT, FONT_SMALL)
	cancel.pressed.connect(_close_info)
	buttons.add_child(cancel)
	return overlay


func _select_tab(key: String) -> void:
	_tab = key
	(_tab_buttons[key] as Button).button_pressed = true
	_tab_scroll.scroll_vertical = 0
	_render_tab()


func _render_tab() -> void:
	_clear(_tab_body)
	_craft_buttons.clear()
	_info_buttons.clear()
	_collect_buttons.clear()
	if _tab == "storage":
		_render_storage()
	elif _tab == "upgrades":
		_add_block(_info_block("УЛУЧШЕНИЕ КУЗНИЦЫ: УРОВЕНЬ 1 -> 2", [
			"Улучшение кузницы откроет рецепты защитных доспехов, шлемов и лат.",
			"Для улучшения потребуются доски, каменные блоки и ресурсы города.",
		], CLOSED_TITLE_COLOR, 120))
	elif _recipes_for(_tab).is_empty():
		_add_block(_info_block("РАЗДЕЛ «%s» ЗАКРЫТ" % _tab_label(_tab), [
			"Ковка элементов брони и защитной экипировки открывается на 2-м уровне кузницы.",
			"Развивайте город и улучшайте здания во вкладке «УЛУЧШЕНИЯ».",
		], CLOSED_TITLE_COLOR, 120))
	else:
		_render_recipes(_tab)


func _render_recipes(tab: String) -> void:
	var grid := _grid()
	_tab_body.add_child(grid)
	for recipe in _recipes_for(tab):
		grid.add_child(_recipe_card(recipe))


func _recipe_card(recipe: Dictionary) -> PanelContainer:
	var recipe_id := int(recipe["id"])
	var card := _card(CARD_BG, CARD_BORDER)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 3)
	card.add_child(box)
	box.add_child(_text(str(recipe["name"]), CARD_TITLE_COLOR, FONT_MEDIUM))
	box.add_child(_divider(CARD_RULE_COLOR))
	box.add_child(_text("Требование: %s" % MISSING_VALUE, REQUIREMENT_COLOR, FONT_SMALL))
	box.add_child(_text("Урон: %s" % MISSING_VALUE, DAMAGE_COLOR, FONT_SMALL))
	box.add_child(_text("Характеристики: %s" % MISSING_VALUE, EMPTY_VALUE_COLOR, FONT_SMALL))
	box.add_child(_text("Бафы: %s" % MISSING_VALUE, EMPTY_VALUE_COLOR, FONT_SMALL))
	box.add_child(_spacer())
	var footer := HBoxContainer.new()
	footer.add_theme_constant_override("separation", 6)
	box.add_child(footer)
	var info := Button.new()
	info.text = "ИНФО"
	info.custom_minimum_size = Vector2(INFO_BUTTON_WIDTH, BUTTON_HEIGHT)
	_style_button(info, INFO_BG, INFO_HOVER_BG, INFO_TEXT, INFO_HOVER_TEXT, FONT_SMALL)
	info.pressed.connect(_open_info.bind(recipe_id))
	footer.add_child(info)
	_info_buttons[recipe_id] = info
	var craft := Button.new()
	craft.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	craft.custom_minimum_size = Vector2(0, BUTTON_HEIGHT)
	_style_craft(craft, _craft_state(recipe))
	craft.pressed.connect(_on_craft_pressed.bind(recipe_id))
	footer.add_child(craft)
	_craft_buttons[recipe_id] = craft
	return card


func _render_storage() -> void:
	if _warehouse.is_empty():
		_add_block(_info_block("СКЛАД ГОТОВОЙ ПРОДУКЦИИ ПУСТ", [
			"Здесь будут храниться выкованные предметы вашего персонажа.",
			"Вам не обязательно ждать окончания ковки в кузнице — вы можете",
			"спокойно покинуть кузницу и вернуться забрать свой заказ в любое время.",
			"С этого склада можно забрать только свои заказы, чужие предметы недоступны.",
		], EMPTY_TITLE_COLOR, 153))
		return
	var grid := _grid()
	_tab_body.add_child(grid)
	for order in _warehouse:
		grid.add_child(_ready_card(_dict(order)))


func _ready_card(order: Dictionary) -> PanelContainer:
	var order_id := int(order.get("order_id", 0))
	var card := _card(READY_BG, READY_BORDER)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 3)
	card.add_child(box)
	box.add_child(_text(str(order.get("item_name", "Предмет")), CARD_TITLE_COLOR, FONT_MEDIUM))
	box.add_child(_text("ГОТОВО К ВЫДАЧЕ", READY_BADGE_COLOR, FONT_SMALL))
	box.add_child(_divider(READY_RULE_COLOR))
	var description := str(order.get("description", "Готовый выкованный предмет"))
	box.add_child(_text(description.left(38), READY_DESC_COLOR, FONT_SMALL))
	box.add_child(_text("Вес: %s кг" % str(order.get("weight", 1)), READY_WEIGHT_COLOR, FONT_SMALL))
	box.add_child(_text("Заказ ожидает на вашем складе кузницы", READY_NOTE_COLOR, FONT_SMALL))
	box.add_child(_spacer())
	var collect := Button.new()
	collect.text = "ЗАБРАТЬ В РЮКЗАК"
	collect.custom_minimum_size = Vector2(0, BUTTON_HEIGHT)
	_style_button(collect, COLLECT_BG, COLLECT_HOVER_BG, BUTTON_TEXT, BUTTON_TEXT, FONT_SMALL)
	collect.pressed.connect(_on_collect_pressed.bind(order_id))
	box.add_child(collect)
	_collect_buttons[order_id] = collect
	return card


func _render_process() -> void:
	_queue_title.text = "ПРОЦЕСС РАБОТЫ КУЗНИЦЫ • ОЧЕРЕДЬ: %d / %d (МАКС. %d ЗАКАЗОВ)" % [_queue_count, _queue_limit, _queue_limit]
	var idle := _queue.is_empty()
	_work_hint.visible = idle
	_work_owner.visible = not idle
	_work_time.visible = not idle
	_progress_box.visible = not idle
	if idle:
		_work_title.text = "Горн свободен. Кузнец ждет заказов"
		_work_title.add_theme_color_override("font_color", IDLE_TITLE_COLOR)
	else:
		var current := _dict(_queue[0])
		_work_title.text = "В РАБОТЕ: %s" % str(current.get("item_name", "Предмет"))
		_work_title.add_theme_color_override("font_color", WORK_TITLE_COLOR)
		_work_owner.text = "Заказчик: %s" % str(current.get("owner_name", ""))
	_render_slots()


func _render_slots() -> void:
	for index in range(QUEUE_SLOTS):
		var slot: Dictionary = _slots[index]
		var filled := index < _queue.size()
		var entry := _dict(_queue[index]) if filled else {}
		var current := filled and index == 0 and str(entry.get("status", "")) == "working"
		(slot["panel"] as PanelContainer).add_theme_stylebox_override("panel", _slot_style(filled, current))
		var badge := slot["badge"] as Label
		badge.text = _slot_badge(index, filled, current)
		badge.add_theme_color_override("font_color", BADGE_CURRENT_COLOR if current else (BADGE_QUEUED_COLOR if filled else BADGE_FREE_COLOR))
		(slot["busy"] as Control).visible = filled
		(slot["free"] as Control).visible = not filled
		if filled:
			(slot["name"] as Label).text = str(entry.get("item_name", "Предмет")).left(13)
			(slot["owner"] as Label).text = "Игрок: %s" % str(entry.get("owner_name", "")).left(11)


func _slot_badge(index: int, filled: bool, current: bool) -> String:
	if not filled:
		return "[%d] СВОБОДНЫЙ СЛОТ" % (index + 1)
	return "[%d] В РАБОТЕ" % (index + 1) if current else "[%d] В ОЧЕРЕДИ" % (index + 1)


func _slot_style(filled: bool, current: bool) -> StyleBoxFlat:
	if current:
		return _box(SLOT_CURRENT_BG, SLOT_CURRENT_BORDER, 2, 5, 6)
	if filled:
		return _box(SLOT_QUEUED_BG, SLOT_QUEUED_BORDER, 1, 5, 6)
	return _box(SLOT_FREE_BG, SLOT_FREE_BORDER, 1, 5, 6)


# Остаток времени: сервер присылает seconds_left на момент ответа; заказ в работе убывает локально, как в Python.
func _remaining(index: int) -> float:
	var entry := _dict(_queue[index])
	var left := float(entry.get("seconds_left", 0))
	if index == 0 and str(entry.get("status", "")) == "working":
		left -= _elapsed
	return maxf(0.0, left)


func _render_clock() -> void:
	var total := 0.0
	for index in range(_queue.size()):
		total += _remaining(index)
	_queue_total.text = "ОБЩЕЕ ВРЕМЯ ЗАГРУЗКИ: %s" % WORKSHOP_VIEW_SCRIPT.format_time(int(total))
	for index in range(mini(_queue.size(), QUEUE_SLOTS)):
		(_slots[index]["timer"] as Label).text = WORKSHOP_VIEW_SCRIPT.format_time(int(_remaining(index)))
	if _queue.is_empty():
		return
	var duration := maxf(1.0, float(_dict(_queue[0]).get("duration_seconds", 1)))
	var seconds_left := _remaining(0)
	var ratio := clampf((duration - seconds_left) / duration, 0.0, 1.0)
	_work_time.text = "До готовности: %s" % WORKSHOP_VIEW_SCRIPT.format_time(int(seconds_left))
	_progress_bar.value = ratio * 100.0
	_progress_percent.text = "%d%% (%s)" % [floori(ratio * 100.0), WORKSHOP_VIEW_SCRIPT.format_time(int(seconds_left))]


# Порядок как в Python: полная очередь важнее нехватки материалов или меди.
func _craft_state(recipe: Dictionary) -> CraftState:
	if _queue_count >= _queue_limit:
		return CraftState.QUEUE_FULL
	if _lacks_resources(recipe):
		return CraftState.NO_MATERIALS
	return CraftState.READY


func _lacks_resources(recipe: Dictionary) -> bool:
	if _has_character and not CURRENCY_SCRIPT.has_enough_copper(_character, int(recipe["copper"])):
		return true
	if _has_inventory:
		var materials: Dictionary = recipe["materials"]
		for item_id in materials:
			if int(_inventory_counts.get(item_id, 0)) < int(materials[item_id]):
				return true
	return false


func _style_craft(button: Button, state: CraftState) -> void:
	button.disabled = state != CraftState.READY
	match state:
		CraftState.READY:
			button.text = "ВЫКОВАТЬ"
			_style_button(button, CRAFT_BG, CRAFT_HOVER_BG, BUTTON_TEXT, BUTTON_TEXT, FONT_SMALL)
		CraftState.QUEUE_FULL:
			button.text = "ОЧЕРЕДЬ (%d/%d)" % [_queue_count, _queue_limit]
			_style_button(button, QUEUE_FULL_BG, QUEUE_FULL_BG, QUEUE_FULL_TEXT, QUEUE_FULL_TEXT, FONT_SMALL)
		CraftState.NO_MATERIALS:
			button.text = "НЕТ МАТЕРИАЛОВ"
			_style_button(button, NO_MATERIALS_BG, NO_MATERIALS_BG, NO_MATERIALS_TEXT, NO_MATERIALS_TEXT, FONT_SMALL)


func _on_craft_pressed(recipe_id: int) -> void:
	if _craft_state(_recipe(recipe_id)) != CraftState.READY:
		return
	action_requested.emit("create_order", {"item_id": recipe_id})


func _on_collect_pressed(order_id: int) -> void:
	action_requested.emit("collect_order", {"order_id": order_id})


func _render_info() -> void:
	var recipe := _recipe(_info_recipe_id)
	_popup_title.text = str(recipe["name"])
	for field in POPUP_FIELDS:
		(_popup_values[field] as Label).text = MISSING_VALUE
	(_popup_values["Рецепт:"] as Label).text = _materials_text(recipe)
	(_popup_values["Изготовления:"] as Label).text = "%d м" % floori(float(recipe["seconds"]) / 60.0)
	(_popup_values["Цена:"] as Label).text = _price_text(int(recipe["copper"]))
	_style_craft(_popup_craft, _craft_state(recipe))


func _materials_text(recipe: Dictionary) -> String:
	var parts := PackedStringArray()
	var materials: Dictionary = recipe["materials"]
	for item_id in materials:
		parts.append("%s ×%d" % [FORGE_MATERIAL_NAMES.get(item_id, "Материал"), int(materials[item_id])])
	return ", ".join(parts)


func _price_text(copper: int) -> String:
	return CURRENCY_SCRIPT.format_amount(copper) if copper > 0 else "без дополнительной платы"


func _on_popup_craft_pressed() -> void:
	var recipe_id := _info_recipe_id
	if _craft_state(_recipe(recipe_id)) != CraftState.READY:
		return
	_close_info()
	action_requested.emit("create_order", {"item_id": recipe_id})


func _on_dim_input(event: InputEvent) -> void:
	var click := event as InputEventMouseButton
	if click != null and click.pressed and click.button_index == MOUSE_BUTTON_LEFT:
		_close_info()


func _style_tab(button: Button) -> void:
	button.add_theme_stylebox_override("normal", _box(TAB_BG, TAB_BG, 0, 5, 4))
	button.add_theme_stylebox_override("hover", _box(TAB_BG, TAB_BG, 0, 5, 4))
	button.add_theme_stylebox_override("pressed", _box(TAB_ACTIVE_BG, TAB_ACTIVE_BG, 0, 5, 4))
	button.add_theme_stylebox_override("hover_pressed", _box(TAB_ACTIVE_BG, TAB_ACTIVE_BG, 0, 5, 4))
	button.add_theme_stylebox_override("focus", _box(TAB_BG, TAB_BG, 0, 5, 4))
	button.add_theme_color_override("font_color", TAB_TEXT)
	button.add_theme_color_override("font_hover_color", TAB_TEXT)
	button.add_theme_color_override("font_pressed_color", TAB_ACTIVE_TEXT)
	button.add_theme_color_override("font_hover_pressed_color", TAB_ACTIVE_TEXT)
	button.add_theme_color_override("font_focus_color", TAB_TEXT)
	button.add_theme_font_size_override("font_size", FONT_SMALL)


static func _style_button(button: Button, bg: Color, hover_bg: Color, text: Color, hover_text: Color, font_size: int) -> void:
	button.add_theme_stylebox_override("normal", _box(bg, bg, 0, 5, 4))
	button.add_theme_stylebox_override("hover", _box(hover_bg, hover_bg, 0, 5, 4))
	button.add_theme_stylebox_override("pressed", _box(hover_bg, hover_bg, 0, 5, 4))
	button.add_theme_stylebox_override("focus", _box(bg, bg, 0, 5, 4))
	button.add_theme_stylebox_override("disabled", _box(bg, bg, 0, 5, 4))
	button.add_theme_color_override("font_color", text)
	button.add_theme_color_override("font_hover_color", hover_text)
	button.add_theme_color_override("font_pressed_color", hover_text)
	button.add_theme_color_override("font_focus_color", text)
	button.add_theme_color_override("font_disabled_color", text)
	button.add_theme_font_size_override("font_size", font_size)


func _card(bg: Color, border: Color) -> PanelContainer:
	var card := PanelContainer.new()
	card.custom_minimum_size = Vector2(CARD_WIDTH, CARD_HEIGHT)
	card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	card.add_theme_stylebox_override("panel", _box(bg, border, 1, 5, 9))
	return card


func _grid() -> GridContainer:
	var grid := GridContainer.new()
	grid.columns = GRID_COLUMNS
	grid.add_theme_constant_override("h_separation", CARD_GAP_X)
	grid.add_theme_constant_override("v_separation", CARD_GAP_Y)
	return grid


func _info_block(title: String, lines: Array, title_color: Color, min_height: int) -> PanelContainer:
	var block := PanelContainer.new()
	block.custom_minimum_size = Vector2(0, min_height)
	block.add_theme_stylebox_override("panel", _box(BLOCK_BG, BLOCK_BORDER, 1, 5, 12))
	var box := VBoxContainer.new()
	box.alignment = BoxContainer.ALIGNMENT_CENTER
	box.add_theme_constant_override("separation", 6)
	block.add_child(box)
	box.add_child(_centered(_text(title, title_color, FONT_MEDIUM)))
	for line in lines:
		box.add_child(_centered(_text(str(line), BLOCK_TEXT_COLOR, FONT_SMALL)))
	return block


func _add_block(block: Control) -> void:
	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", BLOCK_MARGIN_X)
	margin.add_theme_constant_override("margin_right", BLOCK_MARGIN_X)
	margin.add_theme_constant_override("margin_top", BLOCK_MARGIN_TOP)
	margin.add_child(block)
	_tab_body.add_child(margin)


func _centered(label: Label) -> Label:
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return label


func _text(value: String, color: Color, font_size: int) -> Label:
	var label := Label.new()
	label.text = value
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	return label


func _divider(color: Color) -> ColorRect:
	var rule := ColorRect.new()
	rule.color = color
	rule.custom_minimum_size = Vector2(0, 1)
	return rule


func _spacer() -> Control:
	var spacer := Control.new()
	spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	return spacer


func _clear(container: Node) -> void:
	for child in container.get_children():
		container.remove_child(child)
		child.queue_free()
