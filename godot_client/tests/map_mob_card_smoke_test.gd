extends Node

const PACK := "res://assets/base_tails/LPC/LPC Imp 2"
const FULL_STATES := ["idle", "walk", "run", "attack", "hurt", "death", "run_attack", "walk_attack"]
const FULL_ROW_ORDER := ["idle", "walk", "run", "attack", "run_attack", "walk_attack", "hurt", "death"]
const ODD_STATES := ["animation_1", "animation_2", "flight"]
const DIRECTION_ORDER := ["down", "left", "up", "right"]
const DIRECTION_TITLES := {"down": "вниз", "left": "влево", "up": "вверх", "right": "вправо"}
const SHEET_BLOCK_DIRECTIONS := ["down", "up", "left", "right"]
const FULL_NAME := "Гоблин-разведчик"
const ODD_NAME := "Очень длинное название моба для проверки обрезки текста"
const PLAIN_NAME := "Моб без направлений"


class CardEditor extends "res://scripts/map_editor.gd":
	var fake_mouse := Vector2(-1000, -1000)


	func _ready() -> void:
		_mode = "tower"
		_build_ui()


	func _animal_palette_item_at_position(_position: Vector2) -> int:
		return super(fake_mouse)


var editor: CardEditor
var failed := false
var walk_clips: Array = []


func _ready() -> void:
	call_deferred("_run")


func _check(condition: bool, message: String) -> bool:
	if not condition:
		push_error(message)
		failed = true
	return condition


func _frames(count: int) -> void:
	for _index in range(count):
		await get_tree().process_frame


func _finish() -> void:
	if is_instance_valid(editor):
		editor.free()
	if not failed:
		print("Mob card smoke tests passed: fixed size and position, pinning, close button, and green action and direction highlight.")
	get_tree().quit(1 if failed else 0)


func _run() -> void:
	editor = CardEditor.new()
	editor.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(editor)
	await _frames(2)
	if not _prepare_mobs():
		_finish()
		return
	editor._show_animal_palette(PACK)
	editor._version_overlay.visible = false
	editor.set_process(false)
	await _frames(3)
	var indexes := _palette_indexes()
	if not _check(
		indexes.has(FULL_NAME) and indexes.has(ODD_NAME) and indexes.has(PLAIN_NAME) \
			and editor._animal_palette.item_count >= 5,
		"В палитре тестового набора нет ожидаемых мобов.",
	):
		_finish()
		return
	await _check_card_geometry()
	if not failed:
		_check_direction_detection()
	if not failed:
		await _check_action_highlight(int(indexes[FULL_NAME]))
	if not failed:
		await _check_other_actions(int(indexes[ODD_NAME]))
	if not failed:
		await _check_plain_card(int(indexes[PLAIN_NAME]))
	if not failed:
		await _check_pin_flow()
	_finish()


func _prepare_mobs() -> bool:
	var paths: Array[String] = []
	editor._collect_lpc_png_files(PACK, paths)
	editor._build_lpc_imp_groups(PACK, "LPC Imp 2", "LPC Imp 2", paths)
	for candidate in editor._animal_groups:
		var walk_state: Dictionary = candidate.get("states", {}).get("walk", {})
		if not walk_state.is_empty():
			walk_clips = walk_state.get("clips", [])
			break
	if not _check(walk_clips.size() == 4, "У LPC Imp 2 не найдены четыре направления ходьбы."):
		return false
	var full: Dictionary = editor._get_or_create_lpc_mob_group(PACK, "probe", "full", FULL_NAME)
	for state_name in FULL_STATES:
		for clip in walk_clips:
			editor._add_lpc_mob_clip(full, state_name, clip.duplicate(true))
	var odd: Dictionary = editor._get_or_create_lpc_mob_group(PACK, "probe", "odd", ODD_NAME)
	for state_name in ODD_STATES:
		for clip in walk_clips:
			editor._add_lpc_mob_clip(odd, state_name, clip.duplicate(true))
	var plain: Dictionary = editor._get_or_create_lpc_mob_group(PACK, "probe", "plain", PLAIN_NAME)
	editor._add_lpc_mob_clip(plain, "animation_1", _without_direction(walk_clips[0]))
	return true


func _without_direction(clip: Dictionary) -> Dictionary:
	var copy: Dictionary = clip.duplicate(true)
	copy.erase("direction")
	return copy


