import copy
import random
import time
import uuid

from combat.group_battle import GROUP_BATTLE_TTL_SECONDS, MAX_GROUP_BATTLE_PARTICIPANTS, prepare_group_participants, split_balanced_teams
from server.world import get_bot_opponents


PRESENCE_TTL = 15
DUEL_OFFER_TTL = 120
PRESENCE = {}
MESSAGES = []
DUEL_OFFERS = []
GROUP_BATTLE_OFFERS = []
BOT_TAVERN_REPLIES = {
    "win": [
        "Славный бой! Мой удар справа сапогом в глаз был шикарным!!!",
        "Хах, видели как я его коленом в печень отправил на землю?! Красота!!!",
        "Моя левая рука сегодня работала как молот кузнеца, чистая победа!",
        "Он думал что устоит после моего апперкота... наивный!!!",
        "Заказывайте мне самый крепкий эль, я это заслужил после такого нокаута!",
        "Видели его лицо когда я ему прямой в нос засадил? Бесценно!!!",
        "Ещё один бедолага отправился в объятия сна благодаря моему хуку!",
        "Моя бабка бьёт сильнее чем этот \"боец\"... шучу, но было легко!",
        "Три зуба на арене — мой сегодняшний трофей, всем показать?!",
        "Он упал так красиво, что я почти прослезился... от гордости за себя!",
    ],
    "loss": [
        "Что-то моя жопа пережила серьёзный стресс!!",
        "Мне кажется его кулак был размером с наковальню... и попал точно в челюсть.",
        "Кто-нибудь видел куда улетели два моих передних зуба?",
        "Лекаря сюда, срочно! И побольше эля для анестезии!!!",
        "Я упал так красиво, что даже сам удивился... не специально!",
        "Моё лицо теперь новая карта звёздного неба, все синяки видели?",
        "Ладно, признаю — он бил как разгневанный тролль!",
        "Кажется, я забыл как дышать носом... временно, надеюсь!",
        "Земля сегодня была особенно твёрдой когда я в неё влетел спиной.",
        "Моя гордость болит больше чем ребра, а ребра болят ОЧЕНЬ сильно!",
    ],
    "draw": [
        "Ну что за бой, оба без зубов остались, зато без обид!",
        "Так, надо признать — сегодня наши кулаки оказались одинаково тупыми!",
        "Судья наверное сам не понял кто кого больше отхватил... ничья, чтоб её!",
        "Мы оба выглядим как после встречи с горным троллем, засчитано поровну!",
        "Ладно, в следующий раз реванш, а сейчас — эль за счёт заведения, раз победителя нет!",
    ],
}
BOT_TAVERN_MESSAGES = []


def _cleanup():
    now = time.time()
    cutoff = now - PRESENCE_TTL
    for token in list(PRESENCE):
        if PRESENCE[token]["seen_at"] < cutoff:
            del PRESENCE[token]
    for offer in DUEL_OFFERS:
        if offer["status"] == "pending" and offer["created_at"] + offer.get("ttl", DUEL_OFFER_TTL) <= now:
            offer["status"] = "expired"
            offer["expired_at"] = now
    for offer in GROUP_BATTLE_OFFERS:
        if offer["status"] == "waiting" and offer["created_at"] + offer["ttl"] <= now:
            if len(offer["participants"]) >= 6:
                offer["participants"] = prepare_group_participants(offer["participants"])
                offer["teams"] = split_balanced_teams(offer["participants"], seed=offer["id"])
                offer["status"] = "ready"
            else:
                offer["status"] = "expired"


def update_presence(token, user_id, character, location):
    _cleanup()
    PRESENCE[token] = {
        "token": token,
        "user_id": user_id,
        "character_id": character["id"],
        "name": character["name"],
        "level": character["level"],
        "xp": character["xp"],
        "hp": character["hp"],
        "max_hp": character["max_hp"],
        "mp": character["mp"],
        "max_mp": character["max_mp"],
        "stats": copy.deepcopy(character["stats"]),
        "stat_points": character["stat_points"],
        "location": location,
        "seen_at": time.time(),
    }


def occupants(user_id, location):
    _cleanup()
    result = []
    for item in PRESENCE.values():
        if item["location"] == location:
            result.append({key: value for key, value in item.items() if key != "token"})
    if location in {"backyard", "tavern"}:
        for bot in get_bot_opponents():
            if bot.get("zone") != location:
                continue
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


def record_bot_tavern_reply(bot_id, bot_name, outcome, location="tavern", db=None):
    outcome_key = outcome if outcome in BOT_TAVERN_REPLIES else "draw"
    text = random.choice(BOT_TAVERN_REPLIES[outcome_key])
    if db is None:
        try:
            from server.database import Database
            db = Database()
        except Exception:
            db = None
    if db is not None:
        try:
            sender_id = db.ensure_bot_character(bot_id, bot_name)
            db.add_chat_message(sender_id, location, text)
        except Exception:
            pass
    reply = {
        "id": f"bot-reply-{bot_id}-{int(time.time() * 1000)}",
        "sender": bot_name,
        "sender_id": str(bot_id),
        "recipient_id": None,
        "text": text,
        "location": location,
        "created_at": time.time(),
    }
    BOT_TAVERN_MESSAGES.append(reply)
    if len(BOT_TAVERN_MESSAGES) > 200:
        del BOT_TAVERN_MESSAGES[:-200]
    return reply


def bot_tavern_messages(location):
    if location != "tavern":
        return []
    return [
        dict(message)
        for message in BOT_TAVERN_MESSAGES
        if message.get("location") == location
    ]


