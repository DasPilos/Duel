from types import SimpleNamespace
import unittest

import pygame

from combat.card_database import UNIVERSAL_CARDS, card_to_dict, cards_for_type
from ui.card_shop_window import CARD_CATEGORIES, CARD_CATEGORY_BY_KEY, CardShopWindow
from ui.card_tooltip import card_tooltip_lines, draw_card_tooltip
from ui.dungeon_window import DungeonRoomWindow


class CardShopWindowTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1280, 800), pygame.HIDDEN)
        scene = SimpleNamespace(session=SimpleNamespace(
            character={"id": 1, "coins": 100}, client=None
        ))
        self.window = CardShopWindow(scene)
        self.window.cards = [
            {
                "key": key,
                "name": key,
                "price_coins": 100,
                "available": True,
                "resource_cost": 0,
                "effect_data": {"range": 2},
            }
            for key in CARD_CATEGORY_BY_KEY
        ]

    def tearDown(self):
        pygame.quit()

    def test_shop_categories_separate_card_effects(self):
        self.window.selected_category = "traps"
        self.assertEqual(
            {card["key"] for card in self.window.filtered_cards},
            {"universal_trap", "universal_roots_trap"},
        )
        self.window.selected_category = "movement"
        self.assertEqual(
            [card["key"] for card in self.window.filtered_cards],
            ["universal_dash", "universal_teleport"],
        )
        self.assertEqual([key for key, _ in CARD_CATEGORIES][0], "all")

    def test_mage_shift_appears_in_common_movement_filter(self):
        shift = next(card for card in self.window.cards if card["key"] == "mage_shift")
        shift.update(class_key="mage", rarity="common")
        self.window.selected_class = "mage"
        self.window.selected_rarity = "common"
        self.window.selected_category = "movement"

        self.assertEqual([card["key"] for card in self.window.filtered_cards], ["mage_shift"])

    def test_shop_list_scrolls_without_drawing_rows_outside_panel(self):
        self.window.selected_category = "all"
        rows = self.window.item_rows()
        self.assertLessEqual(len(rows), self.window.visible_row_count)
        self.assertTrue(all(
            row.top >= self.window.rect.top + self.window.CONTENT_TOP
            and row.bottom <= self.window.rect.top + self.window.CONTENT_BOTTOM
            for row in rows
        ))
        self.window._scroll(2)
        self.assertEqual(self.window.scroll_offset, 2)
        self.assertEqual(
            len(self.window.item_rows()),
            min(self.window.visible_row_count, len(self.window.cards) - 2),
        )

    def test_universal_tooltip_contains_effect_range_and_resource_cost(self):
        bonebreaker = next(card for card in UNIVERSAL_CARDS if card.key == "universal_bonebreaker")
        lines = card_tooltip_lines(bonebreaker)
        details = "\n".join(lines)

        self.assertIn("сломанные кости на 2 хода", details)
        self.assertIn("4% максимального здоровья", details)
        self.assertIn("Дальность: 1 гекс.", details)
        self.assertIn("Стоимость розыгрыша: 13 уникального ресурса.", details)

        screen = pygame.Surface((1280, 800))
        draw_card_tooltip(screen, bonebreaker, (1260, 790), self.window.small_font)

    def test_new_universal_cards_have_requested_coin_prices_and_rarities(self):
        cards = {card.key: card_to_dict(card) for card in UNIVERSAL_CARDS}
        expected = {
            "universal_trap": (50, "common"),
            "universal_barricade": (40, "common"),
            "universal_dash": (15, "common"),
            "universal_wolf": (100, "rare"),
            "universal_roots_trap": (45, "common"),
            "universal_resource_recovery": (220, "epic"),
            "universal_knockback": (90, "rare"),
            "universal_divine_healing": (75, "rare"),
            "universal_dreadful_corruption": (1100, "legendary"),
            "universal_unstable_elixir": (150, "epic"),
            "universal_evolution": (170, "epic"),
            "universal_teleport": (200, "epic"),
        }

        for key, (price, rarity) in expected.items():
            with self.subTest(card=key):
                self.assertEqual(cards[key]["price_gold"], price)
                self.assertEqual(cards[key]["rarity"], rarity)
                self.assertEqual(
                    cards[key]["sale_price_coins"],
                    {"common": 15, "rare": 35, "epic": 120, "legendary": 450}[rarity],
                )
        self.assertEqual(cards["universal_resource_recovery"]["name"], "Медитация")

    def test_deck_tooltip_uses_physical_card_effect_description(self):
        card = next(card for card in cards_for_type("archer") if card.key == "archer_blood_sacrifice")

        self.assertIn("вашего HP", "\n".join(card_tooltip_lines(card)))

    def test_assassin_experience_tooltip_describes_next_attack(self):
        card = next(card for card in cards_for_type("assassin") if card.key == "assassin_experience")
        details = "\n".join(card_tooltip_lines(card))

        self.assertIn("Следующая атака", details)
        self.assertIn("+10%", details)
        self.assertIn("+25%", details)

    def test_card_shop_draws_tooltip_for_hovered_card(self):
        from unittest.mock import patch

        self.window.is_open = True
        row = self.window.item_rows()[0]
        screen = pygame.Surface((1920, 1080))
        with (
            patch("ui.card_shop_window.pygame.mouse.get_pos", return_value=row.center),
            patch("ui.card_shop_window.draw_card_tooltip") as draw_tooltip,
        ):
            self.window.draw(screen)

        draw_tooltip.assert_called_once()

    def test_dungeon_shop_draws_tooltip_for_hovered_card(self):
        from unittest.mock import patch

        scene = SimpleNamespace(session=SimpleNamespace(character={"id": 1}, client=None))
        window = DungeonRoomWindow(scene)
        window.is_open = True
        window.room = 2
        window.cards = [
            {
                "key": "universal_bonebreaker",
                "name": "Костолом",
                "price_silver": 4,
                "effect_type": "arena_bonebreaker",
                "effect_data": {"range": 1, "duration": 2, "movement_max_hp_percent": 4},
                "resource_type": "unique",
                "resource_cost": 13,
            }
        ]
        row = window._rows()[0]
        screen = pygame.Surface((1920, 1080))
        with (
            patch("ui.dungeon_window.pygame.mouse.get_pos", return_value=row.center),
            patch("ui.dungeon_window.draw_card_tooltip") as draw_tooltip,
        ):
            window.draw(screen)

        draw_tooltip.assert_called_once()


if __name__ == "__main__":
    unittest.main()
