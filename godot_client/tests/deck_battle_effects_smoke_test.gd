extends Node

# Визуал боя Калоды: тайминги Python, однократный розыгрыш по ключу обмена, очередь шагов, всплывающие числа с
# теми же подписями, цветами и стеком, что в duel_resolver.py, полёты драфта, интро и раздача, блокировка ввода во
# время анимаций и проводка ответа боя через deck_world.gd (очередь, музыка и переход фазы работают как раньше).
# Времена в проверках берутся двоичными долями (0.25, 0.5), чтобы граница шага не зависела от округления.
const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const RULES := preload("res://scripts/deck_battle_layout_rules.gd")
const VISUAL := preload("res://scripts/deck_battle_visual_state.gd")
const VIEW_SCRIPT := preload("res://scripts/deck_battle_view.gd")
const CARD_VIEW_SCRIPT := preload("res://scripts/deck_battle_card_view.gd")
const EFFECTS_SCRIPT := preload("res://scripts/deck_battle_effects.gd")
const FIXTURE_DIR := "res://tests/fixtures/deck_battle/"
const WAIT_LIMIT_MS := 5000
# Звуки в этом тесте не нужны: без корня звуков файлы не грузятся и воспроизведение не стартует.
const MISSING_SOUND_ROOT := "__deck_battle_effects_missing_sound_root__"

var _failures: Array[String] = []
var _checks := 0
var _hosts: Array = []


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_constants()
	_check_floating_texts()
	_check_stacking_with_alive_texts()
	_check_flight_frames()
	_check_reveal_flights()
	_check_exchange_key()
	await _check_once_only()
	await _check_damage_timeline()
	await _check_result_transition_is_immediate()
	await _check_transition_drops_pending_steps()
	await _check_draft_intro_and_reveal()
	await _check_pick_flights()
	await _check_new_battle_clears_queue()
	await _check_lock_and_damage_display()
	await _check_world_wiring()
	for host in _hosts:
		(host["view"] as Node).queue_free()
	_hosts.clear()
	await get_tree().process_frame
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_battle_effects_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _check_constants() -> void:
	_check(RULES.ATTACK_ANIMATION_SECONDS == 0.5, "клэш 0.5 с (settings.py: ATTACK_ANIMATION_SECONDS)")
	_check(RULES.DAMAGE_ANIMATION_SECONDS == 1.0, "урон 1.0 с (settings.py: DAMAGE_ANIMATION_SECONDS)")
	_check(RULES.DECK_SHUFFLE_SECONDS == 2.0, "перетасовка 2.0 с (settings.py: DECK_SHUFFLE_SECONDS)")
	_check(RULES.DRAFT_CARD_DELAY_SECONDS == 0.03 and RULES.DRAFT_REVEAL_START_DELAY_SECONDS == 1.0, "раздача: задержка карты 0.03 с, старт 1.0 с")
	_check(RULES.CARD_MOVE_SECONDS == 1.0 and RULES.PLAYER_DRAFT_PICK_MOVE_SECONDS == 0.5 and RULES.TABLE_TO_HAND_MOVE_SECONDS == 0.5, "полёты: 1.0 с, выбор игрока 0.5 с, выбор соперника 0.5 с")
	_check(RULES.DRAFT_INTRO_SECONDS == 2.0, "интро 2.0 с: intro_table 1 с + intro_deck 1 с")
	_check(RULES.FLOATING_TEXT_SECONDS == 10.0, "всплывающие числа висят 10 с (FPS * 10)")
	_check(is_equal_approx(VISUAL.reveal_duration(20), 2.62), "reveal_duration(20) = 1.0 + 19 * 0.03 + 1.0 + 0.05")
	_check(VISUAL.panel_top() == 832.0, "числа над панелями: верх панели 850 минус 18")
	_check(VISUAL.panel_center_x("player") == 189.0 and VISUAL.panel_center_x("enemy") == 1730.0, "центры панелей характеристик 189 и 1730")
	_check(RULES.DAMAGE_COLOR == Color8(255, 60, 60) and RULES.DODGE_COLOR == Color8(150, 220, 255), "цвета урона (255,60,60) и уворота (150,220,255)")
	_check(RULES.HEAL_TEXT_COLOR == Color8(110, 235, 120) and RULES.EFFECT_TEXT_COLOR == Color8(255, 220, 120), "цвета лечения (110,235,120) и эффекта (255,220,120)")


