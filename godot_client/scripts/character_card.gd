extends Control

# Карточка персонажа в координатах клиента Python (440×1065). Масштаб задаёт родительский оверлей.

signal stat_requested(stat_name: String, delta: int)
signal level_requested(delta: int)
signal close_requested

const Rules := preload("res://scripts/character_profile_rules.gd")

const CARD_WIDTH := 440.0
const CARD_HEIGHT := 1065.0
const DESIGN_SIZE := Vector2(1920.0, 1080.0)
const FONT_SIZE := 18
const CARD_BG := Color8(30, 32, 45, 225)
const PLAYER_BORDER := Color8(80, 180, 120)
const NAME_COLOR := Color8(240, 240, 245)
const ID_COLOR := Color8(170, 175, 185)
const LABEL_COLOR := Color8(210, 215, 225)
const XP_COLOR := Color8(255, 220, 120)
const AMOUNT_COLOR := Color8(235, 235, 240)
const STAT_TEXT_COLOR := Color8(255, 255, 255)
const BONUS_COLOR := Color8(140, 230, 150)
const ATTACK_COLOR := Color8(235, 215, 150)
const MOVE_COLOR := Color8(150, 220, 255)
const HP_COLOR := Color8(210, 80, 80)
const MP_COLOR := Color8(60, 140, 220)
const BAR_BG := Color8(40, 10, 10)
const BAR_WIDTH := 360.0
const BAR_HEIGHT := 14.0
const LEVEL_Y := 48.0
const HP_Y := 100.0
const MP_Y := 140.0
const CURRENCY_Y := 165.0
const CURRENCY_ICON_SIZE := 30.0
const CURRENCY_COLORS := {
	"copper": Color8(184, 115, 51),
	"silver": Color8(192, 192, 200),
	"gold": Color8(235, 190, 60),
}
const BUTTON_COLOR := Color8(235, 235, 235)
const MINUS_HOVER := Color8(210, 80, 80)
const PLUS_HOVER := Color8(80, 200, 120)
const BUTTON_TEXT := Color8(30, 32, 45)
const STAT_BUTTON_SIZE := 13.0
const STAT_BUTTON_GAP := 6.0
const STAT_CONTROL_SHIFT_X := 70.0
const STAT_ROW_HEIGHT := 20.0
const CLOSE_COLOR := Color8(60, 36, 40)
const CLOSE_BORDER := Color8(200, 70, 70)
const CLOSE_CROSS := Color8(240, 200, 200)
const BOX_BG := Color8(24, 29, 30)
const BOX_BORDER := Color8(82, 88, 76)
const FIGURE_COLOR := Color8(96, 88, 104)
const SLOT_BG := Color8(48, 44, 48)
const SLOT_HOVER := Color8(70, 64, 70)
const SLOT_BORDER := Color8(85, 78, 80)
const SLOT_ALPHA := 0.65
const SLOT_LABEL_COLOR := Color8(150, 142, 130)
const SLOT_ITEM_COLOR := Color8(235, 225, 200)
const SLOT_WIDTH := 66.0
const SLOT_HEIGHT := 62.0
const SLOT_LAYOUT := [
	["ears", "Серьги", 0, 0], ["head", "Голова", 2, 0], ["neck", "Шея", 4, 0],
	["back", "Плащ", 0, 1], ["body", "Доспех", 2, 1], ["ring", "Кольцо", 4, 1],
	["hands", "Руки", 0, 2], ["shield", "П рука", 1, 2], ["belt", "Пояс", 2, 2],
	["weapon", "Л рука", 3, 2], ["ring_2", "Кольцо", 4, 2],
	["legs", "Ноги", 2, 3], ["feet", "Обувь", 2, 4],
]
const COLUMN_CENTERS := [48.0, 143.0, 220.0, 308.0, 389.0]
const AREA_TOP_OFFSET := 151.0
const AREA_BOTTOM_OFFSET := 180.0
const RARITY_COLORS := {
	"common": Color8(205, 205, 205),
	"rare": Color8(80, 150, 255),
	"epic": Color8(180, 100, 240),
	"legendary": Color8(255, 170, 40),
}
const TOOLTIP_BG := Color8(22, 25, 31)
const TOOLTIP_BORDER := Color8(145, 133, 112)
const TOOLTIP_MAX_WIDTH := 240.0
const TOOLTIP_FONT_SIZE := 13
const GUIDE_COLOR := Color8(120, 220, 120)

