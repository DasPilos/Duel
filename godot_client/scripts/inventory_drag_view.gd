extends Control

# Сетка рюкзака 10×5 и «кукла» экипировки из ui/inventory_window.py. Вид ничего не отправляет: он рисует состояние
# и эмитит намерения, а окно-владелец отправляет их на сервер. Пока действие ждёт ответа, вид не эмитит новых намерений;
# владелец сообщает результат через resolve_action. Раскладка в пикселях Python, масштаб задаёт родитель.

signal move_requested(from_slot: int, to_slot: int)
signal equip_requested(slot_index: int, slot: String)
signal unequip_requested(slot: String, target_slot: int)
signal use_requested(slot_index: int)
signal drop_requested(slot_index: int)
signal selection_changed(target: Array)
signal drop_confirm_changed(active: bool)
# message_requested сохранён для окон без цветов; message_colored несёт цвет как в ui/inventory_window.py.
signal message_requested(text: String, is_error: bool)
signal message_colored(text: String, color: Color)

const RULES := preload("res://scripts/inventory_drag_rules.gd")
const CARD := preload("res://scripts/character_card.gd")
const ITEM_ICON_RULES := preload("res://scripts/deck_item_icon_rules.gd")

const BACKPACK_COLS := 10
const BACKPACK_ROWS := 5
const CELL := 62.0
const GAP := 4.0
const CELL_SIZE := Vector2(62.0, 62.0)
const ICON_BOX := 62
const VIEW_SIZE := Vector2(1120.0, 440.0)
# Рамка 440×440 даёт слоты в тех же координатах, что Python при его рамке карточки
const PAPERDOLL_FRAME := Rect2(0.0, 0.0, 440.0, 440.0)
const GRID_ORIGIN := Vector2(464.0, 56.0)
const GOLD := Color8(255, 215, 120)
const HIGHLIGHT_COLOR := Color8(120, 220, 120)
const PLACEHOLDER_COLOR := Color(0.35, 0.31, 0.35)
const DRAGGED_ALPHA := 70.0 / 255.0
const GHOST_ALPHA := 210.0 / 255.0
const DROP_CONFIRM_SECONDS := 3.0
# Режим «только рюкзак»: без «куклы», экипировка перетаскивается на карточку персонажа.
const BAG_ONLY_ORIGIN := Vector2(0.0, 28.0)
const BAG_ONLY_SIZE := Vector2(656.0, 360.0)
const TOOLTIP_FONT_SIZE := 13
const TOOLTIP_LINE := 16.0
const TOOLTIP_PAD := 6.0
const TOOLTIP_MAX_WIDTH := 240.0
const HEADER_FONT_SIZE := 20
const LABEL_FONT_SIZE := 18
const QUANTITY_FONT_SIZE := 15
const PLACEHOLDER_FONT_SIZE := 24

var _inventory: Dictionary = {}
var _equipment: Dictionary = {}
var _capacity := 0
var _selected: Array = []
var _pressed: Array = []
var _press_position := Vector2.ZERO
var _dragging := false
# Действие, переданное владельцу окна: текст успеха и выбор применяются только после resolve_action.
var _pending: Dictionary = {}
var _drop_slot := -1
var _cell_rects: Array[Rect2] = []
var _slot_rects: Dictionary = {}
var _styles: Dictionary = {}
var _assets_root := ""
var _drop_timer: Timer
var _bag_only := false

signal drop_outside_requested(source: Array, global_point: Vector2)


func _init() -> void:
	size = VIEW_SIZE
	custom_minimum_size = VIEW_SIZE
	focus_mode = Control.FOCUS_CLICK
	_slot_rects = RULES.paperdoll_slot_rects(PAPERDOLL_FRAME)
	_layout_cells()
	_assets_root = ITEM_ICON_RULES.default_assets_root(ProjectSettings.globalize_path("res://").trim_suffix("/"))
	_drop_timer = Timer.new()
	_drop_timer.one_shot = true
	_drop_timer.wait_time = DROP_CONFIRM_SECONDS
	_drop_timer.timeout.connect(_on_drop_confirm_timeout)
	add_child(_drop_timer)
	gui_input.connect(_on_gui_input)
	mouse_exited.connect(queue_redraw)