# Ожидаемые подписи вычислены по duel_resolver.py вручную: стек идёт вверх по колонке стороны с шагом 30 px от 832.
func _check_floating_texts() -> void:
	var exchange: Array = [
		{"side": "player", "card": "Удар", "damage": 14, "healed": 3, "critical": true, "dodged": false, "attack": true, "critical_attack": true, "attack_dodged": false},
		{"side": "enemy", "card": "Вспышка", "damage": 0, "healed": 0, "critical": false, "dodged": true, "attack": true, "critical_attack": false, "attack_dodged": true},
		{"side": "player", "card": "Выпады", "damage": 0, "healed": 0, "critical": false, "dodged": false, "hits": 4, "hit_results": [
			{"damage": 4, "dodged": false, "blocked": false, "critical": false},
			{"damage": 0, "dodged": true, "blocked": false, "critical": false},
			{"damage": 0, "dodged": false, "blocked": true, "critical": false},
			{"damage": 9, "dodged": false, "blocked": false, "critical": true},
		]},
		{"side": "player", "card": "Щит", "damage": 0, "healed": 5, "critical": false, "dodged": false, "effect_cards": ["Щит"], "effect_text": "ОГЛУШЕНИЕ", "dodge_bonus": 10},
	]
	var specs := VISUAL.floating_specs(exchange, [])
	var lines: Array = []
	for spec in specs:
		lines.append("%s@%d,%d" % [str(spec["text"]), int(spec["x"]), int(spec["y"])])
	_check(lines == [
		"+3 HP@189,832",
		"HP-14@1730,832",
		"HP-0@189,802",
		"-4 HP@1730,802",
		"УВОРОТ@1730,772",
		"БЛОК@1730,742",
		"-9 HP@1730,712",
		"Щит@189,772",
		"ОГЛУШЕНИЕ@189,742",
		"+10%@189,712",
		"+5 HP@189,682",
	], "подписи и стек чисел совпадают с duel_resolver.py: %s" % str(lines))
	var colors: Array = []
	for spec in specs:
		colors.append(spec["color"])
	_check(colors == [
		RULES.HEAL_TEXT_COLOR, RULES.DAMAGE_COLOR, RULES.DODGE_COLOR, RULES.TEXT_COLOR, RULES.DODGE_COLOR, RULES.DODGE_COLOR,
		RULES.DAMAGE_COLOR, RULES.EFFECT_TEXT_COLOR, RULES.EFFECT_TEXT_COLOR, RULES.DODGE_COLOR, RULES.HEAL_TEXT_COLOR,
	], "цвета: лечение зелёное, крит красный, уворот голубой, обычный урон светлый, эффект жёлтый")
	_check(str(specs[1]["kind"]) == "image" and str(specs[1]["asset"]) == RULES.DAMAGE_RESULT_ASSET, "крит-атака: HP-N на картинке damage_result.png")
	_check(str(specs[2]["kind"]) == "image" and str(specs[2]["asset"]) == RULES.DODGED_RESULT_ASSET, "атака мимо: HP-0 на картинке dodged_result.png")
	_check(str(specs[5]["text"]) == "БЛОК" and int(specs[5]["font_size"]) == RULES.FLOATING_CRITICAL_FONT_SIZE, "БЛОК: шрифт critical (25), как FloatingText с critical_font")
	_check(int(specs[3]["font_size"]) == RULES.FLOATING_TEXT_FONT_SIZE and int(specs[1]["font_size"]) == RULES.FLOATING_CRITICAL_FONT_SIZE, "обычные числа 24 px, HP-N 25 px")


func _check_stacking_with_alive_texts() -> void:
	var heal: Array = [{"side": "player", "healed": 3}]
	var alive: Array = [
		{"x": 189.0, "y": 832.0, "remaining": 5.0},
		{"x": 189.0, "y": 802.0, "remaining": 0.0},
		{"x": 1730.0, "y": 832.0, "remaining": 5.0},
	]
	var specs := VISUAL.floating_specs(heal, alive)
	_check(specs.size() == 1 and is_equal_approx(float(specs[0]["y"]), 802.0), "занятая строка сдвигает число вверх, истёкшее (remaining 0) место свободно")


