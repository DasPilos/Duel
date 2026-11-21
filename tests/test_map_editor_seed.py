import unittest

from client.map_editor_seed import _pools, build_tower_seed_cells, decode_tiles
from client.map_editor_state import MapEditorState
from core.map_catalog import infrastructure_keys
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
    return build_tower_seed_cells(terrain or make_terrain(), CATALOG, MAP_W, MAP_H)


def objects_by_anchor(cells):
    return {(cell["x"], cell["y"]): cell["key"] for cell in cells if cell["layer"] == "object"}


def category(key):
    return CATALOG[key]["category"]


class TowerSeedTests(unittest.TestCase):
    def test_decode_tiles_expands_row_spans(self):
        self.assertEqual(decode_tiles([[1, 2, 4]]), {(2, 1), (3, 1), (4, 1)})

    def test_seed_uses_catalog_pools_only(self):
        self.assertTrue(all(_pools(CATALOG).values()), _pools(CATALOG))
        self.assertTrue(all(cell["key"] in CATALOG for cell in make_cells()))

    def test_seed_passes_server_validation_and_loads_without_loss(self):
        cells = make_cells()
        map_editor.validate_cells(cells, list(CATALOG.values()), MAP_W, MAP_H)
        state = MapEditorState(list(CATALOG.values()), cells, MAP_W, MAP_H)
        self.assertEqual(len(state.to_cells()), len(cells))

    def test_every_tile_gets_ground(self):
        cells = make_cells()
        ground = {(cell["x"], cell["y"]): cell["key"] for cell in cells if cell["layer"] == "ground"}
        relief = {(cell["x"], cell["y"]): cell["key"] for cell in cells if cell["layer"] == "relief"}
        self.assertEqual(len(ground), MAP_W * MAP_H)
        self.assertEqual(category(ground[(0, 2)]), "water")
        self.assertEqual(category(ground[(0, 0)]), "grass")
        self.assertEqual(category(ground[(8, 1)]), "grass")
        self.assertEqual(category(relief[(8, 1)]), "rock")

    def test_road_sits_on_overlay_and_grass_stays_below(self):
        cells = make_cells()
        overlay = {(cell["x"], cell["y"]): cell["key"] for cell in cells if cell["layer"] == "overlay"}
        ground = {(cell["x"], cell["y"]): cell["key"] for cell in cells if cell["layer"] == "ground"}
        self.assertEqual(set(overlay), {(x, 3) for x in range(MAP_W)})
        for x in range(MAP_W):
            self.assertEqual(category(overlay[(x, 3)]), "road")
            self.assertEqual(category(ground[(x, 3)]), "grass")

    def test_forest_dry_and_mountain_objects(self):
        objects = objects_by_anchor(make_cells())
        self.assertEqual(category(objects[(0, 5)]), "tree")
        self.assertEqual(category(objects[(10, 0)]), "old_tree")
        self.assertEqual(category(objects[(11, 0)]), "old_tree")
        self.assertNotIn((8, 1), objects)
        self.assertNotIn((9, 1), objects)

    def test_props_and_bridge_are_objects_and_infrastructure(self):
        cells = make_cells()
        objects = objects_by_anchor(cells)
        self.assertEqual(category(objects[(7, 7)]), "stump")
        self.assertEqual(category(objects[(10, 6)]), "log")
        infra = {(cell["x"], cell["y"]): cell["key"] for cell in cells if cell["layer"] == "infra"}
        self.assertTrue(infra)
        self.assertTrue(set(infra.values()) <= infrastructure_keys())

    def test_bridge_covers_forest_tile_without_tree(self):
        objects = objects_by_anchor(make_cells())
        self.assertNotIn((4, 4), objects)

    def test_seed_is_deterministic(self):
        self.assertEqual(make_cells(), make_cells())

    def test_seed_replaces_map_as_one_undo_step(self):
        state = MapEditorState(list(CATALOG.values()), [], MAP_W, MAP_H)
        state.replace_cells(make_cells())
        self.assertTrue(state.dirty)
        self.assertTrue(state.infra)
        self.assertTrue(state.undo())
        self.assertEqual(state.ground, {})
        self.assertEqual(state.infra, {})
        self.assertEqual(state.objects, {})


if __name__ == "__main__":
    unittest.main()
