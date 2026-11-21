extends Node

# Переход между фазами боя: выбор перехода по фазам, затемнение, один вызов после окончания и игнор повтора.
const TRANSITION_SCRIPT := preload("res://scripts/deck_phase_transition.gd")

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_kinds()
	await _check_playback()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_phase_transition_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _check_kinds() -> void:
	_check(TRANSITION_SCRIPT.transition_kind("draft", "planning") == "battle_start", "старт боя: драфт → планирование")
	_check(TRANSITION_SCRIPT.transition_kind("planning", "result") == "result", "итог боя: планирование → результат")
	_check(TRANSITION_SCRIPT.transition_kind("draw", "result") == "result", "итог боя из добора")
	_check(TRANSITION_SCRIPT.transition_kind("result", "result") == "", "повторный результат без перехода")
	_check(TRANSITION_SCRIPT.transition_kind("", "draft") == "", "первая фаза без перехода")
	_check(TRANSITION_SCRIPT.transition_kind("planning", "draw") == "", "обычная смена фаз без перехода")


func _check_playback() -> void:
	var host := Node.new()
	add_child(host)
	var transition = TRANSITION_SCRIPT.new()
	host.add_child(transition)
	await get_tree().process_frame

	_check(not transition.is_active() and not transition.visible, "переход выключен по умолчанию")
	var calls: Array = []
	transition.play(func() -> void: calls.append(true), 0.2)
	_check(transition.is_active() and transition.visible, "переход запускается")
	transition.play(func() -> void: calls.append("second"), 0.2)
	await get_tree().create_timer(0.08).timeout
	_check(transition.is_active() and calls.is_empty(), "повторный запуск во время перехода игнорируется")
	await get_tree().create_timer(0.3).timeout
	_check(not transition.is_active() and not transition.visible, "переход завершается и скрывается")
	_check(calls == [true], "после затемнения вызывается ровно одно продолжение")
	host.queue_free()
	await get_tree().process_frame
