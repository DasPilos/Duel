import copy
import time
import uuid

from combat.group_battle import GROUP_BATTLE_TTL_SECONDS, prepare_group_participants, split_balanced_teams


GROUP_BATTLE_OFFERS = []


def cleanup():
    for offer in GROUP_BATTLE_OFFERS:
        if offer["status"] == "waiting" and offer["created_at"] + offer["ttl"] <= time.time():
            if len(offer["participants"]) >= 6:
                offer["participants"] = prepare_group_participants(offer["participants"])
                offer["teams"] = split_balanced_teams(offer["participants"], seed=offer["id"])
                offer["status"] = "ready"
            else:
                offer["status"] = "expired"


def has_active_application(character_id):
    cleanup()
    return any(offer["status"] == "waiting" and any(item["id"] == character_id for item in offer["participants"]) for offer in GROUP_BATTLE_OFFERS)


def create_group_battle_offer(sender, ttl=GROUP_BATTLE_TTL_SECONDS, max_participants=10):
    cleanup()
    for offer in GROUP_BATTLE_OFFERS:
        if offer["status"] == "waiting" and any(item["id"] == sender["id"] for item in offer["participants"]):
            return copy.deepcopy(offer)
    offer = {"id": str(uuid.uuid4()), "mode": "wall_to_wall", "sender_id": sender["id"], "sender": sender["name"], "max_participants": int(max_participants), "ttl": int(ttl), "participants": [copy.deepcopy(sender)], "status": "waiting", "created_at": time.time()}
    GROUP_BATTLE_OFFERS.append(offer)
    return copy.deepcopy(offer)


def join_group_battle_offer(offer_id, participant):
    cleanup()
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
    cleanup()
    return [copy.deepcopy(offer) for offer in GROUP_BATTLE_OFFERS if offer["status"] == "waiting"]


def group_battle_offer(offer_id):
    cleanup()
    offer = next((item for item in GROUP_BATTLE_OFFERS if item["id"] == offer_id), None)
    return copy.deepcopy(offer) if offer is not None else None


def leave_group_battle_offer(offer_id, participant_id):
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