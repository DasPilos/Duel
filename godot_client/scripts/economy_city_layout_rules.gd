extends RefCounted
# Раскладка Радбурга для карты Экономики (клиентская таблица, без запросов к серверу).
# Источники:
#   геометрия зданий, входы и стены — server/structures.py CITY_OBJECTS / CITY_WALLS (тайл 16 px, сетка 200x200),
#     тот же набор Python-клиент получает от /api/city/structures; тесты сверяют таблицу с фикстурой этого набора;
#   солидные части зданий (SOLID_RECTS) — solid_rects из CITY_OBJECTS;
#   ворота — scenes/city/rendering.py _draw_walls_and_gates (прямоугольники совпадают с проёмами в CITY_WALLS);
#   двери и выталкивание героя — scenes/city_scene.py update(), строки 1090–1169 (DOORS);
#   подписи, цвета зданий, дома — scenes/city/rendering.py (_draw_city_objects, _draw_citizen_houses);
#     HOUSE_LOTS посчитан функцией build_citizen_house_lots из rendering.py по CITY_OBJECTS;
#   фон — scenes/city_scene.py draw(): плаца, проспекты и кварталы с чередованием цвета по (x + y).
# Угадано, в Python этого нет: спрайты каталога city_buildings к зданиям (поля sprite), ключи Экономики
# для амбара, склада и конюшни (economy_key — совпадают с BUILDINGS в economy_world.gd), стартовая точка
# игрока (PLAYER_SPAWN_PX — вход «east» из city_scene.py spawn_map).

const TILE_PX := 16
const GRID_TILES := Vector2i(200, 200)
const PLAYER_SPAWN_PX := Vector2(3056.0, 1600.0)
const SPAWN_DIRECTION := "w"
# Плашка подписи, как draw_map_badge в scenes/map_common.py: шрифт 13 px жирный, отступы 5 px по бокам и 2 px сверху и снизу.
const BADGE_FONT_SIZE := 13
const BADGE_PAD_X := 5.0
const BADGE_PAD_Y := 2.0
# player_speed из city_scene.py (px в секунду до множителя груза) и city_population_count по умолчанию.
const WALK_SPEED_PX := 220.0
const DEFAULT_HOUSE_COUNT := 4

