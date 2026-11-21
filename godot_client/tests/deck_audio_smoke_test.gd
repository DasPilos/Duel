extends Node

# Звук боя Deck: правила (треки, эффекты, громкость, затухание, приглушение), менеджер (запуск, остановка,
# затухание, отсутствующие файлы) и проводка в мире: переходы фаз и обмены ударами.
const AUDIO_SCRIPT := preload("res://scripts/deck_audio.gd")
const RULES := preload("res://scripts/deck_audio_rules.gd")
const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const SCENE_TRANSITION := preload("res://scripts/scene_transition.gd")
const UNREACHABLE_URL := "http://127.0.0.1:9"
const MISSING_ROOT := "__deck_audio_missing_root__"

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_rules()
	await _check_manager()
	await _check_clash()
	await _check_tavern()
	await _check_draft_intro()
	await _check_enemy_picks()
	await _check_world_hooks()
	GameSession.clear()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_audio_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _check_rules() -> void:
	_check(RULES.music_track_for_phase("draft") == "draft", "драфт играет трек драфта")
	_check(RULES.music_track_for_phase("planning") == "battle" and RULES.music_track_for_phase("draw") == "battle", "планирование и добор играют боевой трек")
	_check(RULES.music_track_for_phase("result") == "" and RULES.music_track_for_phase("") == "", "результат и пустая фаза без музыки")
	_check(RULES.music_files("draft") == ["sound/music/draft_theme.mp3"], "файл драфта — draft_theme.mp3")
	_check(RULES.music_files("battle") == ["sound/music/battle_theme_1.mp3", "sound/music/battle_theme_2.mp3"], "боевые треки — battle_theme_1 и 2")
	_check(RULES.music_files("unknown").is_empty(), "неизвестный трек пуст")
	_check(RULES.music_files("tavern") == ["sound/music/tavern_theme_1.mp3", "sound/music/tavern_theme_2.mp3", "sound/music/tavern_theme_3.mp3", "sound/music/tavern_theme_4.mp3"], "таверна — четыре трека tavern_theme_1..4")
	_check(RULES.TAVERN_TRACK == "tavern" and not RULES.track_loops("tavern") and RULES.track_loops("draft") and RULES.track_loops("battle"), "таверновые треки не зацикливаются, боевые и драфт зацикливаются")
	_check(RULES.effect_files("damage").size() == 5 and RULES.effect_files("damage")[4] == "sound/effects/damage_5.mp3", "пять звуков урона")
	_check(RULES.effect_files("dodge") == ["sound/effects/dodge_hit.mp3", "sound/effects/dodge_whoosh.mp3"], "уворот — два звука")
	_check(RULES.effect_plays_all("dodge") and not RULES.effect_plays_all("damage"), "уворот играет оба звука, урон выбирает один")
	_check(RULES.effect_ducks_music("damage") and RULES.effect_ducks_music("dodge") and RULES.effect_ducks_music("critical_hit"), "удары приглушают музыку")
	_check(not RULES.effect_ducks_music("card_move") and not RULES.effect_ducks_music("draft_cards_deal"), "перемещение карты и раздача музыку не приглушают")

	_check(RULES.effects_for_exchange([{"damage": 3, "critical": false}]) == ["damage"], "обычный удар даёт звук урона")
	_check(RULES.effects_for_exchange([{"damage": 5, "critical": true, "critical_attack": true}]) == ["damage", "critical_hit"], "критический удар даёт урон и крит")
	_check(RULES.effects_for_exchange([{"attack_dodged": true, "damage": 0}]) == ["dodge"], "уворот даёт звук уворота")
	_check(RULES.effects_for_exchange([{"damage": 0, "healed": 4}]).is_empty(), "лечение без удара без звука")
	_check(RULES.effects_for_exchange([{"hit_results": [{"dodged": true}, {"damage": 2, "critical": true}]}]) == ["dodge", "damage", "critical_hit"], "серия ударов играет по одному звуку на тип")
	_check(RULES.effects_for_exchange([{"damage": 0, "critical_attack": true}]) == ["damage"], "атака без урона звучит как удар")
	_check(RULES.effects_for_exchange([{"skipped": true, "damage": 0}]).is_empty() and RULES.effects_for_exchange([]).is_empty() and RULES.effects_for_exchange(null).is_empty(), "пропуск, пустой обмен и пустое значение без звука")
	_check(RULES.effects_for_exchange([{"damage": 2}, {"damage": 3}]) == ["damage", "damage"], "каждый удар проигрывает свой звук")

	_check(RULES.effects_for_action("pick_starting") == ["card_move"] and RULES.effects_for_action("pick_redraft") == ["card_move"], "выбор карты в драфте играет перемещение")
	_check(RULES.effects_for_action("deselect") == ["card_move"], "возврат выбранной карты играет перемещение")
	_check(RULES.effects_for_action("select").is_empty() and RULES.effects_for_action("confirm").is_empty() and RULES.effects_for_action("choose_draw").is_empty(), "розыгрыш, подтверждение и добор без звука, как в Python")
	_check(RULES.effects_for_draft_start("starting") == ["draft_cards_deal"] and RULES.effects_for_draft_start("redraft").is_empty(), "раздача звучит только в стартовом драфте")
	_check(is_equal_approx(RULES.effect_delay("draft_cards_deal"), 1.0) and RULES.effect_delay("card_move") == 0.0, "раздача через 1 с после начала драфта")
	_check(is_equal_approx(RULES.DRAFT_INTRO_SECONDS, 2.0) and RULES.DRAFT_TRACK == "draft", "интро стартового драфта 2 с (две фазы по 1 с)")
	_check(is_equal_approx(RULES.draft_music_delay("starting"), 2.0) and RULES.draft_music_delay("redraft") == 0.0, "перераздача звучит без интро")
	_check(RULES.draft_pick_keys({"opponent_draft_picks": ["a", "b"]}) == ["a", "b"] and RULES.draft_pick_keys({}).is_empty(), "выборы соперника читаются из снимка, без поля они пусты")
	_check(RULES.new_draft_picks([], ["a"]) == ["a"] and RULES.new_draft_picks(["a"], ["a", "b"]) == ["b"], "новыми считаются только ключи, которых не было")
	_check(RULES.new_draft_picks(["a", "a"], ["a"]).is_empty() and RULES.new_draft_picks(["a"], ["a", "a"]) == ["a"], "копии одной карты считаются по отдельности")
	_check(RULES.new_draft_picks(["a", "b"], []).is_empty(), "пустой драфт не даёт новых выборов")
	_check(RULES.effects_for_enemy_picks(["a", "b"]) == ["card_move", "card_move"] and RULES.effects_for_enemy_picks([]).is_empty(), "каждый выбор соперника — перемещение карты")
	_check(RULES.last_draft_pick_keys({"opponent_last_draft_picks": ["a", "b"]}) == ["a", "b"] and RULES.last_draft_pick_keys({"opponent_draft_picks": ["a"]}).is_empty(), "последние выборы соперника читаются из своего поля")

	_check(is_equal_approx(RULES.TRANSITION_FADE_SECONDS, 0.75), "затухание перехода 0.75 с")
	_check(is_equal_approx(RULES.MUSIC_VOLUME, 1.0) and is_equal_approx(RULES.EFFECT_VOLUME, 1.0), "громкость музыки и эффектов 1.0")
	_check(is_equal_approx(RULES.DUCK_VOLUME, 0.5) and is_equal_approx(RULES.DUCK_HOLD_SECONDS, 1.2), "приглушение до 0.5 на 1.2 с")
	_check(is_equal_approx(RULES.CLASH_DUCK_SECONDS, 1.5), "приглушение на клэше 1.5 с (0.5 + 1.0 из settings.py)")
	_check(is_equal_approx(RULES.ATTACK_ANIMATION_SECONDS, 0.5), "удары звучат через 0.5 с после начала клэша")
	_check(is_equal_approx(RULES.gain_to_db(1.0), 0.0) and RULES.gain_to_db(0.0) == RULES.SILENT_DB and is_equal_approx(RULES.gain_to_db(0.5), -6.0206), "громкость переводится в дБ")

	var fade := RULES.fade_start(1.0, RULES.TRANSITION_FADE_SECONDS)
	_check(is_equal_approx(RULES.fade_gain(fade), 1.0), "затухание начинается с полной громкости")
	fade = RULES.fade_advance(fade, 0.375)
	_check(is_equal_approx(RULES.fade_gain(fade), 0.5) and not RULES.fade_finished(fade), "на половине затухания половина громкости")
	fade = RULES.fade_advance(fade, 0.5)
	_check(RULES.fade_finished(fade) and RULES.fade_gain(fade) == 0.0, "затухание заканчивается тишиной")

	var duck := RULES.duck_begin(RULES.duck_idle(), RULES.DUCK_HOLD_SECONDS, RULES.DUCK_VOLUME)
	_check(str(duck["state"]) == "down", "приглушение начинается со спада")
	duck = RULES.duck_advance(duck, 0.02)
	_check(str(duck["state"]) == "held" and is_equal_approx(float(duck["volume"]), 0.5), "за 20 мс музыка падает до 0.5 и держится")
	duck = RULES.duck_advance(duck, 1.0)
	duck = RULES.duck_begin(duck, RULES.DUCK_HOLD_SECONDS, RULES.DUCK_VOLUME)
	duck = RULES.duck_advance(duck, 0.5)
	_check(str(duck["state"]) == "held", "повторный удар продлевает удержание")
	duck = RULES.duck_advance(duck, 0.8)
	_check(str(duck["state"]) == "up", "после удержания громкость возвращается")
	duck = RULES.duck_advance(duck, 0.03)
	_check(str(duck["state"]) == "idle" and is_equal_approx(float(duck["volume"]), 1.0), "возврат громкости завершается на 1.0")

	_check(RULES.default_assets_root("E:/python/game/godot_client") == "E:/python/game/assets", "ассеты лежат рядом с godot_client")
	var strike_events := [{"damage": 1}]
	var resolved := [{"turn": 2, "events": strike_events}]
	_check(RULES.exchange_key("b1", [], []).is_empty() and RULES.exchange_key("b1", resolved, [{"damage": 9}]).is_empty(), "ключ пуст без записи того же обмена")
	_check(not RULES.exchange_key("b1", resolved, strike_events).is_empty(), "ключ есть у записи розыгрыша")
	_check(RULES.exchange_key("b1", resolved, strike_events) == RULES.exchange_key("b1", resolved + [{"turn": 2, "events": [{"side": "player", "burned": true}]}], strike_events), "сожжение карты не меняет ключ обмена")
	_check(RULES.exchange_key("b1", resolved, strike_events) != RULES.exchange_key("b1", [{"turn": 3, "events": strike_events}], strike_events), "розыгрыш с теми же событиями на другом ходу — другой ключ")


