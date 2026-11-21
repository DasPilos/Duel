extends Node

# Правила производственного окна (ui/production_building_window.py): место игрока, полный склад, выбор горожанина,
# тексты подтверждений и сообщений, производство в час, формат времени, стадия, таймеры, участки и текст уровня. Сетевых вызовов нет.
const RULES := preload("res://scripts/economy_production_rules.gd")

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_slots_and_player()
	_check_storage()
	_check_hire_candidate()
	_check_prompts_and_messages()
	_check_status_rates_and_clock()
	_check_stage_and_timers()
	_check_next_level_text()
	_check_plot_rules()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("economy_production_rules_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _state() -> Dictionary:
	return {
		"building": "farm",
		"level": 2,
		"workers": 2,
		"max_workers": 5,
		"player_work": {"slot_index": 2},
		"storage": {"wheat": 40, "wood": 10, "limit": 100},
		"worker_slots": [
			{"slot_index": 0, "occupied": false, "worker_id": null, "resource": "wheat", "resources": ["wheat"]},
			{"slot_index": 1, "occupied": true, "worker_id": "citizen:5", "resource": "wheat", "resources": ["wheat"], "is_player": false},
			{"slot_index": 2, "occupied": true, "worker_id": "player:7", "resource": "wheat", "resources": ["wheat"], "is_player": true},
		],
	}


func _check_slots_and_player() -> void:
	_check(RULES.player_worker_id(7) == "player:7", "идентификатор игрока player:N")
	_check(RULES.player_is_working(_state(), 7), "игрок 7 стоит на месте 2")
	_check(not RULES.player_is_working(_state(), 8), "другой персонаж не работает")
	_check(int(RULES.player_slot(_state(), 7).get("slot_index", -1)) == 2, "место игрока находится по worker_id")
	_check(str(RULES.slot_at(_state(), 1).get("worker_id", "")) == "citizen:5", "место находится по slot_index")
	_check(RULES.slot_at(_state(), 99).is_empty(), "несуществующее место пустое")
	_check(RULES.citizen_id("citizen:12") == 12, "номер горожанина из citizen:N")
	_check(RULES.citizen_id("player:7") == -1, "игрок не горожанин")
	_check(RULES.citizen_id("citizen-5") == -1, "старый формат citizen-N не отзывается, как в Python")
	_check(RULES.citizen_id(null) == -1, "пустое место не горожанин")


func _check_storage() -> void:
	_check(RULES.storage_is_full({"storage_full": true}), "storage_full от сервера главнее")
	_check(RULES.storage_is_full({"storage_full": true, "storage": {"wheat": 1, "limit": 100}}), "storage_full true даёт полный склад")
	_check(not RULES.storage_is_full({"storage_full": false, "storage": {"wheat": 100, "limit": 100}}), "storage_full false главнее товаров")
	_check(RULES.storage_is_full({"storage": {"wheat": 100, "wood": 100, "limit": 100}}), "все товары на лимите — склад полон")
	_check(not RULES.storage_is_full({"storage": {"wheat": 100, "wood": 99, "limit": 100}}), "один товар ниже лимита — склад не полон")
	_check(not RULES.storage_is_full({"storage": {"limit": 100}}), "склад без товаров не полон")
	var full := {"wheat": 100, "flax": 100, "limit": 100}
	_check(RULES.slot_storage_is_full([{"resource": "wheat"}], full), "место с полным ресурсом полно")
	_check(not RULES.slot_storage_is_full([{"resource": "wheat"}], {"wheat": 99, "limit": 100}), "неполный ресурс места не блокирует")
	_check(not RULES.slot_storage_is_full([{"resources": ["wheat", "flax"]}], {"wheat": 100, "flax": 10, "limit": 100}),
		"место с двумя ресурсами полно, только если полны оба")
	_check(RULES.slot_storage_is_full([{"resources": ["wheat", "flax"]}], full), "оба ресурса места на лимите")
	_check(not RULES.slot_storage_is_full([{"resource": null}], full), "место без ресурса не блокируется")
	var state := _state()
	state["storage"] = {"wheat": 100, "limit": 100}
	_check(RULES.player_click_blocked(state, 0, 7), "встать на чужое место при полном складе нельзя")
	_check(not RULES.player_click_blocked(state, 2, 7), "своё место не блокируется складом")
	_check(not RULES.player_click_blocked(_state(), 0, 7), "при неполном складе нажатие проходит")
	state["player_work"] = null
	_check(RULES.player_confirm_blocked(state, 0), "подтверждение блокируется, если игрок нигде не работает и склад полон")
	state["player_work"] = {"slot_index": 2}
	_check(not RULES.player_confirm_blocked(state, 0), "при работе игрока подтверждение не блокируется")


func _check_hire_candidate() -> void:
	var citizens := [
		{"id": 1, "name": "Занят", "job_building": "farm", "satisfaction": "satisfied", "work_status": "Занят"},
		{"id": 2, "name": "Голодный", "job_building": null, "satisfaction": "starving", "work_status": "Свободен"},
		{"id": 3, "name": "В городе", "job_building": null, "satisfaction": "satisfied", "work_status": "В городе"},
		{"id": 4, "name": "В пути", "job_building": null, "satisfaction": "satisfied", "work_status": "Свободен", "travel_direction": "outbound"},
		{"id": 7, "name": "Работает", "job_building": null, "satisfaction": "satisfied", "work_status": "Свободен", "working": true},
		{"id": 5, "name": "Подходит", "job_building": null, "satisfaction": "satisfied", "work_status": "Свободен", "travel_direction": null},
		{"id": 6, "name": "Второй", "job_building": null, "satisfaction": "satisfied", "work_status": "Свободен"},
	]
	_check(int(RULES.hire_candidate(citizens).get("id", 0)) == 5, "берётся первый подходящий горожанин по порядку списка")
	var no_status := [{"id": 8, "name": "Без статуса", "job_building": null, "satisfaction": "satisfied"}]
	_check(int(RULES.hire_candidate(no_status).get("id", 0)) == 8, "без work_status считаем Свободен, как в Python")
	_check(RULES.hire_candidate([]).is_empty(), "пустой список не даёт горожанина")
	_check(RULES.hire_candidate(null).is_empty(), "неверный список не даёт горожанина")


func _check_prompts_and_messages() -> void:
	_check(RULES.confirm_prompt("hire", {}) == "Поставить горожанина на работу?", "вопрос найма как в Python")
	_check(RULES.confirm_prompt("fire", {}) == "Снять горожанина с работы?", "вопрос снятия как в Python")
	_check(RULES.confirm_prompt("player", {"player_work": {"slot_index": 2}}) == "Остановить вашу добычу?", "вопрос остановки добычи")
	_check(RULES.confirm_prompt("player", {"player_work": null}) == "Встать на добычу вместо горожанина?", "вопрос начала добычи")
	_check(RULES.MSG_LEAVE_BLOCKED == "Чтобы покинуть место, завершите работу.", "сообщение о незавершённой работе как в Python")
	_check(RULES.MSG_STORAGE_FULL == "Склад переполнен, нельзя начать добычу.", "сообщение о полном складе как в Python")
	_check(RULES.MSG_RECALLED == "Горожанин возвращается в город.", "сообщение о возврате горожанина как в Python")
	_check(RULES.MSG_NO_CITIZENS == "Нет свободных горожан для работы.", "сообщение об отсутствии горожан как в Python")
	_check(RULES.hired_text("Анна") == "Анна отправлен к месту работы.", "сообщение о найме как в Python")


func _check_status_rates_and_clock() -> void:
	_check(RULES.status_key({"upgrade": {"in_progress": true}}) == "upgrade", "статус: идёт улучшение")
	_check(RULES.status_key({"storage_full": true, "workers": 3}) == "full", "статус: склад полон важнее работы")
	_check(RULES.status_key({"workers": 1}) == "working", "статус: работает")
	_check(RULES.status_key({}) == "idle", "статус: нет рабочих")
	var rates_state := {"worker_slots": [
		{"occupied": true, "is_travelling": false, "resources": ["wheat"], "timer_sec_by_resource": {"wheat": 900}},
		{"occupied": true, "is_travelling": true, "resources": ["wheat"], "timer_sec_by_resource": {"wheat": 900}},
		{"occupied": false, "resources": ["wood"], "timer_sec_by_resource": {"wood": 600}},
	]}
	var rates := RULES.production_per_hour(rates_state)
	_check(is_equal_approx(float(rates.get("wheat", 0.0)), 4.0), "в пути место не даёт производства, занятое — 3600/900 в час")
	_check(rates.has("wood") and is_equal_approx(float(rates["wood"]), 0.0), "свободный ресурс есть в списке с нулём, как в Python")
	_check(RULES.clock_text(3725) == "1:02:05", "время с часами как в Python: 1:02:05")
	_check(RULES.clock_text(65) == "1:05", "время без часов: минуты:секунды")
	_check(RULES.clock_text(3600) == "1:00:00", "ровно час")
	_check(RULES.clock_text(-3) == "0:00", "отрицательное время даёт нули")


func _check_stage_and_timers() -> void:
	_check(RULES.stage_index({"stage": 2}) == 2, "стадия берётся из состояния здания")
	_check(RULES.stage_index({"stage": 9}) == 3, "стадия не выше четвёртой")
	_check(RULES.stage_index({}) == 0, "без стадии первая")
	_check(RULES.texture_file("wheat", 0) == "field_wheat_stage_1.png", "файл текстуры: стадия плюс один, как в Python")
	_check(RULES.texture_file("cotton", 3) == "field_cotton_stage_4.png", "четвёртая стадия")
	var slot := {"occupied": true, "resources": ["leather", "meat"], "timer_sec_by_resource": {"meat": 600},
		"resource_progress_sec": {"leather": 10}, "progress_sec": 0}
	_check(RULES.resource_timer(slot, "meat") == 600.0, "цикл из слота учитывает бонус")
	_check(RULES.resource_timer(slot, "leather") == 460.0, "без цикла в слоте берётся базовый из справочника")
	var entries := RULES.timer_entries(slot)
	_check(entries.size() == 2 and entries[0]["resource"] == "leather" and float(entries[0]["progress"]) == 10.0,
		"таймеры места идут по ресурсам в порядке слота")
	_check(RULES.timer_entries({"occupied": true, "is_travelling": true, "resources": ["wheat"]}).is_empty(), "в пути таймеров нет")
	_check(RULES.timer_entries({"occupied": false, "resources": ["wheat"]}).is_empty(), "свободное место без таймеров")
	_check(RULES.timer_entries({"occupied": true, "resources": ["jet"]}).is_empty(), "самоцвет без цикла не показывается")
	_check(RULES.seconds_left(120.0, 100.0, 0.0) == 20, "остаток до единицы")
	_check(RULES.seconds_left(120.0, 100.0, 30.0) == 110, "прошедшее время переходит через цикл")
	_check(RULES.seconds_left(140.0, 0.0, 0.0) == 140, "новый цикл полный")
	_check(RULES.seconds_left(140.0, 139.5, 0.0) == 1, "дробная секунда округляется вверх")
	_check(RULES.clock_text(RULES.seconds_left(120.0, 100.0, 0.0)) == "0:20", "таймер места в минутах и секундах")


# Ожидаемые строки получены из production_desc в ui/production_building_window.py.
func _check_next_level_text() -> void:
	_check(RULES.production_desc("farm", 2) == "Горожанин: пшеница 1 ед. за 140 с, лён 1 ед. за 480 с, хлопок 1 ед. за 980 с. Вместимость каждого товара: 800. Горожан: 4.",
		"следующий уровень фермы: циклы, склад и горожане как в Python")
	_check(RULES.production_desc("farm", 10) == "Горожанин: пшеница 1 ед. за 140 с, лён 1 ед. за 480 с, хлопок 1 ед. за 980 с. Вместимость каждого товара: 12000. Горожан: 26.",
		"ферма 10 уровня: горожан на 1 больше таблицы")
	_check(RULES.production_desc("lumber_camp", 2) == "Горожанин: древесина 1 ед. за 240 с, ягоды 1 ед. за 360 с. Вместимость каждого товара: 800. Горожан: 3.",
		"следующий уровень лесопилки")
	_check(RULES.production_desc("mountain_rift", 2) == "Горожанин: камень 1 ед. за 200 с, железная руда 1 ед. за 300 с, мифриловая руда 1 ед. за 900 с, обсидиановая порода 1 ед. за 1400 с. Вместимость каждого товара: 800. Горожан: 3.",
		"следующий уровень разлома: ресурсы в порядке участков")
	_check(RULES.production_desc("barnyard", 2) == "Горожанин: кожа 1 ед. за 460 с, мясо 1 ед. за 680 с. Вместимость каждого товара: 800. Горожан: 3.",
		"следующий уровень загона")
	_check(RULES.production_desc("black_pit", 2) == "Горожанин: уголь 1 ед. за 600 с. Вместимость каждого товара: 800. Горожан: 3.",
		"копь до третьего уровня без бонуса")
	_check(RULES.production_desc("black_pit", 3) == "Горожанин: уголь 1 ед. за 600 с. Бонусный самоцвет: шанс 0.43% на каждую добытую единицу угля (гагат 100%; каждый 1 кг). Вместимость каждого товара: 1000. Горожан: 4.",
		"копь третьего уровня: шанс бонуса и самоцветы")
	_check(RULES.production_desc("black_pit", 10) == "Горожанин: уголь 1 ед. за 600 с. Бонусный самоцвет: шанс 3.51% на каждую добытую единицу угля (гагат 11%, малахит 12%, топаз 13%, гранат 14%, изумруд 14%, рубин 14%, сапфир 14%, алмаз 8%; каждый 1 кг). Вместимость каждого товара: 12000. Горожан: 25.",
		"копь десятого уровня: все самоцветы по весам")


func _check_plot_rules() -> void:
	var rift := RULES.plot_groups("mountain_rift")
	_check(rift.size() == 4 and int(rift[0]["places"]) == 7 and int(rift[1]["places"]) == 10,
		"прииски собраны по видам, места складываются")
	_check(RULES.plot_name("mountain_rift", rift[1]) == "Прииск железа", "название прииска без ресурса в скобках")
	_check(RULES.plot_groups("barnyard").size() == 1 and int(RULES.plot_groups("barnyard")[0]["places"]) == 25,
		"загон один на все места")
	_check(RULES.plot_name("farm", RULES.plot_groups("farm")[0]) == "Поле (пшеница)", "название поля с ресурсом")
	var state := {
		"worker_slots": [
			{"slot_index": 0, "occupied": false, "resources": ["wheat"]},
			{"slot_index": 1, "occupied": true, "worker_id": "citizen:5", "worker_name": "Анна", "is_player": false, "resources": ["wheat"]},
			{"slot_index": 2, "occupied": false, "resources": ["wheat"]},
			{"slot_index": 3, "occupied": true, "worker_id": "player:7", "is_player": true, "resources": ["wheat"]},
			{"slot_index": 1000, "occupied": false, "resources": ["wheat"]},
			{"slot_index": 2101, "occupied": false, "resources": ["wheat"]},
		],
		"farm_upgrades": {"ration_plots": [0.0], "extra_places": {"1": 1.0}},
	}
	var first: Array = RULES.plot_slots(state, "farm", 0)
	_check(first.size() == 3 and int(first[2]["slot_index"]) == 1000, "бонусное место ration добавляется к первому полю")
	_check(RULES.plot_slots(state, "farm", 1).size() == 3, "дополнительное место фермы добавляется к полю")
	_check(RULES.plot_slots(state, "farm", 4) == null, "закрытый участок не имеет мест")
	_check(RULES.plot_click(state, "farm", 0) == {"action": "hire", "slot_index": 0}, "клик по свободному месту — найм")
	_check(RULES.plot_click(state, "farm", 1) == {"action": "hire", "slot_index": 2}, "первое свободное место участка")
	_check(RULES.plot_click(state, "farm", 4) == {"message": "Поле (лён) откроется на 4 уровне"}, "закрытый участок называет уровень")
	_check(RULES.plot_remove(state, "farm", 0) == {"action": "fire", "slot_index": 1}, "правый клик снимает горожанина")
	_check(RULES.plot_remove(state, "farm", 1) == {"message": RULES.MSG_PLOT_EMPTY}, "игрок сам себя не снимает")
	_check(RULES.plot_hint(state, "farm", 0, 42) == "Поле (пшеница): работников 1 / 3. Клик — заменить горожанина собой",
		"подсказка поля: занятые места и замена горожанина")
	_check(RULES.plot_hint(state, "farm", 4, 42) == "Поле (лён), мест: 1. Откроется на 4 уровне", "подсказка закрытого поля")
	var pit := {"worker_slots": [
		{"slot_index": 0, "occupied": true, "worker_id": "citizen:3", "is_player": false, "resources": ["coal"]},
		{"slot_index": 1, "occupied": false, "resources": ["coal"]},
	]}
	_check(RULES.plot_hint(pit, "black_pit", 0, 42) == "Копанка (уголь): горняков 1 / 2. Клик — отправить горожанина",
		"подсказка копанки")
	var rift_state := {"worker_slots": [
		{"slot_index": 0, "occupied": true, "worker_id": "citizen:3", "is_player": false, "resources": ["stone"]},
	]}
	_check(RULES.plot_hint(rift_state, "mountain_rift", 0, 42) == "Прииск камня: горожан 1 / 1 (до 7 с улучшениями). Клик — снять горожанина",
		"подсказка прииска: мест столько, сколько открыто")
	var pen_state := {"worker_slots": [
		{"slot_index": 0, "occupied": true, "worker_id": "citizen:3", "is_player": false, "resources": ["leather", "meat"]},
		{"slot_index": 1, "occupied": false, "resources": ["leather", "meat"]},
	]}
	_check(RULES.plot_hint(pen_state, "barnyard", 0, 42) == "Загон: горожан 1 / 2 (до 25 с улучшениями). Клик — отправить горожанина",
		"подсказка загона")
	_check(RULES.plot_lock_caption("farm", 1) == "Пшеница · ур. 2", "надпись закрытого поля")
	_check(RULES.plot_lock_caption("black_pit", 1) == "Копанка · ур. 2", "надпись закрытой копанки")
	_check(RULES.plot_lock_caption("mountain_rift", 1) == "Прииск железа · ур. 2", "надпись закрытого прииска")
