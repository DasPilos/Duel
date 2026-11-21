extends Node

const METER := preload("res://scripts/storage_meter.gd")

var _failures: Array[String] = []


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check(METER.fill_color(0, 100) == Color8(218, 69, 65), "до 20 % склад красный")
	_check(METER.fill_color(20, 100) == Color8(218, 69, 65), "ровно 20 % ещё красный, как в Python")
	_check(METER.fill_color(21, 100) == Color8(232, 191, 67), "выше 20 % жёлтый")
	_check(METER.fill_color(40, 100) == Color8(232, 191, 67), "ровно 40 % жёлтый")
	_check(METER.fill_color(41, 100) == Color8(75, 190, 100), "выше 40 % зелёный")
	_check(METER.fill_color(70, 100) == Color8(75, 190, 100), "ровно 70 % зелёный")
	_check(METER.fill_color(71, 100) == Color8(116, 218, 245), "выше 70 % голубой")
	_check(METER.fill_color(5, 0) == Color8(218, 69, 65), "нулевая вместимость красная")
	_check(is_equal_approx(METER.fill_ratio(50, 200), 0.25), "доля заполнения 25 %")
	_check(is_equal_approx(METER.fill_ratio(300, 200), 1.0), "переполнение ограничено 100 %")
	_check(is_equal_approx(METER.fill_ratio(-4, 200), 0.0) and is_equal_approx(METER.fill_ratio(4, 0), 0.0), "отрицательный запас и нулевая вместимость дают 0 %")
	_check(METER.charge_color(0) == Color8(48, 225, 105), "при зарядке первые 350 мс зелёный")
	_check(METER.charge_color(350) == Color8(246, 255, 250), "следующие 350 мс светлый")
	_check(METER.charge_color(700) == Color8(48, 225, 105), "мигание возвращается к зелёному")

	var entries: Array = METER.storage_entries({"wheat": 12, "wood": 3, "limit": 500})
	_check(entries.size() == 2 and entries[0] == {"resource": "wheat", "amount": 12} and entries[1] == {"resource": "wood", "amount": 3}, "служебный ключ limit не попадает в строки склада")

	var meter := METER.new()
	meter.set_values(50, 200, true)
	_check(meter._amount == 50 and meter._capacity == 200 and meter._charging, "метр запоминает значения и режим зарядки")
	meter.free()

	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("storage_meter_smoke_test: OK")
	get_tree().quit(code)


func _check(condition: bool, message: String) -> void:
	if not condition:
		_failures.append(message)