func _palette_indexes() -> Dictionary:
	var result := {}
	for index in range(editor._animal_palette.item_count):
		var group: Dictionary = editor._animal_groups_by_key.get(
			str(editor._animal_palette.get_item_metadata(index)),
			{},
		)
		result[str(group.get("name", ""))] = index
	return result


func _highlighted_rows() -> Array[String]:
	var result: Array[String] = []
	for row_id in editor._animal_card_rows:
		var panel: PanelContainer = editor._animal_card_rows[row_id]["panel"]
		if panel.get_theme_stylebox("panel") == editor._animal_card_row_styles["current"]:
			result.append(str(row_id))
	return result


func _highlighted_arrows() -> Array[String]:
	var result: Array[String] = []
	for direction in editor._animal_card_directions:
		var panel: PanelContainer = editor._animal_card_directions[direction]["panel"]
		if panel.get_theme_stylebox("panel") == editor._animal_card_row_styles["current"]:
			result.append(str(direction))
	return result


func _current_clip_state() -> String:
	if editor._animal_preview_clips.is_empty():
		return ""
	return str(editor._animal_preview_clips[editor._animal_preview_clip_index].get("state", ""))


func _current_clip_direction() -> String:
	if editor._animal_preview_clips.is_empty():
		return ""
	return str(editor._animal_preview_clips[editor._animal_preview_clip_index].get("direction", ""))


func _check_card_geometry() -> void:
	var card: PanelContainer = editor._animal_hover_card
	var viewport_rect := get_viewport().get_visible_rect()
	var palette_rect: Rect2 = editor._animal_palette.get_global_rect()
	var expected_position: Vector2 = editor._animal_hover_card_position(
		palette_rect, editor.ANIMAL_CARD_SIZE, viewport_rect.size,
	)
	for label in card.find_children("*", "Label", true, false):
		if not _check(
			label.clip_text and label.text_overrun_behavior == TextServer.OVERRUN_TRIM_ELLIPSIS,
			"Текст карточки моба не обрезается и может менять её размер.",
		):
			return
	for index in range(editor._animal_palette.item_count):
		if not _check(
			editor._animal_palette.get_item_tooltip(index).is_empty(),
			"У строки моба в палитре не должно быть перекрывающего всплывающего текста.",
		):
			return
		editor._begin_animal_palette_preview(index)
		await _frames(2)
		var card_rect := Rect2(card.global_position, card.size)
		if not _check(card.visible, "Карточка не появилась при наведении на моба."):
			return
		if not _check(
			card.size == editor.ANIMAL_CARD_SIZE and card.custom_minimum_size == editor.ANIMAL_CARD_SIZE,
			"Размер карточки зависит от моба: %s вместо %s." % [card.size, editor.ANIMAL_CARD_SIZE],
		):
			return
		if not _check(
			card.global_position.is_equal_approx(expected_position)
				and not card_rect.intersects(palette_rect)
				and card.get_theme_font_size("font_size") == 8
				and card.mouse_filter == Control.MOUSE_FILTER_IGNORE
				and editor._animal_card_settings_button.disabled
				and editor._animal_card_close_button.disabled,
			"Карточка при наведении прыгает, перекрывает палитру или перехватывает мышь.",
		):
			return
	var center_offset := Rect2(card.global_position, card.size).get_center() - viewport_rect.get_center()
	_check(
		absf(center_offset.x) < 1.0 and absf(center_offset.y) < 1.0,
		"Карточка должна находиться в центре экрана, если не пересекается с палитрой.",
	)
	var shifted: Vector2 = editor._animal_hover_card_position(
		Rect2(300, 20, 500, 600), editor.ANIMAL_CARD_SIZE, Vector2(1280, 720),
	)
	var clamped: Vector2 = editor._animal_hover_card_position(
		Rect2(0, 0, 100, 100), editor.ANIMAL_CARD_SIZE, Vector2(200, 100),
	)
	_check(
		is_equal_approx(shifted.x, 808.0) and is_equal_approx(shifted.y, 268.0)
			and clamped == Vector2.ZERO,
		"Позиция карточки неверно сдвигается от палитры или выходит за экран.",
	)
	editor._reset_animal_palette_hover()


func _arrow_styles() -> Dictionary:
	var result := {}
	for direction in editor._animal_card_directions:
		var panel: PanelContainer = editor._animal_card_directions[direction]["panel"]
		var style := panel.get_theme_stylebox("panel")
		for style_name in editor._animal_card_row_styles:
			if editor._animal_card_row_styles[style_name] == style:
				result[direction] = style_name
	return result


