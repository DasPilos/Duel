extends Node

const RULES := preload("res://scripts/tower_hud_rules.gd")
const VIEW_SCRIPT := preload("res://scripts/tower_hud_view.gd")
const FRONT_LINE_VIEW_SCRIPT := preload("res://scripts/front_line_hud_view.gd")
const HOTBAR_SCRIPT := preload("res://scripts/hotbar.gd")
const DETAILS_RULES := preload("res://scripts/create_character_details_rules.gd")
const CLASS_RULES := preload("res://scripts/deck_class_card_rules.gd")

const BASE_VIEW := Vector2(1280.0, 720.0)
# Рельеф для сравнения с Python: WorldMapScene._build_minimap на сетке 125×125 при высоте 128.
# Хеш считается по пикселям 2..125, потому что рамка Python 2 px, а в Godot 1 px.
const TERRAIN_JSON := """{"map":{"tiles_w":125,"tiles_h":125,"version":3},"obstacles":[],"tiles":{"forest":[[10,5,9],[11,5,9],[12,30,31],[40,58,61]],"water":[[40,60,70]],"dry":[[80,20,25],[60,35,36]],"mountain":[[100,100,110],[40,66,67]],"paths":[[60,30,40]],"impassable":[],"partial":[]},"roads":{"tiles":[[3,3],[4,3],[4,4],[50,50],[40,60],[65,40]],"routes":[],"travel_seconds":0},"bridges":[{"tiles":[[60,60],[61,60],[62,60],[38,60]]}],"objects":[{"id":"town_radburg","tile_x":70,"tile_y":20,"tile_w":3,"tile_h":2},{"id":"shack","tile_x":10,"tile_y":100,"tile_w":1,"tile_h":1},{"id":"main_castle","tile_x":120,"tile_y":5,"tile_w":4,"tile_h":4}]}"""
const TERRAIN_HASH := 324220852
const PANEL_KEYS := ["player_panel", "minimap", "coords", "hotbar"]

var _failures: Array[String] = []
var _view = VIEW_SCRIPT.new()
var _front_line_view = FRONT_LINE_VIEW_SCRIPT.new()
var _portrait: Texture2D
var _draw_calls := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_layout_inside_base()
	_check_no_overlap()
	_check_hotbar_matches_existing_control()
	_check_minimap_sizes_and_tiles()
	_check_plural_words()
	_check_rounding_and_ratios()
	_check_coords_and_corpses()
	_check_polygon_spans()
	_check_minimap_image()
	_check_coords_text_fits()
	_check_front_line_layout()
	await _check_drawing()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("tower_hud_smoke_test: OK")
	get_tree().quit(code)


func _check_layout_inside_base() -> void:
	var layout: Dictionary = _view.layout(BASE_VIEW)
	var base := Rect2(Vector2.ZERO, BASE_VIEW)
	for key in PANEL_KEYS:
		_check(layout.has(key) and base.encloses(layout[key]), "%s внутри базового вида 1280×720" % key)
	_check(layout["player_panel"] == Rect2(3, 3, 252, 110), "панель персонажа слева вверху")
	_check(layout["minimap"] == Rect2(3, 589, 128, 128), "миникарта башни 128×128 у левого нижнего угла")
	_check(layout["coords"] == Rect2(3, 538, RULES.COORDS_WIDTH, 48), "координаты стоят над миникартой")
	_check(layout["hotbar"] == Rect2(407, 670, 466, 43), "хотбар по центру внизу, как слоты hotbar.gd")


func _check_no_overlap() -> void:
	for grid in [RULES.DEFAULT_GRID, Vector2i(512, 256)]:
		var layout: Dictionary = RULES.layout(BASE_VIEW, grid)
		for first in PANEL_KEYS.size():
			for second in range(first + 1, PANEL_KEYS.size()):
				var shared: Rect2 = layout[PANEL_KEYS[first]].intersection(layout[PANEL_KEYS[second]])
				_check(not shared.has_area(), "%s и %s не перекрываются (сетка %s)" % [PANEL_KEYS[first], PANEL_KEYS[second], str(grid)])


