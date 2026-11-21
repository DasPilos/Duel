"""Серверная часть арены: владелец и зона, близость, награды, возрождение и инвентарь."""

import json
import unittest

from deck.combat.card_database import class_cards_for_type
from deck.map_config import KOBOLD_RESPAWN_SECONDS, RESPAWN_CRYSTAL, TILE_SIZE
from deck.server import arena
from deck.server.arena_service import ArenaService
from tests.deck.test_deck_arena_server import _autoplay

USER_ID = 11
CHARACTER_ID = 7
NOW = 1000.0
DECK_KEYS = [card.key for card in class_cards_for_type("warrior")]
KOBOLD_POSITION = (55 * TILE_SIZE + 24, 12 * TILE_SIZE + 24)


def character_payload(**overrides):
    payload = {
        "id": CHARACTER_ID,
        "name": "Тест",
        "level": 5,
        "type": "warrior",
        "stats": {"strength": 6, "agility": 4, "intuition": 3, "wisdom": 2, "intellect": 2, "harmony": 2, "endurance": 6},
        "hp": 60,
        "max_hp": 80,
        "mp": 10,
        "max_mp": 10,
        "talents": {},
        "xp": 0,
        "stat_points": 0,
        "zone": "world_map",
        "position_x": float(KOBOLD_POSITION[0]),
        "position_y": float(KOBOLD_POSITION[1]),
        "position_direction": "s",
        "coins": 0,
        "equipment": {},
    }
    payload.update(overrides)
    return payload


class FakeDatabase:
    def __init__(self, character):
        self.character = dict(character)
        self.xp_calls = []
        self.saved = []
        self.xp_error = None
        self.save_error = None

    def get_character_for_battle(self, character_id):
        if character_id != CHARACTER_ID:
            return None
        return {"user_id": USER_ID, "character": dict(self.character)}

    def get_character(self, user_id, character_id):
        return dict(self.character)

    def report_npc_kill_xp(self, user_id, character_id, encounter_id, defeated_types, request_id):
        self.xp_calls.append((encounter_id, tuple(defeated_types), request_id))
        if self.xp_error is not None:
            raise self.xp_error
        awarded = 10 * len(defeated_types)
        self.character["xp"] += awarded
        return {"character": dict(self.character), "xp": awarded}

    def save_character(self, user_id, character_id, payload):
        if self.save_error is not None:
            raise self.save_error
        self.saved.append(dict(payload))
        self.character.update(payload)
        return dict(self.character)


class FakeItems:
    def __init__(self, inventory=None):
        self.inventory = dict(inventory or {})
        self.removed = []

    def get_active_deck(self, character_id):
        return {"cards": DECK_KEYS}

    def remove_from_inventory(self, character_id, item_id, quantity=1):
        if self.inventory.get(item_id, 0) < quantity:
            return False
        self.inventory[item_id] -= quantity
        self.removed.append((character_id, item_id, quantity))
        return True


def make_service(inventory=None, **overrides):
    database = FakeDatabase(character_payload(**overrides))
    items = FakeItems(inventory)
    return ArenaService(database, items), database, items


def start_kobold(service, seed=1):
    return service.start(USER_ID, CHARACTER_ID, "kobold", now=NOW, seed=seed)


def finish_draft(service, session):
    state = service.active(CHARACTER_ID, now=NOW)
    while state["phase"] in ("draft", "draw_choice"):
        if state["phase"] == "draft":
            command = {"type": "draft", "card_key": state["draft_cards"][0]["key"]}
        else:
            command = {"type": "draw_choice", "card_key": state["draw_choices"][0]["key"]}
        state = service.action(USER_ID, CHARACTER_ID, session.session_id, command, now=NOW)["state"]


