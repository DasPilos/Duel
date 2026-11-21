extends RefCounted

const ENDPOINT := "/map/editor/test-world"
const TIMEOUT_SECONDS := 30.0
const ADMIN_ONLY_TEXT := "Создавать миры может только админ"
const MODE_ONLY_TEXT := "тестовый мир создаётся только в режиме Колоды"
const NETWORK_TEXT := "Нет ответа от сервера. Проверьте подключение и адрес."
const EMPTY_RESPONSE_TEXT := "Сервер вернул пустой или неверный JSON-ответ."


static func build_payload(saved_id: int, name: String, test := true) -> Dictionary:
	return {"saved_id": saved_id, "name": name.strip_edges(), "test": test}


static func can_create(role: String) -> bool:
	return role == "admin"


# Маршрут создания тестового мира есть только в API Колоды (deck/server/main.py).
static func can_create_in_mode(mode: String) -> bool:
	return mode == "deck"


static func result_message(result: int, response_code: int, parsed: Variant) -> String:
	if result != HTTPRequest.RESULT_SUCCESS:
		return error_message(NETWORK_TEXT)
	if response_code < 200 or response_code >= 300:
		var text := "Ошибка сервера (%d)." % response_code
		if parsed is Dictionary and parsed.has("error"):
			text = str(parsed["error"])
		return error_message(text)
	if not parsed is Dictionary:
		return error_message(EMPTY_RESPONSE_TEXT)
	return success_message(parsed)


static func success_message(response: Dictionary) -> String:
	var world_status: Dictionary = response.get("status", {})
	var kind := "Тестовый мир" if bool(response.get("test", true)) else "Мир"
	var address := ""
	if not str(world_status.get("server_url", "")).is_empty():
		address = " Адрес сервера мира: %s." % str(world_status["server_url"])
	var serving := " Этот сервер обслуживает мир." if bool(world_status.get("served_here", false)) else " Сервер мира запускается отдельно."
	return "%s «%s» создан, ID %d.%s%s" % [
		kind, str(response.get("name", "")), int(response.get("world_id", 0)), address, serving,
	]


static func error_message(text: String) -> String:
	return "Тестовый мир не создан: %s" % text
