import os
import math
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from core.map_catalog import catalog_definitions, winter_animated_groups
from scenes.map_editor_scene import (
    ANIMAL_ANIMATIONS, MAP_DIR, MapEditorScene, PALETTE_ANIMATIONS, TREE_ANIMATIONS, WATERFOWL_ANIMATIONS,
)
from scenes.world_map_scene import MAP_TREE_SCALE
from scenes.map_palette import BLOCK_PAD, BLOCK_X, Palette
from scenes.world_map_scene import WorldMapScene
from core.map_animals import animal_sheet


def pixels(surface, rect):
    return pygame.image.tobytes(surface.subsurface(rect), "RGBA")


class PaletteAnimationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        font = pygame.font.SysFont("arial", 14)
        cls.palette = Palette(catalog_definitions(), MAP_DIR, font, font, max_panel=640, animations=PALETTE_ANIMATIONS)
        cls.screen = pygame.Surface((700, 900))
        cls.view = pygame.Rect(0, 0, 700, 900)

    def cell_of(self, key):
        for row in self.palette.rows:
            if row.kind != "block":
                continue
            for rect, item in row.cells:
                if item["item_key"] == key:
                    return row, rect
        self.fail(f"{key} нет в палитре")

    def render(self, key, hovered, ticks):
        row, rect = self.cell_of(key)
        self.screen.fill((0, 0, 0))
        self.palette.draw(self.screen, self.view, row.top, None, hovered=hovered, ticks=ticks)
        return pixels(self.screen, rect.move(BLOCK_X, BLOCK_PAD))

    def test_every_tree_sheet_is_animated(self):
        for key in ("tree1", "tree2", "tree3", "old_tree1", "old_tree2", "old_tree3", "big_tree"):
            self.assertTrue(self.palette.is_animated(key), key)
        self.assertFalse(self.palette.is_animated("dec_001"))

    def test_cell_shows_one_frame_not_the_whole_sheet(self):
        row, rect = self.cell_of("tree1")
        native = self.palette._native_image(row_item(row, "tree1"))
        self.assertEqual(native.get_size(), TREE_ANIMATIONS["tree1"]["frame"])

    def test_map_editor_tree_uses_full_world_frame_size(self):
        catalog = {item["item_key"]: item for item in catalog_definitions()}
        scene = object.__new__(MapEditorScene)
        scene.natives = {}
        scene.state = SimpleNamespace(items=catalog)
        scene.zoom = 1

        self.assertEqual(MAP_TREE_SCALE, 1.0)
        self.assertEqual(scene._native("tree1").get_size(), (160, 256))

    def test_hovered_tree_changes_with_time(self):
        first = self.render("tree1", "tree1", 0)
        later = self.render("tree1", "tree1", TREE_ANIMATIONS["tree1"]["ms"] * 3)
        self.assertNotEqual(first, later)

    def test_animation_loops_over_all_frames(self):
        animation = TREE_ANIMATIONS["tree1"]
        period = animation["ms"] * animation["frames"]
        self.assertEqual(self.render("tree1", "tree1", 0), self.render("tree1", "tree1", period))

    def test_tree_without_hover_stays_still(self):
        self.assertEqual(self.render("tree1", None, 0), self.render("tree1", None, 700))

    def test_hover_on_one_tree_does_not_animate_another(self):
        self.assertEqual(self.render("tree2", "tree1", 0), self.render("tree2", "tree1", 700))

    def test_static_cell_is_the_first_frame(self):
        animation = TREE_ANIMATIONS["tree1"]
        self.assertEqual(self.render("tree1", None, 0), self.render("tree1", "tree1", 0))
        self.assertEqual(self.render("tree1", "tree1", 0), self.render("tree1", "tree1", animation["ms"] - 1))

    def test_every_animal_sheet_is_animated_on_hover(self):
        self.assertEqual(len(ANIMAL_ANIMATIONS), 9)
        for key, animation in ANIMAL_ANIMATIONS.items():
            with self.subTest(key=key):
                self.assertTrue(self.palette.is_animated(key))
                first = self.render(key, key, 0)
                later = self.render(key, key, animation["ms"])
                self.assertNotEqual(first, later)

    def test_animal_animation_resets_when_pointer_leaves(self):
        for key in ANIMAL_ANIMATIONS:
            with self.subTest(key=key):
                static = self.render(key, None, 0)
                later = self.render(key, key, ANIMAL_ANIMATIONS[key]["ms"])
                self.assertNotEqual(static, later)
                self.assertEqual(self.render(key, None, 700), static)
                self.assertEqual(self.render(key, key, 0), static)

    def test_waterfowl_have_separate_hover_animations(self):
        self.assertEqual(set(WATERFOWL_ANIMATIONS), {
            "animal_duck_water", "animal_drake_water", "animal_duckling_water",
        })
        for key, animation in WATERFOWL_ANIMATIONS.items():
            with self.subTest(key=key):
                self.assertTrue(self.palette.is_animated(key))
                first = self.render(key, key, 0)
                later = self.render(key, key, animation["ms"])
                self.assertNotEqual(first, later)
                self.assertEqual(self.render(key, None, 700), self.render(key, None, 0))

    def test_animated_water_preview_is_smaller_and_still_animates_on_hover(self):
        group = winter_animated_groups()[0]
        row, rect = next(
            (row, rect)
            for row in self.palette.rows
            if row.kind == "block"
            for rect, preview in row.previews
            if preview["key"] == group["key"]
        )
        display_rect = self.palette._preview_rect(rect, group)
        self.assertEqual(
            display_rect.size,
            (
                round(rect.w * 0.5),
                round(rect.h * 0.5),
            ),
        )
        self.assertEqual(display_rect.center, rect.center)
        row_surface = self.palette._block_surface(row)
        self.assertEqual(row_surface.get_at(rect.topleft).a, 0)

        screen = pygame.Surface((700, row.height), pygame.SRCALPHA)
        view = pygame.Rect(0, 0, 700, row.height)
        preview_rect = display_rect.move(BLOCK_X, BLOCK_PAD)
        self.palette.draw(
            screen, view, row.top, None, hovered=group["key"], ticks=0,
        )
        first_frame = pixels(screen, preview_rect)
        self.palette.draw(
            screen, view, row.top, None, hovered=group["key"], ticks=150,
        )
        later_frame = pixels(screen, preview_rect)
        self.assertNotEqual(first_frame, later_frame)

    def test_winter_animation_uses_tile_ids_from_the_atlas(self):
        key = "winter_water_detilazation_0232"
        row, _item_rect = self.cell_of(key)
        item = row_item(row, key)
        animation = self.palette.animations[key]
        sheet = pygame.image.load(str(MAP_DIR / item["asset"])).convert_alpha()
        frame_width, frame_height = animation["frame"]
        columns = sheet.get_width() // frame_width
        tile_id = animation["tile_ids"][1]
        expected = sheet.subsurface(pygame.Rect(
            (tile_id % columns) * frame_width,
            (tile_id // columns) * frame_height,
            frame_width,
            frame_height,
        ))

        actual = self.palette._native_image(item, frame=1)
        self.assertEqual(
            pygame.image.tobytes(actual, "RGBA"),
            pygame.image.tobytes(expected, "RGBA"),
        )

    def test_map_editor_uses_one_sprite_frame_for_every_animal(self):
        catalog = {item["item_key"]: item for item in catalog_definitions()}
        scene = object.__new__(MapEditorScene)
        scene.natives = {}
        scene.state = SimpleNamespace(items=catalog)

        animal_keys = [key for key, item in catalog.items() if item["category"] == "animal"]
        self.assertEqual(len(animal_keys), 12)
        for key in animal_keys:
            with self.subTest(key=key):
                image = scene._native(key)
                self.assertEqual(image.get_size(), PALETTE_ANIMATIONS[key]["frame"])

    def test_live_world_animals_use_facing_and_movement_rows(self):
        catalog = [item for item in catalog_definitions() if item["category"] == "animal"]
        scene = object.__new__(WorldMapScene)
        scene.animal_frames = {}
        self.assertEqual(len(catalog), 12)
        directions = (
            (math.pi / 2, 0),
            (-math.pi / 2, 1),
            (math.pi, 2),
            (0.0, 3),
        )
        for item in catalog:
            key = item["item_key"]
            layout = animal_sheet(key)
            source = pygame.image.load(
                MAP_DIR / "animals" / f"{layout.asset}.png"
            ).convert_alpha()
            walk_row_start = 8 if key.endswith("_water") else 0
            idle_row_start = walk_row_start + 4
            with self.subTest(key=item["item_key"]):
                for facing, direction in directions:
                    walking = scene._animal_frame_for(key, facing, True, 0)
                    expected_walk = source.subsurface(pygame.Rect(
                        0, (walk_row_start + direction) * layout.frame_size,
                        layout.frame_size, layout.frame_size,
                    ))
                    self.assertEqual(pygame.image.tobytes(walking, "RGBA"), pygame.image.tobytes(expected_walk, "RGBA"))

                    idle = scene._animal_frame_for(key, facing, False, 0)
                    expected_idle = source.subsurface(pygame.Rect(
                        0, (idle_row_start + direction) * layout.frame_size,
                        layout.frame_size, layout.frame_size,
                    ))
                    self.assertEqual(pygame.image.tobytes(idle, "RGBA"), pygame.image.tobytes(expected_idle, "RGBA"))

    def test_live_world_animal_walk_frames_animate_but_idle_stays_still(self):
        scene = object.__new__(WorldMapScene)
        scene.animal_frames = {}
        self.assertNotEqual(
            pygame.image.tobytes(scene._animal_frame_for("animal_buffalo", 0.0, True, 0), "RGBA"),
            pygame.image.tobytes(scene._animal_frame_for("animal_buffalo", 0.0, True, 160), "RGBA"),
        )
        self.assertEqual(
            pygame.image.tobytes(scene._animal_frame_for("animal_buffalo", 0.0, False, 0), "RGBA"),
            pygame.image.tobytes(scene._animal_frame_for("animal_buffalo", 0.0, False, 160), "RGBA"),
        )


def row_item(row, key):
    return next(item for _rect, item in row.cells if item["item_key"] == key)


if __name__ == "__main__":
    unittest.main()
