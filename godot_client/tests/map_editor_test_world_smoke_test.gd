extends Node

const TEST_WORLD_RULES = preload("res://scripts/map_editor_test_world_rules.gd")


class TestWorldEditor extends "res://scripts/map_editor.gd":
	var save_count := 0
	var post_count := 0
	var posted_path := ""
	var posted_payload: Dictionary = {}

	func _ready() -> void:
		_mode = "deck"
		_api_prefix = "/api/deck"
		_build_ui()

	func _save_map() -> void:
		save_count += 1
		_pending_action = "save_map"

	func _post_test_world(path: String, payload: Dictionary) -> bool:
		post_count += 1
		posted_path = path
		posted_payload = payload
		_set_status("Создаём тестовый мир…")
		return true


var editor: TestWorldEditor
var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _run() -> void:
	var saved_user: Dictionary = GameSession.user.duplicate(true)
	editor = TestWorldEditor.new()
	editor.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(editor)
	await get_tree().process_frame
	editor._map_width.value = 16
	editor._map_height.value = 16
	_check_rules()
	_check_button()
	_check_role_and_guards()
	_check_save_then_create()
	_check_responses()
	GameSession.user = saved_user
	_finish()


func _finish() -> void:
	if is_instance_valid(editor):
		editor.free()
	for failure in _failures:
		push_error(failure)
	if _failures.is_empty():
		print("map_editor_test_world_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(0 if _failures.is_empty() else 1)


func _check_rules() -> void:
	_check(
		TEST_WORLD_RULES.build_payload(12, "  Тест  ") == {"saved_id": 12, "name": "Тест", "test": true},
		"Тело запроса как в Python: saved_id, name и test=true по умолчанию",
	)
	_check(
		TEST_WORLD_RULES.can_create("admin") and not TEST_WORLD_RULES.can_create("moderator") and not TEST_WORLD_RULES.can_create(""),
		"Создавать тестовый мир может только админ",
	)
	_check(
		TEST_WORLD_RULES.can_create_in_mode("deck") and not TEST_WORLD_RULES.can_create_in_mode("economy") and not TEST_WORLD_RULES.can_create_in_mode(""),
		"Тестовый мир создаётся только в режиме Колоды: маршрута в других API нет",
	)
	var served := {
		"world_id": 5, "name": "Тест", "mode": "economy", "test": true,
		"status": {"world_id": 5, "server_url": "http://127.0.0.1:8766", "served_here": false},
	}
	_check(
		TEST_WORLD_RULES.result_message(HTTPRequest.RESULT_SUCCESS, 200, served)
		== "Тестовый мир «Тест» создан, ID 5. Адрес сервера мира: http://127.0.0.1:8766. Сервер мира запускается отдельно.",
		"Успех: название, ID и адрес мира в сообщении",
	)
	served["status"]["served_here"] = true
	_check(
		TEST_WORLD_RULES.result_message(HTTPRequest.RESULT_SUCCESS, 200, served).ends_with("Этот сервер обслуживает мир."),
		"Если мир обслуживает этот сервер, сообщение говорит об этом",
	)
	_check(
		TEST_WORLD_RULES.result_message(HTTPRequest.RESULT_SUCCESS, 403, {"error": "Создавать миры может только админ"})
		== "Тестовый мир не создан: Создавать миры может только админ",
		"Ошибка сервера показывается текстом сервера",
	)
	_check(
		TEST_WORLD_RULES.result_message(HTTPRequest.RESULT_CANT_CONNECT, 0, null)
		== "Тестовый мир не создан: Нет ответа от сервера. Проверьте подключение и адрес.",
		"Нет связи с сервером: понятное сообщение",
	)
	_check(
		TEST_WORLD_RULES.result_message(HTTPRequest.RESULT_SUCCESS, 500, null) == "Тестовый мир не создан: Ошибка сервера (500).",
		"Ошибка без текста показывает код ответа",
	)
	_check(
		TEST_WORLD_RULES.result_message(HTTPRequest.RESULT_SUCCESS, 200, null)
		== "Тестовый мир не создан: Сервер вернул пустой или неверный JSON-ответ.",
		"Пустой ответ 200 считается ошибкой формата",
	)
	_check(TEST_WORLD_RULES.TIMEOUT_SECONDS == 30.0, "Таймаут не меньше 30 секунд, как у клиента Python")


func _check_button() -> void:
	_check(editor._test_world_button != null and editor._test_world_button.text == "Тестовый мир", "Кнопка «Тестовый мир» есть на панели редактора")


func _check_role_and_guards() -> void:
	editor._create_default_layers()
	editor._render_layers()
	GameSession.user = {"role": "moderator"}
	editor._map_name.text = "Тест"
	editor._create_test_world()
	_check(
		editor._status.text == "Тестовый мир не создан: Создавать миры может только админ" and editor.save_count == 0,
		"Модератор получает ответ о правах и карта не сохраняется",
	)
	GameSession.user = {"role": "admin"}
	editor._layers[0]["cells"]["1:1"] = editor._encode_atlas_cell("res://assets/base_tails/tile.png", Vector2i(0, 0))
	editor._create_test_world()
	_check(
		editor._status.text == "Тестовый мир не создан: карта содержит локальные тайлы листов, животных или мобов" and editor.save_count == 0,
		"Локальные тайлы не отправляются в тестовый мир",
	)
	editor._layers[0]["cells"].erase("1:1")
	editor._map_name.text = "   "
	editor._create_test_world()
	_check(editor._status.text == "Тестовый мир не создан: введите название карты" and editor.save_count == 0, "Без названия мир не создаётся")
	editor._map_name.text = "Тест"
	editor._test_world_request = HTTPRequest.new()
	editor.add_child(editor._test_world_request)
	editor._create_test_world()
	_check(editor._status.text == "Тестовый мир уже создаётся. Подождите." and editor.save_count == 0, "Повторный клик не запускает второй запрос")
	editor._finish_test_world_request()
	_check(editor._test_world_request == null, "Завершённый запрос очищается")


func _check_save_then_create() -> void:
	editor._map_name.text = "Тест"
	editor._create_test_world()
	_check(editor.save_count == 1 and editor._test_world_after_save and editor.post_count == 0, "Тестовый мир сначала сохраняет карту на сервере")
	editor._on_api_completed(true, {"saved_id": 77})
	_check(editor._saved_id == 77 and editor.post_count == 1 and not editor._test_world_after_save, "После сохранения запрос уходит с новым saved_id")
	_check(editor.posted_path == "/api/deck/map/editor/test-world", "Адрес запроса: префикс Колоды плюс эндпоинт тестового мира")
	_check(editor.posted_payload == {"saved_id": 77, "name": "Тест", "test": true}, "Тело запроса совпадает с Python: saved_id, name, test")
	editor._create_test_world()
	editor._on_api_completed(false, "Клетка (1, 1) уже занята")
	_check(
		editor._status.text == "Тестовый мир не создан: карта не сохранена на сервере: Клетка (1, 1) уже занята"
		and not editor._test_world_after_save and editor.post_count == 1,
		"Ошибка сохранения останавливает создание мира и показывает причину",
	)
	editor._mode = "economy"
	var saves_before: int = editor.save_count
	var posts_before: int = editor.post_count
	editor._create_test_world()
	_check(
		editor._status.text == "Тестовый мир не создан: тестовый мир создаётся только в режиме Колоды" and editor.save_count == saves_before and editor.post_count == posts_before,
		"В режиме Башни тестовый мир не создаётся: карта не сохраняется и запроса нет",
	)
	editor._mode = "deck"


func _check_responses() -> void:
	editor._test_world_request = null
	var success_body := JSON.stringify({
		"world_id": 9, "name": "Тест", "test": true,
		"status": {"server_url": "http://127.0.0.1:8766", "served_here": true},
	}).to_utf8_buffer()
	editor._on_test_world_completed(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), success_body)
	_check(
		editor._status.text.begins_with("Тестовый мир «Тест» создан, ID 9.") and editor._status.text.ends_with("Этот сервер обслуживает мир."),
		"Успешный ответ показывается в статусе: название, ID и адрес",
	)
	var error_body := JSON.stringify({"error": "Создавать миры может только админ"}).to_utf8_buffer()
	editor._on_test_world_completed(HTTPRequest.RESULT_SUCCESS, 403, PackedStringArray(), error_body)
	_check(editor._status.text == "Тестовый мир не создан: Создавать миры может только админ", "Ошибка сервера показывается в статусе текстом сервера")
	editor._on_test_world_completed(HTTPRequest.RESULT_CANT_CONNECT, 0, PackedStringArray(), PackedByteArray())
	_check(
		editor._status.text == "Тестовый мир не создан: Нет ответа от сервера. Проверьте подключение и адрес.",
		"Нет связи показывается в статусе",
	)
