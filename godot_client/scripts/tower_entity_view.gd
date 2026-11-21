extends RefCounted

# Отрисовка сущностей мира Tower (порт scenes/world_map_scene.py: _draw_mobs, _draw_player_corpses,
# _draw_player_character, _draw_harvest_progress, _draw_click_effect) с кадрами из ../assets.
# Координаты мира — пиксели Python (тайл 32), вызывающий задаёт transform канвы. Подписи и полоски, которые
# не должны масштабироваться, отдаются числами (mob_overheads, player_overhead, corpse_overheads); полоска
# добычи и кольцо клика рисуются в экранных координатах (draw_harvest_progress, draw_click_effect).

const RULES := preload("res://scripts/tower_entity_rules.gd")
const DECK_SPRITE := preload("res://scripts/deck_player_sprite_rules.gd")
const SHAPE_RULES := preload("res://scripts/economy_citizen_sprite_rules.gd")
const FRONT_LINE_SPRITES := preload("res://scripts/front_line_hero_sprite_rules.gd")

const PLAYER_NAME_FALLBACK := "Герой"
const PLAYER_SHADOW_COLOR := Color(10 / 255.0, 12 / 255.0, 16 / 255.0, 170 / 255.0)
const SELECT_COLOR := Color(1.0, 215 / 255.0, 60 / 255.0)
const CORPSE_FILL_COLOR := Color(70 / 255.0, 70 / 255.0, 78 / 255.0)
const CORPSE_COLOR := Color(190 / 255.0, 190 / 255.0, 200 / 255.0)
const CLICK_RGB := Color(80 / 255.0, 255 / 255.0, 120 / 255.0)
const HARVEST_BACK_COLOR := Color(30 / 255.0, 30 / 255.0, 30 / 255.0)
const HARVEST_FILL_COLOR := Color(120 / 255.0, 220 / 255.0, 1.0)
const OVERHEAD_BAR_SIZE := Vector2(100.0, 10.0)
const OVERHEAD_GAP := 2.0
const MOB_BAR_SIZE := Vector2(100.0, 5.0)
const MOB_BAR_GAP := 3.0
const CRYSTAL_RING_RADIUS := 18.0
const CRYSTAL_PULSE := 0.12
const CRYSTAL_PULSE_PER_SECOND := 6.0
const CRYSTAL_FALLBACK_RADIUS := 7.0
const CRYSTAL_DEFAULT_COLOR := Color(0.25, 0.70, 0.98)
const CRYSTAL_FALLBACK_COLORS := {
	"blue": Color(0.25, 0.70, 0.98), "green": Color(0.32, 0.88, 0.52), "red": Color(0.98, 0.32, 0.26),
	"violet": Color(0.74, 0.45, 0.96), "yellow": Color(0.98, 0.83, 0.28),
}
const CHIBI_CAPE_COLOR := Color(34 / 255.0, 110 / 255.0, 55 / 255.0)
const CHIBI_BODY_COLOR := Color(85 / 255.0, 115 / 255.0, 145 / 255.0)
const CHIBI_BODY_BORDER_COLOR := Color(40 / 255.0, 60 / 255.0, 80 / 255.0)
const CHIBI_LEG_COLOR := Color(50 / 255.0, 65 / 255.0, 80 / 255.0)
const CHIBI_HEAD_COLOR := Color(220 / 255.0, 195 / 255.0, 160 / 255.0)
const CHIBI_HAT_COLOR := Color(215 / 255.0, 180 / 255.0, 75 / 255.0)
const CHIBI_FEATHER_COLOR := Color(40 / 255.0, 160 / 255.0, 70 / 255.0)
const IDLE_FOLDER := "2Idle"
const RUN_FOLDER := "3run"
const MAP_ANIMALS_FOLDER := "map/animals"
const MAP_CRYSTALS_FOLDER := "map/crystals"
const NPC_FOLDER := "NPC"
const BANDIT_FILE := "mobs/woodland_bandit.png"
const WARRIOR_FOLDER := "warrior"
const WARRIOR_ANIMATIONS := ["idle", "run", "attack1", "attack2", "gothit", "death"]

static var _npc_cache: Dictionary = {}
static var _animal_cache: Dictionary = {}
static var _crystal_cache: Dictionary = {}
static var _warrior_cache: Dictionary = {}
static var _warrior_loaded := false
static var _warrior_base_height := 0
static var _bandit: Texture2D = null
static var _bandit_loaded := false

var _mob_states: Dictionary = {}
var _hero: Dictionary = {}
var _player_is_warrior := true
var _player_front_line := false
var _player_profession := ""
var _rng := RandomNumberGenerator.new()


func _init() -> void:
	_rng.randomize()


# Мобы, животные и герой по глубине (y ног) вместе с дополнительными элементами (передние деревья), как _draw_mobs в
# Python: сортировка по (глубина, порядок), актёры — порядок 1, дополнительные — 2, при равном ключе порядок добавления.
# extra_entries — [{"base_y": float, "draw": Callable(canvas)}]; необязательный "rect" (мировой Rect2) включает правило
# переднего плана Python: элемент рисуется, если base_y не меньше y актёра и прямоугольники пересекаются.
func draw_actors(canvas: CanvasItem, mobs: Array, animals: Array, player: Dictionary, direction: String,
		anim_time: float, moving: bool, selected_mob_id: String, now_msec: int, extra_entries: Array = []) -> void:
	for entry in _actor_plan(mobs, animals, player, direction, anim_time, moving, selected_mob_id, now_msec, extra_entries):
		entry["draw"].call(canvas)


func draw_player(canvas: CanvasItem, player: Dictionary, direction: String, anim_time: float, moving: bool) -> void:
	_draw_player_entry(canvas, _player_draw_state(player, direction, anim_time, moving), direction, anim_time, moving)


const AFK_TINT := Color8(135, 139, 145)
const OTHER_PLAYER_HEAD := Color8(218, 190, 153)
const OTHER_PLAYER_BODY := Color8(74, 126, 102)
const AFK_PLAYER_HEAD := Color8(145, 149, 153)
const AFK_PLAYER_BODY := Color8(100, 105, 112)


