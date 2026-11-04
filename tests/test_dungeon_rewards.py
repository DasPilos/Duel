import unittest

from core.dungeon_rewards import roll_dungeon_treasure


class FixedRolls:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


class DungeonTreasureTests(unittest.TestCase):
    def test_reward_rolls_are_independent_and_can_all_drop_together(self):
        rewards = roll_dungeon_treasure(FixedRolls(0.0))
        self.assertEqual(rewards["coins"], 830)
        self.assertEqual(
            [(item["item_id"], item["quantity"]) for item in rewards["items"]],
            [(901, 1), (902, 1), (901, 2), (903, 1), (904, 1), (905, 1), (906, 1)],
        )

    def test_guaranteed_coin_reward_is_separate_from_optional_item_rolls(self):
        rewards = roll_dungeon_treasure(FixedRolls(0.999))
        self.assertEqual(rewards, {"coins": 830, "items": []})


if __name__ == "__main__":
    unittest.main()
