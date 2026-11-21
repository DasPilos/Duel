extends Control

signal restart_requested

const PANEL_COLOR := Color8(25, 29, 31)
const BORDER_COLOR := Color8(113, 133, 126)
const TEXT_COLOR := Color8(230, 226, 211)
const NOTICE_COLOR := Color8(255, 220, 144)
const BUTTON_COLOR := Color8(84, 111, 83)
const BUTTON_HOVER_COLOR := Color8(103, 143, 98)
const SIMPLE_SIZE := Vector2(250, 36)
const NOTICE_MAX_WIDTH := 760.0
const NOTICE_HEIGHT := 76.0
const TOP_MARGIN := 10.0

var _status: Dictionary = {}
var _server_time := 0.0
var _server_time_received_msec := 0
var _utc_offset_seconds := 0
var _notice_key := ""
var _notice_received_msec := 0
var _blocked := false
var _panel: PanelContainer
var _simple_label: Label
var _notice_box: HBoxContainer
var _notice_title: Label
var _notice_details: Label
var _restart_button: Button


func _init() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	z_index = 120
	visible = false

	_panel = PanelContainer.new()
	_panel.add_theme_stylebox_override("panel", _panel_style())
	add_child(_panel)

	var margin := MarginContainer.new()
	for side in ["margin_left", "margin_right"]:
		margin.add_theme_constant_override(side, 14)
	for side in ["margin_top", "margin_bottom"]:
		margin.add_theme_constant_override(side, 6)
	_panel.add_child(margin)

	var content := VBoxContainer.new()
	content.alignment = BoxContainer.ALIGNMENT_CENTER
	margin.add_child(content)

	_simple_label = Label.new()
	_simple_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_simple_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_simple_label.add_theme_font_size_override("font_size", 14)
	_simple_label.add_theme_color_override("font_color", TEXT_COLOR)
	content.add_child(_simple_label)

	_notice_box = HBoxContainer.new()
	_notice_box.add_theme_constant_override("separation", 12)
	_notice_box.visible = false
	content.add_child(_notice_box)

	var texts := VBoxContainer.new()
	texts.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_notice_box.add_child(texts)

	_notice_title = Label.new()
	_notice_title.add_theme_font_size_override("font_size", 12)
	_notice_title.add_theme_color_override("font_color", NOTICE_COLOR)
	texts.add_child(_notice_title)

	_notice_details = Label.new()
	_notice_details.add_theme_font_size_override("font_size", 11)
	_notice_details.add_theme_color_override("font_color", TEXT_COLOR)
	texts.add_child(_notice_details)

	_restart_button = Button.new()
	_restart_button.text = "Перезапустить клиент"
	_restart_button.focus_mode = Control.FOCUS_NONE
	_restart_button.custom_minimum_size = Vector2(150, 28)
	_restart_button.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_restart_button.add_theme_font_size_override("font_size", 11)
	_restart_button.add_theme_color_override("font_color", TEXT_COLOR)
	_restart_button.add_theme_color_override("font_hover_color", TEXT_COLOR)
	_restart_button.add_theme_stylebox_override("normal", _button_style(BUTTON_COLOR))
	_restart_button.add_theme_stylebox_override("hover", _button_style(BUTTON_HOVER_COLOR))
	_restart_button.add_theme_stylebox_override("pressed", _button_style(BUTTON_COLOR.darkened(0.15)))
	_restart_button.pressed.connect(_on_restart_pressed)
	_notice_box.add_child(_restart_button)


func _process(_delta: float) -> void:
	if visible:
		_refresh_texts()


func apply_status(status: Dictionary) -> void:
	var notice_key := _notice_key_of(status.get("restart_notice"))
	if notice_key != _notice_key:
		_notice_key = notice_key
		_notice_received_msec = Time.get_ticks_msec()
	_status = status.duplicate()
	if status.get("server_time") != null:
		_server_time = float(status["server_time"])
		_server_time_received_msec = Time.get_ticks_msec()
	_utc_offset_seconds = int(status.get("server_utc_offset_seconds", 0))
	_refresh()


# Скрывает плашку, пока открыто меню выхода или показан экран потери связи.
func set_blocked(value: bool) -> void:
	_blocked = value
	_refresh()


func _refresh() -> void:
	visible = not _status.is_empty() and not _blocked
	if not visible:
		return
	if _status.get("restart_notice") is Dictionary:
		var width := minf(get_viewport_rect().size.x - 24.0, NOTICE_MAX_WIDTH)
		_simple_label.visible = false
		_notice_box.visible = true
		_apply_layout(Vector2(width, NOTICE_HEIGHT))
	else:
		_simple_label.visible = true
		_notice_box.visible = false
		_apply_layout(SIMPLE_SIZE)
	_refresh_texts()


func _refresh_texts() -> void:
	var online := maxi(0, int(_status.get("online_players", 0)))
	var clock := _clock_text()
	var notice: Variant = _status.get("restart_notice")
	if notice is Dictionary:
		var elapsed := (Time.get_ticks_msec() - _notice_received_msec) / 1000
		var remaining := maxi(0, int(notice.get("seconds_remaining", 0)) - elapsed)
		_notice_title.text = "%s Перезапуск через %d:%02d" % [
			str(notice.get("message", "Сервер получил обновление.")),
			remaining / 60,
			remaining % 60,
		]
		_notice_details.text = "Онлайн: %d · Сервер: %s. Если нужно, перезапустите клиент." % [online, clock]
	else:
		_simple_label.text = "Игроков онлайн: %d   %s" % [online, clock]


func _clock_text() -> String:
	if _server_time <= 0.0:
		return "--:--:--"
	var estimated := _server_time + float(Time.get_ticks_msec() - _server_time_received_msec) / 1000.0
	var parts := Time.get_time_dict_from_unix_time(int(floor(estimated)) + _utc_offset_seconds)
	return "%02d:%02d:%02d" % [parts["hour"], parts["minute"], parts["second"]]


func _apply_layout(target: Vector2) -> void:
	_panel.anchor_left = 0.5
	_panel.anchor_right = 0.5
	_panel.anchor_top = 0.0
	_panel.anchor_bottom = 0.0
	_panel.offset_left = -target.x / 2.0
	_panel.offset_right = target.x / 2.0
	_panel.offset_top = TOP_MARGIN
	_panel.offset_bottom = TOP_MARGIN + target.y


func _on_restart_pressed() -> void:
	restart_requested.emit()


static func _notice_key_of(notice: Variant) -> String:
	if not notice is Dictionary:
		return ""
	return str(notice.get("restart_at", ""))


static func _panel_style() -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = PANEL_COLOR
	style.border_color = BORDER_COLOR
	style.set_border_width_all(1)
	style.set_corner_radius_all(5)
	return style


static func _button_style(color: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.set_corner_radius_all(4)
	style.content_margin_top = 4
	style.content_margin_bottom = 4
	return style
