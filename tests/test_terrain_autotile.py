import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from core.map_catalog import catalog_definitions, palette_group_decor, palette_group_layers, palette_groups
from core.terrain_autotile import (
    FULL_COVERAGE,
    SUBDIV,
    border_candidates,
    desired_coverage,
    is_full,
    pick_border_tile,
    small_tiles,
    tile_shape,
)


def _half(coverage, side):
    """Среднее покрытие половины тайла: top, bottom, left или right."""
    rows = [coverage[i * SUBDIV:(i + 1) * SUBDIV] for i in range(SUBDIV)]
    half = SUBDIV // 2
    parts = {
        "top": [v for row in rows[:half] for v in row],
        "bottom": [v for row in rows[half:] for v in row],
        "left": [v for row in rows for v in row[:half]],
        "right": [v for row in rows for v in row[half:]],
    }[side]
    return sum(parts) / len(parts)


class TerrainAutotileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.items = {item["item_key"]: item for item in catalog_definitions()}
        cls.assets = {key: item["asset"] for key, item in cls.items.items()}
        cls.group = palette_groups()[0]
        layers = {layer["role"]: layer for layer in palette_group_layers(cls.group)}
        cls.elevation = set(layers["elevation"]["cells"].values())
        cls.base = palette_group_decor(cls.group)["grass"]["base"]
        keys = sorted({cell["key"] for cell in cls.group["cells"]} - cls.elevation)
        cls.candidates = border_candidates(keys, cls.assets, cls.base[0])

    def _picked(self, road):
        key = pick_border_tile(self.candidates, desired_coverage(5, 5, road), random.Random(1))
        return key, tile_shape(self.assets[key])[0]

    def test_tile_shape_reports_coverage_per_subcell_and_colour(self):
        coverage, colour = tile_shape(self.assets[self.base[0]])
        self.assertEqual(len(coverage), SUBDIV * SUBDIV)
        self.assertTrue(is_full(coverage))
        self.assertEqual(len(colour), 3)

    def test_no_road_nearby_wants_full_grass(self):
        self.assertTrue(is_full(desired_coverage(5, 5, set())))
        self.assertTrue(is_full(desired_coverage(5, 5, {(9, 9), (1, 1)})))

    def test_road_side_is_where_grass_must_be_transparent(self):
        south = desired_coverage(5, 5, {(5, 6)})
        self.assertGreaterEqual(_half(south, "top"), FULL_COVERAGE)
        self.assertLess(_half(south, "bottom"), 0.2)
        west = desired_coverage(5, 5, {(4, 5)})
        self.assertGreaterEqual(_half(west, "right"), FULL_COVERAGE)
        self.assertLess(_half(west, "left"), 0.2)

    def test_candidates_are_grass_pieces_and_skip_elevation_and_full_tiles(self):
        keys = {key for key, _ in self.candidates}
        self.assertGreaterEqual(len(keys), 20)
        self.assertFalse(keys & self.elevation)
        self.assertTrue(all(not is_full(coverage) for _, coverage in self.candidates))

    def test_picked_edge_tile_is_transparent_on_the_road_side(self):
        for road, transparent, solid in (
            ({(5, 6)}, "bottom", "top"),
            ({(5, 4)}, "top", "bottom"),
            ({(4, 5)}, "left", "right"),
            ({(6, 5)}, "right", "left"),
        ):
            _, coverage = self._picked(road)
            self.assertLess(_half(coverage, transparent), _half(coverage, solid), (road, transparent))

    def test_corner_and_diagonal_cases_use_notched_pieces(self):
        _, diagonal = self._picked({(6, 6)})
        self.assertLess(sum(diagonal), 16)
        self.assertGreater(sum(diagonal), 12)
        _, bend = self._picked({(5, 6), (6, 5), (6, 6), (4, 6), (6, 4)})
        self.assertLess(sum(bend), 9)

    def test_small_tiles_split_into_border_pieces_and_flat_tone_variants_per_surface(self):
        for group in palette_groups():
            if group.get("layout") != 2:
                continue
            small = small_tiles(group, self.assets)
            self.assertEqual(set(small), {"ground", "grass"})
            for surface, parts in small.items():
                self.assertTrue(parts["pieces"] and parts["flat"], (group["title"], surface))
                self.assertTrue(all(is_full(tile_shape(self.assets[key])[0]) for key in parts["flat"]))
                self.assertTrue(all(not is_full(tile_shape(self.assets[key])[0]) for key in parts["pieces"]))
                self.assertEqual(len(parts["pieces"]), len(set(parts["pieces"])))

    def test_small_tiles_of_group_without_them_are_empty(self):
        self.assertEqual(small_tiles({"title": "t", "layout": 0, "cells": []}, self.assets), {})

    def test_choice_is_deterministic_for_a_seed_and_varies_between_equal_pieces(self):
        road = {(5, 6), (4, 6), (6, 6)}
        picks = {pick_border_tile(self.candidates, desired_coverage(5, 5, road), random.Random(seed)) for seed in range(30)}
        self.assertGreaterEqual(len(picks), 2)
        again = pick_border_tile(self.candidates, desired_coverage(5, 5, road), random.Random(3))
        self.assertEqual(again, pick_border_tile(self.candidates, desired_coverage(5, 5, road), random.Random(3)))


if __name__ == "__main__":
    unittest.main()