const BUILDINGS := [
	{"id": "crystal_of_life", "name": "Кристалл Жизни", "label": "Кристалл Жизни [3x3]",
		"rect": Rect2i(98, 98, 6, 6), "entrance": Vector2i(100, 104), "economy_key": "", "sprite": "", "style": "crystal",
		"fill": [26, 36, 48], "trim": [60, 180, 220]},
	{"id": "main_castle", "name": "Главный замок", "label": "Главный замок [15x15]",
		"rect": Rect2i(136, 126, 30, 30), "entrance": Vector2i(150, 154), "economy_key": "", "window": "castle", "sprite": "", "style": "castle",
		"fill": [36, 44, 56], "trim": [100, 125, 155]},
	{"id": "tavern_building", "name": "Городская Таверна", "label": "Таверна [10х7, 2 этажа]",
		"rect": Rect2i(110, 24, 20, 14), "entrance": Vector2i(110, 30), "economy_key": "", "window": "tavern", "sprite": "city_building_tavern", "style": "block",
		"fill": [60, 48, 40], "trim": [115, 90, 65]},
	{"id": "barn_building", "name": "Городской Амбар", "label": "Городской Амбар [Ур. 1 • 12х10]",
		"rect": Rect2i(10, 70, 24, 20), "entrance": Vector2i(32, 80), "economy_key": "barn", "sprite": "", "style": "block",
		"fill": [82, 60, 40], "trim": [55, 38, 24]},
	{"id": "warehouse_building", "name": "Городской Склад", "label": "Городской Склад [Ур. 1 • 12х10]",
		"rect": Rect2i(10, 36, 24, 20), "entrance": Vector2i(32, 46), "economy_key": "warehouse", "sprite": "", "style": "block",
		"fill": [52, 58, 68], "trim": [34, 40, 48]},
	{"id": "forge_building", "name": "Городская Кузница", "label": "Городская Кузница [Ур. 1 • 9х7]",
		"rect": Rect2i(46, 50, 18, 14), "entrance": Vector2i(46, 56), "economy_key": "", "window": "forge", "sprite": "city_building_smithy", "style": "block",
		"fill": [50, 44, 42], "trim": [80, 50, 40]},
	{"id": "workshop_building", "name": "Городская Мастерская", "label": "Городская Мастерская [Ур. 1 • 9х7]",
		"rect": Rect2i(46, 26, 18, 14), "entrance": Vector2i(46, 32), "economy_key": "", "window": "workshop", "sprite": "city_building_glassblower", "style": "block",
		"fill": [48, 54, 62], "trim": [80, 100, 125]},
	{"id": "barracks_building", "name": "Городские Казармы", "label": "Городские Казармы [Ур. 1 • 9х13]",
		"rect": Rect2i(160, 62, 18, 26), "entrance": Vector2i(168, 86), "economy_key": "", "window": "barracks", "sprite": "", "style": "block",
		"fill": [55, 62, 72], "trim": [35, 40, 48]},
	{"id": "engineering_building", "name": "Инженерная палата", "label": "Инженерная палата [Ур. 1 • 10х8]",
		"rect": Rect2i(70, 24, 20, 16), "entrance": Vector2i(88, 30), "economy_key": "", "window": "engineering", "sprite": "", "style": "block",
		"fill": [48, 56, 58], "trim": [60, 80, 85]},
	{"id": "university_building", "name": "Городской Университет", "label": "Университет [Ур. 1 • 15х11]",
		"rect": Rect2i(32, 168, 30, 22), "entrance": Vector2i(46, 168), "economy_key": "", "window": "university", "sprite": "city_building_library", "style": "block",
		"fill": [50, 58, 70], "trim": [110, 140, 180]},
	{"id": "military_academy", "name": "Военная академия", "label": "Военная академия [Ур. 1 • 10х7]",
		"rect": Rect2i(20, 140, 20, 14), "entrance": Vector2i(38, 146), "economy_key": "", "window": "academy", "sprite": "city_building_guild", "style": "block",
		"fill": [52, 44, 48], "trim": [140, 70, 70]},
	{"id": "mage_school_building", "name": "Школа стихий", "label": "Школа стихий [Ур. 1 • 15х9]",
		"rect": Rect2i(60, 124, 30, 18), "entrance": Vector2i(88, 132), "economy_key": "", "window": "mage_school", "sprite": "city_building_mage_tower", "style": "block",
		"fill": [36, 30, 56], "trim": [150, 90, 220]},
	{"id": "stable_building", "name": "Городская Конюшня", "label": "Городская Конюшня [17х6]",
		"rect": Rect2i(154, 12, 34, 12), "entrance": Vector2i(170, 22), "economy_key": "stable", "sprite": "", "style": "block",
		"fill": [116, 91, 58], "trim": [66, 48, 32]},
]

# Стены и башни — прямоугольники CITY_WALLS в пикселях мира (как на сервере).
const WALL_RECTS := [
	Rect2i(0, 0, 1504, 64), Rect2i(1696, 0, 1504, 64),
	Rect2i(0, 3136, 1504, 64), Rect2i(1696, 3136, 1504, 64),
	Rect2i(0, 64, 64, 1440), Rect2i(0, 1696, 64, 1440),
	Rect2i(3136, 64, 64, 1344), Rect2i(3136, 1792, 64, 1344),
]
const TOWER_RECTS := [
	Rect2i(0, 0, 160, 160), Rect2i(3040, 0, 160, 160),
	Rect2i(0, 3040, 160, 160), Rect2i(3040, 3040, 160, 160),
]

# Секции палисада по стадиям city_upgrade_state в scenes/city/rendering.py.
const PALISADE_SECTIONS := [
	[[Vector2(1696, 3136), Vector2(3136, 3136)], [Vector2(3136, 1792), Vector2(3136, 3136)]],
	[[Vector2(3136, 64), Vector2(3136, 1408)], [Vector2(1696, 64), Vector2(3136, 64)]],
	[[Vector2(64, 64), Vector2(64, 1504)], [Vector2(64, 64), Vector2(1504, 64)]],
	[[Vector2(64, 1696), Vector2(64, 3136)], [Vector2(64, 3136), Vector2(1504, 3136)]],
]

