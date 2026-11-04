import unittest

import pygame

from client.network import ServerError
from kaloda import settings
from kaloda.combat.talents import talent_tree_for
from kaloda.quests import QUESTS, quest_log_for
from kaloda.ui.dungeon_window import DungeonRoomWindow
from kaloda.ui.guild_window import GuildWindow
from kaloda.ui.library_window import LibraryWindow
from kaloda.ui.supplies_shop_window import SuppliesShopWindow
from kaloda.ui.talent_tree_window import TalentTreeWindow


class FakeClient:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def _guard(self):
        if self.fail:
            raise ServerError("нет связи")

    def claim_guild_quest_reward(self, character_id, quest_id, request_id):
        self._guard()
        self.calls.append(("claim", character_id, quest_id))
        return {"character": {"coins": 500}, "reward_coins": 10}

    def get_supplies_shop_catalog(self):
        self._guard()
        return [
            {"item_id": 4, "name": "Зелье здоровья", "description": "Лечит", "price": 150},
            {"item_id": 5, "name": "Зелье маны", "description": "Мана", "price": 90},
        ]

    def buy_supplies_item(self, character_id, item_id):
        self._guard()
        self.calls.append(("buy_item", character_id, item_id))
        return {"character": {"coins": 310}}

    def get_dungeon_card_shop_catalog(self):
        self._guard()
        return [
            {"key": "universal_bonebreaker", "name": "Костолом", "price": 400, "available": True,
             "group_name": "Универсальные: Тактика", "effect_type": "arena_bonebreaker",
             "effect_data": {"range": 1}, "resource_type": "unique", "resource_cost": 13,
             "rarity": "common", "image_path": ""},
            {"key": "universal_trap", "name": "Ловушка", "price": 300, "available": True,
             "group_name": "Универсальные: Тактика", "effect_type": "arena_trap",
             "effect_data": {"range": 2}, "resource_type": "unique", "resource_cost": 10,
             "rarity": "common", "image_path": ""},
        ]

    def buy_dungeon_card(self, character_id, card_key):
        self._guard()
        self.calls.append(("buy_card", character_id, card_key))
        return {"character": {"coins": 100}}

    def claim_dungeon_treasure(self, character_id, request_id):
        self._guard()
        self.calls.append(("treasure", character_id))
        return {"character": {"coins": 20000}, "rewards": ["Корона короля", "Копьё стража"]}

    def load_character(self, character_id):
        self._guard()
        return {"level": 3, "talents": {}}

    def choose_character_talent(self, character_id, level, option_id):
        self._guard()
        self.calls.append(("talent", character_id, level, option_id))
        return {"talents": {str(level): option_id}}

    def list_item_catalog(self):
        self._guard()
        return [
            {"id": 4, "name": "Зелье здоровья", "item_type": "potion", "rarity": "common",
             "price": 150, "description": "Восстанавливает здоровье.", "can_use": True,
             "effects": {"type": "heal", "heal": 30}},
            {"id": 901, "name": "Копьё стража", "item_type": "material", "rarity": "rare",
             "price": 0, "description": "Трофей.", "can_use": False, "effects": {}},
        ]


class FakeScene:
    def __init__(self, client=None):
        self.session = type("Session", (), {})()
        self.session.client = client or FakeClient()
        self.session.character = {
            "id": 7, "name": "Герой", "type": "warrior", "level": 3,
            "coins": 250, "talents": {},
        }
        self.advanced = 0
        self.exited = 0

    def advance_dungeon_room(self):
        self.advanced += 1

    def exit_dungeon(self):
        self.exited += 1


def _click(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)


