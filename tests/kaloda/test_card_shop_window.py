import unittest

import pygame

from client.network import ServerError
from kaloda import settings
from kaloda.ui.card_shop_window import CardShopWindow


def _catalog_card(key, name, price):
    return {
        "key": key,
        "name": name,
        "price": price,
        "group_name": "Универсальные: Тактика",
        "effect_type": "arena_trap",
        "effect_data": {"range": 2},
        "resource_type": "unique",
        "resource_cost": 10,
        "rarity": "common",
        "image_path": "",
    }


class FakeClient:
    def __init__(self, fail_catalog=False):
        self.fail_catalog = fail_catalog
        self.bought = []

    def get_card_shop_catalog(self):
        if self.fail_catalog:
            raise ServerError("нет связи")
        return [
            _catalog_card("universal_trap", "Ловушка", 300),
            _catalog_card("universal_dash", "Рывок", 100),
        ]

    def get_card_collection(self, character_id):
        return [{"card_key": "universal_trap", "quantity": 1}]

    def buy_card(self, character_id, card_key):
        self.bought.append((character_id, card_key))
        return {"character": {"coins": 700}}


def _window(client):
    session = type("Session", (), {})()
    session.client = client
    session.character = {"id": 7, "coins": 1000}
    scene = type("Scene", (), {})()
    scene.session = session
    return CardShopWindow(scene), session


class TestCardShopWindow(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.addCleanup(pygame.quit)

    def test_open_loads_catalog_and_owned_cards(self):
        window, _session = _window(FakeClient())

        window.open()

        self.assertTrue(window.is_open)
        self.assertEqual([card["key"] for card in window.cards], ["universal_trap", "universal_dash"])
        self.assertEqual(window.owned, {"universal_trap": 1})

    def test_buy_updates_collection_and_wallet(self):
        client = FakeClient()
        window, session = _window(client)
        window.open()
        window.selected_index = 1

        window._buy()

        self.assertEqual(client.bought, [(7, "universal_dash")])
        self.assertEqual(window.owned["universal_dash"], 1)
        self.assertEqual(session.character["coins"], 700)
        self.assertEqual(window.message, "Куплено: Рывок")

    def test_category_filter_limits_visible_cards(self):
        window, _session = _window(FakeClient())
        window.open()

        window.selected_category = "traps"

        self.assertEqual([card["key"] for card in window.filtered_cards], ["universal_trap"])

    def test_draw_renders_rows_and_balance(self):
        window, _session = _window(FakeClient())
        window.open()
        screen = pygame.Surface((settings.WIDTH, settings.HEIGHT))

        window.draw(screen)

        self.assertEqual(len(window.item_rows()), 2)

    def test_server_error_is_shown_instead_of_crashing(self):
        window, _session = _window(FakeClient(fail_catalog=True))

        window.open()

        self.assertEqual(window.cards, [])
        self.assertIn("Не удалось загрузить ассортимент", window.message)


if __name__ == "__main__":
    unittest.main()