# Непроходимые части зданий в пикселях мира (solid_rects из server/structures.py CITY_OBJECTS). Клетки входов
# в них не входят, поэтому входы проходимы, как в Python; полные прямоугольники зданий — BUILDINGS.
const SOLID_RECTS := {
	"crystal_of_life": [Rect2i(1568, 1568, 96, 96)],
	"main_castle": [Rect2i(2176, 2016, 480, 448), Rect2i(2176, 2464, 192, 32), Rect2i(2464, 2464, 192, 32)],
	"tavern_building": [Rect2i(1792, 384, 288, 224), Rect2i(1760, 384, 32, 96), Rect2i(1760, 512, 32, 96)],
	"barn_building": [Rect2i(160, 1120, 352, 320), Rect2i(512, 1120, 32, 160), Rect2i(512, 1312, 32, 128)],
	"warehouse_building": [Rect2i(160, 576, 352, 320), Rect2i(512, 576, 32, 160), Rect2i(512, 768, 32, 128)],
	"forge_building": [Rect2i(768, 800, 256, 224), Rect2i(736, 800, 32, 96), Rect2i(736, 928, 32, 96)],
	"workshop_building": [Rect2i(768, 416, 256, 224), Rect2i(736, 416, 32, 96), Rect2i(736, 544, 32, 96)],
	"barracks_building": [Rect2i(2560, 992, 288, 384), Rect2i(2560, 1376, 128, 32), Rect2i(2720, 1376, 128, 32)],
	"engineering_building": [Rect2i(1120, 384, 288, 256), Rect2i(1408, 384, 32, 96), Rect2i(1408, 512, 32, 128)],
	"university_building": [Rect2i(512, 2720, 480, 320), Rect2i(512, 2688, 224, 32), Rect2i(768, 2688, 224, 32)],
	"military_academy": [Rect2i(320, 2240, 288, 224), Rect2i(608, 2240, 32, 96), Rect2i(608, 2368, 32, 96)],
	"mage_school_building": [Rect2i(960, 1984, 448, 288), Rect2i(1408, 1984, 32, 128), Rect2i(1408, 2144, 32, 128)],
	"stable_building": [
		Rect2i(2464, 192, 544, 32), Rect2i(2464, 192, 32, 192), Rect2i(2976, 192, 32, 192),
		Rect2i(2464, 352, 256, 32), Rect2i(2752, 352, 256, 32),
	],
}

# Ворота — проёмы в стенах в тайлах; border — цвет рамки из rendering.py.
const GATES := [
	{"id": "east", "name": "Главные ворота", "rect": Rect2i(196, 88, 4, 24), "border": [255, 215, 60]},
	{"id": "north", "name": "Северные ворота", "rect": Rect2i(94, 0, 12, 4), "border": [100, 200, 255]},
	{"id": "south", "name": "Южные ворота", "rect": Rect2i(94, 196, 12, 4), "border": [100, 200, 255]},
	{"id": "west", "name": "Западные ворота", "rect": Rect2i(0, 94, 4, 12), "border": [100, 200, 255]},
]

# Двери (update() в city_scene.py, строки 1090–1169): тайл, на который наступает герой, окно, которое открывается,
# и тайл, куда герой выталкивается. Таверна в Python уходит на карту навигации; здесь открывается окно таверны,
# а герой ставится перед дверью, как spawn «tavern» в city_scene.py.
const DOORS := [
	{"tile": Vector2i(110, 30), "window": "tavern", "push": Vector2i(108, 30)},
	{"tile": Vector2i(32, 80), "window": "barn", "push": Vector2i(34, 80)},
	{"tile": Vector2i(32, 46), "window": "warehouse", "push": Vector2i(34, 46)},
	{"tile": Vector2i(46, 56), "window": "forge", "push": Vector2i(44, 56)},
	{"tile": Vector2i(46, 32), "window": "workshop", "push": Vector2i(44, 32)},
	{"tile": Vector2i(168, 86), "window": "barracks", "push": Vector2i(168, 88)},
	{"tile": Vector2i(88, 30), "window": "engineering", "push": Vector2i(90, 30)},
	{"tile": Vector2i(46, 168), "window": "university", "push": Vector2i(46, 166)},
	{"tile": Vector2i(38, 146), "window": "academy", "push": Vector2i(40, 146)},
	{"tile": Vector2i(88, 132), "window": "mage_school", "push": Vector2i(90, 132)},
]