func _check_action_highlight(index: int) -> void:
	var card: PanelContainer = editor._animal_hover_card
	editor._begin_animal_palette_preview(index)
	await _frames(2)
	var supported: Dictionary = editor._animal_card_supported
	for row_id in FULL_ROW_ORDER:
		if not _check(bool(supported.get(row_id, false)), "Действие «%s» не отмечено как доступное." % row_id):
			return
	if not _check(
		not bool(supported.get("jump", true)) and not bool(supported.get("other", true)),
		"Недоступные действия отмечены как доступные.",
	):
		return
	var expected: Array[String] = []
	for row_id in FULL_ROW_ORDER:
		for direction in DIRECTION_ORDER:
			expected.append("%s|%s" % [row_id, direction])
	if not _check(
		editor._animal_preview_clips.size() == expected.size(),
		"Шагов предпросмотра должно быть «действия × направления» (%d), а их %d." % [
			expected.size(), editor._animal_preview_clips.size(),
		],
	):
		return
	var seen: Array[String] = []
	var durations: Array[float] = []
	var step_started := 0.0
	var elapsed := 0.0
	var previous_index := -1
	var wrapped := false
	for _tick in range(1500):
		var step_index: int = editor._animal_preview_clip_index
		if step_index != previous_index:
			if previous_index >= 0:
				durations.append(elapsed - step_started)
			if step_index == 0 and previous_index >= 0:
				wrapped = true
				break
			var row_id := _current_clip_state()
			var direction := _current_clip_direction()
			if not _check(
				_highlighted_rows() == [row_id] and editor._animal_card_current_row == row_id,
				"Зелёной должна быть ровно одна строка — действие, которое сейчас показывает палитра: %s." % [
					_highlighted_rows(),
				],
			):
				return
			if not _check(
				_highlighted_arrows() == [direction],
				"Зелёной должна быть ровно одна стрелка — направление текущего действия: %s вместо %s." % [
					_highlighted_arrows(), direction,
				],
			):
				return
			var styles := _arrow_styles()
			for arrow in DIRECTION_ORDER:
				if not _check(
					styles.get(arrow, "") == ("current" if arrow == direction else "supported"),
					"Стрелка «%s» подсвечена неверно (%s) при направлении «%s»." % [
						arrow, styles.get(arrow, ""), direction,
					],
				):
					return
			var expected_text := "Сейчас: %s · %s (%d/%d)" % [
				editor._animal_state_title(row_id),
				DIRECTION_TITLES[direction],
				step_index + 1,
				expected.size(),
			]
			if not _check(
				editor._animal_card_state.text == expected_text,
				"Строка «Сейчас» показывает «%s» вместо «%s»." % [editor._animal_card_state.text, expected_text],
			):
				return
			seen.append("%s|%s" % [row_id, direction])
			step_started = elapsed
			previous_index = step_index
		editor._advance_animal_palette_preview(0.1)
		elapsed += 0.1
	if not _check(wrapped and seen == expected, "Каждое действие должно пройти все направления по очереди: %s." % [seen]):
		return
	if not _check(
		editor.ANIMAL_PREVIEW_MIN_STEP_SECONDS >= 0.5,
		"Минимальная выдержка шага подсветки короче полсекунды — её не успеть прочитать.",
	):
		return
	for duration in durations:
		if not _check(
			duration >= editor.ANIMAL_PREVIEW_MIN_STEP_SECONDS - 0.11,
			"Шаг подсветки слишком короткий: %.2f с." % duration,
		):
			return
	_check(card.visible, "Карточка пропала во время прокрутки действий.")
	editor._reset_animal_palette_hover()


func _check_other_actions(index: int) -> void:
	editor._begin_animal_palette_preview(index)
	await _frames(2)
	var supported: Dictionary = editor._animal_card_supported
	var highlighted := _highlighted_rows()
	_check(
		bool(supported.get("other", false)) and not bool(supported.get("idle", true))
			and highlighted == ["other"]
			and _highlighted_arrows() == ["down"]
			and editor._animal_card_state.text == "Сейчас: Анимация 1 · вниз (1/12)",
		"Нестандартные анимации должны подсвечивать строку «Другое» и все четыре направления.",
	)
	editor._reset_animal_palette_hover()


