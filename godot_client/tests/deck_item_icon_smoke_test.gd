extends Node

const RULES := preload("res://scripts/deck_item_icon_rules.gd")
const CARD_SCRIPT := preload("res://scripts/deck_character_card.gd")
const CHARACTER_RULES := preload("res://scripts/deck_character_rules.gd")
const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const SAMPLES_PATH := "res://tests/deck_character_samples.json"
const UNREACHABLE_URL := "http://127.0.0.1:9"
const MISSING_ROOT := "E:/python/game/no_such_assets"
const KNOWN_KEY := "right_hand_steel_sword"
const FIXTURE_ROOT := "user://deck_item_icon_smoke"
const FIXTURE_FILES := [
	"fighters/equipment/placeholders/zz_only_placeholder.png",
	"item_icons/zz_only_item.png",
	"fighters/equipment/placeholders/zz_both.png",
	"item_icons/zz_both.png",
]
const FIXTURE_DIRS := ["fighters/equipment/placeholders", "fighters/equipment", "fighters", "item_icons"]

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var samples: Variant = JSON.parse_string(FileAccess.get_file_as_string(SAMPLES_PATH))
	var root := RULES.default_assets_root(ProjectSettings.globalize_path("res://"))
	_make_fixtures()
	_check_key_validation()
	_check_paths(root)
	_check_textures(root)
	if samples is Dictionary:
		await _check_card(samples["profiles"]["warrior"]["input"], root)
		await _check_inventory_rows(samples["profiles"]["warrior"]["input"], root)
	else:
		_check(false, "файл эталона читается")
	_remove_fixtures()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_item_icon_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_key_validation() -> void:
	# Ожидаемые значения получены из ICON_KEY_RE в core/item_icons.py (Python re.match).
	var expected := {
		"weapon_iron_sword": true,
		"right_hand_steel_sword": true,
		"1start": true,
		"a".repeat(64): true,
		"a\n": true,
		"Weapon": false,
		"": false,
		"../secret": false,
		"_bad": false,
		"ab cd": false,
		"a".repeat(65): false,
	}
	for key in expected:
		_check(RULES.is_valid_key(str(key)) == expected[key], "ключ «%s» проверяется как в Python" % str(key).c_escape())


func _check_paths(root: String) -> void:
	var path := RULES.icon_path(root, KNOWN_KEY)
	_check(path.ends_with("/fighters/equipment/placeholders/%s.png" % KNOWN_KEY) and FileAccess.file_exists(path),
		"ключ ведёт к существующему PNG в слоях экипировки")
	_check(RULES.icon_path(root, "no_such_icon_xyz").is_empty(), "нет файла: путь пустой, без ошибки")
	_check(RULES.icon_path(root, "").is_empty(), "пустой ключ: путь пустой")
	_check(RULES.icon_path(root, "../fighters/equipment/placeholders/" + KNOWN_KEY).is_empty(), "переход по каталогам в ключе отклоняется")
	_check(RULES.icon_path("", KNOWN_KEY).is_empty(), "без папки ассетов путь пустой")
	_check(RULES.icon_path(MISSING_ROOT, KNOWN_KEY).is_empty() and RULES.icon_texture(MISSING_ROOT, KNOWN_KEY, 16) == null,
		"нет папки ассетов: текстуры нет, без ошибки")
	var fixture := ProjectSettings.globalize_path(FIXTURE_ROOT)
	_check(RULES.icon_path(fixture, "zz_only_placeholder").ends_with("/fighters/equipment/placeholders/zz_only_placeholder.png"),
		"файл только в слоях экипировки находится")
	_check(RULES.icon_path(fixture, "zz_only_item").ends_with("/item_icons/zz_only_item.png"),
		"файл только в item_icons находится")
	_check(RULES.icon_path(fixture, "zz_both").ends_with("/fighters/equipment/placeholders/zz_both.png"),
		"при двух файлах побеждает слой экипировки, как в Python")
	_check(RULES.icon_texture(fixture, "zz_only_item", 16) != null, "текстура берётся из item_icons")
	_check(RULES.icon_texture(fixture, "zz_missing", 16) == null, "отсутствующий файл: текстуры нет")
	_check(RULES.item_key({"name": "Шлем"}).is_empty() and RULES.item_key({"icon": null}).is_empty(),
		"предмет без icon или с null даёт пустой ключ")
	_check(RULES.item_key({"icon": KNOWN_KEY}) == KNOWN_KEY and RULES.item_key(null).is_empty(), "ключ берётся из поля icon")


