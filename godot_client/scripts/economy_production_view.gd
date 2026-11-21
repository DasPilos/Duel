extends "res://scripts/economy_storage_view.gd"

# Производственное окно (ферма, лесопилка, разлом, скотный двор, чёрная яма) из ui/production_building_window.py:
# вкладки ПРОИЗВОДСТВО, СКЛАД и УЛУЧШЕНИЕ. Вид не делает HTTP: по action_requested родитель выполняет действие.
#   "hire", "fire", "player" с payload {"slot_index": int}: вид уже спросил подтверждение, как диалог в Python.
#   "refresh" без payload: родитель перечитывает здание; так же Python перечитывает его при входе на УЛУЧШЕНИЕ.
#   "storage_withdraw", "storage_deposit", "upgrade_building" — как в economy_storage_view.gd.
#   "production_upgrade" с payload {"upgrade_id": String}: карточка улучшения фермы или лесопилки, родитель шлёт POST.
# Подтверждение выводится полосой над таблицей, а не поверх окна: обновление каждые 5 секунд её не сбрасывает.
# Холст участков над таблицей: клик по участку даёт найм или снятие горожанина, как в Python (plot_clicked, plot_removed).

const RULES := preload("res://scripts/economy_production_rules.gd")
const UPGRADE_RULES := preload("res://scripts/economy_production_upgrades.gd")
const PLOTS_VIEW := preload("res://scripts/economy_production_plots_view.gd")
const CURRENCY := preload("res://scripts/currency_format.gd")
const STORAGE_VIEW := preload("res://scripts/economy_storage_view.gd")
const PRODUCTION_NAMES := {
	"farm": "Крестьянское поселение",
	"lumber_camp": "Лагерь лесорубов",
	"mountain_rift": "Горный разлом",
	"barnyard": "Скотный двор",
	"black_pit": "Чёрная яма",
}
const PRODUCTION_TABS := [
	["production", "ПРОИЗВОДСТВО"],
	["storage", "СКЛАД"],
	["upgrade", "УЛУЧШЕНИЕ"],
]
const STATUS_TEXTS := {
	"upgrade": "Идёт улучшение",
	"full": "Склад переполнен",
	"working": "Работает",
	"idle": "Нет рабочих",
}
const STATUS_COLORS := {
	"upgrade": Color8(120, 190, 240),
	"full": Color8(240, 90, 80),
	"working": Color8(110, 230, 120),
	"idle": Color8(240, 210, 90),
}
# Надписи бонусов добычи, как resource_labels в draw_worker_stats Python.
const BONUS_LABELS := {
	"wheat": "Пшеница",
	"wood": "Древесина",
	"iron": "Железо",
	"stone": "Камень",
	"coal": "Уголь",
	"leather": "Кожа",
	"meat": "Мясо",
}
const SLOT_ROW_HEIGHT := 40.0
const SLOT_TABLE_MAX_HEIGHT := 300.0
const SLOT_EVEN_BG := Color8(35, 42, 39)
const SLOT_ODD_BG := Color8(30, 36, 35)
const WORKER_COLOR := Color8(213, 207, 187)
const PLAYER_COLOR := Color8(151, 211, 156)
const FREE_COLOR := Color8(170, 175, 165)
const TRAVEL_COLOR := Color8(100, 185, 245)
const BONUS_COLOR := Color8(117, 225, 128)
const RATE_COLOR := Color8(190, 220, 235)
const TIMER_COLOR := Color8(190, 205, 184)
const MUTED_COLOR := Color8(145, 150, 142)
const BUTTON_SIZE := Vector2(184, 26)
const BUTTON_TEXT := Color8(235, 245, 230)
const HIRE_BG := Color8(68, 112, 60)
const PLAYER_BG := Color8(75, 120, 155)
const LEAVE_BG := Color8(120, 90, 46)
const FIRE_BG := Color8(120, 64, 56)
const CONFIRM_BG := Color8(28, 31, 28)
const CONFIRM_BORDER := Color8(185, 151, 86)
const CONFIRM_TEXT := Color8(235, 218, 183)
const CONFIRM_YES_BG := Color8(70, 119, 65)
const CONFIRM_YES_HOVER := Color8(90, 150, 85)
const CONFIRM_YES_TEXT := Color8(245, 241, 221)
const CONFIRM_NO_BG := Color8(63, 59, 51)
const CONFIRM_NO_HOVER := Color8(85, 79, 68)
const CONFIRM_NO_TEXT := Color8(220, 214, 194)
const CARD_BG := Color8(34, 39, 31)
const CARD_READY_BORDER := Color8(108, 137, 82)
const CARD_LOCKED_BORDER := Color8(77, 78, 66)
const CARD_TITLE_COLOR := Color8(232, 218, 184)
const CARD_REQUIREMENT_OK := Color8(161, 201, 148)
const CARD_REQUIREMENT_LOCKED := Color8(222, 161, 115)
const CARD_RESULT_COLOR := Color8(197, 207, 190)
const CARD_DURATION_COLOR := Color8(180, 194, 176)
const CARD_PRICE_COLOR := Color8(224, 214, 188)
const CARD_COMPLETE_COLOR := Color8(143, 208, 139)
const CARD_ACTIVE_COLOR := Color8(132, 193, 231)
const CARD_BUTTON_SIZE := Vector2(210, 30)
const CARD_BUTTON_ON_BG := Color8(75, 125, 70)
const CARD_BUTTON_ON_HOVER := Color8(92, 150, 86)
const CARD_BUTTON_ON_TEXT := Color8(240, 238, 220)
const CARD_BUTTON_OFF_BG := Color8(49, 51, 46)
const CARD_BUTTON_OFF_TEXT := Color8(140, 142, 132)
const CARD_BUTTON_TEXTS := {
	"requirements": "СНАЧАЛА ПРЕДЫДУЩИЕ",
	"funds": "НЕДОСТАТОЧНО",
	"busy": "ИДЁТ УЛУЧШЕНИЕ",
	"start": "НАЧАТЬ",
}

