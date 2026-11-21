extends Node

# Менеджер звука боя Deck: музыка по фазам, эффекты событий и приглушение музыки на ударах.
# Повторный запуск того же трека и повторная остановка безопасны; отсутствующие файлы пропускаются без ошибок.
const RULES := preload("res://scripts/deck_audio_rules.gd")
const WORLD_RULES := preload("res://scripts/world_audio_rules.gd")

var sound_root := ""
var _music_player: AudioStreamPlayer
var _track := ""
var _track_file := ""
var _tavern_active := false
var _music_starts := 0
var _fade: Dictionary = {}
var _duck: Dictionary = RULES.duck_idle()
var _battle_phase := ""
var _exchange_battle_id := ""
var _exchange_key := ""
var _picks_battle_id := ""
var _picks_seen: Array[String] = []
var _picks_in_draft := false
var _scheduled: Array[Dictionary] = []
var _clock := 0.0
var _effect_counts: Dictionary = {}
var _streams: Dictionary = {}
var _rng := RandomNumberGenerator.new()


func _init() -> void:
	sound_root = RULES.default_assets_root(ProjectSettings.globalize_path("res://"))


func _ready() -> void:
	_rng.randomize()
	_music_player = AudioStreamPlayer.new()
	add_child(_music_player)
	_music_player.finished.connect(_on_music_finished)


func _process(delta: float) -> void:
	tick(delta)


# Время идёт от события к событию: затухание и приглушение доходят до каждого отложенного звука точно.
func tick(delta: float) -> void:
	var remaining := maxf(delta, 0.0)
	var target := _clock + remaining
	var index := _next_due_index(target)
	while index >= 0:
		var item: Dictionary = _scheduled[index]
		_scheduled.remove_at(index)
		var at := float(item["at"])
		var wait := maxf(at - _clock, 0.0)
		_advance_mix(wait)
		remaining -= wait
		_clock = maxf(_clock, at)
		_fire(item)
		index = _next_due_index(target)
	_advance_mix(remaining)
	_clock = target
	_apply_music_volume()


# Возвращает true, если трек уже играет или успешно запущен. Любой трек отключает режим таверны.
func play_track(track_id: String) -> bool:
	if _music_player == null or not is_inside_tree():
		return false
	_tavern_active = false
	if track_id == _track and _fade.is_empty() and _music_player.playing:
		return true
	_stop_player()
	var files := RULES.music_files(track_id)
	if files.is_empty():
		return false
	var file := files[_rng.randi_range(0, files.size() - 1)]
	var stream := _load_stream(file, RULES.track_loops(track_id))
	if stream == null:
		return false
	_begin_track(track_id, file, stream)
	return true


func stop_music() -> void:
	_stop_player()


# Таверна: случайный трек; при repeat следующий берётся по сигналу finished, как update_tavern_music() в Python.
# Без repeat трек звучит один раз: так музыка комнаты продолжается на карте и на заднем дворе.
func play_tavern(repeat: bool = true) -> bool:
	if _music_player == null or not is_inside_tree():
		return false
	_stop_player()
	_tavern_active = repeat
	return _start_random_tavern()


func stop_tavern() -> void:
	_tavern_active = false
	stop_music()


# Смена экрана мира, как DeckWorld.go() в Python: музыка стихает за время перехода, затем новый экран меняет её.
func change_location(from: String, to: String) -> void:
	if from == to:
		return
	fade_out_all(WORLD_RULES.TRANSITION_FADE_SECONDS)
	_schedule_at({"kind": "location", "action": RULES.location_change_music(from, to)}, _clock + WORLD_RULES.TRANSITION_FADE_SECONDS)


func is_tavern_active() -> bool:
	return _tavern_active


func fade_out_all(duration: float) -> void:
	_tavern_active = false
	if duration <= 0.0 or _track.is_empty() or _music_player == null or not _music_player.playing:
		stop_music()
		return
	_duck = RULES.duck_idle()
	_fade = RULES.fade_start(RULES.fade_gain(_fade), duration)


# Затухание перед переходом фазы; возвращает длительность перехода, которую нужно передать в deck_phase_transition.gd.
func fade_out_for_transition() -> float:
	fade_out_all(RULES.TRANSITION_FADE_SECONDS)
	return RULES.TRANSITION_FADE_SECONDS


func duck_battle_music(duration: float) -> void:
	_duck = RULES.duck_begin(_duck, duration, RULES.DUCK_VOLUME)