func _check_manager() -> void:
	var manager = AUDIO_SCRIPT.new()
	add_child(manager)
	manager.set_process(false)
	await get_tree().process_frame
	_check(FileAccess.file_exists(manager.sound_root.path_join("sound/music/draft_theme.mp3")), "файлы музыки найдены рядом с проектом")

	_check(manager.play_track("draft") and manager.current_track() == "draft" and manager.is_music_playing(), "драфт запускается и играет")
	var starts: int = manager.music_starts()
	_check(manager.play_track("draft") and manager.music_starts() == starts, "повторный запуск того же трека не перезапускает его")
	manager.sync_battle_music({"phase": "planning"})
	var battle_file: String = manager.track_file()
	_check(manager.current_track() == "battle" and manager.is_music_playing(), "планирование переключает на боевой трек")
	_check(battle_file.ends_with("battle_theme_1.mp3") or battle_file.ends_with("battle_theme_2.mp3"), "боевой трек выбран из двух файлов")
	starts = manager.music_starts()
	manager.sync_battle_music({"phase": "draw"})
	manager.sync_battle_music({"phase": "planning"})
	_check(manager.music_starts() == starts and manager.track_file() == battle_file, "добор и планирование не перезапускают боевой трек")

	manager.fade_out_all(0.5)
	_check(manager.is_fading() and manager.is_music_playing(), "затухание идёт, музыка ещё звучит")
	manager.tick(0.25)
	_check(manager.is_fading() and absf(manager.music_volume_db() - RULES.gain_to_db(0.5)) < 0.01, "на половине затухания громкость около половины")
	manager.tick(0.3)
	_check(not manager.is_fading() and manager.current_track().is_empty() and not manager.is_music_playing(), "затухание заканчивается остановкой")
	manager.stop_music()
	manager.stop_music()
	_check(manager.current_track().is_empty() and not manager.is_music_playing(), "повторная остановка безопасна")

	manager.play_track("battle")
	_check(is_equal_approx(manager.fade_out_for_transition(), 0.75) and manager.is_fading(), "переход затухает музыку на 0.75 с")
	manager.tick(0.75)
	_check(manager.current_track().is_empty(), "после перехода музыки нет")

	manager.play_track("battle")
	manager.play_effect("damage")
	_check(manager.effect_count("damage") == 1 and manager.duck_state() == "down", "удар приглушает боевую музыку")
	manager.tick(0.02)
	_check(manager.duck_state() == "held" and absf(manager.music_volume_db() - RULES.gain_to_db(0.5)) < 0.01, "приглушённая музыка держится на половине громкости")
	manager.tick(1.3)
	_check(manager.duck_state() == "up", "после удержания музыка начинает возвращаться")
	manager.tick(0.03)
	_check(manager.duck_state() == "idle" and absf(manager.music_volume_db()) < 0.01, "громкость возвращается к 1.0")
	manager.stop_music()

	_check(manager.play_effect("card_move") and manager.effect_count("card_move") == 1, "перемещение карты играет один звук")
	_check(manager.play_effect("dodge") and manager.effect_count("dodge") == 1, "уворот играет оба звука")
	_check(not manager.play_effect("victory") and manager.effect_count("victory") == 0, "неизвестный эффект тихо пропускается")
	manager.on_battle_action("pick_starting")
	_check(manager.effect_count("card_move") == 2, "выбор карты в драфте играет перемещение")

	var missing = AUDIO_SCRIPT.new()
	add_child(missing)
	missing.set_process(false)
	await get_tree().process_frame
	missing.sound_root = ProjectSettings.globalize_path("res://").path_join(MISSING_ROOT)
	_check(not missing.play_track("draft") and not missing.is_music_playing(), "нет файла музыки — трек пропущен")
	_check(not missing.play_effect("card_move") and missing.effect_count("card_move") == 0, "нет файла эффекта — звук пропущен")
	missing.sync_battle_music({"phase": "planning"})
	missing.on_battle_update({"battle_id": "b9", "history": [], "last_exchange": [{"damage": 2}]})
	missing.tick(1.0)
	_check(missing.current_track().is_empty() and not missing.is_music_playing(), "отсутствующие файлы не ломают синхронизацию")

	var draft = AUDIO_SCRIPT.new()
	add_child(draft)
	draft.set_process(false)
	await get_tree().process_frame
	draft.sync_battle_music({"phase": "draft", "draft_mode": "starting"})
	_check(draft.current_track().is_empty() and draft.pending_count() == 1, "драфт ждёт интро перед музыкой")
	draft.tick(2.0)
	_check(draft.current_track() == "draft" and draft.pending_count() == 1, "после интро звучит музыка драфта, раздача запланирована")
	draft.tick(0.5)
	_check(draft.effect_count("draft_cards_deal") == 0, "раздача ещё не звучит")
	draft.tick(0.6)
	_check(draft.effect_count("draft_cards_deal") == 1 and draft.pending_count() == 0, "раздача звучит через секунду после старта музыки драфта")
	draft.sync_battle_music({"phase": "draft", "draft_mode": "starting"})
	draft.tick(2.0)
	_check(draft.effect_count("draft_cards_deal") == 1 and draft.music_starts() == 1, "повторный снимок драфта не повторяет раздачу и музыку")
	draft.on_battle_update({"battle_id": "b2", "history": [], "last_exchange": []})
	var exchange := [{"damage": 2}]
	draft.on_battle_update({"battle_id": "b2", "history": [{"turn": 2, "events": exchange}], "last_exchange": exchange})
	_check(draft.effect_count("damage") == 0 and draft.duck_state() == "down", "новый обмен сразу приглушает музыку, удар ждёт конца клэша")
	draft.tick(0.6)
	_check(draft.effect_count("damage") == 1, "новый обмен ударами звучит один раз, через 0.5 с")
	draft.on_battle_update({"battle_id": "b2", "history": [{"turn": 2, "events": exchange}], "last_exchange": exchange})
	draft.tick(0.6)
	_check(draft.effect_count("damage") == 1, "повторный снимок обмена не повторяет удар")
	draft.sync_battle_music({"phase": "result"})
	_check(draft.current_track().is_empty() and draft.pending_count() == 0, "результат останавливает музыку")

	var loose = AUDIO_SCRIPT.new()
	_check(not loose.play_track("draft") and not loose.play_effect("card_move"), "вне дерева сцены звук пропускается без ошибок")
	loose.sync_battle_music({"phase": "draft"})
	loose.tick(0.1)
	_check(is_equal_approx(loose.fade_out_for_transition(), 0.75), "вне дерева переход тоже возвращает длительность")
	loose.free()

	var live = AUDIO_SCRIPT.new()
	add_child(live)
	await get_tree().process_frame
	live.play_track("draft")
	live.fade_out_all(0.1)
	await get_tree().create_timer(0.4).timeout
	_check(live.current_track().is_empty(), "затухание завершается само по кадрам")

	for node in [manager, missing, draft, live]:
		node.queue_free()
	await get_tree().process_frame


