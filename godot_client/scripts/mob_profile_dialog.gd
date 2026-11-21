extends Control

signal save_requested(settings: Dictionary)
signal cancel_requested

const Rules := preload("res://scripts/mob_profile_rules.gd")
const Style := preload("res://scripts/mob_profile_style.gd")
const PatrolGrid := preload("res://scripts/mob_patrol_grid.gd")
const EquipmentPanel := preload("res://scripts/mob_equipment_panel.gd")

# Размеры как в окне «Новый предмет» редактора: колонки фиксированной ширины, подписи 12 px, контролы 28 px
const PANEL_WIDTH := 920.0
const COLUMN_WIDTH := 286.0
const COLUMN_GAP := 12
const ROW_GAP := 6
const LABEL_WIDTH := 160.0
const INPUT_WIDTH := 52.0
const LABEL_FONT_SIZE := 12
const STATE_BUTTON_FONT_SIZE := 12
const STEP_SIZE := Vector2(28, 28)
const PATROL_CELL_SIZE := 15
# Короткие подписи: единицы и пояснения показываются в подсказке при наведении
const FIELD_HINTS := {
	"move_speed": "скорость передвижения моба",
	"windup": "время замаха до удара",
	"backswing": "время отката после удара",
	"max_hp": "максимальное здоровье",
	"max_mp": "максимальная мана",
	"attack_range": "дальность удара; 100 ед. = 1 тайл",
	"area_radius": "радиус взрыва мага: урон героям в радиусе от точки попадания",
	"reward_xp": "делится между героями по доле урона",
	"reward_copper": "монеты при смерти, делятся по доле урона",
	"aggro_tiles": "радиус агрессии (Tower и Economy)",
	"respawn_seconds": "время до возрождения (Tower и Economy)",
}
const STAT_HINTS := {
	"strength": "урон удара",
	"agility": "уворот и скорость хода",
	"intuition": "критический удар и скорость замаха",
	"wisdom": "не используется в бою Front Line",
	"intellect": "не используется в бою Front Line",
	"endurance": "броня и здоровье",
}
const FRONT_LINE_RESOURCE_DEFAULTS := {"max_hp": 48, "max_mp": 18, "attack_range": 100, "area_radius": 50}
# Поля Front Line, которые хранятся целыми числами
const INTEGER_RESOURCE_KEYS := ["max_hp", "max_mp", "attack_range", "area_radius"]
const MAIN_FIELDS := [
	{"key": "move_speed", "label": "Скорость передвижения", "unit": "px/с", "step": 5.0},
	{"key": "windup", "label": "Скорость замаха", "unit": "с", "step": 0.05},
	{"key": "backswing", "label": "Скорость отката", "unit": "с", "step": 0.05},
	{"key": "aggro_tiles", "label": "Агрессия", "unit": "тайлов", "step": 0.5},
	{"key": "respawn_seconds", "label": "Респаун", "unit": "", "step": 5.0},
	{"key": "reward_copper", "label": "Монеты", "unit": "мед.", "step": 5.0},
]
const XP_FIELD := {"key": "reward_xp", "label": "Опыт", "unit": "", "step": 5.0}
const PATROL_PRESETS := [["clear", "Очистить"], ["circle3", "Круг 3"], ["circle6", "Круг 6"]]
# Во Front Line эти параметры не используются: затемняются и не активны
const FRONT_LINE_INACTIVE_FIELDS := ["aggro_tiles", "respawn_seconds", "max_mp"]
const FRONT_LINE_INACTIVE_STATS := ["wisdom", "intellect"]
const INACTIVE_ALPHA := 0.35
# Урон моба (Front Line): база вручную, фактический = база + 2 за очко силы (world_stats.DAMAGE_PER_STRENGTH)
const DAMAGE_PER_STRENGTH := 2
const DAMAGE_FIELDS := ["damage_min", "damage_max"]
const DAMAGE_LIMIT := 1000
const DAMAGE_LABEL_WIDTH := 72.0
const DAMAGE_INPUT_WIDTH := 100.0

var rules: Dictionary = {}
var mob_name := ""
var mode := ""
var attack_style := "warrior"
var attack_style_buttons: Dictionary = {}
var level := 1
var state := "aggressive"
var stats: Dictionary = {}
var equipment: Dictionary = {}
var values: Dictionary = {}
var dropped_equipment_count := 0

var field_rows: Dictionary = {}
var field_inputs: Dictionary = {}
var field_minus: Dictionary = {}
var field_plus: Dictionary = {}
var stat_inputs: Dictionary = {}
var stat_minus: Dictionary = {}
var stat_plus: Dictionary = {}
var state_buttons: Dictionary = {}
var level_input: LineEdit
var level_minus: Button
var level_plus: Button
var patrol_grid: PatrolGrid
var equipment_panel: EquipmentPanel
var panel: PanelContainer
var save_button: Button
var cancel_button: Button

