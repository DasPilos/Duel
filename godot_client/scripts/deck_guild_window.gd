extends Control

# Окно гильдии из deck/ui/guild_window.py: приглашение, список заданий и награда.
# Принятие задания окно делает само (локальный прогресс). Сдачу окно не выполняет: оно просит мир
# (claim_requested), тот запрашивает награду у сервера и потом возвращает результат через show_message.

signal claim_requested(quest_id: String)

const QUEST_LOG := preload("res://scripts/deck_quest_log.gd")
const CURRENCY := preload("res://scripts/deck_currency.gd")
const WINDOW_WIDTH := 620.0
const WINDOW_HEIGHT := 440.0
const LIST_WIDTH := 230.0
const ROW_HEIGHT := 44.0
const DESCRIPTION_WIDTH := 340.0
const WINDOW_BACKGROUND := Color8(30, 27, 18, 250)
const WINDOW_BORDER := Color8(220, 180, 60)
const TITLE_COLOR := Color8(255, 215, 90)
const QUEST_TITLE_COLOR := Color8(255, 225, 140)
const TEXT_COLOR := Color8(230, 225, 205)
const DONE_COLOR := Color8(120, 230, 130)
const MESSAGE_COLOR := Color8(255, 225, 140)
const ERROR_COLOR := Color8(255, 150, 140)
const STATUS_TEXT := {"available": "доступно", "active": "взято", "completed": "выполнено!"}
const ACTION_TEXT := {"available": "ПРИНЯТЬ ЗАДАНИЕ", "active": "ЗАДАНИЕ ВЗЯТО", "completed": "СДАТЬ ЗАДАНИЕ"}
const WELCOME_LINES := [
	"Добро пожаловать, искатель приключений!",
	"Здесь можно взять задания и получить за них награду.",
	"Нажмите «ЗАДАНИЯ», чтобы посмотреть доступные поручения.",
]

var _quest_log
var _view := "main"
var _selected_id := ""
var _window: PanelContainer
var _welcome: VBoxContainer
var _quests_view: HBoxContainer
var _footer: Control
var _rows: Dictionary = {}
var _group := ButtonGroup.new()
var _detail_title: Label
var _detail_description: Label
var _detail_reward: Label
var _detail_progress: Label
var _message: Label
var _action_button: Button


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	visible = false
	_selected_id = str(QUEST_LOG.QUESTS[0]["id"])
	var backdrop := ColorRect.new()
	backdrop.color = Color(0, 0, 0, 0.6)
	backdrop.mouse_filter = Control.MOUSE_FILTER_STOP
	backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	backdrop.gui_input.connect(_on_backdrop_input)
	add_child(backdrop)
	var center := CenterContainer.new()
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	_window = PanelContainer.new()
	_window.custom_minimum_size = Vector2(WINDOW_WIDTH, WINDOW_HEIGHT)
	_window.add_theme_stylebox_override("panel", _box_style())
	center.add_child(_window)
	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 8)
	_window.add_child(layout)
	layout.add_child(_build_header())
	layout.add_child(_build_tabs())
	_welcome = _build_welcome()
	layout.add_child(_welcome)
	_quests_view = _build_quests_view()
	layout.add_child(_quests_view)
	_footer = _build_footer()
	layout.add_child(_footer)


func open(quest_log) -> void:
	_quest_log = quest_log
	_view = "main"
	show_message("")
	visible = true
	refresh()


func close() -> void:
	visible = false


func is_open() -> bool:
	return visible


func show_message(text: String, is_error := false) -> void:
	_message.text = text
	_message.add_theme_color_override("font_color", ERROR_COLOR if is_error else MESSAGE_COLOR)


func refresh() -> void:
	if _quest_log == null:
		return
	_welcome.visible = _view == "main"
	_quests_view.visible = _view == "quests"
	_footer.visible = _view == "quests"
	for quest in QUEST_LOG.QUESTS:
		var quest_id := str(quest["id"])
		var status: String = _quest_log.status(quest_id)
		var row: Button = _rows[quest_id]
		row.text = "%s\n%s" % [str(quest["title"]), STATUS_TEXT[status]]
		var text_color := DONE_COLOR if status == "completed" else TEXT_COLOR
		for color_name in ["font_color", "font_hover_color", "font_pressed_color", "font_hover_pressed_color", "font_focus_color"]:
			row.add_theme_color_override(color_name, text_color)
	var quest := QUEST_LOG.quest_by_id(_selected_id)
	var status: String = _quest_log.status(_selected_id)
	_detail_title.text = str(quest["title"])
	_detail_description.text = str(quest["description"])
	_detail_reward.text = "Награда: %s" % CURRENCY.format_coins(int(quest["reward_coins"]))
	_detail_progress.visible = status != "available"
	_detail_progress.text = "Прогресс: %d/%d" % [_quest_log.progress_of(_selected_id), int(quest["count"])]
	_action_button.text = ACTION_TEXT[status]
	_action_button.disabled = status == "active"


