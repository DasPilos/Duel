extends Node

# Клавиша I в мире Колоды (deck/scenes/world_flow.py: handle_event): какие экраны открывают карточку, что блокирует,
# и как открытый рюкзак принимает клавишу. Сетевых вызовов нет.
const RULES := preload("res://scripts/deck_profile_key_rules.gd")

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_profile_screens()
	_check_blockers()
	_check_backpack()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_profile_key_rules_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _check_profile_screens() -> void:
	_check(RULES.action_for("home", "world_map", false, true) == RULES.TOGGLE, "на карте мира I переключает карточку")
	_check(RULES.action_for("tavern", "tavern", false, true) == RULES.TOGGLE, "в таверне I переключает карточку")
	_check(RULES.action_for("character_room", "character_room", false, true) == RULES.TOGGLE, "в комнате I переключает карточку")


func _check_blockers() -> void:
	_check(RULES.action_for("home", "world_map", true, true) == RULES.NONE, "чат с фокусом ввода забирает I на карте")
	_check(RULES.action_for("tavern", "tavern", true, true) == RULES.NONE, "чат с фокусом ввода забирает I в таверне")
	_check(RULES.action_for("home", "world_map", false, false) == RULES.NONE, "без персонажа I ничего не открывает")
	_check(RULES.action_for("battle", "world_map", false, true) == RULES.NONE, "бой блокирует I, даже если бой начат на карте")
	_check(RULES.action_for("backyard", "backyard", false, true) == RULES.NONE, "задний двор не открывает карточку по I")
	_check(RULES.action_for("collection", "world_map", false, true) == RULES.NONE, "коллекция не открывает карточку по I")
	_check(RULES.action_for("decks", "tavern", false, true) == RULES.NONE, "колоды не открывают карточку по I")
	_check(RULES.action_for("shop", "world_map", false, true) == RULES.NONE, "лавка карт не открывает карточку по I")
	_check(RULES.action_for("home", "backyard", false, true) == RULES.NONE, "вид карты с локацией заднего двора не принимает I")


func _check_backpack() -> void:
	_check(RULES.action_for("inventory", "world_map", false, true) == RULES.CLOSE_BACKPACK, "открытый рюкзак закрывается клавишей I")
	_check(RULES.action_for("inventory", "character_room", false, true) == RULES.CLOSE_BACKPACK, "рюкзак из комнаты закрывается клавишей I")
	_check(RULES.action_for("inventory", "tavern", true, true) == RULES.CLOSE_BACKPACK, "рюкзак закрывается I даже при фокусе ввода, как в Python")
	_check(RULES.action_for("inventory", "tavern", false, false) == RULES.CLOSE_BACKPACK, "рюкзак закрывается I без персонажа, как в Python")