var _equipment_items: Array = []
var _equipment_loaded := false
var _free_label: Label
var _state_hint: Label
var _endurance_hint: Label
var _patrol_count_label: Label
var _equipment_count_label: Label
var _message_label: Label
var _patrol_presets: HBoxContainer
var _equipment_button: Button
var _damage_inputs: Dictionary = {}
var _damage_actual: Dictionary = {}


func _init() -> void:
	theme = Style.make_theme()


# options: mode_name, equipment_items (нет ключа — список не загружен), note, integration_note.
func setup(name_text: String, mode_id: String, settings: Dictionary, options: Dictionary = {}) -> void:
	mob_name = name_text
	mode = mode_id
	rules = Rules.rules_for_mode(mode_id)
	_load_settings(settings)
	_equipment_loaded = options.has("equipment_items")
	_equipment_items = options.get("equipment_items", [])
	_build_ui(str(options.get("mode_name", mode_id)), str(options.get("integration_note", "")))
	patrol_grid.set_offsets(settings.get("patrol", []) if settings.get("patrol") is Array else [])
	_refresh_all()
	set_message(str(options.get("note", "")))


func free_points() -> int:
	return Rules.free_points(rules, level, stats)


func total_points() -> int:
	return Rules.total_free_points(rules, level)


func message_text() -> String:
	return _message_label.text


func set_message(text: String, color: Color = Style.WARN_COLOR) -> void:
	_message_label.text = text
	_message_label.add_theme_color_override("font_color", color)


func set_busy(busy: bool) -> void:
	save_button.disabled = busy
	if busy:
		set_message("Сохраняем профиль на сервере…", Style.DIM_COLOR)


func _integer_min(key: String) -> int:
	return 1 if key == "max_hp" else 0


func _integer_max(key: String) -> int:
	return Rules.ATTACK_RANGE_MAX if key == "attack_range" else 9223372036854775806


func set_field_value(key: String, value: float) -> void:
	if key in INTEGER_RESOURCE_KEYS:
		set_integer_field_value(key, roundi(value))
		return
	values[key] = Rules.clamp_field(key, value)
	_refresh_field(key)


func set_integer_field_value(key: String, value: int) -> void:
	values[key] = clampi(value, _integer_min(key), _integer_max(key))
	_refresh_field(key)


func step_field(key: String, direction: int) -> void:
	if key in INTEGER_RESOURCE_KEYS:
		set_integer_field_value(
			key,
			int(values[key]) + direction * int(_field_step(key)),
		)
	else:
		set_field_value(key, float(values[key]) + direction * _field_step(key))


func set_level(value: int) -> void:
	level = clampi(value, int(rules["level_min"]), int(rules["level_cap"]))
	if not bool(rules.get("unlimited", false)):
		stats["endurance"] = Rules.endurance_for_level(rules, level)
	_trim_stats_to_budget()
	_refresh_level_and_stats()


func step_level(direction: int) -> void:
	set_level(level + direction)


func set_stat_value(stat: String, value: int) -> void:
	if (stat == "endurance" and not bool(rules.get("unlimited", false))) or not stats.has(stat):
		return
	if bool(rules.get("unlimited", false)) and value == 9223372036854775807 \
		and int(stats[stat]) == 9223372036854775807:
		return
	if bool(rules.get("unlimited", false)):
		stats[stat] = maxi(value, int(rules["stat_min"]))
	else:
		var highest := int(stats[stat]) + maxi(0, free_points())
		stats[stat] = clampi(value, int(rules["stat_min"]), highest)
	_refresh_level_and_stats()


func step_stat(stat: String, direction: int) -> void:
	if stats.has(stat):
		set_stat_value(stat, int(stats[stat]) + direction)


func set_state(state_id: String) -> void:
	if not state_id in Rules.STATES:
		return
	state = state_id
	_refresh_states()


func set_attack_style(style_id: String) -> void:
	if not style_id in Rules.ATTACK_STYLE_IDS:
		return
	attack_style = style_id
	_apply_mode_availability()


func open_equipment() -> void:
	_commit_all_inputs()
	equipment_panel.open(stats, level)


func collect_settings() -> Dictionary:
	var settings := {}
	for spec in _settings_fields():
		var key := str(spec["key"])
		settings[key] = int(values[key]) if key in INTEGER_RESOURCE_KEYS \
			else Rules.field_output(key, float(values[key]))
	if mode == "front_line":
		for key in DAMAGE_FIELDS:
			settings[key] = int(values[key])
		settings["attack_style"] = attack_style
	settings["state"] = state
	settings["level"] = level
	var stat_values := {}
	for entry in rules["stats"]:
		stat_values[str(entry[0])] = int(stats[str(entry[0])])
	settings["stats"] = stat_values
	var worn := {}
	for slot in Rules.EQUIPMENT_SLOTS:
		worn[slot] = equipment.get(slot)
	settings["equipment"] = worn
	settings["patrol"] = patrol_grid.offsets()
	return settings


func request_save() -> void:
	_commit_all_inputs()
	var cleaned := Rules.drop_unfit_equipment(equipment, _equipment_items, stats, level)
	dropped_equipment_count = 0
	for slot in cleaned:
		if equipment.get(slot) != cleaned[slot]:
			dropped_equipment_count += 1
			equipment[slot] = cleaned[slot]
	_refresh_equipment_count()
	var settings := collect_settings()
	var problem := Rules.validate_settings(rules, settings)
	if not problem.is_empty():
		set_message(problem)
		return
	set_message("")
	save_requested.emit(settings)


