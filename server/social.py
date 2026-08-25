import copy
import time
import uuid

from server.world import get_bot_opponents


PRESENCE_TTL = 15
DUEL_OFFER_TTL = 120
BOT_REPOST_DELAY = 30
PRESENCE = {}
MESSAGES = []
DUEL_OFFERS = []


def _cleanup():
    now = time.time()
    cutoff = now - PRESENCE_TTL
    for token in list(PRESENCE):
        if PRESENCE[token]["seen_at"] < cutoff:
            del PRESENCE[token]
    for offer in DUEL_OFFERS:
        if offer["status"] == "pending" and offer["created_at"] + DUEL_OFFER_TTL <= now:
            offer["status"] = "expired"
            offer["expired_at"] = now


def update_presence(token, user_id, character, location):
    _cleanup()
    PRESENCE[token] = {
        "token": token,
        "user_id": user_id,
        "character_id": character["id"],
        "name": character["name"],
        "level": character["level"],
        "hp": character["hp"],
        "max_hp": character["max_hp"],
        "stats": copy.deepcopy(character["stats"]),
        "location": location,
        "seen_at": time.time(),
    }


def occupants(user_id, location):
    _cleanup()
    result = []
    for item in PRESENCE.values():
        if item["location"] == location:
            result.append({key: value for key, value in item.items() if key != "token"})
    if location == "backyard":
        for bot in get_bot_opponents():
            result.append({
                **bot,
                "character_id": bot["id"],
                "kind": "bot",
                "location": location,
            })
    return result


def backyard_duel_error(player, opponent):
    if player.get("level") != opponent.get("level"):
        return "Бой возможен только между персонажами одного уровня"

    player_total = sum(player.get("stats", {}).values())
    opponent_total = sum(opponent.get("stats", {}).values())
    if player_total != 26 or opponent_total != 26:
        return "Для равного боя у каждого должно быть ровно 26 очков характеристик"

    equipment_keys = ("equipment", "items", "weapon", "armor", "gear")
    if any(player.get(key) for key in equipment_keys) or any(opponent.get(key) for key in equipment_keys):
        return "На заднем дворе проводятся только кулачные бои без экипировки"
    return None


def add_message(sender, recipient_id, text, location):
    message = {
        "id": str(uuid.uuid4()),
        "sender": sender["name"],
        "sender_id": sender["character_id"],
        "recipient_id": recipient_id,
        "text": text,
        "location": location,
        "created_at": time.time(),
    }
    MESSAGES.append(message)
    del MESSAGES[:-100]
    return message


def messages_for(character_id, location):
    _cleanup()
    return [
        message for message in MESSAGES
        if message["location"] == location
        and (message["recipient_id"] is None or message["recipient_id"] == character_id)
    ][-50:]


def add_duel_offer(sender, target_id, location):
    offer = {
        "id": str(uuid.uuid4()),
        "sender_id": sender["character_id"],
        "sender": sender["name"],
        "target_id": target_id,
        "location": location,
        "status": "pending",
        "created_at": time.time(),
    }
    DUEL_OFFERS.append(offer)
    return offer


def offers_for(character_id):
    _cleanup()
    return [
        copy.deepcopy(offer)
        for offer in DUEL_OFFERS
        if offer["status"] == "pending"
        and offer["target_id"] == character_id
        and offer["sender_id"] != character_id
    ]


def add_public_duel_offer(sender, location):
    _cleanup()
    for offer in DUEL_OFFERS:
        if offer["sender_id"] == sender["character_id"] and offer["location"] == location and offer["status"] == "pending":
            return copy.deepcopy(offer)
    return add_duel_offer(sender, None, location)


def pending_public_offer(sender_id, location):
    _cleanup()
    for offer in DUEL_OFFERS:
        if (
            offer["sender_id"] == sender_id
            and offer["location"] == location
            and offer["target_id"] is None
            and offer["status"] == "pending"
        ):
            return copy.deepcopy(offer)
    return None


def cancel_public_duel_offer(sender_id, location):
    _cleanup()
    for offer in DUEL_OFFERS:
        if (
            offer["sender_id"] == sender_id
            and offer["location"] == location
            and offer["target_id"] is None
            and offer["status"] == "pending"
        ):
            offer["status"] = "cancelled"
            offer["cancelled_at"] = time.time()
            return copy.deepcopy(offer)
    raise ValueError("Нет активной заявки для отмены")


def _latest_public_offer(sender_id, location):
    offers = [
        offer for offer in DUEL_OFFERS
        if offer["sender_id"] == sender_id
        and offer["location"] == location
        and offer["target_id"] is None
    ]
    return max(offers, key=lambda offer: offer.get("created_at", 0)) if offers else None


def public_offers(location, exclude_character_id=None):
    _cleanup()
    now = time.time()
    available_bots = {}
    if location == "backyard":
        available_bots = {bot["id"]: bot for bot in get_bot_opponents()}
        for offer in DUEL_OFFERS:
            if (
                offer["status"] == "pending"
                and offer["location"] == location
                and offer["target_id"] is None
                and offer["sender_id"] in available_bots
                and available_bots[offer["sender_id"]]["hp"] < available_bots[offer["sender_id"]]["max_hp"]
            ):
                offer["status"] = "expired"
                offer["expired_at"] = now

        for bot in available_bots.values():
            if bot["hp"] < bot["max_hp"] or pending_public_offer(bot["id"], location) is not None:
                continue
            last_offer = _latest_public_offer(bot["id"], location)
            if last_offer is not None and last_offer.get("status") in {"expired", "declined", "cancelled"}:
                cooldown_from = (
                    last_offer.get("expired_at")
                    or last_offer.get("responded_at")
                    or last_offer.get("cancelled_at")
                    or last_offer.get("created_at", 0)
                )
                if now < float(cooldown_from) + BOT_REPOST_DELAY:
                    continue
            if bot["hp"] >= bot["max_hp"]:
                add_public_duel_offer({
                    "character_id": bot["id"],
                    "name": bot["name"],
                }, location)
    offers = [
        copy.deepcopy(offer)
        for offer in DUEL_OFFERS
        if offer["location"] == location
        and offer["target_id"] is None
        and offer["status"] == "pending"
        and (offer["sender_id"] not in available_bots or available_bots[offer["sender_id"]]["hp"] >= available_bots[offer["sender_id"]]["max_hp"])
        and offer["sender_id"] != exclude_character_id
    ]
    offers.sort(key=lambda offer: offer.get("created_at", 0), reverse=True)
    return offers


def respond_duel_offer(character_id, offer_id, accepted):
    for offer in DUEL_OFFERS:
        if offer["id"] == offer_id and offer["status"] == "pending" and (offer["target_id"] == character_id or offer["target_id"] is None) and offer["sender_id"] != character_id:
            offer["status"] = "accepted" if accepted else "declined"
            offer["accepted_by"] = character_id if accepted else None
            offer["responded_at"] = time.time()
            return copy.deepcopy(offer)
    raise ValueError("Предложение поединка не найдено")
