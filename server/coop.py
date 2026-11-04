"""In-memory co-op party invitations for players sharing a world-map tile."""

import threading
import time
import uuid

from core.map_config import TILE_SIZE
from server import presence


MAX_PARTY_SIZE = 3
INVITE_TTL_SECONDS = 120
PARTIES = {}
INVITES = {}
_LOCK = threading.RLock()


def _cleanup():
    now = time.time()
    for invite_id, invite in list(INVITES.items()):
        if invite["expires_at"] <= now or invite["status"] != "pending":
            INVITES.pop(invite_id, None)
    for party_id, party in list(PARTIES.items()):
        if now - party["seen_at"] > INVITE_TTL_SECONDS * 3:
            PARTIES.pop(party_id, None)
            for invite_id, invite in list(INVITES.items()):
                if invite["party_id"] == party_id:
                    INVITES.pop(invite_id, None)


def _presence(character_id):
    return presence.get_character_presence(int(character_id))


def _tile_for(item):
    if not item:
        return None
    try:
        return (
            int(float(item["position_x"]) // TILE_SIZE),
            int(float(item["position_y"]) // TILE_SIZE),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _same_map_tile(first_id, second_id):
    first = _presence(first_id)
    second = _presence(second_id)
    if not first or not second:
        return False
    if (
        first.get("location") != "world_map"
        or second.get("location") != "world_map"
        or first.get("afk")
        or second.get("afk")
    ):
        return False
    try:
        first_tile = (
            int(float(first["position_x"]) // TILE_SIZE),
            int(float(first["position_y"]) // TILE_SIZE),
        )
        second_tile = (
            int(float(second["position_x"]) // TILE_SIZE),
            int(float(second["position_y"]) // TILE_SIZE),
        )
    except (KeyError, TypeError, ValueError):
        return False
    return first_tile == second_tile


def _party_for(character_id):
    return next(
        (
            party for party in PARTIES.values()
            if int(character_id) in party["members"]
        ),
        None,
    )


def _public_party(party):
    members = []
    for character_id in party["members"]:
        item = _presence(character_id)
        if item:
            members.append({
                "character_id": character_id,
                "name": item.get("name", ""),
                "tile": _tile_for(item),
            })
        else:
            members.append({"character_id": character_id, "name": "", "tile": None})
    return {
        "id": party["id"],
        "leader_id": party["leader_id"],
        "members": members,
        "max_members": MAX_PARTY_SIZE,
    }


def state_for(character_id):
    with _LOCK:
        _cleanup()
        party = _party_for(int(character_id))
        if party:
            party["seen_at"] = time.time()
        incoming = [
            {
                **invite,
                "sender": (
                    {"character_id": invite["sender_id"], "name": (
                        (_presence(invite["sender_id"]) or {}).get("name", "")
                    )}
                ),
            }
            for invite in INVITES.values()
            if invite["target_id"] == int(character_id)
            and invite["status"] == "pending"
        ]
        return {
            "party": _public_party(party) if party else None,
            "incoming": incoming,
        }


def create_invite(sender_id, target_id):
    sender_id, target_id = int(sender_id), int(target_id)
    if sender_id == target_id:
        raise ValueError("Нельзя пригласить самого себя")
    with _LOCK:
        _cleanup()
        if not _same_map_tile(sender_id, target_id):
            raise ValueError("Для приглашения нужно находиться на одном тайле карты")
        sender_party = _party_for(sender_id)
        target_party = _party_for(target_id)
        if target_party:
            raise ValueError("Персонаж уже состоит в группе")
        if sender_party is None:
            sender_party = {
                "id": str(uuid.uuid4()),
                "leader_id": sender_id,
                "members": [sender_id],
                "seen_at": time.time(),
            }
            PARTIES[sender_party["id"]] = sender_party
        if len(sender_party["members"]) >= MAX_PARTY_SIZE:
            raise ValueError("В группе может быть не более трёх игроков")
        if any(
            invite["party_id"] == sender_party["id"]
            and invite["target_id"] == target_id
            and invite["status"] == "pending"
            for invite in INVITES.values()
        ):
            raise ValueError("Приглашение уже отправлено")
        invite = {
            "id": str(uuid.uuid4()),
            "party_id": sender_party["id"],
            "sender_id": sender_id,
            "target_id": target_id,
            "status": "pending",
            "expires_at": time.time() + INVITE_TTL_SECONDS,
        }
        INVITES[invite["id"]] = invite
        sender_party["seen_at"] = time.time()
        return {"invite": dict(invite), "party": _public_party(sender_party)}


def respond_invite(character_id, invite_id, accepted):
    character_id = int(character_id)
    with _LOCK:
        _cleanup()
        invite = INVITES.get(str(invite_id))
        if invite is None or invite["target_id"] != character_id:
            raise ValueError("Приглашение не найдено или уже истекло")
        if not accepted:
            INVITES.pop(invite["id"], None)
            return {"accepted": False, "party": None}
        if not _same_map_tile(invite["sender_id"], character_id):
            raise ValueError("Чтобы вступить в группу, нужно остаться на том же тайле")
        party = PARTIES.get(invite["party_id"])
        if party is None or _party_for(character_id):
            raise ValueError("Группа больше недоступна")
        if len(party["members"]) >= MAX_PARTY_SIZE:
            raise ValueError("В группе может быть не более трёх игроков")
        party["members"].append(character_id)
        party["seen_at"] = time.time()
        INVITES.pop(invite["id"], None)
        return {"accepted": True, "party": _public_party(party)}


def leave_party(character_id):
    character_id = int(character_id)
    with _LOCK:
        _cleanup()
        party = _party_for(character_id)
        if party is None:
            return {"party": None}
        party["members"].remove(character_id)
        for invite_id, invite in list(INVITES.items()):
            if invite["party_id"] == party["id"] and (
                invite["sender_id"] == character_id
                or invite["target_id"] == character_id
            ):
                INVITES.pop(invite_id, None)
        if not party["members"]:
            PARTIES.pop(party["id"], None)
            return {"party": None}
        if party["leader_id"] == character_id:
            party["leader_id"] = party["members"][0]
        party["seen_at"] = time.time()
        return {"party": _public_party(party)}
