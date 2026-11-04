import unittest

from server import coop, presence


class CoopPartyTests(unittest.TestCase):
    def setUp(self):
        self._presence = dict(presence.PRESENCE)
        self._parties = dict(coop.PARTIES)
        self._invites = dict(coop.INVITES)
        presence.PRESENCE.clear()
        coop.PARTIES.clear()
        coop.INVITES.clear()
        self._add_player(1, 0)
        self._add_player(2, 0)
        self._add_player(3, 0)
        self._add_player(4, 0)

    def tearDown(self):
        presence.PRESENCE.clear()
        presence.PRESENCE.update(self._presence)
        coop.PARTIES.clear()
        coop.PARTIES.update(self._parties)
        coop.INVITES.clear()
        coop.INVITES.update(self._invites)

    @staticmethod
    def _add_player(character_id, tile_x):
        presence.update_presence(
            f"coop-test-{character_id}",
            character_id,
            {
                "id": character_id,
                "name": f"Игрок {character_id}",
                "position_x": tile_x * coop.TILE_SIZE + 5,
                "position_y": 5,
            },
            "world_map",
        )

    def test_party_invite_acceptance_caps_party_at_three(self):
        first = coop.create_invite(1, 2)
        self.assertTrue(coop.respond_invite(2, first["invite"]["id"], True)["accepted"])
        second = coop.create_invite(1, 3)
        self.assertTrue(coop.respond_invite(3, second["invite"]["id"], True)["accepted"])
        with self.assertRaisesRegex(ValueError, "трёх"):
            coop.create_invite(1, 4)

    def test_invite_requires_players_on_same_tile(self):
        self._add_player(4, 3)
        with self.assertRaisesRegex(ValueError, "одном тайле"):
            coop.create_invite(1, 4)

    def test_acceptance_rechecks_that_players_remain_on_the_same_tile(self):
        invitation = coop.create_invite(1, 2)["invite"]
        self._add_player(2, 4)
        with self.assertRaisesRegex(ValueError, "том же тайле"):
            coop.respond_invite(2, invitation["id"], True)


if __name__ == "__main__":
    unittest.main()
