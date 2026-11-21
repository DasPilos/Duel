extends RefCounted

# Чистая логика визуала боя Калоды: ключ розыгрыша, план шагов, модели показа и всплывающие числа.
# Без сцены и таймеров; шаги проигрывает deck_battle_effects.gd. Источники Python: deck/scenes/duel_scene.py
# (порядок фаз и тайминги), deck/scenes/duel_resolver.py (тексты и цвета чисел), deck/ui/renderers/card_area.py
# (полёты карт и раздача). Снимок — словарь deck/server/battles.py:snapshot.

const RULES := preload("res://scripts/deck_battle_layout_rules.gd")
const TRANSITION_SCRIPT := preload("res://scripts/deck_phase_transition.gd")

const KIND_CLASH := "clash"
const KIND_DAMAGE := "damage"
const KIND_SHUFFLE := "shuffle"
const KIND_PICK := "pick"
const KIND_ENEMY_PICK := "enemy_pick"
const KIND_INTRO := "intro"
const KIND_REVEAL := "reveal"
const KIND_SHOW := "show"
const PICK_ACTIONS := ["pick_starting", "pick_redraft"]


# Ключ последнего розыгрыша: бой, номер хода и сами события last_exchange. Фаза в ключ не входит: она меняется
# внутри одного розыгрыша (planning → draw → planning), и обмен проигрался бы снова. Длина history тоже не
# подходит: сервер отдаёт последние 12 записей, а сожжение карты добавляет запись без обмена.
static func exchange_key(state: Dictionary) -> String:
	var exchange: Variant = state.get("last_exchange", [])
	if not exchange is Array or (exchange as Array).is_empty():
		return ""
	return "%s|%s|%s" % [str(state.get("battle_id", "")), str(state.get("turn", 0)), JSON.stringify(exchange)]


# Полная запись снимка: одинаковый опрос даёт одинаковую запись и ничего не ставит в очередь.
static func signature(state: Dictionary) -> String:
	return JSON.stringify(state)


static func transition_kind(previous_phase: String, next_phase: String) -> String:
	return TRANSITION_SCRIPT.transition_kind(previous_phase, next_phase)


static func is_starting_draft(state: Dictionary) -> bool:
	return str(state.get("phase", "")) == "draft" and str(state.get("draft_mode", "")) == "starting"


# Шаги от показанного состояния prev до нового снимка latest.
# context: new_exchange — ключ розыгрыша ещё не проигрывался; action и card_key — ход игрока из запроса;
# allow_transition — false для опроса, как в прежнем коде (переходы только после ответа на действие).
# Шаг: kind, duration (сек), display (что показать в начале шага), transition (только у show).
static func plan(prev: Dictionary, latest: Dictionary, context: Dictionary, project_dir: String) -> Array[Dictionary]:
	var steps: Array[Dictionary] = []
	var prev_phase := str(prev.get("phase", ""))
	var next_phase := str(latest.get("phase", ""))
	var transition := ""
	if bool(context.get("allow_transition", true)):
		transition = transition_kind(prev_phase, next_phase)
	if not transition.is_empty():
		# Переход фазы закрывает поле затемнением: шаги старой фазы не проигрываются, переход идёт сразу, как раньше.
		steps.append(_show(latest, transition))
		return steps
	var exchange := exchange_of(latest)
	if not prev.is_empty() and bool(context.get("new_exchange", false)) and prev_phase != "draft" and not exchange.is_empty():
		var after := exchange_display(prev, latest)
		steps.append(_step(KIND_CLASH, RULES.ATTACK_ANIMATION_SECONDS, clash_display(prev)))
		steps.append(_step(KIND_DAMAGE, RULES.DAMAGE_ANIMATION_SECONDS, after, {"exchange": exchange}))
		if next_phase != "result":
			steps.append(_step(KIND_SHUFFLE, RULES.DECK_SHUFFLE_SECONDS, after))
		steps.append(_show(latest, ""))
		return steps
	if not prev.is_empty() and prev_phase == "draft":
		_plan_draft_picks(prev, latest, context, project_dir, steps)
	steps.append(_show(latest, ""))
	return steps