func request_cancel() -> void:
	cancel_requested.emit()


func _input(event: InputEvent) -> void:
	if not is_visible_in_tree():
		return
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_ESCAPE:
		get_viewport().set_input_as_handled()
		if equipment_panel.visible:
			equipment_panel.handle_cancel()
		else:
			request_cancel()
		return
	if event is InputEventMouseButton and event.pressed and not equipment_panel.visible:
		var direction := 0
		if event.button_index == MOUSE_BUTTON_WHEEL_UP:
			direction = 1
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			direction = -1
		if direction == 0:
			return
		for key in field_rows:
			var row: Control = field_rows[key]
			if row.get_global_rect().has_point(event.position):
				_commit_all_inputs()
				step_field(str(key), direction)
				get_viewport().set_input_as_handled()
				return


func _load_settings(settings: Dictionary) -> void:
	values.clear()
	for spec in _settings_fields():
		var key := str(spec["key"])
		var raw: Variant = settings.get(key)
		if key in INTEGER_RESOURCE_KEYS:
			var default_value := int(FRONT_LINE_RESOURCE_DEFAULTS[key])
			var value := int(raw) if raw is int or raw is float else default_value
			values[key] = clampi(value, _integer_min(key), _integer_max(key))
		else:
			values[key] = Rules.clamp_field(
				key,
				float(raw) if raw is float or raw is int else float(Rules.LIMITS[key][0]),
			)
	for key in DAMAGE_FIELDS:
		var raw_damage: Variant = settings.get(key)
		values[key] = clampi(int(raw_damage) if raw_damage is float or raw_damage is int else 0, 0, DAMAGE_LIMIT)
	var level_min := int(rules["level_min"])
	var raw_level: Variant = settings.get("level")
	level = clampi(
		int(raw_level) if raw_level is float or raw_level is int else level_min,
		level_min,
		int(rules["level_cap"]),
	)
	attack_style = str(settings.get("attack_style", "warrior"))
	if not attack_style in Rules.ATTACK_STYLE_IDS:
		attack_style = "warrior"
	state = str(settings.get("state", "aggressive"))
	if not state in Rules.STATES:
		state = "aggressive"
	var loaded_stats: Variant = settings.get("stats")
	stats = {}
	for entry in rules["stats"]:
		var stat := str(entry[0])
		var raw_stat: Variant = loaded_stats.get(stat) if loaded_stats is Dictionary else null
		var value := int(raw_stat) if raw_stat is float or raw_stat is int else 0
		stats[stat] = maxi(value, int(rules["stat_min"]))
	if not bool(rules.get("unlimited", false)):
		stats["endurance"] = Rules.endurance_for_level(rules, level)
	_trim_stats_to_budget()
	var loaded_equipment: Variant = settings.get("equipment")
	equipment = {}
	for slot in Rules.EQUIPMENT_SLOTS:
		var raw_item: Variant = loaded_equipment.get(slot) if loaded_equipment is Dictionary else null
		var item_id := int(raw_item) if raw_item is float or raw_item is int else 0
		equipment[slot] = item_id if item_id > 0 else null


func _settings_fields() -> Array:
	var result: Array = MAIN_FIELDS.duplicate()
	result.append(XP_FIELD)
	if mode == "front_line":
		result.append_array(Rules.FRONT_LINE_RESOURCE_FIELDS)
	return result


# Лишние очки снимаются с последних характеристик, как при смене уровня в игре.
func _trim_stats_to_budget() -> void:
	if bool(rules.get("unlimited", false)):
		return
	var order := Rules.allocatable_stats(rules)
	order.reverse()
	for stat in order:
		var excess := -free_points()
		if excess <= 0:
			return
		var removable := int(stats[stat]) - int(rules["stat_min"])
		stats[stat] = int(stats[stat]) - mini(excess, removable)


func _field_step(key: String) -> float:
	if key == str(XP_FIELD["key"]):
		return float(XP_FIELD["step"])
	for spec in Rules.FRONT_LINE_RESOURCE_FIELDS:
		if str(spec["key"]) == key:
			return float(spec["step"])
	for spec in MAIN_FIELDS:
		if str(spec["key"]) == key:
			return float(spec["step"])
	return 1.0