# Возвращает true, если хотя бы один файл эффекта загружен и запущен.
func play_effect(effect_id: String) -> bool:
	if not is_inside_tree():
		return false
	var candidates := RULES.effect_files(effect_id)
	if candidates.is_empty():
		return false
	var chosen: Array[String] = []
	if RULES.effect_plays_all(effect_id):
		chosen = candidates
	else:
		chosen.append(candidates[_rng.randi_range(0, candidates.size() - 1)])
	var played := false
	for file in chosen:
		var stream := _load_stream(file, false)
		if stream != null:
			_spawn_effect(stream)
			played = true
	if not played:
		return false
	_effect_counts[effect_id] = int(_effect_counts.get(effect_id, 0)) + 1
	if RULES.effect_ducks_music(effect_id):
		duck_battle_music(RULES.DUCK_HOLD_SECONDS)
	return true


func schedule_effect(effect_id: String, delay: float) -> void:
	_schedule_at({"kind": "effect", "effect": effect_id}, _clock + maxf(delay, 0.0))
	_fire_due_now()


func on_battle_action(action: String) -> void:
	for effect_id in RULES.effects_for_action(action):
		play_effect(effect_id)


# Новый обмен боя: сначала приглушение на клэше, затем удары. Первый снимок боя только запоминает обмен.
func on_battle_update(state: Dictionary) -> void:
	var battle_id := str(state.get("battle_id", ""))
	_play_enemy_picks(battle_id, state)
	var exchange: Variant = state.get("last_exchange", [])
	var key := RULES.exchange_key(battle_id, state.get("history", []), exchange)
	var same_battle := battle_id == _exchange_battle_id
	var previous_key := _exchange_key
	_exchange_battle_id = battle_id
	if not same_battle:
		_exchange_key = key
		return
	if key.is_empty() or key == previous_key:
		return
	_exchange_key = key
	duck_battle_music(RULES.CLASH_DUCK_SECONDS)
	for effect_id in RULES.effects_for_exchange(exchange):
		schedule_effect(effect_id, RULES.ATTACK_ANIMATION_SECONDS)


# Выборы соперника в драфте: звук на каждую карту, которой не было в прошлом снимке того же боя.
# Когда бой покидает драфт, звучат выборы последнего драфта, которых не было в его снимках.
# Первый снимок боя только запоминает выборы, поэтому уже сделанные до его появления не звучат.
func _play_enemy_picks(battle_id: String, state: Dictionary) -> void:
	var phase := str(state.get("phase", ""))
	var current := RULES.draft_pick_keys(state)
	var fresh: Array[String] = []
	if not battle_id.is_empty() and battle_id == _picks_battle_id:
		fresh = RULES.new_draft_picks(_picks_seen, current)
		if _picks_in_draft and phase != "draft":
			fresh.append_array(RULES.new_draft_picks(_picks_seen, RULES.last_draft_pick_keys(state)))
	_picks_battle_id = battle_id
	_picks_seen = current
	_picks_in_draft = phase == "draft"
	for effect_id in RULES.effects_for_enemy_picks(fresh):
		play_effect(effect_id)


# Музыка по фазе боя. Стартовый драфт звучит после интро, раздача — через DRAFT_DEAL_DELAY_SECONDS после неё.
# Любой выход из драфта отменяет ещё не начатый старт; результат останавливает музыку.
func sync_battle_music(state: Dictionary) -> void:
	var phase := str(state.get("phase", ""))
	var entered_draft := phase == "draft" and _battle_phase != "draft"
	_battle_phase = phase
	var track := RULES.music_track_for_phase(phase)
	if track.is_empty():
		_cancel_draft_schedule()
		stop_music()
		return
	if track != RULES.DRAFT_TRACK:
		_cancel_draft_schedule()
		play_track(track)
		return
	if entered_draft:
		_cancel_draft_schedule()
		var draft_mode := str(state.get("draft_mode", ""))
		_schedule_draft_track(draft_mode, RULES.draft_music_delay(draft_mode))


func current_track() -> String:
	return _track


func track_file() -> String:
	return _track_file


func is_music_playing() -> bool:
	return _music_player != null and _music_player.playing and not _track.is_empty()


func is_fading() -> bool:
	return not _fade.is_empty()


func duck_state() -> String:
	return str(_duck.get("state", RULES.DUCK_IDLE))


func music_volume_db() -> float:
	return _music_player.volume_db if _music_player != null else RULES.SILENT_DB


func music_starts() -> int:
	return _music_starts


func effect_count(effect_id: String) -> int:
	return int(_effect_counts.get(effect_id, 0))


func pending_count() -> int:
	return _scheduled.size()


