extends Node

const PREVIEW_SCRIPT := preload("res://scripts/magic_casting_preview.gd")

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	_run()
	for failure in _failures:
		push_error(failure)
	if _failures.is_empty():
		print("magic_casting_preview_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(0 if _failures.is_empty() else 1)


func _run() -> void:
	var preview = PREVIEW_SCRIPT.new()
	var classes := ["warrior", "archer", "mage"]
	var directions := ["s", "w", "e", "n"]
	for profession in classes:
		for level in range(1, 10):
			for direction in directions:
				var texture: Texture2D = preview.frame_texture(profession, level, direction, 0)
				_check(texture != null and texture.get_size() == Vector2i(64, 64), "%s level %d direction %s frame 0" % [profession, level, direction])
			var last_frame: Texture2D = preview.frame_texture(profession, level, "s", 4)
			_check(last_frame != null and last_frame.get_size() == Vector2i(64, 64), "%s level %d frame 4" % [profession, level])


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)
