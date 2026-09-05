import unittest

import pygame

from ui.character_profile_overlay import CharacterProfileOverlay
from ui.collection_panel import CollectionPanel


class CollectionPanelTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.panel = CollectionPanel()

    def tearDown(self):
        pygame.quit()

    def test_collection_uses_six_by_ten_card_grid(self):
        self.assertEqual(self.panel.COLS, 6)
        self.assertEqual(self.panel.ROWS, 10)
        self.assertEqual(self.panel.CARD_WIDTH, 250)
        self.assertEqual(self.panel.CARD_HEIGHT, 350)
        self.assertEqual(self.panel._card_rect(6).x, self.panel.panel_x)
        self.assertGreater(self.panel._card_rect(6).y, self.panel._card_rect(0).y)

    def test_collection_sorts_cards_by_name(self):
        self.panel.set_cards([
            {"name": "Ярость", "slot_index": 0},
            {"name": "Атака", "slot_index": 1},
        ])
        self.panel.sort_mode = "name"
        self.panel._sort_cards()

        self.assertEqual([card["name"] for card in self.panel.cards], ["Атака", "Ярость"])

    def test_collection_scroll_is_bounded(self):
        self.panel.is_open = True
        self.panel.scroll_y = self.panel.max_scroll

        self.assertGreater(self.panel.max_scroll, 0)
        self.assertLessEqual(self.panel.scroll_y, self.panel.max_scroll)

    def test_first_profile_slot_opens_collection(self):
        cards = [{"key": "test", "name": "Тестовая", "slot_index": 0}]
        overlay = CharacterProfileOverlay(
            pygame.font.Font(None, 18),
            collection_loader=lambda: cards,
        )
        overlay.open({"id": 1, "name": "Игрок"})

        action, _ = overlay.handle_click(overlay.slot_buttons[0].center)

        self.assertEqual(action, "handled")
        self.assertTrue(overlay.collection_panel.is_open)
        self.assertEqual(overlay.collection_panel.cards, cards)


if __name__ == "__main__":
    unittest.main()
