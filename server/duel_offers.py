import copy
import time
import uuid

from server.world import get_bot_opponents


DUEL_OFFER_TTL = 120
DUEL_OFFERS = []


def backyard_duel_error(player, opponent):
    if player.get("level") != opponent.get("level"):
        return "Бой возможен только между персонажами одного уровня"
    if sum(player.get("stats", {}).values()) != 26 or sum(opponent.get("stats", {}).values()) != 26:
        return "Для равного боя у каждого должно быть ровно 26 очков характеристик"
    equipment_keys = ("equipment", "items", "weapon", "armor", "gear")
    if any(player.get(key) for key in equipment_keys) or any(opponent.get(key) for key in equipment_keys):
        return "На заднем дворе проводятся только кулачные бои без экипировки"
    return None


def cleanup():
    now = time.time()
    for offer in DUEL_OFFERS:
        if offer["status"] == "pending" and offer["created_at"] + offer.get("ttl", DUEL_OFFER_TTL) <= now:
            offer["status"] = "expired"
            offer["expired_at"] = now


def add_duel_offer(sender, target_id, location, ttl=DUEL_OFFER_TTL, created_at=None):
    offer = {
        "id": str(uuid.uuid4()), "sender_id": sender["character_id"],
        "sender": sender["name"], "target_id": target_id, "location": location,
        "status": "pending", "created_at": time.time() if created_at is None else float(created_at),
        "ttl": int(ttl),
    }
    DUEL_OFFERS.append(offer)
    return offer


def add_public_duel_offer(sender, location, ttl=DUEL_OFFER_TTL, created_at=None):
    cleanup()
    for offer in DUEL_OFFERS:
        if offer["sender_id"] == sender["character_id"] and offer["location"] == location and offer["status"] == "pending":
            return copy.deepcopy(offer)
    return add_duel_offer(sender, None, location, ttl, created_at)


def pending_public_offer(sender_id, location):
    cleanup()
    return next((copy.deepcopy(offer) for offer in DUEL_OFFERS if offer["sender_id"] == sender_id and offer["location"] == location and offer["target_id"] is None and offer["status"] == "pending"), None)


def has_active_application(character_id):
    from server import group_offers
    return pending_public_offer(character_id, "backyard") is not None or group_offers.has_active_application(character_id)


def offers_for(character_id):
    cleanup()
    return [copy.deepcopy(offer) for offer in DUEL_OFFERS if offer["status"] == "pending" and offer["target_id"] == character_id and offer["sender_id"] != character_id]


def cancel_public_duel_offer(sender_id, location):
    cleanup()
    for offer in DUEL_OFFERS:
        if offer["sender_id"] == sender_id and offer["location"] == location and offer["target_id"] is None and offer["status"] == "pending":
            offer["status"] = "cancelled"
            offer["cancelled_at"] = time.time()
            return copy.deepcopy(offer)
    raise ValueError("Нет активной заявки для отмены")


def pending_bot_public_offers(location):
    return [copy.deepcopy(offer) for offer in DUEL_OFFERS if offer["location"] == location and offer["target_id"] is None and offer["status"] == "pending" and str(offer["sender_id"]).startswith("bot_")]


def close_public_offer(offer_id, status, now=None):
    for offer in DUEL_OFFERS:
        if offer["id"] == offer_id and offer["status"] == "pending":
            offer["status"] = status
            offer[f"{status}_at"] = time.time() if now is None else float(now)
            return copy.deepcopy(offer)
    raise ValueError("Заявка поединка не найдена")


def accept_public_offer(offer_id, accepter_id, now=None):
    return _set_offer_status(offer_id, "accepted", accepter_id, now)


def _set_offer_status(offer_id, status, character_id, now=None):
    for offer in DUEL_OFFERS:
        if offer["id"] == offer_id and offer["status"] == "pending":
            offer["status"] = status
            offer["accepted_by"] = character_id
            offer["responded_at"] = time.time() if now is None else float(now)
            return copy.deepcopy(offer)
    raise ValueError("Заявка поединка не найдена")


def public_offers(location, exclude_character_id=None):
    cleanup()
    available_bots = {bot["id"]: bot for bot in get_bot_opponents()} if location == "backyard" else {}
    for offer in DUEL_OFFERS:
        bot = available_bots.get(offer["sender_id"])
        if (
            offer["status"] == "pending"
            and offer["location"] == location
            and bot is not None
            and (bot["zone"] != "backyard" or bot["hp"] < bot["max_hp"])
        ):
            offer["status"] = "expired"
    return [copy.deepcopy(offer) for offer in DUEL_OFFERS if offer["location"] == location and offer["target_id"] is None and offer["status"] == "pending" and offer["sender_id"] != exclude_character_id and (offer["sender_id"] not in available_bots or (available_bots[offer["sender_id"]]["zone"] == "backyard" and available_bots[offer["sender_id"]]["hp"] >= available_bots[offer["sender_id"]]["max_hp"]))]


def respond_duel_offer(character_id, offer_id, accepted):
    for offer in DUEL_OFFERS:
        if offer["id"] == offer_id and offer["status"] == "pending" and (offer["target_id"] == character_id or offer["target_id"] is None) and offer["sender_id"] != character_id:
            offer["status"] = "accepted" if accepted else "declined"
            offer["accepted_by"] = character_id if accepted else None
            offer["responded_at"] = time.time()
            return copy.deepcopy(offer)
    raise ValueError("Предложение поединка не найдено")