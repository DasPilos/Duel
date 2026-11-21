import os
import unittest
import random
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from core.map_catalog import (
    DECOR_CHANCE,
    DECOR_MIN_DISTANCE,
    HIDDEN_CATEGORIES,
    TALL_ROLES,
    WATER_ANIMAL_KEYS,
    MAIN_TILE_SHARE,
    bridge_stamps,
    catalog_definitions,
    decor_fits,
    decor_spaced,
    desert_animated_groups,
    desert_tile_specs,
    palette_group_decor,
    palette_group_layers,
    palette_groups,
    palette_landscape,
    palette_hidden_keys,
    palette_sheets,
    pick_decor,
    rocky_animated_groups,
    rocky_tile_specs,
    rocky_water_object_groups,
    tile_allows_objects,
    overlay_keys,
    undead_animated_groups,
    undead_tile_specs,
    winter_tile_specs,
    winter_animated_groups,
)
from scenes.map_editor_scene import MapEditorScene
from scenes.map_palette import (
    BLOCK_MARK, BLOCK_PAD, BLOCK_X, COLUMNS, PANEL_MARGIN, PANEL_W_MIN,
    PASSABLE_MARK, Palette, _series,
)

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
        compound_keys = {
            cell["key"]
            for group in (
                *rocky_animated_groups(),
                *winter_animated_groups(),
                *undead_animated_groups(),
                *desert_animated_groups(),
            )
            for cell in group["cells"]
        }
        water_object_keys = {
            cell["key"]
            for group in rocky_water_object_groups()
            for cell in group["cells"]
        }
        self.assertEqual(
            set(keys),
            ({item["item_key"] for item in self.catalog} - hidden) | compound_keys | water_object_keys,
        )
        placed = Counter(cell["key"] for group in palette_groups() for cell in group["cells"])
        shown = Counter(keys)
        for key, count in placed.items():
            self.assertEqual(shown[key], count, key)
        sheet_keys = {cell["key"] for sheet in palette_sheets() for cell in sheet["cells"]}
        self.assertFalse(sheet_keys & set(placed))

    def test_artist_layout_places_tiles_inside_their_catalog_section(self):
        source = Palette(
            self.catalog,
            MAP_DIR,
            pygame.font.Font(None, 16),
            pygame.font.Font(None, 16),
            max_panel=640,
        )
        key = next(
            item["item_key"]
            for row in source.rows
            if row.kind == "block"
            for _rect, item in row.cells
            if not source.compound_entries(item["item_key"])
        )
        layout = Palette(
            self.catalog,
            MAP_DIR,
            pygame.font.Font(None, 16),
            pygame.font.Font(None, 16),
            max_panel=640,
            arrange_mode=True,
        )
        group = layout.arrangement_group_for_item(key)
        section = next(
            row for row in layout.rows
            if row.arrange_group == group
        )
        occupied = set(layout.arrangement_positions(group).values())
        target = next(
            (column, line)
            for line in range(section.size[1] // layout.tile + 2)
            for column in range(10)
            if (column, line) not in occupied
        )
        palette = Palette(
            self.catalog,
            MAP_DIR,
            pygame.font.Font(None, 16),
            pygame.font.Font(None, 16),
            max_panel=640,
            rules={key: {"palette_position": {"x": target[0], "y": target[1]}}},
            arrange_mode=True,
        )
        section = next(row for row in palette.rows if row.arrange_group == group)
        tile_rect = next(
            rect for rect, item in section.cells if item["item_key"] == key
        )
        occupied = set(palette.arrangement_positions(group).values())
        empty_slot = next(
            (column, line)
            for line in range(section.size[1] // palette.tile)
            for column in range(10)
            if (column, line) not in occupied
        )

        self.assertEqual(
            tile_rect.topleft,
            (target[0] * palette.tile, target[1] * palette.tile),
        )
        self.assertEqual(
            palette.arrangement_position_at(
                BLOCK_X + empty_slot[0] * palette.tile + 1,
                section.top + BLOCK_PAD + empty_slot[1] * palette.tile + 1,
            ),
            (group, *empty_slot),
        )
        self.assertIsNone(palette.arrangement_item_at((group, *empty_slot)))
        self.assertEqual(
            palette.item_at(
                BLOCK_X + tile_rect.centerx,
                section.top + BLOCK_PAD + tile_rect.centery,
            ),
            key,
        )
        self.assertEqual(
            sum(
                item["item_key"] == key
                for row in palette.rows
                if row.kind == "block"
                for _rect, item in row.cells
            ),
            1,
        )
        self.assertGreaterEqual(section.size[1] // palette.tile, 4)

    def test_artist_layout_preserves_relative_cells_and_legacy_positions_reset(self):
        palette = Palette(
            self.catalog,
            MAP_DIR,
            pygame.font.Font(None, 16),
            pygame.font.Font(None, 16),
            max_panel=640,
            arrange_mode=True,
        )
        group_title, clusters = next(
            (title, clusters)
            for title, clusters in palette._sections
            if any(
                len(cluster.cells) > 1
                and len({item["item_key"] for _position, item in cluster.cells}) == len(cluster.cells)
                for cluster in clusters
            )
        )
        cluster = next(
            cluster for cluster in clusters
            if len(cluster.cells) > 1
            and len({item["item_key"] for _position, item in cluster.cells}) == len(cluster.cells)
        )
        keys = [item["item_key"] for _position, item in cluster.cells]
        positions = palette.arrangement_positions(group_title)
        expected_positions = [
            (column, line)
            for (column, line), _item in cluster.cells
        ]
        actual_positions = [positions[key] for key in keys]
        expected_origin = expected_positions[0]
        actual_origin = actual_positions[0]
        self.assertEqual(
            [
                (column - actual_origin[0], line - actual_origin[1])
                for column, line in actual_positions
            ],
            [
                (column - expected_origin[0], line - expected_origin[1])
                for column, line in expected_positions
            ],
        )

        legacy_rules = {
            item["item_key"]: {"palette_position": {"x": index % 10, "y": index // 10}}
            for index, item in enumerate(
                item
                for _title, section_clusters in palette._sections
                for section_cluster in section_clusters
                for _position, item in section_cluster.cells
                if not section_cluster.compound
                and section_cluster.preview_group is None
            )
        }
        legacy_palette = Palette(
            self.catalog,
            MAP_DIR,
            pygame.font.Font(None, 16),
            pygame.font.Font(None, 16),
            max_panel=640,
            rules=legacy_rules,
            arrange_mode=True,
        )
        self.assertTrue(legacy_palette.legacy_position_keys())
        self.assertEqual(
            legacy_palette.arrangement_positions(group_title),
            positions,
        )
        original_palette = Palette(
            self.catalog,
            MAP_DIR,
            pygame.font.Font(None, 16),
            pygame.font.Font(None, 16),
            max_panel=640,
        )
        restored_palette = Palette(
            self.catalog,
            MAP_DIR,
            pygame.font.Font(None, 16),
            pygame.font.Font(None, 16),
            max_panel=640,
            rules=legacy_rules,
        )
        self.assertEqual(
            [
                (row.kind, row.title, [
                    (rect.topleft, item["item_key"])
                    for rect, item in row.cells
                ] if row.kind == "block" else [])
                for row in restored_palette.rows
            ],
            [
                (row.kind, row.title, [
                    (rect.topleft, item["item_key"])
                    for rect, item in row.cells
                ] if row.kind == "block" else [])
                for row in original_palette.rows
            ],
        )

    def test_animated_water_is_shown_as_whole_compound_stamps(self):
        groups = rocky_animated_groups()
        self.assertGreater(len(groups), 0)
        water_object_keys = {
            cell["key"]
            for group in rocky_water_object_groups()
            for cell in group["cells"]
        }
        for group in groups:
            visible_keys = [cell["key"] for cell in group["cells"] if cell["key"] not in water_object_keys]
            for key in visible_keys:
                with self.subTest(key=key):
                    entries = self.palette.compound_entries(key)
                    self.assertGreater(len(entries), 0)
                    self.assertTrue(all(entry[3] == "overlay" for entry in entries))
                    for cell in group["cells"]:
                        if cell["key"] in water_object_keys:
                            continue
                        self.assertIn(cell["key"], {entry[2] for entry in entries})
                        self.assertEqual(
                            self.palette.compound_entries(cell["key"]),
                            entries,
                        )

    def test_water_objects_include_author_wave_cells_and_full_preview(self):
        groups = rocky_water_object_groups()
        self.assertEqual(len(groups), 8)
        by_key = {item["item_key"]: item for item in self.catalog}
        expected_wave_counts = {
            "rocky_water_object_boat": 16,
            "rocky_water_object_sail": 2,
            "rocky_water_object_house": 7,
            "rocky_water_object_ruins_1": 12,
            "rocky_water_object_ruins_2": 9,
            "rocky_water_object_ruins_3": 10,
            "rocky_water_object_ruins_4": 6,
            "rocky_water_object_nessy": 16,
        }
        for group in groups:
            with self.subTest(group=group["key"]):
                object_cells = [cell for cell in group["cells"] if cell["layer"] == "objects"]
                overlay_cells = [cell for cell in group["cells"] if cell["layer"] == "overlay"]
                self.assertGreaterEqual(len(object_cells), 1)
                self.assertGreater(len(overlay_cells), 0)
                self.assertEqual(len(overlay_cells), expected_wave_counts[group["key"]])
                self.assertTrue(all(
                    cell["key"].startswith("rocky_water_under_objects_")
                    for cell in overlay_cells
                ))
                self.assertTrue(all(by_key[cell["key"]]["kind"] == "object" for cell in object_cells))
                self.assertTrue(all(by_key[cell["key"]]["kind"] == "ground" for cell in overlay_cells))
                for cell in object_cells:
                    image = pygame.image.load(
                        str(MAP_DIR / by_key[cell["key"]]["asset"])
                    ).convert_alpha()
                    self.assertEqual(image.get_bounding_rect(), image.get_rect())
                entries = self.palette.compound_entries(group["primary_key"])
                self.assertEqual(len(entries), len(group["cells"]))
                self.assertTrue(any(
                    row.kind == "block"
                    and any(preview["key"] == group["key"] for _rect, preview in row.previews)
                    for row in self.palette.rows
                ))
                row = next(
                    row for row in self.palette.rows
                    if row.kind == "block"
                    and any(preview["key"] == group["key"] for _rect, preview in row.previews)
                )
                rect, _preview = next(
                    (rect, preview) for rect, preview in row.previews
                    if preview["key"] == group["key"]
                )
                point = (BLOCK_X + rect.centerx, row.top + BLOCK_PAD + rect.centery                )
                self.assertEqual(self.palette.item_at(*point), group["primary_key"])
                self.assertIsNone(self.palette.item_layer_at(*point))

    def test_water_ruins_are_separated_and_ordered_numerically(self):
        expected_headers = ["Руины 1", "Руины 2", "Руины 3", "Руины 4"]
        ruin_headers = [
            row.title for row in self.palette.rows
            if row.kind == "subheader" and row.title in expected_headers
        ]
        self.assertEqual(ruin_headers, expected_headers)

        groups = {
            group["key"].rsplit("_", 1)[1]: group["key"]
            for group in rocky_water_object_groups()
            if group["key"].startswith("rocky_water_object_ruins_")
        }
        for index, title in enumerate(ruin_headers):
            start = next(
                row_index for row_index, row in enumerate(self.palette.rows)
                if row.kind == "subheader" and row.title == title
            )
            stop = next(
                (
                    row_index for row_index in range(start + 1, len(self.palette.rows))
                    if self.palette.rows[row_index].kind in ("subheader", "header")
                ),
                len(self.palette.rows),
            )
            shown_groups = {
                preview["key"]
                for row in self.palette.rows[start + 1:stop]
                if row.kind == "block"
                for _rect, preview in row.previews
            }
            self.assertEqual(shown_groups, {groups[str(index + 1)]})

    def test_water_object_sprite_uses_tiled_pixel_alignment(self):
        boat_key = "rocky_water_object_boat_1"
        boat = next(item for item in self.catalog if item["item_key"] == boat_key)
        self.assertEqual(
            boat["render_offset_tiles"],
            {"x": -0.46875, "y": -0.125},
        )
        image = pygame.image.load(str(MAP_DIR / boat["asset"])).convert_alpha()
        footprint = pygame.Rect(100, 200, 32, 32)
        scene = SimpleNamespace(state=SimpleNamespace(items={boat_key: boat}))
        actual = MapEditorScene._object_rect(scene, boat_key, image, footprint)
        offset = boat["render_offset_tiles"]
        expected = image.get_rect(midbottom=(
            footprint.centerx + round(offset["x"] * footprint.w / boat["footprint_w"]),
            footprint.bottom + round(offset["y"] * footprint.h / boat["footprint_h"]),
        ))
        self.assertEqual(actual, expected)

    def test_author_growth_objects_are_grouped_as_ordered_stage_series(self):
        specs = rocky_tile_specs()
        growth = [
            item for item in self.catalog
            if item.get("growth_series")
            and not specs.get(item["item_key"], {}).get("palette_hidden", False)
        ]
        groups = _series(growth)
        self.assertGreaterEqual(len(groups), 10)
        self.assertTrue(all(len(series) >= 2 for series in groups))
        for series in groups:
            sizes = [item["growth_size"] for item in series]
            self.assertEqual(sizes, sorted(sizes))
            self.assertTrue(all(item["category"] == "bush" for item in series))
        growth_rows = [
            row for row in self.palette.rows
            if row.kind == "block"
            and any(item.get("growth_series") for _rect, item in row.cells)
        ]
        self.assertEqual(len(growth_rows), len(groups))
        for row in growth_rows:
            row_items = [item for _rect, item in row.cells if item.get("growth_series")]
            self.assertEqual(len({item["growth_series"] for item in row_items}), 1)
            self.assertEqual(
                [item["item_key"] for _rect, item in row.cells],
                [item["item_key"] for item in sorted(row_items, key=lambda item: item["growth_size"])],
            )
            self.assertEqual(len({rect.y for rect, _item in row.cells}), 1)
        shown = set(self._cells())
        self.assertTrue(all(
            item["item_key"] in shown for item in growth
        ))

    def test_rock_growth_families_have_five_sizes_in_separate_rows(self):
        growth = [
            item for item in self.catalog
            if item.get("growth_series", "").startswith("rocky_rock")
        ]
        expected_series = {
            f"rocky_rock{rock}_{surface}"
            for rock in range(1, 4)
            for surface in ("grass", "ground")
        }
        self.assertEqual(
            {item["growth_series"] for item in growth},
            expected_series,
        )
        for series in expected_series:
            with self.subTest(series=series):
                row = next(
                    row for row in self.palette.rows
                    if row.kind == "block"
                    and any(
                        item.get("growth_series") == series
                        for _rect, item in row.cells
                    )
                )
                row_items = [item for _rect, item in row.cells]
                self.assertEqual(len(row_items), 5)
                self.assertEqual(
                    {item["growth_stage"] for item in row_items},
                    set(range(1, 6)),
                )
                self.assertTrue(all(item.get("growth_series") == series for item in row_items))
                sizes = [item["growth_size"] for item in row_items]
                self.assertEqual(sizes, sorted(sizes))

    def test_growth_stage_silhouettes_are_hidden_from_the_atlas_palette(self):
        specs = rocky_tile_specs()
        for key in (
            "rocky_objects_004",
            "rocky_objects_005",
            "rocky_objects_009",
            "rocky_objects_045",
            "rocky_objects_062",
            "rocky_objects_072",
        ):
            with self.subTest(key=key):
                self.assertTrue(specs[key]["palette_hidden"])
                self.assertNotIn(key, self._cells())

    def test_detail_sheet_fragments_are_hidden_and_complete_sprites_are_sorted(self):
        specs = rocky_tile_specs()
        detail_sprites = [
            item for item in self.catalog
            if item["item_key"].startswith("rocky_details_object_")
        ]
        section_headers = [
            row for row in self.palette.rows
            if row.kind == "header"
            and row.title == "Скалистый биом · Цельные детали и растения"
        ]
        self.assertEqual(len(detail_sprites), 30)
        self.assertEqual(len(section_headers), 1)

        visible_detail_sprites = [
            item for item in detail_sprites
            if not specs[item["item_key"]]["palette_hidden"]
        ]
        rows = [
            row for row in self.palette.rows
            if row.kind == "block"
            and any(
                item["item_key"].startswith("rocky_details_object_")
                for _rect, item in row.cells
            )
        ]
        self.assertEqual(len(rows), len(visible_detail_sprites))
        sizes = []
        for row in rows:
            row_items = [item for _rect, item in row.cells]
            self.assertEqual(len(row_items), 1)
            sizes.append(row_items[0]["growth_size"])
        self.assertEqual(sizes, sorted(sizes))

        hidden_parts = {
            f"rocky_details_{tile_id:04d}"
            for item in detail_sprites
            for tile_id in specs[item["item_key"]]["source_tile_ids"]
            if f"rocky_details_{tile_id:04d}" in specs
        }
        self.assertTrue(hidden_parts)
        self.assertFalse(hidden_parts & set(self._cells()))
        detail_tiles = {
            key
            for key, spec in specs.items()
            if spec["sheet"] == "details" and spec.get("representation") != "sprite"
        }
        self.assertTrue(detail_tiles)
        self.assertTrue(all(specs[key]["palette_hidden"] for key in detail_tiles))
        self.assertFalse(detail_tiles & set(self._cells()))

    def test_animals_have_a_dedicated_palette_section(self):
        headers = [row for row in self.palette.rows if row.kind == "header"]
        self.assertIn("Животные", [row.title for row in headers])
        animal_header = next(row for row in headers if row.title == "Животные")
        self.assertEqual(headers[headers.index(animal_header) - 1].title, "Кусты и растения")
        section_end = next(
            (row.top for row in headers if row.top > animal_header.top),
            self.palette.height,
        )
        animal_cells = [
            item["item_key"]
            for row in self.palette.rows
            if row.kind == "block" and animal_header.top < row.top < section_end
            for _, item in row.cells
        ]
        self.assertEqual(len(animal_cells), 12)
        self.assertTrue(all(key.startswith("animal_") for key in animal_cells))
        water_header = next(row for row in self.palette.rows if row.kind == "subheader" and row.title == "Водные")
        water_cells = [
            item["item_key"]
            for row in self.palette.rows
            if row.kind == "block" and row.top > water_header.top
            and row.top < next(
                (header.top for header in headers if header.top > water_header.top),
                self.palette.height,
            )
            for _, item in row.cells
        ]
        self.assertEqual(set(water_cells), WATER_ANIMAL_KEYS)

    def test_unused_rock_leaves_road_and_water_tiles_are_removed_from_catalog(self):
        expected_duplicates = {
            item["key"]
            for item in (
                *rocky_tile_specs().values(),
                *winter_tile_specs().values(),
                *undead_tile_specs().values(),
                *desert_tile_specs().values(),
            )
            if item.get("palette_hidden", False)
        }
        self.assertEqual(palette_hidden_keys(self.catalog), expected_duplicates)
        by_key = {item["item_key"]: item for item in self.catalog}
        placed = {cell["key"] for group in palette_groups() for cell in group["cells"]}
        placed.update(rocky_tile_specs())
        placed.update(winter_tile_specs())
        placed.update(undead_tile_specs())
        placed.update(desert_tile_specs())
        outside = {
            key for key, item in by_key.items() if item["kind"] == "ground" and item["category"] in HIDDEN_CATEGORIES
        }
        self.assertEqual(outside - placed, set())

    def test_artist_group_is_first_and_keeps_layout(self):
        group = palette_groups()[0]
        headers = [row for row in self.palette.rows if row.kind == "header"]
        self.assertEqual(headers[0].title, group["title"])
        header = next(row for row in headers if row.title == group["title"])
        first = next(row for row in self.palette.rows if row.kind == "block" and row.top > header.top)
        tile = self.palette.tile
        placed = sorted((item["item_key"], rect.x // tile, rect.y // tile) for rect, item in first.cells)
        self.assertEqual(placed, sorted((cell["key"], cell["x"], cell["y"]) for cell in group["cells"]))

    def test_growing_bushes_are_first_in_their_section_and_get_three_stages_per_row(self):
        palette = Palette(catalog_definitions(), MAP_DIR, pygame.font.Font(None, 16), pygame.font.Font(None, 16), max_panel=640)
        for tile in (16, 20, 24):
            palette.set_tile(tile)
            headers = [row for row in palette.rows if row.kind == "header"]
            bush_index = next(index for index, row in enumerate(headers) if row.title == "Кусты и растения")
            self.assertGreater(bush_index, 0)
            self.assertEqual(headers[bush_index - 1].title, "Брёвна")
            header = headers[bush_index]
            rows = []
            for row in palette.rows:
                if row.top <= header.top:
                    continue
                if row.kind == "header":
                    break
                if row.kind != "block":
                    continue
                rows.append(row)
            growth_rows = rows[:12]
            self.assertEqual(len(growth_rows), 12)
            for row in growth_rows:
                self.assertEqual(len(row.cells), 3)
                self.assertEqual(
                    [int(item["item_key"].rsplit("_", 1)[1]) for _, item in sorted(row.cells, key=lambda cell: cell[0].x)],
                    [1, 2, 3],
                )
            growth_keys = {item["item_key"] for row in growth_rows for _, item in row.cells}
            self.assertEqual(len(growth_keys), 36)
            self.assertTrue(all(item["category"] == "bush" for row in growth_rows for _, item in row.cells))
        palette.set_tile(20)

    def test_rows_hold_at_most_ten_tiles_and_panel_follows_zoom(self):
        palette = self.palette
        for tile in (16, 24):
            palette.set_tile(tile)
            limit = COLUMNS * tile
            for row in palette.rows:
                if row.kind != "block":
                    continue
                artist_context = any(
                    item.get("palette_artist_copy")
                    for _rect, item in row.cells
                )
                if artist_context:
                    self.assertLessEqual(
                        row.size[0],
                        palette.max_panel - PANEL_MARGIN,
                    )
                else:
                    self.assertLessEqual(row.size[0], limit)
            context_columns = max(
                cluster.cols
                for _title, clusters in palette._sections
                for cluster in clusters
                if cluster.artist_context
            )
            context_width = context_columns * min(
                tile,
                (palette.max_panel - PANEL_MARGIN) // context_columns,
            ) + PANEL_MARGIN
            self.assertEqual(
                palette.panel_width(),
                max(
                    PANEL_W_MIN,
                    min(max(limit + PANEL_MARGIN, context_width), palette.max_panel),
                ),
            )
        palette.set_tile(20)

    def test_custom_groups_and_order_are_applied_to_palette_layout(self):
        grass = next(item for item in self.catalog if item["category"] == "grass")
        tree = next(item for item in self.catalog if item["category"] == "tree")
        rules = {
            grass["item_key"]: {"palette_group": "Моя группа", "palette_order": 2},
            tree["item_key"]: {"palette_group": "Моя группа", "palette_order": 1},
        }
        palette = Palette(
            self.catalog,
            MAP_DIR,
            self.palette.font,
            self.palette.small,
            max_panel=640,
            rules=rules,
        )

        title, clusters = next(
            section for section in palette._sections if section[0] == "Моя группа"
        )
        self.assertEqual(title, "Моя группа")
        self.assertEqual(
            [item["item_key"] for cluster in clusters for _position, item in cluster.cells],
            [tree["item_key"], grass["item_key"]],
        )

    def test_passability_triangle_uses_upper_left_corner_for_both_states(self):
        item = next(item for item in self.catalog if item["category"] == "grass")
        image = pygame.Surface((20, 20), pygame.SRCALPHA)
        rect = pygame.Rect(2, 2, 20, 20)
        original_rules = self.palette.rules
        try:
            for blocks, expected in ((False, PASSABLE_MARK), (True, BLOCK_MARK)):
                self.palette.rules = {item["item_key"]: {"blocks": blocks}}
                target = pygame.Surface((24, 24), pygame.SRCALPHA)
                self.palette._paint_cell(target, rect, item, image)
                self.assertEqual(target.get_at((3, 3))[:3], expected)
        finally:
            self.palette.rules = original_rules

    def test_item_at_returns_group_tile(self):
        group = palette_groups()[0]
        cell = group["cells"][0]
        row = next(row for row in self.palette.rows if row.kind == "block" and any(item["item_key"] == cell["key"] for _, item in row.cells))
        rect, _ = next((rect, item) for rect, item in row.cells if item["item_key"] == cell["key"])
        x = 12 + rect.centerx
        y = row.top + 4 + rect.centery
        self.assertEqual(self.palette.item_at(x, y), cell["key"])

    def test_sample_role_overrides_transparency_key_classification(self):
        examples = {}
        for row in self.palette.rows:
            if row.kind != "block":
                continue
            for rect, item in row.cells:
                for frame, role, _ in row.frames:
                    if not frame.collidepoint(rect.center) or item["item_key"] not in overlay_keys():
                        continue
                    if role in ("ground", "grass") and "ground" not in examples:
                        examples["ground"] = (row, rect)
                    elif role == "mountain" and "relief" not in examples:
                        examples["relief"] = (row, rect)
            if len(examples) == 2:
                break

        self.assertEqual(set(examples), {"ground", "relief"})
        for expected_layer, (row, rect) in examples.items():
            x = 12 + rect.centerx
            y = row.top + 4 + rect.centery
            self.assertEqual(self.palette.item_layer_at(x, y), expected_layer)

    def test_stamp_entries_follow_dragged_rectangle(self):
        group = palette_groups()[0]
        header = next(row for row in self.palette.rows if row.kind == "header" and row.title == group["title"])
        first = next(row for row in self.palette.rows if row.kind == "block" and row.top > header.top)
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
        group_title = palette_groups()[0]["title"]
        header = next(index for index, row in enumerate(rows) if row.kind == "header" and row.title == group_title)
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
        self.assertIn("Кусты и растения", headers)
        self.assertEqual(headers[len(headers) - len(sheets):], [sheet["title"] for sheet in sheets])
        self.assertEqual(headers.count(palette_groups()[0]["title"]), 1)

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


class CrystalGrowthAnchorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((10, 10))
        cls.font = pygame.font.Font(None, 16)

    def test_all_stages_of_a_color_share_one_base_point(self):
        palette = Palette(catalog_definitions(), MAP_DIR, self.font, self.font, max_panel=640)
        series = _series([item for item in catalog_definitions() if item["category"] == "crystal"])
        self.assertEqual(len(series), 10)
        for stages in series:
            bases = []
            for item in stages:
                image = palette._cell_image(item, (44, 44))
                rect = image.get_bounding_rect()
                bases.append((rect.centerx, rect.bottom))
            self.assertEqual(len(set(bases)), 1, stages[0]["item_key"])
            self.assertLessEqual(abs(bases[0][0] - 22), 1, stages[0]["item_key"])


class BushGrowthAnchorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((10, 10))
        cls.font = pygame.font.Font(None, 16)

    def test_bush_growth_series_are_ordered_and_share_one_base_point(self):
        catalog = catalog_definitions()
        bushes = [
            item for item in catalog
            if item["category"] == "bush" and item["item_key"].startswith("bush_")
            and item["item_key"].rsplit("_", 1)[-1] in {"1", "2", "3"}
            and not item.get("growth_series")
        ]
        series = _series(bushes)
        palette = Palette(catalog, MAP_DIR, self.font, self.font, max_panel=640)

        self.assertEqual(len(series), 12)
        for stages in series:
            self.assertEqual([int(item["item_key"].rsplit("_", 1)[1]) for item in stages], [1, 2, 3])
            bases = []
            for item in stages:
                image = palette._cell_image(item, (44, 44))
                rect = image.get_bounding_rect()
                bases.append((rect.centerx, rect.bottom))
            self.assertEqual(len(set(bases)), 1, stages[0]["item_key"])
            self.assertLessEqual(abs(bases[0][0] - 22), 1, stages[0]["item_key"])


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
        in_blocks.update(rocky_tile_specs())
        in_blocks.update(winter_tile_specs())
        in_blocks.update(undead_tile_specs())
        in_blocks.update(desert_tile_specs())
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
    def test_floor_tiles_and_bridge_stamps_are_walkable(self):
        catalog = {item["item_key"]: item for item in catalog_definitions()}
        floor = [key for key, item in catalog.items() if item["category"] == "floor"]
        bridges = {
            key
            for stamp in bridge_stamps()
            for key in stamp.values()
        }

        self.assertTrue(floor)
        blocked_floor = [key for key in floor if catalog[key]["blocks"]]
        self.assertTrue(blocked_floor)
        self.assertTrue(all(key.startswith("winter_") for key in blocked_floor))
        self.assertTrue(bridges)
        self.assertFalse([key for key in bridges if catalog[key]["blocks"]])

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