var _character_id := 0
var _worker_state: Dictionary = {}
var _status_label: Label
var _rate_label: Label
var _confirm_strip: PanelContainer
var _confirm_label: Label
var _pending_action := ""
var _pending_slot := -1
var _travel_labels: Array = []
var _card_clocks: Array = []
var _timer_labels: Array = []
var _plots_view


func set_character_id(character_id: int) -> void:
	_character_id = character_id


func set_state(state: Dictionary) -> void:
	_worker_state = state.duplicate(true)
	super.set_state(state)
	var key := RULES.status_key(state)
	_subtitle.text = "Уровень %d · Горожане: %d / %d" % [
		int(state.get("level", 1)),
		int(state.get("workers", 0)),
		int(state.get("max_workers", 0)),
	]
	_status_label.text = str(STATUS_TEXTS[key])
	_status_label.add_theme_color_override("font_color", STATUS_COLORS[key])
	_update_rates(state)


func _tab_entries() -> Array:
	return PRODUCTION_TABS


func _building_info() -> Dictionary:
	return {"name": str(PRODUCTION_NAMES.get(_building, "")), "unit": ""}


func _build_ui() -> void:
	super._build_ui()
	_status_label = _text("", STATUS_COLORS["idle"], 12)
	add_child(_status_label)
	move_child(_status_label, _subtitle.get_index() + 1)
	_rate_label = _text("", RATE_COLOR, 11)
	_rate_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_rate_label)
	move_child(_rate_label, _status_label.get_index() + 1)
	_build_confirm_strip()


func _process(delta: float) -> void:
	super._process(delta)
	for entry in _travel_labels:
		_set_travel_text(entry["label"], int(entry["seconds"]))
	for entry in _card_clocks:
		_set_card_clock(entry["label"], int(entry["seconds"]))
	for entry in _timer_labels:
		_set_timer_text(entry)