var _profile: Dictionary = {}
# Arial, как в клиенте Python (settings.FONT_NAME): ширины текста и раскладка совпадают с ним.
var _font: SystemFont
# Слот-ориентир при выборе предмета из рюкзака: подсвечивается зелёным.
var _guide_slot := ""


func _init() -> void:
	size = Vector2(CARD_WIDTH, CARD_HEIGHT)
	custom_minimum_size = size
	mouse_filter = Control.MOUSE_FILTER_PASS
	_font = SystemFont.new()
	_font.font_names = PackedStringArray(["Arial"])
	_profile = Rules.normalize_profile({})


func set_profile(profile: Dictionary) -> void:
	_profile = Rules.normalize_profile(profile)
	queue_redraw()


# Подсветка слота, куда подходит выбранный предмет рюкзака; пустая строка — без подсветки.
func set_guide_slot(slot: String) -> void:
	_guide_slot = slot
	queue_redraw()


# Ключ слота экипировки под точкой (локальные координаты карточки), иначе пустая строка.
func slot_key_at(point: Vector2) -> String:
	var rects := _slot_rects()
	for entry in SLOT_LAYOUT:
		if (rects[entry[0]] as Rect2).has_point(point):
			return str(entry[0])
	return ""


func current_profile() -> Dictionary:
	return _profile.duplicate(true)


func close_button_rect() -> Rect2:
	return Rect2(CARD_WIDTH - 34.0, 10.0, 24.0, 24.0)


func stat_button_rect(stat_name: String, delta: int) -> Rect2:
	for index in Rules.STAT_ROWS.size():
		if Rules.STAT_ROWS[index][0] == stat_name:
			var controls := _stat_control_rects(_stat_row_y(index))
			return controls[1] if delta > 0 else controls[0]
	return Rect2()


func level_button_rect(delta: int) -> Rect2:
	var controls := _level_control_rects()
	return controls[1] if delta > 0 else controls[0]


# Клик внутри карточки всегда считается её: мир под карточкой не получает ЛКМ.
func handle_click(point: Vector2) -> bool:
	if not Rect2(Vector2.ZERO, size).has_point(point):
		return false
	if close_button_rect().has_point(point):
		close_requested.emit()
		return true
	for index in Rules.STAT_ROWS.size():
		var stat_name: String = Rules.STAT_ROWS[index][0]
		var controls := _stat_control_rects(_stat_row_y(index))
		if controls[1].has_point(point):
			stat_requested.emit(stat_name, 1)
			return true
		if controls[0].has_point(point):
			stat_requested.emit(stat_name, -1)
			return true
	if Rules.is_debug_unlimited(_profile):
		var level_controls := _level_control_rects()
		if level_controls[1].has_point(point):
			level_requested.emit(1)
			return true
		if level_controls[0].has_point(point):
			level_requested.emit(-1)
			return true
	return true


func _gui_input(event: InputEvent) -> void:
	var button_event := event as InputEventMouseButton
	if button_event != null and button_event.pressed and button_event.button_index == MOUSE_BUTTON_LEFT:
		if handle_click(button_event.position):
			accept_event()
		return
	if event is InputEventMouseMotion:
		queue_redraw()


func _draw() -> void:
	draw_style_box(_box_style(CARD_BG, PLAYER_BORDER, 8, 2), Rect2(Vector2.ZERO, size))
	_draw_header()
	_draw_level_and_xp()
	_draw_resources()
	_draw_currency()
	_draw_paperdoll()
	_draw_load_and_speed()
	_draw_stats()
	_draw_close_cross()
	_draw_equipment_tooltip()


