extends PanelContainer

# Компактная карточка персонажа для окна сравнения. Состав как в deck/ui/character_card.py: шапка с глифом
# класса и ID, уровень и XP, HP и MP, монеты, кукла со слотами и характеристики с производными значениями.
# Кукла рисует базовую фигуру и полупрозрачные слоты, как deck/ui/character_card.py; класс на карточке не показывается.

signal stat_requested(stat_name: String, delta: int)

const RULES := preload("res://scripts/deck_character_rules.gd")
const CLASS_RULES := preload("res://scripts/deck_class_card_rules.gd")
const CARD_WIDTH := 330.0
const SLOT_SIZE := Vector2(58, 28)
const SLOT_GAP := 2
const SLOT_COLUMNS := 5
const SLOT_ROWS := 5
const STAT_LABEL_WIDTH := 118.0
const TEXT_COLOR := Color8(240, 240, 245)
const MUTED_COLOR := Color8(170, 175, 185)
const EMPTY_COLOR := Color8(120, 115, 125)
const XP_COLOR := Color8(255, 220, 120)
const HP_COLOR := Color8(210, 80, 80)
const MP_COLOR := Color8(60, 140, 220)
const BAR_BACKGROUND := Color8(36, 34, 44)
const CARD_BACKGROUND := Color8(26, 24, 34, 242)
const SLOT_BACKGROUND := Color8(48, 44, 48)
const SLOT_BORDER := Color8(85, 78, 80)
# Слоты полупрозрачны всегда, потому что кукла рисует фигуру под ними: SLOT_OPACITY = 65 в deck/ui/equipment_slots.py.
const SLOT_ALPHA := 0.65
const ITEM_ICON_RULES := preload("res://scripts/deck_item_icon_rules.gd")
# Иконка 62 px из deck/ui/equipment_slots.py в слоте 58×32 не помещается: здесь 16 px слева от названия предмета.
const SLOT_ICON_SIZE := 16
const SLOT_ICON_GAP := 3

var _equipment: Dictionary = {}
var _border_style: StyleBoxFlat
var _glyph_style: StyleBoxFlat
var _glyph_label: Label
var _title_label: Label
var _name_label: Label
var _id_label: Label
var _level_label: Label
var _xp_label: Label
var _hp_label: Label
var _hp_bar: ProgressBar
var _mp_label: Label
var _mp_bar: ProgressBar
var _coins_label: Label
var _stat_points_label: Label
var _paperdoll: Control
var _paperdoll_grid: GridContainer
var _figure: TextureRect
var _assets_root := ""
var _slot_cells: Dictionary = {}
var _slot_styles: Array[StyleBoxFlat] = []
var _stat_labels: Dictionary = {}
var _derived_labels: Dictionary = {}
var _derived_keys: Dictionary = {}
var _stat_controls: Dictionary = {}
var _stat_plus: Dictionary = {}
static var _art_cache: Dictionary = {}


func _init() -> void:
	custom_minimum_size.x = CARD_WIDTH
	_border_style = StyleBoxFlat.new()
	_border_style.bg_color = CARD_BACKGROUND
	_border_style.set_border_width_all(2)
	_border_style.set_corner_radius_all(6)
	_border_style.set_content_margin_all(6)
	add_theme_stylebox_override("panel", _border_style)
	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 3)
	add_child(layout)
	layout.add_child(_build_header())
	layout.add_child(_build_level_row())
	_hp_label = _make_label(12, TEXT_COLOR)
	layout.add_child(_hp_label)
	_hp_bar = _make_bar(HP_COLOR)
	layout.add_child(_hp_bar)
	_mp_label = _make_label(12, TEXT_COLOR)
	layout.add_child(_mp_label)
	_mp_bar = _make_bar(MP_COLOR)
	layout.add_child(_mp_bar)
	_coins_label = _make_label(12, TEXT_COLOR)
	layout.add_child(_coins_label)
	layout.add_child(_build_paperdoll())
	layout.add_child(_build_stats())