func _select_tab(key: String) -> void:
	super._select_tab(key)
	if key == RULES.TAB_UPGRADE:
		action_requested.emit("refresh", {})


func _render_tab() -> void:
	_clock_label = null
	_travel_labels.clear()
	_card_clocks.clear()
	_timer_labels.clear()
	_plots_view = null
	if _tab != RULES.TAB_PRODUCTION:
		super._render_tab()
		return
	_clear(_body)
	_render_production()


func _render_upgrade() -> void:
	if not UPGRADE_RULES.has_cards(_building):
		super._render_upgrade()
		return
	var progress := UPGRADE_RULES.progress_of(_worker_state, _building)
	var level := int(_worker_state.get("level", 1))
	var completed := _dict_of(progress.get("completed", {}))
	for pair in UPGRADE_RULES.available(_building, level, completed):
		_body.add_child(_upgrade_card(str(pair[0]), pair[1], progress))


# Карточка как в _draw_building_upgrade_cards Python: требования, результат, время, цена и кнопка.
func _upgrade_card(upgrade_id: String, upgrade: Dictionary, progress: Dictionary) -> PanelContainer:
	var level := int(_worker_state.get("level", 1))
	var completed := _dict_of(progress.get("completed", {}))
	var warehouse := _dict_of(_worker_state.get("warehouse_storage", {}))
	var copper := UPGRADE_RULES.spendable_copper(_worker_state)
	var status := UPGRADE_RULES.card_status(upgrade_id, upgrade, _building, level, progress, warehouse, copper)
	var met := UPGRADE_RULES.requirements_met(_building, upgrade_id, upgrade, level, completed)
	var can_start := status == UPGRADE_RULES.STATUS_START
	var card := PanelContainer.new()
	card.add_theme_stylebox_override("panel", _box(CARD_BG, CARD_READY_BORDER if can_start else CARD_LOCKED_BORDER, 1, 6, 12.0, 8.0))
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 3)
	card.add_child(box)
	box.add_child(_text(str(upgrade.get("name", "")), CARD_TITLE_COLOR, 14))
	box.add_child(_text("Требование: %s" % str(upgrade.get("requirement", "")),
		CARD_REQUIREMENT_OK if met else CARD_REQUIREMENT_LOCKED, 12))
	box.add_child(_text("Результат: %s" % str(upgrade.get("result", "")), CARD_RESULT_COLOR, 12))
	box.add_child(_text("Время улучшения: %s" % STORAGE_VIEW.format_duration(int(upgrade.get("time_seconds", 0))),
		CARD_DURATION_COLOR, 12))
	var footer := HBoxContainer.new()
	footer.add_theme_constant_override("separation", 12)
	box.add_child(footer)
	footer.add_child(_price_label(upgrade, copper, warehouse))
	var filler := Control.new()
	filler.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	footer.add_child(filler)
	footer.add_child(_status_control(status, upgrade_id, progress))
	return card


func _price_label(upgrade: Dictionary, copper: int, warehouse: Dictionary) -> Label:
	var text := "Доступно: %s %s" % [CURRENCY.format_amount(copper), UPGRADE_RULES.price_text(upgrade)]
	var wood_cost := int(_dict_of(upgrade.get("materials", {})).get("wood", 0))
	if wood_cost > 0:
		text += " · %d/%d древесины" % [int(warehouse.get("wood", 0)), wood_cost]
	return _text(text, CARD_PRICE_COLOR, 12)


