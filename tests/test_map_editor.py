import unittest

from server import map_editor
from core.map_catalog import (
    catalog_definitions, terrain_layer_keys, water_decor_requires_water_keys,
)

MAP_W = 16
MAP_H = 16


class MapCatalogDefinitionTests(unittest.TestCase):
    def test_catalog_keys_are_unique_and_cover_objects(self):
        catalog = map_editor.catalog_definitions()
        keys = [item["item_key"] for item in catalog]

        self.assertEqual(len(keys), len(set(keys)))
        kinds = {item["kind"] for item in catalog}
        object_categories = {item["category"] for item in catalog if item["kind"] == "object"}
        ground_categories = {item["category"] for item in catalog if item["kind"] == "ground"}
        self.assertEqual(kinds, {"ground", "object"})
        self.assertTrue({"tree", "stump", "log", "old_tree", "bush"} <= object_categories)
        self.assertIn("rock", ground_categories)

    def test_water_tiles_block_and_some_grass_does_not(self):
        catalog = map_editor.catalog_definitions()

        water = [item for item in catalog if item["category"] == "water"]
        grass = [item for item in catalog if item["category"] == "grass"]

        self.assertTrue(water and all(item["blocks"] for item in water))
        self.assertTrue(any(not item["blocks"] for item in grass))

    def test_crystals_are_blocking_objects_from_crystal_folder(self):
        catalog = map_editor.catalog_definitions()

        crystals = [item for item in catalog if item["category"] == "crystal"]

        self.assertEqual(len(crystals), 40)
        self.assertTrue(all(item["kind"] == "object" and item["blocks"] for item in crystals))
        self.assertTrue(all(item["asset"].startswith("crystals/") for item in crystals))

    def test_crystals_have_four_growth_stages_per_color(self):
        catalog = map_editor.catalog_definitions()

        stages = {}
        for item in catalog:
            if item["category"] == "crystal":
                color, stage = item["item_key"].rsplit("_", 1)
                stages.setdefault(color, []).append(int(stage))

        self.assertEqual(len(stages), 10)
        self.assertTrue(all(sorted(values) == [1, 2, 3, 4] for values in stages.values()))

    def test_bushes_are_individual_objects_from_bush_folder(self):
        catalog = catalog_definitions()
        bushes = [item for item in catalog if item["asset"].startswith("bushes/")]

        self.assertEqual(len(bushes), 40)
        self.assertTrue(all(item["kind"] == "object" and item["category"] == "bush" for item in bushes))
        self.assertTrue(all(not item["blocks"] for item in bushes))
        stages = {}
        decorations = []
        for item in bushes:
            prefix, _, stage = item["item_key"].rpartition("_")
            if prefix.startswith("bush_") and stage in {"1", "2", "3"}:
                stages.setdefault(prefix, []).append(int(stage))
            else:
                decorations.append(item)
        self.assertEqual(len(stages), 12)
        self.assertTrue(all(sorted(values) == [1, 2, 3] for values in stages.values()))
        self.assertEqual(len(decorations), 4)

    def test_animals_are_blocking_objects_from_animals_folder(self):
        catalog = catalog_definitions()
        animals = [item for item in catalog if item["asset"].startswith("animals/")]

        self.assertEqual(
            {item["item_key"] for item in animals},
            {
                "animal_buffalo", "animal_buffalo_cub", "animal_cat", "animal_colt",
                "animal_dog", "animal_donkey", "animal_drake", "animal_drake_water",
                "animal_duck", "animal_duck_water", "animal_duckling", "animal_duckling_water",
            },
        )
        self.assertTrue(all(item["kind"] == "object" and item["category"] == "animal" for item in animals))
        self.assertTrue(all(item["blocks"] for item in animals))
        waterfowl = [item for item in animals if item["item_key"].endswith("_water")]
        self.assertEqual(len(waterfowl), 3)
        self.assertTrue(all(item["asset"].endswith("_water.png") for item in waterfowl))


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

    def test_waterfowl_must_be_on_water_regardless_of_cell_order(self):
        catalog = [
            {"item_key": "water", "kind": "ground", "category": "water", "footprint_w": 1, "footprint_h": 1},
            {"item_key": "grass", "kind": "ground", "category": "grass", "footprint_w": 1, "footprint_h": 1},
            {"item_key": "animal_duck_water", "kind": "object", "category": "animal",
             "footprint_w": 1, "footprint_h": 1},
            {"item_key": "animal_duck", "kind": "object", "category": "animal",
             "footprint_w": 1, "footprint_h": 1},
        ]
        cells = [
            {"layer": "object", "x": 2, "y": 2, "key": "animal_duck_water"},
            {"layer": "ground", "x": 2, "y": 2, "key": "water"},
        ]
        self.assertEqual(
            map_editor.validate_cells(cells, catalog, MAP_W, MAP_H),
            [("object", 2, 2, "animal_duck_water"), ("ground", 2, 2, "water")],
        )
        with self.assertRaisesRegex(ValueError, "только на тайлах воды"):
            map_editor.validate_cells(
                [{"layer": "object", "x": 2, "y": 2, "key": "animal_duck_water"}],
                catalog, MAP_W, MAP_H,
            )
        self.assertEqual(
            map_editor.validate_cells(
                [{"layer": "object", "x": 2, "y": 2, "key": "animal_duck"}],
                catalog, MAP_W, MAP_H,
            ),
            [("object", 2, 2, "animal_duck")],
        )

    def test_water_effects_must_be_over_ground_water(self):
        catalog = [
            {"item_key": "water", "kind": "ground", "category": "water", "footprint_w": 1, "footprint_h": 1},
            {"item_key": "ripple", "kind": "ground", "category": "water", "footprint_w": 1, "footprint_h": 1},
            {"item_key": "plank", "kind": "ground", "category": "floor", "footprint_w": 1, "footprint_h": 1},
        ]
        effect = {"layer": "overlay", "x": 2, "y": 2, "key": "ripple"}
        water = {"layer": "ground", "x": 2, "y": 2, "key": "water"}
        with self.assertRaisesRegex(ValueError, "Водные эффекты можно размещать только на тайлах воды"):
            map_editor.validate_cells([effect], catalog, MAP_W, MAP_H)
        self.assertEqual(
            map_editor.validate_cells([effect, water], catalog, MAP_W, MAP_H),
            [("overlay", 2, 2, "ripple"), ("ground", 2, 2, "water")],
        )
        with self.assertRaisesRegex(ValueError, "Водные эффекты можно размещать только на тайлах воды"):
            map_editor.validate_cells(
                [effect, water, {"layer": "infra", "x": 2, "y": 2, "key": "plank"}],
                catalog,
                MAP_W,
                MAP_H,
            )

    def test_winter_water_animation_must_be_over_ground_water(self):
        catalog = catalog_definitions()
        by_key = {item["item_key"]: item for item in catalog}
        effect_key = next(
            key for key in water_decor_requires_water_keys()
            if by_key[key]["category"] == "floor"
        )
        water_key = next(item["item_key"] for item in catalog if item["category"] == "water")
        effect = {"layer": "overlay", "x": 2, "y": 2, "key": effect_key}
        water = {"layer": "ground", "x": 2, "y": 2, "key": water_key}

        with self.assertRaisesRegex(ValueError, "Водные эффекты можно размещать только на тайлах воды"):
            map_editor.validate_cells([effect], catalog, MAP_W, MAP_H)
        self.assertEqual(
            map_editor.validate_cells([effect, water], catalog, MAP_W, MAP_H),
            [("overlay", 2, 2, effect_key), ("ground", 2, 2, water_key)],
        )

    def test_waterfowl_cannot_be_published_over_infrastructure(self):
        catalog = [
            {"item_key": "water", "kind": "ground", "category": "water", "footprint_w": 1, "footprint_h": 1},
            {"item_key": "plank", "kind": "ground", "category": "floor", "footprint_w": 1, "footprint_h": 1},
            {"item_key": "animal_duck_water", "kind": "object", "category": "animal",
             "footprint_w": 1, "footprint_h": 1},
        ]
        with self.assertRaisesRegex(ValueError, "только на тайлах воды"):
            map_editor.validate_cells(
                [
                    {"layer": "ground", "x": 2, "y": 2, "key": "water"},
                    {"layer": "infra", "x": 2, "y": 2, "key": "plank"},
                    {"layer": "object", "x": 2, "y": 2, "key": "animal_duck_water"},
                ],
                catalog, MAP_W, MAP_H,
            )


