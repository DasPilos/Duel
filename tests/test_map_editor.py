import unittest

from server import map_editor

MAP_W = 16
MAP_H = 16


class MapCatalogDefinitionTests(unittest.TestCase):
    def test_catalog_keys_are_unique_and_cover_objects(self):
        catalog = map_editor.catalog_definitions()
        keys = [item["item_key"] for item in catalog]

        self.assertEqual(len(keys), len(set(keys)))
        kinds = {item["kind"] for item in catalog}
        categories = {item["category"] for item in catalog if item["kind"] == "object"}
        self.assertEqual(kinds, {"ground", "object"})
        self.assertTrue({"rock", "tree", "stump", "log", "bridge"} <= categories)

    def test_water_tiles_block_and_grass_does_not(self):
        catalog = {item["item_key"]: item for item in map_editor.catalog_definitions()}

        water = next(item for key, item in catalog.items() if item["category"] == "water")
        grass = next(item for key, item in catalog.items() if item["category"] == "grass")

        self.assertTrue(water["blocks"])
        self.assertFalse(grass["blocks"])


class ValidateCellsTests(unittest.TestCase):
    def setUp(self):
        self.catalog = [
            {"item_key": "grass_1", "kind": "ground", "footprint_w": 1, "footprint_h": 1},
            {"item_key": "rock_1", "kind": "object", "footprint_w": 1, "footprint_h": 1},
            {"item_key": "log_1", "kind": "object", "footprint_w": 2, "footprint_h": 1},
        ]

    def _validate(self, cells):
        return map_editor.validate_cells(cells, self.catalog, MAP_W, MAP_H)

    def test_valid_cells_are_returned_as_rows(self):
        rows = self._validate([
            {"layer": "ground", "x": 0, "y": 0, "key": "grass_1"},
            {"layer": "object", "x": 3, "y": 3, "key": "rock_1"},
        ])

        self.assertEqual(rows, [("ground", 0, 0, "grass_1"), ("object", 3, 3, "rock_1")])

    def test_rejects_unknown_item(self):
        with self.assertRaises(ValueError):
            self._validate([{"layer": "ground", "x": 0, "y": 0, "key": "missing"}])

    def test_rejects_item_on_wrong_layer(self):
        with self.assertRaises(ValueError):
            self._validate([{"layer": "ground", "x": 0, "y": 0, "key": "rock_1"}])

    def test_rejects_object_overlapping_wide_object(self):
        with self.assertRaises(ValueError):
            self._validate([
                {"layer": "object", "x": 2, "y": 2, "key": "log_1"},
                {"layer": "object", "x": 3, "y": 2, "key": "rock_1"},
            ])

    def test_rejects_footprint_outside_map(self):
        with self.assertRaises(ValueError):
            self._validate([{"layer": "object", "x": 15, "y": 0, "key": "log_1"}])

    def test_rejects_duplicate_anchor_on_same_layer(self):
        with self.assertRaises(ValueError):
            self._validate([
                {"layer": "ground", "x": 1, "y": 1, "key": "grass_1"},
                {"layer": "ground", "x": 1, "y": 1, "key": "grass_1"},
            ])


class OverlayLayerTests(unittest.TestCase):
    CATALOG = [
        {"item_key": "water", "kind": "ground", "category": "water", "footprint_w": 1, "footprint_h": 1, "blocks": True},
        {"item_key": "plank", "kind": "ground", "category": "floor", "footprint_w": 1, "footprint_h": 1, "blocks": False},
        {"item_key": "rock_1", "kind": "object", "category": "rock", "footprint_w": 1, "footprint_h": 1, "blocks": True},
    ]

    def test_overlay_accepts_ground_items_only(self):
        rows = map_editor.validate_cells(
            [
                {"layer": "ground", "x": 0, "y": 0, "key": "water"},
                {"layer": "overlay", "x": 0, "y": 0, "key": "plank"},
            ],
            self.CATALOG, MAP_W, MAP_H,
        )
        self.assertEqual(rows, [("ground", 0, 0, "water"), ("overlay", 0, 0, "plank")])
        with self.assertRaises(ValueError):
            map_editor.validate_cells(
                [{"layer": "overlay", "x": 0, "y": 0, "key": "rock_1"}], self.CATALOG, MAP_W, MAP_H
            )

    def test_overlay_over_water_makes_tile_walkable(self):
        cells = [
            {"layer": "ground", "x": 1, "y": 1, "key": "water"},
            {"layer": "ground", "x": 2, "y": 1, "key": "water"},
            {"layer": "overlay", "x": 1, "y": 1, "key": "plank"},
        ]
        terrain = map_editor.terrain_from_cells(cells, self.CATALOG)
        self.assertEqual(terrain["water"], frozenset({(2, 1)}))
        self.assertEqual(terrain["impassable"], frozenset({(2, 1)}))


if __name__ == "__main__":
    unittest.main()
