extends Node

const HUD_SCRIPT := preload("res://scripts/server_status_hud.gd")

var _failures: Array[String] = []
var _restart_requests := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var hud = HUD_SCRIPT.new()
	hud.restart_requested.connect(func() -> void: _restart_requests += 1)
	add_child(hud)

	_check(not hud.visible, "без статуса плашка скрыта")

	hud.apply_status({
		"online_players": 3,
		"server_time": 1700000000.0,
		"server_timezone": "Europe/Kyiv",
		"server_utc_offset_seconds": 7200,
		"restart_notice": null,
	})
	_check(hud.visible, "со статусом плашка видна")
	_check(hud._simple_label.visible and not hud._notice_box.visible, "без уведомления показан короткий вариант")
	_check(hud._simple_label.text == "Игроков онлайн: 3   00:13:20", "онлайн и серверное время с часовым поясом сервера: %s" % hud._simple_label.text)
	_check(hud._panel.offset_right - hud._panel.offset_left == 250.0, "короткая плашка 250 px в базовых единицах")

	hud.set_blocked(true)
	_check(not hud.visible, "при открытом меню выхода или потере связи плашка скрыта")
	hud.set_blocked(false)
	_check(hud.visible, "после снятия блокировки плашка снова видна")

	hud.apply_status({
		"online_players": 5,
		"server_time": 1700000000.0,
		"server_utc_offset_seconds": 7200,
		"restart_notice": {"message": "Сервер получил обновление.", "seconds_remaining": 90, "restart_at": 1700000090.0},
	})
	_check(hud._notice_box.visible and not hud._simple_label.visible, "с уведомлением показан вариант перезапуска")
	_check(hud._notice_title.text == "Сервер получил обновление. Перезапуск через 1:30", "заголовок уведомления: %s" % hud._notice_title.text)
	_check(hud._notice_details.text == "Онлайн: 5 · Сервер: 00:13:20. Если нужно, перезапустите клиент.", "строка деталей: %s" % hud._notice_details.text)
	_check(hud._panel.offset_right - hud._panel.offset_left == 760.0 or hud._panel.offset_right - hud._panel.offset_left == get_viewport().get_visible_rect().size.x - 24.0, "панель уведомления 760 px или по ширине окна")

	hud._notice_received_msec = Time.get_ticks_msec() - 30000
	hud._refresh_texts()
	_check(hud._notice_title.text.ends_with("Перезапуск через 1:00"), "отсчёт уменьшается с прошедшим временем: %s" % hud._notice_title.text)

	hud._restart_button.pressed.emit()
	_check(_restart_requests == 1, "кнопка «Перезапустить клиент» шлёт restart_requested")

	hud.apply_status({"online_players": 5, "server_time": 1700000000.0, "server_utc_offset_seconds": 0, "restart_notice": null})
	_check(hud._simple_label.visible and hud._simple_label.text == "Игроков онлайн: 5   22:13:20", "после снятия уведомления возвращается короткая плашка: %s" % hud._simple_label.text)

	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("server_status_hud_smoke_test: OK")
	get_tree().quit(code)


func _check(condition: bool, message: String) -> void:
	if not condition:
		_failures.append(message)
