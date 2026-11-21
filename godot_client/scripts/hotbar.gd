extends Control

const HOTBAR_KEYS := [KEY_1, KEY_2, KEY_3, KEY_4, KEY_5, KEY_6, KEY_7, KEY_8, KEY_9, KEY_0]
const LABELS := ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]
const SLOT_SIZE := 43.0
const SLOT_GAP := 4.0
const BOTTOM_MARGIN := 7.0
const FLASH_DURATION := 0.15
const DASH_SLOT := 0
const DASH_COOLDOWN := 40.0
const BACKGROUND_COLOR := Color8(18, 16, 14)
const BORDER_COLOR := Color8(110, 92, 60)
const FLASH_BORDER_COLOR := Color8(235, 205, 120)
const ACTIVE_BORDER_COLOR := Color8(255, 215, 60)
const TEXT_COLOR := Color8(230, 220, 190)
const COOLDOWN_TEXT_COLOR := Color8(255, 245, 210)
const OVERLAY_COLOR := Color(0, 0, 0, 0.59)

var _dash_cooldown := 0.0
var _dash_active := false
var _flash_index := -1
var _flash_left := 0.0


func _init() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	z_index = 90


# Клики по слотам остаются в интерфейсе, а клики между слотами идут в мир.
func _has_point(point: Vector2) -> bool:
	return slot_at(point) >= 0


func slot_rect(index: int) -> Rect2:
	var total := LABELS.size() * SLOT_SIZE + (LABELS.size() - 1) * SLOT_GAP
	var left := (size.x - total) / 2.0
	var top := size.y - BOTTOM_MARGIN - SLOT_SIZE
	return Rect2(left + index * (SLOT_SIZE + SLOT_GAP), top, SLOT_SIZE, SLOT_SIZE)


func slot_at(point: Vector2) -> int:
	for index in LABELS.size():
		if slot_rect(index).has_point(point):
			return index
	return -1


func key_slot(keycode: Key) -> int:
	return HOTBAR_KEYS.find(keycode)


func flash(index: int) -> void:
	_flash_index = index
	_flash_left = FLASH_DURATION


func set_dash_state(cooldown: float, active: bool) -> void:
	_dash_cooldown = maxf(0.0, cooldown)
	_dash_active = active


func _process(delta: float) -> void:
	if _flash_left > 0.0:
		_flash_left = maxf(0.0, _flash_left - delta)
		if _flash_left == 0.0:
			_flash_index = -1
	queue_redraw()


func _draw() -> void:
	var font := get_theme_default_font()
	for index in LABELS.size():
		var rect := slot_rect(index)
		draw_rect(rect, BACKGROUND_COLOR)
		var border := BORDER_COLOR
		if index == DASH_SLOT and _dash_active:
			border = ACTIVE_BORDER_COLOR
		elif index == _flash_index:
			border = FLASH_BORDER_COLOR
		draw_rect(rect, border, false, 2.0)
		draw_string(font, rect.position + Vector2(5, 14), LABELS[index], HORIZONTAL_ALIGNMENT_LEFT, -1, 12, TEXT_COLOR)
		if index != DASH_SLOT:
			continue
		var name_width := font.get_string_size("Рывок", HORIZONTAL_ALIGNMENT_LEFT, -1, 11).x
		draw_string(font, Vector2(rect.get_center().x - name_width / 2.0, rect.end.y - 4), "Рывок", HORIZONTAL_ALIGNMENT_LEFT, -1, 11, TEXT_COLOR)
		if _dash_cooldown > 0.0:
			var ratio := minf(1.0, _dash_cooldown / DASH_COOLDOWN)
			var overlay_height := floorf((rect.size.y - 4.0) * ratio)
			if overlay_height > 0.0:
				draw_rect(Rect2(rect.position + Vector2(2, 2), Vector2(rect.size.x - 4.0, overlay_height)), OVERLAY_COLOR)
			var seconds := str(int(ceil(_dash_cooldown)))
			var seconds_width := font.get_string_size(seconds, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x
			draw_string(font, Vector2(rect.get_center().x - seconds_width / 2.0, rect.get_center().y + 5), seconds, HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COOLDOWN_TEXT_COLOR)