func _check_clash() -> void:
	var clash = AUDIO_SCRIPT.new()
	add_child(clash)
	clash.set_process(false)
	await get_tree().process_frame
	var hit := [{"damage": 4, "critical": true, "critical_attack": true}]
	var second := [{"damage": 2}]
	clash.on_battle_update({"battle_id": "k1", "history": [], "last_exchange": []})
	_check(clash.duck_state() == "idle", "первый снимок боя не приглушает музыку")
	clash.on_battle_update({"battle_id": "k2", "history": [_resolve(3, hit)], "last_exchange": hit})
	_check(clash.duck_state() == "idle" and clash.effect_count("damage") == 0, "первый снимок с прошлым обменом молчит и не приглушает")
	var history := [_resolve(3, hit), _resolve(4, second)]
	clash.on_battle_update({"battle_id": "k2", "history": history, "last_exchange": second})
	_check(clash.duck_state() == "down" and clash.effect_count("damage") == 0, "новый обмен сразу приглушает музыку на клэше, удар ждёт")
	clash.tick(0.02)
	clash.tick(0.3)
	_check(clash.duck_state() == "held" and clash.effect_count("damage") == 0, "до конца клэша удара нет")
	clash.tick(0.3)
	_check(clash.effect_count("damage") == 1, "через 0.5 с клэша звучит удар")
	clash.tick(0.9)
	_check(clash.duck_state() == "held", "удар продлевает приглушение до 1.2 с")
	clash.tick(0.2)
	_check(clash.duck_state() == "up", "через 1.7 с после клэша музыка возвращается")
	clash.on_battle_update({"battle_id": "k2", "history": history, "last_exchange": second})
	_check(clash.duck_state() == "up" and clash.effect_count("damage") == 1, "повторный снимок того же обмена не приглушает и не играет снова")
	var burned: Array = history + [{"turn": 4, "events": [{"side": "player", "card": "Огонь", "burned": true}]}]
	clash.on_battle_update({"battle_id": "k2", "history": burned, "last_exchange": second})
	_check(clash.duck_state() == "up" and clash.effect_count("damage") == 1, "сожжение карты не считается новым обменом")
	clash.on_battle_update({"battle_id": "k2", "turn": 5, "history": history, "last_exchange": second})
	_check(clash.duck_state() == "up" and clash.effect_count("damage") == 1, "смена хода без розыгрыша не приглушает")
	clash.on_battle_update({"battle_id": "k2", "history": history + [_resolve(5, second)], "last_exchange": second})
	_check(clash.duck_state() == "down" and clash.effect_count("damage") == 1, "следующий розыгрыш сразу приглушает музыку, удар позже")
	clash.tick(0.6)
	_check(clash.effect_count("damage") == 2, "удар следующего розыгрыша звучит через 0.5 с")
	clash.queue_free()
	await get_tree().process_frame


