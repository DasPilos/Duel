extends Node

# Музыка комнаты и переходов Колоды (deck/scenes/character_room.py, deck/ui/music.py, ui/scene_transition.py):
# правила смены экрана и длительность затухания. Сетевых вызовов нет.
const RULES := preload("res://scripts/deck_audio_rules.gd")
const WORLD_RULES := preload("res://scripts/world_audio_rules.gd")

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_close_and_init()
	_check_changes()
	_check_transition_time()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_room_music_rules_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _check_close_and_init() -> void:
	_check(RULES.location_close_music("tavern") == RULES.LOCATION_STOP, "уход из таверны останавливает музыку")
	_check(RULES.location_close_music("character_room") == RULES.LOCATION_TAVERN_ONCE, "уход из комнаты запускает трек таверны без повтора")
	_check(RULES.location_close_music("world_map") == RULES.LOCATION_NONE, "уход с карты ничего не меняет")
	_check(RULES.location_close_music("backyard") == RULES.LOCATION_NONE, "уход с заднего двора ничего не меняет")
	_check(RULES.location_init_music("tavern") == RULES.LOCATION_TAVERN_REPEAT, "вход в таверну играет треки по кругу")
	_check(RULES.location_init_music("character_room") == RULES.LOCATION_STOP, "вход в комнату — тишина")
	_check(RULES.location_init_music("world_map") == RULES.LOCATION_NONE, "вход на карту ничего не меняет")
	_check(RULES.location_init_music("backyard") == RULES.LOCATION_NONE, "вход на задний двор ничего не меняет")


func _check_changes() -> void:
	_check(RULES.location_change_music("character_room", "tavern") == RULES.LOCATION_TAVERN_REPEAT, "из комнаты в таверну: таверна по кругу")
	_check(RULES.location_change_music("character_room", "world_map") == RULES.LOCATION_TAVERN_ONCE, "из комнаты на карту: один трек таверны")
	_check(RULES.location_change_music("character_room", "backyard") == RULES.LOCATION_TAVERN_ONCE, "из комнаты на задний двор: один трек таверны")
	_check(RULES.location_change_music("tavern", "character_room") == RULES.LOCATION_STOP, "из таверны в комнату: тишина")
	_check(RULES.location_change_music("tavern", "world_map") == RULES.LOCATION_STOP, "из таверны на карту: тишина")
	_check(RULES.location_change_music("tavern", "backyard") == RULES.LOCATION_STOP, "из таверны на задний двор: тишина")
	_check(RULES.location_change_music("world_map", "character_room") == RULES.LOCATION_STOP, "с карты в комнату: тишина")
	_check(RULES.location_change_music("world_map", "tavern") == RULES.LOCATION_TAVERN_REPEAT, "с карты в таверну: таверна по кругу")
	_check(RULES.location_change_music("backyard", "world_map") == RULES.LOCATION_NONE, "с заднего двора на карту: музыки нет")
	_check(RULES.location_change_music("", "character_room") == RULES.LOCATION_STOP, "первый вход в комнату — тишина")
	_check(RULES.location_change_music("", "tavern") == RULES.LOCATION_TAVERN_REPEAT, "первый вход в таверну играет таверну")


func _check_transition_time() -> void:
	_check(is_equal_approx(WORLD_RULES.TRANSITION_FADE_SECONDS, 1.0 / 1.3 / 1.5), "переход затухает 1/1.3/1.5 с, как ui/scene_transition.py")