# Старт стартового драфта: интро (стол пуст), раздача карт из колоды по задержкам Python, затем драфт.
static func plan_battle_start(latest: Dictionary, project_dir: String) -> Array[Dictionary]:
	var pre := pre_draft_display(latest)
	var steps: Array[Dictionary] = []
	steps.append(_step(KIND_INTRO, RULES.DRAFT_INTRO_SECONDS, pre))
	steps.append(_step(KIND_REVEAL, reveal_duration(_array_of(latest.get("table", [])).size()), pre, {
		"flights": reveal_flights(latest, project_dir),
	}))
	steps.append(_show(latest, ""))
	return steps


# duel_scene.py: reveal_duration = задержка старта + задержка последней карты + CARD_MOVE_SECONDS + 0.05.
static func reveal_duration(table_count: int) -> float:
	var last_card_delay := maxi(0, table_count - 1) * RULES.DRAFT_CARD_DELAY_SECONDS
	return RULES.DRAFT_REVEAL_START_DELAY_SECONDS + last_card_delay + RULES.CARD_MOVE_SECONDS + RULES.DRAFT_REVEAL_TAIL_SECONDS


# card_area.py:_draw_reveal_cards: карта i стартует через DRAFT_REVEAL_START_DELAY + i * DRAFT_CARD_DELAY,
# летит из колоды в слот за CARD_MOVE_SECONDS с переворотом.
static func reveal_flights(state: Dictionary, project_dir: String) -> Array[Dictionary]:
	var flights: Array[Dictionary] = []
	var mode := str(state.get("draft_mode", ""))
	var table := _array_of(state.get("table", []))
	var unique := _unique_type(state)
	var layout := RULES.layout_for_state(state)
	var deck_center := (layout["deck"] as Rect2).get_center()
	for index in range(table.size()):
		var slot := RULES.draft_slot_rect(mode, index, layout["card_table"])
		flights.append({
			"entry": RULES.card_entry(RULES.ZONE_TABLE, index, _dict_of(table[index]), slot, {}, project_dir, unique),
			"start": RULES.DRAFT_REVEAL_START_DELAY_SECONDS + index * RULES.DRAFT_CARD_DELAY_SECONDS,
			"duration": RULES.CARD_MOVE_SECONDS,
			"from": deck_center,
			"to": slot.get_center(),
			"from_size": RULES.CARD_SIZE,
			"to_size": slot.size,
			"flip": true,
		})
	return flights


static func pre_draft_display(state: Dictionary) -> Dictionary:
	var display := state.duplicate(true)
	display["table"] = []
	display["hand"] = []
	display["selected"] = []
	display["can_select"] = []
	display["draw_choices"] = []
	display["opponent_draft_picks"] = []
	display["opponent_last_draft_picks"] = []
	display["last_exchange"] = []
	return display


# Клэш (duel_scene.py: фаза clash): на поле только сыгранные карты, руки не рисуются и не подсвечиваются.
static func clash_display(prev: Dictionary) -> Dictionary:
	var display := prev.duplicate(true)
	display["hand"] = played_cards(prev)
	display["can_select"] = []
	display["confirmed"] = true
	return display


# Состояние на время удара (duel_scene.py: после resolve_turn). Карты стола остаются на поле, как в Python
# (selected из показанного снимка), а руки, HP и история уже новые. Сыгранные карты стоят первыми, чтобы выбор
# занял именно их, а не копии из новой руки.
static func exchange_display(prev: Dictionary, latest: Dictionary) -> Dictionary:
	var display := prev.duplicate(true)
	display["phase"] = "planning"
	display["hand"] = played_cards(prev) + _array_of(latest.get("hand", []))
	display["can_select"] = []
	display["confirmed"] = true
	display["draw_choices"] = []
	display["table"] = []
	display["draft_mode"] = ""
	display["turn"] = latest.get("turn", 0)
	display["fighter"] = latest.get("fighter", {})
	display["opponent"] = latest.get("opponent", {})
	display["last_exchange"] = latest.get("last_exchange", [])
	display["history"] = latest.get("history", [])
	display["opponent_draft_picks"] = []
	display["opponent_last_draft_picks"] = []
	return display


static func table_index_of(state: Dictionary, card_key: String) -> int:
	return _index_of_key(_array_of(state.get("table", [])), card_key, {})


