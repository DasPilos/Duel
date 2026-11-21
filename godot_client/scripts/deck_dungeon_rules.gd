extends RefCounted

# Комнаты подземелья из deck/scenes/world_map_scene.py и deck/ui/dungeon_window.py.
# Комнаты идут в ряд: 1 — бой, 2 — торговец, 3 — бой, 4 — фонтан, 5 — бой, 6 — сокровищница.
# Клиент ведёт комнату по клеткам: Python двигал героя пикселями, а сервер получает клетку комнаты при старте боя.

const ORIGIN := Vector2i(64, 34)
const NO_TILE := Vector2i(-100000, -100000)
const SIZE := Vector2i(14, 10)
const ENTRANCE := Rect2i(25, 43, 3, 4)
const APPROACH := Vector2i(24, 45)
const ACTOR_OFFSET := Vector2i(8, 5)
const ROOM_COUNT := 6
const GATE_SECONDS := 5.0
const BATTLE_ROOMS := [1, 3, 5]
const MERCHANT_ROOM := 2
const FOUNTAIN_ROOM := 4
const CHEST_ROOM := 6
const ROOM_NAMES := {
	1: "Комната I • Скелетный дозор",
	2: "Комната II • Подземный торговец",
	3: "Комната III • Некромант",
	4: "Комната IV • Целебный фонтан",
	5: "Комната V • Король скелетов",
	6: "Комната VI • Сокровищница",
}
const ACTOR_LABELS := {
	1: "2 СКЕЛЕТА",
	2: "ТОРГОВЕЦ",
	3: "СКЕЛЕТЫ • НЕКРОМАНСЕР",
	4: "ФОНТАН",
	5: "СТРАЖА • КОРОЛЬ",
	6: "СУНДУК",
}
const HINTS := {
	"battle_closed": "Враги преграждают проход",
	"merchant_closed": "Поговорите с торговцем и закройте магазин, чтобы пройти дальше",
	"fountain_closed": "Используйте фонтан, чтобы открыть проход",
	"chest": "Откройте сундук и заберите награды",
	"default": "WASD / стрелки — ходьба • E — взаимодействовать",
}
const TREASURE_EXIT_HINT := "Подойдите к сундуку и нажмите E, чтобы выйти"


static func room_name(room: int) -> String:
	return str(ROOM_NAMES.get(room, ""))


# Идентификатор встречи комнаты, как в deck/server/arena.py (DUNGEON_ROOM_BATTLES) и опыте за убийства.
static func battle_source(room: int) -> String:
	return "dungeon_room_%d" % room


static func door_row() -> int:
	return ORIGIN.y + SIZE.y / 2


# Проём в восточной стене на уровне середины комнаты.
static func door_tile() -> Vector2i:
	return Vector2i(ORIGIN.x + SIZE.x - 1, door_row())


static func start_tile() -> Vector2i:
	return Vector2i(ORIGIN.x + 1, door_row())


static func actor_tile() -> Vector2i:
	return ORIGIN + ACTOR_OFFSET


static func is_inside(tile: Vector2i) -> bool:
	return tile.x >= ORIGIN.x and tile.x < ORIGIN.x + SIZE.x and tile.y >= ORIGIN.y and tile.y < ORIGIN.y + SIZE.y


# Стены как в _draw_dungeon_room: верхний и нижний ряды, левый столбец и восточный столбец, кроме открытого проёма.
static func is_wall(tile: Vector2i, gate_open: bool) -> bool:
	if not is_inside(tile):
		return true
	if tile.y == ORIGIN.y or tile.y == ORIGIN.y + SIZE.y - 1 or tile.x == ORIGIN.x:
		return true
	if tile.x == ORIGIN.x + SIZE.x - 1:
		return not (tile == door_tile() and gate_open)
	return false


static func is_passable(tile: Vector2i, gate_open: bool) -> bool:
	return not is_wall(tile, gate_open)


static func gate_open(room: int, cleared: Dictionary, completed: Dictionary) -> bool:
	if room in BATTLE_ROOMS:
		return cleared.has(room)
	if room == MERCHANT_ROOM or room == FOUNTAIN_ROOM:
		return completed.has(room)
	return false


# Выход через проём в следующую комнату; из последней комнаты выхода нет.
static func leaves_east(room: int, tile: Vector2i, step: Vector2i, gate: bool) -> bool:
	return room < ROOM_COUNT and gate and tile == door_tile() and step == Vector2i(1, 0)


static func actor_reachable(tile: Vector2i) -> bool:
	var actor := actor_tile()
	return maxi(absi(tile.x - actor.x), absi(tile.y - actor.y)) <= 1


static func battle_pending(room: int, cleared: Dictionary) -> bool:
	return room in BATTLE_ROOMS and not cleared.has(room)


static func hint(room: int, gate: bool, _treasure_opened: bool) -> String:
	match room:
		1, 3, 5:
			return str(HINTS["battle_closed"]) if not gate else str(HINTS["default"])
		2:
			return str(HINTS["merchant_closed"]) if not gate else str(HINTS["default"])
		4:
			return str(HINTS["fountain_closed"]) if not gate else str(HINTS["default"])
		6:
			return str(HINTS["chest"])
	return str(HINTS["default"])


static func on_entrance(tile: Vector2i) -> bool:
	return ENTRANCE.has_point(tile)


static func tile_pixel(tile: Vector2i, tile_size: float) -> Vector2:
	return Vector2((tile.x + 0.5) * tile_size, (tile.y + 0.5) * tile_size)


# Идентификатор запроса чека сокровища: UUID v4, как uuid.uuid4() в Python.
static func new_request_id() -> String:
	var digits := "0123456789abcdef"
	var text := ""
	for index in 32:
		if index in [8, 12, 16, 20]:
			text += "-"
		var digit := randi() % 16
		if index == 12:
			digit = 4
		elif index == 16:
			digit = 8 + randi() % 4
		text += digits[digit]
	return text
