extends Node

const RULES := preload("res://scripts/tower_entity_rules.gd")
const VIEW := preload("res://scripts/tower_entity_view.gd")
const DECK_SPRITE := preload("res://scripts/deck_player_sprite_rules.gd")

var _failures: Array[String] = []
var _checks := 0
var _entities = VIEW.new()
var _draw_calls := 0


class Probe extends Node2D:
	var callback: Callable

	func _draw() -> void:
		if callback.is_valid():
			callback.call(self)


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_facing()
	_check_frame_rules()
	_check_mob_and_hero_states()
	_check_harvest_click_corpse()
	_check_synthetic_images()
	_check_npc_and_animal_assets()
	_check_warrior_images()
	_check_player_sprite_sizes()
	_check_portrait()
	_check_extra_entries()
	await _check_draw_probe()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("tower_entity_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _assets_root() -> String:
	return DECK_SPRITE.assets_root(ProjectSettings.globalize_path("res://"))


func _load_rgba(path: String) -> Image:
	var image := Image.load_from_file(path)
	if image == null or image.is_empty():
		return null
	image.convert(Image.FORMAT_RGBA8)
	return image


func _check_facing() -> void:
	var vectors := [
		Vector2(1, 0), Vector2(1, 1), Vector2(0, 1), Vector2(-1, 1), Vector2(-1, 0), Vector2(-1, -1),
		Vector2(0, -1), Vector2(1, -1), Vector2(1, 0.41421356237309503), Vector2(1, 0.41217025707350236),
		Vector2(3, -1), Vector2.from_angle(deg_to_rad(80.0)), Vector2.from_angle(deg_to_rad(120.0)),
		Vector2.from_angle(deg_to_rad(170.0)), Vector2.from_angle(deg_to_rad(-170.0)),
		Vector2.from_angle(deg_to_rad(-135.0)), Vector2.from_angle(deg_to_rad(-100.0)),
		Vector2.from_angle(deg_to_rad(-30.0)), Vector2.from_angle(deg_to_rad(30.0)),
	]
	var expected := ["e", "se", "s", "sw", "w", "nw", "n", "ne", "se", "e", "e", "s", "sw", "w", "w", "nw", "n", "ne", "se"]
	for index in range(vectors.size()):
		_check(RULES.facing_direction(vectors[index]) == expected[index], "направление по вектору #%d" % index)
	_check(RULES.py_round(0.5) == 0 and RULES.py_round(1.5) == 2 and RULES.py_round(2.5) == 2, "round как в Python: половины к чётному")
	_check(RULES.py_round(-0.5) == 0 and RULES.py_round(-1.5) == -2 and RULES.py_round(2.4) == 2, "round для отрицательных и нецелых")
	_check(RULES.py_round(2.6) == 3 and RULES.py_round(-2.5) == -2 and RULES.py_round(3.5) == 4, "round для 2.6, -2.5, 3.5")
	var npc_angles := [0.0, PI / 4.0, PI / 2.0, 3.0 * PI / 4.0, PI, -3.0 * PI / 4.0, -PI / 2.0, -PI / 4.0, 0.1, -2.0]
	var npc_expected := [2, 2, 0, 0, 3, 1, 1, 2, 2, 1]
	var animal_expected := [3, 3, 0, 0, 2, 1, 1, 3, 3, 1]
	for index in range(npc_angles.size()):
		_check(RULES.npc_facing_row(npc_angles[index]) == npc_expected[index], "строка NPC по углу #%d" % index)
		_check(RULES.animal_facing_index(npc_angles[index]) == animal_expected[index], "строка животного по углу #%d" % index)


func _check_frame_rules() -> void:
	var hero_sprites = load("res://scripts/front_line_hero_sprite_rules.gd")
	_check(hero_sprites.row_frame_count("archer", "idle", "n") == 4 and hero_sprites.row_frame_count("archer", "idle", "s") == 12, "спина героя: цикл покоя только по заполненным кадрам строки, фронт остаётся 12")
	_check(hero_sprites.frame_texture("archer", "idle", "n", 9) != null and hero_sprites.frame_texture("archer", "idle", "n", 9).get_size() == Vector2(64, 64), "спина героя: кадр 9 берётся из заполненных кадров и не пуст")
	_check(RULES.walk_frame_index(0, true) == 0 and RULES.walk_frame_index(125, true) == 1, "ходьба моба: 8 кадров/с по 4 кадрам")
	_check(RULES.walk_frame_index(500, true) == 0 and RULES.walk_frame_index(250, true) == 2, "ходьба моба: переход кадра")
	_check(RULES.walk_frame_index(250, false) == 0, "стоячий моб держит первый кадр")
	_check(RULES.attack_frame_index(1000, 1000.0, 800.0) == 0 and RULES.attack_frame_index(1400, 1000.0, 800.0) == 2, "замах моба: кадры по прогрессу")
	_check(RULES.attack_frame_index(1800, 1000.0, 800.0) == 3 and RULES.attack_frame_index(900, 1000.0, 800.0) == 0, "замах моба: зажим 0..3")
	_check(RULES.walk_frame_index(625, true, 6) == 5 and RULES.walk_frame_index(750, true, 6) == 0, "ходьба моба проходит все 6 кадров листа")
	_check(RULES.attack_windup_frames(8) == 4 and RULES.attack_windup_frames(7) == 3 and RULES.attack_windup_frames(1) == 1, "замах занимает первую половину листа атаки")
	var swing_state := {"attack_started": 1000.0, "attack_ms": 800.0, "strike_started": 2000.0, "strike_ms": 400.0}
	_check(RULES.mob_attack_frame(swing_state, 0.4, 1400, 8, 4) == 2, "замах моба идёт по кадрам до удара")
	_check(RULES.mob_attack_frame(swing_state, 0.0, 2000, 8, 4) == 4 and RULES.mob_attack_frame(swing_state, 0.0, 2300, 8, 4) == 7, "после удара моб доигрывает вторую половину листа")
	_check(RULES.mob_attack_frame(swing_state, 0.0, 2400, 8, 4) == -1 and RULES.mob_attack_frame(swing_state, 0.0, 2000, 4, 4) == -1, "откат закончен или лист без кадров удара: атаки нет")
	var swing_ids := {"swing_started": 1000.0, "swing_windup_ms": 800.0, "swing_backswing_ms": 400.0}
	_check(RULES.mob_attack_frame(swing_ids, 0.0, 1400, 8, 4) == 2, "цикл атаки по swing_id: замах идёт без новых снимков")
	_check(RULES.mob_attack_frame(swing_ids, 0.0, 1800, 8, 4) == 4 and RULES.mob_attack_frame(swing_ids, 0.0, 2199, 8, 4) == 7, "цикл атаки: откат доигрывает вторую половину за backswing_ms")
	_check(RULES.mob_attack_frame(swing_ids, 0.0, 2300, 8, 4) == -1, "цикл атаки кончается через замах и откат")
	_check(RULES.mob_hurt_frame({"hurt_started": 1000.0}, 1000, 4) == 0 and RULES.mob_hurt_frame({"hurt_started": 1000.0}, 1200, 4) == 2, "анимация урона моба: кадры за 400 мс")
	_check(RULES.mob_hurt_frame({"hurt_started": 1000.0}, 1400, 4) == -1 and RULES.mob_hurt_frame({}, 1000, 4) == -1, "анимация урона моба проигрывается один раз")
	_check(RULES.death_frame_index(0.0, 7) == 0 and RULES.death_frame_index(143.0, 7) == 1, "смерть моба: 7 кадров/с")
	_check(RULES.death_frame_index(1000.0, 7) == 6, "смерть моба: последний кадр держится")
	_check(RULES.corpse_alpha_byte(30000.0) == 255 and RULES.corpse_alpha_byte(37500.0) == 127, "труп гаснет после 30 с")
	_check(RULES.corpse_visible(44999.0) and not RULES.corpse_visible(45000.0), "труп исчезает через 45 с")
	_check(is_equal_approx(RULES.corpse_fall_degrees(250.0), 45.0) and is_equal_approx(RULES.corpse_fall_degrees(600.0), 90.0), "падение без листа смерти: 90° за 0.5 с")
	_check(RULES.animal_frame_index(160, 6) == 1 and RULES.animal_frame_index(959, 6) == 5 and RULES.animal_frame_index(960, 6) == 0, "животное: кадр каждые 160 мс")
	_check(is_equal_approx(RULES.hp_ratio(50.0, 100.0), 0.5) and RULES.hp_ratio(-5.0, 100.0) == 0.0, "полоска ХП: нижний зажим")
	_check(RULES.hp_ratio(150.0, 100.0) == 1.0 and RULES.hp_ratio(3.0, 0.0) == 1.0, "полоска ХП: верхний зажим и максимум 0")
	_check(RULES.player_state(true, true, false, false, false) == "run", "воин идёт: бег")
	_check(RULES.player_state(true, false, true, false, false) == "attack", "воин замахивается: атака")
	_check(RULES.player_state(true, true, false, true, false) == "gothit", "удар важнее ходьбы")
	_check(RULES.player_state(true, false, false, false, true) == "death", "смерть воина")
	_check(RULES.player_state(false, true, true, true, true) == "run" and RULES.player_state(false, false, true, false, false) == "idle", "не-воин: только бег и стойка")
	_check(RULES.player_frame_index("idle", 1.3, 4, 0.0) == 1 and RULES.player_frame_index("run", 0.35, 6, 0.0) == 3, "кадр героя по времени, fps 4 и 10")
	_check(RULES.player_frame_index("attack", 0.0, 10, 0.55) == 5 and RULES.player_frame_index("death", 0.0, 8, 1.0) == 7, "кадр атаки и смерти по прогрессу")
	_check(is_equal_approx(RULES.attack_progress(0.4, 0.8), 0.5) and RULES.attack_progress(0.0, 0.8) == 0.0, "прогресс замаха")
	_check(RULES.attack_progress(0.5, 0.0) == 0.0, "прогресс замаха без полного времени берёт текущий замах")
	var clicks := [[0.35, 8, 255], [0.175, 16, 127], [0.0, 24, 0], [0.1, 19, 72]]
	for click in clicks:
		var style := RULES.click_effect_style(click[0])
		_check(int(style["radius"]) == click[1] and int(style["alpha"]) == click[2], "кольцо клика при таймере %s" % str(click[0]))


func _check_mob_and_hero_states() -> void:
	var mob_a := {"id": "a", "x": 10.0, "y": 20.0, "state": "alive", "hp": 5.0, "max_hp": 10.0, "windup": 0.0, "windup_total": 0.0, "facing": 0.0}
	var first := RULES.advance_mob({}, mob_a, 1000)
	_check(float(first["moved_at"]) == 1000.0 and not first.has("died_at") and not first.has("attack_started"), "новый моб: время движения от первого кадра")
	var second := RULES.advance_mob(first, mob_a, 2000)
	_check(float(second["moved_at"]) == 1000.0, "стоящий моб не сбрасывает время движения")
	var mob_b := mob_a.duplicate()
	mob_b["x"] = 12.0
	var moved := RULES.advance_mob(second, mob_b, 2500)
	_check(float(moved["moved_at"]) == 2500.0, "сдвиг позиции обновляет время движения")
	var mob_dead := mob_b.duplicate()
	mob_dead["state"] = "dead"
	mob_dead["hp"] = 0.0
	var died := RULES.advance_mob(moved, mob_dead, 3000)
	_check(float(died["died_at"]) == 3000.0, "переход в dead ставит время смерти")
	_check(float(RULES.advance_mob(died, mob_dead, 3100)["died_at"]) == 3000.0, "повторный снимок не переставляет смерть")
	_check(not RULES.advance_mob({}, mob_dead, 3000).has("died_at"), "мёртвый при первом появлении не получает смерть, как в Python")
	var swing := mob_a.duplicate()
	swing["windup"] = 0.5
	swing["windup_total"] = 0.8
	var started := RULES.advance_mob(second, swing, 4000)
	_check(float(started["attack_started"]) == 4000.0 and is_equal_approx(float(started["attack_ms"]), 800.0), "начало замаха моба: время и длительность")
	var swing_more := swing.duplicate()
	swing_more["windup"] = 0.4
	_check(float(RULES.advance_mob(started, swing_more, 4100)["attack_started"]) == 4000.0, "продолжающийся замах не перезапускает атаку")
	var strike := mob_a.duplicate()
	strike["backswing"] = 0.3
	strike["backswing_total"] = 0.4
	var struck := RULES.advance_mob(started, strike, 5000)
	_check(is_equal_approx(float(struck["strike_started"]), 4900.0) and is_equal_approx(float(struck["strike_ms"]), 400.0), "удар моба: откат отсчитывается от момента удара")
	_check(float(RULES.advance_mob(struck, strike, 5100)["strike_started"]) == float(struck["strike_started"]), "продолжающийся откат не перезапускает удар")
	var walker_a := {"id": "w", "x": 0.0, "y": 0.0, "state": "alive", "hp": 5.0, "max_hp": 10.0, "windup": 0.0, "windup_total": 0.0, "facing": 0.0}
	var walker_b := walker_a.duplicate()
	walker_b["x"] = 20.0
	var walk_first := RULES.advance_mob({}, walker_a, 1000)
	var walk_second := RULES.advance_mob(walk_first, walker_b, 1200)
	_check(RULES.mob_display_position(walk_second, 1200, Vector2(20.0, 0.0)).is_equal_approx(Vector2(10.0, 0.0)), "буфер 100 мс: в момент второго снимка моб на середине пути")
	_check(RULES.mob_display_position(walk_second, 1300, Vector2(20.0, 0.0)).is_equal_approx(Vector2(20.0, 0.0)), "буфер 100 мс: через 100 мс моб на позиции второго снимка")
	_check(RULES.mob_display_position(walk_second, 1500, Vector2(20.0, 0.0)).is_equal_approx(Vector2(20.0, 0.0)), "за последним снимком позиция держится, без экстраполяции")
	_check(RULES.mob_display_position(walk_second, 1100, Vector2(20.0, 0.0)).is_equal_approx(Vector2(0.0, 0.0)), "до второго снимка показывается первый")
	_check(RULES.mob_display_position({}, 1000, Vector2(5.0, 5.0)) == Vector2(5.0, 5.0), "новый моб без истории ставится сразу")
	_check(RULES.lunge_offset(300.0, 500.0, 0.0, 3.0) == Vector2.ZERO, "выпад: вне окна удара смещения нет")
	_check(RULES.lunge_offset(500.0, 500.0, 0.0, 3.0).is_equal_approx(Vector2(3.0, 0.0)), "выпад: максимум в момент удара вдоль взгляда")
	_check(RULES.lunge_offset(500.0, 500.0, PI / 2.0, 3.0).is_equal_approx(Vector2(0.0, 3.0)), "выпад: направление следует за взглядом")
	var swing_payload := mob_a.duplicate()
	swing_payload["swing_id"] = 7
	swing_payload["windup"] = 0.5
	swing_payload["windup_total"] = 0.8
	swing_payload["backswing_total"] = 0.4
	var swung := RULES.advance_mob(second, swing_payload, 4000)
	_check(is_equal_approx(float(swung["swing_started"]), 3700.0), "снимок в середине замаха: цикл отсчитывается от начала замаха")
	var swung_more := swing_payload.duplicate()
	swung_more["windup"] = 0.4
	_check(float(RULES.advance_mob(swung, swung_more, 4100)["swing_started"]) == float(swung["swing_started"]), "тот же swing_id не перезапускает цикл атаки")
	var hit_payload := mob_a.duplicate()
	hit_payload["hurt_id"] = 1
	_check(not RULES.advance_mob(second, hit_payload, 4500).has("hurt_started"), "первый снимок с hurt_id не проигрывает урон")
	var hit_again := hit_payload.duplicate()
	hit_again["hurt_id"] = 2
	_check(float(RULES.advance_mob(hit_payload, hit_again, 4600)["hurt_started"]) == 4600.0, "новый hurt_id запускает анимацию урона")
	var hp_drop := mob_a.duplicate()
	hp_drop["hp"] = 3.0
	_check(float(RULES.advance_mob(second, hp_drop, 4700)["hurt_started"]) == 4700.0, "без hurt_id урон виден по падению здоровья")

	var hero_a := RULES.advance_hero({}, {"hp": 100.0, "windup": 0.0, "windup_total": 0.0}, 1.0, 0)
	_check(hero_a["hit_started"] == null and RULES.hero_hit_progress(hero_a, 1.0) == null, "первый снимок героя без удара")
	var hero_b := RULES.advance_hero(hero_a, {"hp": 90.0, "windup": 0.0, "windup_total": 0.0}, 2.0, 0)
	_check(float(hero_b["hit_started"]) == 2.0, "падение здоровья героя запускает удар")
	_check(is_equal_approx(float(RULES.hero_hit_progress(hero_b, 2.2)), 0.2 / 0.45), "прогресс удара по времени")
	_check(RULES.hero_hit_progress(hero_b, 2.5) == null, "удар заканчивается через 0.45 с")
	var hero_c := RULES.advance_hero(hero_b, {"hp": 0.0, "windup": 0.0, "windup_total": 0.0}, 3.0, 0)
	_check(float(hero_c["death_started"]) == 3.0 and hero_c["hit_started"] == null, "смерть отменяет удар")
	var hero_swing := {"hp": 100.0, "windup": 0.5, "windup_total": 0.8, "backswing": 0.0, "backswing_total": 0.4, "swing_id": 3}
	var hero_s := RULES.advance_hero({}, hero_swing, 10.0, 0)
	_check(is_equal_approx(float(hero_s["swing_started"]), 9.7), "герой: цикл по swing_id отсчитывается от начала замаха")
	_check(RULES.hero_attack_frame(hero_s, 10.5, 8) == 4, "герой: удар на границе замаха и отката")
	_check(is_equal_approx(float(RULES.hero_death_progress(hero_c, 3.5)), 0.5) and is_equal_approx(float(RULES.hero_death_progress(hero_c, 5.0)), 1.0), "прогресс смерти по времени, зажим до 1")
	var hero_d := RULES.advance_hero(hero_c, {"hp": 40.0, "windup": 0.0, "windup_total": 0.0}, 6.0, 0)
	_check(hero_d["death_started"] == null and RULES.hero_death_progress(hero_d, 6.5) == null, "воскрешение снимает смерть")
	var hero_e := RULES.advance_hero(hero_d, {"hp": 40.0, "windup": 0.5, "windup_total": 0.8}, 7.0, 1)
	_check(int(hero_e["variant"]) == 1, "вариант атаки выбирается в начале замаха")
	var hero_f := RULES.advance_hero(hero_e, {"hp": 40.0, "windup": 0.4, "windup_total": 0.8}, 7.1, 0)
	_check(int(hero_f["variant"]) == 1, "вариант атаки не меняется во время замаха")
	_check(float(hero_e["attack_started"]) == 7.0 and RULES.hero_attack_frame(hero_f, 7.4, 8) == 2, "замах героя идёт по первой половине листа")
	var hero_g := RULES.advance_hero(hero_f, {"hp": 40.0, "windup": 0.0, "backswing": 0.5, "backswing_total": 0.5}, 8.0, 0)
	_check(RULES.hero_attack_frame(hero_g, 8.0, 8) == 4 and RULES.hero_attack_frame(hero_g, 8.45, 8) == 7, "после удара герой доигрывает вторую половину листа")
	_check(RULES.hero_attack_frame(hero_g, 8.5, 8) == -1 and RULES.hero_attack_frame(hero_d, 6.0, 8) == -1, "без замаха и отката кадра атаки нет")


func _check_harvest_click_corpse() -> void:
	_check(RULES.harvest_visible({"x": 1, "y": 2, "progress": 2.0, "total": 4.0}), "добыча видна при total > 0")
	_check(not RULES.harvest_visible(null) and not RULES.harvest_visible({"total": 0.0}), "без добычи полоски нет")
	_check(is_equal_approx(RULES.harvest_fill({"progress": 2.5, "total": 5.0}), 0.5), "заполнение добычи")
	var bar := RULES.harvest_bar_rect(Vector2(100.7, 50.2), 0.28)
	_check(bar == Rect2(80, 35, 40, 6), "полоска добычи в экранных координатах, zoom 0.28")
	_check(RULES.harvest_bar_rect(Vector2(7.9, 3.3), 1.0) == Rect2(-12, -22, 40, 6), "полоска добычи: усечение к нулю у отрицательных")
	_check(RULES.harvest_bar_rect(Vector2(-3.6, 22.9), 0.5) == Rect2(-23, 4, 40, 6), "полоска добычи: zoom 0.5 у края")
	_check(RULES.harvest_center({"x": 3, "y": 4}) == Vector2(112, 144) and RULES.harvest_center(null) == Vector2.ZERO, "центр клетки добычи в мире")
	_check(RULES.tile_of([4, 5]) == Vector2i(4, 5) and RULES.tile_of(null) == null and RULES.tile_of(Vector2i(1, 2)) == Vector2i(1, 2), "клетка добычи из пары")
	_check(RULES.tile_center(Vector2i(2, 3)) == Vector2(80, 112), "центр клетки")
	_check(is_equal_approx(RULES.corpse_distance_tiles(Vector2(96, 128), Vector2.ZERO), 5.0), "расстояние до трупа в тайлах")
	_check(RULES.corpse_marker_rect(Vector2(100, 50)) == Rect2(86, 30, 28, 20), "маркер трупа 28x20 над ногами")
	_check(RULES.center_rect(Vector2(100, 100), Vector2(77, 77)) == Rect2(62, 62, 77, 77), "прямоугольник по центру: половина с полом")
	_check(RULES.midbottom_rect(Vector2(100, 100), Vector2(32, 32)) == Rect2(84, 68, 32, 32), "прямоугольник по низу центра")
	var sheet_red := RULES.npc_sheet_names("imp_vanilla")
	_check(sheet_red.get("folder") == "imp_red_vanilla" and sheet_red.get("walk") == "imp_red_vanilla walk.png", "лист NPC: красный вариант")
	_check(RULES.npc_sheet_names("imp_green_sword_shield").get("folder") == "imp_green_sword_shield", "лист NPC: зелёный с щитом")
	_check(RULES.npc_sheet_names("bandit").is_empty(), "неизвестный вид без листа")
	_check(RULES.animal_layout("animal_cat").get("asset") == "cat" and RULES.animal_layout("animal_zzz").is_empty(), "описание животного по ключу")
	_check(RULES.animal_layout("animal_duck_water").get("asset") == "duck", "водоплавающее использует лист вида")


func _check_synthetic_images() -> void:
	var image := Image.create_empty(10, 10, false, Image.FORMAT_RGBA8)
	for y in range(1, 9):
		for x in range(1, 9):
			image.set_pixel(x, y, Color(0, 0, 0, 100.0 / 255.0))
	for y in range(3, 9):
		for x in range(2, 7):
			image.set_pixel(x, y, Color(1, 1, 1, 1))
	var full := Rect2i(Vector2i.ZERO, image.get_size())
	_check(RULES.opaque_rect(image, 201, full) == Rect2i(2, 3, 5, 6), "плотная фигура без полупрозрачной тени")
	_check(RULES.opaque_rect(image, 1, full) == Rect2i(1, 1, 8, 8), "любая непрозрачность")
	_check(RULES.feet_anchor(image) == Vector2i(4, 9), "точка ног по нижней полосе фигуры")
	var canvas := Image.create_empty(4, 4, false, Image.FORMAT_RGBA8)
	var source := Image.create_empty(3, 3, false, Image.FORMAT_RGBA8)
	source.fill(Color(1, 0, 0, 1))
	RULES.blit_clipped(canvas, source, Vector2i(2, 2))
	_check(canvas.get_pixel(2, 2).a > 0.5 and canvas.get_pixel(3, 3).a > 0.5 and canvas.get_pixel(1, 1).a < 0.5, "вставка с обрезкой справа и снизу")
	var clipped := Image.create_empty(4, 4, false, Image.FORMAT_RGBA8)
	RULES.blit_clipped(clipped, source, Vector2i(-1, -1))
	_check(clipped.get_pixel(1, 1).a > 0.5 and clipped.get_pixel(2, 2).a < 0.5, "вставка с отрицательным сдвигом")
	_check(RULES.warrior_source("w", ["n", "e", "s"]) == {"source": "e", "mirrored": true}, "недостающий запад берётся зеркально из востока")
	_check(RULES.warrior_source("nw", ["n", "s", "e"]) == {"source": "n", "mirrored": false}, "недостающий северо-запад берётся из соседнего по кругу")
	_check(RULES.warrior_extents([{"anchor": Vector2(10, 20), "box": Rect2i(0, 5, 30, 25)}]) == Vector3i(21, 15, 10), "размеры холста воина по габариту")
	_check(RULES.warrior_offset(Vector2(82.5, 91.5), 83, 100) == Vector2i(0, 8), "смещение кадра воина: округление как в Python")
	_check(is_equal_approx(RULES.warrior_scale([121, 130, 100]), 90.0 / 121.0), "масштаб воина по медиане высоты ходьбы")
	_check(RULES.mob_figure_size(Vector2i(60, 41), 41) == Vector2i(16, 11), "обычный моб уменьшен примерно в четыре раза")
	_check(RULES.mob_canvas_offset(Rect2i(0, 0, 16, 16)) == Vector2i(0, 0), "ноги моба остаются в пределах половины тайла")


func _check_npc_and_animal_assets() -> void:
	var npc_walk := _load_rgba(_assets_root().path_join("NPC/imp_red_vanilla/imp_red_vanilla walk.png"))
	_check(npc_walk != null and npc_walk.get_size() == Vector2i(256, 256), "лист ходьбы NPC 256x256")
	if npc_walk != null:
		var sample_cells := [Vector2i(0, 0), Vector2i(1, 0), Vector2i(0, 2), Vector2i(3, 2)]
		for cell_key in sample_cells:
			var cell := npc_walk.get_region(Rect2i(cell_key.x * 64, cell_key.y * 64, 64, 64))
			var canvas := RULES.normalize_npc_frame(cell)
			var bounds := canvas.get_used_rect()
			_check(
				canvas.get_size() == Vector2i(16, 16)
				and bounds.size.x <= 16
				and bounds.size.y <= 16
				and bounds.end.y == 16,
				"обычный NPC помещается в половину тайла и стоит на опорной линии %s" % str(cell_key),
			)
	var death := _load_rgba(_assets_root().path_join("NPC/imp_red_vanilla/imp_red_vanilla death.png"))
	_check(death != null and death.get_width() / 64 == 7, "лист смерти NPC: 7 кадров по 64 px")
	var cat := RULES.animal_frame_rects(RULES.animal_layout("animal_cat"), Vector2i(256, 256))
	_check(cat["moving"].size() == 4 and cat["moving"][0].size() == 6 and cat["idle"][0].size() == 1, "животное: 4 строки по 6 кадров и стойка")
	_check(cat["moving"][0][0] == Rect2i(0, 0, 32, 32) and cat["moving"][0][1] == Rect2i(32, 0, 32, 32), "животное: первые кадры ходьбы")
	_check(cat["idle"][0][0] == Rect2i(0, 128, 32, 32) and cat["moving"][3][5] == Rect2i(160, 96, 32, 32), "животное: строки стойки и последний кадр")
	var duck := RULES.animal_frame_rects(RULES.animal_layout("animal_duck_water"), Vector2i(192, 512))
	_check(duck["moving"][0][0] == Rect2i(0, 256, 32, 32) and duck["idle"][0][0] == Rect2i(0, 384, 32, 32), "водоплавающее: строки 8..15")
	_check(duck["moving"][3][5] == Rect2i(160, 352, 32, 32), "водоплавающее: последний кадр")
	var small := RULES.animal_frame_rects(RULES.animal_layout("animal_cat"), Vector2i(64, 64))
	_check(small["moving"][0].size() == 2 and small["moving"][2].is_empty(), "кадры за пределами листа не берутся")
	_check(_load_rgba(_assets_root().path_join("map/animals/duck.png")).get_size() == Vector2i(192, 512), "лист утки 192x512")


func _check_warrior_images() -> void:
	var built := VIEW.build_warrior_images(_assets_root().path_join("warrior"))
	_check(not built.is_empty(), "кадры воина загружены")
	if built.is_empty():
		return
	var raw_cases := {
		"walk/e/01.png": [Rect2i(96, 3, 41, 120), Rect2i(11, 2, 127, 126), Vector2i(111, 123)],
		"attack1/s/01.png": [Rect2i(209, 19, 49, 159), Rect2i(89, 18, 170, 165), Vector2i(243, 178)],
		"gothit/n/01.png": [Rect2i(206, 34, 49, 132), Rect2i(129, 33, 127, 135), Vector2i(219, 166)],
		"idle/w/01.png": [Rect2i(81, 8, 41, 119), Rect2i(15, 7, 108, 122), Vector2i(106, 127)],
	}
	for rel in raw_cases:
		var raw := _load_rgba(_assets_root().path_join("warrior").path_join(rel))
		var full := Rect2i(Vector2i.ZERO, raw.get_size())
		var expected: Array = raw_cases[rel]
		_check(RULES.opaque_rect(raw, 201, full) == expected[0], "плотная фигура кадра %s как в pygame" % rel)
		_check(raw.get_used_rect() == expected[1], "видимые пиксели кадра %s как в pygame" % rel)
		_check(RULES.feet_anchor(raw) == expected[2], "точка ног кадра %s как в pygame" % rel)
	var animations: Dictionary = built["animations"]
	# pygame даёт 103 (smoothscale): билинейный ресэмпл Godot на 1 px ниже по верхнему краю кадров ходьбы.
	_check(int(built["base_height"]) == 102, "высота холста воина по ногам: 102 px (pygame 103)")
	_check(animations["idle"]["e"].size() == 1 and animations["idle"]["e"][0].get_size() == Vector2i(166, 102), "стойка воина: один кадр 166x102")
	_check(animations["run"]["e"].size() == 10 and animations["run"]["e"][0].get_size() == Vector2i(166, 102), "бег воина: 10 кадров 166x102")
	_check(animations["attack1"]["e"].size() == 10 and animations["attack1"]["e"][0].get_size() == Vector2i(364, 146), "атака 1: 10 кадров 364x146 как в pygame")
	_check(animations["attack2"]["e"].size() == 18 and animations["attack2"]["n"][0].get_size() == Vector2i(364, 146), "атака 2: 18 кадров 364x146 как в pygame")
	_check(animations["gothit"]["e"].size() == 6 and animations["death"]["e"].size() == 8, "удар 6 кадров, смерть 8 кадров")
	for animation in ["idle", "run", "attack1", "attack2", "gothit", "death"]:
		_check(animations[animation].size() == 8, "все 8 направлений для %s" % animation)


func _check_player_sprite_sizes() -> void:
	var expected := {"2Idle": {"e": [32, 4], "s": [54, 4]}, "3run": {"e": [74, 6], "w": [68, 6]}}
	for folder in expected:
		var frames := DECK_SPRITE.directional_frames(_assets_root().path_join(folder), RULES.PLAYER_SPRITE_HEIGHT)
		for direction in expected[folder]:
			var row: Array = expected[folder][direction]
			var textures: Array = frames.get(direction, [])
			_check(textures.size() == row[1] and textures[0].get_size() == Vector2(row[0], 90), "кадры %s/%s 90 px как в pygame" % [folder, direction])


func _check_portrait() -> void:
	_entities.player_overhead({"x": 0.0, "y": 0.0, "type": "warrior", "hp": 1.0, "max_hp": 1.0}, "s", 0.0, false)
	var warrior_portrait: Variant = _entities.player_portrait_texture("s")
	_entities.player_overhead({"x": 0.0, "y": 0.0, "type": "archer", "hp": 1.0, "max_hp": 1.0}, "s", 0.0, false)
	var archer_portrait: Variant = _entities.player_portrait_texture("s")
	_check(
		warrior_portrait is Texture2D and warrior_portrait.get_size() == Vector2(166, 102)
		and archer_portrait is Texture2D and archer_portrait.get_size() == Vector2(54, 90),
		"портрет героя: первый кадр стойки нативного размера для воина и лучника"
	)


func _check_extra_entries() -> void:
	var player := {"x": 40.0, "y": 100.0, "hp": 1.0, "max_hp": 1.0, "type": "archer"}
	var without_extras: Array = _entities._actor_plan([], [], player, "s", 0.0, false, "", 0, [])
	_check(without_extras.size() == 1 and int(without_extras[0]["order"]) == 1, "без дополнительных элементов в плане только герой")
	var order: Array = []
	var everywhere := Rect2(0.0, 0.0, 1000.0, 1000.0)
	var far := Rect2(500.0, 500.0, 10.0, 10.0)
	var extras: Array = [
		{"base_y": 300.0, "draw": func(canvas: CanvasItem) -> void: order.append("high")},
		{"base_y": 10.0, "draw": func(canvas: CanvasItem) -> void: order.append("low")},
		{"base_y": 100.0, "draw": func(canvas: CanvasItem) -> void: order.append("same")},
		{"base_y": 50.0, "rect": everywhere, "draw": func(canvas: CanvasItem) -> void: order.append("behind")},
		{"base_y": 150.0, "rect": everywhere, "draw": func(canvas: CanvasItem) -> void: order.append("front")},
		{"base_y": 150.0, "rect": far, "draw": func(canvas: CanvasItem) -> void: order.append("far")},
	]
	var plan: Array = _entities._actor_plan([], [], player, "s", 0.0, false, "", 0, extras)
	for entry in plan:
		if int(entry["order"]) == 1:
			entry["draw"] = func(canvas: CanvasItem) -> void: order.append("player")
	for entry in plan:
		entry["draw"].call(null)
	_check(order == ["low", "player", "same", "front", "high"], "дополнительный элемент с большей глубиной рисуется после актёра с меньшей; передний план по прямоугольнику")


func _check_draw_probe() -> void:
	var mobs := [
		{"id": "m1", "kind": "imp_vanilla", "x": 100.0, "y": 120.0, "hp": 5.0, "max_hp": 10.0, "state": "alive", "facing": 0.0, "windup": 0.0, "windup_total": 0.0, "level": 1},
		{"id": "m2", "kind": "imp_green_sword", "x": 200.0, "y": 50.0, "hp": 0.0, "max_hp": 10.0, "state": "dead", "facing": 3.14, "windup": 0.0, "windup_total": 0.0, "level": 1},
	]
	var animals := [{"id": 1, "key": "animal_cat", "x": 50.0, "y": 60.0, "facing": 0.0, "moving": true}]
	var player := {"x": 80.0, "y": 90.0, "hp": 80.0, "max_hp": 100.0, "mp": 20.0, "max_mp": 40.0, "type": "warrior", "name": "Тест", "windup": 0.0, "windup_total": 0.0}
	var corpses := [{"id": 7, "x": 300.0, "y": 200.0, "copper": 10}]
	var crystals := [[10, 11, "blue", 2], [12, 13, "unknown_color", 1]]
	var harvest := {"x": 10, "y": 11, "progress": 2.0, "total": 4.0}
	var overheads: Array = _entities.mob_overheads(mobs, "m1", 1000)
	_check(overheads.size() == 1 and overheads[0]["id"] == "m1", "полоска ХП только у живого моба")
	if overheads.size() == 1:
		_check(overheads[0]["anchor"] == Vector2(100.0, 112.0) and is_equal_approx(overheads[0]["hp_ratio"], 0.5), "ХП моба: верх спрайта 16 px и доля")
		_check(overheads[0]["bar_size"] == Vector2(32.0, 5.0), "полоска ХП не шире одного тайла для обычного моба")
		_check(overheads[0]["hp_text"] == "ХП 5/10" and overheads[0]["selected"], "подпись ХП моба и выбор")
	var hero: Dictionary = _entities.player_overhead(player, "s", 1.0, true)
	_check(is_equal_approx(float(hero["mp_bar_bottom"]), 90.0 - 102.0 - 4.0), "полоска МП над холстом воина: ноги минус база минус 4")
	_check(hero["hp_text"] == "ХП 80/100" and hero["mp_text"] == "МП 20/40" and hero["name"] == "Тест", "подписи героя")
	var archer: Dictionary = _entities.player_overhead({"x": 80.0, "y": 90.0, "hp": 1.0, "max_hp": 2.0, "type": "archer"}, "s", 0.0, false)
	_check(is_equal_approx(float(archer["mp_bar_bottom"]), 90.0 - 90.0 - 4.0), "полоска МП над стойкой лучника: высота кадра 90")
	_entities._sync_mobs(mobs, 1000)
	var regular_sprite: Dictionary = _entities._mob_sprite(mobs[0], 1000)
	_check(
		not regular_sprite.is_empty() and regular_sprite["texture"] is Texture2D,
		"обычный imp из волны имеет видимый спрайт",
	)
	var front_line_mob: Dictionary = mobs[0].duplicate(true)
	front_line_mob["id"] = "front_line_mob"
	front_line_mob["front_line"] = true
	var front_line_sprite: Dictionary = _entities._mob_sprite(front_line_mob, 1000)
	_check(
		front_line_sprite["rect"].size == Vector2(RULES.NPC_FRAME_SIZE, RULES.NPC_FRAME_SIZE),
		"Front Line сохраняет исходный кадр imp 64x64 без уменьшения",
	)
	var palette_mob := {
		"id": "palette_goblin",
		"kind": "mob|goblin sprite-pack|g1",
		"x": 140.0,
		"y": 120.0,
		"hp": 5.0,
		"max_hp": 10.0,
		"state": "alive",
		"facing": 0.0,
		"windup": 0.0,
		"windup_total": 0.0,
	}
	_entities._sync_mobs([palette_mob], 1000)
	var palette_sprite: Dictionary = _entities._mob_sprite(palette_mob, 1000)
	_check(
		not palette_sprite.is_empty() and palette_sprite["texture"] is Texture2D,
		"спрайт гоблина из палитры загружается для боевой волны",
	)
	var active_map_mob := {
		"id": "active_map_rat",
		"kind": "mob|craftpix-net-415491-giant-rat-4-direction-pixel-character-sprite-pack|rat1",
		"x": 160.0,
		"y": 120.0,
		"hp": 5.0,
		"max_hp": 10.0,
		"state": "walk",
		"facing": 0.0,
		"windup": 0.0,
		"windup_total": 0.0,
		"front_line": true,
	}
	_entities._sync_mobs([active_map_mob], 1000)
	var moved_map_mob: Dictionary = active_map_mob.duplicate(true)
	moved_map_mob["x"] = 161.0
	_entities._sync_mobs([moved_map_mob], 1125)
	var rat_walk_first: Dictionary = _entities._mob_sprite(moved_map_mob, 1250)
	var rat_walk_next: Dictionary = _entities._mob_sprite(moved_map_mob, 1375)
	_check(
		not rat_walk_first.is_empty()
		and not rat_walk_next.is_empty()
		and rat_walk_first["texture"] != rat_walk_next["texture"],
		"анимация ходьбы крысы из активной волны карты переключает кадры",
	)
	if not rat_walk_first.is_empty():
		var source := _load_rgba(ProjectSettings.globalize_path("res://assets/base_tails/LPC/craftpix-net-415491-giant-rat-4-direction-pixel-character-sprite-pack/Tiled/Rat1_Walk_with_shadow.png"))
		var frame_size := source.get_height() / 4
		# Строки паков палитры: вниз, вверх, влево, вправо — взгляд вправо берёт строку 3.
		var source_cell := source.get_region(Rect2i(0, 3 * frame_size, frame_size, frame_size))
		var idle_rat: Dictionary = _entities._mob_sprite(active_map_mob, 2000)
		var loaded: Image = idle_rat["texture"].get_image()
		_check(_same_visible_pixels(loaded, source_cell) and idle_rat["rect"].size == Vector2(frame_size, frame_size),
			"Кадр крысы Front Line сохраняет исходные видимые пиксели, прозрачность и размер художника")
		var left_rat: Dictionary = active_map_mob.duplicate(true)
		left_rat["id"] = "left_rat"
		left_rat["facing"] = PI
		_entities._sync_mobs([left_rat], 0)
		var left_sprite: Dictionary = _entities._mob_sprite(left_rat, 2000)
		_check(_same_visible_pixels(left_sprite["texture"].get_image(), source.get_region(Rect2i(0, 2 * frame_size, frame_size, frame_size))),
			"крыса, идущая влево, смотрит влево, а не пятится")
		var bounds: Rect2 = idle_rat.get("bounds", idle_rat["rect"])
		_check(idle_rat.has("bounds") and idle_rat["rect"].encloses(bounds) and bounds.size.x < frame_size * 0.75 and bounds.size.y < frame_size * 0.75,
			"рамка крысы охватывает видимые пиксели, а не весь кадр листа")
		_entities._sync_mobs([active_map_mob], 2000)
		var live_bounds: Rect2 = _entities._mob_sprite(active_map_mob, 2000).get("bounds", bounds)
		var rat_overheads: Array = _entities.mob_overheads([active_map_mob], "active_map_rat", 2000)
		_check(rat_overheads.size() == 1 and rat_overheads[0]["outline"] == live_bounds.grow(4.0)
			and is_equal_approx(rat_overheads[0]["anchor"].y, live_bounds.position.y),
			"выделение и полоска ХП крысы стоят по видимому телу")
		var attack_sheets: Dictionary = VIEW._npc_sheets(str(active_map_mob["kind"]), true)
		var attack_row: Array = attack_sheets["attack"][RULES.NPC_ROW_RIGHT]
		var biting: Dictionary = active_map_mob.duplicate(true)
		biting["backswing"] = 0.4
		biting["backswing_total"] = 0.4
		_entities._sync_mobs([biting], 3000)
		var bite: Dictionary = _entities._mob_sprite(biting, 3000)
		_check(attack_row.size() == 8 and int(attack_sheets["attack_windup_frames"]) == 4
			and bite["texture"] == attack_row[4],
			"после удара крыса показывает кадр укуса из второй половины листа атаки")
		var rat_boss: Dictionary = active_map_mob.duplicate(true)
		rat_boss["id"] = "rat_boss"
		rat_boss["is_boss"] = true
		var large_rat: Dictionary = _entities._mob_sprite(rat_boss, 2000)
		_check(large_rat["rect"].size == idle_rat["rect"].size * 4.0
			and large_rat["texture"] == idle_rat["texture"],
			"Только босс крысы увеличивается ровно вчетверо без повторного уменьшения исходника")
		for mob in [active_map_mob, rat_boss]:
			var dead: Dictionary = mob.duplicate(true)
			dead["hp"] = 0
			dead["state"] = "dead"
			_entities._sync_mobs([mob], 2000)
			_entities._sync_mobs([dead], 2100)
			var corpse: Dictionary = _entities._mob_sprite(dead, 2100)
			_check(not corpse.is_empty() and corpse["rect"].size == Vector2(frame_size, frame_size) * (4.0 if mob.get("is_boss", false) else 1.0),
				"Размер обычной крысы и босса сохраняется в анимации смерти")
	var boss: Dictionary = mobs[0].duplicate(true)
	boss["id"] = "boss"
	boss["is_boss"] = true
	var boss_sprite: Dictionary = _entities._mob_sprite(boss, 1000)
	_check(
		boss_sprite["rect"].size == regular_sprite["rect"].size * 4.0
		and boss_sprite["rect"].get_center() == regular_sprite["rect"].get_center(),
		"спрайт босса вчетверо больше спрайта того же существа",
	)
	var boss_overheads: Array = _entities.mob_overheads([boss], "", 1000)
	_check(
		boss_overheads.size() == 1 and boss_overheads[0]["bar_size"] == Vector2(64.0, 5.0),
		"полоска HP босса соответствует увеличенному спрайту",
	)
	var labels: Array = _entities.corpse_overheads(corpses, 7, Rect2(0, 0, 1000, 1000))
	_check(labels.size() == 1 and labels[0]["anchor"] == Vector2(300.0, 180.0) and labels[0]["selected"], "подпись трупа над маркером")
	var dying: Dictionary = mobs[0].duplicate()
	dying["hp"] = 0.0
	dying["state"] = "dead"
	_entities._sync_mobs([mobs[0]], 1000)
	_entities._sync_mobs([dying], 1200)
	var death_sprite: Dictionary = _entities._mob_sprite(dying, 1200)
	_check(not death_sprite.is_empty() and is_equal_approx(float(death_sprite["alpha"]), 1.0) and float(death_sprite["rotation"]) == 0.0, "смерть моба: лист смерти без поворота")
	var fallback: Dictionary = _entities._death_sprite({"died_at": 0.0}, {"death": null, "walk": VIEW._npc_sheets("imp_vanilla")["walk"], "attack": null}, Vector2(50, 50), 0.0, 250)
	_check(is_equal_approx(float(fallback["rotation"]), -deg_to_rad(45.0)) and fallback["rect"] == Rect2(42, 42, 16, 16), "труп без листа смерти падает на 45° против часовой")
	_check(_entities._death_sprite({"died_at": 0.0}, {"death": null, "walk": null, "attack": null}, Vector2.ZERO, 0.0, 0).is_empty(), "без кадров труп не рисуется")
	_check(_entities._death_sprite({"died_at": 0.0}, {"death": [], "walk": null, "attack": null}, Vector2.ZERO, 0.0, 0).is_empty(), "пустой лист смерти не даёт кадра")
	_check(_entities._death_sprite({"died_at": 0.0}, {"death": null, "walk": null, "attack": null}, Vector2.ZERO, 0.0, 45000).is_empty(), "труп исчезает через 45 с")
	var swinging: Dictionary = mobs[0].duplicate()
	swinging["id"] = "m3"
	swinging["windup"] = 0.4
	swinging["windup_total"] = 0.8
	var swing_overheads: Array = _entities.mob_overheads([swinging], "", 1000)
	_check(swing_overheads.size() == 1 and swing_overheads[0]["anchor"] == Vector2(100.0, 112.0), "полоска ХП у моба в замахе на том же месте")
	var calls := [0]
	var extra_calls: Array = []
	var probe_extra := {"base_y": 5000.0, "draw": func(canvas: CanvasItem) -> void: extra_calls.append(canvas)}
	var steps := [
		{"now": 1000, "mobs": [mobs[0], swinging], "player": player, "moving": true, "anim": 1.0},
		{"now": 1100, "mobs": [mobs[0], swinging], "player": _with(player, {"hp": 50.0, "windup": 0.3, "windup_total": 0.6}), "moving": false, "anim": 1.1},
		{"now": 1200, "mobs": [dying], "player": _with(player, {"hp": 0.0}), "moving": false, "anim": 1.2},
		{"now": 1700, "mobs": [dying], "player": _with(player, {"hp": 0.0}), "moving": false, "anim": 1.7},
		{"now": 50000, "mobs": [dying], "player": _with(player, {"hp": 0.0}), "moving": false, "anim": 2.0},
	]
	var probe := Probe.new()
	probe.callback = func(canvas: CanvasItem) -> void:
		var step: Dictionary = steps[calls[0]]
		calls[0] += 1
		_entities.draw_actors(canvas, step["mobs"], animals, step["player"], "sw", step["anim"], step["moving"], "m1", step["now"])
		_entities.draw_actors(canvas, [], [], step["player"], "sw", step["anim"], step["moving"], "m1", step["now"], [probe_extra])
		_entities.draw_mobs(canvas, step["mobs"], "m1", step["now"])
		_entities.draw_animals(canvas, [{"id": 2, "key": "animal_duck_water", "x": 70.0, "y": 80.0, "facing": 1.5, "moving": false}], step["now"])
		_entities.draw_player(canvas, step["player"], "w", step["anim"], step["moving"])
		_entities.draw_corpses(canvas, corpses, 7, Rect2(0, 0, 1000, 1000))
		_entities.draw_crystals(canvas, crystals, [10, 11], step["now"])
		_entities.draw_harvest_progress(canvas, harvest, Vector2(100, 100), 0.28)
		_entities.draw_click_effect(canvas, Vector2(120, 120), 0.2)
	add_child(probe)
	for _step in steps:
		probe.queue_redraw()
		await get_tree().process_frame
	probe.queue_free()
	_draw_calls = calls[0]
	_check(_draw_calls == steps.size(), "блок отрисовки выполнился на всех кадрах")
	_check(extra_calls.size() == steps.size() and extra_calls[0] is CanvasItem, "draw_actors рисует дополнительный элемент на каждом кадре с канвой")


func _with(source: Dictionary, changes: Dictionary) -> Dictionary:
	var result := source.duplicate()
	result.merge(changes, true)
	return result


func _same_visible_pixels(loaded: Image, source_cell: Image) -> bool:
	if loaded == null or loaded.get_size() != source_cell.get_size():
		return false
	for y in source_cell.get_height():
		for x in source_cell.get_width():
			var original := source_cell.get_pixel(x, y)
			var actual := loaded.get_pixel(x, y)
			# Импорт Godot меняет RGB только у полностью прозрачной кромки.
			if original.a != actual.a or (original.a != 0 and original != actual):
				return false
	return true
