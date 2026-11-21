extends Node

# Очередь визуала боя. Шаги deck_battle_visual_state.gd проигрываются по порядку: клэш, урон с всплывающими
# числами, перетасовка, полёты стартового драфта и интро. Показ состояния идёт через сигнал display_requested;
# шаг show ждёт display_done(), если сцена запускает переход фазы. Пока идут шаги, карты не нажимаются
# (is_busy), и кнопки боя скрыты, как в Python, где ввод принимается только в фазах планирования и драфта.

signal display_requested(state: Dictionary, transition: String)

const VISUAL := preload("res://scripts/deck_battle_visual_state.gd")
const RULES := preload("res://scripts/deck_battle_layout_rules.gd")
const CARD_VIEW_SCRIPT := preload("res://scripts/deck_battle_card_view.gd")

var _view
var _layer: Control
var _queue: Array[Dictionary] = []
var _elapsed := 0.0
var _started := false
var _waiting := false
var _advancing := false
var _battle_id := ""
var _seen_key := ""
var _tail: Dictionary = {}
var _texts: Array[Dictionary] = []
var _flights: Array[Dictionary] = []
var _project_dir := ""
var _layout: Dictionary = RULES.STANDARD_LAYOUT


func _process(delta: float) -> void:
	advance(delta)


# Визуал рисует на слое view.overlay_layer() в координатах макета 1920x1080.
func attach(view) -> void:
	_view = view
	_layer = view.overlay_layer()


func is_busy() -> bool:
	return not _queue.is_empty() and str(_queue[0].get("kind", "")) != VISUAL.KIND_SHOW


# latest — пришедший снимок (ответ или опрос), displayed — что сейчас показано, context — action и card_key
# хода игрока и allow_transition (false для опроса). Ключ розыгрыша проигрывается один раз; новый бой сбрасывает
# очередь и только запоминает текущий обмен.
func submit(latest: Dictionary, displayed: Dictionary, context: Dictionary = {}) -> void:
	if _project_dir.is_empty():
		_project_dir = CARD_VIEW_SCRIPT.project_dir()
	_layout = RULES.layout_for_state(latest)
	var battle_id := str(latest.get("battle_id", ""))
	var allow_transition := bool(context.get("allow_transition", true))
	if battle_id != _battle_id:
		_forget_battle()
		_battle_id = battle_id
		_seen_key = VISUAL.exchange_key(latest)
		var fresh := displayed.is_empty() or str(displayed.get("battle_id", "")) != battle_id
		var steps: Array[Dictionary] = []
		if VISUAL.is_starting_draft(latest) and fresh:
			steps = VISUAL.plan_battle_start(latest, _project_dir)
		else:
			steps = VISUAL.plan(displayed, latest, {"allow_transition": allow_transition}, _project_dir)
		_enqueue(steps, latest)
		return
	var previous: Dictionary = _tail if not _queue.is_empty() else displayed
	if VISUAL.signature(latest) == VISUAL.signature(previous):
		return
	var key := VISUAL.exchange_key(latest)
	var new_exchange := not key.is_empty() and key != _seen_key
	if new_exchange:
		_seen_key = key
	var steps := VISUAL.plan(previous, latest, {
		"new_exchange": new_exchange,
		"action": str(context.get("action", "")),
		"card_key": str(context.get("card_key", "")),
		"allow_transition": allow_transition,
	}, _project_dir)
	_enqueue(steps, latest)


# Сцена сообщает, что показала состояние шага show (после перехода фазы, если он был).
func display_done() -> void:
	if not _waiting:
		return
	_waiting = false
	advance(0.0)


# Конец боя или выход с экрана боя: очередь, всплывающие числа и полёты убираются, обмен забывается.
func clear() -> void:
	_forget_battle()


# Продвигает очередь на delta секунд; вызывается из _process, тесты вызывают напрямую.
func advance(delta: float) -> void:
	if _advancing:
		return
	_advancing = true
	var remaining := maxf(delta, 0.0)
	_advance_texts(remaining)
	while not _queue.is_empty() and not _waiting:
		if not _started:
			_started = true
			_start_step(_queue[0])
			if _waiting or _queue.is_empty():
				break
		var left := float(_queue[0].get("duration", 0.0)) - _elapsed
		if remaining < left:
			_elapsed += remaining
			break
		remaining -= left
		_finish_step()
	_update_flights()
	_advancing = false


