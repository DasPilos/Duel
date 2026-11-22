extends SceneTree

# Проверка правила проходимости по слоям: верхний видимый слой, в котором есть клетка, решает проходимость.

const LAYER_RULES = preload("res://scripts/layer_rules.gd")

var _failures := 0


func _init() -> void:
	_check(LAYER_RULES.default_passable("tile"), "слой тайлов по умолчанию проходим")
	_check(not LAYER_RULES.default_passable("object"), "слой объектов по умолчанию непроходим")
	_check(LAYER_RULES.affects_passability("animal"), "животные подчиняются флагу слоя")
	_check(LAYER_RULES.affects_passability("decorative"), "декор подчиняется флагу слоя")
	_check(not LAYER_RULES.affects_passability("group"), "группа не имеет клеток")
	_check(LAYER_RULES.default_passable("mob"), "слой мобов по умолчанию проходим")
	_check(LAYER_RULES.is_passable({"type": "tile"}), "старый слой без флага получает значение по типу")
	_check(not LAYER_RULES.is_passable({"type": "object"}), "старый слой объектов без флага непроходим")

	var water := {"type": "tile", "passable": false, "cells": {"1:1": "water", "2:1": "water"}}
	var bridge := {"type": "tile", "passable": true, "cells": {"2:1": "bridge"}}
	var blocked := LAYER_RULES.blocked_cells([water, bridge])
	_check(blocked.has("1:1"), "вода без моста непроходима")
	_check(not blocked.has("2:1"), "мост на воде проходим (верхний слой)")

	var shore := {"type": "tile", "passable": true, "cells": {"1:1": "shore"}}
	_check(not LAYER_RULES.blocked_cells([water, shore]).has("1:1"), "берег поверх воды делает клетку проходимой")

	var tree := {"type": "object", "passable": false, "cells": {"0:0": "tree"}}
	var land := {"type": "tile", "passable": true, "cells": {"0:0": "grass"}}
	_check(LAYER_RULES.blocked_cells([land, tree]).has("0:0"), "объект на траве непроходим")

	var animal := {"type": "animal", "passable": false, "cells": {"3:3": "deer"}}
	_check(LAYER_RULES.blocked_cells([animal]).has("3:3"), "непроходимый слой животных блокирует клетку")
	var animal_pass := {"type": "animal", "cells": {"3:3": "deer"}}
	_check(LAYER_RULES.blocked_cells([animal_pass]).is_empty(), "проходимый по умолчанию слой животных не блокирует")

	var empty_cell_check := LAYER_RULES.blocked_cells([water])
	_check(not empty_cell_check.has("5:5"), "пустая клетка проходима")

	print("layer passability checks failures=%d" % _failures)
	quit(_failures)


func _check(condition: bool, message: String) -> void:
	if not condition:
		_failures += 1
		print("FAIL: %s" % message)
