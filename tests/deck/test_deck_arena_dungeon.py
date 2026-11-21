"""Подземелье на сервере: проход, порядок комнат, позиция у противника, итоги и состав боёв."""

import unittest

from deck.combat.arena_battle import NECROMANCER_DECK, SKELETON_GUARD_DECK, SKELETON_KING_DECK
from deck.map_config import TILE_SIZE
from deck.server import arena
from tests.deck.test_deck_arena_service import CHARACTER_ID, DECK_KEYS, NOW, USER_ID, finish_draft, make_service

ACTOR = arena.dungeon_actor_tile()


def room_position(tile):
    return tile[0] * TILE_SIZE + TILE_SIZE / 2, tile[1] * TILE_SIZE + TILE_SIZE / 2


def start_room(service, source, tile=(ACTOR[0] - 1, ACTOR[1])):
    x, y = room_position(tile)
    return service.start(USER_ID, CHARACTER_ID, source, seed=3, position_x=x, position_y=y)


def finished_report(result, source, **overrides):
    report = {
        "result": result,
        "encounter_id": source,
        "defeated_npc_types": [],
        "enemy_count": 2,
        "player_hp": 40,
        "player_mp": 5,
        "reward_request_id": "7d1b6a4e-0000-4000-8000-000000000001",
    }
    report.update(overrides)
    return report


class DungeonEntryTests(unittest.TestCase):
    def test_battle_needs_entering_the_dungeon_first(self):
        service, _, _ = make_service()
        with self.assertRaisesRegex(arena.ArenaError, "Сначала войдите"):
            start_room(service, "dungeon_room_1")

    def test_exit_forgets_the_run(self):
        service, _, _ = make_service()
        service.dungeon_enter(CHARACTER_ID)
        service.dungeon_exit(CHARACTER_ID)
        with self.assertRaisesRegex(arena.ArenaError, "Сначала войдите"):
            start_room(service, "dungeon_room_1")

    def test_active_battle_blocks_entering_and_leaving(self):
        service, _, _ = make_service()
        service.dungeon_enter(CHARACTER_ID)
        start_room(service, "dungeon_room_1")
        with self.assertRaisesRegex(arena.ArenaError, "завершите бой"):
            service.dungeon_enter(CHARACTER_ID)
        with self.assertRaisesRegex(arena.ArenaError, "завершите бой"):
            service.dungeon_exit(CHARACTER_ID)


class DungeonBattleStartTests(unittest.TestCase):
    def setUp(self):
        self.service, self.database, _ = make_service()
        self.service.dungeon_enter(CHARACTER_ID)

    def test_room_one_battle_starts_next_to_the_skeletons(self):
        view = start_room(self.service, "dungeon_room_1")
        self.assertEqual(view["source"], "dungeon_room_1")
        self.assertEqual(view["phase"], "draft")
        enemies = [unit for unit in view["units"] if unit["side"] == "enemy"]
        self.assertEqual([unit["name"] for unit in enemies], ["Скелет", "Скелет"])

    def test_player_must_stand_inside_the_room(self):
        with self.assertRaisesRegex(arena.ArenaError, "в комнате подземелья"):
            start_room(self.service, "dungeon_room_1", tile=(ACTOR[0] - 1, 10))

    def test_player_must_be_next_to_the_actor(self):
        with self.assertRaisesRegex(arena.ArenaError, "Подойдите ближе"):
            start_room(self.service, "dungeon_room_1", tile=(ACTOR[0] - 3, ACTOR[1]))

    def test_room_three_waits_for_room_one(self):
        with self.assertRaisesRegex(arena.ArenaError, "предыдущую комнату"):
            start_room(self.service, "dungeon_room_3")

    def test_cleared_room_cannot_be_started_again(self):
        self.service.apply_rewards(USER_ID, CHARACTER_ID, finished_report("win", "dungeon_room_1"), now=NOW)
        with self.assertRaisesRegex(arena.ArenaError, "уже пройдена"):
            start_room(self.service, "dungeon_room_1")
        view = start_room(self.service, "dungeon_room_3")
        self.assertEqual(view["source"], "dungeon_room_3")

    def test_room_three_has_a_necromancer_and_room_five_a_king(self):
        room_three = arena.start_session(
            self.database.get_character_for_battle(CHARACTER_ID)["character"], source="dungeon_room_3",
            position_x=room_position((ACTOR[0] - 1, ACTOR[1]))[0], position_y=room_position((ACTOR[0] - 1, ACTOR[1]))[1],
            deck_keys=DECK_KEYS, seed=5,
        ).battle
        names = [room_three.fighters[eid].name for eid in room_three.enemy_ids]
        self.assertEqual(len(names), 3)
        self.assertTrue(any("Некромансер" in name for name in names))
        self.assertIs(room_three.enemy_decks[room_three.enemy_ids[2]], NECROMANCER_DECK)

        room_five = arena.start_session(
            self.database.get_character_for_battle(CHARACTER_ID)["character"], source="dungeon_room_5",
            position_x=room_position((ACTOR[0] - 1, ACTOR[1]))[0], position_y=room_position((ACTOR[0] - 1, ACTOR[1]))[1],
            deck_keys=DECK_KEYS, seed=5,
        ).battle
        self.assertIs(room_five.enemy_decks[room_five.enemy_ids[0]], SKELETON_GUARD_DECK)
        self.assertIs(room_five.enemy_decks[room_five.enemy_ids[2]], SKELETON_KING_DECK)
        self.assertTrue(any("Король" in room_five.fighters[eid].name for eid in room_five.enemy_ids))