func _draw_header() -> void:
	var display_name := str(_profile.get("name", "Персонаж"))
	var name_width := _text(Vector2(20.0, 20.0), display_name, NAME_COLOR, FONT_SIZE)
	var character_id: Variant = _profile.get("character_id")
	var id_text := "-" if character_id == null else str(character_id)
	_text(Vector2(20.0 + name_width + 20.0, 20.0), "ID: %s" % id_text, ID_COLOR, FONT_SIZE)


func _draw_level_and_xp() -> void:
	var level := int(_profile.get("level", 1))
	var level_width := _text(Vector2(20.0, LEVEL_Y), "Уровень %d" % level, LABEL_COLOR, FONT_SIZE)
	var xp_x := 20.0 + level_width + 15.0
	if Rules.is_debug_unlimited(_profile):
		var controls := _level_control_rects()
		_draw_button(controls[0], "-", BUTTON_COLOR, MINUS_HOVER)
		_draw_button(controls[1], "+", BUTTON_COLOR, PLUS_HOVER)
		xp_x = controls[1].end.x + 20.0
	var next_xp := Rules.xp_to_next(level)
	var xp_text := "XP: максимум" if next_xp == 0 else "XP: %d/%d" % [int(_profile.get("xp", 0)), next_xp]
	_text(Vector2(xp_x, LEVEL_Y), xp_text, XP_COLOR, FONT_SIZE)


func _draw_resources() -> void:
	var hp := Rules.displayed_hp(_profile)
	_draw_bar(HP_Y, "HP", hp.x, hp.y, HP_COLOR)
	_draw_bar(MP_Y, "MP", int(_profile.get("mp", 0)), int(_profile.get("max_mp", 1)), MP_COLOR)


func _draw_bar(y: float, label: String, value: int, maximum: int, color: Color) -> void:
	var ratio := clampf(float(value) / float(maxi(1, maximum)), 0.0, 1.0)
	_text(Vector2(20.0, y - _line_height(FONT_SIZE) - 2.0), "%s %d/%d" % [label, value, maximum], LABEL_COLOR, FONT_SIZE)
	var bar := Rect2(20.0, y, BAR_WIDTH, BAR_HEIGHT)
	draw_rect(bar, BAR_BG)
	draw_rect(Rect2(bar.position, Vector2(BAR_WIDTH * ratio, BAR_HEIGHT)), color)


func _draw_currency() -> void:
	var cursor := 20.0
	for currency in ["copper", "silver", "gold"]:
		var icon_center := Vector2(cursor + CURRENCY_ICON_SIZE / 2.0, CURRENCY_Y + CURRENCY_ICON_SIZE / 2.0)
		draw_circle(icon_center, CURRENCY_ICON_SIZE / 2.0 - 2.0, CURRENCY_COLORS[currency])
		var amount_x := cursor + CURRENCY_ICON_SIZE + 4.0
		var amount_top := CURRENCY_Y + CURRENCY_ICON_SIZE / 2.0 - _line_height(FONT_SIZE) / 2.0
		var amount_width := _text(Vector2(amount_x, amount_top), str(int(_profile.get(currency, 0))), AMOUNT_COLOR, FONT_SIZE)
		cursor = amount_x + amount_width + 18.0