func queued_kinds() -> Array:
	var kinds: Array = []
	for step in _queue:
		kinds.append(str(step.get("kind", "")))
	return kinds


func is_waiting_display() -> bool:
	return _waiting


func floating_texts() -> Array:
	var result: Array = []
	for item in _texts:
		result.append({
			"text": item["text"],
			"color": item["color"],
			"x": item["x"],
			"y": item["y"],
			"remaining": item["remaining"],
			"kind": item["kind"],
		})
	return result


func flight_count() -> int:
	return _flights.size()


func flight_node(index: int) -> Control:
	return _flights[index]["node"] as Control


func _enqueue(steps: Array[Dictionary], latest: Dictionary) -> void:
	for step in steps:
		if str(step.get("kind", "")) == VISUAL.KIND_SHOW and not str(step.get("transition", "")).is_empty():
			_drop_pending()
			break
	_queue.append_array(steps)
	_tail = latest.duplicate(true)
	advance(0.0)


func _start_step(step: Dictionary) -> void:
	var kind := str(step.get("kind", ""))
	var display: Dictionary = step.get("display", {})
	if kind == VISUAL.KIND_SHOW:
		_waiting = true
		display_requested.emit(display, str(step.get("transition", "")))
		return
	if kind == VISUAL.KIND_DAMAGE:
		_spawn_texts(step.get("exchange", []))
	if kind == VISUAL.KIND_PICK:
		var source := _source_center(int(step.get("source_index", -1)))
		display_requested.emit(display, "")
		_spawn_flight(step["entry"], source, _hand_center(int(step.get("hand_count", 1))), RULES.CARD_SIZE, RULES.CARD_SIZE, false, 0.0, RULES.PLAYER_DRAFT_PICK_MOVE_SECONDS)
		return
	if kind == VISUAL.KIND_ENEMY_PICK:
		display_requested.emit(display, "")
		_spawn_flight(step["entry"], (_layout["deck"] as Rect2).get_center(), _enemy_hand_center(int(step.get("enemy_count", 1))), RULES.CARD_SIZE, RULES.CARD_SIZE, false, 0.0, RULES.TABLE_TO_HAND_MOVE_SECONDS)
		return
	display_requested.emit(display, "")
	if kind == VISUAL.KIND_REVEAL:
		for flight_variant in step.get("flights", []):
			var flight: Dictionary = flight_variant
			_spawn_flight(flight["entry"], flight["from"], flight["to"], flight["from_size"], flight["to_size"], bool(flight["flip"]), float(flight["start"]), float(flight["duration"]))


func _finish_step() -> void:
	_free_flights()
	_queue.pop_front()
	_elapsed = 0.0
	_started = false


# Переход фазы: шаги старой фазы и всплывающие числа снимаются, показ переходит к новому состоянию сразу.
func _drop_pending() -> void:
	_free_flights()
	_clear_texts()
	_queue.clear()
	_elapsed = 0.0
	_started = false
	_waiting = false


func _forget_battle() -> void:
	_drop_pending()
	_battle_id = ""
	_seen_key = ""
	_tail = {}


# Центр карты стола в момент начала шага: источник полёта берётся с экрана до смены показа.
func _source_center(index: int) -> Vector2:
	if _view != null and index >= 0 and _view.has_method("card_rect_of"):
		var rect: Rect2 = _view.card_rect_of(RULES.ZONE_TABLE, index)
		if rect.size != Vector2.ZERO:
			return rect.get_center()
	return (_layout["card_table"] as Rect2).get_center()


func _hand_center(count: int) -> Vector2:
	var total := maxi(1, count)
	return RULES.row_card_rect(_layout["player_hand"], total, total - 1).get_center()


func _enemy_hand_center(count: int) -> Vector2:
	var total := maxi(1, count)
	return RULES.row_card_rect(_layout["enemy_hand"], total, total - 1).get_center()


