extends RefCounted

# Правила комнаты персонажа Колоды: порт deck/scenes/character_room.py. Вкладки, подписи, порядок слотов и строки
# взяты из Python. Сетевых запросов здесь нет: мир запрашивает разделы и передаёт ответы сюда для разбора.

const CHARACTER_RULES := preload("res://scripts/deck_character_rules.gd")
const LOBBY_FORMAT := preload("res://scripts/lobby_format.gd")

const TAB_EQUIPMENT := "equipment"
const TAB_CHESTS := "chests"
const TAB_DECKS := "decks"
const TAB_ORDER := [TAB_EQUIPMENT, TAB_CHESTS, TAB_DECKS]
const TAB_TITLES := {"equipment": "Экипировка", "chests": "Сундуки", "decks": "Колоды"}

# Раздел — отдельный запрос к серверу. Вкладка «Сундуки» показывает два раздела.
const SECTION_EQUIPMENT := "equipment"
const SECTION_CHEST1 := "chest1"
const SECTION_CHEST2 := "chest2"
const SECTION_DECKS := "decks"
const ACTION_PREFIX := "room_"

const STATE_IDLE := ""
const STATE_LOADING := "loading"
const STATE_READY := "ready"
const STATE_FAILED := "failed"

const TITLE_TEXT := "КОМНАТА ПЕРСОНАЖА"
const TAVERN_TEXT := "Вернуться в таверну"
const CARD_TOOLTIP := "Карточка персонажа"
const EQUIPMENT_TITLE := "ЭКИПИРОВКА"
const CHESTS_TITLE := "СУНДУКИ"
const DECKS_TITLE := "КОЛОДЫ"
const CHEST_TITLES := {"chest1": "СУНДУК 1 (КАРТЫ)", "chest2": "СУНДУК 2 (МАТЕРИАЛЫ)"}
const EQUIPMENT_EMPTY_TEXT := "Экипировка пуста"
const EMPTY_SLOT_TEXT := "[Пусто]"
const CHEST_EMPTY_TEXT := "Сундук пуст."
const DECKS_EMPTY_TEXT := "Колоды не найдены"
const LOADING_TEXT := "Загрузка…"
const FAILED_TEXT := "Не удалось загрузить данные."
const DEFAULT_ITEM_NAME := "Предмет"


static func is_tab(tab: String) -> bool:
	return TAB_TITLES.has(tab)


static func sections_for_tab(tab: String) -> Array:
	if tab == TAB_EQUIPMENT:
		return [SECTION_EQUIPMENT]
	if tab == TAB_CHESTS:
		return [SECTION_CHEST1, SECTION_CHEST2]
	if tab == TAB_DECKS:
		return [SECTION_DECKS]
	return []


static func section_action(section: String) -> String:
	return ACTION_PREFIX + section


static func section_from_action(action: String) -> String:
	return action.trim_prefix(ACTION_PREFIX)


static func section_path(section: String, character_id: int) -> String:
	if section == SECTION_EQUIPMENT:
		return "/api/equipment/%d" % character_id
	if section == SECTION_CHEST1 or section == SECTION_CHEST2:
		return "/api/storage/%d/%s" % [character_id, section]
	if section == SECTION_DECKS:
		return "/api/deck/decks/%d" % character_id
	return ""


# Раздел запрашивают, если его ещё не было или прошлый запрос не удался.
static func needs_load(state: String) -> bool:
	return state == STATE_IDLE or state == STATE_FAILED


# Данные раздела из ответа сервера; null, если ответ не похож на ожидаемый.
static func section_payload(section: String, payload: Variant) -> Variant:
	if not payload is Dictionary:
		return null
	if section == SECTION_EQUIPMENT:
		return payload.get("equipment") if payload.get("equipment") is Dictionary else null
	if section == SECTION_DECKS:
		return payload.get("decks") if payload.get("decks") is Array else null
	if section == SECTION_CHEST1 or section == SECTION_CHEST2:
		return payload.get("storage") if payload.get("storage") is Array else null
	return null


static func character_line(character: Dictionary) -> String:
	return "Персонаж: %s (Уровень %d) | Монеты: %d" % [
		str(character.get("name", "Персонаж")),
		int(character.get("level", 1)),
		int(character.get("coins", 0)),
	]


static func chest_title(section: String) -> String:
	return str(CHEST_TITLES.get(section, section))


# Строки экипировки в порядке слотов Python; пустой слот выводится как «[Пусто]».
static func equipment_rows(equipment: Dictionary) -> Array:
	var rows: Array = []
	for slot_info in CHARACTER_RULES.SLOT_LAYOUT:
		var item: Variant = equipment.get(str(slot_info[0]))
		var label := str(slot_info[1])
		if item is Dictionary:
			rows.append({
				"label": label,
				"name": item_title(item),
				"bonuses": bonus_text(item.get("bonuses")),
				"empty": false,
			})
		else:
			rows.append({"label": label, "name": EMPTY_SLOT_TEXT, "bonuses": "", "empty": true})
	return rows


static func item_title(item: Dictionary) -> String:
	return "%s (%s)" % [str(item.get("name", DEFAULT_ITEM_NAME)), str(item.get("rarity", "common"))]


# Бонусы в порядке предмета, как в Python: «+2 Сила, +1 Интуиция».
static func bonus_text(bonuses: Variant) -> String:
	if not bonuses is Dictionary:
		return ""
	var values := bonuses as Dictionary
	var parts := PackedStringArray()
	for key in values:
		var stat := str(CHARACTER_RULES.EQUIPMENT_LABELS.get(str(key), str(key)))
		parts.append("+%s %s" % [_whole_text(values[key]), stat])
	return ", ".join(parts)


# JSON отдаёт все числа как float: 2.0 выводим как «2», как в Python.
static func _whole_text(value: Variant) -> String:
	if value is float and is_equal_approx(value, roundf(value)):
		return str(int(value))
	return str(value)


# Все предметы сундука: «Название ×количество». Список прокручивается, поэтому строк не ограничиваем.
static func storage_lines(items: Array) -> Array:
	var lines: Array = []
	for item in items:
		if item is Dictionary:
			lines.append("%s ×%d" % [str(item.get("name", DEFAULT_ITEM_NAME)), int(item.get("quantity", 1))])
	return lines


static func deck_title(deck: Dictionary, index: int) -> String:
	return str(deck.get("name", "Колода %d" % (index + 1)))


# Дата последнего изменения колоды; updated_at есть в каждом ответе сервера.
static func deck_info_text(deck: Dictionary) -> String:
	return "Карт: %d | Последнее обновление: %s" % [card_count(deck), timestamp_text(deck.get("updated_at"))]


# Как len(deck["cards"]) в Python: число разных карт в колоде.
static func card_count(deck: Dictionary) -> int:
	var cards: Variant = deck.get("cards", {})
	if cards is Dictionary:
		return (cards as Dictionary).size()
	if cards is Array:
		return (cards as Array).size()
	return 0


# Сервер отдаёт unix-время; Python выводит сырое число, здесь показываем дату и время, как в лобби.
static func timestamp_text(value: Variant) -> String:
	if LOBBY_FORMAT.is_timestamp(value):
		return LOBBY_FORMAT.local_datetime_text(float(value))
	return "N/A"
