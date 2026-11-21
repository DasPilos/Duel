extends Node

# Герой на карте города: кадры воина из загрузчика Tower (стойка и ходьба на одном холсте), выбор кадра по состоянию и
# направлению, тень, плашка ника и иконка профессии по геометрии scenes/city/rendering.py при масштабе карты 1.
const RULES := preload("res://scripts/economy_city_player_sprite_rules.gd")
const SPRITE_RULES := preload("res://scripts/economy_player_sprite_rules.gd")
const CITY_MAP_SCRIPT := preload("res://scripts/economy_city_map.gd")

var _failures: Array[String] = []
var _checks := 0
var _hero_draws := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_warrior_frames()
	_check_frame_choice()
	_check_geometry()
	await _check_map_hero()
	GameSession.clear()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("economy_city_player_sprite_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_warrior_frames() -> void:
	var sets := _warrior_sets()
	_check(sets.has("idle") and sets.has("run"), "кадры воина — стойка и ходьба — грузятся из ../assets/warrior")
	for state in ["idle", "run"]:
		_check((sets.get(state, {}) as Dictionary).size() == 8, "%s есть во всех восьми направлениях" % state)
	var idle: Texture2D = sets["idle"]["s"][0]
	var run: Texture2D = sets["run"]["s"][0]
	_check(idle.get_size() == run.get_size(), "стойка и ходьба лежат на одном холсте, как base-папки в Python")


func _check_frame_choice() -> void:
	var sets := _warrior_sets()
	_check(SPRITE_RULES.frame_for(sets, false, "s", 0.0) == sets["idle"]["s"][0], "стоящий воин показывает первый кадр стойки")
	_check(SPRITE_RULES.frame_for(sets, true, "s", 0.0) == sets["run"]["s"][0], "идущий воин показывает кадр ходьбы")
	var run_east: Array = sets["run"]["e"]
	_check(SPRITE_RULES.frame_for(sets, true, "e", 0.25) == run_east[int(0.25 * SPRITE_RULES.RUN_FPS) % run_east.size()],
		"ходьба меняет кадр с 10 кадрами в секунду")
	var idle_east: Array = sets["idle"]["e"]
	_check(SPRITE_RULES.frame_for(sets, false, "e", 0.5) == idle_east[int(0.5 * SPRITE_RULES.IDLE_FPS) % idle_east.size()],
		"стойка меняет кадр с 4 кадрами в секунду")
	_check(SPRITE_RULES.is_warrior({"type": "warrior"}) and not SPRITE_RULES.is_warrior({"type": "mage"}) and not SPRITE_RULES.is_warrior({}),
		"воин определяется по профессии type")


func _check_geometry() -> void:
	var feet := Vector2(400.0, 300.0)
	_check(_bounds(RULES.shadow_points(feet, 1.0)).is_equal_approx(Rect2(384.0, 295.0, 32.0, 14.0)),
		"тень — эллипс 32x14 с верхом на 5 px выше ног, как shadow_surf в Python")
	var plate := RULES.name_plate(Vector2(100.0, 16.0), feet, 1.0)
	_check(plate.is_equal_approx(Rect2(346.0, 240.0, 108.0, 20.0)), "плашка ника: низ текста на 42 px выше ног, отступ 4 и 2 px")
	_check(RULES.name_plate(Vector2(100.0, 16.0), feet, 0.5).is_equal_approx(Rect2(346.0, 261.0, 108.0, 20.0)),
		"подъём плашки масштабируется вместе с картой")
	_check(RULES.icon_rect(plate).is_equal_approx(Rect2(310.0, 234.0, 32.0, 32.0)),
		"иконка профессии 32 px слева от плашки с зазором 4 px, центр по высоте плашки")
	_check(RULES.name_text({"name": "Арн"}) == "Арн" and RULES.name_text({}) == "Герой", "ник берётся из персонажа, без ника — «Герой»")


func _check_map_hero() -> void:
	var sets := _warrior_sets()
	var map = CITY_MAP_SCRIPT.new()
	map.custom_minimum_size = Vector2(900, 480)
	add_child(map)
	map.size = Vector2(900, 480)
	map.fit_map()
	map._player_layer.draw.connect(_count_hero_draw)
	GameSession.clear()
	GameSession.character = {"id": 42, "name": "Арн", "type": "warrior"}
	await get_tree().process_frame
	await get_tree().process_frame
	_check(_hero_draws > 0, "слой героя перерисовывается и рисует воина без ошибок")
	var idle_frames: Array = sets["idle"][map._direction]
	var run_frames: Array = sets["run"][map._direction]
	map._moving = false
	_check(idle_frames.has(map._player_frame()), "воин в покое берёт кадры стойки")
	map._moving = true
	_check(run_frames.has(map._player_frame()), "воин в движении берёт кадры ходьбы")

	GameSession.character = {"id": 43, "name": "Лира", "type": "mage"}
	map._moving = false
	_check(map._player_frame() != null and not idle_frames.has(map._player_frame()), "маг берёт стойку 2Idle, а не кадры воина")

	await _check_afk_frames(map, sets)

	map._sprite_root = "res://no_such_sprites"
	map._sprites_loaded = false
	var draws_before := _hero_draws
	_check(map._player_frame() == null, "без кадров герой рисуется маркером")
	await get_tree().process_frame
	await get_tree().process_frame
	_check(_hero_draws > draws_before, "маркер перерисовывается без ошибок")
	map.queue_free()


# AFK-игроки города как draw_afk_players (ui/afk_presence.py): воин — стойка воина, остальные — стойка 2Idle,
# направление — position_direction или «s».
func _check_afk_frames(map, sets: Dictionary) -> void:
	var root := SPRITE_RULES.assets_root(ProjectSettings.globalize_path("res://"))
	var idle_2d: Dictionary = SPRITE_RULES.frame_sets(root)["idle"]
	var warrior := {"character_id": 7, "name": "Бродяга", "type": "warrior", "location": "city", "afk": true,
		"position_x": 400.0, "position_y": 300.0}
	var mage := {"character_id": 8, "name": "Сонный", "type": "mage", "location": "city", "afk": true,
		"position_x": 440.0, "position_y": 300.0, "position_direction": "e"}
	var untyped := {"character_id": 9, "name": "Безымянный", "location": "city", "afk": true,
		"position_x": 480.0, "position_y": 300.0}
	var elsewhere := {"character_id": 10, "name": "В таверне", "type": "warrior", "location": "tavern", "afk": true,
		"position_x": 1.0, "position_y": 1.0}
	map.set_afk_players([warrior, mage, untyped, elsewhere])
	_check(map.afk_player_count() == 3, "в городе рисуются AFK-игроки этой локации с позицией")
	_check((sets["idle"]["s"] as Array).has(map._afk_frame(warrior)), "AFK-воин стоит кадром стойки воина, без направления — на юг")
	_check((idle_2d["e"] as Array).has(map._afk_frame(mage)), "AFK-маг стоит кадром 2Idle по своему направлению")
	_check((idle_2d["s"] as Array).has(map._afk_frame(untyped)), "AFK без профессии — стойка 2Idle, как player_frame в Python")
	var draws_before := _hero_draws
	await get_tree().process_frame
	await get_tree().process_frame
	_check(_hero_draws > draws_before, "AFK-игроки перерисовываются вместе со слоем героя без ошибок")
	map.set_afk_players([])
	_check(map.afk_player_count() == 0, "пустой список очищает AFK в городе")


func _warrior_sets() -> Dictionary:
	return SPRITE_RULES.warrior_frame_sets(SPRITE_RULES.assets_root(ProjectSettings.globalize_path("res://")))


func _bounds(points: PackedVector2Array) -> Rect2:
	var low := points[0]
	var high := points[0]
	for point in points:
		low = low.min(point)
		high = high.max(point)
	return Rect2(low, high - low)


func _count_hero_draw() -> void:
	_hero_draws += 1


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)
