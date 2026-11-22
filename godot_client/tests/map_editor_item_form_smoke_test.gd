extends Node

const RULES = preload("res://scripts/map_editor_item_form_rules.gd")
const DIALOG_SCRIPT = preload("res://scripts/map_editor_item_form.gd")
const FIXTURE_PATH := "res://tests/map_editor_item_form_fixture.json"
const NO_ICONS_TEXT := "В базе иконок пока нет файлов для этого слота. Положите PNG в assets/item_icons"


class ItemFormEditor extends "res://scripts/map_editor.gd":
	var submitted_item_form: Dictionary = {}
	var submitted_item_action := ""

	func _ready() -> void:
		_mode = "economy"
		_build_ui()

	func _request_item_save(action: String, form: Dictionary) -> void:
		_pending_action = action
		submitted_item_action = action
		submitted_item_form = form.duplicate(true)


var editor: ItemFormEditor
var _failures: Array[String] = []
var _checks := 0
var _fixture: Dictionary = {}
var _known: Array = []


func _ready() -> void:
	call_deferred("_run")


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _run() -> void:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(FIXTURE_PATH))
	_check(parsed is Dictionary, "Фикстура читается как JSON-объект")
	if parsed is Dictionary:
		_fixture = parsed
		_known = _fixture["known_icons"]
		_check_rules()
		_check_validate_cases()
		_check_int_text()
		_check_icon_helpers()
		await _check_dialog()
		await _check_editor_hook()
	_finish()


