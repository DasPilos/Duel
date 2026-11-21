extends Node

# Комментатор боя: строки обмена из last_exchange как в duel_commentator.py (текст, цвета исходов), перспектива
# зрителя по стороне и журнал розыгрышей: каждый розыгрыш один раз, старт боя один раз, новый бой сбрасывает журнал.
const RULES := preload("res://scripts/deck_battle_commentator_rules.gd")

const PLAYER_NAME := "Забияка"
const ENEMY_NAME := "Безпроводной Душ"
const DEFAULT := Color8(230, 230, 230)
const CRIT := Color8(255, 40, 40)
const DODGE := Color8(150, 220, 255)
const SAMPLE := [
	{"side": "player", "card": "Прямой удар", "damage": 21, "dodged": false, "critical": true, "healed": 0},
	{"side": "enemy", "card": "Блок", "damage": 0, "dodged": false, "critical": false, "healed": 0},
]
const SAMPLE_TEXT := "Забияка применил Прямой удар. Безпроводной Душ потерял здоровье (-21 хп) Безпроводной Душ применил Блок"

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_sample_exchange()
	_check_viewer_side()
	_check_skip_dodge_heal_plain()
	_check_bbcode()
	_check_log()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_battle_commentator_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_sample_exchange() -> void:
	var line := RULES.exchange_line(SAMPLE, "player", PLAYER_NAME, ENEMY_NAME)
	_check(RULES.line_text(line) == SAMPLE_TEXT, "обмен из теста Python: текст строки")
	_check(line.size() == 4, "строка из четырёх сегментов: фраза, маркер урона, пробел, фраза")
	var first: Dictionary = line[0]
	var marker: Dictionary = line[1]
	_check(first["text"] == "Забияка применил Прямой удар. Безпроводной Душ потерял здоровье " and first["color"] == DEFAULT, "фраза удара обычным цветом, без маркера")
	_check(marker["text"] == "(-21 хп)" and marker["color"] == CRIT, "маркер критического урона красным")
	_check((line[3] as Dictionary)["color"] == DEFAULT, "фраза соперника обычным цветом")


# Событие несёт абсолютную сторону боя: имя «зрителя» берётся по его стороне, а не по стороне player.
func _check_viewer_side() -> void:
	var line := RULES.exchange_line(SAMPLE, "enemy", ENEMY_NAME, PLAYER_NAME)
	_check(RULES.line_text(line) == SAMPLE_TEXT, "зритель на стороне enemy: та же строка по именам")
	var mirrored := RULES.exchange_line([{"side": "enemy", "card": "Блок", "damage": 0, "dodged": false, "healed": 0}], "enemy", ENEMY_NAME, PLAYER_NAME)
	_check(RULES.line_text(mirrored) == "Безпроводной Душ применил Блок", "собственное действие зрителя называет его имя")


func _check_skip_dodge_heal_plain() -> void:
	var skipped := RULES.exchange_line([{"side": "enemy", "card": null, "skipped": true}], "player", PLAYER_NAME, ENEMY_NAME)
	_check(RULES.line_text(skipped) == "Безпроводной Душ не предпринимает попыток в этот ход", "пропуск хода: строка без карты")
	var dodged := RULES.exchange_line([{"side": "player", "card": "Вспышка", "damage": 0, "dodged": true, "healed": 0}], "player", PLAYER_NAME, ENEMY_NAME)
	_check(RULES.line_text(dodged) == "Забияка применил Вспышка, но Безпроводной Душ избежал удара (-0 хп)", "уворот: текст как в Python")
	_check((dodged[1] as Dictionary)["color"] == DODGE, "уворот окрашен голубым")
	var healed := RULES.exchange_line([{"side": "enemy", "card": "Исцеление", "damage": 0, "healed": 3, "dodged": false}], "player", PLAYER_NAME, ENEMY_NAME)
	_check(RULES.line_text(healed) == "Безпроводной Душ применил Исцеление и восстановил 3 хп", "лечение: текст с числом хп")
	var plain := RULES.exchange_line([{"side": "player", "card": "Щит", "damage": 0, "healed": 0}], "player", PLAYER_NAME, ENEMY_NAME)
	_check(RULES.line_text(plain) == "Забияка применил Щит" and plain.size() == 1, "без урона и лечения: только действие")
	var from_json := RULES.exchange_line([{"side": "player", "card": "Удар", "damage": 7.0, "critical": false}], "player", PLAYER_NAME, ENEMY_NAME)
	_check(RULES.line_text(from_json).ends_with("(-7 хп)"), "урон из JSON (float) выводится целым")
	_check(RULES.exchange_line([], "player", PLAYER_NAME, ENEMY_NAME).is_empty(), "пустой обмен: пустая строка")


func _check_bbcode() -> void:
	var line := [{"text": "a [b]", "color": CRIT}, {"text": " ", "color": DEFAULT}]
	_check(RULES.line_bbcode(line) == "[color=#ff2828]a [lb]b][/color][color=#e6e6e6] [/color]", "BBCode: цвет по сегментам и экранирование «[»")
	_check(RULES.line_bbcode(RULES.start_line()) == "[color=#e6e6e6]Бой начался.[/color]", "строка старта серым цветом")


func _check_log() -> void:
	var waiting := _state("b1", 0, [], "player")
	var log: Dictionary = RULES.next_log({}, waiting)
	_check(_texts(log) == [RULES.START_TEXT], "новый бой: только строка старта")
	_check(_texts(RULES.next_log(log, waiting)) == [RULES.START_TEXT], "опрос без розыгрыша ничего не добавляет")
	var resolved := _state("b1", 1, SAMPLE, "player")
	log = RULES.next_log(log, resolved)
	_check(_texts(log) == [RULES.START_TEXT, SAMPLE_TEXT], "розыгрыш добавляет одну строку")
	log = RULES.next_log(log, resolved)
	_check(_texts(log).size() == 2, "повторный снимок того же розыгрыша строку не добавляет")
	log = RULES.next_log(log, _state("b1", 2, SAMPLE, "player"))
	_check(_texts(log).size() == 3, "тот же обмен в следующем ходу — новая строка")
	_check(_texts(RULES.next_log(log, _state("b2", 3, [], "player"))) == [RULES.START_TEXT], "новый бой сбрасывает журнал")
	_check(_texts(RULES.next_log({}, resolved)) == [RULES.START_TEXT, SAMPLE_TEXT], "первый снимок боя с обменом показывает его последним")
	_check(RULES.next_log(log, {}) == log, "снимок без battle_id журнал не меняет")


func _state(battle_id: String, turn: int, exchange: Array, side: String) -> Dictionary:
	return {
		"battle_id": battle_id,
		"turn": turn,
		"side": side,
		"fighter": {"name": PLAYER_NAME},
		"opponent": {"name": ENEMY_NAME},
		"last_exchange": exchange,
	}


func _texts(log: Dictionary) -> Array:
	var texts: Array = []
	for line in log.get("lines", []):
		texts.append(RULES.line_text(line))
	return texts


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)
