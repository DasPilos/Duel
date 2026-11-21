extends RefCounted

# Звук боя Deck: трек и эффект для фазы и события, как deck/ui/music.py и вызовы из deck/scenes/duel_*.py.
# Файлы лежат в assets/sound рядом с godot_client; отсутствующие файлы менеджер пропускает.

const TRANSITION_FADE_SECONDS := 0.75
const MUSIC_VOLUME := 1.0
const EFFECT_VOLUME := 1.0
const DUCK_VOLUME := 0.5
const DUCK_HOLD_SECONDS := 1.2
const DUCK_FADE_DOWN_SECONDS := 0.020
const DUCK_FADE_UP_SECONDS := 0.030
# ATTACK_ANIMATION_SECONDS + DAMAGE_ANIMATION_SECONDS из deck/settings.py (0.5 + 1.0): клэш приглушает музыку.
const CLASH_DUCK_SECONDS := 1.5
# ATTACK_ANIMATION_SECONDS из deck/settings.py: удары звучат, когда duel_scene.py после клэша вызывает resolve_turn().
const ATTACK_ANIMATION_SECONDS := 0.5
# intro_table и intro_deck по 1 с (deck/scenes/duel_scene.py: старт сцены, затем draft_reveal с play_draft_music).
const DRAFT_INTRO_SECONDS := 2.0
const DRAFT_TRACK := "draft"
# DRAFT_REVEAL_START_DELAY_SECONDS из deck/settings.py.
const DRAFT_DEAL_DELAY_SECONDS := 1.0
const SILENT_DB := -80.0
const PROJECT_ASSETS_RELATIVE := "../assets"

const DUCK_IDLE := "idle"
const DUCK_DOWN := "down"
const DUCK_HELD := "held"
const DUCK_UP := "up"

const TAVERN_TRACK := "tavern"
# Музыка смены экрана мира (DeckWorld._switch в Python): close() старого экрана, затем __init__ нового.
const LOCATION_NONE := ""
const LOCATION_STOP := "stop"
const LOCATION_TAVERN_REPEAT := "tavern_repeat"
const LOCATION_TAVERN_ONCE := "tavern_once"
const TRACK_FILES := {
	"draft": ["sound/music/draft_theme.mp3"],
	"battle": ["sound/music/battle_theme_1.mp3", "sound/music/battle_theme_2.mp3"],
	"tavern": [
		"sound/music/tavern_theme_1.mp3",
		"sound/music/tavern_theme_2.mp3",
		"sound/music/tavern_theme_3.mp3",
		"sound/music/tavern_theme_4.mp3",
	],
}
const EFFECT_FILES := {
	"draft_cards_deal": ["sound/effects/draft_cards_deal.mp3"],
	"card_move": ["sound/effects/card_move.mp3"],
	"damage": [
		"sound/effects/damage_1.mp3",
		"sound/effects/damage_2.mp3",
		"sound/effects/damage_3.mp3",
		"sound/effects/damage_4.mp3",
		"sound/effects/damage_5.mp3",
	],
	"dodge": ["sound/effects/dodge_hit.mp3", "sound/effects/dodge_whoosh.mp3"],
	"critical_hit": ["sound/effects/critical_hit.mp3"],
}


static func default_assets_root(project_dir: String) -> String:
	return project_dir.path_join(PROJECT_ASSETS_RELATIVE).simplify_path()


static func resolve_path(assets_root: String, relative: String) -> String:
	return assets_root.path_join(relative)


# Драфт играет трек драфта; планирование и добор боевой трек; результат без музыки.
static func music_track_for_phase(phase: String) -> String:
	match phase:
		"draft":
			return "draft"
		"planning", "draw":
			return "battle"
	return ""


static func music_files(track_id: String) -> Array[String]:
	return _string_array(TRACK_FILES.get(track_id, []))


# Таверновые треки не зацикливаются: следующий берётся по сигналу finished.
static func track_loops(track_id: String) -> bool:
	return track_id != TAVERN_TRACK


static func effect_files(effect_id: String) -> Array[String]:
	return _string_array(EFFECT_FILES.get(effect_id, []))


# Уворот играет оба звука сразу; остальные эффекты выбирают один файл из набора.
static func effect_plays_all(effect_id: String) -> bool:
	return effect_id == "dodge"


# Удары приглушают боевую музыку, как duck_battle_music() в Python.
static func effect_ducks_music(effect_id: String) -> bool:
	return effect_id in ["damage", "dodge", "critical_hit"]