# Карта игрока уходит из стола в руку (battle.choose_starting_card).
static func after_player_pick(state: Dictionary, card_key: String) -> Dictionary:
	var display := state.duplicate(true)
	var index := table_index_of(display, card_key)
	if index < 0:
		return display
	var table := _array_of(display.get("table", []))
	var card: Variant = table[index]
	table.remove_at(index)
	display["table"] = table
	var hand := _array_of(display.get("hand", []))
	hand.append(card)
	display["hand"] = hand
	return display


# Выбор соперника уходит из стола. Руку соперника снимок не отдаёт, поэтому на экране её нет.
static func after_enemy_pick(state: Dictionary, card_key: String) -> Dictionary:
	var display := state.duplicate(true)
	var index := table_index_of(display, card_key)
	if index < 0:
		return display
	var table := _array_of(display.get("table", []))
	table.remove_at(index)
	display["table"] = table
	return display


# Выборы соперника, которых не было в показанном снимке; копии одной карты считаются отдельно.
static func new_enemy_picks(prev: Dictionary, latest: Dictionary) -> Array[String]:
	var unmatched := {}
	for key in _string_array(prev.get("opponent_draft_picks", [])):
		unmatched[key] = int(unmatched.get(key, 0)) + 1
	var fresh: Array[String] = []
	for key in _string_array(latest.get("opponent_draft_picks", [])):
		var count := int(unmatched.get(key, 0))
		if count > 0:
			unmatched[key] = count - 1
		else:
			fresh.append(key)
	return fresh


# Центр панели характеристик стороны: duel_renderer.py:_floating_text_x (panel_x + panel_width // 2).
static func panel_center_x(side: String, layout: Dictionary = RULES.STANDARD_LAYOUT) -> float:
	var rect := RULES.stats_panel_rect(side, RULES.MAX_HAND_SIZE, layout)
	return floorf(rect.position.x + floorf(rect.size.x / 2.0))


# duel_resolver.py:_floating_text_panel_top — верх панели характеристик минус отступ.
static func panel_top() -> float:
	return RULES.stats_panel_rect("player").position.y - RULES.FLOATING_TEXT_PANEL_GAP


# Порт duel_resolver.py:_add_floating_damage и _add_floating_effect/_bonus/_heal. alive — уже висящие
# числа {x, y, remaining}. Возвращает подписи в порядке создания: {kind, text, color, x, y, font_size, asset};
# x, y — центр подписи, как в Python (FloatingText рисуется по центру).
static func floating_specs(exchange: Array, alive: Array, layout: Dictionary = RULES.STANDARD_LAYOUT) -> Array[Dictionary]:
	var occupied: Array = []
	for item_variant in alive:
		var item := _dict_of(item_variant)
		if float(item.get("remaining", 0.0)) > 0.0:
			occupied.append({"x": float(item.get("x", 0.0)), "y": float(item.get("y", 0.0))})
	# next_y: высота следующей строки по стороне; x — центры колонок панелей выбранного макета (мага они другие).
	var next_y := {
		"player": panel_top(),
		"enemy": panel_top(),
		"x": {"player": panel_center_x("player", layout), "enemy": panel_center_x("enemy", layout)},
	}
	var specs: Array[Dictionary] = []
	for event_variant in exchange:
		if not event_variant is Dictionary:
			continue
		var event: Dictionary = event_variant
		var side := str(event.get("side", ""))
		var target := "enemy" if side == "player" else "player"
		for card_name in _string_array(event.get("effect_cards", [])):
			_add(specs, occupied, next_y, side, "text", card_name, RULES.EFFECT_TEXT_COLOR, RULES.FLOATING_TEXT_FONT_SIZE, "")
		if not str(event.get("effect_text", "")).is_empty():
			_add(specs, occupied, next_y, side, "text", str(event["effect_text"]), RULES.EFFECT_TEXT_COLOR, RULES.FLOATING_TEXT_FONT_SIZE, "")
		if int(event.get("dodge_bonus", 0)) > 0:
			_add(specs, occupied, next_y, side, "text", "+%d%%" % int(event["dodge_bonus"]), RULES.DODGE_COLOR, RULES.FLOATING_TEXT_FONT_SIZE, "")
		if int(event.get("healed", 0)) > 0:
			_add(specs, occupied, next_y, side, "text", "+%d HP" % int(event["healed"]), RULES.HEAL_TEXT_COLOR, RULES.FLOATING_TEXT_FONT_SIZE, "")
		var hit_results: Variant = event.get("hit_results", null)
		if hit_results is Array and not (hit_results as Array).is_empty():
			for hit_variant in hit_results:
				var hit := _dict_of(hit_variant)
				if bool(hit.get("dodged", false)):
					_add(specs, occupied, next_y, target, "text", "УВОРОТ", RULES.DODGE_COLOR, RULES.FLOATING_TEXT_FONT_SIZE, "")
				elif bool(hit.get("blocked", false)):
					_add(specs, occupied, next_y, target, "text", "БЛОК", RULES.DODGE_COLOR, RULES.FLOATING_CRITICAL_FONT_SIZE, "")
				else:
					_add_damage(specs, occupied, next_y, target, int(hit.get("damage", 0)), false, bool(hit.get("critical", false)))
			continue
		if bool(event.get("attack_dodged", false)):
			_add(specs, occupied, next_y, target, "image", "HP-0", RULES.DODGE_COLOR, RULES.FLOATING_CRITICAL_FONT_SIZE, RULES.DODGED_RESULT_ASSET)
		var damage := int(event.get("damage", 0))
		var critical_attack := bool(event.get("critical_attack", false))
		if damage <= 0 and not critical_attack:
			continue
		if critical_attack:
			_add(specs, occupied, next_y, target, "image", "HP-%d" % damage, RULES.DAMAGE_COLOR, RULES.FLOATING_CRITICAL_FONT_SIZE, RULES.DAMAGE_RESULT_ASSET)
		else:
			_add_damage(specs, occupied, next_y, target, damage, bool(event.get("dodged", false)), bool(event.get("critical", false)))
	return specs


