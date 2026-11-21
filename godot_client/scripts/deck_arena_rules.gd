extends RefCounted

# Геометрия и правила арены из deck/ui/arena_overlay.py и deck/combat/arena_battle.py.
# Бой ведёт сервер: клиент рисует поле и переводит клики в команды по превью, которое присылает сервер.

const SQRT3 := 1.7320508075688772
const NO_TILE := Vector2i(-100000, -100000)
const TRANSFER_EFFECT := "necromancer_transfer"
const DAGGER_ITEM_ID := 6
const BATTLE_ITEM_IDS := [4, 5, 6, 52]
const ITEM_NAMES := {
	4: "Зелье восстановления здоровья",
	5: "Зелье восстановления маны",
	6: "Метательный кинжал",
	52: "Свиток разрушения магии",
}
const RESOURCE_NAMES := {
	"rage": "Ярость",
	"accuracy": "Меткость",
	"concentration": "Концентрация",
	"mana": "Мана",
	"necrotism": "Некротизм",
}
const RESULT_TEXT := {
	"win": ["ПОБЕДА!", "Противник повержен.", Color8(120, 235, 140)],
	"loss": ["ПОРАЖЕНИЕ", "Вы вернётесь в зал с полным здоровьем.", Color8(245, 110, 100)],
	"teleport": ["ТЕЛЕПОРТ", "Вы покинули арену.", Color8(110, 210, 255)],
}
const SIDE_LABELS := {"player": "Вы", "ally": "Союзник", "enemy": "Враг", "summon": "Призыв"}
const HINT_SUFFIX := " — S отменяет розыгрыш"
const MOVE_FAILED := "Сюда не дойти: до %d клеток по свободным клеткам арены"
const MAX_LOG_LINES := 8


static func text_of(value: Variant) -> String:
	return "" if value == null else str(value)


static func tile_from_array(value: Variant) -> Vector2i:
	if value is Array and value.size() >= 2:
		return Vector2i(int(value[0]), int(value[1]))
	return NO_TILE


static func tile_to_array(tile: Vector2i) -> Array:
	return [tile.x, tile.y]


static func tile_set(values: Array) -> Dictionary:
	var result := {}
	for value in values:
		result[tile_from_array(value)] = true
	return result


static func contains_tile(values: Array, tile: Vector2i) -> bool:
	for value in values:
		if tile_from_array(value) == tile:
			return true
	return false


# Осевая координата q для смещения odd-r: нечётные строки сдвинуты вправо, как hex_distance в Python.
static func hex_q(tile: Vector2i) -> int:
	return tile.x - (tile.y - (tile.y & 1)) / 2


static func hex_distance(a: Vector2i, b: Vector2i) -> int:
	var dq := hex_q(a) - hex_q(b)
	var dr := a.y - b.y
	return maxi(maxi(absi(dq), absi(dr)), absi(dq + dr))


# Порядок соседей совпадает с рёбрами гекса: СВ, В, ЮВ, ЮЗ, З, СЗ.
static func hex_neighbors(tile: Vector2i) -> Array[Vector2i]:
	var shift := tile.y & 1
	var result: Array[Vector2i] = []
	result.append(Vector2i(tile.x + shift, tile.y - 1))
	result.append(Vector2i(tile.x + 1, tile.y))
	result.append(Vector2i(tile.x + shift, tile.y + 1))
	result.append(Vector2i(tile.x + shift - 1, tile.y + 1))
	result.append(Vector2i(tile.x - 1, tile.y))
	result.append(Vector2i(tile.x + shift - 1, tile.y - 1))
	return result


# Центр клетки: как tile_center в ArenaController, center_qr — осевые координаты центра арены.
static func tile_center(tile: Vector2i, center_qr: Vector2i, size: float, origin: Vector2) -> Vector2:
	var dq := float(hex_q(tile) - center_qr.x)
	var dr := float(tile.y - center_qr.y)
	return origin + Vector2((dq + dr / 2.0) * size, dr * size * SQRT3 / 2.0)


# Шестиугольник с вершинами сверху и снизу, как tile_polygon в оверлее.
static func hex_polygon(center: Vector2, size: float) -> PackedVector2Array:
	var radius := size / SQRT3
	var half_width := size / 2.0
	return PackedVector2Array([
		center + Vector2(0.0, -radius),
		center + Vector2(half_width, -radius / 2.0),
		center + Vector2(half_width, radius / 2.0),
		center + Vector2(0.0, radius),
		center + Vector2(-half_width, radius / 2.0),
		center + Vector2(-half_width, -radius / 2.0),
	])


