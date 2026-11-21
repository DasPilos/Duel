extends RefCounted

# Раскладка и данные заднего двора из deck/ui/renderers/backyard.py, deck/scenes/backyard_scene.py и deck/ui/chat/panel.py.
# Координаты — пиксели Python при 1920×1080; вид рисует их в тех же единицах (масштаб 2/3 внутри окна 1280×720).

const DESIGN_SIZE := Vector2(1920.0, 1080.0)
const TAVERN_BUTTON := Rect2(1640.0, 35.0, 220.0, 45.0)
const INVENTORY_BUTTON := Rect2(1850.0, 10.0, 50.0, 50.0)
const APPLICATION_FRAME := Rect2(560.0, 40.0, 800.0, 560.0)
const DUEL_LIST := Rect2(585.0, 115.0, 750.0, 145.0)
const GROUP_LIST := Rect2(585.0, 365.0, 750.0, 200.0)
const DUEL_BUTTON := Rect2(560.0, 620.0, 220.0, 40.0)
const GROUP_BUTTON := Rect2(800.0, 620.0, 220.0, 40.0)
const ACCEPT_BUTTON := Rect2(1040.0, 620.0, 220.0, 40.0)
const TITLE_POS := Vector2(585.0, 60.0)
const GROUP_LABEL_POS := Vector2(585.0, 305.0)
const ERROR_POS := Vector2(600.0, 690.0)
const TIMER_TOP := 665.0
const ROW_STEP := 42.0
const ROW_HEIGHT := 34.0
const ROW_PADDING := 12.0
const ROW_TEXT_TOP := 8.0
const NEW_OFFER_SECONDS := 30.0
const DEFAULT_TTL := 120
const GROUP_SLOTS := 10
const EMPTY_TEXT := "Активных заявок пока нет"
const DUEL_HINT := "Нажмите для просмотра"
const GROUP_HINT := "Нажмите для участия"
const DUEL_TITLE := "ОДИН НА ОДИН"
const GROUP_TITLE := "СТЕНКА НА СТЕНКУ"
const TAVERN_TEXT := "В ТАВЕРНУ"
const DUEL_TEXT := "ОДИН НА ОДИН"
const CANCEL_DUEL_TEXT := "ОТОЗВАТЬ ЗАЯВКУ"
const GROUP_TEXT := "Стенка на стенку"
const CANCEL_GROUP_TEXT := "Отменить сбор"
const ACCEPT_TEXT := "ПРИНЯТЬ ЗАЯВКУ"
const DUEL_GUARD := "Сначала отмените сбор стенка на стенку"
const GROUP_GUARD := "Сначала отмените заявку один на один"
const NO_INCOMING_TEXT := "Нет заявок для принятия"
const LEVEL_LOCKED_TEXT := "Уровень в этом окне не меняется."
const ROW_ACTION_COMPARE := "Сравнить"
const ROW_ACTION_ACCEPT := "Принять"
const ROW_ACTION_DECLINE := "Отклонить"
const CHALLENGE_TEXT := "Вызвать"
const AFK_CHALLENGE_TEXT := "ДУЭЛЬ"
const CHAT_CHANNELS := ["Общий", "Личные"]
const CHAT_ROOM_TITLE := "ЗАДНИЙ ДВОР"
const CHAT_SEND_TEXT := "ОТПРАВИТЬ"
const CHAT_TOGGLE_TEXT := "СВЕРНУТЬ"
const CHAT_COLLAPSED_TEXT := "ЧАТ"
const CHAT_PANEL := Rect2(451.0, 790.0, 1018.0, 285.0)
const CHAT_CONTENT_TOP := 58.0
const CHAT_INPUT_BOTTOM_GAP := 35.0
const CHAT_CONTENT_BOTTOM_GAP := 10.0
const CHAT_DIVIDER_WIDTH := 8.0
const CHAT_DIVIDER_GAP := 8.0
const CHAT_PEOPLE_WIDTH := 150.0
const CHAT_MIN_CHAT_WIDTH := 300.0
const CHAT_MIN_PEOPLE_WIDTH := 150.0
const CHAT_TEXT_LEFT := 12.0
const CHAT_INPUT_LEFT := 5.0
const CHAT_SEND_WIDTH := 70.0
const CHAT_FIELD_GAP := 4.0
const CHAT_CHANNEL_SIZE := Vector2(70.0, 25.0)
const CHAT_CHANNEL_STEP := 75.0
const CHAT_TOGGLE_SIZE := Vector2(70.0, 25.0)
const CHAT_COLLAPSED_SIZE := Vector2(70.0, 25.0)
const CHAT_LINE_HEIGHT := 20.0
const CHAT_LINE_GAP := 4.0
const CHAT_PEOPLE_ROW_HEIGHT := 28.0
const CHAT_PEOPLE_TEXT_LEFT := 10.0
const CHAT_PEOPLE_BUTTON_SIZE := Vector2(58.0, 23.0)
const CHAT_PEOPLE_BUTTON_RIGHT := 69.0
const GOLD_PREFIX := "[ИГРОК] "


