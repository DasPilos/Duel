extends Node

# Музыка переходов Колоды в менеджере звука (deck/scenes/character_room.py, deck/ui/music.py, ui/scene_transition.py):
# смена экрана затухает за время перехода, в комнате тишина, выход из комнаты на карту играет один трек таверны.
const AUDIO_SCRIPT := preload("res://scripts/deck_audio.gd")

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	await _check_transitions()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_room_music_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _check_transitions() -> void:
	var audio = AUDIO_SCRIPT.new()
	add_child(audio)
	audio.set_process(false)
	await get_tree().process_frame
	_check(FileAccess.file_exists(audio.sound_root.path_join("sound/music/tavern_theme_1.mp3")), "файлы музыки таверны найдены рядом с проектом")

	audio.change_location("", "tavern")
	_check(audio.pending_count() == 1 and audio.current_track().is_empty(), "вход в таверну ждёт конца перехода")
	audio.tick(0.3)
	_check(audio.current_track().is_empty(), "до конца перехода музыка таверны не начинается")
	audio.tick(0.3)
	_check(audio.is_tavern_active() and audio.current_track() == "tavern" and audio.is_music_playing(), "после перехода в таверне играет музыка по кругу")

	audio.change_location("tavern", "character_room")
	_check(audio.is_fading() and not audio.is_tavern_active(), "выход из таверны в комнату затухает музыку")
	audio.tick(0.6)
	_check(audio.current_track().is_empty() and not audio.is_music_playing(), "в комнате тишина после перехода")

	audio.change_location("character_room", "world_map")
	audio.tick(0.2)
	_check(audio.current_track().is_empty(), "выход из комнаты на карту: трек не начинается до конца перехода")
	audio.tick(0.4)
	_check(audio.current_track() == "tavern" and audio.is_music_playing(), "на карте после комнаты звучит трек таверны")
	_check(not audio.is_tavern_active(), "трек после комнаты не повторяется, как Python без update_tavern_music")

	audio.change_location("world_map", "tavern")
	_check(audio.is_fading(), "переход с карты в таверну затухает оставшийся трек")
	audio.tick(0.6)
	_check(audio.is_tavern_active() and audio.is_music_playing(), "таверна снова играет по кругу")

	audio.change_location("tavern", "character_room")
	audio.tick(0.6)
	audio.change_location("character_room", "backyard")
	audio.tick(0.6)
	_check(audio.current_track() == "tavern" and not audio.is_tavern_active(), "выход из комнаты на задний двор тоже даёт один трек")

	audio.change_location("backyard", "character_room")
	audio.tick(0.6)
	_check(audio.current_track().is_empty(), "вход в комнату с заднего двора тишина")

	audio.change_location("character_room", "tavern")
	audio.tick(0.6)
	_check(audio.is_tavern_active() and audio.current_track() == "tavern", "из комнаты в таверну звучит таверна по кругу")

	var pending: int = audio.pending_count()
	audio.change_location("tavern", "tavern")
	_check(audio.pending_count() == pending and not audio.is_fading(), "переход на тот же экран ничего не меняет")

	audio.stop_tavern()
	audio.queue_free()
	await get_tree().create_timer(0.2).timeout
