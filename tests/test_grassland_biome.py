import unittest
import xml.etree.ElementTree as ET

from core.map_catalog import (
    catalog_definitions,
    grassland_animations,
    grassland_tile_specs,
    overlay_keys,
)
from scripts.import_grassland_biome import _used_tiles


class GrasslandBiomeTests(unittest.TestCase):
    def test_used_tile_reader_includes_animation_frames_from_chunks(self):
        root = ET.fromstring(
            '<map><layer name="terrain"><data encoding="csv">'
            '<chunk x="0" y="0" width="3" height="1">11,0,12</chunk>'
            '</data></layer></map>'
        )
        tilesets = [{
            "name": "Ground_grass",
            "first_gid": 11,
            "end_gid": 20,
            "animations": {1: [{"tile_id": 4, "duration": 120}]},
        }]

        self.assertEqual(_used_tiles(root, tilesets), {"Ground_grass": {0, 1, 4}})

    def test_imported_tiles_are_registered_and_have_assets(self):
        specs = grassland_tile_specs()
        catalog = {
            item["item_key"]: item
            for item in catalog_definitions()
            if item["item_key"] in specs
        }

        self.assertGreater(len(specs), 1000)
        self.assertEqual(set(catalog), set(specs))
        self.assertTrue(all(item["asset"].startswith("grassland/") for item in catalog.values()))
        self.assertEqual(specs["grassland_water_coasts_0081"]["category"], "grass")
        self.assertTrue({
            key for key, spec in specs.items() if spec["layer"] == "overlay"
        }.issubset(overlay_keys()))
        self.assertTrue(set(grassland_animations()).issubset(specs))


if __name__ == "__main__":
    unittest.main()