# Клетка под курсором: ближайший центр, но только внутри гекса (с небольшим допуском).
static func tile_at(pos: Vector2, tiles: Array, center_qr: Vector2i, size: float, origin: Vector2) -> Vector2i:
	var best := NO_TILE
	var best_distance := INF
	for value in tiles:
		var tile := tile_from_array(value)
		var distance := tile_center(tile, center_qr, size, origin).distance_to(pos)
		if distance < best_distance:
			best_distance = distance
			best = tile
	return best if best_distance <= size / SQRT3 + 0.5 else NO_TILE


# Размер клетки и начало координат, при которых всё поле помещается в область area.
static func fit_board(tiles: Array, center_qr: Vector2i, area: Vector2) -> Dictionary:
	if tiles.is_empty():
		return {"size": 1.0, "origin": area / 2.0}
	var low := Vector2(INF, INF)
	var high := Vector2(-INF, -INF)
	for value in tiles:
		var center := tile_center(tile_from_array(value), center_qr, 1.0, Vector2.ZERO)
		low = Vector2(minf(low.x, center.x), minf(low.y, center.y))
		high = Vector2(maxf(high.x, center.x), maxf(high.y, center.y))
	var extent := high - low + Vector2(1.0, 2.0 / SQRT3)
	var size := clampf(minf((area.x - 16.0) / extent.x, (area.y - 16.0) / extent.y), 4.0, 120.0)
	return {"size": size, "origin": area / 2.0 - (low + high) / 2.0 * size}


static func unit_by_id(units: Array, unit_id: String) -> Dictionary:
	for unit in units:
		if unit is Dictionary and str(unit.get("id", "")) == unit_id:
			return unit
	return {}


static func unit_at_tile(units: Array, tile: Vector2i) -> Dictionary:
	for unit in units:
		if unit is Dictionary and tile_from_array(unit.get("position", [])) == tile:
			return unit
	return {}


static func result_of(state: Dictionary) -> String:
	return text_of(state.get("result"))


static func status_text(state: Dictionary) -> String:
	if not result_of(state).is_empty():
		return "Бой окончен"
	match str(state.get("phase", "")):
		"draft":
			return "Выберите стартовые карты"
		"draw_choice":
			return "Выберите карту из добора"
	return "Ваш ход" if str(state.get("active_side", "")) == "player" else "Ход противника..."


static func opponent_name(state: Dictionary) -> String:
	var alive := 0
	var first_name := ""
	for unit in state.get("units", []):
		if unit is Dictionary and str(unit.get("side", "")) == "enemy":
			alive += 1
			if first_name.is_empty():
				first_name = str(unit.get("name", ""))
	var total := int(state.get("enemies_total", 1))
	if total > 1:
		var noun := "лагеря кобольдов" if str(state.get("source", "")).begins_with("kobold_camp") else "противников"
		return "%s (%d/%d)" % [noun, alive, total]
	return first_name if not first_name.is_empty() else "противник"


static func banner_title(state: Dictionary) -> String:
	var rect: Array = state.get("arena", {}).get("rect", [0, 0, 0, 0])
	return "БОЙ: %s против %s — %d×%d — раунд %d — %s" % [
		unit_name(state, "player"),
		opponent_name(state),
		int(rect[2]),
		int(rect[3]),
		int(state.get("round", 1)),
		status_text(state),
	]


static func details_text(state: Dictionary) -> String:
	var move_range := int(state.get("move_range", 3))
	var moved := "использовано" if bool(state.get("moved", false)) else "доступно (до %d клеток)" % move_range
	var distance := "—"
	if state.get("target_distance") != null:
		distance = str(int(state["target_distance"]))
	return "Перемещение: %s   |   Карты: %d/%d   |   В руке: %d/%d   |   B — сжечь карту   |   Цель: %s, дистанция %s" % [
		moved,
		int(state.get("cards_played", 0)),
		int(state.get("max_cards", 2)),
		state.get("hand", []).size(),
		int(state.get("hand_limit", 0)),
		unit_name(state, text_of(state.get("target"))),
		distance,
	]


static func unit_name(state: Dictionary, unit_id: String) -> String:
	var unit := unit_by_id(state.get("units", []), unit_id)
	return str(unit.get("name", "—"))


