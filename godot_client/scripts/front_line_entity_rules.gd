extends RefCounted

# Правила сущностей мира Tower: порт scenes/world_map_scene.py (мобы, животные, труп, добыча, клик) и
# scenes/player_sprites.py (герой). Здесь числа, индексы кадров, переходы состояний и обработка изображений
# без отрисовки; отрисовку и кэш текстур делает tower_entity_view.gd.
# Направление и кадры бега/стойки берутся из deck_player_sprite_rules.gd: то же правило, но высота 90 px, а не 56.

const DECK_SPRITE := preload("res://scripts/deck_player_sprite_rules.gd")

const TILE_SIZE := 16.0
const DIRECTIONS := ["n", "ne", "e", "se", "s", "sw", "w", "nw"]

const NPC_FRAME_SIZE := 64
const NPC_FRAMES_PER_ROW := 4
const NPC_ROW_DOWN := 0
const NPC_ROW_UP := 1
const NPC_ROW_RIGHT := 2
const NPC_ROW_LEFT := 3
const NPC_COLORS := ["red", "green", "blue"]
const NPC_VARIANTS := ["vanilla", "sword", "pitchfork", "sword_shield", "pitchfork_shield"]
const MOB_CANVAS_SIZE := 16
const MOB_FIGURE_HEIGHT := 16
const MOB_FEET_Y := 16
const MOB_WALK_FPS := 8.0
const MOB_WALK_HOLD_MS := 300.0
const MOB_DEATH_FPS := 7.0
# Один проход анимации урона у моба после удара по нему.
const MOB_HURT_MS := 400.0
const MOB_DEATH_SIZE := 16
const MOB_CORPSE_FALL_MS := 500.0
const MOB_CORPSE_HOLD_MS := 30000.0
const MOB_CORPSE_FADE_MS := 15000.0

const ANIMAL_FRAME_MS := 160
const ANIMAL_SHEETS := {
	"buffalo": [64, 6, 6], "buffalo_cub": [64, 6, 6], "cat": [32, 8, 6], "colt": [32, 6, 6], "dog": [32, 6, 6],
	"donkey": [64, 6, 6], "drake": [32, 6, 6], "duck": [32, 6, 6], "duckling": [32, 6, 6],
}
const WATERFOWL_SHEETS := {
	"duck_water": [32, 6, 6], "drake_water": [32, 6, 6], "duckling_water": [32, 6, 6],
}
const WATERFOWL_WALK_ROWS := [8, 9, 10, 11]
const WATERFOWL_IDLE_ROWS := [12, 13, 14, 15]
const LAND_WALK_ROWS := [0, 1, 2, 3]
const LAND_IDLE_ROWS := [4, 5, 6, 7]

const PLAYER_SPRITE_HEIGHT := 90
const PLAYER_RUN_FPS := 10.0
const PLAYER_IDLE_FPS := 4.0
const WARRIOR_PROFESSION := "warrior"
const WARRIOR_ATTACKS := ["attack1", "attack2"]
const WARRIOR_ANIMATION_FOLDER := {
	"idle": "idle", "run": "walk", "walking": "walk", "attack1": "attack1", "attack2": "attack2",
	"gothit": "gothit", "death": "death",
}
const WARRIOR_SOURCE_FOLDERS := ["idle", "walk", "attack1", "attack2", "gothit", "death"]
const WARRIOR_BASE_FOLDERS := ["idle", "walk"]
const WARRIOR_WIDE_FOLDERS := ["attack1", "attack2", "gothit", "death"]
const WARRIOR_FIRST_FRAME_ANCHOR := ["gothit", "death"]
const WARRIOR_BODY_MIN_ALPHA := 201
const WARRIOR_FEET_BAND_SHARE := 0.25
const WARRIOR_FEET_MARGIN := 3
const WARRIOR_MIRROR_PARTNER := {
	"n": "n", "s": "s", "e": "w", "w": "e", "ne": "nw", "nw": "ne", "se": "sw", "sw": "se",
}
const HERO_HIT_SECONDS := 0.45
const HERO_DEATH_SECONDS := 1.0

const CORPSE_SIZE := Vector2(28.0, 20.0)
const CLICK_EFFECT_DURATION := 0.35
const HARVEST_BAR_SIZE := Vector2(40.0, 6.0)
const HARVEST_BAR_LIFT_PX := 10.0