func _check_textures(root: String) -> void:
	var texture := RULES.icon_texture(root, KNOWN_KEY, 16)
	_check(texture != null, "иконка меча загружается")
	if texture == null:
		return
	var source := Image.load_from_file(RULES.icon_path(root, KNOWN_KEY))
	_check(source != null, "PNG меча читается")
	if source != null:
		var expected := RULES.fitted_size(source.get_used_rect().size, 16)
		_check(Vector2i(texture.get_width(), texture.get_height()) == expected, "обрезка по прозрачности и вписывание как в Python")
	_check(maxi(texture.get_width(), texture.get_height()) == 13, "длинная сторона 13 px = 84 % от 16 px")
	_check(RULES.icon_texture(root, KNOWN_KEY, 16) == texture, "повторный запрос отдаёт ту же текстуру из кэша")
	var large := RULES.icon_texture(root, KNOWN_KEY, 32)
	_check(large != null and maxi(large.get_width(), large.get_height()) == 26 and large != texture,
		"другой размер даёт отдельную текстуру")
	_check(RULES.fitted_size(Vector2i(1024, 1024), 62) == Vector2i(52, 52), "квадрат 1024 px вписывается в 52 px, как в Python")
	_check(RULES.fitted_size(Vector2i(300, 600), 62) == Vector2i(26, 52), "прямоугольник сохраняет пропорции")
	_check(RULES.fitted_size(Vector2i.ZERO, 62) == Vector2i.ZERO and RULES.fitted_size(Vector2i(10, 10), 0) == Vector2i.ZERO,
		"пустые размеры не дают картинки")


func _check_card(warrior: Dictionary, root: String) -> void:
	var card = CARD_SCRIPT.new()
	add_child(card)
	await get_tree().process_frame
	var profile := CHARACTER_RULES.normalize_profile(warrior, "ИГРОК", "player")
	profile["equipment"] = {
		"weapon": {"name": "Меч", "icon": KNOWN_KEY},
		"head": {"name": "Шлем"},
		"body": {"name": "Доспех", "icon": "zz_no_such_icon"},
	}
	card.set_assets_root(root)
	card.set_profile(profile, "ИГРОК", Color8(80, 180, 120), true, null)
	var weapon: Dictionary = card._slot_cells["weapon"]
	_check(weapon["icon"].visible and weapon["icon"].texture != null, "слот оружия с иконкой показывает текстуру")
	_check(weapon["item"].text == "Меч", "слот оружия: название на месте")
	var head: Dictionary = card._slot_cells["head"]
	_check(not head["icon"].visible and head["icon"].texture == null, "предмет без icon: текстуры нет")
	_check(head["item"].text == "Шлем", "предмет без icon: название показано")
	var body: Dictionary = card._slot_cells["body"]
	_check(not body["icon"].visible and body["icon"].texture == null, "иконка без файла: текстуры нет, без ошибки")
	_check(body["item"].text == "Доспех", "иконка без файла: название на месте")
	var ears: Dictionary = card._slot_cells["ears"]
	_check(not ears["icon"].visible and ears["icon"].texture == null and ears["item"].text == "—", "пустой слот: текстуры нет")
	card.set_assets_root(MISSING_ROOT)
	_check(not weapon["icon"].visible and weapon["item"].text == "Меч", "нет папки ассетов: иконка скрыта, название на месте")
	card.set_assets_root(root)
	_check(weapon["icon"].visible, "папка снова доступна: иконка показана")
	profile["equipment"] = {}
	card.set_profile(profile, "ИГРОК", Color8(80, 180, 120), true, null)
	_check(not weapon["icon"].visible and weapon["item"].text == "—", "снятое оружие: иконка скрыта")
	card.queue_free()
	await get_tree().process_frame


