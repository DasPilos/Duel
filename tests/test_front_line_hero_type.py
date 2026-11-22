import unittest
from types import SimpleNamespace
from unittest.mock import patch

from front_line.server.world_mobs import WorldService


def _player(profession):
    fighter = SimpleNamespace(hp=50, max_hp=60, mp=10, max_mp=20, profession_type=profession)
    return SimpleNamespace(
        character_id=5, fighter=fighter, x=1.0, y=2.0, facing=0, windup=0.0, windup_total=0.0,
        swing_id=0, backswing=0.0, attack_target=None, windup_target=None, dash=None,
        dash_cooldown=0.0, move_speed=10.0, carry_multiplier=1.0,
    )


class HeroTypeInSnapshotTests(unittest.TestCase):
    def test_player_payload_carries_the_drafted_class(self):
        service = WorldService.__new__(WorldService)
        with patch("front_line.server.world_mobs.get_attack_reach", return_value=1.0), \
                patch.object(WorldService, "_harvest_payload", return_value=None):
            payload = service._player_payload(_player("mage"))
        self.assertEqual(payload["type"], "mage")


if __name__ == "__main__":
    unittest.main()