class DungeonRewardTests(unittest.TestCase):
    def setUp(self):
        self.service, self.database, _ = make_service(hp=60, mp=10)
        self.service.dungeon_enter(CHARACTER_ID)
        start_room(self.service, "dungeon_room_1")

    def test_win_keeps_hp_and_position_and_claims_xp_for_the_room(self):
        report = finished_report("win", "dungeon_room_1", defeated_npc_types=["skeleton", "skeleton"])
        result = self.service.apply_rewards(USER_ID, CHARACTER_ID, report, now=NOW)
        self.assertEqual(self.database.xp_calls[0][0], "dungeon_room_1")
        self.assertEqual(result["xp_awarded"], 20)
        saved = self.database.saved[-1]
        self.assertEqual(saved, {"hp": 40, "mp": 5})

    def test_loss_restores_hp_and_returns_to_the_entrance(self):
        self.service.apply_rewards(USER_ID, CHARACTER_ID, finished_report("loss", "dungeon_room_1"), now=NOW)
        saved = self.database.saved[-1]
        self.assertEqual(saved["hp"], 80)
        self.assertEqual(saved["position_x"], arena.DUNGEON_APPROACH_POSITION[0])
        self.assertEqual(saved["position_y"], arena.DUNGEON_APPROACH_POSITION[1])
        with self.assertRaisesRegex(arena.ArenaError, "Сначала войдите"):
            start_room(self.service, "dungeon_room_3")

    def test_teleport_only_moves_to_the_entrance_and_keeps_hp(self):
        self.service.apply_rewards(USER_ID, CHARACTER_ID, finished_report("teleport", "dungeon_room_1"), now=NOW)
        saved = self.database.saved[-1]
        self.assertNotIn("hp", saved)
        self.assertNotIn("mp", saved)
        self.assertEqual(saved["position_x"], arena.DUNGEON_APPROACH_POSITION[0])
        with self.assertRaisesRegex(arena.ArenaError, "Сначала войдите"):
            start_room(self.service, "dungeon_room_1")

    def test_dungeon_battles_do_not_respawn_world_encounters(self):
        self.service.apply_rewards(USER_ID, CHARACTER_ID, finished_report("win", "dungeon_room_1"), now=NOW)
        self.assertTrue(self.service.alive(CHARACTER_ID, "dungeon_room_1", NOW))
        self.assertTrue(self.service.alive(CHARACTER_ID, "kobold", NOW))


class DungeonFullRunTests(unittest.TestCase):
    def test_room_one_win_opens_room_three_for_a_new_battle(self):
        service, _, _ = make_service()
        service.dungeon_enter(CHARACTER_ID)
        session_view = start_room(service, "dungeon_room_1")
        self.assertEqual(session_view["source"], "dungeon_room_1")
        service.registry._remove(service.registry.active(CHARACTER_ID))
        service.apply_rewards(USER_ID, CHARACTER_ID, finished_report("win", "dungeon_room_1"), now=NOW)
        view = start_room(service, "dungeon_room_3")
        self.assertEqual(len([unit for unit in view["units"] if unit["side"] == "enemy"]), 3)


if __name__ == "__main__":
    unittest.main()
