import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from core.map_catalog import catalog_definitions, palette_group_layers, palette_groups
from core.relief_tiling import WALL_ROWS, ReliefTiles, assemble, wall_below
from core.terrain_autotile import desired_coverage, tile_shape


class WallBelowTests(unittest.TestCase):
    def test_wall_is_rows_below_every_southern_edge_and_never_overlaps_plateau(self):
        plateau = {(x, y) for x in range(4) for y in range(3)}
        wall = wall_below(plateau)
        self.assertEqual(wall, {(x, y) for x in range(4) for y in range(3, 3 + WALL_ROWS)})
        self.assertFalse(wall & plateau)

    def test_notch_in_plateau_gets_wall_under_its_edge(self):
        plateau = {(x, y) for x in range(4) for y in range(3)} - {(1, 2)}
        wall = wall_below(plateau)
        self.assertIn((1, 2), wall)
        self.assertIn((1, 3), wall)
        self.assertFalse(wall & plateau)

    def test_empty_plateau_has_no_wall(self):
        self.assertEqual(wall_below(set()), set())


class ReliefAssemblyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.items = {item["item_key"]: item for item in catalog_definitions()}
        cls.assets = {key: item["asset"] for key, item in cls.items.items()}
        group = next(g for g in palette_groups() if g.get("mountain_top"))
        layer = next(l for l in palette_group_layers(group) if l["role"] == "mountain")
        keys = sorted(set(layer["cells"].values()))
        cls.plateau_keys = [k for k in keys if cls.items[k]["category"] == "grass"]
        cls.wall_keys = [k for k in keys if cls.items[k]["category"] != "grass"]
        cls.tiles = ReliefTiles(cls.plateau_keys, cls.wall_keys, cls.assets, dict(layer["cells"]))

    def _massif(self, seed=1, width=8, height=4):
        plateau = {(x, y) for x in range(width) for y in range(height)} - {(0, 0)}
        wall = wall_below(plateau)
        return plateau, wall, assemble(self.tiles, plateau, wall, random.Random(seed))

    def test_every_cell_gets_a_tile_of_its_own_kind(self):
        plateau, wall, state = self._massif()
        self.assertEqual(set(state), plateau | wall)
        for cell in plateau:
            self.assertIn(state[cell], self.plateau_keys)
        for cell in wall:
            self.assertIn(state[cell], self.wall_keys)

    def test_border_tiles_open_towards_the_outside(self):
        plateau, wall, state = self._massif()
        outside = {(x, y) for x in range(-3, 12) for y in range(-3, 10)} - plateau - wall
        for cell in (c for c in plateau | wall if c[0] == 0 and 1 <= c[1] <= 3):
            coverage = tile_shape(self.assets[state[cell]])[0]
            wanted = desired_coverage(cell[0], cell[1], outside)
            left = sum(coverage[row * 4] + coverage[row * 4 + 1] for row in range(4))
            right = sum(coverage[row * 4 + 2] + coverage[row * 4 + 3] for row in range(4))
            self.assertLess(left, right, cell)
            self.assertLess(left, 8.0 - 3.0, (cell, wanted))

    def test_assembly_is_deterministic_for_a_seed_and_varies_between_seeds(self):
        self.assertEqual(self._massif(3)[2], self._massif(3)[2])
        self.assertNotEqual(self._massif(3)[2], self._massif(4)[2])

    def test_adjacent_tiles_match_better_than_random_pairs(self):
        _, _, state = self._massif(2, 9, 5)
        cost, count = 0.0, 0
        for (x, y), key in state.items():
            if (x + 1, y) in state:
                cost += self.tiles.horizontal[key][state[(x + 1, y)]]
                count += 1
        rng = random.Random(1)
        pool = self.plateau_keys
        random_cost = sum(self.tiles.horizontal[rng.choice(pool)][rng.choice(pool)] for _ in range(300)) / 300
        self.assertLess(cost / count, random_cost)

    def test_empty_massif_gives_nothing(self):
        self.assertEqual(assemble(self.tiles, set(), set(), random.Random(1)), {})


if __name__ == "__main__":
    unittest.main()