static func unit_info_text(unit: Dictionary) -> String:
	if unit.is_empty():
		return ""
	var lines := PackedStringArray()
	lines.append(str(unit.get("name", "")))
	lines.append(SIDE_LABELS.get(str(unit.get("side", "")), ""))
	lines.append("Здоровье: %d/%d" % [int(unit.get("hp", 0)), int(unit.get("max_hp", 0))])
	if int(unit.get("max_mp", 0)) > 0:
		lines.append("Мана: %d/%d" % [int(unit.get("mp", 0)), int(unit.get("max_mp", 0))])
	lines.append("Урон за бой: %d" % int(unit.get("damage_dealt", 0)))
	var effects: Array = unit.get("effects", [])
	var effects_text := "нет"
	if not effects.is_empty():
		var parts := PackedStringArray()
		for effect in effects:
			parts.append(str(effect))
		effects_text = ", ".join(parts)
	lines.append("Эффекты: " + effects_text)
	return "\n".join(lines)


static func resource_text(card: Dictionary) -> String:
	var resource := str(card.get("resource_type", ""))
	return "%s %d" % [str(RESOURCE_NAMES.get(resource, resource)), int(card.get("resource_cost", 0))]


static func hand_card_text(card: Dictionary) -> String:
	return str(card.get("name", "")) + "\n" + resource_text(card)


static func card_tooltip(card: Dictionary) -> String:
	var lines := PackedStringArray()
	lines.append(str(card.get("name", "")))
	var group := str(card.get("group", ""))
	if not group.is_empty():
		lines.append(group)
	return "\n".join(lines)


static func item_name(item: Dictionary) -> String:
	var name := str(item.get("name", ""))
	if name.is_empty():
		name = str(ITEM_NAMES.get(int(item.get("item_id", 0)), "Предмет"))
	return name


# Розыгрыш карты: режим выбора цели повторяет _click_target и valid_targets/valid_tiles из оверлея.
static func card_mode(card: Dictionary) -> String:
	if str(card.get("effect", "")) == TRANSFER_EFFECT:
		return "transfer"
	match str(card.get("role", "")):
		"enemy":
			return "attack"
		"summon", "tile":
			return "tile"
	return "unit"


static func targeting_hint(card: Dictionary, transfer_target: String, summon_range: int) -> String:
	if card_mode(card) == "transfer":
		var transfer_text := "Выберите свободный гекс для перемещения существа"
		if transfer_target.is_empty():
			transfer_text = "Выберите существо-союзника для переноса"
		return transfer_text + HINT_SUFFIX
	var role_text := ""
	match str(card.get("role", "")):
		"enemy":
			role_text = "Выберите гекс для атаки"
		"ally":
			role_text = "Выберите себя или союзника"
		"self":
			role_text = "Нажмите на себя"
		"summon":
			role_text = "Выберите клетку для призыва (радиус %d)" % summon_range
		"tile":
			role_text = "Выберите свободный гекс в пределах дальности карты"
		_:
			role_text = "Выберите цель"
	return role_text + HINT_SUFFIX


static func move_failed_text(move_range: int) -> String:
	return MOVE_FAILED % move_range


# Что делает клик по полю при выбранной карте. Возвращает kind: play (с command), transfer_target или hint.
static func plan_targeting_click(card: Dictionary, preview: Dictionary, tile: Vector2i, unit: Dictionary, transfer_target: String, card_index: int) -> Dictionary:
	var unit_id := str(unit.get("id", ""))
	var targets: Array = preview.get("targets", [])
	match card_mode(card):
		"transfer":
			if transfer_target.is_empty():
				if not unit_id.is_empty() and unit_id in targets:
					return {"kind": "transfer_target", "target": unit_id}
			else:
				var reach: Array = preview.get("transfer_tiles", {}).get(transfer_target, [])
				if contains_tile(reach, tile):
					return _play_plan(card_index, {"target": transfer_target, "destination": tile_to_array(tile)})
		"attack":
			if contains_tile(preview.get("aim_tiles", []), tile):
				return _play_plan(card_index, {"aim_tile": tile_to_array(tile)})
			if str(unit.get("side", "")) == "enemy" and not unit_id.is_empty():
				return _play_plan(card_index, {"target": unit_id})
		"tile":
			if contains_tile(preview.get("tiles", []), tile):
				return _play_plan(card_index, {"tile": tile_to_array(tile)})
		_:
			if not unit_id.is_empty() and unit_id in targets:
				return _play_plan(card_index, {"target": unit_id})
	return {"kind": "hint"}


static func _play_plan(card_index: int, fields: Dictionary) -> Dictionary:
	var command := {"type": "play", "card_index": card_index}
	command.merge(fields)
	return {"kind": "play", "command": command}