func _finish() -> void:
	if is_instance_valid(editor):
		editor.free()
	for failure in _failures:
		push_error(failure)
	if _failures.is_empty():
		print("map_editor_item_form_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(0 if _failures.is_empty() else 1)


# Числа из JSON приходят float; сравниваем так, как их записал Python.
func _normalized(value: Variant) -> Variant:
	if value is Dictionary:
		var result := {}
		for key in value:
			result[key] = _normalized(value[key])
		return result
	if value is Array:
		var items: Array = []
		for item in value:
			items.append(_normalized(item))
		return items
	if value is float and is_equal_approx(value, roundf(value)):
		return int(value)
	return value


func _same(actual: Variant, expected: Variant) -> bool:
	return _normalized(actual) == _normalized(expected)


func _check_rules() -> void:
	_check(_same(RULES.default_form(), _fixture["default_form"]), "Значения по умолчанию совпадают с default_form в Python")
	var actual_limits := {
		"MAX_NAME": RULES.MAX_NAME,
		"MAX_STAT": RULES.MAX_STAT,
		"MAX_LEVEL": RULES.MAX_LEVEL,
		"MAX_PERCENT": RULES.MAX_PERCENT,
		"MAX_HP": RULES.MAX_HP,
		"MAX_DAMAGE": RULES.MAX_DAMAGE,
		"MAX_ATTACK_DISTANCE": RULES.MAX_ATTACK_DISTANCE,
		"MAX_AURA_RADIUS": RULES.MAX_AURA_RADIUS,
		"MAX_PRICE": RULES.MAX_PRICE,
		"CUSTOM_ITEM_FIRST_ID": RULES.CUSTOM_ITEM_FIRST_ID,
		"DEFAULT_CRIT_POWER": RULES.DEFAULT_CRIT_POWER,
	}
	_check(_same(actual_limits, _fixture["limits"]), "Ограничения MAX_* совпадают с core/item_form.py")
	_check(_same(RULES.EQUIPMENT_SLOTS, _fixture["slots"]), "Слоты предметов объединяют два слота колец")
	_check(_same(RULES.SLOT_LABELS, _fixture["slot_labels"]), "Подписи слотов как в scenes/item_form_dialog.py")
	_check(
		RULES.SLOT_LABELS.get("ring") == "Кольца"
		and not RULES.EQUIPMENT_SLOTS.has("ring_2")
		and RULES.form_from_item({"equip_slot": "ring_2"})["slot"] == "ring"
		and RULES.validate_form({"name": "Кольцо", "slot": "ring_2"}, _known)["clean"]["slot"] == "ring",
		"Слот колец общий, а старые записи второго слота нормализуются",
	)
	var stat_pairs: Array = []
	for stat in RULES.FORM_STATS:
		stat_pairs.append([stat, RULES.STAT_LABELS[stat]])
	_check(_same(stat_pairs, _fixture["stats"]), "Характеристики и подписи совпадают с mob_modes.STAT_LABELS")
	_check(_same(RULES.SLOT_ICON_PREFIXES, _fixture["slot_icon_prefixes"]), "Префиксы имён иконок по слотам как в core/item_icons.py")
	var table: Array = []
	for column in RULES.field_columns():
		var rows: Array = []
		for spec in column:
			rows.append([spec["key"], spec["label"], spec["kind"], spec["step"], spec["low"], spec["high"]])
		table.append(rows)
	_check(_same(table, _fixture["field_columns"]), "Таблица полей совпадает с COLUMNS из scenes/item_form_dialog.py")


func _check_validate_cases() -> void:
	for entry in _fixture["validate_cases"]:
		var name := str(entry["name"])
		var checked: Dictionary = RULES.validate_form(entry["form"], _known)
		var expected_error := str(entry["error"])
		if expected_error.is_empty():
			_check(
				str(checked["error"]).is_empty() and _same(checked["clean"], entry["clean"]),
				"Принятая форма %s совпадает с validate_form из Python" % name,
			)
		else:
			_check(
				str(checked["error"]) == expected_error,
				"Ошибка %s: Godot «%s», Python «%s»" % [name, checked["error"], expected_error],
			)


func _check_int_text() -> void:
	for entry in _fixture["int_text_cases"]:
		var text := str(entry["text"])
		_check(_same(RULES.parse_int(text), entry["value"]), "Текст %s читается как int() в Python" % JSON.stringify(text))


func _check_icon_helpers() -> void:
	var expected_options: Dictionary = _fixture["icons_for_slot"]
	for slot in _fixture["slots"]:
		_check(
			_same(RULES.icons_for_slot(str(slot), _known), expected_options[str(slot)]),
			"Иконки слота %s как icons_for_slot в Python" % str(slot),
		)
	_check(
		_same(RULES.icon_keys_from_files(PackedStringArray(_fixture["icon_files"])), _known),
		"Ключи иконок из имён файлов совпадают с icon_keys() в Python",
	)
	_check(not RULES.is_known_icon("", _known) and not RULES.is_known_icon(null, _known), "Пустой и null ключ не считаются иконкой")
	var options: Array = RULES.icon_options_for_slot("weapon", _known)
	_check(options[0] == null and options.size() == 1 + RULES.icons_for_slot("weapon", _known).size(), "Первый пункт выбора иконки — «нет»")
	_check(
		RULES.item_subcategory({"name": "Железный меч"}) == "Мечи"
		and RULES.item_subcategory({"icon": "weapon_axe"}) == "Топоры"
		and RULES.item_subcategory({"name": "Незнакомый предмет"}) == "Прочее",
		"Типы предметов определяются по названию или иконке, неизвестные относятся к «Прочее»",
	)
	var categories: Array = RULES.item_categories([
		{"equip_slot": "weapon", "name": "Меч"},
		{"equip_slot": "weapon", "name": "Топор"},
		{"equip_slot": "shield", "name": "Щит"},
	], "weapon")
	_check(_same(categories, ["Мечи", "Топоры"]), "Подкатегории собираются только для выбранного слота")
	var edit_form: Dictionary = RULES.form_from_item({
		"name": "Меч",
		"equip_slot": "weapon",
		"price": 120,
		"icon": "weapon_old_sword",
		"bonuses": {"strength": 3, "hp": 20},
		"effects": {"damage": [4, 8], "requirements": {"level": 2, "agility": 1}, "crit": 5},
	})
	_check(
		edit_form["name"] == "Меч"
		and edit_form["damage_min"] == 4
		and edit_form["damage_max"] == 8
		and edit_form["level"] == 2
		and edit_form["requirements"]["agility"] == 1
		and edit_form["bonuses"]["strength"] == 3
		and edit_form["hp"] == 20
		and edit_form["crit"] == 5,
		"Данные существующего предмета преобразуются в заполненную форму редактирования",
	)


func _check_dialog() -> void:
	var dialog = DIALOG_SCRIPT.new()
	dialog.setup("", _known)
	add_child(dialog)
	await get_tree().process_frame
	_check(_same(dialog.icon_keys(), _known), "Окно получает список иконок")
	_check(_same(dialog.form, RULES.default_form()), "Новое окно начинается с формы по умолчанию")
	var existing_dialog = DIALOG_SCRIPT.new()
	existing_dialog.setup("", _known, {
		"name": "Старый предмет",
		"slot": "weapon",
		"icon": "legacy_icon",
	}, 1000)
	_check(
		existing_dialog._title_label.text == "Настройки предмета"
		and existing_dialog.form["name"] == "Старый предмет"
		and existing_dialog.icon_keys().has("legacy_icon")
		and RULES.validate_form(existing_dialog.form, existing_dialog.icon_keys())["error"].is_empty(),
		"При редактировании сохраняется и принимается прежний ключ иконки без локального PNG",
	)
	existing_dialog.free()
	var saved: Array = []
	var cancels: Array = []
	dialog.save_requested.connect(func(form: Dictionary) -> void: saved.append(form))
	dialog.cancel_requested.connect(func() -> void: cancels.append(true))

	dialog.request_save()
	_check(saved.size() == 1 and saved[0]["name"] == "", "OK без проверки отдаёт форму редактору")

	var name_input: LineEdit = dialog._name_input
	name_input.text = "Меч"
	name_input.text_changed.emit("Меч")
	_check(dialog.form["name"] == "Меч", "Название пишется с клавиатуры в форму")

	var windup: LineEdit = dialog._int_inputs["windup_percent"]
	windup.text = " 12 "
	windup.text_submitted.emit(" 12 ")
	_check(dialog.form["windup_percent"] == 12 and windup.text == "12", "Число с клавиатуры приводится к виду 12")
	windup.text = "abc"
	windup.text_submitted.emit("abc")
	_check(dialog.form["windup_percent"] == "abc", "Нечисловой текст остаётся в форме до проверки")
	dialog.request_save()
	_check(str(saved[saved.size() - 1]["windup_percent"]) == "abc", "OK отдаёт редактору нечисловой текст для проверки")
	windup.text = "0"
	windup.text_submitted.emit("0")

	var move_buttons: Array = dialog._int_steps["move_speed_percent"]
	move_buttons[1].pressed.emit()
	_check(dialog.form["move_speed_percent"] == 5, "Кнопка «+» прибавляет шаг поля")
	for _i in range(40):
		move_buttons[0].pressed.emit()
	_check(dialog.form["move_speed_percent"] == -90, "Кнопка «−» не опускает значение ниже -90")
	for _i in range(60):
		move_buttons[1].pressed.emit()
	_check(dialog.form["move_speed_percent"] == 200, "Кнопка «+» не поднимает значение выше 200")

	var stat_input: LineEdit = dialog._int_inputs["req:strength"]
	stat_input.text = "7"
	stat_input.text_submitted.emit("7")
	_check(dialog.form["requirements"]["strength"] == 7, "Требование из клавиатуры пишется в requirements")
	(dialog._int_steps["bon:intellect"][1] as Button).pressed.emit()
	_check(dialog.form["bonuses"]["intellect"] == 1, "Характеристика предмета меняется кнопкой")

	dialog._slot_next.pressed.emit()
	_check(dialog.form["slot"] == "shield", "Слот «>» идёт по списку слотов Python")
	dialog._slot_prev.pressed.emit()
	dialog._slot_prev.pressed.emit()
	_check(dialog.form["slot"] == "feet" and dialog._slot_label.text == "Обувь", "Слот «<» показывает подпись слота")

	var flag: CheckBox = dialog._flag_inputs["two_handed"]
	flag.button_pressed = true
	_check(dialog.form["two_handed"] == true, "Флажок «Обе руки» пишет двуручный в форму")

	dialog._icon_button.pressed.emit()
	_check(dialog._picker.visible, "Кнопка иконки открывает выбор")
	var options: Array = dialog._picker_options
	_check(options[0] == null and _same(options.slice(1), expected_icons("feet")), "Выбор иконки: «нет» и иконки слота feet")
	_check(not dialog._picker_warning.visible, "Предупреждение о пустой базе скрыто, когда иконки есть")
	var shield_category: Button
	for child in dialog._picker_grid.get_children():
		var category_button := child as Button
		if category_button != null and category_button.text.begins_with("Щиты"):
			shield_category = category_button
			break
	_check(shield_category != null, "Пикер сначала показывает категории иконок")
	shield_category.pressed.emit()
	_check(dialog._picker_stage == "icons" and dialog._picker_back_button.visible, "Категория открывает список иконок и кнопку возврата")
	var esc := InputEventKey.new()
	esc.keycode = KEY_ESCAPE
	esc.physical_keycode = KEY_ESCAPE
	esc.pressed = true
	dialog._input(esc)
	_check(not dialog._picker.visible and cancels.is_empty(), "ESC сначала закрывает выбор иконки и не отменяет окно")
	dialog._icon_button.pressed.emit()
	shield_category = null
	for child in dialog._picker_grid.get_children():
		var category_button := child as Button
		if category_button != null and category_button.text.begins_with("Щиты"):
			shield_category = category_button
			break
	if shield_category != null:
		shield_category.pressed.emit()
	var shield_index: int = dialog._icon_options_by_category["Щиты"].find("shield_oak")
	(dialog._picker_grid.get_child(shield_index) as Button).pressed.emit()
	_check(dialog.form["icon"] == "shield_oak" and dialog._icon_button.text == "shield_oak", "Выбор иконки пишет ключ в форму")
	_check(not dialog._picker.visible, "После выбора иконки окно выбора закрывается")
	dialog._icon_button.pressed.emit()
	var right_click := InputEventMouseButton.new()
	right_click.button_index = MOUSE_BUTTON_RIGHT
	right_click.pressed = true
	dialog._on_picker_backdrop_input(right_click)
	_check(dialog._picker.visible, "Правый клик по фону выбора иконки его не закрывает, как в Python")
	var left_click := InputEventMouseButton.new()
	left_click.button_index = MOUSE_BUTTON_LEFT
	left_click.pressed = true
	dialog._on_picker_backdrop_input(left_click)
	_check(not dialog._picker.visible, "Левый клик по фону закрывает выбор иконки")
	var right_open := InputEventMouseButton.new()
	right_open.button_index = MOUSE_BUTTON_RIGHT
	right_open.pressed = true
	dialog._on_icon_button_gui_input(right_open)
	_check(dialog._picker.visible, "Правый клик по полю иконки открывает меню направлений")
	dialog._picker_back_button.pressed.emit()
	_check(dialog._picker_stage == "categories", "Кнопка «Назад» возвращает к направлениям иконок")
	dialog._close_icon_picker()

	dialog.set_message("Укажите название предмета")
	_check(dialog.message_text() == "Укажите название предмета", "Сообщение об ошибке показывается в окне")
	dialog._input(esc)
	_check(cancels.size() == 1, "ESC без открытого выбора отменяет окно")
	dialog.request_cancel()
	_check(cancels.size() == 2, "Кнопка «Отмена» сообщает редактору об отмене")

	var empty_dialog = DIALOG_SCRIPT.new()
	empty_dialog.setup("", [])
	empty_dialog._icon_button.pressed.emit()
	_check(empty_dialog._picker_warning.visible and empty_dialog._picker_warning.text == NO_ICONS_TEXT, "Без файлов иконок показывается подсказка Python")
	empty_dialog.free()
	dialog.queue_free()
	await get_tree().process_frame


func expected_icons(slot: String) -> Array:
	return _fixture["icons_for_slot"][slot]


func _check_editor_hook() -> void:
	editor = ItemFormEditor.new()
	editor.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(editor)
	await get_tree().process_frame
	_check(editor._add_item_button != null and editor._add_item_button.text == "+ Добавить предмет", "Кнопка «+ Добавить предмет» есть в редакторе")
	_check(editor._inventory_button != null and editor._inventory_button.text == "Инвентарь", "Кнопка инвентаря находится на панели инструментов")
	editor._open_item_form()
	var first = editor._item_form_dialog
	_check(is_instance_valid(first), "Кнопка открывает окно «Новый предмет»")
	editor._open_item_form()
	_check(editor._item_form_dialog == first, "Повторное открытие не создаёт второе окно")

	var undo_key := InputEventKey.new()
	undo_key.keycode = KEY_Z
	undo_key.physical_keycode = KEY_Z
	undo_key.ctrl_pressed = true
	undo_key.pressed = true
	editor._status.text = ""
	editor._unhandled_key_input(undo_key)
	_check(editor._status.text.is_empty(), "Пока окно открыто, горячие клавиши редактора не срабатывают")

	first.request_save()
	_check(first.message_text() == "Укажите название предмета", "Пустое название: ошибка показана в окне, как в Python")
	_check(is_instance_valid(editor._item_form_dialog) and editor._new_items.is_empty(), "Ошибка не закрывает окно и ничего не сохраняет")

	first._name_input.text = "Меч"
	first._name_input.text_changed.emit("Меч")
	first._int_inputs["price"].text = "1500"
	first._int_inputs["price"].text_submitted.emit("1500")
	first._int_inputs["damage_max"].text = "9"
	first._int_inputs["damage_max"].text_submitted.emit("9")
	first._int_inputs["hp"].text = "1_000"
	first._int_inputs["hp"].text_submitted.emit("1_000")
	first._int_inputs["attack_range"].text = "8"
	first._int_inputs["attack_range"].text_submitted.emit("8")
	first._int_inputs["attack_area"].text = "3"
	first._int_inputs["attack_area"].text_submitted.emit("3")
	first._int_inputs["lifesteal_percent"].text = "12"
	first._int_inputs["lifesteal_percent"].text_submitted.emit("12")
	first._int_inputs["aura_radius_px"].text = "180"
	first._int_inputs["aura_radius_px"].text_submitted.emit("180")
	first._int_inputs["aura_lifesteal_percent"].text = "20"
	first._int_inputs["aura_lifesteal_percent"].text_submitted.emit("20")
	var aura_type: OptionButton = first._choice_inputs["aura_type"]
	for index in range(aura_type.item_count):
		if aura_type.get_item_metadata(index) == "vampirism":
			aura_type.select(index)
			aura_type.item_selected.emit(index)
			break
	var aura_target: OptionButton = first._choice_inputs["aura_target"]
	for index in range(aura_target.item_count):
		if aura_target.get_item_metadata(index) == "enemies":
			aura_target.select(index)
			aura_target.item_selected.emit(index)
			break
	first.request_save()
	_check(editor._pending_action == "create_item", "Принятая форма отправляется на сервер")
	_check(
		editor.submitted_item_form.get("lifesteal_percent") == 12
		and editor.submitted_item_form.get("aura_type") == "vampirism"
		and editor.submitted_item_form.get("aura_target") == "enemies"
		and editor.submitted_item_form.get("aura_radius_px") == 180
		and editor.submitted_item_form.get("aura_lifesteal_percent") == 20,
		"В сетевой запрос входят вампиризм и параметры ауры",
	)
	_check(is_instance_valid(editor._item_form_dialog) and editor._new_items.is_empty(), "Форма остаётся открытой до ответа сервера")
	editor._on_api_completed(true, {
		"item": {
			"id": 1001,
			"name": "Меч",
			"item_type": "equipment",
			"equip_slot": "weapon",
			"effects": {"attack_range": 8, "attack_area": 3},
			"bonuses": {"hp": 1000},
		},
	})
	_check(editor._item_form_dialog == null, "После ответа сервера окно закрывается")
	_check(editor._new_items.size() == 1, "Созданный сервером предмет добавляется в состояние редактора")
	var item: Dictionary = editor._new_items[0] if editor._new_items.size() == 1 else {}
	_check(editor._inventory_items.size() == 1 and editor._spawn_item_catalog.size() == 1, "Новый предмет попадает в каталог и список появления")
	_check(
		editor._status.text == editor.ITEM_SAVED_STATUS % ["Меч", "Economy"],
		"Новый предмет подтверждается в статусе",
	)
	editor._open_inventory()
	editor._select_inventory_slot("weapon")
	var category_buttons := editor._inventory_list.get_children()
	_check(
		category_buttons.size() == 1 and (category_buttons[0] as Button).text.begins_with("Мечи"),
		"Инвентарь показывает типы предметов внутри выбранного слота",
	)
	var double_click := InputEventMouseButton.new()
	double_click.button_index = MOUSE_BUTTON_LEFT
	double_click.pressed = true
	double_click.double_click = true
	editor._on_inventory_item_icon_input(double_click, 20)
	_check(editor._item_form_dialog == null, "Встроенные предметы нельзя открыть для редактирования")
	editor._on_inventory_item_icon_input(double_click, 1001)
	var edit_dialog = editor._item_form_dialog
	_check(
		edit_dialog != null
		and edit_dialog.form["name"] == "Меч"
		and edit_dialog._title_label.text == "Настройки предмета",
		"Двойной клик по пользовательскому предмету открывает заполненную форму",
	)
	edit_dialog._name_input.text = "Меч усиленный"
	edit_dialog._name_input.text_changed.emit("Меч усиленный")
	edit_dialog.request_save()
	_check(
		editor.submitted_item_action == "edit_item"
		and editor._pending_action == "edit_item"
		and editor._editing_item_id == 1001,
		"Сохранение существующего пользовательского предмета отправляется как редактирование",
	)
	editor._on_api_completed(true, {
		"item": {
			"id": 1001,
			"name": "Меч усиленный",
			"item_type": "equipment",
			"equip_slot": "weapon",
			"effects": {},
			"bonuses": {},
		},
	})
	_check(editor._inventory_items.size() == 1 and editor._inventory_items[0]["name"] == "Меч усиленный", "Редактирование обновляет запись без дубликата")
	_check(
		item.get("name") == "Меч" and item.get("id") == 1001 and item.get("effects", {}).get("attack_range") == 8,
		"В состоянии редактора лежит ответ сервера с новым предметом",
	)
	_check(editor._status.text == "Предмет «Меч усиленный» обновлён.", "Изменённый предмет подтверждается в статусе")
	_check(editor._inventory_button.text == "Инвентарь · 1", "Счётчик инвентаря учитывает созданную экипировку")
	editor._open_inventory()
	editor._select_inventory_slot("weapon")
	editor._select_inventory_category("Мечи")
	_check(editor._inventory_list.get_child_count() == 1, "Инвентарь показывает предмет")
	var inventory_icon_button := editor._inventory_list.get_child(0).get_child(0) as Button
	_check(
		inventory_icon_button.custom_minimum_size == Vector2(66, 62) * editor.EDITOR_UI_SCALE,
		"Иконка в инвентаре имеет размер слота карточки",
	)
	editor._inventory_items.append({
		"id": 1002,
		"name": "Кольцо",
		"item_type": "equipment",
		"equip_slot": "ring_2",
	})
	editor._inventory_items.append({
		"id": 1003,
		"name": "Золотое кольцо",
		"item_type": "equipment",
		"equip_slot": "ring",
	})
	_check(
		editor._inventory_count_for_slot("ring") == 2
		and editor._inventory_count_for_slot("ring_2") == 0
		and RULES.item_categories(editor._inventory_items, "ring") == ["Кольца"],
		"Каталог объединяет кольца из обоих старых слотов",
	)
	editor._inventory_dialog.hide()
	editor._status.text = ""
	editor._unhandled_key_input(undo_key)
	_check(editor._status.text == "Нет действий для отмены.", "После закрытия окна горячие клавиши снова работают")

	editor._open_item_form()
	editor._item_form_dialog.request_cancel()
	_check(editor._item_form_dialog == null and editor._new_items.size() == 1, "Отмена закрывает окно и ничего не добавляет")

	var mob_stub := Control.new()
	editor._mob_profile_dialog = mob_stub
	editor._open_item_form()
	_check(editor._item_form_dialog == null, "Открытый профиль моба не даёт открыть окно предмета")
	editor._mob_profile_dialog = null
	mob_stub.free()
