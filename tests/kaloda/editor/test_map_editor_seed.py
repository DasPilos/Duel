import unittest

from kaloda.editor.catalog import catalog_definitions
from kaloda.editor.seed import build_world_seed_cells, decode_tiles
from kaloda.editor.state import MapEditorState
from kaloda.server import map_editor

MAP_W, MAP_H = 12, 8
CATALOG = {item["item_key"]: item for item in catalog_definitions()}


def make_terrain(tiles=None, props=()):
    """Ответ /api/kaloda/map/terrain опубликованной карты: наборы тайлов строками [y, x_начало, x_конец]."""
    sets = {"water": [], "paths": [], "floor": [], "mountain": [], "forest": [], "dry": []}
    sets.update(tiles or {})
    return {"width_tiles": MAP_W, "height_tiles": MAP_H, "tiles": sets, "props": list(props)}


def seed(terrain=None):
    return build_world_seed_cells(terrain or make_terrain(), CATALOG, MAP_W, MAP_H)


def ground_at(cells):
    return {(c["x"], c["y"]): c["key"] for c in cells if c["layer"] == "ground"}


def objects_at(cells):
    return {(c["x"], c["y"]): c["key"] for c in cells if c["layer"] == "object"}


class DecodeTests(unittest.TestCase):
    def test_row_ranges_expand_to_tiles(self):
        self.assertEqual(decode_tiles([[1, 2, 4]]), {(2, 1), (3, 1), (4, 1)})
        self.assertEqual(decode_tiles([]), set())


class WorldSeedTests(unittest.TestCase):
    def test_every_tile_gets_one_ground_key_from_the_catalog(self):
        cells = seed()
        ground = ground_at(cells)
        self.assertEqual(len(ground), MAP_W * MAP_H)
        for key in ground.values():
            self.assertEqual(CATALOG[key]["kind"], "ground")

    def test_terrain_sets_pick_their_catalog_categories(self):
        cells = ground_at(seed(make_terrain({
            "water": [[0, 0, 0]], "paths": [[0, 1, 1]], "floor": [[0, 2, 2]], "mountain": [[0, 3, 3]],
        })))
        self.assertEqual(CATALOG[cells[(0, 0)]]["category"], "water")
        self.assertEqual(CATALOG[cells[(1, 0)]]["category"], "road")
        self.assertEqual(CATALOG[cells[(2, 0)]]["category"], "floor")
        self.assertEqual(CATALOG[cells[(3, 0)]]["category"], "rock")
        self.assertEqual(CATALOG[cells[(4, 0)]]["category"], "grass")

    def test_forest_and_dry_tiles_become_trees_and_props_become_stumps_and_logs(self):
        objects = objects_at(seed(make_terrain({
            "forest": [[1, 3, 3]], "dry": [[2, 5, 5]],
        }, props=[{"type": "stump", "tiles": [[7, 7]]}, {"type": "log", "tiles": [[9, 0]]}])))
        self.assertEqual(CATALOG[objects[(3, 1)]]["category"], "tree")
        self.assertEqual(CATALOG[objects[(5, 2)]]["category"], "old_tree")
        self.assertEqual(CATALOG[objects[(7, 7)]]["category"], "stump")
        self.assertEqual(CATALOG[objects[(9, 0)]]["category"], "log")

    def test_seed_is_deterministic(self):
        terrain = make_terrain({"forest": [[0, 0, 5]], "water": [[3, 2, 8]]})
        self.assertEqual(seed(terrain), seed(terrain))

    def test_seed_passes_server_validation_and_loads_without_loss(self):
        cells = seed(make_terrain({"forest": [[0, 0, 3]], "water": [[2, 4, 6]], "dry": [[4, 8, 9]]}))
        rows = map_editor.validate_cells(cells, list(CATALOG.values()), MAP_W, MAP_H)
        self.assertEqual(len(rows), len(cells))
        state = MapEditorState(list(CATALOG.values()), cells, MAP_W, MAP_H)
        self.assertEqual(sorted(state.to_cells(), key=str), sorted(cells, key=str))

    def test_seed_replaces_map_as_one_undo_step(self):
        state = MapEditorState(list(CATALOG.values()), [], MAP_W, MAP_H)
        state.replace_cells(seed(make_terrain({"water": [[0, 0, 2]]})))
        self.assertEqual(len(state.ground), MAP_W * MAP_H)
        self.assertTrue(state.undo())
        self.assertEqual(state.ground, {})

    def test_objects_never_overlap(self):
        cells = seed(make_terrain({"forest": [[0, 0, 11], [1, 0, 11]], "dry": [[0, 0, 11]]}))
        positions = [(c["x"], c["y"]) for c in cells if c["layer"] == "object"]
        self.assertEqual(len(positions), len(set(positions)))


if __name__ == "__main__":
    unittest.main()
