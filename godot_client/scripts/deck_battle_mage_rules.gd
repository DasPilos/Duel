extends RefCounted

# Режим мага боя Калоды: порт deck/scenes/mage_battle_scene.py (макет стола и заголовок).
# Макет выбирается по профессии игрока (fighter.type снимка), как сцена мага в deck/scenes/world_flow.py:62.
# Колоды мага на клиенте не строятся: их присылает сервер. Флаг mage_mode боя снимок не содержит, для макета он не нужен.

const CHARACTER_RULES := preload("res://scripts/deck_character_rules.gd")

const TITLE_TEXT := "МАГИЧЕСКАЯ ДУЭЛЬ"  # mage_battle_scene.py: draw
const TITLE_FONT_SIZE := 20  # mage_battle_scene.py: SysFont("arial", 20)
const TITLE_COLOR := Color8(190, 140, 240)  # mage_battle_scene.py: (190, 140, 240)

# mage_battle_scene.py:_configure_mage_layout. Кнопка «играть карты» не нужна: кнопки боя стоят внизу экрана.
const LAYOUT := {
	"card_table": Rect2(20, 170, 1880, 520),
	"enemy_hand": Rect2(410, 20, 1100, 130),
	"enemy_selected": Rect2(390, 245, 1140, 120),
	"player_selected": Rect2(390, 520, 1140, 120),
	"player_hand": Rect2(300, 850, 1320, 180),
	"discard": Rect2(75, 285, 170, 300),
	"deck": Rect2(1675, 285, 170, 300),
	"turn_bar": Rect2(810, 715, 300, 18),
}

static func is_mage(state: Dictionary) -> bool:
	var fighter: Variant = state.get("fighter", {})
	if not fighter is Dictionary:
		return false
	var profession := str((fighter as Dictionary).get("type", ""))
	return CHARACTER_RULES.normalize_profession_type(profession) == "mage"


# Заголовок скрыт на экране результата (mage_battle_scene.py: фазы result и result_transition).
static func title_visible(phase: String) -> bool:
	return phase != "result"