func _check_flight_frames() -> void:
	var from := Vector2(100, 100)
	var to := Vector2(300, 500)
	var size := Vector2(150, 200)
	var start := VISUAL.flight_frame(from, to, size, size, 0.0, false)
	_check((start["rect"] as Rect2).get_center().is_equal_approx(from) and not bool(start["back"]), "полёт в начале стоит в точке старта лицом")
	var end := VISUAL.flight_frame(from, to, size, size, 1.0, false)
	_check((end["rect"] as Rect2).get_center().is_equal_approx(to), "полёт в конце стоит в точке назначения")
	var middle := VISUAL.flight_frame(from, to, size, size, 0.5, false)
	_check((middle["rect"] as Rect2).get_center().is_equal_approx(Vector2(200, 300)), "линейная интерполяция центра (шаг выбора игрока и соперника)")
	var first_half := VISUAL.flight_frame(from, to, size, size, 0.25, true)
	_check(bool(first_half["back"]) and is_equal_approx((first_half["rect"] as Rect2).size.x, 75.0), "переворот: первая половина — рубашка, ширина 150 * |2p - 1|")
	var second_half := VISUAL.flight_frame(from, to, size, size, 0.75, true)
	_check(not bool(second_half["back"]) and is_equal_approx((second_half["rect"] as Rect2).size.x, 75.0), "переворот: вторая половина — лицо")
	var card = CARD_VIEW_SCRIPT.new()
	card.configure({"zone": "table", "index": 0, "card": {"name": "Тест"}, "rect": Rect2(0, 0, 150, 200), "pressable": true})
	card.place_flight(Rect2(10, 20, 75, 200), true)
	_check(card.is_flight_back() and not card.is_pressable() and card.mouse_filter == Control.MOUSE_FILTER_IGNORE, "полёт карты: рубашка, не нажимается и не принимает мышь")
	card.place_flight(Rect2(10, 20, 75, 200), false)
	_check(not card.is_flight_back() and card.size.is_equal_approx(Vector2(75, 200)), "полёт карты: вторая половина показывает лицо с новым размером")
	card.free()


func _check_reveal_flights() -> void:
	var draft := _fixture("draft_starting.json")
	var flights := VISUAL.reveal_flights(draft, ProjectSettings.globalize_path("res://"))
	_check(flights.size() == 20, "раздача стартового драфта: по карте на каждую карту стола")
	_check(is_equal_approx(float(flights[0]["start"]), 1.0) and is_equal_approx(float(flights[19]["start"]), 1.0 + 19 * 0.03), "карта i стартует через 1.0 + i * 0.03 с")
	_check((flights[3]["to"] as Vector2).is_equal_approx(RULES.draft_slot_rect("starting", 3).get_center()) and (flights[0]["from"] as Vector2).is_equal_approx(RULES.DECK_RECT.get_center()), "полёт из колоды в слот стартового драфта")
	_check(bool(flights[0]["flip"]) and float(flights[0]["duration"]) == 1.0, "раздача: переворот, 1.0 с на карту")


func _check_exchange_key() -> void:
	var base := _after_exchange()
	var key := VISUAL.exchange_key(base)
	_check(not key.is_empty(), "ключ обмена есть, когда в снимке есть last_exchange")
	var poll := base.duplicate(true)
	poll["seconds_left"] = 17
	_check(VISUAL.exchange_key(poll) == key, "опрос того же обмена с другим таймером — тот же ключ")
	var draw := base.duplicate(true)
	draw["phase"] = "draw"
	_check(VISUAL.exchange_key(draw) == key, "фаза не входит в ключ: planning → draw → planning не даёт повтора")
	var longer := base.duplicate(true)
	longer["history"] = (base["history"] as Array) + [{"turn": 9, "events": [{"side": "player", "card": "Сжигание", "burned": true}]}]
	_check(VISUAL.exchange_key(longer) == key, "длина history не входит в ключ (сожжение добавляет запись)")
	var next_turn := base.duplicate(true)
	next_turn["turn"] = 4
	_check(VISUAL.exchange_key(next_turn) != key, "новый ход — новый ключ")
	var quiet := base.duplicate(true)
	quiet["last_exchange"] = []
	_check(VISUAL.exchange_key(quiet).is_empty(), "без обмена ключа нет")


