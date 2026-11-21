import unittest
from types import SimpleNamespace

from front_line.server.combat import apply_lifesteal, aura_lifesteal_percent


class ItemCombatEffectsTests(unittest.TestCase):
    def test_vampirism_aura_only_applies_to_selected_side_in_radius(self):
        fighter = SimpleNamespace(equipment={
            "ring": {"effects": {"aura": {
                "type": "vampirism",
                "target": "allies",
                "radius_px": 160,
                "lifesteal_percent": 25,
            }}},
        })
        self.assertEqual(aura_lifesteal_percent(fighter, "allies", 160), 25)
        self.assertEqual(aura_lifesteal_percent(fighter, "allies", 161), 0)
        self.assertEqual(aura_lifesteal_percent(fighter, "enemies", 80), 0)

    def test_lifesteal_heals_only_by_percent_of_damage_and_caps_at_max_hp(self):
        fighter = SimpleNamespace(hp=70, max_hp=100)
        self.assertEqual(apply_lifesteal(fighter, 40, 25), 10)
        self.assertEqual(fighter.hp, 80)
        self.assertEqual(apply_lifesteal(fighter, 100, 50), 20)
        self.assertEqual(fighter.hp, 100)


if __name__ == "__main__":
    unittest.main()
