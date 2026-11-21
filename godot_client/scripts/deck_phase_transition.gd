extends Control

# Переход между фазами боя, как deck/ui/phase_transition.py: кадр замораживается, экран темнеет за duration секунд,
# затем вызывается on_finished, и показывается новая фаза. Затухание музыки пока не перенесено (см. port-audio).
const DEFAULT_DURATION := 0.75

var _duration := DEFAULT_DURATION
var _elapsed := 0.0
var _active := false
var _on_finished := Callable()
var _frozen: TextureRect
var _shade: ColorRect


static func transition_kind(previous_phase: String, next_phase: String) -> String:
	if previous_phase == "draft" and next_phase == "planning":
		return "battle_start"
	if next_phase == "result" and previous_phase != "result" and not previous_phase.is_empty():
		return "result"
	return ""


func _init() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = false
	_frozen = TextureRect.new()
	_frozen.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_frozen.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_frozen.stretch_mode = TextureRect.STRETCH_SCALE
	_frozen.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_frozen)
	_shade = ColorRect.new()
	_shade.color = Color(0, 0, 0, 0)
	_shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_shade)


func is_active() -> bool:
	return _active


# Во время перехода новый вызов игнорируется, как в Python.
func play(on_finished: Callable, duration := DEFAULT_DURATION) -> void:
	if _active:
		return
	_active = true
	_duration = maxf(0.01, duration)
	_elapsed = 0.0
	_on_finished = on_finished
	_shade.color = Color(0, 0, 0, 0)
	mouse_filter = Control.MOUSE_FILTER_STOP
	visible = true
	_frozen.texture = _capture_frame()


# В headless-режиме рендера нет, кадр не захватывается.
func _capture_frame() -> Texture2D:
	if DisplayServer.get_name() == "headless":
		return null
	var image := get_viewport().get_texture().get_image()
	if image == null or image.is_empty():
		return null
	return ImageTexture.create_from_image(image)


func _process(delta: float) -> void:
	if not _active:
		return
	_elapsed += delta
	var progress := minf(1.0, _elapsed / _duration)
	_shade.color = Color(0, 0, 0, progress)
	if progress < 1.0:
		return
	_active = false
	visible = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_frozen.texture = null
	var callback := _on_finished
	_on_finished = Callable()
	if callback.is_valid():
		callback.call()
