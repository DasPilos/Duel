extends Node

# Звук Башни и Экономики: менеджер (таверна, затухание при переходе, бег, одноразовые звуки, отсутствующие файлы)
# и проводка в world_entry.gd и economy_world.gd: экраны, удар, вихрь и рывок.
const AUDIO_SCRIPT := preload("res://scripts/world_audio.gd")
const RULES := preload("res://scripts/world_audio_rules.gd")
const WORLD_SCRIPT := preload("res://scripts/world_entry.gd")
const ECONOMY_SCRIPT := preload("res://scripts/economy_world.gd")
const UNREACHABLE_URL := "http://127.0.0.1:9"
const MISSING_ROOT := "__world_audio_missing_root__"

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	await get_tree().process_frame
	_check_tavern()
	_check_transition()
	_check_running_and_effects()
	_check_missing_files()
	_check_tower_screens()
	_check_tower_swing_whirl()
	_check_tower_dash_gate()
	_check_map_equipment_request()
	_check_economy_views()
	GameSession.clear()
	_stop_all_players(get_tree().root)
	await get_tree().process_frame
	await get_tree().process_frame
	await get_tree().process_frame
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("world_audio_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


# Короткие звуки ещё звучат в момент выхода; остановка освобождает их воспроизведение до конца процесса.
func _stop_all_players(node: Node) -> void:
	if node is AudioStreamPlayer:
		(node as AudioStreamPlayer).stop()
	for child in node.get_children():
		_stop_all_players(child)


func _new_audio():
	var audio = AUDIO_SCRIPT.new()
	add_child(audio)
	return audio


func _check_tavern() -> void:
	var audio = _new_audio()
	_check(audio.play_tavern(), "таверна запускает трек")
	_check(audio.is_music_playing(), "трек таверны играет")
	_check(audio.music_starts() == 1, "первый трек таверны запущен")
	audio._on_music_finished()
	_check(audio.music_starts() == 2, "после конца трека таверна берёт следующий")
	audio.queue_free()


func _check_transition() -> void:
	var audio = _new_audio()
	audio.fade_out_for_transition()
	_check(not audio.is_fading(), "переход без музыки не запускает затухание")
	audio.play_tavern()
	audio.fade_out_for_transition()
	_check(audio.is_fading(), "переход начинает затухание музыки")
	audio._process(RULES.TRANSITION_FADE_SECONDS * 0.5)
	_check(audio.is_music_playing() and audio.is_fading(), "на середине затухание ещё идёт")
	audio._process(RULES.TRANSITION_FADE_SECONDS)
	_check(not audio.is_music_playing() and not audio.is_fading(), "затухание заканчивается остановкой музыки")
	audio._on_music_finished()
	_check(audio.music_starts() == 1, "после перехода конец трека не запускает таверну")
	audio.play_tavern()
	_check(audio.is_music_playing() and audio.music_starts() == 2, "таверна снова играет после перехода")
	audio.queue_free()


func _check_running_and_effects() -> void:
	var audio = _new_audio()
	audio.set_running(true)
	_check(audio.is_running(), "бег включается")
	audio.set_running(true)
	_check(audio.is_running(), "повторное включение бега ничего не ломает")
	audio.set_running(false)
	_check(not audio.is_running(), "бег выключается")
	_check(audio.play_swing({"name": "Стальной меч"}), "удар мечом играет звук")
	_check(audio.effect_count("swing") == 1, "удар мечом считается")
	_check(not audio.play_swing({"name": "Простой лук"}), "оружие без набора звуков не играет удар")
	_check(not audio.play_swing(null), "без оружия удар беззвучен")
	_check(audio.effect_count("swing") == 1, "беззвучный удар не считается")
	_check(audio.play_dash(), "рывок играет звук")
	_check(audio.play_whirl(), "вихрь играет звук")
	_check(audio.effect_count("dash") == 1 and audio.effect_count("whirl") == 1, "рывок и вихрь считаются")
	audio.queue_free()


func _check_missing_files() -> void:
	var audio = AUDIO_SCRIPT.new()
	audio.sound_root = MISSING_ROOT
	add_child(audio)
	_check(not audio.play_tavern(), "таверна без файлов не запускается и не падает")
	_check(not audio.play_dash(), "рывок без файла беззвучен")
	audio.set_running(true)
	_check(not audio.is_running(), "бег без файла не включается")
	audio.queue_free()


func _make_world():
	GameSession.clear()
	GameSession.world = {"server_url": UNREACHABLE_URL}
	var world = WORLD_SCRIPT.new()
	add_child(world)
	return world


func _check_tower_screens() -> void:
	var world = _make_world()
	world._set_screen(WORLD_SCRIPT.SCREEN_HUB)
	var audio = world._world_audio()
	_check(audio.is_music_playing(), "таверна Башни запускает музыку")
	world._set_screen(WORLD_SCRIPT.SCREEN_ROOM)
	_check(audio.is_fading(), "выход из таверны в комнату затухает")
	audio._process(1.0)
	_check(not audio.is_music_playing(), "в комнате Башни музыки нет")
	world._set_screen(WORLD_SCRIPT.SCREEN_HUB)
	_check(audio.is_music_playing(), "возврат в таверну снова запускает музыку")
	world._set_screen(WORLD_SCRIPT.SCREEN_MAP)
	_check(audio.is_fading(), "выход из таверны на карту затухает")
	audio.set_running(true)
	world._set_screen(WORLD_SCRIPT.SCREEN_ROOM)
	_check(not audio.is_running(), "уход с карты останавливает бег")
	world._set_screen(WORLD_SCRIPT.SCREEN_MAP)
	_check(world._world_swing_id == null, "новая карта сбрасывает запоминание замаха")
	world.queue_free()


func _check_tower_swing_whirl() -> void:
	var world = _make_world()
	world._set_screen(WORLD_SCRIPT.SCREEN_MAP)
	var audio = world._world_audio()
	GameSession.character["equipment"] = {"weapon": {"name": "Стальной меч"}}
	world._update_swing_sound({"swing_id": 4})
	_check(audio.effect_count("swing") == 0, "первый снимок запоминает замах без звука")
	world._update_swing_sound({"swing_id": 5})
	_check(audio.effect_count("swing") == 1, "новый замах играет удар")
	world._update_swing_sound({"swing_id": 5})
	_check(audio.effect_count("swing") == 1, "тот же замах не повторяет звук")
	GameSession.character["equipment"] = {}
	world._inventory_state = {}
	world._update_swing_sound({"swing_id": 6})
	_check(audio.effect_count("swing") == 1, "без оружия замах беззвучен")
	world._apply_world_events([{"type": "whirl"}], null)
	_check(audio.effect_count("whirl") == 1, "событие whirl играет вихрь")
	world.queue_free()


func _check_tower_dash_gate() -> void:
	var world = _make_world()
	GameSession.world_snapshot = {"player": {"dash_active": false, "windup": 0.0, "dash_cooldown": 0.0}}
	_check(world._dash_can_start(), "готовый рывок можно запустить")
	GameSession.world_snapshot = {"player": {"dash_active": false, "windup": 0.0, "dash_cooldown": 3.0}}
	_check(not world._dash_can_start(), "рывок на перезарядке не запускается")
	GameSession.world_snapshot = {"player": {"dash_active": false, "windup": 0.4, "dash_cooldown": 0.0}}
	_check(not world._dash_can_start(), "рывок во время замаха не запускается")
	GameSession.world_snapshot = {"player": {"dash_active": true, "windup": 0.0, "dash_cooldown": 0.0}}
	_check(not world._dash_can_start(), "рывок во время рывка не запускается")
	world.queue_free()


func _check_map_equipment_request() -> void:
	var world = _make_world()
	GameSession.character = {"id": 7, "name": "Карта", "zone": "world_map"}
	world._pending_action = "busy"
	world._enter_screen(WORLD_SCRIPT.SCREEN_MAP)
	var queue: Array = world._request_queue
	_check(queue.size() == 2 and queue[0]["action"] == "terrain" and queue[1]["action"] == "equipment_load", "карта запрашивает терейн, а затем экипировку")
	_check(queue[1]["path"] == "/api/inventory/7", "экипировка грузится по инвентарю персонажа")
	world._pending_action = "equipment_load"
	world._on_api_completed(true, {"inventory": [], "equipment": {"weapon": {"name": "Стальной меч"}}})
	_check(str(world._current_equipment().get("weapon", {}).get("name", "")) == "Стальной меч", "ответ экипировки обновляет оружие для звука удара")
	_check(not world._inventory_loaded, "загрузка экипировки не отмечает инвентарь загруженным")
	world._pending_action = ""
	world.queue_free()


func _check_economy_views() -> void:
	GameSession.clear()
	GameSession.world = {"server_url": UNREACHABLE_URL}
	var economy = ECONOMY_SCRIPT.new()
	add_child(economy)
	economy._set_view("tavern")
	var audio = economy._world_audio()
	_check(audio.is_music_playing(), "таверна Экономики запускает музыку")
	economy._set_view("map")
	_check(audio.is_fading(), "выход из таверны в город Экономики затухает")
	audio._process(1.0)
	_check(not audio.is_music_playing(), "город Экономики без музыки")
	economy._set_view("tavern")
	_check(audio.is_music_playing() and audio.music_starts() == 2, "возврат в таверну Экономики снова запускает музыку")
	economy._set_view("tavern")
	_check(audio.music_starts() == 2, "повторный выбор таверны не перезапускает трек")
	economy.queue_free()