func _check_plain_card(index: int) -> void:
	editor._begin_animal_palette_preview(index)
	await _frames(2)
	var styles := _arrow_styles()
	for arrow in DIRECTION_ORDER:
		if not _check(
			styles.get(arrow, "") == "missing",
			"Если у моба нет данных о направлении, стрелка «%s» не должна подсвечиваться." % arrow,
		):
			return
	_check(
		editor._animal_preview_clips.size() == 1
			and _current_clip_direction().is_empty()
			and _highlighted_arrows().is_empty()
			and editor._animal_card_state.text == "Сейчас: Анимация 1 (1/1)",
		"Моб без направлений должен показываться одним шагом без подсвеченной стрелки.",
	)
	editor._reset_animal_palette_hover()


func _check_direction_detection() -> void:
	var explicit: Array[Dictionary] = editor._animal_state_direction_clips({"clips": walk_clips})
	var explicit_order: Array[String] = []
	for entry in explicit:
		explicit_order.append(str(entry["direction"]))
	if not _check(
		explicit_order == DIRECTION_ORDER,
		"Направления должны идти по кругу «вниз, влево, вверх, вправо»: %s." % [explicit_order],
	):
		return
	var all_directions: Dictionary = editor._animal_group_directions({"states": {"walk": {"clips": walk_clips}}})
	if not _check(
		all_directions == {"up": true, "down": true, "left": true, "right": true},
		"Объединение направлений моба определено неверно: %s." % [all_directions],
	):
		return

	var shortened: Array = []
	for clip in walk_clips:
		var copy: Dictionary = clip.duplicate(true)
		copy["frame_ids"] = [copy["frame_ids"][0]]
		shortened.append(copy)
	var doubled: Array = walk_clips.duplicate(true) + shortened
	var deduped: Array[Dictionary] = editor._animal_state_direction_clips({"clips": doubled})
	if not _check(deduped.size() == 4, "Повторные клипы одного направления должны схлопываться."):
		return
	for entry in deduped:
		if not _check(
			entry["clip"]["frame_ids"].size() > 1,
			"Из повторных клипов направления должен выбираться первый.",
		):
			return

	var unplayable: Array[Dictionary] = editor._animal_state_direction_clips({"clips": [
		{"direction": "up", "frame_ids": []},
		walk_clips[0],
	]})
	if not _check(
		unplayable.size() == 1 and unplayable[0]["direction"] == "down",
		"Клип без кадров не должен давать направление.",
	):
		return

	var stripped: Array = []
	for clip in walk_clips:
		stripped.append(_without_direction(clip))
	var sheet: Dictionary = editor._atlas_sheets_by_path.get(str(stripped[0]["sheet_path"]), {})
	var rows := int(sheet.get("rows", 0))
	var columns := int(sheet.get("columns", 0))
	if not _check(rows % 4 == 0 and columns > 0, "Лист LPC Imp 2 не делится на четыре блока направлений."):
		return
	var by_block: Array[Dictionary] = editor._animal_state_direction_clips({"clips": stripped})
	var block_directions := {}
	var used_blocks := {}
	for clip in stripped:
		used_blocks[int(clip["origin_tile_id"]) / columns * 4 / rows] = true
	for entry in by_block:
		var block: int = int(entry["clip"]["origin_tile_id"]) / columns * 4 / rows
		block_directions[str(entry["direction"])] = block
		if not _check(
			entry["direction"] == SHEET_BLOCK_DIRECTIONS[block],
			"Клип из блока %d листа должен получать направление «%s», а не «%s»." % [
				block, SHEET_BLOCK_DIRECTIONS[block], entry["direction"],
			],
		):
			return
	if not _check(
		by_block.size() == used_blocks.size() and by_block.size() >= 2,
		"Клипы одного листа из разных блоков должны получить разные направления: %s." % [block_directions],
	):
		return

	var single: Array[Dictionary] = editor._animal_state_direction_clips({"clips": [stripped[0]]})
	_check(
		single.size() == 1 and str(single[0]["direction"]).is_empty(),
		"Единственный клип без явного направления не должен получать направление по блоку.",
	)
	var plain_group := {"kind": "mob", "states": {"animation_1": {"clips": [stripped[0]]}}}
	var plain_sequence: Array[Dictionary] = editor._animal_palette_preview_sequence(plain_group)
	_check(
		plain_sequence.size() == 1 and str(plain_sequence[0]["direction"]).is_empty(),
		"Последовательность предпросмотра моба без направлений должна состоять из одного шага.",
	)