func _check_front_line_layout() -> void:
	for grid in [Vector2i(64, 64), Vector2i(512, 256), Vector2i(1600, 16), Vector2i(16, 1600)]:
		_front_line_view.configure_minimap({"map": {"tiles_w": grid.x, "tiles_h": grid.y}})
		for view_size in [Vector2(960, 540), BASE_VIEW, Vector2(1920, 1080), Vector2(2560, 1080)]:
			var layout: Dictionary = _front_line_view.layout(view_size)
			var viewport := Rect2(Vector2.ZERO, view_size)
			for key in layout:
				_check(viewport.encloses(layout[key]), "Front Line %s внутри окна %s, карта %s" % [key, view_size, grid])
			var panels := ["player_panel", "minimap_frame", "coords"]
			for first in panels.size():
				for second in range(first + 1, panels.size()):
					_check(not (layout[panels[first]] as Rect2).intersects(layout[panels[second]]), "Front Line: %s не перекрывает %s" % [panels[first], panels[second]])
			var minimap_frame: Rect2 = layout["minimap_frame"]
			_check(minimap_frame.position.x <= 8 and view_size.y - minimap_frame.end.y <= 8, "Front Line: мини-карта у левого нижнего края с безопасным отступом")
			var hp: Rect2 = layout["hp"]
			var mp: Rect2 = layout["mp"]
			_check(is_equal_approx(hp.position.y, mp.position.y) and hp.end.x < mp.position.x, "ХП и МП стоят горизонтально в одной строке")
			_check(hp.end.y < (layout["hotbar"] as Rect2).position.y, "ХП/МП расположены над спецприёмами")
			var xp: Rect2 = layout["xp"]
			_check(xp.end.y < hp.position.y and is_equal_approx(xp.position.x, hp.position.x) and is_equal_approx(xp.end.x, mp.end.x), "Опыт над ХП и МП во всю их ширину")
			var slots: Array[Rect2] = _front_line_view.special_slot_rects(layout["player_panel"])
			_check(slots.size() == 9, "Front Line: ровно девять слотов спецприёмов")
			for index in slots.size():
				_check((layout["player_panel"] as Rect2).encloses(slots[index]), "Слот %d внутри панели" % (index + 1))
				if index > 0:
					_check(slots[index - 1].end.x < slots[index].position.x and is_equal_approx(slots[0].position.y, slots[index].position.y), "Слоты в один ряд без перекрытий")
	_front_line_view.configure_minimap(JSON.parse_string(TERRAIN_JSON))
	_check(FRONT_LINE_VIEW_SCRIPT.experience_text(35, 185) == "Опыт 35 \\ 185", "Опыт: получено \\ нужно до следующего уровня")
	_check(FRONT_LINE_VIEW_SCRIPT.experience_text(0, 0) == "Опыт: максимальный уровень", "На максимальном уровне порога нет")


func _check_hotbar_matches_existing_control() -> void:
	var hotbar = HOTBAR_SCRIPT.new()
	hotbar.set_anchors_preset(Control.PRESET_TOP_LEFT)
	hotbar.size = BASE_VIEW
	var slots := RULES.hotbar_slot_rects(RULES.hotbar_rect(BASE_VIEW))
	var same := slots.size() == 10
	for index in slots.size():
		same = same and slots[index].is_equal_approx(hotbar.slot_rect(index))
	_check(same, "слоты хотбара совпадают с hotbar.gd")
	hotbar.free()


func _check_minimap_sizes_and_tiles() -> void:
	_check(RULES.minimap_size(RULES.MINIMAP_HEIGHT, Vector2i(125, 125)) == Vector2i(128, 128), "башня 125×125: квадратная миникарта")
	_check(RULES.minimap_size(192, Vector2i(125, 125)) == Vector2i(192, 192), "высота Python 192 даёт квадрат 192")
	_check(RULES.minimap_size(RULES.MINIMAP_HEIGHT, Vector2i(512, 256)) == Vector2i(256, 128), "сетка 512×256: ширина по пропорции")
	var scale := RULES.tile_scale(Vector2i(128, 128), Vector2i(125, 125))
	_check(scale.is_equal_approx(Vector2(1.024, 1.024)), "масштаб тайла 128/125")
	var expected := {
		Vector2i(0, 0): Rect2i(0, 0, 1, 1),
		Vector2i(1, 0): Rect2i(1, 0, 1, 1),
		Vector2i(41, 0): Rect2i(41, 0, 2, 1),
		Vector2i(83, 83): Rect2i(84, 84, 2, 2),
		Vector2i(124, 124): Rect2i(126, 126, 2, 2),
		Vector2i(10, 20): Rect2i(10, 20, 1, 1),
		Vector2i(50, 50): Rect2i(51, 51, 1, 1),
	}
	for tile in expected:
		_check(RULES.minimap_tile_rect(tile, scale) == expected[tile], "тайл %s → прямоугольник Python" % str(tile))