# Только рюкзак: кукла не рисуется, цели экипировки здесь не нужны.
func set_bag_only(enabled: bool) -> void:
	_bag_only = enabled
	_slot_rects = {} if enabled else RULES.paperdoll_slot_rects(PAPERDOLL_FRAME)
	_layout_cells()
	custom_minimum_size = BAG_ONLY_SIZE if enabled else VIEW_SIZE
	size = custom_minimum_size
	queue_redraw()


func _grid_origin() -> Vector2:
	return BAG_ONLY_ORIGIN if _bag_only else GRID_ORIGIN


func _layout_cells() -> void:
	_cell_rects.clear()
	for index in BACKPACK_COLS * BACKPACK_ROWS:
		var column := index % BACKPACK_COLS
		var row := floori(float(index) / BACKPACK_COLS)
		_cell_rects.append(Rect2(_grid_origin() + Vector2(column * (CELL + GAP), row * (CELL + GAP)), CELL_SIZE))


# Состояние с сервера. Выбор сбрасывается, если выбранная ячейка опустела.
func set_items(items: Array, equipment: Dictionary, capacity: int) -> void:
	_inventory = {}
	for item in items:
		if item is Dictionary:
			_inventory[int(item.get("slot_index", -1))] = item
	_equipment = {}
	for slot in equipment:
		if equipment[slot] is Dictionary:
			_equipment[str(slot)] = equipment[slot]
	_capacity = capacity
	if not _selected.is_empty() and item_at(_selected).is_empty():
		_selected = []
	selection_changed.emit(_selected)
	queue_redraw()


func item_at(target: Array) -> Dictionary:
	if target.is_empty():
		return {}
	if str(target[0]) == RULES.KIND_BAG:
		return _inventory.get(int(target[1]), {})
	if str(target[0]) == RULES.KIND_EQUIP:
		return _equipment.get(str(target[1]), {})
	return {}


func target_at(point: Vector2) -> Array:
	for index in _cell_rects.size():
		if _cell_rects[index].has_point(point):
			return [RULES.KIND_BAG, index]
	for slot in _slot_rects:
		var rect: Rect2 = _slot_rects[slot]
		if rect.has_point(point):
			return [RULES.KIND_EQUIP, slot]
	return []


func selected_target() -> Array:
	return _selected.duplicate()


func selected_item() -> Dictionary:
	return item_at(_selected)


func highlight_slot() -> String:
	return RULES.highlight_slot(_dragging, _pressed, item_at(_pressed))


func is_dragging() -> bool:
	return _dragging


func cell_rect(index: int) -> Rect2:
	return _cell_rects[index]


# Вид рисуется в пикселях Python; хозяин с другим масштабом получает рамку по размеру масштабированного вида.
static func scaled_host(view: Control, factor: float) -> Control:
	view.scale = Vector2(factor, factor)
	var host := Control.new()
	host.custom_minimum_size = VIEW_SIZE * factor
	host.mouse_filter = Control.MOUSE_FILTER_IGNORE
	host.add_child(view)
	return host


func slot_rect(slot: String) -> Rect2:
	return _slot_rects.get(slot, Rect2())


# Правый клик и кнопка «Надеть / Снять / Использовать» в окне: одно и то же действие.
func quick_action(target: Array) -> void:
	_apply_decision(RULES.quick_decision(target, item_at(target)))


# Первое действие подтверждает выброс на 3 секунды, второе в этот срок отправляет drop_requested.
func request_drop(target: Array) -> void:
	var item := item_at(target)
	if item.is_empty() or str(target[0]) != RULES.KIND_BAG:
		return
	if not _pending.is_empty():
		_say(RULES.BUSY_MESSAGE, RULES.BAD_COLOR)
		return
	var slot := int(target[1])
	var item_name := RULES.text_of(item, "name", "Предмет")
	if drop_confirm_active() and _drop_slot == slot:
		reset_drop_confirm()
		_start_action({"action": RULES.ACTION_DROP, "params": {"slot_index": slot}, "message": "Выброшено: %s" % item_name})
		return
	reset_drop_confirm()
	_drop_slot = slot
	_drop_timer.start()
	drop_confirm_changed.emit(true)
	_say("Нажмите «Точно?», чтобы выбросить: %s" % item_name, RULES.BAD_COLOR)
	queue_redraw()


func drop_confirm_active() -> bool:
	return _drop_slot >= 0 and not _drop_timer.is_stopped()