func _check_once_only() -> void:
	var host = await _make_host()
	var fx = host["effects"]
	fx.submit(_before_exchange(), {}, {})
	var after := _after_exchange()
	fx.submit(after, host["current"], {"action": "confirm"})
	fx.advance(3.5)
	var first := (fx.floating_texts() as Array).size()
	_check(first == 1, "обмен проигрался один раз: одно число (-6 HP)")
	var poll := after.duplicate(true)
	poll["seconds_left"] = 33
	fx.submit(poll, host["current"], {})
	fx.advance(0.0)
	_check((fx.queued_kinds() as Array).is_empty() and (fx.floating_texts() as Array).size() == first, "тот же обмен в повторном опросе не проигрывается")
	var draw := after.duplicate(true)
	draw["phase"] = "draw"
	fx.submit(draw, host["current"], {})
	_check((fx.queued_kinds() as Array).is_empty() and (fx.floating_texts() as Array).size() == first, "смена фазы (draw) с тем же обменом не проигрывает его снова")
	fx.submit(after, host["current"], {})
	_check((fx.floating_texts() as Array).size() == first, "возврат к planning с тем же обменом не проигрывает его снова")
	var next := after.duplicate(true)
	next["turn"] = 4
	fx.submit(next, host["current"], {"action": "confirm"})
	fx.advance(0.5)
	_check((fx.floating_texts() as Array).size() == first + 1, "новый ход с обменом проигрывается и даёт новое число")
	fx.advance(4.0)


# Клэш 0.5 с (сыгранные карты на столе, HP старый), урон 1.0 с (HP новый, число появляется в начале), перетасовка
# 2.0 с, затем новое состояние. Число висит 10 с от появления.
func _check_damage_timeline() -> void:
	var host = await _make_host()
	var fx = host["effects"]
	var view = host["view"]
	fx.submit(_before_exchange(), {}, {})
	fx.submit(_after_exchange(), host["current"], {"action": "confirm"})
	_check(str(fx.queued_kinds()) == str(["clash", "damage", "shuffle", "show"]), "порядок шагов: клэш, урон, перетасовка, показ")
	_check(fx.is_busy() and view.input_locked(), "во время клэша ввод закрыт")
	_check(view.card_count() == 2 and view.card_view("selected", 0) != null and view.card_view("hand", 0) == null and view.bar_state("player", "hp")["value"] == 106.0, "клэш: на столе только сыгранные карты, руки не рисуются, HP ещё старый")
	fx.advance(0.25)
	_check(view.bar_state("player", "hp")["value"] == 106.0 and (fx.floating_texts() as Array).is_empty(), "через 0.25 с клэш идёт, чисел нет")
	fx.advance(0.25)
	_check(str(fx.queued_kinds()) == str(["damage", "shuffle", "show"]), "на 0.5 с клэш закончился, начался урон")
	var texts: Array = fx.floating_texts()
	_check(texts.size() == 1 and str(texts[0]["text"]) == "-6 HP" and texts[0]["color"] == RULES.TEXT_COLOR, "на 0.5 с появилось число -6 HP обычным цветом")
	_check(is_equal_approx(float(texts[0]["x"]), 1730.0) and is_equal_approx(float(texts[0]["y"]), 832.0), "число над панелью цели (соперника) на высоте 832")
	_check(view.bar_state("player", "hp")["value"] == 100.0 and view.card_count() == 7, "урон: HP новый, сыгранные карты ещё на столе")
	fx.advance(0.5)
	_check(str(fx.queued_kinds()) == str(["damage", "shuffle", "show"]), "при 1.0 с урона перетасовка ещё не началась")
	fx.advance(0.5)
	_check(str(fx.queued_kinds()) == str(["shuffle", "show"]), "через 1.5 с начинается перетасовка")
	fx.advance(2.0)
	_check(not fx.is_busy() and (fx.queued_kinds() as Array).is_empty(), "после перетасовки (2.0 с) очередь пуста")
	_check(view.card_count() == 5 and view.card_view("selected", 0) == null and not view.input_locked(), "показано новое состояние: руки 5, стола нет, ввод открыт")
	_check(is_equal_approx(float((fx.floating_texts()[0] as Dictionary)["remaining"]), 7.0), "число висит 10 с от появления: через 3.5 с осталось 7 с")
	fx.advance(6.9)
	_check((fx.floating_texts() as Array).size() == 1, "число ещё на месте за 0.1 с до конца")
	fx.advance(0.2)
	_check((fx.floating_texts() as Array).is_empty(), "число пропадает после 10 с")


