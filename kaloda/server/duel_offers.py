import copy
import threading
import time
import uuid

from kaloda.server import group_offers
from kaloda.server.bots import get_bot_opponents


DUEL_OFFER_TTL = 120
# Закрытая заявка ещё видна клиентам: бот принял заявку игрока — игроку нужно успеть начать бой. Потом запись удаляется.
CLOSED_OFFER_RETENTION = 600
DUEL_OFFERS = []
# HTTP-потоки и поток ботов меняют заявки одновременно. Замок берётся только на время работы со списком
# и никогда не удерживается при обращении к ботам (у них свой замок, порядок: боты -> заявки).
_LOCK = threading.RLock()


def backyard_duel_error(player, opponent):
    if player.get("level") != opponent.get("level"):
        return "Бой возможен только между персонажами одного уровня"
    if player.get("equipment") or opponent.get("equipment"):
        return "На заднем дворе бои проводятся без экипировки"
    return None


def _normalize_id(character_id):
    """Игрок — целый id, бот — строка bot_*: id из JSON-запроса может прийти строкой."""
    if isinstance(character_id, str) and character_id.isascii() and character_id.isdigit():
        return int(character_id)
    return character_id


def _close(offer, status, now=None, timestamp_key=None):
    now = time.time() if now is None else float(now)
    offer["status"] = status
    offer[timestamp_key or f"{status}_at"] = now
    offer["closed_at"] = now


def _is_stale(offer, now):
    if offer["status"] == "pending":
        return False
    closed_at = offer.get("closed_at") or offer["created_at"] + offer.get("ttl", DUEL_OFFER_TTL)
    return closed_at + CLOSED_OFFER_RETENTION <= now


def cleanup():
    now = time.time()
    with _LOCK:
        for offer in DUEL_OFFERS:
            if offer["status"] == "pending" and offer["created_at"] + offer.get("ttl", DUEL_OFFER_TTL) <= now:
                _close(offer, "expired", now)
        # Список остаётся тем же объектом: на него ссылаются social.DUEL_OFFERS и обработчик
        DUEL_OFFERS[:] = [offer for offer in DUEL_OFFERS if not _is_stale(offer, now)]


def add_duel_offer(sender, target_id, location, ttl=DUEL_OFFER_TTL, created_at=None, accepted_by=None):
    """Создаёт заявку и возвращает сохранённую запись: правки её полей остаются в хранилище.
    С accepted_by заявка сразу принята (вызов бота или афк-игрока, которым отвечать некому)."""
    offer = {
        "id": str(uuid.uuid4()), "sender_id": sender["character_id"],
        "sender": sender["name"], "target_id": _normalize_id(target_id), "location": location,
        "status": "pending", "created_at": time.time() if created_at is None else float(created_at),
        "ttl": int(ttl),
    }
    if accepted_by is not None:
        _close(offer, "accepted", timestamp_key="responded_at")
        offer["accepted_by"] = accepted_by
    with _LOCK:
        DUEL_OFFERS.append(offer)
    return offer


def add_public_duel_offer(sender, location, ttl=DUEL_OFFER_TTL, created_at=None):
    with _LOCK:
        cleanup()
        for offer in DUEL_OFFERS:
            if offer["sender_id"] == sender["character_id"] and offer["location"] == location and offer["status"] == "pending":
                return copy.deepcopy(offer)
        return copy.deepcopy(add_duel_offer(sender, None, location, ttl, created_at))


def pending_public_offer(sender_id, location):
    with _LOCK:
        cleanup()
        return next(
            (
                copy.deepcopy(offer) for offer in DUEL_OFFERS
                if offer["sender_id"] == sender_id and offer["location"] == location
                and offer["target_id"] is None and offer["status"] == "pending"
            ),
            None,
        )


def has_active_application(character_id):
    return pending_public_offer(character_id, "backyard") is not None or group_offers.has_active_application(character_id)