static func py_round(value: float) -> int:
	var floored := floorf(value)
	var fraction := value - floored
	if fraction > 0.5:
		return int(floored) + 1
	if fraction < 0.5:
		return int(floored)
	var base := int(floored)
	return base if base % 2 == 0 else base + 1


static func facing_direction(delta: Vector2) -> String:
	return DECK_SPRITE.direction_for(delta)


# Строка листа NPC по углу взгляда: вниз, вверх, вправо или влево (_mob_facing_row, npc_catalog.facing_row).
static func npc_facing_row(angle: float) -> int:
	var dx := cos(angle)
	var dy := sin(angle)
	if absf(dx) >= absf(dy):
		return NPC_ROW_RIGHT if dx >= 0.0 else NPC_ROW_LEFT
	return NPC_ROW_DOWN if dy >= 0.0 else NPC_ROW_UP


# Индекс строки животного: 0 вниз, 1 вверх, 2 влево, 3 вправо (core/map_animals.animal_facing_index).
static func animal_facing_index(angle: float) -> int:
	var dx := cos(angle)
	var dy := sin(angle)
	if absf(dx) >= absf(dy):
		return 3 if dx >= 0.0 else 2
	return 0 if dy >= 0.0 else 1


static func walk_frame_index(now_msec: int, walking: bool, count: int = NPC_FRAMES_PER_ROW) -> int:
	if not walking:
		return 0
	return int(float(now_msec) / 1000.0 * MOB_WALK_FPS) % maxi(1, count)


static func attack_frame_index(now_msec: int, started_msec: float, attack_ms: float, count: int = NPC_FRAMES_PER_ROW) -> int:
	var progress := (float(now_msec) - started_msec) / maxf(1.0, attack_ms)
	return clampi(int(progress * count), 0, maxi(1, count) - 1)


# Кадры замаха в листе атаки: первая половина. Удар нарисован в середине листа, остальное — откат после удара.
static func attack_windup_frames(count: int) -> int:
	return maxi(1, floori(count * 0.5))


# Кадр одного цикла атаки по локальным часам (без зависимости от снимков): замах до удара идёт по первым
# split кадрам, откат после удара — по остальным. Вне цикла (до начала или после отката) — -1.
static func swing_frame(elapsed_ms: float, windup_ms: float, backswing_ms: float, count: int, split: int) -> int:
	var total := windup_ms + backswing_ms
	if count <= 0 or elapsed_ms < 0.0 or total <= 0.0 or elapsed_ms >= total:
		return -1
	var windup_frames := clampi(split, 1, count)
	if elapsed_ms < windup_ms:
		return clampi(int(elapsed_ms / maxf(1.0, windup_ms) * windup_frames), 0, windup_frames - 1)
	if windup_frames >= count:
		return -1
	var strike_progress := (elapsed_ms - windup_ms) / maxf(1.0, backswing_ms)
	return windup_frames + clampi(int(strike_progress * (count - windup_frames)), 0, count - windup_frames - 1)


# Кадр анимации урона моба за MOB_HURT_MS или -1, если моб не получал удара в этот момент.
static func mob_hurt_frame(state: Dictionary, now_msec: int, count: int) -> int:
	if count <= 0 or not state.has("hurt_started"):
		return -1
	var elapsed := float(now_msec) - float(state["hurt_started"])
	if elapsed < 0.0 or elapsed >= MOB_HURT_MS:
		return -1
	return clampi(int(elapsed / MOB_HURT_MS * count), 0, count - 1)


# Кадр атаки моба или -1, если моб не бьёт. Если снимок прислал swing_id, кадры идут по swing_frame;
# иначе (старый сервер) — по windup/backswing из снимка, как раньше.
static func mob_attack_frame(state: Dictionary, windup: float, now_msec: int, count: int, windup_frames: int) -> int:
	if count <= 0:
		return -1
	var split := clampi(windup_frames, 1, count)
	if state.has("swing_started"):
		return swing_frame(
			float(now_msec) - float(state["swing_started"]),
			float(state.get("swing_windup_ms", 0.0)),
			float(state.get("swing_backswing_ms", 0.0)),
			count,
			split,
		)
	if windup > 0.0:
		return attack_frame_index(
			now_msec, float(state.get("attack_started", 0.0)), float(state.get("attack_ms", 0.0)), split,
		)
	if split >= count or not state.has("strike_started"):
		return -1
	var elapsed := float(now_msec) - float(state["strike_started"])
	var strike_ms := float(state.get("strike_ms", 0.0))
	if elapsed < 0.0 or elapsed >= strike_ms:
		return -1
	return split + clampi(int(elapsed / maxf(1.0, strike_ms) * (count - split)), 0, count - split - 1)