func _check_result_transition_is_immediate() -> void:
	var host = await _make_host()
	var fx = host["effects"]
	fx.submit(_before_exchange(), {}, {})
	var result := _after_exchange()
	result["phase"] = "result"
	result["outcome"] = "win"
	fx.submit(result, host["current"], {"action": "confirm", "allow_transition": true})
	_check(str(fx.queued_kinds()) == str(["show"]) and fx.is_waiting_display(), "итог боя: переход к итогу сразу с ответом, шаги старой фазы не проигрываются")
	_check(str((host["displays"] as Array)[-1]["transition"]) == "result" and (fx.floating_texts() as Array).is_empty(), "переход запрошен с видом result, числа последнего обмена не появляются")
	fx.display_done()
	_check(not fx.is_busy() and (fx.queued_kinds() as Array).is_empty(), "после display_done очередь пуста")


# Переход фазы снимает шаги, которые ещё идут (клэш), и числа: поле закрыто затемнением, как в Python при переходе.
func _check_transition_drops_pending_steps() -> void:
	var host = await _make_host()
	var fx = host["effects"]
	fx.submit(_before_exchange(), {}, {})
	fx.submit(_after_exchange(), host["current"], {"action": "confirm"})
	fx.advance(0.25)
	_check(str(fx.queued_kinds()) == str(["clash", "damage", "shuffle", "show"]), "перед переходом клэш ещё идёт")
	var result := _after_exchange()
	result["turn"] = 4
	result["phase"] = "result"
	fx.submit(result, host["current"], {"action": "confirm", "allow_transition": true})
	_check(str(fx.queued_kinds()) == str(["show"]) and fx.is_waiting_display(), "переход снимает шаги клэша и урона и показывается сразу")
	fx.display_done()
	_check(not fx.is_busy() and (fx.floating_texts() as Array).is_empty(), "после перехода очередь и числа пусты")


# Интро 2.0 с с пустым столом, затем раздача по задержкам Python; драфт открыт после последней карты.
func _check_draft_intro_and_reveal() -> void:
	var host = await _make_host()
	var fx = host["effects"]
	var view = host["view"]
	fx.submit(_fixture("draft_starting.json"), {}, {})
	_check(str(fx.queued_kinds()) == str(["intro", "reveal", "show"]), "старт боя: интро, раздача, драфт")
	_check(view.card_count() == 0 and view.draft_texts()["visible"], "интро: стол пуст, рамка драфта с заголовком видна")
	fx.advance(1.5)
	_check(str(fx.queued_kinds()) == str(["intro", "reveal", "show"]), "до конца интро (2.0 с) раздача не идёт")
	fx.advance(0.5)
	_check(str(fx.queued_kinds()) == str(["reveal", "show"]) and fx.flight_count() == 20 and not fx.flight_node(0).visible, "раздача: 20 полётов, первый ещё не стартовал")
	fx.advance(0.5)
	fx.advance(0.5)
	_check(fx.flight_node(0).visible, "первая карта летит с 1.0 с раздачи")
	_check((fx.flight_node(0).position + fx.flight_node(0).size / 2.0).distance_to(RULES.DECK_RECT.get_center()) < 5.0, "карта начинает полёт из колоды")
	fx.advance(3.0)
	_check(not fx.is_busy() and fx.flight_count() == 0 and view.card_count() == 22 and view.card_view("table", 19) != null, "после раздачи драфт открыт: 20 карт стола и 2 карты руки")