func _build_ui(mode_name: String, integration_note: String) -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var shade := ColorRect.new()
	shade.color = Style.SHADE_COLOR
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	shade.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(shade)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(center)
	panel = PanelContainer.new()
	panel.custom_minimum_size.x = PANEL_WIDTH
	panel.mouse_filter = Control.MOUSE_FILTER_STOP
	center.add_child(panel)
	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 18)
	margin.add_theme_constant_override("margin_right", 18)
	margin.add_theme_constant_override("margin_top", 12)
	margin.add_theme_constant_override("margin_bottom", 12)
	panel.add_child(margin)
	var outer := VBoxContainer.new()
	outer.add_theme_constant_override("separation", 8)
	margin.add_child(outer)
	outer.add_child(Style.make_label(
		"Параметры: %s  ·  режим «%s»" % [mob_name, mode_name],
		Style.TEXT_COLOR,
		Style.TITLE_FONT_SIZE,
	))
	outer.add_child(_wrapped_label(
		"Параметры относятся к виду моба: их получают все такие мобы во всех мирах режима",
		Style.DIM_COLOR,
		Style.SMALL_FONT_SIZE,
	))
	var body := HBoxContainer.new()
	body.add_theme_constant_override("separation", COLUMN_GAP)
	outer.add_child(body)
	var combat := _new_column()
	var stats := _new_column()
	var patrol := _new_column()
	body.add_child(combat)
	body.add_child(stats)
	body.add_child(patrol)
	_build_combat_column(combat)
	_build_stats_column(stats)
	_build_patrol_column(patrol, integration_note)
	_build_footer(outer)
	equipment_panel = EquipmentPanel.new()
	equipment_panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	equipment_panel.setup(mob_name, rules, equipment, _equipment_items, _equipment_loaded)
	equipment_panel.closed.connect(_refresh_equipment_count)
	add_child(equipment_panel)
	_apply_mode_availability()


func _new_column() -> VBoxContainer:
	var column := VBoxContainer.new()
	column.custom_minimum_size.x = COLUMN_WIDTH
	column.add_theme_constant_override("separation", ROW_GAP)
	return column


func _section_header(text: String) -> Label:
	return Style.make_label(text, Style.ACTIVE_COLOR, Style.HEADER_FONT_SIZE)


func _field_spec(key: String) -> Dictionary:
	if key == str(XP_FIELD["key"]):
		return XP_FIELD
	for spec in MAIN_FIELDS:
		if str(spec["key"]) == key:
			return spec
	for spec in Rules.FRONT_LINE_RESOURCE_FIELDS:
		if str(spec["key"]) == key:
			return spec
	return {}


# Бой и награда: скорости, ресурсы (во Front Line), опыт и монеты.
func _build_combat_column(column: VBoxContainer) -> void:
	column.add_child(_section_header("Бой"))
	for key in ["move_speed", "windup", "backswing"]:
		_add_field_row(column, _field_spec(key))
	if mode == "front_line":
		for spec in Rules.FRONT_LINE_RESOURCE_FIELDS:
			if str(spec["key"]) != "area_radius":
				_add_field_row(column, spec)
	column.add_child(_spacer(6))
	column.add_child(_section_header("Награда"))
	_add_field_row(column, XP_FIELD)
	_add_field_row(column, _field_spec("reward_copper"))
	column.add_child(_spacer(4))
	column.add_child(_section_header("Поведение"))
	_add_field_row(column, _field_spec("aggro_tiles"))
	_add_field_row(column, _field_spec("respawn_seconds"))
	var state_row := HBoxContainer.new()
	state_row.add_theme_constant_override("separation", 6)
	column.add_child(state_row)
	for state_id in Rules.STATES:
		var button := Style.make_button(str(Rules.STATE_LABELS[state_id]), Vector2(0, STEP_SIZE.y + 4))
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.add_theme_font_size_override("font_size", STATE_BUTTON_FONT_SIZE)
		button.pressed.connect(set_state.bind(state_id))
		state_row.add_child(button)
		state_buttons[state_id] = button
	_state_hint = _wrapped_label("", Style.DIM_COLOR, Style.SMALL_FONT_SIZE)
	column.add_child(_state_hint)


# Характеристики (уровень и шесть значений) и поведение моба.
func _build_stats_column(column: VBoxContainer) -> void:
	var header := HBoxContainer.new()
	header.add_theme_constant_override("separation", 10)
	column.add_child(header)
	header.add_child(_section_header("Характеристики"))
	_free_label = Style.make_label("", Style.DIM_COLOR, Style.SMALL_FONT_SIZE)
	_free_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	header.add_child(_free_label)
	_add_level_row(column)
	for stat_id in rules["stats"]:
		column.add_child(_make_stat_cell(str(stat_id[0])))
	_endurance_hint = Style.make_label("", Style.DIM_COLOR, Style.SMALL_FONT_SIZE)
	column.add_child(_endurance_hint)
	if mode == "front_line":
		_add_damage_block(column)
		_add_attack_style_block(column)


# Характер боя и радиус урона мага: в колонке характеристик, чтобы колонка «Бой» не стала выше окна.
func _add_attack_style_block(column: VBoxContainer) -> void:
	column.add_child(_spacer(4))
	column.add_child(_section_header("Характер боя"))
	var style_row := HBoxContainer.new()
	style_row.add_theme_constant_override("separation", 6)
	column.add_child(style_row)
	for style_entry in Rules.ATTACK_STYLES:
		var style_id := str(style_entry[0])
		var style_button := Style.make_button(str(style_entry[1]), Vector2(0, STEP_SIZE.y + 4))
		style_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		style_button.pressed.connect(set_attack_style.bind(style_id))
		style_row.add_child(style_button)
		attack_style_buttons[style_id] = style_button
	for spec in Rules.FRONT_LINE_RESOURCE_FIELDS:
		if str(spec["key"]) == "area_radius":
			_add_field_row(column, spec)


