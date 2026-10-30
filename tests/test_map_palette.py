import os
import unittest
import random
from collections import Counter
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from core.map_catalog import (
    DECOR_CHANCE,
    DECOR_MIN_DISTANCE,
    HIDDEN_CATEGORIES,
    TALL_ROLES,
    MAIN_TILE_SHARE,
    catalog_definitions,
    decor_fits,
    decor_spaced,
    palette_group_decor,
    palette_group_layers,
    palette_groups,
    palette_landscape,
    palette_hidden_keys,
    palette_sheets,
    pick_decor,
    tile_allows_objects,
)
from scenes.map_palette import COLUMNS, PANEL_MARGIN, PANEL_W_MIN, Palette

MAP_DIR = Path(__file__).resolve().parent.parent / "assets" / "map"


class PaletteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((10, 10))
        cls.catalog = catalog_definitions()
        font = pygame.font.Font(None, 16)
        cls.palette = Palette(cls.catalog, MAP_DIR, font, font, max_panel=640)

    def _cells(self):
        return [item["item_key"] for row in self.palette.rows if row.kind == "block" for _, item in row.cells]

    def test_every_catalog_item_is_shown_and_sample_tiles_are_not_duplicated(self):
        keys = self._cells()
        hidden = palette_hidden_keys(self.catalog)
        self.assertEqual(set(keys), {item["item_key"] for item in self.catalog} - hidden)
        placed = Counter(cell["key"] for group in palette_groups() for cell in group["cells"])
        shown = Counter(keys)
        for key, count in placed.items():
            self.assertEqual(shown[key], count, key)
        sheet_keys = {cell["key"] for sheet in palette_sheets() for cell in sheet["cells"]}
        self.assertFalse(sheet_keys & set(placed))

    def test_unused_rock_leaves_road_and_water_tiles_are_removed_from_catalog(self):
        self.assertEqual(palette_hidden_keys(self.catalog), set())
        by_key = {item["item_key"]: item for item in self.catalog}
        placed = {cell["key"] for group in palette_groups() for cell in group["cells"]}
        outside = {
            key for key, item in by_key.items() if item["kind"] == "ground" and item["category"] in HIDDEN_CATEGORIES
        }
        self.assertEqual(outside - placed, set())

    def test_artist_group_is_first_and_keeps_layout(self):
        group = palette_groups()[0]
        headers = [row for row in self.palette.rows if row.kind == "header"]
        self.assertEqual(headers[0].title, group["title"])
        first = next(row for row in self.palette.rows if row.kind == "block")
        tile = self.palette.tile
        placed = sorted((item["item_key"], rect.x // tile, rect.y // tile) for rect, item in first.cells)
        self.assertEqual(placed, sorted((cell["key"], cell["x"], cell["y"]) for cell in group["cells"]))

    def test_rows_hold_at_most_ten_tiles_and_panel_follows_zoom(self):
        palette = self.palette
        for tile in (16, 24):
            palette.set_tile(tile)
            limit = COLUMNS * tile
            self.assertTrue(all(row.size[0] <= limit for row in palette.rows if row.kind == "block"))
            self.assertEqual(palette.panel_width(), max(PANEL_W_MIN, limit + PANEL_MARGIN))
        palette.set_tile(20)

    def test_item_at_returns_group_tile(self):
        group = palette_groups()[0]
        cell = group["cells"][0]
        first = next(row for row in self.palette.rows if row.kind == "block")
        tile = self.palette.tile
        x = 12 + cell["x"] * tile + tile // 2
        y = first.top + 4 + cell["y"] * tile + tile // 2
        self.assertEqual(self.palette.item_at(x, y), cell["key"])

    def test_stamp_entries_follow_dragged_rectangle(self):
        group = palette_groups()[0]
        first = next(row for row in self.palette.rows if row.kind == "block")
        tile = self.palette.tile
        left = 12 + 1 * tile + 2
        top = first.top + 4 + 2 * tile + 2
        entries = self.palette.stamp_entries((left, top), (left + 2 * tile, top + tile))
        expected = {
            (cell["x"] - 1, cell["y"] - 2): cell["key"]
            for cell in group["cells"]
            if 1 <= cell["x"] <= 3 and 2 <= cell["y"] <= 3
        }
        self.assertEqual({(col, line): key for key, col, line in entries}, expected)

    def test_stamp_entries_ignore_headers(self):
        self.assertEqual(self.palette.stamp_entries((20, 5), (60, 20)), [])

    def test_forest_follows_layout_two_with_decor_on_top_and_base_blocks_below(self):
        group = palette_groups()[0]
        self.assertEqual(group["title"], FOREST_DRY)
        layers = palette_group_layers(group)
        self.assertEqual(
            [(layer["number"], layer["role"]) for layer in layers],
            [
                (1, "ground"), (2, "grass"), (None, "ground_decor"), (None, "grass_decor"),
                (None, "ground_small"), (None, "grass_small"), (3, "elevation"),
            ],
        )
        self.assertEqual(
            [(layer["x"], layer["y"], layer["w"], layer["h"]) for layer in layers],
            [(0, 10, 5, 5), (5, 10, 5, 5), (0, 0, 5, 10), (5, 0, 5, 10), (0, 15, 5, 4), (5, 15, 5, 4), (0, 20, 10, 12)],
        )
        self.assertEqual([len(layer["inner"]) for layer in layers], [9, 9, 18, 18, 0, 0, 0])
        for layer in layers:
            self.assertTrue(all(
                layer["x"] <= x < layer["x"] + layer["w"] and layer["y"] <= y < layer["y"] + layer["h"]
                for x, y in layer["cells"]
            ))

    def test_layers_use_only_blocks_that_have_tiles(self):
        group = {"title": "t", "cells": [{"key": "a", "x": 6, "y": 1}, {"key": "b", "x": 2, "y": 7}]}
        layers = palette_group_layers(group)
        self.assertEqual([layer["role"] for layer in layers], ["grass", "ground_decor"])
        self.assertEqual(layers[0]["cells"], {(6, 1): "a"})
        self.assertEqual(layers[1]["cells"], {(2, 7): "b"})

    def test_palette_labels_and_frames_layers_of_group(self):
        rows = self.palette.rows
        header = next(index for index, row in enumerate(rows) if row.kind == "header")
        caption = rows[header + 1]
        self.assertEqual(caption.kind, "caption")
        self.assertEqual([layer["role"] for _, layer in caption.cells], ["ground_decor", "grass_decor"])
        block = rows[header + 2]
        self.assertEqual(
            [role for _, role, _ in block.frames],
            ["ground", "grass", "ground_decor", "grass_decor", "ground_small", "grass_small", "elevation"],
        )
        tile = self.palette.tile
        self.assertEqual(
            [frame.topleft for frame, _, _ in block.frames],
            [(0, 10 * tile), (5 * tile, 10 * tile), (0, 0), (5 * tile, 0), (0, 15 * tile), (5 * tile, 15 * tile), (0, 20 * tile)],
        )
        self.assertEqual(
            [label for _, _, label in block.frames],
            ["1 · лесная дорога", "2 · лесная трава", None, None, "малые: дорога", "малые: трава", "3 · лесная возвышенность"],
        )

class SheetBlocksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((10, 10))
        font = pygame.font.Font(None, 16)
        cls.palette = Palette(catalog_definitions(), MAP_DIR, font, font, max_panel=640)

    def _headers(self):
        return [row for row in self.palette.rows if row.kind == "header"]

    def test_sheet_blocks_are_last_and_sample_stays_first(self):
        sheets = palette_sheets()
        headers = [row.title for row in self._headers()]
        self.assertEqual(headers[0], palette_groups()[0]["title"])
        self.assertEqual(headers[len(headers) - len(sheets):], [sheet["title"] for sheet in sheets])
        self.assertNotIn(headers[0], headers[1:])

    def test_sheet_blocks_keep_sheet_layout_and_fit_ten_columns(self):
        for sheet in palette_sheets():
            self.assertLessEqual(max(cell["x"] for cell in sheet["cells"]) + 1, 10, sheet["title"])
            positions = [(cell["x"], cell["y"]) for cell in sheet["cells"]]
            self.assertEqual(len(positions), len(set(positions)), sheet["title"])
            for cell in sheet["cells"]:
                row, col = (int(part) for part in cell["key"][4:].replace("_c", " ").split())
                first = sheet["cells"][0]
                first_row, first_col = (int(part) for part in first["key"][4:].replace("_c", " ").split())
                self.assertEqual((row - first_row, col - first_col), (cell["y"] - first["y"], cell["x"] - first["x"]))

    def test_sheet_tiles_do_not_overlap_between_blocks(self):
        keys = [cell["key"] for sheet in palette_sheets() for cell in sheet["cells"]]
        self.assertEqual(len(keys), len(set(keys)))


class ObjectPlacementRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.group = palette_groups()[0]
        cls.layers = {layer["role"]: layer for layer in palette_group_layers(cls.group)}
        cls.catalog = {item["item_key"]: item for item in catalog_definitions()}

    def test_layers_declare_where_objects_may_stand(self):
        self.assertFalse(self.layers["ground"]["objects_allowed"])
        self.assertTrue(self.layers["grass"]["objects_allowed"])
        self.assertFalse(self.layers["elevation"]["objects_allowed"])
        self.assertFalse(self.layers["ground_small"]["objects_allowed"])
        self.assertTrue(self.layers["grass_small"]["objects_allowed"])

    def test_elevation_tiles_forbid_objects_and_block_movement_except_listed_ones(self):
        walkable = set(self.group.get("elevation_passable", []))
        keys = set(self.layers["elevation"]["cells"].values())
        self.assertTrue(walkable and walkable <= keys)
        for key in keys:
            self.assertFalse(tile_allows_objects(key, self.catalog[key]["category"]), key)
            self.assertEqual(self.catalog[key]["blocks"], key not in walkable, key)

    def test_ground_layer_tiles_are_roads_for_objects(self):
        for key in self.layers["ground"]["cells"].values():
            self.assertFalse(tile_allows_objects(key, self.catalog[key]["category"]), key)

    def test_grass_layer_tiles_accept_trees_and_bushes(self):
        for key in self.layers["grass"]["cells"].values():
            self.assertTrue(tile_allows_objects(key, self.catalog[key]["category"]), key)

    def test_tiles_outside_layer_blocks_follow_category(self):
        in_blocks = {
            key for group in palette_groups() for layer in palette_group_layers(group) for key in layer["cells"].values()
        }
        outside = [key for key in self.catalog if key not in in_blocks and self.catalog[key]["kind"] == "ground"]
        grass = next(key for key in outside if self.catalog[key]["category"] == "grass")
        self.assertTrue(tile_allows_objects(grass, "grass"))
        self.assertEqual([key for key in outside if self.catalog[key]["category"] in ("water", "road")], [])


FOREST_DRY = "Лесной ландшафт · сухой лес"
FOREST_LIVE = "Лесной ландшафт · живой лес"


def _mountain():
    return next(group for group in palette_groups() if group["title"] == "Горный ландшафт")


class DecorRuleTests(unittest.TestCase):
    def test_forest_base_is_inside_blocks_five_and_six_and_decor_inside_blocks_one_to_four(self):
        group = palette_groups()[0]
        cells = {(cell["x"], cell["y"]): cell["key"] for cell in group["cells"]}
        decor = palette_group_decor(group)
        self.assertEqual(set(decor), {"ground", "grass"})
        for role, left in (("ground", 0), ("grass", 5)):
            base = {cells[(x, y)] for x in range(left + 1, left + 4) for y in range(11, 14)}
            inner_decor = {cells[(x, y)] for x in range(left + 1, left + 4) for y in (1, 2, 3, 6, 7, 8)}
            self.assertEqual(set(decor[role]["base"]), base)
            self.assertEqual(len(decor[role]["base"]), 9)
            self.assertEqual(set(decor[role]["decor"]), inner_decor - base)
            self.assertNotIn("main", decor[role])

    def test_mountain_follows_layout_two_like_forest(self):
        group = _mountain()
        tiles = {cell["key"] for cell in group["cells"]}
        decor = palette_group_decor(group)
        self.assertEqual(group["layout"], 2)
        self.assertEqual(set(decor), {"ground", "grass"})
        for role in ("ground", "grass"):
            self.assertTrue(decor[role]["base"])
            self.assertTrue(set(decor[role]["base"] + decor[role]["decor"]) <= tiles)
            self.assertFalse(set(decor[role]["base"]) & set(decor[role]["decor"]))

    def test_empty_base_block_takes_the_first_filled_decor_block_as_base(self):
        def block(left, top, prefix):
            return [{"key": f"{prefix}{x}{y}", "x": left + x, "y": top + y} for x in range(1, 4) for y in range(1, 4)]

        ring = [{"key": "ring0", "x": 0, "y": 10}, {"key": "ring1", "x": 5, "y": 10}]
        cells = ring + block(0, 0, "a") + block(0, 5, "b")
        decor = palette_group_decor({"title": "t", "layout": 2, "cells": cells})
        self.assertEqual(set(decor["ground"]["base"]), {f"a{x}{y}" for x in range(1, 4) for y in range(1, 4)})
        self.assertEqual(set(decor["ground"]["decor"]), {f"b{x}{y}" for x in range(1, 4) for y in range(1, 4)})
        grass_only = palette_group_decor({"title": "t", "layout": 2, "cells": ring + block(5, 0, "d")})
        self.assertEqual(set(grass_only), {"grass"})
        self.assertEqual(set(grass_only["grass"]["base"]), {f"d{x}{y}" for x in range(1, 4) for y in range(1, 4)})
        self.assertEqual(grass_only["grass"]["decor"], [])

    def test_layout_one_keeps_centre_tile_as_the_only_base(self):
        def block(left, top, prefix):
            return [{"key": f"{prefix}{x}{y}", "x": left + x, "y": top + y} for x in range(5) for y in range(5)]

        cells = block(0, 0, "a") + block(5, 0, "b") + block(0, 5, "c") + block(5, 5, "d")
        decor = palette_group_decor({"title": "t", "cells": cells})
        self.assertEqual(set(decor), {"ground", "grass"})
        self.assertEqual(decor["ground"]["main"], "a22")
        self.assertEqual(decor["ground"]["base"], ["a22"])
        inner_a = {f"a{x}{y}" for x in range(1, 4) for y in range(1, 4)} - {"a22"}
        inner_c = {f"c{x}{y}" for x in range(1, 4) for y in range(1, 4)}
        self.assertEqual(set(decor["ground"]["decor"]), inner_a | inner_c)
        self.assertEqual(decor["grass"]["main"], "b22")

    def test_group_without_layers_has_no_blocks_or_decor(self):
        cells = [{"key": f"k{x}{y}", "x": x, "y": y} for x in range(10) for y in range(12)]
        group = {"title": "t", "cells": cells, "layout": 0}
        self.assertEqual(palette_group_layers(group), [])
        self.assertEqual(palette_group_decor(group), {})

    def test_decor_needs_both_blocks_and_centre_tile(self):
        cells = [{"key": f"k{x}{y}", "x": x, "y": y} for x in range(5) for y in range(5)]
        self.assertEqual(palette_group_decor({"title": "t", "cells": cells}), {})
        both = cells + [{"key": f"d{x}{y}", "x": x, "y": y + 5} for x in range(5) for y in range(5)]
        self.assertEqual(set(palette_group_decor({"title": "t", "cells": both})), {"ground"})
        without_centre = [cell for cell in both if (cell["x"], cell["y"]) != (2, 2)]
        self.assertEqual(palette_group_decor({"title": "t", "cells": without_centre}), {})

    def test_main_tile_share_is_ninety_percent(self):
        self.assertEqual(MAIN_TILE_SHARE, 0.9)
        self.assertAlmostEqual(DECOR_CHANCE, 0.1)

    def test_decor_is_not_closer_than_three_tiles(self):
        self.assertEqual(DECOR_MIN_DISTANCE, 3)
        placed = {(5, 5): "d"}
        for near in ((6, 5), (7, 5), (7, 7), (5, 3), (4, 4)):
            self.assertFalse(decor_fits(*near, placed), near)
        for far in ((8, 5), (5, 8), (8, 8), (2, 2), (10, 5)):
            self.assertTrue(decor_fits(*far, placed), far)
        self.assertFalse(decor_fits(5, 5, placed))

    def test_decor_spaced_detects_violations(self):
        self.assertTrue(decor_spaced({}))
        self.assertTrue(decor_spaced({(0, 0): "a", (3, 0): "b", (0, 3): "a", (3, 3): "b"}))
        self.assertFalse(decor_spaced({(0, 0): "a", (2, 0): "b"}))
        self.assertFalse(decor_spaced({(0, 0): "a", (2, 2): "a"}))

    def test_pick_decor_is_rare_random_and_spaced(self):
        rng = random.Random(3)
        placed = {}
        cells = [(x, y) for x in range(60) for y in range(60)]
        rng.shuffle(cells)
        picked = [pick_decor(["a", "b"], x, y, placed, rng) for x, y in cells]
        share = sum(key is not None for key in picked) / len(cells)
        self.assertTrue(0.03 < share <= 0.10, share)
        self.assertEqual(set(placed.values()), {"a", "b"})
        self.assertTrue(decor_spaced(placed))

    def test_pick_decor_dense_field_fills_only_a_lattice(self):
        rng = random.Random(5)
        placed = {}
        for x in range(12):
            for y in range(12):
                pick_decor(["only"], x, y, placed, rng, chance=1.0)
        self.assertEqual(len(placed), 16)
        self.assertTrue(decor_spaced(placed))

    def test_pick_decor_chance_zero_or_no_keys_places_nothing(self):
        placed = {}
        self.assertIsNone(pick_decor(["a"], 0, 0, placed, random.Random(1), chance=0))
        self.assertIsNone(pick_decor([], 0, 0, placed, random.Random(1), chance=1))
        self.assertEqual(placed, {})


class MountainSampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((10, 10))
        cls.group = _mountain()
        cls.layers = {layer["role"]: layer for layer in palette_group_layers(cls.group)}
        cls.catalog = {item["item_key"]: item for item in catalog_definitions()}
        font = pygame.font.Font(None, 16)
        cls.palette = Palette(list(cls.catalog.values()), MAP_DIR, font, font, max_panel=640)

    def test_mountain_follows_same_block_convention_with_relief_layer(self):
        self.assertEqual(
            [(layer["number"], layer["role"]) for layer in self.layers.values()],
            [
                (1, "ground"), (2, "grass"), (None, "ground_decor"), (None, "grass_decor"),
                (None, "ground_small"), (None, "grass_small"), (4, "river"), (4, "mountain"),
            ],
        )
        self.assertEqual(
            [(layer["x"], layer["y"], layer["w"], layer["h"]) for layer in self.layers.values()],
            [
                (0, 10, 5, 5), (5, 10, 5, 5), (0, 0, 5, 10), (5, 0, 5, 10), (0, 15, 5, 4), (5, 15, 5, 4),
                (0, 33, 10, 11), (0, 44, 10, 20),
            ],
        )
        self.assertEqual(self.layers["ground"]["name"], "горная дорога")
        self.assertEqual(self.layers["river"]["name"], "горные реки")
        self.assertEqual(self.layers["mountain"]["name"], "горы")
        self.assertNotIn("elevation", self.layers)

    def test_mountains_are_impassable_and_take_no_objects(self):
        for key in set(self.layers["mountain"]["cells"].values()):
            self.assertTrue(self.catalog[key]["blocks"], key)
            self.assertFalse(tile_allows_objects(key, self.catalog[key]["category"]), key)
        self.assertEqual(len(self.layers["mountain"]["inner"]), 0)

    def test_base_tiles_come_from_blocks_five_and_six_and_are_walkable(self):
        decor = palette_group_decor(self.group)
        self.assertEqual({self.catalog[key]["category"] for key in decor["ground"]["base"]}, {"road"})
        for role in ("ground", "grass"):
            self.assertTrue(decor[role]["base"])
            self.assertFalse(any(self.catalog[key]["blocks"] for key in decor[role]["base"] + decor[role]["decor"]))

    def test_rivers_forbid_objects(self):
        for key in self.layers["river"]["cells"].values():
            self.assertFalse(tile_allows_objects(key, self.catalog[key]["category"]), key)
        for key in self.layers["grass"]["cells"].values():
            self.assertTrue(tile_allows_objects(key, self.catalog[key]["category"]), key)

    def test_palette_shows_forest_transition_mountain_in_this_order_with_all_frames(self):
        headers = [row.title for row in self.palette.rows if row.kind == "header"]
        self.assertEqual(headers[:4], [FOREST_DRY, FOREST_LIVE, "Переход лес горы", "Горный ландшафт"])
        index = headers.index("Горный ландшафт")
        position = next(i for i, row in enumerate(self.palette.rows) if row.kind == "header" and row.title == "Горный ландшафт")
        self.assertEqual(index, 3)
        block = self.palette.rows[position + 2]
        self.assertEqual(
            [(role, label) for _, role, label in block.frames][-2:],
            [("river", "4 · горные реки"), ("mountain", "4 · горы")],
        )

    def test_transition_is_a_plain_block_between_forest_and_mountain(self):
        groups = palette_groups()
        self.assertEqual([group["title"] for group in groups[:4]], [FOREST_DRY, FOREST_LIVE, "Переход лес горы", "Горный ландшафт"])
        transition = groups[2]
        self.assertEqual(transition["layout"], 0)
        self.assertEqual(palette_group_layers(transition), [])
        position = next(i for i, row in enumerate(self.palette.rows) if row.kind == "header" and row.title == "Переход лес горы")
        block = self.palette.rows[position + 1]
        self.assertEqual(block.kind, "block")
        self.assertEqual(block.frames, [])
        tile = self.palette.tile
        placed = sorted((item["item_key"], rect.x // tile, rect.y // tile) for rect, item in block.cells)
        self.assertEqual(placed, sorted((cell["key"], cell["x"], cell["y"]) for cell in transition["cells"]))

class PlainsAndInfrastructureTests(unittest.TestCase):
    def test_road_grass_decor_and_small_tiles_of_every_sample_are_walkable(self):
        catalog = {item["item_key"]: item for item in catalog_definitions()}
        tall = {
            key for group in palette_groups() for layer in palette_group_layers(group)
            if layer["role"] in TALL_ROLES for key in layer["cells"].values()
        }
        for group in palette_groups():
            for layer in palette_group_layers(group):
                if layer["role"] not in TALL_ROLES:
                    blocked = [key for key in layer["cells"].values() if catalog[key]["blocks"] and key not in tall]
                    self.assertEqual(blocked, [], (group["title"], layer["role"]))

    def test_plains_follow_layout_two_with_lakes_and_follow_the_mountains(self):
        titles = [group["title"] for group in palette_groups()]
        self.assertEqual(titles.index("Равнины"), titles.index("Горный ландшафт") + 1)
        plains = next(group for group in palette_groups() if group["title"] == "Равнины")
        self.assertEqual(plains["layout"], 2)
        layers = {layer["role"]: layer for layer in palette_group_layers(plains)}
        self.assertEqual((layers["river"]["number"], layers["river"]["y"]), (4, 21))
        self.assertNotIn("mountain", layers)
        small = {cell["key"] for layer in ("ground_small", "grass_small") for cell in plains["cells"]
                 if layers[layer]["y"] <= cell["y"] < layers[layer]["y"] + layers[layer]["h"]}
        catalog = {item["item_key"]: item for item in catalog_definitions()}
        self.assertFalse(any(catalog[key]["blocks"] for key in small))

    def test_infrastructure_with_bridge_is_a_plain_block(self):
        infrastructure = next(group for group in palette_groups() if group["title"] == "Инфраструктура")
        self.assertEqual(infrastructure["layout"], 0)
        self.assertEqual(palette_group_layers(infrastructure), [])


class ForestVariantsTests(unittest.TestCase):
    def test_forest_has_dry_template_first_and_live_template_second_with_a_note(self):
        variants = palette_landscape("Лесной ландшафт")
        self.assertEqual(list(variants), ["dry", "live"])
        self.assertEqual([group["title"] for group in variants.values()], [FOREST_DRY, FOREST_LIVE])
        self.assertEqual([group["title"] for group in palette_groups()[:2]], [FOREST_DRY, FOREST_LIVE])
        self.assertIn("пни", variants["dry"]["note"])
        self.assertIn("живой", variants["live"]["note"])

    def test_both_templates_follow_layout_two_with_the_same_geometry(self):
        shapes = []
        for group in palette_landscape("Лесной ландшафт").values():
            self.assertEqual(group["layout"], 2)
            layers = palette_group_layers(group)
            shapes.append([(layer["role"], layer["x"], layer["y"], layer["w"], layer["h"]) for layer in layers])
            decor = palette_group_decor(group)
            self.assertEqual([len(decor[role]["base"]) for role in ("ground", "grass")], [9, 9])
            self.assertTrue(all(0 <= cell["x"] < 10 for cell in group["cells"]))
        self.assertEqual(shapes[0], shapes[1])

    def test_landscape_without_variant_is_one_main_sample(self):
        self.assertEqual(list(palette_landscape("Горный ландшафт")), ["main"])
        self.assertEqual(palette_landscape("нет такого"), {})


if __name__ == "__main__":
    unittest.main()
