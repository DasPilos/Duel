extends Node

# Подземелье: геометрия комнат, стены и проём, ходьба, бой у противника, торговец, фонтан и сундук.
const VIEW_SCRIPT := preload("res://scripts/deck_dungeon_view.gd")
const RULES := preload("res://scripts/deck_dungeon_rules.gd")

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	await _check_rules()
	await _check_view()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_dungeon_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _check_rules() -> void:
	_check(RULES.door_tile() == Vector2i(77, 39), "проём на восточной стене посреди комнаты")
	_check(RULES.start_tile() == Vector2i(65, 39), "игрок входит у западной стены на уровне проёма")
	_check(RULES.actor_tile() == Vector2i(72, 39), "противник стоит на ORIGIN + (8, 5), как в Python")
	_check(RULES.APPROACH == Vector2i(24, 45), "ко входу — клетка перед порталом, как checkpoint_position")
	_check(RULES.is_wall(Vector2i(70, 34), false), "верхний ряд — стена")
	_check(RULES.is_wall(Vector2i(64, 39), false), "левый столбец — стена")
	_check(not RULES.is_wall(Vector2i(66, 36), false), "внутри комнаты пол")
	_check(RULES.is_wall(Vector2i(77, 39), false), "закрытый проём — стена")
	_check(not RULES.is_wall(Vector2i(77, 39), true), "открытый проём проходим")
	_check(RULES.is_wall(Vector2i(77, 38), true), "остальная восточная стена закрыта и при открытом проёме")
	_check(RULES.is_wall(Vector2i(63, 39), true), "за пределами комнаты стена")
	_check(RULES.gate_open(1, {1: true}, {}), "после победы в комнате 1 проход открыт")
	_check(not RULES.gate_open(1, {}, {}), "до победы в комнате 1 проход закрыт")
	_check(RULES.gate_open(2, {}, {2: true}), "торговец открывает проход после «ЗАКРЫТЬ МАГАЗИН»")
	_check(RULES.gate_open(4, {}, {4: true}), "фонтан открывает проход")
	_check(not RULES.gate_open(6, {6: true}, {6: true}), "из последней комнаты выхода по проёму нет")
	_check(RULES.leaves_east(1, RULES.door_tile(), Vector2i(1, 0), true), "шаг на восток через открытый проём ведёт в следующую комнату")
	_check(not RULES.leaves_east(6, RULES.door_tile(), Vector2i(1, 0), true), "в шестой комнате проёма нет")
	_check(not RULES.leaves_east(1, RULES.door_tile(), Vector2i(1, 0), false), "закрытый проём не пускает")
	_check(RULES.actor_reachable(Vector2i(71, 38)), "диагональ к противнику — рядом")
	_check(not RULES.actor_reachable(Vector2i(70, 39)), "две клетки до противника — далеко")
	_check(RULES.battle_pending(3, {1: true}), "бой комнаты 3 ждёт, пока не пройдён")
	_check(not RULES.battle_pending(3, {3: true}), "пройденный бой не начинается снова")
	_check(RULES.hint(1, false, false) == "Враги преграждают проход", "подсказка боя как в Python")
	_check(RULES.hint(2, false, false) == "Поговорите с торговцем и закройте магазин, чтобы пройти дальше", "подсказка торговца как в Python")
	_check(RULES.hint(6, false, false) == "Откройте сундук и заберите награды", "подсказка сундука как в Python")
	_check(RULES.on_entrance(Vector2i(25, 43)) and RULES.on_entrance(Vector2i(27, 46)), "вход занимает тайлы 25..27 × 43..46")
	_check(not RULES.on_entrance(Vector2i(28, 43)) and not RULES.on_entrance(Vector2i(24, 45)), "соседние тайлы не вход")
	_check(RULES.room_name(4) == "Комната IV • Целебный фонтан", "названия комнат как в Python")
	var request := RULES.new_request_id()
	_check(request.length() == 36 and request[14] == "4" and "89ab".contains(request[19]), "идентификатор сокровища — UUID v4")
	await get_tree().process_frame


func _walk(view, target: Vector2i) -> void:
	for _step in 40:
		var before: Vector2i = view.player_tile()
		if before == target:
			return
		var step := Vector2i(signi(target.x - before.x), 0) if before.x != target.x else Vector2i(0, signi(target.y - before.y))
		view._try_move(step)
		if view.player_tile() == before:
			_check(false, "ход заблокирован на пути к цели")
			return