static func clamp_divider(divider_x: float) -> float:
	var minimum_x := CHAT_PANEL.position.x + CHAT_TEXT_LEFT + CHAT_MIN_CHAT_WIDTH + CHAT_DIVIDER_GAP
	var maximum_x := CHAT_PANEL.end.x - CHAT_DIVIDER_GAP - CHAT_MIN_PEOPLE_WIDTH - CHAT_DIVIDER_GAP - CHAT_DIVIDER_WIDTH
	return clampf(float(int(divider_x)), minimum_x, maximum_x)


static func default_divider_x() -> float:
	return CHAT_PANEL.end.x - CHAT_PEOPLE_WIDTH - CHAT_DIVIDER_GAP * 2.0 - CHAT_DIVIDER_WIDTH


static func chat_layout(divider_x: float, send_width := CHAT_SEND_WIDTH) -> Dictionary:
	var panel := CHAT_PANEL
	var content_y := panel.position.y + CHAT_CONTENT_TOP
	var input_y := panel.end.y - CHAT_INPUT_BOTTOM_GAP
	var content_height := maxf(80.0, input_y - content_y - CHAT_CONTENT_BOTTOM_GAP)
	var divider := Rect2(clamp_divider(divider_x), content_y, CHAT_DIVIDER_WIDTH, content_height)
	var people_x := divider.end.x + CHAT_DIVIDER_GAP
	var message_right := divider.position.x - CHAT_DIVIDER_GAP
	var message_x := panel.position.x + CHAT_TEXT_LEFT
	var input := Rect2(panel.position.x + CHAT_INPUT_LEFT, input_y, message_right - panel.position.x - CHAT_INPUT_LEFT, 25.0)
	var send := Rect2(input.end.x - send_width, input.position.y, send_width, input.size.y)
	var field := Rect2(input.position.x, input.position.y, send.position.x - CHAT_FIELD_GAP - input.position.x, input.size.y)
	var channels: Array = []
	for index in CHAT_CHANNELS.size():
		channels.append(Rect2(panel.position.x + CHAT_TEXT_LEFT + index * CHAT_CHANNEL_STEP, panel.position.y + 10.0, CHAT_CHANNEL_SIZE.x, CHAT_CHANNEL_SIZE.y))
	return {
		"panel": panel,
		"divider": divider,
		"people": Rect2(people_x, content_y, panel.end.x - CHAT_DIVIDER_GAP - people_x, content_height),
		"messages": Rect2(message_x, content_y, message_right - message_x, content_height),
		"field": field,
		"send": send,
		"toggle": Rect2(panel.end.x - 80.0, panel.end.y - 30.0, CHAT_TOGGLE_SIZE.x, CHAT_TOGGLE_SIZE.y),
		"room_pos": Vector2(people_x, panel.position.y + 14.0),
		"channels": channels,
	}