func _check_tavern() -> void:
	var tavern = AUDIO_SCRIPT.new()
	add_child(tavern)
	tavern.set_process(false)
	await get_tree().process_frame
	_check(tavern.play_tavern() and tavern.current_track() == "tavern" and tavern.is_tavern_active(), "таверна запускает случайный трек")
	_check(RULES.music_files("tavern").has(tavern.track_file()), "трек таверны взят из четырёх файлов")
	_check(not (tavern._music_player.stream as AudioStreamMP3).loop, "трек таверны не зацикливается")
	var starts: int = tavern.music_starts()
	tavern._music_player.stop()
	tavern._music_player.finished.emit()
	_check(tavern.music_starts() == starts + 1 and tavern.is_music_playing() and tavern.is_tavern_active(), "по сигналу finished запускается следующий трек таверны")
	_check(RULES.music_files("tavern").has(tavern.track_file()), "следующий трек тоже из списка таверны")
	tavern.play_track("battle")
	_check(not tavern.is_tavern_active() and tavern.current_track() == "battle", "боевой трек отключает режим таверны")
	starts = tavern.music_starts()
	tavern._music_player.stop()
	tavern._music_player.finished.emit()
	_check(tavern.music_starts() == starts and not tavern.is_tavern_active(), "конец боевого трека не запускает таверну")
	tavern.play_tavern()
	tavern.fade_out_all(0.5)
	_check(not tavern.is_tavern_active() and tavern.is_fading(), "затухание перехода тоже выключает режим таверны")
	tavern.play_tavern()
	tavern.stop_tavern()
	_check(not tavern.is_tavern_active() and tavern.current_track().is_empty() and not tavern.is_music_playing(), "выход из таверны останавливает музыку")
	tavern.stop_tavern()
	_check(not tavern.is_tavern_active(), "повторный выход из таверны безопасен")
	tavern.sound_root = ProjectSettings.globalize_path("res://").path_join(MISSING_ROOT)
	_check(not tavern.play_tavern() and tavern.current_track().is_empty(), "нет файлов таверны — трек пропущен без ошибок")
	tavern.queue_free()
	await get_tree().process_frame