# Чужой игрок на карте, как draw_active_players и draw_afk_players в ui/afk_presence.py: спрайт класса в стойке
# по направлению; AFK тонируется (135, 139, 145), без спрайта рисуется серая фигурка.
func draw_other_player(canvas: CanvasItem, occupant: Dictionary, direction: String, afk: bool) -> void:
	var feet := Vector2(float(occupant.get("position_x", 0.0)), float(occupant.get("position_y", 0.0)))
	if not bool(occupant.get("front_line", false)):
		canvas.draw_colored_polygon(SHAPE_RULES.ellipse_points(Rect2(feet.x - 14.0, feet.y - 4.0, 28.0, 10.0)), PLAYER_SHADOW_COLOR)
	var warrior := str(occupant.get("type", "")) == RULES.WARRIOR_PROFESSION
	if bool(occupant.get("front_line", false)):
		var profession := str(occupant.get("type", ""))
		var texture: Texture2D = FRONT_LINE_SPRITES.frame_texture(profession, "idle", direction, 0)
		if texture != null:
			canvas.draw_texture_rect(
				texture,
				DECK_SPRITE.player_frame_rect(feet, Vector2i(texture.get_size())),
				false,
				AFK_TINT if afk else Color.WHITE,
			)
			return
	var frames: Array = DECK_SPRITE.frames_for_direction(_state_frames(warrior, "idle"), direction)
	if frames.is_empty():
		canvas.draw_circle(feet + Vector2(0.0, -28.0), 7.0, AFK_PLAYER_HEAD if afk else OTHER_PLAYER_HEAD)
		canvas.draw_rect(Rect2(feet.x - 6.0, feet.y - 21.0, 12.0, 17.0), AFK_PLAYER_BODY if afk else OTHER_PLAYER_BODY)
		return
	var texture: Texture2D = frames[0]
	canvas.draw_texture_rect(texture, DECK_SPRITE.player_frame_rect(feet, Vector2i(texture.get_size())), false, AFK_TINT if afk else Color.WHITE)


# Портрет героя для панели: первый кадр стойки по направлению, как player_frame(moving=False) в _draw_player_panel
# (Python). Профессия — из последнего словаря игрока, переданного в draw_*/player_overhead; до первого вызова — воин.
# Кадры берутся из статического кэша. Для не-воинов Python анимирует стойку по времени, здесь кадр 0.
func player_portrait_texture(direction: String = "s") -> Texture2D:
	if _player_front_line:
		return FRONT_LINE_SPRITES.frame_texture(_player_profession, "idle", direction, 0)
	var frames: Array = DECK_SPRITE.frames_for_direction(_state_frames(_player_is_warrior, "idle"), direction)
	if frames.is_empty():
		return null
	return frames[0]


func draw_mobs(canvas: CanvasItem, mobs: Array, selected_id: String, now_msec: int) -> void:
	_sync_mobs(mobs, now_msec)
	for mob in mobs:
		if mob is Dictionary:
			var sprite := _mob_sprite(mob, now_msec)
			if not sprite.is_empty():
				_draw_mob_entry(canvas, mob, sprite, selected_id)


func draw_animals(canvas: CanvasItem, animals: Array, now_msec: int) -> void:
	for animal in animals:
		if animal is Dictionary:
			var sprite := _animal_sprite(animal, now_msec)
			if not sprite.is_empty():
				_draw_animal_entry(canvas, sprite)


func draw_corpses(canvas: CanvasItem, corpses: Array, selected_id: int, visible_world: Rect2) -> void:
	for corpse in corpses:
		if not corpse is Dictionary:
			continue
		var rect := RULES.corpse_marker_rect(_point(corpse))
		if not visible_world.intersects(rect):
			continue
		var color := SELECT_COLOR if int(corpse.get("id", -1)) == selected_id else CORPSE_COLOR
		var outline := SHAPE_RULES.ellipse_points(rect)
		canvas.draw_colored_polygon(outline, CORPSE_FILL_COLOR)
		canvas.draw_polyline(_closed(outline), color, 2.0)
		var center := rect.get_center()
		canvas.draw_line(Vector2(center.x, rect.position.y + 4.0), Vector2(center.x, rect.end.y - 4.0), color, 2.0)
		canvas.draw_line(Vector2(rect.position.x + 6.0, center.y - 2.0), Vector2(rect.end.x - 6.0, center.y - 2.0), color, 2.0)


# Кристаллы: crystals — [x, y, color, stage] из снимка рельефа. Спрайт по цвету и стадии из assets/map/crystals;
# кольцо у клетки добычи (harvest_target) пульсирует, как подсветка активного объекта в Python.
# Не входит в draw_actors: в Python-клиенте Tower тела кристаллов нет, решает вызывающий.
func draw_crystals(canvas: CanvasItem, crystals: Array, harvest_target: Variant, now_msec: int) -> void:
	var target: Variant = RULES.tile_of(harvest_target)
	for crystal in crystals:
		if not crystal is Array or crystal.size() < 4:
			continue
		var tile := Vector2i(int(crystal[0]), int(crystal[1]))
		var color_name := str(crystal[2])
		var center := RULES.tile_center(tile)
		var texture := _crystal_texture(color_name, int(crystal[3]))
		if texture != null:
			var bottom := Vector2(center.x, (tile.y + 1) * RULES.TILE_SIZE)
			canvas.draw_texture_rect(texture, RULES.midbottom_rect(bottom, texture.get_size()), false)
		else:
			_draw_crystal_fallback(canvas, center, color_name)
		if target != null and tile == target:
			var pulse := 1.0 + CRYSTAL_PULSE * sin(float(now_msec) / 1000.0 * CRYSTAL_PULSE_PER_SECOND)
			canvas.draw_arc(center, CRYSTAL_RING_RADIUS * pulse, 0.0, TAU, 24, SELECT_COLOR, 2.0)


# Полоска добычи над клеткой (экранные координаты: tile_center_screen — центр тайла на экране, zoom — масштаб мира).
func draw_harvest_progress(canvas: CanvasItem, harvest: Variant, tile_center_screen: Vector2, zoom: float) -> void:
	if not RULES.harvest_visible(harvest):
		return
	var bar := RULES.harvest_bar_rect(tile_center_screen, zoom)
	canvas.draw_rect(bar, HARVEST_BACK_COLOR)
	var fill_width := float(int(bar.size.x * RULES.harvest_fill(harvest)))
	canvas.draw_rect(Rect2(bar.position, Vector2(fill_width, bar.size.y)), HARVEST_FILL_COLOR)
	canvas.draw_rect(bar, Color.BLACK, false, 1.0)


# Расходящееся кольцо клика (экранные координаты); timer_left — секунды до конца, как в Python (0.35 → 0).
func draw_click_effect(canvas: CanvasItem, center_screen: Vector2, timer_left: float) -> void:
	var style := RULES.click_effect_style(timer_left)
	var alpha := int(style["alpha"])
	if alpha <= 0:
		return
	var color := Color(CLICK_RGB.r, CLICK_RGB.g, CLICK_RGB.b, alpha / 255.0)
	canvas.draw_arc(center_screen, float(style["radius"]) - 1.0, 0.0, TAU, 32, color, 2.0)


