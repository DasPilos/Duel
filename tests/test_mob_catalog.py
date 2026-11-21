import unittest

from core.mob_catalog import MOB_CATALOG, MOB_KEYS, PALETTE_MOB_CATALOG, palette_mob
from core.mob_profiles import mob_profiles


class MobCatalogTests(unittest.TestCase):
    def test_catalog_includes_every_current_lpc_palette_mob_group(self):
        keys = {mob["key"] for mob in MOB_CATALOG}

        self.assertEqual(len(keys), 80)
        self.assertIn("imp_vanilla", keys)
        self.assertIn("mob|goblin sprite-pack|g1", keys)
        self.assertIn(
            "mob|craftpix-net-415491-giant-rat-4-direction-pixel-character-sprite-pack|rat1",
            keys,
        )
        self.assertEqual(MOB_KEYS, frozenset(keys))

    def test_palette_mobs_have_existing_source_packs_and_combat_profiles(self):
        profiles = mob_profiles()

        for mob in PALETTE_MOB_CATALOG:
            with self.subTest(key=mob["key"]):
                self.assertTrue(mob["pack_path"].is_dir())
                self.assertTrue(mob["name"])
                self.assertIn(mob["key"], profiles)
                self.assertEqual(profiles[mob["key"]]["name"], mob["name"])
                self.assertIs(palette_mob(mob["key"]), mob)

    def test_unknown_key_is_not_a_palette_mob(self):
        self.assertIsNone(palette_mob("mob|not-a-pack|rat1"))


if __name__ == "__main__":
    unittest.main()