func _status_control(status: String, upgrade_id: String, progress: Dictionary) -> Control:
	if status == UPGRADE_RULES.STATUS_COMPLETE:
		return _text("УСТАНОВЛЕНО", CARD_COMPLETE_COLOR, 12)
	if status == UPGRADE_RULES.STATUS_ACTIVE:
		var clock := _text("", CARD_ACTIVE_COLOR, 12)
		var seconds := int(progress.get("seconds_left", 0))
		_card_clocks.append({"label": clock, "seconds": seconds})
		_set_card_clock(clock, seconds)
		return clock
	var can_start := status == UPGRADE_RULES.STATUS_START
	var button := Button.new()
	button.text = str(CARD_BUTTON_TEXTS.get(status, ""))
	button.custom_minimum_size = CARD_BUTTON_SIZE
	button.size_flags_horizontal = Control.SIZE_SHRINK_END
	button.disabled = not can_start
	_style_button(button,
		CARD_BUTTON_ON_BG if can_start else CARD_BUTTON_OFF_BG,
		CARD_BUTTON_ON_HOVER if can_start else CARD_BUTTON_OFF_BG,
		CARD_BUTTON_ON_TEXT if can_start else CARD_BUTTON_OFF_TEXT)
	button.add_theme_stylebox_override("disabled", _box(CARD_BUTTON_OFF_BG, CARD_BUTTON_OFF_BG, 0, 5, 12.0, 4.0))
	button.add_theme_color_override("font_disabled_color", CARD_BUTTON_OFF_TEXT)
	if can_start:
		button.pressed.connect(_on_upgrade_card_pressed.bind(upgrade_id))
	return button


func _on_upgrade_card_pressed(upgrade_id: String) -> void:
	action_requested.emit("production_upgrade", {"upgrade_id": upgrade_id})


func _set_card_clock(label: Label, seconds: int) -> void:
	label.text = "Осталось: %s" % STORAGE_VIEW.format_clock(maxi(0, int(seconds - _elapsed)))


func _render_production() -> void:
	if RULES.has_plot_view(_building):
		_plots_view = PLOTS_VIEW.new()
		_plots_view.set_building(_building)
		_plots_view.set_state(_worker_state, _character_id)
		_plots_view.plot_clicked.connect(_on_plot_clicked)
		_plots_view.plot_removed.connect(_on_plot_removed)
		_body.add_child(_plots_view)
	var slots := RULES.slots_of(_worker_state)
	if slots.is_empty():
		_body.add_child(_text("Нет рабочих мест", MUTED_COLOR, 13))
		return
	var header := PanelContainer.new()
	header.add_theme_stylebox_override("panel", _box(HEADER_BG, HEADER_BG, 0, 0, 8.0, 2.0))
	header.add_child(_text("Рабочие места и работники", TITLE_COLOR, 13))
	_body.add_child(header)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.custom_minimum_size.y = minf(slots.size() * SLOT_ROW_HEIGHT, SLOT_TABLE_MAX_HEIGHT)
	_body.add_child(scroll)
	var rows := VBoxContainer.new()
	rows.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	rows.add_theme_constant_override("separation", 0)
	scroll.add_child(rows)
	for index in range(slots.size()):
		if slots[index] is Dictionary:
			rows.add_child(_slot_row(slots[index], index))


func _slot_row(slot: Dictionary, index: int) -> PanelContainer:
	var background := SLOT_ODD_BG if index % 2 == 1 else SLOT_EVEN_BG
	var row := PanelContainer.new()
	row.custom_minimum_size.y = SLOT_ROW_HEIGHT
	row.add_theme_stylebox_override("panel", _box(background, background, 0, 0, 8.0, 3.0))
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 0)
	row.add_child(column)
	var line := HBoxContainer.new()
	line.add_theme_constant_override("separation", 8)
	column.add_child(line)
	var worker := _worker_text(slot)
	var label := _text(worker["text"], worker["color"], 13)
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	line.add_child(label)
	var slot_index := int(slot.get("slot_index", 0))
	for button_spec in _slot_buttons(slot):
		line.add_child(_slot_button(button_spec[0], button_spec[1], slot_index, button_spec[2]))
	var timers := RULES.timer_entries(slot)
	if not timers.is_empty():
		column.add_child(_timer_line(timers))
	if bool(slot.get("is_travelling", false)):
		var travel := _text("", TRAVEL_COLOR, 11)
		column.add_child(travel)
		_travel_labels.append({"label": travel, "seconds": int(slot.get("travel_seconds_left", 0))})
		_set_travel_text(travel, int(slot.get("travel_seconds_left", 0)))
	return row