# Подписи ХП над живыми мобами: anchor — верх спрайта (мировые координаты). Полоска bar_size (100x5) стоит
# над anchor с зазором gap, подпись — над полоской; outline — прямоугольник выделения. Рисует вызывающий.
func mob_overheads(mobs: Array, selected_id: String, now_msec: int) -> Array:
	_sync_mobs(mobs, now_msec)
	var result: Array = []
	for mob in mobs:
		if not mob is Dictionary or float(mob.get("hp", 0.0)) <= 0.0:
			continue
		var sprite := _mob_sprite(mob, now_msec)
		if sprite.is_empty():
			continue
		var rect: Rect2 = sprite.get("bounds", sprite["rect"])
		var hp := float(mob.get("hp", 0.0))
		var max_hp := float(mob.get("max_hp", 1.0))
		var mob_id := str(mob.get("id", ""))
		result.append({
			"id": mob_id,
			"anchor": Vector2(rect.position.x + floorf(rect.size.x / 2.0), rect.position.y),
			"outline": rect.grow(4.0),
			"bar_size": Vector2(maxf(RULES.TILE_SIZE, rect.size.x), MOB_BAR_SIZE.y),
			"gap": MOB_BAR_GAP,
			"hp_ratio": RULES.hp_ratio(hp, max_hp),
			"hp_text": "ХП %d/%d" % [int(hp), int(max_hp)],
			"selected": mob_id == selected_id,
		})
	return result


# Подписи героя: mp_bar_bottom — нижний край полоски МП (как name_y в _draw_player_character). Стек снизу вверх
# по Python: полоска МП, её подпись, полоска ХП, её подпись, ник. Полоски OVERHEAD_BAR_SIZE, зазор OVERHEAD_GAP;
# подписи и полоски рисует вызывающий, их высота зависит от шрифта.
func player_overhead(player: Dictionary, direction: String, anim_time: float, moving: bool) -> Dictionary:
	_update_hero(player, anim_time)
	var feet := _point(player)
	var picture := _player_picture(player, direction, anim_time, moving)
	var texture: Texture2D = picture["texture"]
	var mp_bar_bottom := feet.y + float(_chibi_bob(anim_time, moving)) - 23.0
	if texture != null and bool(picture["warrior"]):
		mp_bar_bottom = feet.y - float(_warrior_base_height) - 4.0
	elif texture != null:
		mp_bar_bottom = feet.y - texture.get_height() - 4.0
	var hp := float(player.get("hp", 0.0))
	var max_hp := float(player.get("max_hp", 1.0))
	var mp := float(player.get("mp", 0.0))
	var max_mp := float(player.get("max_mp", 1.0))
	return {
		"feet": feet,
		"name": str(player.get("name", PLAYER_NAME_FALLBACK)),
		"profession": str(player.get("type", "")),
		"mp_bar_bottom": mp_bar_bottom,
		"bar_size": OVERHEAD_BAR_SIZE,
		"gap": OVERHEAD_GAP,
		"hp_ratio": RULES.hp_ratio(hp, max_hp),
		"hp_text": "ХП %d/%d" % [int(hp), int(max_hp)],
		"mp_ratio": RULES.hp_ratio(mp, max_mp),
		"mp_text": "МП %d/%d" % [int(mp), int(max_mp)],
	}


# Подписи «Труп» над трупами в области видимости: anchor — верх маркера, подпись рисуется над ним.
func corpse_overheads(corpses: Array, selected_id: int, visible_world: Rect2) -> Array:
	var result: Array = []
	for corpse in corpses:
		if not corpse is Dictionary:
			continue
		var rect := RULES.corpse_marker_rect(_point(corpse))
		if not visible_world.intersects(rect):
			continue
		var corpse_id := int(corpse.get("id", -1))
		result.append({
			"id": corpse_id,
			"text": "Труп",
			"anchor": Vector2(rect.position.x + floorf(rect.size.x / 2.0), rect.position.y),
			"gap": OVERHEAD_GAP,
			"selected": corpse_id == selected_id,
		})
	return result


static func _depth_before(a: Dictionary, b: Dictionary) -> bool:
	if a["depth"] != b["depth"]:
		return a["depth"] < b["depth"]
	if a["order"] != b["order"]:
		return a["order"] < b["order"]
	return a["index"] < b["index"]


# План отрисовки {depth, order, index, draw}. Актёры без спрайта пропускаются, герой есть всегда, как в Python.
func _actor_plan(mobs: Array, animals: Array, player: Dictionary, direction: String, anim_time: float, moving: bool,
		selected_mob_id: String, now_msec: int, extra_entries: Array) -> Array:
	_sync_mobs(mobs, now_msec)
	var entries: Array = []
	var actors: Array = []
	for mob in mobs:
		if not mob is Dictionary:
			continue
		var sprite := _mob_sprite(mob, now_msec)
		if not sprite.is_empty():
			_add_actor(entries, actors, float(mob.get("y", 0.0)), sprite.get("bounds", sprite["rect"]),
				Callable(self, "_draw_mob_entry").bind(mob, sprite, selected_mob_id))
	for animal in animals:
		if not animal is Dictionary:
			continue
		var sprite := _animal_sprite(animal, now_msec)
		if not sprite.is_empty():
			_add_actor(entries, actors, float(animal.get("y", 0.0)), sprite["rect"],
				Callable(self, "_draw_animal_entry").bind(sprite))
	var state := _player_draw_state(player, direction, anim_time, moving)
	if bool(player.get("visible", true)):
		var feet: Vector2 = state["feet"]
		_add_actor(entries, actors, feet.y, state["rect"],
			Callable(self, "_draw_player_entry").bind(state, direction, anim_time, moving))
	for extra in extra_entries:
		if not extra is Dictionary or not extra.get("draw") is Callable:
			continue
		var base_y := float(extra.get("base_y", 0.0))
		if extra.has("rect") and not _is_foreground(base_y, extra["rect"], actors):
			continue
		entries.append({"depth": base_y, "order": 2, "index": entries.size(), "draw": extra["draw"]})
	entries.sort_custom(_depth_before)
	return entries


func _add_actor(entries: Array, actors: Array, depth: float, rect: Rect2, draw: Callable) -> void:
	entries.append({"depth": depth, "order": 1, "index": entries.size(), "draw": draw})
	actors.append({"depth": depth, "rect": rect})