# Положение и поворот карты в полёте (card_area.py:_draw_moving_card). progress — 0..1. При flip ширина
# сжимается, и первую половину полёта видна рубашка. Возвращает {rect, back}.
static func flight_frame(from_center: Vector2, to_center: Vector2, from_size: Vector2, to_size: Vector2, progress: float, flip: bool) -> Dictionary:
	var p := clampf(progress, 0.0, 1.0)
	var center := Vector2(
		float(int(from_center.x + (to_center.x - from_center.x) * p)),
		float(int(from_center.y + (to_center.y - from_center.y) * p)),
	)
	var width := roundf(from_size.x + (to_size.x - from_size.x) * p)
	var height := roundf(from_size.y + (to_size.y - from_size.y) * p)
	if flip:
		width = maxf(2.0, float(int(width * absf(2.0 * p - 1.0))))
	var rect := Rect2(center - Vector2(width, height) / 2.0, Vector2(width, height))
	return {"rect": rect, "back": flip and p < 0.5}


static func exchange_of(state: Dictionary) -> Array:
	return _array_of(state.get("last_exchange", []))


# Сыгранные карты: первая копия каждого ключа выбора из руки, в порядке выбора.
static func played_cards(prev: Dictionary) -> Array:
	var prev_hand := _array_of(prev.get("hand", []))
	var played: Array = []
	var used := {}
	for key in _string_array(prev.get("selected", [])):
		var found := _index_of_key(prev_hand, key, used)
		if found >= 0:
			used[found] = true
			played.append(prev_hand[found])
	return played


