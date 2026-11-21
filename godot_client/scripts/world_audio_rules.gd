extends RefCounted

# Звук Башни и Экономики, как ui/music.py, ui/sfx.py и ui/scene_transition.py: таверна, бег, удар, рывок и вихрь.
# Линейное затухание и громкость в дБ берём из deck_audio_rules.gd, чтобы не дублировать математику.
const FADE_RULES := preload("res://scripts/deck_audio_rules.gd")

# Та же длительность, что DURATION в scene_transition.gd и TRANSITION_SECONDS в ui/scene_transition.py.
const TRANSITION_FADE_SECONDS := 1.0 / 1.3 / 1.5
const MUSIC_VOLUME := 1.0
const EFFECT_VOLUME := 1.0
const TAVERN_FILES := [
	"sound/music/tavern_theme_1.mp3",
	"sound/music/tavern_theme_2.mp3",
	"sound/music/tavern_theme_3.mp3",
	"sound/music/tavern_theme_4.mp3",
]
const SWORD_SWING_FILES := [
	"sound/effects/sword_swing_1.mp3",
	"sound/effects/sword_swing_2.mp3",
	"sound/effects/sword_swing_3.mp3",
]
const CLUB_SWING_FILES := ["sound/effects/club_swing.mp3"]
const KNIFE_SWING_FILES := ["sound/effects/knife_swing_1.mp3", "sound/effects/knife_swing_2.mp3"]
const RUN_FILE := "sound/effects/run_grass.mp3"
const DASH_FILE := "sound/effects/dash_slice.mp3"
const WHIRL_FILE := "sound/effects/dash_whirl_strike.mp3"


static func tavern_files() -> Array[String]:
	return _strings(TAVERN_FILES)


# Набор замаха по названию оружия, как swing_sounds_for_weapon() в ui/sfx.py: меч, дубина или молот, нож или кинжал.
static func swing_files_for_weapon(weapon: Variant) -> Array[String]:
	var name := ""
	if weapon is Dictionary:
		name = str((weapon as Dictionary).get("name", "")).to_lower()
	if name.contains("меч"):
		return _strings(SWORD_SWING_FILES)
	if name.contains("дубин") or name.contains("молот"):
		return _strings(CLUB_SWING_FILES)
	if name.contains("нож") or name.contains("кинжал"):
		return _strings(KNIFE_SWING_FILES)
	return _strings([])


static func _strings(values: Array) -> Array[String]:
	var result: Array[String] = []
	for value in values:
		result.append(str(value))
	return result
