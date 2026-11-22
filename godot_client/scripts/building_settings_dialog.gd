extends ConfirmationDialog

# Настройки главного здания: здоровье, регенерация HP в минуту и до пяти слотов обороны.
# Каждый слот настраивается отдельно: тип атаки, урон мин/макс, радиус (единицы, как у героев),
# интервал между выстрелами в секундах (скорость снаряда — стандартная, как у героев).

const SPAWN_RULES = preload("res://scripts/map_editor_spawn_rules.gd")
const ATTACK_LABELS := {"arrow": "Стрелы", "magic": "Магические выстрелы"}
const ATTACK_ORDER := ["arrow", "magic"]

var _hp_spin: SpinBox
var _regen_spin: SpinBox
var _slots_box: VBoxContainer
var _add_button: Button
var _slot_rows: Array = []


func _ready() -> void:
	title = "Настройки главного здания"
	ok_button_text = "Сохранить"
	min_size = Vector2i(620, 560)
	var scroll := ScrollContainer.new()
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	add_child(scroll)
	var body := VBoxContainer.new()
	body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(body)
	_hp_spin = _labeled_spin(body, "Здоровье здания", 1, 100000, 1, 500)
	_regen_spin = _labeled_spin(body, "Регенерация HP в минуту (60 с)", 0, 10000, 1, 0)
	var defense_title := Label.new()
	defense_title.text = "Оборона (слоты до %d)" % SPAWN_RULES.MAX_DEFENSE_SLOTS
	body.add_child(defense_title)
	_slots_box = VBoxContainer.new()
	_slots_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	body.add_child(_slots_box)
	_add_button = Button.new()
	_add_button.text = "Добавить оборону"
	_add_button.pressed.connect(_on_add_slot_pressed)
	body.add_child(_add_button)


# Заполняет форму из сохранённых настроек здания (значения проходят через ту же проверку, что и на сервере).
func set_settings(settings: Variant) -> void:
	var normalized: Dictionary = SPAWN_RULES.normalize_building_settings(settings)
	_hp_spin.value = int(normalized["hp"])
	_regen_spin.value = int(normalized["hp_regen_per_minute"])
	for row in _slot_rows:
		row["box"].queue_free()
	_slot_rows.clear()
	for slot in normalized["defense_slots"]:
		_add_slot_row(slot)
	_refresh_add_button()


# Возвращает настройки в виде, который принимает сервер.
func get_settings() -> Dictionary:
	var slots: Array = []
	for row in _slot_rows:
		var attack_index: int = row["attack"].selected
		slots.append({
			"attack": ATTACK_ORDER[attack_index],
			"damage_min": int(row["damage_min"].value),
			"damage_max": int(row["damage_max"].value),
			"radius_units": float(row["radius"].value),
			"interval_seconds": float(row["interval"].value),
		})
	return SPAWN_RULES.normalize_building_settings({
		"hp": int(_hp_spin.value),
		"hp_regen_per_minute": int(_regen_spin.value),
		"defense_slots": slots,
	})


func slot_count() -> int:
	return _slot_rows.size()


func _on_add_slot_pressed() -> void:
	if _slot_rows.size() >= SPAWN_RULES.MAX_DEFENSE_SLOTS:
		return
	_add_slot_row({"attack": "arrow", "damage_min": 1, "damage_max": 2, "radius_units": 300.0, "interval_seconds": 2.0})
	_refresh_add_button()


func _add_slot_row(slot: Dictionary) -> void:
	var box := VBoxContainer.new()
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var header := HBoxContainer.new()
	var title_label := Label.new()
	title_label.text = "Слот обороны %d" % (_slot_rows.size() + 1)
	title_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(title_label)
	var remove_button := Button.new()
	remove_button.text = "Удалить слот"
	header.add_child(remove_button)
	box.add_child(header)
	var attack := OptionButton.new()
	for attack_id in ATTACK_ORDER:
		attack.add_item(ATTACK_LABELS[attack_id])
	attack.select(maxi(0, ATTACK_ORDER.find(str(slot["attack"]))))
	box.add_child(attack)
	var row := {"box": box, "attack": attack}
	row["damage_min"] = _labeled_spin(box, "Урон минимум", 0, SPAWN_RULES.BUILDING_DAMAGE_MAX, 1, int(slot["damage_min"]))
	row["damage_max"] = _labeled_spin(box, "Урон максимум", 0, SPAWN_RULES.BUILDING_DAMAGE_MAX, 1, int(slot["damage_max"]))
	row["radius"] = _labeled_spin(box, "Радиус атаки (единицы, как у героев; 50 ед. = 1 тайл)", 10, 2000, 10, float(slot["radius_units"]))
	row["interval"] = _labeled_spin(box, "Интервал между выстрелами, с", 0.2, 60, 0.1, float(slot["interval_seconds"]))
	remove_button.pressed.connect(_remove_slot.bind(row))
	_slots_box.add_child(box)
	_slot_rows.append(row)


func _remove_slot(row: Dictionary) -> void:
	_slot_rows.erase(row)
	row["box"].queue_free()
	_refresh_add_button()


func _refresh_add_button() -> void:
	_add_button.disabled = _slot_rows.size() >= SPAWN_RULES.MAX_DEFENSE_SLOTS


func _labeled_spin(parent: Container, caption: String, low: float, high: float, step: float, value: float) -> SpinBox:
	var label := Label.new()
	label.text = caption
	parent.add_child(label)
	var spin := SpinBox.new()
	spin.min_value = low
	spin.max_value = high
	spin.step = step
	spin.value = value
	spin.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(spin)
	return spin
