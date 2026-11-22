extends Control

const SCENE_TRANSITION := preload("res://scripts/scene_transition.gd")
const CANVAS_SCRIPT = preload("res://scripts/map_editor_canvas.gd")
const ATLAS_PALETTE_SCRIPT = preload("res://scripts/map_atlas_palette.gd")
const FLOATING_PANEL_SCRIPT = preload("res://scripts/editor_floating_panel.gd")
const ANIMATED_PALETTE_SCRIPT = preload("res://scripts/map_animated_palette.gd")
const MOB_PROFILE_DIALOG_SCRIPT = preload("res://scripts/mob_profile_dialog.gd")
const MOB_PROFILE_RULES = preload("res://scripts/mob_profile_rules.gd")
const BUILDING_SETTINGS_DIALOG_SCRIPT = preload("res://scripts/building_settings_dialog.gd")
const BUILDING_FOOTPRINT_TILES := 5
const BUILDING_ANIM_STEP_SECONDS := 0.15
const BUILDING_FRAME_PATHS := {
	"castle_8": [
		"res://assets/map/main_buildings/castle_anim_1.png", "res://assets/map/main_buildings/castle_anim_2.png",
		"res://assets/map/main_buildings/castle_anim_3.png", "res://assets/map/main_buildings/castle_anim_4.png",
		"res://assets/map/main_buildings/castle_anim_5.png", "res://assets/map/main_buildings/castle_anim_6.png",
		"res://assets/map/main_buildings/castle_anim_7.png", "res://assets/map/main_buildings/castle_anim_8.png",
	],
	"castle_5": [
		"res://assets/map/main_buildings/main_castle_anim_1.png", "res://assets/map/main_buildings/main_castle_anim_2.png",
		"res://assets/map/main_buildings/main_castle_anim_3.png", "res://assets/map/main_buildings/main_castle_anim_4.png",
		"res://assets/map/main_buildings/main_castle_anim_5.png",
	],
}
const LAYER_LIST_SCRIPT = preload("res://scripts/layer_list.gd")
const LAYER_RULES = preload("res://scripts/layer_rules.gd")
const MINIMAP_STROKE_REBUILD_MSEC := 200
const LOADING_TREE_SHEET := "res://assets/base_tails/Biome/craftpix-net-477432-flying-islands-pixel-art-top-down-tileset/PNG/Tree_animated.png"
const LOADING_GOLEM_SHEET := "res://assets/base_tails/LPC/craftpix-net-625807-golem-pixel-art-top-down-sprite-pack/PNG/Golem2/With_shadow/Golem2_Walk_with_shadow.png"
const LOADING_GOLEM_DIRECTION_ROW := 3
const LOADING_MAGE_SHEET := "res://assets/base_tails/Герои/mage/craftpix-net-137340-mage-1-3-level-pixel-top-down-sprite-character/PNG/Mage_1lvl/With_shadow/Mage_lvl1_Walk.png"
const LOADING_SMITH_SHEET := "res://assets/base_tails/pack/craftpix-net-741016-pixel-blacksmith-house-interior-and-exterior-assets/PNG/Smith/Forge/full/Smith_forge_full.png"
const HISTORY_RULES = preload("res://scripts/map_editor_history_rules.gd")
const FILL_RULES = preload("res://scripts/map_editor_fill_rules.gd")
const SELECTION_RULES = preload("res://scripts/map_editor_selection_rules.gd")
const DRAFTS_RULES = preload("res://scripts/map_editor_drafts_rules.gd")
const TEST_WORLD_RULES = preload("res://scripts/map_editor_test_world_rules.gd")
const MINIMAP_RULES = preload("res://scripts/map_editor_minimap_rules.gd")
const SPAWN_RULES = preload("res://scripts/map_editor_spawn_rules.gd")
const SEED_RULES = preload("res://scripts/map_editor_seed_rules.gd")
const ITEM_FORM_DIALOG_SCRIPT = preload("res://scripts/map_editor_item_form.gd")
const ITEM_FORM_RULES = preload("res://scripts/map_editor_item_form_rules.gd")
const ITEM_SAVED_STATUS := "Предмет «%s» добавлен в инвентарь режима %s"
const TOOL_BRUSH := "brush"
const TOOL_FILL := "fill"
const TOOL_SELECT := "select"
const TOOL_STAMP := "stamp"
const TOOL_SPAWN := "spawn"
const SELECT_COLOR := Color(0.47, 0.78, 1.0)
const HOVER_COLOR := Color(1.0, 0.86, 0.35)
const SPAWN_COLOR := Color(0.31, 0.86, 0.47)
const MOB_SPAWN_COLOR := Color(0.93, 0.22, 0.18)
const SPAWN_OUTLINE_COLOR := Color(0.04, 0.16, 0.08)
const SPAWN_TEXT_COLOR := Color(0.04, 0.12, 0.06)
const DEFAULT_MAP_SIZE := 64
const EDITOR_UI_SCALE := 0.5
const EDITOR_DIALOG_SIZE := Vector2i(400, 390)
const EDITOR_FORM_LABEL_WIDTH := 160
const EDITOR_FORM_SPACING := 4
const TILE_SIZE := 16.0
const ATLAS_TILE_SIZE := 16
const ANIMAL_PALETTE_ICON_SIZE := 80
const ANIMAL_CARD_SIZE := Vector2(262, 184)
const ANIMAL_CARD_MARGIN := 8.0
const ANIMAL_CARD_ROW_WIDTH := 84.0
const ANIMAL_CARD_ARROW_SIZE := Vector2(20, 18)
const ANIMAL_PREVIEW_MIN_STEP_SECONDS := 0.7
const ANIMAL_DIRECTION_ORDER := ["down", "left", "up", "right"]
const ANIMAL_DIRECTION_TITLES := {"down": "вниз", "left": "влево", "up": "вверх", "right": "вправо"}
const ANIMAL_SHEET_DIRECTION_BLOCKS := ["down", "up", "left", "right"]
const ANIMAL_CARD_TITLE_COLOR := Color(0.94, 0.82, 0.56)
const ANIMAL_CARD_TEXT_COLOR := Color(0.86, 0.9, 0.94)
const ANIMAL_CARD_DIM_COLOR := Color(0.42, 0.45, 0.5)
const ANIMAL_CARD_CURRENT_TEXT_COLOR := Color(0.95, 1.0, 0.95)
const ANIMAL_CARD_BORDER_COLOR := Color(0.36, 0.52, 0.72)
const ANIMAL_CARD_PINNED_COLOR := Color(0.94, 0.82, 0.56)
const ANIMAL_CARD_OTHER_ROW := "other"
const ANIMAL_ACTION_ROWS := [
	["idle", "Покой"],
	["walk", "Ходьба"],
	["run", "Бег"],
	["attack", "Атака"],
	["run_attack", "Атака в беге"],
	["walk_attack", "Атака в ходьбе"],
	["hurt", "Урон"],
	["death", "Смерть"],
	["jump", "Прыжок"],
	["other", "Другое"],
]
const ATLAS_ANNOTATIONS_PATH := "user://tile_annotations.cfg"
const AUTOTILE_CORNER_VARIANTS := [
	{"key": "inner_nw", "title": "Внутренний ↖"},
	{"key": "inner_ne", "title": "Внутренний ↗"},
	{"key": "inner_sw", "title": "Внутренний ↙"},
	{"key": "inner_se", "title": "Внутренний ↘"},
	{"key": "diagonal_nw", "title": "Диагональ ↖"},
	{"key": "diagonal_ne", "title": "Диагональ ↗"},
	{"key": "diagonal_sw", "title": "Диагональ ↙"},
	{"key": "diagonal_se", "title": "Диагональ ↘"},
]
const AUTOTILE_NEIGHBOR_OFFSETS := [
	Vector2i.UP,
	Vector2i(1, -1),
	Vector2i.RIGHT,
	Vector2i(1, 1),
	Vector2i.DOWN,
	Vector2i(-1, 1),
	Vector2i.LEFT,
	Vector2i(-1, -1),
]
const AUTOTILE_PROFILE_FORMAT_VERSION := 1
const ANIMAL_SETTINGS_PATH := "user://map_animal_settings.cfg"
const UNDO_HISTORY_LIMIT := 100
const BIOME_ROOT := "res://assets/base_tails/Biome"
const CRAFTPIX_PACK_ROOT := "res://assets/base_tails/pack"
const ANIMATION_STATES := [
	"idle", "walk", "run", "attack", "hurt", "death", "jump", "fly", "flight", "move", "swim",
]
const MOVEMENT_STATES := ["walk", "run", "jump", "fly", "flight", "move", "swim"]
const CRAFTPIX_PACK_LABELS := {
	"craftpix-net-160005-free-ruined-temple-top-down-location-pixel-art": "Руины храма",
	"craftpix-net-169442-free-2d-top-down-pixel-dungeon-asset-pack": "Подземелье",
	"craftpix-net-189780-free-top-down-pixel-art-guild-hall-asset-pack": "Гильдия",
	"craftpix-net-218281-free-pixel-art-dungeon-objects-asset-pack": "Объекты подземелья",
	"craftpix-net-229968-fantasy-rpg-hunters-lodge-top-down-pixel-art-pack": "Охотничья хижина",
	"craftpix-net-289481-mage-tower-top-down-pixel-art-asset-pack": "Башня мага",
	"craftpix-net-447058-fantasy-rpg-camp-top-down-pixel-art-pack": "Лагерь",
	"craftpix-net-471853-top-down-farm-with-animals-pixel-art-asset-pack": "Ферма и животные",
	"craftpix-net-477438-free-chapel-pixel-art-top-down-asset-pack": "Часовня",
	"craftpix-net-548007-glowing-cave-objects-pixel-art-asset-pack": "Светящаяся пещера",
	"craftpix-net-573594-hp-mana-stamina-and-scroll-bar-pixel-rpg-asset-pack": "Полосы и иконки",
	"craftpix-net-587497-pixel-art-market-square-rpg-shop-and-npc-assets-pack": "Рыночная площадь",
	"craftpix-net-626036-pixel-art-training-arena-tileset-for-rpg-games": "Тренировочная арена",
	"craftpix-net-653272-nobles-manor-pixel-top-down-tileset-asset-pack": "Усадьба",
	"craftpix-net-654184-main-characters-home-free-top-down-pixel-art-asset": "Дом персонажей",
	"craftpix-net-659586-fantasy-rpg-prison-top-down-pixel-art-pack": "Тюрьма",
	"craftpix-net-665895-free-pixel-dungeon-props-and-objects-asset-pack": "Предметы подземелья",
	"craftpix-net-666104-tavern-top-down-pixel-rpg-asset-pack": "Таверна",
	"craftpix-net-692491-free-glassblowers-workshop-top-down-pixel-art-asset": "Мастерская стеклодува",
	"craftpix-net-741016-pixel-blacksmith-house-interior-and-exterior-assets": "Дом кузнеца",
	"craftpix-net-742958-pixel-art-herbalists-hut-top-down-asset-pack": "Хижина травника",
	"craftpix-net-845649-library-inventory-top-down-pixel-art-asset-pack": "Библиотека",
	"craftpix-net-885927-2d-pixel-fishing-village-pack-dock-interior-boats-npcs": "Рыбацкая деревня",
	"craftpix-net-913553-sewer-tileset-and-environment-pixel-art-asset-pack": "Канализация",
}
const GLADES_GRASS_SHEET := "res://assets/base_tails/Biome/craftpix-net-189510-grassland-top-down-tileset-pixel-art/Tiled_files/ground_grasss.png"
const GLADES_GRASS_CENTER := Vector2i(2, 1)
const GLADES_GRASS_ARTIST_PROFILE = preload("res://scripts/glades_grass_artist_profile.gd")
const BRIDGES_ROOT := "res://assets/base_tails/bridges"
const ANIMALS_ROOT := "res://assets/base_tails/animals"
const HERO_ROOT := "res://assets/base_tails/Герои"
const SWORDSMAN_ROOT := HERO_ROOT + "/swordsman"
const MAGE_ROOT := HERO_ROOT + "/mage"
const ARCHER_ROOT := HERO_ROOT + "/archer"
const LPC_ROOT := "res://assets/base_tails/LPC"
const HERO_FRAME_SIZE := 64
const ATLAS_CELL_PREFIX := "atlas|"
const ANIMAL_INSTANCE_PREFIX := "animal|"
const MOB_INSTANCE_PREFIX := "mob|"
const LAYER_TILE := "tile"
const LAYER_DECORATIVE := "decorative"
const LAYER_OBJECT := "object"
const LAYER_ANIMAL := "animal"
const LAYER_MOB := "mob"
const LAYER_GROUP := "group"
const CATEGORY_COLORS := {
	"water": Color(0.13, 0.34, 0.54),
	"road": Color(0.55, 0.44, 0.29),
	"grass": Color(0.24, 0.43, 0.24),
	"forest": Color(0.14, 0.31, 0.19),
	"mountain": Color(0.39, 0.39, 0.38),
	"building": Color(0.54, 0.34, 0.25),
	"animal": Color(0.65, 0.55, 0.37),
}

var _api_prefix := "/api"
var _mode := "front_line"
var _pending_action := ""
var _pending_upload_source: Dictionary = {}
var _catalog: Array[Dictionary] = []
var _catalog_by_key: Dictionary = {}
var _atlas_sheets: Array[Dictionary] = []
var _atlas_sheets_by_path: Dictionary = {}
var _animal_groups: Array[Dictionary] = []
var _animal_groups_by_key: Dictionary = {}
var _animal_brush_settings: Dictionary = {}
var _animal_settings_config_path := ANIMAL_SETTINGS_PATH
var _selected_atlas_path := ""
var _animal_hover_index := -1
var _animal_preview_clips: Array[Dictionary] = []
var _animal_preview_clip_index := 0
var _animal_preview_frame_index := 0
var _animal_preview_elapsed := 0.0
var _animal_preview_step_elapsed := 0.0
var _animal_hover_card: PanelContainer
var _animal_hover_card_key := ""
var _animal_card_pinned_key := ""
var _animal_card_supported: Dictionary = {}
var _animal_card_current_row := ""
var _animal_card_rows: Dictionary = {}
var _animal_card_directions: Dictionary = {}
var _animal_card_panel_styles: Dictionary = {}
var _animal_card_row_styles: Dictionary = {}
var _animal_card_title: Label
var _animal_card_mode: Label
var _animal_card_hint: Label
var _animal_card_state: Label
var _animal_card_settings_button: Button
var _animal_card_close_button: Button
var _pending_mob_profile_key := ""
var _pending_mob_profile_kind := ""
var _pending_mob_profile_settings: Dictionary = {}
var _mob_profile_dialog: Control
var _building_settings_dialog: ConfirmationDialog
var _building_spawn_button: Button
var _building_sprite := "castle_8"
var _building_frame_cache := {}
var _building_anim_frame := 0
var _building_anim_timer: Timer
var _building_palette_icons: Array = []
var _item_form_dialog: Control
var _new_items: Array[Dictionary] = []
var _add_item_button: Button
var _inventory_button: Button
var _inventory_dialog: ConfirmationDialog
var _inventory_list: VBoxContainer
var _inventory_back_button: Button
var _inventory_items: Array[Dictionary] = []
var _inventory_level := "slots"
var _inventory_selected_slot := ""
var _inventory_selected_category := ""
var _pending_item_form: Dictionary = {}
var _editing_item_id := 0
var _selected_atlas_coords := Vector2i.ZERO
var _selected_atlas_region := Rect2i()
var _atlas_annotations: Dictionary = {}
var _atlas_corner_tiles: Dictionary = {}
var _pending_corner_variant := ""
var _corner_variant_select: OptionButton
var _corner_variant_assign_button: Button
var _corner_variant_clear_button: Button
var _corner_assignment_status: Label
var _autotile_profile_save_dialog: FileDialog
var _autotile_profile_load_dialog: FileDialog
var _terrain_generation_dialog: ConfirmationDialog
var _terrain_generation_button: Button
var _terrain_generation_biome_count := 0
var _terrain_generation_biome_count_slider: HSlider
var _terrain_generation_biome_count_value: Label
var _terrain_generation_biome_rows: VBoxContainer
var _terrain_generation_biome_options: Array[Dictionary] = []
var _terrain_generation_width: SpinBox
var _terrain_generation_height: SpinBox
var _terrain_generation_feature_sliders: Dictionary = {}
var _terrain_generation_feature_values: Dictionary = {}
var _last_terrain_generation_settings: Dictionary = {}
var _custom_tile_groups: Dictionary = {}
var _custom_group_by_key: Dictionary = {}
var _active_custom_group_id := ""
var _active_stamp_rows := 1
var _auto_brush_enabled := false
var _active_tool := TOOL_BRUSH
var _selection := Rect2i()
var _stamp_buffer: Dictionary = {}
var _spawns: Array = []
var _spawn_type := SPAWN_RULES.TYPE_HERO
var _spawn_settings_dialog: ConfirmationDialog
var _spawn_settings_index := -1
var _spawn_name_edit: LineEdit
var _spawn_rename_dialog: ConfirmationDialog
var _spawn_rename_index := -1
var _spawn_rename_edit: LineEdit
var _spawn_mob_select: OptionButton
var _spawn_target_select: OptionButton
var _spawn_target_row: HBoxContainer
var _spawn_wave_count_spin: SpinBox
var _spawn_wave_select: OptionButton
var _spawn_wave_configs: Array[Dictionary] = []
var _spawn_wave_index := 0
var _spawn_start_delay_edit: LineEdit
var _spawn_count_spin: SpinBox
var _spawn_squad_min_spin: SpinBox
var _spawn_squad_max_spin: SpinBox
var _spawn_squad_preview_label: Label
var _spawn_interval_edit: LineEdit
var _spawn_boss_checkbox: CheckBox
var _spawn_boss_fields: VBoxContainer
var _spawn_boss_hp_spin: SpinBox
var _spawn_boss_mp_spin: SpinBox
var _spawn_boss_reward_xp_spin: SpinBox
var _spawn_boss_spell_slots: Array[Dictionary] = []
var _spawn_item_catalog: Array[Dictionary] = []
var _spawn_boss_drop_controls: Array[Dictionary] = []
var _select_drag: Dictionary = {}
var _hover_cell := Vector2i(-1, -1)
var _local_drafts_folder: String = DRAFTS_RULES.DEFAULT_FOLDER
var _local_draft_id := ""
var _publish_world_name := ""
var _publish_request_world_id := 0
var _publish_request_world_name := ""
var _test_world_button: Button
var _test_world_request: HTTPRequest
var _test_world_after_save := false
var _minimap_visible := false
var _minimap_dirty := true
var _minimap_dragging := false
var _minimap_texture: ImageTexture
var _minimap_built_msec := 0
var _minimap_button: Button
var _annotation_config_path := ATLAS_ANNOTATIONS_PATH
var _stroke_button := MOUSE_BUTTON_NONE
var _last_stroke_cell := Vector2i(-1, -1)
var _stroke_snapshot: Array[Dictionary] = []
var _stroke_spawns: Array = []
var _stroke_active_layer_id := 0
var _undo_stack: Array[Dictionary] = []
var _redo_stack: Array[Dictionary] = []
var _saved_maps: Array[Dictionary] = []
var _initial_saved_map_id := 0
var _initial_map_setup: Dictionary = {}
var _layers: Array[Dictionary] = []
var _next_layer_id := 1
var _active_layer_id := 0
var _selected_item_key := ""
var _saved_id := 0
var _last_save_merged_cells := 0
var _saved_maps_status := ""
var _pan := Vector2(40, 35)
var _zoom := 1.0
var _pan_dragging := false
var _asset_requests: Dictionary = {}
var _textures: Dictionary = {}
var _worlds: Array[Dictionary] = []
var _sheet_tabs: VBoxContainer
var _sheet_tabs_scroll: ScrollContainer
var _biome_list: VBoxContainer
var _biome_buttons: Dictionary = {}
var _sheet_buttons: Dictionary = {}
var _selected_biome_path := ""
var _atlas_scroll: ScrollContainer
var _atlas_palette: Control
var _animal_palette: ItemList
var _atlas_info: Label
var _annotation_controls: VBoxContainer
var _annotation_height_select: OptionButton
var _brush_button: Button
var _auto_brush_button: Button
var _undo_button: Button
var _redo_button: Button
var _fill_button: Button
var _select_button: Button
var _stamp_button: Button
var _hero_spawn_button: Button
var _mob_spawn_button: Button
var _local_draft_select: OptionButton
var _canvas_brush_controls: HBoxContainer
var _publish_group_button: Button
var _publish_group_name: LineEdit
var _publish_group_category: OptionButton
var _catalog_tab: Button
var _workspace: Control
var _floating_panels: Array[Control] = []
var _panels_placed := false
var _layer_panel: VBoxContainer
var _layer_passable_select: OptionButton
var _passability_button: Button
var _show_passability := false
var _ui_root: VBoxContainer

var _status: Label
var _canvas: Control
var _layer_list: ScrollContainer
var _layer_info: Label
var _palette: ItemList
var _layer_name: LineEdit
var _layer_type: OptionButton
var _map_name: LineEdit
var _map_width: SpinBox
var _map_height: SpinBox
var _saved_select: OptionButton
var _save_draft_button: Button
var _load_draft_button: Button
var _refresh_drafts_button: Button
var _publish_select: OptionButton
var _mode_label: Label
var _editor_version_label: Label
var _version_overlay: ColorRect
var _version_overlay_message: Label
var _version_retry_button: Button
var _loading_overlay: ColorRect
var _loading_message: Label
var _loading_progress: ProgressBar
var _loading_progress_target := 0.0
var _loading_preview_area: Control
var _loading_preview: TextureRect
var _loading_preview_frames: Array[Texture2D] = []
var _loading_preview_frame := 0
var _loading_preview_elapsed := 0.0
var _loading_preview_mobile := false
var _loading_preview_travel := 0.0


func _ready() -> void:
	_initial_map_setup = GameSession.map_editor_setup.duplicate(true)
	GameSession.map_editor_setup.clear()
	if not _is_map_moderator():
		_show_access_denied()
		return
	if GameSession.world_token.is_empty():
		if GameSession.token.is_empty() or not ApiClient.set_server_url(GameSession.hub_url):
			_set_status("Войдите в аккаунт, чтобы открыть редактор карт.")
			return
		ApiClient.token = GameSession.token
		_mode = str(_initial_map_setup.get("mode", "front_line"))
	else:
		_mode = str(GameSession.world.get("mode", "front_line"))
		var world_url := str(GameSession.world.get("server_url", "")).strip_edges()
		if not ApiClient.set_server_url(world_url):
			_set_status("У выбранного мира неверный адрес сервера.")
			return
		ApiClient.token = GameSession.world_token
	_initial_saved_map_id = int(_initial_map_setup.get("saved_id", 0))
	_api_prefix = "/api/deck" if _mode == "deck" and not GameSession.world_token.is_empty() else "/api"
	_create_loading_overlay()
	_set_loading_stage(
		"Загрузка биомов", LOADING_TREE_SHEET, Vector2i(160, 160), 6, 0, false,
	)
	_set_loading_progress(0, "Загрузка биомов")
	await get_tree().process_frame
	ApiClient.request_completed.connect(_on_api_completed)
	_load_atlas_annotations(_annotation_config_path)
	var animal_settings_error := _load_animal_brush_settings(_animal_settings_config_path)
	if animal_settings_error != OK:
		_set_status("Не удалось загрузить настройки существ.")
	_set_loading_progress(5, "Подготовка редактора")
	_build_ui()
	_loading_overlay.move_to_front()
	await get_tree().process_frame
	await _discover_atlas_sheets()
	_create_default_layers()
	_render_layers()
	_pending_action = "catalog"
	if _initial_saved_map_id == 0:
		_map_name.text = str(_initial_map_setup.get("name", ""))
		_map_width.value = int(_initial_map_setup.get("map_w", DEFAULT_MAP_SIZE))
		_map_height.value = int(_initial_map_setup.get("map_h", DEFAULT_MAP_SIZE))
	_set_loading_progress(78, "Подключение к серверу")
	_check_editor_server_version()


func _create_loading_overlay() -> void:
	_loading_overlay = ColorRect.new()
	_loading_overlay.color = Color(0.035, 0.04, 0.05, 1.0)
	_loading_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_loading_overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	_loading_overlay.z_index = 200
	add_child(_loading_overlay)

	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_loading_overlay.add_child(center)
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(560, 340)
	var panel_style := StyleBoxFlat.new()
	panel_style.bg_color = Color(0.055, 0.075, 0.11, 0.98)
	panel_style.border_color = Color(0.24, 0.43, 0.62, 0.9)
	panel_style.set_border_width_all(2)
	panel_style.set_corner_radius_all(18)
	panel_style.set_content_margin_all(24)
	panel.add_theme_stylebox_override("panel", panel_style)
	center.add_child(panel)
	var content := VBoxContainer.new()
	content.add_theme_constant_override("separation", 14)
	panel.add_child(content)
	var title := Label.new()
	title.text = "ПОДГОТОВКА МИРА"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_color_override("font_color", Color(0.95, 0.79, 0.43))
	title.add_theme_font_size_override("font_size", 22)
	content.add_child(title)
	_loading_message = Label.new()
	_loading_message.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_loading_message.add_theme_color_override("font_color", Color(0.86, 0.91, 0.98))
	_loading_message.add_theme_font_size_override("font_size", 17)
	_loading_message.text = "Загрузка биомов"
	content.add_child(_loading_message)
	var preview_frame := PanelContainer.new()
	preview_frame.custom_minimum_size = Vector2(480, 164)
	var preview_style := StyleBoxFlat.new()
	preview_style.bg_color = Color(0.025, 0.04, 0.065, 0.9)
	preview_style.border_color = Color(0.18, 0.3, 0.43, 0.8)
	preview_style.set_border_width_all(1)
	preview_style.set_corner_radius_all(12)
	preview_frame.add_theme_stylebox_override("panel", preview_style)
	content.add_child(preview_frame)
	_loading_preview_area = Control.new()
	_loading_preview_area.custom_minimum_size = Vector2(468, 152)
	_loading_preview_area.clip_contents = true
	preview_frame.add_child(_loading_preview_area)
	_loading_preview = TextureRect.new()
	_loading_preview.size = Vector2(144, 144)
	_loading_preview.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_loading_preview.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_loading_preview.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_loading_preview_area.add_child(_loading_preview)
	_loading_progress = ProgressBar.new()
	_loading_progress.min_value = 0
	_loading_progress.max_value = 100
	_loading_progress.value = 0
	_loading_progress.show_percentage = true
	_loading_progress.custom_minimum_size.y = 18
	var progress_background := StyleBoxFlat.new()
	progress_background.bg_color = Color(0.02, 0.035, 0.055)
	progress_background.set_corner_radius_all(9)
	var progress_fill := StyleBoxFlat.new()
	progress_fill.bg_color = Color(0.31, 0.72, 0.62)
	progress_fill.set_corner_radius_all(9)
	_loading_progress.add_theme_stylebox_override("background", progress_background)
	_loading_progress.add_theme_stylebox_override("fill", progress_fill)
	content.add_child(_loading_progress)


func _set_loading_stage(
	message: String,
	sheet_path: String,
	frame_size: Vector2i,
	frame_count: int,
	frame_row: int,
	mobile: bool,
) -> void:
	_loading_preview_frames.clear()
	_loading_preview_frame = 0
	_loading_preview_elapsed = 0.0
	_loading_preview_mobile = mobile
	_loading_preview_travel = 0.0
	_loading_message.text = message
	var sheet := load(sheet_path) as Texture2D
	if sheet == null:
		push_warning("Не удалось загрузить изображение экрана загрузки: " + sheet_path)
		_loading_preview.texture = null
		return
	if frame_size.x <= 0 or frame_size.y <= 0:
		push_warning("Неверный размер кадра экрана загрузки: " + sheet_path)
		_loading_preview.texture = sheet
		return
	var rows := floori(float(sheet.get_height()) / float(frame_size.y))
	if frame_row < 0 or frame_row >= rows:
		push_warning("Неверная разметка анимации экрана загрузки: " + sheet_path)
		_loading_preview.texture = sheet
		return
	var columns := mini(frame_count, floori(float(sheet.get_width()) / float(frame_size.x)))
	for column in range(columns):
		var frame := AtlasTexture.new()
		frame.atlas = sheet
		frame.region = Rect2(
			column * frame_size.x, frame_row * frame_size.y, frame_size.x, frame_size.y,
		)
		_loading_preview_frames.append(frame)
	_loading_preview.texture = _loading_preview_frames[0] if not _loading_preview_frames.is_empty() else sheet


func _set_loading_progress(percent: int, message: String) -> void:
	if not is_instance_valid(_loading_overlay):
		return
	_loading_progress_target = clampf(float(percent), 0.0, 100.0)
	_loading_message.text = message


func _advance_loading_progress(done: int, total: int, message: String, yield_frame := true) -> int:
	done += 1
	var percent := mini(75, 5 + roundi(float(done) / float(maxi(total, 1)) * 70.0))
	_set_loading_progress(percent, message)
	if is_inside_tree() and (yield_frame or done % 8 == 0):
		await get_tree().process_frame
	return done


func _finish_loading_overlay() -> void:
	if not is_instance_valid(_loading_overlay):
		return
	_loading_overlay.queue_free()
	_loading_overlay = null


func _check_editor_server_version() -> void:
	if is_instance_valid(_loading_overlay):
		_set_loading_progress(80, "Проверка сервера")
	_show_version_overlay("Проверяем совместимость редактора и сервера…")
	_pending_action = "editor_version"
	ApiClient.request_json(
		HTTPClient.METHOD_GET,
		"/api/version?app=editor&version=%s&protocol=%d" % [
			ApiClient.EDITOR_VERSION,
			ApiClient.PROTOCOL_VERSION,
		],
		{},
		false,
	)


func _exit_tree() -> void:
	if ApiClient.request_completed.is_connected(_on_api_completed):
		ApiClient.request_completed.disconnect(_on_api_completed)
	for request in _asset_requests.values():
		if is_instance_valid(request):
			request.queue_free()
	_asset_requests.clear()


func _process(delta: float) -> void:
	if is_instance_valid(_loading_progress):
		_loading_progress.value = move_toward(
			_loading_progress.value, _loading_progress_target, delta * 180.0,
		)
	if is_instance_valid(_loading_preview) and is_instance_valid(_loading_preview_area):
		_loading_preview_elapsed += delta
		if _loading_preview_elapsed >= 0.13 and not _loading_preview_frames.is_empty():
			_loading_preview_elapsed = fmod(_loading_preview_elapsed, 0.13)
			_loading_preview_frame = (
				_loading_preview_frame + 1
			) % _loading_preview_frames.size()
			_loading_preview.texture = _loading_preview_frames[_loading_preview_frame]
		if _loading_preview_mobile:
			_loading_preview_travel = fposmod(
				_loading_preview_travel + delta * 110.0,
				_loading_preview_area.size.x + _loading_preview.size.x,
			)
			_loading_preview.position.x = _loading_preview_travel - _loading_preview.size.x
		else:
			_loading_preview.position.x = (
				_loading_preview_area.size.x - _loading_preview.size.x
			) * 0.5 + sin(Time.get_ticks_msec() / 700.0) * 4.0
		_loading_preview.position.y = (
			_loading_preview_area.size.y - _loading_preview.size.y
		) * 0.5
	if (not _atlas_sheets.is_empty() and _has_atlas_animations_in_map()) \
		or _has_animal_instances_in_map():
		_canvas.queue_redraw()
	_update_animal_palette_hover(delta)


func _has_atlas_animations_in_map() -> bool:
	for layer in _layers:
		for value in layer.get("cells", {}).values():
			var atlas_cell := _decode_atlas_cell(str(value))
			if atlas_cell.is_empty():
				continue
			var sheet: Dictionary = _atlas_sheets_by_path.get(str(atlas_cell["path"]), {})
			var animations: Dictionary = sheet.get("animations", {})
			var coords: Vector2i = atlas_cell["coords"]
			var tile_id := coords.y * int(sheet.get("columns", 0)) + coords.x
			if animations.has(tile_id):
				return true
	return false


func _is_map_moderator() -> bool:
	var role := str(GameSession.user.get("role", ""))
	return role == "moderator" or role == "admin"


func _build_ui() -> void:
	var root := VBoxContainer.new()
	_ui_root = root
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var editor_theme := Theme.new()
	editor_theme.default_base_scale = EDITOR_UI_SCALE
	editor_theme.default_font_size = roundi(16 * EDITOR_UI_SCALE)
	root.theme = editor_theme
	root.add_theme_constant_override("separation", roundi(6 * EDITOR_UI_SCALE))
	add_child(root)

	var toolbar := HFlowContainer.new()
	toolbar.add_theme_constant_override("h_separation", roundi(4 * EDITOR_UI_SCALE))
	toolbar.add_theme_constant_override("v_separation", roundi(4 * EDITOR_UI_SCALE))
	root.add_child(toolbar)
	var back_button := Button.new()
	back_button.text = "Назад"
	back_button.pressed.connect(_leave_editor)
	toolbar.add_child(back_button)
	_mode_label = Label.new()
	_mode_label.text = "Режим: " + str(WorldModeRegistry.describe(_mode).get("name", _mode))
	toolbar.add_child(_mode_label)
	_editor_version_label = Label.new()
	_editor_version_label.text = "Редактор %s" % ApiClient.EDITOR_VERSION
	toolbar.add_child(_editor_version_label)
	_map_name = LineEdit.new()
	_map_name.placeholder_text = "Название карты"
	_map_name.custom_minimum_size.x = roundi(130 * EDITOR_UI_SCALE)
	toolbar.add_child(_map_name)
	_map_width = _new_spinbox(16, 1600, DEFAULT_MAP_SIZE)
	_map_height = _new_spinbox(16, 1600, DEFAULT_MAP_SIZE)
	toolbar.add_child(_labeled_control("Ширина", _map_width))
	toolbar.add_child(_labeled_control("Высота", _map_height))
	_save_draft_button = Button.new()
	_save_draft_button.text = "Сохранить"
	_save_draft_button.tooltip_text = "Сохранить текущую карту на сервере как черновик"
	_save_draft_button.pressed.connect(_save_map)
	toolbar.add_child(_save_draft_button)
	_saved_select = OptionButton.new()
	_saved_select.custom_minimum_size.x = roundi(120 * EDITOR_UI_SCALE)
	_saved_select.add_item("Черновики")
	toolbar.add_child(_saved_select)
	_load_draft_button = Button.new()
	_load_draft_button.text = "Загрузить"
	_load_draft_button.tooltip_text = "Загрузить выбранный черновик карты"
	_load_draft_button.pressed.connect(_load_selected_map)
	toolbar.add_child(_load_draft_button)
	_refresh_drafts_button = Button.new()
	_refresh_drafts_button.text = "Обновить"
	_refresh_drafts_button.tooltip_text = "Обновить список черновиков с сервера"
	_refresh_drafts_button.pressed.connect(_load_saved_maps)
	toolbar.add_child(_refresh_drafts_button)
	var publish_button := Button.new()
	publish_button.text = "Публикация"
	publish_button.pressed.connect(_load_worlds_for_publish)
	toolbar.add_child(publish_button)
	_test_world_button = Button.new()
	_test_world_button.text = "Тестовый мир"
	_test_world_button.tooltip_text = "Создать тестовый мир Колоды из этой карты. Карта сначала сохранится на сервере; создаёт только админ"
	_test_world_button.pressed.connect(_create_test_world)
	toolbar.add_child(_test_world_button)
	var generate_button := Button.new()
	generate_button.text = "Из мира"
	generate_button.tooltip_text = "Заполнить карту рельефом опубликованной карты мира (режим Колоды). Отмена — Ctrl+Z"
	generate_button.pressed.connect(_generate_from_world)
	toolbar.add_child(generate_button)
	var terrain_button := Button.new()
	terrain_button.text = "Тест тайлов"
	terrain_button.pressed.connect(_open_terrain_demo)
	toolbar.add_child(terrain_button)
	_terrain_generation_button = Button.new()
	_terrain_generation_button.text = "Генерировать карту"
	_terrain_generation_button.tooltip_text = "Настроить размер карты, биомы, воду, горы и лес"
	_terrain_generation_button.pressed.connect(_show_terrain_generation_dialog)
	toolbar.add_child(_terrain_generation_button)

	var local_toolbar := HFlowContainer.new()
	local_toolbar.add_theme_constant_override("h_separation", roundi(4 * EDITOR_UI_SCALE))
	local_toolbar.add_theme_constant_override("v_separation", roundi(4 * EDITOR_UI_SCALE))
	root.add_child(local_toolbar)
	var local_caption := Label.new()
	local_caption.text = "Локально:"
	local_toolbar.add_child(local_caption)
	_local_draft_select = OptionButton.new()
	_local_draft_select.custom_minimum_size.x = roundi(150 * EDITOR_UI_SCALE)
	local_toolbar.add_child(_local_draft_select)
	var local_save_button := Button.new()
	local_save_button.text = "Сохранить"
	local_save_button.tooltip_text = "Сохранить карту в черновик на этом компьютере, сервер не нужен"
	local_save_button.pressed.connect(_save_local_draft)
	local_toolbar.add_child(local_save_button)
	var local_open_button := Button.new()
	local_open_button.text = "Открыть"
	local_open_button.tooltip_text = "Открыть выбранный черновик с этого компьютера"
	local_open_button.pressed.connect(_open_selected_local_draft)
	local_toolbar.add_child(local_open_button)
	var local_delete_button := Button.new()
	local_delete_button.text = "Удалить локально"
	local_delete_button.tooltip_text = "Удалить выбранный черновик с этого компьютера"
	local_delete_button.pressed.connect(_request_delete_local_draft)
	local_toolbar.add_child(local_delete_button)

	# Рабочая область: каждый блок (биомы, листы, палитра, холст, слои) двигается и меняет размер мышью.
	_workspace = Control.new()
	_workspace.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_workspace.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_workspace.clip_contents = true
	_workspace.custom_minimum_size = Vector2(320, 320)
	_workspace.resized.connect(_layout_initial_panels)
	root.add_child(_workspace)

	var palette_panel := HBoxContainer.new()
	palette_panel.custom_minimum_size.x = roundi(360 * EDITOR_UI_SCALE)

	var biome_panel := VBoxContainer.new()
	biome_panel.custom_minimum_size.x = roundi(110 * EDITOR_UI_SCALE)
	palette_panel.add_child(biome_panel)
	var biome_title := Label.new()
	biome_title.text = "Биомы"
	biome_panel.add_child(biome_title)
	var biome_scroll := ScrollContainer.new()
	biome_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	biome_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	biome_panel.add_child(biome_scroll)
	_biome_list = VBoxContainer.new()
	_biome_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	biome_scroll.add_child(_biome_list)

	var sheet_panel := VBoxContainer.new()
	sheet_panel.custom_minimum_size.x = roundi(115 * EDITOR_UI_SCALE)
	palette_panel.add_child(sheet_panel)
	var sheet_title := Label.new()
	sheet_title.text = "Листы"
	sheet_panel.add_child(sheet_title)
	_sheet_tabs_scroll = ScrollContainer.new()
	_sheet_tabs_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_sheet_tabs_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	_sheet_tabs_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	sheet_panel.add_child(_sheet_tabs_scroll)
	_sheet_tabs = VBoxContainer.new()
	_sheet_tabs.add_theme_constant_override("separation", roundi(4 * EDITOR_UI_SCALE))
	_sheet_tabs_scroll.add_child(_sheet_tabs)

	var atlas_panel := VBoxContainer.new()
	atlas_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	atlas_panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	palette_panel.add_child(atlas_panel)
	_atlas_info = Label.new()
	_atlas_info.text = "Выберите лист"
	atlas_panel.add_child(_atlas_info)
	_corner_assignment_status = Label.new()
	_corner_assignment_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_corner_assignment_status.visible = false
	atlas_panel.add_child(_corner_assignment_status)
	_add_item_button = Button.new()
	_add_item_button.text = "+ Добавить предмет"
	_add_item_button.tooltip_text = "Создать предмет экипировки для текущего режима"
	_add_item_button.pressed.connect(_open_item_form)
	atlas_panel.add_child(_add_item_button)
	_annotation_controls = VBoxContainer.new()
	_annotation_controls.add_theme_constant_override("separation", roundi(4 * EDITOR_UI_SCALE))
	_annotation_height_select = OptionButton.new()
	for rows in [3, 4, 5]:
		_annotation_height_select.add_item("3×%d" % rows)
		_annotation_height_select.set_item_metadata(_annotation_height_select.item_count - 1, rows)
	_annotation_height_select.select(0)
	_annotation_height_select.tooltip_text = "Автокисть: 3×3, 3×4 или 3×5"
	_annotation_height_select.item_selected.connect(_on_autotile_rows_selected)
	_corner_variant_select = OptionButton.new()
	for corner_variant in AUTOTILE_CORNER_VARIANTS:
		_corner_variant_select.add_item(str(corner_variant["title"]))
		_corner_variant_select.set_item_metadata(
			_corner_variant_select.item_count - 1,
			str(corner_variant["key"]),
		)
	for mask in range(256):
		var mask_key := _autotile_mask_key(mask)
		_corner_variant_select.add_item(_autotile_mask_title(mask))
		_corner_variant_select.set_item_metadata(_corner_variant_select.item_count - 1, mask_key)
	_corner_variant_select.select(0)
	_corner_variant_select.tooltip_text = "Выберите один из 256 рисунков соседей или особый угол, затем назначьте ему любой тайл атласа."
	_corner_variant_select.item_selected.connect(_on_corner_variant_selected)
	_corner_variant_assign_button = Button.new()
	_corner_variant_assign_button.text = "Назначить тайл"
	_corner_variant_assign_button.toggle_mode = true
	_corner_variant_assign_button.tooltip_text = "Нажмите — кнопка останется включённой. Затем щёлкните нужный тайл в палитре."
	_corner_variant_assign_button.toggled.connect(_on_corner_assignment_button_toggled)
	_corner_variant_clear_button = Button.new()
	_corner_variant_clear_button.text = "Сбросить"
	_corner_variant_clear_button.tooltip_text = "Убрать тайл для выбранного варианта угла."
	_corner_variant_clear_button.pressed.connect(_clear_corner_tile_assignment)
	_publish_group_button = Button.new()
	_publish_group_button.text = "Опубликовать группу"
	_publish_group_button.disabled = true
	_publish_group_button.pressed.connect(_show_publish_group_dialog)
	_atlas_scroll = ScrollContainer.new()
	_atlas_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_atlas_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	_atlas_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	atlas_panel.add_child(_atlas_scroll)
	_atlas_palette = ATLAS_PALETTE_SCRIPT.new()
	_atlas_palette.tile_selected.connect(_on_atlas_tile_selected)
	_atlas_palette.region_selected.connect(_on_atlas_region_selected)
	_atlas_scroll.add_child(_atlas_palette)
	_palette = ItemList.new()
	_palette.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_palette.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_palette.select_mode = ItemList.SELECT_SINGLE
	_palette.item_selected.connect(_on_palette_item_selected)
	_palette.visible = false
	atlas_panel.add_child(_palette)
	_animal_palette = ANIMATED_PALETTE_SCRIPT.new()
	_animal_palette.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_animal_palette.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_animal_palette.select_mode = ItemList.SELECT_SINGLE
	_animal_palette.icon_mode = ItemList.ICON_MODE_TOP
	_animal_palette.fixed_icon_size = Vector2i(
		ANIMAL_PALETTE_ICON_SIZE,
		ANIMAL_PALETTE_ICON_SIZE,
	)
	_animal_palette.visible = false
	_animal_palette.item_selected.connect(_on_animal_item_selected)
	_animal_palette.item_activated.connect(_on_animal_item_activated)
	_animal_palette.gui_input.connect(_on_animal_palette_gui_input)
	atlas_panel.add_child(_animal_palette)
	_build_animal_hover_card(editor_theme)

	var canvas_container := VBoxContainer.new()
	canvas_container.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	canvas_container.size_flags_vertical = Control.SIZE_EXPAND_FILL
	var canvas_toolbar := HBoxContainer.new()
	canvas_toolbar.add_theme_constant_override("separation", roundi(6 * EDITOR_UI_SCALE))
	canvas_container.add_child(canvas_toolbar)
	var brush_group := ButtonGroup.new()
	_brush_button = Button.new()
	_brush_button.text = "Кисть"
	_brush_button.toggle_mode = true
	_brush_button.button_group = brush_group
	_brush_button.button_pressed = true
	_brush_button.pressed.connect(_set_auto_brush.bind(false))
	canvas_toolbar.add_child(_brush_button)
	_auto_brush_button = Button.new()
	_auto_brush_button.text = "Автокисть"
	_auto_brush_button.toggle_mode = true
	_auto_brush_button.button_group = brush_group
	_auto_brush_button.pressed.connect(_set_auto_brush.bind(true))
	canvas_toolbar.add_child(_auto_brush_button)
	_fill_button = Button.new()
	_fill_button.text = "Заливка (F)"
	_fill_button.toggle_mode = true
	_fill_button.button_group = brush_group
	_fill_button.pressed.connect(_select_tool.bind(TOOL_FILL))
	canvas_toolbar.add_child(_fill_button)
	_select_button = Button.new()
	_select_button.text = "Выделение (V)"
	_select_button.toggle_mode = true
	_select_button.button_group = brush_group
	_select_button.pressed.connect(_select_tool.bind(TOOL_SELECT))
	canvas_toolbar.add_child(_select_button)
	_stamp_button = Button.new()
	_stamp_button.text = "Вставка (Ctrl+V)"
	_stamp_button.toggle_mode = true
	_stamp_button.button_group = brush_group
	_stamp_button.pressed.connect(_select_tool.bind(TOOL_STAMP))
	canvas_toolbar.add_child(_stamp_button)
	_undo_button = Button.new()
	_undo_button.text = "Отменить (Ctrl+Z)"
	_undo_button.disabled = true
	_undo_button.pressed.connect(_undo_last_action)
	canvas_toolbar.add_child(_undo_button)
	_redo_button = Button.new()
	_redo_button.text = "Повторить (Ctrl+Y)"
	_redo_button.disabled = true
	_redo_button.pressed.connect(_redo_last_action)
	canvas_toolbar.add_child(_redo_button)
	_minimap_button = Button.new()
	_minimap_button.text = "Миникарта (M)"
	_minimap_button.toggle_mode = true
	_minimap_button.button_pressed = false
	_minimap_button.pressed.connect(_toggle_minimap)
	canvas_toolbar.add_child(_minimap_button)
	_passability_button = Button.new()
	_passability_button.text = "Проходимость"
	_passability_button.toggle_mode = true
	_passability_button.tooltip_text = "Подсветить клетки, заблокированные слоями непроходимости"
	_passability_button.toggled.connect(_on_passability_toggled)
	canvas_toolbar.add_child(_passability_button)
	_annotation_controls.add_child(_annotation_height_select)
	_annotation_controls.add_child(_corner_variant_select)
	_annotation_controls.add_child(_corner_variant_assign_button)
	_annotation_controls.add_child(_corner_variant_clear_button)
	var save_profile_button := Button.new()
	save_profile_button.text = "Сохранить профиль"
	save_profile_button.tooltip_text = "Экспортировать настройки выбранной группы в переносимый JSON"
	save_profile_button.pressed.connect(_show_autotile_profile_save_dialog)
	_annotation_controls.add_child(save_profile_button)
	var load_profile_button := Button.new()
	load_profile_button.text = "Загрузить профиль"
	load_profile_button.tooltip_text = "Импортировать профиль JSON для выбранной группы атласа"
	load_profile_button.pressed.connect(_show_autotile_profile_load_dialog)
	_annotation_controls.add_child(load_profile_button)
	_canvas = CANVAS_SCRIPT.new()
	_canvas.editor = self
	_canvas.custom_minimum_size = Vector2(320, 320)
	_canvas.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_canvas.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_canvas.clip_contents = true
	_canvas.mouse_filter = Control.MOUSE_FILTER_STOP
	# Холст занимает всю область блока и меняет размер вместе с рамкой.
	var canvas_viewport := Control.new()
	canvas_viewport.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	canvas_viewport.size_flags_vertical = Control.SIZE_EXPAND_FILL
	canvas_viewport.clip_contents = true
	canvas_container.add_child(canvas_viewport)
	canvas_viewport.add_child(_canvas)
	_canvas.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_canvas.mouse_exited.connect(_on_canvas_mouse_exited)

	_layer_panel = VBoxContainer.new()
	_layer_panel.custom_minimum_size.x = 170
	_layer_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var side_panel_scroll := ScrollContainer.new()
	side_panel_scroll.custom_minimum_size.x = 190
	side_panel_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	side_panel_scroll.clip_contents = true
	side_panel_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	side_panel_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	side_panel_scroll.add_child(_layer_panel)
	var autotile_title := Label.new()
	autotile_title.text = "Автокисть"
	_layer_panel.add_child(autotile_title)
	_layer_panel.add_child(_annotation_controls)
	_layer_panel.add_child(_publish_group_button)
	_hero_spawn_button = Button.new()
	_hero_spawn_button.toggle_mode = true
	_hero_spawn_button.button_group = brush_group
	_hero_spawn_button.tooltip_text = "Размещать и редактировать точки возрождения игроков"
	_hero_spawn_button.pressed.connect(_select_spawn_type.bind(SPAWN_RULES.TYPE_HERO))
	_layer_panel.add_child(_hero_spawn_button)
	_mob_spawn_button = Button.new()
	_mob_spawn_button.toggle_mode = true
	_mob_spawn_button.button_group = brush_group
	_mob_spawn_button.tooltip_text = "Размещать точки появления ЛПС; двойной щелчок открывает индивидуальные настройки"
	_mob_spawn_button.pressed.connect(_select_spawn_type.bind(SPAWN_RULES.TYPE_MOB))
	_layer_panel.add_child(_mob_spawn_button)
	_building_spawn_button = Button.new()
	_building_spawn_button.toggle_mode = true
	_building_spawn_button.button_group = brush_group
	_building_spawn_button.tooltip_text = "Размещать главные здания; двойной щелчок открывает оборону и здоровье"
	_building_spawn_button.pressed.connect(_select_spawn_type.bind(SPAWN_RULES.TYPE_BUILDING))
	_layer_panel.add_child(_building_spawn_button)
	_inventory_button = Button.new()
	_inventory_button.text = "Инвентарь"
	_inventory_button.tooltip_text = "Предметы экипировки для выбранного режима"
	_inventory_button.pressed.connect(_open_inventory)
	_inventory_button.visible = _mode != "deck"
	_layer_panel.add_child(_inventory_button)
	_refresh_spawn_button()
	var side_separator := HSeparator.new()
	_layer_panel.add_child(side_separator)
	var layer_title := Label.new()
	layer_title.text = "Слои"
	_layer_panel.add_child(layer_title)
	_layer_list = LAYER_LIST_SCRIPT.new()
	_layer_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_layer_list.clip_contents = true
	_layer_list.custom_minimum_size.y = 160
	_layer_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_layer_list.layer_selected.connect(_on_layer_list_selected)
	_layer_list.visibility_toggled.connect(_on_layer_visibility_toggled)
	_layer_list.layer_renamed.connect(_on_layer_renamed)
	_layer_list.layer_dropped.connect(_on_layer_dropped)
	_layer_panel.add_child(_layer_list)
	_layer_info = Label.new()
	_layer_info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_layer_info.add_theme_color_override("font_color", Color(0.68, 0.72, 0.78))
	_layer_panel.add_child(_layer_info)
	_layer_type = OptionButton.new()
	_layer_type.add_item("Слой тайлов", 0)
	_layer_type.add_item("Слой объектов", 1)
	_layer_type.add_item("Группа слоёв", 2)
	_layer_type.add_item("Слой животных", 3)
	_layer_type.add_item("Слой мобов", 4)
	_layer_type.add_item("Декоративный (только вид)", 5)
	_layer_type.add_item("Слой изображений (позже)", 6)
	_layer_type.set_item_disabled(6, true)
	_layer_panel.add_child(_layer_type)
	_layer_passable_select = OptionButton.new()
	_layer_passable_select.add_item("Проходимый", 0)
	_layer_passable_select.add_item("Непроходимый", 1)
	_layer_passable_select.select(0)
	_layer_passable_select.tooltip_text = "Проходимость слоя: клетки слоя проходимы или нет"
	_layer_type.item_selected.connect(_on_new_layer_type_selected)
	_layer_panel.add_child(_layer_passable_select)
	_layer_name = LineEdit.new()
	_layer_name.placeholder_text = "Название нового слоя"
	_layer_panel.add_child(_layer_name)
	var layer_actions := GridContainer.new()
	layer_actions.columns = 2
	_layer_panel.add_child(layer_actions)
	_add_layer_action(layer_actions, "Добавить", _add_layer)
	_add_layer_action(layer_actions, "Имя", _rename_layer, "Переименовать выбранный слой")
	_add_layer_action(layer_actions, "Вверх", _move_layer.bind(1))
	_add_layer_action(layer_actions, "Вниз", _move_layer.bind(-1))
	_add_layer_action(layer_actions, "Замок", _toggle_layer_lock, "Заблокировать или разблокировать слой")
	_add_layer_action(layer_actions, "Дубль", _duplicate_layer, "Дублировать выбранный слой")
	_add_layer_action(layer_actions, "Проход.", _toggle_layer_passable, "Переключить проходимость выбранного слоя")
	_add_layer_action(layer_actions, "Удалить", _delete_layer)

	canvas_container.custom_minimum_size = Vector2(320, 320)
	_add_floating_panel("biomes", "Биомы", biome_panel)
	_add_floating_panel("sheets", "Листы", sheet_panel)
	_add_floating_panel("palette", "Палитра", atlas_panel)
	_add_floating_panel("canvas", "Холст", canvas_container)
	_add_floating_panel("side", "Слои и инструменты", side_panel_scroll)
	_layout_initial_panels()
	# Все кнопки и надписи редактора выровнены по левому краю, включая созданные позже.
	_align_controls_left(root)
	get_tree().node_added.connect(_on_node_added_align_left)

	_status = Label.new()
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	root.add_child(_status)
	_version_overlay = ColorRect.new()
	_version_overlay.color = Color(0.02, 0.025, 0.035, 0.88)
	_version_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_version_overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	_version_overlay.z_index = 100
	add_child(_version_overlay)
	var overlay_center := CenterContainer.new()
	overlay_center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_version_overlay.add_child(overlay_center)
	var overlay_content := VBoxContainer.new()
	overlay_content.alignment = BoxContainer.ALIGNMENT_CENTER
	overlay_content.add_theme_constant_override("separation", 18)
	overlay_center.add_child(overlay_content)
	_version_overlay_message = Label.new()
	_version_overlay_message.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_version_overlay_message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_version_overlay_message.custom_minimum_size = Vector2(640, 80)
	overlay_content.add_child(_version_overlay_message)
	_version_retry_button = Button.new()
	_version_retry_button.text = "Повторить проверку"
	_version_retry_button.custom_minimum_size = Vector2(220, 42)
	_version_retry_button.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	_version_retry_button.pressed.connect(_check_editor_server_version)
	overlay_content.add_child(_version_retry_button)
	_refresh_local_drafts()


func _show_version_overlay(message: String, can_retry := false) -> void:
	if _version_overlay == null:
		return
	_version_overlay_message.text = message
	if can_retry:
		_version_overlay_message.text += "\nАдрес сервера: %s" % ApiClient.base_url
	_version_retry_button.visible = can_retry
	_version_overlay.visible = true


func _open_terrain_demo() -> void:
	SCENE_TRANSITION.run(get_tree(), _change_to_terrain_demo)


func _change_to_terrain_demo() -> void:
	var error := get_tree().change_scene_to_file("res://scenes/terrain_autotile_demo.tscn")
	if error != OK:
		_set_status("Не удалось открыть тест Terrain: " + error_string(error))


func _new_spinbox(minimum: int, maximum: int, value: int) -> SpinBox:
	var spin := SpinBox.new()
	spin.min_value = minimum
	spin.max_value = maximum
	spin.value = value
	spin.custom_minimum_size.x = roundi(70 * EDITOR_UI_SCALE)
	return spin


func _labeled_control(caption: String, control: Control) -> Control:
	var box := HBoxContainer.new()
	var label := Label.new()
	label.text = caption
	box.add_child(label)
	box.add_child(control)
	return box


func _add_layer_action(
	parent: Control,
	caption: String,
	callback: Callable,
	tooltip := "",
) -> void:
	var button := Button.new()
	button.text = caption
	button.tooltip_text = tooltip
	button.pressed.connect(callback)
	parent.add_child(button)


func _create_default_layers() -> void:
	_minimap_dirty = true
	_undo_stack.clear()
	_redo_stack.clear()
	_stroke_snapshot.clear()
	_selection = Rect2i()
	_reset_layers()


func _reset_layers() -> void:
	_layers.clear()
	_layers.append(_new_layer("Земля", LAYER_TILE, 0))
	_layers.append(_new_layer("Объекты", LAYER_OBJECT, 0))
	_layers.append(_new_layer("Животные", LAYER_ANIMAL, 0))
	_layers.append(_new_layer("Мобы", LAYER_MOB, 0))
	_active_layer_id = int(_layers[0]["id"])


func _new_layer(layer_name: String, layer_type: String, parent_id: int) -> Dictionary:
	var layer := {
		"id": _next_layer_id,
		"name": layer_name,
		"type": layer_type,
		"parent_id": parent_id,
		"visible": true,
		"locked": false,
		"passable": LAYER_RULES.default_passable(layer_type),
		"cells": {},
		"animal_settings": {},
	}
	_next_layer_id += 1
	return layer


func _add_layer() -> void:
	var name := _layer_name.text.strip_edges()
	if name.is_empty():
		name = "Новый слой"
	var layer_types: Array[String] = [
		LAYER_TILE, LAYER_OBJECT, LAYER_GROUP, LAYER_ANIMAL, LAYER_MOB, LAYER_DECORATIVE,
	]
	var layer_type: String = layer_types[_layer_type.get_selected_id()]
	var parent_id := _active_layer_id if _layer_type.get_selected_id() == 2 and _get_layer(_active_layer_id).get("type") == LAYER_GROUP else 0
	var layer: Dictionary = _new_layer(name, layer_type, parent_id)
	layer["passable"] = _layer_passable_select.selected == 0
	_push_layers_undo()
	_layers.insert(LAYER_RULES.insert_index(_layers, layer_type), layer)
	_active_layer_id = int(layer["id"])
	_layer_name.clear()
	_render_layers()
	_canvas.queue_redraw()
	var number := LAYER_RULES.number_of(_layers, _active_layer_id)
	_set_status(
		"Добавлена группа «%s»." % name if number == 0
		else "Добавлен слой %d «%s»." % [number, name]
	)


func _rename_layer() -> void:
	var layer := _get_layer(_active_layer_id)
	if layer.is_empty():
		_set_status("Сначала выберите слой.")
		return
	var name := _layer_name.text.strip_edges()
	if name.is_empty():
		_set_status("Введите новое название слоя.")
		return
	_layer_name.clear()
	_set_layer_name(_active_layer_id, name)


func _on_layer_renamed(layer_id: int, new_name: String) -> void:
	_set_layer_name(layer_id, new_name)


func _set_layer_name(layer_id: int, new_name: String) -> void:
	var layer := _get_layer(layer_id)
	var name := new_name.strip_edges()
	if layer.is_empty() or name.is_empty() or name == str(layer.get("name", "")):
		return
	_push_layers_undo()
	layer["name"] = name
	_render_layers()
	_set_status("Слой переименован: «%s»." % name)


func _on_layer_visibility_toggled(layer_id: int) -> void:
	var layer := _get_layer(layer_id)
	if layer.is_empty():
		return
	_set_layer_visibility(layer_id, not bool(layer.get("visible", true)))


func _set_layer_visibility(layer_id: int, visible: bool) -> void:
	var layer := _get_layer(layer_id)
	if layer.is_empty() or bool(layer.get("visible", true)) == visible:
		return
	_push_layers_undo()
	layer["visible"] = visible
	if not _is_layer_visible(_get_layer(_active_layer_id)):
		var fallback_layer_id := _first_editable_visible_layer_id()
		if fallback_layer_id > 0:
			_active_layer_id = fallback_layer_id
	_render_layers()
	_canvas.queue_redraw()
	_set_status(
		"Слой «%s» скрыт." % str(layer.get("name", "Слой"))
		if not bool(layer["visible"])
		else "Слой «%s» отображается." % str(layer.get("name", "Слой"))
	)


func _first_editable_visible_layer_id() -> int:
	for candidate in _layers:
		if str(candidate.get("type", "")) == LAYER_GROUP \
			or bool(candidate.get("locked", false)) \
			or not _is_layer_visible(candidate):
			continue
		return int(candidate.get("id", 0))
	return 0


func _toggle_layer_lock() -> void:
	var layer := _get_layer(_active_layer_id)
	if layer.is_empty():
		return
	_push_layers_undo()
	layer["locked"] = not bool(layer.get("locked", false))
	_render_layers()
	_set_status("Слой «%s» %s." % [
		str(layer.get("name", "")),
		"заблокирован" if bool(layer["locked"]) else "разблокирован",
	])


# direction > 0 поднимает активный слой выше (к верху списка), direction < 0 опускает ниже.
func _move_layer(direction: int) -> void:
	var index := _layer_index(_active_layer_id)
	if index < 0:
		return
	var step := 1 if direction > 0 else -1
	var parent_id := int(_layers[index].get("parent_id", 0))
	var neighbor := index + step
	while neighbor >= 0 and neighbor < _layers.size() \
		and int(_layers[neighbor].get("parent_id", 0)) != parent_id:
		neighbor += step
	if neighbor < 0 or neighbor >= _layers.size():
		return
	_move_layer_next_to(_active_layer_id, int(_layers[neighbor]["id"]), step > 0)


func _on_layer_dropped(layer_id: int, target_id: int, above: bool) -> void:
	_move_layer_next_to(layer_id, target_id, above)


# above == true ставит слой выше целевого (в списке и на холсте), false — ниже.
func _move_layer_next_to(layer_id: int, target_id: int, above: bool) -> bool:
	var source := _layer_index(layer_id)
	var target := _layer_index(target_id)
	if layer_id == target_id or source < 0 or target < 0:
		return false
	var moving: Dictionary = _layers[source]
	if int(moving.get("parent_id", 0)) != int(_layers[target].get("parent_id", 0)):
		_set_status("Слой можно переставлять только среди слоёв своей группы.")
		return false
	var before := _layer_ids()
	var redo_before := _redo_stack.duplicate()
	_push_layers_undo()
	_layers.remove_at(source)
	_layers.insert(_layer_index(target_id) + (1 if above else 0), moving)
	var requested := _layer_ids()
	LAYER_RULES.normalize_order(_layers)
	var placed := _layer_ids()
	if placed == before:
		_undo_stack.pop_back()
		_redo_stack.assign(redo_before)
		_refresh_history_buttons()
		if requested != before:
			_set_status("Слои тайлов всегда остаются под слоями объектов, животных и мобов.")
		return false
	_active_layer_id = layer_id
	_render_layers()
	_canvas.queue_redraw()
	var number := LAYER_RULES.number_of(_layers, layer_id)
	var message := "Слой «%s» теперь под номером %d." % [str(moving.get("name", "Слой")), number] \
		if number > 0 else "Группа «%s» перемещена." % str(moving.get("name", "Группа"))
	if placed != requested:
		message += " Слои тайлов всегда остаются под слоями объектов, поэтому слой встал на границу."
	_set_status(message)
	return true


func _layer_ids() -> Array[int]:
	var ids: Array[int] = []
	for layer in _layers:
		ids.append(int(layer.get("id", 0)))
	return ids


func _layers_snapshot() -> Dictionary:
	return {
		"layers": _layers.duplicate(true),
		"active_layer_id": _active_layer_id,
		"spawns": _spawns.duplicate(true),
		"map_w": int(_map_width.value),
		"map_h": int(_map_height.value),
	}


func _push_undo_snapshot(snapshot: Dictionary) -> void:
	HISTORY_RULES.record(_undo_stack, _redo_stack, snapshot, UNDO_HISTORY_LIMIT)
	_minimap_dirty = true
	_refresh_history_buttons()


func _refresh_history_buttons() -> void:
	if _undo_button == null:
		return
	_undo_button.disabled = _undo_stack.is_empty()
	_redo_button.disabled = _redo_stack.is_empty()


func _push_layers_undo() -> void:
	_push_undo_snapshot(_layers_snapshot())


func _duplicate_layer() -> void:
	var layer := _get_layer(_active_layer_id)
	if layer.is_empty() or layer.get("type") == LAYER_GROUP:
		return
	_push_layers_undo()
	var copy := layer.duplicate(true)
	copy["id"] = _next_layer_id
	_next_layer_id += 1
	copy["name"] = str(layer.get("name", "Слой")) + " — копия"
	_layers.insert(_layer_index(_active_layer_id) + 1, copy)
	_active_layer_id = int(copy["id"])
	_render_layers()
	_canvas.queue_redraw()


func _delete_layer() -> void:
	var index := _layer_index(_active_layer_id)
	if index < 0:
		return
	var snapshot := _layers_snapshot()
	var layer_id := _active_layer_id
	var descendants := [layer_id]
	var changed := true
	while changed:
		changed = false
		for layer in _layers:
			if int(layer.get("parent_id", 0)) in descendants and int(layer["id"]) not in descendants:
				descendants.append(int(layer["id"]))
				changed = true
	for remove_id in descendants:
		var remove_index := _layer_index(remove_id)
		if remove_index >= 0:
			_layers.remove_at(remove_index)
	if _layers.is_empty():
		_create_default_layers()
	_push_undo_snapshot(snapshot)
	_active_layer_id = int(_layers[0]["id"])
	_render_layers()
	_canvas.queue_redraw()


func _render_layers() -> void:
	_refresh_history_buttons()
	if _layer_list == null:
		return
	_layer_list.refresh(_layer_entries(), _active_layer_id)
	_update_layer_info()


# Список показывает слои сверху вниз: верхний слой на холсте — первая строка.
func _layer_entries() -> Array[Dictionary]:
	var entries: Array[Dictionary] = []
	_append_layer_entries(entries, LAYER_RULES.numbers(_layers), 0, 0)
	return entries


func _append_layer_entries(
	entries: Array[Dictionary], numbers: Dictionary, parent_id: int, depth: int,
) -> void:
	for index in range(_layers.size() - 1, -1, -1):
		var layer: Dictionary = _layers[index]
		if int(layer.get("parent_id", 0)) != parent_id:
			continue
		var layer_id := int(layer.get("id", 0))
		var number := int(numbers.get(layer_id, 0))
		var type_label := _layer_type_label(str(layer.get("type", "")))
		var heading := "Группа слоёв" if number == 0 else "Слой %d · %s" % [number, type_label]
		entries.append({
			"id": layer_id,
			"name": str(layer.get("name", "Слой")),
			"type": str(layer.get("type", "")),
			"parent_id": parent_id,
			"depth": depth,
			"number": number,
			"visible": bool(layer.get("visible", true)),
			"effective_visible": _is_layer_visible(layer),
			"locked": bool(layer.get("locked", false)),
			"tooltip": heading + "\nКлик — выбрать слой, двойной клик — переименовать.\nПеретащите строку, чтобы изменить порядок.",
		})
		_append_layer_entries(entries, numbers, layer_id, depth + 1)


func _update_layer_info() -> void:
	if _layer_info == null:
		return
	var layer := _get_layer(_active_layer_id)
	if layer.is_empty():
		_layer_info.text = "Слой не выбран."
		return
	var number := LAYER_RULES.number_of(_layers, _active_layer_id)
	var parts: Array[String] = []
	if number > 0:
		parts.append("Слой %d" % number)
		parts.append(_layer_type_label(str(layer.get("type", ""))))
		if LAYER_RULES.affects_passability(str(layer.get("type", ""))):
			parts.append("проходимый" if LAYER_RULES.is_passable(layer) else "непроходимый")
	else:
		parts.append("Группа слоёв")
	if not bool(layer.get("visible", true)):
		parts.append("скрыт")
	if bool(layer.get("locked", false)):
		parts.append("заблокирован")
	_layer_info.text = " · ".join(parts)


func _on_new_layer_type_selected(_index: int) -> void:
	var layer_type := _selected_new_layer_type()
	_layer_passable_select.select(0 if LAYER_RULES.default_passable(layer_type) else 1)
	_layer_passable_select.disabled = not LAYER_RULES.affects_passability(layer_type)


func _selected_new_layer_type() -> String:
	var layer_types: Array[String] = [
		LAYER_TILE, LAYER_OBJECT, LAYER_GROUP, LAYER_ANIMAL, LAYER_MOB, LAYER_DECORATIVE,
	]
	return layer_types[_layer_type.get_selected_id()]


func _toggle_layer_passable() -> void:
	var layer := _get_layer(_active_layer_id)
	if layer.is_empty():
		_set_status("Сначала выберите слой.")
		return
	if not LAYER_RULES.affects_passability(str(layer.get("type", ""))):
		_set_status("У групп слоёв нет клеток, проходимость не задаётся.")
		return
	_push_layers_undo()
	layer["passable"] = not LAYER_RULES.is_passable(layer)
	_update_layer_info()
	_canvas.queue_redraw()
	_set_status("Слой «%s»: %s." % [
		str(layer.get("name", "")),
		"проходимый" if bool(layer["passable"]) else "непроходимый",
	])


func _on_passability_toggled(pressed: bool) -> void:
	_show_passability = pressed
	_canvas.queue_redraw()
	_set_status("Подсветка непроходимых клеток включена." if pressed else "Подсветка проходимости выключена.")


func _draw_passability_overlay(canvas: Control, tile_size: float) -> void:
	var layers_for_rules: Array = []
	for layer in _layers:
		if str(layer.get("type", "")) != LAYER_GROUP and _is_layer_visible(layer):
			layers_for_rules.append(layer)
	for coord in LAYER_RULES.blocked_cells(layers_for_rules):
		var parts := str(coord).split(":")
		if parts.size() != 2:
			continue
		var rect := Rect2(_pan + Vector2(int(parts[0]), int(parts[1])) * tile_size, Vector2.ONE * tile_size)
		canvas.draw_rect(rect, Color(0.95, 0.15, 0.15, 0.4))


func _align_controls_left(node: Node) -> void:
	if node is Button:
		(node as Button).alignment = HORIZONTAL_ALIGNMENT_LEFT
	elif node is Label:
		(node as Label).horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	for child in node.get_children():
		_align_controls_left(child)


func _on_node_added_align_left(node: Node) -> void:
	if _ui_root != null and is_instance_valid(_ui_root) and _ui_root.is_ancestor_of(node):
		_align_controls_left(node)


# Блок редактора: заголовок с кнопками закрепить и свернуть, уголок для размера.
func _add_floating_panel(key: String, title: String, content: Control) -> void:
	var panel: Control = FLOATING_PANEL_SCRIPT.new()
	panel.panel_key = key
	panel.set_title(title)
	_workspace.add_child(panel)
	panel.set_content(content)
	panel.layout_changed.connect(_save_panel_layout)
	_floating_panels.append(panel)


# Стартовая раскладка блоков: доли рабочей области (x, ширина). Дальше блоки двигаются мышью.
const PANEL_LAYOUT_FILE := "user://editor_panel_layout.json"
const PANEL_LAYOUT_FRACTIONS := [
	[0.0, 0.11],
	[0.115, 0.13],
	[0.25, 0.30],
	[0.555, 0.32],
	[0.88, 0.12],
]


func _layout_initial_panels() -> void:
	# Раньше всех блоков (сигнал resized может прийти во время сборки) или без размера области раскладку не делаем.
	if _panels_placed or _workspace == null or _floating_panels.size() < PANEL_LAYOUT_FRACTIONS.size():
		return
	if _workspace.size.x <= 0.0 or _workspace.size.y <= 0.0:
		return
	_panels_placed = true
	var area := _workspace.size
	var saved := _read_saved_panel_states()
	for index in range(mini(_floating_panels.size(), PANEL_LAYOUT_FRACTIONS.size())):
		var fraction: Array = PANEL_LAYOUT_FRACTIONS[index]
		var panel: Control = _floating_panels[index]
		if saved.has(panel.panel_key):
			panel.apply_state(saved[panel.panel_key])
		else:
			panel.position = Vector2(float(fraction[0]) * area.x, 0.0)
			panel.size = Vector2(float(fraction[1]) * area.x, area.y)
	# Порядок наложения: от нижнего блока к верхнему, как сохранено.
	var ordered := _floating_panels.duplicate()
	ordered.sort_custom(func(a: Control, b: Control) -> bool:
		return _saved_z(saved, a) < _saved_z(saved, b))
	for panel in ordered:
		panel.move_to_front()


func _saved_z(saved: Dictionary, panel: Control) -> int:
	return int(saved.get(panel.panel_key, {}).get("z", 0)) if saved.has(panel.panel_key) else 0


# Сохранённая раскладка блоков из локального файла: ключ панели -> состояние. Ошибки файла игнорируются.
func _read_saved_panel_states() -> Dictionary:
	if not FileAccess.file_exists(PANEL_LAYOUT_FILE):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(PANEL_LAYOUT_FILE))
	if not parsed is Dictionary or not parsed.get("panels", null) is Array:
		return {}
	var by_key := {}
	for state in parsed["panels"]:
		if state is Dictionary and state.has("key"):
			by_key[str(state["key"])] = state
	return by_key


# Пишет раскладку всех блоков (положение, размер, закрепление, свёрнутость, порядок наложения).
func _save_panel_layout() -> void:
	if not _panels_placed:
		return
	var states: Array = []
	for panel in _floating_panels:
		var state: Dictionary = panel.get_state()
		state["z"] = panel.get_index()
		states.append(state)
	var file := FileAccess.open(PANEL_LAYOUT_FILE, FileAccess.WRITE)
	if file == null:
		return
	file.store_string(JSON.stringify({"version": 1, "panels": states}, "	"))


func _layer_type_label(layer_type: String) -> String:
	match layer_type:
		LAYER_TILE:
			return "тайлы"
		LAYER_DECORATIVE:
			return "декор · не меняет поверхность"
		LAYER_OBJECT:
			return "объекты"
		LAYER_ANIMAL:
			return "животные"
		LAYER_MOB:
			return "мобы"
		LAYER_GROUP:
			return "группа"
	return layer_type


func _is_tile_layer(layer: Dictionary) -> bool:
	return str(layer.get("type", "")) in [LAYER_TILE, LAYER_DECORATIVE]


func _is_layer_visible(layer: Dictionary) -> bool:
	var current := layer
	while not current.is_empty():
		if not bool(current.get("visible", true)):
			return false
		var parent_id := int(current.get("parent_id", 0))
		if parent_id == 0:
			break
		current = _get_layer(parent_id)
	return true


func _on_layer_list_selected(layer_id: int) -> void:
	if _layer_index(layer_id) < 0:
		return
	_active_layer_id = layer_id
	_layer_list.set_active(layer_id)
	_update_layer_info()


func _layer_index(layer_id: int) -> int:
	for index in range(_layers.size()):
		if int(_layers[index].get("id", 0)) == layer_id:
			return index
	return -1


func _get_layer(layer_id: int) -> Dictionary:
	var index := _layer_index(layer_id)
	return _layers[index] if index >= 0 else {}


# Превью отрядов: сервер считает отправления по тем же правилам, что и бой.
func _on_spawn_squad_inputs_changed(_value: float) -> void:
	_request_spawn_preview()


func _request_spawn_preview() -> void:
	if not is_instance_valid(_spawn_squad_preview_label) or not _pending_action.is_empty():
		return
	var squad_min := int(_spawn_squad_min_spin.value)
	var squad_max := maxi(squad_min, int(_spawn_squad_max_spin.value))
	_spawn_squad_preview_label.text = "Считаем отправления…"
	_pending_action = "spawn_preview"
	var sent := ApiClient.request_json(
		HTTPClient.METHOD_POST,
		"%s/map/spawn-preview" % _api_prefix,
		{"count": int(_spawn_count_spin.value), "squad_min": squad_min, "squad_max": squad_max},
	)
	if not sent:
		_pending_action = ""


func _show_spawn_preview(success: bool, payload: Variant) -> void:
	if not is_instance_valid(_spawn_squad_preview_label):
		return
	if not success or not payload is Dictionary:
		_spawn_squad_preview_label.text = "Превью недоступно: %s" % str(payload)
		return
	var sizes: Array = payload.get("sizes", [])
	var parts: Array[String] = []
	if sizes.size() <= 60:
		for size in sizes:
			parts.append(str(int(size)))
	else:
		for index in range(30):
			parts.append(str(int(sizes[index])))
		parts.append("…")
		for index in range(sizes.size() - 10, sizes.size()):
			parts.append(str(int(sizes[index])))
	_spawn_squad_preview_label.text = "Отправлений: %d. Размеры: %s" % [
		int(payload.get("ticks", sizes.size())),
		", ".join(PackedStringArray(parts)),
	]


func _on_api_completed(success: bool, payload: Variant) -> void:
	var action := _pending_action
	_pending_action = ""
	if action == "spawn_preview":
		_show_spawn_preview(success, payload)
		return
	if not success:
		if action == "item_catalog":
			_set_status("Не удалось загрузить каталог экипировки: %s" % str(payload))
			_load_saved_maps()
			return
		if action in ["create_item", "edit_item"]:
			if is_instance_valid(_item_form_dialog):
				_item_form_dialog.set_message(str(payload))
			_pending_item_form.clear()
			_set_status("Не удалось сохранить предмет: %s" % str(payload))
			return
		if action == "mob_equipment_items":
			_show_pending_mob_profile(null)
			return
		if action == "mob_profile_save" and is_instance_valid(_mob_profile_dialog):
			_mob_profile_dialog.set_busy(false)
			_mob_profile_dialog.set_message(str(payload))
			_set_status("Не удалось сохранить настройки моба: %s" % str(payload))
			return
		if action == "save_map" and _test_world_after_save:
			_test_world_after_save = false
			_set_status(TEST_WORLD_RULES.error_message("карта не сохранена на сервере: %s" % str(payload)))
			return
		if action == "world_terrain":
			_set_status("Не загружено: %s" % str(payload))
			return
		_saved_maps_status = ""
		_set_status(
			"Не удалось сохранить карту: %s" % str(payload)
			if action == "save_map" else str(payload)
		)
		if action == "editor_version":
			_finish_loading_overlay()
			_show_version_overlay(
				"Не удалось проверить версию сервера.\n" + str(payload),
				true,
			)
			return
		if action == "publish_tile_group":
			_pending_upload_source.clear()
		if action == "mob_profile_load":
			_clear_pending_mob_profile()
		if action in ["catalog", "saved_maps", "load_map"]:
			_finish_loading_overlay()
		return
	if action == "mob_equipment_items":
		var listed: Variant = payload.get("items") if payload is Dictionary else null
		_show_pending_mob_profile(listed if listed is Array else null)
		return
	if not payload is Dictionary:
		if action == "item_catalog":
			_set_status("Сервер вернул неверный формат каталога предметов.")
			_load_saved_maps()
			return
		if action in ["create_item", "edit_item"]:
			if is_instance_valid(_item_form_dialog):
				_item_form_dialog.set_message("Сервер вернул неверный формат предмета.")
			_pending_item_form.clear()
			_set_status("Сервер вернул неверный формат предмета.")
			return
		if action in ["editor_version", "catalog", "item_catalog", "saved_maps", "load_map"]:
			_finish_loading_overlay()
		_set_status("Сервер вернул неожиданный ответ.")
		return
	match action:
		"editor_version":
			var compatibility: Variant = payload.get("compatibility", {})
			if not compatibility is Dictionary or compatibility.get("compatible") != true:
				var reason := str(
					compatibility.get("reason", "Версии редактора и сервера несовместимы.")
				) if compatibility is Dictionary else "Сервер вернул неверный формат совместимости."
				_set_status(reason)
				_finish_loading_overlay()
				_show_version_overlay(reason, true)
				return
			_editor_version_label.text = "Редактор %s · Сервер %s" % [
				ApiClient.EDITOR_VERSION,
				str(payload.get("server_version", "?")),
			]
			_version_overlay.visible = false
			_set_loading_progress(83, "Загрузка каталога тайлов")
			_pending_action = "catalog"
			ApiClient.request_json(HTTPClient.METHOD_GET, _api_prefix + "/map/catalog")
		"mob_profile_load":
			var settings: Variant = payload.get("settings", {})
			if not settings is Dictionary:
				_set_status("Сервер вернул неверный формат настроек моба.")
				_clear_pending_mob_profile()
				return
			_pending_mob_profile_settings = settings
			_request_mob_equipment()
		"mob_profile_save":
			var dropped := 0
			if is_instance_valid(_mob_profile_dialog):
				dropped = int(_mob_profile_dialog.dropped_equipment_count)
			_close_mob_profile_dialog()
			_clear_pending_mob_profile()
			var saved_text := "Настройки моба сохранены для режима %s." % str(
				WorldModeRegistry.describe(_mode).get("name", _mode),
			)
			if dropped > 0:
				saved_text += " Снято предметов, не подходящих по требованиям: %d." % dropped
			_set_status(saved_text)
		"catalog":
			_catalog.clear()
			_catalog_by_key.clear()
			for value in payload.get("items", []):
				if value is Dictionary:
					var item: Dictionary = value
					var key := str(item.get("item_key", ""))
					if not key.is_empty():
						_catalog.append(item)
						_catalog_by_key[key] = item
			_set_custom_tile_groups(payload.get("tile_groups", []))
			_render_palette()
			if _mode != "deck":
				_set_loading_progress(90, "Загрузка инвентаря")
				_request_item_catalog()
			else:
				_load_saved_maps()
		"item_catalog":
			_inventory_items.clear()
			_spawn_item_catalog.clear()
			var items: Variant = payload.get("items", [])
			if not items is Array:
				_set_status("Сервер вернул неверный формат каталога предметов.")
				_load_saved_maps()
				return
			for value in items:
				if value is Dictionary and int(value.get("id", 0)) > 0:
					_inventory_items.append(value)
					_spawn_item_catalog.append(value)
			_refresh_inventory_button()
			if is_instance_valid(_inventory_dialog) and _inventory_dialog.visible:
				_render_inventory_items()
			_load_saved_maps()
		"create_item", "edit_item":
			var item: Variant = payload.get("item")
			if not item is Dictionary or int(item.get("id", 0)) <= 0:
				if is_instance_valid(_item_form_dialog):
					_item_form_dialog.set_message("Сервер вернул неверный формат предмета.")
				_pending_item_form.clear()
				_set_status("Сервер вернул некорректный предмет.")
				return
			if action == "create_item":
				_inventory_items.append(item)
				_spawn_item_catalog.append(item)
				_new_items.append(item)
			else:
				_replace_catalog_item(_inventory_items, item)
				_replace_catalog_item(_spawn_item_catalog, item)
				for index in range(_new_items.size()):
					if int(_new_items[index].get("id", 0)) == int(item.get("id", 0)):
						_new_items[index] = item
			_pending_item_form.clear()
			_close_item_form_dialog()
			_inventory_level = "slots"
			_inventory_selected_slot = ""
			_inventory_selected_category = ""
			_render_inventory_items()
			_refresh_inventory_button()
			if action == "create_item":
				_set_status(ITEM_SAVED_STATUS % [
					str(item.get("name", "Предмет")),
					str(WorldModeRegistry.describe(_mode).get("name", _mode)),
				])
			else:
				_set_status("Предмет «%s» обновлён." % str(item.get("name", "Предмет")))
		"saved_maps":
			_saved_maps.clear()
			for value in payload.get("saved_maps", []):
				if value is Dictionary:
					_saved_maps.append(value)
			_render_saved_maps()
			if _initial_saved_map_id > 0:
				var saved_index := -1
				for index in range(_saved_select.item_count):
					if int(_saved_select.get_item_metadata(index)) == _initial_saved_map_id:
						saved_index = index
						break
				_initial_saved_map_id = 0
				if saved_index < 0:
					_finish_loading_overlay()
					_set_status("Выбранная сохранённая карта не найдена.")
					return
				_saved_select.select(saved_index)
				if is_instance_valid(_loading_overlay):
					_set_loading_progress(98, "Загрузка карты")
				_load_selected_map()
			else:
				_set_status(
					_saved_maps_status if not _saved_maps_status.is_empty()
					else "Каталог готов. Выберите элемент и рисуйте на холсте."
				)
				_saved_maps_status = ""
				_set_loading_progress(100, "Редактор готов")
				_finish_loading_overlay()
		"load_map":
			_load_map_payload(payload.get("map", {}))
			_set_loading_progress(100, "Редактор готов")
			_finish_loading_overlay()
		"world_terrain":
			_apply_world_terrain(payload.get("terrain"))
		"load_map":
			_load_map_payload(payload.get("map", {}))
		"save_map":
			_saved_id = int(payload.get("saved_id", _saved_id))
			if not _local_draft_id.is_empty():
				DRAFTS_RULES.mark_server_map(_local_drafts_folder, _local_draft_id, _saved_id, _map_name.text.strip_edges())
			if _test_world_after_save:
				_test_world_after_save = false
				_request_test_world()
				return
			var saved_message := "Карта сохранена. ID: %d." % _saved_id
			if _has_unpublished_local_assets():
				saved_message = "Черновик сохранён (ID %d). Локальные тайлы, животные и мобы пока доступны только в редакторе и не публикуются в игровой мир." % _saved_id
			if _last_save_merged_cells > 0:
				saved_message += " Клеток, где слои тайлов перекрывают друг друга: %d — в мир попадёт верхний слой, в черновике сохранены все слои." % _last_save_merged_cells
			_set_status(saved_message)
			if _publish_world_id > 0:
				_publish_saved_map()
				return
			_saved_maps_status = saved_message
			_load_saved_maps()
		"worlds":
			_worlds.clear()
			for value in payload.get("worlds", []):
				if value is Dictionary and str(value.get("mode", _mode)) == _mode:
					_worlds.append(value)
			_show_publish_dialog()
		"publish":
			_set_status("Карта опубликована. ID публикации: %s" % str(payload.get("published_id", payload.get("map_id", "готово"))))
			if not _local_draft_id.is_empty() and _publish_request_world_id > 0:
				DRAFTS_RULES.mark_published(_local_drafts_folder, _local_draft_id, _publish_request_world_id, _publish_request_world_name)
		"publish_tile_group":
			var uploaded_group: Variant = payload.get("group", {})
			if not uploaded_group is Dictionary or uploaded_group.is_empty():
				_pending_upload_source.clear()
				_set_status("Сервер загрузил группу, но не вернул её разметку.")
				return
			for value in payload.get("items", []):
				if value is Dictionary:
					var item: Dictionary = value
					var key := str(item.get("item_key", ""))
					if not key.is_empty():
						_catalog.append(item)
						_catalog_by_key[key] = item
			_register_custom_tile_group(uploaded_group)
			var uploaded_group_id := str(uploaded_group.get("group_id", ""))
			var uploaded_rows := int(uploaded_group.get("tile_rows", 0))
			var registered_group: Dictionary = _custom_tile_groups.get(uploaded_group_id, {})
			if registered_group.is_empty():
				_pending_upload_source.clear()
				_set_status("Сервер вернул неполную разметку группы тайлов.")
				return
			var uploaded_tile_keys: Array = registered_group["tile_keys"]
			_active_custom_group_id = uploaded_group_id
			_active_stamp_rows = uploaded_rows
			_selected_item_key = str(uploaded_tile_keys[1][1])
			var converted_cells := _replace_uploaded_local_group_cells(
				uploaded_group_id,
				str(_pending_upload_source.get("sheet_path", "")),
				_pending_upload_source.get("center", Vector2i.ZERO),
				int(_pending_upload_source.get("rows", 0)),
				uploaded_group,
			)
			_pending_upload_source.clear()
			_render_palette()
			_publish_group_button.disabled = true
			_canvas.queue_redraw()
			_set_status("Группа опубликована и добавлена в серверную палитру. Переведено клеток карты в группу сервера: %d." % converted_cells)


func _render_palette() -> void:
	_palette.clear()
	for item in _catalog:
		var is_custom_tile := item.has("tile_group_id")
		if is_custom_tile and (int(item.get("tile_x", -1)) != 1 or int(item.get("tile_y", -1)) != 1):
			continue
		var label := "%s  ·  %s" % [
			str(item.get("tile_group_name", item.get("item_key", ""))),
			"3×%d · %s" % [int(item.get("tile_rows", 3)), str(item.get("category", ""))]
				if is_custom_tile else str(item.get("category", "")),
		]
		_palette.add_item(label)
		_palette.set_item_metadata(_palette.item_count - 1, str(item.get("item_key", "")))


func _set_custom_tile_groups(groups: Variant) -> void:
	_custom_tile_groups.clear()
	_custom_group_by_key.clear()
	if not groups is Array:
		return
	for value in groups:
		_register_custom_tile_group(value)


func _register_custom_tile_group(value: Variant) -> void:
	if not value is Dictionary:
		return
	var group: Dictionary = value
	var group_id := str(group.get("group_id", ""))
	var rows := int(group.get("tile_rows", 0))
	var tile_keys: Variant = group.get("tile_keys", [])
	if group_id.is_empty() or rows not in [3, 4, 5] or not tile_keys is Array or tile_keys.size() != rows:
		return
	var normalized_keys: Array = []
	for row in range(rows):
		var row_value: Variant = tile_keys[row]
		if not row_value is Array or row_value.size() != 3:
			return
		var normalized_row: Array[String] = []
		for key in row_value:
			if str(key).is_empty():
				return
			normalized_row.append(str(key))
		normalized_keys.append(normalized_row)
	group["tile_keys"] = normalized_keys
	_custom_tile_groups[group_id] = group
	for row in range(rows):
		for column in range(3):
			_custom_group_by_key[normalized_keys[row][column]] = {
				"group_id": group_id,
				"tile_x": column,
				"tile_y": row,
			}

func _on_palette_item_selected(index: int) -> void:
	_activate_brush_for_palette_selection()
	_selected_item_key = str(_palette.get_item_metadata(index))
	_selected_atlas_path = ""
	var group_info: Dictionary = _custom_group_by_key.get(_selected_item_key, {})
	_active_custom_group_id = str(group_info.get("group_id", ""))
	_active_stamp_rows = int(_custom_tile_groups.get(_active_custom_group_id, {}).get("tile_rows", 1))
	if not _active_custom_group_id.is_empty():
		_set_status("Выбрана серверная группа 3×%d. ЛКМ рисует с автоподбором краёв; ПКМ стирает." % _active_stamp_rows)
	else:
		_set_status("Выбран элемент: " + _selected_item_key)


func _atlas_loading_work_total() -> int:
	var total := 0
	var root_directory := DirAccess.open(BIOME_ROOT)
	if root_directory != null:
		for biome_folder in root_directory.get_directories():
			total += 1
			var directory := DirAccess.open(
				BIOME_ROOT.path_join(biome_folder).path_join("Tiled_files"),
			)
			if directory == null:
				continue
			for file_name in directory.get_files():
				if file_name.get_extension().to_lower() == "png":
					total += 1
	var bridges_directory := DirAccess.open(BRIDGES_ROOT)
	if bridges_directory != null:
		for pack_folder in bridges_directory.get_directories():
			if pack_folder.begins_with(".") or pack_folder == "__MACOSX":
				continue
			var sheet_path := BRIDGES_ROOT.path_join(pack_folder) \
				.path_join("PNG_n_Tiled").path_join("Bridges.png")
			if FileAccess.file_exists(sheet_path):
				total += 2
	var animals_directory := DirAccess.open(ANIMALS_ROOT)
	if animals_directory != null:
		for pack_folder in animals_directory.get_directories():
			total += 1
			var sheet_directory_path := ANIMALS_ROOT.path_join(pack_folder).path_join("Tiled")
			if not DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(sheet_directory_path)):
				sheet_directory_path = ANIMALS_ROOT.path_join(pack_folder).path_join("PNG_n_Tiled")
			var directory := DirAccess.open(sheet_directory_path)
			if directory == null:
				continue
			for file_name in directory.get_files():
				if file_name.get_extension().to_lower() == "png" and not file_name.begins_with("._"):
					total += 1
	var lpc_directory := DirAccess.open(LPC_ROOT)
	if lpc_directory != null:
		for pack_folder in lpc_directory.get_directories():
			if pack_folder.begins_with(".") or pack_folder == "__MACOSX" or pack_folder == "wolfs":
				continue
			total += 1
			var png_paths: Array[String] = []
			_collect_lpc_png_files(LPC_ROOT.path_join(pack_folder), png_paths)
			total += png_paths.size()
	var craftpix_directory := DirAccess.open(CRAFTPIX_PACK_ROOT)
	if craftpix_directory != null:
		for pack_folder in craftpix_directory.get_directories():
			var png_paths := _craftpix_pack_png_files(CRAFTPIX_PACK_ROOT.path_join(pack_folder))
			if not png_paths.is_empty():
				total += 1 + png_paths.size()
	total += _swordsman_level_directories().size()
	total += _mage_level_directories().size()
	total += _archer_level_directories().size()
	return maxi(total, 1)


func _discover_atlas_sheets() -> void:
	var root_directory := DirAccess.open(BIOME_ROOT)
	if root_directory == null:
		push_error("Не удалось открыть папку биомов: " + BIOME_ROOT)
		_set_status("Не найдена папка биомов: " + BIOME_ROOT)
		return
	var loading_total := _atlas_loading_work_total()
	var loading_done := 0
	_set_loading_progress(5, "Загрузка биомов")
	if is_inside_tree():
		await get_tree().process_frame
	_set_loading_stage(
		"Загрузка биомов", LOADING_TREE_SHEET, Vector2i(160, 160), 6, 0, false,
	)
	_add_palette_section_title("Биомы")
	var biome_names := root_directory.get_directories()
	biome_names.sort()
	for biome_folder in biome_names:
		var sheet_directory_path := BIOME_ROOT.path_join(biome_folder).path_join("Tiled_files")
		var directory := DirAccess.open(sheet_directory_path)
		if directory == null:
			continue
		var files := directory.get_files()
		files.sort()
		var biome_path := BIOME_ROOT.path_join(biome_folder)
		var biome_name := _biome_display_name(biome_folder)
		var biome_button := Button.new()
		biome_button.text = biome_name
		biome_button.tooltip_text = biome_folder
		biome_button.toggle_mode = true
		biome_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		biome_button.pressed.connect(_select_biome.bind(biome_path, biome_button))
		_biome_list.add_child(biome_button)
		_biome_buttons[biome_path] = biome_button
		loading_done = await _advance_loading_progress(
			loading_done, loading_total, "Загрузка биомов",
		)
		for file_name in files:
			if file_name.get_extension().to_lower() != "png":
				continue
			var sheet_path := sheet_directory_path.path_join(file_name)
			_add_atlas_sheet(sheet_path, biome_path, biome_name, ATLAS_TILE_SIZE, _atlas_category(file_name.get_basename()))
			loading_done = await _advance_loading_progress(
				loading_done, loading_total, "Загрузка биомов",
			)
	_add_palette_section_title("Мосты")
	var bridges_directory := DirAccess.open(BRIDGES_ROOT)
	if bridges_directory == null:
		push_warning("Не удалось открыть папку мостов: " + BRIDGES_ROOT)
	else:
		var bridge_packs := bridges_directory.get_directories()
		bridge_packs.sort()
		for pack_folder in bridge_packs:
			if pack_folder.begins_with(".") or pack_folder == "__MACOSX":
				continue
			var pack_path := BRIDGES_ROOT.path_join(pack_folder)
			var sheet_directory_path := pack_path.path_join("PNG_n_Tiled")
			var sheet_path := sheet_directory_path.path_join("Bridges.png")
			if not FileAccess.file_exists(sheet_path):
				continue
			var pack_name := "Мосты"
			var bridge_button := Button.new()
			bridge_button.text = pack_name
			bridge_button.tooltip_text = pack_folder
			bridge_button.toggle_mode = true
			bridge_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			bridge_button.pressed.connect(_select_biome.bind(pack_path, bridge_button))
			_biome_list.add_child(bridge_button)
			_biome_buttons[pack_path] = bridge_button
			loading_done = await _advance_loading_progress(
				loading_done, loading_total, "Загрузка биомов",
			)
			_add_atlas_sheet(sheet_path, pack_path, pack_name, ATLAS_TILE_SIZE, "Мосты")
			loading_done = await _advance_loading_progress(
				loading_done, loading_total, "Загрузка биомов",
			)
	_set_loading_stage(
		"Загрузка мобов", LOADING_GOLEM_SHEET, Vector2i(128, 128), 8,
		LOADING_GOLEM_DIRECTION_ROW, true,
	)
	_add_palette_section_title("Животные")
	var animals_directory := DirAccess.open(ANIMALS_ROOT)
	if animals_directory == null:
		push_warning("Не удалось открыть папку животных: " + ANIMALS_ROOT)
	else:
		var animal_packs := animals_directory.get_directories()
		animal_packs.sort()
		for pack_folder in animal_packs:
			var sheet_directory_path := ANIMALS_ROOT.path_join(pack_folder).path_join("Tiled")
			if not DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(sheet_directory_path)):
				sheet_directory_path = ANIMALS_ROOT.path_join(pack_folder).path_join("PNG_n_Tiled")
			var directory := DirAccess.open(sheet_directory_path)
			if directory == null:
				continue
			var files := directory.get_files()
			files.sort()
			var pack_path := ANIMALS_ROOT.path_join(pack_folder)
			var pack_name := _animal_pack_display_name(pack_folder)
			var animal_button := Button.new()
			animal_button.text = pack_name
			animal_button.tooltip_text = pack_folder
			animal_button.toggle_mode = true
			animal_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			animal_button.pressed.connect(_select_biome.bind(pack_path, animal_button))
			_biome_list.add_child(animal_button)
			_biome_buttons[pack_path] = animal_button
			for file_name in files:
				if file_name.get_extension().to_lower() != "png" or file_name.begins_with("._"):
					continue
				var sheet_path := sheet_directory_path.path_join(file_name)
				_add_atlas_sheet(
					sheet_path, pack_path, pack_name, ATLAS_TILE_SIZE, "Спрайты животных", false,
				)
				loading_done = await _advance_loading_progress(
					loading_done, loading_total, "Загрузка мобов",
				)
			await _build_animal_groups(pack_path, pack_folder)
			loading_done = await _advance_loading_progress(
				loading_done, loading_total, "Загрузка мобов",
			)
	_set_loading_stage(
		"Загрузка мобов", LOADING_GOLEM_SHEET, Vector2i(128, 128), 8,
		LOADING_GOLEM_DIRECTION_ROW, true,
	)
	_add_palette_section_title("LPC")
	var lpc_directory := DirAccess.open(LPC_ROOT)
	if lpc_directory == null:
		push_warning("Не удалось открыть папку LPC: " + LPC_ROOT)
	else:
		var lpc_packs := lpc_directory.get_directories()
		lpc_packs.sort()
		for pack_folder in lpc_packs:
			# Волки убраны из палитры: их листы нарезаются неверно.
			if pack_folder.begins_with(".") or pack_folder == "__MACOSX" or pack_folder == "wolfs":
				continue
			var pack_path := LPC_ROOT.path_join(pack_folder)
			var pack_name := _lpc_pack_display_name(pack_folder)
			var mob_button := Button.new()
			mob_button.text = pack_name
			mob_button.tooltip_text = pack_folder
			mob_button.toggle_mode = true
			mob_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			mob_button.pressed.connect(_select_biome.bind(pack_path, mob_button))
			_biome_list.add_child(mob_button)
			_biome_buttons[pack_path] = mob_button
			var png_paths: Array[String] = []
			_collect_lpc_png_files(pack_path, png_paths)
			png_paths.sort()
			for sheet_path in png_paths:
				if sheet_path.get_file().to_lower().ends_with("_with_shadow.png"):
					var sheet_animations := _read_sheet_animations(sheet_path)
					_add_atlas_sheet(
						sheet_path, pack_path, pack_name, ATLAS_TILE_SIZE, "Спрайты LPC",
						false, false, sheet_animations, false,
					)
				loading_done = await _advance_loading_progress(
					loading_done, loading_total, "Загрузка мобов",
				)
			if pack_folder == "goblin sprite-pack":
				_build_lpc_goblin_groups(pack_path, pack_folder, png_paths)
			else:
				await _build_animal_groups(pack_path, pack_folder, "mob")
			if pack_folder in ["LPC imp", "LPC Imp 2"]:
				_build_lpc_imp_groups(pack_path, pack_folder, pack_name, png_paths)
			loading_done = await _advance_loading_progress(
				loading_done, loading_total, "Загрузка мобов",
			)
	_set_loading_stage(
		"Загрузка пакетов", LOADING_SMITH_SHEET, Vector2i(48, 48), 6, 0, false,
	)
	_add_palette_section_title("Пакеты Craftpix")
	var craftpix_directory := DirAccess.open(CRAFTPIX_PACK_ROOT)
	if craftpix_directory == null:
		push_warning("Не удалось открыть папку пакетов Craftpix: " + CRAFTPIX_PACK_ROOT)
	else:
		var craftpix_packs := craftpix_directory.get_directories()
		craftpix_packs.sort()
		for pack_folder in craftpix_packs:
			var pack_path := CRAFTPIX_PACK_ROOT.path_join(pack_folder)
			var sheet_paths := _craftpix_pack_png_files(pack_path)
			if sheet_paths.is_empty():
				continue
			var pack_name := _craftpix_pack_display_name(pack_folder)
			var pack_button := Button.new()
			pack_button.text = pack_name
			pack_button.tooltip_text = pack_folder
			pack_button.toggle_mode = true
			pack_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			pack_button.pressed.connect(_select_biome.bind(pack_path, pack_button))
			_biome_list.add_child(pack_button)
			_biome_buttons[pack_path] = pack_button
			loading_done = await _advance_loading_progress(
				loading_done, loading_total, "Загрузка пакетов",
			)
			for sheet_path in sheet_paths:
				_add_atlas_sheet(
					sheet_path, pack_path, pack_name, ATLAS_TILE_SIZE, pack_name,
					true, "/tiled_files/" in sheet_path.to_lower(), {}, false,
				)
				loading_done = await _advance_loading_progress(
					loading_done, loading_total, "Загрузка пакетов", false,
				)
			if _build_craftpix_animation_groups(pack_path, pack_folder, pack_name, sheet_paths) > 0:
				var animation_path := pack_path + "|animated"
				var animation_button := Button.new()
				animation_button.text = pack_name + " · анимации"
				animation_button.tooltip_text = "Цельные подвижные спрайты из набора «%s»" % pack_name
				animation_button.toggle_mode = true
				animation_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
				animation_button.pressed.connect(
					_select_animated_pack.bind(pack_path, animation_path, animation_button),
				)
				_biome_list.add_child(animation_button)
				_biome_buttons[animation_path] = animation_button
	_set_loading_stage(
		"Загрузка героев", LOADING_MAGE_SHEET, Vector2i(64, 64), 6, 0, true,
	)
	_add_palette_section_title("Герои")
	var swordsman_button := Button.new()
	swordsman_button.text = "Воин"
	swordsman_button.tooltip_text = "Девять уровней героя-воина"
	swordsman_button.toggle_mode = true
	swordsman_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	swordsman_button.pressed.connect(
		_select_biome.bind(SWORDSMAN_ROOT, swordsman_button),
	)
	_biome_list.add_child(swordsman_button)
	_biome_buttons[SWORDSMAN_ROOT] = swordsman_button
	var loaded_hero_levels := await _build_swordsman_hero_groups()
	for hero_level in loaded_hero_levels:
		loading_done = await _advance_loading_progress(
			loading_done, loading_total, "Загрузка героев",
		)
	var mage_button := Button.new()
	mage_button.text = "Маг"
	mage_button.tooltip_text = "Девять уровней героя-мага"
	mage_button.toggle_mode = true
	mage_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	mage_button.pressed.connect(_select_biome.bind(MAGE_ROOT, mage_button))
	_biome_list.add_child(mage_button)
	_biome_buttons[MAGE_ROOT] = mage_button
	var loaded_mage_levels := await _build_mage_hero_groups()
	for hero_level in loaded_mage_levels:
		loading_done = await _advance_loading_progress(
			loading_done, loading_total, "Загрузка героев",
		)
	var archer_button := Button.new()
	archer_button.text = "Лучник"
	archer_button.tooltip_text = "Девять уровней героя-лучника"
	archer_button.toggle_mode = true
	archer_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	archer_button.pressed.connect(_select_biome.bind(ARCHER_ROOT, archer_button))
	_biome_list.add_child(archer_button)
	_biome_buttons[ARCHER_ROOT] = archer_button
	var loaded_archer_levels := await _build_archer_hero_groups()
	for hero_level in loaded_archer_levels:
		loading_done = await _advance_loading_progress(
			loading_done, loading_total, "Загрузка героев",
		)
	_add_palette_section_title("Главные здания")
	for castle in [["castle_8", "Замок"], ["castle_5", "Замок 1"]]:
		var castle_button := Button.new()
		castle_button.text = str(castle[1])
		castle_button.tooltip_text = "Главное здание 5×5 клеток: оборона, здоровье и регенерация задаются в его настройках"
		castle_button.toggle_mode = true
		castle_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		castle_button.icon = _building_frame(str(castle[0]), 0)
		castle_button.pressed.connect(_pick_building_sprite.bind(str(castle[0])))
		_biome_list.add_child(castle_button)
		_building_palette_icons.append({"button": castle_button, "sprite": str(castle[0])})
	_ensure_building_anim_timer()
	_catalog_tab = Button.new()
	_catalog_tab.text = "Каталог сервера"
	_catalog_tab.tooltip_text = "Серверные элементы, совместимые с публикацией"
	_catalog_tab.toggle_mode = true
	_catalog_tab.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_catalog_tab.pressed.connect(_show_server_catalog.bind(true))
	_sheet_tabs.add_child(_catalog_tab)
	var preferred_biome_path := ""
	for sheet in _atlas_sheets:
		if "flying-islands" in str(sheet["biome_path"]):
			preferred_biome_path = str(sheet["biome_path"])
			break
	if preferred_biome_path.is_empty() and not _atlas_sheets.is_empty():
		preferred_biome_path = str(_atlas_sheets[0]["biome_path"])
	var preferred_button: Button = _biome_buttons.get(preferred_biome_path)
	if preferred_button != null:
		_select_biome(preferred_biome_path, preferred_button)


func _add_palette_section_title(title: String) -> void:
	var label := Label.new()
	label.text = title
	label.add_theme_color_override("font_color", Color(0.94, 0.82, 0.56))
	_biome_list.add_child(label)


func _craftpix_pack_display_name(folder_name: String) -> String:
	return str(CRAFTPIX_PACK_LABELS.get(folder_name, folder_name.replace("-", " ").capitalize()))


func _craftpix_pack_png_files(pack_path: String) -> Array[String]:
	var paths: Array[String] = []
	var pack_directory := DirAccess.open(pack_path)
	if pack_directory == null:
		return paths
	for folder_name in ["PNG", "Tiled_files", "Tiled_foles"]:
		var source_path := pack_path.path_join(folder_name)
		if not DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(source_path)):
			continue
		_collect_pack_png_files(source_path, paths)
	paths.sort()
	return paths


func _collect_pack_png_files(directory_path: String, paths: Array[String]) -> void:
	var directory := DirAccess.open(directory_path)
	if directory == null:
		push_warning("Не удалось открыть каталог изображений пакета: " + directory_path)
		return
	var file_names := directory.get_files()
	file_names.sort()
	for file_name in file_names:
		if file_name.begins_with("._") or file_name.get_extension().to_lower() != "png":
			continue
		paths.append(directory_path.path_join(file_name))
	var folder_names := directory.get_directories()
	folder_names.sort()
	for folder_name in folder_names:
		if folder_name.begins_with(".") or folder_name == "__MACOSX":
			continue
		_collect_pack_png_files(directory_path.path_join(folder_name), paths)


func _png_dimensions(sheet_path: String) -> Vector2i:
	var file := FileAccess.open(sheet_path, FileAccess.READ)
	if file == null:
		push_warning("Не удалось прочитать PNG-лист пакета: " + sheet_path)
		return Vector2i.ZERO
	var header := file.get_buffer(24)
	file.close()
	if header.size() < 24 or header[0] != 137 or header[1] != 80 or header[2] != 78 \
		or header[3] != 71 or header[4] != 13 or header[5] != 10 or header[6] != 26 \
		or header[7] != 10:
		push_warning("PNG-лист пакета имеет неверный заголовок: " + sheet_path)
		return Vector2i.ZERO
	return Vector2i(_png_header_uint32(header, 16), _png_header_uint32(header, 20))


func _png_header_uint32(header: PackedByteArray, offset: int) -> int:
	return (int(header[offset]) << 24) | (int(header[offset + 1]) << 16) \
		| (int(header[offset + 2]) << 8) | int(header[offset + 3])


func _add_atlas_sheet(
	sheet_path: String,
	group_path: String,
	group_name: String,
	tile_size: int,
	category: String,
	create_tab := true,
	read_animations := true,
	animations_override: Dictionary = {},
	load_texture := true,
) -> void:
	var texture: Texture2D
	var image_size: Vector2i
	if load_texture:
		texture = load(sheet_path) as Texture2D
		if texture == null:
			push_warning("Не удалось загрузить лист тайлов: " + sheet_path)
			return
		image_size = Vector2i(texture.get_size())
	else:
		image_size = _png_dimensions(sheet_path)
	if image_size.x <= 0 or image_size.y <= 0:
		return
	var sheet := {
		"path": sheet_path,
		"biome_path": group_path,
		"biome_name": group_name,
		"name": sheet_path.get_file().get_basename(),
		"category": category,
		"tile_size": tile_size,
		"texture": texture,
		"columns": image_size.x / tile_size,
		"rows": image_size.y / tile_size,
		"animations": animations_override if not animations_override.is_empty() \
			else (_read_sheet_animations(sheet_path) if read_animations else {}),
	}
	_atlas_sheets_by_path[sheet_path] = sheet
	_atlas_sheets.append(sheet)
	if not create_tab:
		return
	var tab := Button.new()
	tab.text = str(sheet["name"])
	tab.tooltip_text = "%s · %s · %d×%d кадров%s" % [
		group_name,
		category,
		int(sheet["columns"]),
		int(sheet["rows"]),
		" · анимаций: %d" % sheet["animations"].size() if not sheet["animations"].is_empty() else "",
	]
	tab.toggle_mode = true
	tab.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	tab.pressed.connect(_select_atlas_sheet.bind(sheet_path, tab))
	_sheet_tabs.add_child(tab)
	_sheet_buttons[sheet_path] = tab


func _ensure_atlas_sheet_texture(sheet_path: String) -> Texture2D:
	var sheet: Dictionary = _atlas_sheets_by_path.get(sheet_path, {})
	if sheet.is_empty():
		return null
	var texture: Texture2D = sheet.get("texture")
	if texture != null:
		return texture
	if ResourceLoader.exists(sheet_path, "Texture2D"):
		texture = load(sheet_path) as Texture2D
	if texture == null:
		var image := Image.new()
		if image.load(ProjectSettings.globalize_path(sheet_path)) != OK:
			push_error("Не удалось загрузить изображение выбранного листа: " + sheet_path)
			return null
		texture = ImageTexture.create_from_image(image)
	sheet["texture"] = texture
	_atlas_sheets_by_path[sheet_path] = sheet
	return texture


func _craftpix_animation_info(sheet_name: String) -> Dictionary:
	var stem := sheet_name
	var animation_suffix_pattern := RegEx.new()
	animation_suffix_pattern.compile("(?i)(?:_animation|_animated)(\\d*)$")
	var animation_suffix_match := animation_suffix_pattern.search(stem)
	var has_animation_suffix := animation_suffix_match != null
	var animation_variant := ""
	if has_animation_suffix:
		animation_variant = animation_suffix_match.get_string(1)
		stem = stem.left(animation_suffix_match.get_start())
	else:
		for suffix in ["_without_shadow", "_with_shadow", "-sheet", "_sheet"]:
			if stem.to_lower().ends_with(suffix):
				stem = stem.left(stem.length() - suffix.length())
	stem = stem.strip_edges()
	var direction := ""
	var direction_pattern := RegEx.new()
	direction_pattern.compile("(?i)[ _-](front|back|left|right|up|down)$")
	var direction_match := direction_pattern.search(stem)
	if direction_match != null:
		direction = direction_match.get_string(1).to_lower()
		if direction == "front":
			direction = "down"
		elif direction == "back":
			direction = "up"
		stem = stem.left(direction_match.get_start()).strip_edges()
	var state_pattern := RegEx.new()
	state_pattern.compile("(?i)^(.+?)[ _-](idle|walk|run|attack|hurt|death|jump|fly|flight|move|swim)(?:[ _-](inside|outside))?$")
	var state_match := state_pattern.search(stem)
	if state_match == null:
		var animation_prefix_pattern := RegEx.new()
		animation_prefix_pattern.compile("(?i)^animation[_ -](.+)$")
		var animation_prefix_match := animation_prefix_pattern.search(stem)
		if animation_prefix_match != null:
			stem = animation_prefix_match.get_string(1).strip_edges()
			has_animation_suffix = true
			state_match = state_pattern.search(stem)
	if state_match == null and has_animation_suffix and not stem.is_empty():
		var entity_name := stem
		if not animation_variant.is_empty():
			entity_name += "_" + animation_variant
		return {
			"entity_name": entity_name,
			"entity_key": entity_name.to_lower().replace(" ", "_").replace("-", "_"),
			"state": "animation",
			"direction": "",
		}
	if state_match == null:
		return {}
	var entity_name := state_match.get_string(1).strip_edges()
	var variant := state_match.get_string(3).to_lower()
	if not variant.is_empty():
		entity_name += "_" + variant
	if entity_name.is_empty():
		return {}
	var state_name := state_match.get_string(2).to_lower()
	if state_name == "flight":
		state_name = "fly"
	return {
		"entity_name": entity_name,
		"entity_key": entity_name.to_lower().replace(" ", "_").replace("-", "_"),
		"state": state_name,
		"direction": direction,
	}


func _craftpix_animation_priority(sheet_path: String) -> int:
	var path := sheet_path.to_lower()
	var file_name := path.get_file()
	var priority := 0
	if file_name.ends_with("_with_shadow.png"):
		priority += 4
	elif not file_name.ends_with("_without_shadow.png"):
		priority += 2
	if "/png/" in path:
		priority += 1
	var sheet: Dictionary = _atlas_sheets_by_path.get(sheet_path, {})
	if not sheet.get("animations", {}).is_empty():
		priority += 8
	return priority


func _build_craftpix_animation_groups(
	pack_path: String,
	pack_folder: String,
	pack_name: String,
	sheet_paths: Array[String],
) -> int:
	var preferred_sheets: Dictionary = {}
	var preferred_infos: Dictionary = {}
	for sheet_path in sheet_paths:
		var sheet_name := sheet_path.get_file().get_basename()
		var info := _craftpix_animation_info(sheet_name)
		if info.is_empty():
			continue
		var canonical_name := sheet_name.to_lower()
		for suffix in ["_without_shadow", "_with_shadow"]:
			if canonical_name.ends_with(suffix):
				canonical_name = canonical_name.left(canonical_name.length() - suffix.length())
		var priority := _craftpix_animation_priority(sheet_path)
		var existing_path: String = preferred_sheets.get(canonical_name, "")
		if not existing_path.is_empty() and _craftpix_animation_priority(existing_path) >= priority:
			continue
		preferred_sheets[canonical_name] = sheet_path
		preferred_infos[canonical_name] = info
	var groups: Dictionary = {}
	var canonical_names: Array = preferred_sheets.keys()
	canonical_names.sort()
	for canonical_name in canonical_names:
		var info: Dictionary = preferred_infos[canonical_name]
		var entity_key := str(info["entity_key"])
		if not groups.has(entity_key):
			groups[entity_key] = {
				"name": str(info["entity_name"]).replace("_", " ").capitalize(),
				"states": {},
			}
		var group: Dictionary = groups[entity_key]
		var states: Dictionary = group["states"]
		var state_name := str(info["state"])
		var state: Dictionary = states.get(state_name, {"name": state_name, "entries": []})
		var entries: Array = state["entries"]
		entries.append({
			"path": str(preferred_sheets[canonical_name]),
			"direction": str(info["direction"]),
		})
		state["entries"] = entries
		states[state_name] = state
		group["states"] = states
		groups[entity_key] = group
	var entity_keys: Array = groups.keys()
	entity_keys.sort()
	var created := 0
	for entity_key in entity_keys:
		var group: Dictionary = groups[entity_key]
		var states: Dictionary = group["states"]
		var has_movement := false
		for state_name in states:
			if state_name in MOVEMENT_STATES or state_name == "animation":
				has_movement = true
				break
		if not has_movement:
			continue
		var state_names: Array = states.keys()
		state_names.sort()
		for state_name in state_names:
			var state: Dictionary = states[state_name]
			var clips: Array[Dictionary] = []
			for entry in state["entries"]:
				clips.append_array(_craftpix_animation_clips(
					str(entry["path"]),
					str(entry["direction"]),
					state_name == "animation",
				))
			state["clips"] = clips
			states[state_name] = state
		group["states"] = states
		var usable_states: Array[String] = []
		for state_name in states:
			if not states[state_name].get("clips", []).is_empty():
				usable_states.append(str(state_name))
		var has_usable_movement := false
		for state_name in usable_states:
			if state_name in MOVEMENT_STATES or state_name == "animation":
				has_usable_movement = true
				break
		if not has_usable_movement:
			continue
		group["default_state"] = _default_animal_state(usable_states)
		var variants: Array[Dictionary] = []
		if usable_states.size() == 1 and usable_states[0] == "animation":
			var animation_state: Dictionary = states["animation"]
			for clip_index in animation_state["clips"].size():
				var variant_state := animation_state.duplicate(true)
				variant_state["clips"] = [animation_state["clips"][clip_index]]
				variant_state["name"] = "animation"
				var variant_states: Dictionary = {"animation": variant_state}
				variants.append({
					"states": variant_states,
					"name": "%s %d" % [group["name"], clip_index + 1],
					"key": "%s_%d" % [entity_key, clip_index + 1],
				})
		else:
			variants.append({
				"states": states,
				"name": str(group["name"]),
				"key": str(entity_key),
			})
		for variant in variants:
			var key := _animal_instance_key(pack_folder, str(variant["key"]))
			var animal_group := {
				"key": key,
				"pack_path": pack_path,
				"pack_folder": pack_folder,
				"name": str(variant["name"]),
				"kind": "animal",
				"states": variant["states"],
				"default_state": str(group["default_state"]),
			}
			_animal_groups.append(animal_group)
			_animal_groups_by_key[key] = animal_group
			created += 1
	return created


func _craftpix_animation_clips(
	sheet_path: String,
	direction: String,
	vertical_only := false,
) -> Array[Dictionary]:
	var clips: Array[Dictionary] = []
	var sheet: Dictionary = _atlas_sheets_by_path.get(sheet_path, {})
	if sheet.is_empty():
		return clips
	var vertical_clips := _craftpix_vertical_animation_clips(sheet_path, sheet)
	if not vertical_clips.is_empty():
		return vertical_clips
	if vertical_only:
		return clips
	var tile_size := int(sheet.get("tile_size", ATLAS_TILE_SIZE))
	var columns := int(sheet.get("columns", 0))
	var rows := int(sheet.get("rows", 0))
	if tile_size <= 0 or columns <= 0 or rows <= 0:
		return clips
	var image_width := columns * tile_size
	var image_height := rows * tile_size
	var direction_names := ["down", "left", "right", "up"]
	var direction_count := 1
	var frame_height := image_height
	if direction.is_empty() and image_height % 4 == 0:
		direction_count = 4
		frame_height = image_height / direction_count
	if frame_height < tile_size or frame_height % tile_size != 0 or image_width % frame_height != 0:
		return clips
	var frame_size_tiles := frame_height / tile_size
	var frame_count := columns / frame_size_tiles
	if frame_count < 2:
		return clips
	for row in direction_count:
		var frames: Array[Dictionary] = []
		for frame_index in frame_count:
			frames.append({
				"tile_id": row * frame_size_tiles * columns + frame_index * frame_size_tiles,
				"duration": 120,
			})
		var clip := {
			"sheet_path": sheet_path,
			"frame_ids": frames,
			"frame_size": Vector2i(frame_size_tiles, frame_size_tiles),
			"origin_tile_id": int(frames[0]["tile_id"]),
			"direction": str(direction_names[row]) if direction.is_empty() else direction,
		}
		clips.append(clip)
	return clips


func _craftpix_vertical_animation_clips(
	sheet_path: String,
	sheet: Dictionary,
) -> Array[Dictionary]:
	var clips: Array[Dictionary] = []
	var animations: Dictionary = sheet.get("animations", {})
	var columns := int(sheet.get("columns", 0))
	var rows := int(sheet.get("rows", 0))
	var tile_size := int(sheet.get("tile_size", ATLAS_TILE_SIZE))
	if animations.is_empty() or columns <= 0 or rows <= 0 or tile_size <= 0:
		return clips
	var tile_ids: Array[int] = []
	for tile_id in animations:
		tile_ids.append(int(tile_id))
	tile_ids.sort()
	var frame_ids: Array = []
	var frame_height_tiles := 0
	for tile_id in tile_ids:
		var candidate_frames: Array = animations[tile_id]
		if candidate_frames.size() < 2:
			continue
		var unique_frames: Array[Dictionary] = []
		# Tiled повторяет ID кадра для паузы; объединяем длительность перед поиском шага по строкам.
		for candidate_frame in candidate_frames:
			var source_id := int(candidate_frame.get("tile_id", -1))
			if not unique_frames.is_empty() \
				and int(unique_frames[-1].get("tile_id", -1)) == source_id:
				unique_frames[-1]["duration"] = int(unique_frames[-1].get("duration", 0)) \
					+ int(candidate_frame.get("duration", 0))
			else:
				unique_frames.append(candidate_frame.duplicate(true))
		if unique_frames.size() < 2:
			continue
		var first_id := int(unique_frames[0].get("tile_id", -1))
		var second_id := int(unique_frames[1].get("tile_id", -1))
		var vertical_step := absi(second_id - first_id)
		if first_id != tile_id or vertical_step <= columns or vertical_step % columns != 0:
			continue
		var candidate_height := vertical_step / columns
		var valid_track := candidate_height > 0
		var start_row := int(tile_id / columns)
		for unique_frame in unique_frames:
			var source_id := int(unique_frame.get("tile_id", -1))
			var source_row := int(source_id / columns)
			if source_id % columns != tile_id % columns \
				or posmod(abs(source_row - start_row), candidate_height) != 0 \
				or source_row + candidate_height > rows:
				valid_track = false
				break
		if not valid_track:
			continue
		frame_ids = unique_frames
		frame_height_tiles = candidate_height
		break
	if frame_ids.is_empty():
		return clips
	var image := Image.load_from_file(sheet_path)
	if image == null or image.is_empty():
		push_error("Не удалось прочитать вертикальный лист анимации: " + sheet_path)
		return clips
	var frame_height := frame_height_tiles * tile_size
	var column_ranges: Array[Vector2i] = []
	var range_start := -1
	for x in image.get_width():
		var occupied := false
		for y in image.get_height():
			# Слабое свечение не должно склеивать соседние варианты анимации.
			if image.get_pixel(x, y).a > 0.25:
				occupied = true
				break
		if occupied and range_start < 0:
			range_start = x
		elif not occupied and range_start >= 0:
			column_ranges.append(Vector2i(range_start, x))
			range_start = -1
	if range_start >= 0:
		column_ranges.append(Vector2i(range_start, image.get_width()))
	for column_range in column_ranges:
		var frames: Array[Dictionary] = []
		for frame_index in frame_ids.size():
			var frame_id := int(frame_ids[frame_index].get("tile_id", -1))
			var frame_y := int(frame_id / columns) * tile_size
			var frame_rect := Rect2i(
				column_range.x,
				frame_y,
				column_range.y - column_range.x,
				frame_height,
			)
			if frame_id < 0 or not Rect2i(Vector2i.ZERO, image.get_size()).encloses(frame_rect):
				frames.clear()
				break
			frames.append({
				"tile_id": frame_index,
				"duration": int(frame_ids[frame_index].get("duration", 120)),
				"source_rect": frame_rect,
			})
		if frames.size() < 2:
			continue
		clips.append({
			"sheet_path": sheet_path,
			"frame_ids": frames,
			"frame_size": Vector2i(
				ceili(float(column_range.y - column_range.x) / float(tile_size)),
				frame_height_tiles,
			),
			"origin_tile_id": int(frame_ids[0]["tile_id"]),
		})
	return clips


func _build_animal_groups(
	pack_path: String,
	pack_folder: String,
	group_kind := "animal",
) -> void:
	var groups_by_species: Dictionary = {}
	var is_fish_pack := pack_folder == "craftpix-net-596440-fishing-and-gathering-pixel-art-rpg-icons"
	var action_pattern := RegEx.new()
	action_pattern.compile("(?i)(walk_attack|run_attack|idle|walk|run|attack|hurt|death|jump|flight|fly|move|swim)\\d*$")
	var direction_suffix_pattern := RegEx.new()
	direction_suffix_pattern.compile("(?i)_?(front|back|left|right)$")
	for sheet in _atlas_sheets:
		if str(sheet.get("biome_path", "")) != pack_path:
			continue
		var sheet_name := str(sheet.get("name", ""))
		var lower_name := sheet_name.to_lower()
		if is_fish_pack:
			var fish_number := lower_name.trim_prefix("fish")
			if not lower_name.begins_with("fish") or not fish_number.is_valid_int():
				continue
		elif not lower_name.ends_with("_with_shadow"):
			continue
		var stem := sheet_name
		if lower_name.ends_with("_with_shadow"):
			stem = stem.left(stem.length() - "_with_shadow".length())
		stem = stem.strip_edges()
		if stem.to_lower().ends_with("_animation"):
			stem = stem.left(stem.length() - "_animation".length())
		var state_name := "animation"
		stem = direction_suffix_pattern.sub(stem, "", true).strip_edges()
		var action_match := action_pattern.search(stem)
		if action_match != null:
			state_name = action_match.get_string(1).to_lower()
			stem = stem.left(action_match.get_start()).trim_suffix("_").trim_suffix("-").strip_edges()
		var species_key := stem.to_lower()
		if species_key.is_empty():
			continue
		var animal_key := _animal_instance_key(pack_folder, species_key) \
			if group_kind == "animal" else _mob_instance_key(pack_folder, species_key)
		if not groups_by_species.has(species_key):
			groups_by_species[species_key] = {
				"key": animal_key,
				"pack_path": pack_path,
				"pack_folder": pack_folder,
				"name": _lpc_mob_display_name(pack_folder, stem) if group_kind == "mob" \
					else stem.replace("_", " ").capitalize(),
				"kind": group_kind,
				"states": {},
			}
		var group: Dictionary = groups_by_species[species_key]
		var states: Dictionary = group["states"]
		if not states.has(state_name):
			states[state_name] = {"name": state_name, "sheets": []}
		var state: Dictionary = states[state_name]
		state["sheets"].append(str(sheet["path"]))
		states[state_name] = state
		group["states"] = states
		groups_by_species[species_key] = group
	var species_keys: Array[String] = []
	for species_key in groups_by_species:
		species_keys.append(str(species_key))
	species_keys.sort()
	for species_key in species_keys:
		var group: Dictionary = groups_by_species[species_key]
		var states: Dictionary = group["states"]
		var state_names: Array[String] = []
		for state_name in states:
			state_names.append(str(state_name))
		state_names.sort()
		for state_name in state_names:
			var state: Dictionary = states[state_name]
			var sheet_paths: Array = state["sheets"]
			sheet_paths.sort()
			var preferred_paths: Dictionary = {}
			for sheet_path in sheet_paths:
				var path := str(sheet_path)
				var sheet_name := path.get_file().to_lower()
				var existing_path: String = preferred_paths.get(sheet_name, "")
				var candidate_sheet: Dictionary = _atlas_sheets_by_path.get(path, {})
				var existing_sheet: Dictionary = _atlas_sheets_by_path.get(existing_path, {})
				if existing_path.is_empty() \
					or (existing_sheet.get("animations", {}).is_empty()
						and not candidate_sheet.get("animations", {}).is_empty()) \
					or (not candidate_sheet.get("animations", {}).is_empty()
						and "/tiled/" in path.to_lower()
						and "/tiled/" not in existing_path.to_lower()):
					preferred_paths[sheet_name] = path
			var clips: Array[Dictionary] = []
			var preferred_names: Array = preferred_paths.keys()
			preferred_names.sort()
			for sheet_name in preferred_names:
				var sheet_path: String = preferred_paths[sheet_name]
				var sheet: Dictionary = _atlas_sheets_by_path.get(sheet_path, {})
				var sheet_clips := _extract_animal_clips(sheet, is_fish_pack)
				if sheet_clips.is_empty():
					sheet_clips = _craftpix_animation_clips(sheet_path, "")
				clips.append_array(sheet_clips)
			if clips.is_empty():
				continue
			state["clips"] = clips
			states[state_name] = state
		var has_clips := false
		for state in states.values():
			if not state.get("clips", []).is_empty():
				has_clips = true
				break
		if not has_clips:
			continue
		group["states"] = states
		group["default_state"] = _default_animal_state(state_names)
		_animal_groups.append(group)
		_animal_groups_by_key[str(group["key"])] = group
		if is_inside_tree():
			await get_tree().process_frame


func _swordsman_level_directories() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var root_directory := DirAccess.open(SWORDSMAN_ROOT)
	if root_directory == null:
		return result
	var level_pattern := RegEx.new()
	level_pattern.compile("(?i)^Swordsman_lvl([1-9])$")
	var pack_folders := root_directory.get_directories()
	pack_folders.sort()
	for pack_folder in pack_folders:
		if pack_folder.begins_with(".") or pack_folder == "__MACOSX":
			continue
		var png_path := SWORDSMAN_ROOT.path_join(pack_folder).path_join("PNG")
		var png_directory := DirAccess.open(png_path)
		if png_directory == null:
			continue
		var level_folders := png_directory.get_directories()
		level_folders.sort()
		for level_folder in level_folders:
			var level_match := level_pattern.search(level_folder)
			if level_match == null:
				continue
			var parts_path := png_path.path_join(level_folder).path_join("Parts")
			if DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(parts_path)):
				result.append({
					"level": int(level_match.get_string(1)),
					"parts_path": parts_path,
				})
	result.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return int(a["level"]) < int(b["level"])
	)
	return result


func _build_swordsman_hero_groups() -> int:
	var levels := _swordsman_level_directories()
	var layer_pattern := RegEx.new()
	layer_pattern.compile(
		"(?i)^(?:Swordsman_)?lvl([1-9])_(.+)_(sword_back|body|head|shadow|sword|sword_arm)$",
	)
	var supported_actions := [
		"idle", "walk", "run", "attack", "hurt", "death", "run_attack", "walk_attack",
	]
	for level_info in levels:
		var level := int(level_info["level"])
		var parts_path := str(level_info["parts_path"])
		var parts_directory := DirAccess.open(parts_path)
		if parts_directory == null:
			push_error("Не удалось открыть части спрайта мечника: " + parts_path)
			continue
		var action_layers: Dictionary = {}
		for file_name in parts_directory.get_files():
			if file_name.begins_with("._") or file_name.get_extension().to_lower() != "png":
				continue
			var layer_match := layer_pattern.search(file_name.get_basename())
			if layer_match == null or int(layer_match.get_string(1)) != level:
				continue
			var action_name := layer_match.get_string(2).to_lower()
			if not supported_actions.has(action_name):
				continue
			var layer_name := layer_match.get_string(3).to_lower()
			var layers: Dictionary = action_layers.get(action_name, {})
			layers[layer_name] = parts_path.path_join(file_name)
			action_layers[action_name] = layers
		var states: Dictionary = {}
		for action in supported_actions:
			var layers: Dictionary = action_layers.get(action, {})
			if not layers.has("body") or not layers.has("head"):
				continue
			var sheet_path := _compose_swordsman_action_sheet(level, action, layers)
			if sheet_path.is_empty():
				continue
			var sheet: Dictionary = _atlas_sheets_by_path[sheet_path]
			var clips := _swordsman_action_clips(sheet_path, sheet)
			if clips.is_empty():
				continue
			states[action] = {"name": action, "clips": clips}
			if is_inside_tree():
				await get_tree().process_frame
		if not states.has("idle"):
			push_error("Для мечника уровня %d не удалось собрать анимацию покоя." % level)
			continue
		var hero_key := _animal_instance_key("swordsman", "swordsman_lvl%d" % level)
		var group := {
			"key": hero_key,
			"pack_path": SWORDSMAN_ROOT,
			"pack_folder": "swordsman",
			"name": "Мечник · уровень %d" % level,
			"kind": "hero",
			"states": states,
			"default_state": "idle",
		}
		_animal_groups.append(group)
		_animal_groups_by_key[hero_key] = group
		if is_inside_tree():
			await get_tree().process_frame
	return levels.size()


func _compose_swordsman_action_sheet(
	level: int,
	action: String,
	layers: Dictionary,
) -> String:
	var layer_order := ["shadow", "sword_back", "body", "head", "sword", "sword_arm"]
	var source_images: Array[Image] = []
	var image_size := Vector2i.ZERO
	for layer_name in layer_order:
		if not layers.has(layer_name):
			continue
		var source := Image.new()
		var source_path := ProjectSettings.globalize_path(str(layers[layer_name]))
		var load_error := source.load(source_path)
		if load_error != OK:
			push_error("Не удалось загрузить часть героя: %s (%s)" % [str(layers[layer_name]), error_string(load_error)])
			return ""
		if image_size == Vector2i.ZERO:
			image_size = source.get_size()
		elif source.get_size() != image_size:
			push_error("Размеры частей анимации мечника не совпадают: " + str(layers[layer_name]))
			return ""
		source_images.append(source)
	if image_size.x <= 0 or image_size.y <= 0 \
		or image_size.x % HERO_FRAME_SIZE != 0 or image_size.y != HERO_FRAME_SIZE * 4:
		push_error("Неверный формат листа анимации мечника, уровень %d, действие %s." % [level, action])
		return ""
	var composite := Image.create(
		image_size.x, image_size.y, false, Image.FORMAT_RGBA8,
	)
	composite.fill(Color.TRANSPARENT)
	for source in source_images:
		composite.blend_rect(
			source,
			Rect2i(Vector2i.ZERO, image_size),
			Vector2i.ZERO,
		)
	var sheet_path := "hero://swordsman/level_%d/%s" % [level, action]
	_atlas_sheets_by_path[sheet_path] = {
		"path": sheet_path,
		"name": "Мечник · уровень %d · %s" % [level, action],
		"texture": ImageTexture.create_from_image(composite),
		"tile_size": ATLAS_TILE_SIZE,
		"columns": image_size.x / ATLAS_TILE_SIZE,
		"rows": image_size.y / ATLAS_TILE_SIZE,
		"animations": {},
	}
	return sheet_path


func _swordsman_action_clips(sheet_path: String, sheet: Dictionary) -> Array[Dictionary]:
	var clips: Array[Dictionary] = []
	var columns := int(sheet.get("columns", 0))
	var rows := int(sheet.get("rows", 0))
	var frame_width_tiles := HERO_FRAME_SIZE / ATLAS_TILE_SIZE
	var frame_count := columns / frame_width_tiles
	if columns <= 0 or rows != frame_width_tiles * 4 or frame_count <= 0:
		return clips
	var directions := ["down", "left", "right", "up"]
	for row in range(4):
		var frames: Array[Dictionary] = []
		for frame_index in range(frame_count):
			frames.append({
				"tile_id": row * frame_width_tiles * columns + frame_index * frame_width_tiles,
				"duration": 100,
			})
		clips.append({
			"sheet_path": sheet_path,
			"frame_ids": frames,
			"frame_size": Vector2i(frame_width_tiles, frame_width_tiles),
			"origin_tile_id": int(frames[0]["tile_id"]),
			"direction": directions[row],
		})
	return clips


func _mage_level_directories() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var root_directory := DirAccess.open(MAGE_ROOT)
	if root_directory == null:
		return result
	var level_pattern := RegEx.new()
	level_pattern.compile("(?i)^Mage_([1-9])lvl$")
	var pack_folders := root_directory.get_directories()
	pack_folders.sort()
	for pack_folder in pack_folders:
		if pack_folder.begins_with(".") or pack_folder == "__MACOSX":
			continue
		var png_path := MAGE_ROOT.path_join(pack_folder).path_join("PNG")
		var png_directory := DirAccess.open(png_path)
		if png_directory == null:
			continue
		var level_folders := png_directory.get_directories()
		level_folders.sort()
		for level_folder in level_folders:
			var level_match := level_pattern.search(level_folder)
			if level_match == null:
				continue
			var sprite_path := png_path.path_join(level_folder).path_join("With_shadow")
			if DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(sprite_path)):
				result.append({
					"level": int(level_match.get_string(1)),
					"sprite_path": sprite_path,
				})
	result.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return int(a["level"]) < int(b["level"])
	)
	return result


func _build_mage_hero_groups() -> int:
	var levels := _mage_level_directories()
	var action_pattern := RegEx.new()
	action_pattern.compile("(?i)^Mage_lvl([1-9])_(attack|death|hurt|idle|run|walk)$")
	var supported_actions := ["idle", "walk", "run", "attack", "hurt", "death"]
	for level_info in levels:
		var level := int(level_info["level"])
		var sprite_path := str(level_info["sprite_path"])
		var sprite_directory := DirAccess.open(sprite_path)
		if sprite_directory == null:
			push_error("Не удалось открыть готовые спрайты мага: " + sprite_path)
			continue
		var action_paths: Dictionary = {}
		for file_name in sprite_directory.get_files():
			if file_name.begins_with("._") or file_name.get_extension().to_lower() != "png":
				continue
			var action_match := action_pattern.search(file_name.get_basename())
			if action_match == null or int(action_match.get_string(1)) != level:
				continue
			action_paths[action_match.get_string(2).to_lower()] = sprite_path.path_join(file_name)
		var states: Dictionary = {}
		for action in supported_actions:
			if not action_paths.has(action):
				continue
			var sheet_path := _load_hero_action_sheet(
				"mage", "Маг", level, action, str(action_paths[action]),
			)
			if sheet_path.is_empty():
				continue
			var sheet: Dictionary = _atlas_sheets_by_path[sheet_path]
			var clips := _swordsman_action_clips(sheet_path, sheet)
			if not clips.is_empty():
				states[action] = {"name": action, "clips": clips}
			if is_inside_tree():
				await get_tree().process_frame
		if not states.has("idle"):
			push_error("Для мага уровня %d не удалось загрузить анимацию покоя." % level)
			continue
		var hero_key := _animal_instance_key("mage", "mage_lvl%d" % level)
		var group := {
			"key": hero_key,
			"pack_path": MAGE_ROOT,
			"pack_folder": "mage",
			"name": "Маг · уровень %d" % level,
			"kind": "hero",
			"states": states,
			"default_state": "idle",
		}
		_animal_groups.append(group)
		_animal_groups_by_key[hero_key] = group
		if is_inside_tree():
			await get_tree().process_frame
	return levels.size()


func _load_hero_action_sheet(
	hero_type: String,
	hero_name: String,
	level: int,
	action: String,
	image_path: String,
) -> String:
	var image := Image.new()
	var load_error := image.load(ProjectSettings.globalize_path(image_path))
	if load_error != OK:
		push_error("Не удалось загрузить спрайт героя: %s (%s)" % [
			image_path, error_string(load_error),
		])
		return ""
	if image.get_width() <= 0 or image.get_width() % HERO_FRAME_SIZE != 0 \
		or image.get_height() != HERO_FRAME_SIZE * 4:
		push_error("Неверный формат спрайта героя %s, уровень %d, действие %s." % [
			hero_name, level, action,
		])
		return ""
	var sheet_path := "hero://%s/level_%d/%s" % [hero_type, level, action]
	_atlas_sheets_by_path[sheet_path] = {
		"path": sheet_path,
		"name": "%s · уровень %d · %s" % [hero_name, level, action],
		"texture": ImageTexture.create_from_image(image),
		"tile_size": ATLAS_TILE_SIZE,
		"columns": image.get_width() / ATLAS_TILE_SIZE,
		"rows": image.get_height() / ATLAS_TILE_SIZE,
		"animations": {},
	}
	return sheet_path


func _archer_level_directories() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var root_directory := DirAccess.open(ARCHER_ROOT)
	if root_directory == null:
		return result
	var level_pattern := RegEx.new()
	level_pattern.compile("(?i)^Archer_lvl([1-9])$")
	var pack_folders := root_directory.get_directories()
	pack_folders.sort()
	for pack_folder in pack_folders:
		if pack_folder.begins_with(".") or pack_folder == "__MACOSX":
			continue
		var png_path := ARCHER_ROOT.path_join(pack_folder).path_join("PNG")
		var png_directory := DirAccess.open(png_path)
		if png_directory == null:
			continue
		var level_folders := png_directory.get_directories()
		level_folders.sort()
		for level_folder in level_folders:
			var level_match := level_pattern.search(level_folder)
			if level_match == null:
				continue
			var sprite_path := png_path.path_join(level_folder).path_join("Without_shadow")
			if DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(sprite_path)):
				result.append({
					"level": int(level_match.get_string(1)),
					"sprite_path": sprite_path,
				})
	result.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return int(a["level"]) < int(b["level"])
	)
	return result


func _build_archer_hero_groups() -> int:
	var levels := _archer_level_directories()
	var action_pattern := RegEx.new()
	action_pattern.compile(
		"(?i)^(?:Archer_)?lvl([1-9])_(attack|death|hurt|idle|run|walk)(?:_full)?_without_shadow$",
	)
	var supported_actions := ["idle", "walk", "run", "attack", "hurt", "death"]
	for level_info in levels:
		var level := int(level_info["level"])
		var sprite_path := str(level_info["sprite_path"])
		var sprite_directory := DirAccess.open(sprite_path)
		if sprite_directory == null:
			push_error("Не удалось открыть готовые спрайты лучника: " + sprite_path)
			continue
		var action_paths: Dictionary = {}
		for file_name in sprite_directory.get_files():
			if file_name.begins_with("._") or file_name.get_extension().to_lower() != "png":
				continue
			var action_match := action_pattern.search(file_name.get_basename())
			if action_match == null or int(action_match.get_string(1)) != level:
				continue
			action_paths[action_match.get_string(2).to_lower()] = sprite_path.path_join(file_name)
		var states: Dictionary = {}
		for action in supported_actions:
			if not action_paths.has(action):
				continue
			var sheet_path := _load_hero_action_sheet(
				"archer", "Лучник", level, action, str(action_paths[action]),
			)
			if sheet_path.is_empty():
				continue
			var sheet: Dictionary = _atlas_sheets_by_path[sheet_path]
			var clips := _swordsman_action_clips(sheet_path, sheet)
			if not clips.is_empty():
				states[action] = {"name": action, "clips": clips}
			if is_inside_tree():
				await get_tree().process_frame
		if not states.has("idle"):
			push_error("Для лучника уровня %d не удалось загрузить анимацию покоя." % level)
			continue
		var hero_key := _animal_instance_key("archer", "archer_lvl%d" % level)
		var group := {
			"key": hero_key,
			"pack_path": ARCHER_ROOT,
			"pack_folder": "archer",
			"name": "Лучник · уровень %d" % level,
			"kind": "hero",
			"states": states,
			"default_state": "idle",
		}
		_animal_groups.append(group)
		_animal_groups_by_key[hero_key] = group
		if is_inside_tree():
			await get_tree().process_frame
	return levels.size()


func _collect_lpc_png_files(directory_path: String, output: Array[String]) -> void:
	var directory := DirAccess.open(directory_path)
	if directory == null:
		push_warning("Не удалось открыть каталог ресурсов LPC: " + directory_path)
		return
	var files := directory.get_files()
	files.sort()
	for file_name in files:
		if file_name.begins_with("._") or file_name.get_extension().to_lower() != "png":
			continue
		output.append(directory_path.path_join(file_name))
	var child_directories := directory.get_directories()
	child_directories.sort()
	for child_name in child_directories:
		if child_name.begins_with(".") or child_name == "__MACOSX":
			continue
		_collect_lpc_png_files(directory_path.path_join(child_name), output)


func _lpc_pack_display_name(pack_folder: String) -> String:
	match pack_folder:
		"craftpix-net-870078-top-down-pixel-skeletons-character-sprite-pack":
			return "Скелеты"
		"craftpix-net-625807-golem-pixel-art-top-down-sprite-pack":
			return "Големы"
		"craftpix-net-208004-free-vampire-4-direction-pixel-character-sprite-pack":
			return "Вампиры"
		"craftpix-net-284465-free-predator-plant-mobs-pixel-art-pack":
			return "Хищные растения"
		"craftpix-net-393827-top-down-pixel-gnolls-character-pack":
			return "Гноллы"
		"craftpix-net-404608-beholder-monsters-top-down-pixel-art-sprites":
			return "Бехолдеры"
		"craftpix-net-415491-giant-rat-4-direction-pixel-character-sprite-pack":
			return "Крысы"
		"craftpix-net-463118-demons-4-direction-pixel-character-sprite-pack":
			return "Демоны"
		"craftpix-net-500988-imp-mobs-pixel-art-character-sprite-pack":
			return "Импы"
		"craftpix-net-510319-top-down-pixel-art-slime-monsters-sprite-pack":
			return "Слаймы"
		"craftpix-net-543463-top-down-pixel-lich-character-sprites":
			return "Личи"
		"craftpix-net-550920-zombie-4-direction-pixel-character-sprite-pack":
			return "Зомби"
		"craftpix-net-743043-pixel-art-slime-enemies-top-down-sprite-pack":
			return "Слаймы 2"
		"craftpix-net-788364-free-slime-mobs-pixel-art-top-down-sprite-pack":
			return "Слаймы 3"
		"craftpix-net-827305-slime-boss-pixel-art-2d-sprite-for-roguelike-games":
			return "Босс-слайм"
		"craftpix-net-838021-top-down-pixel-ent-character-sprites":
			return "Энты"
		"craftpix-net-846584-top-down-pixel-mushroom-sprite-pack":
			return "Грибы"
		"craftpix-net-894297-top-down-pixel-ghost-character-sprite-pack":
			return "Призраки"
		"craftpix-net-900504-lizardmen-pixel-art-character-sprite-pack":
			return "Ящеролюды"
		"goblin sprite-pack":
			return "Гоблины"
		"orc sprite":
			return "Орки"
		"LPC imp":
			return "Импы LPC"
		"LPC Imp 2":
			return "Импы LPC 2"
	return pack_folder.replace("-", " ").capitalize()


func _lpc_mob_display_name(pack_folder: String, stem: String) -> String:
	var lower_stem := stem.to_lower()
	var name_prefixes := [
		["slime_boss", "Босс-слайм"],
		["golem", "Голем"],
		["vampires", "Вампир"],
		["skeleton", "Скелет"],
		["plant", "Растение"],
		["gnoll", "Гнолл"],
		["beholder", "Бехолдер"],
		["rat", "Крыса"],
		["demon", "Демон"],
		["imp", "Имп"],
		["slime", "Слайм"],
		["lich", "Лич"],
		["zombie", "Зомби"],
		["ent", "Энт"],
		["mushroom", "Гриб"],
		["ghost", "Призрак"],
		["lizardman", "Ящеролюд"],
		["orc", "Орк"],
		["g", "Гоблин"],
	]
	for entry in name_prefixes:
		var source_prefix := str(entry[0])
		if not lower_stem.begins_with(source_prefix):
			continue
		var suffix := stem.substr(source_prefix.length()).trim_prefix("_").strip_edges()
		return str(entry[1]) + (" " + suffix if not suffix.is_empty() else "")
	return stem.replace("_", " ").capitalize()


func _mob_instance_key(pack_folder: String, species_key: String) -> String:
	return "%s%s|%s" % [MOB_INSTANCE_PREFIX, pack_folder, species_key]


func _get_or_create_lpc_mob_group(
	pack_path: String,
	pack_folder: String,
	species_key: String,
	display_name: String,
) -> Dictionary:
	var key := _mob_instance_key(pack_folder, species_key)
	var existing: Dictionary = _animal_groups_by_key.get(key, {})
	if not existing.is_empty():
		return existing
	var group := {
		"key": key,
		"pack_path": pack_path,
		"pack_folder": pack_folder,
		"name": display_name,
		"kind": "mob",
		"states": {},
		"default_state": "",
	}
	_animal_groups.append(group)
	_animal_groups_by_key[key] = group
	return group


func _add_lpc_mob_clip(group: Dictionary, state_name: String, clip: Dictionary) -> void:
	var states: Dictionary = group.get("states", {})
	var state: Dictionary = states.get(state_name, {"name": state_name, "clips": []})
	var clips: Array = state.get("clips", [])
	clips.append(clip)
	state["clips"] = clips
	states[state_name] = state
	group["states"] = states
	var state_names: Array[String] = []
	for name in states:
		state_names.append(str(name))
	state_names.sort()
	group["default_state"] = _default_animal_state(state_names)
	_animal_groups_by_key[str(group["key"])] = group


func _make_lpc_grid_clip(
	sheet_path: String,
	start_cell: Vector2i,
	frame_size: Vector2i,
	frame_count: int,
	duration_msec := 120,
	direction_name := "",
) -> Dictionary:
	var sheet: Dictionary = _atlas_sheets_by_path.get(sheet_path, {})
	var columns := int(sheet.get("columns", 0))
	var rows := int(sheet.get("rows", 0))
	if columns <= 0 or frame_count <= 0 or start_cell.x < 0 or start_cell.y < 0 \
		or start_cell.x + frame_size.x * frame_count > columns \
		or start_cell.y + frame_size.y > rows:
		return {}
	var first_tile_id := start_cell.y * columns + start_cell.x
	var frames: Array[Dictionary] = []
	for index in range(frame_count):
		frames.append({
			"tile_id": first_tile_id + index * frame_size.x,
			"duration": duration_msec,
		})
	var clip := {
		"sheet_path": sheet_path,
		"frame_ids": frames,
		"frame_size": frame_size,
		"origin_tile_id": first_tile_id,
	}
	if not direction_name.is_empty():
		clip["direction"] = direction_name
	return clip


func _build_lpc_imp_groups(
	pack_path: String,
	pack_folder: String,
	pack_name: String,
	png_paths: Array[String],
) -> void:
	for sheet_path in png_paths:
		var base_name := sheet_path.get_file().get_basename().to_lower()
		var action := ""
		if base_name.begins_with("walk - "):
			action = "walk"
		elif base_name.begins_with("attack - "):
			action = "attack"
		elif base_name == "imp death":
			action = "death"
		if action.is_empty():
			continue
		if not _atlas_sheets_by_path.has(sheet_path):
			_add_atlas_sheet(
				sheet_path, pack_path, pack_name, ATLAS_TILE_SIZE, "Спрайты LPC", false, false,
			)
		var equipment := "vanilla"
		if action != "death":
			equipment = base_name.trim_prefix(action + " - ").replace(" ", "_")
		var color_name := ""
		if pack_folder == "LPC Imp 2":
			color_name = sheet_path.get_base_dir().get_file().to_lower()
		var equipment_variants: Array[String] = [equipment]
		if action == "death" and pack_folder == "LPC Imp 2":
			equipment_variants = [
				"vanilla", "sword", "sword_shield", "pitchfork", "pitchfork_shield",
			]
		var frame_count := 7 if action == "death" else 4
		var direction_count := 1 if action == "death" else 4
		var direction_names := ["down", "left", "right", "up"]
		for variant in equipment_variants:
			var species_key := "%s%s_%s" % [
				(color_name + "_") if not color_name.is_empty() else "",
				"imp",
				variant,
			]
			var display_name := "Имп"
			if not color_name.is_empty():
				display_name += " · " + color_name.capitalize()
			if variant != "vanilla":
				display_name += " · " + variant.replace("_", " ").capitalize()
			var group := _get_or_create_lpc_mob_group(
				pack_path, pack_folder, species_key, display_name,
			)
			group["profile_kind"] = (
				"imp_%s" % variant
				if color_name.is_empty() or color_name == "red"
				else "imp_%s_%s" % [color_name, variant]
			)
			_animal_groups_by_key[str(group["key"])] = group
			for direction in range(direction_count):
				var clip := _make_lpc_grid_clip(
					sheet_path,
					Vector2i(0, direction * 4),
					Vector2i(4, 4),
					frame_count,
					120,
					direction_names[direction] if direction_count > 1 else "down",
				)
				if clip.is_empty():
					push_warning("Не удалось разобрать LPC-анимацию: " + sheet_path)
					break
				_add_lpc_mob_clip(group, action, clip)


func _build_lpc_goblin_groups(
	pack_path: String,
	pack_folder: String,
	png_paths: Array[String],
) -> void:
	var variant_pattern := RegEx.new()
	variant_pattern.compile("(?i)^goblin([1-3])$")
	var action_pattern := RegEx.new()
	action_pattern.compile(
		"(?i)^(idle|walk|run|attack|hurt|death|walk_attack|run_attack)\\d?$",
	)
	var direction_names := ["down", "up", "left", "right"]
	for sheet_path in png_paths:
		if not sheet_path.get_file().to_lower().ends_with("_with_shadow.png"):
			continue
		var variant_folder := sheet_path.get_base_dir().get_base_dir().get_file()
		var variant_match := variant_pattern.search(variant_folder)
		if variant_match == null:
			continue
		var base_name := sheet_path.get_file().get_basename().to_lower()
		base_name = base_name.trim_suffix("_with_shadow")
		var action_match := action_pattern.search(base_name)
		if action_match == null:
			continue
		var variant_number := variant_match.get_string(1)
		var species_key := "g" + variant_number
		var group := _get_or_create_lpc_mob_group(
			pack_path,
			pack_folder,
			species_key,
			"Гоблин " + variant_number,
		)
		var sheet: Dictionary = _atlas_sheets_by_path.get(sheet_path, {})
		var columns := int(sheet.get("columns", 0))
		var rows := int(sheet.get("rows", 0))
		if columns % 2 != 0 or rows < 8:
			push_warning("Не удалось разобрать LPC-анимацию гоблина: " + sheet_path)
			continue
		var frame_count := int(columns / 2)
		var state_name := action_match.get_string(1).to_lower()
		for direction_index in range(direction_names.size()):
			var clip := _make_lpc_grid_clip(
				sheet_path,
				Vector2i(0, direction_index * 2),
				Vector2i(2, 2),
				frame_count,
				120,
				direction_names[direction_index],
			)
			if clip.is_empty():
				push_warning("Не удалось разобрать LPC-анимацию гоблина: " + sheet_path)
				break
			_add_lpc_mob_clip(group, state_name, clip)


func _default_animal_state(state_names: Array[String]) -> String:
	for preferred in ["idle", "animation", "walk", "run"]:
		if preferred in state_names:
			return preferred
	return state_names[0] if not state_names.is_empty() else ""


func _extract_animal_clips(sheet: Dictionary, is_fish_pack: bool) -> Array[Dictionary]:
	var clips: Array[Dictionary] = []
	var animations: Dictionary = sheet.get("animations", {})
	var columns := int(sheet.get("columns", 0))
	var rows := int(sheet.get("rows", 0))
	if animations.is_empty() or columns <= 0 or rows <= 0:
		return clips
	var tile_ids: Array[int] = []
	for tile_id in animations:
		tile_ids.append(int(tile_id))
	tile_ids.sort()
	for tile_id in tile_ids:
		var frames: Array = animations[tile_id]
		if frames.is_empty():
			continue
		var frame_stride := _animal_frame_width(frames, columns)
		var frame_size := Vector2i(frame_stride, 1 if is_fish_pack else frame_stride)
		if not is_fish_pack:
			for frame in frames:
				var frame_id := int(frame.get("tile_id", -1))
				if frame_id >= 0:
					var frame_x := frame_id % columns
					frame_size.x = mini(frame_size.x, columns - frame_x)
		var origin := Vector2i(tile_id % columns, tile_id / columns)
		if origin.x + frame_size.x > columns or origin.y + frame_size.y > rows:
			continue
		if origin.x > 0 and _animal_animation_matches(animations, tile_id - 1, tile_id, 1):
			continue
		var first_animation_row := _animal_first_animation_row(animations, origin.x, columns)
		if posmod(origin.y - first_animation_row, frame_size.y) != 0:
			continue
		var valid_frames := true
		for frame in frames:
			var frame_id := int(frame.get("tile_id", -1))
			var frame_origin := Vector2i(frame_id % columns, frame_id / columns)
			if frame_id < 0 or frame_origin.x + frame_size.x > columns \
				or frame_origin.y + frame_size.y > rows:
				valid_frames = false
				break
		if not valid_frames:
			continue
		clips.append({
			"sheet_path": str(sheet.get("path", "")),
			"frame_ids": frames.duplicate(true),
			"frame_size": frame_size,
			"origin_tile_id": tile_id,
		})
	return clips


func _animal_first_animation_row(animations: Dictionary, column: int, columns: int) -> int:
	var first_row := 2147483647
	for tile_id in animations:
		if int(tile_id) % columns == column:
			first_row = mini(first_row, int(tile_id) / columns)
	return 0 if first_row == 2147483647 else first_row


func _animal_frame_width(frames: Array, columns: int) -> int:
	var previous_id := -1
	for frame in frames:
		var frame_id := int(frame.get("tile_id", -1))
		if previous_id >= 0:
			var step := frame_id - previous_id
			if step > 0 and step < columns:
				return mini(step, 8)
		previous_id = frame_id
	return 1


func _animal_animation_matches(
	animations: Dictionary,
	candidate_id: int,
	base_id: int,
	offset: int,
) -> bool:
	var candidate_frames: Array = animations.get(candidate_id, [])
	var base_frames: Array = animations.get(base_id, [])
	if candidate_frames.is_empty() or candidate_frames.size() != base_frames.size():
		return false
	for index in range(base_frames.size()):
		if int(candidate_frames[index].get("tile_id", -1)) + offset \
			!= int(base_frames[index].get("tile_id", -1)) \
			or int(candidate_frames[index].get("duration", 0)) \
			!= int(base_frames[index].get("duration", 0)):
			return false
	return true


func _animal_instance_key(pack_folder: String, species_key: String) -> String:
	return "%s%s|%s" % [ANIMAL_INSTANCE_PREFIX, pack_folder, species_key]


func _update_animal_palette_hover(delta: float) -> void:
	if _animal_palette == null or not _animal_palette.visible:
		_reset_animal_palette_hover()
		return
	var hover_index := -1
	if _animal_card_pinned_key.is_empty():
		hover_index = _animal_palette_item_at_position(
			_animal_palette.get_local_mouse_position(),
		)
	else:
		hover_index = _animal_palette_index_by_key(_animal_card_pinned_key)
	if hover_index < 0:
		_reset_animal_palette_hover()
		return
	if hover_index != _animal_hover_index:
		_begin_animal_palette_preview(hover_index)
	_advance_animal_palette_preview(delta)


func _animal_palette_index_by_key(group_key: String) -> int:
	for index in range(_animal_palette.item_count):
		if str(_animal_palette.get_item_metadata(index)) == group_key:
			return index
	return -1


func _animal_palette_item_at_position(position: Vector2) -> int:
	if _animal_palette == null \
		or not Rect2(Vector2.ZERO, _animal_palette.size).has_point(position):
		return -1
	return _animal_palette.get_item_at_position(position, true)


func _begin_animal_palette_preview(index: int) -> void:
	if _animal_hover_index >= 0 and _animal_hover_index < _animal_palette.item_count:
		var previous_key := str(_animal_palette.get_item_metadata(_animal_hover_index))
		var previous_group: Dictionary = _animal_groups_by_key.get(previous_key, {})
		_animal_palette.set_item_icon(_animal_hover_index, _animal_group_icon(previous_group))
	_animal_hover_index = index
	_animal_preview_clip_index = 0
	_animal_preview_frame_index = 0
	_animal_preview_elapsed = 0.0
	_animal_preview_step_elapsed = 0.0
	var group_key := str(_animal_palette.get_item_metadata(index))
	var group: Dictionary = _animal_groups_by_key.get(group_key, {})
	_animal_preview_clips = _animal_palette_preview_sequence(group)
	if str(group.get("kind", "animal")) == "mob":
		_show_animal_hover_card(group, group_key == _animal_card_pinned_key)
	else:
		_hide_animal_hover_card()
	if _animal_preview_clips.is_empty():
		return
	_set_animal_palette_preview_icon()


func _on_animal_palette_gui_input(event: InputEvent) -> void:
	var mouse_event := event as InputEventMouseButton
	if mouse_event == null or not mouse_event.pressed \
		or mouse_event.button_index != MOUSE_BUTTON_LEFT:
		return
	_pin_animal_hover_card(_animal_palette_item_at_position(mouse_event.position))


func _pin_animal_hover_card(index: int) -> void:
	if _animal_palette == null or index < 0 or index >= _animal_palette.item_count:
		return
	var group_key := str(_animal_palette.get_item_metadata(index))
	var group: Dictionary = _animal_groups_by_key.get(group_key, {})
	if str(group.get("kind", "animal")) != "mob":
		return
	_animal_card_pinned_key = group_key
	if _animal_hover_index == index:
		_show_animal_hover_card(group, true)
	else:
		_begin_animal_palette_preview(index)


func _on_animal_card_close_pressed() -> void:
	_reset_animal_palette_hover()


func _on_animal_card_settings_pressed() -> void:
	var group_key := _animal_card_pinned_key
	if group_key.is_empty():
		return
	_reset_animal_palette_hover()
	_load_mob_profile(group_key)


func _build_animal_hover_card(card_theme: Theme) -> void:
	_animal_card_panel_styles = {
		"hover": _animal_card_panel_style(ANIMAL_CARD_BORDER_COLOR, 1),
		"pinned": _animal_card_panel_style(ANIMAL_CARD_PINNED_COLOR, 2),
	}
	_animal_card_row_styles = {
		"supported": _animal_card_row_style(Color(0.14, 0.17, 0.21)),
		"missing": _animal_card_row_style(Color(0.095, 0.105, 0.13)),
		"current": _animal_card_row_style(Color(0.12, 0.5, 0.27)),
	}
	_animal_hover_card = PanelContainer.new()
	_animal_hover_card.visible = false
	_animal_hover_card.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_animal_hover_card.theme = card_theme
	_animal_hover_card.custom_minimum_size = ANIMAL_CARD_SIZE
	_animal_hover_card.add_theme_stylebox_override("panel", _animal_card_panel_styles["hover"])
	add_child(_animal_hover_card)

	var content := VBoxContainer.new()
	content.add_theme_constant_override("separation", 3)
	_animal_hover_card.add_child(content)
	_animal_card_title = _new_animal_card_label(ANIMAL_CARD_TITLE_COLOR)
	content.add_child(_animal_card_title)
	var mode_line := HBoxContainer.new()
	mode_line.add_theme_constant_override("separation", 6)
	content.add_child(mode_line)
	_animal_card_mode = _new_animal_card_label(ANIMAL_CARD_TEXT_COLOR)
	_animal_card_mode.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	mode_line.add_child(_animal_card_mode)
	_animal_card_hint = _new_animal_card_label(ANIMAL_CARD_DIM_COLOR)
	_animal_card_hint.custom_minimum_size.x = 80
	_animal_card_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	mode_line.add_child(_animal_card_hint)
	content.add_child(HSeparator.new())

	var body := HBoxContainer.new()
	body.add_theme_constant_override("separation", 8)
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	content.add_child(body)
	var actions_box := VBoxContainer.new()
	actions_box.add_theme_constant_override("separation", 2)
	body.add_child(actions_box)
	actions_box.add_child(_new_animal_card_label(ANIMAL_CARD_DIM_COLOR, "Действия"))
	var actions_grid := GridContainer.new()
	actions_grid.columns = 2
	actions_grid.add_theme_constant_override("h_separation", 3)
	actions_grid.add_theme_constant_override("v_separation", 2)
	actions_box.add_child(actions_grid)
	_animal_card_rows.clear()
	for action in ANIMAL_ACTION_ROWS:
		var row := PanelContainer.new()
		row.custom_minimum_size.x = ANIMAL_CARD_ROW_WIDTH
		row.mouse_filter = Control.MOUSE_FILTER_IGNORE
		row.add_theme_stylebox_override("panel", _animal_card_row_styles["missing"])
		var row_label := _new_animal_card_label(ANIMAL_CARD_DIM_COLOR)
		row.add_child(row_label)
		actions_grid.add_child(row)
		_animal_card_rows[str(action[0])] = {"panel": row, "label": row_label}

	var directions_box := VBoxContainer.new()
	directions_box.add_theme_constant_override("separation", 2)
	body.add_child(directions_box)
	var directions_title := _new_animal_card_label(ANIMAL_CARD_DIM_COLOR, "Направления")
	directions_title.custom_minimum_size.x = 66
	directions_box.add_child(directions_title)
	var directions_grid := GridContainer.new()
	directions_grid.columns = 3
	directions_grid.add_theme_constant_override("h_separation", 2)
	directions_grid.add_theme_constant_override("v_separation", 2)
	directions_grid.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	directions_box.add_child(directions_grid)
	_animal_card_directions.clear()
	var arrows := [
		["", ""], ["up", "↑"], ["", ""],
		["left", "←"], ["", "•"], ["right", "→"],
		["", ""], ["down", "↓"], ["", ""],
	]
	for arrow in arrows:
		var direction := str(arrow[0])
		var arrow_cell := PanelContainer.new()
		arrow_cell.custom_minimum_size = ANIMAL_CARD_ARROW_SIZE
		arrow_cell.mouse_filter = Control.MOUSE_FILTER_IGNORE
		directions_grid.add_child(arrow_cell)
		if str(arrow[1]).is_empty():
			arrow_cell.add_theme_stylebox_override("panel", StyleBoxEmpty.new())
			continue
		var arrow_label := _new_animal_card_label(ANIMAL_CARD_DIM_COLOR, str(arrow[1]))
		arrow_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		arrow_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		arrow_cell.add_child(arrow_label)
		if direction.is_empty():
			arrow_cell.add_theme_stylebox_override("panel", StyleBoxEmpty.new())
			arrow_label.add_theme_color_override("font_color", ANIMAL_CARD_TEXT_COLOR)
			continue
		arrow_cell.add_theme_stylebox_override("panel", _animal_card_row_styles["missing"])
		_animal_card_directions[direction] = {"panel": arrow_cell, "label": arrow_label}

	_animal_card_state = _new_animal_card_label(ANIMAL_CARD_TEXT_COLOR)
	content.add_child(_animal_card_state)
	var buttons := HBoxContainer.new()
	buttons.add_theme_constant_override("separation", 4)
	content.add_child(buttons)
	_animal_card_settings_button = Button.new()
	_animal_card_settings_button.text = "Настроить моба"
	_animal_card_settings_button.focus_mode = Control.FOCUS_NONE
	_animal_card_settings_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_animal_card_settings_button.pressed.connect(_on_animal_card_settings_pressed)
	buttons.add_child(_animal_card_settings_button)
	_animal_card_close_button = Button.new()
	_animal_card_close_button.text = "Закрыть"
	_animal_card_close_button.focus_mode = Control.FOCUS_NONE
	_animal_card_close_button.pressed.connect(_on_animal_card_close_pressed)
	buttons.add_child(_animal_card_close_button)


func _animal_card_panel_style(border_color: Color, border_width: int) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.07, 0.085, 0.11, 0.97)
	style.border_color = border_color
	style.set_border_width_all(border_width)
	style.set_corner_radius_all(3)
	style.content_margin_left = 6.0
	style.content_margin_right = 6.0
	style.content_margin_top = 5.0
	style.content_margin_bottom = 5.0
	style.shadow_color = Color(0.0, 0.0, 0.0, 0.5)
	style.shadow_size = 4
	return style


func _animal_card_row_style(background: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = background
	style.set_corner_radius_all(2)
	style.content_margin_left = 3.0
	style.content_margin_right = 3.0
	style.content_margin_top = 1.0
	style.content_margin_bottom = 1.0
	return style


func _new_animal_card_label(color: Color, text := "") -> Label:
	var label := Label.new()
	label.text = text
	label.clip_text = true
	label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.add_theme_color_override("font_color", color)
	return label


func _show_animal_hover_card(group: Dictionary, pinned: bool) -> void:
	var group_key := str(group.get("key", ""))
	if group_key.is_empty() or _animal_hover_card == null:
		return
	_animal_hover_card_key = group_key
	_animal_card_title.text = str(group.get("name", "Моб"))
	_animal_card_mode.text = "Режим: %s" % str(
		WorldModeRegistry.describe(_mode).get("name", _mode),
	)
	_animal_card_supported = _animal_group_actions(group)
	_set_animal_card_pinned(pinned)
	_refresh_animal_card_state()
	_animal_hover_card.visible = true
	_animal_hover_card.global_position = _animal_hover_card_position(
		_animal_palette.get_global_rect(),
		_animal_hover_card.get_combined_minimum_size(),
		_animal_card_viewport_size(),
	)
	_animal_hover_card.move_to_front()


func _hide_animal_hover_card() -> void:
	if _animal_hover_card != null:
		_animal_hover_card.visible = false
	_animal_hover_card_key = ""
	_animal_card_current_row = ""


func _animal_card_viewport_size() -> Vector2:
	if is_inside_tree():
		return get_viewport_rect().size
	return Vector2(1920, 1080)


func _set_animal_card_pinned(pinned: bool) -> void:
	_animal_hover_card.add_theme_stylebox_override(
		"panel",
		_animal_card_panel_styles["pinned" if pinned else "hover"],
	)
	_animal_hover_card.mouse_filter = (
		Control.MOUSE_FILTER_STOP if pinned else Control.MOUSE_FILTER_IGNORE
	)
	_animal_card_hint.text = "Закреплено" if pinned else "ЛКМ — закрепить"
	_animal_card_hint.add_theme_color_override(
		"font_color",
		ANIMAL_CARD_PINNED_COLOR if pinned else ANIMAL_CARD_DIM_COLOR,
	)
	_animal_card_settings_button.disabled = not pinned
	_animal_card_close_button.disabled = not pinned


func _refresh_animal_card_state() -> void:
	var state_name := ""
	var current_direction := ""
	if not _animal_preview_clips.is_empty():
		var current: Dictionary = _animal_preview_clips[_animal_preview_clip_index]
		state_name = str(current.get("state", ""))
		current_direction = str(current.get("direction", ""))
	_animal_card_current_row = _animal_state_action_row(state_name) \
		if not state_name.is_empty() else ""
	for action in ANIMAL_ACTION_ROWS:
		var row_id := str(action[0])
		var row: Dictionary = _animal_card_rows[row_id]
		var is_current := row_id == _animal_card_current_row
		var supported := bool(_animal_card_supported.get(row_id, false))
		var style_name := "current" if is_current else "supported" if supported else "missing"
		var mark := "▶" if is_current else "✓" if supported else "—"
		var row_label: Label = row["label"]
		row["panel"].add_theme_stylebox_override("panel", _animal_card_row_styles[style_name])
		row_label.text = "%s  %s" % [mark, action[1]]
		row_label.add_theme_color_override(
			"font_color",
			ANIMAL_CARD_CURRENT_TEXT_COLOR if is_current \
				else ANIMAL_CARD_TEXT_COLOR if supported else ANIMAL_CARD_DIM_COLOR,
		)
	var state_directions := {}
	for entry in _animal_preview_clips:
		if str(entry.get("state", "")) == state_name:
			state_directions[str(entry.get("direction", ""))] = true
	for direction in _animal_card_directions:
		var arrow: Dictionary = _animal_card_directions[direction]
		var is_current: bool = str(direction) == current_direction
		var available: bool = state_directions.has(direction)
		var style_name := "current" if is_current else "supported" if available else "missing"
		arrow["panel"].add_theme_stylebox_override("panel", _animal_card_row_styles[style_name])
		arrow["label"].add_theme_color_override(
			"font_color",
			ANIMAL_CARD_CURRENT_TEXT_COLOR if is_current \
				else ANIMAL_CARD_TEXT_COLOR if available else ANIMAL_CARD_DIM_COLOR,
		)
	if state_name.is_empty():
		_animal_card_state.text = "Анимаций для показа нет"
		return
	var action_title := _animal_state_title(state_name)
	if ANIMAL_DIRECTION_TITLES.has(current_direction):
		action_title += " · " + str(ANIMAL_DIRECTION_TITLES[current_direction])
	_animal_card_state.text = "Сейчас: %s (%d/%d)" % [
		action_title,
		_animal_preview_clip_index + 1,
		_animal_preview_clips.size(),
	]


func _animal_state_action_row(state_name: String) -> String:
	for action in ANIMAL_ACTION_ROWS:
		if str(action[0]) == state_name and state_name != ANIMAL_CARD_OTHER_ROW:
			return state_name
	return ANIMAL_CARD_OTHER_ROW


func _animal_state_title(state_name: String) -> String:
	var row_id := _animal_state_action_row(state_name)
	if row_id != ANIMAL_CARD_OTHER_ROW:
		for action in ANIMAL_ACTION_ROWS:
			if str(action[0]) == row_id:
				return str(action[1])
	if state_name == "animation":
		return "Анимация"
	if state_name == "flight":
		return "Полёт"
	if state_name.begins_with("animation_") and state_name.trim_prefix("animation_").is_valid_int():
		return "Анимация " + state_name.trim_prefix("animation_")
	return state_name


func _animal_hover_card_position(
	palette_rect: Rect2,
	card_size: Vector2,
	viewport_size: Vector2,
) -> Vector2:
	var card_position := (viewport_size - card_size) * 0.5
	card_position.x = maxf(card_position.x, palette_rect.end.x + ANIMAL_CARD_MARGIN)
	card_position.x = clampf(card_position.x, 0.0, maxf(0.0, viewport_size.x - card_size.x))
	card_position.y = clampf(card_position.y, 0.0, maxf(0.0, viewport_size.y - card_size.y))
	return card_position


func _animal_group_directions(group: Dictionary) -> Dictionary:
	var directions := {"up": false, "down": false, "left": false, "right": false}
	var states: Dictionary = group.get("states", {})
	for state in states.values():
		for entry in _animal_state_direction_clips(state):
			if directions.has(entry["direction"]):
				directions[entry["direction"]] = true
	return directions


# Возвращает по одному клипу на направление в порядке ANIMAL_DIRECTION_ORDER.
# Если направление определить нельзя, отдаёт один клип с пустым направлением.
func _animal_state_direction_clips(state: Dictionary) -> Array[Dictionary]:
	var playable: Array[Dictionary] = []
	var blocks_by_sheet := {}
	for clip in state.get("clips", []):
		if not clip is Dictionary or clip.get("frame_ids", []).is_empty():
			continue
		playable.append(clip)
		var block := _animal_clip_sheet_block(clip)
		if str(clip.get("direction", "")).is_empty() and block >= 0:
			var sheet_path := str(clip.get("sheet_path", ""))
			var blocks: Dictionary = blocks_by_sheet.get(sheet_path, {})
			blocks[block] = true
			blocks_by_sheet[sheet_path] = blocks
	var by_direction := {}
	for clip in playable:
		var direction := str(clip.get("direction", ""))
		if direction.is_empty():
			var block := _animal_clip_sheet_block(clip)
			var blocks: Dictionary = blocks_by_sheet.get(str(clip.get("sheet_path", "")), {})
			if block >= 0 and blocks.size() >= 2:
				direction = ANIMAL_SHEET_DIRECTION_BLOCKS[block]
		if ANIMAL_DIRECTION_ORDER.has(direction) and not by_direction.has(direction):
			by_direction[direction] = clip
	var result: Array[Dictionary] = []
	for direction in ANIMAL_DIRECTION_ORDER:
		if by_direction.has(direction):
			result.append({"direction": direction, "clip": by_direction[direction]})
	if result.is_empty() and not playable.is_empty():
		result.append({"direction": "", "clip": playable[0]})
	return result


# Листы 4-направленных наборов состоят из четырёх вертикальных блоков: вниз, вверх, влево, вправо.
func _animal_clip_sheet_block(clip: Dictionary) -> int:
	var sheet: Dictionary = _atlas_sheets_by_path.get(str(clip.get("sheet_path", "")), {})
	var columns := int(sheet.get("columns", 0))
	var rows := int(sheet.get("rows", 0))
	var frames: Array = clip.get("frame_ids", [])
	if columns <= 0 or rows < 4 or rows % 4 != 0 or frames.is_empty():
		return -1
	var tile_id := int(clip.get("origin_tile_id", frames[0].get("tile_id", -1)))
	if tile_id < 0:
		return -1
	return clampi(tile_id / columns * 4 / rows, 0, 3)


func _animal_group_actions(group: Dictionary) -> Dictionary:
	var result := {}
	for action in ANIMAL_ACTION_ROWS:
		result[str(action[0])] = false
	for entry in _animal_palette_preview_sequence(group):
		result[_animal_state_action_row(str(entry.get("state", "")))] = true
	return result


func _animal_state_order(state_name: String) -> int:
	var row_id := _animal_state_action_row(state_name)
	for index in range(ANIMAL_ACTION_ROWS.size()):
		if str(ANIMAL_ACTION_ROWS[index][0]) == row_id:
			return index
	return ANIMAL_ACTION_ROWS.size()


func _animal_palette_preview_sequence(group: Dictionary) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var states: Dictionary = group.get("states", {})
	var state_names: Array[String] = []
	for state_name in states:
		state_names.append(str(state_name))
	state_names.sort_custom(func(a: String, b: String) -> bool:
		var a_order := _animal_state_order(a)
		var b_order := _animal_state_order(b)
		if a_order != b_order:
			return a_order < b_order
		return a.naturalnocasecmp_to(b) < 0
	)
	for state_name in state_names:
		var state: Dictionary = states.get(state_name, {})
		if str(group.get("kind", "animal")) == "mob":
			for entry in _animal_state_direction_clips(state):
				result.append({
					"state": state_name,
					"clip": entry["clip"],
					"direction": entry["direction"],
				})
			continue
		for clip in state.get("clips", []):
			if not clip is Dictionary or clip.get("frame_ids", []).is_empty():
				continue
			result.append({"state": state_name, "clip": clip, "direction": ""})
			break
	return result


func _advance_animal_palette_preview(delta: float) -> void:
	if _animal_preview_clips.is_empty() or delta <= 0.0:
		return
	_animal_preview_elapsed += delta
	_animal_preview_step_elapsed += delta
	var frame_changed := false
	var step_changed := false
	var safety := 0
	while safety < 128:
		var current: Dictionary = _animal_preview_clips[_animal_preview_clip_index]
		var frames: Array = current.get("clip", {}).get("frame_ids", [])
		if frames.is_empty():
			break
		var duration := maxf(
			float(frames[_animal_preview_frame_index].get("duration", 100)) / 1000.0,
			0.05,
		)
		if _animal_preview_elapsed < duration:
			break
		_animal_preview_elapsed -= duration
		_animal_preview_frame_index += 1
		if _animal_preview_frame_index >= frames.size():
			_animal_preview_frame_index = 0
			# Шаг (действие в одном направлении) доигрывается целыми циклами минимум заданное время, чтобы подсветку можно было прочитать.
			if _animal_preview_step_elapsed >= ANIMAL_PREVIEW_MIN_STEP_SECONDS \
				and _animal_preview_clips.size() > 1:
				_animal_preview_clip_index = posmod(
					_animal_preview_clip_index + 1,
					_animal_preview_clips.size(),
				)
				_animal_preview_step_elapsed = _animal_preview_elapsed
				step_changed = true
		frame_changed = true
		safety += 1
	if step_changed and not _animal_hover_card_key.is_empty():
		_refresh_animal_card_state()
	if frame_changed:
		_set_animal_palette_preview_icon()


func _set_animal_palette_preview_icon() -> void:
	if _animal_hover_index < 0 or _animal_hover_index >= _animal_palette.item_count \
		or _animal_preview_clips.is_empty():
		return
	var entry: Dictionary = _animal_preview_clips[_animal_preview_clip_index]
	var preview_image := _animal_clip_preview_image(
		entry.get("clip", {}),
		_animal_preview_frame_index,
	)
	if preview_image != null:
		_animal_palette.set_item_icon(
			_animal_hover_index,
			ImageTexture.create_from_image(preview_image),
		)


func _animal_clip_preview_image(clip: Dictionary, frame_index: int) -> Image:
	var sheet_path := str(clip.get("sheet_path", ""))
	var sheet: Dictionary = _atlas_sheets_by_path.get(sheet_path, {})
	var texture := _ensure_atlas_sheet_texture(sheet_path)
	var frames: Array = clip.get("frame_ids", [])
	var columns := int(sheet.get("columns", 0))
	var tile_size := int(sheet.get("tile_size", ATLAS_TILE_SIZE))
	if texture == null or frames.is_empty() or columns <= 0:
		return null
	var frame: Dictionary = frames[clampi(frame_index, 0, frames.size() - 1)]
	var frame_id := int(frame.get("tile_id", -1))
	var frame_size: Vector2i = clip.get("frame_size", Vector2i.ONE)
	if frame_id < 0 or frame_size.x <= 0 or frame_size.y <= 0:
		return null
	var source := Rect2i(
		Vector2i(frame_id % columns, frame_id / columns) * tile_size,
		frame_size * tile_size,
	)
	if frame.has("source_rect"):
		source = frame["source_rect"]
	var image := texture.get_image()
	if image.is_empty() or not Rect2i(Vector2i.ZERO, image.get_size()).encloses(source):
		return null
	var frame_image := image.get_region(source)
	var scale := minf(
		float(ANIMAL_PALETTE_ICON_SIZE) / float(frame_image.get_width()),
		float(ANIMAL_PALETTE_ICON_SIZE) / float(frame_image.get_height()),
	)
	var fitted_size := Vector2i(
		maxi(1, roundi(float(frame_image.get_width()) * scale)),
		maxi(1, roundi(float(frame_image.get_height()) * scale)),
	)
	frame_image.resize(fitted_size.x, fitted_size.y, Image.INTERPOLATE_NEAREST)
	var preview := Image.create(
		ANIMAL_PALETTE_ICON_SIZE,
		ANIMAL_PALETTE_ICON_SIZE,
		false,
		Image.FORMAT_RGBA8,
	)
	preview.fill(Color(0, 0, 0, 0))
	var destination := Vector2i(
		(ANIMAL_PALETTE_ICON_SIZE - fitted_size.x) / 2,
		(ANIMAL_PALETTE_ICON_SIZE - fitted_size.y) / 2,
	)
	preview.blit_rect(frame_image, Rect2i(Vector2i.ZERO, fitted_size), destination)
	return preview


func _reset_animal_palette_hover() -> void:
	if _animal_palette != null and _animal_hover_index >= 0 \
		and _animal_hover_index < _animal_palette.item_count:
		var group_key := str(_animal_palette.get_item_metadata(_animal_hover_index))
		var group: Dictionary = _animal_groups_by_key.get(group_key, {})
		_animal_palette.set_item_icon(_animal_hover_index, _animal_group_icon(group))
	_animal_hover_index = -1
	_animal_preview_clips.clear()
	_animal_preview_clip_index = 0
	_animal_preview_frame_index = 0
	_animal_preview_elapsed = 0.0
	_animal_preview_step_elapsed = 0.0
	_animal_card_pinned_key = ""
	_hide_animal_hover_card()


func _show_animal_palette(pack_path: String) -> void:
	if _auto_brush_enabled:
		_set_auto_brush(false)
	_reset_animal_palette_hover()
	_animal_palette.clear()
	_animal_palette.visible = true
	_animal_palette.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var is_mob_pack := pack_path.begins_with(LPC_ROOT + "/")
	var is_hero_pack := pack_path.begins_with(HERO_ROOT + "/")
	if is_mob_pack:
		_animal_palette.custom_maximum_size.x = 320
	else:
		# -1 снимает ограничение ширины; 0 сжимал бы список до нуля пикселей.
		_animal_palette.custom_maximum_size = Vector2(-1, -1)
	_atlas_scroll.visible = false
	_palette.visible = false
	_annotation_controls.visible = false
	_publish_group_button.visible = false
	_selected_atlas_path = ""
	_selected_item_key = ""
	_active_custom_group_id = ""
	_selected_atlas_region = Rect2i()
	_publish_group_button.disabled = true
	var creature_count := 0
	for group in _animal_groups:
		if str(group.get("pack_path", "")) != pack_path:
			continue
		var states: Dictionary = group.get("states", {})
		var state_names: Array[String] = []
		for state_name in states:
			state_names.append(str(state_name))
		state_names.sort()
		var item_index := _animal_palette.add_item(
			str(group.get("name", "Животное")),
			_animal_group_icon(group),
		)
		_animal_palette.set_item_metadata(item_index, str(group.get("key", "")))
		if str(group.get("kind", "animal")) != "mob":
			_animal_palette.set_item_tooltip(
				item_index,
				"Целый спрайт · движения: %s" % ", ".join(state_names),
			)
		creature_count += 1
	_atlas_info.text = "Готовые спрайты · %d %s" % [
		creature_count, "мобов" if is_mob_pack else "героев" if is_hero_pack else "животных",
	]
	if creature_count == 0:
		_set_status("В этом наборе не найдены готовые спрайты.")
	else:
		_set_status("Выберите готовый спрайт: его анимации объединены в одном объекте.")


func _animal_group_icon(group: Dictionary) -> Texture2D:
	var states: Dictionary = group.get("states", {})
	var state_name := str(group.get("default_state", ""))
	var state: Dictionary = states.get(state_name, {})
	var clips: Array = state.get("clips", [])
	if clips.is_empty():
		return null
	var clip: Dictionary = clips[0]
	var icon := _animal_clip_preview_image(clip, 0)
	if icon == null:
		return null
	return ImageTexture.create_from_image(icon)


func _on_animal_item_selected(index: int) -> void:
	_activate_brush_for_palette_selection()
	_selected_item_key = str(_animal_palette.get_item_metadata(index))
	_selected_atlas_path = ""
	_active_custom_group_id = ""
	_selected_atlas_region = Rect2i()
	var group: Dictionary = _animal_groups_by_key.get(_selected_item_key, {})
	if group.is_empty():
		return
	var is_mob := str(group.get("kind", "animal")) == "mob"
	var target_layer_type := LAYER_MOB if is_mob else LAYER_ANIMAL
	var target_layer_name := "Мобы" if is_mob else "Животные"
	var creature_layer_found := false
	for layer in _layers:
		if str(layer.get("type", "")) == target_layer_type \
			and not bool(layer.get("locked", false)) and _is_layer_visible(layer):
			_active_layer_id = int(layer.get("id", 0))
			_render_layers()
			creature_layer_found = true
			break
	if not creature_layer_found:
		_set_status("Чтобы размещать существо, покажите и разблокируйте слой «%s»." % target_layer_name)
		return
	var states: Dictionary = group.get("states", {})
	var state_names: Array[String] = []
	for state_name in states:
		state_names.append(str(state_name))
	state_names.sort()
	if str(group.get("kind", "")) == "hero":
		_set_status(
			"Выбран герой «%s» (%s). ЛКМ размещает его на слое «Животные»."
			% [str(group.get("name", "Герой")), ", ".join(state_names)]
		)
		return
	_set_status(
		"Выбран целый спрайт «%s» (%s), радиус патруля: %d клеток (%s). ЛКМ размещает на слое «%s»."
		% [
			str(group.get("name", "Существо")),
			", ".join(state_names),
			_animal_brush_radius(_selected_item_key, _mode),
			_mode,
			target_layer_name,
		]
	)


func _on_animal_item_activated(index: int) -> void:
	_on_animal_item_selected(index)
	var animal_key := str(_animal_palette.get_item_metadata(index))
	var group: Dictionary = _animal_groups_by_key.get(animal_key, {})
	if group.is_empty():
		return
	if str(group.get("kind", "animal")) == "mob":
		_reset_animal_palette_hover()
		_load_mob_profile(animal_key)
		return
	var dialog := ConfirmationDialog.new()
	var creature_name := str(group.get("name", "Существо"))
	dialog.title = "Настройки существа: " + creature_name
	dialog.dialog_text = "Настройки режима: %s" % str(WorldModeRegistry.describe(_mode).get("name", _mode))
	var controls := VBoxContainer.new()
	var radius_control := _new_spinbox(
		1,
		maxi(int(_map_width.value), int(_map_height.value)),
		_animal_brush_radius(animal_key, _mode),
	)
	controls.add_child(_labeled_control("Радиус хаотичного патруля (клетки)", radius_control))
	dialog.add_child(controls)
	dialog.confirmed.connect(
		_confirm_animal_brush_settings.bind(animal_key, _mode, radius_control, dialog)
	)
	dialog.canceled.connect(dialog.queue_free)
	add_child(dialog)
	dialog.popup_centered()


func _load_mob_profile(mob_key: String) -> void:
	var group: Dictionary = _animal_groups_by_key.get(mob_key, {})
	if group.is_empty() or str(group.get("kind", "")) != "mob":
		_set_status("Не удалось открыть настройки: моб не найден.")
		return
	_pending_mob_profile_key = mob_key
	_pending_mob_profile_kind = str(group.get("profile_kind", mob_key))
	_pending_action = "mob_profile_load"
	_set_status("Загружаем настройки моба с сервера…")
	var path := "%s/map/mob-settings?mode=%s&kind=%s" % [
		_api_prefix,
		_mode.uri_encode(),
		_pending_mob_profile_kind.uri_encode(),
	]
	ApiClient.request_json(HTTPClient.METHOD_GET, path)


func _show_mob_profile(mob_key: String, settings: Dictionary, equipment_items: Variant = null) -> void:
	var group: Dictionary = _animal_groups_by_key.get(mob_key, {})
	if group.is_empty():
		_set_status("Моб больше не найден в палитре.")
		_clear_pending_mob_profile()
		return
	_close_mob_profile_dialog()
	var options := {"mode_name": str(WorldModeRegistry.describe(_mode).get("name", _mode))}
	if equipment_items is Array:
		options["equipment_items"] = equipment_items
	else:
		options["note"] = "Экипировка не загружена: сервер не отдал список предметов. ID предмета можно ввести вручную."
	if str(group.get("profile_kind", mob_key)) == mob_key:
		options["integration_note"] = "Профиль сохранится на сервере, но этот LPC-набор пока не подключён к игровому NPC-каталогу."
	var dialog: Control = MOB_PROFILE_DIALOG_SCRIPT.new()
	dialog.setup(str(group.get("name", "Моб")), _mode, settings, options)
	dialog.save_requested.connect(_save_mob_profile)
	dialog.cancel_requested.connect(_cancel_mob_profile)
	add_child(dialog)
	_mob_profile_dialog = dialog
	_set_status("Параметры моба «%s»: изменения применятся после сохранения." % str(group.get("name", "Моб")))


func _show_pending_mob_profile(equipment_items: Variant) -> void:
	_show_mob_profile(_pending_mob_profile_key, _pending_mob_profile_settings, equipment_items)


func _mob_equipment_path() -> String:
	var slots := PackedStringArray()
	for slot in MOB_PROFILE_RULES.EQUIPMENT_SLOTS:
		var item_slot: String = MOB_PROFILE_RULES.item_slot(slot)
		if not slots.has(item_slot):
			slots.append(item_slot)
	return "%s/items/equipment?slots=%s" % [_api_prefix, ",".join(slots)]


func _request_mob_equipment() -> void:
	_pending_action = "mob_equipment_items"
	_set_status("Загружаем список экипировки…")
	ApiClient.request_json(HTTPClient.METHOD_GET, _mob_equipment_path())


func _save_mob_profile(settings: Dictionary) -> void:
	if not is_instance_valid(_mob_profile_dialog) or _pending_mob_profile_key.is_empty():
		return
	_mob_profile_dialog.set_busy(true)
	_pending_action = "mob_profile_save"
	_set_status("Сохраняем профиль моба на сервере…")
	ApiClient.request_json(HTTPClient.METHOD_POST, _api_prefix + "/map/mob-settings", {
		"mode": _mode,
		"kind": _pending_mob_profile_kind,
		"settings": settings,
	})


func _cancel_mob_profile() -> void:
	_close_mob_profile_dialog()
	_clear_pending_mob_profile()
	_set_status("Изменения профиля моба отменены.")


func _close_mob_profile_dialog() -> void:
	if is_instance_valid(_mob_profile_dialog):
		_mob_profile_dialog.queue_free()
	_mob_profile_dialog = null


func _clear_pending_mob_profile() -> void:
	_pending_mob_profile_key = ""
	_pending_mob_profile_kind = ""
	_pending_mob_profile_settings = {}


func _open_item_form(item: Dictionary = {}) -> void:
	if _mode == "deck":
		_set_status("Создание экипировки доступно только в режимах с персонажами.")
		return
	if not _pending_action.is_empty():
		_set_status("Дождитесь завершения текущего запроса.")
		return
	if is_instance_valid(_item_form_dialog) or is_instance_valid(_mob_profile_dialog):
		return
	_editing_item_id = int(item.get("id", 0))
	if _editing_item_id > 0 and _editing_item_id < ITEM_FORM_RULES.CUSTOM_ITEM_FIRST_ID:
		_set_status("Встроенные предметы нельзя редактировать.")
		_editing_item_id = 0
		return
	var folder: String = ITEM_FORM_DIALOG_SCRIPT.default_icon_folder()
	var dialog: Control = ITEM_FORM_DIALOG_SCRIPT.new()
	var initial_form: Dictionary = ITEM_FORM_RULES.form_from_item(item) if _editing_item_id > 0 else {}
	dialog.setup(folder, ITEM_FORM_DIALOG_SCRIPT.scan_icon_keys(folder), initial_form, _editing_item_id)
	dialog.save_requested.connect(_on_item_form_save_requested)
	dialog.cancel_requested.connect(_close_item_form_dialog)
	add_child(dialog)
	_item_form_dialog = dialog


func _on_item_form_save_requested(form: Dictionary) -> void:
	if not is_instance_valid(_item_form_dialog):
		return
	var action := "edit_item" if _editing_item_id >= ITEM_FORM_RULES.CUSTOM_ITEM_FIRST_ID else "create_item"
	if _pending_action in ["create_item", "edit_item"]:
		return
	var known_icons: Array = _item_form_dialog.icon_keys()
	var current_icon: Variant = form.get("icon")
	if current_icon is String and ITEM_FORM_RULES.is_valid_icon_key(current_icon) and not known_icons.has(current_icon):
		known_icons.append(current_icon)
	var checked: Dictionary = ITEM_FORM_RULES.validate_form(form, known_icons)
	var error := str(checked["error"])
	if not error.is_empty():
		_item_form_dialog.set_message(error)
		return
	_pending_item_form = checked["clean"].duplicate(true)
	_pending_action = action
	_item_form_dialog.set_message("Сохраняем изменения предмета…" if action == "edit_item" else "Сохраняем предмет в инвентарь режима…")
	_request_item_save(action, _pending_item_form)


func _request_item_save(action: String, form: Dictionary) -> void:
	var method: HTTPClient.Method = HTTPClient.METHOD_POST
	var path := _api_prefix + "/items/catalog"
	if action == "edit_item":
		method = HTTPClient.METHOD_PUT
		path += "/%d" % _editing_item_id
	_pending_action = action
	ApiClient.request_json(method, path, {
		"mode": _mode,
		"form": form,
	})


func _request_item_catalog() -> void:
	_pending_action = "item_catalog"
	ApiClient.request_json(
		HTTPClient.METHOD_GET,
		_api_prefix + "/items/catalog?mode=" + _mode.uri_encode(),
	)


func _open_inventory() -> void:
	if _mode == "deck":
		return
	_ensure_inventory_dialog()
	_inventory_level = "slots"
	_inventory_selected_slot = ""
	_inventory_selected_category = ""
	_render_inventory_items()
	_inventory_dialog.popup_centered(Vector2i(640, 500))
	if _inventory_items.is_empty() and _pending_action.is_empty():
		_request_item_catalog()


func _ensure_inventory_dialog() -> void:
	if is_instance_valid(_inventory_dialog):
		return
	_inventory_dialog = ConfirmationDialog.new()
	_inventory_dialog.theme = _ui_root.theme
	_inventory_dialog.title = "Инвентарь · экипировка"
	_inventory_dialog.ok_button_text = "Закрыть"
	_inventory_dialog.cancel_button_text = "Закрыть"
	_inventory_dialog.custom_action.connect(_on_inventory_custom_action)
	_inventory_dialog.add_button("+ Создать предмет", false, "create_item")
	_inventory_back_button = _inventory_dialog.add_button("← Назад", false, "inventory_back")
	_inventory_back_button.visible = false
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size = Vector2(EDITOR_DIALOG_SIZE.x - 24, 390)
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_inventory_dialog.add_child(scroll)
	_inventory_list = VBoxContainer.new()
	_inventory_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_inventory_list.add_theme_constant_override("separation", roundi(6 * EDITOR_UI_SCALE))
	scroll.add_child(_inventory_list)
	add_child(_inventory_dialog)


func _on_inventory_custom_action(action: StringName) -> void:
	if action == "create_item":
		_open_item_form()
	elif action == "inventory_back":
		_inventory_go_back()


func _refresh_inventory_button() -> void:
	if is_instance_valid(_inventory_button):
		_inventory_button.text = "Инвентарь · %d" % _equipment_item_count()


func _equipment_item_count() -> int:
	var count := 0
	for item in _inventory_items:
		if str(item.get("item_type", "")) == "equipment":
			count += 1
	return count


func _render_inventory_items() -> void:
	if not is_instance_valid(_inventory_list):
		return
	for child in _inventory_list.get_children():
		_inventory_list.remove_child(child)
		child.queue_free()
	_inventory_back_button.visible = _inventory_level != "slots"
	match _inventory_level:
		"slots":
			_inventory_dialog.title = "Инвентарь · выберите слот"
			for slot in ITEM_FORM_RULES.EQUIPMENT_SLOTS:
				var count := _inventory_count_for_slot(str(slot))
				_add_inventory_navigation_button(
					"%s · %d" % [str(ITEM_FORM_RULES.SLOT_LABELS.get(str(slot), slot)), count],
					_select_inventory_slot.bind(str(slot)),
				)
			if _equipment_item_count() == 0:
				_add_inventory_empty_label("Экипировки пока нет. Создайте первый предмет.")
		"categories":
			_inventory_dialog.title = "%s · выберите тип" % str(ITEM_FORM_RULES.SLOT_LABELS.get(_inventory_selected_slot, "Слот"))
			var categories: Array = ITEM_FORM_RULES.item_categories(_inventory_items, _inventory_selected_slot)
			for category in categories:
				_add_inventory_navigation_button(
					"%s · %d" % [str(category), _inventory_count_for_category(str(category))],
					_select_inventory_category.bind(str(category)),
				)
			if categories.is_empty():
				_add_inventory_empty_label("В этом слоте пока нет предметов.")
		"items":
			_inventory_dialog.title = "%s · %s" % [
				str(ITEM_FORM_RULES.SLOT_LABELS.get(_inventory_selected_slot, "Слот")),
				_inventory_selected_category,
			]
			for item in _inventory_items:
				if str(item.get("item_type", "")) == "equipment" \
					and _inventory_item_slot(item) == _inventory_selected_slot \
					and ITEM_FORM_RULES.item_subcategory(item) == _inventory_selected_category:
					_add_inventory_item_row(item)
			if _inventory_list.get_child_count() == 0:
				_add_inventory_empty_label("В этой категории пока нет предметов.")


func _inventory_count_for_slot(slot: String) -> int:
	var count := 0
	for item in _inventory_items:
		if str(item.get("item_type", "")) == "equipment" and _inventory_item_slot(item) == slot:
			count += 1
	return count


func _inventory_item_slot(item: Dictionary) -> String:
	var slot := str(item.get("equip_slot", ""))
	return "ring" if slot == "ring_2" else slot


func _inventory_count_for_category(category: String) -> int:
	var count := 0
	for item in _inventory_items:
		if str(item.get("item_type", "")) == "equipment" \
			and _inventory_item_slot(item) == _inventory_selected_slot \
			and ITEM_FORM_RULES.item_subcategory(item) == category:
			count += 1
	return count


func _add_inventory_navigation_button(text: String, callback: Callable) -> void:
	var button := Button.new()
	button.text = text
	button.custom_minimum_size.y = roundi(38 * EDITOR_UI_SCALE)
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.pressed.connect(callback)
	_inventory_list.add_child(button)


func _add_inventory_empty_label(text: String) -> void:
	var empty_label := Label.new()
	empty_label.text = text
	_inventory_list.add_child(empty_label)


func _select_inventory_slot(slot: String) -> void:
	_inventory_selected_slot = slot
	_inventory_level = "categories"
	_render_inventory_items()


func _select_inventory_category(category: String) -> void:
	_inventory_selected_category = category
	_inventory_level = "items"
	_render_inventory_items()


func _inventory_go_back() -> void:
	if _inventory_level == "items":
		_inventory_level = "categories"
	elif _inventory_level == "categories":
		_inventory_level = "slots"
		_inventory_selected_slot = ""
		_inventory_selected_category = ""
	_render_inventory_items()


func _add_inventory_item_row(item: Dictionary) -> void:
	var row := HBoxContainer.new()
	row.custom_minimum_size.y = roundi(72 * EDITOR_UI_SCALE)
	row.add_theme_constant_override("separation", roundi(8 * EDITOR_UI_SCALE))
	_inventory_list.add_child(row)
	var icon_button := Button.new()
	icon_button.custom_minimum_size = Vector2(66, 62) * EDITOR_UI_SCALE
	icon_button.gui_input.connect(_on_inventory_item_icon_input.bind(int(item.get("id", 0))))
	row.add_child(icon_button)
	var icon := TextureRect.new()
	icon.custom_minimum_size = Vector2(66, 62) * EDITOR_UI_SCALE
	icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	var icon_key := str(item.get("icon", ""))
	var icon_path := "res://assets/item_icons/%s.png" % icon_key
	if not icon_key.is_empty() and ResourceLoader.exists(icon_path):
		icon.texture = load(icon_path)
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	icon_button.add_child(icon)
	var details := VBoxContainer.new()
	details.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(details)
	var title := Label.new()
	title.text = "%s · #%d" % [str(item.get("name", "Предмет")), int(item.get("id", 0))]
	title.clip_text = true
	title.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	details.add_child(title)
	var slot: String = str(ITEM_FORM_RULES.SLOT_LABELS.get(str(item.get("equip_slot", "")), "Слот не указан"))
	var info := Label.new()
	info.text = "%s · %s" % [str(slot), _inventory_item_summary(item)]
	info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	info.add_theme_font_size_override("font_size", roundi(12 * EDITOR_UI_SCALE))
	details.add_child(info)


func _on_inventory_item_icon_input(event: InputEvent, item_id: int) -> void:
	var mouse_event := event as InputEventMouseButton
	if mouse_event == null or not mouse_event.pressed or mouse_event.button_index != MOUSE_BUTTON_LEFT \
		or not mouse_event.double_click:
		return
	if item_id < ITEM_FORM_RULES.CUSTOM_ITEM_FIRST_ID:
		_set_status("Встроенные предметы доступны только для просмотра.")
		return
	for item in _inventory_items:
		if int(item.get("id", 0)) == item_id and str(item.get("item_type", "")) == "equipment":
			_open_item_form(item)
			return


func _replace_catalog_item(items: Array[Dictionary], updated_item: Dictionary) -> void:
	var item_id := int(updated_item.get("id", 0))
	for index in range(items.size()):
		if int(items[index].get("id", 0)) == item_id:
			items[index] = updated_item
			return
	items.append(updated_item)


func _inventory_item_summary(item: Dictionary) -> String:
	var parts: Array[String] = []
	var bonuses: Variant = item.get("bonuses", {})
	if bonuses is Dictionary:
		for stat in ITEM_FORM_RULES.STAT_LABELS:
			var amount := int(bonuses.get(stat, 0))
			if amount != 0:
				parts.append("%s +%d" % [str(ITEM_FORM_RULES.STAT_LABELS[stat]), amount])
	var effects: Variant = item.get("effects", {})
	if effects is Dictionary:
		for effect_key in ["crit", "crit_power", "anti_dodge", "anti_crit", "block"]:
			var amount := int(effects.get(effect_key, 0))
			if amount != 0:
				var effect_labels := {
					"crit": "Шанс крита",
					"crit_power": "Мощь крита",
					"anti_dodge": "Анти-уворот",
					"anti_crit": "Анти-крит",
					"block": "Блок",
				}
				parts.append("%s %+d%%" % [str(effect_labels[effect_key]), amount])
		for effect_key in [
			"windup_percent", "recovery_percent", "move_speed_percent", "attack_range", "attack_area",
			"lifesteal_percent",
		]:
			var amount := int(effects.get(effect_key, 0))
			if amount != 0:
				var labels := {
					"windup_percent": "Замах",
					"recovery_percent": "Скорость атаки",
					"move_speed_percent": "Скорость движения",
					"attack_range": "Дальность атаки",
					"attack_area": "Площадь атаки",
					"lifesteal_percent": "Вампиризм",
				}
				var suffix := " клеток" if effect_key in ["attack_range", "attack_area"] else "%"
				parts.append("%s %+d%s" % [str(labels[effect_key]), amount, suffix])
		var aura: Variant = effects.get("aura", {})
		if aura is Dictionary and str(aura.get("type", "")) == "vampirism":
			var target := "союзникам" if str(aura.get("target", "allies")) == "allies" else "врагам"
			parts.append(
				"Аура вампиризма: %s px, %d%% %s"
				% [int(aura.get("radius_px", 0)), int(aura.get("lifesteal_percent", 0)), target]
			)
	return ", ".join(parts) if not parts.is_empty() else "Без бонусов"


func _close_item_form_dialog() -> void:
	if is_instance_valid(_item_form_dialog):
		_item_form_dialog.queue_free()
	_item_form_dialog = null
	_editing_item_id = 0


func _confirm_animal_brush_settings(
	animal_key: String,
	mode: String,
	radius_control: SpinBox,
	dialog: ConfirmationDialog,
) -> void:
	if not _save_animal_brush_settings(animal_key, mode, int(radius_control.value)):
		return
	dialog.queue_free()
	_set_status(
		"Для существа задан радиус патруля %d клеток в режиме %s."
		% [int(radius_control.value), str(WorldModeRegistry.describe(mode).get("name", mode))]
	)


func _animal_brush_radius(animal_key: String, mode: String) -> int:
	var modes: Dictionary = _animal_brush_settings.get(animal_key, {})
	return int(modes.get(mode, 5))


func _load_animal_brush_settings(path: String = ANIMAL_SETTINGS_PATH) -> Error:
	_animal_brush_settings.clear()
	var config := ConfigFile.new()
	var error := config.load(path)
	if error == ERR_FILE_NOT_FOUND:
		return OK
	if error != OK:
		push_error("Не удалось загрузить настройки патруля существ: %s" % error_string(error))
		return error
	for mode in config.get_sections():
		for animal_key in config.get_section_keys(mode):
			var radius := int(config.get_value(mode, animal_key, 0))
			if radius <= 0:
				push_warning("Пропущен неверный радиус патруля для %s (%s)." % [animal_key, mode])
				continue
			var modes: Dictionary = _animal_brush_settings.get(animal_key, {})
			modes[mode] = radius
			_animal_brush_settings[animal_key] = modes
	return OK


func _save_animal_brush_settings(animal_key: String, mode: String, patrol_radius: int) -> bool:
	if not _animal_groups_by_key.has(animal_key) or mode.is_empty() \
		or patrol_radius < 1:
		_set_status("Не удалось сохранить настройки: существо или радиус указаны неверно.")
		return false
	var config := ConfigFile.new()
	var load_error := config.load(_animal_settings_config_path)
	if load_error != OK and load_error != ERR_FILE_NOT_FOUND:
		push_error("Не удалось открыть настройки патруля существ: %s" % error_string(load_error))
		_set_status("Не удалось прочитать файл настроек существ.")
		return false
	config.set_value(mode, animal_key, patrol_radius)
	var save_error := config.save(_animal_settings_config_path)
	if save_error != OK:
		push_error("Не удалось сохранить настройки патруля существ: %s" % error_string(save_error))
		_set_status("Не удалось сохранить настройки существа.")
		return false
	var modes: Dictionary = _animal_brush_settings.get(animal_key, {})
	modes[mode] = patrol_radius
	_animal_brush_settings[animal_key] = modes
	return true


func _animal_pack_display_name(folder_name: String) -> String:
	match folder_name:
		"craftpix-net-213727-top-down-cute-farm-animals-pixel-sprite":
			return "Домашние животные"
		"craftpix-net-291971-free-top-down-animals-farm-pixel-art-sprites":
			return "Фермерские животные"
		"craftpix-net-596440-fishing-and-gathering-pixel-art-rpg-icons":
			return "Рыбы и рыбалка"
		"craftpix-net-789196-free-top-down-hunt-animals-pixel-sprite-pack":
			return "Дикие животные"
		"village-farm-animals-sprite-sheet":
			return "Животные деревни"
	return folder_name.replace("-", " ").capitalize()


func _biome_display_name(folder_name: String) -> String:
	var name := folder_name.to_lower()
	if "flying-islands" in name:
		return "Летающие острова"
	if "grassland" in name:
		return "Луга"
	if "dungeon" in name or "cave" in name:
		return "Подземелья"
	if "rocky" in name:
		return "Скалы"
	match name:
		"cursed":
			return "Проклятый"
		"desert":
			return "Пустыня"
		"swamp":
			return "Болото"
		"undeadt":
			return "Нежить"
		"winter":
			return "Зима"
	return folder_name.replace("_", " ").capitalize()


func _select_biome(biome_path: String, selected_button: Button) -> void:
	_selected_biome_path = biome_path
	selected_button.button_pressed = true
	_catalog_tab.button_pressed = false
	for path in _biome_buttons:
		var button: Button = _biome_buttons[path]
		button.button_pressed = path == biome_path
	var first_sheet_path := ""
	for path in _sheet_buttons:
		var sheet: Dictionary = _atlas_sheets_by_path.get(path, {})
		var visible := str(sheet.get("biome_path", "")) == biome_path
		var button: Button = _sheet_buttons[path]
		button.visible = visible
		if visible and first_sheet_path.is_empty():
			first_sheet_path = str(path)
	_catalog_tab.visible = true
	if biome_path.begins_with(ANIMALS_ROOT + "/") \
		or biome_path.begins_with(LPC_ROOT + "/") \
		or biome_path.begins_with(HERO_ROOT + "/"):
		_show_animal_palette(biome_path)
		return
	_reset_animal_palette_hover()
	_animal_palette.visible = false
	_atlas_scroll.visible = true
	if not first_sheet_path.is_empty():
		_select_atlas_sheet(first_sheet_path, _sheet_buttons[first_sheet_path])


func _select_animated_pack(pack_path: String, animation_path: String, selected_button: Button) -> void:
	_selected_biome_path = animation_path
	selected_button.button_pressed = true
	_catalog_tab.button_pressed = false
	for path in _biome_buttons:
		var button: Button = _biome_buttons[path]
		button.button_pressed = path == animation_path
	for path in _sheet_buttons:
		var button: Button = _sheet_buttons[path]
		button.visible = false
		button.button_pressed = false
	_catalog_tab.visible = true
	_show_animal_palette(pack_path)


func _atlas_category(sheet_name: String) -> String:
	var name := sheet_name.to_lower()
	if "ground" in name or "snow" in name or "ice" in name or "moss" in name:
		return "Почва"
	if "cloud" in name:
		return "Облака"
	if "water" in name or "coast" in name or "fall" in name:
		return "Вода"
	if "bridge" in name:
		return "Мосты"
	if "object" in name or "tree" in name or "flower" in name or "statue" in name or "rock" in name:
		return "Объекты"
	if "shadow" in name or "detail" in name or "spot" in name or "crack" in name:
		return "Детали"
	return "Разное"


func _select_atlas_sheet(sheet_path: String, selected_tab: Button) -> void:
	_pending_corner_variant = ""
	_set_corner_assignment_button_pressed(false)
	selected_tab.button_pressed = true
	for path in _sheet_buttons:
		var button: Button = _sheet_buttons[path]
		button.button_pressed = path == sheet_path
	_catalog_tab.button_pressed = false
	var sheet: Dictionary = _atlas_sheets_by_path.get(sheet_path, {})
	if sheet.is_empty():
		return
	var texture := _ensure_atlas_sheet_texture(sheet_path)
	if texture == null:
		_set_status("Не удалось загрузить изображение выбранного листа.")
		return
	var atlas_tile_size := int(sheet.get("tile_size", ATLAS_TILE_SIZE))
	_auto_brush_button.disabled = atlas_tile_size != ATLAS_TILE_SIZE
	if atlas_tile_size != ATLAS_TILE_SIZE and _auto_brush_enabled:
		_set_auto_brush(false)
	_selected_item_key = ""
	_active_custom_group_id = ""
	_active_stamp_rows = 1
	_selected_atlas_region = Rect2i()
	_publish_group_button.disabled = true
	_selected_atlas_path = sheet_path
	_atlas_palette.set_atlas(texture, sheet["animations"], atlas_tile_size)
	_atlas_scroll.scroll_horizontal = 0
	_atlas_scroll.scroll_vertical = 0
	_atlas_scroll.visible = true
	_palette.visible = false
	_animal_palette.visible = false
	_annotation_controls.visible = _auto_brush_enabled
	_publish_group_button.visible = atlas_tile_size == ATLAS_TILE_SIZE
	_publish_group_button.disabled = atlas_tile_size != ATLAS_TILE_SIZE \
		or _selected_atlas_region.size.x != 3 \
		or _selected_atlas_region.size.y not in [3, 4, 5]
	_refresh_autotile_palette_labels(sheet_path)
	_atlas_info.text = "%s · %s · %d×%d · Ctrl+колесо меняет масштаб" % [
		str(sheet["name"]),
		str(sheet["category"]),
		atlas_tile_size,
		atlas_tile_size,
	]
	_annotation_controls.visible = _auto_brush_enabled and atlas_tile_size == ATLAS_TILE_SIZE
	_corner_assignment_status.visible = _auto_brush_enabled and atlas_tile_size == ATLAS_TILE_SIZE
	_update_corner_assignment_indicator()
	_set_status("Выбран лист %s (%s). Кадр можно рисовать на слое тайлов." % [str(sheet["name"]), str(sheet["category"])])


func _show_server_catalog(from_button := false) -> void:
	if from_button:
		_catalog_tab.button_pressed = true
	_pending_corner_variant = ""
	_set_corner_assignment_button_pressed(false)
	for path in _sheet_buttons:
		var button: Button = _sheet_buttons[path]
		button.button_pressed = false
	_selected_atlas_path = ""
	_selected_item_key = ""
	_active_custom_group_id = ""
	_selected_atlas_region = Rect2i()
	_publish_group_button.disabled = true
	_publish_group_button.visible = false
	_atlas_scroll.visible = false
	_animal_palette.visible = false
	_palette.visible = true
	_annotation_controls.visible = false
	_corner_assignment_status.visible = false
	_atlas_info.text = "Серверный каталог · элементы можно публиковать"


func _on_atlas_tile_selected(coords: Vector2i) -> void:
	if _selected_atlas_path.is_empty():
		return
	if not _pending_corner_variant.is_empty():
		var selected_stamp := _decode_atlas_cell(_selected_item_key)
		if selected_stamp.is_empty() or not _auto_brush_enabled:
			_pending_corner_variant = ""
			_set_status("Сначала выберите центр группы автокисти, затем задайте вариант угла.")
			return
		var center: Vector2i = selected_stamp["coords"]
		var assigned_variant := _pending_corner_variant
		_pending_corner_variant = ""
		_set_corner_assignment_button_pressed(false)
		if _save_atlas_corner_tile(_selected_atlas_path, center, assigned_variant, coords):
			_update_corner_assignment_indicator()
			var assigned_tiles := _autotile_rule_tiles(
				_corner_annotation_key(_selected_atlas_path, center, assigned_variant),
			)
			_set_status("Тайл (%d, %d) добавлен варианту «%s». Всего тайлов: %d." % [
				coords.x, coords.y, _corner_variant_title(assigned_variant), assigned_tiles.size(),
			])
		return
	_activate_brush_for_palette_selection()
	_selected_atlas_region = Rect2i()
	_publish_group_button.disabled = true
	_active_custom_group_id = ""
	_selected_atlas_coords = coords
	_selected_item_key = _encode_atlas_cell(_selected_atlas_path, coords)
	var sheet: Dictionary = _atlas_sheets_by_path.get(_selected_atlas_path, {})
	var atlas_tile_size := int(sheet.get("tile_size", ATLAS_TILE_SIZE))
	_publish_group_button.visible = atlas_tile_size == ATLAS_TILE_SIZE
	if _auto_brush_enabled:
		var rows := int(_annotation_height_select.get_item_metadata(_annotation_height_select.selected))
		if not _save_atlas_annotation(_selected_atlas_path, coords, rows):
			_selected_item_key = ""
			return
		_active_stamp_rows = rows
		_set_status("Шаблон 3×%d размечен с центром (%d, %d). При размещении его нижние ряды добавятся автоматически." % [
			rows, coords.x, coords.y,
		])
		_update_corner_assignment_indicator()
	else:
		_active_stamp_rows = 1
		_selected_atlas_region = Rect2i(coords, Vector2i.ONE)
		_set_status("Выбран %s (%d, %d)%s" % [
			str(sheet.get("name", "Лист")),
			coords.x,
			coords.y,
			" · для автокисти переключите режим и выберите центр",
		])


func _on_autotile_rows_selected(index: int) -> void:
	_active_stamp_rows = int(_annotation_height_select.get_item_metadata(index))
	if _auto_brush_enabled and not _selected_atlas_path.is_empty():
		_selected_item_key = ""
		_selected_atlas_region = Rect2i()
		_update_corner_assignment_indicator()
		_set_status("Автокисть 3×%d: теперь выберите центральный тайл на листе." % _active_stamp_rows)


func _set_auto_brush(enabled: bool) -> void:
	if not enabled:
		_pending_corner_variant = ""
		_set_corner_assignment_button_pressed(false)
	_active_tool = TOOL_BRUSH
	_auto_brush_enabled = enabled
	_brush_button.set_block_signals(true)
	_brush_button.button_pressed = not enabled
	_brush_button.set_block_signals(false)
	_auto_brush_button.set_block_signals(true)
	_auto_brush_button.button_pressed = enabled
	_auto_brush_button.set_block_signals(false)
	_annotation_controls.visible = enabled and not _selected_atlas_path.is_empty()
	_corner_assignment_status.visible = enabled and not _selected_atlas_path.is_empty()
	if enabled:
		_active_stamp_rows = int(_annotation_height_select.get_item_metadata(_annotation_height_select.selected))
		if not _selected_atlas_path.is_empty():
			_selected_item_key = ""
			_selected_atlas_region = Rect2i()
		_set_status("Автокисть 3×%d: выберите центральный тайл на листе; края подберутся по соседям." % _active_stamp_rows)
	else:
		_active_stamp_rows = 1
		_set_status("Обычная кисть: щёлкните тайл или выделите рамкой группу и наносите её на холст.")
	_update_corner_assignment_indicator()
	var sheet: Dictionary = _atlas_sheets_by_path.get(_selected_atlas_path, {})
	var atlas_tile_size := int(sheet.get("tile_size", ATLAS_TILE_SIZE))
	_publish_group_button.visible = not _selected_atlas_path.is_empty() and atlas_tile_size == ATLAS_TILE_SIZE
	_publish_group_button.disabled = int(sheet.get("tile_size", ATLAS_TILE_SIZE)) != ATLAS_TILE_SIZE \
		or _selected_atlas_path.is_empty() \
		or _selected_atlas_region.size.x != 3 \
		or _selected_atlas_region.size.y not in [3, 4, 5]


func _on_atlas_region_selected(region: Rect2i) -> void:
	_pending_corner_variant = ""
	if _selected_atlas_path.is_empty():
		return
	_selected_atlas_region = Rect2i()
	_publish_group_button.disabled = true
	var sheet: Dictionary = _atlas_sheets_by_path.get(_selected_atlas_path, {})
	if sheet.is_empty():
		return
	if region.size.x <= 0 or region.size.y <= 0 \
		or region.position.x < 0 or region.position.y < 0 \
		or region.end.x > int(sheet.get("columns", 0)) \
		or region.end.y > int(sheet.get("rows", 0)):
		_set_status("Выделение выходит за границы листа.")
		return
	if _auto_brush_enabled and (region.size.x != 3 or region.size.y not in [3, 4, 5]):
		_set_status("Для автокисти выделите формат 3×3, 3×4 или 3×5 либо щёлкните центральный тайл.")
		return
	_activate_brush_for_palette_selection()
	var center_offset := Vector2i(floori(float(region.size.x) / 2.0), floori(float(region.size.y) / 2.0))
	var center := region.position + center_offset
	var rows := region.size.y
	if _auto_brush_enabled:
		_annotation_height_select.set_block_signals(true)
		_annotation_height_select.select(rows - 3)
		_annotation_height_select.set_block_signals(false)
		if not _save_atlas_annotation(_selected_atlas_path, center, rows):
			return
	_selected_atlas_coords = center
	_selected_item_key = _encode_atlas_cell(_selected_atlas_path, center)
	if _auto_brush_enabled:
		var autotile_rows := int(_annotation_height_select.get_item_metadata(_annotation_height_select.selected))
		_active_stamp_rows = autotile_rows
		_selected_atlas_region = Rect2i()
		_atlas_info.text = "%s · центр автокисти 3×%d · (%d, %d)" % [
			str(sheet["name"]), autotile_rows, center.x, center.y,
		]
	else:
		_active_stamp_rows = rows
		_selected_atlas_region = region
		_atlas_info.text = "%s · штамп %d×%d · центр (%d, %d)" % [
			str(sheet["name"]), region.size.x, region.size.y, center.x, center.y,
		]
	_publish_group_button.visible = int(sheet.get("tile_size", ATLAS_TILE_SIZE)) == ATLAS_TILE_SIZE
	_publish_group_button.disabled = int(sheet.get("tile_size", ATLAS_TILE_SIZE)) != ATLAS_TILE_SIZE \
		or _selected_atlas_region.size.x != 3 \
		or _selected_atlas_region.size.y not in [3, 4, 5]
	_update_corner_assignment_indicator()
	_set_status("Выбор готов. ЛКМ наносит; ПКМ стирает клетки.")


func _activate_brush_for_palette_selection() -> void:
	if not _auto_brush_enabled and _active_tool != TOOL_BRUSH:
		_select_tool(TOOL_BRUSH)


func _corner_variant_title(variant_key: String) -> String:
	if variant_key.begins_with("mask_"):
		var mask_text := variant_key.trim_prefix("mask_")
		if mask_text.is_valid_int():
			return _autotile_mask_title(int(mask_text))
	for variant in AUTOTILE_CORNER_VARIANTS:
		if str(variant["key"]) == variant_key:
			return str(variant["title"])
	return variant_key


func _autotile_rule_marker(variant_key: String) -> String:
	if variant_key.begins_with("mask_"):
		return "M%s" % variant_key.trim_prefix("mask_")
	if variant_key.begins_with("inner_"):
		return "I%s" % variant_key.trim_prefix("inner_").to_upper()
	if variant_key.begins_with("diagonal_"):
		return "D%s" % variant_key.trim_prefix("diagonal_").to_upper()
	return variant_key


func _autotile_rule_directions(variant_key: String) -> String:
	if variant_key.begins_with("mask_"):
		var mask_text := variant_key.trim_prefix("mask_")
		if not mask_text.is_valid_int():
			return variant_key
		var mask := int(mask_text)
		var directions := ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
		var connected: Array[String] = []
		for index in range(directions.size()):
			if mask & (1 << index):
				connected.append(directions[index])
		return "Маска %03d · соседи: %s" % [
			mask, "—" if connected.is_empty() else ", ".join(connected),
		]
	return _corner_variant_title(variant_key)


func _refresh_autotile_palette_labels(sheet_path := "") -> void:
	if _atlas_palette == null:
		return
	var active_sheet := _selected_atlas_path if sheet_path.is_empty() else sheet_path
	var labels: Dictionary = {}
	for assignment_key in _atlas_corner_tiles:
		var parts := str(assignment_key).split("|")
		if parts.size() != 5 or parts[1] != active_sheet:
			continue
		var rule_tiles := _autotile_rule_tiles(assignment_key)
		for tile_index in range(rule_tiles.size()):
			var coords: Vector2i = rule_tiles[tile_index]
			var tile_key := "%d:%d" % [coords.x, coords.y]
			if not labels.has(tile_key):
				labels[tile_key] = {"markers": [], "details": []}
			var marker_data: Dictionary = labels[tile_key]
			var marker := _autotile_rule_marker(str(parts[4]))
			if rule_tiles.size() > 1:
				marker += "·"
			if not marker_data["markers"].has(marker):
				marker_data["markers"].append(marker)
			var details := "%s · группа %s,%s · вариант %d/%d" % [
				_autotile_rule_directions(str(parts[4])), parts[2], parts[3],
				tile_index + 1, rule_tiles.size(),
			]
			if not marker_data["details"].has(details):
				marker_data["details"].append(details)
	for tile_key in labels:
		var marker_data: Dictionary = labels[tile_key]
		marker_data["details"] = PackedStringArray(marker_data["details"])
	_atlas_palette.set_autotile_labels(labels)


func _autotile_mask_key(mask: int) -> String:
	return "mask_%03d" % mask


func _autotile_mask_title(mask: int) -> String:
	var north_west := "#" if mask & 128 else "."
	var north := "#" if mask & 1 else "."
	var north_east := "#" if mask & 2 else "."
	var west := "#" if mask & 64 else "."
	var east := "#" if mask & 4 else "."
	var south_west := "#" if mask & 32 else "."
	var south := "#" if mask & 16 else "."
	var south_east := "#" if mask & 8 else "."
	return "Маска %03d %s%s%s/%s@%s/%s%s%s" % [
		mask,
		north_west, north, north_east,
		west, east,
		south_west, south, south_east,
	]


func _selected_autotile_corner_variant() -> String:
	if _corner_variant_select == null or _corner_variant_select.item_count == 0:
		return ""
	return str(_corner_variant_select.get_item_metadata(_corner_variant_select.selected))


func _on_corner_variant_selected(_index: int) -> void:
	var selected_stamp := _decode_atlas_cell(_selected_item_key)
	var variant_key := _selected_autotile_corner_variant()
	if not _auto_brush_enabled or _selected_atlas_path.is_empty() or selected_stamp.is_empty():
		_update_corner_assignment_indicator()
		_set_status("Выберите центр группы автокисти. Затем включите «Назначить тайл» и щёлкните нужный тайл в палитре.")
		return
	var center: Vector2i = selected_stamp["coords"]
	var corner_key := _corner_annotation_key(_selected_atlas_path, center, variant_key)
	if _atlas_corner_tiles.has(corner_key):
		var tiles := _autotile_rule_tiles(corner_key)
		_set_status(
			"У правила «%s» уже %d тайлов. Чтобы добавить ещё один вариант, нажмите «Назначить тайл» и выберите его в палитре."
			% [_corner_variant_title(variant_key), tiles.size()],
		)
	else:
		_set_status("Для «%s» тайл не задан. Включите «Назначить тайл», затем выберите нужную клетку в палитре." % _corner_variant_title(variant_key))
	_update_corner_assignment_indicator()


func _set_corner_assignment_button_pressed(pressed: bool) -> void:
	if _corner_variant_assign_button == null:
		return
	_corner_variant_assign_button.set_block_signals(true)
	_corner_variant_assign_button.button_pressed = pressed
	_corner_variant_assign_button.set_block_signals(false)
	_corner_variant_assign_button.text = "Выберите в палитре" if pressed else "Назначить тайл"
	_corner_variant_select.disabled = pressed


func _on_corner_assignment_button_toggled(pressed: bool) -> void:
	if pressed:
		_begin_corner_tile_assignment()
	elif not _pending_corner_variant.is_empty():
		_pending_corner_variant = ""
		_set_status("Выбор тайла отменён.")
	_update_corner_assignment_indicator()


func _update_corner_assignment_indicator() -> void:
	if _corner_variant_select == null or _corner_assignment_status == null:
		return
	var selected_stamp := _decode_atlas_cell(_selected_item_key)
	var has_group := _auto_brush_enabled \
		and not _selected_atlas_path.is_empty() \
		and not selected_stamp.is_empty()
	var center := Vector2i.ZERO
	if has_group:
		center = selected_stamp["coords"]
	var selected_variant := _selected_autotile_corner_variant()
	for index in range(_corner_variant_select.item_count):
		var variant_key := str(_corner_variant_select.get_item_metadata(index))
		var item_text := _corner_variant_title(variant_key)
		if has_group:
			var assignment_key := _corner_annotation_key(_selected_atlas_path, center, variant_key)
			if _atlas_corner_tiles.has(assignment_key):
				item_text += " [%d тайлов]" % _autotile_rule_tiles(assignment_key).size()
		_corner_variant_select.set_item_text(index, item_text)
	if not _auto_brush_enabled or _selected_atlas_path.is_empty():
		_corner_assignment_status.text = "Выберите лист и включите автокисть."
	elif not has_group:
		_corner_assignment_status.text = "Сначала выберите центральный тайл автокисти."
	elif not _pending_corner_variant.is_empty():
		_corner_assignment_status.text = "Теперь щёлкните нужный тайл в палитре."
	else:
		var assignment_key := _corner_annotation_key(_selected_atlas_path, center, selected_variant)
		if _atlas_corner_tiles.has(assignment_key):
			var tiles := _autotile_rule_tiles(assignment_key)
			var tile_labels: Array[String] = []
			for coords in tiles:
				tile_labels.append("%d,%d" % [coords.x, coords.y])
			_corner_assignment_status.text = "Для «%s» тайлов: %d (%s)." % [
				_corner_variant_title(selected_variant), tiles.size(),
				", ".join(PackedStringArray(tile_labels)),
			]
		else:
			_corner_assignment_status.text = "Для «%s» тайл не назначен." % _corner_variant_title(selected_variant)


func _begin_corner_tile_assignment() -> void:
	var selected_stamp := _decode_atlas_cell(_selected_item_key)
	if not _auto_brush_enabled or _selected_atlas_path.is_empty() or selected_stamp.is_empty():
		_set_corner_assignment_button_pressed(false)
		_set_status("Выберите лист, включите автокисть и щёлкните центральный тайл группы; затем назначьте вариант угла.")
		return
	_pending_corner_variant = _selected_autotile_corner_variant()
	if _pending_corner_variant.is_empty():
		_set_corner_assignment_button_pressed(false)
		_set_status("Сначала выберите вариант угла.")
		return
	_set_corner_assignment_button_pressed(true)
	_set_status("Кнопка включена: щёлкните тайл в палитре, чтобы назначить его для «%s»." % _corner_variant_title(_pending_corner_variant))
	_update_corner_assignment_indicator()


func _clear_corner_tile_assignment() -> void:
	var selected_stamp := _decode_atlas_cell(_selected_item_key)
	var variant_key := _selected_autotile_corner_variant()
	if not _auto_brush_enabled or _selected_atlas_path.is_empty() or selected_stamp.is_empty():
		_set_status("Выберите центр группы автокисти, чтобы сбросить её настройку угла.")
		return
	var center: Vector2i = selected_stamp["coords"]
	if not _save_atlas_corner_tile(
		_selected_atlas_path, center, variant_key, Vector2i.ZERO, true,
	):
		return
	_update_corner_assignment_indicator()
	_set_status("Настройка «%s» сброшена; будет использован тайл по умолчанию." % _corner_variant_title(variant_key))


func _save_atlas_corner_tile(
	sheet_path: String,
	center: Vector2i,
	variant_key: String,
	coords: Vector2i,
	clear := false,
) -> bool:
	var sheet: Dictionary = _atlas_sheets_by_path.get(sheet_path, {})
	var valid_variant := false
	for variant in AUTOTILE_CORNER_VARIANTS:
		if str(variant["key"]) == variant_key:
			valid_variant = true
			break
	if variant_key.begins_with("mask_"):
		var mask_text := variant_key.trim_prefix("mask_")
		valid_variant = mask_text.is_valid_int() and int(mask_text) in range(256)
	if sheet.is_empty() or not valid_variant:
		_set_status("Не удалось определить лист или форму автокисти.")
		return false
	if not clear and (
		coords.x < 0 or coords.y < 0
		or coords.x >= int(sheet.get("columns", 0))
		or coords.y >= int(sheet.get("rows", 0))
	):
		_set_status("Выбранный тайл находится за границами листа.")
		return false
	var config := ConfigFile.new()
	var load_error := config.load(_annotation_config_path)
	if load_error != OK and load_error != ERR_FILE_NOT_FOUND:
		push_error("Не удалось открыть файл разметки углов автокисти: %s" % error_string(load_error))
		_set_status("Не удалось прочитать настройки углов автокисти.")
		return false
	var key := _corner_annotation_key(sheet_path, center, variant_key)
	if clear:
		if config.has_section_key("corner_tiles", key):
			config.erase_section_key("corner_tiles", key)
	else:
		var tiles := _autotile_rule_tiles(key)
		if not tiles.has(coords):
			tiles.append(coords)
		config.set_value("corner_tiles", key, _autotile_rule_value(tiles))
	var save_error := config.save(_annotation_config_path)
	if save_error != OK:
		push_error("Не удалось сохранить разметку угла автокисти: %s" % error_string(save_error))
		_set_status("Не удалось сохранить настройку угла.")
		return false
	if clear:
		_atlas_corner_tiles.erase(key)
	else:
		var tiles := _autotile_rule_tiles(key)
		if not tiles.has(coords):
			tiles.append(coords)
		_atlas_corner_tiles[key] = _autotile_rule_value(tiles)
	_refresh_autotile_palette_labels(sheet_path)
	return true


func _show_autotile_profile_save_dialog() -> void:
	if _autotile_profile_save_dialog == null:
		_autotile_profile_save_dialog = FileDialog.new()
		_autotile_profile_save_dialog.file_mode = FileDialog.FILE_MODE_SAVE_FILE
		_autotile_profile_save_dialog.access = FileDialog.ACCESS_FILESYSTEM
		_autotile_profile_save_dialog.title = "Сохранить профиль автокисти"
		_autotile_profile_save_dialog.filters = PackedStringArray(["*.json ; Профиль автокисти"])
		_autotile_profile_save_dialog.current_file = "autotile_palette.json"
		_autotile_profile_save_dialog.file_selected.connect(_save_autotile_profile)
		add_child(_autotile_profile_save_dialog)
	_autotile_profile_save_dialog.popup_centered_ratio(0.6)


func _show_autotile_profile_load_dialog() -> void:
	if _autotile_profile_load_dialog == null:
		_autotile_profile_load_dialog = FileDialog.new()
		_autotile_profile_load_dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
		_autotile_profile_load_dialog.access = FileDialog.ACCESS_FILESYSTEM
		_autotile_profile_load_dialog.title = "Загрузить профиль автокисти"
		_autotile_profile_load_dialog.filters = PackedStringArray(["*.json ; Профиль автокисти"])
		_autotile_profile_load_dialog.file_selected.connect(_load_autotile_profile)
		add_child(_autotile_profile_load_dialog)
	_autotile_profile_load_dialog.popup_centered_ratio(0.6)


func _save_autotile_profile(path: String) -> bool:
	var stamp := _decode_atlas_cell(_selected_item_key)
	if _selected_atlas_path.is_empty() or stamp.is_empty():
		_set_status("Чтобы сохранить профиль, выберите центральный тайл настроенной группы.")
		return false
	var center: Vector2i = stamp["coords"]
	var rows := int(_atlas_annotations.get(_annotation_key(_selected_atlas_path, center), 0))
	if rows not in [3, 4, 5]:
		rows = _active_stamp_rows if _active_stamp_rows in [3, 4, 5] else 3
	var rules: Array[Dictionary] = []
	for mask in range(256):
		var rule_key := _corner_annotation_key(
			_selected_atlas_path, center, _autotile_mask_key(mask),
		)
		if not _atlas_corner_tiles.has(rule_key):
			continue
		var rule_tiles := _autotile_rule_tiles_payload(_autotile_rule_tiles(rule_key))
		var rule_payload: Dictionary = {"mask": mask}
		if rule_tiles.size() == 1:
			rule_payload["tile"] = rule_tiles[0]
		else:
			rule_payload["tiles"] = rule_tiles
		rules.append(rule_payload)
	var named_rules: Array[Dictionary] = []
	for variant in AUTOTILE_CORNER_VARIANTS:
		var variant_key := str(variant["key"])
		var rule_key := _corner_annotation_key(_selected_atlas_path, center, variant_key)
		if not _atlas_corner_tiles.has(rule_key):
			continue
		var rule_tiles := _autotile_rule_tiles_payload(_autotile_rule_tiles(rule_key))
		var rule_payload: Dictionary = {"variant": variant_key}
		if rule_tiles.size() == 1:
			rule_payload["tile"] = rule_tiles[0]
		else:
			rule_payload["tiles"] = rule_tiles
		named_rules.append(rule_payload)
	var profile := {
		"source_sheet": _selected_atlas_path.trim_prefix("res://"),
		"center": [center.x, center.y],
		"rows": rows,
		"rules": rules,
		"named_rules": named_rules,
	}
	var document := {
		"format_version": AUTOTILE_PROFILE_FORMAT_VERSION,
		"profiles": [profile],
	}
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		push_error("Не удалось создать профиль автокисти: %s" % error_string(FileAccess.get_open_error()))
		_set_status("Не удалось сохранить профиль автокисти.")
		return false
	file.store_string(JSON.stringify(document, "\t") + "\n")
	file.close()
	_set_status("Профиль группы сохранён: %s" % path.get_file())
	return true


func _load_autotile_profile(path: String) -> bool:
	var stamp := _decode_atlas_cell(_selected_item_key)
	if _selected_atlas_path.is_empty() or stamp.is_empty():
		_set_status("Сначала выберите лист и центральный тайл группы, куда загрузить профиль.")
		return false
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		push_error("Не удалось открыть профиль автокисти: %s" % error_string(FileAccess.get_open_error()))
		_set_status("Не удалось прочитать файл профиля.")
		return false
	var contents := file.get_as_text()
	file.close()
	var parser := JSON.new()
	var parse_error := parser.parse(contents)
	if parse_error != OK:
		push_error("Ошибка JSON профиля автокисти, строка %d: %s" % [
			parser.get_error_line(),
			parser.get_error_message(),
		])
		_set_status("Файл профиля содержит ошибку JSON.")
		return false
	var document: Variant = parser.data
	if typeof(document) != TYPE_DICTIONARY \
		or int(document.get("format_version", 0)) != AUTOTILE_PROFILE_FORMAT_VERSION:
		_set_status("Формат профиля автокисти не поддерживается.")
		return false
	var profiles: Variant = document.get("profiles", [])
	if typeof(profiles) != TYPE_ARRAY or profiles.size() != 1 \
		or typeof(profiles[0]) != TYPE_DICTIONARY:
		_set_status("Профиль должен содержать ровно одну группу тайлов.")
		return false
	var profile: Dictionary = profiles[0]
	var source_sheet := str(profile.get("source_sheet", ""))
	if source_sheet.begins_with("res://"):
		source_sheet = source_sheet.trim_prefix("res://")
	if source_sheet != _selected_atlas_path.trim_prefix("res://"):
		_set_status("Профиль создан для другого листа атласа. Выберите соответствующий лист.")
		return false
	var center: Vector2i = stamp["coords"]
	var sheet: Dictionary = _atlas_sheets_by_path.get(_selected_atlas_path, {})
	if sheet.is_empty():
		_set_status("Не удалось найти выбранный лист атласа.")
		return false
	var rows := int(profile.get("rows", 0))
	if rows not in [3, 4, 5]:
		_set_status("В профиле указана неверная высота группы.")
		return false
	var rules: Variant = profile.get("rules", [])
	var named_rules: Variant = profile.get("named_rules", [])
	if typeof(rules) != TYPE_ARRAY or typeof(named_rules) != TYPE_ARRAY:
		_set_status("В профиле неверно записаны правила тайлов.")
		return false
	var imported_rules: Dictionary = {}
	for rule_variant in rules:
		if typeof(rule_variant) != TYPE_DICTIONARY:
			_set_status("В профиле найдено правило неверного формата.")
			return false
		var mask := int(rule_variant.get("mask", -1))
		if mask not in range(256):
			_set_status("В профиле найдено неверное правило маски соседей.")
			return false
		var rule_tiles := _autotile_rule_tiles_from_payload(rule_variant, sheet)
		if rule_tiles.is_empty():
			_set_status("Координата тайла в профиле выходит за границы листа.")
			return false
		var variant_key := _autotile_mask_key(mask)
		if imported_rules.has(variant_key):
			_set_status("В профиле повторяется маска соседей %d." % mask)
			return false
		imported_rules[variant_key] = _autotile_rule_value(rule_tiles)
	for named_rule_variant in named_rules:
		if typeof(named_rule_variant) != TYPE_DICTIONARY:
			_set_status("В профиле найдено именованное правило неверного формата.")
			return false
		var variant_key := str(named_rule_variant.get("variant", ""))
		var valid_variant := false
		for variant in AUTOTILE_CORNER_VARIANTS:
			if str(variant["key"]) == variant_key:
				valid_variant = true
				break
		var rule_tiles := _autotile_rule_tiles_from_payload(named_rule_variant, sheet)
		if not valid_variant or rule_tiles.is_empty():
			_set_status("В профиле найдено неизвестное именованное правило.")
			return false
		if imported_rules.has(variant_key):
			_set_status("В профиле найдено неверное или повторяющееся именованное правило.")
			return false
		imported_rules[variant_key] = _autotile_rule_value(rule_tiles)
	var config := ConfigFile.new()
	var load_error := config.load(_annotation_config_path)
	if load_error != OK and load_error != ERR_FILE_NOT_FOUND:
		push_error("Не удалось открыть настройки профиля автокисти: %s" % error_string(load_error))
		_set_status("Не удалось обновить настройки профиля.")
		return false
	var group_key := _annotation_key(_selected_atlas_path, center)
	config.set_value("stamps", group_key, rows)
	for config_key in config.get_section_keys("corner_tiles"):
		if str(config_key).begins_with(group_key + "|"):
			config.erase_section_key("corner_tiles", config_key)
	for variant_key in imported_rules:
		config.set_value(
			"corner_tiles",
			_corner_annotation_key(_selected_atlas_path, center, str(variant_key)),
			imported_rules[variant_key],
		)
	var save_error := config.save(_annotation_config_path)
	if save_error != OK:
		push_error("Не удалось сохранить импортированный профиль: %s" % error_string(save_error))
		_set_status("Не удалось сохранить загруженный профиль.")
		return false
	_atlas_annotations[group_key] = rows
	for atlas_key in _atlas_corner_tiles.keys():
		if str(atlas_key).begins_with(group_key + "|"):
			_atlas_corner_tiles.erase(atlas_key)
	for variant_key in imported_rules:
		_atlas_corner_tiles[
			_corner_annotation_key(_selected_atlas_path, center, str(variant_key))
		] = imported_rules[variant_key]
	_active_stamp_rows = rows
	if _annotation_height_select != null:
		_annotation_height_select.select(rows - 3)
	_refresh_autotile_palette_labels(_selected_atlas_path)
	_update_corner_assignment_indicator()
	_set_status("Профиль группы загружен: %d правил соседей и %d особых углов." % [
		rules.size(), named_rules.size(),
	])
	return true


func _atlas_coords_are_valid(sheet: Dictionary, coords: Vector2i) -> bool:
	return coords.x >= 0 and coords.y >= 0 \
		and coords.x < int(sheet.get("columns", 0)) \
		and coords.y < int(sheet.get("rows", 0))


func _autotile_generation_profiles() -> Array[Dictionary]:
	var profiles: Array[Dictionary] = []
	for annotation_key in _atlas_annotations:
		var decoded := _decode_atlas_cell(str(annotation_key))
		if decoded.is_empty():
			continue
		var sheet_path := str(decoded["path"])
		if sheet_path == GLADES_GRASS_SHEET:
			continue
		var sheet: Dictionary = _atlas_sheets_by_path.get(sheet_path, {})
		var biome_path := str(sheet.get("biome_path", ""))
		if sheet.is_empty() or not biome_path.begins_with(BIOME_ROOT):
			continue
		profiles.append({
			"sheet_path": sheet_path,
			"center": decoded["coords"],
			"rows": int(_atlas_annotations[annotation_key]),
			"biome_path": biome_path,
			"sheet_name": str(sheet.get("name", sheet_path.get_file())),
			"category": str(sheet.get("category", "")),
			"label": "%s · %s · центр %d,%d · 3×%d" % [
				str(sheet.get("biome_name", "Биом")),
				str(sheet.get("name", sheet_path.get_file())),
				decoded["coords"].x,
				decoded["coords"].y,
				int(_atlas_annotations[annotation_key]),
			],
		})
	var grass_sheet: Dictionary = _atlas_sheets_by_path.get(GLADES_GRASS_SHEET, {})
	if not grass_sheet.is_empty():
		var meadow_path := str(
			grass_sheet.get(
				"biome_path",
				GLADES_GRASS_SHEET.get_base_dir().get_base_dir(),
			),
		)
		profiles.append({
			"sheet_path": GLADES_GRASS_SHEET,
			"center": GLADES_GRASS_CENTER,
			"rows": 3,
			"biome_path": meadow_path,
			"sheet_name": str(grass_sheet.get("name", GLADES_GRASS_SHEET.get_file())),
			"category": "Почва",
			"artist_reference": true,
			"label": "%s · Луг по образцу Glades" % str(grass_sheet.get("biome_name", "Луг")),
		})
	profiles.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return str(a["label"]) < str(b["label"])
	)
	return profiles


func _load_glades_grass_artist_rules() -> Dictionary:
	return GLADES_GRASS_ARTIST_PROFILE.load_rules()


func _show_terrain_generation_dialog() -> void:
	_terrain_generation_biome_options.clear()
	for biome_path in _biome_buttons:
		if not str(biome_path).begins_with(BIOME_ROOT):
			continue
		var biome_button: Button = _biome_buttons[biome_path]
		var folder_name := str(biome_path).get_file().to_lower()
		if "dungeon" in folder_name or "cave" in folder_name \
			or "подземель" in str(biome_button.text).to_lower():
			continue
		_terrain_generation_biome_options.append({
			"path": str(biome_path),
			"name": biome_button.text,
		})
	_terrain_generation_biome_options.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return str(a["name"]) < str(b["name"])
	)
	if _terrain_generation_dialog == null:
		_terrain_generation_dialog = ConfirmationDialog.new()
		_terrain_generation_dialog.title = "Генерировать карту"
		_terrain_generation_dialog.theme = _ui_root.theme
		_terrain_generation_dialog.size = Vector2i(
			roundi(620 * EDITOR_UI_SCALE),
			roundi(570 * EDITOR_UI_SCALE),
		)
		_terrain_generation_dialog.get_ok_button().text = "Начать генерацию"
		_terrain_generation_dialog.confirmed.connect(
			_generate_terrain_from_dialog.bind(_terrain_generation_dialog),
		)
		_terrain_generation_dialog.canceled.connect(_terrain_generation_dialog.hide)
		var dialog_content := ScrollContainer.new()
		dialog_content.custom_minimum_size = Vector2(
			roundi(620 * EDITOR_UI_SCALE),
			roundi(500 * EDITOR_UI_SCALE),
		)
		dialog_content.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
		dialog_content.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
		dialog_content.theme = _ui_root.theme
		_terrain_generation_dialog.add_child(dialog_content)
		var content := VBoxContainer.new()
		content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		content.theme = _ui_root.theme
		content.add_theme_constant_override("separation", roundi(6 * EDITOR_UI_SCALE))
		dialog_content.add_child(content)
		var size_title := Label.new()
		size_title.text = "Размер карты"
		content.add_child(size_title)
		var size_row := HBoxContainer.new()
		content.add_child(size_row)
		_terrain_generation_width = _new_spinbox(16, 1600, int(_map_width.value))
		_terrain_generation_height = _new_spinbox(16, 1600, int(_map_height.value))
		size_row.add_child(_labeled_control("Ширина:", _terrain_generation_width))
		size_row.add_child(_labeled_control("Высота:", _terrain_generation_height))
		var biome_count_row := HBoxContainer.new()
		content.add_child(biome_count_row)
		_terrain_generation_biome_count_value = Label.new()
		_terrain_generation_biome_count_row(biome_count_row)
		var biome_help := Label.new()
		biome_help.text = "Для каждого пункта ниже можно выбрать биом или оставить «Рандом»."
		biome_help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		content.add_child(biome_help)
		var biome_scroll := ScrollContainer.new()
		biome_scroll.custom_minimum_size = Vector2(
			roundi(540 * EDITOR_UI_SCALE),
			roundi(190 * EDITOR_UI_SCALE),
		)
		biome_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
		content.add_child(biome_scroll)
		_terrain_generation_biome_rows = VBoxContainer.new()
		_terrain_generation_biome_rows.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		biome_scroll.add_child(_terrain_generation_biome_rows)
		for feature in [
			["water", "Воды на карте:"],
			["mountain", "Горы на карте:"],
			["forest", "Леса на карте:"],
		]:
			_add_terrain_generation_slider(content, str(feature[0]), str(feature[1]))
		add_child(_terrain_generation_dialog)
	_rebuild_terrain_generation_biome_rows()
	if is_inside_tree():
		_terrain_generation_dialog.popup_centered()


func _terrain_generation_biome_count_row(row: HBoxContainer) -> void:
	var label := Label.new()
	label.text = "Количество биомов:"
	row.add_child(label)
	_terrain_generation_biome_count_slider = HSlider.new()
	_terrain_generation_biome_count_slider.min_value = 0
	_terrain_generation_biome_count_slider.max_value = 6
	_terrain_generation_biome_count_slider.step = 1
	_terrain_generation_biome_count_slider.value = 1
	_terrain_generation_biome_count_slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_terrain_generation_biome_count_slider.value_changed.connect(_on_terrain_biome_count_changed)
	row.add_child(_terrain_generation_biome_count_slider)
	_terrain_generation_biome_count_value.text = "1"
	_terrain_generation_biome_count_value.custom_minimum_size.x = roundi(24 * EDITOR_UI_SCALE)
	row.add_child(_terrain_generation_biome_count_value)


func _add_terrain_generation_slider(parent: Control, key: String, caption: String) -> void:
	var row := HBoxContainer.new()
	parent.add_child(row)
	var label := Label.new()
	label.text = caption
	label.custom_minimum_size.x = roundi(130 * EDITOR_UI_SCALE)
	row.add_child(label)
	var slider := HSlider.new()
	slider.min_value = 0
	slider.max_value = 10
	slider.step = 1
	slider.value = 0
	slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var value_label := Label.new()
	value_label.text = "0"
	value_label.custom_minimum_size.x = roundi(24 * EDITOR_UI_SCALE)
	slider.value_changed.connect(_on_terrain_feature_value_changed.bind(key, value_label))
	row.add_child(slider)
	row.add_child(value_label)
	_terrain_generation_feature_sliders[key] = slider
	_terrain_generation_feature_values[key] = value_label


func _on_terrain_biome_count_changed(value: float) -> void:
	_terrain_generation_biome_count_value.text = str(int(value))
	_rebuild_terrain_generation_biome_rows()


func _on_terrain_feature_value_changed(value: float, key: String, value_label: Label) -> void:
	value_label.text = str(int(value))
	_terrain_generation_feature_values[key] = value_label


func _rebuild_terrain_generation_biome_rows() -> void:
	if _terrain_generation_biome_rows == null:
		return
	var previous_choices: Array[String] = []
	for row in _terrain_generation_biome_rows.get_children():
		var selector := (row as HBoxContainer).get_child(1) as OptionButton
		previous_choices.append(str(selector.get_item_metadata(selector.selected)))
	for child in _terrain_generation_biome_rows.get_children():
		_terrain_generation_biome_rows.remove_child(child)
		child.free()
	_terrain_generation_biome_count = int(_terrain_generation_biome_count_slider.value)
	for index in range(_terrain_generation_biome_count):
		var row := HBoxContainer.new()
		_terrain_generation_biome_rows.add_child(row)
		var label := Label.new()
		label.text = "Биом %d:" % (index + 1)
		label.custom_minimum_size.x = roundi(70 * EDITOR_UI_SCALE)
		row.add_child(label)
		var selector := OptionButton.new()
		selector.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		selector.add_item("Рандом")
		selector.set_item_metadata(0, "")
		for biome in _terrain_generation_biome_options:
			selector.add_item(str(biome["name"]))
			selector.set_item_metadata(selector.item_count - 1, str(biome["path"]))
		if index < previous_choices.size():
			var previous_choice := previous_choices[index]
			for option_index in range(selector.item_count):
				if str(selector.get_item_metadata(option_index)) == previous_choice:
					selector.select(option_index)
					break
		row.add_child(selector)


func _generate_terrain_from_dialog(dialog: ConfirmationDialog) -> void:
	var biome_choices: Array[String] = []
	for child in _terrain_generation_biome_rows.get_children():
		var row := child as HBoxContainer
		var selector := row.get_child(1) as OptionButton
		biome_choices.append(str(selector.get_item_metadata(selector.selected)))
	var settings := {
		"map_w": int(_terrain_generation_width.value),
		"map_h": int(_terrain_generation_height.value),
		"biome_count": _terrain_generation_biome_count,
		"biomes": biome_choices,
		"water": int((_terrain_generation_feature_sliders["water"] as HSlider).value),
		"mountain": int((_terrain_generation_feature_sliders["mountain"] as HSlider).value),
		"forest": int((_terrain_generation_feature_sliders["forest"] as HSlider).value),
	}
	if int(settings["biome_count"]) == 0 \
		and int(settings["water"]) == 0 \
		and int(settings["mountain"]) == 0 \
		and int(settings["forest"]) == 0:
		_reject_terrain_generation(
			dialog,
			"Выберите хотя бы один биом или установите интенсивность воды, гор либо леса.",
		)
		return

	var all_profiles := _autotile_generation_profiles()
	var ground_profiles: Array[Dictionary] = []
	for profile in all_profiles:
		if _terrain_profile_matches(str(profile.get("category", "")), str(profile.get("sheet_name", "")), "ground"):
			ground_profiles.append(profile)
	var artist_reference_biomes: Dictionary = {}
	for profile in ground_profiles:
		if bool(profile.get("artist_reference", false)):
			artist_reference_biomes[str(profile.get("biome_path", ""))] = true
	var preferred_ground_profiles: Array[Dictionary] = []
	for profile in ground_profiles:
		var biome_path := str(profile.get("biome_path", ""))
		if artist_reference_biomes.has(biome_path) \
			and not bool(profile.get("artist_reference", false)):
			continue
		preferred_ground_profiles.append(profile)
	ground_profiles = preferred_ground_profiles
	var rng := RandomNumberGenerator.new()
	rng.randomize()
	var selected_biomes: Array[Dictionary] = []
	var random_biome_profiles := ground_profiles.duplicate()
	for index in range(biome_choices.size()):
		var requested_path := biome_choices[index]
		var candidates: Array[Dictionary] = []
		if requested_path.is_empty():
			candidates = random_biome_profiles
		else:
			for profile in ground_profiles:
				if str(profile.get("biome_path", "")) == requested_path:
					candidates.append(profile)
		if candidates.is_empty():
			var biome_name := requested_path.get_file() if not requested_path.is_empty() else "доступный случайный биом"
			_reject_terrain_generation(
				dialog,
				(
					"Для биома «%s» нет настроенной группы автокисти почвы. "
					+ "Выберите для неё центр группы 3×3/3×5 в атласе и повторите генерацию."
				) % biome_name,
			)
			return
		var selected_index := rng.randi_range(0, candidates.size() - 1)
		var profile: Dictionary = candidates[selected_index].duplicate(true)
		selected_biomes.append(profile)
		if requested_path.is_empty():
			random_biome_profiles.erase(candidates[selected_index])
	var needs_glades_grass_rules := false
	for profile in selected_biomes:
		if bool(profile.get("artist_reference", false)):
			needs_glades_grass_rules = true
			break
	var glades_grass_rules: Dictionary = {}
	if needs_glades_grass_rules:
		var artist_data := _load_glades_grass_artist_rules()
		if artist_data.is_empty():
			_reject_terrain_generation(
				dialog,
				"Не удалось прочитать правила травы из образца Glades.tmx.",
			)
			return
		glades_grass_rules = artist_data["rules"]
	for index in range(selected_biomes.size()):
		if bool(selected_biomes[index].get("artist_reference", false)):
			selected_biomes[index]["artist_rules"] = glades_grass_rules

	var selected_biome_paths: Array[String] = []
	for profile in selected_biomes:
		var path := str(profile.get("biome_path", ""))
		if not path.is_empty() and not selected_biome_paths.has(path):
			selected_biome_paths.append(path)
	var feature_definitions := [
		["water", "Вода", "water", int(settings["water"])],
		["mountain", "Горы", "mountain", int(settings["mountain"])],
		["forest", "Лес", "forest", int(settings["forest"])],
	]
	var selected_features: Array[Dictionary] = []
	for definition in feature_definitions:
		var intensity := int(definition[3])
		if intensity <= 0:
			continue
		var feature_type := str(definition[2])
		var preferred: Array[Dictionary] = []
		var fallback: Array[Dictionary] = []
		for profile in all_profiles:
			if not _terrain_profile_matches(
				str(profile.get("category", "")),
				str(profile.get("sheet_name", "")),
				feature_type,
			):
				continue
			fallback.append(profile)
			if selected_biome_paths.has(str(profile.get("biome_path", ""))):
				preferred.append(profile)
		var candidates := preferred if not preferred.is_empty() else fallback
		if candidates.is_empty():
			_reject_terrain_generation(
				dialog,
				(
					"Для генерации «%s» нет настроенной группы автокисти. "
					+ "Назначьте автокисть на подходящем атласе и повторите генерацию."
				) % str(definition[1]),
			)
			return
		var profile: Dictionary = candidates[rng.randi_range(0, candidates.size() - 1)].duplicate(true)
		profile["feature"] = feature_type
		profile["feature_name"] = str(definition[1])
		profile["intensity"] = intensity
		selected_features.append(profile)

	_map_width.value = int(settings["map_w"])
	_map_height.value = int(settings["map_h"])
	_last_terrain_generation_settings = settings
	_generate_terrain_layers(selected_biomes, selected_features, rng.randi())
	dialog.hide()
	_set_status(
		"Карта сгенерирована: %d×%d, биомов %d, вода %d, горы %d, лес %d."
		% [
			_last_terrain_generation_settings["map_w"],
			_last_terrain_generation_settings["map_h"],
			_last_terrain_generation_settings["biome_count"],
			_last_terrain_generation_settings["water"],
			_last_terrain_generation_settings["mountain"],
			_last_terrain_generation_settings["forest"],
		],
	)


func _reject_terrain_generation(dialog: ConfirmationDialog, message: String) -> void:
	_set_status(message)
	if dialog.is_inside_tree():
		dialog.call_deferred("popup_centered")


func _terrain_profile_matches(category: String, sheet_name: String, feature: String) -> bool:
	var category_lower := category.to_lower()
	var name_lower := sheet_name.to_lower()
	match feature:
		"ground":
			return category_lower == "почва" \
				or "ground" in name_lower or "grass" in name_lower \
				or "snow" in name_lower or "ice" in name_lower or "moss" in name_lower
		"water":
			return category_lower == "вода" \
				or "water" in name_lower or "coast" in name_lower \
				or "river" in name_lower or "lake" in name_lower or "sea" in name_lower
		"mountain":
			return category_lower == "горы" \
				or "mountain" in name_lower or "rock" in name_lower \
				or "cliff" in name_lower or "stone" in name_lower
		"forest":
			return category_lower == "лес" \
				or "forest" in name_lower or "tree" in name_lower \
				or "bush" in name_lower or "wood" in name_lower
	return false


func _generate_terrain_layers(
	biome_profiles: Array[Dictionary],
	feature_profiles: Array[Dictionary],
	seed_value: int,
) -> void:
	var width := int(_map_width.value)
	var height := int(_map_height.value)
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	var biome_seeds: Array[Vector2i] = []
	for _index in range(biome_profiles.size()):
		var seed_cell := Vector2i(rng.randi_range(0, width - 1), rng.randi_range(0, height - 1))
		var attempts := 0
		while seed_cell in biome_seeds and attempts < 50:
			seed_cell = Vector2i(rng.randi_range(0, width - 1), rng.randi_range(0, height - 1))
			attempts += 1
		biome_seeds.append(seed_cell)
	var biome_warp_x := FastNoiseLite.new()
	biome_warp_x.seed = seed_value + 701
	biome_warp_x.frequency = 0.035
	biome_warp_x.fractal_octaves = 2
	var biome_warp_y := FastNoiseLite.new()
	biome_warp_y.seed = seed_value + 809
	biome_warp_y.frequency = 0.035
	biome_warp_y.fractal_octaves = 2
	var biome_warp_strength := float(mini(width, height)) * 0.12
	var biome_layer := _new_layer("Авто · Биомы", LAYER_TILE, 0)
	var biome_cells: Dictionary = biome_layer["cells"]
	var first_cells: Array[Vector2i] = []
	for _profile in biome_profiles:
		first_cells.append(Vector2i(-1, -1))
	if not biome_profiles.is_empty():
		for y in range(height):
			for x in range(width):
				var cell := Vector2i(x, y)
				var nearest_index := _terrain_biome_index(
					cell, biome_seeds, biome_warp_x, biome_warp_y, biome_warp_strength,
				)
				var profile: Dictionary = biome_profiles[nearest_index]
				var cell_key := _cell_key(x, y)
				biome_cells[cell_key] = _encode_autotile_cell(
					str(profile["sheet_path"]), profile["center"], profile["center"],
				)
				if first_cells[nearest_index].x < 0:
					first_cells[nearest_index] = cell
		for index in range(biome_profiles.size()):
			if first_cells[index].x >= 0:
				var profile: Dictionary = biome_profiles[index]
				_refresh_autotile_group(
					biome_layer, str(profile["sheet_path"]), profile["center"],
					int(profile["rows"]), first_cells[index],
					profile.get("artist_rules", {}),
				)
	var generated_layers: Array[Dictionary] = []
	if not biome_cells.is_empty():
		generated_layers.append(biome_layer)
	var noise_settings := {
		"forest": [0.055, 0.12, 101],
		"mountain": [0.045, 0.28, 211],
		"elevation": [0.075, 0.42, 307],
		"water": [0.04, 0.48, 401],
		"river": [0.0, 0.0, 503],
		"road": [0.0, 0.0, 607],
	}
	for profile in feature_profiles:
		var feature_key := str(profile["feature"])
		var feature_settings: Array = noise_settings[feature_key]
		var feature_cells: Dictionary
		if feature_key in ["river", "road"]:
			feature_cells = _terrain_route_cells(
				profile, width, height, seed_value + int(feature_settings[2]), feature_key,
			)
		else:
			var noise := FastNoiseLite.new()
			noise.seed = seed_value + int(feature_settings[2])
			noise.frequency = float(feature_settings[0])
			noise.fractal_octaves = 3
			feature_cells = {}
			var threshold := float(feature_settings[1])
			if profile.has("intensity"):
				threshold = 0.72 - float(profile["intensity"]) * 0.12
			for y in range(height):
				for x in range(width):
					if noise.get_noise_2d(x, y) < threshold:
						continue
					var cell_key := _cell_key(x, y)
					feature_cells[cell_key] = _encode_autotile_cell(
						str(profile["sheet_path"]), profile["center"], profile["center"],
					)
		if feature_cells.is_empty():
			continue
		var feature_layer := _new_layer(
			"Авто · %s" % str(profile["feature_name"]), LAYER_TILE, 0,
		)
		feature_layer["cells"] = feature_cells
		for component_seed in _terrain_cell_component_seeds(feature_cells):
			_refresh_autotile_group(
				feature_layer, str(profile["sheet_path"]), profile["center"],
				int(profile["rows"]), component_seed,
			)
		generated_layers.append(feature_layer)
	_push_layers_undo()
	for index in range(_layers.size() - 1, -1, -1):
		if str(_layers[index].get("name", "")).begins_with("Авто · "):
			_layers.remove_at(index)
	var insert_index := _layers.size()
	for index in range(_layers.size()):
		if not _is_tile_layer(_layers[index]):
			insert_index = index
			break
	for index in range(generated_layers.size()):
		_layers.insert(insert_index + index, generated_layers[index])
	if not generated_layers.is_empty():
		_active_layer_id = int(generated_layers[0]["id"])
	_minimap_dirty = true
	_render_layers()
	_canvas.queue_redraw()
	_refresh_history_buttons()
	_set_status(
		"Ландшафт сгенерирован. Биомов: %d; дополнительных областей: %d; зерно: %d. Ctrl+Z отменяет всю генерацию."
		% [biome_profiles.size(), generated_layers.size() - 1, seed_value],
	)


func _terrain_biome_index(
	cell: Vector2i,
	biome_seeds: Array[Vector2i],
	warp_x: FastNoiseLite,
	warp_y: FastNoiseLite,
	warp_strength: float,
) -> int:
	if biome_seeds.is_empty():
		return -1
	var sample := Vector2(cell)
	sample.x += warp_x.get_noise_2d(cell.x, cell.y) * warp_strength
	sample.y += warp_y.get_noise_2d(cell.x, cell.y) * warp_strength
	var nearest_index := 0
	var nearest_distance := INF
	for index in range(biome_seeds.size()):
		var distance := Vector2(biome_seeds[index]).distance_squared_to(sample)
		if distance < nearest_distance:
			nearest_distance = distance
			nearest_index = index
	return nearest_index


func _terrain_route_cells(
	profile: Dictionary,
	width: int,
	height: int,
	seed_value: int,
	route_type: String,
) -> Dictionary:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	var routes := 1 if route_type == "river" else 2
	var cells: Dictionary = {}
	for _route_index in range(routes):
		var horizontal := rng.randf() < 0.5
		var current := rng.randi_range(1, height - 2) if horizontal else rng.randi_range(1, width - 2)
		var previous := current
		var extent := width if horizontal else height
		for position in range(extent):
			previous = current
			if position > 1 and position < extent - 2 and rng.randf() < 0.32:
				current = clampi(current + rng.randi_range(-1, 1), 0, (height - 1) if horizontal else (width - 1))
			var coordinates: Array[Vector2i] = []
			if horizontal:
				coordinates.append(Vector2i(position, previous))
				coordinates.append(Vector2i(position, current))
			else:
				coordinates.append(Vector2i(previous, position))
				coordinates.append(Vector2i(current, position))
			for cell in coordinates:
				cells[_cell_key(cell.x, cell.y)] = _encode_autotile_cell(
					str(profile["sheet_path"]), profile["center"], profile["center"],
				)
	return cells


func _terrain_cell_component_seeds(cells: Dictionary) -> Array[Vector2i]:
	var unvisited: Dictionary = {}
	for cell_key in cells:
		var parts := str(cell_key).split(":")
		if parts.size() == 2:
			unvisited[Vector2i(int(parts[0]), int(parts[1]))] = true
	var seeds: Array[Vector2i] = []
	while not unvisited.is_empty():
		var start: Vector2i = unvisited.keys()[0]
		seeds.append(start)
		unvisited.erase(start)
		var pending: Array[Vector2i] = [start]
		while not pending.is_empty():
			var current: Vector2i = pending.pop_back()
			for offset in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
				var neighbor: Vector2i = current + Vector2i(offset)
				if not unvisited.has(neighbor):
					continue
				unvisited.erase(neighbor)
				pending.append(neighbor)
	return seeds


func _show_publish_group_dialog() -> void:
	if _selected_atlas_path.is_empty() or _selected_atlas_region.size.x != 3 \
		or _selected_atlas_region.size.y not in [3, 4, 5]:
		_set_status("Сначала выделите в палитре группу размером 3×3, 3×4 или 3×5.")
		return
	var dialog := ConfirmationDialog.new()
	dialog.title = "Опубликовать группу тайлов"
	dialog.dialog_text = "Группа станет доступна в общей серверной палитре."
	_publish_group_name = LineEdit.new()
	_publish_group_name.text = str(_atlas_sheets_by_path.get(_selected_atlas_path, {}).get("name", "Новая группа"))
	_publish_group_name.placeholder_text = "Название группы"
	dialog.add_child(_publish_group_name)
	_publish_group_category = OptionButton.new()
	var categories := [
		["Трава", "grass"],
		["Горы", "mountain"],
		["Вода", "water"],
		["Дорога", "road"],
		["Лес", "forest"],
	]
	for category in categories:
		_publish_group_category.add_item(category[0])
		_publish_group_category.set_item_metadata(_publish_group_category.item_count - 1, category[1])
	_publish_group_category.select(0)
	dialog.add_child(_publish_group_category)
	dialog.confirmed.connect(_publish_atlas_group.bind(dialog))
	dialog.canceled.connect(dialog.queue_free)
	add_child(dialog)
	dialog.popup_centered()


func _publish_atlas_group(dialog: ConfirmationDialog) -> void:
	var group_name := _publish_group_name.text.strip_edges()
	if group_name.is_empty() or group_name.length() > 48:
		_set_status("Название группы должно содержать от 1 до 48 символов.")
		return
	var sheet: Dictionary = _atlas_sheets_by_path.get(_selected_atlas_path, {})
	var texture: Texture2D = sheet.get("texture")
	if texture == null:
		_set_status("Не удалось прочитать изображение выбранного листа.")
		return
	var source_image := texture.get_image()
	if source_image.is_empty():
		_set_status("Изображение выбранного листа пустое.")
		return
	var tiles: Array[Dictionary] = []
	var tile_size := int(sheet.get("tile_size", ATLAS_TILE_SIZE))
	for tile_y in range(_selected_atlas_region.size.y):
		for tile_x in range(3):
			var source_position := _selected_atlas_region.position + Vector2i(tile_x, tile_y)
			var tile_image := source_image.get_region(Rect2i(source_position * tile_size, Vector2i.ONE * tile_size))
			var png := tile_image.save_png_to_buffer()
			if png.is_empty():
				_set_status("Не удалось подготовить PNG тайла (%d, %d)." % [tile_x, tile_y])
				return
			tiles.append({
				"x": tile_x,
				"y": tile_y,
				"png": Marshalls.raw_to_base64(png),
			})
	var payload := {
		"name": group_name,
		"category": str(_publish_group_category.get_item_metadata(_publish_group_category.selected)),
		"tile_rows": _selected_atlas_region.size.y,
		"tiles": tiles,
	}
	_pending_upload_source = {
		"sheet_path": _selected_atlas_path,
		"center": _selected_atlas_region.position + Vector2i(1, 1),
		"rows": _selected_atlas_region.size.y,
	}
	dialog.queue_free()
	_pending_action = "publish_tile_group"
	_set_status("Загружаем группу 3×%d в общий каталог…" % _selected_atlas_region.size.y)
	ApiClient.request_json(HTTPClient.METHOD_POST, _api_prefix + "/map/tile-groups", payload)


func _replace_uploaded_local_group_cells(
	group_id: String,
	sheet_path: String,
	group_center: Vector2i,
	group_rows: int,
	uploaded_group: Dictionary,
) -> int:
	if str(uploaded_group.get("group_id", "")) != group_id:
		return 0
	var group: Dictionary = _custom_tile_groups.get(group_id, {})
	if group.is_empty() or int(group.get("tile_rows", 0)) != group_rows:
		return 0
	var tile_keys: Array = group["tile_keys"]
	var replaced := 0
	for layer in _layers:
		var cells: Dictionary = layer.get("cells", {})
		for cell_key in cells:
			var decoded := _decode_atlas_cell(str(cells[cell_key]))
			if not _same_autotile_group(decoded, sheet_path, group_center):
				continue
			var source_coords: Vector2i = decoded["coords"]
			var tile_x := source_coords.x - group_center.x + 1
			var tile_y := source_coords.y - group_center.y + 1
			if tile_x < 0 or tile_x >= 3 or tile_y < 0 or tile_y >= group_rows:
				continue
			cells[cell_key] = tile_keys[tile_y][tile_x]
			replaced += 1
		layer["cells"] = cells
	return replaced


func _annotation_key(sheet_path: String, center: Vector2i) -> String:
	return _encode_atlas_cell(sheet_path, center)


func _corner_annotation_key(sheet_path: String, center: Vector2i, variant_key: String) -> String:
	return "%s|%s" % [_annotation_key(sheet_path, center), variant_key]


func _autotile_rule_tiles(rule_key: String) -> Array[Vector2i]:
	var result: Array[Vector2i] = []
	var stored: Variant = _atlas_corner_tiles.get(rule_key)
	if typeof(stored) == TYPE_VECTOR2I:
		result.append(stored)
	elif typeof(stored) == TYPE_ARRAY:
		for tile in stored:
			if typeof(tile) == TYPE_VECTOR2I and not result.has(tile):
				result.append(tile)
	return result


func _autotile_rule_value(tiles: Array[Vector2i]) -> Variant:
	if tiles.size() == 1:
		return tiles[0]
	return tiles.duplicate()


func _autotile_rule_tiles_payload(tiles: Array[Vector2i]) -> Array:
	var payload: Array = []
	for coords in tiles:
		payload.append([coords.x, coords.y])
	return payload


func _autotile_rule_tiles_from_payload(rule: Dictionary, sheet: Dictionary) -> Array[Vector2i]:
	var result: Array[Vector2i] = []
	var values: Variant = rule.get("tiles", [])
	if typeof(values) == TYPE_ARRAY:
		for tile_variant in values:
			if typeof(tile_variant) != TYPE_ARRAY or tile_variant.size() != 2:
				return []
			var coords := Vector2i(int(tile_variant[0]), int(tile_variant[1]))
			if not _atlas_coords_are_valid(sheet, coords) or result.has(coords):
				return []
			result.append(coords)
	if result.is_empty() and rule.has("tile"):
		var legacy_tile: Variant = rule["tile"]
		if typeof(legacy_tile) != TYPE_ARRAY or legacy_tile.size() != 2:
			return []
		var coords := Vector2i(int(legacy_tile[0]), int(legacy_tile[1]))
		if not _atlas_coords_are_valid(sheet, coords):
			return []
		result.append(coords)
	return result


func _load_atlas_annotations(path: String = ATLAS_ANNOTATIONS_PATH) -> Error:
	_atlas_annotations.clear()
	_atlas_corner_tiles.clear()
	var config := ConfigFile.new()
	var error := config.load(path)
	if error == ERR_FILE_NOT_FOUND:
		return OK
	if error != OK:
		push_error("Не удалось загрузить разметку атласных тайлов: %s" % error_string(error))
		return error
	if config.has_section("stamps"):
		for key in config.get_section_keys("stamps"):
			var rows := int(config.get_value("stamps", key, 0))
			if rows in [3, 4, 5]:
				_atlas_annotations[key] = rows
			else:
				push_warning("Пропущена неверная высота шаблона атласного тайла: %s" % key)
	if config.has_section("corner_tiles"):
		for key in config.get_section_keys("corner_tiles"):
			var stored: Variant = config.get_value("corner_tiles", key)
			var valid_tiles: Array[Vector2i] = []
			if typeof(stored) == TYPE_VECTOR2I:
				if stored.x >= 0 and stored.y >= 0:
					valid_tiles.append(stored)
			elif typeof(stored) == TYPE_ARRAY:
				for tile in stored:
					if typeof(tile) != TYPE_VECTOR2I or tile.x < 0 or tile.y < 0 \
						or valid_tiles.has(tile):
						valid_tiles.clear()
						break
					valid_tiles.append(tile)
			if valid_tiles.is_empty():
				push_warning("Пропущена неверная координата угла автокисти: %s" % key)
				continue
			var valid_variant := false
			for variant in AUTOTILE_CORNER_VARIANTS:
				if key.ends_with("|" + str(variant["key"])):
					valid_variant = true
					break
			if key.contains("|mask_"):
				var key_parts := key.split("|")
				var variant_key := str(key_parts[key_parts.size() - 1])
				var mask_text := variant_key.trim_prefix("mask_")
				valid_variant = mask_text.is_valid_int() and int(mask_text) in range(256)
			if valid_variant:
				_atlas_corner_tiles[key] = _autotile_rule_value(valid_tiles)
			else:
				push_warning("Пропущена неизвестная форма автокисти: %s" % key)
	return OK


func _save_atlas_annotation(sheet_path: String, center: Vector2i, rows: int, path: String = "") -> bool:
	var sheet: Dictionary = _atlas_sheets_by_path.get(sheet_path, {})
	if sheet.is_empty() or rows not in [3, 4, 5]:
		_set_status("Выберите лист и высоту 3×3, 3×4 или 3×5.")
		return false
	var origin := center - Vector2i(1, 1)
	var columns := int(sheet.get("columns", 0))
	var atlas_rows := int(sheet.get("rows", 0))
	if origin.x < 0 or origin.x + 3 > columns or origin.y < 0 or origin.y + rows > atlas_rows:
		_set_status("Шаблон 3×%d выходит за границы листа. Нужен центр во второй колонке и достаточно рядов ниже." % rows)
		return false
	var config := ConfigFile.new()
	var target_path := _annotation_config_path if path.is_empty() else path
	var load_error := config.load(target_path)
	if load_error != OK and load_error != ERR_FILE_NOT_FOUND:
		push_error("Не удалось открыть файл разметки атласных тайлов: %s" % error_string(load_error))
		_set_status("Не удалось прочитать файл разметки атласных тайлов.")
		return false
	var key := _annotation_key(sheet_path, center)
	config.set_value("stamps", key, rows)
	var save_error := config.save(target_path)
	if save_error != OK:
		push_error("Не удалось сохранить разметку атласного тайла: %s" % error_string(save_error))
		_set_status("Не удалось сохранить разметку шаблона.")
		return false
	_atlas_annotations[key] = rows
	return true


func _encode_atlas_cell(sheet_path: String, coords: Vector2i) -> String:
	return "%s%s|%d|%d" % [ATLAS_CELL_PREFIX, sheet_path, coords.x, coords.y]


func _decode_atlas_cell(key: String) -> Dictionary:
	if not key.begins_with(ATLAS_CELL_PREFIX):
		return {}
	var parts := key.trim_prefix(ATLAS_CELL_PREFIX).split("|")
	if parts.size() not in [3, 5, 6]:
		return {}
	var decoded := {
		"path": parts[0],
		"coords": Vector2i(int(parts[1]), int(parts[2])),
	}
	if parts.size() == 5:
		decoded["group_center"] = Vector2i(int(parts[3]), int(parts[4]))
	elif parts.size() == 6:
		decoded["group_center"] = Vector2i(int(parts[3]), int(parts[4]))
		decoded["autotile_role"] = parts[5]
	return decoded


func _encode_autotile_cell(
	sheet_path: String,
	coords: Vector2i,
	group_center: Vector2i,
	is_extension := false,
) -> String:
	return "%s%s|%d|%d|%d|%d|%s" % [
		ATLAS_CELL_PREFIX, sheet_path, coords.x, coords.y,
		group_center.x, group_center.y, "extension" if is_extension else "core",
	]


func _current_atlas_animation_frame(sheet: Dictionary, coords: Vector2i) -> Vector2i:
	var columns := int(sheet.get("columns", 0))
	if columns <= 0:
		return coords
	var tile_id := coords.y * columns + coords.x
	var animations: Dictionary = sheet.get("animations", {})
	var frames: Array = animations.get(tile_id, [])
	if frames.is_empty():
		return coords
	var cycle_duration := 0.0
	for frame in frames:
		cycle_duration += maxf(float(frame.get("duration", 100)), 1.0) / 1000.0
	if cycle_duration <= 0.0:
		return coords
	var frame_time := fmod(float(Time.get_ticks_msec()) / 1000.0, cycle_duration)
	for frame in frames:
		frame_time -= maxf(float(frame.get("duration", 100)), 1.0) / 1000.0
		if frame_time < 0.0:
			var frame_id := int(frame.get("tile_id", tile_id))
			return Vector2i(frame_id % columns, frame_id / columns)
	return coords


func _read_sheet_animations(sheet_path: String) -> Dictionary:
	var animations := {}
	var directory := DirAccess.open(sheet_path.get_base_dir())
	if directory == null:
		push_warning("Не удалось открыть каталог метаданных листа: " + sheet_path.get_base_dir())
		return animations
	for file_name in directory.get_files():
		if file_name.begins_with("._"):
			continue
		var extension := file_name.get_extension().to_lower()
		if extension not in ["tmx", "tsx"]:
			continue
		_read_animation_metadata(sheet_path.get_base_dir().path_join(file_name), sheet_path.get_file(), animations)
	return animations


func _read_animation_metadata(metadata_path: String, sheet_file_name: String, animations: Dictionary) -> void:
	var parser := XMLParser.new()
	var open_error := parser.open(metadata_path)
	if open_error != OK:
		push_warning("Не удалось прочитать анимации из %s: %s" % [metadata_path, error_string(open_error)])
		return
	var image_name := ""
	var tile_id := -1
	var frames: Array[Dictionary] = []
	while true:
		var read_error := parser.read()
		if read_error == ERR_FILE_EOF:
			break
		if read_error != OK:
			push_warning("Ошибка XML при чтении анимаций листа %s." % metadata_path)
			break
		if parser.get_node_type() == XMLParser.NODE_ELEMENT:
			match parser.get_node_name():
				"tileset":
					image_name = ""
				"image":
					image_name = parser.get_named_attribute_value("source").get_file()
				"tile":
					tile_id = int(parser.get_named_attribute_value("id"))
					frames.clear()
				"frame":
					if tile_id >= 0:
						frames.append({
							"tile_id": int(parser.get_named_attribute_value("tileid")),
							"duration": int(parser.get_named_attribute_value("duration")),
						})
		elif parser.get_node_type() == XMLParser.NODE_ELEMENT_END and parser.get_node_name() == "tile":
			if image_name.to_lower() == sheet_file_name.to_lower() and not frames.is_empty():
				animations[tile_id] = frames.duplicate()
			tile_id = -1
			frames.clear()


func _load_saved_maps() -> void:
	_pending_action = "saved_maps"
	if is_instance_valid(_loading_overlay):
		_set_loading_progress(95, "Загрузка карт")
	if _saved_maps_status.is_empty():
		_set_status("Загружаем список черновиков…")
	ApiClient.request_json(HTTPClient.METHOD_GET, _api_prefix + "/map/saved?mode=" + _mode.uri_encode())


func _render_saved_maps() -> void:
	_saved_select.clear()
	_saved_select.add_item("Выбрать черновик")
	_saved_select.set_item_metadata(0, 0)
	for saved_map in _saved_maps:
		_saved_select.add_item("%s · %sx%s" % [
			str(saved_map.get("name", "Без названия")),
			str(saved_map.get("map_w", 0)),
			str(saved_map.get("map_h", 0)),
		])
		_saved_select.set_item_metadata(_saved_select.item_count - 1, int(saved_map.get("id", 0)))


func _load_selected_map() -> void:
	if _saved_select.selected < 0 or _saved_select.selected >= _saved_select.item_count:
		_set_status("Сначала выберите черновик карты.")
		return
	var saved_id := int(_saved_select.get_item_metadata(_saved_select.selected))
	if saved_id <= 0:
		_set_status("Выберите черновик карты.")
		return
	_pending_action = "load_map"
	_set_status("Загружаем черновик карты…")
	ApiClient.request_json(HTTPClient.METHOD_GET, _api_prefix + "/map/editor/saved/%d" % saved_id)


func _load_map_payload(map_data: Variant) -> void:
	if not map_data is Dictionary:
		_set_status("Сохранённая карта имеет неверный формат.")
		return
	_saved_id = int(map_data.get("id", 0))
	_map_name.text = str(map_data.get("name", ""))
	_map_width.value = int(map_data.get("map_w", DEFAULT_MAP_SIZE))
	_map_height.value = int(map_data.get("map_h", DEFAULT_MAP_SIZE))
	_spawns = SPAWN_RULES.load_spawns(map_data.get("spawns", []), _map_size(), _mode)
	_refresh_spawn_button()
	_minimap_dirty = true
	_undo_stack.clear()
	_redo_stack.clear()
	_stroke_snapshot.clear()
	_selection = Rect2i()
	_layers.clear()
	_next_layer_id = 1
	var stored_layers: Variant = map_data.get("editor_layers", [])
	if stored_layers is Array:
		for stored in stored_layers:
			if stored is Dictionary:
				var layer: Dictionary = stored.duplicate(true)
				layer["id"] = int(layer.get("id", _next_layer_id))
				layer["parent_id"] = int(layer.get("parent_id", 0))
				layer["visible"] = bool(layer.get("visible", true))
				layer["locked"] = bool(layer.get("locked", false))
				layer["passable"] = LAYER_RULES.is_passable(layer)
				layer["cells"] = _cells_to_dictionary(layer.get("cells", []))
				layer["animal_settings"] = _animal_settings_to_dictionary(
					layer.get("animal_settings", {})
				)
				_next_layer_id = maxi(_next_layer_id, int(layer["id"]) + 1)
				_layers.append(layer)
	if _layers.is_empty():
		_create_default_layers()
		var ground: Dictionary = _layers[0]
		for cell in map_data.get("cells", []):
			if cell is Dictionary:
				var cell_key := str(cell.get("key", ""))
				var target_layer := ground
				if cell_key.begins_with(ANIMAL_INSTANCE_PREFIX):
					target_layer = _ensure_animal_layer()
				elif cell_key.begins_with(MOB_INSTANCE_PREFIX):
					target_layer = _ensure_mob_layer()
				elif str(cell.get("layer", "")) == "object":
					target_layer = _layer_by_type(LAYER_OBJECT)
				target_layer["cells"][_cell_key(int(cell.get("x", 0)), int(cell.get("y", 0)))] = cell_key
	_ensure_animal_layer()
	_ensure_mob_layer()
	_move_animal_instances_to_animal_layer()
	_move_mob_instances_to_mob_layer()
	var reordered := LAYER_RULES.normalize_order(_layers)
	_active_layer_id = int(_layers[0].get("id", 1))
	_render_layers()
	_canvas.queue_redraw()
	_set_status(
		"Карта загружена. Слои и содержимое восстановлены."
		+ (" Слои тайлов поставлены под слои объектов." if reordered else "")
	)


func _layer_by_type(layer_type: String) -> Dictionary:
	for layer in _layers:
		if str(layer.get("type", "")) == layer_type:
			return layer
	return {}


func _ensure_animal_layer() -> Dictionary:
	var animal_layer := _layer_by_type(LAYER_ANIMAL)
	if animal_layer.is_empty():
		animal_layer = _new_layer("Животные", LAYER_ANIMAL, 0)
		_layers.append(animal_layer)
	return animal_layer


func _ensure_mob_layer() -> Dictionary:
	var mob_layer := _layer_by_type(LAYER_MOB)
	if mob_layer.is_empty():
		mob_layer = _new_layer("Мобы", LAYER_MOB, 0)
		_layers.append(mob_layer)
	return mob_layer


func _move_animal_instances_to_animal_layer() -> void:
	_move_creature_instances_to_layer(
		ANIMAL_INSTANCE_PREFIX, _ensure_animal_layer(),
	)


func _move_mob_instances_to_mob_layer() -> void:
	_move_creature_instances_to_layer(
		MOB_INSTANCE_PREFIX, _ensure_mob_layer(),
	)


func _move_creature_instances_to_layer(prefix: String, target_layer: Dictionary) -> void:
	var moved_cells: Dictionary = {}
	var moved_settings: Dictionary = {}
	var sources_were_visible := true
	var moved_any := false
	for layer in _layers:
		if int(layer.get("id", 0)) == int(target_layer.get("id", 0)):
			continue
		var cells: Dictionary = layer.get("cells", {})
		var creature_coords: Array = []
		for coord in cells:
			if str(cells[coord]).begins_with(prefix):
				creature_coords.append(coord)
		if creature_coords.is_empty():
			continue
		moved_any = true
		sources_were_visible = sources_were_visible and _is_layer_visible(layer)
		for coord in creature_coords:
			moved_cells[coord] = cells[coord]
			var source_settings: Dictionary = layer.get("animal_settings", {})
			if source_settings.has(coord):
				moved_settings[coord] = source_settings[coord]
			cells.erase(coord)
			layer.get("animal_settings", {}).erase(coord)
		layer["cells"] = cells
	for coord in moved_cells:
		target_layer["cells"][coord] = moved_cells[coord]
		if moved_settings.has(coord):
			target_layer["animal_settings"][coord] = moved_settings[coord]
		else:
			target_layer["animal_settings"][coord] = {
				"mode": _mode,
				"patrol_radius": _animal_brush_radius(str(moved_cells[coord]), _mode),
			}
	if moved_any:
		target_layer["visible"] = sources_were_visible


func _animal_settings_to_dictionary(value: Variant) -> Dictionary:
	return value.duplicate(true) if value is Dictionary else {}


func _cells_to_dictionary(value: Variant) -> Dictionary:
	var cells := {}
	if value is Array:
		for cell in value:
			if cell is Dictionary:
				cells[_cell_key(int(cell.get("x", 0)), int(cell.get("y", 0)))] = str(cell.get("key", ""))
	elif value is Dictionary:
		cells = value.duplicate(true)
	return cells


func _save_map() -> void:
	var name := _map_name.text.strip_edges()
	if name.is_empty():
		_set_status("Введите название карты перед сохранением.")
		return
	var previous_spawn_count := _spawns.size()
	_spawns = SPAWN_RULES.load_spawns(_spawns, _map_size(), _mode)
	var removed_spawn_count := previous_spawn_count - _spawns.size()
	if removed_spawn_count > 0:
		_refresh_spawn_button()
		_canvas.queue_redraw()
	if not _front_line_spawns_supported():
		_set_status(
			"Карта не сохранена: в волне выбран моб, который ещё не подключён к боевому каталогу."
		)
		return
	var serialized_layers := _serialize_editor_layers()
	_last_save_merged_cells = int(serialized_layers["merged_cells"])
	_post_saved_map({
		"saved_id": _saved_id,
		"name": name,
		"mode": _mode,
		"map_w": int(_map_width.value),
		"map_h": int(_map_height.value),
		"cells": serialized_layers["catalog_cells"],
		"editor_layers": serialized_layers["editor_layers"],
		"mobs": [],
		"spawns": _spawn_payload(),
	})
	if removed_spawn_count > 0:
		_set_status(
			"Удалено некорректных или скрытых точек спауна: %d. Карта отправлена на сохранение."
			% removed_spawn_count,
		)


func _spawn_payload() -> Array:
	return SPAWN_RULES.to_payload(_spawns, _mode, _map_size())


func _post_saved_map(payload: Dictionary) -> void:
	_pending_action = "save_map"
	_set_status("Сохраняем карту в черновики…")
	ApiClient.request_json(HTTPClient.METHOD_POST, _api_prefix + "/map/editor/saved", payload)


func _refresh_local_drafts(selected_id := "") -> void:
	if _local_draft_select == null:
		return
	var target_id := selected_id if not selected_id.is_empty() else _selected_local_draft_id()
	_local_draft_select.clear()
	for draft in DRAFTS_RULES.list_drafts(_local_drafts_folder):
		var label := "%s · %d×%d" % [str(draft["name"]), int(draft["map_w"]), int(draft["map_h"])]
		var worlds: Array = draft["active_worlds"]
		if not worlds.is_empty():
			label += " · в мире «%s»" % ", ".join(PackedStringArray(worlds))
		_local_draft_select.add_item(label)
		var index := _local_draft_select.item_count - 1
		_local_draft_select.set_item_metadata(index, str(draft["id"]))
		if str(draft["id"]) == target_id:
			_local_draft_select.select(index)


func _selected_local_draft_id() -> String:
	if _local_draft_select == null:
		return ""
	var index := _local_draft_select.selected
	if index < 0 or index >= _local_draft_select.item_count:
		return ""
	return str(_local_draft_select.get_item_metadata(index))


func _save_local_draft() -> bool:
	var serialized := _serialize_editor_layers()
	var result: Dictionary = DRAFTS_RULES.save_draft(
		_local_drafts_folder, _map_name.text, serialized["catalog_cells"], int(_map_width.value), int(_map_height.value),
		_local_draft_id, _mode, [], _spawn_payload(), serialized["editor_layers"],
	)
	if not str(result["error"]).is_empty():
		_set_status("Черновик не сохранён: %s" % str(result["error"]))
		return false
	var draft: Dictionary = result["draft"]
	_local_draft_id = str(draft["id"])
	_map_name.text = str(draft["name"])
	_refresh_local_drafts(_local_draft_id)
	_set_status("Черновик «%s» сохранён на этом компьютере." % str(draft["name"]))
	return true


func _open_local_draft(draft_id: String) -> void:
	var result: Dictionary = DRAFTS_RULES.load_draft(_local_drafts_folder, draft_id)
	if not str(result["error"]).is_empty():
		_set_status("Черновик не открыт: %s" % str(result["error"]))
		return
	var draft: Dictionary = result["draft"]
	var draft_mode := str(draft.get("mode", _mode))
	if draft_mode != _mode:
		_set_status("Черновик создан для режима «%s»: откройте редактор в этом режиме." % str(
			WorldModeRegistry.describe(draft_mode).get("name", draft_mode),
		))
		return
	var server_map: Variant = draft.get("server_map")
	_load_map_payload({
		"id": int(server_map.get("saved_id", 0)) if server_map is Dictionary else 0,
		"name": str(draft.get("name", "")),
		"map_w": int(draft.get("map_w", DEFAULT_MAP_SIZE)),
		"map_h": int(draft.get("map_h", DEFAULT_MAP_SIZE)),
		"editor_layers": draft.get("editor_layers", []),
		"cells": draft.get("cells", []),
		"spawns": draft.get("spawns", []),
	})
	_local_draft_id = str(draft["id"])
	_refresh_local_drafts(_local_draft_id)
	_set_status("Черновик «%s» открыт с этого компьютера." % str(draft.get("name", "")))


func _open_selected_local_draft() -> void:
	var draft_id := _selected_local_draft_id()
	if draft_id.is_empty():
		_set_status("Сначала выберите черновик на этом компьютере.")
		return
	_open_local_draft(draft_id)


func _local_draft_summary(draft_id: String) -> Dictionary:
	for draft in DRAFTS_RULES.list_drafts(_local_drafts_folder):
		if str(draft["id"]) == draft_id:
			return draft
	return {}


func _request_delete_local_draft() -> void:
	var draft_id := _selected_local_draft_id()
	if draft_id.is_empty():
		_set_status("Сначала выберите черновик на этом компьютере.")
		return
	var draft := _local_draft_summary(draft_id)
	if draft.is_empty():
		_refresh_local_drafts()
		_set_status("Черновик уже удалён.")
		return
	var worlds: Array = draft["active_worlds"]
	if not worlds.is_empty():
		_set_status("Нельзя удалить: карта играет в мире «%s»" % ", ".join(PackedStringArray(worlds)))
		return
	var dialog := ConfirmationDialog.new()
	dialog.title = "Удалить черновик"
	dialog.dialog_text = "Удалить черновик «%s» с этого компьютера? Карта на сервере не изменится." % str(draft["name"])
	dialog.confirmed.connect(_delete_local_draft.bind(draft_id, dialog))
	dialog.canceled.connect(dialog.queue_free)
	add_child(dialog)
	dialog.popup_centered()


func _delete_local_draft(draft_id: String, dialog: ConfirmationDialog) -> void:
	dialog.queue_free()
	var name := str(_local_draft_summary(draft_id).get("name", ""))
	var error := DRAFTS_RULES.delete_draft(_local_drafts_folder, draft_id)
	if not error.is_empty():
		_set_status("Черновик не удалён: %s" % error)
		return
	if _local_draft_id == draft_id:
		_local_draft_id = ""
	_refresh_local_drafts()
	_set_status("Черновик «%s» удалён с этого компьютера." % name)


func _storage_layer(layer_type: String, item: Dictionary) -> String:
	if layer_type in [LAYER_OBJECT, LAYER_ANIMAL, LAYER_MOB] \
		or str(item.get("kind", "")) == "object":
		return "object"
	var editor_layer := int(item.get("editor_layer", 0))
	match editor_layer:
		1, 3:
			return "ground"
		2, 4:
			return "overlay"
		5:
			return "elevation"
		6:
			return "infra"
	if str(item.get("category", "")) == "water":
		return "ground"
	return "ground"


func _load_worlds_for_publish() -> void:
	if _has_unpublished_local_assets():
		_set_status("Публикация недоступна: карта содержит локальные тайлы листов, животных или мобов. Игровой сервер пока принимает только элементы каталога сервера.")
		return
	_pending_action = "worlds"
	ApiClient.request_json(HTTPClient.METHOD_GET, _api_prefix + "/worlds")


func _show_publish_dialog() -> void:
	if _worlds.is_empty():
		_set_status("Нет доступных миров режима %s для публикации." % _mode)
		return
	var dialog := ConfirmationDialog.new()
	dialog.title = "Опубликовать карту"
	dialog.dialog_text = "Выберите целевой мир:"
	_publish_select = OptionButton.new()
	_publish_select.custom_minimum_size.x = 300
	for world in _worlds:
		_publish_select.add_item(str(world.get("name", "Мир")))
		_publish_select.set_item_metadata(_publish_select.item_count - 1, int(world.get("id", 0)))
	dialog.add_child(_publish_select)
	dialog.confirmed.connect(_publish_map.bind(dialog))
	dialog.canceled.connect(dialog.queue_free)
	add_child(dialog)
	dialog.popup_centered()


func _publish_map(dialog: ConfirmationDialog) -> void:
	var world_id := int(_publish_select.get_item_metadata(_publish_select.selected))
	if world_id <= 0:
		_set_status("Выберите целевой мир.")
		return
	var current_saved_id := _saved_id
	_publish_world_name = _publish_select.get_item_text(_publish_select.selected)
	_save_before_publish(world_id, current_saved_id)
	dialog.queue_free()


var _publish_world_id := 0


func _save_before_publish(world_id: int, current_saved_id: int) -> void:
	_publish_world_id = world_id
	if current_saved_id > 0:
		_publish_saved_map()
		return
	_save_map()


func _publish_saved_map() -> void:
	if _has_unpublished_local_assets():
		_publish_world_id = 0
		_set_status("Публикация недоступна: карта содержит локальные тайлы листов, животных или мобов.")
		return
	var data := _build_map_payload()
	data["world_id"] = _publish_world_id
	data["saved_id"] = _saved_id
	_publish_request_world_id = _publish_world_id
	_publish_request_world_name = _publish_world_name
	_publish_world_id = 0
	_pending_action = "publish"
	_set_status("Публикуем карту…")
	ApiClient.request_json(HTTPClient.METHOD_POST, _api_prefix + "/map/editor/publish", data)


func _generate_from_world() -> void:
	if _api_prefix != "/api/deck":
		_set_status("Сгенерировать можно только на карте мира Колоды: откройте редактор из мира.")
		return
	_pending_action = "world_terrain"
	_set_status("Загружаем рельеф карты мира…")
	ApiClient.request_json(HTTPClient.METHOD_GET, _api_prefix + "/map/terrain")


func _apply_world_terrain(terrain: Variant) -> void:
	if not terrain is Dictionary or not terrain.has("tiles"):
		_set_status("Мир сервера играет процедурным рельефом: опубликованной карты нет")
		return
	var map_w := int(terrain.get("width_tiles", DEFAULT_MAP_SIZE))
	var map_h := int(terrain.get("height_tiles", DEFAULT_MAP_SIZE))
	var cells: Array = SEED_RULES.build_cells(terrain, _catalog_by_key, map_w, map_h)
	if cells.is_empty():
		_set_status("Не удалось построить карту из рельефа: каталог тайлов пуст.")
		return
	_push_undo_snapshot(_layers_snapshot())
	_map_width.value = map_w
	_map_height.value = map_h
	_reset_layers()
	for cell in cells:
		var target := _layer_by_type(LAYER_OBJECT) if str(cell["layer"]) == "object" else _layers[0]
		target["cells"][_cell_key(int(cell["x"]), int(cell["y"]))] = str(cell["key"])
	_spawns = []
	_selection = Rect2i()
	_saved_id = 0
	_local_draft_id = ""
	_minimap_dirty = true
	_render_layers()
	_canvas.queue_redraw()
	_set_status("Карта мира в черновике, клеток: %d. Сохраните черновик (Ctrl+S)" % cells.size())


func _create_test_world() -> void:
	if not TEST_WORLD_RULES.can_create(str(GameSession.user.get("role", ""))):
		_set_status(TEST_WORLD_RULES.error_message(TEST_WORLD_RULES.ADMIN_ONLY_TEXT))
		return
	if not TEST_WORLD_RULES.can_create_in_mode(_mode):
		_set_status(TEST_WORLD_RULES.error_message(TEST_WORLD_RULES.MODE_ONLY_TEXT))
		return
	if is_instance_valid(_test_world_request):
		_set_status("Тестовый мир уже создаётся. Подождите.")
		return
	if _has_unpublished_local_assets():
		_set_status(TEST_WORLD_RULES.error_message("карта содержит локальные тайлы листов, животных или мобов"))
		return
	if _map_name.text.strip_edges().is_empty():
		_set_status(TEST_WORLD_RULES.error_message("введите название карты"))
		return
	_test_world_after_save = true
	_save_map()


func _request_test_world() -> void:
	_post_test_world(_api_prefix + TEST_WORLD_RULES.ENDPOINT, TEST_WORLD_RULES.build_payload(_saved_id, _map_name.text, true))


func _post_test_world(path: String, payload: Dictionary) -> bool:
	var request := HTTPRequest.new()
	request.timeout = TEST_WORLD_RULES.TIMEOUT_SECONDS
	add_child(request)
	_test_world_request = request
	request.request_completed.connect(_on_test_world_completed)
	var headers := PackedStringArray(["Content-Type: application/json", "Authorization: Bearer " + ApiClient.token])
	var error := request.request(ApiClient.base_url + path, headers, HTTPClient.METHOD_POST, JSON.stringify(payload))
	if error != OK:
		_finish_test_world_request()
		_set_status(TEST_WORLD_RULES.error_message("Не удалось начать запрос: " + error_string(error)))
		return false
	_set_status("Создаём тестовый мир…")
	return true


func _on_test_world_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	_finish_test_world_request()
	var parsed: Variant = null
	if not body.is_empty():
		parsed = JSON.parse_string(body.get_string_from_utf8())
	_set_status(TEST_WORLD_RULES.result_message(result, response_code, parsed))


func _finish_test_world_request() -> void:
	if is_instance_valid(_test_world_request):
		_test_world_request.queue_free()
	_test_world_request = null


func _build_map_payload() -> Dictionary:
	var serialized_layers := _serialize_editor_layers()
	return {
		"name": _map_name.text.strip_edges(),
		"mode": _mode,
		"map_w": int(_map_width.value),
		"map_h": int(_map_height.value),
		"cells": serialized_layers["catalog_cells"],
		"editor_layers": serialized_layers["editor_layers"],
		"mobs": [],
		"spawns": _spawn_payload(),
	}


func _serialize_editor_layers() -> Dictionary:
	# Сервер хранит по одному тайлу на клетку слоя хранения, поэтому из нескольких
	# слоёв редактора в плоский список попадает верхний; полные слои остаются в editor_layers.
	var catalog_cells_by_slot := {}
	var merged_cells := 0
	var stored_layers: Array[Dictionary] = []
	for layer in _layers:
		var serialized := {
			"id": int(layer["id"]),
			"name": str(layer["name"]),
			"type": str(layer["type"]),
			"parent_id": int(layer.get("parent_id", 0)),
			"visible": bool(layer.get("visible", true)),
			"locked": bool(layer.get("locked", false)),
			"passable": LAYER_RULES.is_passable(layer),
				"animal_settings": _animal_settings_to_dictionary(layer.get("animal_settings", {})),
			"cells": [],
		}
		var layer_cells: Array[Dictionary] = []
		for coord in layer.get("cells", {}):
			var parts := str(coord).split(":")
			if parts.size() != 2:
				continue
			var key := str(layer["cells"][coord])
			var catalog_item: Dictionary = _catalog_by_key.get(key, {})
			var storage_layer := _storage_layer(str(layer.get("type", "")), catalog_item)
			var cell := {
				"layer": storage_layer,
				"x": int(parts[0]),
				"y": int(parts[1]),
				"key": key,
			}
			layer_cells.append(cell)
			if not catalog_item.is_empty():
				var slot_key := "%s|%d|%d" % [storage_layer, int(cell["x"]), int(cell["y"])]
				if catalog_cells_by_slot.has(slot_key):
					merged_cells += 1
				catalog_cells_by_slot[slot_key] = cell
		serialized["cells"] = layer_cells
		stored_layers.append(serialized)
	var catalog_cells: Array[Dictionary] = []
	for cell in catalog_cells_by_slot.values():
		catalog_cells.append(cell)
	return {
		"catalog_cells": catalog_cells,
		"editor_layers": stored_layers,
		"merged_cells": merged_cells,
	}


func _has_unpublished_local_assets() -> bool:
	for layer in _layers:
		for key in layer.get("cells", {}).values():
			var cell_key := str(key)
			if not _decode_atlas_cell(cell_key).is_empty() \
				or cell_key.begins_with(ANIMAL_INSTANCE_PREFIX) \
				or cell_key.begins_with(MOB_INSTANCE_PREFIX):
				return true
	return false


func _has_atlas_cells() -> bool:
	for layer in _layers:
		for key in layer.get("cells", {}).values():
			if not _decode_atlas_cell(str(key)).is_empty():
				return true
	return false


func _has_animal_instances_in_map() -> bool:
	for layer in _layers:
		for key in layer.get("cells", {}).values():
			if str(key).begins_with(ANIMAL_INSTANCE_PREFIX) \
				or str(key).begins_with(MOB_INSTANCE_PREFIX):
				return true
	return false


func _leave_editor() -> void:
	SCENE_TRANSITION.run(get_tree(), _change_to_menu)


func _change_to_menu() -> void:
	var error := get_tree().change_scene_to_file("res://scenes/main.tscn")
	if error != OK:
		_set_status("Не удалось вернуться в меню: " + error_string(error))


func _show_access_denied() -> void:
	var label := Label.new()
	label.text = "Редактор карт доступен только модераторам и администраторам."
	label.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	add_child(label)


func _set_status(message: String) -> void:
	if _status != null:
		_status.text = message


func _cell_key(x: int, y: int) -> String:
	return "%d:%d" % [x, y]


func _unhandled_key_input(event: InputEvent) -> void:
	var key_event := event as InputEventKey
	if key_event == null or not key_event.pressed or key_event.echo or is_instance_valid(_item_form_dialog):
		return
	if not _handle_shortcut(key_event):
		return
	var viewport := get_viewport()
	if viewport != null:
		viewport.set_input_as_handled()


func _handle_shortcut(key_event: InputEventKey) -> bool:
	if not key_event.ctrl_pressed:
		return _handle_tool_shortcut(key_event)
	if _key_matches(key_event, KEY_Z):
		if key_event.shift_pressed:
			_redo_last_action()
		else:
			_undo_last_action()
	elif _key_matches(key_event, KEY_Y):
		_redo_last_action()
	elif _key_matches(key_event, KEY_C):
		_copy_selection()
	elif _key_matches(key_event, KEY_X):
		_cut_selection()
	elif _key_matches(key_event, KEY_V):
		_select_tool(TOOL_STAMP)
	elif _key_matches(key_event, KEY_D):
		_deselect()
	elif _key_matches(key_event, KEY_S):
		_save_local_draft()
	elif _key_matches(key_event, KEY_L):
		_open_selected_local_draft()
	else:
		return false
	return true


# Сочетания проверяются и по символу, и по физической клавише: на русской раскладке Ctrl+Z даёт другой символ.
func _key_matches(key_event: InputEventKey, key: Key) -> bool:
	return key_event.keycode == key or key_event.physical_keycode == key


func _handle_tool_shortcut(key_event: InputEventKey) -> bool:
	if _key_matches(key_event, KEY_B):
		_select_tool(TOOL_BRUSH)
	elif _key_matches(key_event, KEY_F):
		_select_tool(TOOL_FILL)
	elif _key_matches(key_event, KEY_V):
		_select_tool(TOOL_SELECT)
	elif _key_matches(key_event, KEY_DELETE):
		if not _selection.has_area():
			return false
		_delete_selection()
	elif _key_matches(key_event, KEY_M):
		_toggle_minimap()
	elif _key_matches(key_event, KEY_ESCAPE):
		return _handle_escape()
	else:
		return false
	return true


func _undo_last_action() -> void:
	if _undo_stack.is_empty():
		_set_status("Нет действий для отмены.")
		return
	_restore_history_snapshot(HISTORY_RULES.undo(_undo_stack, _redo_stack, _layers_snapshot()))
	_set_status("Последнее действие отменено.")


func _redo_last_action() -> void:
	if _redo_stack.is_empty():
		_set_status("Нет действий для повтора.")
		return
	_restore_history_snapshot(HISTORY_RULES.redo(_undo_stack, _redo_stack, _layers_snapshot(), UNDO_HISTORY_LIMIT))
	_set_status("Действие повторено.")


func _restore_history_snapshot(snapshot: Dictionary) -> void:
	_layers = snapshot["layers"]
	_active_layer_id = int(snapshot["active_layer_id"])
	_map_width.value = int(snapshot.get("map_w", _map_width.value))
	_map_height.value = int(snapshot.get("map_h", _map_height.value))
	_spawns = SPAWN_RULES.load_spawns(snapshot.get("spawns", []), _map_size(), _mode)
	_refresh_spawn_button()
	_selection = Rect2i()
	_minimap_dirty = true
	_render_layers()
	_canvas.queue_redraw()
	_refresh_history_buttons()


func _paint_canvas_at(position: Vector2) -> void:
	var map_cell := _map_cell_at(position)
	match _active_tool:
		TOOL_FILL:
			_fill_canvas_cell(map_cell)
		TOOL_SELECT:
			_select_press(map_cell)
		TOOL_STAMP:
			_paste_stamp_at(map_cell)
		TOOL_SPAWN:
			_toggle_spawn(map_cell)
		_:
			_paint_canvas_cell(map_cell)


func _map_cell_at(position: Vector2) -> Vector2i:
	var tile_size := TILE_SIZE * _zoom
	return Vector2i(
		floori((position.x - _pan.x) / tile_size),
		floori((position.y - _pan.y) / tile_size)
	)


func _begin_canvas_stroke(position: Vector2, button: MouseButton) -> void:
	_minimap_dirty = true
	_stroke_button = button
	_last_stroke_cell = Vector2i(-1, -1)
	_stroke_snapshot = _layers.duplicate(true)
	_stroke_spawns = _spawns.duplicate(true)
	_stroke_active_layer_id = _active_layer_id
	if button == MOUSE_BUTTON_LEFT:
		_paint_canvas_at(position)
	elif button == MOUSE_BUTTON_RIGHT:
		_erase_canvas_at(position)


func _end_canvas_stroke(button: MouseButton) -> void:
	if _stroke_button == button:
		_stroke_button = MOUSE_BUTTON_NONE
		_last_stroke_cell = Vector2i(-1, -1)
		_select_drag = {}
		if _stroke_snapshot != _layers or _stroke_spawns != _spawns:
			_push_undo_snapshot({
				"layers": _stroke_snapshot,
				"active_layer_id": _stroke_active_layer_id,
				"spawns": _stroke_spawns,
			})
		_stroke_snapshot = []
		_stroke_spawns = []
		_canvas.queue_redraw()


func _paint_canvas_drag_at(position: Vector2) -> void:
	match _active_tool:
		TOOL_BRUSH:
			_paint_stroke_to(_map_cell_at(position))
		TOOL_SELECT:
			_select_drag_to(_map_cell_at(position))


func _erase_canvas_drag_at(position: Vector2) -> void:
	if _active_tool in [TOOL_BRUSH, TOOL_FILL]:
		_erase_stroke_to(_map_cell_at(position))


func _paint_stroke_to(target: Vector2i) -> void:
	if _last_stroke_cell.x < 0:
		_paint_canvas_cell(target)
		return
	var distance := maxi(absi(target.x - _last_stroke_cell.x), absi(target.y - _last_stroke_cell.y))
	if distance <= 0:
		return
	var start := _last_stroke_cell
	for step in range(1, distance + 1):
		var point := Vector2(start).lerp(Vector2(target), float(step) / distance)
		_paint_canvas_cell(Vector2i(roundi(point.x), roundi(point.y)))


func _erase_stroke_to(target: Vector2i) -> void:
	if _last_stroke_cell.x < 0:
		_erase_canvas_cell(target)
		return
	var distance := maxi(absi(target.x - _last_stroke_cell.x), absi(target.y - _last_stroke_cell.y))
	if distance <= 0:
		return
	var start := _last_stroke_cell
	for step in range(1, distance + 1):
		var point := Vector2(start).lerp(Vector2(target), float(step) / distance)
		_erase_canvas_cell(Vector2i(roundi(point.x), roundi(point.y)))


func _paint_canvas_cell(map_cell: Vector2i) -> void:
	_minimap_dirty = true
	if _selected_item_key.is_empty():
		return
	var map_x := map_cell.x
	var map_y := map_cell.y
	if map_x < 0 or map_y < 0 or map_x >= int(_map_width.value) or map_y >= int(_map_height.value):
		_last_stroke_cell = map_cell
		return
	if map_cell == _last_stroke_cell:
		return
	_last_stroke_cell = map_cell
	var layer := _get_layer(_active_layer_id)
	if layer.is_empty() or bool(layer.get("locked", false)) or str(layer.get("type", "")) == LAYER_GROUP \
		or not _is_layer_visible(layer):
		return
	var item: Dictionary = _catalog_by_key.get(_selected_item_key, {})
	var atlas_cell := _decode_atlas_cell(_selected_item_key)
	var animal_group: Dictionary = _animal_groups_by_key.get(_selected_item_key, {})
	if item.is_empty() and atlas_cell.is_empty() and animal_group.is_empty():
		return
	if not _active_custom_group_id.is_empty() and _custom_tile_groups.has(_active_custom_group_id):
		if not _is_tile_layer(layer):
			_set_status("Группы тайлов можно размещать только на слое тайлов.")
			return
		var cells: Dictionary = layer.get("cells", {})
		var target_key := _cell_key(map_x, map_y)
		var occupied_key := str(cells.get(target_key, ""))
		var occupied_group: Dictionary = _custom_group_by_key.get(occupied_key, {})
		if not occupied_key.is_empty() and str(occupied_group.get("group_id", "")) != _active_custom_group_id:
			_set_status("Эта клетка занята другим тайлом.")
			return
		var group: Dictionary = _custom_tile_groups[_active_custom_group_id]
		if not _auto_brush_enabled:
			_place_custom_group_stamp(layer, group, map_cell)
			return
		var extension_depth := int(occupied_group.get("tile_y", 0)) - 3
		if extension_depth > 0:
			_promote_custom_extensions_above(
				cells, map_cell, _active_custom_group_id, group, extension_depth,
			)
		cells[target_key] = group["tile_keys"][1][1]
		layer["cells"] = cells
		_refresh_custom_tile_group(layer, _active_custom_group_id, map_cell)
		_canvas.queue_redraw()
		return
	if not animal_group.is_empty():
		var is_mob := str(animal_group.get("kind", "animal")) == "mob"
		var required_layer_type := LAYER_MOB if is_mob else LAYER_ANIMAL
		var required_layer_name := "Мобы" if is_mob else "Животные"
		if str(layer.get("type", "")) != required_layer_type:
			_set_status("Готовые спрайты можно размещать только на слое «%s»." % required_layer_name)
			return
		var animal_size := _animal_instance_frame_size(animal_group)
		if map_x + animal_size.x > int(_map_width.value) \
			or map_y + animal_size.y > int(_map_height.value):
			_set_status("Животное не помещается на карте целиком.")
			return
		var cells: Dictionary = layer.get("cells", {})
		var target_key := _cell_key(map_x, map_y)
		var occupied_key := str(cells.get(target_key, ""))
		if not occupied_key.is_empty() and occupied_key != _selected_item_key:
			_set_status("Эта клетка занята другим объектом.")
			return
		cells[target_key] = _selected_item_key
		layer["cells"] = cells
		var animal_settings: Dictionary = layer.get("animal_settings", {})
		animal_settings[target_key] = {
			"mode": _mode,
			"patrol_radius": _animal_brush_radius(_selected_item_key, _mode),
		}
		layer["animal_settings"] = animal_settings
		_canvas.queue_redraw()
		return
	if not atlas_cell.is_empty():
		if str(layer.get("type", "")) in [LAYER_ANIMAL, LAYER_MOB]:
			var layer_name := "Мобы" if str(layer.get("type", "")) == LAYER_MOB else "Животные"
			_set_status("На слое «%s» можно размещать только готовые спрайты." % layer_name)
			return
		if not _is_tile_layer(layer):
			_set_status("Тайлы листов можно размещать только на слое тайлов.")
			return
		if _auto_brush_enabled:
			var sheet_path := str(atlas_cell["path"])
			var group_center: Vector2i = atlas_cell["coords"]
			var cells: Dictionary = layer.get("cells", {})
			var target_key := _cell_key(map_x, map_y)
			var existing := _decode_atlas_cell(str(cells.get(target_key, "")))
			var existing_is_matching_manual_tile: bool = not existing.has("group_center") \
				and str(existing.get("path", "")) == sheet_path \
				and existing.get("coords", Vector2i.ZERO) == group_center
			if not str(cells.get(target_key, "")).is_empty() \
				and not _same_autotile_group(existing, sheet_path, group_center) \
				and not existing_is_matching_manual_tile:
				_set_status("Эта клетка занята другим тайлом.")
				return
			var extension_depth := 0
			if _is_autotile_extension(existing):
				var existing_coords: Vector2i = existing.get("coords", Vector2i.ZERO)
				extension_depth = existing_coords.y - group_center.y - 2
			if _same_autotile_group(existing, sheet_path, group_center) and extension_depth > 0:
				_promote_atlas_extensions_above(
					cells, map_cell, sheet_path, group_center, extension_depth,
				)
			cells[target_key] = _encode_autotile_cell(sheet_path, group_center, group_center)
			_promote_compatible_manual_autotile_cells(cells, map_cell, sheet_path, group_center)
			layer["cells"] = cells
			_refresh_autotile_group(
				layer, sheet_path, group_center, _active_stamp_rows, map_cell,
			)
			_canvas.queue_redraw()
			return
		var stamp_region := _selected_atlas_region
		if stamp_region.size == Vector2i.ZERO:
			stamp_region = Rect2i(atlas_cell["coords"], Vector2i.ONE)
		if stamp_region.size == Vector2i.ONE:
			var sheet_path := str(atlas_cell["path"])
			var group_center: Vector2i = atlas_cell["coords"]
			var cells: Dictionary = layer.get("cells", {})
			var existing := _decode_atlas_cell(str(cells.get(_cell_key(map_x, map_y), "")))
			var joins_autotile_group := _same_autotile_group(
				existing, sheet_path, group_center,
			) or _has_adjacent_autotile_core(cells, map_cell, sheet_path, group_center)
			if joins_autotile_group:
				cells[_cell_key(map_x, map_y)] = _encode_autotile_cell(
					sheet_path, group_center, group_center,
				)
				_promote_compatible_manual_autotile_cells(
					cells, map_cell, sheet_path, group_center,
				)
				layer["cells"] = cells
				var group_rows := int(_atlas_annotations.get(
					_annotation_key(sheet_path, group_center), 3,
				))
				if group_rows not in [3, 4, 5]:
					group_rows = 3
				_refresh_autotile_group(
					layer, sheet_path, group_center, group_rows, map_cell,
				)
				_canvas.queue_redraw()
				return
		_place_atlas_brush_stamp(layer, str(atlas_cell["path"]), stamp_region, map_cell)
		_canvas.queue_redraw()
		return
	if str(layer.get("type", "")) in [LAYER_ANIMAL, LAYER_MOB]:
		var layer_name := "Мобы" if str(layer.get("type", "")) == LAYER_MOB else "Животные"
		_set_status("На слое «%s» можно размещать только готовые спрайты." % layer_name)
		return
	if str(layer.get("type", "")) == LAYER_OBJECT and str(item.get("kind", "")) != "object":
		_set_status("На слое объектов можно размещать только объекты.")
		return
	if str(layer.get("type", "")) == LAYER_TILE and str(item.get("kind", "")) == "object":
		_set_status("Выберите слой объектов для размещения объекта.")
		return
	layer["cells"][_cell_key(map_x, map_y)] = _selected_item_key
	_canvas.queue_redraw()


func _select_tool(tool: String) -> void:
	if tool == TOOL_BRUSH:
		_set_auto_brush(false)
		return
	if tool == TOOL_STAMP and _stamp_buffer.is_empty():
		_set_status("Буфер пуст: выделите область (V) и нажмите Ctrl+C или Ctrl+X")
		_sync_tool_buttons()
		return
	_active_tool = tool
	_auto_brush_enabled = false
	_annotation_controls.visible = false
	_sync_tool_buttons()
	match tool:
		TOOL_FILL:
			_set_status("Заливка: ЛКМ заливает связанную область земли того же вида, ПКМ стирает.")
		TOOL_SELECT:
			_set_status("Выделение: тяните рамку ЛКМ, внутри рамки тяните, чтобы переместить. Delete — удалить, Ctrl+C/X — копировать/вырезать.")
		TOOL_STAMP:
			_set_status("Вставка: клик по карте вставит кусок левым верхним углом в клетку курсора. ПКМ или Esc — отмена.")
		TOOL_SPAWN:
			_set_status("Точки (%s): ЛКМ разместить; двойной щелчок — переименовать или настроить." % _spawn_type_title())


func _toggle_spawn(map_cell: Vector2i) -> void:
	if _spawn_type == SPAWN_RULES.TYPE_MOB:
		var active_layer := _get_layer(_active_layer_id)
		if str(active_layer.get("type", "")) != LAYER_MOB:
			_set_status("Точки появления ЛПС можно размещать только на слое «Мобы».")
			return
		if bool(active_layer.get("locked", false)) or not _is_layer_visible(active_layer):
			_set_status("Чтобы размещать точки ЛПС, разблокируйте и покажите слой «Мобы».")
			return
	if SPAWN_RULES.find(_spawns, map_cell) >= 0:
		_set_status("Точка уже размещена. Двойной щелчок открывает её настройки.")
		return
	var settings := _default_mob_spawn_settings() if _spawn_type == SPAWN_RULES.TYPE_MOB else {}
	if _spawn_type == SPAWN_RULES.TYPE_BUILDING:
		settings = SPAWN_RULES.normalize_building_settings({})
	if _spawn_type == SPAWN_RULES.TYPE_MOB:
		var waves: Array = settings.get("waves", [])
		if waves.is_empty() or str(waves[0].get("mob_key", "")).is_empty():
			_set_status("В палитре нет мобов для размещения точки.")
			return
	var result: Dictionary = SPAWN_RULES.toggle(
		_spawns, map_cell, _map_size(), _spawn_type, settings, _mode == "front_line", _building_sprite
	)
	if not str(result["error"]).is_empty():
		_set_status(str(result["error"]))
		return
	if result["result"] == SPAWN_RULES.ADDED:
		var title := "Точка появления ЛПС" if _spawn_type == SPAWN_RULES.TYPE_MOB else "Точка возрождения"
		_set_status("%s %s на (%d, %d)" % [title, _spawns[-1]["name"], map_cell.x, map_cell.y])
	else:
		_set_status("Точка не размещена.")
	_refresh_spawn_button()
	_canvas.queue_redraw()


func _remove_spawn(map_cell: Vector2i) -> void:
	if not SPAWN_RULES.erase(_spawns, map_cell):
		return
	_set_status("Точка спауна убрана с (%d, %d)" % [map_cell.x, map_cell.y])
	_refresh_spawn_button()
	_canvas.queue_redraw()


func _sync_tool_buttons() -> void:
	_set_button_pressed(_brush_button, _active_tool == TOOL_BRUSH and not _auto_brush_enabled)
	_set_button_pressed(_auto_brush_button, _active_tool == TOOL_BRUSH and _auto_brush_enabled)
	_set_button_pressed(_fill_button, _active_tool == TOOL_FILL)
	_set_button_pressed(_select_button, _active_tool == TOOL_SELECT)
	_set_button_pressed(_stamp_button, _active_tool == TOOL_STAMP)
	_set_button_pressed(_hero_spawn_button, _active_tool == TOOL_SPAWN and _spawn_type == SPAWN_RULES.TYPE_HERO)
	_set_button_pressed(_mob_spawn_button, _active_tool == TOOL_SPAWN and _spawn_type == SPAWN_RULES.TYPE_MOB)
	_set_button_pressed(_building_spawn_button, _active_tool == TOOL_SPAWN and _spawn_type == SPAWN_RULES.TYPE_BUILDING)
	_refresh_spawn_button()


func _set_button_pressed(button: Button, pressed: bool) -> void:
	button.set_block_signals(true)
	button.button_pressed = pressed
	button.set_block_signals(false)


func _fill_canvas_cell(map_cell: Vector2i) -> void:
	if _selected_item_key.is_empty():
		return
	var layer := _get_layer(_active_layer_id)
	if layer.is_empty() or bool(layer.get("locked", false)) or str(layer.get("type", "")) == LAYER_GROUP \
		or not _is_layer_visible(layer):
		return
	if not _is_tile_layer(layer):
		_set_status("Заливка работает только на слое тайлов.")
		return
	var error := _fill_selection_error()
	if not error.is_empty():
		_set_status(error)
		return
	var cells: Dictionary = layer.get("cells", {})
	var filled: Array = FILL_RULES.fill(cells, _map_size(), map_cell, _selected_item_key)
	layer["cells"] = cells
	_canvas.queue_redraw()
	if filled.is_empty():
		_set_status("Область уже этого вида")
	else:
		_set_status("Залито клеток: %d" % filled.size())


func _fill_selection_error() -> String:
	if not _active_custom_group_id.is_empty():
		return "Серверную группу тайлов нельзя залить: выберите один тайл земли"
	var animal_group: Dictionary = _animal_groups_by_key.get(_selected_item_key, {})
	if not animal_group.is_empty():
		return "Заливка работает только с землёй"
	if not _decode_atlas_cell(_selected_item_key).is_empty():
		if _selected_atlas_region.size.x > 1 or _selected_atlas_region.size.y > 1:
			return "Заливка работает одним тайлом: выберите один тайл на листе"
		return ""
	var item: Dictionary = _catalog_by_key.get(_selected_item_key, {})
	if str(item.get("kind", "")) != "ground":
		return "Заливка работает только с землёй"
	return ""


func _map_size() -> Vector2i:
	return Vector2i(int(_map_width.value), int(_map_height.value))


func _select_press(map_cell: Vector2i) -> void:
	if not _inside_map(map_cell):
		return
	if SELECTION_RULES.contains(_selection, map_cell):
		_select_drag = {"mode": "move", "last": map_cell}
		return
	_selection = Rect2i(map_cell, Vector2i.ONE)
	_select_drag = {"mode": "rect", "start": map_cell}
	_canvas.queue_redraw()


func _select_drag_to(map_cell: Vector2i) -> void:
	if _select_drag.is_empty() or not _inside_map(map_cell):
		return
	if _select_drag["mode"] == "rect":
		_selection = SELECTION_RULES.rect_between(_select_drag["start"], map_cell)
		_canvas.queue_redraw()
		return
	var delta: Vector2i = map_cell - _select_drag["last"]
	if delta == Vector2i.ZERO:
		return
	var result: Dictionary = SELECTION_RULES.move(_editable_selection_layers(), _selection, delta, _map_size())
	_minimap_dirty = true
	if not str(result["error"]).is_empty():
		_set_status(str(result["error"]))
		return
	if int(result["count"]) > 0:
		_selection.position += delta
	_select_drag["last"] = map_cell
	_canvas.queue_redraw()


func _editable_selection_layers() -> Array:
	var targets: Array = []
	for layer in _layers:
		if str(layer.get("type", "")) not in [LAYER_TILE, LAYER_DECORATIVE, LAYER_OBJECT]:
			continue
		if bool(layer.get("locked", false)) or not _is_layer_visible(layer):
			continue
		targets.append(layer)
	return targets


func _deselect() -> void:
	if not _selection.has_area():
		return
	_selection = Rect2i()
	_canvas.queue_redraw()


func _delete_selection() -> void:
	if not _selection.has_area():
		return
	var before := _layers_snapshot()
	var count: int = SELECTION_RULES.delete(_editable_selection_layers(), _selection)
	_commit_edit(before)
	_canvas.queue_redraw()
	_set_status("Удалено элементов: %d" % count)


func _copy_selection() -> bool:
	var stamp: Dictionary = SELECTION_RULES.copy(_editable_selection_layers(), _selection)
	if stamp.is_empty():
		_set_status("В выделении нет элементов для копирования" if _selection.has_area() else "Сначала выделите область (V)")
		return false
	_stamp_buffer = stamp
	_set_status("Скопировано элементов: %d. Ctrl+V — вставить куском" % int(stamp["count"]))
	return true


func _cut_selection() -> void:
	if not _copy_selection():
		return
	_delete_selection()
	_set_status("Вырезано. Ctrl+V — вставить куском")


func _paste_stamp_at(map_cell: Vector2i) -> void:
	if _stamp_buffer.is_empty() or not _inside_map(map_cell):
		return
	var result: Dictionary = SELECTION_RULES.paste(_editable_selection_layers(), _stamp_buffer, map_cell, _map_size(), _active_layer_id)
	if not str(result["error"]).is_empty():
		_set_status(str(result["error"]))
		return
	_selection = result["rect"]
	_canvas.queue_redraw()
	var message := "Вставлено элементов: %d" % int(result["count"])
	if int(result["skipped"]) > 0:
		message += ". Не вставлено: %d (нет подходящего слоя или он заблокирован)" % int(result["skipped"])
	_set_status(message)


func _commit_edit(before: Dictionary) -> void:
	if before["layers"] != _layers or before["spawns"] != _spawns:
		_push_undo_snapshot(before)


func _inside_map(map_cell: Vector2i) -> bool:
	return map_cell.x >= 0 and map_cell.y >= 0 and map_cell.x < int(_map_width.value) and map_cell.y < int(_map_height.value)


func _update_canvas_hover(position: Vector2) -> void:
	var cell := _map_cell_at(position)
	if not _inside_map(cell):
		cell = Vector2i(-1, -1)
	if cell == _hover_cell:
		return
	_hover_cell = cell
	if _active_tool in [TOOL_STAMP, TOOL_SPAWN]:
		_canvas.queue_redraw()


func _on_canvas_mouse_exited() -> void:
	_hover_cell = Vector2i(-1, -1)
	if _active_tool in [TOOL_STAMP, TOOL_SPAWN]:
		_canvas.queue_redraw()


func _handle_escape() -> bool:
	if _active_tool == TOOL_STAMP:
		_select_tool(TOOL_BRUSH)
		return true
	if _selection.has_area():
		_deselect()
		return true
	return false


func _place_atlas_brush_stamp(layer: Dictionary, sheet_path: String, region: Rect2i, map_center: Vector2i) -> bool:
	var center_offset := Vector2i(floori(float(region.size.x) / 2.0), floori(float(region.size.y) / 2.0))
	var map_origin := map_center - center_offset
	var map_width := int(_map_width.value)
	var map_height := int(_map_height.value)
	if region.size.x > map_width or region.size.y > map_height:
		_set_status("Выбранная группа больше карты и не помещается целиком.")
		return false
	map_origin.x = clampi(map_origin.x, 0, map_width - region.size.x)
	map_origin.y = clampi(map_origin.y, 0, map_height - region.size.y)
	var sheet: Dictionary = _atlas_sheets_by_path.get(sheet_path, {})
	var cells: Dictionary = layer.get("cells", {})
	var stamp: Dictionary = {}
	for row in range(region.size.y):
		for column in range(region.size.x):
			var destination := map_origin + Vector2i(column, row)
			var target_key := _cell_key(destination.x, destination.y)
			var tile_coords := region.position + Vector2i(column, row)
			var tile_key := _encode_atlas_cell(sheet_path, tile_coords)
			if cells.has(target_key) and str(cells[target_key]) != tile_key \
				and region.size != Vector2i.ONE:
				_set_status("Группа не нанесена: она пересекается с уже занятыми клетками.")
				return false
			stamp[target_key] = tile_key
	for target_key in stamp:
		cells[target_key] = stamp[target_key]
	layer["cells"] = cells
	if map_origin != map_center - center_offset:
		_set_status("Штамп прижат к краю карты и размещён целиком.")
	return true


func _animal_instance_frame_size(group: Dictionary) -> Vector2i:
	var states: Dictionary = group.get("states", {})
	var state: Dictionary = states.get(str(group.get("default_state", "")), {})
	var clips: Array = state.get("clips", [])
	if clips.is_empty():
		return Vector2i.ONE
	return Vector2i(clips[0].get("frame_size", Vector2i.ONE))


func _place_custom_group_stamp(layer: Dictionary, group: Dictionary, map_center: Vector2i) -> bool:
	var tile_keys: Array = group.get("tile_keys", [])
	if tile_keys.is_empty():
		return false
	var group_rows := tile_keys.size()
	var map_origin := map_center - Vector2i(1, 1)
	var cells: Dictionary = layer.get("cells", {})
	var stamp: Dictionary = {}
	for row in range(group_rows):
		for column in range(3):
			var destination := map_origin + Vector2i(column, row)
			if destination.x < 0 or destination.y < 0 \
				or destination.x >= int(_map_width.value) or destination.y >= int(_map_height.value):
				_set_status("Выбранная серверная группа не помещается на карту целиком.")
				return false
			var target_key := _cell_key(destination.x, destination.y)
			var tile_key := str(tile_keys[row][column])
			if cells.has(target_key) and str(cells[target_key]) != tile_key:
				_set_status("Группа не нанесена: она пересекается с уже занятыми клетками.")
				return false
			stamp[target_key] = tile_key
	for target_key in stamp:
		cells[target_key] = stamp[target_key]
	layer["cells"] = cells
	_canvas.queue_redraw()
	return true


func _select_spawn_type(spawn_type: String) -> void:
	if spawn_type == SPAWN_RULES.TYPE_MOB:
		var mob_layer_found := false
		for layer in _layers:
			if str(layer.get("type", "")) == LAYER_MOB \
				and not bool(layer.get("locked", false)) and _is_layer_visible(layer):
				_active_layer_id = int(layer.get("id", 0))
				mob_layer_found = true
				break
		if not mob_layer_found:
			_set_status("Чтобы размещать точки ЛПС, покажите и разблокируйте слой «Мобы».")
			_sync_tool_buttons()
			return
		_render_layers()
	_spawn_type = spawn_type
	_select_tool(TOOL_SPAWN)
	_set_status(
		"Размещение точек появления ЛПС: сначала поставьте точку, затем настройте её двойным щелчком."
		if spawn_type == SPAWN_RULES.TYPE_MOB
		else "Размещение точек возрождения игроков."
	)


func _spawn_type_title(spawn_type := "") -> String:
	var selected_type := _spawn_type if spawn_type.is_empty() else spawn_type
	if selected_type == SPAWN_RULES.TYPE_BUILDING:
		return "главных зданий"
	return "ЛПС" if selected_type == SPAWN_RULES.TYPE_MOB else "возрождения игроков"


func _building_frame(sprite: String, frame: int) -> Texture2D:
	var paths: Array = BUILDING_FRAME_PATHS.get(sprite, BUILDING_FRAME_PATHS["castle_8"])
	var path := str(paths[posmod(frame, paths.size())])
	if not _building_frame_cache.has(path):
		_building_frame_cache[path] = load(path) as Texture2D
	return _building_frame_cache[path]


func _pick_building_sprite(sprite: String) -> void:
	_building_sprite = sprite
	_select_spawn_type(SPAWN_RULES.TYPE_BUILDING)


func _ensure_building_anim_timer() -> void:
	if _building_anim_timer != null:
		return
	_building_anim_timer = Timer.new()
	_building_anim_timer.wait_time = BUILDING_ANIM_STEP_SECONDS
	_building_anim_timer.timeout.connect(_on_building_anim_tick)
	add_child(_building_anim_timer)
	_building_anim_timer.start()


func _on_building_anim_tick() -> void:
	_building_anim_frame += 1
	for entry in _building_palette_icons:
		var button: Button = entry["button"]
		if is_instance_valid(button):
			button.icon = _building_frame(str(entry["sprite"]), _building_anim_frame)
	if _canvas != null and _count_spawns(SPAWN_RULES.TYPE_BUILDING) > 0:
		_canvas.queue_redraw()


func _open_building_settings(spawn_index: int) -> void:
	if _building_settings_dialog == null:
		_building_settings_dialog = BUILDING_SETTINGS_DIALOG_SCRIPT.new()
		_building_settings_dialog.theme = _ui_root.theme
		_building_settings_dialog.confirmed.connect(_save_building_settings)
		_ui_root.add_child(_building_settings_dialog)
	_spawn_settings_index = spawn_index
	_building_settings_dialog.set_settings(_spawns[spawn_index].get("settings", {}))
	_building_settings_dialog.popup_centered()


func _save_building_settings() -> void:
	if _spawn_settings_index < 0 or _spawn_settings_index >= _spawns.size():
		return
	_spawns[_spawn_settings_index]["settings"] = _building_settings_dialog.get_settings()
	_set_status("Настройки главного здания сохранены.")
	_refresh_spawn_button()


func _count_spawns(spawn_type: String) -> int:
	var count := 0
	for spawn in _spawns:
		if str(spawn.get("type", SPAWN_RULES.TYPE_HERO)) == spawn_type:
			count += 1
	return count


func _refresh_spawn_button() -> void:
	if _hero_spawn_button == null or _mob_spawn_button == null:
		return
	_hero_spawn_button.text = "Возрождения · %d" % _count_spawns(SPAWN_RULES.TYPE_HERO)
	_mob_spawn_button.text = "Появления ЛПС · %d" % _count_spawns(SPAWN_RULES.TYPE_MOB)
	if _building_spawn_button != null:
		_building_spawn_button.text = "Главные здания · %d" % _count_spawns(SPAWN_RULES.TYPE_BUILDING)


func _default_mob_spawn_settings() -> Dictionary:
	var mob_key := ""
	for group in _animal_groups:
		if str(group.get("kind", "")) == "mob":
			mob_key = _spawn_mob_key(group)
			if not mob_key.is_empty():
				break
	return {"waves": [{
		"level": 1,
		"mob_key": mob_key,
		"count": 1,
		"interval_seconds": 30,
		"squad_min": 1,
		"squad_max": 1,
		"start_after_seconds": 0,
		"target": SPAWN_RULES.TARGET_OBJECTIVE,
	}]}


func _open_spawn_settings(spawn_index: int) -> void:
	if spawn_index < 0 or spawn_index >= _spawns.size():
		return
	if str(_spawns[spawn_index].get("type", "")) == SPAWN_RULES.TYPE_BUILDING:
		_open_building_settings(spawn_index)
		return
	_spawn_settings_index = spawn_index
	var settings: Dictionary = _spawns[spawn_index].get(
		"settings", _default_mob_spawn_settings()
	).duplicate(true)
	var title := "Настройки точки ЛПС (%d, %d)" % [
		int(_spawns[spawn_index]["x"]), int(_spawns[spawn_index]["y"]),
	]
	_configure_spawn_settings_dialog(settings, title)
	_spawn_name_edit.text = str(_spawns[spawn_index].get("name", spawn_index + 1))


func _configure_spawn_settings_dialog(settings: Dictionary, title: String) -> void:
	_ensure_spawn_settings_dialog()
	var normalized := SPAWN_RULES.normalize_mob_settings(settings, _mode == "front_line")
	_spawn_wave_configs = normalized["waves"].duplicate(true)
	_spawn_wave_index = 0
	_spawn_wave_count_spin.set_block_signals(true)
	_spawn_wave_count_spin.value = _spawn_wave_configs.size()
	_spawn_wave_count_spin.set_block_signals(false)
	_refresh_spawn_wave_select()
	_load_spawn_wave_form()
	_spawn_settings_dialog.title = title
	_spawn_settings_dialog.popup_centered(EDITOR_DIALOG_SIZE)


func _refresh_spawn_wave_select() -> void:
	_spawn_wave_select.clear()
	for index in range(_spawn_wave_configs.size()):
		_spawn_wave_select.add_item("Волна %d" % (index + 1))
	_spawn_wave_select.select(clampi(_spawn_wave_index, 0, maxi(0, _spawn_wave_configs.size() - 1)))


func _on_spawn_wave_count_changed(value: float) -> void:
	if not _store_spawn_wave_form():
		_spawn_wave_count_spin.set_value_no_signal(_spawn_wave_configs.size())
		return
	var requested_count := clampi(roundi(value), 1, SPAWN_RULES.MAX_SPAWN_WAVES)
	var previous_count := _spawn_wave_configs.size()
	while _spawn_wave_configs.size() < requested_count:
		var template: Dictionary = _spawn_wave_configs[-1].duplicate(true) if not _spawn_wave_configs.is_empty() \
			else _default_mob_spawn_settings()["waves"][0]
		_spawn_wave_configs.append(template)
	while _spawn_wave_configs.size() > requested_count:
		_spawn_wave_configs.pop_back()
	_spawn_wave_index = requested_count - 1 if requested_count > previous_count else mini(
		_spawn_wave_index, requested_count - 1
	)
	_refresh_spawn_wave_select()
	_load_spawn_wave_form()


func _add_spawn_wave() -> void:
	if _spawn_wave_configs.size() >= SPAWN_RULES.MAX_SPAWN_WAVES:
		return
	_spawn_wave_count_spin.value = _spawn_wave_configs.size() + 1


func _on_spawn_wave_selected(index: int) -> void:
	if not _store_spawn_wave_form():
		_refresh_spawn_wave_select()
		return
	_spawn_wave_index = index
	_load_spawn_wave_form()


func _store_spawn_wave_form() -> bool:
	if _spawn_wave_configs.is_empty() or _spawn_wave_index < 0 \
		or _spawn_wave_index >= _spawn_wave_configs.size():
		return false
	var start_delay := _parse_duration(
		_spawn_start_delay_edit.text,
		SPAWN_RULES.MAX_START_DELAY_SECONDS,
		true,
		"Время старта волны",
	)
	if not bool(start_delay["valid"]):
		_set_status(str(start_delay["error"]))
		return false
	var interval := _parse_duration(
		_spawn_interval_edit.text,
		SPAWN_RULES.MAX_INTERVAL_SECONDS,
		false,
		"Интервал появления",
	)
	if not bool(interval["valid"]):
		_set_status(str(interval["error"]))
		return false
	var current_wave: Dictionary = _spawn_wave_configs[_spawn_wave_index]
	var wave := {
		"mob_key": str(_spawn_mob_select.get_item_metadata(_spawn_mob_select.selected))
			if _spawn_mob_select.selected >= 0 else "",
		"start_after_seconds": int(start_delay["seconds"]),
		"level": int(current_wave.get("level", 1)),
		"count": int(_spawn_count_spin.value),
		"interval_seconds": int(interval["seconds"]),
		"squad_min": int(_spawn_squad_min_spin.value),
		"squad_max": int(_spawn_squad_max_spin.value),
	}
	if _mode == "front_line":
		wave["target"] = _spawn_target_select.get_item_metadata(_spawn_target_select.selected)
		var boss := {
			"enabled": _spawn_boss_checkbox.button_pressed,
			"max_hp": int(_spawn_boss_hp_spin.value),
			"max_mp": int(_spawn_boss_mp_spin.value),
			"reward_xp": int(_spawn_boss_reward_xp_spin.value),
			"spell_slots": [],
			"drop_slots": [],
		}
		for slot_controls in _spawn_boss_spell_slots:
			var spell_select: OptionButton = slot_controls["spell_select"]
			var cooldown := _parse_duration(
				(slot_controls["cooldown"] as LineEdit).text,
				SPAWN_RULES.MAX_BOSS_SPELL_COOLDOWN_SECONDS,
				true,
				"Перезарядка заклинания",
			)
			if not bool(cooldown["valid"]):
				_set_status(str(cooldown["error"]))
				return false
			boss["spell_slots"].append({
				"spell_key": str(spell_select.get_item_metadata(spell_select.selected))
					if spell_select.selected >= 0 else "",
				"range": int((slot_controls["range"] as SpinBox).value),
				"damage": int((slot_controls["damage"] as SpinBox).value),
				"cooldown_seconds": int(cooldown["seconds"]),
				"area_radius": int((slot_controls["area_radius"] as SpinBox).value),
				"mana_cost": int((slot_controls["mana_cost"] as SpinBox).value),
			})
		for slot_controls in _spawn_boss_drop_controls:
			var item_select: OptionButton = slot_controls["item_select"]
			boss["drop_slots"].append({
				"item_id": int(item_select.get_item_metadata(item_select.selected))
					if item_select.selected >= 0 else 0,
				"chance_percent": int((slot_controls["chance"] as SpinBox).value),
			})
		wave["boss"] = boss
	_spawn_wave_configs[_spawn_wave_index] = wave
	return true


func _load_spawn_wave_form() -> void:
	if _spawn_wave_configs.is_empty() or _spawn_wave_index < 0 \
		or _spawn_wave_index >= _spawn_wave_configs.size():
		return
	var settings: Dictionary = _spawn_wave_configs[_spawn_wave_index]
	_spawn_mob_select.clear()
	var selected_index := -1
	for group in _animal_groups:
		if str(group.get("kind", "")) != "mob":
			continue
		var key := _spawn_mob_key(group)
		if key.is_empty():
			continue
		_spawn_mob_select.add_icon_item(
			_animal_group_icon(group),
			str(group.get("name", key)),
		)
		var option_index := _spawn_mob_select.item_count - 1
		_spawn_mob_select.set_item_metadata(option_index, key)
		if key == str(settings.get("mob_key", "")):
			selected_index = option_index
	if selected_index < 0 and not str(settings.get("mob_key", "")).is_empty():
		_spawn_mob_select.add_item(
			"Не подключён к бою: " + str(settings["mob_key"]),
		)
		selected_index = _spawn_mob_select.item_count - 1
		_spawn_mob_select.set_item_metadata(selected_index, str(settings["mob_key"]))
		_spawn_mob_select.set_item_disabled(selected_index, true)
	if _spawn_mob_select.item_count == 0:
		_set_status("В палитре нет мобов для настройки волны.")
		return
	_spawn_mob_select.select(maxi(0, selected_index))
	_spawn_start_delay_edit.text = _format_duration(int(settings.get("start_after_seconds", 0)))
	_spawn_count_spin.value = int(settings.get("count", 1))
	_spawn_squad_min_spin.value = int(settings.get("squad_min", 1))
	_spawn_squad_max_spin.value = int(settings.get("squad_max", settings.get("squad_min", 1)))
	_request_spawn_preview()
	_spawn_interval_edit.text = _format_duration(int(settings.get("interval_seconds", 30)))
	_spawn_target_row.visible = _mode == "front_line"
	_select_spawn_target(str(settings.get("target", SPAWN_RULES.TARGET_OBJECTIVE)))
	var boss: Dictionary = SPAWN_RULES.normalize_boss_settings(settings.get("boss", {}))
	_spawn_boss_checkbox.visible = _mode == "front_line"
	_spawn_boss_checkbox.set_pressed_no_signal(bool(boss["enabled"]))
	_spawn_boss_fields.visible = _mode == "front_line" and bool(boss["enabled"])
	_spawn_boss_hp_spin.value = int(boss["max_hp"])
	_spawn_boss_mp_spin.value = int(boss["max_mp"])
	_spawn_boss_reward_xp_spin.value = int(boss["reward_xp"])
	for index in range(_spawn_boss_spell_slots.size()):
		var slot: Dictionary = boss["spell_slots"][index]
		var controls: Dictionary = _spawn_boss_spell_slots[index]
		var spell_select: OptionButton = controls["spell_select"]
		spell_select.clear()
		spell_select.add_item("Выбор заклинаний будет доступен позже")
		spell_select.set_item_metadata(0, "")
		spell_select.set_item_disabled(0, true)
		var spell_key := str(slot["spell_key"])
		if not spell_key.is_empty():
			spell_select.add_item("Сохранённое заклинание")
			spell_select.set_item_metadata(1, spell_key)
		spell_select.select(1 if not spell_key.is_empty() else 0)
		(controls["range"] as SpinBox).value = int(slot["range"])
		(controls["damage"] as SpinBox).value = int(slot["damage"])
		(controls["cooldown"] as LineEdit).text = _format_duration(
			int(slot["cooldown_seconds"]),
		)
		(controls["area_radius"] as SpinBox).value = int(slot["area_radius"])
		(controls["mana_cost"] as SpinBox).value = int(slot["mana_cost"])
	for index in range(_spawn_boss_drop_controls.size()):
		var slot: Dictionary = boss["drop_slots"][index]
		var controls: Dictionary = _spawn_boss_drop_controls[index]
		var item_select: OptionButton = controls["item_select"]
		item_select.clear()
		item_select.add_item("— Не выбран —")
		item_select.set_item_metadata(0, 0)
		var selected_item_id := int(slot["item_id"])
		var selected_drop_index := 0
		for item in _spawn_item_catalog:
			var item_id := int(item.get("id", 0))
			item_select.add_item("%s · #%d" % [str(item.get("name", "Предмет")), item_id])
			var option_index := item_select.item_count - 1
			item_select.set_item_metadata(option_index, item_id)
			if item_id == selected_item_id:
				selected_drop_index = option_index
		if selected_item_id > 0 and selected_drop_index == 0:
			item_select.add_item("Неизвестный предмет · #%d" % selected_item_id)
			selected_drop_index = item_select.item_count - 1
			item_select.set_item_metadata(selected_drop_index, selected_item_id)
		item_select.select(selected_drop_index)
		(controls["chance"] as SpinBox).value = int(slot["chance_percent"])


func _on_spawn_boss_toggled(enabled: bool) -> void:
	_spawn_boss_fields.visible = enabled and _mode == "front_line"


func _ensure_spawn_settings_dialog() -> void:
	if _spawn_settings_dialog != null:
		return
	_spawn_settings_dialog = ConfirmationDialog.new()
	_spawn_settings_dialog.theme = _ui_root.theme
	_spawn_settings_dialog.title = "Настройки точки ЛПС"
	_spawn_settings_dialog.ok_button_text = "Сохранить"
	_spawn_settings_dialog.confirmed.connect(_save_spawn_settings)
	_spawn_settings_dialog.custom_action.connect(_on_spawn_settings_custom_action)
	_spawn_settings_dialog.add_button("Удалить точку", false, "delete_spawn")
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size = Vector2(EDITOR_DIALOG_SIZE) - Vector2(24, 100)
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_spawn_settings_dialog.add_child(scroll)
	var form := VBoxContainer.new()
	form.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	form.add_theme_constant_override("separation", EDITOR_FORM_SPACING)
	scroll.add_child(form)
	_spawn_name_edit = LineEdit.new()
	_spawn_name_edit.max_length = 32
	_spawn_name_edit.placeholder_text = "Название точки"
	_add_spawn_setting_row(form, "Название", _spawn_name_edit)
	_spawn_wave_count_spin = _new_spawn_spin_box()
	_spawn_wave_count_spin.min_value = 1
	_spawn_wave_count_spin.max_value = SPAWN_RULES.MAX_SPAWN_WAVES
	_spawn_wave_count_spin.value = 1
	_spawn_wave_count_spin.value_changed.connect(_on_spawn_wave_count_changed)
	_add_spawn_setting_row(form, "Количество волн", _spawn_wave_count_spin)
	var wave_controls := HBoxContainer.new()
	_spawn_wave_select = OptionButton.new()
	_spawn_wave_select.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_spawn_wave_select.item_selected.connect(_on_spawn_wave_selected)
	wave_controls.add_child(_spawn_wave_select)
	var add_wave_button := Button.new()
	add_wave_button.text = "+ Волна"
	add_wave_button.tooltip_text = "Добавить независимую волну с копией текущих настроек"
	add_wave_button.pressed.connect(_add_spawn_wave)
	wave_controls.add_child(add_wave_button)
	form.add_child(wave_controls)
	_spawn_mob_select = OptionButton.new()
	_add_spawn_setting_row(form, "Моб", _spawn_mob_select)
	_spawn_start_delay_edit = _new_duration_edit()
	_add_spawn_setting_row(form, "Время старта (ЧЧ:ММ:СС)", _spawn_start_delay_edit)
	_spawn_target_select = OptionButton.new()
	_spawn_target_select.add_item("Главная цель", 0)
	_spawn_target_select.set_item_metadata(0, SPAWN_RULES.TARGET_OBJECTIVE)
	_spawn_target_select.add_item("Персонажи", 1)
	_spawn_target_select.set_item_metadata(1, SPAWN_RULES.TARGET_CHARACTERS)
	_spawn_target_select.add_item("Главная цель и персонажи", 2)
	_spawn_target_select.set_item_metadata(2, SPAWN_RULES.TARGET_BOTH)
	_spawn_target_row = _add_spawn_setting_row(form, "Цель мобов", _spawn_target_select)
	_spawn_target_row.visible = _mode == "front_line"
	_spawn_count_spin = _new_spawn_spin_box()
	_spawn_count_spin.max_value = SPAWN_RULES.MAX_SPAWN_COUNT
	_add_spawn_setting_row(form, "Мобов в волне", _spawn_count_spin)
	_spawn_interval_edit = _new_duration_edit()
	_add_spawn_setting_row(form, "Интервал появления (ЧЧ:ММ:СС)", _spawn_interval_edit)
	_spawn_squad_min_spin = _new_spawn_spin_box()
	_spawn_squad_min_spin.min_value = 1
	_spawn_squad_min_spin.max_value = SPAWN_RULES.MAX_SPAWN_COUNT
	_add_spawn_setting_row(form, "Отряд: минимум", _spawn_squad_min_spin)
	_spawn_squad_max_spin = _new_spawn_spin_box()
	_spawn_squad_max_spin.min_value = 1
	_spawn_squad_max_spin.max_value = SPAWN_RULES.MAX_SPAWN_COUNT
	_add_spawn_setting_row(form, "Отряд: максимум", _spawn_squad_max_spin)
	_spawn_squad_preview_label = Label.new()
	_spawn_squad_preview_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_spawn_squad_preview_label.add_theme_color_override("font_color", Color8(160, 200, 255))
	_add_spawn_setting_row(form, "Отправления", _spawn_squad_preview_label)
	_spawn_count_spin.value_changed.connect(_on_spawn_squad_inputs_changed)
	_spawn_squad_min_spin.value_changed.connect(_on_spawn_squad_inputs_changed)
	_spawn_squad_max_spin.value_changed.connect(_on_spawn_squad_inputs_changed)
	_spawn_boss_checkbox = CheckBox.new()
	_spawn_boss_checkbox.text = "Волна содержит босса"
	_spawn_boss_checkbox.toggled.connect(_on_spawn_boss_toggled)
	_spawn_boss_checkbox.visible = _mode == "front_line"
	form.add_child(_spawn_boss_checkbox)
	_spawn_boss_fields = VBoxContainer.new()
	_spawn_boss_fields.add_theme_constant_override("separation", EDITOR_FORM_SPACING)
	_spawn_boss_fields.visible = false
	form.add_child(_spawn_boss_fields)
	_spawn_boss_hp_spin = _new_spawn_spin_box()
	_spawn_boss_hp_spin.max_value = SPAWN_RULES.MAX_BOSS_STAT
	_add_spawn_setting_row(_spawn_boss_fields, "Босс: ХП", _spawn_boss_hp_spin)
	_spawn_boss_mp_spin = _new_spawn_spin_box()
	_spawn_boss_mp_spin.min_value = 0
	_spawn_boss_mp_spin.max_value = SPAWN_RULES.MAX_BOSS_STAT
	_add_spawn_setting_row(_spawn_boss_fields, "Босс: МП", _spawn_boss_mp_spin)
	_spawn_boss_reward_xp_spin = _new_spawn_spin_box()
	_spawn_boss_reward_xp_spin.min_value = 0
	_spawn_boss_reward_xp_spin.max_value = SPAWN_RULES.MAX_SPAWN_REWARD
	_add_spawn_setting_row(_spawn_boss_fields, "Опыт за босса", _spawn_boss_reward_xp_spin)
	_spawn_boss_spell_slots.clear()
	for slot_index in range(SPAWN_RULES.MAX_BOSS_SPELL_SLOTS):
		var slot_group := VBoxContainer.new()
		slot_group.add_theme_constant_override("separation", EDITOR_FORM_SPACING)
		var slot_title := Label.new()
		slot_title.text = "Заклинание %d" % (slot_index + 1)
		slot_group.add_child(slot_title)
		var spell_select := OptionButton.new()
		spell_select.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		_add_spawn_setting_row(slot_group, "Спел", spell_select)
		var spell_controls := {
			"spell_select": spell_select,
			"range": _new_spawn_spin_box(),
			"damage": _new_spawn_spin_box(),
			"cooldown": _new_duration_edit(),
			"area_radius": _new_spawn_spin_box(),
			"mana_cost": _new_spawn_spin_box(),
		}
		(spell_controls["range"] as SpinBox).min_value = 0
		(spell_controls["range"] as SpinBox).max_value = SPAWN_RULES.MAX_BOSS_SPELL_RANGE
		(spell_controls["damage"] as SpinBox).min_value = 0
		(spell_controls["damage"] as SpinBox).max_value = SPAWN_RULES.MAX_BOSS_STAT
		(spell_controls["area_radius"] as SpinBox).min_value = 0
		(spell_controls["area_radius"] as SpinBox).max_value = SPAWN_RULES.MAX_BOSS_SPELL_RANGE
		(spell_controls["mana_cost"] as SpinBox).min_value = 0
		(spell_controls["mana_cost"] as SpinBox).max_value = SPAWN_RULES.MAX_BOSS_STAT
		_add_spawn_setting_row(slot_group, "Дальность (клетки)", spell_controls["range"])
		_add_spawn_setting_row(slot_group, "Урон", spell_controls["damage"])
		_add_spawn_setting_row(slot_group, "Перезарядка (ЧЧ:ММ:СС)", spell_controls["cooldown"])
		_add_spawn_setting_row(slot_group, "Радиус поражения (клетки)", spell_controls["area_radius"])
		_add_spawn_setting_row(slot_group, "Затраты МП", spell_controls["mana_cost"])
		_spawn_boss_fields.add_child(slot_group)
		_spawn_boss_spell_slots.append(spell_controls)
	var drop_hint := Label.new()
	drop_hint.text = "Сумма шансов ≤100%; остаток — без выпадения"
	_spawn_boss_fields.add_child(drop_hint)
	_spawn_boss_drop_controls.clear()
	for slot_index in range(SPAWN_RULES.MAX_BOSS_DROP_SLOTS):
		var slot_group := VBoxContainer.new()
		slot_group.add_theme_constant_override("separation", EDITOR_FORM_SPACING)
		var slot_title := Label.new()
		slot_title.text = "Предмет %d" % (slot_index + 1)
		slot_group.add_child(slot_title)
		var item_select := OptionButton.new()
		item_select.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		_add_spawn_setting_row(slot_group, "Предмет", item_select)
		var chance_spin := _new_spawn_spin_box()
		chance_spin.min_value = 0
		chance_spin.max_value = 100
		_add_spawn_setting_row(slot_group, "Шанс (%)", chance_spin)
		_spawn_boss_fields.add_child(slot_group)
		_spawn_boss_drop_controls.append({
			"item_select": item_select,
			"chance": chance_spin,
		})
	add_child(_spawn_settings_dialog)


func _new_spawn_spin_box() -> SpinBox:
	var spin := SpinBox.new()
	spin.min_value = 1
	spin.max_value = 1000000000
	spin.step = 1
	spin.rounded = true
	spin.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	return spin


func _new_duration_edit() -> LineEdit:
	var edit := LineEdit.new()
	edit.placeholder_text = "00:00:00"
	edit.max_length = 9
	edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	return edit


func _format_duration(seconds: int) -> String:
	var total := maxi(0, seconds)
	return "%02d:%02d:%02d" % [
		floori(float(total) / 3600.0),
		floori(float(total % 3600) / 60.0),
		total % 60,
	]


func _parse_duration(
	value: String,
	max_seconds: int,
	allow_zero: bool,
	label: String,
) -> Dictionary:
	var parts := value.strip_edges().split(":")
	if parts.size() != 3 or parts[0].length() < 2 or parts[1].length() != 2 or parts[2].length() != 2:
		return {"valid": false, "error": "%s: используйте формат ЧЧ:ММ:СС." % label}
	for part in parts:
		if not part.is_valid_int() or int(part) < 0:
			return {"valid": false, "error": "%s: используйте формат ЧЧ:ММ:СС." % label}
	var hours := int(parts[0])
	var minutes := int(parts[1])
	var seconds := int(parts[2])
	if minutes > 59 or seconds > 59:
		return {"valid": false, "error": "%s: минуты и секунды должны быть от 00 до 59." % label}
	var total := hours * 3600 + minutes * 60 + seconds
	if total > max_seconds or (not allow_zero and total == 0):
		var requirement := "больше 00:00:00" if not allow_zero else "не больше " + _format_duration(max_seconds)
		return {"valid": false, "error": "%s: время должно быть %s." % [label, requirement]}
	return {"valid": true, "seconds": total, "error": ""}


func _add_spawn_setting_row(parent: VBoxContainer, title: String, control: Control) -> HBoxContainer:
	var row := HBoxContainer.new()
	var label := Label.new()
	label.text = title
	label.custom_minimum_size.x = roundi(EDITOR_FORM_LABEL_WIDTH * EDITOR_UI_SCALE)
	row.add_child(label)
	control.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	control.custom_minimum_size.y = roundi(28 * EDITOR_UI_SCALE)
	row.add_child(control)
	parent.add_child(row)
	return row


func _select_spawn_target(target: String) -> void:
	for index in range(_spawn_target_select.item_count):
		if str(_spawn_target_select.get_item_metadata(index)) == target:
			_spawn_target_select.select(index)
			return
	_spawn_target_select.select(0)


func _save_spawn_settings() -> void:
	if not _store_spawn_wave_form():
		return
	var settings := {"waves": _spawn_wave_configs.duplicate(true)}
	if _apply_mob_spawn_settings(_spawn_settings_index, settings, _spawn_name_edit.text):
		_spawn_settings_dialog.hide()


func _apply_mob_spawn_settings(spawn_index: int, settings: Dictionary, spawn_name := "") -> bool:
	if spawn_index < 0 or spawn_index >= _spawns.size():
		_set_status("Сначала разместите точку появления ЛПС.")
		return false
	var normalized_name := spawn_name.strip_edges()
	if normalized_name.is_empty() or normalized_name.length() > 32:
		_set_status("Название точки должно содержать от 1 до 32 символов.")
		return false
	var normalized := SPAWN_RULES.normalize_mob_settings(settings, _mode == "front_line")
	for wave in normalized["waves"]:
		var mob_key := str(wave.get("mob_key", "")).strip_edges()
		var group := _spawn_group_for_key(mob_key)
		if mob_key.is_empty() or str(group.get("kind", "")) != "mob":
			_set_status(
				"Для волн Front Line доступны только мобы, подключённые к боевому каталогу."
				if _mode == "front_line"
				else "Для каждой волны выберите моба из палитры."
			)
			return false
		if _mode == "front_line" and not SPAWN_RULES.is_front_line_mob_key(mob_key):
			_set_status(
				"Этот моб пока не подключён к боевому каталогу и не может появиться в волне."
			)
			return false
		if _mode == "front_line":
			var total_drop_chance := 0
			for drop_slot in wave["boss"]["drop_slots"]:
				var item_id := int(drop_slot.get("item_id", 0))
				var chance := int(drop_slot.get("chance_percent", 0))
				if item_id <= 0 and chance > 0:
					_set_status("Выберите предмет для каждого слота с ненулевым шансом.")
					return false
				total_drop_chance += chance
			if total_drop_chance > 100:
				_set_status("Сумма шансов предметов босса не должна превышать 100%.")
				return false
	if _spawns[spawn_index].get("settings", {}) == normalized \
		and str(_spawns[spawn_index].get("name", "")) == normalized_name:
		return true
	var before := _layers_snapshot()
	_spawns[spawn_index]["settings"] = normalized
	_spawns[spawn_index]["name"] = normalized_name
	_push_undo_snapshot(before)
	_refresh_spawn_button()
	_canvas.queue_redraw()
	_set_status("Название и настройки точки появления ЛПС сохранены.")
	return true


func _spawn_mob_key(group: Dictionary) -> String:
	var key := str(group.get("key", ""))
	if _mode == "front_line":
		key = str(group.get("profile_kind", key))
	if _mode == "front_line" and not SPAWN_RULES.is_front_line_mob_key(key):
		return ""
	return key


func _spawn_group_for_key(mob_key: String) -> Dictionary:
	var group: Dictionary = _animal_groups_by_key.get(mob_key, {})
	if not group.is_empty() or _mode != "front_line":
		return group
	for candidate in _animal_groups:
		if str(candidate.get("profile_kind", "")) == mob_key:
			return candidate
	return {}


func _front_line_spawns_supported() -> bool:
	if _mode != "front_line":
		return true
	for spawn in _spawns:
		if str(spawn.get("type", "")) != SPAWN_RULES.TYPE_MOB:
			continue
		var settings: Dictionary = spawn.get("settings", {})
		var waves: Array = settings.get("waves", [])
		if waves.is_empty():
			return false
		for wave in waves:
			if not wave is Dictionary:
				return false
			var mob_key := str(wave.get("mob_key", ""))
			var group := _spawn_group_for_key(mob_key)
			if not SPAWN_RULES.is_front_line_mob_key(mob_key) \
				or str(group.get("kind", "")) != "mob":
				return false
	return true


func _handle_canvas_double_click(position: Vector2) -> void:
	var map_cell := _map_cell_at(position)
	var index := SPAWN_RULES.find(_spawns, map_cell)
	if index < 0:
		return
	if str(_spawns[index].get("type", SPAWN_RULES.TYPE_HERO)) in [SPAWN_RULES.TYPE_MOB, SPAWN_RULES.TYPE_BUILDING]:
		_open_spawn_settings(index)
	else:
		_open_spawn_rename(index)


func _open_spawn_rename(spawn_index: int) -> void:
	if spawn_index < 0 or spawn_index >= _spawns.size():
		return
	_ensure_spawn_rename_dialog()
	_spawn_rename_index = spawn_index
	_spawn_rename_edit.text = str(_spawns[spawn_index].get("name", spawn_index + 1))
	_spawn_rename_dialog.title = "Переименование точки возрождения"
	_spawn_rename_dialog.popup_centered(EDITOR_DIALOG_SIZE)


func _ensure_spawn_rename_dialog() -> void:
	if _spawn_rename_dialog != null:
		return
	_spawn_rename_dialog = ConfirmationDialog.new()
	_spawn_rename_dialog.theme = _ui_root.theme
	_spawn_rename_dialog.ok_button_text = "Сохранить"
	_spawn_rename_dialog.confirmed.connect(_save_spawn_rename)
	_spawn_rename_dialog.custom_action.connect(_on_spawn_rename_custom_action)
	_spawn_rename_dialog.add_button("Удалить точку", false, "delete_spawn")
	var form := VBoxContainer.new()
	form.add_theme_constant_override("separation", EDITOR_FORM_SPACING)
	_spawn_rename_dialog.add_child(form)
	_spawn_rename_edit = LineEdit.new()
	_spawn_rename_edit.max_length = 32
	_spawn_rename_edit.placeholder_text = "Название точки"
	_add_spawn_setting_row(form, "Название", _spawn_rename_edit)
	add_child(_spawn_rename_dialog)


func _save_spawn_rename() -> void:
	if _rename_spawn(_spawn_rename_index, _spawn_rename_edit.text):
		_spawn_rename_dialog.hide()


func _rename_spawn(spawn_index: int, value: String) -> bool:
	if spawn_index < 0 or spawn_index >= _spawns.size():
		_set_status("Точка появления не найдена.")
		return false
	var name := value.strip_edges()
	if name.is_empty() or name.length() > 32:
		_set_status("Название точки должно содержать от 1 до 32 символов.")
		return false
	if str(_spawns[spawn_index].get("name", "")) == name:
		return true
	var before := _layers_snapshot()
	_spawns[spawn_index]["name"] = name
	_push_undo_snapshot(before)
	_canvas.queue_redraw()
	_set_status("Точка переименована.")
	return true


func _on_spawn_settings_custom_action(action: String) -> void:
	if action == "delete_spawn":
		_delete_spawn_from_dialog(_spawn_settings_index)
		_spawn_settings_dialog.hide()


func _on_spawn_rename_custom_action(action: String) -> void:
	if action == "delete_spawn":
		_delete_spawn_from_dialog(_spawn_rename_index)
		_spawn_rename_dialog.hide()


func _delete_spawn_from_dialog(spawn_index: int) -> void:
	if spawn_index < 0 or spawn_index >= _spawns.size():
		_set_status("Точка появления не найдена.")
		return
	var before := _layers_snapshot()
	_spawns.remove_at(spawn_index)
	_push_undo_snapshot(before)
	_refresh_spawn_button()
	_canvas.queue_redraw()
	_set_status("Точка появления удалена.")


func _erase_canvas_at(position: Vector2) -> void:
	var map_cell := _map_cell_at(position)
	var spawn_index := SPAWN_RULES.find(_spawns, map_cell)
	if spawn_index >= 0 and str(_spawns[spawn_index].get("type", SPAWN_RULES.TYPE_HERO)) == SPAWN_RULES.TYPE_MOB:
		_open_spawn_settings(spawn_index)
		return
	match _active_tool:
		TOOL_SELECT:
			_deselect()
		TOOL_STAMP:
			_select_tool(TOOL_BRUSH)
		TOOL_SPAWN:
			_remove_spawn(map_cell)
		_:
			_erase_canvas_cell(map_cell)


func _erase_canvas_cell(map_cell: Vector2i) -> void:
	_minimap_dirty = true
	if map_cell.x < 0 or map_cell.y < 0 or map_cell.x >= int(_map_width.value) or map_cell.y >= int(_map_height.value):
		_last_stroke_cell = map_cell
		return
	if map_cell == _last_stroke_cell:
		return
	_last_stroke_cell = map_cell
	var layer := _get_layer(_active_layer_id)
	if layer.is_empty() or bool(layer.get("locked", false)) or str(layer.get("type", "")) == LAYER_GROUP \
		or not _is_layer_visible(layer):
		return
	var cells: Dictionary = layer.get("cells", {})
	var target_key := _cell_key(map_cell.x, map_cell.y)
	var target_cell_key := str(cells.get(target_key, ""))
	var animal_anchor_key := _animal_anchor_key_at(cells, map_cell)
	if not animal_anchor_key.is_empty():
		cells.erase(animal_anchor_key)
		layer["cells"] = cells
		var animal_settings: Dictionary = layer.get("animal_settings", {})
		animal_settings.erase(animal_anchor_key)
		layer["animal_settings"] = animal_settings
		_canvas.queue_redraw()
		return
	if cells.erase(target_key):
		layer["cells"] = cells
		_canvas.queue_redraw()


func _animal_anchor_key_at(cells: Dictionary, map_cell: Vector2i) -> String:
	for coord in cells:
		var animal_key := str(cells[coord])
		var group: Dictionary = _animal_groups_by_key.get(animal_key, {})
		if group.is_empty():
			continue
		var parts := str(coord).split(":")
		if parts.size() != 2:
			continue
		var anchor := Vector2i(int(parts[0]), int(parts[1]))
		var frame_size := _animal_instance_frame_size(group)
		if map_cell.x >= anchor.x and map_cell.y >= anchor.y \
			and map_cell.x < anchor.x + frame_size.x \
			and map_cell.y < anchor.y + frame_size.y:
			return str(coord)
	return ""


func _refresh_custom_tile_group(layer: Dictionary, group_id: String, seed_cell: Vector2i) -> void:
	var group: Dictionary = _custom_tile_groups.get(group_id, {})
	if group.is_empty():
		return
	var tile_keys: Array = group["tile_keys"]
	var rows := tile_keys.size()
	var cells: Dictionary = layer.get("cells", {})
	var candidate_core_cells: Dictionary = {}
	for key in cells:
		var group_info: Dictionary = _custom_group_by_key.get(str(cells[key]), {})
		if str(group_info.get("group_id", "")) != group_id:
			continue
		var position_parts := str(key).split(":")
		if position_parts.size() != 2:
			continue
		var map_cell := Vector2i(int(position_parts[0]), int(position_parts[1]))
		if int(group_info["tile_y"]) <= 2:
			candidate_core_cells[map_cell] = key
	var core_cells := _connected_group_cells(candidate_core_cells, seed_cell)
	if core_cells.is_empty():
		return
	var component_extensions: Dictionary = {}
	for cell_variant in core_cells:
		var map_cell: Vector2i = cell_variant
		for row in range(3, rows):
			var extension_cell: Vector2i = map_cell + Vector2i(0, row - 2)
			component_extensions[_cell_key(extension_cell.x, extension_cell.y)] = true
	for extension_key in component_extensions:
		var extension_info: Dictionary = _custom_group_by_key.get(
			str(cells.get(extension_key, "")),
			{},
		)
		if str(extension_info.get("group_id", "")) == group_id \
			and int(extension_info.get("tile_y", 0)) > 2:
			cells.erase(extension_key)
	var occupied_cells: Dictionary = {}
	for cell_variant in core_cells:
		var map_cell: Vector2i = cell_variant
		occupied_cells[map_cell] = true
	for cell_variant in core_cells:
		var map_cell: Vector2i = cell_variant
		var key: String = core_cells[map_cell]
		var tile_x := 1
		var tile_y := 1
		if not occupied_cells.has(map_cell + Vector2i.LEFT):
			tile_x -= 1
		elif not occupied_cells.has(map_cell + Vector2i.RIGHT):
			tile_x += 1
		if not occupied_cells.has(map_cell + Vector2i.UP):
			tile_y -= 1
		elif not occupied_cells.has(map_cell + Vector2i.DOWN):
			tile_y += 1
		cells[key] = tile_keys[tile_y][tile_x]
	for cell_variant in core_cells:
		var map_cell: Vector2i = cell_variant
		if occupied_cells.has(map_cell + Vector2i.DOWN):
			continue
		var key: String = core_cells[map_cell]
		var group_info: Dictionary = _custom_group_by_key.get(str(cells[key]), {})
		var tile_x := int(group_info.get("tile_x", 1))
		for row in range(3, rows):
			var extension_cell: Vector2i = map_cell + Vector2i(0, row - 2)
			if extension_cell.x < 0 or extension_cell.y < 0 \
				or extension_cell.x >= int(_map_width.value) or extension_cell.y >= int(_map_height.value):
				continue
			var extension_key := _cell_key(extension_cell.x, extension_cell.y)
			if cells.has(extension_key):
				var existing_group: Dictionary = _custom_group_by_key.get(str(cells[extension_key]), {})
				if str(existing_group.get("group_id", "")) != group_id \
					or int(existing_group.get("tile_y", 0)) <= 2:
					continue
			cells[extension_key] = tile_keys[row][tile_x]
	layer["cells"] = cells


func _connected_group_cells(candidates: Dictionary, seed_cell: Vector2i) -> Dictionary:
	var connected: Dictionary = {}
	if not candidates.has(seed_cell):
		return connected
	var pending: Array[Vector2i] = [seed_cell]
	connected[seed_cell] = candidates[seed_cell]
	while not pending.is_empty():
		var current: Vector2i = pending.pop_back()
		for offset in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
			var neighbor: Vector2i = current + offset
			if connected.has(neighbor) or not candidates.has(neighbor):
				continue
			connected[neighbor] = candidates[neighbor]
			pending.append(neighbor)
	return connected


func _same_autotile_group(cell: Dictionary, sheet_path: String, group_center: Vector2i) -> bool:
	return str(cell.get("path", "")) == sheet_path \
		and cell.has("group_center") \
		and cell["group_center"] == group_center


func _is_autotile_extension(
	cell: Dictionary,
	artist_rules: Dictionary = {},
) -> bool:
	var group_center: Vector2i = cell.get("group_center", Vector2i.ZERO)
	var coords: Vector2i = cell.get("coords", Vector2i.ZERO)
	if cell.has("autotile_role"):
		return str(cell["autotile_role"]) == "extension"
	if coords.y <= group_center.y + 1:
		return false
	for rule_tiles_variant in artist_rules.values():
		for rule_tile_variant in rule_tiles_variant:
			if rule_tile_variant is Vector2i and rule_tile_variant == coords:
				return false
	var rule_prefix := "%s|" % _annotation_key(str(cell.get("path", "")), group_center)
	for rule_key in _atlas_corner_tiles:
		if not str(rule_key).begins_with(rule_prefix):
			continue
		if _autotile_rule_tiles(str(rule_key)).has(coords):
			return false
	return true


func _has_adjacent_autotile_core(
	cells: Dictionary,
	map_cell: Vector2i,
	sheet_path: String,
	group_center: Vector2i,
) -> bool:
	for offset in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
		var neighbor := _decode_atlas_cell(
			str(cells.get(_cell_key(map_cell.x + offset.x, map_cell.y + offset.y), "")),
		)
		if not _same_autotile_group(neighbor, sheet_path, group_center):
			continue
		if not _is_autotile_extension(neighbor):
			return true
	return false


func _promote_compatible_manual_autotile_cells(
	cells: Dictionary,
	seed_cell: Vector2i,
	sheet_path: String,
	group_center: Vector2i,
) -> void:
	var visited: Dictionary = {seed_cell: true}
	var pending: Array[Vector2i] = [seed_cell]
	while not pending.is_empty():
		var current: Vector2i = pending.pop_back()
		for offset in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
			var neighbor_cell: Vector2i = current + offset
			if visited.has(neighbor_cell):
				continue
			visited[neighbor_cell] = true
			var key := _cell_key(neighbor_cell.x, neighbor_cell.y)
			var neighbor := _decode_atlas_cell(str(cells.get(key, "")))
			if str(neighbor.get("path", "")) != sheet_path:
				continue
			if neighbor.has("group_center"):
				if not _same_autotile_group(neighbor, sheet_path, group_center) \
					or _is_autotile_extension(neighbor):
					continue
			elif neighbor.get("coords", Vector2i.ZERO) != group_center:
				continue
			else:
				cells[key] = _encode_autotile_cell(sheet_path, group_center, group_center)
			pending.append(neighbor_cell)


func _promote_atlas_extensions_above(
	cells: Dictionary,
	map_cell: Vector2i,
	sheet_path: String,
	group_center: Vector2i,
	extension_depth: int,
) -> void:
	for offset in range(1, extension_depth + 1):
		var previous_cell := map_cell - Vector2i.DOWN * offset
		var previous_key := _cell_key(previous_cell.x, previous_cell.y)
		var previous := _decode_atlas_cell(str(cells.get(previous_key, "")))
		if not _same_autotile_group(previous, sheet_path, group_center) \
			or not _is_autotile_extension(previous):
			break
		cells[previous_key] = _encode_autotile_cell(sheet_path, group_center, group_center)


func _promote_custom_extensions_above(
	cells: Dictionary,
	map_cell: Vector2i,
	group_id: String,
	group: Dictionary,
	extension_depth: int,
) -> void:
	for offset in range(1, extension_depth + 1):
		var previous_cell := map_cell - Vector2i.DOWN * offset
		var previous_key := _cell_key(previous_cell.x, previous_cell.y)
		var previous_group: Dictionary = _custom_group_by_key.get(str(cells.get(previous_key, "")), {})
		if str(previous_group.get("group_id", "")) != group_id \
			or int(previous_group.get("tile_y", 0)) <= 2:
			break
		cells[previous_key] = group["tile_keys"][1][1]


func _refresh_autotile_group(
	layer: Dictionary,
	sheet_path: String,
	group_center: Vector2i,
	group_rows: int,
	seed_cell: Vector2i,
	artist_rules: Dictionary = {},
) -> void:
	var cells: Dictionary = layer.get("cells", {})
	var candidate_core_cells: Dictionary = {}
	for key in cells:
		var decoded := _decode_atlas_cell(str(cells[key]))
		if not _same_autotile_group(decoded, sheet_path, group_center):
			continue
		var position_parts := str(key).split(":")
		if position_parts.size() != 2:
			continue
		var map_cell := Vector2i(int(position_parts[0]), int(position_parts[1]))
		if not _is_autotile_extension(decoded, artist_rules):
			candidate_core_cells[map_cell] = key
	var core_cells := _connected_group_cells(candidate_core_cells, seed_cell)
	if core_cells.is_empty():
		return
	var component_extensions: Dictionary = {}
	for cell_variant in core_cells:
		var map_cell: Vector2i = cell_variant
		for row in range(3, group_rows):
			var extension_cell: Vector2i = map_cell + Vector2i(0, row - 2)
			component_extensions[_cell_key(extension_cell.x, extension_cell.y)] = true
	for extension_key in component_extensions:
		var existing := _decode_atlas_cell(str(cells.get(extension_key, "")))
		if _same_autotile_group(existing, sheet_path, group_center) \
			and _is_autotile_extension(existing, artist_rules):
			cells.erase(extension_key)
	var occupied_cells: Dictionary = {}
	for cell_variant in core_cells:
		var map_cell: Vector2i = cell_variant
		occupied_cells[map_cell] = true
	var has_unmapped_corner_combination := false
	var rule_key_by_cell: Dictionary = {}
	var rule_tiles_by_cell: Dictionary = {}
	var ordered_cells: Array[Vector2i] = []
	for cell_variant in core_cells:
		var map_cell: Vector2i = cell_variant
		var key: String = core_cells[map_cell]
		var atlas_coords := group_center
		if not occupied_cells.has(map_cell + Vector2i.LEFT):
			atlas_coords.x -= 1
		elif not occupied_cells.has(map_cell + Vector2i.RIGHT):
			atlas_coords.x += 1
		if not occupied_cells.has(map_cell + Vector2i.UP):
			atlas_coords.y -= 1
		elif not occupied_cells.has(map_cell + Vector2i.DOWN):
			atlas_coords.y += 1
		var corner_variants := _autotile_corner_variants_for_cell(
			map_cell, occupied_cells, candidate_core_cells,
		)
		var mask := _autotile_mask_for_cell(map_cell, candidate_core_cells)
		var mask_key := _corner_annotation_key(
			sheet_path, group_center, _autotile_mask_key(mask),
		)
		var applied_rule_key := ""
		var applied_rule_tiles: Array[Vector2i] = []
		var sheet: Dictionary = _atlas_sheets_by_path.get(sheet_path, {})
		if artist_rules.has(mask):
			for mask_coords_variant in artist_rules[mask]:
				var mask_coords: Vector2i = mask_coords_variant
				if _atlas_coords_are_valid(sheet, mask_coords):
					applied_rule_tiles.append(mask_coords)
			if not applied_rule_tiles.is_empty():
				applied_rule_key = mask_key
			else:
				push_warning("Пропущено правило образца вне границ листа: %s" % mask_key)
		if applied_rule_key.is_empty() and _atlas_corner_tiles.has(mask_key):
			for mask_coords in _autotile_rule_tiles(mask_key):
				if _atlas_coords_are_valid(sheet, mask_coords):
					applied_rule_tiles.append(mask_coords)
			if not applied_rule_tiles.is_empty():
				applied_rule_key = mask_key
			else:
				push_warning("Пропущена настройка маски вне границ листа: %s" % mask_key)
				_set_status("Координата тайла для маски выходит за границы листа.")
		if applied_rule_key.is_empty() and corner_variants.size() == 1:
			var corner_key := _corner_annotation_key(
				sheet_path, group_center, corner_variants[0],
			)
			if _atlas_corner_tiles.has(corner_key):
				for corner_coords in _autotile_rule_tiles(corner_key):
					if _atlas_coords_are_valid(sheet, corner_coords):
						applied_rule_tiles.append(corner_coords)
				if not applied_rule_tiles.is_empty():
					applied_rule_key = corner_key
				else:
					push_warning("Пропущена настройка угла вне границ листа: %s" % corner_key)
					_set_status("Координата тайла для угла выходит за границы листа.")
		if applied_rule_key.is_empty() and corner_variants.size() > 1:
			has_unmapped_corner_combination = true
		if applied_rule_key.is_empty():
			cells[key] = _encode_autotile_cell(sheet_path, atlas_coords, group_center)
		else:
			rule_key_by_cell[map_cell] = applied_rule_key
			rule_tiles_by_cell[map_cell] = applied_rule_tiles
		ordered_cells.append(map_cell)
	ordered_cells.sort_custom(func(first: Vector2i, second: Vector2i) -> bool:
		if first.y == second.y:
			return first.x < second.x
		return first.y < second.y
	)
	var selected_rule_tiles: Dictionary = {}
	for map_cell in ordered_cells:
		if not rule_tiles_by_cell.has(map_cell):
			continue
		var rule_key: String = rule_key_by_cell[map_cell]
		var rule_tiles: Array[Vector2i] = rule_tiles_by_cell[map_cell]
		var selected_coords := _choose_autotile_variant(
			rule_tiles, rule_key, map_cell, selected_rule_tiles,
		)
		var key: String = core_cells[map_cell]
		cells[key] = _encode_autotile_cell(sheet_path, selected_coords, group_center)
		selected_rule_tiles[map_cell] = {"rule_key": rule_key, "coords": selected_coords}
	for cell_variant in core_cells:
		var map_cell: Vector2i = cell_variant
		if occupied_cells.has(map_cell + Vector2i.DOWN):
			continue
		var key: String = core_cells[map_cell]
		for row in range(3, group_rows):
			var extension_cell: Vector2i = map_cell + Vector2i(0, row - 2)
			if extension_cell.x < 0 or extension_cell.y < 0 \
				or extension_cell.x >= int(_map_width.value) or extension_cell.y >= int(_map_height.value):
				continue
			var extension_key := _cell_key(extension_cell.x, extension_cell.y)
			if cells.has(extension_key):
				var existing := _decode_atlas_cell(str(cells[extension_key]))
				if not _same_autotile_group(existing, sheet_path, group_center) \
					or not _is_autotile_extension(existing, artist_rules):
					continue
			var resolved_cell := _decode_atlas_cell(str(cells[key]))
			var resolved_coords: Vector2i = resolved_cell["coords"]
			var source_coords := Vector2i(resolved_coords.x, group_center.y + row - 1)
			cells[extension_key] = _encode_autotile_cell(
				sheet_path, source_coords, group_center, true,
			)
	layer["cells"] = cells
	if has_unmapped_corner_combination:
		_set_status("Для сочетания соседних клеток нет точного правила маски. Назначьте маску этой формы в палитре автокисти.")


func _choose_autotile_variant(
	candidates: Array[Vector2i],
	rule_key: String,
	map_cell: Vector2i,
	selected_neighbors: Dictionary,
) -> Vector2i:
	if candidates.size() <= 1:
		return candidates[0] if not candidates.is_empty() else Vector2i.ZERO
	var forbidden: Array[Vector2i] = []
	for offset in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
		var neighbor: Dictionary = selected_neighbors.get(map_cell + offset, {})
		if str(neighbor.get("rule_key", "")) == rule_key:
			var neighbor_coords: Vector2i = neighbor.get("coords", Vector2i.ZERO)
			if not forbidden.has(neighbor_coords):
				forbidden.append(neighbor_coords)
	var start_index := absi(hash("%s|%d|%d" % [rule_key, map_cell.x, map_cell.y])) % candidates.size()
	for offset in range(candidates.size()):
		var candidate: Vector2i = candidates[(start_index + offset) % candidates.size()]
		if not forbidden.has(candidate):
			return candidate
	return candidates[start_index]


func _autotile_mask_for_cell(map_cell: Vector2i, neighboring_cells: Dictionary) -> int:
	var mask := 0
	for index in range(AUTOTILE_NEIGHBOR_OFFSETS.size()):
		if neighboring_cells.has(map_cell + AUTOTILE_NEIGHBOR_OFFSETS[index]):
			mask |= 1 << index
	return mask


func _autotile_corner_variants_for_cell(
	map_cell: Vector2i,
	connected_cells: Dictionary,
	all_group_cells: Dictionary,
) -> Array[String]:
	var variants: Array[String] = []
	var corners: Array[Dictionary] = [
		{
			"name": "nw",
			"first": Vector2i.UP,
			"second": Vector2i.LEFT,
			"diagonal": Vector2i(-1, -1),
		},
		{
			"name": "ne",
			"first": Vector2i.UP,
			"second": Vector2i.RIGHT,
			"diagonal": Vector2i(1, -1),
		},
		{
			"name": "sw",
			"first": Vector2i.DOWN,
			"second": Vector2i.LEFT,
			"diagonal": Vector2i(-1, 1),
		},
		{
			"name": "se",
			"first": Vector2i.DOWN,
			"second": Vector2i.RIGHT,
			"diagonal": Vector2i(1, 1),
		},
	]
	for corner in corners:
		var first_offset: Vector2i = corner["first"]
		var second_offset: Vector2i = corner["second"]
		var diagonal_offset: Vector2i = corner["diagonal"]
		var has_first: bool = connected_cells.has(map_cell + first_offset)
		var has_second: bool = connected_cells.has(map_cell + second_offset)
		if has_first != has_second:
			continue
		var has_diagonal: bool = all_group_cells.has(map_cell + diagonal_offset)
		var variant_name := ""
		if has_first and not has_diagonal:
			variant_name = "inner"
		elif not has_first and has_diagonal:
			variant_name = "diagonal"
		else:
			continue
		variants.append("%s_%s" % [variant_name, str(corner["name"])])
	return variants


func _draw_map_canvas(canvas: Control) -> void:
	var tile_size := TILE_SIZE * _zoom
	var map_rect := Rect2(_pan, Vector2(int(_map_width.value), int(_map_height.value)) * tile_size)
	canvas.draw_rect(map_rect, Color(0.09, 0.11, 0.12))
	canvas.draw_rect(map_rect, Color(0.65, 0.66, 0.62), false, 2.0)
	for layer in _layers:
		if not _is_layer_visible(layer) or str(layer.get("type", "")) == LAYER_GROUP:
			continue
		for coord in layer.get("cells", {}):
			var parts := str(coord).split(":")
			if parts.size() != 2:
				continue
			var cell_position := Vector2(int(parts[0]), int(parts[1]))
			var rect := Rect2(_pan + cell_position * tile_size, Vector2.ONE * tile_size)
			var key := str(layer["cells"][coord])
			var animal_group: Dictionary = _animal_groups_by_key.get(key, {})
			if not animal_group.is_empty():
				_draw_animal_instance(canvas, animal_group, cell_position, tile_size)
				continue
			_draw_cell_key(canvas, key, rect)
	if _show_passability:
		_draw_passability_overlay(canvas, tile_size)
	for x in range(int(_map_width.value) + 1):
		var px := _pan.x + float(x) * tile_size
		canvas.draw_line(Vector2(px, _pan.y), Vector2(px, _pan.y + float(_map_height.value) * tile_size), Color(0.12, 0.14, 0.15, 0.6))
	for y in range(int(_map_height.value) + 1):
		var py := _pan.y + float(y) * tile_size
		canvas.draw_line(Vector2(_pan.x, py), Vector2(_pan.x + float(_map_width.value) * tile_size, py), Color(0.12, 0.14, 0.15, 0.6))
	_draw_large_object_sprites(canvas, tile_size)
	_draw_spawn_overlay(canvas, tile_size)
	_draw_selection_overlay(canvas, tile_size)
	_draw_stamp_preview(canvas, tile_size)
	_draw_minimap(canvas)


func _draw_minimap(canvas: Control) -> void:
	var map_size := _map_size()
	if not _minimap_visible or map_size.x <= 0 or map_size.y <= 0:
		return
	var rect := MINIMAP_RULES.rect_for(canvas.size, map_size)
	if rect.size.x < 2.0 or rect.size.y < 2.0:
		return
	_refresh_minimap_texture(map_size)
	canvas.draw_texture_rect(_minimap_texture, rect, false)
	canvas.draw_rect(rect, Color(0.27, 0.29, 0.32), false, 1.0)
	var view := MINIMAP_RULES.view_rect(_pan, TILE_SIZE * _zoom, canvas.size, map_size, rect)
	canvas.draw_rect(view, MINIMAP_RULES.VIEW_COLOR, false, 1.0)


func _refresh_minimap_texture(map_size: Vector2i) -> void:
	var size_changed := _minimap_texture == null or _minimap_texture.get_size() != Vector2(map_size)
	if not _minimap_dirty and not size_changed:
		return
	var now := Time.get_ticks_msec()
	if not size_changed and _stroke_button != MOUSE_BUTTON_NONE and now - _minimap_built_msec < MINIMAP_STROKE_REBUILD_MSEC:
		return
	var layers: Array = []
	for layer in _layers:
		if str(layer.get("type", "")) in [LAYER_TILE, LAYER_DECORATIVE, LAYER_OBJECT] and _is_layer_visible(layer):
			layers.append(layer)
	var image := MINIMAP_RULES.build_image(map_size, layers, Callable(self, "_minimap_category"))
	_minimap_texture = ImageTexture.create_from_image(image)
	_minimap_dirty = false
	_minimap_built_msec = now


func _minimap_category(key: String) -> String:
	var item: Dictionary = _catalog_by_key.get(key, {})
	if not item.is_empty():
		return str(item.get("category", ""))
	var atlas_cell := _decode_atlas_cell(key)
	if not atlas_cell.is_empty():
		var sheet: Dictionary = _atlas_sheets_by_path.get(str(atlas_cell["path"]), {})
		return MINIMAP_RULES.atlas_category(_atlas_category(str(sheet.get("name", ""))))
	return ""


func _minimap_rect() -> Rect2:
	if _canvas == null:
		return Rect2()
	return MINIMAP_RULES.rect_for(_canvas.size, _map_size())


func _minimap_contains(position: Vector2) -> bool:
	return _minimap_visible and _minimap_rect().has_point(position)


func _minimap_press(position: Vector2) -> bool:
	if not _minimap_contains(position):
		return false
	_minimap_dragging = true
	_center_view_on_minimap(position)
	return true


func _minimap_drag(position: Vector2) -> void:
	if _minimap_dragging:
		_center_view_on_minimap(position)


func _minimap_release() -> bool:
	if not _minimap_dragging:
		return false
	_minimap_dragging = false
	return true


func _minimap_drag_active() -> bool:
	return _minimap_dragging


func _center_view_on_minimap(position: Vector2) -> void:
	var rect := _minimap_rect()
	var tile := MINIMAP_RULES.tile_at(position, rect, _map_size())
	_pan = MINIMAP_RULES.pan_for_center(tile, _canvas.size, TILE_SIZE * _zoom)
	_canvas.queue_redraw()


func _toggle_minimap() -> void:
	_minimap_visible = not _minimap_visible
	_minimap_dragging = false
	_minimap_button.set_block_signals(true)
	_minimap_button.button_pressed = _minimap_visible
	_minimap_button.set_block_signals(false)
	_canvas.queue_redraw()
	_set_status("Миникарта показана." if _minimap_visible else "Миникарта скрыта.")


func _draw_cell_key(canvas: Control, key: String, rect: Rect2, tint := Color.WHITE) -> void:
	var atlas_cell := _decode_atlas_cell(key)
	if not atlas_cell.is_empty():
		var atlas_sheet: Dictionary = _atlas_sheets_by_path.get(str(atlas_cell["path"]), {})
		var atlas_texture := _ensure_atlas_sheet_texture(str(atlas_cell["path"]))
		if atlas_texture != null:
			var source_coords: Vector2i = atlas_cell["coords"]
			source_coords = _current_atlas_animation_frame(atlas_sheet, source_coords)
			var source_tile_size := int(atlas_sheet.get("tile_size", ATLAS_TILE_SIZE))
			var source_rect := Rect2(Vector2(source_coords * source_tile_size), Vector2.ONE * source_tile_size)
			canvas.draw_texture_rect_region(atlas_texture, rect, source_rect, tint)
		return
	var item: Dictionary = _catalog_by_key.get(key, {})
	var destination := rect
	if str(item.get("kind", "")) == "object" \
		and str(item.get("representation", "")) == "sprite":
		destination.size *= Vector2(
			int(item.get("footprint_w", 1)),
			int(item.get("footprint_h", 1)),
		)
	var texture: Texture2D = _textures.get(key)
	if texture != null:
		canvas.draw_texture_rect(texture, destination, false, tint)
		return
	var color: Color = CATEGORY_COLORS.get(str(item.get("category", "")), Color(0.38, 0.39, 0.35))
	canvas.draw_rect(destination, color * tint)
	canvas.draw_rect(destination, Color(0.1, 0.1, 0.1, 0.5 * tint.a), false, 1.0)
	if not item.is_empty() and not _asset_requests.has(key):
		_request_texture(key)


func _draw_large_object_sprites(canvas: Control, tile_size: float) -> void:
	for layer in _layers:
		if not _is_layer_visible(layer) or str(layer.get("type", "")) != LAYER_OBJECT:
			continue
		for coord in layer.get("cells", {}):
			var key := str(layer["cells"][coord])
			var item: Dictionary = _catalog_by_key.get(key, {})
			if str(item.get("representation", "")) != "sprite":
				continue
			var parts := str(coord).split(":")
			if parts.size() != 2:
				continue
			var position := Vector2(int(parts[0]), int(parts[1]))
			var destination := Rect2(
				_pan + position * tile_size,
				Vector2(
					int(item.get("footprint_w", 1)),
					int(item.get("footprint_h", 1)),
				) * tile_size,
			)
			var texture: Texture2D = _textures.get(key)
			if texture != null:
				canvas.draw_texture_rect(texture, destination, false)


func _draw_selection_overlay(canvas: Control, tile_size: float) -> void:
	if not _selection.has_area():
		return
	var rect := Rect2(_pan + Vector2(_selection.position) * tile_size, Vector2(_selection.size) * tile_size)
	canvas.draw_rect(rect, SELECT_COLOR, false, 2.0)


func _draw_stamp_preview(canvas: Control, tile_size: float) -> void:
	if _active_tool != TOOL_STAMP or not _inside_map(_hover_cell) or _stamp_buffer.is_empty():
		return
	var tint := Color(1.0, 1.0, 1.0, 0.55)
	for part in _stamp_buffer["parts"]:
		for item in part["cells"]:
			var cell := _hover_cell + Vector2i(item[0], item[1])
			var rect := Rect2(_pan + Vector2(cell) * tile_size, Vector2.ONE * tile_size)
			_draw_cell_key(canvas, str(item[2]), rect, tint)
	var frame := Rect2(_pan + Vector2(_hover_cell) * tile_size, Vector2(int(_stamp_buffer["w"]), int(_stamp_buffer["h"])) * tile_size)
	canvas.draw_rect(frame, HOVER_COLOR, false, 2.0)


# Здание 5×5 клеток: спрайт по ширине пяти клеток, низ картинки — на нижней границе клетки точки.
func _draw_building_marker(canvas: Control, spawn: Dictionary, tile_size: float) -> void:
	var cell := Vector2i(int(spawn.get("x", 0)), int(spawn.get("y", 0)))
	var texture := _building_frame(str(spawn.get("sprite", "castle_8")), _building_anim_frame)
	var origin := _pan + Vector2(cell) * tile_size
	var width := float(BUILDING_FOOTPRINT_TILES) * tile_size
	if texture == null:
		canvas.draw_rect(Rect2(origin, Vector2.ONE * width), SPAWN_COLOR, false, 2.0)
		return
	var height := width * float(texture.get_height()) / float(texture.get_width())
	canvas.draw_texture_rect(texture, Rect2(origin.x + tile_size * 0.5 - width * 0.5, origin.y + tile_size - height, width, height), false)


func _draw_spawn_overlay(canvas: Control, tile_size: float) -> void:
	var radius := maxf(4.0, tile_size * 0.5)
	var font := ThemeDB.fallback_font
	var font_size := maxi(8, roundi(tile_size * 0.6))
	var type_numbers := {
		SPAWN_RULES.TYPE_HERO: 0,
		SPAWN_RULES.TYPE_MOB: 0,
	}
	for spawn in _spawns:
		var cell := Vector2i(int(spawn.get("x", -1)), int(spawn.get("y", -1)))
		if str(spawn.get("type", "")) == SPAWN_RULES.TYPE_BUILDING:
			_draw_building_marker(canvas, spawn, tile_size)
			continue
		var is_mob := str(spawn.get("type", SPAWN_RULES.TYPE_HERO)) == SPAWN_RULES.TYPE_MOB
		var spawn_type := SPAWN_RULES.TYPE_MOB if is_mob else SPAWN_RULES.TYPE_HERO
		type_numbers[spawn_type] += 1
		var center := _pan + (Vector2(cell) + Vector2(0.5, 0.5)) * tile_size
		var spawn_color := MOB_SPAWN_COLOR if is_mob else SPAWN_COLOR
		var text_color := Color.WHITE if is_mob else SPAWN_TEXT_COLOR
		canvas.draw_circle(center, radius, spawn_color)
		canvas.draw_arc(center, radius, 0.0, TAU, 32, SPAWN_OUTLINE_COLOR, 2.0)
		if tile_size >= 12.0:
			var label := str(spawn.get("name", type_numbers[spawn_type]))
			if label.is_valid_int():
				label = str(type_numbers[spawn_type])
			var label_size := font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size)
			var baseline := center + Vector2(-label_size.x * 0.5, (font.get_ascent(font_size) - font.get_descent(font_size)) * 0.5)
			canvas.draw_string(font, baseline, label, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, text_color)
	if _active_tool == TOOL_SPAWN and _inside_map(_hover_cell):
		var hover_rect := Rect2(_pan + Vector2(_hover_cell) * tile_size, Vector2.ONE * tile_size)
		canvas.draw_rect(hover_rect, HOVER_COLOR, false, 2.0)


func _draw_animal_instance(
	canvas: Control,
	group: Dictionary,
	cell_position: Vector2,
	tile_size: float,
) -> void:
	var states: Dictionary = group.get("states", {})
	var state: Dictionary = states.get(str(group.get("default_state", "")), {})
	var clips: Array = state.get("clips", [])
	if clips.is_empty():
		return
	var clip: Dictionary = clips[0]
	var sheet_path := str(clip.get("sheet_path", ""))
	var sheet: Dictionary = _atlas_sheets_by_path.get(sheet_path, {})
	var texture := _ensure_atlas_sheet_texture(sheet_path)
	var frames: Array = clip.get("frame_ids", [])
	var columns := int(sheet.get("columns", 0))
	if texture == null or frames.is_empty() or columns <= 0:
		return
	var frame_id := _current_animal_animation_tile(clip)
	if frame_id < 0:
		return
	var source_tile_size := int(sheet.get("tile_size", ATLAS_TILE_SIZE))
	var frame_size: Vector2i = clip.get("frame_size", Vector2i.ONE)
	var current_frame: Dictionary = {}
	for frame in frames:
		if int(frame.get("tile_id", -1)) == frame_id:
			current_frame = frame
			break
	var source_rect := Rect2i(
		Vector2i(frame_id % columns, frame_id / columns) * source_tile_size,
		frame_size * source_tile_size,
	)
	if current_frame.has("source_rect"):
		source_rect = current_frame["source_rect"]
	var destination_size := Vector2(frame_size) * tile_size
	var destination_position := _pan + cell_position * tile_size
	if current_frame.has("source_rect"):
		var native_size := Vector2(source_rect.size) * tile_size / float(source_tile_size)
		destination_position += Vector2(
			(destination_size.x - native_size.x) * 0.5,
			destination_size.y - native_size.y,
		)
		destination_size = native_size
	var destination := Rect2(destination_position, destination_size)
	canvas.draw_texture_rect_region(
		texture,
		destination,
		Rect2(Vector2(source_rect.position), Vector2(source_rect.size)),
	)


func _current_animal_animation_tile(clip: Dictionary) -> int:
	var frames: Array = clip.get("frame_ids", [])
	if frames.is_empty():
		return -1
	var cycle_duration := 0.0
	for frame in frames:
		cycle_duration += maxf(float(frame.get("duration", 100)), 1.0) / 1000.0
	if cycle_duration <= 0.0:
		return int(frames[0].get("tile_id", -1))
	var frame_time := fmod(float(Time.get_ticks_msec()) / 1000.0, cycle_duration)
	for frame in frames:
		frame_time -= maxf(float(frame.get("duration", 100)), 1.0) / 1000.0
		if frame_time < 0.0:
			return int(frame.get("tile_id", -1))
	return int(frames[0].get("tile_id", -1))


func _request_texture(key: String) -> void:
	var request := HTTPRequest.new()
	request.timeout = 20.0
	add_child(request)
	_asset_requests[key] = request
	request.request_completed.connect(_on_texture_loaded.bind(key, request))
	var url := ApiClient.base_url + _api_prefix + "/map/assets/" + key.uri_encode()
	var headers := PackedStringArray(["Authorization: Bearer " + ApiClient.token])
	var error := request.request(url, headers)
	if error != OK:
		_asset_requests.erase(key)
		request.queue_free()
		push_warning("Не удалось запросить изображение карты «%s»: %s" % [key, error_string(error)])


func _on_texture_loaded(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray, key: String, request: HTTPRequest) -> void:
	_asset_requests.erase(key)
	if result == HTTPRequest.RESULT_SUCCESS and response_code >= 200 and response_code < 300:
		var image := Image.new()
		var error := image.load_png_from_buffer(body)
		if error == OK:
			_textures[key] = ImageTexture.create_from_image(image)
		else:
			push_warning("Не удалось прочитать изображение карты «%s»." % key)
	else:
		push_warning("Сервер не вернул изображение карты «%s» (HTTP %d)." % [key, response_code])
	request.queue_free()
	_canvas.queue_redraw()


func _change_zoom(direction: int, mouse_position: Vector2) -> void:
	var old_zoom := _zoom
	_zoom = clampf(_zoom + float(direction) * 0.1, 0.4, 2.5)
	var map_position := (mouse_position - _pan) / (TILE_SIZE * old_zoom)
	_pan = mouse_position - map_position * (TILE_SIZE * _zoom)
	_canvas.queue_redraw()


func _set_pan_drag(pressed: bool, position: Vector2) -> void:
	_pan_dragging = pressed


func _pan_canvas(relative: Vector2) -> void:
	if _pan_dragging:
		_pan += relative
		_canvas.queue_redraw()