# Правило переднего плана из _draw_mobs: дерево впереди, если его base_y не меньше y актёра и прямоугольники пересекаются.
static func _is_foreground(base_y: float, rect: Rect2, actors: Array) -> bool:
	for actor in actors:
		if base_y >= actor["depth"] and rect.intersects(actor["rect"]):
			return true
	return false


func _sync_mobs(mobs: Array, now_msec: int) -> void:
	for mob in mobs:
		if mob is Dictionary:
			var mob_id := str(mob.get("id", ""))
			_mob_states[mob_id] = RULES.advance_mob(_mob_states.get(mob_id, {}), mob, now_msec)


func _draw_mob_entry(canvas: CanvasItem, mob: Dictionary, sprite: Dictionary, selected_id: String) -> void:
	var rect: Rect2 = sprite["rect"]
	var tint := Color(1.0, 1.0, 1.0, float(sprite["alpha"]))
	var texture: Texture2D = sprite["texture"]
	var rotation := float(sprite["rotation"])
	if rotation == 0.0:
		canvas.draw_texture_rect(texture, rect, false, tint)
	else:
		_draw_rotated(canvas, texture, rect.get_center(), rect.size, rotation, tint)
	if str(mob.get("id", "")) == selected_id and float(mob.get("hp", 0.0)) > 0.0:
		var outline: Rect2 = sprite.get("bounds", rect)
		canvas.draw_polyline(_closed(SHAPE_RULES.rounded_rect_points(outline.grow(4.0), 6.0)), SELECT_COLOR, 2.0)


# Спрайт моба: {texture, rect, rotation (рад., по часовой на экране), alpha} или {} — рисовать нечего.
func _mob_sprite(mob: Dictionary, now_msec: int) -> Dictionary:
	var state: Dictionary = _mob_states.get(str(mob.get("id", "")), {})
	var sheets := _npc_sheets(str(mob.get("kind", "")), bool(mob.get("front_line", false)))
	var center := RULES.mob_display_position(state, now_msec, _point(mob))
	if state.has("swing_started"):
		var mob_elapsed := float(now_msec) - float(state["swing_started"])
		center += RULES.lunge_offset(mob_elapsed, float(state.get("swing_windup_ms", 0.0)), float(mob.get("facing", 0.0)), RULES.MOB_LUNGE_PX)
	var facing := float(mob.get("facing", 0.0))
	var size_multiplier := 4.0 if bool(mob.get("is_boss", false)) else 1.0
	if float(mob.get("hp", 0.0)) <= 0.0:
		return _death_sprite(state, sheets, center, facing, now_msec, size_multiplier)
	var walk: Variant = sheets["walk"]
	if walk == null:
		if str(mob.get("kind", "")).begins_with("mob|"):
			return {}
		var bandit := _bandit_texture()
		if bandit == null:
			return {}
		return _sprite(bandit, RULES.center_rect(center, bandit.get_size() * size_multiplier), 0.0, 1.0)
	var row := RULES.npc_facing_row(facing)
	var attack: Variant = sheets["attack"]
	var hurt: Variant = sheets.get("hurt")
	var texture: Texture2D = null
	if hurt != null:
		var hurt_frames: Array = hurt[row]
		var hurt_index := RULES.mob_hurt_frame(state, now_msec, hurt_frames.size())
		if hurt_index >= 0:
			texture = hurt_frames[hurt_index]
	if texture == null and attack != null:
		var attack_frames: Array = attack[row]
		var index := RULES.mob_attack_frame(
			state, float(mob.get("windup", 0.0)), now_msec, attack_frames.size(),
			int(sheets.get("attack_windup_frames", RULES.NPC_FRAMES_PER_ROW)),
		)
		if index >= 0:
			texture = attack_frames[index]
	if texture == null:
		var walking := RULES.mob_walking(now_msec, float(state.get("moved_at", -RULES.MOB_WALK_HOLD_MS)))
		var walk_frames: Array = walk[row]
		texture = walk_frames[RULES.walk_frame_index(now_msec, walking, walk_frames.size())]
	var sprite := _sprite(texture, RULES.center_rect(center, texture.get_size() * size_multiplier), 0.0, 1.0)
	var bounds: Variant = sheets.get("bounds")
	if bounds != null:
		var visible_rect: Rect2 = bounds[row]
		sprite["bounds"] = Rect2(center + visible_rect.position * size_multiplier, visible_rect.size * size_multiplier)
	return sprite


func _death_sprite(
	state: Dictionary,
	sheets: Dictionary,
	center: Vector2,
	facing: float,
	now_msec: int,
	size_multiplier := 1.0,
) -> Dictionary:
	var died_at: Variant = state.get("died_at", null)
	var deaths: Variant = sheets["death"]
	var walk: Variant = sheets["walk"]
	var has_deaths: bool = deaths != null and not deaths.is_empty()
	if died_at == null or not (has_deaths or walk != null):
		return {}
	var elapsed := float(now_msec) - float(died_at)
	if not RULES.corpse_visible(elapsed):
		return {}
	var alpha := float(RULES.corpse_alpha_byte(elapsed)) / 255.0
	if has_deaths:
		var frame: Texture2D = deaths[RULES.death_frame_index(elapsed, deaths.size())]
		return _sprite(frame, RULES.center_rect(center, frame.get_size() * size_multiplier), 0.0, alpha)
	var base: Texture2D = walk[RULES.npc_facing_row(facing)][0]
	var fall := -deg_to_rad(RULES.corpse_fall_degrees(elapsed))
	return _sprite(base, RULES.center_rect(center, base.get_size() * size_multiplier), fall, alpha)


func _sprite(texture: Texture2D, rect: Rect2, rotation: float, alpha: float) -> Dictionary:
	return {"texture": texture, "rect": rect, "rotation": rotation, "alpha": alpha}


# Кадр животного: {texture, rect (по низу спрайта), source} или {} — без кадров животное не рисуется.
func _animal_sprite(animal: Dictionary, now_msec: int) -> Dictionary:
	var sheet := _animal_sheet(str(animal.get("key", "")))
	if sheet.is_empty():
		return {}
	var moving := bool(animal.get("moving", false))
	var rows: Array = sheet["rects"]["moving" if moving else "idle"]
	var row_rects: Array = rows[RULES.animal_facing_index(float(animal.get("facing", 0.0)))]
	if row_rects.is_empty():
		return {}
	var index := RULES.animal_frame_index(now_msec, row_rects.size()) if moving else 0
	var source: Rect2i = row_rects[index]
	var size := Vector2(source.size)
	return {
		"texture": sheet["texture"],
		"rect": RULES.midbottom_rect(_point(animal), size),
		"source": Rect2(Vector2(source.position), size),
	}


