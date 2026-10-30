import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from core.mob_profiles import NPC_KEYS  # noqa: E402
from core import mob_modes, settings  # noqa: E402
from scenes.map_editor_ui import EquipmentDialog, MobParamsDialog  # noqa: E402
from scenes.world_map_scene import MOB_PROFILES, WorldMapScene  # noqa: E402
from server.items_database import ItemsDatabase  # noqa: E402
from tests.fixtures import create_test_database, drop_test_database  # noqa: E402


def _item_payload(item_id, name, equip_slot, bonuses=None):
    return {"id": item_id, "name": name, "equip_slot": equip_slot, "bonuses": bonuses or {}}


def _scene():
    return WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=None))


class PygameTestCase(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)

    def tearDown(self):
        pygame.quit()


class PlayerOverheadWithoutCharacterTests(PygameTestCase):
    def test_player_is_drawn_when_session_character_is_none(self):
        scene = WorldMapScene(SimpleNamespace(character=None, client=None))
        scene._draw_player_character(pygame.display.get_surface())


class MobEquipmentTests(PygameTestCase):
    def setUp(self):
        super().setUp()
        self.kind = next(iter(MOB_PROFILES))

    def test_mob_profiles_are_only_editor_npcs_without_equipment_key(self):
        self.assertEqual(set(MOB_PROFILES), NPC_KEYS)
        for profile in MOB_PROFILES.values():
            self.assertNotIn("equipment", profile)

    def test_fighter_gets_equipment_from_server_snapshot(self):
        sword = _item_payload(20, "Железный меч", "weapon", {"strength": 1})
        shield = _item_payload(38, "Круглый щит", "shield", {"endurance": 2})
        fighter = _scene()._build_mob_fighter(self.kind, equipment={"weapon": sword, "shield": shield})

        self.assertEqual(fighter.equipment["weapon"]["name"], "Железный меч")
        self.assertEqual(fighter.equipment["shield"]["name"], "Круглый щит")
        self.assertEqual(fighter.equipment_stat_modifiers, {"strength": 1, "endurance": 2})

    def test_fighter_without_snapshot_equipment_has_no_gear(self):
        fighter = _scene()._build_mob_fighter(self.kind)
        self.assertEqual(fighter.equipment, {})
        self.assertEqual(fighter.equipment_stat_modifiers, {})

    def test_equipment_hp_bonus_raises_mob_max_hp(self):
        scene = _scene()
        plain = scene._build_mob_fighter(self.kind)
        armored = scene._build_mob_fighter(
            self.kind, equipment={"shield": _item_payload(39, "Деревянный щит", "shield", {"hp": 20})}
        )
        self.assertGreater(armored.max_hp, plain.max_hp)

    def test_snapshot_equipment_is_copied_not_shared(self):
        sword = _item_payload(20, "Железный меч", "weapon")
        fighter = _scene()._build_mob_fighter(self.kind, equipment={"weapon": sword})
        sword["name"] = "Изменён"
        self.assertEqual(fighter.equipment["weapon"]["name"], "Железный меч")