func _check_draft_intro() -> void:
	var intro = AUDIO_SCRIPT.new()
	add_child(intro)
	intro.set_process(false)
	await get_tree().process_frame
	intro.sync_battle_music({"phase": "draft", "draft_mode": "starting"})
	intro.sync_battle_music({"phase": "draft", "draft_mode": "starting"})
	_check(intro.pending_count() == 1, "повторный снимок во время интро не планирует второй старт")
	intro.tick(1.9)
	_check(intro.current_track().is_empty(), "первая секунда интро: музыки драфта нет")
	intro.tick(0.2)
	_check(intro.current_track() == "draft" and intro.music_starts() == 1, "со второй секундой интро звучит музыка драфта")
	intro.tick(0.5)
	_check(intro.effect_count("draft_cards_deal") == 0, "раздача ещё не звучит")
	intro.tick(0.6)
	_check(intro.effect_count("draft_cards_deal") == 1, "раздача через секунду после старта музыки")

	var redraft = AUDIO_SCRIPT.new()
	add_child(redraft)
	redraft.set_process(false)
	await get_tree().process_frame
	redraft.sync_battle_music({"phase": "draft", "draft_mode": "redraft"})
	_check(redraft.current_track() == "draft" and redraft.pending_count() == 0, "перераздача запускает музыку сразу, без интро и раздачи")

	var ended = AUDIO_SCRIPT.new()
	add_child(ended)
	ended.set_process(false)
	await get_tree().process_frame
	ended.sync_battle_music({"phase": "draft", "draft_mode": "starting"})
	ended.sync_battle_music({"phase": "result"})
	ended.tick(3.0)
	_check(ended.music_starts() == 0 and ended.pending_count() == 0, "результат до конца интро отменяет старт драфта")

	var skipped = AUDIO_SCRIPT.new()
	add_child(skipped)
	skipped.set_process(false)
	await get_tree().process_frame
	skipped.sync_battle_music({"phase": "draft", "draft_mode": "starting"})
	skipped.sync_battle_music({"phase": "planning"})
	skipped.tick(3.0)
	_check(skipped.current_track() == "battle" and skipped.music_starts() == 1, "переход в планирование отменяет старт драфта и звучит боевой трек")

	for node in [intro, redraft, ended, skipped]:
		node.queue_free()
	await get_tree().process_frame


