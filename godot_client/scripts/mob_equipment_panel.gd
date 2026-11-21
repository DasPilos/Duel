extends Control

signal closed

const Rules := preload("res://scripts/mob_profile_rules.gd")
const Style := preload("res://scripts/mob_profile_style.gd")

const PANEL_SIZE := Vector2(740, 470)
const CELL_SIZE := Vector2(124, 54)
const CELL_GAP := 12
const PICKER_WIDTH := 480.0
const ROW_HEIGHT := 34
const PICKER_MAX_ROWS := 9
# Кукла как в окне персонажа: слот -> [колонка, строка, подпись]
const SLOT_CELLS := {
	"ears": [0, 0, "Серьги"],
	"head": [2, 0, "Голова"],
	"neck": [4, 0, "Шея"],
	"back": [0, 1, "Плащ"],
	"body": [2, 1, "Доспех"],
	"ring": [4, 1, "Кольцо"],
	"hands": [0, 2, "Руки"],
	"weapon": [1, 2, "П рука"],
	"belt": [2, 2, "Пояс"],
	"shield": [3, 2, "Л рука"],
	"ring_2": [4, 2, "Кольцо"],
	"legs": [2, 3, "Ноги"],
	"feet": [2, 4, "Обувь"],
}

# Слот -> id предмета или null; словарь принадлежит окну параметров и правится на месте.
var equipment: Dictionary = {}
var slot_buttons: Dictionary = {}
var option_buttons: Array[Button] = []
var picker_slot := ""

var _rules: Dictionary = {}
var _stats: Dictionary = {}
var _level := 1
var _items: Array = []
var _items_by_id: Dictionary = {}
var _items_loaded := false
var _title: Label
var _slot_values: Dictionary = {}
var _picker_layer: ColorRect
var _picker_title: Label
var _picker_info: Label
var _picker_scroll: ScrollContainer
var _picker_list: VBoxContainer
var _manual_row: HBoxContainer
var _manual_input: LineEdit


func _init() -> void:
	visible = false
	mouse_filter = Control.MOUSE_FILTER_STOP
	_build_ui()
	_build_picker()


func setup(
	mob_name: String,
	rules: Dictionary,
	equipment_data: Dictionary,
	items: Array,
	items_loaded: bool,
) -> void:
	_rules = rules
	equipment = equipment_data
	_items = items
	_items_loaded = items_loaded
	_items_by_id.clear()
	for item in items:
		if item is Dictionary and item.has("id"):
			_items_by_id[int(item["id"])] = item
	_title.text = "Экипировка: %s" % mob_name
	_refresh_cells()


func open(stats: Dictionary, level: int) -> void:
	_stats = stats
	_level = level
	close_picker()
	_refresh_cells()
	visible = true


func finish() -> void:
	close_picker()
	visible = false
	closed.emit()


# Esc: сначала закрывает список предметов, затем само окно.
func handle_cancel() -> void:
	if picker_slot.is_empty():
		finish()
	else:
		close_picker()


func equipped_count() -> int:
	var count := 0
	for slot in SLOT_CELLS:
		if equipment.get(slot) != null:
			count += 1
	return count


func slot_items(slot: String) -> Array:
	var wanted := Rules.item_slot(slot)
	return _items.filter(func(item: Variant) -> bool:
		return item is Dictionary and str(item.get("equip_slot", "")) == wanted
	)


# Предметы слота, подходящие виду по характеристикам и уровню и не надетые в другом слоте.
func eligible_items(slot: String) -> Array:
	var worn_elsewhere := {}
	for other in equipment:
		if other != slot and equipment[other] != null:
			worn_elsewhere[int(equipment[other])] = true
	return slot_items(slot).filter(func(item: Dictionary) -> bool:
		return not worn_elsewhere.has(int(item["id"])) and Rules.item_fits(item, _stats, _level)
	)


func hidden_count(slot: String) -> int:
	var hidden := 0
	for item: Dictionary in slot_items(slot):
		if not Rules.item_fits(item, _stats, _level):
			hidden += 1
	return hidden


# Варианты списка: null («пусто») и id подходящих предметов.
func option_ids(slot: String) -> Array:
	var ids: Array = [null]
	for item: Dictionary in eligible_items(slot):
		ids.append(int(item["id"]))
	return ids


func open_slot(slot: String) -> void:
	if not SLOT_CELLS.has(slot):
		return
	picker_slot = slot
	_rebuild_picker()
	_picker_layer.visible = true