class MobEquipmentDialogTests(PygameTestCase):
    ITEMS = [
        _item_payload(20, "Железный меч", "weapon"),
        _item_payload(23, "Дубина", "weapon"),
        _item_payload(38, "Круглый щит", "shield"),
    ]

    def setUp(self):
        super().setUp()
        self.font = pygame.font.Font(None, 20)
        self.small = pygame.font.Font(None, 16)

    def _dialog(self, equipment, items=()):
        settings = mob_modes.default_settings(next(iter(MOB_PROFILES)))
        settings["equipment"] = equipment
        return MobParamsDialog(self.font, self.small, "Бес", "tower", settings, items)

    def _window(self, equipment, items):
        settings = mob_modes.default_settings(next(iter(MOB_PROFILES)))
        settings["equipment"] = equipment
        return EquipmentDialog(self.font, self.small, "Бес", settings["stats"], settings["level"], equipment, items)

    def test_equipment_window_lists_only_items_of_each_slot_with_none_first(self):
        window = self._window({}, self.ITEMS)
        self.assertEqual([None if item is None else item["id"] for item in window._eligible("weapon")], [None, 20, 23])
        self.assertEqual([None if item is None else item["id"] for item in window._eligible("shield")], [None, 38])

    def test_picking_an_item_in_the_window_sets_its_slot_and_none_clears_it(self):
        equipment = {}
        window = self._window(equipment, self.ITEMS)
        window.picker_slot = "weapon"
        picker = window._picker_rect()
        self.assertIsNone(window._pick(window._picker_row(picker, 1).center), None)
        self.assertEqual(equipment["weapon"], 20)
        window.picker_slot = "weapon"
        window._pick(window._picker_row(window._picker_rect(), 0).center)
        self.assertIsNone(equipment["weapon"])

    def test_offline_editor_keeps_saved_item_as_placeholder(self):
        dialog = self._dialog({"weapon": 99, "shield": None}, ())
        self.assertEqual(dialog.settings()["equipment"]["weapon"], 99)
        window = self._window({"weapon": 99}, ())
        window.draw(pygame.display.get_surface())

    def test_dialog_draws_with_equipment_rows_and_buttons(self):
        dialog = self._dialog({"weapon": 20, "shield": None}, self.ITEMS)
        dialog.draw(pygame.display.get_surface())
        self.assertEqual(dialog.handle_event(SimpleNamespace(type=pygame.MOUSEBUTTONDOWN, button=1, pos=(-1000, -1000))), None)


class MobEquipmentSettingsTests(unittest.TestCase):
    def _settings(self, equipment):
        settings = mob_modes.default_settings(next(iter(MOB_PROFILES)))
        settings["equipment"] = equipment
        return settings

    def test_valid_slots_are_kept_and_none_means_empty(self):
        result = mob_modes.validate_settings(self._settings({"weapon": 20, "shield": None}))
        self.assertEqual(result["equipment"]["weapon"], 20)
        self.assertEqual(set(result["equipment"]), set(mob_modes.MOB_EQUIPMENT_SLOTS))
        self.assertIsNone(result["equipment"]["shield"])

    def test_numeric_string_id_is_converted(self):
        result = mob_modes.validate_settings(self._settings({"weapon": "20", "shield": None}))
        self.assertEqual(result["equipment"]["weapon"], 20)

    def test_missing_equipment_defaults_to_empty_slots(self):
        settings = self._settings({})
        del settings["equipment"]
        self.assertEqual(mob_modes.validate_settings(settings)["equipment"], {slot: None for slot in mob_modes.MOB_EQUIPMENT_SLOTS})

    def test_unknown_slot_is_rejected(self):
        with self.assertRaises(ValueError):
            mob_modes.validate_settings(self._settings({"helmet": 5}))

    def test_non_positive_or_non_numeric_id_is_rejected(self):
        for bad in (0, -3, "abc"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                mob_modes.validate_settings(self._settings({"weapon": bad}))


class CatalogEndpointDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = create_test_database()
        cls.items = ItemsDatabase(cls.db)

    @classmethod
    def tearDownClass(cls):
        drop_test_database(cls.db)

    def test_returns_catalog_payloads_keyed_by_id(self):
        payloads = self.items.get_catalog_items([38, 23, 23])
        self.assertEqual(sorted(payloads), ["23", "38"])
        self.assertEqual(payloads["23"]["weight"], 5.0)
        self.assertEqual(payloads["23"]["equip_slot"], "weapon")
        self.assertEqual(payloads["38"]["weight"], 3.5)
        self.assertEqual(payloads["38"]["icon"], "left_hand_round_shield")

    def test_empty_request_returns_empty_mapping(self):
        self.assertEqual(self.items.get_catalog_items([]), {})

    def test_equipment_items_are_only_weapon_and_shield_ordered_by_id(self):
        items = self.items.get_equipment_items(["weapon", "shield"])
        ids = [item["id"] for item in items]
        self.assertEqual(ids, sorted(ids))
        self.assertTrue(all(item["equip_slot"] in {"weapon", "shield"} for item in items))
        self.assertIn(20, ids)
        self.assertIn(38, ids)
        self.assertNotIn(30, ids)

    def test_equipment_items_for_unknown_slot_is_empty(self):
        self.assertEqual(self.items.get_equipment_items(["helmet"]), [])


if __name__ == "__main__":
    unittest.main()
