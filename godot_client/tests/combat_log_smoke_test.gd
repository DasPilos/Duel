extends Node

const LOG_SCRIPT := preload("res://scripts/combat_log.gd")

var _failures: Array[String] = []


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_wrap_check()
	var log = LOG_SCRIPT.new()
	add_child(log)
	log.add("Первая", Color.WHITE)
	log.add("Вторая")
	log.add("Третья")
	_check(log._pending.size() == 3 and log._visible_entries.is_empty(), "записи ждут очереди появления")

	log._process(0.7)
	_check(log._visible_entries.size() == 1 and log._pending.size() == 2, "за интервал 0,6 с появляется одна запись")
	log._process(0.7)
	log._process(0.7)
	_check(log._visible_entries.size() == 3 and log._pending.is_empty(), "все записи появляются по очереди")

	var entry: Dictionary = log._visible_entries[0]
	log._clock = float(entry["shown_at"]) + 10.0
	_check(log._entry_alpha(entry) == 1.0, "в течение 30 с запись непрозрачна")
	log._clock = float(entry["shown_at"]) + 32.5
	_check(is_equal_approx(log._entry_alpha(entry), 0.5), "затухание за 5 с: на 2,5 с альфа 0,5")
	log._clock = float(entry["shown_at"]) + 36.0
	log._process(0.0)
	_check(log._visible_entries.size() < 3, "после 35 с запись удаляется из бокового лога")

	_check(not log.captures_keyboard() and log.mouse_filter == Control.MOUSE_FILTER_IGNORE, "закрытый лог не перехватывает ввод")
	log.toggle_full()
	_check(log.captures_keyboard() and log.mouse_filter == Control.MOUSE_FILTER_STOP, "полный лог перехватывает клавиатуру и мышь")
	log.close_full()
	_check(not log.captures_keyboard() and log.mouse_filter == Control.MOUSE_FILTER_IGNORE, "закрытие полного лога возвращает ввод миру")

	for index in 510:
		log.add("Строка %d" % index)
	_check(log._history.size() == 500, "история ограничена 500 записями")

	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("combat_log_smoke_test: OK")
	get_tree().quit(code)


func _check(condition: bool, message: String) -> void:
	if not condition:
		_failures.append(message)


func _wrap_check() -> void:
	var font := ThemeDB.fallback_font
	var helper = LOG_SCRIPT.new()
	var lines = helper._wrap("Удар по мобу на сорок пять урона и ещё текст чтобы перенеслось", 120.0, font)
	helper.free()
	_check(lines.size() >= 2, "длинная запись переносится на несколько строк")