class FeatureWindowTestCase(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.addCleanup(pygame.quit)
        self.screen = pygame.Surface((settings.WIDTH, settings.HEIGHT))


class TestGuildWindow(FeatureWindowTestCase):
    def test_both_views_draw_and_quests_button_opens_the_list(self):
        window = GuildWindow(FakeScene())
        window.open()
        window.draw(self.screen)

        window.handle_event(_click(window.quests_button.center))
        window.draw(self.screen)

        self.assertEqual(window.view, "quests")

    def test_accepting_then_claiming_pays_reward_in_coins(self):
        scene = FakeScene()
        window = GuildWindow(scene)
        window.open()
        window.view = "quests"
        window.selected_id = "kill_kobold"

        window._act()
        self.assertEqual(quest_log_for(scene.session).status("kill_kobold"), "active")
        quest_log_for(scene.session).record_progress("kobold")
        window._act()

        self.assertEqual(scene.session.character["coins"], 500)
        self.assertEqual(window.message, "Получено: 10 монет")
        self.assertEqual(quest_log_for(scene.session).status("kill_kobold"), "available")
        self.assertEqual(scene.session.client.calls, [("claim", 7, "kill_kobold")])

    def test_claim_failure_keeps_the_quest_completed(self):
        scene = FakeScene(FakeClient(fail=True))
        window = GuildWindow(scene)
        window.open()
        window.selected_id = "kill_kobold"
        log = quest_log_for(scene.session)
        log.accept("kill_kobold")
        log.record_progress("kobold")

        window._act()

        self.assertIn("Не удалось сдать задание", window.message)
        self.assertEqual(log.status("kill_kobold"), "completed")

    def test_every_quest_pays_a_positive_reward(self):
        self.assertTrue(all(quest.reward_coins > 0 for quest in QUESTS))


class TestSuppliesShopWindow(FeatureWindowTestCase):
    def test_open_buy_and_draw(self):
        scene = FakeScene()
        window = SuppliesShopWindow(scene)
        window.open()
        window.selected_index = 1

        window._buy()
        window.draw(self.screen)

        self.assertEqual(scene.session.client.calls, [("buy_item", 7, 5)])
        self.assertEqual(scene.session.character["coins"], 310)
        self.assertEqual(window.message, "Куплено: Зелье маны")

    def test_catalog_failure_is_reported(self):
        window = SuppliesShopWindow(FakeScene(FakeClient(fail=True)))

        window.open()

        self.assertEqual(window.items, [])
        self.assertIn("Не удалось загрузить ассортимент", window.message)


class TestTalentTreeWindow(FeatureWindowTestCase):
    def test_open_refreshes_character_and_draws(self):
        scene = FakeScene()
        window = TalentTreeWindow(scene)

        window.open()
        window.draw(self.screen)

        self.assertEqual(scene.session.character["level"], 3)

    def test_choosing_an_option_calls_server_and_updates_character(self):
        scene = FakeScene()
        window = TalentTreeWindow(scene)
        entry = next(entry for entry in talent_tree_for("warrior") if not entry.get("passive"))
        scene.session.character["level"] = entry["level"]
        option = entry["options"][0]

        window._choose(entry, option)

        self.assertEqual(scene.session.client.calls, [("talent", 7, entry["level"], option["id"])])
        self.assertEqual(scene.session.character["talents"][str(entry["level"])], option["id"])

    def test_locked_level_is_refused_before_calling_server(self):
        scene = FakeScene()
        window = TalentTreeWindow(scene)
        entry = next(entry for entry in talent_tree_for("warrior") if not entry.get("passive"))
        scene.session.character["level"] = entry["level"] - 1

        window._choose(entry, entry["options"][0])

        self.assertIn("доступно с", window.message)
        self.assertEqual(scene.session.client.calls, [])


class TestDungeonRoomWindow(FeatureWindowTestCase):
    def test_merchant_room_lists_supplies_and_dungeon_cards_only(self):
        window = DungeonRoomWindow(FakeScene())

        window.open(2)
        window.draw(self.screen)

        self.assertEqual(len(window.items), 2)
        self.assertEqual([card["key"] for card in window.cards], ["universal_bonebreaker"])

    def test_buying_a_card_syncs_the_coins_balance_from_the_server(self):
        scene = FakeScene()
        window = DungeonRoomWindow(scene)
        window.open(2)
        window.selected_index = len(window.items)

        window._buy_selected()

        self.assertEqual(scene.session.client.calls, [("buy_card", 7, "universal_bonebreaker")])
        self.assertEqual(scene.session.character["coins"], 100)

    def test_buying_a_supply_item_updates_wallet(self):
        scene = FakeScene()
        window = DungeonRoomWindow(scene)
        window.open(2)
        window.selected_index = 0

        window._buy_selected()

        self.assertEqual(scene.session.character["coins"], 310)
        self.assertEqual(window.message, "Куплено: Зелье здоровья")

    def test_treasure_room_claims_rewards_once_and_exit_button_leaves(self):
        scene = FakeScene()
        window = DungeonRoomWindow(scene)
        window.open(6)

        window.handle_event(_click(window.action_rect.center))
        window.draw(self.screen)

        self.assertTrue(window.treasure_opened)
        self.assertEqual(window.treasure_rewards, ["Корона короля", "Копьё стража"])
        self.assertEqual(scene.session.character["coins"], 20000)

        window.handle_event(_click(window.continue_rect.center))
        self.assertEqual(scene.exited, 1)

    def test_fountain_room_continue_advances_the_dungeon(self):
        scene = FakeScene()
        window = DungeonRoomWindow(scene)
        window.open(4)
        window.draw(self.screen)

        window.handle_event(_click(window.continue_rect.center))

        self.assertEqual(scene.advanced, 1)


class TestLibraryWindow(FeatureWindowTestCase):
    def test_places_tab_is_gone_and_items_come_from_the_server(self):
        window = LibraryWindow(FakeScene())

        window.open()

        self.assertNotIn("Места", LibraryWindow.CATEGORIES)
        self.assertEqual([entry["name"] for entry in window.data["Предметы"]],
                         ["Зелье здоровья", "Копьё стража"])
        self.assertIn("Цена: 150 монет.", window.data["Предметы"][0]["description"])

    def test_every_category_draws_and_search_filters(self):
        window = LibraryWindow(FakeScene())
        window.open()

        for index, _category in enumerate(window.CATEGORIES):
            window.category_index = index
            window.draw(self.screen)

        window.category_index = window.CATEGORIES.index("Существа")
        window.search_text = "кобольд"
        self.assertTrue(all("кобольд" in (entry["name"] + entry["description"]).casefold()
                            for entry in window.filtered_entries()))
        self.assertGreater(len(window.filtered_entries()), 0)

    def test_item_catalog_failure_is_shown_instead_of_crashing(self):
        window = LibraryWindow(FakeScene(FakeClient(fail=True)))

        window.open()
        window.category_index = window.CATEGORIES.index("Предметы")
        window.draw(self.screen)

        self.assertEqual(window.data["Предметы"], [])
        self.assertIn("Каталог предметов недоступен", window.items_message)

    def test_physical_damage_text_matches_max_dice_rule(self):
        window = LibraryWindow(FakeScene())

        effect = next(entry for entry in window.data["Эффекты"] if entry["name"] == "Физический урон")

        self.assertIn("максимум кубиков", effect["description"])


if __name__ == "__main__":
    unittest.main()
