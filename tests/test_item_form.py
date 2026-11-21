import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from core import item_form, item_icons
from core.map_catalog import catalog_definitions
from scenes.item_form_dialog import ItemFormDialog, SLOT_LABELS
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

    def test_attack_range_and_area_are_saved_as_equipment_effects(self):
        form = {**club_form(), "attack_range": 8, "attack_area": 3}
        record = item_form.build_item(form, 1006)
        self.assertEqual(record["effects"]["attack_range"], 8)
        self.assertEqual(record["effects"]["attack_area"], 3)
        with self.assertRaisesRegex(ValueError, "Дальность атаки, клеток"):
            item_form.validate_form({**club_form(), "attack_range": item_form.MAX_ATTACK_DISTANCE + 1})
        with self.assertRaisesRegex(ValueError, "Площадь атаки, клеток"):
            item_form.validate_form({**club_form(), "attack_area": -1})

    def test_lifesteal_and_vampirism_aura_are_serialized(self):
        form = {
            **club_form(),
            "lifesteal_percent": 12,
            "aura_type": "vampirism",
            "aura_target": "allies",
            "aura_radius_px": 180,
            "aura_lifesteal_percent": 20,
        }
        record = item_form.build_item(form, 1007)
        self.assertEqual(record["effects"]["lifesteal_percent"], 12)
        self.assertEqual(record["effects"]["aura"], {
            "type": "vampirism",
            "target": "allies",
            "radius_px": 180,
            "lifesteal_percent": 20,
        })
        with self.assertRaisesRegex(ValueError, "Радиус ауры, пикселей"):
            item_form.validate_form({**club_form(), "aura_radius_px": item_form.MAX_AURA_RADIUS + 1})
        with self.assertRaisesRegex(ValueError, "Вампиризм ауры, %"):
            item_form.validate_form({**club_form(), "aura_lifesteal_percent": 101})
        with self.assertRaisesRegex(ValueError, "Выберите цель ауры"):
            item_form.validate_form({**club_form(), "aura_target": "everyone"})

    def test_missing_fields_take_defaults(self):
        clean = item_form.validate_form({"name": "Меч", "slot": "weapon"})
        self.assertEqual(clean["requirements"]["strength"], 0)
        self.assertEqual(clean["crit_power"], item_form.DEFAULT_CRIT_POWER)

    def test_ring_item_uses_one_generic_slot_for_both_loadout_positions(self):
        self.assertNotIn("ring_2", item_form.ITEM_FORM_SLOTS)
        clean = item_form.validate_form({"name": "Кольцо", "slot": "ring_2"})
        self.assertEqual(clean["slot"], "ring")
        self.assertEqual(item_form.build_item({"name": "Кольцо", "slot": "ring_2"}, 1008)["equip_slot"], "ring")

    def test_invalid_values_are_rejected_with_a_message(self):
        with self.assertRaisesRegex(ValueError, "Форма предмета должна быть объектом"):
            item_form.validate_form([])
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

    def test_ring_slot_label_is_shared(self):
        self.assertEqual(SLOT_LABELS["ring"], "Кольца")
        self.assertNotIn("ring_2", SLOT_LABELS)

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