static func effect_delay(effect_id: String) -> float:
	return DRAFT_DEAL_DELAY_SECONDS if effect_id == "draft_cards_deal" else 0.0


# Стартовый драфт начинается с интро; перераздача играет сразу (play_draft_music() после deck_shuffle).
static func draft_music_delay(draft_mode: String) -> float:
	return DRAFT_INTRO_SECONDS if draft_mode == "starting" else 0.0


# Выбор карты в драфте и возврат выбранной карты в руку дают перемещение карты, как duel_input.py.
static func effects_for_action(action: String) -> Array[String]:
	var effects: Array[String] = []
	if action in ["pick_starting", "pick_redraft", "deselect"]:
		effects.append("card_move")
	return effects


# Раздача звучит только в стартовом драфте.
static func effects_for_draft_start(draft_mode: String) -> Array[String]:
	var effects: Array[String] = []
	if draft_mode == "starting":
		effects.append("draft_cards_deal")
	return effects


# Ключи карт, которые соперник взял в текущем драфте (поле opponent_draft_picks снимка боя).
static func draft_pick_keys(state: Dictionary) -> Array[String]:
	return _string_array(state.get("opponent_draft_picks", []))


# Ключи карт соперника из драфта, который только что закончился (поле opponent_last_draft_picks); живёт до розыгрыша.
static func last_draft_pick_keys(state: Dictionary) -> Array[String]:
	return _string_array(state.get("opponent_last_draft_picks", []))


# Выборы соперника, которых не было в прошлом снимке того же боя; копии одной карты считаются по отдельности.
static func new_draft_picks(previous: Array[String], current: Array[String]) -> Array[String]:
	var unmatched := {}
	for key in previous:
		unmatched[key] = int(unmatched.get(key, 0)) + 1
	var fresh: Array[String] = []
	for key in current:
		var count := int(unmatched.get(key, 0))
		if count > 0:
			unmatched[key] = count - 1
		else:
			fresh.append(key)
	return fresh


# Каждый новый выбор соперника — перемещение карты, как _start_enemy_card_transfer() в duel_scene.py.
static func effects_for_enemy_picks(fresh_picks: Array[String]) -> Array[String]:
	var effects: Array[String] = []
	for _pick in fresh_picks:
		effects.append("card_move")
	return effects


# Эффекты обмена ударами в том же порядке и количестве, что вызовы в duel_resolver.py.
static func effects_for_exchange(exchange: Variant) -> Array[String]:
	var effects: Array[String] = []
	if not exchange is Array:
		return effects
	for event_variant in exchange:
		if not event_variant is Dictionary:
			continue
		var event: Dictionary = event_variant
		var hit_results: Variant = event.get("hit_results", [])
		if hit_results is Array and not (hit_results as Array).is_empty():
			effects.append_array(_hit_results_effects(hit_results as Array))
			continue
		if bool(event.get("attack_dodged", false)):
			effects.append("dodge")
		if int(event.get("damage", 0)) <= 0 and not bool(event.get("critical_attack", false)):
			continue
		effects.append("damage")
		if bool(event.get("critical", false)):
			effects.append("critical_hit")
	return effects


# Ключ последнего обмена: запись history с теми же событиями, что last_exchange. Такая запись появляется
# только при розыгрыше хода; сожжение карты, добор и перераздача ключ не меняют.
static func exchange_key(battle_id: String, history: Variant, exchange: Variant) -> String:
	if not history is Array:
		return ""
	var events_json := JSON.stringify(exchange)
	var entries: Array = history
	for index in range(entries.size() - 1, -1, -1):
		var entry: Variant = entries[index]
		if entry is Dictionary and JSON.stringify(entry.get("events", [])) == events_json:
			return "%s|%s|%s" % [battle_id, str(entry.get("turn", 0)), events_json]
	return ""


# Действие музыки при смене экрана: close() старого экрана, затем __init__ нового. Таверна по кругу играет только
# в таверне (update_tavern_music), поэтому выход из комнаты на карту даёт один трек без повтора.
static func location_close_music(location: String) -> String:
	match location:
		"tavern":
			return LOCATION_STOP
		"character_room":
			return LOCATION_TAVERN_ONCE
	return LOCATION_NONE


static func location_init_music(location: String) -> String:
	match location:
		"tavern":
			return LOCATION_TAVERN_REPEAT
		"character_room":
			return LOCATION_STOP
	return LOCATION_NONE