func _show_quests() -> void:
	_view = "quests"
	refresh()


func _on_row_toggled(on: bool, quest_id: String) -> void:
	if not on:
		return
	_selected_id = quest_id
	show_message("")
	refresh()


func _on_action_pressed() -> void:
	var status: String = _quest_log.status(_selected_id)
	if status == "available":
		_quest_log.accept(_selected_id)
		show_message("Задание «%s» принято" % str(QUEST_LOG.quest_by_id(_selected_id)["title"]))
		refresh()
	elif status == "completed":
		claim_requested.emit(_selected_id)


func _on_backdrop_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		close()


func _build_header() -> Control:
	var header := HBoxContainer.new()
	var title := _make_label(17, TITLE_COLOR)
	title.text = "Гильдия искателей приключений"
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(title)
	var close_button := Button.new()
	close_button.text = "×"
	close_button.custom_minimum_size = Vector2(32, 28)
	close_button.pressed.connect(close)
	header.add_child(close_button)
	return header


func _build_tabs() -> Control:
	var tabs := HBoxContainer.new()
	var quests_button := Button.new()
	quests_button.text = "ЗАДАНИЯ"
	quests_button.custom_minimum_size = Vector2(160, 32)
	quests_button.pressed.connect(_show_quests)
	tabs.add_child(quests_button)
	return tabs


func _build_welcome() -> VBoxContainer:
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 6)
	for line in WELCOME_LINES:
		var label := _make_label(14, TEXT_COLOR)
		label.text = line
		label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		label.custom_minimum_size.x = WINDOW_WIDTH - 40.0
		box.add_child(label)
	return box


func _build_quests_view() -> HBoxContainer:
	var view := HBoxContainer.new()
	view.add_theme_constant_override("separation", 14)
	var list := VBoxContainer.new()
	list.custom_minimum_size.x = LIST_WIDTH
	list.add_theme_constant_override("separation", 4)
	view.add_child(list)
	for quest in QUEST_LOG.QUESTS:
		var quest_id := str(quest["id"])
		var row := Button.new()
		row.toggle_mode = true
		row.button_group = _group
		row.alignment = HORIZONTAL_ALIGNMENT_LEFT
		row.custom_minimum_size = Vector2(LIST_WIDTH, ROW_HEIGHT)
		row.button_pressed = quest_id == _selected_id
		row.toggled.connect(_on_row_toggled.bind(quest_id))
		list.add_child(row)
		_rows[quest_id] = row
	var details := VBoxContainer.new()
	details.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	details.add_theme_constant_override("separation", 6)
	view.add_child(details)
	_detail_title = _make_label(16, QUEST_TITLE_COLOR)
	details.add_child(_detail_title)
	_detail_description = _make_label(14, TEXT_COLOR)
	_detail_description.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_detail_description.custom_minimum_size.x = DESCRIPTION_WIDTH
	details.add_child(_detail_description)
	_detail_reward = _make_label(14, TEXT_COLOR)
	details.add_child(_detail_reward)
	_detail_progress = _make_label(14, DONE_COLOR)
	details.add_child(_detail_progress)
	return view


func _build_footer() -> Control:
	var footer := HBoxContainer.new()
	footer.add_theme_constant_override("separation", 12)
	_message = _make_label(13, MESSAGE_COLOR)
	_message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_message.custom_minimum_size.x = 260.0
	_message.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	footer.add_child(_message)
	_action_button = Button.new()
	_action_button.custom_minimum_size = Vector2(210, 36)
	_action_button.pressed.connect(_on_action_pressed)
	footer.add_child(_action_button)
	return footer


func _make_label(font_size: int, color: Color) -> Label:
	var label := Label.new()
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return label


func _box_style() -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = WINDOW_BACKGROUND
	style.border_color = WINDOW_BORDER
	style.set_border_width_all(2)
	style.set_corner_radius_all(8)
	style.set_content_margin_all(12)
	return style