static func collapsed_toggle_rect() -> Rect2:
	return Rect2(DESIGN_SIZE.x - 80.0, DESIGN_SIZE.y - 25.0, CHAT_COLLAPSED_SIZE.x, CHAT_COLLAPSED_SIZE.y)


static func seconds_left(created_at: float, ttl: float, now: float) -> int:
	return maxi(0, int(created_at + ttl - now))


static func countdown_text(seconds: int) -> String:
	return "%d:%02d" % [seconds / 60, seconds % 60]


static func active_application(application: Variant, now: float) -> Dictionary:
	if not application is Dictionary or application.is_empty():
		return {}
	var offer: Dictionary = application
	if str(offer.get("status", "")) != "pending":
		return {}
	var ttl := float(offer.get("ttl", DEFAULT_TTL))
	if now >= float(offer.get("created_at", 0.0)) + ttl:
		return {}
	return offer


static func application_timer_text(application: Dictionary, now: float) -> String:
	if application.is_empty():
		return ""
	var left := seconds_left(float(application.get("created_at", now)), float(application.get("ttl", DEFAULT_TTL)), now)
	return "Заявка активна: %s" % countdown_text(left)


static func group_timer_text(group: Dictionary, now: float) -> String:
	if group.is_empty():
		return ""
	var left := seconds_left(float(group.get("created_at", now)), float(group.get("ttl", DEFAULT_TTL)), now)
	return "Сбор активен: %s" % countdown_text(left)


static func duel_button_title(my_application: Dictionary) -> String:
	return CANCEL_DUEL_TEXT if not my_application.is_empty() else DUEL_TEXT


static func group_button_title(own_group: Dictionary) -> String:
	return CANCEL_GROUP_TEXT if not own_group.is_empty() else GROUP_TEXT


static func id_text(value: Variant) -> String:
	if value is float and is_equal_approx(value, roundf(value)):
		return str(int(value))
	return str(value)


static func is_own_offer(offer: Dictionary, own_id: String) -> bool:
	return id_text(offer.get("sender_id", "")) == own_id


static func own_group(offers: Array, own_id: String) -> Dictionary:
	for offer in offers:
		if not offer is Dictionary:
			continue
		var participants: Variant = offer.get("participants", [])
		if not participants is Array:
			continue
		for participant in participants:
			if participant is Dictionary and id_text(participant.get("id", "")) == own_id:
				return offer
	return {}



static func is_new_offer(offer: Dictionary, now: float) -> bool:
	return now - float(offer.get("created_at", 0.0)) <= NEW_OFFER_SECONDS


static func duel_offers(offers: Array, my_application: Dictionary, own_id: String, own_name: String) -> Array:
	var result: Array = []
	var seen := {}
	for offer in offers:
		if not offer is Dictionary:
			continue
		var offer_id := str(offer.get("id", ""))
		if seen.has(offer_id):
			continue
		seen[offer_id] = true
		result.append(offer.duplicate(true))
	if not my_application.is_empty() and not seen.has(str(my_application.get("id", ""))):
		var own := my_application.duplicate(true)
		own["sender_id"] = own_id
		own["sender"] = own_name
		result.append(own)
	result.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return float(a.get("created_at", 0.0)) > float(b.get("created_at", 0.0)))
	return result


static func duel_label(offer: Dictionary, own_id: String, now: float) -> Dictionary:
	var own := is_own_offer(offer, own_id)
	var fresh := is_new_offer(offer, now)
	var text := str(offer.get("sender", offer.get("sender_name", "Игрок")))
	if own:
		text += " (ваша заявка)"
	elif fresh:
		text += " (новая)"
	return {"text": text, "highlight": own or fresh}


static func group_label(offer: Dictionary) -> String:
	var participants: Variant = offer.get("participants", [])
	var count: int = participants.size() if participants is Array else 0
	return "%s (%d/%d)" % [str(offer.get("sender", "Группа")), count, GROUP_SLOTS]