func _item_center(index: int) -> Vector2:
	var rect: Rect2 = editor._animal_palette.get_item_rect(index, true)
	return editor._animal_palette.get_global_rect().position + rect.get_center()


func _move_mouse(point: Vector2) -> void:
	editor.fake_mouse = point - editor._animal_palette.global_position
	var motion := InputEventMouseMotion.new()
	motion.position = point
	motion.global_position = point
	get_viewport().push_input(motion, true)
	await _frames(3)


func _click(point: Vector2) -> void:
	await _move_mouse(point)
	for pressed in [true, false]:
		var button := InputEventMouseButton.new()
		button.button_index = MOUSE_BUTTON_LEFT
		button.pressed = pressed
		button.position = point
		button.global_position = point
		button.button_mask = MOUSE_BUTTON_MASK_LEFT if pressed else 0
		get_viewport().push_input(button, true)
		await _frames(2)


func _card_state(hovered_key: String, pinned_key: String) -> bool:
	var card: PanelContainer = editor._animal_hover_card
	if hovered_key.is_empty():
		return card.visible == false and editor._animal_hover_card_key.is_empty() \
			and editor._animal_card_pinned_key == pinned_key
	var pinned := not pinned_key.is_empty()
	return card.visible and editor._animal_hover_card_key == hovered_key \
		and editor._animal_card_pinned_key == pinned_key \
		and (card.mouse_filter == Control.MOUSE_FILTER_STOP) == pinned \
		and editor._animal_card_close_button.disabled != pinned \
		and editor._animal_card_settings_button.disabled != pinned \
		and editor._animal_card_hint.text == ("Закреплено" if pinned else "ЛКМ — закрепить")


func _check_pin_flow() -> void:
	editor.set_process(true)
	var key_a := str(editor._animal_palette.get_item_metadata(1))
	var key_b := str(editor._animal_palette.get_item_metadata(2))
	var key_c := str(editor._animal_palette.get_item_metadata(3))
	await _move_mouse(Vector2(900, 100))
	if not _check(_card_state("", ""), "Карточка видна, когда мышь вне палитры."):
		return
	await _move_mouse(_item_center(1))
	if not _check(_card_state(key_a, ""), "Наведение на моба не показывает его карточку."):
		return
	await _move_mouse(_item_center(3))
	if not _check(_card_state(key_c, ""), "При наведении на другого моба карточка не переключилась."):
		return
	await _move_mouse(Vector2(900, 100))
	if not _check(_card_state("", ""), "Карточка не исчезла, когда мышь покинула моба."):
		return

	await _click(_item_center(3))
	if not _check(_card_state(key_c, key_c), "ЛКМ по мобу не закрепляет карточку."):
		return
	await _move_mouse(_item_center(1))
	if not _check(_card_state(key_c, key_c), "Закреплённая карточка реагирует на наведение на других мобов."):
		return
	await _move_mouse(Vector2(900, 100))
	if not _check(_card_state(key_c, key_c), "Закреплённая карточка исчезла вместе с наведением."):
		return
	await _click(_item_center(2))
	if not _check(_card_state(key_b, key_b), "ЛКМ по другому мобу не переносит закрепление."):
		return

	var close_point: Vector2 = editor._animal_card_close_button.get_global_rect().get_center()
	await _click(close_point)
	if not _check(_card_state("", ""), "Кнопка «Закрыть» не закрывает закреплённую карточку."):
		return
	await _move_mouse(_item_center(1))
	if not _check(_card_state(key_a, ""), "После закрытия наведение снова не работает."):
		return

	await _click(_item_center(1))
	if not _check(_card_state(key_a, key_a), "Карточку не удалось закрепить повторно."):
		return
	var settings_point: Vector2 = editor._animal_card_settings_button.get_global_rect().get_center()
	await _click(settings_point)
	if not _check(
		_card_state("", "") and editor._pending_mob_profile_key == key_a,
		"Кнопка «Настроить моба» не открывает профиль выбранного моба.",
	):
		return

	editor._pin_animal_hover_card(2)
	await _frames(2)
	editor._on_animal_item_activated(2)
	await _frames(2)
	_check(
		_card_state("", "") and editor._pending_mob_profile_key == key_b,
		"Двойной щелчок по мобу должен открыть профиль и убрать карточку.",
	)