func _draw_animal_entry(canvas: CanvasItem, sprite: Dictionary) -> void:
	canvas.draw_texture_rect_region(sprite["texture"], sprite["rect"], sprite["source"])


# Состояние героя для отрисовки и сортировки: ноги, текстура (null — фигурка) и прямоугольник. Как в Python: кадр по
# низу от ног, без кадра — прямоугольник 26x38 от точки (sx - 13, sy - 25). Обновляет состояние героя.
func _player_draw_state(player: Dictionary, direction: String, anim_time: float, moving: bool) -> Dictionary:
	_update_hero(player, anim_time)
	var feet := _point(player)
	var texture: Texture2D = _player_picture(player, direction, anim_time, moving)["texture"]
	var rect := Rect2(feet.x - 13.0, feet.y - 25.0, 26.0, 38.0)
	if texture != null:
		rect = DECK_SPRITE.player_frame_rect(feet, Vector2i(texture.get_size()))
	if bool(player.get("front_line", false)) and str(player.get("projectile", "")).is_empty() and _hero.has("swing_started"):
		var elapsed := (anim_time - float(_hero["swing_started"])) * 1000.0
		rect.position += RULES.lunge_offset(elapsed, float(_hero.get("swing_windup_ms", 0.0)), float(player.get("facing", 0.0)), RULES.HERO_LUNGE_PX)
	return {"feet": feet, "texture": texture, "rect": rect, "front_line": bool(player.get("front_line", false))}


func _draw_player_entry(canvas: CanvasItem, state: Dictionary, direction: String, anim_time: float, moving: bool) -> void:
	var feet: Vector2 = state["feet"]
	if not bool(state.get("front_line", false)):
		canvas.draw_colored_polygon(SHAPE_RULES.ellipse_points(Rect2(feet.x - 14.0, feet.y - 4.0, 28.0, 10.0)), PLAYER_SHADOW_COLOR)
	var texture: Texture2D = state["texture"]
	if texture == null:
		_draw_chibi(canvas, feet, direction, anim_time, moving)
		return
	canvas.draw_texture_rect(texture, state["rect"], false)


func _update_hero(player: Dictionary, anim_time: float) -> void:
	_hero = RULES.advance_hero(_hero, player, anim_time, _rng.randi() % 2)
	_player_is_warrior = str(player.get("type", "")) == RULES.WARRIOR_PROFESSION
	_player_front_line = bool(player.get("front_line", false))
	_player_profession = str(player.get("type", ""))


# Кадр героя: {texture (null — рисуется фигурка), warrior}. Воин — свой набор с замахом, ударом и смертью.
func _player_picture(player: Dictionary, direction: String, anim_time: float, moving: bool) -> Dictionary:
	var warrior := str(player.get("type", "")) == RULES.WARRIOR_PROFESSION
	var front_line := bool(player.get("front_line", false))
	if front_line:
		var profession := str(player.get("type", ""))
		var attack_count := FRONT_LINE_SPRITES.frame_count(profession, "attack")
		var attack_frame := RULES.hero_attack_frame(_hero, anim_time, attack_count)
		if moving and RULES.swing_in_backswing(_hero, anim_time):
			attack_frame = -1
		if attack_frame >= 0:
			var attack_direction := RULES.facing_direction(Vector2.from_angle(float(player.get("facing", 0.0))))
			var attack_texture: Texture2D = FRONT_LINE_SPRITES.frame_texture(
				profession, "attack", attack_direction, attack_frame,
			)
			if attack_texture != null:
				return {"texture": attack_texture, "warrior": false}
		var state := "run" if moving else "idle"
		var frame_count := FRONT_LINE_SPRITES.row_frame_count(profession, state, direction)
		if frame_count > 0:
			var fps := 10.0 if moving else 4.0
			var frame_index := int(anim_time * fps) % frame_count
			var hero_texture: Texture2D = FRONT_LINE_SPRITES.frame_texture(
				profession,
				state,
				direction,
				frame_index,
			)
			if hero_texture != null:
				return {"texture": hero_texture, "warrior": false}
	var hit: Variant = RULES.hero_hit_progress(_hero, anim_time)
	var death: Variant = RULES.hero_death_progress(_hero, anim_time)
	var windup := float(_hero.get("windup", 0.0))
	var state := RULES.player_state(warrior, moving, windup > 0.0, hit != null, death != null)
	var progress := RULES.attack_progress(windup, float(_hero.get("windup_total", 0.0)))
	if state == "gothit":
		progress = float(hit)
	elif state == "death":
		progress = float(death)
	var texture: Texture2D = null
	var frames: Array = DECK_SPRITE.frames_for_direction(_state_frames(warrior, state), direction)
	if not frames.is_empty():
		texture = frames[RULES.player_frame_index(state, anim_time, frames.size(), progress)]
	return {"texture": texture, "warrior": warrior}


func _state_frames(warrior: bool, state: String) -> Dictionary:
	if warrior:
		var animation := state
		if state == "attack":
			animation = RULES.WARRIOR_ATTACKS[int(_hero.get("variant", 0)) % RULES.WARRIOR_ATTACKS.size()]
		return _warrior_set().get(animation, {})
	if state == "run":
		var run := _player_directional(RUN_FOLDER)
		if not run.is_empty():
			return run
	return _player_directional(IDLE_FOLDER)


# Фигурка без спрайтов, как процедурный чиби-воин в Python (_draw_player_character, фолбэк).
func _draw_chibi(canvas: CanvasItem, feet: Vector2, direction: String, anim_time: float, moving: bool) -> void:
	var bob := _chibi_bob(anim_time, moving)
	var leg := int(sin(anim_time * 14.0) * 2.0) if moving else 0
	var cy := feet.y + float(bob)
	var sx := feet.x
	var facing := -1.0 if direction.contains("w") else 1.0
	canvas.draw_colored_polygon(PackedVector2Array([
		Vector2(sx - 5.0 * facing, cy - 4.0), Vector2(sx - 12.0 * facing, cy + 8.0), Vector2(sx - 4.0 * facing, cy + 9.0),
	]), CHIBI_CAPE_COLOR)
	canvas.draw_rect(Rect2(sx - 6.0, cy - 6.0, 12.0, 13.0), CHIBI_BODY_COLOR)
	canvas.draw_rect(Rect2(sx - 6.0, cy - 6.0, 12.0, 13.0), CHIBI_BODY_BORDER_COLOR, false, 1.0)
	canvas.draw_rect(Rect2(sx - 5.0, cy + 7.0 - float(leg), 4.0, 5.0), CHIBI_LEG_COLOR)
	canvas.draw_rect(Rect2(sx + 1.0, cy + 7.0 + float(leg), 4.0, 5.0), CHIBI_LEG_COLOR)
	canvas.draw_circle(Vector2(sx, cy - 11.0), 6.0, CHIBI_HEAD_COLOR)
	canvas.draw_rect(Rect2(sx - 6.0, cy - 17.0, 12.0, 7.0), CHIBI_HAT_COLOR)
	canvas.draw_line(Vector2(sx - 2.0 * facing, cy - 17.0), Vector2(sx - 6.0 * facing, cy - 22.0), CHIBI_FEATHER_COLOR, 2.0)


