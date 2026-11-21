extends Node

# Три независимых канала: основной (как раньше), мир (синхронизация состояния) и команды игрока.
# Занятость одного канала не блокирует остальные: синхронизация не ждёт чат, карточку или покупку.
signal request_completed(success: bool, payload: Variant)
signal world_request_completed(success: bool, payload: Variant)
signal command_completed(success: bool, payload: Variant)

const CLIENT_VERSION := "1.0.0"
const EDITOR_VERSION := "1.0.0"
const PROTOCOL_VERSION := 1

var base_url := "http://127.0.0.1:8765"
var token := ""
var _http: HTTPRequest
var _busy := false
var _world_http: HTTPRequest
var _world_busy := false
var _command_http: HTTPRequest
var _command_busy := false
var _command_queue: Array = []


func _ready() -> void:
	_http = _make_channel(_on_request_completed)
	_world_http = _make_channel(_on_world_request_completed)
	_command_http = _make_channel(_on_command_request_completed)


func _make_channel(callback: Callable) -> HTTPRequest:
	var channel := HTTPRequest.new()
	channel.timeout = 10.0
	add_child(channel)
	channel.request_completed.connect(callback)
	return channel


func set_server_url(url: String) -> bool:
	var normalized := url.strip_edges().trim_suffix("/")
	if not normalized.begins_with("http://") and not normalized.begins_with("https://"):
		return false
	base_url = normalized
	return true


func request_json(method: HTTPClient.Method, path: String, payload: Dictionary = {}, authenticated := true) -> bool:
	if _busy:
		request_completed.emit(false, "Запрос уже выполняется. Подождите.")
		return false
	var error_text := _start(_http, method, path, payload, authenticated)
	if error_text.is_empty():
		_busy = true
		return true
	request_completed.emit(false, error_text)
	return false


# Синхронизация мира: свой канал. Пока он занят, новый снимок не посылается (ответ придёт раньше).
func request_world_json(method: HTTPClient.Method, path: String, payload: Dictionary = {}) -> bool:
	if _world_busy:
		return false
	var error_text := _start(_world_http, method, path, payload, true)
	if error_text.is_empty():
		_world_busy = true
		return true
	world_request_completed.emit(false, error_text)
	return false


# Приказ игрока: очередь команд на своём канале, уходит сразу и не ждёт синхронизации мира.
func request_command(path: String, payload: Dictionary) -> void:
	_command_queue.append({"path": path, "payload": payload})
	_pump_commands()


func _pump_commands() -> void:
	if _command_busy or _command_queue.is_empty():
		return
	var item: Dictionary = _command_queue.pop_front()
	var error_text := _start(_command_http, HTTPClient.METHOD_POST, str(item["path"]), item["payload"], true)
	if error_text.is_empty():
		_command_busy = true
		return
	command_completed.emit(false, error_text)
	_pump_commands()


# Пустая строка — запрос начат; иначе текст ошибки для игрока.
func _start(channel: HTTPRequest, method: HTTPClient.Method, path: String, payload: Dictionary, authenticated: bool) -> String:
	if not path.begins_with("/"):
		return "Путь API должен начинаться с /."
	var headers := PackedStringArray(["Content-Type: application/json"])
	if authenticated:
		if token.is_empty():
			return "Сначала войдите в аккаунт."
		headers.append("Authorization: Bearer " + token)
	var body := ""
	if method != HTTPClient.METHOD_GET and not payload.is_empty():
		body = JSON.stringify(payload)
	var error := channel.request(base_url + path, headers, method, body)
	if error != OK:
		return "Не удалось начать запрос: " + error_string(error)
	return ""


# Ответ сервера: [успех, данные или текст ошибки].
func _parse_result(result: int, response_code: int, body: PackedByteArray) -> Array:
	if result != HTTPRequest.RESULT_SUCCESS:
		return [false, "Нет ответа от сервера. Проверьте подключение и адрес."]
	var parsed: Variant = JSON.parse_string(body.get_string_from_utf8())
	if response_code < 200 or response_code >= 300:
		var message := "Ошибка сервера (%d)." % response_code
		if parsed is Dictionary and parsed.has("error"):
			message = str(parsed["error"])
		return [false, message]
	if parsed == null:
		return [false, "Сервер вернул пустой или неверный JSON-ответ."]
	return [true, parsed]


func _on_request_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	_busy = false
	var outcome: Array = _parse_result(result, response_code, body)
	request_completed.emit(bool(outcome[0]), outcome[1])


func _on_world_request_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	_world_busy = false
	var outcome: Array = _parse_result(result, response_code, body)
	world_request_completed.emit(bool(outcome[0]), outcome[1])


func _on_command_request_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	_command_busy = false
	var outcome: Array = _parse_result(result, response_code, body)
	command_completed.emit(bool(outcome[0]), outcome[1])
	_pump_commands()