static func mob_walking(now_msec: int, moved_at_msec: float) -> bool:
	return float(now_msec) - moved_at_msec < MOB_WALK_HOLD_MS


static func death_frame_index(elapsed_ms: float, count: int) -> int:
	return clampi(int(elapsed_ms / 1000.0 * MOB_DEATH_FPS), 0, maxi(0, count - 1))


static func corpse_visible(elapsed_ms: float) -> bool:
	return elapsed_ms < MOB_CORPSE_HOLD_MS + MOB_CORPSE_FADE_MS


static func corpse_fall_degrees(elapsed_ms: float) -> float:
	return 90.0 * clampf(elapsed_ms / MOB_CORPSE_FALL_MS, 0.0, 1.0)


# Прозрачность трупа 0..255: полная до MOB_CORPSE_HOLD_MS, дальше гаснет до нуля за MOB_CORPSE_FADE_MS.
static func corpse_alpha_byte(elapsed_ms: float) -> int:
	if elapsed_ms <= MOB_CORPSE_HOLD_MS:
		return 255
	var fade := (elapsed_ms - MOB_CORPSE_HOLD_MS) / MOB_CORPSE_FADE_MS
	return int(255.0 * (1.0 - fade))


static func hp_ratio(hp: float, max_hp: float) -> float:
	return clampf(hp / maxf(max_hp, 1.0), 0.0, 1.0)


static func corpse_distance_tiles(corpse_position: Vector2, player_position: Vector2) -> float:
	return corpse_position.distance_to(player_position) / TILE_SIZE


static func corpse_marker_rect(feet: Vector2) -> Rect2:
	return Rect2(feet.x - CORPSE_SIZE.x / 2.0, feet.y - CORPSE_SIZE.y, CORPSE_SIZE.x, CORPSE_SIZE.y)


static func center_rect(center: Vector2, size: Vector2) -> Rect2:
	return Rect2(center.x - floorf(size.x / 2.0), center.y - floorf(size.y / 2.0), size.x, size.y)


static func midbottom_rect(bottom_center: Vector2, size: Vector2) -> Rect2:
	return Rect2(bottom_center.x - floorf(size.x / 2.0), bottom_center.y - size.y, size.x, size.y)


static func tile_center(tile: Vector2i) -> Vector2:
	return Vector2((tile.x + 0.5) * TILE_SIZE, (tile.y + 0.5) * TILE_SIZE)


# Клетка из пары [x, y] или Vector2i; null — не клетка (например, добычи нет).
static func tile_of(value: Variant) -> Variant:
	if value is Vector2i:
		return value
	if value is Array and value.size() >= 2:
		return Vector2i(int(value[0]), int(value[1]))
	return null


static func harvest_visible(harvest: Variant) -> bool:
	return harvest is Dictionary and float(harvest.get("total", 0.0)) > 0.0


# Центр клетки добычи в мировых координатах (для перевода в экран перед draw_harvest_progress).
static func harvest_center(harvest: Variant) -> Vector2:
	if not harvest is Dictionary:
		return Vector2.ZERO
	return tile_center(Vector2i(int(harvest.get("x", 0)), int(harvest.get("y", 0))))


static func harvest_fill(harvest: Variant) -> float:
	if not harvest_visible(harvest):
		return 0.0
	return minf(1.0, float(harvest.get("progress", 0.0)) / float(harvest["total"]))


# Полоска добычи в экранных координатах, как _draw_harvest_progress: центр тайла, zoom — масштаб мира.
static func harvest_bar_rect(tile_center_screen: Vector2, zoom: float) -> Rect2:
	var left := int(tile_center_screen.x - HARVEST_BAR_SIZE.x / 2.0)
	var top := int(tile_center_screen.y - TILE_SIZE * zoom / 2.0 - HARVEST_BAR_LIFT_PX)
	return Rect2(left, top, HARVEST_BAR_SIZE.x, HARVEST_BAR_SIZE.y)