func _chibi_bob(anim_time: float, moving: bool) -> int:
	return int(sin(anim_time * 14.0) * 2.5) if moving else int(sin(anim_time * 4.0))


func _draw_crystal_fallback(canvas: CanvasItem, center: Vector2, color_name: String) -> void:
	var color: Color = CRYSTAL_FALLBACK_COLORS.get(color_name, CRYSTAL_DEFAULT_COLOR)
	var r := CRYSTAL_FALLBACK_RADIUS
	canvas.draw_colored_polygon(PackedVector2Array([
		center + Vector2(0.0, -r), center + Vector2(r * 0.7, 0.0), center + Vector2(0.0, r), center + Vector2(-r * 0.7, 0.0),
	]), color)


# Поворот вокруг центра без смены transform канвы: четырёхугольник с текстурой.
static func _draw_rotated(canvas: CanvasItem, texture: Texture2D, center: Vector2, size: Vector2, rotation: float, tint: Color) -> void:
	var half := size / 2.0
	var points := PackedVector2Array()
	for corner in [Vector2(-half.x, -half.y), Vector2(half.x, -half.y), Vector2(half.x, half.y), Vector2(-half.x, half.y)]:
		points.append(center + corner.rotated(rotation))
	var colors := PackedColorArray([tint, tint, tint, tint])
	var uvs := PackedVector2Array([Vector2(0.0, 0.0), Vector2(1.0, 0.0), Vector2(1.0, 1.0), Vector2(0.0, 1.0)])
	canvas.draw_primitive(points, colors, uvs, texture)


static func _closed(points: PackedVector2Array) -> PackedVector2Array:
	var result := points.duplicate()
	result.append(points[0])
	return result


static func _point(data: Dictionary) -> Vector2:
	return Vector2(float(data.get("x", 0.0)), float(data.get("y", 0.0)))


static func _assets_root() -> String:
	return DECK_SPRITE.assets_root(ProjectSettings.globalize_path("res://"))


static func _load_rgba(path: String) -> Image:
	var image: Image
	if path.begins_with("res://"):
		if not ResourceLoader.exists(path):
			return null
		var texture := load(path) as Texture2D
		if texture == null:
			return null
		image = texture.get_image()
	else:
		if not FileAccess.file_exists(path):
			return null
		image = Image.load_from_file(path)
	if image == null or image.is_empty():
		return null
	image.convert(Image.FORMAT_RGBA8)
	return image


static func _player_directional(folder: String) -> Dictionary:
	return DECK_SPRITE.directional_frames(_assets_root().path_join(folder), RULES.PLAYER_SPRITE_HEIGHT)


static func _npc_sheets(kind: String, native_size: bool = false) -> Dictionary:
	var cache_key := kind + ("|native" if native_size else "")
	if not _npc_cache.has(cache_key):
		var sheets := {"walk": null, "attack": null, "hurt": null, "death": null, "bounds": null}
		sheets["attack_windup_frames"] = RULES.NPC_FRAMES_PER_ROW
		var names := RULES.npc_sheet_names(kind)
		if not names.is_empty():
			var folder := _assets_root().path_join(NPC_FOLDER).path_join(names["folder"])
			sheets["walk"] = _npc_rows(folder.path_join(names["walk"]), native_size)
			sheets["attack"] = _npc_rows(folder.path_join(names["attack"]), native_size)
			sheets["death"] = _npc_death(folder.path_join(names["death"]), native_size)
		elif kind.begins_with("mob|"):
			var paths := _palette_mob_sheet_paths(kind)
			sheets["walk"] = _palette_mob_rows(
				paths, ["walk", "run", "animation", "idle", "death"], native_size,
			)
			sheets["attack"] = _palette_mob_rows(
				paths,
				["attack", "walk_attack", "run_attack", "animation", "walk", "run", "death"],
				native_size,
			)
			if sheets["attack"] != null:
				sheets["attack_windup_frames"] = RULES.attack_windup_frames(sheets["attack"][0].size())
			sheets["hurt"] = _palette_mob_rows(paths, ["hurt"], native_size)
			sheets["death"] = _palette_mob_death(paths, native_size)
			if sheets["walk"] == null:
				push_warning("Не удалось загрузить спрайт моба из палитры: " + kind)
			elif native_size:
				sheets["bounds"] = _visible_bounds(sheets["walk"])
		_npc_cache[cache_key] = sheets
	return _npc_cache[cache_key]


# Видимая часть кадров ходьбы по строкам: смещение от центра кадра и размер. У паков палитры кадр
# намного больше самого моба, поэтому рамка выбора и полоска ХП строятся по видимым пикселям.
static func _visible_bounds(rows: Dictionary) -> Dictionary:
	var result := {}
	for row in rows:
		var used := Rect2i()
		var frame_size := Vector2.ZERO
		for texture in rows[row]:
			var image: Image = texture.get_image()
			frame_size = Vector2(image.get_size())
			var frame_used := image.get_used_rect()
			if frame_used.has_area():
				used = frame_used if not used.has_area() else used.merge(frame_used)
		if used.has_area():
			result[row] = Rect2(Vector2(used.position) - frame_size / 2.0, Vector2(used.size))
		else:
			result[row] = Rect2(-frame_size / 2.0, frame_size)
	return result


