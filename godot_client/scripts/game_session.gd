extends Node

var hub_url := "http://127.0.0.1:8765"
var token := ""
var world_token := ""
var user: Dictionary = {}
var world: Dictionary = {}
var character: Dictionary = {}
var world_snapshot: Dictionary = {}
var map_editor_setup: Dictionary = {}
var pending_map_gate := ""
var pending_city_gate := ""


func authenticate(server_url: String, auth_token: String, user_data: Dictionary) -> void:
	hub_url = server_url
	token = auth_token
	world_token = ""
	user = user_data.duplicate(true)


func select_world(world_data: Dictionary) -> void:
	world = world_data.duplicate(true)
	world_token = ""


func select_character(character_data: Dictionary) -> void:
	character = character_data.duplicate(true)


func update_world_snapshot(snapshot: Dictionary) -> void:
	world_snapshot = snapshot.duplicate(true)


func clear_character() -> void:
	character.clear()
	world_snapshot.clear()
	world_token = ""


# Выход из мира в лобби: мир тоже сбрасывается, иначе лобби при открытии подключит его снова.
func leave_world() -> void:
	clear_character()
	world.clear()


# Ворота, через которые герой ушёл из города на карту мира; карта читает их при входе и сбрасывает.
func take_pending_map_gate() -> String:
	var gate := pending_map_gate
	pending_map_gate = ""
	return gate


# Вход в город при возврате с карты мира; город читает его при запуске и сбрасывает.
func take_pending_city_gate() -> String:
	var gate := pending_city_gate
	pending_city_gate = ""
	return gate


func clear() -> void:
	token = ""
	world_token = ""
	user.clear()
	world.clear()
	character.clear()
	world_snapshot.clear()
	map_editor_setup.clear()
	pending_map_gate = ""
	pending_city_gate = ""