# Дома жителей: [tile_x, tile_y, width_tiles, depth_tiles, floors], порядок как у build_citizen_house_lots.
const HOUSE_LOTS := [
	[32, 20, 6, 6, 3], [152, 44, 6, 6, 3], [56, 152, 6, 6, 3], [152, 164, 6, 6, 2], [68, 80, 6, 6, 1],
	[8, 116, 6, 6, 3], [128, 116, 6, 6, 2], [8, 176, 6, 6, 2], [116, 8, 6, 6, 3], [176, 116, 6, 6, 1],
]
const HOUSE_WALLS := [[132, 94, 64], [151, 111, 72], [112, 113, 106], [153, 128, 91]]
const HOUSE_ROOFS := [[91, 55, 42], [105, 67, 46], [75, 73, 66], [121, 77, 47]]

const GROUND := {
	"plaza": [[78, 74, 66], [84, 80, 72]],
	"avenue": [[68, 66, 60], [74, 72, 66]],
	"quarter": [[38, 44, 52], [42, 48, 56]],
}

const STONE_COLOR := [96, 104, 104]
const STONE_DARK_COLOR := [60, 66, 67]
const TOWER_COLOR := [86, 94, 92]
const TOWER_DARK_COLOR := [35, 42, 43]
const GATE_FILL := [25, 45, 35]

const CATALOG_DIR := "city_buildings"
const CATALOG_FILE := "catalog.json"


static func rgb(values: Array, alpha := 1.0) -> Color:
	return Color(values[0] / 255.0, values[1] / 255.0, values[2] / 255.0, alpha)


static func building_by_id(building_id: String) -> Dictionary:
	for building in BUILDINGS:
		if str(building["id"]) == building_id:
			return building
	return {}


static func building_at_tile(tile: Vector2i) -> Dictionary:
	for building in BUILDINGS:
		if (building["rect"] as Rect2i).has_point(tile):
			return building
	return {}


static func tile_of(world: Vector2) -> Vector2i:
	return Vector2i(floori(world.x / TILE_PX), floori(world.y / TILE_PX))


static func building_at_world(world: Vector2) -> Dictionary:
	return building_at_tile(tile_of(world))


# Ключ здания для открытия состояния; пустая строка — здание без состояния в клиенте Экономики.
static func window_key_at_world(world: Vector2) -> String:
	return window_key(building_at_world(world))


static func window_key(building: Dictionary) -> String:
	return str(building.get("window", building.get("economy_key", "")))


static func economy_key_at_world(world: Vector2) -> String:
	return str(building_at_world(world).get("economy_key", ""))


static func building_world_rect(building: Dictionary) -> Rect2:
	var rect: Rect2i = building["rect"]
	return Rect2(Vector2(rect.position * TILE_PX), Vector2(rect.size * TILE_PX))


static func building_badge_text(building: Dictionary) -> String:
	return str(building.get("label", building.get("name", "")))


# Зазор между низом плашки и верхом здания в пикселях экрана: у замка 12, у остальных 10 (scenes/city/rendering.py).
static func badge_gap(building_id: String) -> float:
	return 12.0 if building_id == "main_castle" else 10.0


# Прямоугольник плашки по размеру текста; низ текста стоит в bottom_center, плашка на 2 px ниже (midbottom + inflate(10, 4) в Python).
static func badge_rect(text_size: Vector2, bottom_center: Vector2) -> Rect2:
	var size := Vector2(text_size.x + BADGE_PAD_X * 2.0, text_size.y + BADGE_PAD_Y * 2.0)
	return Rect2(Vector2(bottom_center.x - size.x * 0.5, bottom_center.y - text_size.y - BADGE_PAD_Y), size)