# Силуэт вместо спрайта: спрайты персонажей переносятся отдельно (нужны ассеты).
func _draw_paperdoll() -> void:
	draw_circle(Vector2(CARD_WIDTH / 2.0, 470.0), 18.0, FIGURE_COLOR)
	draw_rect(Rect2(CARD_WIDTH / 2.0 - 24.0, 492.0, 48.0, 80.0), FIGURE_COLOR)
	var mouse := get_local_mouse_position()
	var rects := _slot_rects()
	var equipment := _profile.get("equipment", {}) as Dictionary
	for entry in SLOT_LAYOUT:
		var slot: String = entry[0]
		var rect: Rect2 = rects[slot]
		var item: Variant = equipment.get(slot)
		var base_fill := SLOT_HOVER if rect.has_point(mouse) else SLOT_BG
		var border := SLOT_BORDER
		if item is Dictionary:
			border = RARITY_COLORS.get(str(item.get("rarity", "")), SLOT_BORDER)
		var border_width := 2
		if slot == _guide_slot:
			border = GUIDE_COLOR
			border_width = 3
		draw_style_box(_box_style(Color(base_fill, SLOT_ALPHA), border, 6, border_width), rect)
		if item is Dictionary:
			var item_name := _fit_text(str(item.get("name", "Предмет")), rect.size.x - 6.0)
			_text_centered(rect, item_name, SLOT_ITEM_COLOR, FONT_SIZE)
		else:
			_text_centered(rect, str(entry[1]), SLOT_LABEL_COLOR, FONT_SIZE)


func _draw_load_and_speed() -> void:
	var feet: Rect2 = _slot_rects()["feet"]
	var capacity := Rules.carry_capacity(_profile)
	var carried := float(_profile.get("carried_weight_kg", 0.0))
	var carry_bottom := _draw_chip(feet.end.y + 10.0, [["Грузоподъёмность: %s/%d кг" % [str(carried), capacity], Rules.load_color(carried, float(capacity))]])
	var speeds := Rules.combat_speed_values(_profile)
	var speed_top := carry_bottom + 6.0
	speed_top = _draw_chip(speed_top, [["Скорость атаки: %s с" % str(speeds["attack_seconds"]), ATTACK_COLOR]]) + 4.0
	var move_parts: Array = [["Скорость передвижения: %d px/с" % int(speeds["move_speed"]), MOVE_COLOR]]
	var bonus := int(speeds["move_speed_bonus"])
	if bonus != 0:
		move_parts.append([" " + _signed(bonus), BONUS_COLOR])
	_draw_chip(speed_top, move_parts)


# Плашка по центру карточки из цветных кусков текста; возвращает нижний край плашки.
func _draw_chip(top: float, parts: Array) -> float:
	var total := 0.0
	for part in parts:
		total += _text_width(part[0], FONT_SIZE)
	var box := Rect2(CARD_WIDTH / 2.0 - total / 2.0 - 6.0, top - 3.0, total + 12.0, _line_height(FONT_SIZE) + 6.0)
	draw_style_box(_box_style(BOX_BG, BOX_BORDER, 4, 1), box)
	var cursor := CARD_WIDTH / 2.0 - total / 2.0
	for part in parts:
		cursor += _text(Vector2(cursor, top), part[0], part[1], FONT_SIZE)
	return box.end.y


func _draw_stats() -> void:
	var header_y := _stats_header_y()
	_text(Vector2(20.0, header_y), "ХАРАКТЕРИСТИКИ", PLAYER_BORDER, FONT_SIZE)
	_text(Vector2(20.0, header_y - 22.0), "Свободные очки: %d" % int(_profile.get("stat_points", 0)), XP_COLOR, FONT_SIZE)
	var stats := _profile.get("stats", {}) as Dictionary
	var effective := Rules.effective_stats(_profile)
	var bonuses := _profile.get("equipment_bonuses", {}) as Dictionary
	var derived := Rules.derived_values(_profile)
	var derived_x := _stat_text_right() + 50.0 + STAT_CONTROL_SHIFT_X
	for index in Rules.STAT_ROWS.size():
		var row: Array = Rules.STAT_ROWS[index]
		var key: String = row[0]
		var row_y := _stat_row_y(index)
		var base_text := "%s: %s" % [row[1], str(stats.get(key, effective.get(key, 0)))]
		var base_width := _text(Vector2(20.0, row_y), base_text, STAT_TEXT_COLOR, FONT_SIZE)
		if stats.has(key):
			var bonus := int(bonuses.get(key, 0))
			if bonus != 0:
				_text(Vector2(20.0 + base_width + _text_width(" ", FONT_SIZE), row_y), _signed(bonus), BONUS_COLOR, FONT_SIZE)
		var derived_key: String = row[2]
		if not derived_key.is_empty() and derived.has(derived_key):
			var derived_text := "%s: %s" % [derived_key, str(derived[derived_key])]
			var derived_font_size := _fitting_font_size(derived_text, CARD_WIDTH - derived_x - 6.0)
			_text(Vector2(derived_x, row_y), derived_text, Rules.derived_color(derived_key), derived_font_size)
		var controls := _stat_control_rects(row_y)
		_draw_button(controls[0], "-", BUTTON_COLOR, MINUS_HOVER)
		_draw_button(controls[1], "+", BUTTON_COLOR, PLUS_HOVER)