static func _palette_mob_sheet_paths(kind: String) -> Dictionary:
	var key_parts := kind.split("|", false)
	if key_parts.size() != 3 or key_parts[0] != "mob" \
		or key_parts[1].contains("/") or key_parts[1].contains("\\") \
		or key_parts[1].contains(".."):
		return {}
	var pack_folder := key_parts[1]
	var species_key := key_parts[2]
	var pack_path := "res://assets/base_tails/LPC".path_join(pack_folder)
	var png_paths: Array[String] = []
	_collect_palette_mob_pngs(pack_path, png_paths)
	var paths := {}
	var action_pattern := RegEx.new()
	action_pattern.compile(
		"(?i)(walk_attack|run_attack|idle|walk|run|attack|hurt|death|jump|flight|fly|move|swim)\\d*$",
	)
	var direction_pattern := RegEx.new()
	direction_pattern.compile("(?i)_?(front|back|left|right)$")
	var goblin_variant_pattern := RegEx.new()
	goblin_variant_pattern.compile("(?i)^goblin([1-3])$")
	var goblin_action_pattern := RegEx.new()
	goblin_action_pattern.compile(
		"(?i)^(idle|walk|run|attack|hurt|death|walk_attack|run_attack)\\d?$",
	)
	for sheet_path in png_paths:
		var file_name := sheet_path.get_file()
		if file_name.begins_with("._") or not file_name.to_lower().ends_with("_with_shadow.png"):
			continue
		var state_name := "animation"
		var sheet_species := ""
		if pack_folder == "goblin sprite-pack":
			var variant_folder := sheet_path.get_base_dir().get_base_dir().get_file().to_lower()
			var variant_match := goblin_variant_pattern.search(variant_folder)
			var goblin_action := file_name.get_basename().to_lower()
			goblin_action = goblin_action.left(goblin_action.length() - "_with_shadow".length())
			var action_match := goblin_action_pattern.search(goblin_action)
			if variant_match == null or action_match == null:
				continue
			sheet_species = "g" + variant_match.get_string(1)
			state_name = action_match.get_string(1).to_lower()
		else:
			var stem := file_name.get_basename()
			stem = stem.left(stem.length() - "_with_shadow".length()).strip_edges()
			if stem.to_lower().ends_with("_animation"):
				stem = stem.left(stem.length() - "_animation".length())
			stem = direction_pattern.sub(stem, "", true).strip_edges()
			var action_match := action_pattern.search(stem)
			if action_match != null:
				state_name = action_match.get_string(1).to_lower()
				stem = stem.left(action_match.get_start()).trim_suffix("_").trim_suffix("-").strip_edges()
			sheet_species = stem.to_lower()
		if sheet_species != species_key:
			continue
		var previous_path: String = paths.get(state_name, "")
		if previous_path.is_empty() or _palette_mob_path_priority(sheet_path) > _palette_mob_path_priority(previous_path):
			paths[state_name] = sheet_path
	return paths


static func _collect_palette_mob_pngs(path: String, output: Array[String]) -> void:
	var directory := DirAccess.open(path)
	if directory == null:
		return
	var files := directory.get_files()
	files.sort()
	for file_name in files:
		if file_name.begins_with("._") or file_name.get_extension().to_lower() != "png":
			continue
		output.append(path.path_join(file_name))
	var child_directories := directory.get_directories()
	child_directories.sort()
	for child_name in child_directories:
		if child_name.begins_with(".") or child_name == "__MACOSX":
			continue
		_collect_palette_mob_pngs(path.path_join(child_name), output)


static func _palette_mob_path_priority(path: String) -> int:
	var normalized := path.replace("\\", "/").to_lower()
	return 1 if "/tiled/" in normalized or "/tiled_files/" in normalized else 0


static func _palette_mob_rows(paths: Dictionary, state_order: Array, native_size: bool = false) -> Variant:
	var sheet_path := ""
	for state_name in state_order:
		sheet_path = str(paths.get(state_name, ""))
		if not sheet_path.is_empty():
			break
	if sheet_path.is_empty():
		return null
	var sheet := _load_rgba(sheet_path)
	if sheet == null or sheet.get_height() % 4 != 0:
		return null
	var frame_size := int(sheet.get_height() / 4)
	if frame_size <= 0 or sheet.get_width() < frame_size:
		return null
	var frame_count := int(sheet.get_width() / frame_size)
	var rows := {}
	for row in range(4):
		var textures: Array = []
		# Паки палитры хранят строки вниз, вверх, влево, вправо; у NPC строка 2 — вправо, 3 — влево.
		var source_row: int = [0, 1, 3, 2][row]
		for column in range(frame_count):
			var cell := sheet.get_region(
				Rect2i(column * frame_size, source_row * frame_size, frame_size, frame_size),
			)
			textures.append(ImageTexture.create_from_image(cell if native_size else RULES.normalize_npc_frame(cell)))
		rows[row] = textures
	return rows


static func _palette_mob_death(paths: Dictionary, native_size: bool = false) -> Variant:
	var sheet_path := str(paths.get("death", ""))
	if sheet_path.is_empty():
		return null
	var sheet := _load_rgba(sheet_path)
	if sheet == null or sheet.get_height() % 4 != 0:
		return null
	var frame_size := int(sheet.get_height() / 4)
	var frame_count := mini(int(sheet.get_width() / frame_size), 7)
	var frames: Array = []
	for column in range(frame_count):
		var cell := sheet.get_region(Rect2i(column * frame_size, 0, frame_size, frame_size))
		if not native_size:
			cell.resize(RULES.MOB_DEATH_SIZE, RULES.MOB_DEATH_SIZE, Image.INTERPOLATE_NEAREST)
		frames.append(ImageTexture.create_from_image(cell))
	return frames if not frames.is_empty() else null


# Листы ходьбы и атаки: четыре направления, по четыре кадра в каждом.
static func _npc_rows(path: String, native_size: bool = false) -> Variant:
	var sheet := _load_rgba(path)
	if sheet == null:
		return null
	var size := RULES.NPC_FRAME_SIZE
	var rows := {}
	for row in range(4):
		var textures: Array = []
		for column in range(RULES.NPC_FRAMES_PER_ROW):
			var cell := sheet.get_region(Rect2i(column * size, row * size, size, size))
			textures.append(ImageTexture.create_from_image(cell if native_size else RULES.normalize_npc_frame(cell)))
		rows[row] = textures
	return rows


static func _npc_death(path: String, native_size: bool = false) -> Variant:
	var sheet := _load_rgba(path)
	if sheet == null:
		return null
	var size := RULES.NPC_FRAME_SIZE
	var frames: Array = []
	for column in range(sheet.get_width() / size):
		var cell := sheet.get_region(Rect2i(column * size, 0, size, size))
		if not native_size:
			cell.resize(RULES.MOB_DEATH_SIZE, RULES.MOB_DEATH_SIZE, Image.INTERPOLATE_NEAREST)
		frames.append(ImageTexture.create_from_image(cell))
	return frames


static func _animal_sheet(key: String) -> Dictionary:
	if not _animal_cache.has(key):
		var result := {}
		var layout := RULES.animal_layout(key)
		if not layout.is_empty():
			var image := _load_rgba(_assets_root().path_join(MAP_ANIMALS_FOLDER).path_join(str(layout["asset"]) + ".png"))
			if image != null:
				result = {
					"texture": ImageTexture.create_from_image(image),
					"rects": RULES.animal_frame_rects(layout, image.get_size()),
				}
		_animal_cache[key] = result
	return _animal_cache[key]