static func gate_world_rect(gate: Dictionary) -> Rect2:
	var rect: Rect2i = gate["rect"]
	return Rect2(Vector2(rect.position * TILE_PX), Vector2(rect.size * TILE_PX))


static func door_at_tile(tile: Vector2i) -> Dictionary:
	for door in DOORS:
		if door["tile"] == tile:
			return door
	return {}


static func tile_center(tile: Vector2i) -> Vector2:
	return Vector2(tile * TILE_PX) + Vector2(TILE_PX, TILE_PX) * 0.5


# Дом жителя как citizen_house_solid_rects (scenes/city/rendering.py): на 5 px шире участка, высота с этажами и крышей.
static func house_solid_rect(lot: Array) -> Rect2i:
	# Высоты этажа и крыши в пикселях мира, как было при 32 px: 16 и 8 (не зависят от размера клетки).
	var floor_height := maxi(15, 16)
	var roof_height := maxi(4, 8)
	var depth := int(lot[3]) * TILE_PX
	var height := depth + (int(lot[4]) - 1) * floor_height + roof_height
	return Rect2i(int(lot[0]) * TILE_PX - 5, int(lot[1]) * TILE_PX + depth - height, int(lot[2]) * TILE_PX + 10, height)


# Солидные прямоугольники для проверки ходьбы: стены, башни, части зданий и первые house_count домов,
# как в _check_collision и _citizen_house_solid_rects (city_scene.py, rendering.py).
static func solid_rects(house_count: int) -> Array[Rect2i]:
	var rects: Array[Rect2i] = []
	rects.append_array(WALL_RECTS)
	rects.append_array(TOWER_RECTS)
	for building in BUILDINGS:
		rects.append_array(SOLID_RECTS.get(str(building["id"]), []))
	for index in range(clampi(house_count, 0, HOUSE_LOTS.size())):
		rects.append(house_solid_rect(HOUSE_LOTS[index]))
	return rects


static func ground_color(tile: Vector2i) -> Color:
	var zone := "quarter"
	if tile.x >= 80 and tile.x <= 118 and tile.y >= 80 and tile.y <= 118:
		zone = "plaza"
	elif (tile.x >= 94 and tile.x <= 104) or (tile.y >= 94 and tile.y <= 104) or (tile.x >= 160 and tile.y >= 88 and tile.y <= 110):
		zone = "avenue"
	var pair: Array = GROUND[zone]
	return rgb(pair[0] if (tile.x + tile.y) % 2 == 0 else pair[1])


# Строки подсказки: подпись здания, население замка и состояние из Экономики.
# city — ответ /api/castle/{id}/population (поле population), state — ответ /api/buildings (поле building).
static func tooltip_lines(building: Dictionary, city: Dictionary, state: Dictionary) -> PackedStringArray:
	var lines := PackedStringArray([str(building.get("label", building.get("name", "")))])
	if str(building.get("id", "")) == "main_castle":
		if city.has("population"):
			lines.append("Население: %d / %d" % [int(city.get("population", 0)), int(city.get("population_capacity", 0))])
		else:
			lines.append("Население: нет данных, откройте «Обновить город»")
	var key := str(building.get("economy_key", ""))
	if not key.is_empty() and str(state.get("building", "")) == key:
		lines.append("Уровень %d · рабочих %d / %d" % [
			int(state.get("level", 1)), int(state.get("workers", 0)), int(state.get("max_workers", 0)),
		])
	elif not key.is_empty():
		lines.append("Клик — состояние здания")
	elif not str(building.get("window", "")).is_empty():
		lines.append("Клик — открыть окно")
	else:
		lines.append("Состояние здания здесь не открывается")
	return lines


static func map_assets_root(project_dir: String) -> String:
	return project_dir.path_join("../assets/map").simplify_path()


# Путь к спрайту относительно assets/map по ключу каталога city_buildings/catalog.json; "" если ключа нет.
static func catalog_asset(catalog_text: String, key: String) -> String:
	var parsed: Variant = JSON.parse_string(catalog_text)
	if not parsed is Dictionary or not parsed.get("items", null) is Array:
		return ""
	for item in parsed["items"]:
		if item is Dictionary and str(item.get("key", "")) == key:
			return str(item.get("asset", ""))
	return ""
