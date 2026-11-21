extends RefCounted

# Комментатор боя Калоды: порт строк deck/scenes/duel_commentator.py:add_combat_comments. Одна строка на розыгрыш,
# как в Python: обмены хода идут подряд через пробел. Строка — массив сегментов {text, color}.
# Вход — last_exchange снимка (deck/server/battles.py) и имена бойцов; исходов боя здесь нет.
# Фразы ENEMY_*_PHRASES и PLAYER_*_PHRASES из duel_commentator.py Python не вызывает, поэтому они не портированы.

const VISUAL := preload("res://scripts/deck_battle_visual_state.gd")

const DEFAULT_COLOR := Color8(230, 230, 230)  # duel_commentator.py: DEFAULT_COLOR
const CRIT_COLOR := Color8(255, 40, 40)  # duel_commentator.py: CRIT_COLOR
const DODGE_COLOR := Color8(150, 220, 255)  # duel_commentator.py: DODGE_COLOR
const START_TEXT := "Бой начался."  # duel_scene.py: start_battle_comments
const DAMAGE_MARKER := "(-"


# Журнал боя: battle_id, ключ последнего розыгрыша (VISUAL.exchange_key) и строки. Ключ тот же, что у показа
# розыгрыша в deck_battle_effects.gd, поэтому каждый розыгрыш попадает в журнал один раз, даже при опросе.
static func next_log(previous: Dictionary, state: Dictionary) -> Dictionary:
	var battle_id := str(state.get("battle_id", ""))
	if battle_id.is_empty():
		return previous
	var log: Dictionary = {}
	if str(previous.get("battle_id", "")) == battle_id:
		log = previous.duplicate(true)
	else:
		log = {"battle_id": battle_id, "key": "", "lines": [start_line()]}
	var key := VISUAL.exchange_key(state)
	if not key.is_empty() and key != str(log["key"]):
		var fighter := _dict_of(state.get("fighter", {}))
		var opponent := _dict_of(state.get("opponent", {}))
		var lines: Array = log["lines"]
		lines.append(exchange_line(VISUAL.exchange_of(state), str(state.get("side", "player")), str(fighter.get("name", "")), str(opponent.get("name", ""))))
		log["key"] = key
	return log


static func start_line() -> Array:
	return [_segment(START_TEXT, DEFAULT_COLOR)]


# exchange — last_exchange снимка. viewer_side — сторона зрителя ("player" или "enemy"): в событиях сторона
# абсолютная, поэтому «игрок» в тексте — боец зрителя, а не всегда сторона player.
static func exchange_line(exchange: Array, viewer_side: String, viewer_name: String, opponent_name: String) -> Array:
	var segments: Array = []
	for event_variant in exchange:
		if not event_variant is Dictionary:
			continue
		if not segments.is_empty():
			segments.append(_segment(" ", DEFAULT_COLOR))
		var event: Dictionary = event_variant
		var own := str(event.get("side", "")) == viewer_side
		var actor := viewer_name if own else opponent_name
		var target := opponent_name if own else viewer_name
		var card := str(event.get("card", ""))
		var damage := _int_of(event.get("damage", 0))
		var healed := _int_of(event.get("healed", 0))
		var text := "%s применил %s" % [actor, card]
		var color := DEFAULT_COLOR
		if bool(event.get("skipped", false)):
			text = "%s не предпринимает попыток в этот ход" % actor
		elif damage != 0:
			text = "%s применил %s. %s потерял здоровье (-%d хп)" % [actor, card, target, damage]
			color = CRIT_COLOR if bool(event.get("critical", false)) else DEFAULT_COLOR
		elif bool(event.get("dodged", false)):
			text = "%s применил %s, но %s избежал удара (-0 хп)" % [actor, card, target]
			color = DODGE_COLOR
		elif healed != 0:
			text = "%s применил %s и восстановил %d хп" % [actor, card, healed]
		segments.append_array(_split_marker(text, color))
	return segments


static func line_text(line: Array) -> String:
	var text := ""
	for segment_variant in line:
		text += str(_dict_of(segment_variant).get("text", ""))
	return text


# Текст строки для RichTextLabel: цвет сегмента и экранирование «[» (BBCode).
static func line_bbcode(line: Array) -> String:
	var bbcode := ""
	for segment_variant in line:
		var segment := _dict_of(segment_variant)
		var color: Color = segment.get("color", DEFAULT_COLOR)
		var text := str(segment.get("text", "")).replace("[", "[lb]")
		bbcode += "[color=#%s]%s[/color]" % [color.to_html(false), text]
	return bbcode


# Как duel_commentator.py: часть от последнего «(-» (урон или 0 при уклонении) окрашивается цветом исхода.
static func _split_marker(text: String, color: Color) -> Array:
	var at := text.rfind(DAMAGE_MARKER)
	if at < 0:
		return [_segment(text, DEFAULT_COLOR)]
	return [_segment(text.substr(0, at), DEFAULT_COLOR), _segment(text.substr(at), color)]


static func _segment(text: String, color: Color) -> Dictionary:
	return {"text": text, "color": color}


static func _dict_of(value: Variant) -> Dictionary:
	if value is Dictionary:
		return value
	return {}


static func _int_of(value: Variant) -> int:
	if value is int or value is float:
		return int(value)
	if value is String and (value as String).is_valid_int():
		return int(value)
	return 0