func reset_drop_confirm() -> void:
	var was_active := drop_confirm_active()
	_drop_timer.stop()
	_drop_slot = -1
	if was_active:
		drop_confirm_changed.emit(false)
	queue_redraw()


func reset_interaction() -> void:
	_pending = {}
	_pressed = []
	_dragging = false
	reset_drop_confirm()
	_set_selection([])


func _on_drop_confirm_timeout() -> void:
	_drop_slot = -1
	drop_confirm_changed.emit(false)
	queue_redraw()


func _on_gui_input(event: InputEvent) -> void:
	var button_event := event as InputEventMouseButton
	if button_event != null:
		_on_mouse_button(button_event)
		return
	var motion := event as InputEventMouseMotion
	if motion != null:
		if not _pressed.is_empty() and not _dragging:
			_dragging = RULES.is_drag_started(_press_position, motion.position)
		queue_redraw()
		return
	var key_event := event as InputEventKey
	if key_event != null and key_event.pressed and not key_event.echo and key_event.keycode == KEY_DELETE and not _selected.is_empty():
		request_drop(_selected)
		accept_event()


func _on_mouse_button(event: InputEventMouseButton) -> void:
	if event.button_index == MOUSE_BUTTON_LEFT:
		if event.pressed:
			_press(event.position)
		else:
			_release(event.position)
		accept_event()
	elif event.button_index == MOUSE_BUTTON_RIGHT and event.pressed:
		var target := target_at(event.position)
		if not item_at(target).is_empty():
			_set_selection(target)
			quick_action(target)
		accept_event()


func _press(point: Vector2) -> void:
	var target := target_at(point)
	if not target.is_empty() and not item_at(target).is_empty():
		_pressed = target
		_press_position = point
		_dragging = false
		if target != _selected:
			reset_drop_confirm()
		_set_selection(target)
	elif not target.is_empty():
		_set_selection([])


func _release(point: Vector2) -> void:
	if not _pressed.is_empty() and _dragging:
		if target_at(point).is_empty() and str(_pressed[0]) == RULES.KIND_BAG:
			# Отпущено вне рюкзака: окно мира решает, это карточка персонажа или нет.
			drop_outside_requested.emit(_pressed.duplicate(), get_global_mouse_position())
		else:
			_apply_decision(RULES.drop_decision(_pressed, target_at(point), item_at(_pressed)))
	_pressed = []
	_dragging = false
	queue_redraw()


# Сообщение уходит текстом с флагом ошибки для прежних владельцев и текстом с цветом для окна экономики.
func _say(text: String, color: Color) -> void:
	message_requested.emit(text, color == RULES.BAD_COLOR)
	message_colored.emit(text, color)


# Внешний источник решения (сброс на карточку персонажа) идёт тем же путём, что и сброс внутри сетки.
func apply_decision(decision: Dictionary) -> void:
	_apply_decision(decision)


func _apply_decision(decision: Dictionary) -> void:
	var action := str(decision.get("action", RULES.ACTION_NONE))
	if action == RULES.ACTION_NONE:
		var message := str(decision.get("message", ""))
		if not message.is_empty():
			_say(message, RULES.BAD_COLOR if bool(decision.get("is_error", false)) else RULES.TEXT_DIM_COLOR)
		queue_redraw()
		return
	_start_action(decision)


# Действие уходит владельцу окна. Пока оно ждёт ответа, следующие действия не отправляются.
func _start_action(decision: Dictionary) -> void:
	if not _pending.is_empty():
		_say(RULES.BUSY_MESSAGE, RULES.BAD_COLOR)
		return
	_pending = decision
	var action := str(decision["action"])
	var params: Dictionary = decision.get("params", {})
	if action == RULES.ACTION_MOVE:
		move_requested.emit(int(params["from_slot"]), int(params["to_slot"]))
	elif action == RULES.ACTION_EQUIP:
		equip_requested.emit(int(params["slot_index"]), str(params["slot"]))
	elif action == RULES.ACTION_UNEQUIP:
		unequip_requested.emit(str(params["slot"]), int(params["target_slot"]))
	elif action == RULES.ACTION_USE:
		use_requested.emit(int(params["slot_index"]))
	elif action == RULES.ACTION_DROP:
		drop_requested.emit(int(params["slot_index"]))
	queue_redraw()