# Патруль (сетка и пресеты), экипировка и примечание.
func _build_patrol_column(column: VBoxContainer, integration_note: String) -> void:
	var header := HBoxContainer.new()
	header.add_theme_constant_override("separation", 10)
	column.add_child(header)
	header.add_child(_section_header("Патруль"))
	_patrol_count_label = Style.make_label("", Style.DIM_COLOR, Style.SMALL_FONT_SIZE)
	_patrol_count_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	header.add_child(_patrol_count_label)
	patrol_grid = PatrolGrid.new()
	patrol_grid.set_cell_size(PATROL_CELL_SIZE)
	patrol_grid.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	patrol_grid.changed.connect(_refresh_patrol_count)
	column.add_child(patrol_grid)
	_patrol_presets = HBoxContainer.new()
	_patrol_presets.add_theme_constant_override("separation", 6)
	column.add_child(_patrol_presets)
	for preset in PATROL_PRESETS:
		var button := Style.make_button(str(preset[1]), Vector2(0, STEP_SIZE.y))
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.pressed.connect(patrol_grid.apply_preset.bind(str(preset[0])))
		_patrol_presets.add_child(button)
	column.add_child(_wrapped_label(
		"Жёлтый крест — точка появления моба",
		Style.DIM_COLOR,
		Style.SMALL_FONT_SIZE,
	))
	column.add_child(_spacer(8))
	column.add_child(_section_header("Экипировка"))
	var equipment_row := HBoxContainer.new()
	equipment_row.add_theme_constant_override("separation", 10)
	column.add_child(equipment_row)
	var open_button := Style.make_button("Открыть экипировку", Vector2(0, STEP_SIZE.y + 4))
	open_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	open_button.pressed.connect(open_equipment)
	_equipment_button = open_button
	equipment_row.add_child(open_button)
	_equipment_count_label = Style.make_label("", Style.DIM_COLOR, Style.SMALL_FONT_SIZE)
	_equipment_count_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	equipment_row.add_child(_equipment_count_label)
	if not integration_note.is_empty():
		column.add_child(_wrapped_label(integration_note, Style.WARN_COLOR, Style.SMALL_FONT_SIZE))


func _add_level_row(column: VBoxContainer) -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", ROW_GAP)
	column.add_child(row)
	row.add_child(_row_label("Уровень", LABEL_WIDTH))
	var widgets := _add_stepper(row, INPUT_WIDTH)
	level_minus = widgets["minus"]
	level_input = widgets["input"]
	level_plus = widgets["plus"]
	level_minus.pressed.connect(_on_level_step.bind(-1))
	level_plus.pressed.connect(_on_level_step.bind(1))
	level_input.text_submitted.connect(_on_level_submitted)
	level_input.focus_exited.connect(_commit_level)


func _build_footer(outer: VBoxContainer) -> void:
	var footer := HBoxContainer.new()
	footer.add_theme_constant_override("separation", 14)
	outer.add_child(footer)
	save_button = Style.make_button("Сохранить изменения", Vector2(200, 34))
	var save_border := Style.SAVE_COLOR.lightened(0.25)
	save_button.add_theme_stylebox_override("normal", Style.flat(Style.SAVE_COLOR, save_border))
	save_button.add_theme_stylebox_override("hover", Style.flat(Style.SAVE_HOVER_COLOR, save_border))
	save_button.add_theme_stylebox_override("pressed", Style.flat(Style.SAVE_COLOR.darkened(0.15), save_border))
	save_button.add_theme_stylebox_override(
		"disabled",
		Style.flat(Style.SAVE_COLOR.darkened(0.5), Style.SAVE_COLOR),
	)
	save_button.pressed.connect(request_save)
	footer.add_child(save_button)
	cancel_button = Style.make_button("Отмена", Vector2(120, 34))
	cancel_button.pressed.connect(request_cancel)
	footer.add_child(cancel_button)
	_message_label = Style.make_label("", Style.WARN_COLOR, Style.SMALL_FONT_SIZE)
	_message_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_message_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_message_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	footer.add_child(_message_label)


# Строка «подпись — кнопки −/+ — поле»: единица измерения и пояснение в подсказке.
func _add_field_row(parent: Container, spec: Dictionary) -> void:
	var key := str(spec["key"])
	var hint := _field_hint(spec)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", ROW_GAP)
	parent.add_child(row)
	var label := _row_label(str(spec["label"]), LABEL_WIDTH)
	label.tooltip_text = hint
	row.add_child(label)
	var widgets := _add_stepper(row, INPUT_WIDTH)
	var minus: Button = widgets["minus"]
	var input: LineEdit = widgets["input"]
	var plus: Button = widgets["plus"]
	input.tooltip_text = hint
	minus.pressed.connect(_on_field_step.bind(key, -1))
	plus.pressed.connect(_on_field_step.bind(key, 1))
	input.text_submitted.connect(_on_field_submitted.bind(key))
	input.focus_exited.connect(_commit_field.bind(key))
	field_rows[key] = row
	field_inputs[key] = input
	field_minus[key] = minus
	field_plus[key] = plus