func _check_plural_words() -> void:
	var words := {
		0: "тайлов", 1: "тайл", 2: "тайла", 3: "тайла", 4: "тайла", 5: "тайлов",
		11: "тайлов", 12: "тайлов", 13: "тайлов", 14: "тайлов", 21: "тайл", 22: "тайла",
		25: "тайлов", 100: "тайлов", 101: "тайл", 102: "тайла", 104: "тайла", 111: "тайлов",
		112: "тайлов", 114: "тайлов", 121: "тайл", 125: "тайлов",
	}
	for count in words:
		_check(RULES.tiles_word(count) == words[count], "слово для %d тайлов" % count)
	_check(RULES.tiles_label(21) == "21 тайл", "подпись «21 тайл»")


func _check_rounding_and_ratios() -> void:
	_check(RULES.py_round(2.5) == 2 and RULES.py_round(3.5) == 4, "round: ровно .5 идёт к чётному")
	_check(RULES.py_round(0.5) == 0 and RULES.py_round(1.5) == 2 and RULES.py_round(-2.5) == -2, "round: отрицательные и нули")
	_check(RULES.py_round(2.51) == 3 and RULES.py_round(2.49) == 2, "round: обычные значения")
	_check(is_equal_approx(RULES.bar_ratio(50.0, 100.0), 0.5), "доля HP 50 из 100")
	_check(RULES.bar_ratio(150.0, 100.0) == 1.0, "доля HP зажата сверху")
	_check(RULES.bar_ratio(-5.0, 100.0) == 0.0, "доля HP зажата снизу")
	_check(RULES.bar_ratio(10.0, 0.0) == 1.0 and RULES.bar_ratio(0.0, 0.0) == 0.0, "нулевой максимум считается как 1")
	_check(RULES.bar_fill_width(160.0, 0.999) == 159.0 and RULES.bar_fill_width(160.0, 0.5) == 80.0, "заливка полоски целая, как int() в Python")
	_check(RULES.hp_label(49.9, 120.0) == "49/120 ХП" and RULES.mp_label(7.2, 30.0) == "7/30 МП", "подписи HP и MP как в Python")
	_check(RULES.display_name({}) == "Герой" and RULES.display_name({"name": ""}) == "Герой", "пустое имя заменяется на «Герой»")
	_check(RULES.display_name({"name": "Вася"}) == "Вася", "имя берётся как есть")
	_check(RULES.fit_size(Vector2(64, 128), 80.0) == Vector2(40, 80), "портрет 64×128 вписан в 80")
	_check(RULES.fit_size(Vector2(100, 33), 80.0) == Vector2(80, 26), "портрет 100×33 вписан в 80, высота округлена")
	_check(RULES.fit_size(Vector2.ZERO, 80.0) == Vector2.ZERO, "пустой портрет не рисуется")
	_check(RULES.fit_font_size(100.0, 150.0, 13) == 13 and RULES.fit_font_size(200.0, 150.0, 13) == 9, "шрифт уменьшается, если строка шире")