def messages_for(character_id, location):
    _cleanup()
    return [
        message for message in MESSAGES
        if message["location"] == location
        and (message["recipient_id"] is None or message["recipient_id"] == character_id)
    ][-50:]


def add_duel_offer(sender, target_id, location, ttl=DUEL_OFFER_TTL, created_at=None):
    offer = {
        "id": str(uuid.uuid4()),
        "sender_id": sender["character_id"],
        "sender": sender["name"],
        "target_id": target_id,
        "location": location,
        "status": "pending",
        "created_at": time.time() if created_at is None else float(created_at),
        "ttl": int(ttl),
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


def add_public_duel_offer(sender, location, ttl=DUEL_OFFER_TTL, created_at=None):
    _cleanup()
    for offer in DUEL_OFFERS:
        if offer["sender_id"] == sender["character_id"] and offer["location"] == location and offer["status"] == "pending":
            return copy.deepcopy(offer)
    return add_duel_offer(sender, None, location, ttl, created_at)


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


def has_active_application(character_id):
    _cleanup()
    if pending_public_offer(character_id, "backyard") is not None:
        return True
    return any(
        offer["status"] == "waiting"
        and any(item["id"] == character_id for item in offer["participants"])
        for offer in GROUP_BATTLE_OFFERS
    )


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


def pending_bot_public_offers(location):
    """Return current bot applications without creating or mutating new ones."""
    return [
        offer for offer in DUEL_OFFERS
        if offer["location"] == location
        and offer["target_id"] is None
        and offer["status"] == "pending"
        and str(offer["sender_id"]).startswith("bot_")
    ]


def close_public_offer(offer_id, status, now=None):
    for offer in DUEL_OFFERS:
        if offer["id"] == offer_id and offer["status"] == "pending":
            offer["status"] = status
            offer[f"{status}_at"] = time.time() if now is None else float(now)
            return copy.deepcopy(offer)
    raise ValueError("Заявка поединка не найдена")


def accept_public_offer(offer_id, accepter_id, now=None):
    for offer in DUEL_OFFERS:
        if offer["id"] == offer_id and offer["status"] == "pending":
            offer["status"] = "accepted"
            offer["accepted_by"] = accepter_id
            offer["responded_at"] = time.time() if now is None else float(now)
            return copy.deepcopy(offer)
    raise ValueError("Заявка поединка не найдена")


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
                and (
                    available_bots[offer["sender_id"]]["zone"] != "backyard"
                    or available_bots[offer["sender_id"]]["hp"] < available_bots[offer["sender_id"]]["max_hp"]
                )
            ):
                offer["status"] = "expired"
                offer["expired_at"] = now
    offers = [
        copy.deepcopy(offer)
        for offer in DUEL_OFFERS
        if offer["location"] == location
        and offer["target_id"] is None
        and offer["status"] == "pending"
        and (
            offer["sender_id"] not in available_bots
            or (
                available_bots[offer["sender_id"]]["zone"] == "backyard"
                and available_bots[offer["sender_id"]]["hp"] >= available_bots[offer["sender_id"]]["max_hp"]
            )
        )
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


def create_group_battle_offer(sender, ttl=GROUP_BATTLE_TTL_SECONDS, max_participants=10):
    _cleanup()
    for offer in GROUP_BATTLE_OFFERS:
        if offer["status"] == "waiting" and any(item["id"] == sender["id"] for item in offer["participants"]):
            return copy.deepcopy(offer)
    offer = {
        "id": str(uuid.uuid4()),
        "mode": "wall_to_wall",
        "sender_id": sender["id"],
        "sender": sender["name"],
        "max_participants": int(max_participants),
        "ttl": int(ttl),
        "participants": [copy.deepcopy(sender)],
        "status": "waiting",
        "created_at": time.time(),
    }
    GROUP_BATTLE_OFFERS.append(offer)
    return copy.deepcopy(offer)


def join_group_battle_offer(offer_id, participant):
    _cleanup()
    offer = next((item for item in GROUP_BATTLE_OFFERS if item["id"] == offer_id), None)
    if offer is None or offer["status"] != "waiting":
        raise ValueError("Заявка группового боя уже закрыта")
    if any(item["id"] == participant["id"] for item in offer["participants"]):
        return copy.deepcopy(offer)
    if len(offer["participants"]) >= offer["max_participants"]:
        raise ValueError(f"В групповом бою может быть не больше {offer['max_participants']} участников")
    offer["participants"].append(copy.deepcopy(participant))
    return copy.deepcopy(offer)


def group_battle_offers():
    _cleanup()
    return [copy.deepcopy(offer) for offer in GROUP_BATTLE_OFFERS if offer["status"] == "waiting"]


def group_battle_offer(offer_id):
    _cleanup()
    offer = next((item for item in GROUP_BATTLE_OFFERS if item["id"] == offer_id), None)
    return copy.deepcopy(offer) if offer is not None else None


def leave_group_battle_offer(offer_id, participant_id):
    _cleanup()
    offer = next((item for item in GROUP_BATTLE_OFFERS if item["id"] == offer_id), None)
    if offer is None or offer["status"] != "waiting":
        raise ValueError("Заявка группового боя уже закрыта")
    if participant_id == offer["sender_id"]:
        offer["status"] = "cancelled"
        offer["cancelled_at"] = time.time()
    else:
        offer["participants"] = [item for item in offer["participants"] if item["id"] != participant_id]
    return copy.deepcopy(offer)