# Текст места: номер, ресурс и работник; для игрока — бонусы добычи, как в draw_worker_stats Python.
func _worker_text(slot: Dictionary) -> Dictionary:
	var occupied := bool(slot.get("occupied", false))
	var own := str(slot.get("worker_id", "")) == RULES.player_worker_id(_character_id)
	var worker := "Свободна"
	var color := FREE_COLOR
	if occupied:
		worker = str(slot.get("worker_name", "")) if not str(slot.get("worker_name", "")).is_empty() else "Горожанин"
		color = PLAYER_COLOR if own else WORKER_COLOR
	var text := "Ячейка %d · %s · %s" % [int(slot.get("slot_index", 0)) + 1, _resource_name(_first_resource(slot)), worker]
	if own:
		var bonus := _bonus_text(_dict_of(slot.get("harvest_bonus", {})))
		if not bonus.is_empty():
			text += " · " + bonus
	return {"text": text, "color": color}


func _slot_buttons(slot: Dictionary) -> Array:
	var buttons: Array = []
	var occupied := bool(slot.get("occupied", false))
	var own := str(slot.get("worker_id", "")) == RULES.player_worker_id(_character_id)
	if not occupied:
		buttons.append(["Поставить горожанина", RULES.ACTION_HIRE, HIRE_BG])
		buttons.append(["Встать на добычу", RULES.ACTION_PLAYER, PLAYER_BG])
	elif own:
		buttons.append(["Закончить работу", RULES.ACTION_PLAYER, LEAVE_BG])
	elif not bool(slot.get("is_player", false)):
		buttons.append(["Снять горожанина", RULES.ACTION_FIRE, FIRE_BG])
	return buttons


func _slot_button(text: String, action: String, slot_index: int, color: Color) -> Button:
	var button := Button.new()
	button.text = text
	button.custom_minimum_size = BUTTON_SIZE
	button.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_style_button(button, color, color.lightened(0.2), BUTTON_TEXT)
	button.pressed.connect(_on_slot_button_pressed.bind(action, slot_index))
	return button


func _on_slot_button_pressed(action: String, slot_index: int) -> void:
	if action == RULES.ACTION_PLAYER and RULES.player_click_blocked(_worker_state, slot_index, _character_id):
		set_message(RULES.MSG_STORAGE_FULL)
		return
	_queue_action(action, slot_index)


func _on_confirm_pressed() -> void:
	var action := _pending_action
	var slot_index := _pending_slot
	_hide_confirm()
	action_requested.emit(action, {"slot_index": slot_index})


func _hide_confirm() -> void:
	_confirm_strip.visible = false
	_pending_action = ""
	_pending_slot = -1


func _build_confirm_strip() -> void:
	_confirm_strip = PanelContainer.new()
	_confirm_strip.visible = false
	_confirm_strip.add_theme_stylebox_override("panel", _box(CONFIRM_BG, CONFIRM_BORDER, 2, 6, 10.0, 6.0))
	var line := HBoxContainer.new()
	line.add_theme_constant_override("separation", 8)
	_confirm_strip.add_child(line)
	_confirm_label = _text("", CONFIRM_TEXT, 13)
	_confirm_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_confirm_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	line.add_child(_confirm_label)
	var yes := Button.new()
	yes.text = "ПОДТВЕРДИТЬ"
	_style_button(yes, CONFIRM_YES_BG, CONFIRM_YES_HOVER, CONFIRM_YES_TEXT)
	yes.pressed.connect(_on_confirm_pressed)
	line.add_child(yes)
	var no := Button.new()
	no.text = "ОТМЕНА"
	_style_button(no, CONFIRM_NO_BG, CONFIRM_NO_HOVER, CONFIRM_NO_TEXT)
	no.pressed.connect(_hide_confirm)
	line.add_child(no)
	add_child(_confirm_strip)
	move_child(_confirm_strip, _body.get_index())