func set_profile(profile: Dictionary, title: String, border: Color, editable: bool, opponent: Variant = null) -> void:
	var profession := str(profile.get("profession_type", "warrior"))
	var palette := RULES.class_palette(profession)
	_border_style.border_color = border
	_glyph_style.bg_color = palette["icon_background"]
	_glyph_label.text = str(palette["glyph"])
	_title_label.text = title
	_name_label.text = str(profile.get("name", "Персонаж"))
	var character_id: Variant = profile.get("character_id")
	var id_text := "-"
	if character_id is int or character_id is float:
		id_text = "%d" % int(character_id)
	elif character_id != null:
		id_text = str(character_id)
	_id_label.text = "ID: %s" % id_text
	var level := int(profile.get("level", 1))
	var next_xp := RULES.xp_to_next(level)
	_level_label.text = "Уровень %d" % level
	_xp_label.text = "XP: максимум" if next_xp == 0 else "XP: %d/%d" % [int(profile.get("xp", 0)), next_xp]
	var hp := RULES.displayed_hp(profile)
	_hp_label.text = "HP: %d/%d" % [hp.x, hp.y]
	_hp_bar.max_value = hp.y
	_hp_bar.value = hp.x
	var mp := int(profile.get("mp", 0))
	var max_mp := maxi(1, int(profile.get("max_mp", 1)))
	_mp_label.text = "MP: %d/%d" % [mp, max_mp]
	_mp_bar.max_value = max_mp
	_mp_bar.value = mp
	_coins_label.text = "Монеты: %d" % int(profile.get("coins", 0))
	var equipment: Variant = profile.get("equipment", {})
	_equipment = equipment if equipment is Dictionary else {}
	_refresh_slots()
	_stat_points_label.text = "Свободные очки: %d" % int(profile.get("stat_points", 0))
	var effective := RULES.effective_stats(profile)
	var derived := RULES.derived_values(profile, opponent)
	for row in RULES.STAT_ROWS:
		var stat_key := str(row[0])
		var derived_key: String = _derived_keys[stat_key]
		_stat_labels[stat_key].text = "%s: %d" % [str(row[1]), int(effective.get(stat_key, 0))]
		var has_derived := not derived_key.is_empty() and derived.has(derived_key)
		_derived_labels[stat_key].text = "%s: %s" % [derived_key, str(derived[derived_key])] if has_derived else ""
		_stat_controls[stat_key].visible = editable


# Предмет под точкой (глобальные координаты) для подсказки; пустой словарь, если слот пуст.
func slot_item_at(point: Vector2) -> Dictionary:
	for slot_key in _slot_cells:
		var panel: Control = _slot_cells[slot_key]["panel"]
		var item: Variant = _equipment.get(slot_key)
		if item is Dictionary and panel.get_global_rect().has_point(point):
			return item
	return {}


func _build_header() -> Control:
	var header := HBoxContainer.new()
	header.add_theme_constant_override("separation", 8)
	var glyph_panel := PanelContainer.new()
	glyph_panel.custom_minimum_size = Vector2(30, 30)
	_glyph_style = StyleBoxFlat.new()
	_glyph_style.set_corner_radius_all(6)
	glyph_panel.add_theme_stylebox_override("panel", _glyph_style)
	header.add_child(glyph_panel)
	_glyph_label = _make_label(17, TEXT_COLOR)
	_glyph_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_glyph_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	glyph_panel.add_child(_glyph_label)
	var names := VBoxContainer.new()
	names.add_theme_constant_override("separation", 0)
	header.add_child(names)
	_title_label = _make_label(11, MUTED_COLOR)
	names.add_child(_title_label)
	_name_label = _make_label(15, TEXT_COLOR)
	names.add_child(_name_label)
	_id_label = _make_label(11, MUTED_COLOR)
	names.add_child(_id_label)
	return header


func _build_level_row() -> Control:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 0)
	_level_label = _make_label(12, TEXT_COLOR)
	row.add_child(_level_label)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	spacer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(spacer)
	_xp_label = _make_label(12, XP_COLOR)
	row.add_child(_xp_label)
	return row


func _build_paperdoll() -> Control:
	_paperdoll = Control.new()
	_paperdoll.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_figure = TextureRect.new()
	_figure.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_figure.stretch_mode = TextureRect.STRETCH_SCALE
	_figure.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	_figure.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_figure.visible = false
	_paperdoll.add_child(_figure)
	_paperdoll_grid = _build_grid()
	_paperdoll_grid.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_paperdoll.add_child(_paperdoll_grid)
	_paperdoll_grid.minimum_size_changed.connect(_sync_paperdoll_size)
	_paperdoll.resized.connect(_layout_figure)
	_sync_paperdoll_size()
	_load_figure()
	return _paperdoll


func _build_grid() -> GridContainer:
	var grid := GridContainer.new()
	grid.columns = SLOT_COLUMNS
	grid.add_theme_constant_override("h_separation", SLOT_GAP)
	grid.add_theme_constant_override("v_separation", SLOT_GAP)
	var entries := {}
	for entry in RULES.SLOT_LAYOUT:
		entries[Vector2i(int(entry[2]), int(entry[3]))] = entry
	for row in range(SLOT_ROWS):
		for column in range(SLOT_COLUMNS):
			var entry: Array = entries.get(Vector2i(column, row), [])
			if entry.is_empty():
				var spacer := Control.new()
				spacer.custom_minimum_size = SLOT_SIZE
				spacer.mouse_filter = Control.MOUSE_FILTER_IGNORE
				grid.add_child(spacer)
			else:
				grid.add_child(_build_slot(str(entry[0]), str(entry[1])))
	return grid


func _build_slot(slot_key: String, slot_title: String) -> Control:
	var cell := PanelContainer.new()
	cell.custom_minimum_size = SLOT_SIZE
	cell.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style := StyleBoxFlat.new()
	style.bg_color = Color(SLOT_BACKGROUND, SLOT_ALPHA)
	style.set_border_width_all(1)
	style.set_corner_radius_all(4)
	style.set_content_margin_all(3)
	cell.add_theme_stylebox_override("panel", style)
	_slot_styles.append(style)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 0)
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	cell.add_child(box)
	var title := _make_label(9, MUTED_COLOR)
	title.text = slot_title
	box.add_child(title)
	var item_row := HBoxContainer.new()
	item_row.add_theme_constant_override("separation", SLOT_ICON_GAP)
	item_row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(item_row)
	var icon := ITEM_ICON_RULES.new_icon_rect(SLOT_ICON_SIZE)
	item_row.add_child(icon)
	var item := _make_label(10, EMPTY_COLOR)
	item.clip_text = true
	item.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	item_row.add_child(item)
	_slot_cells[slot_key] = {"panel": cell, "item": item, "icon": icon}
	return cell