func close_picker() -> void:
	picker_slot = ""
	_picker_layer.visible = false


func pick(slot: String, item_id: Variant) -> void:
	equipment[slot] = null if item_id == null else int(item_id)
	close_picker()
	_refresh_cells()


func apply_manual_id() -> void:
	var text := _manual_input.text.strip_edges()
	if not text.is_valid_int() or text.to_int() <= 0:
		_picker_info.text = "ID предмета — целое число больше нуля."
		_picker_info.add_theme_color_override("font_color", Style.WARN_COLOR)
		return
	pick(picker_slot, text.to_int())


func _input(event: InputEvent) -> void:
	if not is_visible_in_tree() or picker_slot.is_empty():
		return
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_RIGHT:
		close_picker()
		get_viewport().set_input_as_handled()


func _build_ui() -> void:
	var shade := ColorRect.new()
	shade.color = Style.SHADE_COLOR
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	shade.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(shade)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(center)
	var window := PanelContainer.new()
	window.custom_minimum_size = PANEL_SIZE
	window.mouse_filter = Control.MOUSE_FILTER_STOP
	center.add_child(window)
	var margin := MarginContainer.new()
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 20)
	window.add_child(margin)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 8)
	margin.add_child(column)

	_title = Style.make_label("", Style.TEXT_COLOR, Style.TITLE_FONT_SIZE)
	column.add_child(_title)
	var hint := Style.make_label(
		"Клик по ячейке выбирает предмет. В списке только предметы, которые подходят по характеристикам и уровню.",
		Style.DIM_COLOR,
		Style.SMALL_FONT_SIZE,
	)
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(hint)

	var doll_center := CenterContainer.new()
	doll_center.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(doll_center)
	var doll := GridContainer.new()
	doll.columns = 5
	doll.add_theme_constant_override("h_separation", CELL_GAP)
	doll.add_theme_constant_override("v_separation", CELL_GAP)
	doll_center.add_child(doll)
	for row in range(5):
		for col in range(5):
			var slot := _slot_at(col, row)
			if slot.is_empty():
				var gap := Control.new()
				gap.custom_minimum_size = CELL_SIZE
				doll.add_child(gap)
			else:
				doll.add_child(_make_slot_button(slot))

	var footer := HBoxContainer.new()
	column.add_child(footer)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	footer.add_child(spacer)
	var done := Style.make_button("Готово", Vector2(140, 40))
	done.pressed.connect(finish)
	footer.add_child(done)


func _slot_at(col: int, row: int) -> String:
	for slot in SLOT_CELLS:
		var cell: Array = SLOT_CELLS[slot]
		if int(cell[0]) == col and int(cell[1]) == row:
			return str(slot)
	return ""


func _make_slot_button(slot: String) -> Button:
	var button := Style.make_button("", CELL_SIZE)
	button.pressed.connect(open_slot.bind(slot))
	var box := VBoxContainer.new()
	box.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT, Control.PRESET_MODE_MINSIZE, 6)
	box.alignment = BoxContainer.ALIGNMENT_CENTER
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_theme_constant_override("separation", 0)
	button.add_child(box)
	var caption := Style.make_label(str(SLOT_CELLS[slot][2]), Style.DIM_COLOR, Style.SMALL_FONT_SIZE)
	caption.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(caption)
	var value := Style.make_label("пусто", Style.OFF_COLOR)
	value.clip_text = true
	value.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	value.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(value)
	slot_buttons[slot] = button
	_slot_values[slot] = value
	return button


