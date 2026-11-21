extends RefCounted

# Спрайты персонажей города Экономики (герой и AFK-игроки): порт load_player_directional_sprites (scenes/player_sprites.py)
# и player_frame для не-воина: бег assets/3run при ходьбе (10 кадров/с), стойка assets/2Idle иначе (4 кадра/с),
# высота 90 px. Воин берёт кадры assets/warrior через загрузчик Tower (warrior_frame_sets): тот же масштаб и ноги.

const DECK_SPRITE := preload("res://scripts/deck_player_sprite_rules.gd")
const TOWER_VIEW := preload("res://scripts/tower_entity_view.gd")
const IDLE_FOLDER := "2Idle"
const RUN_FOLDER := "3run"
const WARRIOR_FOLDER := "warrior"
const SPRITE_HEIGHT := 90
const RUN_FPS := 10.0
const IDLE_FPS := 4.0
const WARRIOR_PROFESSION := "warrior"

static var _warrior_sets: Dictionary = {}
static var _warrior_loaded := false


static func assets_root(project_dir: String) -> String:
	return DECK_SPRITE.assets_root(project_dir)


static func frame_sets(root: String) -> Dictionary:
	return {
		"idle": DECK_SPRITE.directional_frames(root.path_join(IDLE_FOLDER), SPRITE_HEIGHT),
		"run": DECK_SPRITE.directional_frames(root.path_join(RUN_FOLDER), SPRITE_HEIGHT),
	}


static func is_warrior(character: Dictionary) -> bool:
	return str(character.get("type", "")) == WARRIOR_PROFESSION


# Кадры воина по состояниям: idle — стойка, run — ходьба (walk в load_warrior_directional_frames). Загрузчик Tower сам
# масштабирует фигуру до 90 px и ставит ноги; набор грузится один раз. Пустой словарь, если кадров нет.
static func warrior_frame_sets(root: String) -> Dictionary:
	if not _warrior_loaded:
		_warrior_loaded = true
		var built: Dictionary = TOWER_VIEW.build_warrior_images(root.path_join(WARRIOR_FOLDER))
		if not built.is_empty():
			var animations: Dictionary = built["animations"]
			_warrior_sets = {
				"idle": _textures_by_direction(animations["idle"]),
				"run": _textures_by_direction(animations["run"]),
			}
	return _warrior_sets


static func _textures_by_direction(frames_by_direction: Dictionary) -> Dictionary:
	var textures := {}
	for direction in frames_by_direction:
		var frames: Array = []
		for image in frames_by_direction[direction]:
			frames.append(ImageTexture.create_from_image(image))
		textures[direction] = frames
	return textures


# Кадр или null, если кадров нет. Бег, если бег загружен; иначе стойка. Темп кадров задаёт состояние, как в Python.
static func frame_for(sets: Dictionary, moving: bool, direction: String, anim_time: float) -> Texture2D:
	var run: Dictionary = sets.get("run", {})
	var frames_by_direction: Dictionary = run if moving and not run.is_empty() else sets.get("idle", {})
	if frames_by_direction.is_empty():
		return null
	var frames: Array = DECK_SPRITE.frames_for_direction(frames_by_direction, direction)
	if frames.is_empty():
		return null
	var fps := RUN_FPS if moving else IDLE_FPS
	return frames[DECK_SPRITE.frame_index(anim_time, fps, frames.size())]
