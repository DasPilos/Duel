import tempfile
import unittest
from pathlib import Path

from kaloda.editor import mob_modes
from kaloda.editor.mobs import MOB_CATALOG, MOB_KINDS, mob_catalog
from kaloda.map_config import KOBOLD_RESPAWN_SECONDS
from kaloda.server import map_editor


class MobCatalogTests(unittest.TestCase):
    def test_kaloda_mob_kinds_are_the_five_world_enemies(self):
        self.assertEqual(MOB_KINDS, {"kobold", "kobold_camp", "ancient_ent", "skeleton", "necromancer"})
        self.assertEqual([mob["key"] for mob in mob_catalog()], [mob["key"] for mob in MOB_CATALOG])

    def test_kobold_camp_is_three_kobolds_in_one_fight(self):
        camp = next(mob for mob in MOB_CATALOG if mob["key"] == "kobold_camp")
        self.assertEqual(camp["members"], ("kobold", "kobold", "kobold"))

    def test_every_mob_has_a_name_and_a_hint(self):
        for mob in MOB_CATALOG:
            self.assertTrue(mob["name"] and mob["hint"], mob["key"])

    def test_catalog_copy_does_not_change_the_original(self):
        copied = mob_catalog()
        copied[0]["name"] = "changed"
        self.assertNotEqual(MOB_CATALOG[0]["name"], "changed")


class MobSettingsTests(unittest.TestCase):
    def test_defaults_are_valid_and_use_kaloda_stats(self):
        settings = mob_modes.default_settings("kobold")
        self.assertEqual(mob_modes.validate_settings(settings)["stats"]["harmony"], 2)
        self.assertEqual(settings["respawn_seconds"], KOBOLD_RESPAWN_SECONDS)
        self.assertEqual(mob_modes.free_points_for_level(1), 6)
        self.assertEqual(mob_modes.endurance_for_level(3), 4)

    def test_endurance_is_fixed_by_level_and_points_are_limited(self):
        settings = mob_modes.default_settings("skeleton")
        settings["stats"]["endurance"] = 9
        with self.assertRaises(ValueError):
            mob_modes.validate_settings(settings)
        settings = mob_modes.default_settings("skeleton")
        for key in mob_modes.ALLOCATABLE_STATS:
            settings["stats"][key] = 20
        with self.assertRaises(ValueError):
            mob_modes.validate_settings(settings)

    def test_saved_settings_are_written_to_the_given_folder_and_read_back(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            settings = mob_modes.default_settings("necromancer")
            settings["level"] = 2
            settings["stats"]["harmony"] = 3
            settings["stats"]["endurance"] = mob_modes.endurance_for_level(2)
            mob_modes.save_mob_settings("kaloda", "necromancer", settings, folder)
            self.assertTrue((folder / "kaloda.json").is_file())
            loaded = mob_modes.load_mob_settings("kaloda", "necromancer", folder)
            self.assertEqual((loaded["level"], loaded["stats"]["harmony"]), (2, 3))

    def test_unknown_mode_is_refused(self):
        with self.assertRaises(mob_modes.ModeFileError):
            mob_modes.load_mob_settings("tower", "kobold")

    def test_mob_folder_lives_next_to_the_editor(self):
        self.assertEqual(mob_modes.MODES_DIR.name, "mob_modes")
        self.assertEqual(mob_modes.MODES_DIR.parent.name, "editor")


class ServerMobKindsTests(unittest.TestCase):
    def test_server_accepts_kaloda_kinds_and_keeps_legacy_kinds_for_old_maps(self):
        rows = map_editor.validate_mobs(
            [{"kind": "kobold_camp", "x": 1, "y": 1}, {"kind": "imp_sword", "x": 2, "y": 2}], 16, 16,
        )
        self.assertEqual(rows, [("kobold_camp", 1, 1), ("imp_sword", 2, 2)])

    def test_server_still_refuses_unknown_kinds(self):
        with self.assertRaises(ValueError):
            map_editor.validate_mobs([{"kind": "ghost", "x": 0, "y": 0}], 16, 16)


if __name__ == "__main__":
    unittest.main()