func _field_hint(spec: Dictionary) -> String:
	var description := str(FIELD_HINTS.get(str(spec["key"]), ""))
	var unit := str(spec.get("unit", ""))
	if unit.is_empty():
		return description
	return "%s (%s)" % [description, unit] if not description.is_empty() else unit


func _make_stat_cell(stat: String) -> HBoxContainer:
	var cell := HBoxContainer.new()
	cell.add_theme_constant_override("separation", ROW_GAP)
	var label := _row_label(Rules.stat_label(rules, stat), LABEL_WIDTH)
	label.tooltip_text = str(STAT_HINTS.get(stat, ""))
	cell.add_child(label)
	var widgets := _add_stepper(cell, INPUT_WIDTH)
	var minus: Button = widgets["minus"]
	var input: LineEdit = widgets["input"]
	var plus: Button = widgets["plus"]
	input.tooltip_text = label.tooltip_text
	minus.pressed.connect(_on_stat_step.bind(stat, -1))
	plus.pressed.connect(_on_stat_step.bind(stat, 1))
	if stat == "endurance" and not bool(rules.get("unlimited", false)):
		input.editable = false
	else:
		input.text_submitted.connect(_on_stat_submitted.bind(stat))
		input.focus_exited.connect(_commit_stat.bind(stat))
	stat_inputs[stat] = input
	stat_minus[stat] = minus
	stat_plus[stat] = plus
	return cell


func _add_stepper(parent: Container, input_width: float) -> Dictionary:
	var minus := Style.make_button("−", STEP_SIZE)
	var input := LineEdit.new()
	input.custom_minimum_size = Vector2(input_width, STEP_SIZE.y)
	input.alignment = HORIZONTAL_ALIGNMENT_CENTER
	var plus := Style.make_button("+", STEP_SIZE)
	parent.add_child(minus)
	parent.add_child(input)
	parent.add_child(plus)
	return {"minus": minus, "input": input, "plus": plus}


func _row_label(text: String, width: float) -> Label:
	var label := Style.make_label(text, Style.TEXT_COLOR, LABEL_FONT_SIZE)
	label.custom_minimum_size.x = width
	label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	label.clip_text = true
	label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	return label


func _wrapped_label(text: String, color: Color, font_size: int) -> Label:
	var label := Style.make_label(text, color, font_size)
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return label


func _spacer(height: float) -> Control:
	var spacer := Control.new()
	spacer.custom_minimum_size.y = height
	return spacer


func _spacer_h(width: float) -> Control:
	var spacer := Control.new()
	spacer.custom_minimum_size.x = width
	return spacer


# Во Front Line часть параметров не используется: затемняем, отключаем ввод и кнопки, чтобы было видно.
func _apply_mode_availability() -> void:
	if mode != "front_line":
		return
	for key in FRONT_LINE_INACTIVE_FIELDS:
		var row: Node = field_rows.get(key)
		if row == null:
			continue
		(field_inputs[key] as LineEdit).editable = false
		(field_minus[key] as Button).disabled = true
		(field_plus[key] as Button).disabled = true
		_dim(row)
	for stat in FRONT_LINE_INACTIVE_STATS:
		if not stat_inputs.has(stat):
			continue
		var stat_input: LineEdit = stat_inputs[stat]
		stat_input.editable = false
		(stat_minus[stat] as Button).disabled = true
		(stat_plus[stat] as Button).disabled = true
		_dim(stat_input.get_parent())
	if level_input != null:
		level_input.editable = false
		level_minus.disabled = true
		level_plus.disabled = true
		_dim(level_input.get_parent())
	for state_id in state_buttons:
		var button: Button = state_buttons[state_id]
		button.disabled = true
		_dim(button.get_parent())
	if _state_hint != null:
		_dim(_state_hint)
	if patrol_grid != null:
		patrol_grid.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_dim(patrol_grid)
	if _patrol_presets != null:
		for preset_button in _patrol_presets.get_children():
			(preset_button as Button).disabled = true
		_dim(_patrol_presets)
	if _patrol_count_label != null:
		_dim(_patrol_count_label.get_parent())
	if _equipment_button != null:
		_equipment_button.disabled = true
		_dim(_equipment_button.get_parent())
	_refresh_attack_style_view()


# Характер боя: подсветка выбранного и радиус урона активен только у мага.
func _refresh_attack_style_view() -> void:
	for style_id in attack_style_buttons:
		var style_button: Button = attack_style_buttons[style_id]
		if style_id == attack_style:
			var selected := Style.flat(Style.BUTTON_ON_COLOR, Style.ACTIVE_COLOR, 2)
			style_button.add_theme_stylebox_override("normal", selected)
			style_button.add_theme_stylebox_override("hover", selected)
		else:
			style_button.remove_theme_stylebox_override("normal")
			style_button.remove_theme_stylebox_override("hover")
	if not field_rows.has("area_radius"):
		return
	var mage := attack_style == "mage"
	(field_inputs["area_radius"] as LineEdit).editable = mage
	(field_minus["area_radius"] as Button).disabled = not mage
	(field_plus["area_radius"] as Button).disabled = not mage
	var radius_row: Node = field_rows["area_radius"]
	if mage:
		radius_row.modulate = Color(1.0, 1.0, 1.0, 1.0)
	else:
		_dim(radius_row)


