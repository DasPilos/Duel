import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from core import item_form, item_icons
from core.map_catalog import catalog_definitions
from scenes.item_form_dialog import ItemFormDialog
from scenes.map_editor_scene import MapEditorScene


def club_form():
    form = item_form.default_form()
    form.update(name="Дубина", slot="weapon", damage_min=3, damage_max=10, hp=20)
    form["requirements"]["strength"] = 6
    return form


class ItemFormBuildTests(unittest.TestCase):
    def test_club_record_follows_the_catalog_convention(self):
        record = item_form.build_item(club_form(), 1001)
        self.assertEqual(record["id"], 1001)
        self.assertEqual(record["name"], "Дубина")
        self.assertEqual(record["equip_slot"], "weapon")
        self.assertEqual(record["item_type"], "equipment")
        self.assertEqual(record["effects"], {"requirements": {"strength": 6}, "damage": [3, 10]})
        self.assertEqual(record["bonuses"], {"hp": 20})

    def test_percent_fields_go_to_effects_and_block_dodge_to_bonuses_too(self):
        form = club_form()
        form.update(block=5, dodge=3, crit=7, two_handed=True, level=3)
        record = item_form.build_item(form, 1002)
        self.assertEqual(record["effects"]["block"], 5)
        self.assertEqual(record["effects"]["crit"], 7)
        self.assertTrue(record["effects"]["two_handed"])
        self.assertEqual(record["effects"]["requirements"]["level"], 3)
        self.assertEqual(record["bonuses"]["block"], 5)
        self.assertEqual(record["bonuses"]["dodge"], 3)

    def test_default_crit_power_is_not_stored(self):
        record = item_form.build_item(club_form(), 1003)
        self.assertNotIn("crit_power", record["effects"])

    def test_missing_fields_take_defaults(self):
        clean = item_form.validate_form({"name": "Меч", "slot": "weapon"})
        self.assertEqual(clean["requirements"]["strength"], 0)
        self.assertEqual(clean["crit_power"], item_form.DEFAULT_CRIT_POWER)

    def test_invalid_values_are_rejected_with_a_message(self):
        with self.assertRaisesRegex(ValueError, "Укажите название"):
            item_form.validate_form({**club_form(), "name": "  "})
        with self.assertRaisesRegex(ValueError, "Урон «от» не может быть больше"):
            item_form.validate_form({**club_form(), "damage_min": 9, "damage_max": 3})
        with self.assertRaisesRegex(ValueError, "Блок, %"):
            item_form.validate_form({**club_form(), "block": 150})
        with self.assertRaisesRegex(ValueError, "Выберите слот"):
            item_form.validate_form({**club_form(), "slot": "tail"})


class ItemIconTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        for name in ("weapon_iron_sword", "shield_oak", "head_helm"):
            (self.folder / f"{name}.png").write_bytes(b"")
        patcher = patch.object(item_icons, "ITEM_ICON_DIR", self.folder)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_icon_list_is_filtered_by_slot_prefix(self):
        self.assertEqual(item_icons.icons_for_slot("weapon"), ["weapon_iron_sword"])
        self.assertEqual(item_icons.icons_for_slot("shield"), ["shield_oak"])
        self.assertEqual(item_icons.icons_for_slot("feet"), ["head_helm", "shield_oak", "weapon_iron_sword"])

    def test_chosen_icon_is_stored_and_unknown_icon_is_rejected(self):
        form = {**club_form(), "icon": "weapon_iron_sword"}
        self.assertEqual(item_form.build_item(form, 1004)["icon"], "weapon_iron_sword")
        with self.assertRaisesRegex(ValueError, "Иконка не найдена"):
            item_form.validate_form({**club_form(), "icon": "weapon_missing"})
        self.assertIsNone(item_form.build_item(club_form(), 1005)["icon"])


class ItemFormDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1920, 1080))

    def setUp(self):
        self.scene = MapEditorScene(None, catalog_definitions(), lambda: True)
        self.scene.has_map = True

    def click(self, pos):
        self.scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))

    def test_add_button_is_in_every_section_and_opens_the_form(self):
        for section in ("map", "npc", "spawn", "equip"):
            self.scene._set_section(section)
            self.assertLess(self.scene._add_item_rect().bottom, self.scene._list_top())
        self.click(self.scene._add_item_rect().center)
        self.assertIsInstance(self.scene.item_dialog, ItemFormDialog)

    def test_name_typing_and_save_without_server_keeps_the_form_open(self):
        self.click(self.scene._add_item_rect().center)
        dialog = self.scene.item_dialog
        dialog.focus = "name"
        for char in "Меч":
            dialog.handle_event(pygame.event.Event(pygame.KEYDOWN, key=0, mod=0, unicode=char))
        self.assertEqual(dialog.form["name"], "Меч")
        self.click(dialog._save_rect().center)
        self.assertIsNotNone(self.scene.item_dialog)
        self.assertIn("Нет входа", dialog.message)

    def test_escape_closes_the_form(self):
        self.click(self.scene._add_item_rect().center)
        self.scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode=""))
        self.assertIsNone(self.scene.item_dialog)


if __name__ == "__main__":
    unittest.main()