func _check_pick_flights() -> void:
	var host = await _make_host()
	var fx = host["effects"]
	var view = host["view"]
	var draft := _fixture("draft_starting.json")
	fx.submit(draft, {}, {})
	fx.advance(10.0)
	var source: Vector2 = view.card_rect_of("table", 0).get_center()
	var picked := draft.duplicate(true)
	var picked_card: Dictionary = (picked["table"] as Array).pop_front()
	(picked["hand"] as Array).append(picked_card)
	fx.submit(picked, host["current"], {"action": "pick_starting", "card_key": str(picked_card["key"])})
	_check(str(fx.queued_kinds()) == str(["pick", "show"]), "выбор игрока: полёт и показ драфта")
	_check((host["current"]["table"] as Array).size() == 19 and (host["current"]["hand"] as Array).size() == 3, "полёт: карта уже ушла со стола, в руку ещё не вошла")
	_check(fx.flight_node(0).position.is_equal_approx(source - fx.flight_node(0).size / 2.0), "полёт начинается из слота выбранной карты")
	fx.advance(0.5)
	_check(fx.flight_count() == 0 and (host["current"]["hand"] as Array).size() == 3, "после 0.5 с карта в руке")
	var enemy := picked.duplicate(true)
	var enemy_card: Dictionary = (enemy["table"] as Array).pop_front()
	(enemy["opponent_draft_picks"] as Array).append(str(enemy_card["key"]))
	fx.submit(enemy, host["current"], {"action": "confirm"})
	_check(str(fx.queued_kinds()) == str(["enemy_pick", "show"]), "выбор соперника: полёт из колоды и показ")
	_check((fx.flight_node(0).position + fx.flight_node(0).size / 2.0).is_equal_approx(RULES.DECK_RECT.get_center()), "полёт выбора соперника стартует из колоды")
	fx.advance(0.5)
	_check(fx.flight_count() == 0 and not fx.is_busy(), "выбор соперника: 0.5 с, затем очередь пуста")


func _check_new_battle_clears_queue() -> void:
	var host = await _make_host()
	var fx = host["effects"]
	fx.submit(_before_exchange(), {}, {})
	fx.submit(_after_exchange(), host["current"], {"action": "confirm"})
	fx.advance(0.5)
	_check((fx.floating_texts() as Array).size() == 1, "перед сменой боя число было")
	var other := _before_exchange()
	other["battle_id"] = "other-battle"
	fx.submit(other, host["current"], {"action": "confirm"})
	_check((fx.queued_kinds() as Array).is_empty() and (fx.floating_texts() as Array).is_empty(), "новый бой сбрасывает очередь и числа")
	_check(str(host["current"]["battle_id"]) == "other-battle", "новый бой показан сразу, без проигрыша старого обмена")


func _check_lock_and_damage_display() -> void:
	var host = await _make_host()
	var fx = host["effects"]
	var view = host["view"]
	fx.submit(_before_exchange(), {}, {})
	_check(not view.input_locked() and view.card_view("hand", 2).is_pressable(), "без анимации карта руки нажимается")
	fx.submit(_after_exchange(), host["current"], {"action": "confirm"})
	_check(view.input_locked() and view.card_view("hand", 2) == null, "в клэше руки не рисуются и нажать нечего")
	fx.advance(0.5)
	_check(view.card_view("selected", 0).name_text() == "Удар Валентайна", "в уроне сыгранная карта названа по снимку")
	fx.advance(3.0)
	_check(not view.input_locked() and view.card_view("hand", 0).is_pressable(), "после анимаций карта руки снова нажимается")


