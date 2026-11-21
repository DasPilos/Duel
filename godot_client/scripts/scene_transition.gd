extends Node

const DURATION := 1.0 / 1.3 / 1.5
const GROUP := "scene_transition"


# Замораживает кадр, затемняет его, блокирует ввод и один раз вызывает change_scene, когда экран почернел;
# новая сцена появляется сразу, как в Python-клиенте. Пока переход идёт, повторный запрос игнорируется и возвращает null.
static func run(tree: SceneTree, change_scene: Callable) -> CanvasLayer:
	if is_running(tree):
		return null
	var layer := CanvasLayer.new()
	layer.layer = 100
	layer.add_to_group(GROUP)
	var viewport_image: Image = null
	if DisplayServer.get_name() != "headless":
		viewport_image = tree.root.get_texture().get_image()
	if viewport_image != null:
		var frame := TextureRect.new()
		frame.texture = ImageTexture.create_from_image(viewport_image)
		frame.mouse_filter = Control.MOUSE_FILTER_STOP
		frame.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		frame.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		frame.stretch_mode = TextureRect.STRETCH_SCALE
		layer.add_child(frame)
	var shade := ColorRect.new()
	shade.color = Color(0, 0, 0, 0)
	shade.mouse_filter = Control.MOUSE_FILTER_STOP
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	layer.add_child(shade)
	layer.add_child(InputBlocker.new())
	tree.root.add_child(layer)
	var tween := layer.create_tween()
	tween.tween_property(shade, "color:a", 1.0, DURATION)
	tween.tween_callback(_finish.bind(tree, change_scene, layer))
	return layer


# Идёт ли переход: слой уже добавлен, но ещё не освобождён.
static func is_running(tree: SceneTree) -> bool:
	for layer in tree.get_nodes_in_group(GROUP):
		if not layer.is_queued_for_deletion():
			return true
	return false


# Ждёт конца перехода вместе с освобождением слоя: нужно тестам и сценам, которым важен итоговый экран.
static func wait_until_idle(tree: SceneTree) -> void:
	while is_running(tree):
		await tree.process_frame


static func _finish(tree: SceneTree, change_scene: Callable, layer: CanvasLayer) -> void:
	if change_scene.is_valid():
		change_scene.call()
	tree.create_timer(0.1).timeout.connect(layer.queue_free)


# Поглощает все события до интерфейса сцены: мышь и клавиатура не работают, пока экран темнеет.
class InputBlocker extends Node:
	func _ready() -> void:
		set_process_input(true)

	func _input(_event: InputEvent) -> void:
		get_viewport().set_input_as_handled()
