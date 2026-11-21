extends Node

signal connection_lost(seconds_remaining: int)
signal countdown_updated(seconds_remaining: int)
signal connection_restored(character: Dictionary)
signal client_outdated
signal session_invalid(message: String)
signal connection_expired
signal status_received(status: Dictionary)

const POLL_SECONDS := 1.0
const FAILURES_BEFORE_OFFLINE := 2
const GRACE_SECONDS := 10

var base_url := ""
var token := ""
var character_id := 0
var build_id := ""
var is_active := false

var _request: HTTPRequest
var _poll_timer: Timer
var _request_in_flight := false
var _request_stage := ""
var _failures := 0
var _offline_deadline_msec := 0
var _offline := false
var _outdated := false
var _generation := 0
var _request_generation := 0


func _ready() -> void:
	_request = HTTPRequest.new()
	_request.timeout = POLL_SECONDS
	add_child(_request)
	_request.request_completed.connect(_on_request_completed)

	_poll_timer = Timer.new()
	_poll_timer.wait_time = POLL_SECONDS
	_poll_timer.timeout.connect(_on_poll_timeout)
	add_child(_poll_timer)


func start(server_url: String, auth_token: String, selected_character_id: int) -> void:
	stop()
	_generation += 1
	base_url = server_url.trim_suffix("/")
	token = auth_token
	character_id = selected_character_id
	build_id = ""
	_failures = 0
	_offline = false
	_outdated = false
	is_active = true
	_poll_timer.start()
	_poll_server()


func stop() -> void:
	is_active = false
	_generation += 1
	_poll_timer.stop()
	_failures = 0
	_offline = false
	_outdated = false


func _on_poll_timeout() -> void:
	if not is_active or _outdated:
		return
	if _offline:
		var remaining := _remaining_seconds()
		if remaining <= 0:
			is_active = false
			connection_expired.emit()
			return
		countdown_updated.emit(remaining)
	if not _request_in_flight:
		_poll_server()


func _poll_server() -> void:
	if not is_active or _request_in_flight:
		return
	_send_request("/api/server/status", "status")


func _send_request(path: String, stage: String) -> void:
	_request_stage = stage
	_request_generation = _generation
	_request_in_flight = true
	var headers := PackedStringArray([
		"Content-Type: application/json",
		"Authorization: Bearer " + token,
	])
	var error := _request.request(base_url + path, headers, HTTPClient.METHOD_GET)
	if error != OK:
		_request_in_flight = false
		_request_stage = ""
		_handle_unavailable()


func _on_request_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	var stage := _request_stage
	var request_generation := _request_generation
	_request_in_flight = false
	_request_stage = ""
	if not is_active or request_generation != _generation:
		return
	if result != HTTPRequest.RESULT_SUCCESS:
		_handle_unavailable()
		return
	if response_code == 401:
		session_invalid.emit("Сессия на сервере завершилась. Войдите в аккаунт снова.")
		stop()
		return
	if response_code < 200 or response_code >= 300:
		if response_code >= 500:
			_handle_unavailable()
		return

	var parsed: Variant = JSON.parse_string(body.get_string_from_utf8())
	if not parsed is Dictionary:
		_handle_unavailable()
		return

	if stage == "status":
		_handle_status(parsed)
	elif stage == "resync":
		_handle_resync(parsed)


func _handle_status(status: Dictionary) -> void:
	_failures = 0
	status_received.emit(status)
	var current_build := str(status.get("build_id", ""))
	if not current_build.is_empty():
		if build_id.is_empty():
			build_id = current_build
		elif current_build != build_id:
			_outdated = true
			is_active = false
			_poll_timer.stop()
			client_outdated.emit()
			return

	if _offline:
		_send_request("/api/characters/%d" % character_id, "resync")


func _handle_resync(response: Dictionary) -> void:
	var character: Variant = response.get("character")
	if not character is Dictionary:
		_handle_unavailable()
		return
	_offline = false
	_offline_deadline_msec = 0
	connection_restored.emit(character)


func _handle_unavailable() -> void:
	_failures += 1
	if not _offline and _failures >= FAILURES_BEFORE_OFFLINE:
		_offline = true
		_offline_deadline_msec = Time.get_ticks_msec() + GRACE_SECONDS * 1000
		connection_lost.emit(GRACE_SECONDS)


func _remaining_seconds() -> int:
	var milliseconds_left := _offline_deadline_msec - Time.get_ticks_msec()
	if milliseconds_left <= 0:
		return 0
	return int(ceil(float(milliseconds_left) / 1000.0))
