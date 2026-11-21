extends Node

const RULES := preload("res://scripts/deck_class_card_rules.gd")
const CHARACTER_RULES := preload("res://scripts/deck_character_rules.gd")
const CARD_SCRIPT := preload("res://scripts/deck_character_card.gd")
const SAMPLES_PATH := "res://tests/deck_character_samples.json"
const ASSETS_ROOT := "E:/python/game/assets"
const MISSING_ROOT := "E:/python/game/no_such_assets"
const CLASSES := ["warrior", "archer", "assassin", "mage", "necromancer"]
const ART_CLASSES := ["warrior", "archer", "assassin", "mage"]
const EXPECTED_TITLES := {
	"warrior": "ВОИН",
	"archer": "ЛУЧНИК",
	"assassin": "АСАСИН",
	"mage": "МАГ",
	"necromancer": "НЕКРОМАНТ",
}
const EXPECTED_FILES := {
	"warrior": "warrior.png",
	"archer": "archer.png",
	"assassin": "assassin.png",
	"mage": "mage.png",
	"necromancer": "",
}
const EXPECTED_OFFSETS := {"warrior": -20, "archer": 10, "assassin": 0, "mage": -10, "necromancer": 0}
# Ширина после подгонки под высоту базовой фигуры (856 px): round(ширина * 856 / высота), как в fit_figure_to.
const EXPECTED_FIT_WIDTHS := {"warrior": 617, "archer": 420, "assassin": 555, "mage": 435}

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var samples: Variant = JSON.parse_string(FileAccess.get_file_as_string(SAMPLES_PATH))
	if samples is Dictionary:
		_check_rules()
		await _check_card(samples["profiles"])
	else:
		_check(false, "файл эталона читается")
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_class_card_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_rules() -> void:
	_check(RULES.CLASS_INFO.size() == CLASSES.size(), "карта классов покрывает все пять классов")
	for profession in CLASSES:
		_check(RULES.class_title(profession) == EXPECTED_TITLES[profession], "подпись класса: %s" % profession)
		_check(RULES.class_sprite_file(profession) == EXPECTED_FILES[profession], "файл спрайта класса: %s" % profession)
		_check(RULES.sprite_offset_x(profession) == EXPECTED_OFFSETS[profession], "сдвиг фигуры класса: %s" % profession)
	for legacy in ["battle_mage", "support_mage", "harmonist"]:
		_check(RULES.class_title(legacy) == "МАГ" and RULES.class_sprite_file(legacy) == "mage.png", "устаревший маг сводится к mage: %s" % legacy)
	for unknown in ["dragon", ""]:
		_check(RULES.class_title(unknown).is_empty(), "неизвестный класс без подписи: '%s'" % unknown)
		_check(RULES.class_sprite_file(unknown).is_empty() and RULES.sprite_offset_x(unknown) == 0, "неизвестный класс без спрайта: '%s'" % unknown)
		_check(RULES.class_art_path(ASSETS_ROOT, unknown).is_empty(), "неизвестный класс без пути к файлу: '%s'" % unknown)
	_check(RULES.class_art_path("", "warrior").is_empty(), "без корня ассетов пути нет")
	_check(RULES.class_art_path(ASSETS_ROOT, "necromancer").is_empty(), "у некроманта спрайта нет")
	_check(RULES.default_assets_root("E:/python/game/godot_client") == ASSETS_ROOT, "ассеты лежат рядом с godot_client")
	for profession in ART_CLASSES:
		var path := RULES.class_art_path(ASSETS_ROOT, profession)
		_check(path == ASSETS_ROOT + "/classes/" + EXPECTED_FILES[profession], "путь к спрайту: %s" % profession)
		_check(FileAccess.file_exists(path), "файл спрайта существует: %s" % profession)
	_check(FileAccess.file_exists(RULES.base_figure_path(ASSETS_ROOT)), "базовая фигура существует")
	_check(RULES.fitted_figure_size(Rect2i(0, 0, 449, 623), Rect2i(0, 0, 315, 856)) == Vector2i(617, 856), "подгонка ширины по высоте эталона")
	_check(RULES.fitted_figure_size(Rect2i(), Rect2i(0, 0, 315, 856)) == Vector2i.ZERO, "пустая фигура не подгоняется")
	_check_figure_rect()
	_check_fit_against_python()


func _check_figure_rect() -> void:
	var grid := Vector2(298, 178)
	var canvas := Vector2(1024, 1024)
	var ratio := 178.0 / 406.0
	var warrior := RULES.figure_rect(grid, canvas, -20)
	_check(absf(warrior.get_center().x - (149.0 - 20.0 * ratio)) < 0.01, "сдвиг фигуры по X масштабируется вместе с куклой")
	_check(absf(warrior.get_center().y - (89.0 - 23.0 * ratio)) < 0.01, "центр фигуры на 23 px (Python) выше центра сетки")
	_check(absf(warrior.size.y * 856.0 / 1024.0 - 410.88 * ratio) < 0.01, "высота фигуры относительно сетки как в Python")
	_check(absf(RULES.figure_rect(grid, canvas, 0).get_center().x - 149.0) < 0.01, "без сдвига фигура по центру сетки")