# Ответ сервера. Успех переводит выбор к цели и показывает текст действия; у переноса текста нет, строка очищается.
# Ошибка ничего не меняет: выбор остаётся у источника, как в Python после неудачного _request.
func resolve_action(success: bool) -> void:
	var decision := _pending
	_pending = {}
	if success and not decision.is_empty():
		if decision.has("select"):
			_set_selection(decision["select"])
		_say(str(decision.get("message", "")), RULES.success_color(str(decision.get("action", ""))))
	queue_redraw()


func _set_selection(target: Array) -> void:
	if target == _selected:
		return
	_selected = target.duplicate()
	selection_changed.emit(_selected)
	queue_redraw()


func _is_pressed(target: Array) -> bool:
	return _dragging and _pressed == target


func _get_tooltip(_at_position: Vector2) -> String:
	return ""


# Подсказка рисуется самим видом маленьким шрифтом (см. _draw_hover_tooltip).
func _draw() -> void:
	if not _bag_only:
		_draw_paperdoll()
	_draw_backpack()
	_draw_hover_tooltip()
	if _dragging:
		_draw_drag_ghost()


# Строки подсказки предмета под точкой: [текст, цвет]; пусто, если тащим или точка мимо предмета.
func tooltip_lines_at(point: Vector2) -> Array:
	if _dragging:
		return []
	var target := target_at(point)
	if target.is_empty():
		return []
	var item := item_at(target)
	if item.is_empty():
		return []
	return RULES.item_lines(item)


func _draw_hover_tooltip() -> void:
	var lines := tooltip_lines_at(get_local_mouse_position())
	if lines.is_empty():
		return
	var mouse := get_local_mouse_position()
	var font := get_theme_default_font()
	var width := 0.0
	for line in lines:
		width = maxf(width, font.get_string_size(str(line[0]), HORIZONTAL_ALIGNMENT_LEFT, -1, TOOLTIP_FONT_SIZE).x)
	width = minf(width, TOOLTIP_MAX_WIDTH)
	var box_size := Vector2(width + TOOLTIP_PAD * 2.0, TOOLTIP_LINE * lines.size() + TOOLTIP_PAD * 2.0)
	var position := mouse + Vector2(14.0, 14.0)
	position.x = clampf(position.x, 0.0, size.x - box_size.x)
	position.y = clampf(position.y, 0.0, size.y - box_size.y)
	draw_style_box(_style(Color(0.09, 0.1, 0.12, 0.95), Color(0.57, 0.52, 0.44), 1, 4), Rect2(position, box_size))
	var y := position.y + TOOLTIP_PAD + TOOLTIP_LINE - 4.0
	for line in lines:
		draw_string(font, Vector2(position.x + TOOLTIP_PAD, y), str(line[0]), HORIZONTAL_ALIGNMENT_LEFT, width, TOOLTIP_FONT_SIZE, line[1])
		y += TOOLTIP_LINE


func _draw_paperdoll() -> void:
	var center := PAPERDOLL_FRAME.get_center()
	draw_circle(Vector2(center.x, center.y - 40.0), 18.0, CARD.FIGURE_COLOR)
	draw_rect(Rect2(center.x - 24.0, center.y - 18.0, 48.0, 80.0), CARD.FIGURE_COLOR)
	var mouse := get_local_mouse_position()
	var highlight := highlight_slot()
	for slot in _slot_rects:
		var rect: Rect2 = _slot_rects[slot]
		var target := [RULES.KIND_EQUIP, slot]
		var item := item_at(target)
		var fill: Color = CARD.SLOT_HOVER if rect.has_point(mouse) else CARD.SLOT_BG
		var border: Color = RULES.rarity_color(item, CARD.SLOT_BORDER) if not item.is_empty() else CARD.SLOT_BORDER
		var border_width := 2
		if slot == highlight:
			border = HIGHLIGHT_COLOR
			border_width = 3
		draw_style_box(_style(Color(fill, CARD.SLOT_ALPHA), border, border_width, 6), rect)
		if item.is_empty():
			_draw_fitted_text(rect, RULES.slot_label(slot), CARD.SLOT_LABEL_COLOR)
		else:
			_draw_item_icon(rect, item, DRAGGED_ALPHA if _is_pressed(target) else 1.0)
		if _selected == target:
			draw_style_box(_style(Color(0.0, 0.0, 0.0, 0.0), GOLD, 2, 8), rect.grow(3.0))


