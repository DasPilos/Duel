extends Node

const MODES := {
	"economy": {
		"name": "Economy",
		"summary": "Экономический режим. Правила мира определяет сервер.",
		"module_ready": true,
		"scene_path": "res://scenes/economy_world.tscn",
	},
	"deck": {
		"name": "Deck",
		"summary": "Карточный режим. Правила и результаты определяет сервер.",
		"module_ready": true,
		"scene_path": "res://scenes/deck_world.tscn",
	},
	"front_line": {
		"name": "Front Line",
		"summary": "Совместная оборона карты Front Line от волн мобов.",
		"module_ready": true,
		"scene_path": "res://scenes/world_entry.tscn",
	},
}


func describe(mode_key: String) -> Dictionary:
	var mode: Dictionary = MODES.get(mode_key, {})
	if mode.is_empty():
		return {
			"key": mode_key,
			"name": mode_key if not mode_key.is_empty() else "Неизвестный режим",
			"summary": "Для этого режима ещё не подключён игровой модуль клиента.",
			"module_ready": false,
			"scene_path": "",
		}
	var result := mode.duplicate(true)
	result["key"] = mode_key
	return result