# Кольцо клика: radius в экранных px, alpha 0..255; timer_left — сколько секунд осталось (как в Python).
static func click_effect_style(timer_left: float) -> Dictionary:
	var progress := 1.0 - timer_left / CLICK_EFFECT_DURATION
	return {"radius": int(8.0 + progress * 16.0), "alpha": maxi(0, int(255.0 * (1.0 - progress)))}


static func player_state(warrior: bool, moving: bool, attacking: bool, hit: bool, dead: bool) -> String:
	if not warrior:
		return "run" if moving else "idle"
	if dead:
		return "death"
	if hit:
		return "gothit"
	if attacking:
		return "attack"
	return "run" if moving else "idle"


static func player_fps(state: String) -> float:
	return PLAYER_RUN_FPS if state == "run" or state == "walking" else PLAYER_IDLE_FPS


static func player_frame_index(state: String, anim_time: float, count: int, progress: float) -> int:
	if count <= 0:
		return 0
	if state == "attack" or state == "gothit" or state == "death":
		return mini(count - 1, int(clampf(progress, 0.0, 1.0) * count))
	return posmod(int(anim_time * player_fps(state)), count)


# Прогресс замаха 0..1; windup_total = 0 берётся как текущий замах, как `attack_windup_total or attack_windup`.
static func attack_progress(windup: float, windup_total: float) -> float:
	if windup <= 0.0:
		return 0.0
	var total := windup_total if windup_total != 0.0 else windup
	return 1.0 - windup / maxf(total, 1e-6)


# Сколько мс цикла атаки уже прошло к моменту снимка: по замаху, если он ещё идёт, иначе по откату.
static func _swing_elapsed_ms(payload: Dictionary, windup_ms: float, backswing_ms: float) -> float:
	var windup := float(payload.get("windup", 0.0))
	if windup > 0.0:
		return windup_ms - windup * 1000.0
	var backswing := float(payload.get("backswing", 0.0))
	return windup_ms + backswing_ms - backswing * 1000.0


# Переходы моба по снимку, как WorldMapScene._apply_world_mobs: движение, смерть и начало замаха.
# Интерполяция позиции моба между снимками: снимки приходят редко и неравномерно, поэтому моб плавно идёт
# от прошлой позиции к новой за время между снимками. Если снимок задержался, интервал растёт, а
# экстраполяция ограничена MOB_EXTRAPOLATE_LIMIT, чтобы моб не уезжал далеко.
const MOB_SNAPSHOT_MS := 200.0
# Буфер интерполяции: моб показывается с задержкой на MOB_INTERP_DELAY_MS по истории снимков (Dota-подход).
const MOB_INTERP_DELAY_MS := 100.0
const MOB_HISTORY_MAX := 8
const MOB_EXTRAPOLATE_LIMIT := 1.5


# Выпад вперёд в момент удара: короткий всплеск вдоль направления взгляда, центрирован на конце замаха.
const LUNGE_WINDOW_MS := 140.0
const HERO_LUNGE_PX := 3.0
const MOB_LUNGE_PX := 2.0


static func lunge_offset(elapsed_ms: float, windup_ms: float, facing: float, amplitude: float) -> Vector2:
	var offset := elapsed_ms - windup_ms
	if offset < -LUNGE_WINDOW_MS * 0.5 or offset > LUNGE_WINDOW_MS * 0.5:
		return Vector2.ZERO
	var phase := (offset + LUNGE_WINDOW_MS * 0.5) / LUNGE_WINDOW_MS
	return Vector2.from_angle(facing) * amplitude * sin(phase * PI)