func _build_picker() -> void:
	_picker_layer = ColorRect.new()
	_picker_layer.color = Color(0.0, 0.0, 0.0, 0.35)
	_picker_layer.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_picker_layer.mouse_filter = Control.MOUSE_FILTER_STOP
	_picker_layer.visible = false
	_picker_layer.gui_input.connect(_on_picker_layer_input)
	add_child(_picker_layer)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_picker_layer.add_child(center)
	var picker := PanelContainer.new()
	picker.custom_minimum_size.x = PICKER_WIDTH
	picker.mouse_filter = Control.MOUSE_FILTER_STOP
	picker.add_theme_stylebox_override("panel", Style.flat(Style.MENU_COLOR, Style.BORDER_COLOR, 1, 6))
	center.add_child(picker)
	var margin := MarginContainer.new()
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 8)
	picker.add_child(margin)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 6)
	margin.add_child(column)
	_picker_title = Style.make_label("", Style.ACTIVE_COLOR, Style.HEADER_FONT_SIZE)
	column.add_child(_picker_title)
	_picker_info = Style.make_label("", Style.DIM_COLOR, Style.SMALL_FONT_SIZE)
	_picker_info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(_picker_info)
	_picker_scroll = ScrollContainer.new()
	_picker_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	column.add_child(_picker_scroll)
	_picker_list = VBoxContainer.new()
	_picker_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_picker_list.add_theme_constant_override("separation", 4)
	_picker_scroll.add_child(_picker_list)

	_manual_row = HBoxContainer.new()
	_manual_row.add_theme_constant_override("separation", 8)
	column.add_child(_manual_row)
	_manual_row.add_child(Style.make_label("ID предмета:"))
	_manual_input = LineEdit.new()
	_manual_input.custom_minimum_size = Vector2(110, 30)
	_manual_input.text_submitted.connect(func(_text: String) -> void: apply_manual_id())
	_manual_row.add_child(_manual_input)
	var apply := Style.make_button("Применить", Vector2(110, 30))
	apply.pressed.connect(apply_manual_id)
	_manual_row.add_child(apply)
	var clear := Style.make_button("Снять", Vector2(90, 30))
	clear.pressed.connect(func() -> void: pick(picker_slot, null))
	_manual_row.add_child(clear)


func _on_picker_layer_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed:
		close_picker()
		_picker_layer.accept_event()


func _refresh_cells() -> void:
	for slot in SLOT_CELLS:
		var value: Label = _slot_values[slot]
		var item_id: Variant = equipment.get(slot)
		if item_id == null:
			value.text = "пусто"
			value.add_theme_color_override("font_color", Style.OFF_COLOR)
			continue
		var item: Dictionary = _items_by_id.get(int(item_id), {})
		value.text = str(item.get("name", "предмет #%d" % int(item_id)))
		var fits := item.is_empty() or Rules.item_fits(item, _stats, _level)
		value.add_theme_color_override("font_color", Style.TEXT_COLOR if fits else Style.WARN_COLOR)


func _rebuild_picker() -> void:
	for child in _picker_list.get_children():
		_picker_list.remove_child(child)
		child.queue_free()
	option_buttons.clear()
	_picker_title.text = "Слот: %s" % str(SLOT_CELLS[picker_slot][2])
	_picker_info.add_theme_color_override("font_color", Style.DIM_COLOR)
	if not _items_loaded:
		_picker_info.text = "Список предметов не загружен: введите ID предмета из базы вручную."
		_picker_info.visible = true
		_picker_scroll.visible = false
		_manual_row.visible = true
		var current: Variant = equipment.get(picker_slot)
		_manual_input.text = "" if current == null else str(int(current))
		return
	_picker_scroll.visible = true
	_manual_row.visible = false
	var eligible := eligible_items(picker_slot)
	var info: Array[String] = []
	var hidden := hidden_count(picker_slot)
	if hidden > 0:
		info.append("скрыто по требованиям: %d" % hidden)
	if eligible.is_empty():
		info.append("нет подходящих предметов для этого вида")
	_picker_info.text = " · ".join(info)
	_picker_info.visible = not info.is_empty()
	_add_option(null)
	for item: Dictionary in eligible:
		_add_option(item)
	var rows := mini(PICKER_MAX_ROWS, eligible.size() + 1)
	_picker_scroll.custom_minimum_size.y = rows * ROW_HEIGHT


func _add_option(item: Variant) -> void:
	var item_id: Variant = null if item == null else int(item["id"])
	var row := Style.make_button("", Vector2(0, ROW_HEIGHT - 4))
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	if item_id == equipment.get(picker_slot):
		row.add_theme_stylebox_override("normal", Style.flat(Style.BUTTON_ON_COLOR))
	row.pressed.connect(pick.bind(picker_slot, item_id))
	var inner := HBoxContainer.new()
	inner.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT, Control.PRESET_MODE_MINSIZE, 8)
	inner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(inner)
	var name_label := Style.make_label(
		"пусто (без предмета)" if item == null else str(item.get("name", "")),
	)
	name_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	name_label.clip_text = true
	name_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	inner.add_child(name_label)
	if item != null:
		var requirements := Style.make_label(
			Rules.requirement_text(item, _rules),
			Style.DIM_COLOR,
			Style.SMALL_FONT_SIZE,
		)
		requirements.mouse_filter = Control.MOUSE_FILTER_IGNORE
		inner.add_child(requirements)
	row.set_meta("item_id", item_id)
	_picker_list.add_child(row)
	option_buttons.append(row)