func _check_inventory_rows(warrior: Dictionary, root: String) -> void:
	GameSession.clear()
	GameSession.hub_url = UNREACHABLE_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": UNREACHABLE_URL, "name": "Тест"}
	GameSession.character = warrior.duplicate(true)
	ApiClient._http.timeout = 0.5
	var deck = DECK_SCRIPT.new()
	deck.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(deck)
	deck._social_timer.stop()
	deck._battle_timer.stop()
	await _wait_idle(deck)

	deck._inventory_view = "backpack"
	deck._inventory_state = {
		"inventory": [
			{"slot_index": 0, "name": "Меч", "quantity": 1, "icon": KNOWN_KEY},
			{"slot_index": 1, "name": "Шлем", "quantity": 1},
			{"slot_index": 2, "name": "Зелье", "quantity": 2, "icon": "potion_red"},
			{"slot_index": 3, "name": "Пусто", "quantity": 1, "icon": "zz_no_such_icon"},
		],
		"carried_weight_kg": 3.5,
		"capacity": 50,
	}
	deck._render_inventory()
	var grid = deck._inventory_grid
	_check(grid.item_at(["bag", 0]).get("name") == "Меч" and grid.item_at(["bag", 3]).get("name") == "Пусто",
		"рюкзак: предметы лежат в ячейках сетки по slot_index")
	_check(_item_rows(deck._list).is_empty(), "рюкзак: список строк заменён сеткой")
	_check(_icon_of(grid.item_at(["bag", 0]), root) != null, "рюкзак: меч с иконкой в сетке")
	_check(_icon_of(grid.item_at(["bag", 1]), root) == null, "рюкзак: предмет без icon без картинки")
	_check(_icon_of(grid.item_at(["bag", 2]), root) != null, "рюкзак: зелье с иконкой из слоёв экипировки")
	_check(_icon_of(grid.item_at(["bag", 3]), root) == null, "рюкзак: нет файла, картинки нет")

	deck._inventory_view = "chest1"
	deck._storage_items = [
		{"id": 5, "name": "Свиток огня", "quantity": 1, "slot_index": 0, "icon": "scroll"},
		{"id": 6, "name": "Железная руда", "quantity": 3, "slot_index": 1, "icon": "material_iron_ore"},
		{"id": 7, "name": "Без иконки", "quantity": 1, "slot_index": 2},
	]
	deck._render_inventory()
	var rows := _item_rows(deck._list)
	_check(rows.size() == 3, "сундук: строка на каждый предмет")
	if rows.size() == 3:
		_check(rows[0]["icon"].visible and rows[1]["icon"].visible and not rows[2]["icon"].visible,
			"сундук: иконки там, где есть файл")
		_check(rows[1]["label"].text == "Железная руда ×3 · ячейка 2", "сундук: подпись строки прежняя")
	deck.queue_free()
	await get_tree().process_frame


func _item_rows(list: Node) -> Array:
	var rows: Array = []
	for child in list.get_children():
		if child is HBoxContainer and child.get_child_count() >= 2 and child.get_child(0) is TextureRect:
			rows.append({"icon": child.get_child(0), "label": child.get_child(1)})
	return rows


func _icon_of(item: Dictionary, root: String) -> Texture2D:
	return RULES.icon_texture(root, RULES.item_key(item), 62)


func _wait_idle(deck) -> void:
	var waited := 0
	while not deck._pending_action.is_empty() and waited < 240:
		await get_tree().process_frame
		waited += 1
	await get_tree().process_frame


func _make_fixtures() -> void:
	var root := ProjectSettings.globalize_path(FIXTURE_ROOT)
	for folder in FIXTURE_DIRS:
		DirAccess.make_dir_recursive_absolute(root.path_join(folder))
	_write_png(root.path_join("fighters/equipment/placeholders/zz_only_placeholder.png"), Color.RED)
	_write_png(root.path_join("item_icons/zz_only_item.png"), Color.BLUE)
	_write_png(root.path_join("fighters/equipment/placeholders/zz_both.png"), Color.RED)
	_write_png(root.path_join("item_icons/zz_both.png"), Color.BLUE)


func _remove_fixtures() -> void:
	var root := ProjectSettings.globalize_path(FIXTURE_ROOT)
	for file in FIXTURE_FILES:
		DirAccess.remove_absolute(root.path_join(file))
	for folder in FIXTURE_DIRS:
		DirAccess.remove_absolute(root.path_join(folder))
	DirAccess.remove_absolute(root)


func _write_png(path: String, color: Color) -> void:
	var image := Image.create_empty(4, 4, false, Image.FORMAT_RGBA8)
	image.fill(color)
	_check(image.save_png(path) == OK, "фикстура записана: %s" % path.get_file())


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)