static func mob_display_position(state: Dictionary, now_msec: int, current: Vector2) -> Vector2:
	# Показываем моба в момент now - задержка, по истории снимков; за последним снимком держим позицию, не экстраполируем.
	var history: Variant = state.get("history", null)
	if not history is Array or (history as Array).is_empty():
		return current
	var samples: Array = history
	var target := float(now_msec) - MOB_INTERP_DELAY_MS
	var first: Dictionary = samples[0]
	if target <= float(first["t"]):
		return Vector2(float(first["x"]), float(first["y"]))
	for index in range(samples.size() - 1):
		var older: Dictionary = samples[index]
		var newer: Dictionary = samples[index + 1]
		if target <= float(newer["t"]):
			var span := maxf(1.0, float(newer["t"]) - float(older["t"]))
			var fraction := clampf((target - float(older["t"])) / span, 0.0, 1.0)
			return Vector2(float(older["x"]), float(older["y"])).lerp(Vector2(float(newer["x"]), float(newer["y"])), fraction)
	var last: Dictionary = samples[samples.size() - 1]
	return Vector2(float(last["x"]), float(last["y"]))


static func advance_mob(previous: Dictionary, payload: Dictionary, now_msec: int) -> Dictionary:
	var state := previous.duplicate()
	var now := float(now_msec)
	var x := float(payload.get("x", 0.0))
	var y := float(payload.get("y", 0.0))
	if previous.is_empty() or previous.get("x") != x or previous.get("y") != y:
		state["moved_at"] = now
	if not previous.is_empty() and (previous.get("x") != x or previous.get("y") != y):
		state["prev_x"] = float(previous.get("x", x))
		state["prev_y"] = float(previous.get("y", y))
		state["snap_interval"] = clampf(now - float(previous.get("snap_msec", now - MOB_SNAPSHOT_MS)), 100.0, 1000.0)
		state["snap_msec"] = now
	var payload_state := str(payload.get("state", ""))
	var previous_state: Variant = previous.get("state", null)
	if payload_state == "dead" and previous_state != null and str(previous_state) != "dead":
		state["died_at"] = now
	var windup := float(payload.get("windup", 0.0))
	if windup > 0.0 and float(previous.get("windup", 0.0)) <= 0.0:
		state["attack_started"] = now
		state["attack_ms"] = float(payload.get("windup_total", 0.0)) * 1000.0
	var backswing := float(payload.get("backswing", 0.0))
	if backswing > 0.0 and float(previous.get("backswing", 0.0)) <= 0.0:
		var strike_total := maxf(backswing, float(payload.get("backswing_total", 0.0)))
		state["strike_started"] = now - (strike_total - backswing) * 1000.0
		state["strike_ms"] = strike_total * 1000.0
	var swing_id: Variant = payload.get("swing_id", null)
	if swing_id != null and previous.get("swing_id", null) != int(swing_id):
		var windup_ms := float(payload.get("windup_total", 0.0)) * 1000.0
		var backswing_ms := float(payload.get("backswing_total", 0.0)) * 1000.0
		state["swing_id"] = int(swing_id)
		state["swing_started"] = now - _swing_elapsed_ms(payload, windup_ms, backswing_ms)
		state["swing_windup_ms"] = windup_ms
		state["swing_backswing_ms"] = backswing_ms
	var hurt_id: Variant = payload.get("hurt_id", null)
	if hurt_id != null:
		if previous.get("hurt_id", null) != null and previous.get("hurt_id") != int(hurt_id):
			state["hurt_started"] = now
		state["hurt_id"] = int(hurt_id)
	elif previous.has("hp") and float(payload.get("hp", 0.0)) > 0.0 and float(payload.get("hp", 0.0)) < float(previous["hp"]):
		state["hurt_started"] = now
	state["x"] = x
	state["y"] = y
	state["state"] = payload_state
	state["windup"] = windup
	state["backswing"] = backswing
	state["hp"] = float(payload.get("hp", 0.0))
	var history: Array = []
	var previous_history: Variant = previous.get("history", [])
	if previous_history is Array:
		history = (previous_history as Array).duplicate()
	history.append({"t": now, "x": x, "y": y})
	while history.size() > MOB_HISTORY_MAX:
		history.pop_front()
	state["history"] = history
	state["facing"] = float(payload.get("facing", 0.0))
	return state