static func _plan_draft_picks(prev: Dictionary, latest: Dictionary, context: Dictionary, project_dir: String, steps: Array[Dictionary]) -> void:
	var current := prev
	var unique := _unique_type(prev)
	var action := str(context.get("action", ""))
	var card_key := str(context.get("card_key", ""))
	if PICK_ACTIONS.has(action):
		var index := table_index_of(current, card_key)
		if index >= 0:
			var card := _dict_of(_array_of(current.get("table", []))[index])
			var after := after_player_pick(current, card_key)
			steps.append(_step(KIND_PICK, RULES.PLAYER_DRAFT_PICK_MOVE_SECONDS, after, {
				"entry": RULES.card_entry(RULES.ZONE_TABLE, index, card, Rect2(Vector2.ZERO, RULES.CARD_SIZE), {}, project_dir, unique),
				"source_index": index,
				"hand_count": _array_of(after.get("hand", [])).size(),
			}))
			current = after
	var enemy_count := _array_of(prev.get("opponent_draft_picks", [])).size()
	for key in new_enemy_picks(prev, latest):
		var index := table_index_of(current, key)
		if index < 0:
			continue
		enemy_count += 1
		var card := _dict_of(_array_of(current.get("table", []))[index])
		var after := after_enemy_pick(current, key)
		steps.append(_step(KIND_ENEMY_PICK, RULES.TABLE_TO_HAND_MOVE_SECONDS, after, {
			"entry": RULES.card_entry(RULES.ZONE_TABLE, index, card, Rect2(Vector2.ZERO, RULES.CARD_SIZE), {}, project_dir, unique),
			"source_index": index,
			"enemy_count": enemy_count,
		}))
		current = after


static func _unique_type(state: Dictionary) -> String:
	return str(_dict_of(state.get("fighter", {})).get("unique_resource_type", ""))


static func _step(kind: String, duration: float, display: Dictionary, extra: Dictionary = {}) -> Dictionary:
	var step := {"kind": kind, "duration": duration, "display": display.duplicate(true), "transition": ""}
	step.merge(extra)
	return step


static func _show(latest: Dictionary, transition: String) -> Dictionary:
	return {"kind": KIND_SHOW, "duration": 0.0, "display": latest.duplicate(true), "transition": transition}


static func _add_damage(specs: Array[Dictionary], occupied: Array, next_y: Dictionary, side: String, damage: int, dodged: bool, critical: bool) -> void:
	if dodged:
		_add(specs, occupied, next_y, side, "text", "УВОРОТ", RULES.DODGE_COLOR, RULES.FLOATING_TEXT_FONT_SIZE, "")
		return
	var color := RULES.DAMAGE_COLOR if critical else RULES.TEXT_COLOR
	_add(specs, occupied, next_y, side, "text", "-%d HP" % damage, color, RULES.FLOATING_TEXT_FONT_SIZE, "")


# Одна подпись: положение по колонке стороны и занятости (stack_line), затем запись в занятые места.
static func _add(specs: Array[Dictionary], occupied: Array, next_y: Dictionary, side: String, kind: String, text: String, color: Color, font_size: int, asset: String) -> void:
	var x := float((next_y["x"] as Dictionary)[side])
	var y := _stack_line(x, side, next_y, occupied)
	specs.append({"kind": kind, "text": text, "color": color, "x": x, "y": y, "font_size": font_size, "asset": asset})
	occupied.append({"x": x, "y": y})


# duel_resolver.py:stack_line. Строка сдвигается вверх, пока в той же колонке есть занятая высота; затем
# следующая строка этой стороны встаёт выше.
static func _stack_line(x: float, side: String, next_y: Dictionary, occupied: Array) -> float:
	var y := float(next_y[side])
	while _is_taken(occupied, x, y):
		y -= RULES.FLOATING_TEXT_LINE_HEIGHT
	next_y[side] = minf(float(next_y[side]) - RULES.FLOATING_TEXT_LINE_HEIGHT, y - RULES.FLOATING_TEXT_LINE_HEIGHT)
	return y


static func _is_taken(occupied: Array, x: float, y: float) -> bool:
	for item_variant in occupied:
		var item := _dict_of(item_variant)
		if float(item["x"]) == x and absf(float(item["y"]) - y) < RULES.FLOATING_TEXT_LINE_HEIGHT:
			return true
	return false


static func _index_of_key(cards: Array, key: String, used: Dictionary) -> int:
	for index in range(cards.size()):
		if not used.has(index) and str(_dict_of(cards[index]).get("key", "")) == key:
			return index
	return -1


static func _string_array(value: Variant) -> Array:
	var result: Array = []
	if value is Array:
		for item in value:
			result.append(str(item))
	return result


static func _array_of(value: Variant) -> Array:
	if value is Array:
		return value
	return []


static func _dict_of(value: Variant) -> Dictionary:
	if value is Dictionary:
		return value
	return {}