# Проводка через deck_world.gd: опрос боя ставит состояние, ответ с обменом ставит шаги в очередь, переход фазы
# к итогу идёт сразу и снимает шаги старой фазы. Запросы не отправляются: ответ передаётся напрямую.
func _check_world_wiring() -> void:
	GameSession.clear()
	GameSession.character = {"id": 0, "name": "Тест", "zone": "backyard"}
	GameSession.world = {"server_url": "", "name": "Тест"}
	var deck = DECK_SCRIPT.new()
	deck.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(deck)
	deck._audio.sound_root = MISSING_SOUND_ROOT
	deck._character_id = 42
	deck._social_timer.stop()
	deck._battle_timer.stop()
	deck._battle_effects.set_process(false)
	deck._view = "battle"
	deck._pending_action = "battle_active"
	deck._on_api_completed(true, {"battle": _before_exchange()})
	deck._battle_timer.stop()
	_check(str(deck._battle_state.get("phase", "")) == "planning" and not deck._battle_effects.is_busy(), "опрос боя показывает состояние без очереди")
	deck._pending_action = "battle_action"
	deck._battle_game_action = {"action": "confirm", "card_key": ""}
	deck._on_api_completed(true, {"battle": _after_exchange()})
	deck._battle_timer.stop()
	_check(deck._battle_effects.is_busy() and deck._battle_view.input_locked(), "ответ с обменом ставит показ в очередь и закрывает ввод")
	_check(deck._battle_view.bar_state("player", "hp")["value"] == 106.0, "в мире до удара показан прежний HP")
	deck._battle_effects.advance(0.5)
	_check(deck._battle_view.bar_state("player", "hp")["value"] == 100.0 and (deck._battle_effects.floating_texts() as Array).size() == 1, "в мире на 0.5 с показан новый HP и число")
	deck._battle_effects.advance(3.0)
	_check(not deck._battle_effects.is_busy() and str(deck._battle_state.get("phase", "")) == "planning" and deck._battle_view.card_count() == 5, "в мире после шагов показано новое состояние")
	var result := _after_exchange()
	result["turn"] = 4
	result["phase"] = "result"
	result["outcome"] = "win"
	deck._battle_state = _before_exchange()
	deck._show_battle_state()
	deck._pending_action = "battle_action"
	deck._battle_game_action = {"action": "confirm", "card_key": ""}
	deck._on_api_completed(true, {"battle": result})
	deck._battle_timer.stop()
	_check(deck._phase_transition.is_active() and deck._battle_effects.is_busy() == false, "переход к итогу запускается сразу с ответом, шаги старой фазы не идут")
	var started := Time.get_ticks_msec()
	while deck._phase_transition.is_active() and Time.get_ticks_msec() - started < WAIT_LIMIT_MS:
		await get_tree().process_frame
	_check(str(deck._battle_state.get("phase", "")) == "result" and not deck._battle_effects.is_busy(), "после перехода показан итог боя")
	deck.queue_free()
	await get_tree().process_frame
	GameSession.clear()
	ApiClient.base_url = "http://127.0.0.1:8765"
	ApiClient.token = ""


# Экран боя без мира: вид и очередь. Показ записывается в displays, текущее показанное состояние — в current.
func _make_host() -> Dictionary:
	var view = VIEW_SCRIPT.new()
	view.size = Vector2(1920, 1080)
	add_child(view)
	var effects = EFFECTS_SCRIPT.new()
	view.add_child(effects)
	effects.attach(view)
	effects.set_process(false)
	var host := {"view": view, "effects": effects, "displays": [], "current": {}}
	effects.display_requested.connect(_on_display.bind(host))
	_hosts.append(host)
	await get_tree().process_frame
	return host


# Как deck_world._on_battle_display_requested: показ без перехода подтверждается сразу, с переходом ждёт вызова.
func _on_display(state: Dictionary, transition: String, host: Dictionary) -> void:
	(host["displays"] as Array).append({"state": state, "transition": transition})
	host["current"] = state
	var view = host["view"]
	view.set_input_locked((host["effects"] as Node).is_busy())
	view.set_snapshot(state)
	if transition.is_empty():
		(host["effects"] as Node).display_done()


func _fixture(file_name: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(FIXTURE_DIR + file_name))
	return parsed if parsed is Dictionary else {}


# Планирование с выбранными картами; обмена ещё не было.
func _before_exchange() -> Dictionary:
	var state := _fixture("planning_hand.json")
	state["last_exchange"] = []
	state["history"] = []
	return state


# Тот же бой после розыгрыша: сыгранные карты ушли из руки, HP новые, обмен из фикстуры.
func _after_exchange() -> Dictionary:
	var source := _fixture("planning_hand.json")
	var state := _before_exchange()
	var played := source["selected"] as Array
	var hand: Array = []
	for card in source["hand"]:
		if not played.has(str(card["key"])):
			hand.append(card)
	state["turn"] = 3
	state["selected"] = []
	state["hand"] = hand
	state["can_select"] = ["warrior_valen_cleave", "warrior_valen_cleave_copy", "warrior_valen_sweep", "warrior_weakness_strength"]
	state["confirmed"] = false
	state["seconds_left"] = 60
	(state["fighter"] as Dictionary)["hp"] = 100
	(state["opponent"] as Dictionary)["hp"] = 29
	state["last_exchange"] = source["last_exchange"]
	state["history"] = [{"turn": 2, "events": source["last_exchange"]}]
	return state