# Переходы героя по снимку, как WorldMapScene._track_player_hp и поля замаха. variant_roll — случайный
# вариант атаки 0/1, он выбирается только в начале замаха.
static func advance_hero(previous: Dictionary, player: Dictionary, anim_time: float, variant_roll: int) -> Dictionary:
	var state := previous.duplicate()
	var hp := float(player.get("hp", 0.0))
	var windup := float(player.get("windup", 0.0))
	var previous_hp: Variant = previous.get("hp", null)
	state["hit_started"] = previous.get("hit_started", null)
	state["death_started"] = previous.get("death_started", null)
	if previous_hp != null:
		var before := float(previous_hp)
		if hp <= 0.0 and before > 0.0:
			state["death_started"] = anim_time
			state["hit_started"] = null
		elif hp > 0.0:
			state["death_started"] = null
			if hp < before:
				state["hit_started"] = anim_time
	if windup > 0.0 and float(previous.get("windup", 0.0)) <= 0.0:
		state["variant"] = variant_roll
		state["attack_started"] = anim_time
	var backswing := float(player.get("backswing", 0.0))
	if backswing > 0.0 and float(previous.get("backswing", 0.0)) <= 0.0:
		var strike_total := maxf(backswing, float(player.get("backswing_total", 0.0)))
		state["strike_started"] = anim_time - (strike_total - backswing)
		state["strike_total"] = strike_total
	var swing_id: Variant = player.get("swing_id", null)
	if swing_id != null and previous.get("swing_id", null) != int(swing_id):
		var windup_ms := float(player.get("windup_total", 0.0)) * 1000.0
		var backswing_ms := float(player.get("backswing_total", 0.0)) * 1000.0
		state["swing_id"] = int(swing_id)
		state["swing_started"] = anim_time - _swing_elapsed_ms(player, windup_ms, backswing_ms) / 1000.0
		state["swing_windup_ms"] = windup_ms
		state["swing_backswing_ms"] = backswing_ms
	# Отмена замаха приказом: сервер сбросил замах и откат, локальный кадр удара снимаем.
	if state.has("swing_started") and windup <= 0.0 and backswing <= 0.0:
		if (anim_time - float(state["swing_started"])) * 1000.0 < float(state.get("swing_windup_ms", 0.0)):
			state.erase("swing_started")
	state["hp"] = hp
	state["windup"] = windup
	state["backswing"] = backswing
	state["windup_total"] = float(player.get("windup_total", 0.0))
	if not state.has("variant"):
		state["variant"] = 0
	return state


# Кадр атаки героя Front Line или -1: замах по первой половине листа, после удара — откат по второй.
# Откат после удара: герой уже пошёл, кадры удара не показываются, идёт ходьба.
static func swing_in_backswing(state: Dictionary, anim_time: float) -> bool:
	if not state.has("swing_started"):
		return false
	return (anim_time - float(state["swing_started"])) * 1000.0 >= float(state.get("swing_windup_ms", 0.0))


static func hero_attack_frame(state: Dictionary, anim_time: float, count: int) -> int:
	if count <= 0:
		return -1
	var split := attack_windup_frames(count)
	if state.has("swing_started"):
		return swing_frame(
			(anim_time - float(state["swing_started"])) * 1000.0,
			float(state.get("swing_windup_ms", 0.0)),
			float(state.get("swing_backswing_ms", 0.0)),
			count,
			split,
		)
	var windup := float(state.get("windup", 0.0))
	if windup > 0.0:
		var total := float(state.get("windup_total", 0.0))
		var progress := attack_progress(windup, total)
		if total > 0.0 and state.has("attack_started"):
			progress = (anim_time - float(state["attack_started"])) / total
		return clampi(int(clampf(progress, 0.0, 1.0) * split), 0, split - 1)
	if split >= count or not state.has("strike_started"):
		return -1
	var elapsed := anim_time - float(state["strike_started"])
	var strike_total := float(state.get("strike_total", 0.0))
	if elapsed < 0.0 or elapsed >= strike_total:
		return -1
	return split + clampi(int(elapsed / maxf(1e-6, strike_total) * (count - split)), 0, count - split - 1)


static func hero_hit_progress(state: Dictionary, anim_time: float) -> Variant:
	var started: Variant = state.get("hit_started", null)
	if started == null:
		return null
	var elapsed := anim_time - float(started)
	if elapsed >= HERO_HIT_SECONDS:
		return null
	return clampf(elapsed / HERO_HIT_SECONDS, 0.0, 1.0)