func _check_fit_against_python() -> void:
	var reference := Image.load_from_file(RULES.base_figure_path(ASSETS_ROOT))
	_check(reference != null and not reference.is_empty(), "базовый спрайт читается")
	if reference == null or reference.is_empty():
		return
	reference.convert(Image.FORMAT_RGBA8)
	var reference_box := reference.get_used_rect()
	_check(reference_box == Rect2i(348, 95, 315, 856), "границы базовой фигуры совпадают с pygame")
	# Границы, которые pygame (get_bounding_rect) находит в тех же PNG из assets/classes.
	var python_boxes := {
		"warrior": Rect2i(57, 67, 449, 623),
		"archer": Rect2i(183, 58, 275, 560),
		"assassin": Rect2i(124, 55, 366, 564),
		"mage": Rect2i(187, 64, 327, 643),
	}
	for profession in ART_CLASSES:
		var source := Image.load_from_file(RULES.class_art_path(ASSETS_ROOT, profession))
		_check(source != null and not source.is_empty(), "спрайт читается: %s" % profession)
		if source == null or source.is_empty():
			continue
		source.convert(Image.FORMAT_RGBA8)
		_check(source.get_used_rect() == python_boxes[profession], "границы фигуры совпадают с pygame: %s" % profession)
		_check(RULES.fitted_figure_size(source.get_used_rect(), reference_box) == Vector2i(EXPECTED_FIT_WIDTHS[profession], 856), "ширина подгонки как в Python: %s" % profession)
		var fitted := RULES.fit_figure(source, reference.get_size(), reference_box)
		_check(fitted.get_size() == Vector2i(1024, 1024), "холст совпадает с базовым спрайтом: %s" % profession)
		var figure_box := fitted.get_used_rect()
		_check(figure_box.size.y >= 800 and figure_box.size.y <= 860, "фигура подогнана по высоте эталона: %s" % profession)
		_check(absi(figure_box.position.x + floori(figure_box.size.x / 2.0) - 505) <= 12, "фигура по центру эталона: %s" % profession)


func _check_card(profiles: Dictionary) -> void:
	var card = CARD_SCRIPT.new()
	add_child(card)
	await get_tree().process_frame
	var base: Dictionary = profiles["warrior"]["input"]
	card.set_profile(_profile(base, "warrior"), "ИГРОК", Color8(80, 180, 120), true, null)
	await get_tree().process_frame
	await get_tree().process_frame
	var figure_texture: Texture2D = card._figure.texture
	_check(card._figure.visible and figure_texture != null, "кукла рисует базовую фигуру")
	_check(figure_texture != null and figure_texture.get_size() == Vector2(1024, 1024), "базовая фигура в полном холсте, как в Python")
	for profession in CLASSES:
		card.set_profile(_profile(base, profession), "ИГРОК", Color8(80, 180, 120), true, null)
		await get_tree().process_frame
		_check(card._figure.texture == figure_texture, "базовая фигура одна для всех классов: %s" % profession)
		_check(is_equal_approx(_slot_alpha(card), CARD_SCRIPT.SLOT_ALPHA), "слоты полупрозрачны всегда, как в Python: %s" % profession)
		_check(not _has_text(card, EXPECTED_TITLES[profession]), "подписи класса на карточке нет: %s" % profession)

	card.set_profile(_profile(base, "dragon"), "ИГРОК", Color8(80, 180, 120), true, null)
	await get_tree().process_frame
	_check(card._figure.texture == figure_texture and is_equal_approx(_slot_alpha(card), CARD_SCRIPT.SLOT_ALPHA), "неизвестный класс: вид тот же")

	card.set_assets_root(MISSING_ROOT)
	await get_tree().process_frame
	_check(card._figure.texture == null and not card._figure.visible, "нет файлов ассетов: фигуры нет, карточка не падает")
	card.set_assets_root("")
	await get_tree().process_frame
	_check(card._figure.visible and card._figure.texture != null, "путь по умолчанию снова даёт фигуру")
	_check(card._resolved_assets_root() == RULES.default_assets_root(ProjectSettings.globalize_path("res://")), "карточка ищет ассеты рядом с проектом")

	card.set_profile(_profile(base, "warrior"), "ИГРОК", Color8(80, 180, 120), true, null)
	await get_tree().process_frame
	await get_tree().process_frame
	var grid_size: Vector2 = card._paperdoll_grid.get_combined_minimum_size()
	var ratio := grid_size.y / 406.0
	var figure_center: Vector2 = card._figure.position + card._figure.size / 2.0
	_check(grid_size.y > 100.0, "сетка слотов имеет высоту")
	_check(card._paperdoll.custom_minimum_size == grid_size, "куклу резервирует сетка слотов")
	_check(absf(figure_center.x - grid_size.x / 2.0) < 0.5, "базовая фигура по центру куклы без сдвига")
	_check(absf(figure_center.y - (grid_size.y / 2.0 - 23.0 * ratio)) < 0.5, "фигура поднята относительно сетки как в Python")
	_check(absf(card._figure.size.y * 856.0 / 1024.0 - grid_size.y * 410.88 / 406.0) < 0.5, "высота фигуры относительно сетки как в Python")
	var xp_rect: Rect2 = card._xp_label.get_global_rect()
	var row_rect: Rect2 = card._xp_label.get_parent().get_global_rect()
	_check(absf(xp_rect.end.x - row_rect.end.x) < 1.0, "XP остаётся справа в строке уровня")
	_check(card._level_label.text == "Уровень 5" and card._xp_label.text == "XP: 120/350", "уровень и XP не изменились")

	card.queue_free()
	await get_tree().process_frame


func _has_text(node: Node, text: String) -> bool:
	if node is Label and (node as Label).text == text:
		return true
	for child in node.get_children():
		if _has_text(child, text):
			return true
	return false


func _profile(base: Dictionary, profession: String) -> Dictionary:
	var raw: Dictionary = base.duplicate(true)
	raw["type"] = profession
	raw["profession_type"] = profession
	return CHARACTER_RULES.normalize_profile(raw, "ИГРОК", "player")


func _slot_alpha(card) -> float:
	return card._slot_styles[0].bg_color.a


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append("FAIL: " + label)
