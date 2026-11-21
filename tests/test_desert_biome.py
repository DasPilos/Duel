import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
from PIL import Image

from core.map_catalog import (
    MAP_ASSETS,
    catalog_definitions,
    desert_animated_groups,
    desert_animations,
    desert_tile_specs,
    overlay_keys,
    water_decor_keys,
    water_decor_requires_water_keys,
)
from scenes.map_editor_scene import (
    BIOME_TABS,
    MapEditorScene,
    PALETTE_ANIMATIONS,
    WATER_BASE_KEYS,
)
from scenes.map_palette import Palette


class DesertBiomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.specs = desert_tile_specs()
        cls.animations = desert_animations()
        cls.groups = desert_animated_groups()
        cls.catalog = catalog_definitions()
        cls.catalog_by_key = {item["item_key"]: item for item in cls.catalog}
        font = pygame.font.Font(None, 16)
        cls.palette = Palette(
            cls.catalog,
            MAP_ASSETS,
            font,
            font,
            animations=PALETTE_ANIMATIONS,
        )

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_used_tiles_and_complete_source_sprites_are_catalogued(self):
        self.assertGreater(len(self.specs), 3000)
        self.assertTrue(set(self.specs).issubset(self.catalog_by_key))
        sprites = [
            spec for spec in self.specs.values()
            if spec.get("sheet") == "Objects_separately"
        ]
        self.assertEqual(len(sprites), 268)
        for spec in sprites:
            with self.subTest(key=spec["key"]):
                image_path = MAP_ASSETS / spec["asset"]
                self.assertTrue(image_path.is_file())
                with Image.open(image_path) as image:
                    self.assertEqual(
                        image.size,
                        (spec["source_size"][0] * 2, spec["source_size"][1] * 2),
                    )
                self.assertEqual(spec["representation"], "sprite")
                self.assertEqual(spec["editor_layer"], 7)
                self.assertIn(spec["object_type"], {
                    "trees", "plants", "rocks", "structures",
                    "remains", "terrain", "water", "other",
                })

    def test_tiled_animations_have_frames_and_palette_support(self):
        self.assertGreater(len(self.animations), 400)
        self.assertTrue(set(self.animations).issubset(self.specs))
        self.assertTrue(set(self.animations).issubset(PALETTE_ANIMATIONS))
        for key, animation in self.animations.items():
            with self.subTest(key=key):
                self.assertEqual(animation["frames"], len(animation["durations"]))
                self.assertEqual(animation["frames"], len(animation["tile_ids"]))
                self.assertTrue(all(duration > 0 for duration in animation["durations"]))

    def test_animated_compositions_remain_whole_palette_stamps(self):
        self.assertTrue(self.groups)
        for group in self.groups:
            entries = self.palette.compound_entries(group["key"])
            self.assertEqual(
                {(x, y, key, layer) for x, y, key, layer in entries},
                {
                    (cell["x"], cell["y"], cell["key"], cell["layer"])
                    for cell in group["cells"]
                },
            )
            for cell in group["cells"]:
                self.assertIn(cell["key"], self.catalog_by_key)

    def test_water_and_elevation_tiles_use_their_editor_layers(self):
        water_keys = {
            key for key, spec in self.specs.items()
            if spec.get("water_decor")
        }
        base_water_keys = {
            key for key, spec in self.specs.items()
            if (
                spec["sheet"] == "Water_coasts"
                and spec["category"] == "water"
                and spec["layer"] == "ground"
            )
        }
        elevation_keys = {
            key for key, spec in self.specs.items()
            if spec["layer"] == "elevation"
        }
        self.assertTrue(water_keys)
        self.assertTrue(elevation_keys)
        self.assertTrue(water_keys.issubset(overlay_keys()))
        self.assertTrue(water_keys.issubset(water_decor_keys()))
        self.assertTrue(water_keys.issubset(water_decor_requires_water_keys()))
        self.assertTrue(all(self.catalog_by_key[key]["blocks"] for key in elevation_keys))
        self.assertTrue(all(self.catalog_by_key[key]["editor_layer"] == 2 for key in water_keys))
        self.assertTrue(base_water_keys)
        self.assertTrue(base_water_keys.issubset(WATER_BASE_KEYS))
        self.assertFalse(water_keys & WATER_BASE_KEYS)
        scene = MapEditorScene(None, self.catalog, lambda: False)
        self.assertEqual(scene._artist_layer_for_item(next(iter(base_water_keys))), 0)
        self.assertEqual(scene._artist_layer_for_item(next(iter(water_keys))), 1)

    def test_desert_has_its_own_editor_tab_and_palette(self):
        scene = MapEditorScene(None, self.catalog, lambda: False)
        self.assertIn(("desert", "Пустыня"), BIOME_TABS)
        self.assertTrue(scene.biome_catalogs["desert"])
        self.assertTrue(all(
            item["item_key"].startswith("desert_")
            for item in scene.biome_catalogs["desert"]
        ))
        self.assertFalse(any(
            item["item_key"].startswith("desert_")
            for item in scene.biome_catalogs["forest"]
        ))
        self.assertTrue(any(
            title.startswith("Пустыня ·")
            for title, _clusters in self.palette._sections
        ))


if __name__ == "__main__":
    unittest.main()
