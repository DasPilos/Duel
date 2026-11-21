import os
import unittest
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from core.map_catalog import (
    catalog_definitions,
    overlay_keys,
    winter_animated_groups,
    winter_animations,
    winter_tile_specs,
)
from client.map_editor_state import MapEditorState
from scripts.import_winter_biome import (
    IMPASSABLE_WATER_COVERAGE_THRESHOLD,
    WATER_COVERAGE_THRESHOLD,
    WATER_TILE_SHEETS,
    _has_impassable_open_water,
    _is_majority_open_water,
)
from server.map_editor import terrain_from_cells, validate_cells
from scenes.map_editor_scene import PALETTE_ANIMATIONS
from scenes.map_palette import BLOCK_MARK, PASSABLE_MARK, Palette, _series

from PIL import Image


MAP_DIR = Path(__file__).resolve().parent.parent / "assets" / "map"


class WinterBiomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.specs = winter_tile_specs()
        cls.catalog = {
            item["item_key"]: item
            for item in catalog_definitions()
            if item["item_key"] in cls.specs
        }
        cls._atlases = {}
        font = pygame.font.Font(None, 16)
        cls.palette = Palette(
            catalog_definitions(),
            MAP_DIR,
            font,
            font,
            animations=PALETTE_ANIMATIONS,
        )

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_imported_tiles_and_animations_are_in_the_catalog(self):
        self.assertEqual(set(self.catalog), set(self.specs))
        self.assertEqual(len(winter_animations()), 151)
        self.assertTrue(all((MAP_DIR / item["asset"]).is_file() for item in self.specs.values()))
        self.assertTrue({
            key for key, spec in self.specs.items() if spec["layer"] == "overlay"
        }.issubset(overlay_keys()))
        for key, animation in winter_animations().items():
            with self.subTest(key=key):
                self.assertIn(key, self.specs)
                self.assertEqual(animation["frames"], len(animation["durations"]))
                self.assertEqual(animation["frames"], len(animation["tile_ids"]))
                self.assertTrue(all(duration > 0 for duration in animation["durations"]))

    def test_removed_duplicate_ice_tiles_stay_out_of_the_catalog(self):
        tile_ids = {
            spec["tile_id"] for spec in self.specs.values()
            if spec["sheet"] == "Ice"
        }
        self.assertTrue({249, 273}.isdisjoint(tile_ids))

    def test_nonduplicate_winter_items_are_shown_in_the_palette(self):
        visible = {
            item["item_key"]
            for row in self.palette.rows
            if row.kind == "block"
            for _rect, item in row.cells
        }
        expected = {
            key for key, spec in self.specs.items()
            if not spec.get("palette_hidden", False)
        }
        self.assertTrue(expected.issubset(visible))

    def test_ice_and_cracks_share_one_artist_friendly_section(self):
        matching_headers = [
            index for index, row in enumerate(self.palette.rows)
            if row.kind == "header" and row.title == "Лёд и трещины"
        ]
        self.assertEqual(len(matching_headers), 1)
        header_index = matching_headers[0]
        following_header = next(
            (
                index for index in range(header_index + 1, len(self.palette.rows))
                if self.palette.rows[index].kind == "header"
            ),
            len(self.palette.rows),
        )
        section_rows = self.palette.rows[header_index + 1:following_header]
        self.assertFalse(any(row.kind == "subheader" for row in section_rows))
        shown = {
            item["item_key"]
            for row in section_rows
            if row.kind == "block"
            for _rect, item in row.cells
        }
        expected = {
            key for key, spec in self.specs.items()
            if spec["sheet"] in {"Ice", "cracks"}
            and not spec.get("palette_hidden", False)
            and spec.get("representation") != "sprite"
        }
        self.assertEqual(shown, expected)

    def test_open_water_cells_are_blocking_but_ice_cracks_are_walkable(self):
        catalog = {item["item_key"]: item for item in catalog_definitions()}
        open_water = [
            spec for spec in self.specs.values()
            if spec["sheet"].casefold() in WATER_TILE_SHEETS
            and _is_majority_open_water(self._source_tile(spec))
        ]
        self.assertTrue(open_water)
        self.assertTrue(all(catalog[spec["key"]]["category"] == "water" for spec in open_water))
        self.assertTrue(all(catalog[spec["key"]]["blocks"] for spec in open_water))
        for spec in open_water:
            cell = {"layer": "ground", "x": 1, "y": 1, "key": spec["key"]}
            terrain = terrain_from_cells([cell], list(catalog.values()))
            with self.subTest(key=spec["key"]):
                self.assertIn((1, 1), terrain["water"])
                self.assertIn((1, 1), terrain["impassable"])

        walkable = [spec for spec in self.specs.values() if spec["sheet"] == "cracks"]
        self.assertTrue(walkable)
        for spec in walkable:
            with self.subTest(key=spec["key"]):
                self.assertEqual(
                    catalog[spec["key"]]["blocks"],
                    _has_impassable_open_water(self._source_tile(spec)),
                )

    def test_catalog_water_category_matches_majority_of_full_tile_frame(self):
        catalog = {item["item_key"]: item for item in catalog_definitions()}
        visible = {
            item["item_key"]
            for row in self.palette.rows
            if row.kind == "block"
            for _rect, item in row.cells
        }
        relevant = [
            spec for spec in self.specs.values()
            if spec["sheet"].casefold() in WATER_TILE_SHEETS
            or spec["sheet"] == "cracks"
        ]
        self.assertTrue(relevant)
        for spec in relevant:
            has_majority_water = (
                spec["sheet"].casefold() in WATER_TILE_SHEETS
                and _is_majority_open_water(self._source_tile(spec))
            )
            with self.subTest(key=spec["key"]):
                self.assertEqual(spec["category"] == "water", has_majority_water)
                self.assertEqual(
                    catalog[spec["key"]]["blocks"],
                    has_majority_water
                    or (
                        spec["key"] in visible
                        and _has_impassable_open_water(self._source_tile(spec))
                    ),
                )

    def test_open_water_threshold_is_strictly_more_than_half_of_full_frame(self):
        tile = Image.new("RGBA", (16, 16), (120, 209, 237, 255))
        water_pixel = (32, 71, 139, 255)
        pixels = tile.load()
        for index in range(128):
            pixels[index % 16, index // 16] = water_pixel
        self.assertFalse(_is_majority_open_water(tile))
        pixels[0, 8] = water_pixel
        self.assertEqual(WATER_COVERAGE_THRESHOLD, 0.5)
        self.assertTrue(_is_majority_open_water(tile))

    def test_every_visible_palette_tile_with_over_30_percent_water_is_blocked_in_place(self):
        catalog = {item["item_key"]: item for item in catalog_definitions()}
        visible = {
            item["item_key"]
            for row in self.palette.rows
            if row.kind == "block"
            for _rect, item in row.cells
        }
        water_tiles = [
            spec for spec in self.specs.values()
            if spec["key"] in visible
            and spec.get("representation") != "sprite"
            and "columns" in spec
            and _has_impassable_open_water(self._source_tile(spec))
        ]
        self.assertGreater(len(water_tiles), 3)
        self.assertTrue(all(catalog[spec["key"]]["blocks"] for spec in water_tiles))
        self.assertTrue(all(spec["key"] in visible for spec in water_tiles))
        self.assertEqual(IMPASSABLE_WATER_COVERAGE_THRESHOLD, 0.3)

    def test_impassable_water_threshold_is_strictly_more_than_30_percent(self):
        tile = Image.new("RGBA", (10, 10), (120, 209, 237, 255))
        water_pixel = (32, 71, 139, 255)
        pixels = tile.load()
        for index in range(30):
            pixels[index % 10, index // 10] = water_pixel
        self.assertFalse(_has_impassable_open_water(tile))
        pixels[0, 3] = water_pixel
        self.assertTrue(_has_impassable_open_water(tile))

    def _source_tile(self, spec):
        atlas_path = MAP_DIR / spec["asset"]
        atlas = self._atlases.get(atlas_path)
        if atlas is None:
            atlas = Image.open(atlas_path).convert("RGBA")
            self._atlases[atlas_path] = atlas
        tile_size = atlas.width // spec["columns"]
        tile_id = spec["tile_id"]
        column, row = tile_id % spec["columns"], tile_id // spec["columns"]
        return atlas.crop((
            column * tile_size,
            row * tile_size,
            (column + 1) * tile_size,
            (row + 1) * tile_size,
        ))

    def test_ice_palette_marks_passable_and_impassable_tiles(self):
        open_water_spec = next(
            spec for spec in self.specs.values()
            if spec["sheet"] == "Ice" and spec["category"] == "water"
        )
        ice_spec = next(
            spec for spec in self.specs.values()
            if spec["sheet"] == "Ice"
            and spec["category"] != "water"
            and not spec.get("palette_hidden", False)
        )
        for key, expected_color, point in (
            (open_water_spec["key"], BLOCK_MARK, (1, 1)),
            (ice_spec["key"], PASSABLE_MARK, (1, 1)),
        ):
            surface = pygame.Surface((20, 20), pygame.SRCALPHA)
            rect = pygame.Rect(0, 0, 20, 20)
            self.palette._paint_cell(
                surface,
                rect,
                self.catalog[key],
                pygame.Surface((20, 20), pygame.SRCALPHA),
            )
            with self.subTest(key=key):
                self.assertEqual(surface.get_at(point)[:3], expected_color)

    def test_small_object_sprites_keep_their_world_scale_in_the_palette(self):
        tiny = self.catalog["winter_spot_029"]
        normal = self.catalog["winter_spot_001"]
        near_tile_size = next(item for item in catalog_definitions() if item["item_key"] == "dec_054")
        cell_size = 44

        tiny_image = self.palette._cell_image(tiny, (cell_size, cell_size))
        normal_image = self.palette._cell_image(normal, (cell_size, cell_size))
        near_tile_image = self.palette._cell_image(near_tile_size, (cell_size, cell_size))

        self.assertLessEqual(max(tiny_image.get_bounding_rect().size), 4)
        self.assertGreater(normal_image.get_bounding_rect().width, 20)
        self.assertLess(normal_image.get_bounding_rect().width, 32)
        self.assertLess(near_tile_image.get_bounding_rect().width, cell_size - 4)
        self.assertLessEqual(normal_image.get_bounding_rect().width, cell_size - 4)

    def test_water_animations_are_compound_whole_compositions(self):
        groups = winter_animated_groups()
        water_keys = {
            key for key in winter_animations()
            if self.specs[key]["sheet"] == "Water_detilazation"
        }
        grouped_keys = {
            cell["key"]
            for group in groups
            for cell in group["cells"]
        }
        self.assertEqual(grouped_keys, water_keys)
        self.assertTrue(groups)
        for group in groups:
            with self.subTest(group=group["key"]):
                self.assertGreater(len(group["cells"]), 1)
                self.assertEqual(
                    len(self.palette.compound_entries(group["cells"][0]["key"])),
                    len(group["cells"]),
                )
                first = self.palette._water_preview(group, ticks=0, animated=True)
                later = self.palette._water_preview(group, ticks=150, animated=True)
                self.assertNotEqual(
                    pygame.image.tobytes(first, "RGBA"),
                    pygame.image.tobytes(later, "RGBA"),
                )

    def test_winter_details_are_whole_rocks_and_block_placement(self):
        details = [
            spec for spec in self.specs.values()
            if spec["sheet"] == "details"
            and spec.get("representation") == "sprite"
        ]
        detail_tiles = [
            spec for spec in self.specs.values()
            if spec["sheet"] == "details"
            and spec.get("representation") != "sprite"
        ]
        self.assertEqual(len(details), 21)
        self.assertTrue(detail_tiles)
        self.assertTrue(all(spec["palette_hidden"] for spec in detail_tiles))
        for spec in details:
            with self.subTest(key=spec["key"]):
                item = self.catalog[spec["key"]]
                self.assertEqual(item["kind"], "object")
                self.assertEqual(item["category"], "rock")
                self.assertTrue(item["blocks"])
                image = pygame.image.load(str(MAP_DIR / item["asset"])).convert_alpha()
                self.assertGreater(image.get_width(), 16)
                self.assertGreater(image.get_height(), 8)
                self.assertEqual(
                    len(pygame.mask.from_surface(image, 1).connected_components()),
                    1,
                )

    def test_winter_water_tiles_are_passable_and_allowed_on_empty_cells(self):
        catalog = catalog_definitions()
        key, spec = next(
            (key, spec)
            for key, spec in self.specs.items()
            if spec["sheet"].casefold() == "water_detilazation"
            and spec["layer"] == "overlay"
            and spec.get("representation") != "sprite"
        )
        item = next(item for item in catalog if item["item_key"] == key)
        self.assertEqual(item["category"], "floor")
        self.assertFalse(item["blocks"])

        state = MapEditorState(catalog, [], 4, 4)
        self.assertIsNone(state.place(key, 1, 1, layer=spec["layer"]))
        self.assertEqual(state.overlay, {(1, 1): key})
        self.assertEqual(
            validate_cells(
                [{"layer": "overlay", "x": 1, "y": 1, "key": key}],
                catalog,
                4,
                4,
            ),
            [("overlay", 1, 1, key)],
        )
        terrain = terrain_from_cells(
            [{"layer": "overlay", "x": 1, "y": 1, "key": key}],
            catalog,
        )
        self.assertIn((1, 1), terrain["floor"])
        self.assertNotIn((1, 1), terrain["impassable"])

    def test_spots_and_water_details_are_whole_passable_objects(self):
        spot_sprites = [
            spec for spec in self.specs.values()
            if spec["sheet"] == "spots"
            and spec.get("representation") == "sprite"
        ]
        water_sprites = [
            spec for spec in self.specs.values()
            if spec["sheet"] == "water_detilazation_v2"
            and spec.get("representation") == "sprite"
        ]
        self.assertGreater(len(spot_sprites), 10)
        self.assertGreater(len(water_sprites), 50)
        for sheet, sprites in (
            ("spots", spot_sprites),
            ("water_detilazation_v2", water_sprites),
        ):
            for spec in self.specs.values():
                if spec["sheet"] == sheet and spec.get("representation") != "sprite":
                    self.assertTrue(spec["palette_hidden"])
            for spec in sprites:
                with self.subTest(key=spec["key"]):
                    item = self.catalog[spec["key"]]
                    self.assertEqual(item["kind"], "object")
                    self.assertEqual(item["category"], "floor")
                    self.assertFalse(item["blocks"])
                    image = pygame.image.load(str(MAP_DIR / item["asset"])).convert_alpha()
                    self.assertGreater(image.get_width(), 0)
                    self.assertGreater(image.get_height(), 0)

    def test_growth_sprites_remain_intact_and_have_catalog_metadata(self):
        growth = [
            spec for spec in self.specs.values()
            if spec.get("growth_series") is not None
        ]
        self.assertEqual(len(growth), 122)
        for spec in growth:
            with self.subTest(key=spec["key"]):
                self.assertEqual(spec["representation"], "sprite")
                self.assertEqual(spec["asset"].count("/"), 2)
                item = self.catalog[spec["key"]]
                for field in ("display_name", "growth_series", "growth_stage", "growth_size"):
                    self.assertEqual(item[field], spec[field])
                image = pygame.image.load(str(MAP_DIR / spec["asset"])).convert_alpha()
                visible = image.get_bounding_rect()
                self.assertGreater(visible.width, 0)
                self.assertGreater(visible.height, 0)
                self.assertEqual(spec["growth_size"], visible.width * visible.height)

    def test_growth_series_are_ordered_by_visible_size(self):
        grouped = defaultdict(list)
        for item in self.catalog.values():
            if item.get("growth_series") is not None:
                grouped[item["growth_series"]].append(item)

        for series, items in grouped.items():
            expected = [
                item["item_key"]
                for item in sorted(
                    items,
                    key=lambda item: (
                        item["growth_size"],
                        item["growth_stage"],
                        item["item_key"],
                    ),
                )
            ]
            actual = [
                item["item_key"]
                for palette_series in _series(items)
                for item in palette_series
            ]
            with self.subTest(series=series):
                self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