func _draw_backpack() -> void:
	draw_string(get_theme_default_font(), Vector2(_grid_origin().x, _grid_origin().y - 12.0),
		"РЮКЗАК   %d / %d" % [_inventory.size(), _capacity], HORIZONTAL_ALIGNMENT_LEFT, -1, HEADER_FONT_SIZE, GOLD)
	var mouse := get_local_mouse_position()
	for index in _cell_rects.size():
		var rect := _cell_rects[index]
		var target := [RULES.KIND_BAG, index]
		var item := item_at(target)
		var selected := _selected == target
		var fill: Color = CARD.SLOT_HOVER if rect.has_point(mouse) else CARD.SLOT_BG
		var border: Color = RULES.rarity_color(item, CARD.SLOT_BORDER) if not item.is_empty() else CARD.SLOT_BORDER
		draw_style_box(_style(fill, border, 3 if selected else 2, 6), rect)
		if selected:
			draw_style_box(_style(Color(0.0, 0.0, 0.0, 0.0), GOLD, 2, 8), rect.grow(3.0))
		if item.is_empty():
			continue
		_draw_item_icon(rect, item, DRAGGED_ALPHA if _is_pressed(target) else 1.0)
		var quantity := int(item.get("quantity", 1))
		if quantity > 1:
			_draw_quantity(rect, quantity)


func _draw_drag_ghost() -> void:
	var item := item_at(_pressed)
	if item.is_empty():
		return
	_draw_item_icon(Rect2(get_local_mouse_position() - CELL_SIZE / 2.0, CELL_SIZE), item, GHOST_ALPHA)


func _draw_item_icon(rect: Rect2, item: Dictionary, alpha: float) -> void:
	var texture := ITEM_ICON_RULES.icon_texture(_assets_root, ITEM_ICON_RULES.item_key(item), ICON_BOX)
	if texture != null:
		draw_texture(texture, rect.get_center() - texture.get_size() / 2.0, Color(1.0, 1.0, 1.0, alpha))
		return
	var tile := Rect2(rect.position + Vector2(13.0, 13.0), Vector2(36.0, 36.0))
	draw_style_box(_style(Color(PLACEHOLDER_COLOR, alpha), Color(0.0, 0.0, 0.0, 0.0), 0, 6), tile)
	var letter := RULES.text_of(item, "name", "?").substr(0, 1).to_upper()
	_draw_text_centered(tile, letter, Color(0.9, 0.87, 0.8, alpha), PLACEHOLDER_FONT_SIZE)


func _draw_quantity(rect: Rect2, quantity: int) -> void:
	var font := get_theme_default_font()
	var text := str(quantity)
	var width := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, QUANTITY_FONT_SIZE).x
	var baseline := Vector2(rect.end.x - 5.0 - width, rect.end.y - 6.0)
	draw_string(font, baseline + Vector2(1.0, 1.0), text, HORIZONTAL_ALIGNMENT_LEFT, -1, QUANTITY_FONT_SIZE, Color.BLACK)
	draw_string(font, baseline, text, HORIZONTAL_ALIGNMENT_LEFT, -1, QUANTITY_FONT_SIZE, Color.WHITE)


func _draw_fitted_text(rect: Rect2, text: String, color: Color) -> void:
	var font := get_theme_default_font()
	var font_size := LABEL_FONT_SIZE
	while font_size > 10 and font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x > rect.size.x - 6.0:
		font_size -= 1
	_draw_text_centered(rect, text, color, font_size)


func _draw_text_centered(rect: Rect2, text: String, color: Color, font_size: int) -> void:
	var font := get_theme_default_font()
	var width := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x
	var baseline := rect.get_center().y + (font.get_ascent(font_size) - font.get_descent(font_size)) / 2.0
	draw_string(font, Vector2(rect.get_center().x - width / 2.0, baseline), text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, color)


func _style(fill: Color, border: Color, border_width: int, radius: int) -> StyleBoxFlat:
	var key := "%s|%s|%d|%d" % [fill.to_html(), border.to_html(), border_width, radius]
	if not _styles.has(key):
		var style := StyleBoxFlat.new()
		style.bg_color = fill
		style.border_color = border
		style.set_border_width_all(border_width)
		style.set_corner_radius_all(radius)
		_styles[key] = style
	return _styles[key]