static func hero_death_progress(state: Dictionary, anim_time: float) -> Variant:
	var started: Variant = state.get("death_started", null)
	if started == null:
		return null
	return clampf((anim_time - float(started)) / HERO_DEATH_SECONDS, 0.0, 1.0)


# Файлы листов NPC по ключу вида из core/npc_catalog.py; {} — вида нет в каталоге.
static func npc_sheet_names(key: String) -> Dictionary:
	for color in NPC_COLORS:
		for variant in NPC_VARIANTS:
			var folder := "imp_%s_%s" % [color, variant]
			var catalog_key := ("imp_%s" % variant) if color == "red" else folder
			if catalog_key == key:
				return {
					"folder": folder,
					"walk": "%s walk.png" % folder,
					"attack": "%s attack.png" % folder,
					"death": "%s death.png" % folder,
				}
	return {}


# Описание листа животного по ключу animal_<вид> (core/map_animals.animal_sheet); {} — вида нет.
static func animal_layout(key: String) -> Dictionary:
	var name := key.trim_prefix("animal_")
	if WATERFOWL_SHEETS.has(name):
		var waterfowl: Array = WATERFOWL_SHEETS[name]
		return {
			"asset": name.trim_suffix("_water"), "frame_size": waterfowl[0], "columns": waterfowl[1],
			"frames": waterfowl[2], "walking_rows": WATERFOWL_WALK_ROWS, "idle_rows": WATERFOWL_IDLE_ROWS,
		}
	if not ANIMAL_SHEETS.has(name):
		return {}
	var sheet: Array = ANIMAL_SHEETS[name]
	return {
		"asset": name, "frame_size": sheet[0], "columns": sheet[1], "frames": sheet[2],
		"walking_rows": LAND_WALK_ROWS, "idle_rows": LAND_IDLE_ROWS,
	}


# Кадры листа животного: {"moving": [строка][кадр], "idle": [строка][0]}; кадры за пределами листа не берутся.
static func animal_frame_rects(layout: Dictionary, sheet_size: Vector2i) -> Dictionary:
	var size: int = layout["frame_size"]
	var result := {}
	for state in ["moving", "idle"]:
		var rows: Array = layout["walking_rows"] if state == "moving" else layout["idle_rows"]
		var count: int = layout["frames"] if state == "moving" else 1
		var state_rows: Array = []
		for row in rows:
			var row_rects: Array = []
			for column in range(count):
				var rect := Rect2i(column * size, int(row) * size, size, size)
				if rect.end.x > sheet_size.x or rect.end.y > sheet_size.y:
					break
				row_rects.append(rect)
			state_rows.append(row_rects)
		result[state] = state_rows
	return result


static func animal_frame_index(now_msec: int, count: int) -> int:
	return posmod(int(floorf(float(now_msec) / float(ANIMAL_FRAME_MS))), maxi(1, count))


# Границы пикселей с alpha >= min_alpha внутри region (get_bounding_rect(min_alpha) в pygame). Пустая — Rect2i().
static func opaque_rect(image: Image, min_alpha: int, region: Rect2i) -> Rect2i:
	var bounds := region.intersection(Rect2i(Vector2i.ZERO, image.get_size()))
	if not bounds.has_area():
		return Rect2i()
	var mask := BitMap.new()
	mask.create_from_image_alpha(image.get_region(bounds), (min_alpha - 1) / 255.0)
	var outlines := mask.opaque_to_polygons(Rect2i(Vector2i.ZERO, bounds.size), 0.0)
	if outlines.is_empty():
		return Rect2i()
	var low := Vector2(INF, INF)
	var high := Vector2(-INF, -INF)
	for outline in outlines:
		for point in outline:
			low = low.min(point)
			high = high.max(point)
	return Rect2i(bounds.position + Vector2i(low), Vector2i(high - low))


# Точка ног кадра героя: центр нижней полосы плотной фигуры по x и низ фигуры по y (_feet_anchor). Image — RGBA8.
static func feet_anchor(image: Image) -> Vector2i:
	var body := opaque_rect(image, WARRIOR_BODY_MIN_ALPHA, Rect2i(Vector2i.ZERO, image.get_size()))
	var band_height := maxi(2, int(body.size.y * WARRIOR_FEET_BAND_SHARE))
	var band := Rect2i(body.position.x, body.end.y - band_height, body.size.x, band_height)
	var band_body := opaque_rect(image, WARRIOR_BODY_MIN_ALPHA, band)
	var center := 0
	if band_body.has_area():
		center = band_body.position.x - band.position.x + band_body.size.x / 2
	return Vector2i(body.position.x + center, body.end.y)