class ArenaStartTests(unittest.TestCase):
    def test_start_returns_draft_for_nearby_kobold(self):
        service, _, _ = make_service()
        state = start_kobold(service)
        self.assertEqual(state["phase"], "draft")
        self.assertEqual(service.active(CHARACTER_ID, now=NOW)["phase"], "draft")

    def test_start_is_limited_to_the_owner(self):
        service, _, _ = make_service()
        with self.assertRaises(arena.ArenaError):
            service.start(USER_ID + 1, CHARACTER_ID, "kobold", now=NOW, seed=1)

    def test_start_needs_world_map_zone(self):
        service, _, _ = make_service(zone="tavern")
        with self.assertRaises(arena.ArenaError):
            start_kobold(service)

    def test_start_needs_known_position_and_nearby_enemy(self):
        service, _, _ = make_service(position_x=None, position_y=None)
        with self.assertRaises(arena.ArenaError):
            start_kobold(service)
        service, _, _ = make_service(position_x=10 * TILE_SIZE + 24, position_y=10 * TILE_SIZE + 24)
        with self.assertRaises(arena.ArenaError):
            start_kobold(service)

    def test_camp_starts_from_two_tiles(self):
        camp_x, camp_y = arena.ENCOUNTERS["kobold_camp"]["tile"]
        service, _, _ = make_service(position_x=(camp_x + 2) * TILE_SIZE + 24, position_y=camp_y * TILE_SIZE + 24)
        self.assertEqual(service.start(USER_ID, CHARACTER_ID, "kobold_camp", now=NOW, seed=1)["phase"], "draft")
        service, _, _ = make_service(position_x=(camp_x + 3) * TILE_SIZE + 24, position_y=camp_y * TILE_SIZE + 24)
        with self.assertRaises(arena.ArenaError):
            service.start(USER_ID, CHARACTER_ID, "kobold_camp", now=NOW, seed=1)


class ArenaRewardTests(unittest.TestCase):
    def test_win_gives_xp_respawns_later_and_keeps_position(self):
        service, database, _ = make_service()
        start_kobold(service)
        session = service.registry.active(CHARACTER_ID, now=NOW)
        last = _autoplay(session, lambda command: service.action(
            USER_ID, CHARACTER_ID, session.session_id, command, now=NOW))
        finished = last["finished"]
        self.assertEqual(finished["result"], "win")
        self.assertEqual(finished["xp_awarded"], 10)
        self.assertIsNone(finished["xp_error"])
        self.assertNotIn("reward_request_id", finished)
        encounter_id, defeated, request_id = database.xp_calls[0]
        self.assertEqual((encounter_id, defeated), ("kobold", ("kobold",)))
        self.assertEqual(len(request_id), 32)
        self.assertNotIn("position_x", database.saved[-1])
        self.assertGreaterEqual(database.saved[-1]["hp"], 1)
        kobold = service.status(CHARACTER_ID, now=NOW)[0]
        self.assertEqual(kobold, {"source": "kobold", "alive": False, "respawn_in": KOBOLD_RESPAWN_SECONDS})
        with self.assertRaises(arena.ArenaError):
            service.start(USER_ID, CHARACTER_ID, "kobold", now=NOW + 30, seed=1)
        self.assertEqual(service.start(USER_ID, CHARACTER_ID, "kobold", now=NOW + KOBOLD_RESPAWN_SECONDS, seed=1)["phase"], "draft")

    def test_loss_moves_to_crystal_and_restores_max_hp(self):
        service, database, _ = make_service()
        finished = {
            "result": "loss", "encounter_id": "kobold", "defeated_npc_types": [],
            "enemy_count": 1, "player_hp": 0, "player_mp": 3, "reward_request_id": "a" * 32,
        }
        report = service.apply_rewards(USER_ID, CHARACTER_ID, finished, now=NOW)
        self.assertEqual(database.xp_calls, [])
        self.assertEqual(database.saved[-1]["hp"], 80)
        self.assertEqual(database.saved[-1]["mp"], 3)
        self.assertEqual((database.saved[-1]["position_x"], database.saved[-1]["position_y"]),
                         (float(RESPAWN_CRYSTAL["approach_pos"][0]), float(RESPAWN_CRYSTAL["approach_pos"][1])))
        self.assertEqual(database.saved[-1]["position_direction"], "s")
        self.assertEqual(report["xp_awarded"], 0)
        self.assertTrue(service.status(CHARACTER_ID, now=NOW)[0]["alive"])

    def test_teleport_keeps_hp_and_moves_to_crystal(self):
        service, database, _ = make_service()
        finished = {
            "result": "teleport", "encounter_id": "kobold", "defeated_npc_types": ["kobold"],
            "enemy_count": 1, "player_hp": 25, "player_mp": 4, "reward_request_id": "b" * 32,
        }
        service.apply_rewards(USER_ID, CHARACTER_ID, finished, now=NOW)
        self.assertEqual(database.xp_calls[0][1], ("kobold",))
        self.assertEqual(database.saved[-1]["hp"], 25)
        self.assertIn("position_x", database.saved[-1])

    def test_ancient_ent_stays_defeated(self):
        service, _, _ = make_service()
        finished = {
            "result": "win", "encounter_id": "ancient_ent", "defeated_npc_types": ["ancient_ent"],
            "enemy_count": 2, "player_hp": 40, "player_mp": 5, "reward_request_id": "c" * 32,
        }
        service.apply_rewards(USER_ID, CHARACTER_ID, finished, now=NOW)
        ent = [item for item in service.status(CHARACTER_ID, now=NOW + 10 ** 6) if item["source"] == "ancient_ent"][0]
        self.assertEqual(ent, {"source": "ancient_ent", "alive": False, "respawn_in": None})

    def test_xp_failure_is_reported_and_vitals_are_still_saved(self):
        service, database, _ = make_service()
        database.xp_error = ValueError("сбой начисления")
        finished = {
            "result": "win", "encounter_id": "kobold", "defeated_npc_types": ["kobold"],
            "enemy_count": 1, "player_hp": 40, "player_mp": 5, "reward_request_id": "d" * 32,
        }
        report = service.apply_rewards(USER_ID, CHARACTER_ID, finished, now=NOW)
        self.assertIn("сбой начисления", report["xp_error"])
        self.assertIsNone(report["save_error"])
        self.assertEqual(database.saved[-1]["hp"], 40)

    def test_save_failure_is_reported(self):
        service, database, _ = make_service()
        database.save_error = OSError("диск недоступен")
        finished = {
            "result": "loss", "encounter_id": "kobold", "defeated_npc_types": [],
            "enemy_count": 1, "player_hp": 0, "player_mp": 0, "reward_request_id": "e" * 32,
        }
        report = service.apply_rewards(USER_ID, CHARACTER_ID, finished, now=NOW)
        self.assertIn("диск недоступен", report["save_error"])