def offers_for(character_id):
    with _LOCK:
        cleanup()
        return [
            copy.deepcopy(offer) for offer in DUEL_OFFERS
            if offer["status"] == "pending" and offer["target_id"] == character_id and offer["sender_id"] != character_id
        ]


def cancel_public_duel_offer(sender_id, location):
    with _LOCK:
        cleanup()
        for offer in DUEL_OFFERS:
            if offer["sender_id"] == sender_id and offer["location"] == location and offer["target_id"] is None and offer["status"] == "pending":
                _close(offer, "cancelled")
                return copy.deepcopy(offer)
    raise ValueError("Нет активной заявки для отмены")


def pending_bot_public_offers(location):
    with _LOCK:
        cleanup()
        return [
            copy.deepcopy(offer) for offer in DUEL_OFFERS
            if offer["location"] == location and offer["target_id"] is None and offer["status"] == "pending"
            and str(offer["sender_id"]).startswith("bot_")
        ]


def pending_player_public_offers(location):
    with _LOCK:
        cleanup()
        return [
            copy.deepcopy(offer) for offer in DUEL_OFFERS
            if offer["location"] == location and offer["target_id"] is None and offer["status"] == "pending"
            and not str(offer["sender_id"]).startswith("bot_")
        ]


def own_public_offer(sender_id, location):
    """Активная заявка этого отправителя, либо только что принятая ботом — чтобы клиент мог начать бой."""
    with _LOCK:
        cleanup()
        candidates = [
            offer for offer in DUEL_OFFERS
            if offer["sender_id"] == sender_id and offer["location"] == location and offer["target_id"] is None
            and offer["status"] in ("pending", "accepted")
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda offer: offer["created_at"], reverse=True)
        return copy.deepcopy(candidates[0])


def close_public_offer(offer_id, status, now=None):
    with _LOCK:
        for offer in DUEL_OFFERS:
            if offer["id"] == offer_id and offer["status"] == "pending":
                _close(offer, status, now)
                return copy.deepcopy(offer)
    raise ValueError("Заявка поединка не найдена")


def accept_public_offer(offer_id, accepter_id, now=None):
    return _set_offer_status(offer_id, "accepted", accepter_id, now)


def _set_offer_status(offer_id, status, character_id, now=None):
    with _LOCK:
        for offer in DUEL_OFFERS:
            if offer["id"] == offer_id and offer["status"] == "pending":
                _close(offer, status, now, timestamp_key="responded_at")
                offer["accepted_by"] = character_id
                return copy.deepcopy(offer)
    raise ValueError("Заявка поединка не найдена")


def public_offers(location, exclude_character_id=None):
    # Боты опрашиваются до взятия замка заявок, чтобы не нарушать порядок замков
    available_bots = {bot["id"]: bot for bot in get_bot_opponents()} if location == "backyard" else {}
    with _LOCK:
        cleanup()
        result = []
        for offer in DUEL_OFFERS:
            if offer["location"] != location or offer["target_id"] is not None or offer["status"] != "pending":
                continue
            bot = available_bots.get(offer["sender_id"])
            # Раненый бот не может драться: его заявка снимается
            if bot is not None and bot["hp"] < bot["max_hp"]:
                _close(offer, "expired")
                continue
            if offer["sender_id"] != exclude_character_id:
                result.append(copy.deepcopy(offer))
        return result


def respond_duel_offer(character_id, offer_id, accepted):
    with _LOCK:
        cleanup()
        for offer in DUEL_OFFERS:
            if (
                offer["id"] == offer_id and offer["status"] == "pending"
                and (offer["target_id"] == character_id or offer["target_id"] is None)
                and offer["sender_id"] != character_id
            ):
                _close(offer, "accepted" if accepted else "declined", timestamp_key="responded_at")
                offer["accepted_by"] = character_id if accepted else None
                return copy.deepcopy(offer)
    raise ValueError("Предложение поединка не найдено")