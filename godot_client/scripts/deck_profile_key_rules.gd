extends RefCounted

# Клавиша I в мире Колоды, как DeckWorld.handle_event в deck/scenes/world_flow.py: открытый рюкзак закрывается,
# на карте, в таверне и в комнате переключает карточку персонажа. Чат с фокусом ввода, бой, задний двор и
# прочие экраны клавишу не принимают. Чистая логика без сцены.

const NONE := ""
const TOGGLE := "toggle"
const CLOSE_BACKPACK := "close_backpack"
const VIEW_INVENTORY := "inventory"
const PROFILE_VIEWS := ["home", "tavern", "character_room"]
const PROFILE_LOCATIONS := ["world_map", "tavern", "character_room"]


static func action_for(view: String, location: String, typing: bool, has_character: bool) -> String:
	if view == VIEW_INVENTORY:
		return CLOSE_BACKPACK
	if typing or not has_character:
		return NONE
	if view in PROFILE_VIEWS and location in PROFILE_LOCATIONS:
		return TOGGLE
	return NONE