func _draw_close_cross() -> void:
	var rect := close_button_rect()
	draw_style_box(_box_style(CLOSE_COLOR, CLOSE_BORDER, 4, 1), rect)
	draw_line(rect.position + Vector2(7.0, 7.0), rect.end - Vector2(7.0, 7.0), CLOSE_CROSS, 2.0)
	draw_line(Vector2(rect.end.x - 7.0, rect.position.y + 7.0), Vector2(rect.position.x + 7.0, rect.end.y - 7.0), CLOSE_CROSS, 2.0)


func _draw_equipment_tooltip() -> void:
	var mouse := get_local_mouse_position()
	var slot := _slot_at(mouse)
	if slot.is_empty():
		return
	var equipment := _profile.get("equipment", {}) as Dictionary
	var item: Variant = equipment.get(slot)
	if not item is Dictionary:
		return
	var lines := _wrap_lines(Rules.equipment_tooltip_lines(item), TOOLTIP_MAX_WIDTH, TOOLTIP_FONT_SIZE)
	var line_height := _line_height(TOOLTIP_FONT_SIZE) + 2.0
	var widest := 0.0
	for line in lines:
		widest = maxf(widest, _text_width(line[0], TOOLTIP_FONT_SIZE))
	var box_size := Vector2(minf(TOOLTIP_MAX_WIDTH, widest) + 12.0, line_height * lines.size() + 12.0)
	var left := minf(mouse.x + 16.0, DESIGN_SIZE.x - box_size.x - 8.0)
	var top := minf(mouse.y + 16.0, DESIGN_SIZE.y - box_size.y - 8.0)
	var box := Rect2(maxf(8.0, left), maxf(8.0, top), box_size.x, box_size.y)
	draw_style_box(_box_style(TOOLTIP_BG, TOOLTIP_BORDER, 5, 1), box)
	var text_y := box.position.y + 6.0
	for line in lines:
		_text(Vector2(box.position.x + 6.0, text_y), line[0], line[1], TOOLTIP_FONT_SIZE)
		text_y += line_height


func _wrap_lines(lines: Array, max_width: float, font_size: int = FONT_SIZE) -> Array:
	var wrapped: Array = []
	for line in lines:
		var current := ""
		for word in str(line[0]).split(" ", false):
			var candidate: String = word if current.is_empty() else "%s %s" % [current, word]
			if not current.is_empty() and _text_width(candidate, font_size) > max_width:
				wrapped.append([current, line[1]])
				current = word
			else:
				current = candidate
		if not current.is_empty():
			wrapped.append([current, line[1]])
	return wrapped


func _fit_text(text: String, max_width: float) -> String:
	var result := text
	while result.length() > 1 and _text_width(result, FONT_SIZE) > max_width:
		result = result.substr(0, result.length() - 1)
	return result


# Длинный показатель (например, «Крит: 35% × 150%») мельчает, чтобы не выйти за рамку карточки.
func _fitting_font_size(text: String, max_width: float) -> int:
	var font_size := FONT_SIZE
	while font_size > 13 and _text_width(text, font_size) > max_width:
		font_size -= 1
	return font_size