func _check_view() -> void:
	var host := Control.new()
	host.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(host)
	var view = VIEW_SCRIPT.new()
	view.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	host.add_child(view)
	await get_tree().process_frame
	var battles: Array = []
	view.battle_requested.connect(func(room: int, tile: Vector2i) -> void: battles.append([room, tile]))
	var merchants: Array = []
	view.merchant_requested.connect(func() -> void: merchants.append(true))
	var buys: Array = []
	view.merchant_buy_requested.connect(func(kind: String, index: int) -> void: buys.append([kind, index]))
	var fountains: Array = []
	view.fountain_requested.connect(func() -> void: fountains.append(true))
	var chests: Array = []
	view.chest_open_requested.connect(func(request_id: String) -> void: chests.append(request_id))
	var exits: Array = []
	view.exit_requested.connect(func() -> void: exits.append(true))

	_check(not view.is_open() and not view.visible, "подземелье закрыто по умолчанию")
	view.open_dungeon()
	_check(view.is_open() and view.visible and view.room() == 1, "вход открывает первую комнату")
	await get_tree().process_frame
	_check(view._hint.get_global_rect().position.y > 0.0 and view._hint.get_global_rect().end.y <= view.get_global_rect().end.y, "подсказка комнаты видна внутри окна")
	view._interact()
	_check(view._message_label.text == "Подойдите ближе к объекту", "«далеко» показывает сообщение сразу")
	_check(view.player_tile() == RULES.start_tile(), "игрок встаёт у западной стены")
	view._try_move(Vector2i(-1, 0))
	_check(view.player_tile() == RULES.start_tile(), "стена не пускает игрока")
	view._try_move(Vector2i(0, 1))
	_check(view.player_tile() == Vector2i(65, 40), "клетка пола пропускает")
	view._try_move(Vector2i(0, -1))

	_walk(view, Vector2i(71, 39))
	_check(battles.size() == 1 and battles[0][0] == 1 and battles[0][1] == Vector2i(71, 39), "подход к противнику комнаты 1 запрашивает бой")
	_check(view.is_busy(), "пока бой запускается, поле занято")
	view._try_move(Vector2i(-1, 0))
	_check(view.player_tile() == Vector2i(71, 39), "во время боя игрок не ходит")
	view.battle_started(1)
	view.battle_start_failed("Подойдите ближе к противнику")
	_check(not view.is_busy(), "ошибка старта снимает занятость")
	_check(battles.size() == 1, "ошибка старта не повторяет запрос сама")
	view._try_move(Vector2i(-1, 0))
	_walk(view, Vector2i(71, 39))
	_check(battles.size() == 2, "повторный подход после ошибки снова запрашивает бой")
	view.battle_started(1)
	view.battle_won(1)
	_check(view.is_cleared(1) and not view.is_busy(), "победа очищает комнату")
	_walk(view, Vector2i(77, 39))
	_check(view.room() == 1 and view.player_tile() == Vector2i(77, 39), "проём открыт после победы: игрок у двери")
	view._try_move(Vector2i(1, 0))
	_check(view.room() == 2 and view.player_tile() == RULES.start_tile(), "проход ведёт в комнату 2 и ставит игрока у входа")

	_walk(view, Vector2i(71, 39))
	view._interact()
	_check(merchants.size() == 1 and view.panel_name() == "merchant", "E у торговца открывает магазин и просит ассортимент")
	var escape := InputEventKey.new()
	escape.keycode = KEY_ESCAPE
	escape.pressed = true
	view._input(escape)
	_check(view.panel_name() == "merchant", "Esc не закрывает магазин: клавиша уходит в меню выхода")
	view._panel_close.pressed.emit()
	_check(view.panel_name() == "" and not view.is_completed(2), "крестик закрывает магазин без открытия прохода")
	view._interact()
	view.show_merchant([{"name": "Зелье", "price_text": "15"}], [{"name": "Удар", "price_text": "100", "available": false}], "У вас: 500")
	view._merchant_list.select(0)
	view._on_primary_pressed()
	_check(buys.size() == 1 and buys[0] == ["supply", 0] and view.is_busy(), "покупка товара отправляет индекс")
	view.merchant_result("Куплено: Зелье", false, "У вас: 485")
	view._merchant_list.select(1)
	view._on_primary_pressed()
	_check(buys.size() == 1 and not view.is_busy(), "недоступная карта не покупается")
	view._on_secondary_pressed()
	_check(view.panel_name() == "" and view.is_completed(2), "«ЗАКРЫТЬ МАГАЗИН» открывает проход")
	_walk(view, Vector2i(77, 39))
	_check(view.room() == 2 and view.player_tile() == Vector2i(77, 39), "после магазина проём открыт")
	view._try_move(Vector2i(1, 0))
	_check(view.room() == 3 and view.player_tile() == RULES.start_tile(), "проход ведёт в комнату 3")

	_walk(view, Vector2i(71, 39))
	_check(battles.size() == 3 and battles[2][0] == 3, "комната 3 начинает свой бой")
	view.battle_started(3)
	view.battle_won(3)
	_walk(view, Vector2i(77, 39))
	view._try_move(Vector2i(1, 0))
	_check(view.room() == 4, "после победы в комнате 3 проход в комнату 4")

	_walk(view, Vector2i(71, 39))
	view._interact()
	_check(fountains.size() == 1 and view.is_busy(), "E у фонтана запрашивает восстановление")
	view.fountain_result(true, "")
	_check(view.is_completed(4), "фонтан открывает проход")
	_walk(view, Vector2i(77, 39))
	view._try_move(Vector2i(1, 0))
	_check(view.room() == 5, "после фонтана проход в комнату 5")

	_walk(view, Vector2i(71, 39))
	view.battle_started(5)
	view.battle_won(5)
	_walk(view, Vector2i(77, 39))
	view._try_move(Vector2i(1, 0))
	_check(view.room() == 6 and view.player_tile() == RULES.start_tile(), "проход в комнату 6 (сокровищница)")

	_walk(view, Vector2i(71, 39))
	view._interact()
	_check(view.panel_name() == "chest", "E у сундука открывает сундук")
	view._on_primary_pressed()
	_check(chests.size() == 1 and str(chests[0]).length() == 36 and view.is_busy(), "открытие сундука отправляет request_id")
	view.chest_result(false, [], "Не удалось открыть сундук: сеть")
	_check(not view.is_busy() and not view.treasure_opened(), "ошибка сундука не открывает его")
	view._on_primary_pressed()
	view.chest_result(true, ["Золото: 830"], "")
	_check(view.treasure_opened(), "сундук открыт")
	view._on_primary_pressed()
	_check(exits.size() == 1, "«ВЫЙТИ» запрашивает выход из подземелья")

	view.set_suspended(true)
	_check(not view.visible and view.is_open(), "пока открыт бой, поле скрыто")
	view.set_suspended(false)
	_check(view.visible, "после боя поле снова видно")
	view.close_dungeon()
	_check(not view.is_open() and not view.visible, "выход закрывает подземелье")
	host.queue_free()
	await get_tree().process_frame
