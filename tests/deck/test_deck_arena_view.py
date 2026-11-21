"""Вид арены для клиента: доска, клетки хода, существа, превью целей и маршрут розыгрыша карт."""

import json
import unittest
from unittest import mock

from deck.server import arena
from tests.deck.test_deck_arena_server import _finish_draft, start


def _board_tiles(battle):
    left, top, width, height = battle.arena_rect
    return [(x, y) for y in range(top, top + height) for x in range(left, left + width) if battle.in_arena((x, y))]


class ArenaBoardViewTests(unittest.TestCase):
    def setUp(self):
        self.session = start("kobold")
        _finish_draft(self.session)
        self.battle = self.session.battle

    def test_board_lists_every_arena_hex_and_player_stands_on_it(self):
        view = arena.session_view(self.session)
        self.assertEqual([tuple(tile) for tile in view["tiles"]], _board_tiles(self.battle))
        self.assertIn(list(self.battle.positions["player"]), view["tiles"])

    def test_reachable_tiles_are_offered_on_player_turn(self):
        view = arena.session_view(self.session)
        self.assertTrue(view["can_move"])
        self.assertTrue(view["reachable"])
        board = {tuple(tile) for tile in view["tiles"]}
        self.assertTrue(all(tuple(tile) in board for tile in view["reachable"]))

    def test_movement_is_withdrawn_after_the_move(self):
        destination = arena.session_view(self.session)["reachable"][0]
        arena.apply_command(self.session, {"type": "move", "tile": destination})
        view = arena.session_view(self.session)
        self.assertFalse(view["can_move"])
        self.assertEqual(view["reachable"], [])
        self.assertTrue(view["moved"])

    def test_hand_playable_cards_carry_previews_and_others_do_not(self):
        view = arena.session_view(self.session)
        self.assertTrue(view["hand"])
        for card in view["hand"]:
            if card["playable"]:
                self.assertIn("preview", card)
                self.assertEqual(
                    set(card["preview"]),
                    {"targets", "aim_tiles", "tiles", "transfer_tiles"},
                )
            else:
                self.assertNotIn("preview", card)

    def test_previewed_tiles_stay_on_board(self):
        view = arena.session_view(self.session)
        board = {tuple(tile) for tile in view["tiles"]}
        for card in view["hand"]:
            preview = card.get("preview") or {}
            for tile in preview.get("aim_tiles", []) + preview.get("tiles", []):
                self.assertIn(tuple(tile), board)

    def test_units_list_player_and_living_enemies(self):
        view = arena.session_view(self.session)
        ids = [unit["id"] for unit in view["units"]]
        self.assertEqual(ids[0], "player")
        for enemy_id in self.battle.alive_enemies():
            self.assertIn(enemy_id, ids)
        self.assertIn(view["target"], ids)
        self.assertEqual(view["target_distance"], self.battle.distance())

    def test_view_is_json_serializable_with_board_fields(self):
        view = json.loads(json.dumps(arena.session_view(self.session)))
        for key in ("tiles", "obstacles", "barriers", "traps", "grave_soil", "reachable", "hand_limit"):
            self.assertIn(key, view)

    def test_boss_wolf_is_drawn_as_enemy_unit(self):
        session = start("ancient_ent")
        _finish_draft(session)
        view = arena.session_view(session)
        wolves = [unit for unit in view["units"] if "Волк" in unit["name"]]
        self.assertTrue(wolves)
        self.assertTrue(all(unit["side"] == "enemy" for unit in wolves))


class ArenaPlayRoutingTests(unittest.TestCase):
    def setUp(self):
        self.session = start("kobold")
        _finish_draft(self.session)
        self.battle = self.session.battle
        self.battle.play_card = mock.Mock(return_value={"effect_text": "тест"})
        self.enemy = self.battle.alive_enemies()[0]

    def _play(self, command, role):
        with mock.patch.object(arena, "card_role", return_value=role):
            return arena.apply_command(self.session, {"type": "play", "card_index": 0, **command})

    def _call(self):
        args, kwargs = self.battle.play_card.call_args
        return args[1], kwargs["destination"], kwargs["aim_tile"]

    def test_summon_passes_the_chosen_tile_as_target(self):
        tile = self._board_pick()
        self._play({"tile": list(tile)}, "summon")
        self.assertEqual(self._call(), (tile, None, None))

    def test_summon_accepts_destination_as_tile_for_older_clients(self):
        tile = self._board_pick()
        self._play({"destination": list(tile)}, "summon")
        self.assertEqual(self._call(), (tile, None, None))

    def test_tile_card_keeps_tile_target(self):
        tile = self._board_pick()
        self._play({"tile": list(tile)}, "tile")
        self.assertEqual(self._call(), (tile, None, None))

    def test_enemy_hex_becomes_aim_when_card_has_area(self):
        aim = (3, 4)
        with mock.patch.object(self.battle, "aoe_aim_tile_for_target", return_value=aim):
            self._play({"target": self.enemy}, "enemy")
        self.assertEqual(self._call(), (None, None, aim))

    def test_single_target_attack_falls_back_to_enemy_id(self):
        with mock.patch.object(self.battle, "aoe_aim_tile_for_target", return_value=None):
            self._play({"target": self.enemy}, "enemy")
        self.assertEqual(self._call(), (self.enemy, None, None))

    def test_explicit_aim_tile_is_passed_through(self):
        self._play({"aim_tile": [5, 6]}, "enemy")
        self.assertEqual(self._call(), (None, None, (5, 6)))

    def test_attack_on_unknown_unit_is_rejected(self):
        with self.assertRaises(arena.ArenaError):
            self._play({"target": "player"}, "enemy")
        self.battle.play_card.assert_not_called()

    def test_unit_target_for_ally_or_self_cards_is_kept_as_id(self):
        self._play({"target": "player"}, "self")
        self.assertEqual(self._call(), ("player", None, None))

    def _board_pick(self):
        return sorted(self.battle.summon_tiles())[0]


if __name__ == "__main__":
    unittest.main()