static func incoming_offer(selected_id: String, duel_offers_list: Array, my_application: Dictionary, own_id: String) -> Dictionary:
	if selected_id.is_empty() or my_application.is_empty():
		return {}
	for offer in duel_offers_list:
		if offer is Dictionary and str(offer.get("id", "")) == selected_id \
				and not is_own_offer(offer, own_id) and id_text(offer.get("target_id", "")) == own_id:
			return offer
	return {}


static func visible_messages(messages: Array) -> Array:
	var result: Array = []
	for message in messages:
		if message is Dictionary and message.get("recipient_id") == null:
			result.append(message)
	return result


static func message_parts(message: Dictionary, own_id: String) -> Dictionary:
	var text := str(message.get("text", ""))
	var time := str(message.get("time_text", ""))
	var time_prefix := "[%s] " % time if not time.is_empty() else ""
	if text.begins_with(GOLD_PREFIX):
		return {"time": time_prefix, "body": text, "gold": true, "own": false}
	var own := id_text(message.get("sender_id", "")) == own_id
	var sender := "Вы" if own else str(message.get("sender", "Персонаж"))
	return {"time": time_prefix, "body": "%s: %s" % [sender, text], "gold": false, "own": own}


static func people_rows(occupants: Array, own_id: String) -> Array:
	var rows: Array = []
	for occupant in occupants:
		if not occupant is Dictionary:
			continue
		var afk := bool(occupant.get("afk", false))
		var display := str(occupant.get("name", ""))
		var character_id := id_text(occupant.get("character_id", ""))
		rows.append({
			"character_id": character_id,
			"label": display + (" (АФК)" if afk else ""),
			"afk": afk,
			"self": character_id == own_id,
		})
	return rows


static func text_width(font: Font, text: String, font_size: int) -> float:
	return font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x


static func fit_text(font: Font, text: String, font_size: int, max_width: float) -> String:
	if max_width <= 0.0:
		return ""
	if text_width(font, text, font_size) <= max_width:
		return text
	var shortened := text
	while not shortened.is_empty() and text_width(font, shortened + "…", font_size) > max_width:
		shortened = shortened.substr(0, shortened.length() - 1)
	return shortened + "…" if not shortened.is_empty() else ""


static func wrap_text(font: Font, text: String, font_size: int, first_width: float, rest_width: float) -> Array:
	var lines: Array = []
	var current := ""
	var limit := first_width
	for word in text.split(" ", false):
		var candidate := word if current.is_empty() else current + " " + word
		if current.is_empty() or text_width(font, candidate, font_size) <= limit:
			current = candidate
			continue
		lines.append(current)
		limit = rest_width
		current = word
	if not current.is_empty() or lines.is_empty():
		lines.append(current)
	return lines


static func clamp_scroll(scroll: int, item_count: int, visible_count: int) -> int:
	return clampi(scroll, 0, maxi(0, item_count - visible_count))


static func visible_count(height: float, step: float) -> int:
	return maxi(1, int(height / step))


static func row_index_at(local_y: float, scroll: int, step: float, row_height: float) -> int:
	if local_y < 0.0:
		return -1
	var slot := int(local_y / step)
	if local_y - slot * step > row_height:
		return -1
	return slot + scroll


static func scrollbar_thumb(track: Rect2, item_count: int, visible: int, scroll: int) -> Rect2:
	var thumb_height := maxf(20.0, floorf(track.size.y * visible / item_count))
	var travel := track.size.y - thumb_height
	var thumb_y := track.position.y + floorf(travel * scroll / maxf(1.0, float(item_count - visible)))
	return Rect2(track.position.x, thumb_y, track.size.x, thumb_height)


static func message_max_scroll(total_height: float, view_height: float) -> float:
	return maxf(0.0, total_height - view_height + 8.0)
