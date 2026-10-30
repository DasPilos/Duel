import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from scenes.map_equipment_palette import EQUIP_SLOT_ORDER, EquipmentPalette, equipment_key


class EquipmentPaletteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((800, 600))
        cls.font = pygame.font.SysFont(None, 20)
        cls.small = pygame.font.SysFont(None, 16)

    def items(self):
        return [
            {"id": 23, "name": "Дубина", "equip_slot": "weapon", "icon": "weapon_club"},
            {"id": 24, "name": "Лук", "equip_slot": "weapon", "icon": "weapon_bow"},
            {"id": 39, "name": "Щит", "equip_slot": "shield", "icon": "shield_wooden"},
        ]

    def test_every_slot_gets_a_header_in_doll_order(self):
        palette = EquipmentPalette(self.items(), self.font, self.small, 240, 20)
        headers = [row.title for row in palette.rows if row.kind == "header"]
        self.assertEqual(len(headers), len(EQUIP_SLOT_ORDER))
        self.assertEqual(headers[0], "Голова")

    def test_click_on_a_cell_returns_its_item_key(self):
        palette = EquipmentPalette(self.items(), self.font, self.small, 240, 20)
        row = next(row for row in palette.rows if row.kind == "cells" and row.cells[0][1]["id"] == 23)
        rect, _item = row.cells[0]
        self.assertEqual(palette.item_at(rect.centerx, row.top + rect.centery), equipment_key(self.items()[0]))
        self.assertIsNone(palette.item_at(0, row.top))

    def test_zoom_changes_cell_size_and_height(self):
        palette = EquipmentPalette(self.items(), self.font, self.small, 240, 20)
        before = palette.height
        palette.set_tile(48)
        self.assertEqual(palette.tile, 48)
        self.assertGreater(palette.height, before)
        self.assertEqual(palette.item(equipment_key(self.items()[2]))["name"], "Щит")


if __name__ == "__main__":
    unittest.main()