func _spawn_flight(entry: Dictionary, from_center: Vector2, to_center: Vector2, from_size: Vector2, to_size: Vector2, flip: bool, start: float, duration: float) -> void:
	if _layer == null:
		return
	var node = CARD_VIEW_SCRIPT.new()
	_layer.add_child(node)
	node.configure(entry)
	node.call("place_flight", Rect2(from_center - from_size / 2.0, from_size), flip)
	_flights.append({
		"node": node,
		"from": from_center,
		"to": to_center,
		"from_size": from_size,
		"to_size": to_size,
		"flip": flip,
		"start": start,
		"duration": duration,
	})


# card_area.py: рисунок полёта идёт от старта задержки, до неё карта не видна.
func _update_flights() -> void:
	for flight in _flights:
		var node: Control = flight["node"]
		if not is_instance_valid(node):
			continue
		var start := float(flight["start"])
		if _elapsed < start:
			node.visible = false
			continue
		node.visible = true
		var duration := maxf(0.0001, float(flight["duration"]))
		var progress := clampf((_elapsed - start) / duration, 0.0, 1.0)
		var frame := VISUAL.flight_frame(flight["from"], flight["to"], flight["from_size"], flight["to_size"], progress, bool(flight["flip"]))
		node.call("place_flight", frame["rect"], bool(frame["back"]))


func _free_flights() -> void:
	for flight in _flights:
		var node: Node = flight["node"]
		if is_instance_valid(node):
			node.queue_free()
	_flights.clear()


func _spawn_texts(exchange: Variant) -> void:
	if not exchange is Array:
		return
	for spec in VISUAL.floating_specs(exchange, _alive_texts(), _layout):
		_add_text(spec)


func _alive_texts() -> Array:
	var alive: Array = []
	for item in _texts:
		alive.append({"x": item["x"], "y": item["y"], "remaining": item["remaining"]})
	return alive


# Подпись центрируется на (x, y), как FloatingText в duel_resolver.py; картинка HP-N центрируется на тех же
# координатах, а подпись ставится над её низом (FloatingImage.draw: rect.bottom - 28).
func _add_text(spec: Dictionary) -> void:
	if _layer == null:
		return
	var holder := Control.new()
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var label_center := Vector2(float(spec["x"]), float(spec["y"]))
	if str(spec["kind"]) == "image":
		var texture := CARD_VIEW_SCRIPT.load_texture(RULES.asset_path(_project_dir, str(spec["asset"])))
		if texture != null:
			var picture := TextureRect.new()
			picture.texture = texture
			picture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			picture.stretch_mode = TextureRect.STRETCH_SCALE
			picture.size = texture.get_size()
			picture.position = label_center - texture.get_size() / 2.0
			picture.mouse_filter = Control.MOUSE_FILTER_IGNORE
			holder.add_child(picture)
			label_center = Vector2(picture.position.x + picture.size.x / 2.0, picture.position.y + picture.size.y - RULES.FLOATING_IMAGE_LABEL_LIFT)
	var label := _label(str(spec["text"]), spec["color"], int(spec["font_size"]))
	label.position = label_center - RULES.FLOATING_TEXT_BOX / 2.0
	label.size = RULES.FLOATING_TEXT_BOX
	holder.add_child(label)
	_layer.add_child(holder)
	_texts.append({
		"x": float(spec["x"]),
		"y": float(spec["y"]),
		"remaining": RULES.FLOATING_TEXT_SECONDS,
		"node": holder,
		"text": str(spec["text"]),
		"color": spec["color"],
		"kind": str(spec["kind"]),
	})


func _label(text: String, color: Color, font_size: int) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_override("font", CARD_VIEW_SCRIPT.ui_font())
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return label


func _advance_texts(delta: float) -> void:
	var alive: Array[Dictionary] = []
	for item in _texts:
		item["remaining"] = float(item["remaining"]) - delta
		if float(item["remaining"]) > 0.0:
			alive.append(item)
		elif is_instance_valid(item["node"]):
			(item["node"] as Node).queue_free()
	_texts = alive


func _clear_texts() -> void:
	for item in _texts:
		if is_instance_valid(item["node"]):
			(item["node"] as Node).queue_free()
	_texts.clear()
