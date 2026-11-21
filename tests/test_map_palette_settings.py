import unittest

from server import map_palette


class MapPaletteSettingsTests(unittest.TestCase):
    def setUp(self):
        self.catalog = [
            {
                "item_key": "grass",
                "kind": "ground",
                "editor_layer": 3,
                "blocks": False,
            },
            {
                "item_key": "cliff",
                "kind": "ground",
                "editor_layer": 5,
                "blocks": True,
            },
            {
                "item_key": "tree",
                "kind": "object",
                "editor_layer": 7,
                "blocks": True,
            },
        ]

    def test_validates_palette_metadata_and_kind_compatible_layers(self):
        overrides = map_palette.validate_overrides(
            {
                "grass": {
                    "blocks": True,
                    "editor_layer": 5,
                    "palette_group": "Настроенная группа",
                    "palette_order": 2,
                    "palette_position": {"x": 4, "y": 2},
                    "generator_role": "random_decor",
                },
                "tree": {"editor_layer": 8},
            },
            self.catalog,
        )

        self.assertEqual(overrides["grass"]["editor_layer"], 5)
        self.assertEqual(overrides["grass"]["blocks"], True)
        self.assertEqual(overrides["grass"]["palette_position"], {"x": 4, "y": 2})
        self.assertEqual(overrides["tree"]["editor_layer"], 8)

    def test_rejects_invalid_palette_positions(self):
        for position in (
            {"x": 10, "y": 0},
            {"x": 0, "y": -1},
            {"x": True, "y": 0},
            {"x": 0, "y": 256},
            {"x": 1},
        ):
            with self.subTest(position=position):
                with self.assertRaises(ValueError):
                    map_palette.validate_overrides(
                        {"grass": {"palette_position": position}},
                        self.catalog,
                    )

    def test_rejects_assigning_ground_tiles_to_object_only_layers(self):
        with self.assertRaises(ValueError):
            map_palette.validate_overrides(
                {"grass": {"editor_layer": 7}},
                self.catalog,
            )

    def test_layer_change_removes_moved_tile_when_target_layer_is_occupied(self):
        cells = [
            {"layer": "ground", "x": 4, "y": 2, "key": "grass"},
            {"layer": "elevation", "x": 4, "y": 2, "key": "cliff"},
        ]
        updated = {"grass": {"editor_layer": 5}}

        remapped, conflicts, removed = map_palette.remap_cells(
            cells,
            self.catalog,
            {},
            updated,
            context="saved:12",
        )

        self.assertEqual(conflicts, [])
        self.assertEqual(
            remapped,
            [{"layer": "elevation", "x": 4, "y": 2, "key": "cliff"}],
        )
        self.assertEqual(
            removed,
            [{
                "layer": "elevation",
                "x": 4,
                "y": 2,
                "key": "grass",
                "source_layer": "ground",
            }],
        )

        remapped, conflicts, removed = map_palette.remap_cells(
            cells,
            self.catalog,
            {},
            updated,
            resolutions={"saved:12:elevation:4:2": "grass"},
            context="saved:12",
        )

        self.assertEqual(conflicts, [])
        self.assertEqual(
            remapped,
            [{"layer": "elevation", "x": 4, "y": 2, "key": "grass"}],
        )
        self.assertEqual(removed[0]["key"], "cliff")

    def test_same_cells_ignores_order_but_detects_layer_changes(self):
        cells = [
            {"layer": "object", "x": 8, "y": 9, "key": "tree"},
            {"layer": "ground", "x": 4, "y": 2, "key": "grass"},
        ]
        reordered = list(reversed(cells))
        remapped = [
            {"layer": "elevation", "x": 4, "y": 2, "key": "grass"},
            cells[0],
        ]

        self.assertTrue(map_palette.same_cells(cells, reordered))
        self.assertFalse(map_palette.same_cells(cells, remapped))


if __name__ == "__main__":
    unittest.main()
