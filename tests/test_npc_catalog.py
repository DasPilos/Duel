import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from core.map_catalog import catalog_definitions
from core.npc_catalog import NPC_CATALOG, NPC_FRAME, NPC_FRAMES_PER_ROW, npc_catalog, sheet_path
from scenes.map_editor_scene import MapEditorScene


class NpcCatalogTests(unittest.TestCase):
    def test_imp_has_five_variants_in_three_colors_with_unique_keys(self):
        keys = [npc["key"] for npc in NPC_CATALOG]
        self.assertEqual(len(keys), 15)
        self.assertEqual(len(set(keys)), 15)
        self.assertTrue(all(key.startswith("imp_") for key in keys))

    def test_every_sheet_exists_and_is_a_4x4_grid(self):
        side = NPC_FRAME * NPC_FRAMES_PER_ROW
        for npc in NPC_CATALOG:
            for action in ("walk", "attack"):
                path = sheet_path(npc, action)
                self.assertTrue(path.is_file(), path)
                size = pygame.image.load(str(path)).get_size()
                self.assertEqual(size, (side, side), path)

    def test_catalog_copy_does_not_change_the_original(self):
        copy = npc_catalog()
        copy[0]["name"] = "изменено"
        self.assertNotEqual(NPC_CATALOG[0]["name"], "изменено")


class MapEditorNpcTabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1920, 1080))

    def setUp(self):
        self.scene = MapEditorScene(None, catalog_definitions(), lambda: False)
        self.scene.has_map = True

    def click(self, pos):
        self.scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))

    def test_tabs_fit_inside_the_palette_panel(self):
        panel = self.scene.panel_rect()
        for _section, _label, rect in self.scene._tab_rects():
            self.assertTrue(panel.contains(rect), rect)

    def test_npc_tab_switches_and_selects_an_imp(self):
        npc_tab = next(rect for section, _label, rect in self.scene._tab_rects() if section == "npc")
        self.click(npc_tab.center)
        self.assertEqual(self.scene.section, "npc")
        self.click(self.scene._npc_row_rect(1).center)
        self.assertEqual(self.scene.selected_npc, "imp_sword")
        map_tab = next(rect for section, _label, rect in self.scene._tab_rects() if section == "map")
        self.click(map_tab.center)
        self.assertEqual(self.scene.section, "map")

    def test_npc_list_scrolls_and_click_picks_the_scrolled_row(self):
        self.scene._set_section("npc")
        self.assertGreater(self.scene._max_scroll(), 0)
        self.scene.list_scroll = self.scene._max_scroll()
        last = len(self.scene.npc_list) - 1
        self.click(self.scene._npc_row_rect(last).center)
        self.assertEqual(self.scene.selected_npc, self.scene.npc_list[last]["key"])
        self.scene.list_scroll = 0
        self.assertIsNone(self.scene._npc_at((self.scene._npc_row_rect(last).centerx, self.scene._list_bottom() + 5)))

    def test_n_key_toggles_the_section_and_draws(self):
        screen = pygame.display.get_surface()
        self.scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_n, mod=0, unicode="n"))
        self.assertEqual(self.scene.section, "npc")
        self.scene.draw(screen)
        self.scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_n, mod=0, unicode="n"))
        self.assertEqual(self.scene.section, "map")


if __name__ == "__main__":
    unittest.main()
