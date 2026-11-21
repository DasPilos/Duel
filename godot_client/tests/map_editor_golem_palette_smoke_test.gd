extends Node

const EDITOR_SCRIPT = preload("res://scripts/map_editor.gd")
const PACK_FOLDER := "craftpix-net-625807-golem-pixel-art-top-down-sprite-pack"
const PACK_PATH := "res://assets/base_tails/LPC/" + PACK_FOLDER


class GolemEditor extends "res://scripts/map_editor.gd":
	func _ready() -> void:
		_mode = "front_line"
		_build_ui()


var editor: GolemEditor
var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)


func _run() -> void:
	editor = GolemEditor.new()
	editor.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(editor)
	await get_tree().process_frame

	var sheet_paths: Array[String] = []
	editor._collect_lpc_png_files(PACK_PATH, sheet_paths)
	sheet_paths.sort()
	for sheet_path in sheet_paths:
		if not sheet_path.get_file().to_lower().ends_with("_with_shadow.png"):
			continue
		editor._add_atlas_sheet(
			sheet_path,
			PACK_PATH,
			editor._lpc_pack_display_name(PACK_FOLDER),
			16,
			"Спрайты LPC",
			false,
			false,
			{},
			false,
		)
	editor._build_animal_groups(PACK_PATH, PACK_FOLDER, "mob")
	var names := {}
	for group in editor._animal_groups:
		if str(group.get("pack_path", "")) == PACK_PATH:
			names[str(group.get("name", ""))] = group

	_check(editor._lpc_pack_display_name(PACK_FOLDER) == "Големы", "Набор подписан «Големы».")
	_check(
		names.has("Голем 1") and names.has("Голем 2") and names.has("Голем 3"),
		"Три варианта голема появились как отдельные мобы.",
	)
	var golem: Dictionary = names.get("Голем 1", {})
	var states: Dictionary = golem.get("states", {})
	_check(
		golem.get("kind") == "mob"
		and golem.get("default_state") == "idle"
		and states.has("idle") and states.has("walk") and states.has("run")
		and states.has("attack") and states.has("hurt") and states.has("death"),
		"У голема собраны состояния покоя, движения, атаки, получения урона и смерти.",
	)
	_check(
		states.get("idle", {}).get("clips", []).size() == 4
		and states.get("walk", {}).get("clips", []).size() == 4,
		"Листы голема собраны по четырём направлениям.",
	)
	editor._show_animal_palette(PACK_PATH)
	_check(
		editor._animal_palette.visible and editor._animal_palette.item_count == 3,
		"Набор и три голема отображаются в палитре мобов.",
	)
	for golem_name in ["Голем 1", "Голем 2", "Голем 3"]:
		var golem_states: Dictionary = names[golem_name].get("states", {})
		var idle_clips: Array = golem_states.get("idle", {}).get("clips", [])
		var idle_path := str(idle_clips[0].get("sheet_path", "")) if not idle_clips.is_empty() else ""
		var idle_sheet: Dictionary = editor._atlas_sheets_by_path.get(idle_path, {})
		_check(
			idle_sheet.get("texture") is Texture2D,
			"%s отображается с загруженным изображением." % golem_name,
		)

	for failure in _failures:
		push_error(failure)
	if _failures.is_empty():
		print("map_editor_golem_palette_smoke_test: OK (%d checks)" % _checks)
	if is_instance_valid(editor):
		editor.free()
	get_tree().quit(0 if _failures.is_empty() else 1)
