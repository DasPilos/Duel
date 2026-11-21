extends Node

# Другие игроки на карте Башни и в городе Экономики: кто рисуется (на карте активные и AFK с позицией, в городе AFK)
# и опрос присутствия на карте, который идёт всегда, как PresenceState в Python.
const WORLD_SCRIPT := preload("res://scripts/world_entry.gd")
const ECONOMY_SCRIPT := preload("res://scripts/economy_world.gd")
const FRONT_LINE_MAP_VIEW_SCRIPT := preload("res://scripts/front_line_map_view.gd")
const UNREACHABLE_URL := "http://127.0.0.1:9"

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	await get_tree().process_frame
	_check_tower_presence()
	_check_json_self_presence()
	_check_front_line_hud()
	_check_economy_afk()
	_check_front_line_tile_animation()
	GameSession.clear()
	await get_tree().process_frame
	await get_tree().process_frame
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("world_presence_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _occupants() -> Array:
	return [
		{"character_id": 7, "name": "Свой", "location": "world_map", "position_x": 10.0, "position_y": 10.0, "afk": false, "type": "warrior"},
		{"character_id": 8, "name": "Ходок", "location": "world_map", "position_x": 40.0, "position_y": 50.0, "position_direction": "e", "afk": false, "type": "mage"},
		{"character_id": 9, "name": "Спящий", "location": "world_map", "position_x": 64.0, "position_y": 96.0, "afk": true, "type": "mage"},
		{"character_id": 10, "name": "Таверна", "location": "tavern", "position_x": 5.0, "position_y": 5.0, "afk": false, "type": "mage"},
		{"character_id": 11, "name": "Без места", "location": "world_map", "position_x": null, "position_y": null, "afk": true, "type": "mage"},
		{"character_id": 12, "name": "Городской", "location": "city", "position_x": 300.0, "position_y": 400.0, "afk": true, "type": "mage"},
	]


func _make_world(mode: String = "tower"):
	GameSession.clear()
	GameSession.world = {"server_url": UNREACHABLE_URL, "mode": mode}
	GameSession.character = {"id": 7, "name": "Свой", "type": "warrior"}
	var world = WORLD_SCRIPT.new()
	add_child(world)
	return world


func _check_front_line_hud() -> void:
	var world = _make_world("front_line")
	world.size = Vector2(1280, 720)
	world._set_screen(WORLD_SCRIPT.SCREEN_MAP)
	_check(world._hud_view.get_script() == WORLD_SCRIPT.FRONT_LINE_HUD_SCRIPT, "Front Line использует отдельное оформление нижней панели")
	_check(not world._hotbar.visible, "Хотбар Tower с десятым слотом и рывком не отображается в Front Line")
	var layout: Dictionary = world._hud_view.layout(world.size)
	for slot in world._hud_view.special_slot_rects(layout["player_panel"]):
		_check(world._is_ui_point(slot.get_center()), "Клик по слоту спецприёма не уходит в движение")
	_check(world._is_ui_point((layout["hp"] as Rect2).get_center()), "Клик по ХП не уходит в движение")
	_check(world._is_ui_point((layout["minimap_frame"] as Rect2).position + Vector2.ONE), "Рамка мини-карты защищена от кликов в мир")
	_check(not world._is_ui_point(Vector2(20, 20)), "Старая панель сверху не оставляет невидимую область перехвата кликов")
	world._world_ready = true
	var click := InputEventMouseButton.new()
	click.position = world._hud_view.special_slot_rects(layout["player_panel"])[0].get_center()
	click.button_index = MOUSE_BUTTON_LEFT
	click.pressed = true
	world._unhandled_input(click)
	_check(not world._has_move_target and world._click_effect_timer == 0, "Клик по новому HUD не ставит цель движения")
	click.button_index = MOUSE_BUTTON_MIDDLE
	world._unhandled_input(click)
	_check(not world._camera_dragging, "Нажатие средней кнопки на HUD не начинает перетаскивание камеры")
	world._camera_dragging = true
	click.pressed = false
	world._unhandled_input(click)
	_check(not world._camera_dragging, "Отпускание средней кнопки над HUD завершает перетаскивание камеры")
	world.free()
	var tower = _make_world()
	_check(tower._hud_view.get_script() == WORLD_SCRIPT.TOWER_HUD_SCRIPT, "Оформление Tower не изменилось")
	tower.free()


func _check_tower_presence() -> void:
	var world = _make_world()
	world._chat_occupants.clear()
	for occupant in _occupants():
		world._chat_occupants.append(occupant)
	GameSession.world["mode"] = "front_line"
	var stale_self: Dictionary = _occupants()[0].duplicate()
	stale_self["afk"] = true
	stale_self["position_x"] = 0.0
	stale_self["position_y"] = 0.0
	world._chat_occupants.append(stale_self)
	var others: Dictionary = world._other_players()
	_check(others["active"].size() == 1 and str(others["active"][0]["name"]) == "Ходок", "на карте видны активные игроки, кроме себя и игроков в других локациях")
	_check(others["afk"].size() == 1 and str(others["afk"][0]["name"]) == "Спящий", "на карте видны AFK-игроки с позицией на карте, без городских")
	world._set_screen(WORLD_SCRIPT.SCREEN_MAP)
	world._world_ready = true
	_check(world._chat_poll_allowed(), "на карте опрос присутствия идёт и при закрытом чате")
	world._world_ready = false
	_check(not world._chat_poll_allowed(), "до первого снимка мира опроса на карте нет")
	world._world_ready = true
	GameSession.world["mode"] = "front_line"
	_check(is_equal_approx(world._world_scale(), WORLD_SCRIPT.FRONT_LINE_CAMERA_SCALE), "Front Line по умолчанию использует приближённую камеру")
	world._desired_position = Vector2(2000.0, 2000.0)
	world._camera_offset = Vector2.ZERO
	_check(world._camera_position().is_equal_approx(world._desired_position), "камера следует за героем")
	world._camera_offset = Vector2(64.0, -32.0)
	_check(
		world._camera_position().is_equal_approx(world._desired_position + Vector2(64.0, -32.0)),
		"камера поддерживает смещение для обзора карты",
	)
	world._set_front_line_zoom(100.0)
	_check(is_equal_approx(world._world_scale(), WORLD_SCRIPT.FRONT_LINE_CAMERA_MAX_SCALE), "приближение камеры ограничено сверху")
	world._set_front_line_zoom(-100.0)
	_check(is_equal_approx(world._world_scale(), WORLD_SCRIPT.FRONT_LINE_CAMERA_MIN_SCALE), "отдаление камеры ограничено снизу")
	_check_front_line_left_click(world)
	_check_front_line_draft_spawn(world)
	GameSession.world["mode"] = "tower"
	_check(is_equal_approx(world._world_scale(), WORLD_SCRIPT.TOWER_WORLD_SCALE), "обычная карта сохраняет прежний масштаб камеры")
	world._world_ready = true
	world._pending_action = "busy"
	_check(not world._chat_poll_allowed(), "опрос ждёт, пока занят канал запросов")
	world._pending_action = ""
	_check(is_equal_approx(world._chat_timer.wait_time, 2.0), "опрос присутствия идёт раз в 2 секунды, как в Python")
	world.queue_free()


func _check_json_self_presence() -> void:
	var world = _make_world("front_line")
	GameSession.character = JSON.parse_string('{"id":7,"name":"Свой","type":"warrior"}')
	var occupants: Array = JSON.parse_string('[{"character_id":7,"name":"Свой","location":"world_map","position_x":10,"position_y":10,"afk":false},{"character_id":99,"name":"Свой","location":"world_map","position_x":20,"position_y":20,"afk":false}]')
	world._chat_occupants.assign(occupants)
	for position in [Vector2(10, 10), Vector2(1000, 1000)]:
		world._desired_position = position
		for afk in [false, true]:
			world._chat_occupants[0]["afk"] = afk
			var others: Dictionary = world._other_players()
			_check(others["active"].size() == 1 and int(others["active"][0]["character_id"]) == 99,
				"JSON: свой персонаж не дублируется при задержке позиции; другой игрок с тем же именем остаётся видимым")
			_check(others["afk"].is_empty(), "JSON: устаревшая AFK-запись своего героя не рисуется независимо от расстояния")
	world.free()


func _check_front_line_left_click(world: Variant) -> void:
	_check(
		world.mouse_filter == Control.MOUSE_FILTER_IGNORE,
		"Front Line: карта не перехватывает клики до _unhandled_input",
	)
	world.size = Vector2(800.0, 600.0)
	world._world_ready = true
	world._pending_action = ""
	world._desired_position = Vector2(64.0, 64.0)
	world._map_tiles_w = 8
	world._map_tiles_h = 8
	world._collision.configure({"map": {"tiles_w": 8, "tiles_h": 8}, "tiles": {}})
	var click := InputEventMouseButton.new()
	click.button_index = MOUSE_BUTTON_LEFT
	click.pressed = true
	click.position = Vector2(400.0, 300.0)
	world._unhandled_input(click)
	_check(world._has_move_target, "Front Line: ЛКМ по земле задаёт путь герою")
	_check(world._click_effect_timer > 0.0, "Front Line: ЛКМ показывает расходящееся кольцо")


func _check_front_line_draft_spawn(world: Variant) -> void:
	GameSession.world = {"mode": "front_line"}
	GameSession.world_snapshot = {"front_line": {"state": "character_draft"}}
	world._desired_position = Vector2(1024.0, 1024.0)
	world._sent_position = world._desired_position
	var snapshot := {
		"front_line": {"state": "awaiting_wave_draft"},
		"player": {"x": 880.0, "y": 1808.0},
	}
	_check(world._reconcile_front_line_draft_spawn(snapshot), "Front Line: окончание драфта принимает позицию спавна сервера")
	_check(
		world._desired_position.is_equal_approx(Vector2(880.0, 1808.0))
			and world._sent_position.is_equal_approx(world._desired_position),
		"Front Line: после драфта герой отображается в точке возрождения",
	)


func _check_front_line_tile_animation() -> void:
	var map_view = FRONT_LINE_MAP_VIEW_SCRIPT.new()
	map_view.configure({
		"map_w": 1,
		"map_h": 1,
		"layers": [{
			"visible": true,
			"cells": [{
				"x": 0,
				"y": 0,
				"key": "atlas|res://assets/base_tails/Biome/swamp/Tiled_files/water_lilis.png|2|0",
			}],
		}],
	})
	_check(map_view.animated_tile_count() == 1, "Front Line: анимация тайла воды загружена из TSX")
	if map_view.animated_tile_count() == 1:
		var animated_cell: Dictionary = map_view._map_layers[0]["animated_cells"][0]
		_check(
			FRONT_LINE_MAP_VIEW_SCRIPT._animation_frame_tile_id(animated_cell["frames"], 0, 2) == 2,
			"Front Line: тайл воды начинает с первого кадра",
		)
		_check(
			FRONT_LINE_MAP_VIEW_SCRIPT._animation_frame_tile_id(animated_cell["frames"], 150, 2) == 51,
			"Front Line: тайл воды переключает кадр по длительности TSX",
		)


func _check_economy_afk() -> void:
	GameSession.clear()
	GameSession.world = {"server_url": UNREACHABLE_URL}
	var economy = ECONOMY_SCRIPT.new()
	add_child(economy)
	_check(economy._city_map != null, "город Экономики создан")
	economy._city_map.set_afk_players(_occupants())
	_check(economy._city_map.afk_player_count() == 1, "в городе рисуются только AFK-игроки с позицией в городе")
	economy._city_map.set_afk_players([])
	_check(economy._city_map.afk_player_count() == 0, "пустой список очищает AFK в городе")
	economy.queue_free()
