extends Node

# Звук Башни и Экономики: правила (наборы замаха по оружию, длительность перехода) и наличие файлов в assets.
const RULES := preload("res://scripts/world_audio_rules.gd")
const FADE_RULES := preload("res://scripts/deck_audio_rules.gd")
const SCENE_TRANSITION := preload("res://scripts/scene_transition.gd")

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_swing_sets()
	_check_transition_duration()
	_check_files_exist()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("world_audio_rules_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _check_swing_sets() -> void:
	_check(str(RULES.swing_files_for_weapon({"name": "Железный меч"})) == str(RULES.SWORD_SWING_FILES), "меч берёт набор мечей")
	_check(str(RULES.swing_files_for_weapon({"name": "Стальной меч"})) == str(RULES.SWORD_SWING_FILES), "второй меч тоже берёт набор мечей")
	_check(str(RULES.swing_files_for_weapon({"name": "Дубина"})) == str(RULES.CLUB_SWING_FILES), "дубина берёт набор дубины")
	_check(str(RULES.swing_files_for_weapon({"name": "Боевой молот"})) == str(RULES.CLUB_SWING_FILES), "молот берёт набор дубины")
	_check(str(RULES.swing_files_for_weapon({"name": "Кинжал"})) == str(RULES.KNIFE_SWING_FILES), "кинжал берёт набор ножей")
	_check(str(RULES.swing_files_for_weapon({"name": "Стальной нож"})) == str(RULES.KNIFE_SWING_FILES), "нож берёт набор ножей")
	_check(str(RULES.swing_files_for_weapon({"name": "ДУБИНА"})) == str(RULES.CLUB_SWING_FILES), "название оружия сравнивается без учёта регистра")
	_check(RULES.swing_files_for_weapon({"name": "Простой лук"}).is_empty(), "лук без набора звуков беззвучен")
	_check(RULES.swing_files_for_weapon({}).is_empty(), "оружие без названия беззвучно")
	_check(RULES.swing_files_for_weapon(null).is_empty(), "без оружия удар беззвучен")
	_check(RULES.swing_files_for_weapon("меч").is_empty(), "строка вместо оружия не даёт звука")


func _check_transition_duration() -> void:
	_check(is_equal_approx(RULES.TRANSITION_FADE_SECONDS, SCENE_TRANSITION.DURATION), "затухание совпадает с длительностью перехода")
	_check(is_equal_approx(FADE_RULES.gain_to_db(1.0), 0.0), "полная громкость даёт 0 дБ")
	_check(FADE_RULES.gain_to_db(0.0) == FADE_RULES.SILENT_DB, "нулевая громкость даёт тишину")


func _check_files_exist() -> void:
	var root := FADE_RULES.default_assets_root(ProjectSettings.globalize_path("res://"))
	var files: Array = []
	files.append_array(RULES.tavern_files())
	files.append_array(RULES.SWORD_SWING_FILES)
	files.append_array(RULES.CLUB_SWING_FILES)
	files.append_array(RULES.KNIFE_SWING_FILES)
	files.append_array([RULES.RUN_FILE, RULES.DASH_FILE, RULES.WHIRL_FILE])
	for file in files:
		_check(FileAccess.file_exists(FADE_RULES.resolve_path(root, str(file))), "файл звука есть: %s" % str(file))
