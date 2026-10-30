import unittest

from client.map_editor_seed import (
    BRIDGE_KEY, DEAD_TREE_KEYS, GRASS_KEYS, LOG_KEYS, ROAD_KEYS, STUMP_KEYS, TREE_KEYS, WATER_KEYS,
    build_tower_seed_cells, decode_tiles,
)
from client.map_editor_state import MapEditorState
from server import map_editor


MAP_W, MAP_H = 12, 8
CATALOG = {item["item_key"]: item for item in map_editor.catalog_definitions()}


def make_terrain():
    return {
        "tiles": {
            "forest": [[5, 0, 2], [4, 4, 4]],
            "water": [[2, 0, 3]],
            "dry": [[0, 10, 11]],
            "paths": [[3, 0, 11]],
            "mountain": [[1, 8, 9]],
        },
        "props": [
            {"type": "stump", "tiles": [[7, 7]]},
            {"type": "log", "tiles": [[11, 6], [10, 6]]},
        ],
        "bridges": [{"tiles": [[x, y] for y in range(4, 7) for x in range(4, 9)]}],
    }


def make_cells(terrain=None):
    roles = {(8, 1): "rock_01", (9, 1): "rock_01"}
    return build_tower_seed_cells(terrain or make_terrain(), CATALOG, MAP_W, MAP_H, roles)


def objects_by_anchor(cells):
    return {(cell["x"], cell["y"]): cell["key"] for cell in cells if cell["layer"] == "object"}


class TowerSeedTests(unittest.TestCase):
    def test_decode_tiles_expands_row_spans(self):
        self.assertEqual(decode_tiles([[1, 2, 4]]), {(2, 1), (3, 1), (4, 1)})

    def test_seed_keys_exist_in_catalog(self):
        keys = GRASS_KEYS + WATER_KEYS + ROAD_KEYS + TREE_KEYS + DEAD_TREE_KEYS + STUMP_KEYS + LOG_KEYS + (BRIDGE_KEY,)
        missing = [key for key in keys if key not in CATALOG]
        self.assertEqual(missing, [])

    def test_seed_passes_server_validation_and_loads_without_loss(self):
        cells = make_cells()
        map_editor.validate_cells(cells, list(CATALOG.values()), MAP_W, MAP_H)
        state = MapEditorState(list(CATALOG.values()), cells, MAP_W, MAP_H)
        self.assertEqual(len(state.to_cells()), len(cells))

    def test_every_tile_gets_ground(self):
        cells = make_cells()
        ground = {(cell["x"], cell["y"]): cell["key"] for cell in cells if cell["layer"] == "ground"}
        self.assertEqual(len(ground), MAP_W * MAP_H)
        self.assertIn(ground[(0, 2)], WATER_KEYS)
        self.assertIn(ground[(0, 3)], ROAD_KEYS)
        self.assertIn(ground[(0, 0)], GRASS_KEYS)

    def test_forest_dry_and_mountain_objects(self):
        objects = objects_by_anchor(make_cells())
        self.assertIn(objects[(0, 5)], TREE_KEYS)
        self.assertIn(objects[(10, 0)], DEAD_TREE_KEYS)
        self.assertIn(objects[(11, 0)], DEAD_TREE_KEYS)
        self.assertEqual(objects[(8, 1)], "rock_01")
        self.assertEqual(objects[(9, 1)], "rock_01")

    def test_props_and_bridge_anchor_at_top_left(self):
        objects = objects_by_anchor(make_cells())
        self.assertIn(objects[(7, 7)], STUMP_KEYS)
        self.assertIn(objects[(10, 6)], LOG_KEYS)
        self.assertEqual(objects[(3, 3)], BRIDGE_KEY)

    def test_bridge_covers_forest_tile_without_tree(self):
        objects = objects_by_anchor(make_cells())
        self.assertNotIn((4, 4), objects)

    def test_seed_is_deterministic(self):
        self.assertEqual(make_cells(), make_cells())

    def test_seed_replaces_map_as_one_undo_step(self):
        state = MapEditorState(list(CATALOG.values()), [], MAP_W, MAP_H)
        state.replace_cells(make_cells())
        self.assertTrue(state.dirty)
        self.assertEqual(state.objects[(3, 3)], BRIDGE_KEY)
        self.assertTrue(state.undo())
        self.assertEqual(state.ground, {})
        self.assertEqual(state.objects, {})


if __name__ == "__main__":
    unittest.main()