func _dim(node: Node) -> void:
	if node is CanvasItem:
		(node as CanvasItem).modulate = Color(1.0, 1.0, 1.0, INACTIVE_ALPHA)


# Урон моба (только Front Line): базовый минимум и максимум вводятся вручную; ниже фактический урон на карте.
func _add_damage_block(column: VBoxContainer) -> void:
	column.add_child(_spacer(4))
	column.add_child(_section_header("Урон"))
	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", ROW_GAP)
	column.add_child(head)
	head.add_child(_spacer_h(DAMAGE_LABEL_WIDTH))
	head.add_child(_damage_caption("мин"))
	head.add_child(_damage_caption("макс"))
	var base_row := HBoxContainer.new()
	base_row.add_theme_constant_override("separation", ROW_GAP)
	column.add_child(base_row)
	base_row.add_child(_row_label("База", DAMAGE_LABEL_WIDTH))
	for key in DAMAGE_FIELDS:
		var input := LineEdit.new()
		input.custom_minimum_size = Vector2(DAMAGE_INPUT_WIDTH, STEP_SIZE.y)
		input.alignment = HORIZONTAL_ALIGNMENT_CENTER
		input.tooltip_text = "базовый урон моба вручную, без силы и без критического удара"
		input.text_submitted.connect(_on_damage_submitted.bind(key))
		input.focus_exited.connect(_commit_damage.bind(key))
		base_row.add_child(input)
		_damage_inputs[key] = input
	var actual_row := HBoxContainer.new()
	actual_row.add_theme_constant_override("separation", ROW_GAP)
	column.add_child(actual_row)
	actual_row.add_child(_row_label("Факт", DAMAGE_LABEL_WIDTH))
	for key in DAMAGE_FIELDS:
		var cell := PanelContainer.new()
		cell.custom_minimum_size = Vector2(DAMAGE_INPUT_WIDTH, STEP_SIZE.y)
		cell.add_theme_stylebox_override("panel", Style.flat(Style.MENU_COLOR.darkened(0.2)))
		var value := Style.make_label("", Style.ACTIVE_COLOR, LABEL_FONT_SIZE)
		value.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		value.tooltip_text = "фактический урон на карте: база плюс 2 за очко силы; броня цели уменьшает его в бою"
		cell.add_child(value)
		actual_row.add_child(cell)
		_damage_actual[key] = value
	column.add_child(_wrapped_label(
		"Факт = база + %d за очко силы" % DAMAGE_PER_STRENGTH,
		Style.DIM_COLOR,
		Style.SMALL_FONT_SIZE,
	))


func _damage_caption(text: String) -> Label:
	var label := Style.make_label(text, Style.DIM_COLOR, Style.SMALL_FONT_SIZE)
	label.custom_minimum_size.x = DAMAGE_INPUT_WIDTH
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	return label


func _on_damage_submitted(_text: String, key: String) -> void:
	_commit_damage(key)


func _commit_damage(key: String) -> void:
	if not _damage_inputs.has(key):
		return
	var text := (_damage_inputs[key] as LineEdit).text.strip_edges()
	if text.is_valid_int():
		values[key] = clampi(text.to_int(), 0, DAMAGE_LIMIT)
	_refresh_damage()


# Поля базы показывают значения; фактический урон пересчитывается от силы и базы.
func _refresh_damage() -> void:
	for key in DAMAGE_FIELDS:
		if _damage_inputs.has(key) and values.has(key):
			(_damage_inputs[key] as LineEdit).text = str(int(values[key]))
	_refresh_damage_preview()


func _refresh_damage_preview() -> void:
	if not stats.has("strength"):
		return
	var strength_bonus := DAMAGE_PER_STRENGTH * int(stats["strength"])
	for key in DAMAGE_FIELDS:
		if _damage_actual.has(key) and values.has(key):
			(_damage_actual[key] as Label).text = str(int(values[key]) + strength_bonus)


func _refresh_all() -> void:
	for spec in _settings_fields():
		_refresh_field(str(spec["key"]))
	_refresh_level_and_stats()
	_refresh_states()
	_refresh_patrol_count()
	_refresh_equipment_count()


func _refresh_field(key: String) -> void:
	_refresh_field_values(key)
	_apply_mode_availability()


func _refresh_field_values(key: String) -> void:
	var input: LineEdit = field_inputs[key]
	if key in INTEGER_RESOURCE_KEYS:
		var value := int(values[key])
		input.text = str(value)
		(field_minus[key] as Button).disabled = value <= _integer_min(key)
		(field_plus[key] as Button).disabled = value >= _integer_max(key)
		return
	var limits: Array = Rules.LIMITS[key]
	var value := float(values[key])
	input.text = Rules.format_field(key, value)
	(field_minus[key] as Button).disabled = value <= float(limits[0])
	(field_plus[key] as Button).disabled = value >= float(limits[1])


