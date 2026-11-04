import unittest

from core.world_rewards import npc_kill_xp


class NpcKillXpTests(unittest.TestCase):
    def test_rewards_are_per_enemy_and_summons_have_no_reward_type(self):
        self.assertEqual(npc_kill_xp("kobold", ["kobold"]), 3)
        self.assertEqual(npc_kill_xp("kobold_camp_3", ["kobold", "kobold", "kobold"]), 9)
        self.assertEqual(npc_kill_xp("ancient_ent", ["ancient_ent"]), 75)
        self.assertEqual(npc_kill_xp("dungeon_room_3", ["skeleton", "necromancer"]), 55)
        self.assertEqual(
            npc_kill_xp(
                "dungeon_room_5",
                ["skeleton_guard", "skeleton_guard", "skeleton_king"],
            ),
            240,
        )

    def test_rewards_cannot_exceed_or_change_the_encounter_roster(self):
        with self.assertRaisesRegex(ValueError, "Некорректный список"):
            npc_kill_xp("dungeon_room_1", ["skeleton", "skeleton", "skeleton"])
        with self.assertRaisesRegex(ValueError, "нельзя победить"):
            npc_kill_xp("dungeon_room_3", ["summon"])


if __name__ == "__main__":
    unittest.main()