static func _crystal_texture(color_name: String, stage: int) -> Texture2D:
	var key := "%s_%d" % [color_name, stage]
	if not _crystal_cache.has(key):
		var image := _load_rgba(_assets_root().path_join(MAP_CRYSTALS_FOLDER).path_join(key + ".png"))
		_crystal_cache[key] = ImageTexture.create_from_image(image) if image != null else null
	return _crystal_cache[key]


static func _bandit_texture() -> Texture2D:
	if not _bandit_loaded:
		_bandit_loaded = true
		var image := _load_rgba(_assets_root().path_join(BANDIT_FILE))
		if image != null:
			_bandit = ImageTexture.create_from_image(image)
	return _bandit


static func _warrior_set() -> Dictionary:
	if not _warrior_loaded:
		_warrior_loaded = true
		var built := build_warrior_images(_assets_root().path_join(WARRIOR_FOLDER))
		if not built.is_empty():
			_warrior_base_height = int(built["base_height"])
			for animation in WARRIOR_ANIMATIONS:
				var textures := {}
				for direction in built["animations"][animation]:
					textures[direction] = _textures(built["animations"][animation][direction])
				_warrior_cache[animation] = textures
	return _warrior_cache


# Кадры воина как load_warrior_directional_frames: {base_height, animations: {состояние: {направление: [Image]}}}.
# Пустой словарь — нет кадров ходьбы.
static func build_warrior_images(root: String) -> Dictionary:
	var walk_heights: Array = []
	for direction in RULES.DIRECTIONS:
		for image in _load_frames(root.path_join("walk").path_join(direction)):
			walk_heights.append(RULES.opaque_rect(image, RULES.WARRIOR_BODY_MIN_ALPHA, Rect2i(Vector2i.ZERO, image.get_size())).size.y)
	if walk_heights.is_empty():
		return {}
	var scale := RULES.warrior_scale(walk_heights)
	var scaled := {}
	for folder in RULES.WARRIOR_SOURCE_FOLDERS:
		scaled[folder] = _scale_warrior_folder(root.path_join(folder), scale, RULES.WARRIOR_FIRST_FRAME_ANCHOR.has(folder))
	var base := RULES.warrior_extents(_warrior_entries(scaled, RULES.WARRIOR_BASE_FOLDERS))
	var wide := RULES.warrior_extents(_warrior_entries(scaled, RULES.WARRIOR_WIDE_FOLDERS))
	var below := mini(base.z, RULES.WARRIOR_FEET_MARGIN)
	var placed := {}
	for folder in scaled:
		var is_base: bool = RULES.WARRIOR_BASE_FOLDERS.has(folder)
		var half: int = base.x if is_base else wide.x
		var above: int = base.y if is_base else wide.y
		var per_direction := {}
		for direction in scaled[folder]:
			var entry: Dictionary = scaled[folder][direction]
			var canvases: Array = []
			for frame in entry["frames"]:
				var canvas := Image.create_empty(2 * half, above + below, false, Image.FORMAT_RGBA8)
				RULES.blit_clipped(canvas, frame, RULES.warrior_offset(entry["anchor"], half, above))
				canvases.append(canvas)
			per_direction[direction] = canvases
		placed[folder] = per_direction
	var animations := {}
	for animation in RULES.WARRIOR_ANIMATION_FOLDER:
		var folder: String = RULES.WARRIOR_ANIMATION_FOLDER[animation]
		var frames_by_direction: Dictionary = placed[folder].duplicate()
		for direction in RULES.DIRECTIONS:
			if frames_by_direction.has(direction):
				continue
			var source := RULES.warrior_source(direction, frames_by_direction.keys())
			if str(source["source"]).is_empty():
				continue
			var source_frames: Array = frames_by_direction[source["source"]]
			frames_by_direction[direction] = _mirrored(source_frames) if source["mirrored"] else source_frames
		animations[animation] = frames_by_direction
	return {"base_height": base.y + below, "animations": animations}


static func _scale_warrior_folder(folder: String, scale: float, first_frame_anchor: bool) -> Dictionary:
	var result := {}
	for direction in RULES.DIRECTIONS:
		var images := _load_frames(folder.path_join(direction))
		if images.is_empty():
			continue
		var anchors: Array = []
		for image in images:
			anchors.append(RULES.feet_anchor(image))
		var anchor := Vector2.ZERO
		if first_frame_anchor:
			anchor = Vector2(anchors[0]) * scale
		else:
			var xs: Array = []
			var ys: Array = []
			for point in anchors:
				xs.append(point.x)
				ys.append(point.y)
			anchor = Vector2(RULES.median_int(xs), RULES.median_int(ys)) * scale
		var frames: Array = []
		var box := Rect2i()
		for index in range(images.size()):
			var image: Image = images[index]
			var scaled_frame := image.get_region(Rect2i(Vector2i.ZERO, image.get_size()))
			var size := RULES.scaled_size(image.get_size(), scale)
			scaled_frame.resize(size.x, size.y, Image.INTERPOLATE_BILINEAR)
			frames.append(scaled_frame)
			var used := scaled_frame.get_used_rect()
			box = used if index == 0 else _union(box, used)
		result[direction] = {"frames": frames, "anchor": anchor, "box": box}
	return result


static func _warrior_entries(scaled: Dictionary, folders: Array) -> Array:
	var entries: Array = []
	for folder in folders:
		for direction in scaled[folder]:
			var entry: Dictionary = scaled[folder][direction]
			entries.append({"anchor": entry["anchor"], "box": entry["box"]})
	return entries


static func _union(a: Rect2i, b: Rect2i) -> Rect2i:
	var left := mini(a.position.x, b.position.x)
	var top := mini(a.position.y, b.position.y)
	var right := maxi(a.end.x, b.end.x)
	var bottom := maxi(a.end.y, b.end.y)
	return Rect2i(left, top, right - left, bottom - top)


static func _load_frames(folder: String) -> Array:
	var images: Array = []
	for file_name in DECK_SPRITE.frame_names(folder):
		var image := _load_rgba(folder.path_join(file_name))
		if image != null:
			images.append(image)
	return images


static func _mirrored(frames: Array) -> Array:
	var result: Array = []
	for frame in frames:
		var flipped: Image = frame.get_region(Rect2i(Vector2i.ZERO, frame.get_size()))
		flipped.flip_x()
		result.append(flipped)
	return result


static func _textures(images: Array) -> Array:
	var result: Array = []
	for image in images:
		result.append(ImageTexture.create_from_image(image))
	return result