func _refresh_level_and_stats() -> void:
	_refresh_level_and_stats_values()
	_apply_mode_availability()
	_refresh_damage()


func _refresh_level_and_stats_values() -> void:
	level_input.text = str(level)
	level_minus.disabled = level <= int(rules["level_min"])
	level_plus.disabled = level >= int(rules["level_cap"])
	var free := free_points()
	_free_label.text = "Без ограничений" if bool(rules.get("unlimited", false)) \
		else "Свободных очков: %d из %d" % [free, total_points()]
	_free_label.add_theme_color_override(
		"font_color",
		Style.ACTIVE_COLOR if bool(rules.get("unlimited", false)) or free > 0 \
			else Style.DIM_COLOR,
	)
	for stat in stat_inputs:
		(stat_inputs[stat] as LineEdit).text = str(int(stats[stat]))
		var fixed: bool = stat == "endurance" and not bool(rules.get("unlimited", false))
		(stat_minus[stat] as Button).disabled = fixed \
			or int(stats[stat]) <= int(rules["stat_min"])
		(stat_plus[stat] as Button).disabled = fixed \
			or (bool(rules.get("unlimited", false))
				and int(stats[stat]) >= 9223372036854775806) \
			or (not bool(rules.get("unlimited", false)) and free <= 0)
	_endurance_hint.text = "Выносливость задаётся вручную: %d" % int(stats["endurance"]) \
		if bool(rules.get("unlimited", false)) \
		else "Выносливость задаётся уровнем: %d" % int(stats["endurance"])


func _refresh_states() -> void:
	_refresh_states_values()
	_apply_mode_availability()


func _refresh_states_values() -> void:
	for state_id in state_buttons:
		var button: Button = state_buttons[state_id]
		if state_id == state:
			var selected := Style.flat(Style.BUTTON_ON_COLOR, Style.ACTIVE_COLOR, 2)
			button.add_theme_stylebox_override("normal", selected)
			button.add_theme_stylebox_override("hover", selected)
		else:
			button.remove_theme_stylebox_override("normal")
			button.remove_theme_stylebox_override("hover")
	_state_hint.text = str(Rules.STATE_HINTS[state])


func _refresh_patrol_count() -> void:
	_patrol_count_label.text = "клеток: %d · ЛКМ — закрасить, ПКМ — стереть" % patrol_grid.cell_count()


func _refresh_equipment_count() -> void:
	_equipment_count_label.text = "надето: %d из %d" % [
		equipment_panel.equipped_count(),
		Rules.EQUIPMENT_SLOTS.size(),
	]


func _commit_all_inputs() -> void:
	for key in DAMAGE_FIELDS:
		if _damage_inputs.has(key):
			_commit_damage(key)
	_commit_all_inputs_base()


func _commit_all_inputs_base() -> void:
	for key in field_inputs:
		_commit_field(str(key))
	_commit_level()
	for stat in stat_inputs:
		_commit_stat(str(stat))


func _commit_field(key: String) -> void:
	var input: LineEdit = field_inputs[key]
	if key in INTEGER_RESOURCE_KEYS:
		if input.text == str(values[key]):
			return
		var text := input.text.strip_edges()
		if text.is_valid_int():
			set_integer_field_value(key, text.to_int())
		else:
			_refresh_field(key)
		return
	if input.text == Rules.format_field(key, float(values[key])):
		return
	var parsed: Variant = Rules.parse_field(key, input.text)
	if parsed == null:
		_refresh_field(key)
		return
	set_field_value(key, float(parsed))


func _commit_level() -> void:
	if level_input.text == str(level):
		return
	var text := level_input.text.strip_edges()
	if text.is_valid_int():
		set_level(text.to_int())
	else:
		_refresh_level_and_stats()


func _commit_stat(stat: String) -> void:
	var input: LineEdit = stat_inputs[stat]
	if input.text == str(int(stats[stat])):
		return
	var text := input.text.strip_edges()
	if text.is_valid_int():
		set_stat_value(stat, text.to_int())
	else:
		_refresh_level_and_stats()


func _on_field_step(key: String, direction: int) -> void:
	_commit_all_inputs()
	step_field(key, direction)


func _on_level_step(direction: int) -> void:
	_commit_all_inputs()
	step_level(direction)


func _on_stat_step(stat: String, direction: int) -> void:
	_commit_all_inputs()
	step_stat(stat, direction)


func _on_field_submitted(_text: String, key: String) -> void:
	_commit_field(key)
	(field_inputs[key] as LineEdit).release_focus()


func _on_level_submitted(_text: String) -> void:
	_commit_level()
	level_input.release_focus()


func _on_stat_submitted(_text: String, stat: String) -> void:
	_commit_stat(stat)
	(stat_inputs[stat] as LineEdit).release_focus()
