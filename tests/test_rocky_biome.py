import os
import unittest
from collections import defaultdict
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from core.map_catalog import (
    ROCKY_GROUND_MOSS_GRASS_TILE_IDS,
    catalog_definitions,
    rocky_animated_groups,
    rocky_animations,
    rocky_tile_specs,
    rocky_water_object_groups,
)
from client.map_editor_state import MapEditorState
from scenes.map_editor_scene import MAP_DIR, MapEditorScene, PALETTE_ANIMATIONS
from scenes.map_palette import (
    BLOCK_PAD,
    BLOCK_X,
    Palette,
    animation_frame_index,
    rocky_tile_frame,
    series_base,
)


class RockyBiomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.catalog = catalog_definitions()
        cls.rocky_items = [item for item in cls.catalog if item["item_key"].startswith("rocky_")]
        cls.items_by_key = {item["item_key"]: item for item in cls.rocky_items}

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_tiled_import_includes_sources_objects_and_animated_tiles(self):
        specs = rocky_tile_specs()
        spec_items = [item for item in self.catalog if item["item_key"] in specs]
        self.assertEqual(len(specs), len(spec_items))
        self.assertGreater(len(self.rocky_items), 600)
        self.assertLess(len(self.rocky_items), 1000)
        self.assertTrue(all(item["asset"].startswith("rocky\\") or item["asset"].startswith("rocky/")
                            for item in self.rocky_items))
        self.assertEqual(set(rocky_animations()), set(PALETTE_ANIMATIONS) & set(rocky_animations()))
        self.assertGreaterEqual(len(rocky_animations()), 250)
        self.assertLess(len(rocky_animations()), 350)
        for key, animation in rocky_animations().items():
            with self.subTest(key=key):
                self.assertEqual(animation["frames"], len(animation["durations"]))
                self.assertEqual(animation["frames"], len(animation["tile_ids"]))
                self.assertTrue(all(duration > 0 for duration in animation["durations"]))
                self.assertIn(key, specs)

    def test_objects_are_exported_as_complete_sprites_not_source_tiles(self):
        sprites = [spec for spec in rocky_tile_specs().values() if spec["sheet"] == "Objects"]
        self.assertGreaterEqual(len(sprites), 70)
        self.assertLessEqual(len(sprites), 120)
        for spec in sprites:
            with self.subTest(asset=spec["asset"]):
                self.assertEqual(spec["representation"], "sprite")
                image = pygame.image.load(str(MAP_DIR / spec["asset"])).convert_alpha()
                self.assertGreater(image.get_width(), 0)
                self.assertGreater(image.get_height(), 0)
                self.assertGreater(pygame.mask.from_surface(image).count(), 100)
                if spec["key"] in {"rocky_objects_060", "rocky_objects_061"}:
                    components = pygame.mask.from_surface(image, 1).connected_components()
                    self.assertEqual(len(components), 1)
                    sample = (20, 20) if spec["key"] == "rocky_objects_060" else (44, 30)
                    self.assertEqual(image.get_at(sample).a, 0)

    def test_growth_sprite_size_metadata_matches_visible_source_bounds(self):
        growth = [item for item in self.catalog if item.get("growth_series")]
        self.assertTrue(growth)
        for item in growth:
            with self.subTest(key=item["item_key"]):
                image = pygame.image.load(str(MAP_DIR / item["asset"])).convert_alpha()
                visible = image.get_bounding_rect()
                self.assertEqual(item["growth_size"], visible.width * visible.height)

    def test_author_rock_growth_series_include_all_five_stages(self):
        growth = [
            item for item in self.catalog
            if item.get("growth_series", "").startswith("rocky_rock")
        ]
        expected_series = {
            f"rocky_rock{rock}_{surface}"
            for rock in range(1, 4)
            for surface in ("grass", "ground")
        }
        by_series = defaultdict(list)
        for item in growth:
            by_series[item["growth_series"]].append(item)

        specs = rocky_tile_specs()
        self.assertEqual(set(by_series), expected_series)
        for series, items in by_series.items():
            with self.subTest(series=series):
                self.assertEqual({item["growth_stage"] for item in items}, set(range(1, 6)))
                self.assertTrue(all(
                    specs[item["item_key"]]["sheet"] == "Objects_separately"
                    for item in items
                ))
                self.assertTrue(all(item["asset"].startswith("rocky/growth/") for item in items))

    def test_detail_sheet_objects_are_exported_as_complete_sprites(self):
        detail_sprites = [
            item for item in rocky_tile_specs().values()
            if item.get("sheet") == "details"
            and item.get("representation") == "sprite"
        ]
        self.assertEqual(len(detail_sprites), 30)
        by_key = {item["key"]: item for item in detail_sprites}
        self.assertIn("rocky_details_object_010", by_key)
        self.assertEqual(
            by_key["rocky_details_object_010"]["source_tile_ids"],
            [153, 154, 173, 174],
        )
        for item in detail_sprites:
            with self.subTest(key=item["key"]):
                image = pygame.image.load(str(MAP_DIR / item["asset"])).convert_alpha()
                self.assertEqual(image.get_bounding_rect(), image.get_rect())
                self.assertGreater(pygame.mask.from_surface(image).count(), 100)

        hidden_parts = {
            f"rocky_details_{tile_id:04d}"
            for item in detail_sprites
            for tile_id in item["source_tile_ids"]
            if f"rocky_details_{tile_id:04d}" in rocky_tile_specs()
        }
        specs = rocky_tile_specs()
        self.assertTrue(all(specs[key]["palette_hidden"] for key in hidden_parts))
        self.assertTrue(any(item["palette_hidden"] for item in detail_sprites))
        self.assertTrue(all(
            item["palette_hidden"]
            for item in specs.values()
            if item["sheet"] == "details" and item.get("representation") != "sprite"
        ))

    def test_animation_frames_and_duplicate_sprites_are_not_repeated_in_palette(self):
        frame_ids_by_sheet = defaultdict(set)
        animation_signatures = defaultdict(set)
        visible_sprites = set()
        hidden_sprites = 0

        for key, animation in rocky_animations().items():
            spec = rocky_tile_specs()[key]
            frame_ids_by_sheet[spec["sheet"]].update(animation["tile_ids"])
            if spec.get("palette_hidden", False):
                continue
            sheet = pygame.image.load(str(MAP_DIR / spec["asset"])).convert_alpha()
            signature = tuple(
                pygame.image.tobytes(rocky_tile_frame(key, sheet, frame), "RGBA")
                for frame in range(animation["frames"])
            )
            with self.subTest(animation=key):
                self.assertNotIn(signature, animation_signatures[spec["sheet"]])
            animation_signatures[spec["sheet"]].add(signature)

        for spec in rocky_tile_specs().values():
            if (
                spec.get("representation") != "sprite"
                and not spec.get("durations")
                and spec["tile_id"] in frame_ids_by_sheet[spec["sheet"]]
            ):
                self.assertTrue(spec.get("palette_hidden", False), spec["key"])
            if spec.get("representation") != "sprite":
                continue
            image = pygame.image.load(str(MAP_DIR / spec["asset"])).convert_alpha()
            signature = (image.get_size(), pygame.image.tobytes(image, "RGBA"))
            if spec.get("palette_hidden", False):
                hidden_sprites += 1
            else:
                self.assertNotIn(signature, visible_sprites, spec["key"])
                visible_sprites.add(signature)

        self.assertGreater(hidden_sprites, 0)

    def test_tile_0379_is_flipped_horizontally_in_every_animation_frame(self):
        key = "rocky_water_detilazation2_0378"
        spec = rocky_tile_specs()[key]
        self.assertEqual(spec["display_name"], "Тайл 0379")
        self.assertEqual(spec["tile_id"], 378)
        self.assertTrue(spec["flip_x"])

        sheet = pygame.image.load(str(MAP_DIR / spec["asset"])).convert_alpha()
        tile_size = sheet.get_width() // spec["columns"]
        for frame, tile_id in enumerate(spec["frame_tile_ids"]):
            column, row = tile_id % spec["columns"], tile_id // spec["columns"]
            original = sheet.subsurface(pygame.Rect(
                column * tile_size,
                row * tile_size,
                tile_size,
                tile_size,
            ))
            expected = pygame.transform.flip(original, True, False)
            actual = rocky_tile_frame(key, sheet, frame)
            with self.subTest(frame=frame, tile_id=tile_id):
                self.assertEqual(
                    pygame.image.tobytes(actual, "RGBA"),
                    pygame.image.tobytes(expected, "RGBA"),
                )

        adjacent_key = "rocky_water_detilazation2_0379"
        adjacent_spec = rocky_tile_specs()[adjacent_key]
        self.assertFalse(adjacent_spec.get("flip_x", False))

    def test_exact_static_tiles_are_not_repeated_in_the_palette(self):
        signatures = defaultdict(set)
        sheets = {}
        for key, spec in rocky_tile_specs().items():
            if (
                spec.get("palette_hidden", False)
                or spec.get("representation") == "sprite"
                or spec.get("durations")
            ):
                continue
            if spec["asset"] not in sheets:
                sheets[spec["asset"]] = pygame.image.load(
                    str(MAP_DIR / spec["asset"])
                ).convert_alpha()
            sheet = sheets[spec["asset"]]
            image = rocky_tile_frame(key, sheet)
            signature = pygame.image.tobytes(image, "RGBA")
            signature_key = (spec["layer"], signature)
            with self.subTest(key=key):
                self.assertNotIn(signature_key, signatures[spec["sheet"]])
            signatures[spec["sheet"]].add(signature_key)

    def test_palette_cache_keeps_tiles_from_the_same_sheet_distinct(self):
        palette = Palette(
            self.catalog,
            MAP_DIR,
            pygame.font.Font(None, 12),
            pygame.font.Font(None, 12),
            animations=rocky_animations(),
        )
        sheet_items = [
            self.items_by_key[key]
            for key, spec in rocky_tile_specs().items()
            if spec["sheet"] == "Ground_moss"
            and spec.get("representation") != "sprite"
        ]
        sheet = pygame.image.load(
            str(MAP_DIR / sheet_items[0]["asset"])
        ).convert_alpha()
        distinct_items = None
        for index, first in enumerate(sheet_items):
            first_image = rocky_tile_frame(first["item_key"], sheet)
            for second in sheet_items[index + 1:]:
                second_image = rocky_tile_frame(second["item_key"], sheet)
                if pygame.image.tobytes(first_image, "RGBA") != pygame.image.tobytes(second_image, "RGBA"):
                    distinct_items = (first, second)
                    break
            if distinct_items is not None:
                break

        self.assertIsNotNone(distinct_items)
        for item in distinct_items:
            with self.subTest(key=item["item_key"]):
                actual = palette._cell_image(item, (32, 32))
                expected = rocky_tile_frame(item["item_key"], sheet)
                self.assertEqual(
                    pygame.image.tobytes(actual, "RGBA"),
                    pygame.image.tobytes(expected, "RGBA"),
                )

    def test_tiled_layer_roles_map_to_existing_editor_layers(self):
        palette = Palette(
            self.catalog,
            MAP_DIR,
            pygame.font.Font(None, 12),
            pygame.font.Font(None, 12),
            max_panel=500,
        )
        visible_specs = {
            key: spec
            for key, spec in rocky_tile_specs().items()
            if not spec.get("palette_hidden", False)
        }
        for role, expected_layer in (
            ("ground", "ground"),
            ("overlay", "overlay"),
            ("elevation", "elevation"),
            ("infra", "infra"),
        ):
            key = next(
                key for key, spec in visible_specs.items()
                if spec.get("representation") != "sprite" and spec["layer"] == role
            )
            hit = next(
                (row, rect)
                for row in palette.rows
                if row.kind == "block"
                for rect, item in row.cells
                if item["item_key"] == key
            )
            row, rect = hit
            point = (rect.centerx + 12, row.top + 4 + rect.centery)
            self.assertEqual(palette.item_layer_at(*point), expected_layer, key)
            self.assertIn("tiled_layers", visible_specs[key])
            state = MapEditorState(self.catalog, [], 8, 8)
            if visible_specs[key]["category"] == "water" and expected_layer == "overlay":
                water_key = next(
                    water_key for water_key, spec in visible_specs.items()
                    if spec["sheet"] == "Water_coasts"
                )
                self.assertIsNone(state.place(water_key, 0, 0))
            self.assertIsNone(state.place(key, 0, 0, layer=palette.item_layer_at(*point)))
            self.assertEqual(getattr(state, expected_layer)[(0, 0)], key)

    def test_scrolling_to_bottom_renders_all_layer_roles(self):
        palette = Palette(
            self.catalog,
            MAP_DIR,
            pygame.font.Font(None, 12),
            pygame.font.Font(None, 12),
            max_panel=500,
        )
        screen = pygame.Surface((520, 640), pygame.SRCALPHA)
        view = pygame.Rect(0, 0, 500, 640)
        for scroll in range(0, palette.height, view.height):
            with self.subTest(scroll=scroll):
                palette.draw(screen, view, scroll, None)

    def test_objects_used_under_elevated_spaces_render_behind_them(self):
        under_key = next(
            key for key, spec in rocky_tile_specs().items()
            if spec.get("render_order") == "under_elevation"
        )
        foreground_key = next(
            key for key, spec in rocky_tile_specs().items()
            if spec.get("representation") == "sprite"
            and spec.get("render_order") == "foreground"
            and not spec.get("palette_hidden", False)
        )
        elevation_key = next(
            key for key, spec in rocky_tile_specs().items()
            if spec.get("representation") != "sprite" and spec["layer"] == "elevation"
        )
        state = SimpleNamespace(
            map_w=2,
            map_h=1,
            ground={},
            overlay={},
            elevation={(0, 0): elevation_key},
            relief={},
            infra={},
            objects={(0, 0): under_key},
            items={
                key: {"footprint_w": 1, "footprint_h": 1, "category": "bush"}
                for key in (under_key, foreground_key)
            },
        )
        scene = object.__new__(MapEditorScene)
        scene.state = state
        scene.zoom = 32
        scene.origin_x = 0
        scene.origin_y = 0
        scene.show_grid = False
        scene.active_map_layer = 0
        scene.editor_layers = [state]
        scene.editor_layer_visible = [True]
        scene.editor_layer_70 = [False]
        scene.grid_rect = lambda: pygame.Rect(0, 0, 64, 32)
        scene._scaled_at_time = lambda key, _zoom, _ticks: pygame.Surface((32, 32))
        scene._footprint_rect = lambda _key, _x, _y: pygame.Rect(0, 0, 32, 32)
        scene._object_rect = lambda _key, image, footprint: image.get_rect(topleft=footprint.topleft)
        scene._draw_mobs = lambda *_args: None
        scene._draw_spawns = lambda *_args: None
        scene._draw_selection = lambda *_args: None
        scene._draw_hover = lambda *_args: None
        colors = {under_key: (255, 0, 0, 255), foreground_key: (0, 255, 0, 255)}

        def image_for(key, _zoom, _ticks):
            image = pygame.Surface((32, 32), pygame.SRCALPHA)
            image.fill(colors.get(key, (0, 0, 255, 255)))
            return image

        scene._scaled_at_time = image_for
        screen = pygame.Surface((64, 32), pygame.SRCALPHA)
        scene._draw_grid(screen)
        self.assertEqual(screen.get_at((16, 16)), (0, 0, 255, 255))

        state.objects[(1, 0)] = foreground_key
        screen.fill((0, 0, 0, 0))
        scene._draw_grid(screen)
        self.assertEqual(screen.get_at((16, 16)), (0, 255, 0, 255))

    def test_rocky_elevation_tiles_block_movement(self):
        elevation_tiles = [
            spec for spec in rocky_tile_specs().values()
            if spec["key"].startswith("rocky_")
            and spec.get("layer") == "elevation"
            and spec.get("category") != "bush"
        ]
        self.assertTrue(elevation_tiles)
        for spec in elevation_tiles:
            with self.subTest(key=spec["key"]):
                is_grass = (
                    spec["sheet"] == "Ground_moss"
                    and spec["tile_id"] in ROCKY_GROUND_MOSS_GRASS_TILE_IDS
                )
                self.assertEqual(self.items_by_key[spec["key"]]["blocks"], not is_grass)

    def test_rocky_grass_tiles_are_separated_from_impassable_rocks(self):
        palette = Palette(
            self.catalog,
            MAP_DIR,
            pygame.font.Font(None, 16),
            pygame.font.Font(None, 16),
            max_panel=640,
            animations=PALETTE_ANIMATIONS,
        )
        titles = [title for title, _clusters in palette._sections]
        self.assertIn("Скалистый биом · Трава", titles)
        self.assertIn("Скалистый биом · Скалы и возвышенности", titles)
        grass_clusters = next(
            clusters for title, clusters in palette._sections
            if title == "Скалистый биом · Трава"
        )
        grass_ids = {
            rocky_tile_specs()[item["item_key"]]["tile_id"]
            for cluster in grass_clusters
            for _position, item in cluster.cells
        }
        self.assertEqual(grass_ids, ROCKY_GROUND_MOSS_GRASS_TILE_IDS)

    def test_biome_sections_are_separate_and_visible_in_the_palette(self):
        font = pygame.font.SysFont("arial", 12)
        palette = Palette(self.catalog, MAP_DIR, font, font, max_panel=500)
        titles = {title for title, _clusters in palette._sections}
        self.assertTrue({
            "Скалистый биом · Земля (основа)",
            "Скалистый биом · Ландшафт с листа художника",
            "Скалистый биом · Скалы и возвышенности",
            "Скалистый биом · Береговая вода (основа)",
            "Скалистый биом · Водопады",
            "Скалистый биом · Цельные объекты",
            "Скалистый биом · Цельные детали и растения",
        }.issubset(titles))
        rocky_keys = {
            item["item_key"]
            for _title, clusters in palette._sections
            if _title.startswith("Скалистый биом")
            for cluster in clusters
            for _position, item in cluster.cells
        }
        visible_keys = {
            key for key, spec in rocky_tile_specs().items()
            if not spec.get("palette_hidden", False)
        }
        compound_keys = {
            cell["key"]
            for group in rocky_animated_groups()
            for cell in group["cells"]
        }
        water_object_keys = {
            cell["key"]
            for group in rocky_water_object_groups()
            for cell in group["cells"]
        }
        self.assertEqual(rocky_keys, visible_keys | compound_keys | water_object_keys)

    def test_ground_moss_artist_layout_keeps_repeated_tiles_in_context(self):
        palette = Palette(
            self.catalog,
            MAP_DIR,
            pygame.font.Font(None, 16),
            pygame.font.Font(None, 16),
            max_panel=640,
            animations=PALETTE_ANIMATIONS,
        )
        cluster = next(
            clusters[0]
            for title, clusters in palette._sections
            if title == "Скалистый биом · Ландшафт с листа художника"
        )
        specs = rocky_tile_specs()
        expected_cells = {
            tuple(position): key
            for key, spec in specs.items()
            if spec["sheet"] == "Ground_moss"
            and not spec.get("palette_hidden", False)
            for position in spec.get("artist_sheet_positions", [])
        }
        actual_cells = {
            position: item["item_key"]
            for position, item in cluster.cells
        }

        self.assertEqual((cluster.cols, cluster.rows), (20, 16))
        self.assertEqual(actual_cells, expected_cells)
        self.assertGreater(
            len(cluster.cells),
            len({item["item_key"] for _position, item in cluster.cells}),
        )
        self.assertTrue(all(
            item.get("palette_artist_copy")
            for _position, item in cluster.cells
        ))

        copied_roles = set()
        for row in palette.rows:
            for rect, item in row.cells:
                if (
                    not item.get("palette_artist_copy")
                    or item["item_key"] not in specs
                ):
                    continue
                role = specs[item["item_key"]]["layer"]
                copied_roles.add(role)
                self.assertEqual(
                    palette.item_layer_at(
                        BLOCK_X + rect.centerx,
                        row.top + BLOCK_PAD + rect.centery,
                    ),
                    {"ground": "ground", "elevation": "elevation", "infra": "infra"}[role],
                )
        self.assertEqual(copied_roles, {"ground", "elevation"})

    def test_rocky_palette_keeps_tiles_in_atlas_order_and_separates_elevation(self):
        palette = Palette(
            self.catalog,
            MAP_DIR,
            pygame.font.Font(None, 12),
            pygame.font.Font(None, 12),
            max_panel=500,
        )
        _, elevation_clusters = next(
            (title, clusters)
            for title, clusters in palette._sections
            if title == "Скалистый биом · Скалы и возвышенности"
        )
        self.assertTrue(elevation_clusters)
        cluster_first_ids = [
            min(
                rocky_tile_specs()[item["item_key"]]["tile_id"]
                for _position, item in cluster.cells
            )
            for cluster in elevation_clusters
        ]
        self.assertEqual(cluster_first_ids, sorted(cluster_first_ids))
        elevation_keys = {
            item["item_key"]
            for cluster in elevation_clusters
            for _position, item in cluster.cells
        }
        self.assertTrue(elevation_keys)
        self.assertTrue(all(
            rocky_tile_specs()[key]["sheet"] == "Ground_moss"
            and rocky_tile_specs()[key]["layer"] == "elevation"
            for key in elevation_keys
        ))

    def test_tiled_animation_durations_and_cropped_frames_are_used(self):
        key = next(
            key for key in rocky_animations()
            if (lambda sheet: pygame.image.tobytes(rocky_tile_frame(key, sheet, 0), "RGBA")
                != pygame.image.tobytes(rocky_tile_frame(key, sheet, 1), "RGBA"))(
                    pygame.image.load(str(MAP_DIR / self.items_by_key[key]["asset"])).convert_alpha()
                )
        )
        animation = PALETTE_ANIMATIONS[key]
        self.assertEqual(animation_frame_index(animation, 0), 0)
        self.assertEqual(animation_frame_index(animation, animation["durations"][0]), 1)

        scene = object.__new__(MapEditorScene)
        scene.natives = {}
        scene.asset_sheets = {}
        scene.scaled = {}
        scene.state = SimpleNamespace(items=self.items_by_key)
        first = scene._scaled_at_time(key, 32, 0)
        second = scene._scaled_at_time(key, 32, animation["durations"][0])
        self.assertEqual(first.get_size(), (32, 32))
        self.assertNotEqual(
            pygame.image.tobytes(first, "RGBA"),
            pygame.image.tobytes(second, "RGBA"),
        )

    def test_hovering_a_water_composition_animates_all_of_its_tiles(self):
        palette = Palette(
            self.catalog,
            MAP_DIR,
            pygame.font.Font(None, 12),
            pygame.font.Font(None, 12),
            max_panel=500,
            animations=rocky_animations(),
        )
        chosen = None
        for group in rocky_animated_groups():
            animated = []
            for cell in group["cells"]:
                key = cell["key"]
                animation = rocky_animations().get(key)
                if animation is None or animation["frames"] < 2:
                    continue
                sheet = pygame.image.load(
                    str(MAP_DIR / self.items_by_key[key]["asset"])
                ).convert_alpha()
                if pygame.image.tobytes(rocky_tile_frame(key, sheet, 0), "RGBA") != pygame.image.tobytes(
                    rocky_tile_frame(key, sheet, 1),
                    "RGBA",
                ):
                    animated.append(key)
            if len(animated) > 1:
                chosen = (group["cells"][0]["key"], animated[1])
                break
        self.assertIsNotNone(chosen)
        hovered, changing_key = chosen
        animation = rocky_animations()[changing_key]
        row, rect = next(
            (row, rect)
            for row in palette.rows
            if row.kind == "block"
            for rect, item in row.cells
            if item["item_key"] == changing_key
        )
        screen = pygame.Surface((500, row.height), pygame.SRCALPHA)
        view = pygame.Rect(0, 0, 500, row.height)
        palette.draw(screen, view, row.top, None, hovered=hovered, ticks=0)
        cell = rect.move(12, 4)
        first = screen.subsurface(cell).copy()
        palette.draw(
            screen,
            view,
            row.top,
            None,
            hovered=hovered,
            ticks=animation["durations"][0],
        )
        second = screen.subsurface(cell).copy()
        self.assertNotEqual(
            pygame.image.tobytes(first, "RGBA"),
            pygame.image.tobytes(second, "RGBA"),
        )

    def test_ground_water_overlay_and_objects_use_their_editor_layers(self):
        state = MapEditorState(self.catalog, [], 8, 8)
        ground_key = next(
            key for key, spec in rocky_tile_specs().items()
            if spec["sheet"] == "Ground_moss"
        )
        water_key = next(
            key for key, spec in rocky_tile_specs().items()
            if spec["sheet"] == "Water_coasts"
        )
        waterfall_key = next(
            key for key, spec in rocky_tile_specs().items()
            if spec["sheet"] == "Waterfalls" and spec["layer"] == "overlay"
        )
        object_key = next(
            key for key, spec in rocky_tile_specs().items()
            if spec["sheet"] == "Objects"
        )

        self.assertIsNone(state.place(ground_key, 0, 0))
        self.assertIsNone(state.place(water_key, 1, 0))
        self.assertIsNone(state.place(water_key, 2, 0))
        self.assertIsNone(state.place(waterfall_key, 2, 0))
        self.assertIsNone(state.place(object_key, 3, 0))
        self.assertEqual(state.ground[(0, 0)], ground_key)
        self.assertEqual(state.ground[(1, 0)], water_key)
        self.assertEqual(state.overlay[(2, 0)], waterfall_key)
        self.assertEqual(state.objects[(3, 0)], object_key)

    def test_animated_water_effects_are_inserted_as_whole_stamps(self):
        group = rocky_animated_groups()[0]
        entries = [
            (cell["x"], cell["y"], cell["key"], "overlay")
            for cell in group["cells"]
        ]
        state = MapEditorState(self.catalog, [], 32, 16)
        stamp = state.make_stamp(entries)
        self.assertIsNotNone(stamp)
        self.assertEqual(stamp["w"], max(cell["x"] for cell in group["cells"]) + 1)
        self.assertEqual(stamp["h"], max(cell["y"] for cell in group["cells"]) + 1)
        self.assertEqual(len(stamp["overlay"]), len(group["cells"]))

        self.assertEqual(
            state.paste(stamp, 1, 1),
            "Водные эффекты можно размещать только на тайлах воды",
        )
        self.assertEqual(state.overlay, {})
        self.assertFalse(state.dirty)

        for dx, dy, _key in stamp["overlay"]:
            self.assertIsNone(state.place(
                next(key for key, spec in rocky_tile_specs().items()
                     if spec["sheet"] == "Water_coasts"),
                1 + dx,
                1 + dy,
            ))
        self.assertIsNone(state.paste(stamp, 1, 1))
        self.assertEqual(len(state.overlay), len(group["cells"]))

    def test_water_object_stamp_keeps_sprite_and_animated_waves_together(self):
        group = next(group for group in rocky_water_object_groups() if group["key"].endswith("_boat"))
        entries = [
            (cell["x"], cell["y"], cell["key"], cell["layer"])
            for cell in group["cells"]
        ]
        overlay_cells = [cell for cell in group["cells"] if cell["layer"] == "overlay"]
        self.assertTrue(overlay_cells)
        self.assertTrue(all(
            cell["key"].startswith("rocky_water_under_objects_")
            for cell in overlay_cells
        ))
        state = MapEditorState(self.catalog, [], 32, 16)
        stamp = state.make_stamp(entries)
        self.assertIsNotNone(stamp)
        self.assertEqual(len(stamp["objects"]), 1)
        self.assertGreater(len(stamp["overlay"]), 0)
        self.assertEqual(
            state.paste(stamp, 1, 1),
            "Водные эффекты можно размещать только на тайлах воды",
        )
        water_key = next(
            key for key, spec in rocky_tile_specs().items()
            if spec["sheet"] == "Water_coasts"
        )
        for dx, dy, _key in stamp["overlay"]:
            self.assertIsNone(state.place(water_key, 1 + dx, 1 + dy))
        self.assertIsNone(state.paste(stamp, 1, 1))
        self.assertEqual(len(state.objects), 1)
        self.assertEqual(
            len(state.overlay),
            len({(dx, dy) for dx, dy, _key in stamp["overlay"]}),
        )

    def test_growth_stage_sprites_share_their_visible_base_on_the_map(self):
        growth = [
            item for item in self.catalog
            if item.get("growth_series") == "rocky_conifer_tree1"
        ]
        scene = SimpleNamespace(state=SimpleNamespace(items={item["item_key"]: item for item in growth}))
        footprint = pygame.Rect(60, 80, 32, 32)
        bases = []
        for item in growth:
            image = pygame.image.load(str(MAP_DIR / item["asset"])).convert_alpha()
            rect = MapEditorScene._object_rect(scene, item["item_key"], image, footprint)
            base_x, base_y = series_base(image)
            bases.append((rect.left + base_x, rect.top + base_y))
        self.assertEqual(bases, [(footprint.centerx, footprint.bottom)] * len(growth))

    def test_water_effect_cannot_be_placed_or_left_over_land(self):
        effect_key = next(
            key for key, spec in rocky_tile_specs().items()
            if spec["sheet"] == "Water_detilazation2"
            and spec.get("palette_hidden", False)
            and spec.get("frame_tile_ids")
        )
        state = MapEditorState(self.catalog, [], 8, 8)
        self.assertEqual(
            state.place(effect_key, 2, 2, layer="overlay"),
            "Водные эффекты можно размещать только на тайлах воды",
        )
        self.assertEqual(state.overlay, {})
        self.assertIsNone(state.place(
            next(key for key, spec in rocky_tile_specs().items()
                 if spec["sheet"] == "Water_coasts"),
            2,
            2,
        ))
        self.assertIsNone(state.place(effect_key, 2, 2, layer="overlay"))
        replacement = next(
            key for key, spec in rocky_tile_specs().items()
            if spec["sheet"] == "Ground_moss" and spec["layer"] == "ground"
        )
        self.assertEqual(
            state.place(replacement, 2, 2),
            "Водные эффекты можно размещать только на тайлах воды",
        )
        self.assertEqual(state.ground[(2, 2)], next(
            key for key, spec in rocky_tile_specs().items()
            if spec["sheet"] == "Water_coasts"
        ))


if __name__ == "__main__":
    unittest.main()