# Итог перехода: если новый экран сам запускает или останавливает музыку, он важнее старого.
static func location_change_music(from: String, to: String) -> String:
	var init_music := location_init_music(to)
	if init_music != LOCATION_NONE:
		return init_music
	return location_close_music(from)


# Линейное затухание от from до нуля за duration секунд, как fadeout в pygame.
static func fade_start(from_gain: float, duration: float) -> Dictionary:
	return {"from": clampf(from_gain, 0.0, 1.0), "duration": maxf(duration, 0.0001), "elapsed": 0.0}


static func fade_advance(fade: Dictionary, dt: float) -> Dictionary:
	if fade.is_empty():
		return fade
	var advanced := fade.duplicate()
	advanced["elapsed"] = float(fade["elapsed"]) + dt
	return advanced


static func fade_finished(fade: Dictionary) -> bool:
	return not fade.is_empty() and float(fade["elapsed"]) >= float(fade["duration"])


static func fade_gain(fade: Dictionary) -> float:
	if fade.is_empty():
		return 1.0
	var progress := clampf(float(fade["elapsed"]) / float(fade["duration"]), 0.0, 1.0)
	return float(fade["from"]) * (1.0 - progress)


static func duck_idle() -> Dictionary:
	return {"state": DUCK_IDLE, "volume": MUSIC_VOLUME, "from": MUSIC_VOLUME, "to": MUSIC_VOLUME, "elapsed": 0.0, "hold_left": 0.0}


# Если музыка уже приглушена, удар только продлевает удержание, как в duck_battle_music().
static func duck_begin(duck: Dictionary, duration: float, target_volume: float) -> Dictionary:
	var state := str(duck.get("state", DUCK_IDLE))
	if state == DUCK_DOWN or state == DUCK_HELD:
		var extended := duck.duplicate()
		extended["to"] = target_volume
		extended["hold_left"] = maxf(float(duck["hold_left"]), duration)
		return extended
	var volume := float(duck.get("volume", MUSIC_VOLUME))
	return {"state": DUCK_DOWN, "volume": volume, "from": volume, "to": target_volume, "elapsed": 0.0, "hold_left": duration}


static func duck_advance(duck: Dictionary, dt: float) -> Dictionary:
	var state := str(duck.get("state", DUCK_IDLE))
	if state == DUCK_IDLE:
		return duck
	var next := duck.duplicate()
	var elapsed := float(duck["elapsed"]) + dt
	next["elapsed"] = elapsed
	next["hold_left"] = float(duck["hold_left"]) - dt
	match state:
		DUCK_DOWN:
			var down_progress := clampf(elapsed / DUCK_FADE_DOWN_SECONDS, 0.0, 1.0)
			next["volume"] = lerpf(float(duck["from"]), float(duck["to"]), down_progress)
			if down_progress >= 1.0:
				next["state"] = DUCK_HELD
				next["volume"] = float(duck["to"])
		DUCK_HELD:
			next["volume"] = float(duck["to"])
			if float(next["hold_left"]) <= 0.0:
				next["state"] = DUCK_UP
				next["from"] = float(duck["to"])
				next["elapsed"] = 0.0
		DUCK_UP:
			var up_progress := clampf(elapsed / DUCK_FADE_UP_SECONDS, 0.0, 1.0)
			next["volume"] = lerpf(float(duck["from"]), MUSIC_VOLUME, up_progress)
			if up_progress >= 1.0:
				return duck_idle()
	return next


static func music_gain(duck: Dictionary, fade: Dictionary) -> float:
	return MUSIC_VOLUME * float(duck.get("volume", MUSIC_VOLUME)) * fade_gain(fade)


static func gain_to_db(gain: float) -> float:
	if gain <= 0.0001:
		return SILENT_DB
	return maxf(linear_to_db(gain), SILENT_DB)


static func _hit_results_effects(hit_results: Array) -> Array[String]:
	var dodged := false
	var damaged := false
	var critical := false
	for hit_variant in hit_results:
		if not hit_variant is Dictionary:
			continue
		var hit: Dictionary = hit_variant
		var damage := int(hit.get("damage", 0))
		dodged = dodged or bool(hit.get("dodged", false))
		damaged = damaged or damage > 0
		critical = critical or (bool(hit.get("critical", false)) and damage > 0)
	var effects: Array[String] = []
	if dodged:
		effects.append("dodge")
	if damaged:
		effects.append("damage")
	if critical:
		effects.append("critical_hit")
	return effects


static func _string_array(values: Variant) -> Array[String]:
	var result: Array[String] = []
	if values is Array:
		for value in values:
			result.append(str(value))
	return result
