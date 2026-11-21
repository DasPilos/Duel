extends Control

# Индикатор запаса из ui/storage_meter.py: заполнение по доле склада, метки на 20/40/70 %
# и мигание при зарядке улучшения.

const BACK_COLOR := Color8(24, 29, 31)
const MARKER_COLOR := Color8(150, 163, 164)
const MARKER_SHARES := [0.20, 0.40, 0.70]
const CHARGE_LIGHT := Color8(246, 255, 250)
const CHARGE_GREEN := Color8(48, 225, 105)
const CHARGE_BLINK_MS := 350

var _amount := 0
var _capacity := 0
var _charging := false


func _init() -> void:
	custom_minimum_size = Vector2(170.0, 10.0)
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func set_values(amount: int, capacity: int, charging: bool = false) -> void:
	_amount = amount
	_capacity = capacity
	_charging = charging
	queue_redraw()


func _process(_delta: float) -> void:
	if _charging:
		queue_redraw()


func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), BACK_COLOR)
	var inner := Rect2(Vector2.ZERO, size).grow(-1.0)
	if inner.size.x <= 0.0 or inner.size.y <= 0.0:
		return
	var fill_width := roundf(inner.size.x * fill_ratio(_amount, _capacity))
	var color := fill_color(_amount, _capacity)
	if _charging:
		color = charge_color(Time.get_ticks_msec())
	if fill_width > 0.0:
		draw_rect(Rect2(inner.position, Vector2(fill_width, inner.size.y)), color)
	for share in MARKER_SHARES:
		var marker_x := inner.position.x + roundf(inner.size.x * share)
		draw_line(Vector2(marker_x, inner.position.y), Vector2(marker_x, inner.end.y - 1.0), MARKER_COLOR, 1.0)


static func fill_ratio(amount: int, capacity: int) -> float:
	if capacity <= 0:
		return 0.0
	return minf(1.0, float(maxi(0, amount)) / float(capacity))


static func fill_color(amount: int, capacity: int) -> Color:
	var ratio := 0.0 if capacity <= 0 else float(maxi(0, amount)) / float(capacity)
	if ratio <= 0.20:
		return Color8(218, 69, 65)
	if ratio <= 0.40:
		return Color8(232, 191, 67)
	if ratio <= 0.70:
		return Color8(75, 190, 100)
	return Color8(116, 218, 245)


static func charge_color(ticks_ms: int) -> Color:
	return CHARGE_LIGHT if floori(ticks_ms / float(CHARGE_BLINK_MS)) % 2 == 1 else CHARGE_GREEN


# Записи склада без служебного ключа limit: [{resource, amount}, ...].
static func storage_entries(storage: Dictionary) -> Array:
	var entries: Array = []
	for resource in storage:
		if str(resource) == "limit":
			continue
		entries.append({"resource": str(resource), "amount": int(storage[resource])})
	return entries
