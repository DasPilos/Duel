extends "res://scripts/economy_city_map.gd"
# Городская карта, которая стартует у входа, через который герой вернулся с карты мира (CityScene(session, gate=...) в main.py).


func start_at_gate(gate_id: String) -> void:
	var spawn := GATE_RULES.city_spawn(gate_id)
	var spawn_point: Vector2 = spawn["position"]
	_player = spawn_point
	_direction = str(spawn["direction"])
	queue_redraw()