func _update_rates(state: Dictionary) -> void:
	var rates := RULES.production_per_hour(state)
	var parts := PackedStringArray()
	for resource in rates:
		var value := "%.1f" % float(rates[resource])
		parts.append("%s %s ед./ч" % [_resource_name(str(resource)), value.replace(".", ",")])
	_rate_label.visible = not parts.is_empty()
	_rate_label.text = "Производство в час: " + ", ".join(parts)


func _set_travel_text(label: Label, seconds: int) -> void:
	var left := maxi(0, int(seconds - _elapsed))
	label.text = "В пути к объекту · прибытие через %s" % RULES.clock_text(left)


func _first_resource(slot: Dictionary) -> String:
	var resources: Variant = slot.get("resources")
	if resources is Array and not (resources as Array).is_empty():
		return str((resources as Array)[0])
	return str(slot.get("resource", ""))


func _resource_name(code: String) -> String:
	var good := _dict_of(STORAGE_VIEW.GOODS.get(code, {}))
	return str(good.get("name", code))


func _bonus_text(bonus: Dictionary) -> String:
	var parts := PackedStringArray()
	for resource in bonus:
		var percent := int(bonus[resource])
		if percent > 0 and BONUS_LABELS.has(str(resource)):
			parts.append("+%d%% %s" % [percent, BONUS_LABELS[str(resource)]])
	return " · ".join(parts)


static func _dict_of(value: Variant) -> Dictionary:
	return value if value is Dictionary else {}


func _queue_action(action: String, slot_index: int) -> void:
	_pending_action = action
	_pending_slot = slot_index
	_confirm_label.text = RULES.confirm_prompt(action, _worker_state)
	_confirm_strip.visible = true


func _on_plot_clicked(index: int) -> void:
	_apply_plot_result(RULES.plot_click(_worker_state, _building, index))


func _on_plot_removed(index: int) -> void:
	_apply_plot_result(RULES.plot_remove(_worker_state, _building, index))


func _apply_plot_result(result: Dictionary) -> void:
	if result.has("message"):
		set_message(str(result["message"]))
	elif result.has("action"):
		_queue_action(str(result["action"]), int(result["slot_index"]))


# Таймеры места по ресурсам: цветная метка и время до следующей единицы, как в draw_worker_stats Python.
func _timer_line(entries: Array) -> HBoxContainer:
	var line := HBoxContainer.new()
	line.add_theme_constant_override("separation", 6)
	for entry in entries:
		var swatch := ColorRect.new()
		swatch.color = _resource_color(str(entry["resource"]))
		swatch.custom_minimum_size = Vector2(10, 10)
		swatch.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		line.add_child(swatch)
		var timer := {
			"label": _text("", TIMER_COLOR, 11),
			"resource": str(entry["resource"]),
			"timer": float(entry["timer"]),
			"progress": float(entry["progress"]),
		}
		line.add_child(timer["label"])
		_timer_labels.append(timer)
		_set_timer_text(timer)
	return line


func _set_timer_text(entry: Dictionary) -> void:
	var seconds := RULES.seconds_left(float(entry["timer"]), float(entry["progress"]), _elapsed)
	(entry["label"] as Label).text = "%s %s" % [_resource_name(str(entry["resource"])), RULES.clock_text(seconds)]


func _resource_color(code: String) -> Color:
	var good := _dict_of(STORAGE_VIEW.GOODS.get(code, {}))
	return good.get("color", STORAGE_VIEW.UNKNOWN_SWATCH)


# Описание следующего уровня для зданий без карточек, как production_desc в Python.
func _upgrade_description() -> String:
	return RULES.production_desc(_building, int(_upgrade.get("next_level", 0)))