func _check_enemy_picks() -> void:
	var picks = AUDIO_SCRIPT.new()
	add_child(picks)
	picks.set_process(false)
	await get_tree().process_frame
	picks.on_battle_update({"battle_id": "p1", "history": [], "last_exchange": [], "opponent_draft_picks": ["x1"]})
	_check(picks.effect_count("card_move") == 0, "первый снимок боя не проигрывает выборы соперника")
	picks.on_battle_update({"battle_id": "p1", "history": [], "last_exchange": [], "opponent_draft_picks": ["x1", "x2"]})
	_check(picks.effect_count("card_move") == 1, "новый выбор соперника играет перемещение карты")
	picks.on_battle_update({"battle_id": "p1", "history": [], "last_exchange": [], "opponent_draft_picks": ["x1", "x2"]})
	_check(picks.effect_count("card_move") == 1, "повторный снимок не повторяет выбор")
	picks.on_battle_update({"battle_id": "p1", "history": [], "last_exchange": [], "opponent_draft_picks": ["x1", "x2", "x2"]})
	_check(picks.effect_count("card_move") == 2, "вторая копия той же карты считается отдельным выбором")
	picks.on_battle_update({"battle_id": "p1", "history": [], "last_exchange": [], "opponent_draft_picks": []})
	picks.on_battle_update({"battle_id": "p1", "history": [], "last_exchange": [], "opponent_draft_picks": ["y1"]})
	_check(picks.effect_count("card_move") == 3, "перераздача в том же бою играет свои выборы")
	picks.on_battle_update({"battle_id": "p2", "history": [], "last_exchange": [], "opponent_draft_picks": ["z1"]})
	_check(picks.effect_count("card_move") == 3, "первый снимок нового боя не проигрывает выборы")
	picks.on_battle_update({"battle_id": "p2", "history": [], "last_exchange": []})
	_check(picks.effect_count("card_move") == 3, "снимок без поля выборов ничего не проигрывает")
	picks.queue_free()
	await get_tree().process_frame

	var last = AUDIO_SCRIPT.new()
	add_child(last)
	last.set_process(false)
	await get_tree().process_frame
	last.on_battle_update(_pick_state("l1", "draft", []))
	last.on_battle_update(_pick_state("l1", "draft", ["x1"]))
	_check(last.effect_count("card_move") == 1, "выбор соперника в драфте звучит сразу")
	last.on_battle_update(_pick_state("l1", "planning", [], ["x1", "x2"]))
	_check(last.effect_count("card_move") == 2, "выход из драфта играет последний выбор, которого не было в снимках драфта")
	last.on_battle_update(_pick_state("l1", "planning", [], ["x1", "x2"]))
	_check(last.effect_count("card_move") == 2, "повторный снимок после драфта не повторяет выборы")
	last.on_battle_update(_pick_state("l1", "planning", [], []))
	_check(last.effect_count("card_move") == 2, "розыгрыш очищает последний драфт и ничего не играет")
	last.on_battle_update(_pick_state("l2", "draft", ["b1", "b2"]))
	last.on_battle_update(_pick_state("l2", "planning", [], ["b1", "b2"]))
	_check(last.effect_count("card_move") == 2, "стартовые выборы бота до первого снимка не звучат, и на выходе тоже")
	last.on_battle_update(_pick_state("l3", "planning", [], ["c1", "c2"]))
	_check(last.effect_count("card_move") == 2, "вход в бой после драфта не проигрывает его выборы")
	last.on_battle_update(_pick_state("l4", "draft", []))
	last.on_battle_update(_pick_state("l4", "draft", ["d1"]))
	last.on_battle_update(_pick_state("l4", "draft", ["d1", "d1"]))
	last.on_battle_update(_pick_state("l4", "result", [], ["d1", "d1", "d1"]))
	_check(last.effect_count("card_move") == 5, "копии одной карты в драфте и на выходе считаются отдельно")
	last.on_battle_update(_pick_state("l5", "draft", []))
	last.on_battle_update(_pick_state("l5", "planning", [], ["s1"]))
	last.on_battle_update(_pick_state("l5", "planning", [], []))
	last.on_battle_update(_pick_state("l5", "draft", ["r1"]))
	last.on_battle_update(_pick_state("l5", "planning", [], ["r1", "r2"]))
	_check(last.effect_count("card_move") == 8, "перераздача в том же бою играет свои выборы и её последний выбор")
	last.queue_free()
	await get_tree().process_frame


