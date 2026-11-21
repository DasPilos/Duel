import copy
import threading
import time
import uuid

from deck.combat.group_battle import GROUP_BATTLE_TTL_SECONDS, prepare_group_participants, split_balanced_teams


GROUP_BATTLE_OFFERS = []
# Готовая или закрытая заявка ещё видна клиентам (им нужно забрать составы команд), потом запись удаляется.
CLOSED_OFFER_RETENTION = 3600
# Участник групповой заявки виден всем, поэтому деньги персонажа в неё не попадают.
PRIVATE_FIELDS = ("coins",)
# Замок на время работы со списком заявок; других замков внутри не берётся.
_LOCK = threading.RLock()


def _participant(character):
    return {key: copy.deepcopy(value) for key, value in character.items() if key not in PRIVATE_FIELDS}


def _closed_at(offer):
    return (
        offer.get("finished_at")
        or offer.get("started_at")
        or offer.get("ready_at")
        or offer.get("expired_at")
        or offer.get("cancelled_at")
        or offer["created_at"] + offer["ttl"]
    )


def _mark_ready(offer):
    offer["participants"] = prepare_group_participants(offer["participants"])
    offer["teams"] = split_balanced_teams(offer["participants"], seed=offer["id"])
    offer["status"] = "ready"
    offer["ready_at"] = time.time()


def cleanup():
    now = time.time()
    with _LOCK:
        for offer in GROUP_BATTLE_OFFERS:
            if offer["status"] == "waiting" and offer["created_at"] + offer["ttl"] <= now:
                if len(offer["participants"]) >= 6:
                    _mark_ready(offer)
                else:
                    offer["status"] = "expired"
                    offer["expired_at"] = now
        # Список остаётся тем же объектом: на него ссылается social.GROUP_BATTLE_OFFERS
        GROUP_BATTLE_OFFERS[:] = [
            offer for offer in GROUP_BATTLE_OFFERS
            if offer["status"] == "waiting" or _closed_at(offer) + CLOSED_OFFER_RETENTION > now
        ]


def has_active_application(character_id):
    with _LOCK:
        cleanup()
        return any(
            offer["status"] == "waiting" and any(item["id"] == character_id for item in offer["participants"])
            for offer in GROUP_BATTLE_OFFERS
        )


def create_group_battle_offer(sender, ttl=GROUP_BATTLE_TTL_SECONDS, max_participants=10):
    with _LOCK:
        cleanup()
        for offer in GROUP_BATTLE_OFFERS:
            if offer["status"] == "waiting" and any(item["id"] == sender["id"] for item in offer["participants"]):
                return copy.deepcopy(offer)
        offer = {
            "id": str(uuid.uuid4()), "mode": "wall_to_wall", "sender_id": sender["id"], "sender": sender["name"],
            "max_participants": int(max_participants), "ttl": int(ttl), "participants": [_participant(sender)],
            "status": "waiting", "created_at": time.time(),
        }
        GROUP_BATTLE_OFFERS.append(offer)
        return copy.deepcopy(offer)


def join_group_battle_offer(offer_id, participant):
    with _LOCK:
        cleanup()
        offer = next((item for item in GROUP_BATTLE_OFFERS if item["id"] == offer_id), None)
        if offer is None:
            raise ValueError("Заявка группового боя уже закрыта")
        if any(item["id"] == participant["id"] for item in offer["participants"]):
            return copy.deepcopy(offer)
        if offer["status"] != "waiting":
            raise ValueError("Заявка группового боя уже закрыта")
        if len(offer["participants"]) >= offer["max_participants"]:
            raise ValueError(f"В групповом бою может быть не больше {offer['max_participants']} участников")
        offer["participants"].append(_participant(participant))
        if len(offer["participants"]) >= offer["max_participants"]:
            _mark_ready(offer)
        return copy.deepcopy(offer)


def group_battle_offers():
    with _LOCK:
        cleanup()
        return [
            copy.deepcopy(offer) for offer in GROUP_BATTLE_OFFERS
            if offer["status"] in ("waiting", "ready", "in_progress")
        ]


def group_battle_offer(offer_id):
    with _LOCK:
        cleanup()
        offer = next((item for item in GROUP_BATTLE_OFFERS if item["id"] == offer_id), None)
        return copy.deepcopy(offer) if offer is not None else None


def leave_group_battle_offer(offer_id, participant_id):
    with _LOCK:
        cleanup()
        offer = next((item for item in GROUP_BATTLE_OFFERS if item["id"] == offer_id), None)
        if offer is None or offer["status"] != "waiting":
            raise ValueError("Заявка группового боя уже закрыта")
        if participant_id == offer["sender_id"]:
            offer["status"] = "cancelled"
            offer["cancelled_at"] = time.time()
        else:
            offer["participants"] = [item for item in offer["participants"] if item["id"] != participant_id]
        return copy.deepcopy(offer)


def start_group_battle(offer_id):
    with _LOCK:
        cleanup()
        offer = next((item for item in GROUP_BATTLE_OFFERS if item["id"] == offer_id), None)
        if offer is None or offer["status"] not in ("ready", "in_progress"):
            raise ValueError("Групповая заявка ещё не готова к бою")
        if offer["status"] == "ready":
            offer["status"] = "in_progress"
            offer["started_at"] = time.time()
            offer["results"] = {}
        return copy.deepcopy(offer)


def record_group_match_result(offer_id, results):
    with _LOCK:
        offer = next((item for item in GROUP_BATTLE_OFFERS if item["id"] == offer_id), None)
        if offer is None or offer["status"] not in ("in_progress", "completed"):
            return None
        stored = offer.setdefault("results", {})
        for character_id, outcome in results.items():
            stored[str(character_id)] = str(outcome)
        if all(str(participant["id"]) in stored for participant in offer["participants"]):
            scores = [0, 0]
            for team_index, team in enumerate(offer.get("teams", [])):
                for participant in team:
                    outcome = stored.get(str(participant["id"]))
                    if outcome == "win":
                        scores[team_index] += 1
            offer["team_scores"] = scores
            offer["status"] = "completed"
            offer["finished_at"] = time.time()
        return copy.deepcopy(offer)