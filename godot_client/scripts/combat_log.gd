extends Control

const HISTORY_LIMIT := 500
const VISIBLE_SECONDS := 30.0
const FADE_SECONDS := 5.0
const APPEAR_INTERVAL := 0.6
# Сколько строк может ждать в очереди. Больше — лишние показываем сразу, иначе лог отстаёт от боя.
const MAX_PENDING_LINES := 3
const SIDE_WIDTH := 200.0
const SIDE_HEIGHT := 200.0
const SIDE_TOP := 293.0
const SIDE_RIGHT_MARGIN := 7.0
const LINE_HEIGHT := 13.0
const FONT_SIZE := 11
const FULL_SIZE := Vector2(480, 427)
const SCROLL_STEP := 3
const DEFAULT_COLOR := Color8(230, 230, 230)
const TITLE_COLOR := Color8(220, 200, 140)
const TITLE_TEXT := "Полный лог боя (L или ESC - закрыть, колесо - прокрутка)"

var _clock := 0.0
var _appear_timer := 0.0
var _pending: Array = []
var _visible_entries: Array = []
var _history: Array = []
var _full_open := false
var _full_scroll := 0


func _init() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	z_index = 95


func add(text: String, color: Color = DEFAULT_COLOR) -> void:
	var entry := {"text": text, "color": color}
	_pending.append(entry)
	_history.append(entry)
	while _history.size() > HISTORY_LIMIT:
		_history.pop_front()


func captures_keyboard() -> bool:
	return _full_open


func toggle_full() -> void:
	_full_open = not _full_open
	_full_scroll = 0
	mouse_filter = Control.MOUSE_FILTER_STOP if _full_open else Control.MOUSE_FILTER_IGNORE
	queue_redraw()


func close_full() -> void:
	if _full_open:
		toggle_full()


func _show_pending_entry() -> void:
	var entry: Dictionary = _pending.pop_front()
	entry["shown_at"] = _clock
	_visible_entries.append(entry)


func _process(delta: float) -> void:
	_clock += delta
	_appear_timer += delta
	while _pending.size() > MAX_PENDING_LINES:
		_show_pending_entry()
	if not _pending.is_empty() and _appear_timer >= APPEAR_INTERVAL:
		_appear_timer = 0.0
		_show_pending_entry()
	var lifetime := VISIBLE_SECONDS + FADE_SECONDS
	_visible_entries = _visible_entries.filter(func(entry: Dictionary) -> bool:
		return _clock - float(entry["shown_at"]) < lifetime
	)
	queue_redraw()


func _gui_input(event: InputEvent) -> void:
	if not _full_open or not event is InputEventMouseButton or not event.pressed:
		return
	if event.button_index == MOUSE_BUTTON_WHEEL_UP:
		_full_scroll = maxi(0, _full_scroll - SCROLL_STEP)
	elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
		_full_scroll += SCROLL_STEP
	else:
		return
	accept_event()
	queue_redraw()


func _draw() -> void:
	var font := get_theme_default_font()
	_draw_side_panel(font)
	if _full_open:
		_draw_full_log(font)


func _draw_side_panel(font: Font) -> void:
	var rect := Rect2(size.x - SIDE_RIGHT_MARGIN - SIDE_WIDTH, SIDE_TOP, SIDE_WIDTH, SIDE_HEIGHT)
	var bottom := rect.end.y - 8.0
	for index in range(_visible_entries.size() - 1, -1, -1):
		var entry: Dictionary = _visible_entries[index]
		var alpha := _entry_alpha(entry)
		if alpha <= 0.0:
			continue
		var lines := _wrap(str(entry["text"]), rect.size.x - 20.0, font)
		var color: Color = entry["color"]
		color.a = alpha
		for line_index in range(lines.size() - 1, -1, -1):
			if bottom - LINE_HEIGHT < rect.position.y + 8.0:
				return
			bottom -= LINE_HEIGHT
			draw_string(font, Vector2(rect.position.x + 10.0, bottom + LINE_HEIGHT - 3.0), lines[line_index], HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE, color)


func _draw_full_log(font: Font) -> void:
	draw_rect(Rect2(Vector2.ZERO, size), Color(0, 0, 0, 120.0 / 255.0))
	var panel := Rect2((size - FULL_SIZE) / 2.0, FULL_SIZE)
	draw_rect(panel, Color8(22, 24, 34, 220))
	draw_string(font, panel.position + Vector2(14, 22), TITLE_TEXT, HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE, TITLE_COLOR)

	var lines: Array = []
	for entry in _history:
		for line in _wrap(str(entry["text"]), panel.size.x - 28.0, font):
			lines.append([line, entry["color"]])
	var visible_lines := int((panel.size.y - 50.0) / LINE_HEIGHT)
	_full_scroll = mini(_full_scroll, maxi(0, lines.size() - visible_lines))
	var start := maxi(0, lines.size() - visible_lines - _full_scroll)
	var y := panel.position.y + 42.0
	for index in range(start, mini(lines.size(), start + visible_lines)):
		draw_string(font, Vector2(panel.position.x + 14.0, y + LINE_HEIGHT - 3.0), lines[index][0], HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE, lines[index][1])
		y += LINE_HEIGHT


func _entry_alpha(entry: Dictionary) -> float:
	var age := _clock - float(entry["shown_at"])
	if age < VISIBLE_SECONDS:
		return 1.0
	return maxf(0.0, 1.0 - (age - VISIBLE_SECONDS) / FADE_SECONDS)


func _wrap(text: String, width: float, font: Font) -> PackedStringArray:
	var lines := PackedStringArray()
	for paragraph in text.split("\n"):
		var current := ""
		for word in paragraph.split(" "):
			var candidate := word if current.is_empty() else current + " " + word
			if current.is_empty() or font.get_string_size(candidate, HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE).x <= width:
				current = candidate
			else:
				lines.append(current)
				current = word
		lines.append(current)
	return lines