func _battle(phase: String, draft_mode: String, exchange: Array, turn := 1, history: Array = [], picks: Array = [], last_picks: Array = []) -> Dictionary:
	return {
		"battle_id": "b1",
		"phase": phase,
		"draft_mode": draft_mode,
		"turn": turn,
		"seconds_left": 0,
		"fighter": {"name": "Тест", "hp": 60, "max_hp": 142, "mp": 20, "max_mp": 20},
		"opponent": {"name": "Соперник", "hp": 50, "max_hp": 80, "mp": 10, "max_mp": 10},
		"table": [],
		"hand": [],
		"selected": [],
		"can_select": [],
		"draw_choices": [],
		"confirmed": false,
		"opponent_draft_picks": picks,
		"opponent_last_draft_picks": last_picks,
		"history": history,
		"last_exchange": exchange,
		"outcome": "",
	}


func _resolve(turn: int, events: Array) -> Dictionary:
	return {"turn": turn, "events": events}


func _pick_state(battle_id: String, phase: String, picks: Array, last_picks: Array = []) -> Dictionary:
	return {
		"battle_id": battle_id,
		"phase": phase,
		"history": [],
		"last_exchange": [],
		"opponent_draft_picks": picks,
		"opponent_last_draft_picks": last_picks,
	}


func _wait_idle(deck) -> void:
	var started := Time.get_ticks_msec()
	while not deck._pending_action.is_empty() and Time.get_ticks_msec() - started < 5000:
		await get_tree().create_timer(0.01).timeout
	await get_tree().process_frame


