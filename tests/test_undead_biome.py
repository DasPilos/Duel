import os
import unittest
from collections import defaultdict

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
from PIL import Image

from core.map_catalog import (
    MAP_ASSETS,
    catalog_definitions,
    overlay_keys,
    undead_animated_groups,
    undead_animations,
    undead_tile_specs,
    water_decor_keys,
    water_decor_requires_water_keys,
)
from scenes.map_editor_scene import BIOME_TABS, MapEditorScene, PALETTE_ANIMATIONS
from scenes.map_palette import BLOCK_PAD, BLOCK_X, Palette


class UndeadBiomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.specs = undead_tile_specs()
        cls.animations = undead_animations()
        cls.groups = undead_animated_groups()
        cls.catalog = catalog_definitions()
        font = pygame.font.Font(None, 16)
        cls.palette = Palette(
            cls.catalog,
            MAP_ASSETS,
            font,
            font,
            animations=PALETTE_ANIMATIONS,
        )

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_imported_tiles_and_animation_metadata_are_catalogued(self):
        catalog_keys = {item["item_key"] for item in self.catalog}
        self.assertGreater(len(self.specs), 4000)
        self.assertTrue(set(self.specs).issubset(catalog_keys))
        self.assertTrue(set(self.animations).issubset(PALETTE_ANIMATIONS))
        for key, animation in self.animations.items():
            with self.subTest(key=key):
                self.assertIn(key, self.specs)
                self.assertEqual(animation["frames"], len(animation["durations"]))
                if "tile_ids" in animation:
                    self.assertEqual(animation["frames"], len(animation["tile_ids"]))
                else:
                    self.assertEqual(self.specs[key]["representation"], "sprite")
                self.assertTrue(all(duration > 0 for duration in animation["durations"]))

    def test_water_animations_stay_grouped_and_on_water_decor_layer(self):
        water_sheets = {
            "Water_detilazation",
            "Water_detilazation2",
        }
        water_animation_keys = {
            key
            for key, spec in self.specs.items()
            if spec["sheet"] in water_sheets and key in self.animations
        }
        grouped_water_keys = {
            cell["key"]
            for group in self.groups
            if group["sheet"] in water_sheets
            for cell in group["cells"]
        }
        self.assertTrue(water_animation_keys)
        self.assertTrue(grouped_water_keys)
        self.assertTrue(grouped_water_keys.issubset(water_animation_keys))
        self.assertTrue(water_animation_keys.issubset(water_decor_keys()))
        self.assertTrue(water_animation_keys.issubset(water_decor_requires_water_keys()))
        self.assertTrue(water_animation_keys.issubset(overlay_keys()))
        for key in water_animation_keys:
            with self.subTest(key=key):
                self.assertEqual(self.specs[key]["layer"], "overlay")
                self.assertEqual(self.specs[key]["editor_layer"], 2)

        for group in self.groups:
            if group["sheet"] not in water_sheets:
                continue
            entries = self.palette.compound_entries(group["key"])
            self.assertEqual(
                {(entry[0], entry[1], entry[2]) for entry in entries},
                {
                    (cell["x"], cell["y"], cell["key"])
                    for cell in group["cells"]
                },
            )

    def test_coasts_and_water_are_individually_placeable_tiles(self):
        coast_keys = {
            key
            for key, spec in self.specs.items()
            if spec["sheet"].casefold() == "water_coasts"
            and key in self.animations
        }
        self.assertTrue(coast_keys)
        self.assertFalse(any(
            group["sheet"].casefold() == "water_coasts"
            for group in self.groups
        ))

        catalog_by_key = {item["item_key"]: item for item in self.catalog}
        palette_cells = {
            item["item_key"]: (row, rect)
            for row in self.palette.rows
            for rect, item in row.cells
            if item.get("item_key") in coast_keys
        }
        self.assertTrue(coast_keys.issubset(palette_cells))
        for key in coast_keys:
            with self.subTest(key=key):
                spec = self.specs[key]
                self.assertNotEqual(spec.get("representation"), "sprite")
                self.assertEqual(catalog_by_key[key]["kind"], "ground")
                self.assertEqual(self.palette.compound_entries(key), [])
                row, rect = palette_cells[key]
                self.assertEqual(
                    self.palette.item_at(
                        BLOCK_X + rect.centerx,
                        row.top + BLOCK_PAD + rect.centery,
                    ),
                    key,
                )

    def test_complete_source_sprites_are_imported_without_recropping(self):
        item = self.specs["undead_sprite_bones_shadow1_1"]
        imported = MAP_ASSETS / item["asset"]
        with Image.open(imported) as imported_image:
            self.assertEqual(
                imported_image.size,
                (item["source_size"][0] * 2, item["source_size"][1] * 2),
            )
        self.assertEqual(item["representation"], "sprite")
        self.assertEqual(item["editor_layer"], 7)
        self.assertEqual(item["source_name"], "Bones_shadow1_1.png")

    def test_animation_sheets_are_imported_as_whole_visible_sprites(self):
        for index, source_size in enumerate(
            ((96, 128), (80, 96), (64, 64), (80, 112), (96, 112), (48, 80)),
            start=1,
        ):
            key = f"undead_animation{index}"
            with self.subTest(key=key):
                spec = self.specs[key]
                animation = self.animations[key]
                self.assertEqual(spec["representation"], "sprite")
                self.assertFalse(spec["palette_hidden"])
                self.assertEqual(spec["source_size"], list(source_size))
                self.assertEqual(animation["frames"], 6)
                self.assertEqual(animation["frame"], [source_size[0] * 2, source_size[1] * 2])
                with Image.open(MAP_ASSETS / spec["asset"]) as image:
                    self.assertEqual(image.size, (source_size[0] * 12, source_size[1] * 2))
                item = next(item for item in self.catalog if item["item_key"] == key)
                first = self.palette._native_image(item, 0)
                second = self.palette._native_image(item, 1)
                self.assertEqual(first.get_size(), tuple(animation["frame"]))
                self.assertNotEqual(
                    pygame.image.tostring(first, "RGBA"),
                    pygame.image.tostring(second, "RGBA"),
                )

    def test_split_animated_object_atlas_tiles_are_hidden_from_palette(self):
        split_tiles = [
            spec for spec in self.specs.values()
            if spec["sheet"].casefold().startswith("objects_animated")
        ]
        self.assertTrue(split_tiles)
        self.assertTrue(all(spec["palette_hidden"] for spec in split_tiles))

    def test_whole_object_palette_is_split_by_type_and_sorted_by_size(self):
        sections = {
            title: clusters
            for title, clusters in self.palette._sections
            if title.startswith("Нежить · ")
        }
        family_sections = {
            title: clusters
            for title, clusters in sections.items()
            if title not in {
                "Нежить · Спрайты из атласа",
                "Нежить · Цельные детали",
                "Нежить · Анимированные цельные объекты",
            }
        }
        self.assertTrue(family_sections)
        for title, clusters in family_sections.items():
            with self.subTest(section=title):
                specs = [
                    self.specs[item["item_key"]]
                    for cluster in clusters
                    for _position, item in cluster.cells
                ]
                self.assertTrue(all(spec["sheet"] == "Objects_separately" for spec in specs))
                self.assertEqual(len({spec["object_type"] for spec in specs}), 1)
                sizes = [
                    spec["source_size"][0] * spec["source_size"][1]
                    for spec in specs
                ]
                self.assertEqual(sizes, sorted(sizes, reverse=True))

        atlas_items = [
            item["item_key"]
            for cluster in sections["Нежить · Спрайты из атласа"]
            for _position, item in cluster.cells
        ]
        self.assertTrue(atlas_items)
        self.assertTrue(all(self.specs[key]["sheet"] == "Objects" for key in atlas_items))
        animated_items = [
            item["item_key"]
            for cluster in sections["Нежить · Анимированные цельные объекты"]
            for _position, item in cluster.cells
        ]
        self.assertEqual(set(animated_items), {
            f"undead_animation{index}" for index in range(1, 7)
        })

    def test_whole_animated_sprites_advance_on_map(self):
        scene = MapEditorScene(None, self.catalog, lambda: False)
        key = "undead_animation1"
        first = scene._scaled(key, 32, 0)
        second = scene._scaled(key, 32, 1)
        self.assertEqual(first.get_size(), second.get_size())
        self.assertNotEqual(
            pygame.image.tostring(first, "RGBA"),
            pygame.image.tostring(second, "RGBA"),
        )

    def test_duplicate_whole_sprite_images_are_not_repeated_in_the_palette(self):
        visible_keys_by_image = defaultdict(list)
        for key, spec in self.specs.items():
            if spec.get("representation") != "sprite" or spec.get("palette_hidden"):
                continue
            image = Image.open(MAP_ASSETS / spec["asset"]).convert("RGBA")
            bounds = image.getchannel("A").getbbox()
            self.assertIsNotNone(bounds)
            image = image.crop(bounds)
            visible_keys_by_image[(image.size, image.tobytes())].append(key)

        self.assertTrue(visible_keys_by_image)
        self.assertTrue(all(
            len(keys) == 1
            for keys in visible_keys_by_image.values()
        ))

    def test_regular_biome_tiles_keep_their_source_map_layer(self):
        group_keys = {
            cell["key"]
            for group in self.groups
            for cell in group["cells"]
        }
        found_roles = set()
        for row in self.palette.rows:
            if row.kind != "block":
                continue
            for rect, item in row.cells:
                key = item["item_key"]
                spec = self.specs.get(key)
                if (
                    spec is None
                    or spec.get("representation") == "sprite"
                    or key in group_keys
                    or spec["layer"] not in {"ground", "overlay", "elevation", "infra"}
                    or spec["layer"] in found_roles
                ):
                    continue
                found_roles.add(spec["layer"])
                self.assertEqual(
                    self.palette.item_layer_at(
                        BLOCK_X + rect.centerx,
                        row.top + BLOCK_PAD + rect.centery,
                    ),
                    spec["layer"],
                )
        self.assertIn("elevation", found_roles)
        self.assertIn("overlay", found_roles)

    def test_undead_mountains_are_split_into_two_visual_types(self):
        mountain_sections = {
            title: clusters
            for title, clusters in self.palette._sections
            if title in {
                "Биом нежити · Горы — тёмные скалы",
                "Биом нежити · Горы — скалы с каменной вершиной",
            }
        }
        self.assertEqual(len(mountain_sections), 2)
        expected_keys = set()
        found_keys = set()
        for title, clusters in mountain_sections.items():
            expected_type = "stone" if "каменной вершиной" in title else "dark"
            source_specs = {
                key: spec
                for key, spec in self.specs.items()
                if spec["sheet"] == "Ground_rocks"
                and spec["layer"] == "elevation"
                and spec.get("mountain_type") == expected_type
                and not spec["palette_hidden"]
            }
            expected_keys.update(source_specs)
            keys = {
                item["item_key"]
                for cluster in clusters
                for _position, item in cluster.cells
            }
            found_keys.update(keys)
            self.assertEqual(set(source_specs), keys)
            self.assertTrue(all(
                self.specs[key]["mountain_type"] == expected_type
                for key in keys
            ))
            self.assertTrue(all(
                self.specs[key].get("mountain_group")
                for key in keys
            ))
            artist_cluster = next(
                cluster for cluster in clusters
                if cluster.cols == source_specs[next(iter(source_specs))][
                    "artist_sheet_size"
                ][0]
            )
            expected_cells = {
                (column, row): key
                for key, spec in source_specs.items()
                for column, row in spec["artist_sheet_positions"]
            }
            actual_cells = {
                position: item["item_key"]
                for position, item in artist_cluster.cells
            }
            self.assertEqual(actual_cells, expected_cells)
            self.assertEqual(
                (artist_cluster.cols, artist_cluster.rows),
                tuple(source_specs[next(iter(source_specs))][
                    "artist_sheet_size"
                ]),
            )
            narrow_palette = Palette(
                self.catalog,
                MAP_ASSETS,
                pygame.font.Font(None, 16),
                pygame.font.Font(None, 16),
                tile=20,
                max_panel=260,
                animations=PALETTE_ANIMATIONS,
            )
            narrow_palette.rows = []
            narrow_palette._pack([artist_cluster], 0)
            packed_cells = [
                (row, rect, item)
                for row in narrow_palette.rows
                for rect, item in row.cells
            ]
            self.assertTrue(all(
                rect.w == rect.h
                for _row, rect, _item in packed_cells
            ))
            self.assertEqual(len(packed_cells), len(artist_cluster.cells))

        self.assertEqual(found_keys, expected_keys)
        expected_sheet_keys = {
            key
            for key, spec in self.specs.items()
            if spec["sheet"] == "Ground_rocks"
            and not spec["palette_hidden"]
        }
        full_sheet = next(
            clusters[0]
            for title, clusters in self.palette._sections
            if title == "Биом нежити · Горы — ландшафт с листа художника"
        )
        self.assertGreater(
            len(full_sheet.cells),
            len({item["item_key"] for _position, item in full_sheet.cells}),
        )
        self.assertEqual(
            set(item["item_key"] for _position, item in full_sheet.cells)
            | {
                item["item_key"]
                for title, clusters in mountain_sections.items()
                for cluster in clusters
                for _position, item in cluster.cells
            },
            expected_sheet_keys,
        )

    def test_saved_palette_positions_cannot_break_undead_mountain_groups(self):
        mountain_keys = sorted(
            key
            for key, spec in self.specs.items()
            if spec["sheet"] == "Ground_rocks"
            and spec["layer"] == "elevation"
            and spec.get("mountain_group")
            and not spec["palette_hidden"]
        )
        rules = {
            key: {"palette_position": {"x": index % 10, "y": index // 10}}
            for index, key in enumerate(mountain_keys)
        }
        palette = Palette(
            self.catalog,
            MAP_ASSETS,
            pygame.font.Font(None, 16),
            pygame.font.Font(None, 16),
            animations=PALETTE_ANIMATIONS,
            rules=rules,
        )

        for title, clusters in palette._sections:
            if title not in {
                "Биом нежити · Горы — тёмные скалы",
                "Биом нежити · Горы — скалы с каменной вершиной",
            }:
                continue
            expected_type = "stone" if "каменной вершиной" in title else "dark"
            artist_cluster = next(
                cluster for cluster in clusters
                if cluster.compound and cluster.cols == 31
            )
            expected_positions = {
                (column, row): key
                for key in mountain_keys
                for spec in (self.specs[key],)
                if spec["mountain_type"] == expected_type
                for column, row in spec["artist_sheet_positions"]
            }
            actual_positions = {
                position: item["item_key"]
                for position, item in artist_cluster.cells
            }
            self.assertEqual(actual_positions, expected_positions)

    def test_biome_has_a_distinct_editor_palette(self):
        scene = MapEditorScene(None, self.catalog, lambda: False)
        self.assertIn(("undead", "Нежить"), BIOME_TABS)
        self.assertTrue(scene.biome_catalogs["undead"])
        self.assertTrue(all(
            item["item_key"].startswith("undead_")
            for item in scene.biome_catalogs["undead"]
        ))
        self.assertFalse(any(
            item["item_key"].startswith("undead_")
            for item in scene.biome_catalogs["forest"]
        ))


if __name__ == "__main__":
    unittest.main()