class ArenaItemAndStatusTests(unittest.TestCase):
    def test_battle_item_is_taken_from_inventory_before_use(self):
        service, database, items = make_service(inventory={4: 1})
        start_kobold(service)
        session = service.registry.active(CHARACTER_ID, now=NOW)
        finish_draft(service, session)
        battle = session.battle
        battle.player.hp = battle.player.max_hp - 10
        service.action(USER_ID, CHARACTER_ID, session.session_id, {"type": "item", "item_id": 4}, now=NOW)
        self.assertEqual(items.removed, [(CHARACTER_ID, 4, 1)])
        self.assertEqual(items.inventory[4], 0)
        self.assertEqual(battle.player.hp, battle.player.max_hp)

    def test_battle_item_without_inventory_changes_nothing(self):
        service, _, items = make_service(inventory={})
        start_kobold(service)
        session = service.registry.active(CHARACTER_ID, now=NOW)
        finish_draft(service, session)
        battle = session.battle
        battle.player.hp = battle.player.max_hp - 10
        hp_before = battle.player.hp
        with self.assertRaises(arena.ArenaError):
            service.action(USER_ID, CHARACTER_ID, session.session_id, {"type": "item", "item_id": 4}, now=NOW)
        self.assertEqual(items.removed, [])
        self.assertEqual(battle.player.hp, hp_before)

    def test_unknown_session_is_rejected(self):
        service, _, _ = make_service()
        with self.assertRaises(arena.ArenaError):
            service.action(USER_ID, CHARACTER_ID, "missing", {"type": "end_turn"}, now=NOW)

    def test_status_lists_every_encounter_as_json(self):
        service, _, _ = make_service()
        status = service.status(CHARACTER_ID, now=NOW)
        self.assertEqual([item["source"] for item in status], list(arena.ENCOUNTERS))
        self.assertTrue(all(item["alive"] for item in status))
        json.dumps(status)
        self.assertIsNone(service.active(CHARACTER_ID, now=NOW))


if __name__ == "__main__":
    unittest.main()
