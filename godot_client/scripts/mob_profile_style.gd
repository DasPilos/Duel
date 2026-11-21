extends RefCounted

const PANEL_COLOR := Color8(34, 37, 43)
const MENU_COLOR := Color8(42, 46, 54)
const BUTTON_COLOR := Color8(46, 50, 58)
const BUTTON_ON_COLOR := Color8(70, 98, 136)
const BORDER_COLOR := Color8(70, 74, 82)
const TEXT_COLOR := Color8(235, 235, 235)
const DIM_COLOR := Color8(160, 166, 176)
const OFF_COLOR := Color8(95, 100, 110)
const ACTIVE_COLOR := Color8(120, 220, 140)
const WARN_COLOR := Color8(240, 190, 90)
const SAVE_COLOR := Color8(56, 106, 66)
const SAVE_HOVER_COLOR := Color8(70, 130, 80)
const SHADE_COLOR := Color(0.0, 0.0, 0.0, 0.59)

const FONT_SIZE := 13
const SMALL_FONT_SIZE := 11
const HEADER_FONT_SIZE := 14
const TITLE_FONT_SIZE := 15


static func flat(
	background: Color,
	border: Color = BORDER_COLOR,
	border_width := 1,
	radius := 4,
) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = background
	style.border_color = border
	style.set_border_width_all(border_width)
	style.set_corner_radius_all(radius)
	style.content_margin_left = 8.0
	style.content_margin_right = 8.0
	style.content_margin_top = 3.0
	style.content_margin_bottom = 3.0
	return style


static func make_theme() -> Theme:
	var theme := Theme.new()
	theme.default_font_size = FONT_SIZE
	theme.set_color("font_color", "Label", TEXT_COLOR)
	theme.set_font_size("font_size", "Label", FONT_SIZE)
	theme.set_stylebox("normal", "Button", flat(BUTTON_COLOR))
	theme.set_stylebox("hover", "Button", flat(BUTTON_ON_COLOR))
	theme.set_stylebox("pressed", "Button", flat(BUTTON_ON_COLOR.darkened(0.2)))
	theme.set_stylebox("disabled", "Button", flat(BUTTON_COLOR.darkened(0.25), BORDER_COLOR.darkened(0.3)))
	theme.set_stylebox("focus", "Button", StyleBoxEmpty.new())
	theme.set_color("font_color", "Button", TEXT_COLOR)
	theme.set_color("font_hover_color", "Button", TEXT_COLOR)
	theme.set_color("font_pressed_color", "Button", TEXT_COLOR)
	theme.set_color("font_focus_color", "Button", TEXT_COLOR)
	theme.set_color("font_disabled_color", "Button", OFF_COLOR)
	theme.set_font_size("font_size", "Button", FONT_SIZE)
	theme.set_stylebox("normal", "LineEdit", flat(MENU_COLOR))
	theme.set_stylebox("focus", "LineEdit", flat(MENU_COLOR, ACTIVE_COLOR))
	theme.set_stylebox("read_only", "LineEdit", flat(MENU_COLOR.darkened(0.2)))
	theme.set_color("font_color", "LineEdit", TEXT_COLOR)
	theme.set_color("font_uneditable_color", "LineEdit", OFF_COLOR)
	theme.set_color("caret_color", "LineEdit", TEXT_COLOR)
	theme.set_color("selection_color", "LineEdit", BUTTON_ON_COLOR)
	theme.set_font_size("font_size", "LineEdit", FONT_SIZE)
	theme.set_stylebox("panel", "PanelContainer", flat(PANEL_COLOR, BORDER_COLOR, 1, 6))
	var scroll_track := flat(Color8(16, 18, 22), Color8(16, 18, 22), 0, 3)
	var grabber := flat(BORDER_COLOR, BORDER_COLOR, 0, 3)
	var grabber_hover := flat(Color8(96, 102, 112), Color8(96, 102, 112), 0, 3)
	for scrollbar in ["VScrollBar", "HScrollBar"]:
		theme.set_stylebox("scroll", scrollbar, scroll_track)
		theme.set_stylebox("grabber", scrollbar, grabber)
		theme.set_stylebox("grabber_highlight", scrollbar, grabber_hover)
		theme.set_stylebox("grabber_pressed", scrollbar, grabber_hover)
	return theme


static func make_label(text: String, color: Color = TEXT_COLOR, font_size := FONT_SIZE) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_color_override("font_color", color)
	label.add_theme_font_size_override("font_size", font_size)
	return label


static func make_button(text: String, minimum_size := Vector2.ZERO) -> Button:
	var button := Button.new()
	button.text = text
	button.custom_minimum_size = minimum_size
	button.focus_mode = Control.FOCUS_NONE
	return button