# Сброс состояния до stop(): finished, пришедший при остановке, не должен принять её за конец трека.
func _stop_player() -> void:
	_track = ""
	_track_file = ""
	_fade = {}
	_duck = RULES.duck_idle()
	if _music_player != null:
		_music_player.stop()


func _begin_track(track_id: String, file: String, stream: AudioStreamMP3) -> void:
	_track = track_id
	_track_file = file
	_music_starts += 1
	_music_player.stream = stream
	_apply_music_volume()
	_music_player.play()


func _start_random_tavern() -> bool:
	var files := RULES.music_files(RULES.TAVERN_TRACK)
	if files.is_empty():
		return false
	var offset := _rng.randi_range(0, files.size() - 1)
	for step in files.size():
		var file := files[(offset + step) % files.size()]
		var stream := _load_stream(file, RULES.track_loops(RULES.TAVERN_TRACK))
		if stream != null:
			_begin_track(RULES.TAVERN_TRACK, file, stream)
			return true
	return false


# finished приходит только при естественном конце трека; на Godot 4.7.1 stop() его не отправляет.
func _on_music_finished() -> void:
	if _tavern_active and _track == RULES.TAVERN_TRACK and not _music_player.playing:
		if not _start_random_tavern():
			_stop_player()


func _apply_music_volume() -> void:
	if _music_player == null or _track.is_empty():
		return
	_music_player.volume_db = RULES.gain_to_db(RULES.music_gain(_duck, _fade))


func _schedule_at(item: Dictionary, at: float) -> void:
	item["at"] = at
	_scheduled.append(item)


func _schedule_draft_track(draft_mode: String, delay: float) -> void:
	_schedule_at({"kind": "draft_track", "mode": draft_mode}, _clock + maxf(delay, 0.0))
	_fire_due_now()


# Отменяет старт драфта и его раздачу; удары и прочие отложенные звуки остаются.
func _cancel_draft_schedule() -> void:
	var kept: Array[Dictionary] = []
	for item in _scheduled:
		if str(item["kind"]) != "draft_track" and str(item.get("effect", "")) != "draft_cards_deal":
			kept.append(item)
	_scheduled = kept


# События, наступившие уже сейчас (нулевая задержка), выполняются без продвижения времени.
func _fire_due_now() -> void:
	var index := _next_due_index(_clock)
	while index >= 0:
		var item: Dictionary = _scheduled[index]
		_scheduled.remove_at(index)
		_fire(item)
		index = _next_due_index(_clock)


func _next_due_index(target: float) -> int:
	var due := -1
	for index in _scheduled.size():
		var at := float(_scheduled[index]["at"])
		if at <= target and (due < 0 or at < float(_scheduled[due]["at"])):
			due = index
	return due


func _fire(item: Dictionary) -> void:
	if str(item["kind"]) == "effect":
		play_effect(str(item["effect"]))
		return
	if str(item["kind"]) == "location":
		_apply_location_music(str(item["action"]))
		return
	play_track(RULES.DRAFT_TRACK)
	for effect_id in RULES.effects_for_draft_start(str(item["mode"])):
		_schedule_at({"kind": "effect", "effect": effect_id}, float(item["at"]) + RULES.effect_delay(effect_id))


func _apply_location_music(action: String) -> void:
	match action:
		RULES.LOCATION_STOP:
			stop_tavern()
		RULES.LOCATION_TAVERN_REPEAT:
			play_tavern(true)
		RULES.LOCATION_TAVERN_ONCE:
			play_tavern(false)


func _advance_mix(dt: float) -> void:
	if dt <= 0.0:
		return
	if not _fade.is_empty():
		_fade = RULES.fade_advance(_fade, dt)
		if RULES.fade_finished(_fade):
			stop_music()
	_duck = RULES.duck_advance(_duck, dt)


# Одноразовый плеер освобождается после окончания звука.
func _spawn_effect(stream: AudioStream) -> void:
	var player := AudioStreamPlayer.new()
	player.stream = stream
	player.volume_db = RULES.gain_to_db(RULES.EFFECT_VOLUME)
	player.finished.connect(player.queue_free)
	add_child(player)
	player.play()


# Файл читается один раз; отсутствующий или нечитаемый файл кэшируется как null и пропускается.
func _load_stream(relative: String, loop: bool) -> AudioStreamMP3:
	var path := RULES.resolve_path(sound_root, relative)
	if not _streams.has(path):
		var stream: AudioStreamMP3 = null
		if FileAccess.file_exists(path):
			stream = AudioStreamMP3.load_from_file(path)
		_streams[path] = stream
	var cached: AudioStreamMP3 = _streams[path]
	if cached != null:
		cached.loop = loop
	return cached