func _check_world_hooks() -> void:
	GameSession.clear()
	GameSession.hub_url = UNREACHABLE_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": UNREACHABLE_URL, "name": "Тест"}
	GameSession.character = {
		"id": 42,
		"name": "Тест",
		"type": "warrior",
		"level": 5,
		"hp": 60,
		"max_hp": 142,
		"mp": 20,
		"max_mp": 20,
		"coins": 500,
		"zone": "backyard",
		"position_x": float(25 * 48 + 24),
		"position_y": float(43 * 48 + 24),
		"position_direction": "s",
		"talents": {},
	}
	ApiClient._http.timeout = 0.5
	var deck = DECK_SCRIPT.new()
	deck.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(deck)
	deck._social_timer.stop()
	deck._battle_timer.stop()
	await _wait_idle(deck)
	var audio = deck.get("_audio")
	_check(audio != null and audio.current_track().is_empty(), "мир создаёт менеджер звука без музыки")
	if audio == null:
		deck.queue_free()
		return

	deck._pending_action = "battle_start"
	deck._on_api_completed(true, {"battle": _battle("draft", "starting", [], 1, [], ["e0"])})
	await SCENE_TRANSITION.wait_until_idle(get_tree())
	deck._battle_timer.stop()
	_check(audio.current_track().is_empty() and audio.pending_count() == 1, "стартовый драфт ждёт интро, музыка не звучит сразу")
	audio.tick(2.0)
	_check(audio.current_track() == "draft" and audio.is_music_playing(), "после интро звучит музыка драфта")
	audio.tick(1.0)
	_check(audio.effect_count("draft_cards_deal") == 1, "раздача карт через 1 с после старта музыки драфта")
	_check(audio.duck_state() == "idle", "первый снимок боя в мире не приглушает музыку")

	deck._pending_action = "battle_action"
	deck._on_api_completed(true, {"battle": _battle("draft", "starting", [], 1, [], ["e0", "e1"])})
	deck._battle_timer.stop()
	_check(audio.effect_count("card_move") == 1, "выбор соперника в драфте играет перемещение карты, стартовый снимок — нет")
	deck._pending_action = "battle_action"
	deck._on_api_completed(true, {"battle": _battle("planning", "", [], 1, [], [], ["e0", "e1", "e2"])})
	deck._battle_timer.stop()
	_check(audio.effect_count("card_move") == 2, "последний выбор соперника звучит при выходе из драфта")
	_check(deck._phase_transition.is_active() and audio.is_fading(), "переход драфта в планирование затухает музыку")
	deck._pending_action = "battle_active"
	deck._on_api_completed(true, {"battle": _battle("planning", "", [], 1, [], [], ["e0", "e1", "e2"])})
	deck._battle_timer.stop()
	_check(audio.effect_count("card_move") == 2, "опрос после драфта не повторяет последний выбор")
	await get_tree().create_timer(0.9).timeout
	deck._battle_timer.stop()
	_check(not deck._phase_transition.is_active() and audio.current_track() == "battle", "после перехода звучит боевой трек")

	var strike := [{"side": "enemy", "card": "Удар", "damage": 4, "healed": 0, "critical": true, "critical_attack": true}]
	deck._pending_action = "battle_action"
	deck._on_api_completed(true, {"battle": _battle("planning", "", strike, 2, [_resolve(1, strike)])})
	deck._battle_timer.stop()
	_check(audio.duck_state() == "down" and audio.effect_count("damage") == 0, "новый обмен сразу приглушает музыку клэшем, удар ждёт")
	audio.tick(0.6)
	_check(audio.effect_count("damage") == 1 and audio.effect_count("critical_hit") == 1, "через 0.5 с клэша звучат удар с критом")
	deck._pending_action = "battle_active"
	deck._on_api_completed(true, {"battle": _battle("planning", "", strike, 2, [_resolve(1, strike)])})
	deck._battle_timer.stop()
	audio.tick(0.6)
	_check(audio.effect_count("damage") == 1 and audio.effect_count("critical_hit") == 1, "опрос того же хода не повторяет удары")

	var card_moves: int = audio.effect_count("card_move")
	deck._battle_action("deselect", "k1")
	await _wait_idle(deck)
	_check(audio.effect_count("card_move") == card_moves + 1, "возврат выбранной карты играет перемещение")

	deck._pending_action = "battle_action"
	var final := [{"side": "player", "card": "Исцеление", "damage": 0, "healed": 3}]
	deck._on_api_completed(true, {"battle": _battle("result", "", final, 3, [_resolve(1, strike), _resolve(2, final)])})
	deck._battle_timer.stop()
	_check(deck._phase_transition.is_active() and audio.is_fading(), "итог боя затухает музыку перед переходом")
	await get_tree().create_timer(0.9).timeout
	deck._battle_timer.stop()
	_check(audio.current_track().is_empty() and not audio.is_music_playing(), "после итога музыка остановлена")
	_check(str(deck._battle_state.get("phase", "")) == "result", "экран итога показан")
	deck._enter_location("tavern")
	await _wait_idle(deck)
	await get_tree().create_timer(0.6).timeout
	_check(audio.is_tavern_active() and audio.current_track() == "tavern", "вход в таверну запускает музыку таверны после перехода")
	deck._enter_location("world_map")
	_check(audio.is_fading() and not audio.is_tavern_active(), "выход из таверны затухает музыку за время перехода")
	await _wait_idle(deck)
	await get_tree().create_timer(0.6).timeout
	_check(not audio.is_tavern_active() and audio.current_track().is_empty(), "после перехода выход из таверны останавливает музыку")
	deck._enter_location("character_room")
	await _wait_idle(deck)
	await get_tree().create_timer(0.6).timeout
	_check(audio.current_track().is_empty() and not audio.is_tavern_active(), "комната персонажа тихая после перехода")
	deck._enter_location("world_map")
	await _wait_idle(deck)
	await get_tree().create_timer(0.6).timeout
	_check(audio.current_track() == "tavern" and not audio.is_tavern_active(), "выход из комнаты на карту играет один трек таверны")

	deck.queue_free()
	await get_tree().process_frame