static func median_int(values: Array) -> int:
	var ordered := values.duplicate()
	ordered.sort()
	return int(ordered[ordered.size() / 2])


static func warrior_scale(walk_heights: Array) -> float:
	return float(PLAYER_SPRITE_HEIGHT) / float(median_int(walk_heights))


static func scaled_size(size: Vector2i, scale: float) -> Vector2i:
	return Vector2i(maxi(1, py_round(size.x * scale)), maxi(1, py_round(size.y * scale)))


# Половина ширины, высота над ногами и под ногами холста по набору кадров; entries: [{anchor, box}].
static func warrior_extents(entries: Array) -> Vector3i:
	var half := -INF
	var above := -INF
	var below := -INF
	for entry in entries:
		var anchor: Vector2 = entry["anchor"]
		var box: Rect2i = entry["box"]
		half = maxf(half, maxf(anchor.x - box.position.x, box.end.x - anchor.x))
		above = maxf(above, anchor.y - box.position.y)
		below = maxf(below, box.end.y - anchor.y)
	return Vector3i(1 + ceili(half), ceili(above), ceili(below))


static func warrior_offset(anchor: Vector2, half: int, above: int) -> Vector2i:
	return Vector2i(py_round(half - anchor.x), py_round(above - anchor.y))


# Чем заменить отсутствующее направление: зеркальная пара, иначе ближайшее по кругу (_warrior_source_direction).
static func warrior_source(direction: String, available: Array) -> Dictionary:
	var partner: String = WARRIOR_MIRROR_PARTNER[direction]
	if available.has(partner):
		return {"source": partner, "mirrored": true}
	var index := DIRECTIONS.find(direction)
	var count := DIRECTIONS.size()
	for step in range(1, count):
		for candidate in [DIRECTIONS[posmod(index - step, count)], DIRECTIONS[(index + step) % count]]:
			if available.has(candidate):
				return {"source": candidate, "mirrored": false}
	return {"source": "", "mirrored": false}


static func mob_figure_size(crop_size: Vector2i, bounds_height: int) -> Vector2i:
	var height := maxi(1, bounds_height)
	var source_width := maxi(1, crop_size.x)
	var scale := minf(
		float(MOB_FIGURE_HEIGHT) / float(height),
		float(MOB_CANVAS_SIZE) / float(source_width),
	)
	return Vector2i(
		clampi(py_round(float(source_width) * scale), 1, MOB_CANVAS_SIZE),
		clampi(py_round(float(height) * scale), 1, MOB_CANVAS_SIZE),
	)


static func mob_canvas_offset(bounds: Rect2i) -> Vector2i:
	var center_x := bounds.position.x + bounds.size.x / 2
	return Vector2i(MOB_CANVAS_SIZE / 2 - center_x, MOB_FEET_Y - bounds.end.y)


# Обычный моб умещается в половину тайла; босс увеличивается в четыре раза при отрисовке.
static func normalize_npc_frame(cell: Image) -> Image:
	var canvas := Image.create_empty(MOB_CANVAS_SIZE, MOB_CANVAS_SIZE, false, Image.FORMAT_RGBA8)
	var bounds := cell.get_used_rect()
	if bounds.size.y <= 0:
		return canvas
	var crop := cell.get_region(bounds)
	var figure := mob_figure_size(bounds.size, bounds.size.y)
	crop.resize(figure.x, figure.y, Image.INTERPOLATE_NEAREST)
	blit_clipped(canvas, crop, mob_canvas_offset(crop.get_used_rect()))
	return canvas


# Копирует source на canvas в позицию offset, обрезая по краям холста (как blit в pygame).
static func blit_clipped(canvas: Image, source: Image, offset: Vector2i) -> void:
	var target := Rect2i(offset, source.get_size()).intersection(Rect2i(Vector2i.ZERO, canvas.get_size()))
	if not target.has_area():
		return
	canvas.blit_rect(source, Rect2i(target.position - offset, target.size), target.position)