class TerrainLayerValidationTests(unittest.TestCase):
    def test_mountain_tiles_can_be_saved_on_relief_layer(self):
        key = min(terrain_layer_keys()["relief"])
        catalog = catalog_definitions()
        rows = map_editor.validate_cells(
            [{"layer": "relief", "x": 2, "y": 2, "key": key}],
            catalog, MAP_W, MAP_H,
        )
        self.assertEqual(rows, [("relief", 2, 2, key)])


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


class InfraLayerTests(unittest.TestCase):
    CATALOG = [
        {"item_key": "water", "kind": "ground", "category": "water", "footprint_w": 1, "footprint_h": 1, "blocks": True},
        {"item_key": "floor_1", "kind": "ground", "category": "floor", "footprint_w": 1, "footprint_h": 1, "blocks": False},
        {"item_key": "rock_1", "kind": "object", "category": "rock", "footprint_w": 1, "footprint_h": 1, "blocks": True},
    ]

    def test_infra_accepts_ground_items_only(self):
        rows = map_editor.validate_cells(
            [{"layer": "infra", "x": 0, "y": 0, "key": "floor_1"}], self.CATALOG, MAP_W, MAP_H
        )
        self.assertEqual(rows, [("infra", 0, 0, "floor_1")])
        with self.assertRaises(ValueError):
            map_editor.validate_cells(
                [{"layer": "infra", "x": 0, "y": 0, "key": "rock_1"}], self.CATALOG, MAP_W, MAP_H
            )

    def test_infra_over_water_makes_tile_walkable(self):
        cells = [
            {"layer": "ground", "x": 1, "y": 1, "key": "water"},
            {"layer": "infra", "x": 1, "y": 1, "key": "floor_1"},
        ]
        terrain = map_editor.terrain_from_cells(cells, self.CATALOG)
        self.assertEqual(terrain["water"], frozenset())
        self.assertEqual(terrain["impassable"], frozenset())

    def test_infra_keeps_landscape_under_it(self):
        cells = [
            {"layer": "ground", "x": 1, "y": 1, "key": "rock_1"},
            {"layer": "infra", "x": 1, "y": 1, "key": "floor_1"},
            {"layer": "overlay", "x": 2, "y": 1, "key": "rock_1"},
            {"layer": "infra", "x": 2, "y": 1, "key": "floor_1"},
        ]
        terrain = map_editor.terrain_from_cells(cells, self.CATALOG)
        self.assertEqual(terrain["mountain"], frozenset({(1, 1), (2, 1)}))
        self.assertEqual(terrain["impassable"], frozenset({(1, 1), (2, 1)}))

    def test_infra_over_overlay_water_makes_tile_walkable(self):
        cells = [
            {"layer": "ground", "x": 1, "y": 1, "key": "water"},
            {"layer": "overlay", "x": 1, "y": 1, "key": "water"},
            {"layer": "infra", "x": 1, "y": 1, "key": "floor_1"},
        ]
        terrain = map_editor.terrain_from_cells(cells, self.CATALOG)
        self.assertEqual(terrain["water"], frozenset())
        self.assertEqual(terrain["impassable"], frozenset())


if __name__ == "__main__":
    unittest.main()