func _check_coords_and_corpses() -> void:
	var lines := RULES.coords_lines(Vector2(100.7, 64.2), Vector2(1000.9, 2047.9))
	_check(lines == PackedStringArray([
		"Курсор: X=100, Y=64 (тайл: 3, 2)",
		"Персонаж: X=1000, Y=2047 (тайл: 31, 63)",
	]), "строки координат совпадают с Python")
	_check(RULES.coords_lines(Vector2(-12345, -12345), Vector2.ZERO)[0] == "Курсор: X=-12345, Y=-12345 (тайл: -386, -386)", "отрицательные координаты: int() и деление с округлением вниз")
	var mapped := RULES.world_to_minimap(Vector2(2000.0, 1000.0), Rect2(3, 589, 128, 128), Vector2(4000.0, 4000.0))
	_check(mapped.is_equal_approx(Vector2(67.0, 621.0)), "мировые координаты переходят в пиксели миникарты")
	var labels := {
		Vector2(16, 0): "0 тайлов",
		Vector2(48, 0): "2 тайла",
		Vector2(80, 0): "2 тайла",
		Vector2(112, 0): "4 тайла",
		Vector2(176, 0): "6 тайлов",
		Vector2(96, 0): "3 тайла",
		Vector2(672, 0): "21 тайл",
	}
	for corpse in labels:
		var tiles := RULES.py_round(RULES.corpse_distance_tiles(corpse, Vector2.ZERO))
		_check(RULES.tiles_label(tiles) == labels[corpse], "подпись трупа на расстоянии %s px" % str(corpse.x))


func _check_polygon_spans() -> void:
	var triangle := PackedVector2Array([Vector2(1, 1), Vector2(9, 5), Vector2(3, 10)])
	_check(RULES.polygon_row_spans(triangle, 2) == [Vector2i(1, 3)], "треугольник, строка 2")
	_check(RULES.polygon_row_spans(triangle, 4) == [Vector2i(1, 7)], "треугольник, строка 4")
	_check(RULES.polygon_row_spans(triangle, 7) == [Vector2i(2, 6)], "треугольник, строка 7")
	_check(RULES.polygon_row_spans(triangle, 10) == [Vector2i(3, 3)], "треугольник, нижняя вершина")
	_check(RULES.polygon_row_spans(triangle, 11).is_empty(), "за пределами многоугольника заливки нет")
	var square := PackedVector2Array([Vector2(2.4, 2.9), Vector2(8.7, 2.2), Vector2(8.1, 8.9), Vector2(2.0, 8.0)])
	_check(RULES.polygon_row_spans(square, 5) == [Vector2i(2, 8)], "дробные вершины обрезаются до целых, как в pygame")


func _check_minimap_image() -> void:
	_view.configure_minimap(JSON.parse_string(TERRAIN_JSON))
	var image: Image = _view.minimap_image()
	_check(image != null and image.get_size() == Vector2i(128, 128), "миникарта 128×128")
	if image == null:
		return
	_check(_inner_hash(image) == TERRAIN_HASH, "миникарта совпадает с Python _build_minimap по пикселям 2..125")
	var pixels := {
		Vector2i(0, 0): Vector3i(220, 180, 70),
		Vector2i(66, 40): Vector3i(176, 146, 96),
		Vector2i(61, 40): Vector3i(40, 112, 150),
		Vector2i(59, 40): Vector3i(34, 72, 38),
		Vector2i(67, 40): Vector3i(40, 112, 150),
		Vector2i(38, 61): Vector3i(196, 150, 84),
		Vector2i(35, 61): Vector3i(176, 146, 96),
		Vector2i(7, 10): Vector3i(34, 72, 38),
		Vector2i(72, 20): Vector3i(230, 190, 90),
		Vector2i(123, 6): Vector3i(230, 190, 90),
		Vector2i(10, 102): Vector3i(200, 200, 210),
		Vector2i(102, 102): Vector3i(122, 114, 104),
		Vector2i(64, 64): Vector3i(92, 116, 62),
	}
	for pixel in pixels:
		_check(_rgb8(image.get_pixel(pixel.x, pixel.y)) == pixels[pixel], "пиксель %s как в Python" % str(pixel))

	var polygon_view = VIEW_SCRIPT.new()
	polygon_view.configure_minimap({
		"map": {"tiles_w": 125, "tiles_h": 125},
		"obstacles": [
			{"type": "lake", "points": [[0, 0], [320, 0], [320, 320], [0, 320]]},
			{"type": "forest", "points": [[640, 640], [960, 640], [960, 960], [640, 960]]},
		],
		"bridges": null,
	})
	var polygons: Image = polygon_view.minimap_image()
	_check(_rgb8(polygons.get_pixel(5, 5)) == Vector3i(40, 112, 150), "озеро заливает многоугольник")
	_check(_rgb8(polygons.get_pixel(25, 25)) == Vector3i(34, 72, 38), "лес-многоугольник заливается цветом леса")
	_check(_rgb8(polygons.get_pixel(64, 64)) == Vector3i(92, 116, 62), "вне многоугольников трава")


