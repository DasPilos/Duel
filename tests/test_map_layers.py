import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from core.map_catalog import catalog_definitions
from core.map_layers import LAYER_NAMES, layer_of
from scenes.map_editor_scene import MAP_DIR, TREE_ANIMATIONS
from scenes.map_palette import Palette


class LayerMappingTests(unittest.TestCase):
    def test_categories_map_to_the_agreed_layers(self):
        expected = {"water": 0, "road": 1, "floor": 1, "grass": 2, "leaves": 3, "rock": 4}
        for category, layer in expected.items():
            self.assertEqual(layer_of({"kind": "ground", "category": category}), layer, category)

    def test_objects_have_no_layer(self):
        for category in ("tree", "old_tree", "bush", "stump", "log"):
            self.assertIsNone(layer_of({"kind": "object", "category": category}), category)

    def test_every_layer_has_a_name(self):
        self.assertEqual(sorted(LAYER_NAMES), [0, 1, 2, 3, 4])

    def test_catalog_items_all_get_a_layer_or_none_for_objects(self):
        for item in catalog_definitions():
            layer = layer_of(item)
            if item["kind"] == "ground":
                self.assertIn(layer, range(5), item["item_key"])


class RoadLayerTests(unittest.TestCase):
    def test_all_road_items_and_road_decor_are_layer_one(self):
        from core.map_catalog import palette_group_decor, palette_groups
        catalog = {item["item_key"]: item for item in catalog_definitions()}
        road_decor = {
            key
            for group in palette_groups()
            for role, part in palette_group_decor(group).items()
            if "ground" in role
            for key in part["decor"]
        }
        self.assertTrue(road_decor)
        for key in road_decor:
            self.assertEqual(layer_of(catalog[key]), 1, key)
        from core.map_layers import block_layers
        for item in catalog.values():
            if item["kind"] == "ground" and item["category"] in ("road", "floor") and item["item_key"] not in block_layers():
                self.assertEqual(layer_of(item), 1, item["item_key"])

    def test_the_block_decides_the_layer_not_the_category(self):
        from core.map_layers import block_layers
        catalog = {item["item_key"]: item for item in catalog_definitions()}
        in_road_block = [k for k, layer in block_layers().items() if layer == 1 and catalog[k]["category"] == "grass"]
        in_grass_block = [k for k, layer in block_layers().items() if layer == 2 and catalog[k]["category"] == "road"]
        self.assertTrue(in_road_block)
        self.assertTrue(in_grass_block)
        for key in in_road_block:
            self.assertEqual(layer_of(catalog[key]), 1, key)
        for key in in_grass_block:
            self.assertEqual(layer_of(catalog[key]), 2, key)


class PaletteLayerDigitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        font = pygame.font.SysFont("arial", 14)
        catalog = catalog_definitions()
        cls.palette = Palette(catalog, MAP_DIR, font, font, max_panel=640, animations=TREE_ANIMATIONS)
        cls.water = next(item for item in catalog if layer_of(item) == 0)

    def test_palette_draws_the_digit_in_the_corner(self):
        surface = pygame.Surface((64, 64))
        rect = pygame.Rect(0, 0, 64, 64)
        self.palette._paint_cell(surface, rect, self.water, pygame.Surface((64, 64), pygame.SRCALPHA))
        corner = pygame.Rect(2, 64 - 20, 14, 18)
        pixels = {surface.get_at((x, y))[:3] for x in range(corner.left, corner.right) for y in range(corner.top, corner.bottom)}
        self.assertIn((20, 22, 28), pixels)  # подложка плашки с цифрой


if __name__ == "__main__":
    unittest.main()
