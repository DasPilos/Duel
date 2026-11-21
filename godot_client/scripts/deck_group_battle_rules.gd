extends RefCounted

# Правила «стенки на стенку»: заявки, таймеры и пары соперников.
# Пары повторяют deck/server/group_offers.py и _battle_start: соперник — enemy_team[own_index % len(enemy_team)].

const SIZE_OPTIONS := [6, 8, 10]
const SIZE_LABELS := ["6 участников", "8 участников", "10 участников"]
const TTL_OPTIONS := [120, 600, 1800]
const TTL_LABELS := ["2 минуты", "10 минут", "30 минут"]
const DEFAULT_MAX_PARTICIPANTS := 10
const CHOICE_REQUIRED := "Выберите количество участников и время сбора"


static func own_offer(offers: Array, character_id: int) -> Dictionary:
	for offer in offers:
		if offer is Dictionary and _participant_index(offer.get("participants", []), character_id) >= 0:
			return offer
	return {}


static func is_sender(offer: Dictionary, character_id: int) -> bool:
	return str(offer.get("sender_id", "")) == str(character_id)


static func max_participants_of(offer: Dictionary) -> int:
	return int(offer.get("max_participants", DEFAULT_MAX_PARTICIPANTS))


static func participant_count(offer: Dictionary) -> int:
	var participants: Variant = offer.get("participants", [])
	return participants.size() if participants is Array else 0


static func can_join(offer: Dictionary, character_id: int) -> bool:
	if str(offer.get("status", "")) != "waiting":
		return false
	if _participant_index(offer.get("participants", []), character_id) >= 0:
		return false
	return participant_count(offer) < max_participants_of(offer)


static func team_of(offer: Dictionary, character_id: int) -> int:
	var teams: Variant = offer.get("teams", [])
	if not (teams is Array):
		return -1
	var team_list: Array = teams
	for team_index in range(team_list.size()):
		if _participant_index(team_list[team_index], character_id) >= 0:
			return team_index
	return -1


static func opponent_of(offer: Dictionary, character_id: int) -> Dictionary:
	var teams: Variant = offer.get("teams", [])
	if not (teams is Array):
		return {}
	var team_list: Array = teams
	var own_team := team_of(offer, character_id)
	if own_team < 0 or team_list.size() != 2:
		return {}
	var enemy: Array = team_list[1 - own_team]
	if enemy.is_empty():
		return {}
	var own_index := _participant_index(team_list[own_team], character_id)
	var opponent: Variant = enemy[own_index % enemy.size()]
	return opponent if opponent is Dictionary else {}


static func start_available(offer: Dictionary, character_id: int) -> bool:
	return str(offer.get("status", "")) == "ready" and team_of(offer, character_id) >= 0


static func seconds_left(offer: Dictionary, now: float) -> int:
	var ends_at := float(offer.get("created_at", 0.0)) + float(offer.get("ttl", 0))
	return int(maxf(0.0, ends_at - now))


static func format_clock(seconds: int) -> String:
	return "%d:%02d" % [floori(seconds / 60.0), seconds % 60]


static func offer_title(offer: Dictionary) -> String:
	return "%s (%d/%d)" % [str(offer.get("sender", "Группа")), participant_count(offer), max_participants_of(offer)]


static func status_label(offer: Dictionary) -> String:
	match str(offer.get("status", "")):
		"waiting":
			return "набор участников"
		"ready":
			return "команды сформированы"
		"in_progress":
			return "бой идёт"
	return "заявка закрыта"


static func validate_choice(participants_value: int, ttl: int) -> String:
	if not SIZE_OPTIONS.has(participants_value) or not TTL_OPTIONS.has(ttl):
		return CHOICE_REQUIRED
	return ""


static func _participant_index(participants: Variant, character_id: int) -> int:
	if not (participants is Array):
		return -1
	var items: Array = participants
	for index in range(items.size()):
		var item: Variant = items[index]
		if item is Dictionary and str(item.get("id", "")) == str(character_id):
			return index
	return -1
