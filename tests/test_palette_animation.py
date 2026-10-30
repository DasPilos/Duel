import os
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from core.map_catalog import catalog_definitions
from scenes.map_editor_scene import MAP_DIR, TREE_ANIMATIONS
from scenes.map_palette import BLOCK_PAD, BLOCK_X, Palette


def pixels(surface, rect):
    return pygame.image.tobytes(surface.subsurface(rect), "RGBA")


class PaletteAnimationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        font = pygame.font.SysFont("arial", 14)
        cls.palette = Palette(catalog_definitions(), MAP_DIR, font, font, max_panel=640, animations=TREE_ANIMATIONS)
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


def row_item(row, key):
    return next(item for _rect, item in row.cells if item["item_key"] == key)


if __name__ == "__main__":
    unittest.main()
