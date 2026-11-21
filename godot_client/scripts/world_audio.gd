extends Node

# Звук Башни и Экономики: плейлист таверны, бег, удар, рывок и вихрь. Файлы читаются один раз;
# отсутствующие или нечитаемые файлы пропускаются без ошибок, как в Python-клиенте.
const RULES := preload("res://scripts/world_audio_rules.gd")
const FADE_RULES := preload("res://scripts/deck_audio_rules.gd")

var sound_root := ""
var _music_player: AudioStreamPlayer
var _run_player: AudioStreamPlayer
var _tavern_active := false
var _fade: Dictionary = {}
var _streams: Dictionary = {}
var _effect_counts: Dictionary = {}
var _music_starts := 0
var _rng := RandomNumberGenerator.new()


func _init() -> void:
	sound_root = FADE_RULES.default_assets_root(ProjectSettings.globalize_path("res://"))


func _ready() -> void:
	_rng.randomize()
	_music_player = AudioStreamPlayer.new()
	_music_player.finished.connect(_on_music_finished)
	add_child(_music_player)
	_run_player = AudioStreamPlayer.new()
	_run_player.stream = _load_stream(RULES.RUN_FILE, true)
	_run_player.volume_db = FADE_RULES.gain_to_db(RULES.EFFECT_VOLUME)
	add_child(_run_player)


func _process(delta: float) -> void:
	if _fade.is_empty():
		return
	_fade = FADE_RULES.fade_advance(_fade, delta)
	if FADE_RULES.fade_finished(_fade):
		_fade = {}
		_music_player.stop()
		return
	_music_player.volume_db = FADE_RULES.gain_to_db(RULES.MUSIC_VOLUME * FADE_RULES.fade_gain(_fade))


# Уход со сцены: звук останавливается сразу, а не когда аудиосервер дойдёт до конца буфера.
func _exit_tree() -> void:
	for child in get_children():
		if child is AudioStreamPlayer:
			(child as AudioStreamPlayer).stop()


# Таверна: случайный трек без зацикливания; следующий берётся по finished, как update_tavern_music() в Python.
func play_tavern() -> bool:
	if _music_player == null or not is_inside_tree():
		return false
	_tavern_active = true
	_fade = {}
	return _start_random_tavern()


# Переход между экранами: музыка стихает за TRANSITION_FADE_SECONDS, как fade_out_all_music() в Python.
# Повторный вызов во время затухания его не перезапускает: переход гасит музыку в начале, смена экрана вызывает то же снова.
func fade_out_for_transition() -> void:
	_tavern_active = false
	if not _fade.is_empty():
		return
	if _music_player == null or not _music_player.playing:
		_fade = {}
		return
	_fade = FADE_RULES.fade_start(FADE_RULES.fade_gain(_fade), RULES.TRANSITION_FADE_SECONDS)


# Бег: зацикленный звук, пока персонаж идёт; как set_run_sound() в ui/sfx.py.
func set_running(running: bool) -> void:
	if _run_player == null or not is_inside_tree():
		return
	if not running or _run_player.stream == null:
		_run_player.stop()
		return
	if not _run_player.playing:
		_run_player.play()


func play_swing(weapon: Variant) -> bool:
	return _play_effect("swing", RULES.swing_files_for_weapon(weapon))


func play_dash() -> bool:
	return _play_effect("dash", [RULES.DASH_FILE])


func play_whirl() -> bool:
	return _play_effect("whirl", [RULES.WHIRL_FILE])


func is_music_playing() -> bool:
	return _music_player != null and _music_player.playing


func is_fading() -> bool:
	return not _fade.is_empty()


func is_running() -> bool:
	return _run_player != null and _run_player.playing


func music_starts() -> int:
	return _music_starts


func effect_count(effect_id: String) -> int:
	return int(_effect_counts.get(effect_id, 0))


func _start_random_tavern() -> bool:
	var files := RULES.tavern_files()
	var stream := _load_stream(files[_rng.randi_range(0, files.size() - 1)], false)
	if stream == null:
		return false
	_music_player.stream = stream
	_music_player.volume_db = FADE_RULES.gain_to_db(RULES.MUSIC_VOLUME)
	_music_player.play()
	_music_starts += 1
	return true


# finished приходит только при естественном конце трека: остановка при затухании его не посылает.
func _on_music_finished() -> void:
	if _tavern_active:
		_start_random_tavern()


# Одноразовый звук из набора; случайный файл, как play_random_sound() в ui/sfx.py.
func _play_effect(effect_id: String, files: Array) -> bool:
	if not is_inside_tree() or files.is_empty():
		return false
	var stream := _load_stream(str(files[_rng.randi_range(0, files.size() - 1)]), false)
	if stream == null:
		return false
	_spawn_effect(stream)
	_effect_counts[effect_id] = effect_count(effect_id) + 1
	return true


# Одноразовый плеер освобождается после окончания звука.
func _spawn_effect(stream: AudioStream) -> void:
	var player := AudioStreamPlayer.new()
	player.stream = stream
	player.volume_db = FADE_RULES.gain_to_db(RULES.EFFECT_VOLUME)
	player.finished.connect(player.queue_free)
	add_child(player)
	player.play()


func _load_stream(relative: String, loop: bool) -> AudioStreamMP3:
	var path := FADE_RULES.resolve_path(sound_root, relative)
	if not _streams.has(path):
		var stream: AudioStreamMP3 = null
		if FileAccess.file_exists(path):
			stream = AudioStreamMP3.load_from_file(path)
		_streams[path] = stream
	var cached: AudioStreamMP3 = _streams[path]
	if cached != null:
		cached.loop = loop
	return cached
