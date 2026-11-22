extends RefCounted

const TILE := "tile"
const DECORATIVE := "decorative"
const ANIMAL := "animal"
const MOB := "mob"
const GROUP := "group"
const OBJECT := "object"

# Слой 20 и выше имеют самый яркий оттенок.
const GRADIENT_LAYERS := 20
const TILE_DARK := Color8(20, 58, 28)
const TILE_BRIGHT := Color8(104, 244, 88)
const OBJECT_DARK := Color8(18, 46, 122)
const OBJECT_BRIGHT := Color8(150, 206, 255)
const ANIMAL_DARK := Color8(204, 186, 0)
const ANIMAL_BRIGHT := Color8(255, 246, 118)
const MOB_DARK := Color8(170, 26, 26)
const MOB_BRIGHT := Color8(255, 118, 118)
const GROUP_COLOR := Color8(62, 74, 98)
const DARK_TEXT := Color8(12, 20, 12)
const LIGHT_TEXT := Color8(244, 246, 244)


# Номер слоя = место среди слоёв, рисуемых на холсте, снизу вверх. Группы ничего не рисуют и номера не имеют.
static func numbers(layers: Array) -> Dictionary:
	var result := {}
	var next_number := 1
	for layer in layers:
		var layer_id := int(layer.get("id", 0))
		if str(layer.get("type", "")) == GROUP:
			result[layer_id] = 0
			continue
		result[layer_id] = next_number
		next_number += 1
	return result


static func number_of(layers: Array, layer_id: int) -> int:
	return int(numbers(layers).get(layer_id, 0))


static func layer_color(layer_type: String, number: int) -> Color:
	if layer_type == GROUP:
		return GROUP_COLOR
	var progress := clampf(float(number - 1) / float(GRADIENT_LAYERS - 1), 0.0, 1.0)
	if layer_type in [TILE, DECORATIVE]:
		return TILE_DARK.lerp(TILE_BRIGHT, progress)
	if layer_type == ANIMAL:
		return ANIMAL_DARK.lerp(ANIMAL_BRIGHT, progress)
	if layer_type == MOB:
		return MOB_DARK.lerp(MOB_BRIGHT, progress)
	return OBJECT_DARK.lerp(OBJECT_BRIGHT, progress)


static func text_color(background: Color) -> Color:
	var luminance := background.r * 0.299 + background.g * 0.587 + background.b * 0.114
	return DARK_TEXT if luminance > 0.52 else LIGHT_TEXT


# Слои тайлов всегда лежат под слоями объектов, животных и мобов.
# Группы остаются на своих местах, переставляются только рисуемые слои.
static func normalize_order(layers: Array) -> bool:
	var slots: Array[int] = []
	var tiles: Array[Dictionary] = []
	var others: Array[Dictionary] = []
	for index in range(layers.size()):
		var layer: Dictionary = layers[index]
		var layer_type := str(layer.get("type", ""))
		if layer_type == GROUP:
			continue
		slots.append(index)
		if layer_type in [TILE, DECORATIVE]:
			tiles.append(layer)
		else:
			others.append(layer)
	var ordered: Array[Dictionary] = []
	ordered.append_array(tiles)
	ordered.append_array(others)
	var changed := false
	for position in range(slots.size()):
		if int(layers[slots[position]].get("id", 0)) != int(ordered[position].get("id", 0)):
			changed = true
	if changed:
		for position in range(slots.size()):
			layers[slots[position]] = ordered[position]
	return changed


# Новый слой тайлов ложится поверх верхнего слоя тайлов, остальные — на самый верх.
static func insert_index(layers: Array, layer_type: String) -> int:
	if layer_type not in [TILE, DECORATIVE]:
		return layers.size()
	var last_tile := -1
	for index in range(layers.size()):
		if str(layers[index].get("type", "")) in [TILE, DECORATIVE]:
			last_tile = index
	return last_tile + 1


# Проходимость задаёт флаг слоя, его выставляет художник. Действует на все слои, кроме групп (у них нет клеток).
# По умолчанию непроходимы только слои объектов; тайлы, животные, мобы и декор проходимы.
static func affects_passability(layer_type: String) -> bool:
	return layer_type != GROUP


static func default_passable(layer_type: String) -> bool:
	return layer_type != OBJECT


static func is_passable(layer: Dictionary) -> bool:
	return bool(layer.get("passable", default_passable(str(layer.get("type", "")))))


# Заблокированные клетки (ключ "x:y") по слоям, переданным снизу вверх. Верхний слой, в котором есть клетка,
# решает проходимость. Пустые клетки проходимы. Вызывающий передаёт только видимые слои.
static func blocked_cells(layers: Array) -> Dictionary:
	var blocked := {}
	for layer in layers:
		if not affects_passability(str(layer.get("type", ""))):
			continue
		var passable := is_passable(layer)
		for coord in layer.get("cells", {}):
			if passable:
				blocked.erase(coord)
			else:
				blocked[coord] = true
	return blocked