func _check_coords_text_fits() -> void:
	var font := ThemeDB.fallback_font
	for line in RULES.coords_lines(Vector2(4000.0, 4000.0), Vector2(4000.0, 4000.0)):
		var width := font.get_string_size(line, HORIZONTAL_ALIGNMENT_LEFT, -1, 13).x
		_check(width + 2.0 * RULES.COORDS_PAD_X <= RULES.COORDS_WIDTH, "строка координат помещается в резерв: %s" % line)
	_check(font.get_height(13) <= RULES.COORDS_LINE_HEIGHT, "высота строки шрифта 13 px не выше COORDS_LINE_HEIGHT")
	var assets := CLASS_RULES.default_assets_root(ProjectSettings.globalize_path("res://").trim_suffix("/"))
	for profession in ["warrior", "archer", "assassin", "mage"]:
		_check(FileAccess.file_exists(DETAILS_RULES.class_icon_path(assets, profession)), "иконка профессии %s есть в assets" % profession)


func _check_drawing() -> void:
	_portrait = ImageTexture.create_from_image(Image.create(64, 64, false, Image.FORMAT_RGBA8))
	_check(VIEW_SCRIPT.profession_icon("warrior") != null, "иконка warrior загружается из ../assets")
	_check(VIEW_SCRIPT.profession_icon("necromancer") == null, "у некроманта иконки нет")
	var canvas := Control.new()
	canvas.size = BASE_VIEW
	canvas.draw.connect(_on_canvas_draw.bind(canvas))
	add_child(canvas)
	canvas.queue_redraw()
	await get_tree().process_frame
	await get_tree().process_frame
	_check(_draw_calls > 0, "отрисовка HUD выполняется без ошибок в _draw")
	canvas.queue_free()


func _on_canvas_draw(canvas: Control) -> void:
	_draw_calls += 1
	var layout: Dictionary = _view.layout(BASE_VIEW)
	_view.draw_player_panel(canvas, layout["player_panel"], {"name": "Тест", "type": "warrior"}, {"hp": 30, "max_hp": 100, "mp": 5, "max_mp": 20}, _portrait)
	_view.draw_player_panel(canvas, layout["player_panel"], {}, {"hp": 0, "max_hp": 0, "mp": 0, "max_mp": 0}, null)
	_view.draw_minimap(canvas, layout["minimap"], Vector2(1000.0, 1000.0), [{"x": 1100.0, "y": 1000.0}], [{"x": 900.0, "y": 800.0}])
	_view.draw_coords(canvas, layout["coords"], Vector2(100.0, 100.0), Vector2(1000.0, 1000.0))
	var front_line: Dictionary = _front_line_view.layout(BASE_VIEW)
	_front_line_view.draw_player_panel(canvas, front_line["player_panel"], {"name": "Страж", "type": "warrior"},
		{"hp": 230, "max_hp": 300, "mp": 150, "max_mp": 350}, _portrait)
	_front_line_view.draw_player_panel(canvas, front_line["player_panel"], {}, {"hp": 0, "max_hp": 0}, null)
	_front_line_view.draw_minimap(canvas, front_line["minimap"], Vector2(1000, 1000), [], [{"x": 900, "y": 800}])
	_front_line_view.draw_coords(canvas, front_line["coords"], Vector2.ZERO, Vector2(1000, 1000))


func _inner_hash(image: Image) -> int:
	var value := 0
	for y in range(2, image.get_height() - 2):
		for x in range(2, image.get_width() - 2):
			var rgb := _rgb8(image.get_pixel(x, y))
			var code := (rgb.x << 16) | (rgb.y << 8) | rgb.z
			value = (value * 31 + code) % 2147483629
	return value


static func _rgb8(color: Color) -> Vector3i:
	return Vector3i(roundi(color.r * 255.0), roundi(color.g * 255.0), roundi(color.b * 255.0))


func _check(condition: bool, message: String) -> void:
	if not condition:
		_failures.append(message)
