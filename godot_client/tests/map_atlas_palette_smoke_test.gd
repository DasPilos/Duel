extends Node

const MAP_EDITOR = preload("res://scripts/map_editor.gd")
const ATLAS_PALETTE = preload("res://scripts/map_atlas_palette.gd")
const DISPLAY_SETTINGS = preload("res://scripts/display_settings.gd")
const ATLAS_ROOT := "res://assets/base_tails/Biome/craftpix-net-477432-flying-islands-pixel-art-top-down-tileset/Tiled_files"


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var editor = MAP_EDITOR.new()
	editor._build_ui()
	var side_panel_scroll: ScrollContainer = editor._layer_panel.get_parent()
	if editor._workspace_split.get_child_count() != 2 or editor._canvas_side_layout.get_child_count() != 2:
		push_error("Рабочая область редактора не разделена на растягиваемые панели.")
		editor.free()
		get_tree().quit(1)
		return
	if editor._canvas.custom_minimum_size != Vector2(550, 550) \
		or editor._canvas.size_flags_horizontal != Control.SIZE_SHRINK_CENTER \
		or editor._canvas.size_flags_vertical != Control.SIZE_SHRINK_CENTER \
		or editor._annotation_controls.get_parent() != editor._layer_panel \
		or editor._publish_group_button.get_parent() != editor._layer_panel \
		or editor._hero_spawn_button.get_parent() != editor._layer_panel \
		or editor._mob_spawn_button.get_parent() != editor._layer_panel \
		or editor._hero_spawn_button.text != "Возрождения · 0" \
		or editor._mob_spawn_button.text != "Появления ЛПС · 0" \
		or editor._layer_panel.custom_minimum_size.x != 170 \
		or side_panel_scroll.custom_minimum_size.x != 190 \
		or side_panel_scroll.horizontal_scroll_mode != ScrollContainer.SCROLL_MODE_DISABLED \
		or not side_panel_scroll.clip_contents \
		or editor._layer_list.size_flags_horizontal != Control.SIZE_EXPAND_FILL \
		or not editor._layer_list.clip_contents:
		push_error("Правая панель и список слоёв должны оставаться в границах окна.")
		editor.free()
		get_tree().quit(1)
		return
	editor._change_zoom(1, Vector2(200, 200))
	if editor._zoom <= 1.0 or editor._canvas.custom_minimum_size != Vector2(550, 550):
		push_error("Колесо должно масштабировать карту, не меняя фиксированный размер окна рисования.")
		editor.free()
		get_tree().quit(1)
		return
	editor._zoom = 1.0
	editor._create_loading_overlay()
	editor._set_loading_stage(
		"Загрузка биомов", editor.LOADING_TREE_SHEET, Vector2i(160, 160), 6, 0, false,
	)
	var loading_previews_valid: bool = editor._loading_preview_frames.size() == 6
	editor._set_loading_stage(
		"Загрузка мобов", editor.LOADING_GOLEM_SHEET, Vector2i(128, 128), 8,
		editor.LOADING_GOLEM_DIRECTION_ROW, true,
	)
	loading_previews_valid = loading_previews_valid \
		and editor._loading_preview_frames.size() == 8 \
		and (editor._loading_preview_frames[0] as AtlasTexture).region.position.y \
			== editor.LOADING_GOLEM_DIRECTION_ROW * 128 \
		and editor._loading_preview.size.x >= 140
	editor._set_loading_stage(
		"Загрузка героев", editor.LOADING_MAGE_SHEET, Vector2i(64, 64), 6, 0, true,
	)
	loading_previews_valid = loading_previews_valid \
		and editor._loading_preview_frames.size() == 6
	editor._set_loading_stage(
		"Загрузка пакетов", editor.LOADING_SMITH_SHEET, Vector2i(48, 48), 6, 0, false,
	)
	loading_previews_valid = loading_previews_valid \
		and editor._loading_preview_frames.size() == 6
	editor._set_loading_progress(43, "Загрузка мобов")
	editor._process(1.0)
	if editor._loading_progress.value != 43 \
		or not editor._loading_progress.show_percentage \
		or editor._loading_message.text != "Загрузка мобов" \
		or not loading_previews_valid \
		or editor._loading_preview.texture_filter != CanvasItem.TEXTURE_FILTER_NEAREST:
		push_error("Экран загрузки должен показывать этап, прогресс и чёткую анимацию дерева.")
		editor.free()
		get_tree().quit(1)
		return
	if not is_equal_approx(editor._ui_root.theme.default_base_scale, 0.5):
		push_error("Масштаб интерфейса редактора не соответствует половине исходного.")
		editor.free()
		get_tree().quit(1)
		return
	if editor._ui_root.theme.default_font_size != 8:
		push_error("Размер шрифта интерфейса редактора не соответствует половине исходного.")
		editor.free()
		get_tree().quit(1)
		return
	if editor._sheet_tabs_scroll.vertical_scroll_mode != ScrollContainer.SCROLL_MODE_AUTO \
		or editor._workspace_split.split_offset != 0:
		push_error("Список листов должен прокручиваться вертикально, а рабочая область — делить место между палитрой и холстом.")
		editor.free()
		get_tree().quit(1)
		return
	if editor._auto_brush_button.text != "Автокисть" or editor._brush_button.text != "Кисть":
		push_error("Над холстом отсутствуют переключатели обычной и автоматической кисти.")
		editor.free()
		get_tree().quit(1)
		return
	if editor._corner_variant_select.item_count != 264 \
		or editor._autotile_mask_title(65) != "Маска 065 .#./#@./..." \
		or editor._corner_variant_assign_button.text != "Назначить тайл" \
		or not editor._corner_variant_assign_button.toggle_mode \
		or editor._corner_variant_clear_button.text != "Сбросить" \
		or editor._terrain_generation_button.text != "Генерировать карту":
		push_error("В панели автокисти отсутствуют 256 масок соседей и фиксируемый режим назначения тайла.")
		editor.free()
		get_tree().quit(1)
		return
	if editor._ui_root.get_child(0) is not HFlowContainer \
		or editor._ui_root.get_child(1) is not HFlowContainer \
		or editor._map_name.size_flags_horizontal == Control.SIZE_EXPAND_FILL \
		or editor._saved_select.size_flags_horizontal == Control.SIZE_EXPAND_FILL \
		or editor._map_name.custom_minimum_size.x != 65 \
		or editor._saved_select.custom_minimum_size.x != 60:
		push_error("Верхние панели должны компактно переносить пункты меню и не разъезжаться.")
		editor.free()
		get_tree().quit(1)
		return
	if editor._save_draft_button.text != "Сохранить" \
		or editor._load_draft_button.text != "Загрузить" \
		or editor._refresh_drafts_button.text != "Обновить" \
		or not editor._save_draft_button.pressed.is_connected(editor._save_map) \
		or not editor._load_draft_button.pressed.is_connected(editor._load_selected_map) \
		or not editor._refresh_drafts_button.pressed.is_connected(editor._load_saved_maps):
		push_error("В верхней панели отсутствуют рабочие кнопки сохранения и загрузки черновиков.")
		editor.free()
		get_tree().quit(1)
		return
	editor._saved_maps.clear()
	editor._saved_maps.append({
		"id": 19,
		"name": "Проверка черновика",
		"map_w": 64,
		"map_h": 32,
	})
	editor._render_saved_maps()
	if editor._saved_select.item_count != 2 \
		or int(editor._saved_select.get_item_metadata(1)) != 19:
		push_error("Черновики не отображаются в списке загрузки.")
		editor.free()
		get_tree().quit(1)
		return
	editor._create_default_layers()
	editor._render_layers()
	if editor._layer_type.get_item_text(3) != "Слой животных" \
		or editor._layer_type.get_item_text(4) != "Слой мобов" \
		or str(editor._layers[2].get("type", "")) != editor.LAYER_ANIMAL \
		or str(editor._layers[3].get("type", "")) != editor.LAYER_MOB:
		push_error("Для животных и мобов не созданы отдельные типы и слои.")
		editor.free()
		get_tree().quit(1)
		return
	var mob_layer_id := int(editor._layers[3]["id"])
	editor._on_layer_visibility_toggled(mob_layer_id)
	if bool(editor._get_layer(mob_layer_id).get("visible", true)):
		push_error("Кнопка скрытия не скрыла слой мобов.")
		editor.free()
		get_tree().quit(1)
		return
	editor._on_layer_visibility_toggled(mob_layer_id)
	if not bool(editor._get_layer(mob_layer_id).get("visible", false)):
		push_error("Повторное нажатие кнопки не вернуло слой мобов.")
		editor.free()
		get_tree().quit(1)
		return
	var ground_layer_id := int(editor._layers[0]["id"])
	var layer_row: Dictionary = editor._layer_list.get_row(ground_layer_id)
	if layer_row.is_empty() \
		or not layer_row["eye"] is Button \
		or bool(layer_row["eye"].get_meta("hidden")) \
		or str(layer_row["number"].text) != "1":
		push_error("В строке слоя должны быть номер и кнопка скрытия, не подсвеченная у видимого слоя.")
		editor.free()
		get_tree().quit(1)
		return
	editor._set_layer_visibility(ground_layer_id, false)
	if editor._is_layer_visible(editor._get_layer(ground_layer_id)):
		push_error("Кнопка скрытия не скрыла слой на холсте.")
		editor.free()
		get_tree().quit(1)
		return
	layer_row = editor._layer_list.get_row(ground_layer_id)
	if not bool(layer_row["eye"].get_meta("hidden")):
		push_error("Кнопка скрытия не подсвечена у скрытого слоя.")
		editor.free()
		get_tree().quit(1)
		return
	editor._undo_last_action()
	if not editor._is_layer_visible(editor._get_layer(ground_layer_id)):
		push_error("Ctrl+Z не восстановил видимость слоя.")
		editor.free()
		get_tree().quit(1)
		return
	var object_layer_id := int(editor._layers[1]["id"])
	editor._active_layer_id = object_layer_id
	editor._set_layer_visibility(object_layer_id, false)
	if editor._active_layer_id != ground_layer_id \
		or not editor._is_layer_visible(editor._get_layer(editor._active_layer_id)):
		push_error("При скрытии активного слоя объектов редактор не выбрал видимый слой.")
		editor.free()
		get_tree().quit(1)
		return
	editor._catalog_by_key["visibility_smoke"] = {
		"item_key": "visibility_smoke",
		"category": "grass",
	}
	editor._selected_item_key = "visibility_smoke"
	editor._last_stroke_cell = Vector2i(-1, -1)
	editor._paint_canvas_cell(Vector2i(0, 0))
	if str(editor._get_layer(ground_layer_id)["cells"].get("0:0", "")) != "visibility_smoke":
		push_error("Рисование не продолжилось на видимом слое после скрытия объектов.")
		editor.free()
		get_tree().quit(1)
		return
	editor._active_layer_id = object_layer_id
	editor._last_stroke_cell = Vector2i(-1, -1)
	editor._paint_canvas_cell(Vector2i(1, 0))
	if editor._get_layer(object_layer_id)["cells"].has("1:0"):
		push_error("Скрытый слой объектов остался доступен для рисования.")
		editor.free()
		get_tree().quit(1)
		return
	editor._set_layer_visibility(object_layer_id, true)
	editor._get_layer(ground_layer_id)["cells"].erase("0:0")
	editor._active_layer_id = ground_layer_id
	editor._selected_item_key = ""
	editor._render_layers()
	if DISPLAY_SETTINGS.DEFAULT_RESOLUTION != Vector2i(1920, 1080):
		push_error("Стандартное разрешение запуска должно быть 1920×1080.")
		editor.free()
		get_tree().quit(1)
		return
	var settings = DISPLAY_SETTINGS.new()
	var settings_path := "user://display_settings_smoke.cfg"
	var settings_config := ConfigFile.new()
	settings_config.set_value("display", "resolution", [1280, 720])
	if settings_config.save(settings_path) != OK:
		push_error("Не удалось создать файл проверки разрешения.")
		editor.free()
		get_tree().quit(1)
		return
	settings._load_settings(settings_path)
	if settings._settings["resolution"] != Vector2i(1920, 1080):
		push_error("Старое стандартное разрешение не обновилось до 1920×1080.")
		_cleanup_settings(settings_path)
		editor.free()
		get_tree().quit(1)
		return
	_cleanup_settings(settings_path)
	settings.free()
	await editor._discover_atlas_sheets()
	if editor._atlas_sheets.size() < 17 or editor._sheet_tabs.get_child_count() != editor._sheet_buttons.size() + 1:
		push_error("Не все листы биомов появились в вертикальном списке.")
		editor.free()
		get_tree().quit(1)
		return
	if editor._biome_list.get_child_count() < 10:
		push_error("Не все наборы биомов отображаются в боковом списке.")
		editor.free()
		get_tree().quit(1)
		return
	var craftpix_directory := DirAccess.open(editor.CRAFTPIX_PACK_ROOT)
	var craftpix_pack_count := 0
	if craftpix_directory != null:
		for pack_folder in craftpix_directory.get_directories():
			var pack_path: String = editor.CRAFTPIX_PACK_ROOT.path_join(pack_folder)
			var pack_images: Array[String] = editor._craftpix_pack_png_files(pack_path)
			if pack_images.is_empty():
				continue
			craftpix_pack_count += 1
			var pack_button: Button = editor._biome_buttons.get(pack_path)
			var loaded_images := 0
			for image_path in pack_images:
				if editor._atlas_sheets_by_path.has(image_path):
					loaded_images += 1
			if pack_button == null or pack_button.text != editor._craftpix_pack_display_name(pack_folder) \
				or loaded_images != pack_images.size():
				push_error("Пакет Craftpix «%s» должен иметь подписанный раздел со всеми PNG-листами." % pack_folder)
				editor.free()
				get_tree().quit(1)
				return
	if craftpix_pack_count != 24:
		push_error("В общей палитре должны отображаться все 24 пакета Craftpix.")
		editor.free()
		get_tree().quit(1)
		return
	var temple_pack_path: String = editor.CRAFTPIX_PACK_ROOT.path_join(
		"craftpix-net-160005-free-ruined-temple-top-down-location-pixel-art",
	)
	var temple_animation_path := temple_pack_path + "|animated"
	var temple_animation_button: Button = editor._biome_buttons.get(temple_animation_path)
	var cultist_key := editor._animal_instance_key(
		"craftpix-net-160005-free-ruined-temple-top-down-location-pixel-art",
		"cultist1",
	)
	var cultist_group: Dictionary = editor._animal_groups_by_key.get(cultist_key, {})
	if temple_animation_button == null or cultist_group.is_empty() \
		or editor._animal_palette.get_script() != load("res://scripts/map_animated_palette.gd") \
		or editor._animal_instance_frame_size(cultist_group) != Vector2i(2, 2):
		push_error("Анимации персонажей пакета должны собираться в цельные спрайты.")
		editor.free()
		get_tree().quit(1)
		return
	for required_state in ["idle", "walk"]:
		var cultist_state: Dictionary = cultist_group.get("states", {}).get(required_state, {})
		var cultist_clips: Array = cultist_state.get("clips", [])
		if cultist_clips.size() != 4 or cultist_clips[0].get("frame_ids", []).size() != 12:
			push_error("Анимация «%s» персонажа должна содержать четыре направления и 12 кадров." % required_state)
			editor.free()
			get_tree().quit(1)
			return
	editor._select_animated_pack(temple_pack_path, temple_animation_path, temple_animation_button)
	var cultist_palette_item := -1
	for index in editor._animal_palette.item_count:
		if str(editor._animal_palette.get_item_metadata(index)) == cultist_key:
			cultist_palette_item = index
			break
	if not editor._animal_palette.visible or cultist_palette_item < 0:
		push_error("Собранный спрайт должен быть доступен в отдельной палитре анимаций пакета.")
		editor.free()
		get_tree().quit(1)
		return
	var dungeon_pack_folder := "craftpix-net-169442-free-2d-top-down-pixel-dungeon-asset-pack"
	var dungeon_pack_path: String = editor.CRAFTPIX_PACK_ROOT.path_join(dungeon_pack_folder)
	var fire_animation_path := dungeon_pack_path + "|animated"
	var fire_animation_button: Button = editor._biome_buttons.get(fire_animation_path)
	if fire_animation_button == null:
		push_error("Пакет с вертикальными огненными анимациями должен иметь раздел готовых анимаций.")
		editor.free()
		get_tree().quit(1)
		return
	var fire_variant_x_positions: Dictionary = {}
	for variant_index in 4:
		var fire_key := editor._animal_instance_key(dungeon_pack_folder, "fire_%d" % (variant_index + 1))
		var fire_group: Dictionary = editor._animal_groups_by_key.get(fire_key, {})
		var fire_clips: Array = fire_group.get("states", {}).get("animation", {}).get("clips", [])
		if fire_clips.size() != 1 or fire_clips[0].get("frame_ids", []).size() != 6 \
			or not str(fire_clips[0].get("sheet_path", "")).to_lower().contains("/tiled_files/"):
			push_error("Каждый вертикальный эффект огня должен получить отдельный клип из шести кадров с метаданными.")
			editor.free()
			get_tree().quit(1)
			return
		var fire_frames: Array = fire_clips[0]["frame_ids"]
		var first_rect: Rect2i = fire_frames[0].get("source_rect", Rect2i())
		var last_rect: Rect2i = fire_frames[5].get("source_rect", Rect2i())
		if first_rect.size.x <= 0 or first_rect.size.y != 48 \
			or last_rect.position.y - first_rect.position.y != 240:
			push_error("Кадры вертикальной анимации должны вырезаться сверху вниз с правильным размером.")
			editor.free()
			get_tree().quit(1)
			return
		fire_variant_x_positions[first_rect.position.x] = true
	if fire_variant_x_positions.size() != 4:
		push_error("Четыре анимации огня должны быть разделены по отдельным колонкам.")
		editor.free()
		get_tree().quit(1)
		return
	for second_variant_index in 3:
		var second_fire_key := editor._animal_instance_key(
			dungeon_pack_folder,
			"fire_2_%d" % (second_variant_index + 1),
		)
		var second_fire_group: Dictionary = editor._animal_groups_by_key.get(second_fire_key, {})
		var second_fire_clips: Array = second_fire_group.get("states", {}).get("animation", {}).get("clips", [])
		if second_fire_clips.size() != 1 or second_fire_clips[0].get("frame_ids", []).size() != 3:
			push_error("Второй вертикальный лист огня должен собрать отдельные варианты по три кадра.")
			editor.free()
			get_tree().quit(1)
			return
		var second_fire_frames: Array = second_fire_clips[0]["frame_ids"]
		var second_first_rect: Rect2i = second_fire_frames[0].get("source_rect", Rect2i())
		var second_last_rect: Rect2i = second_fire_frames[2].get("source_rect", Rect2i())
		if second_first_rect.size.y != 64 or second_last_rect.position.y - second_first_rect.position.y != 128:
			push_error("Второй вертикальный лист огня должен сохранять высоту и порядок кадров.")
			editor.free()
			get_tree().quit(1)
			return
	for temple_variant_index in 3:
		var temple_fire_key := editor._animal_instance_key(
			"craftpix-net-160005-free-ruined-temple-top-down-location-pixel-art",
			"fire_%d" % (temple_variant_index + 1),
		)
		var temple_fire_group: Dictionary = editor._animal_groups_by_key.get(temple_fire_key, {})
		var temple_fire_clips: Array = temple_fire_group.get("states", {}).get("animation", {}).get("clips", [])
		if temple_fire_clips.size() != 1 or temple_fire_clips[0].get("frame_ids", []).size() != 6:
			push_error("Огненные варианты с движущимися прозрачными свечениями должны разделяться отдельно.")
			editor.free()
			get_tree().quit(1)
			return
		var temple_fire_frames: Array = temple_fire_clips[0]["frame_ids"]
		var temple_first_rect: Rect2i = temple_fire_frames[0].get("source_rect", Rect2i())
		var temple_last_rect: Rect2i = temple_fire_frames[5].get("source_rect", Rect2i())
		if temple_first_rect.size.y != 80 or temple_last_rect.position.y - temple_first_rect.position.y != 400:
			push_error("Кадры второго вертикального листа огня должны быть собраны по пятистрочному шагу.")
			editor.free()
			get_tree().quit(1)
			return
	var chief_sheet_path: String = editor.CRAFTPIX_PACK_ROOT.path_join(
		"craftpix-net-659586-fantasy-rpg-prison-top-down-pixel-art-pack",
	).path_join("Tiled_files").path_join("Chief_idle.png")
	var chief_sheet: Dictionary = editor._atlas_sheets_by_path.get(chief_sheet_path, {})
	var chief_vertical_clips: Array[Dictionary] = editor._craftpix_vertical_animation_clips(
		chief_sheet_path,
		chief_sheet,
	)
	if chief_vertical_clips.size() != 2 or chief_vertical_clips[0].get("frame_ids", []).size() != 6 \
		or chief_vertical_clips[0].get("frame_size") != Vector2i(3, 4):
		push_error("Повторяющиеся кадры вертикальной анимации должны объединяться с длительностью и размером спрайта.")
		editor.free()
		get_tree().quit(1)
		return
	var vampire_pack_path: String = editor.LPC_ROOT.path_join(
		"craftpix-net-208004-free-vampire-4-direction-pixel-character-sprite-pack",
	)
	var vampire_key := editor._mob_instance_key(
		"craftpix-net-208004-free-vampire-4-direction-pixel-character-sprite-pack",
		"vampires1",
	)
	var vampire_group: Dictionary = editor._animal_groups_by_key.get(vampire_key, {})
	if vampire_group.is_empty() or vampire_group.get("states", {}).get("walk", {}).get("clips", []).is_empty():
		push_error("Готовые LPC-листы должны давать цельную анимацию существа.")
		editor.free()
		get_tree().quit(1)
		return
	var cave_pack_path: String = editor.CRAFTPIX_PACK_ROOT.path_join(
		"craftpix-net-548007-glowing-cave-objects-pixel-art-asset-pack",
	)
	var cave_sheet_path: String = cave_pack_path.path_join("PNG").path_join("Blue_crystal1.png")
	var cave_button: Button = editor._biome_buttons.get(cave_pack_path)
	var cave_sheet: Dictionary = editor._atlas_sheets_by_path.get(cave_sheet_path, {})
	if cave_button == null or cave_sheet.is_empty() or cave_sheet.get("texture") != null:
		push_error("Листы пакетов должны появляться в палитре без предварительной загрузки всех текстур.")
		editor.free()
		get_tree().quit(1)
		return
	editor._select_biome(cave_pack_path, cave_button)
	cave_sheet = editor._atlas_sheets_by_path.get(cave_sheet_path, {})
	if cave_sheet.get("texture") == null or editor._atlas_palette.atlas_columns != 8 \
		or editor._atlas_palette.atlas_rows != 8:
		push_error("При выборе пакета изображение должно загружаться и отображаться как атлас.")
		editor.free()
		get_tree().quit(1)
		return
	var bridge_pack_path: String = editor.BRIDGES_ROOT.path_join(
		"craftpix-net-668008-free-bridges-top-down-pixel-art-asset-pack",
	)
	var bridge_sheet_path: String = bridge_pack_path.path_join("PNG_n_Tiled").path_join("Bridges.png")
	var initial_biome_path: String = editor._selected_biome_path
	var bridge_button: Button = editor._biome_buttons.get(bridge_pack_path)
	var bridge_sheet: Dictionary = editor._atlas_sheets_by_path.get(bridge_sheet_path, {})
	if bridge_button == null or bridge_button.text != "Мосты" \
		or bridge_sheet.is_empty() or str(bridge_sheet.get("category", "")) != "Мосты" \
		or int(bridge_sheet.get("tile_size", 0)) != 16 \
		or int(bridge_sheet.get("columns", 0)) != 41 \
		or int(bridge_sheet.get("rows", 0)) != 42:
		push_error("Атлас мостов должен появиться в палитре с сеткой тайлов 16×16.")
		editor.free()
		get_tree().quit(1)
		return
	editor._select_biome(bridge_pack_path, bridge_button)
	if not bridge_button.button_pressed or not editor._atlas_scroll.visible \
		or editor._animal_palette.visible \
		or not editor._sheet_buttons[bridge_sheet_path].visible \
		or editor._atlas_palette.atlas_columns != 41 \
		or editor._atlas_palette.atlas_rows != 42:
		push_error("Выбор набора «Мосты» должен открыть мостовой атлас в редакторе.")
		editor.free()
		get_tree().quit(1)
		return
	var swordsman_button: Button = editor._biome_buttons.get(editor.SWORDSMAN_ROOT)
	if swordsman_button == null or swordsman_button.text != "Воин":
		push_error("В разделе «Герои» должен отображаться подраздел «Воин».")
		editor.free()
		get_tree().quit(1)
		return
	var hero_section_found := false
	var warrior_label_found := false
	for child in editor._biome_list.get_children():
		if child is Label and child.text == "Герои":
			hero_section_found = true
		elif child is Label and child.text == "Воин":
			warrior_label_found = true
	if not hero_section_found or warrior_label_found:
		push_error("Палитра должна показывать раздел «Герои» и подраздел «Воин» без лишнего уровня.")
		editor.free()
		get_tree().quit(1)
		return
	var mage_button: Button = editor._biome_buttons.get(editor.MAGE_ROOT)
	if mage_button == null or mage_button.text != "Маг":
		push_error("В разделе «Герои» должен отображаться отдельный подраздел «Маг».")
		editor.free()
		get_tree().quit(1)
		return
	editor._select_biome(editor.MAGE_ROOT, mage_button)
	if not editor._animal_palette.visible or editor._animal_palette.item_count != 9:
		push_error("В палитре мага должны отображаться все девять уровней.")
		editor.free()
		get_tree().quit(1)
		return
	for level in range(1, 10):
		var mage_key := editor._animal_instance_key("mage", "mage_lvl%d" % level)
		var mage_group: Dictionary = editor._animal_groups_by_key.get(mage_key, {})
		var mage_states: Dictionary = mage_group.get("states", {})
		var mage_idle: Dictionary = mage_states.get("idle", {})
		var mage_clips: Array = mage_idle.get("clips", [])
		var mage_icon: Texture2D = editor._animal_group_icon(mage_group)
		if mage_icon == null or mage_group.is_empty() \
			or str(mage_group.get("kind", "")) != "hero" \
			or str(mage_group.get("name", "")) != "Маг · уровень %d" % level \
			or mage_clips.size() != 4 \
			or mage_clips[0].get("frame_size", Vector2i.ZERO) != Vector2i(4, 4):
			push_error("Не собран анимированный спрайт мага уровня %d." % level)
			editor.free()
			get_tree().quit(1)
			return
		for required_action in ["walk", "run", "attack", "hurt", "death"]:
			if mage_states.get(required_action, {}).get("clips", []).size() != 4:
				push_error("У мага уровня %d отсутствует действие «%s»." % [
					level, required_action,
				])
				editor.free()
				get_tree().quit(1)
				return
	var archer_button: Button = editor._biome_buttons.get(editor.ARCHER_ROOT)
	if archer_button == null or archer_button.text != "Лучник":
		push_error("В разделе «Герои» должен отображаться отдельный подраздел «Лучник».")
		editor.free()
		get_tree().quit(1)
		return
	editor._select_biome(editor.ARCHER_ROOT, archer_button)
	if not editor._animal_palette.visible or editor._animal_palette.item_count != 9:
		push_error("В палитре лучника должны отображаться все девять уровней.")
		editor.free()
		get_tree().quit(1)
		return
	for level in range(1, 10):
		var archer_key := editor._animal_instance_key("archer", "archer_lvl%d" % level)
		var archer_group: Dictionary = editor._animal_groups_by_key.get(archer_key, {})
		var archer_states: Dictionary = archer_group.get("states", {})
		var archer_idle: Dictionary = archer_states.get("idle", {})
		var archer_clips: Array = archer_idle.get("clips", [])
		var archer_icon: Texture2D = editor._animal_group_icon(archer_group)
		if archer_icon == null or archer_group.is_empty() \
			or str(archer_group.get("kind", "")) != "hero" \
			or str(archer_group.get("name", "")) != "Лучник · уровень %d" % level \
			or archer_clips.size() != 4 \
			or archer_clips[0].get("frame_size", Vector2i.ZERO) != Vector2i(4, 4):
			push_error("Не собран анимированный спрайт лучника уровня %d." % level)
			editor.free()
			get_tree().quit(1)
			return
		for required_action in ["walk", "run", "attack", "hurt", "death"]:
			if archer_states.get(required_action, {}).get("clips", []).size() != 4:
				push_error("У лучника уровня %d отсутствует действие «%s»." % [
					level, required_action,
				])
				editor.free()
				get_tree().quit(1)
				return
	editor._select_biome(editor.SWORDSMAN_ROOT, swordsman_button)
	if not editor._animal_palette.visible or editor._animal_palette.item_count != 9:
		push_error("В палитре мечника должны отображаться все девять уровней.")
		editor.free()
		get_tree().quit(1)
		return
	for level in range(1, 10):
		var hero_key := editor._animal_instance_key("swordsman", "swordsman_lvl%d" % level)
		var hero_group: Dictionary = editor._animal_groups_by_key.get(hero_key, {})
		var hero_states: Dictionary = hero_group.get("states", {})
		var idle_state: Dictionary = hero_states.get("idle", {})
		var idle_clips: Array = idle_state.get("clips", [])
		var hero_icon: Texture2D = editor._animal_group_icon(hero_group)
		var icon_image := hero_icon.get_image() if hero_icon != null else null
		var visible_pixels := 0
		if icon_image != null:
			for y in range(icon_image.get_height()):
				for x in range(icon_image.get_width()):
					if icon_image.get_pixel(x, y).a > 0.0:
						visible_pixels += 1
		if hero_group.is_empty() or str(hero_group.get("kind", "")) != "hero" \
			or str(hero_group.get("name", "")) != "Мечник · уровень %d" % level \
			or idle_clips.size() != 4 \
			or idle_clips[0].get("frame_size", Vector2i.ZERO) != Vector2i(4, 4) \
			or visible_pixels == 0:
			push_error("Не собран анимированный спрайт мечника уровня %d." % level)
			editor.free()
			get_tree().quit(1)
			return
		for required_action in ["walk", "run", "attack", "hurt", "death"]:
			if hero_states.get(required_action, {}).get("clips", []).size() != 4:
				push_error("У мечника уровня %d отсутствует действие «%s»." % [
					level, required_action,
				])
				editor.free()
				get_tree().quit(1)
				return
	editor._select_biome(initial_biome_path, editor._biome_buttons[initial_biome_path])
	editor._on_atlas_tile_selected(Vector2i(1, 1))
	if editor._selected_atlas_path != bridge_sheet_path \
		or editor._selected_atlas_coords != Vector2i(1, 1) \
		or editor._selected_item_key.is_empty():
		push_error("Тайлы мостового атласа должны выбираться обычным инструментом редактора.")
		editor.free()
		get_tree().quit(1)
		return
	editor._select_biome(initial_biome_path, editor._biome_buttons[initial_biome_path])
	var ground_sheet: Dictionary = editor._atlas_sheets_by_path.get(ATLAS_ROOT.path_join("Ground_grass.png"), {})
	if ground_sheet.is_empty() or str(ground_sheet["category"]) != "Почва":
		push_error("Лист Ground_grass не получил категорию «Почва».")
		editor.free()
		get_tree().quit(1)
		return
	if str(ground_sheet.get("biome_name", "")) != "Летающие острова":
		push_error("Лист Ground_grass не связан с биомом летающих островов.")
		editor.free()
		get_tree().quit(1)
		return
	var visible_flying_sheets := 0
	for sheet_path in editor._sheet_buttons:
		if editor._sheet_buttons[sheet_path].visible:
			visible_flying_sheets += 1
	if visible_flying_sheets != 17:
		push_error("Выбранный биом должен показывать только свои листы тайлов.")
		editor.free()
		get_tree().quit(1)
		return
	var winter_biome_path := ""
	for candidate_path in editor._biome_buttons:
		if candidate_path.get_file() == "winter":
			winter_biome_path = candidate_path
			break
	if winter_biome_path.is_empty():
		push_error("Не найден биом «Зима» для проверки переключения палитры.")
		editor.free()
		get_tree().quit(1)
		return
	editor._select_biome(winter_biome_path, editor._biome_buttons[winter_biome_path])
	var visible_winter_sheets := 0
	for sheet_path in editor._sheet_buttons:
		if editor._sheet_buttons[sheet_path].visible:
			visible_winter_sheets += 1
	if visible_winter_sheets != 7:
		push_error("При выборе другого биома список листов не переключился.")
		editor.free()
		get_tree().quit(1)
		return
	var animal_pack_path := ""
	for candidate_path in editor._biome_buttons:
		if candidate_path.get_file() == "craftpix-net-596440-fishing-and-gathering-pixel-art-rpg-icons":
			animal_pack_path = candidate_path
			break
	if animal_pack_path.is_empty():
		push_error("В палитре не появился отдельный раздел рыб и животных.")
		editor.free()
		get_tree().quit(1)
		return
	editor._select_biome(animal_pack_path, editor._biome_buttons[animal_pack_path])
	var visible_animal_sheets := 0
	for sheet_path in editor._sheet_buttons:
		if editor._sheet_buttons[sheet_path].visible:
			visible_animal_sheets += 1
	if visible_animal_sheets != 0 or not editor._animal_palette.visible \
		or editor._animal_palette.item_count != 10:
		push_error("Раздел рыб должен показывать десять готовых спрайтов, а не листы тайлов.")
		editor.free()
		get_tree().quit(1)
		return
	if editor._animal_palette.custom_maximum_size.x == 0:
		push_error("Список животных ограничен нулевой шириной и не будет виден на экране.")
		editor.free()
		get_tree().quit(1)
		return
	var fish_sheet_path := animal_pack_path.path_join("PNG_n_Tiled").path_join("Fish1.png")
	var fish_sheet: Dictionary = editor._atlas_sheets_by_path.get(fish_sheet_path, {})
	if fish_sheet.is_empty() or int(fish_sheet.get("tile_size", 0)) != 16 \
		or fish_sheet.get("animations", {}).is_empty():
		push_error("Лист рыб не был загружен как атлас с сеткой тайлов 16×16.")
		editor.free()
		get_tree().quit(1)
		return
	var fish_key := editor._animal_instance_key(animal_pack_path.get_file(), "fish1")
	var fish_group: Dictionary = editor._animal_groups_by_key.get(fish_key, {})
	var fish_state: Dictionary = fish_group.get("states", {}).get("animation", {})
	var fish_clips: Array = fish_state.get("clips", [])
	if fish_group.is_empty() or fish_clips.is_empty() \
		or Vector2i(fish_clips[0].get("frame_size", Vector2i.ZERO)).x <= 1 \
		or editor._animal_palette.get_item_icon(0) == null:
		push_error("Fish1 не собран в цельный анимированный спрайт с миниатюрой.")
		editor.free()
		get_tree().quit(1)
		return
	var animal_settings_path := "user://animal_settings_smoke.cfg"
	editor._animal_settings_config_path = animal_settings_path
	if not editor._save_animal_brush_settings(fish_key, "economy", 7) \
		or not editor._save_animal_brush_settings(fish_key, "economy", 3) \
		or editor._animal_brush_radius(fish_key, "economy") != 7 \
		or editor._animal_brush_radius(fish_key, "economy") != 3:
		push_error("Радиус патруля не сохраняется отдельно для режимов игры.")
		_cleanup_settings(animal_settings_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._animal_brush_settings.clear()
	if editor._load_animal_brush_settings(animal_settings_path) != OK \
		or editor._animal_brush_radius(fish_key, "economy") != 7 \
		or editor._animal_brush_radius(fish_key, "economy") != 3:
		push_error("Настройки патруля не загрузились из файла.")
		_cleanup_settings(animal_settings_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._mode = "economy"
	var boar_pack_path := ""
	for candidate_path in editor._biome_buttons:
		if candidate_path.get_file() == "craftpix-net-789196-free-top-down-hunt-animals-pixel-sprite-pack":
			boar_pack_path = candidate_path
			break
	var boar_key := editor._animal_instance_key(boar_pack_path.get_file(), "boar")
	var boar_group: Dictionary = editor._animal_groups_by_key.get(boar_key, {})
	var boar_states: Dictionary = boar_group.get("states", {})
	for required_state in ["idle", "walk", "run", "attack", "hurt", "death"]:
		if not boar_states.has(required_state) or boar_states[required_state]["clips"].is_empty():
			push_error("У дикого кабана потеряно движение «%s»." % required_state)
			editor.free()
			get_tree().quit(1)
			return
		if boar_states[required_state]["clips"].size() < 4:
			push_error("У движения «%s» дикого кабана потеряны направления." % required_state)
			editor.free()
			get_tree().quit(1)
			return
	for animal_group in editor._animal_groups:
		for state_name in animal_group["states"]:
			if animal_group["states"][state_name]["clips"].is_empty():
				push_error("У спрайта «%s» нет кадров движения «%s»." % [
					animal_group["name"], state_name,
				])
				editor.free()
				get_tree().quit(1)
				return
		if editor._animal_group_icon(animal_group) == null:
			push_error("Не создана миниатюра готового спрайта «%s»." % animal_group["name"])
			editor.free()
			get_tree().quit(1)
			return
	var lpc_pack_count := 0
	for pack_path in editor._biome_buttons:
		if str(pack_path).begins_with(editor.LPC_ROOT + "/"):
			lpc_pack_count += 1
	if lpc_pack_count != 21:
		push_error("В палитру LPC должны попасть все 21 набор мобов (волки убраны); найдено %d." % lpc_pack_count)
		editor.free()
		get_tree().quit(1)
		return
	for pack_path in editor._biome_buttons:
		if not str(pack_path).begins_with(editor.LPC_ROOT + "/"):
			continue
		var pack_group_count := 0
		for mob_group in editor._animal_groups:
			if str(mob_group.get("pack_path", "")) == str(pack_path):
				pack_group_count += 1
		if pack_group_count == 0:
			push_error("Для набора LPC «%s» не создано ни одного моба." % pack_path)
			editor.free()
			get_tree().quit(1)
			return
		var pack_button: Button = editor._biome_buttons[pack_path]
		pack_button.emit_signal("pressed")
		if not editor._animal_palette.visible or editor._animal_palette.item_count != pack_group_count \
			or editor._atlas_scroll.visible or editor._palette.visible:
			push_error("Набор LPC «%s» не переключает центральную панель на мобов." % pack_path)
			editor.free()
			get_tree().quit(1)
			return
	var gnoll_folder := "craftpix-net-393827-top-down-pixel-gnolls-character-pack"
	var gnoll_key := editor._mob_instance_key(gnoll_folder, "gnoll1")
	var gnoll_group: Dictionary = editor._animal_groups_by_key.get(gnoll_key, {})
	var gnoll_states: Dictionary = gnoll_group.get("states", {})
	var gnoll_attack: Dictionary = gnoll_states.get("attack", {})
	var gnoll_attack_clips: Array = gnoll_attack.get("clips", [])
	var gnoll_preview: Array = editor._animal_palette_preview_sequence(gnoll_group)
	var gnoll_preview_ok: bool = gnoll_preview.size() == gnoll_states.size() * editor.ANIMAL_DIRECTION_ORDER.size()
	for gnoll_step in range(gnoll_preview.size()):
		if not gnoll_preview_ok:
			break
		var gnoll_entry: Dictionary = gnoll_preview[gnoll_step]
		var gnoll_first: Dictionary = gnoll_preview[gnoll_step - gnoll_step % editor.ANIMAL_DIRECTION_ORDER.size()]
		gnoll_preview_ok = str(gnoll_entry.get("state", "")) == str(gnoll_first.get("state", "")) \
			and str(gnoll_entry.get("direction", "")) \
				== str(editor.ANIMAL_DIRECTION_ORDER[gnoll_step % editor.ANIMAL_DIRECTION_ORDER.size()])
	if gnoll_attack_clips.size() != 4 or not gnoll_preview_ok \
		or Vector2i(gnoll_attack_clips[0].get("frame_size", Vector2i.ZERO)) != Vector2i(4, 4):
		push_error("Превью гнола должно показывать каждое состояние во всех четырёх направлениях по кругу.")
		editor.free()
		get_tree().quit(1)
		return
	var hover_frames := [{"tile_id": 0, "duration": 100}]
	var hover_probe := {
		"kind": "mob",
		"states": {
			"idle": {"clips": [{"direction": "down", "frame_ids": hover_frames}]},
			"run_attack": {"clips": [{"direction": "left", "frame_ids": hover_frames}]},
			"hurt": {"clips": [{"direction": "left", "frame_ids": hover_frames}]},
			"animation_2": {"clips": [
				{"direction": "left", "frame_ids": hover_frames},
				{"direction": "up", "frame_ids": hover_frames},
			]},
			"jump": {"clips": [{"direction": "right", "frame_ids": []}]},
		},
	}
	var hover_directions: Dictionary = editor._animal_group_directions(hover_probe)
	var hover_actions: Dictionary = editor._animal_group_actions(hover_probe)
	var card_viewport := Vector2(1280, 720)
	var hover_card_centered: Vector2 = editor._animal_hover_card_position(
		Rect2(120, 40, 115, 660),
		editor.ANIMAL_CARD_SIZE,
		card_viewport,
	)
	var hover_card_shifted: Vector2 = editor._animal_hover_card_position(
		Rect2(400, 40, 500, 660),
		editor.ANIMAL_CARD_SIZE,
		card_viewport,
	)
	var hover_card_clamped: Vector2 = editor._animal_hover_card_position(
		Rect2(0, 0, 1200, 720),
		editor.ANIMAL_CARD_SIZE,
		card_viewport,
	)
	if not hover_directions["down"] or not hover_directions["left"] or not hover_directions["up"] \
		or hover_directions["right"] or not hover_actions["idle"] or not hover_actions["run_attack"] \
		or not hover_actions["hurt"] or not hover_actions["other"] \
		or hover_actions["jump"] or hover_actions["walk"] or hover_actions["run"] \
		or hover_actions["attack"] or hover_actions["walk_attack"] or hover_actions["death"]:
		push_error("Карточка моба неверно определяет направления или действия.")
		editor.free()
		get_tree().quit(1)
		return
	if hover_card_centered != (card_viewport - editor.ANIMAL_CARD_SIZE) * 0.5 \
		or hover_card_shifted.x != 400.0 + 500.0 + editor.ANIMAL_CARD_MARGIN \
		or hover_card_shifted.y != hover_card_centered.y \
		or hover_card_clamped.x != card_viewport.x - editor.ANIMAL_CARD_SIZE.x:
		push_error("Карточка моба неверно выбирает позицию: центр экрана, сдвиг от палитры и границы.")
		editor.free()
		get_tree().quit(1)
		return
	var lpc_animation_cases := [
		{
			"folder": "orc sprite",
			"species_prefix": "orc",
			"states": ["idle", "walk", "run", "attack", "hurt", "death", "run_attack", "walk_attack"],
		},
		{
			"folder": "craftpix-net-900504-lizardmen-pixel-art-character-sprite-pack",
			"species_prefix": "lizardman",
			"states": ["idle", "walk", "run", "attack", "hurt", "death"],
		},
		{
			"folder": "craftpix-net-894297-top-down-pixel-ghost-character-sprite-pack",
			"species_prefix": "ghost",
			"states": ["idle", "walk", "run", "attack", "hurt", "death"],
		},
		{
			"folder": "craftpix-net-870078-top-down-pixel-skeletons-character-sprite-pack",
			"species_prefix": "skeleton",
			"states": ["idle", "walk", "run", "attack", "hurt", "death"],
		},
	]
	for test_case in lpc_animation_cases:
		for variant in range(1, 4):
			var species := "%s%d" % [test_case["species_prefix"], variant]
			var mob_key := editor._mob_instance_key(test_case["folder"], species)
			var mob_group: Dictionary = editor._animal_groups_by_key.get(mob_key, {})
			var mob_states: Dictionary = mob_group.get("states", {})
			for state_name in test_case["states"]:
				var clips: Array = mob_states.get(state_name, {}).get("clips", [])
				if clips.is_empty() or editor._animal_clip_preview_image(clips[0], 0) == null:
					push_error("У LPC-моба %s отсутствует корректный кадр состояния «%s»." % [
						species, state_name,
					])
					editor.free()
					get_tree().quit(1)
					return
	var goblin_folder := "goblin sprite-pack"
	var goblin_pack_path: String = editor.LPC_ROOT.path_join(goblin_folder)
	var goblin_pack_button: Button = editor._biome_buttons.get(goblin_pack_path)
	var goblin_state_names := [
		"idle", "walk", "run", "attack", "hurt", "death", "run_attack", "walk_attack",
	]
	var goblin_group_count := 0
	var goblin_pack_group_count := 0
	for group in editor._animal_groups:
		if str(group.get("pack_path", "")) == goblin_pack_path:
			goblin_pack_group_count += 1
	var goblin_key := ""
	for variant in range(1, 4):
		var goblin_species := "g%d" % variant
		goblin_key = editor._mob_instance_key(goblin_folder, goblin_species)
		var goblin_group: Dictionary = editor._animal_groups_by_key.get(goblin_key, {})
		var goblin_states: Dictionary = goblin_group.get("states", {})
		if not goblin_group.is_empty():
			goblin_group_count += 1
		if str(goblin_group.get("name", "")) != "Гоблин %d" % variant \
			or goblin_states.size() != goblin_state_names.size():
			push_error("Гоблин %d должен быть одним собранным мобом со всеми анимациями." % variant)
			editor.free()
			get_tree().quit(1)
			return
		for state_name in goblin_state_names:
			var state: Dictionary = goblin_states.get(state_name, {})
			var directional_clips := editor._animal_state_direction_clips(state)
			if directional_clips.size() != 4:
				push_error("У гоблина %d нет всех направлений анимации «%s»." % [
					variant, state_name,
				])
				editor.free()
				get_tree().quit(1)
				return
			for entry in directional_clips:
				var clip: Dictionary = entry["clip"]
				var expected_frames := 5 if state_name == "attack" \
					else 6 if state_name in ["walk", "walk_attack"] \
					else 8 if state_name in ["run", "run_attack"] \
					else 4 if state_name in ["idle", "hurt"] \
					else 6
				if Vector2i(clip.get("frame_size", Vector2i.ZERO)) != Vector2i(2, 2) \
					or clip.get("frame_ids", []).size() != expected_frames \
					or editor._animal_clip_preview_image(clip, 0) == null:
					push_error("Кадры анимации «%s» гоблина %d разобраны неверно." % [
						state_name, variant,
					])
					editor.free()
					get_tree().quit(1)
					return
	if goblin_pack_button == null or goblin_group_count != 3 or goblin_pack_group_count != 3:
		push_error("В палитре должны быть ровно три собранных варианта гоблинов.")
		editor.free()
		get_tree().quit(1)
		return
	var skeleton_folder := "craftpix-net-870078-top-down-pixel-skeletons-character-sprite-pack"
	var skeleton_pack_path: String = editor.LPC_ROOT.path_join(skeleton_folder)
	var skeleton_pack_button: Button = editor._biome_buttons.get(skeleton_pack_path)
	if skeleton_pack_button == null or skeleton_pack_button.text != "Скелеты":
		push_error("Набор скелетов должен быть доступен под русским названием в палитре LPC.")
		editor.free()
		get_tree().quit(1)
		return
	for skeleton_variant in range(1, 4):
		var skeleton_key := editor._mob_instance_key(
			skeleton_folder, "skeleton%d" % skeleton_variant,
		)
		var skeleton_group: Dictionary = editor._animal_groups_by_key.get(skeleton_key, {})
		if str(skeleton_group.get("name", "")) != "Скелет %d" % skeleton_variant:
			push_error("В палитре отсутствует локализованный скелет %d." % skeleton_variant)
			editor.free()
			get_tree().quit(1)
			return
		for state_name in ["idle", "walk", "run", "attack", "hurt", "death"]:
			var state: Dictionary = skeleton_group.get("states", {}).get(state_name, {})
			var directional_clips := editor._animal_state_direction_clips(state)
			var directions: Dictionary = {}
			for entry in directional_clips:
				directions[str(entry["direction"])] = true
				var clip: Dictionary = entry["clip"]
				if Vector2i(clip.get("frame_size", Vector2i.ZERO)) != Vector2i(4, 4):
					push_error("Кадр скелета %d должен занимать сетку 4×4." % skeleton_variant)
					editor.free()
					get_tree().quit(1)
					return
			if directional_clips.size() != 4 or not directions.has("down") \
				or not directions.has("left") or not directions.has("up") \
				or not directions.has("right"):
				push_error("Анимация «%s» скелета %d должна иметь четыре направления." % [
					state_name, skeleton_variant,
				])
				editor.free()
				get_tree().quit(1)
				return
	var imp2_key := editor._mob_instance_key("LPC Imp 2", "blue_imp_vanilla")
	var imp2_group: Dictionary = editor._animal_groups_by_key.get(imp2_key, {})
	var imp2_directions: Dictionary = editor._animal_group_directions(imp2_group)
	if imp2_group.is_empty() or not imp2_group.get("states", {}).has("walk") \
		or not imp2_group.get("states", {}).has("attack") \
		or not imp2_group.get("states", {}).has("death") \
		or str(imp2_group.get("profile_kind", "")) != "imp_blue_vanilla" \
		or not imp2_directions["down"] or not imp2_directions["left"] \
		or not imp2_directions["right"] or not imp2_directions["up"]:
		push_error("Листовые анимации LPC Imp 2 не собраны в готового моба.")
		editor.free()
		get_tree().quit(1)
		return
	var direction_circle: Array[String] = ["down", "left", "up", "right"]
	var imp2_walk_order: Array[String] = []
	for imp2_entry in editor._animal_state_direction_clips(imp2_group["states"]["walk"]):
		imp2_walk_order.append(str(imp2_entry["direction"]))
	var imp2_death_order: Array[String] = []
	for imp2_entry in editor._animal_state_direction_clips(imp2_group["states"]["death"]):
		imp2_death_order.append(str(imp2_entry["direction"]))
	var zombie_group: Dictionary = editor._animal_groups_by_key.get(
		editor._mob_instance_key(
			"craftpix-net-550920-zombie-4-direction-pixel-character-sprite-pack",
			"zombie1",
		),
		{},
	)
	var zombie_states: Dictionary = zombie_group.get("states", {})
	var zombie_ok := zombie_states.size() >= 6
	for zombie_state in zombie_states.values():
		var zombie_order: Array[String] = []
		for zombie_entry in editor._animal_state_direction_clips(zombie_state):
			zombie_order.append(str(zombie_entry["direction"]))
		zombie_ok = zombie_ok and zombie_order == direction_circle
	if imp2_walk_order != direction_circle or imp2_death_order != ["down"] \
		or not zombie_ok:
		push_error("Направления мобов определены неверно: Imp 2 %s / %s, зомби %s." % [
			imp2_walk_order, imp2_death_order, zombie_ok,
		])
		editor.free()
		get_tree().quit(1)
		return
	var wolves_present: bool = editor._biome_buttons.has(editor.LPC_ROOT.path_join("wolfs"))
	for wolf_check_group in editor._animal_groups:
		wolves_present = wolves_present or str(wolf_check_group.get("pack_folder", "")) == "wolfs"
	if wolves_present:
		push_error("Волки должны быть убраны из палитры мобов.")
		editor.free()
		get_tree().quit(1)
		return
	var sample_clip: Dictionary = imp2_group["states"]["walk"]["clips"][0]
	if editor._animal_palette.fixed_icon_size != Vector2i(80, 80) \
		or editor._animal_clip_preview_image(sample_clip, 0).get_size() != Vector2i(80, 80):
		push_error("Миниатюры мобов должны отображаться крупным единообразным размером.")
		editor.free()
		get_tree().quit(1)
		return
	for mob_group in editor._animal_groups:
		if str(mob_group.get("kind", "")) != "mob":
			continue
		var mob_states: Dictionary = mob_group.get("states", {})
		var preview_states := {}
		for preview_entry in editor._animal_palette_preview_sequence(mob_group):
			preview_states[str(preview_entry.get("state", ""))] = true
		if preview_states.size() != mob_states.size():
			push_error("В hover-предпросмотре потеряно состояние моба «%s»." % mob_group.get("name", ""))
			editor.free()
			get_tree().quit(1)
			return
		for state_name in mob_states:
			for clip in mob_states[state_name].get("clips", []):
				var frames: Array = clip.get("frame_ids", [])
				if frames.is_empty() \
					or editor._animal_clip_preview_image(clip, 0) == null \
					or editor._animal_clip_preview_image(clip, frames.size() - 1) == null:
					push_error("У моба «%s» повреждены кадры состояния «%s»." % [
						mob_group.get("name", ""), state_name,
					])
					editor.free()
					get_tree().quit(1)
					return
	editor._select_biome(goblin_pack_path, editor._biome_buttons[goblin_pack_path])
	editor._animal_palette.size = Vector2(320, 500)
	if editor._animal_palette.custom_maximum_size.x != 320 \
		or editor._animal_palette.size_flags_horizontal != Control.SIZE_EXPAND_FILL \
		or editor._animal_palette_item_at_position(Vector2(-1, 100)) != -1 \
		or editor._animal_palette_item_at_position(Vector2(321, 100)) != -1:
		push_error("Палитра LPC должна заполнять доступную панель, ограничивать ширину и отключать hover вне границ.")
		editor.free()
		get_tree().quit(1)
		return
	var goblin_item_index := -1
	for index in range(editor._animal_palette.item_count):
		if str(editor._animal_palette.get_item_metadata(index)) == goblin_key:
			goblin_item_index = index
			break
	if goblin_item_index < 0:
		push_error("Готовый спрайт гоблина отсутствует в разделе LPC.")
		editor.free()
		get_tree().quit(1)
		return
	editor._begin_animal_palette_preview(goblin_item_index)
	if editor._animal_hover_card == null or not editor._animal_hover_card.visible \
		or editor._animal_hover_card.get_child_count() != 1:
		push_error("При наведении на моба не появляется информационная карточка.")
		editor.free()
		get_tree().quit(1)
		return
	if editor._animal_hover_card.get_theme_font_size("font_size") != 8 \
		or editor._animal_hover_card.custom_minimum_size != editor.ANIMAL_CARD_SIZE:
		push_error("Карточка моба должна использовать компактный шрифт и фиксированный размер.")
		editor.free()
		get_tree().quit(1)
		return
	var preview_clip_count: int = editor._animal_preview_clips.size()
	if preview_clip_count < 4:
		push_error("Предпросмотр моба не включает все состояния и направления.")
		editor.free()
		get_tree().quit(1)
		return
	editor._advance_animal_palette_preview(2.0)
	if editor._animal_preview_clip_index == 0 and editor._animal_preview_frame_index == 0:
		push_error("При наведении предпросмотр не переключает кадры анимации.")
		editor.free()
		get_tree().quit(1)
		return
	editor._show_mob_profile(goblin_key, {
		"move_speed": 150.0,
		"windup": 0.2,
		"backswing": 0.3,
		"aggro_tiles": 3.5,
		"respawn_seconds": 30,
		"reward_copper": 30,
		"reward_xp": 10,
		"state": "aggressive",
		"level": 1,
		"stats": {
			"strength": 3,
			"agility": 3,
			"intuition": 3,
			"wisdom": 3,
			"intellect": 3,
			"endurance": 4,
		},
		"equipment": {},
		"patrol": [[0, 0]],
	})
	var profile_dialog: Control = editor._mob_profile_dialog
	if not is_instance_valid(profile_dialog) \
		or not profile_dialog.field_inputs.has("move_speed") \
		or not profile_dialog.equipment_panel.slot_buttons.has("ring_2") \
		or profile_dialog.patrol_grid.cell_count() != 1:
		push_error("В окне профиля моба отсутствуют поля, экипировка или сетка патруля.")
		editor.free()
		get_tree().quit(1)
		return
	editor._cancel_mob_profile()
	if is_instance_valid(editor._mob_profile_dialog) or editor._pending_mob_profile_key != "":
		push_error("Отмена окна профиля моба должна закрывать его и сбрасывать выбранного моба.")
		editor.free()
		get_tree().quit(1)
		return
	editor._reset_animal_palette_hover()
	editor._select_biome(animal_pack_path, editor._biome_buttons[animal_pack_path])
	var fish_item_index := -1
	for index in range(editor._animal_palette.item_count):
		if str(editor._animal_palette.get_item_metadata(index)) == fish_key:
			fish_item_index = index
			break
	if fish_item_index < 0:
		push_error("Готовый спрайт Fish1 отсутствует в палитре.")
		editor.free()
		get_tree().quit(1)
		return
	if not editor._animal_palette.item_activated.is_connected(editor._on_animal_item_activated):
		push_error("Двойной щелчок по животному не подключён к настройкам.")
		_cleanup_settings(animal_settings_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._on_animal_item_selected(fish_item_index)
	var animal_layer: Dictionary = editor._get_layer(editor._active_layer_id)
	if editor._layers.size() < 3 or str(editor._layers[2].get("type", "")) != editor.LAYER_ANIMAL \
		or str(animal_layer.get("type", "")) != editor.LAYER_ANIMAL:
		push_error("Выбор животного не переключил активный слой на отдельный слой животных.")
		editor.free()
		get_tree().quit(1)
		return
	object_layer_id = int(editor._layers[1]["id"])
	editor._active_layer_id = object_layer_id
	editor._last_stroke_cell = Vector2i(-1, -1)
	editor._paint_canvas_cell(Vector2i(3, 4))
	if editor._get_layer(object_layer_id)["cells"].has("3:4"):
		push_error("Животное ошибочно разместилось на слое объектов.")
		editor.free()
		get_tree().quit(1)
		return
	editor._active_layer_id = int(animal_layer["id"])
	var ordinary_item_key := "regular_item_smoke"
	editor._catalog_by_key[ordinary_item_key] = {
		"item_key": ordinary_item_key,
		"category": "grass",
	}
	editor._selected_item_key = ordinary_item_key
	editor._last_stroke_cell = Vector2i(-1, -1)
	editor._paint_canvas_cell(Vector2i(3, 4))
	if animal_layer["cells"].has("3:4"):
		push_error("Обычный элемент ошибочно разместился на слое животных.")
		editor.free()
		get_tree().quit(1)
		return
	editor._selected_item_key = fish_key
	editor._paint_canvas_cell(Vector2i(4, 4))
	if str(animal_layer["cells"].get("4:4", "")) != fish_key \
		or not editor._has_unpublished_local_assets():
		push_error("Целый спрайт рыбы не разместился на слое животных.")
		editor.free()
		get_tree().quit(1)
		return
	var serialized_animal_map: Dictionary = editor._serialize_editor_layers()
	var stored_animal_cells: Array = []
	for stored_layer in serialized_animal_map["editor_layers"]:
		if str(stored_layer.get("type", "")) == editor.LAYER_ANIMAL:
			stored_animal_cells = stored_layer["cells"]
			break
	if not serialized_animal_map["catalog_cells"].is_empty() \
		or stored_animal_cells.size() != 1 \
		or str(stored_animal_cells[0].get("key", "")) != fish_key:
		push_error("Готовый спрайт не сохраняется как единый локальный объект карты.")
		_cleanup_settings(animal_settings_path)
		editor.free()
		get_tree().quit(1)
		return
	for stored_layer in serialized_animal_map["editor_layers"]:
		if str(stored_layer.get("type", "")) == editor.LAYER_ANIMAL:
			var instance_settings: Dictionary = stored_layer.get("animal_settings", {})
			if int(instance_settings.get("4:4", {}).get("patrol_radius", 0)) != 7 \
				or str(instance_settings.get("4:4", {}).get("mode", "")) != "economy":
				push_error("Радиус патруля не сохраняется вместе с конкретным животным.")
				_cleanup_settings(animal_settings_path)
				editor.free()
				get_tree().quit(1)
				return
			break
	editor._get_layer(object_layer_id)["cells"]["2:2"] = fish_key
	editor._move_animal_instances_to_animal_layer()
	if editor._get_layer(object_layer_id)["cells"].has("2:2") \
		or str(animal_layer["cells"].get("2:2", "")) != fish_key:
		push_error("Животное из старого черновика не перенесено в отдельный слой.")
		editor.free()
		get_tree().quit(1)
		return
	animal_layer["cells"].erase("2:2")
	editor._last_stroke_cell = Vector2i(-1, -1)
	editor._erase_canvas_cell(Vector2i(5, 4))
	if animal_layer["cells"].has("4:4"):
		push_error("Щелчок по кадру целого спрайта не удалил объект по его якорю.")
		_cleanup_settings(animal_settings_path)
		editor.free()
		get_tree().quit(1)
		return
	if animal_layer["animal_settings"].has("4:4"):
		push_error("Удаление животного не удалило его настройки патруля.")
		_cleanup_settings(animal_settings_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._select_biome(goblin_pack_path, editor._biome_buttons[goblin_pack_path])
	editor._on_animal_item_selected(goblin_item_index)
	var mob_layer: Dictionary = editor._get_layer(editor._active_layer_id)
	if str(mob_layer.get("type", "")) != editor.LAYER_MOB:
		push_error("Выбор моба не переключил активный слой на отдельный слой мобов.")
		_cleanup_settings(animal_settings_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._last_stroke_cell = Vector2i(-1, -1)
	editor._paint_canvas_cell(Vector2i(12, 12))
	if str(mob_layer["cells"].get("12:12", "")) != goblin_key:
		push_error("Готовый спрайт моба не размещается на слое «Мобы».")
		_cleanup_settings(animal_settings_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._get_layer(object_layer_id)["cells"]["2:2"] = goblin_key
	editor._move_mob_instances_to_mob_layer()
	if editor._get_layer(object_layer_id)["cells"].has("2:2") \
		or str(mob_layer["cells"].get("2:2", "")) != goblin_key:
		push_error("Моб из старого черновика не перенесён на отдельный слой мобов.")
		_cleanup_settings(animal_settings_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._get_layer(object_layer_id)["cells"].erase("2:2")
	var flying_biome_path: String = ground_sheet["biome_path"]
	editor._select_biome(flying_biome_path, editor._biome_buttons[flying_biome_path])
	var atlas_path := ATLAS_ROOT.path_join("water_detilazation_v2.png")
	var animations: Dictionary = editor._read_sheet_animations(atlas_path)
	if animations.is_empty() or not animations.has(40):
		push_error("Не прочитана анимация тайла 40 из Water_detilazation2.tsx.")
		editor.free()
		get_tree().quit(1)
		return
	var frames: Array = animations[40]
	if frames.size() != 6 or int(frames[0]["duration"]) != 150:
		push_error("Кадры анимации тайла 40 прочитаны неверно.")
		editor.free()
		get_tree().quit(1)
		return

	var palette = editor._atlas_palette
	var texture := load(atlas_path) as Texture2D
	palette.set_atlas(texture, animations)
	if palette.atlas_columns != 37 or palette.atlas_rows != 78:
		push_error("Размер сетки атласа определён неверно.")
		editor.free()
		get_tree().quit(1)
		return
	var click := InputEventMouseButton.new()
	click.button_index = MOUSE_BUTTON_LEFT
	click.pressed = true
	click.position = Vector2(20, 20)
	palette._gui_input(click)
	if palette.selected_coords != Vector2i(2, 2):
		push_error("Щелчок по палитре выбрал неверную клетку: %s." % str(palette.selected_coords))
		editor.free()
		get_tree().quit(1)
		return
	var atlas_width_before_zoom: float = palette.custom_minimum_size.x
	var zoom_event := InputEventMouseButton.new()
	zoom_event.button_index = MOUSE_BUTTON_WHEEL_UP
	zoom_event.pressed = true
	zoom_event.ctrl_pressed = true
	palette._gui_input(zoom_event)
	if palette.custom_minimum_size.x <= atlas_width_before_zoom:
		push_error("Ctrl+колесо не увеличило масштаб атласа.")
		editor.free()
		get_tree().quit(1)
		return

	var local_cell_key: String = editor._encode_atlas_cell(atlas_path, Vector2i(2, 2))
	var test_layers: Array[Dictionary] = [{
		"id": 1,
		"name": "Земля",
		"type": "tile",
		"parent_id": 0,
		"visible": true,
		"locked": false,
		"cells": {"3:4": local_cell_key},
	}]
	editor._layers = test_layers
	editor._catalog_by_key = {}
	var serialized: Dictionary = editor._serialize_editor_layers()
	var stored_layers: Array = serialized["editor_layers"]
	var saved_cells: Array = stored_layers[0]["cells"]
	if not serialized["catalog_cells"].is_empty() or saved_cells.size() != 1 or str(saved_cells[0]["key"]) != local_cell_key:
		push_error("Тайл из локального листа не сохраняется в данных слоя.")
		editor.free()
		get_tree().quit(1)
		return
	var reloaded_cells: Dictionary = editor._cells_to_dictionary(saved_cells)
	if str(reloaded_cells["3:4"]) != local_cell_key or not editor._has_unpublished_local_assets():
		push_error("Сохранённый тайл листа не восстанавливается в редакторе.")
		editor.free()
		get_tree().quit(1)
		return

	var annotation_path := "user://tile_annotations_smoke.cfg"
	editor._annotation_config_path = annotation_path
	editor._load_atlas_annotations(annotation_path)
	editor._selected_atlas_path = atlas_path
	palette._zoom = 0.5
	palette._update_size()
	var select_start := InputEventMouseButton.new()
	select_start.button_index = MOUSE_BUTTON_RIGHT
	select_start.pressed = true
	select_start.position = Vector2(12, 12)
	palette._gui_input(select_start)
	var select_motion := InputEventMouseMotion.new()
	select_motion.button_mask = MOUSE_BUTTON_MASK_RIGHT
	select_motion.position = Vector2(28, 44)
	palette._gui_input(select_motion)
	var select_end := InputEventMouseButton.new()
	select_end.button_index = MOUSE_BUTTON_RIGHT
	select_end.pressed = false
	select_end.position = Vector2(28, 44)
	palette._gui_input(select_end)
	if palette.selected_region != Rect2i(Vector2i(1, 1), Vector2i(3, 5)):
		push_error("Right-button drag did not select the 3×5 atlas group in the palette.")
		_cleanup_annotations(annotation_path)
		_cleanup_settings(animal_settings_path)
		editor.free()
		get_tree().quit(1)
		return
	if editor._selected_atlas_region != Rect2i(Vector2i(1, 1), Vector2i(3, 5)):
		push_error("Right-button palette selection did not activate an ordinary brush stamp.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	if editor._auto_brush_enabled:
		push_error("Выделение обычной кистью случайно включило автокисть.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._create_default_layers()
	var ground_layer: Dictionary = editor._layers[0]
	editor._active_tool = "stamp"
	editor._stamp_buffer = {
		"parts": [{"cells": [[0, 0, "stale_stamp"]]}],
		"w": 1,
		"h": 1,
		"count": 1,
	}
	editor._on_atlas_region_selected(Rect2i(Vector2i(4, 4), Vector2i(2, 2)))
	if editor._active_tool != "brush":
		push_error("Selecting an atlas group must switch away from the previous stamp tool.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._begin_canvas_stroke(_canvas_point_for_cell(editor, Vector2i(10, 10)), MOUSE_BUTTON_LEFT)
	editor._end_canvas_stroke(MOUSE_BUTTON_LEFT)
	if ground_layer["cells"].size() != 4:
		push_error("Обычная кисть не принимает произвольный прямоугольный фрагмент атласа.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._undo_last_action()
	ground_layer = editor._layers[0]
	if not ground_layer["cells"].is_empty():
		push_error("Undo did not reverse the arbitrary rectangular stamp.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._on_atlas_region_selected(Rect2i(Vector2i(1, 1), Vector2i(3, 5)))
	editor._begin_canvas_stroke(_canvas_point_for_cell(editor, Vector2i(10, 10)), MOUSE_BUTTON_LEFT)
	editor._end_canvas_stroke(MOUSE_BUTTON_LEFT)
	var regular_stamp_cells: Dictionary = ground_layer["cells"]
	if regular_stamp_cells.size() != 15 \
		or editor._decode_atlas_cell(str(regular_stamp_cells["9:8"])).get("coords", Vector2i.ZERO) != Vector2i(1, 1) \
		or editor._decode_atlas_cell(str(regular_stamp_cells["11:12"])).get("coords", Vector2i.ZERO) != Vector2i(3, 5):
		push_error("Обычная кисть не нанесла выделенную группу целым штампом: %d клеток, верх %s, низ %s, статус %s." % [
			regular_stamp_cells.size(),
			str(regular_stamp_cells.get("9:8", "")),
			str(regular_stamp_cells.get("11:12", "")),
			editor._status.text,
		])
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._undo_last_action()
	ground_layer = editor._layers[0]
	editor._selected_atlas_region = Rect2i(Vector2i(1, 1), Vector2i(3, 10))
	editor._selected_item_key = editor._encode_atlas_cell(atlas_path, Vector2i(2, 5))
	editor._begin_canvas_stroke(_canvas_point_for_cell(editor, Vector2i(10, 0)), MOUSE_BUTTON_LEFT)
	editor._end_canvas_stroke(MOUSE_BUTTON_LEFT)
	var top_edge_stamp: Dictionary = editor._layers[0]["cells"]
	if top_edge_stamp.size() != 30 or not top_edge_stamp.has("9:0") or not top_edge_stamp.has("11:9"):
		push_error("Обычная кисть не прижала высокий атласный штамп к верхнему краю карты.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._undo_last_action()
	ground_layer = editor._layers[0]
	if not ground_layer["cells"].is_empty():
		push_error("Ctrl+Z не отменил штамп, размещённый у верхней границы.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._selected_atlas_region = Rect2i(Vector2i(1, 1), Vector2i(3, 5))
	editor._selected_item_key = editor._encode_atlas_cell(atlas_path, Vector2i(2, 2))
	editor._begin_canvas_stroke(_canvas_point_for_cell(editor, Vector2i(10, 10)), MOUSE_BUTTON_LEFT)
	editor._end_canvas_stroke(MOUSE_BUTTON_LEFT)
	ground_layer = editor._layers[0]
	if ground_layer["cells"].size() != 15:
		push_error("The brush stamp could not be applied again after undo.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	ground_layer["cells"] = {}
	editor._annotation_height_select.select(2)
	editor._set_auto_brush(true)
	editor._on_atlas_tile_selected(Vector2i(2, 2))
	editor._corner_variant_select.select(0)
	editor._on_corner_variant_selected(0)
	if not editor._status.text.contains("Включите «Назначить тайл»"):
		push_error("Неназначенный вариант угла не подсказывает, как подключить тайл.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	if int(editor._atlas_annotations.get(editor._annotation_key(atlas_path, Vector2i(2, 2)), 0)) != 5:
		push_error("Автокисть не сохранила формат и выбранный центральный тайл.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._corner_variant_assign_button.button_pressed = true
	editor._on_corner_assignment_button_toggled(true)
	if not editor._corner_variant_assign_button.button_pressed \
		or editor._corner_variant_assign_button.text != "Выберите в палитре" \
		or not editor._corner_assignment_status.text.contains("щёлкните нужный тайл"):
		push_error("Кнопка назначения не зафиксировалась и не показала, что следующий щелчок — по палитре.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._on_atlas_tile_selected(Vector2i(0, 0))
	var selected_corner_center := editor._decode_atlas_cell(editor._selected_item_key)
	var assigned_inner_corner_key := editor._corner_annotation_key(
		atlas_path, Vector2i(2, 2), "inner_nw",
	)
	if editor._autotile_rule_tiles(assigned_inner_corner_key) != [Vector2i(0, 0)] \
		or selected_corner_center.get("coords", Vector2i.ZERO) != Vector2i(2, 2) \
		or editor._corner_variant_assign_button.button_pressed \
		or not editor._corner_assignment_status.text.contains("тайлов: 1 (0,0)"):
		push_error("Выбранный угловой тайл не сохранился или заменил центр автокисти.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	if not editor._save_atlas_corner_tile(
		atlas_path, Vector2i(2, 2), "inner_nw", Vector2i(1, 0),
	) or editor._autotile_rule_tiles(assigned_inner_corner_key) != [
		Vector2i(0, 0), Vector2i(1, 0),
	]:
		push_error("Повторное назначение не добавило второй вариант тайла.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	var annotations_config := ConfigFile.new()
	if annotations_config.load(annotation_path) != OK \
		or typeof(annotations_config.get_value("corner_tiles", assigned_inner_corner_key)) != TYPE_ARRAY \
		or annotations_config.get_value("corner_tiles", assigned_inner_corner_key).size() != 2:
		push_error("Список вариантов автокисти не сохранился в локальных настройках.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	if not editor._save_atlas_corner_tile(
		atlas_path, Vector2i(2, 2), "inner_nw", Vector2i(1, 0),
	) or editor._autotile_rule_tiles(assigned_inner_corner_key).size() != 2:
		push_error("Повторное назначение одного тайла создало дубликат.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._clear_corner_tile_assignment()
	if editor._atlas_corner_tiles.has(
		editor._corner_annotation_key(atlas_path, Vector2i(2, 2), "inner_nw"),
	):
		push_error("Кнопка сброса не удалила настройку углового тайла.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._selected_item_key = local_cell_key
	editor._begin_canvas_stroke(_canvas_point_for_cell(editor, Vector2i(10, 10)), MOUSE_BUTTON_LEFT)
	editor._paint_canvas_drag_at(_canvas_point_for_cell(editor, Vector2i(13, 10)))
	editor._end_canvas_stroke(MOUSE_BUTTON_LEFT)
	var autotile_cells: Dictionary = ground_layer["cells"]
	if autotile_cells.size() != 12:
		push_error("Удержание ЛКМ должно нарисовать четыре базовые клетки и автоматически продолжить нижнюю кромку на два ряда.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	var left_edge: Dictionary = editor._decode_atlas_cell(str(autotile_cells["10:10"]))
	var right_edge: Dictionary = editor._decode_atlas_cell(str(autotile_cells["13:10"]))
	if left_edge.get("coords", Vector2i.ZERO) != Vector2i(1, 1) \
		or right_edge.get("coords", Vector2i.ZERO) != Vector2i(3, 1):
		push_error("Автотайлинг не выбрал левый и правый края по соседним клеткам.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	var first_extension: Dictionary = editor._decode_atlas_cell(str(autotile_cells["10:11"]))
	var last_extension: Dictionary = editor._decode_atlas_cell(str(autotile_cells["10:12"]))
	if first_extension.get("coords", Vector2i.ZERO) != Vector2i(1, 4) \
		or last_extension.get("coords", Vector2i.ZERO) != Vector2i(1, 5):
		push_error("Нижние ряды 3×5 не продолжили автоматически выбранный край.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	var original_autotile_cells := autotile_cells.duplicate(true)
	var extension_touch_cells := original_autotile_cells.duplicate(true)
	ground_layer["cells"] = extension_touch_cells
	editor._last_stroke_cell = Vector2i(-1, -1)
	editor._paint_canvas_cell(Vector2i(11, 12))
	var promoted_atlas_extension := editor._decode_atlas_cell(str(extension_touch_cells["11:11"]))
	var touched_atlas_extension := editor._decode_atlas_cell(str(extension_touch_cells["11:12"]))
	if promoted_atlas_extension.get("coords", Vector2i.ZERO).y != 2 \
		or touched_atlas_extension.get("coords", Vector2i.ZERO).y != 3:
		push_error("Касание дальнего ряда 3×5 не включило промежуточный ряд в связный автотайлинг.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	var regular_brush_extension_cells := original_autotile_cells.duplicate(true)
	ground_layer["cells"] = regular_brush_extension_cells
	editor._set_auto_brush(false)
	editor._selected_atlas_region = Rect2i(Vector2i(2, 2), Vector2i.ONE)
	editor._selected_item_key = local_cell_key
	editor._last_stroke_cell = Vector2i(-1, -1)
	editor._paint_canvas_cell(Vector2i(14, 10))
	var regular_brush_joined_tile := editor._decode_atlas_cell(
		str(regular_brush_extension_cells.get("14:10", "")),
	)
	if regular_brush_extension_cells.size() != original_autotile_cells.size() + 3 \
		or regular_brush_joined_tile.get("group_center", Vector2i(-1, -1)) != Vector2i(2, 2) \
		or regular_brush_joined_tile.get("coords", Vector2i.ZERO) != Vector2i(3, 1):
		push_error("Обычная кисть с центральным тайлом должна продолжать соседнюю автокисточную группу.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	var auto_brush_join_cells := original_autotile_cells.duplicate(true)
	auto_brush_join_cells["14:10"] = local_cell_key
	auto_brush_join_cells["15:10"] = local_cell_key
	ground_layer["cells"] = auto_brush_join_cells
	editor._set_auto_brush(true)
	editor._selected_item_key = local_cell_key
	editor._last_stroke_cell = Vector2i(-1, -1)
	editor._paint_canvas_cell(Vector2i(14, 10))
	var promoted_manual_neighbor := editor._decode_atlas_cell(
		str(auto_brush_join_cells.get("15:10", "")),
	)
	if promoted_manual_neighbor.get("group_center", Vector2i(-1, -1)) != Vector2i(2, 2) \
		or promoted_manual_neighbor.get("coords", Vector2i.ZERO) != Vector2i(3, 1):
		push_error("Автокисть должна включать соседние совместимые тайлы обычной кисти в общий автотайлинг.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	ground_layer["cells"] = original_autotile_cells
	autotile_cells = original_autotile_cells
	var test_cell := Vector2i(30, 30)
	var corner_cases: Array[Dictionary] = [
		{"name": "nw", "first": Vector2i.UP, "second": Vector2i.LEFT, "diagonal": Vector2i(-1, -1)},
		{"name": "ne", "first": Vector2i.UP, "second": Vector2i.RIGHT, "diagonal": Vector2i(1, -1)},
		{"name": "sw", "first": Vector2i.DOWN, "second": Vector2i.LEFT, "diagonal": Vector2i(-1, 1)},
		{"name": "se", "first": Vector2i.DOWN, "second": Vector2i.RIGHT, "diagonal": Vector2i(1, 1)},
	]
	for corner_case in corner_cases:
		var inner_neighbors: Dictionary = {}
		inner_neighbors[test_cell + corner_case["first"]] = true
		inner_neighbors[test_cell + corner_case["second"]] = true
		var inner_variant: Array[String] = editor._autotile_corner_variants_for_cell(
			test_cell, inner_neighbors, inner_neighbors,
		)
		var diagonal_neighbors: Dictionary = {test_cell + corner_case["diagonal"]: true}
		var diagonal_variant: Array[String] = editor._autotile_corner_variants_for_cell(
			test_cell, {}, diagonal_neighbors,
		)
		if inner_variant != ["inner_%s" % corner_case["name"]] \
			or diagonal_variant != ["diagonal_%s" % corner_case["name"]]:
			push_error("Автотайлинг не распознал внутренний угол или диагональный стык %s." % corner_case["name"])
			_cleanup_annotations(annotation_path)
			editor.free()
			get_tree().quit(1)
			return
	var corner_test_center := Vector2i(2, 2)
	var inner_corner_key := editor._corner_annotation_key(atlas_path, corner_test_center, "inner_nw")
	editor._atlas_corner_tiles[inner_corner_key] = Vector2i(0, 0)
	var inner_corner_cells: Dictionary = {
		"10:10": editor._encode_autotile_cell(atlas_path, corner_test_center, corner_test_center),
		"10:9": editor._encode_autotile_cell(atlas_path, corner_test_center, corner_test_center),
		"9:10": editor._encode_autotile_cell(atlas_path, corner_test_center, corner_test_center),
	}
	editor._refresh_autotile_group(
		{"cells": inner_corner_cells}, atlas_path, corner_test_center, 3, Vector2i(10, 10),
	)
	var inner_corner_tile := editor._decode_atlas_cell(str(inner_corner_cells["10:10"]))
	if inner_corner_tile.get("coords", Vector2i.ZERO) != Vector2i(0, 0):
		push_error("Автотайлинг не применил настроенный тайл вогнутого угла.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	var diagonal_corner_key := editor._corner_annotation_key(atlas_path, corner_test_center, "diagonal_nw")
	editor._atlas_corner_tiles[diagonal_corner_key] = Vector2i(1, 0)
	var diagonal_corner_cells: Dictionary = {
		"10:10": editor._encode_autotile_cell(atlas_path, corner_test_center, corner_test_center),
		"9:9": editor._encode_autotile_cell(atlas_path, corner_test_center, corner_test_center),
	}
	editor._refresh_autotile_group(
		{"cells": diagonal_corner_cells}, atlas_path, corner_test_center, 3, Vector2i(10, 10),
	)
	var diagonal_corner_tile := editor._decode_atlas_cell(str(diagonal_corner_cells["10:10"]))
	if diagonal_corner_tile.get("coords", Vector2i.ZERO) != Vector2i(1, 0) \
		or editor._decode_atlas_cell(str(diagonal_corner_cells["9:9"])).get("coords", Vector2i.ZERO) != corner_test_center:
		push_error("Диагональный сосед не выбрал свой угол или ошибочно слился с отдельным участком.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	var exact_mask_key := editor._corner_annotation_key(
		atlas_path, corner_test_center, editor._autotile_mask_key(65),
	)
	editor._atlas_corner_tiles[exact_mask_key] = Vector2i(2, 0)
	editor._refresh_autotile_palette_labels(atlas_path)
	var marked_tile: Dictionary = palette.autotile_labels.get("2:0", {})
	if marked_tile.get("markers", []).find("M065") < 0 \
		or not str(marked_tile.get("details", PackedStringArray())[0]).contains("соседи: N, W"):
		push_error("Тайлу из палитры не показаны маска и направления, для которых он назначен.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._refresh_autotile_group(
		{"cells": inner_corner_cells}, atlas_path, corner_test_center, 3, Vector2i(10, 10),
	)
	if editor._decode_atlas_cell(str(inner_corner_cells["10:10"])).get("coords", Vector2i.ZERO) != Vector2i(2, 0):
		push_error("Точное правило маски соседей не переопределило стандартную разметку внутреннего угла.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	var repeated_mask_key := editor._corner_annotation_key(
		atlas_path, corner_test_center, "mask_255",
	)
	editor._atlas_corner_tiles[repeated_mask_key] = [
		Vector2i(1, 0), Vector2i(2, 0),
	]
	var repeated_mask_cells: Dictionary = {}
	for y in range(10, 14):
		for x in range(10, 14):
			repeated_mask_cells["%d:%d" % [x, y]] = editor._encode_autotile_cell(
				atlas_path, corner_test_center, corner_test_center,
			)
	editor._refresh_autotile_group(
		{"cells": repeated_mask_cells}, atlas_path, corner_test_center, 3, Vector2i(10, 10),
	)
	var repeated_mask_tiles: Dictionary = {}
	for y in range(11, 13):
		for x in range(11, 13):
			var tile_info := editor._decode_atlas_cell(str(repeated_mask_cells["%d:%d" % [x, y]]))
			repeated_mask_tiles[Vector2i(x, y)] = tile_info.get("coords", Vector2i.ZERO)
	for map_cell in repeated_mask_tiles:
		for offset in [Vector2i.RIGHT, Vector2i.DOWN]:
			var neighbor_cell: Vector2i = map_cell + offset
			if repeated_mask_tiles.has(neighbor_cell) \
				and repeated_mask_tiles[map_cell] == repeated_mask_tiles[neighbor_cell]:
				push_error("Соседние клетки одного правила получили одинаковый вариант тайла.")
				_cleanup_annotations(annotation_path)
				editor.free()
				get_tree().quit(1)
				return
	var high_rule_center := Vector2i(2, 8)
	var high_rule_coords := Vector2i(2, 11)
	var high_rule_key := editor._corner_annotation_key(
		atlas_path, high_rule_center, "mask_255",
	)
	editor._atlas_corner_tiles[high_rule_key] = high_rule_coords
	var high_rule_cells: Dictionary = {}
	for y in range(10, 13):
		for x in range(10, 13):
			high_rule_cells["%d:%d" % [x, y]] = editor._encode_autotile_cell(
				atlas_path, high_rule_center, high_rule_center,
			)
	editor._refresh_autotile_group(
		{"cells": high_rule_cells}, atlas_path, high_rule_center, 5, Vector2i(11, 11),
	)
	var high_rule_core := editor._decode_atlas_cell(str(high_rule_cells["11:11"]))
	var high_rule_core_cells: Dictionary = {}
	for key in high_rule_cells:
		var decoded := editor._decode_atlas_cell(str(high_rule_cells[key]))
		var parts := str(key).split(":")
		var map_cell := Vector2i(int(parts[0]), int(parts[1]))
		if editor._same_autotile_group(decoded, atlas_path, high_rule_center) \
			and not editor._is_autotile_extension(decoded):
			high_rule_core_cells[map_cell] = key
	if high_rule_core.get("coords", Vector2i.ZERO) != high_rule_coords \
		or editor._is_autotile_extension(high_rule_core) \
		or editor._connected_group_cells(
			high_rule_core_cells, Vector2i(11, 11),
		).size() != 9 \
		or not editor._is_autotile_extension(
			editor._decode_atlas_cell(str(high_rule_cells["11:14"])),
		):
		push_error("Высокий вариант из правила маски должен оставаться базовым тайлом, а нижнее продолжение — отдельным.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	high_rule_cells["11:11"] = "%s%s|%d|%d|%d|%d" % [
		editor.ATLAS_CELL_PREFIX,
		atlas_path,
		high_rule_coords.x,
		high_rule_coords.y,
		high_rule_center.x,
		high_rule_center.y,
	]
	editor._refresh_autotile_group(
		{"cells": high_rule_cells}, atlas_path, high_rule_center, 5, Vector2i(11, 11),
	)
	high_rule_core = editor._decode_atlas_cell(str(high_rule_cells["11:11"]))
	if high_rule_core.get("autotile_role", "") != "core" \
		or editor._is_autotile_extension(high_rule_core):
		push_error("Старый тайл с назначенным высоким вариантом должен оставаться базой автокисти.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._atlas_corner_tiles.erase(repeated_mask_key)
	editor._atlas_corner_tiles.erase(inner_corner_key)
	editor._atlas_corner_tiles.erase(diagonal_corner_key)
	editor._atlas_corner_tiles.erase(exact_mask_key)
	editor._atlas_corner_tiles.erase(high_rule_key)
	ground_layer["cells"] = original_autotile_cells
	autotile_cells = original_autotile_cells
	var disconnected_test_cells := original_autotile_cells.duplicate(true)
	ground_layer["cells"] = disconnected_test_cells
	autotile_cells = disconnected_test_cells
	var disconnected_group_cell := editor._encode_autotile_cell(
		atlas_path, Vector2i(2, 2), Vector2i(2, 2),
	)
	autotile_cells["20:10"] = disconnected_group_cell
	editor._last_stroke_cell = Vector2i(-1, -1)
	editor._paint_canvas_cell(Vector2i(9, 10))
	var continued_left: Dictionary = editor._decode_atlas_cell(str(autotile_cells["10:10"]))
	var continued_left_edge: Dictionary = editor._decode_atlas_cell(str(autotile_cells["9:10"]))
	if str(autotile_cells.get("20:10", "")) != disconnected_group_cell \
		or continued_left.get("coords", Vector2i.ZERO) != Vector2i(2, 1) \
		or continued_left_edge.get("coords", Vector2i.ZERO) != Vector2i(1, 1):
		push_error("Автокисть должна обновлять связный участок и оставлять раздельный участок нетронутым.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	ground_layer["cells"] = original_autotile_cells
	autotile_cells = original_autotile_cells
	var neighbor_before_erase := str(autotile_cells["11:10"])
	editor._begin_canvas_stroke(_canvas_point_for_cell(editor, Vector2i(10, 11)), MOUSE_BUTTON_RIGHT)
	editor._end_canvas_stroke(MOUSE_BUTTON_RIGHT)
	if autotile_cells.size() != 11 or autotile_cells.has("10:11") \
		or not autotile_cells.has("10:10") \
		or str(autotile_cells["11:10"]) != neighbor_before_erase:
		push_error("Стирание автокистью должно удалить только выбранную клетку без изменения соседей.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	var undo_event := InputEventKey.new()
	undo_event.keycode = KEY_Z
	undo_event.ctrl_pressed = true
	undo_event.pressed = true
	editor._unhandled_key_input(undo_event)
	if editor._layers[0]["cells"].size() != 12:
		push_error("Ctrl+Z did not restore the full state before the erase action.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	ground_layer = editor._layers[0]
	editor._begin_canvas_stroke(_canvas_point_for_cell(editor, Vector2i(10, 11)), MOUSE_BUTTON_RIGHT)
	editor._end_canvas_stroke(MOUSE_BUTTON_RIGHT)
	if ground_layer["cells"].size() != 11 or ground_layer["cells"].has("10:11") \
		or not ground_layer["cells"].has("10:10") \
		or str(ground_layer["cells"]["11:10"]) != neighbor_before_erase:
		push_error("The erase action did not apply again after undo.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	var left_neighbor_before_brush := str(ground_layer["cells"]["10:10"])
	var right_neighbor_before_brush := str(ground_layer["cells"]["12:10"])
	editor._set_auto_brush(false)
	editor._on_atlas_tile_selected(Vector2i(1, 1))
	editor._last_stroke_cell = Vector2i(-1, -1)
	editor._paint_canvas_cell(Vector2i(11, 10))
	var replacement := editor._decode_atlas_cell(str(ground_layer["cells"]["11:10"]))
	if replacement.get("coords", Vector2i.ZERO) != Vector2i(1, 1) \
		or replacement.has("group_center") \
		or str(ground_layer["cells"]["10:10"]) != left_neighbor_before_brush \
		or str(ground_layer["cells"]["12:10"]) != right_neighbor_before_brush:
		push_error("Обычная кисть должна заменять только клетку под курсором, не меняя соседей.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	ground_layer["cells"]["11:10"] = neighbor_before_erase
	var custom_tile_keys: Array = []
	for row in range(5):
		var row_keys: Array[String] = []
		for column in range(3):
			var key := "custom_test_%d_%d" % [column, row]
			row_keys.append(key)
			var custom_item := {
				"item_key": key,
				"kind": "ground",
				"category": "grass",
				"editor_layer": 1,
				"tile_group_id": "custom_test",
				"tile_group_name": "Smoke group",
				"tile_x": column,
				"tile_y": row,
				"tile_rows": 5,
			}
			editor._catalog.append(custom_item)
			editor._catalog_by_key[key] = custom_item
		custom_tile_keys.append(row_keys)
	editor._register_custom_tile_group({
		"group_id": "custom_test",
		"name": "Smoke group",
		"category": "grass",
		"tile_rows": 5,
		"tile_keys": custom_tile_keys,
	})
	var migrated_count: int = editor._replace_uploaded_local_group_cells(
		"custom_test",
		atlas_path,
		Vector2i(2, 2),
		5,
		{"group_id": "custom_test"},
	)
	if migrated_count != 11 or editor._has_atlas_cells() \
		or str(ground_layer["cells"]["10:10"]) != custom_tile_keys[0][0]:
		push_error("Публикация группы не преобразовала уже нарисованные локальные тайлы в серверные ключи.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._render_palette()
	if editor._palette.item_count != 1:
		push_error("Server palette should show one brush entry for the entire published tile group.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._on_palette_item_selected(0)
	if editor._active_custom_group_id != "custom_test" or editor._selected_item_key != custom_tile_keys[1][1]:
		push_error("Selecting a server palette group did not activate its autotile brush.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._set_auto_brush(true)
	ground_layer["cells"] = {}
	editor._begin_canvas_stroke(_canvas_point_for_cell(editor, Vector2i(10, 10)), MOUSE_BUTTON_LEFT)
	editor._paint_canvas_drag_at(_canvas_point_for_cell(editor, Vector2i(13, 10)))
	editor._end_canvas_stroke(MOUSE_BUTTON_LEFT)
	var custom_cells: Dictionary = ground_layer["cells"]
	if custom_cells.size() != 12 \
		or str(custom_cells["10:10"]) != custom_tile_keys[0][0] \
		or str(custom_cells["13:10"]) != custom_tile_keys[0][2] \
		or str(custom_cells["10:12"]) != custom_tile_keys[4][0]:
		push_error("Опубликованная серверная группа не рисуется непрерывной кистью с краями и нижним продолжением.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	var original_custom_cells := custom_cells.duplicate(true)
	var custom_extension_touch_cells := original_custom_cells.duplicate(true)
	ground_layer["cells"] = custom_extension_touch_cells
	editor._last_stroke_cell = Vector2i(-1, -1)
	editor._paint_canvas_cell(Vector2i(11, 12))
	if str(custom_extension_touch_cells.get("11:11", "")) != custom_tile_keys[1][0] \
		or str(custom_extension_touch_cells.get("11:12", "")) != custom_tile_keys[2][0]:
		push_error("Касание дальнего ряда серверной группы 3×5 не включило промежуточный ряд в связный автотайлинг.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	ground_layer["cells"] = original_custom_cells
	custom_cells = original_custom_cells
	var custom_disconnected_test_cells := original_custom_cells.duplicate(true)
	ground_layer["cells"] = custom_disconnected_test_cells
	custom_cells = custom_disconnected_test_cells
	custom_cells["20:10"] = custom_tile_keys[1][1]
	editor._last_stroke_cell = Vector2i(-1, -1)
	editor._paint_canvas_cell(Vector2i(9, 10))
	if str(custom_cells.get("20:10", "")) != custom_tile_keys[1][1] \
		or str(custom_cells["10:10"]) != custom_tile_keys[0][1] \
		or str(custom_cells["9:10"]) != custom_tile_keys[0][0]:
		push_error("Серверная автокисть должна обновлять связный участок и оставлять раздельный участок нетронутым.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	ground_layer["cells"] = original_custom_cells
	custom_cells = original_custom_cells
	var custom_neighbor_before_erase := str(custom_cells["11:10"])
	editor._begin_canvas_stroke(_canvas_point_for_cell(editor, Vector2i(10, 11)), MOUSE_BUTTON_RIGHT)
	editor._end_canvas_stroke(MOUSE_BUTTON_RIGHT)
	if custom_cells.size() != 11 or custom_cells.has("10:11") \
		or not custom_cells.has("10:10") \
		or str(custom_cells["11:10"]) != custom_neighbor_before_erase:
		push_error("Стирание серверной группы должно удалить только выбранную клетку.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	var custom_serialized: Dictionary = editor._serialize_editor_layers()
	if custom_serialized["catalog_cells"].size() != 11:
		push_error("Серверные тайлы группы не сохраняются как элементы каталога карты.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	if not editor._save_atlas_corner_tile(
		atlas_path, Vector2i(2, 2), "inner_nw", Vector2i(0, 0),
	) or not editor._save_atlas_corner_tile(
		atlas_path, Vector2i(2, 2), "inner_nw", Vector2i(1, 0),
	):
		push_error("Настройка внутреннего угла не сохранилась.")
		_cleanup_annotations(annotation_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._atlas_corner_tiles[exact_mask_key] = Vector2i(2, 0)
	editor._selected_atlas_path = atlas_path
	editor._selected_item_key = editor._encode_atlas_cell(atlas_path, Vector2i(2, 2))
	var profile_path := "user://autotile_palette_smoke.json"
	if not editor._save_autotile_profile(profile_path):
		push_error("Профиль автокисти не удалось экспортировать.")
		_cleanup_annotations(annotation_path)
		_cleanup_profile(profile_path)
		editor.free()
		get_tree().quit(1)
		return
	var restored_editor = MAP_EDITOR.new()
	restored_editor._annotation_config_path = annotation_path
	restored_editor._load_atlas_annotations(annotation_path)
	restored_editor._atlas_sheets_by_path[atlas_path] = editor._atlas_sheets_by_path[atlas_path]
	restored_editor._selected_atlas_path = atlas_path
	restored_editor._selected_item_key = restored_editor._encode_atlas_cell(atlas_path, Vector2i(2, 2))
	if not restored_editor._load_autotile_profile(profile_path) \
		or restored_editor._atlas_corner_tiles.get(exact_mask_key, Vector2i(-1, -1)) != Vector2i(2, 0):
		push_error("Профиль автокисти не восстановил назначенную маску соседей.")
		_cleanup_annotations(annotation_path)
		_cleanup_profile(profile_path)
		restored_editor.free()
		editor.free()
		get_tree().quit(1)
		return
	if int(restored_editor._atlas_annotations.get(restored_editor._annotation_key(atlas_path, Vector2i(2, 2)), 0)) != 5:
		push_error("Разметка шаблона не пережила повторную загрузку.")
		_cleanup_annotations(annotation_path)
		_cleanup_profile(profile_path)
		restored_editor.free()
		editor.free()
		get_tree().quit(1)
		return
	if restored_editor._autotile_rule_tiles(
		restored_editor._corner_annotation_key(atlas_path, Vector2i(2, 2), "inner_nw"),
	) != [Vector2i(0, 0), Vector2i(1, 0)]:
		push_error("Варианты диагонального тайла не пережили повторную загрузку профиля.")
		_cleanup_annotations(annotation_path)
		_cleanup_profile(profile_path)
		restored_editor.free()
		editor.free()
		get_tree().quit(1)
		return
	restored_editor.free()
	var legacy_profile_path := "user://autotile_palette_legacy_smoke.json"
	var legacy_file := FileAccess.open(legacy_profile_path, FileAccess.WRITE)
	if legacy_file == null:
		push_error("Не удалось создать файл проверки старого формата профиля.")
		_cleanup_annotations(annotation_path)
		_cleanup_profile(profile_path)
		editor.free()
		get_tree().quit(1)
		return
	legacy_file.store_string(JSON.stringify({
		"format_version": 1,
		"profiles": [{
			"source_sheet": atlas_path.trim_prefix("res://"),
			"center": [2, 2],
			"rows": 5,
			"rules": [{"mask": 65, "tile": [0, 0]}],
			"named_rules": [],
		}],
	}))
	legacy_file.close()
	if not editor._load_autotile_profile(legacy_profile_path) \
		or editor._autotile_rule_tiles(exact_mask_key) != [Vector2i(0, 0)]:
		push_error("Профиль старого формата с полем tile не удалось загрузить.")
		_cleanup_annotations(annotation_path)
		_cleanup_profile(profile_path)
		_cleanup_profile(legacy_profile_path)
		editor.free()
		get_tree().quit(1)
		return
	_cleanup_profile(legacy_profile_path)
	var generated_profile: Dictionary = {
		"sheet_path": atlas_path,
		"center": Vector2i(2, 2),
		"rows": 5,
		"biome_path": str(editor._atlas_sheets_by_path[atlas_path]["biome_path"]),
	}
	var river_test_profile: Dictionary = generated_profile.duplicate(true)
	river_test_profile["feature"] = "river"
	river_test_profile["feature_name"] = "Реки"
	var river_route: Dictionary = editor._terrain_route_cells(
		river_test_profile, 16, 16, 1737, "river",
	)
	if river_route.is_empty() or editor._terrain_cell_component_seeds(river_route).size() != 1:
		push_error("Сгенерированное русло должно образовывать связную линию.")
		_cleanup_annotations(annotation_path)
		_cleanup_profile(profile_path)
		editor.free()
		get_tree().quit(1)
		return
	var warp_x := FastNoiseLite.new()
	warp_x.seed = 1935
	warp_x.frequency = 0.035
	warp_x.fractal_octaves = 2
	var warp_y := FastNoiseLite.new()
	warp_y.seed = 2043
	warp_y.frequency = 0.035
	warp_y.fractal_octaves = 2
	var boundary_positions: Dictionary = {}
	var test_biome_seeds: Array[Vector2i] = [Vector2i(12, 8), Vector2i(52, 54)]
	for y in range(64):
		for x in range(64):
			if editor._terrain_biome_index(
				Vector2i(x, y), test_biome_seeds, warp_x, warp_y, 64.0 * 0.12,
			) == 1:
				boundary_positions[x] = true
				break
	if boundary_positions.size() < 4:
		push_error("Границы биомов должны быть неровными, а не прямыми линиями Вороного.")
		_cleanup_annotations(annotation_path)
		_cleanup_profile(profile_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._show_terrain_generation_dialog()
	if editor._terrain_generation_dialog.theme != editor._ui_root.theme \
		or editor._terrain_generation_dialog.size != Vector2i(310, 285) \
		or editor._terrain_generation_biome_rows.get_parent().custom_minimum_size != Vector2(270, 95) \
		or editor._terrain_generation_dialog.get_ok_button().text != "Начать генерацию":
		push_error("Меню генерации не использует масштаб текста и размеров интерфейса редактора.")
		_cleanup_annotations(annotation_path)
		_cleanup_profile(profile_path)
		editor.free()
		get_tree().quit(1)
		return
	if editor._terrain_generation_biome_count_slider.min_value != 0 \
		or editor._terrain_generation_biome_count_slider.max_value != 6 \
		or not editor._terrain_generation_biome_count_slider.value_changed.is_connected(
			editor._on_terrain_biome_count_changed,
		) \
		or editor._terrain_generation_biome_options.is_empty() \
		or editor._terrain_generation_feature_sliders.size() != 3:
		push_error("В окне генерации отсутствуют диапазон биомов 0–6, выбор биома или ползунки воды, гор и леса.")
		_cleanup_annotations(annotation_path)
		_cleanup_profile(profile_path)
		editor.free()
		get_tree().quit(1)
		return
	for biome in editor._terrain_generation_biome_options:
		if "dungeon" in str(biome["path"]).to_lower() \
			or "cave" in str(biome["path"]).to_lower() \
			or "подземель" in str(biome["name"]).to_lower():
			push_error("Специальное подземелье не должно отображаться среди обычных биомов генератора.")
			_cleanup_annotations(annotation_path)
			_cleanup_profile(profile_path)
			editor.free()
			get_tree().quit(1)
			return
	editor._terrain_generation_biome_count_slider.value = 3
	editor._on_terrain_biome_count_changed(3)
	if editor._terrain_generation_biome_rows.get_child_count() != 3:
		push_error("Число строк выбора биомов не следует за ползунком 0–6.")
		_cleanup_annotations(annotation_path)
		_cleanup_profile(profile_path)
		editor.free()
		get_tree().quit(1)
		return
	for row in editor._terrain_generation_biome_rows.get_children():
		var selector := row.get_child(1) as OptionButton
		if selector.item_count == 0 or selector.get_item_text(0) != "Рандом" \
			or str(selector.get_item_metadata(0)) != "":
			push_error("Каждый новый биом должен по умолчанию иметь выбор «Рандом».")
			_cleanup_annotations(annotation_path)
			_cleanup_profile(profile_path)
			editor.free()
			get_tree().quit(1)
			return
	var initial_biome_selector := editor._terrain_generation_biome_rows.get_child(0).get_child(1) as OptionButton
	initial_biome_selector.select(1)
	var selected_biome_path := str(initial_biome_selector.get_item_metadata(initial_biome_selector.selected))
	editor._terrain_generation_biome_count_slider.value = 4
	editor._on_terrain_biome_count_changed(4)
	var preserved_biome_selector := editor._terrain_generation_biome_rows.get_child(0).get_child(1) as OptionButton
	if str(preserved_biome_selector.get_item_metadata(preserved_biome_selector.selected)) != selected_biome_path:
		push_error("Изменение количества биомов сбросило выбор в уже созданной строке.")
		_cleanup_annotations(annotation_path)
		_cleanup_profile(profile_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._terrain_generation_width.value = 16
	editor._terrain_generation_height.value = 20
	(editor._terrain_generation_feature_sliders["water"] as HSlider).value = 0
	(editor._terrain_generation_feature_sliders["mountain"] as HSlider).value = 0
	(editor._terrain_generation_feature_sliders["forest"] as HSlider).value = 0
	editor._terrain_generation_biome_count_slider.value = 0
	editor._on_terrain_biome_count_changed(0)
	if editor._terrain_generation_biome_rows.get_child_count() != 0:
		push_error("Нулевое количество биомов не очистило список выбора.")
		_cleanup_annotations(annotation_path)
		_cleanup_profile(profile_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._terrain_generation_biome_count_slider.value = 1
	editor._on_terrain_biome_count_changed(1)
	var generation_selector := editor._terrain_generation_biome_rows.get_child(0).get_child(1) as OptionButton
	for option_index in range(generation_selector.item_count):
		if str(generation_selector.get_item_metadata(option_index)) == generated_profile["biome_path"]:
			generation_selector.select(option_index)
			break
	editor._atlas_sheets_by_path[atlas_path]["category"] = "Объекты"
	editor._atlas_sheets_by_path[atlas_path]["name"] = "Test atlas"
	var original_map_width := int(editor._map_width.value)
	editor._generate_terrain_from_dialog(editor._terrain_generation_dialog)
	if not editor._last_terrain_generation_settings.is_empty() \
		or int(editor._map_width.value) != original_map_width \
		or "нет настроенной группы автокисти почвы" not in editor._status.text:
		push_error("Генератор должен явно отклонять запуск без настроенного профиля почвы.")
		_cleanup_annotations(annotation_path)
		_cleanup_profile(profile_path)
		editor.free()
		get_tree().quit(1)
		return
	editor._atlas_sheets_by_path[atlas_path]["category"] = "Почва"
	editor._generate_terrain_from_dialog(editor._terrain_generation_dialog)
	if editor._last_terrain_generation_settings.get("map_w") != 16 \
		or editor._last_terrain_generation_settings.get("map_h") != 20 \
		or editor._last_terrain_generation_settings.get("biome_count") != 1 \
		or editor._last_terrain_generation_settings.get("water") != 0 \
		or editor._last_terrain_generation_settings.get("mountain") != 0 \
		or editor._last_terrain_generation_settings.get("forest") != 0 \
		or editor._map_width.value != 16 or editor._map_height.value != 20 \
		or _get_layer_by_name(editor, "Авто · Биомы").get("cells", {}).is_empty():
		push_error("Кнопка «Начать генерацию» не создала слой биомов из выбранных параметров.")
		_cleanup_annotations(annotation_path)
		_cleanup_profile(profile_path)
		editor.free()
		get_tree().quit(1)
		return
	var completed_generation_settings: Dictionary = editor._last_terrain_generation_settings.duplicate(true)
	(editor._terrain_generation_feature_sliders["water"] as HSlider).value = 1
	editor._generate_terrain_from_dialog(editor._terrain_generation_dialog)
	if editor._last_terrain_generation_settings != completed_generation_settings \
		or "Для генерации «Вода» нет настроенной группы автокисти." not in editor._status.text:
		push_error("Генератор должен явно отклонять воду без отдельного профиля воды.")
		_cleanup_annotations(annotation_path)
		_cleanup_profile(profile_path)
		editor.free()
		get_tree().quit(1)
		return
	(editor._terrain_generation_feature_sliders["water"] as HSlider).value = 0
	var generation_biomes: Array[Dictionary] = [generated_profile]
	var generation_features: Array[Dictionary] = [generated_profile.duplicate(true)]
	generation_features[0]["feature"] = "forest"
	generation_features[0]["feature_name"] = "Лес"
	var generation_river_profile: Dictionary = generated_profile.duplicate(true)
	generation_river_profile["feature"] = "river"
	generation_river_profile["feature_name"] = "Реки"
	generation_features.append(generation_river_profile)
	var retained_layer_ids: Array[int] = []
	var previous_auto_layer_ids: Array[int] = []
	for layer in editor._layers:
		if str(layer.get("name", "")).begins_with("Авто · "):
			previous_auto_layer_ids.append(int(layer.get("id", 0)))
		else:
			retained_layer_ids.append(int(layer.get("id", 0)))
	editor._generate_terrain_layers(generation_biomes, generation_features, 1234)
	var generated_ground: Dictionary = _get_layer_by_name(editor, "Авто · Биомы")
	var generated_forest: Dictionary = _get_layer_by_name(editor, "Авто · Лес")
	var generated_river: Dictionary = _get_layer_by_name(editor, "Авто · Реки")
	if generated_ground.is_empty() or generated_forest.is_empty() or generated_river.is_empty() \
		or generated_ground["cells"].is_empty() or generated_forest["cells"].is_empty() \
		or generated_river["cells"].is_empty():
		push_error("Автогенератор не создал выбранные биомы, лесные области и русло: %s." % editor._status.text)
		_cleanup_annotations(annotation_path)
		_cleanup_profile(profile_path)
		editor.free()
		get_tree().quit(1)
		return
	for layer_id in retained_layer_ids:
		if editor._layer_index(layer_id) < 0:
			push_error("Автогенератор удалил слой, который должен был сохранить.")
			_cleanup_annotations(annotation_path)
			_cleanup_profile(profile_path)
			editor.free()
			get_tree().quit(1)
			return
	editor._undo_last_action()
	var restored_auto_layer_ids: Array[int] = []
	for layer in editor._layers:
		if str(layer.get("name", "")).begins_with("Авто · "):
			restored_auto_layer_ids.append(int(layer.get("id", 0)))
	if restored_auto_layer_ids.size() != previous_auto_layer_ids.size():
		push_error("Одна отмена не восстановила предыдущее состояние слоёв генерации.")
		_cleanup_annotations(annotation_path)
		_cleanup_profile(profile_path)
		editor.free()
		get_tree().quit(1)
		return
	for layer_id in previous_auto_layer_ids:
		if not restored_auto_layer_ids.has(layer_id):
			push_error("Отмена генерации не восстановила прежний автоматически созданный слой.")
			_cleanup_annotations(annotation_path)
			_cleanup_profile(profile_path)
			editor.free()
			get_tree().quit(1)
			return
	var artist_data: Dictionary = editor._load_glades_grass_artist_rules()
	var artist_rules: Dictionary = artist_data.get("rules", {})
	var full_mask_tiles: Array = artist_rules.get(255, [])
	if int(artist_data.get("sample_cells", 0)) != 674 \
		or artist_rules.size() != 67 \
		or not full_mask_tiles.has(Vector2i(2, 1)) \
		or full_mask_tiles.size() != 4:
		push_error("Правила травы не совпадают со слоем main space из образца Glades.tmx.")
		_cleanup_annotations(annotation_path)
		_cleanup_profile(profile_path)
		editor.free()
		get_tree().quit(1)
		return
	var artist_profile: Dictionary = {}
	for profile in editor._autotile_generation_profiles():
		if bool(profile.get("artist_reference", false)):
			artist_profile = profile.duplicate(true)
			break
	if artist_profile.is_empty():
		push_error("Биом «Луг» не подключил профиль из образца художника.")
		_cleanup_annotations(annotation_path)
		_cleanup_profile(profile_path)
		editor.free()
		get_tree().quit(1)
		return
	artist_profile["artist_rules"] = artist_rules
	editor._map_width.value = 16
	editor._map_height.value = 20
	editor._generate_terrain_layers([artist_profile], [], 20261115)
	var artist_ground: Dictionary = _get_layer_by_name(editor, "Авто · Биомы")
	var artist_cells: Dictionary = artist_ground.get("cells", {})
	var artist_positions: Dictionary = {}
	var used_grass_tiles: Dictionary = {}
	for cell_key in artist_cells:
		var decoded := editor._decode_atlas_cell(str(artist_cells[cell_key]))
		var coords: Vector2i = decoded.get("coords", Vector2i(-1, -1))
		if str(decoded.get("path", "")) != editor.GLADES_GRASS_SHEET \
			or coords.x < 1 or coords.x > 6 or coords.y < 0 or coords.y > 2:
			push_error("Сгенерированный луг использовал тайл вне травяного поля образца.")
			_cleanup_annotations(annotation_path)
			_cleanup_profile(profile_path)
			editor.free()
			get_tree().quit(1)
			return
		var parts := str(cell_key).split(":")
		var map_cell := Vector2i(int(parts[0]), int(parts[1]))
		artist_positions[map_cell] = coords
		used_grass_tiles[coords] = true
	if artist_cells.size() != 320 \
		or not full_mask_tiles.has(artist_positions.get(Vector2i(8, 10), Vector2i(-1, -1))) \
		or used_grass_tiles.size() < 2:
		push_error("Тестовая карта луга не применила основу и краевые тайлы художника.")
		_cleanup_annotations(annotation_path)
		_cleanup_profile(profile_path)
		editor.free()
		get_tree().quit(1)
		return
	for map_cell_variant in artist_positions:
		var map_cell: Vector2i = map_cell_variant
		var mask := editor._autotile_mask_for_cell(map_cell, artist_positions)
		var candidates: Array = artist_rules.get(mask, [])
		if candidates.size() < 2:
			continue
		for offset in [Vector2i.RIGHT, Vector2i.DOWN]:
			var neighbor: Vector2i = map_cell + offset
			if artist_positions.has(neighbor) \
				and editor._autotile_mask_for_cell(neighbor, artist_positions) == mask \
				and artist_positions[neighbor] == artist_positions[map_cell]:
				push_error("Соседние одинаковые маски луга повторили один и тот же вариант тайла.")
				_cleanup_annotations(annotation_path)
				_cleanup_profile(profile_path)
				editor.free()
				get_tree().quit(1)
				return
	_cleanup_annotations(annotation_path)
	_cleanup_profile(profile_path)
	print("Atlas, animal, LPC mob, and Glades grass generation smoke tests passed.")
	palette.queue_free()
	editor.free()
	get_tree().quit(0)


func _cleanup_settings(path: String) -> void:
	var absolute_path := ProjectSettings.globalize_path(path)
	if FileAccess.file_exists(absolute_path):
		DirAccess.remove_absolute(absolute_path)


func _cleanup_annotations(path: String) -> void:
	var absolute_path := ProjectSettings.globalize_path(path)
	if FileAccess.file_exists(absolute_path):
		DirAccess.remove_absolute(absolute_path)


func _cleanup_profile(path: String) -> void:
	var absolute_path := ProjectSettings.globalize_path(path)
	if FileAccess.file_exists(absolute_path):
		DirAccess.remove_absolute(absolute_path)


func _get_layer_by_name(editor, layer_name: String) -> Dictionary:
	for layer in editor._layers:
		if str(layer.get("name", "")) == layer_name:
			return layer
	return {}


func _canvas_point_for_cell(editor, cell: Vector2i) -> Vector2:
	return editor._pan + (Vector2(cell) + Vector2(0.5, 0.5)) * editor.TILE_SIZE * editor._zoom