func _build_stats() -> Control:
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 1)
	var header := HBoxContainer.new()
	var title := _make_label(12, TEXT_COLOR)
	title.text = "ХАРАКТЕРИСТИКИ"
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(title)
	_stat_points_label = _make_label(12, XP_COLOR)
	header.add_child(_stat_points_label)
	box.add_child(header)
	for row in RULES.STAT_ROWS:
		var stat_key := str(row[0])
		var derived_key := str(row[2])
		var line := HBoxContainer.new()
		line.add_theme_constant_override("separation", 4)
		var stat_label := _make_label(12, TEXT_COLOR)
		stat_label.custom_minimum_size.x = STAT_LABEL_WIDTH
		line.add_child(stat_label)
		var derived_label := _make_label(12, RULES.DERIVED_COLORS.get(derived_key, TEXT_COLOR))
		derived_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		line.add_child(derived_label)
		var controls := HBoxContainer.new()
		controls.add_theme_constant_override("separation", 4)
		var minus := Button.new()
		minus.text = "-"
		minus.custom_minimum_size = Vector2(24, 18)
		minus.pressed.connect(_on_stat_pressed.bind(stat_key, -1))
		controls.add_child(minus)
		var plus := Button.new()
		plus.text = "+"
		plus.custom_minimum_size = Vector2(24, 18)
		plus.pressed.connect(_on_stat_pressed.bind(stat_key, 1))
		controls.add_child(plus)
		line.add_child(controls)
		box.add_child(line)
		_stat_labels[stat_key] = stat_label
		_derived_labels[stat_key] = derived_label
		_derived_keys[stat_key] = derived_key
		_stat_controls[stat_key] = controls
		_stat_plus[stat_key] = plus
	return box


func set_assets_root(path: String) -> void:
	_assets_root = path
	_load_figure()
	_refresh_slots()


func _load_figure() -> void:
	var path := CLASS_RULES.base_figure_path(_resolved_assets_root())
	var texture: Texture2D = null
	if FileAccess.file_exists(path):
		if not _art_cache.has(path):
			_art_cache[path] = _build_figure_texture(path)
		texture = _art_cache[path]
	_figure.texture = texture
	_figure.visible = texture != null
	_layout_figure()


func _resolved_assets_root() -> String:
	if not _assets_root.is_empty():
		return _assets_root
	return CLASS_RULES.default_assets_root(ProjectSettings.globalize_path("res://"))


func _sync_paperdoll_size() -> void:
	_paperdoll.custom_minimum_size = _paperdoll_grid.get_combined_minimum_size()
	_layout_figure()


func _layout_figure() -> void:
	if _figure == null or _figure.texture == null:
		return
	var figure := CLASS_RULES.figure_rect(_paperdoll_grid.get_combined_minimum_size(), _figure.texture.get_size(), 0)
	_figure.position = figure.position
	_figure.size = figure.size


static func _build_figure_texture(path: String) -> Texture2D:
	var source := Image.load_from_file(path)
	if source == null or source.is_empty():
		return null
	source.convert(Image.FORMAT_RGBA8)
	source.generate_mipmaps()
	return ImageTexture.create_from_image(source)


func _refresh_slots() -> void:
	var assets_root := _resolved_assets_root()
	for slot_key in _slot_cells:
		var slot: Dictionary = _slot_cells[slot_key]
		var item_label: Label = slot["item"]
		var item: Variant = _equipment.get(slot_key)
		if item is Dictionary:
			item_label.text = str(item.get("name", "Предмет"))
			item_label.add_theme_color_override("font_color", TEXT_COLOR)
		else:
			item_label.text = "—"
			item_label.add_theme_color_override("font_color", EMPTY_COLOR)
		ITEM_ICON_RULES.apply_icon(slot["icon"], assets_root, ITEM_ICON_RULES.item_key(item), SLOT_ICON_SIZE)


func _on_stat_pressed(stat_name: String, delta: int) -> void:
	stat_requested.emit(stat_name, delta)


func _make_label(font_size: int, color: Color) -> Label:
	var label := Label.new()
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return label


func _make_bar(color: Color) -> ProgressBar:
	var bar := ProgressBar.new()
	bar.show_percentage = false
	bar.custom_minimum_size.y = 8
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var fill := StyleBoxFlat.new()
	fill.bg_color = color
	fill.set_corner_radius_all(3)
	bar.add_theme_stylebox_override("fill", fill)
	var background := StyleBoxFlat.new()
	background.bg_color = BAR_BACKGROUND
	background.set_corner_radius_all(3)
	bar.add_theme_stylebox_override("background", background)
	return bar