func _slot_at(point: Vector2) -> String:
	var rects := _slot_rects()
	for entry in SLOT_LAYOUT:
		var slot: String = entry[0]
		var rect: Rect2 = rects[slot]
		if rect.has_point(point):
			return slot
	return ""


func _slot_rects() -> Dictionary:
	var rects := {}
	var area_center := (AREA_TOP_OFFSET + CARD_HEIGHT - AREA_BOTTOM_OFFSET) / 2.0
	var middle_row_top := floorf(area_center - 8.0)
	var row_tops := [
		middle_row_top - 172.0, middle_row_top - 86.0, middle_row_top,
		middle_row_top + 86.0, middle_row_top + 172.0,
	]
	for entry in SLOT_LAYOUT:
		var column: int = entry[2]
		var row: int = entry[3]
		var left: float = CARD_WIDTH / 2.0 + (COLUMN_CENTERS[column] - 220.0) - SLOT_WIDTH / 2.0
		rects[entry[0]] = Rect2(left, row_tops[row], SLOT_WIDTH, SLOT_HEIGHT)
	return rects


func _stat_row_y(index: int) -> float:
	return CARD_HEIGHT - 32.0 - (Rules.STAT_ROWS.size() - 1 - index) * STAT_ROW_HEIGHT


func _stats_header_y() -> float:
	return _stat_row_y(0) - 28.0


func _stat_text_right() -> float:
	return 20.0 + _text_width("Выносливость: 30", FONT_SIZE)


func _stat_control_rects(row_y: float) -> Array[Rect2]:
	var text_right := _stat_text_right() + 7.0 + STAT_CONTROL_SHIFT_X
	var control_top := row_y + 5.0
	var minus := Rect2(text_right + STAT_BUTTON_GAP, control_top, STAT_BUTTON_SIZE, STAT_BUTTON_SIZE)
	var plus := Rect2(minus.end.x + STAT_BUTTON_GAP, control_top, STAT_BUTTON_SIZE, STAT_BUTTON_SIZE)
	var result: Array[Rect2] = [minus, plus]
	return result


func _level_control_rects() -> Array[Rect2]:
	var text_right := 20.0 + _text_width("Уровень 1000", FONT_SIZE)
	var control_top := LEVEL_Y + 7.0
	var minus := Rect2(text_right + STAT_BUTTON_GAP, control_top, STAT_BUTTON_SIZE, STAT_BUTTON_SIZE)
	var plus := Rect2(minus.end.x + STAT_BUTTON_GAP, control_top, STAT_BUTTON_SIZE, STAT_BUTTON_SIZE)
	var result: Array[Rect2] = [minus, plus]
	return result


func _draw_button(rect: Rect2, label: String, color: Color, hover_color: Color) -> void:
	var fill := hover_color if rect.has_point(get_local_mouse_position()) else color
	draw_style_box(_box_style(fill, Color(0.0, 0.0, 0.0, 0.0), 3, 0), rect)
	_text_centered(rect, label, BUTTON_TEXT, FONT_SIZE)


func _text(top_left: Vector2, text: String, color: Color, font_size: int) -> float:
	draw_string(_font, top_left + Vector2(0.0, _font.get_ascent(font_size)), text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, color)
	return _text_width(text, font_size)


func _text_centered(rect: Rect2, text: String, color: Color, font_size: int) -> void:
	var top := rect.position.y + (rect.size.y - _line_height(font_size)) / 2.0
	_text(Vector2(rect.get_center().x - _text_width(text, font_size) / 2.0, top), text, color, font_size)


func _text_width(text: String, font_size: int) -> float:
	return _font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x


func _line_height(font_size: int) -> float:
	return _font.get_height(font_size)


func _signed(value: int) -> String:
	return "+%d" % value if value > 0 else "%d" % value


func _box_style(bg: Color, border: Color, radius: int, border_width: int) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = bg
	style.border_color = border
	style.set_border_width_all(border_width)
	style.set_corner_radius_all(radius)
	return style
