import unittest

import pygame

from client.network import ServerError
from kaloda import settings
from kaloda.scenes.character_room import CharacterRoom
from kaloda.scenes.character_scene import CharacterScene
from kaloda.scenes.create_character_scene import CreateCharacterScene
from kaloda.scenes.tavern_scene import TavernScene

STATS = {name: 2 for name in ("strength", "agility", "intuition", "wisdom", "intellect", "harmony", "endurance")}


def hero(**fields):
    return {
        "id": 7, "name": "Герой", "type": "warrior", "level": 3, "xp": 10,
        "hp": 90, "max_hp": 120, "mp": 20, "max_mp": 30, "stats": dict(STATS), "stat_points": 0,
        "coins": 130, **fields,
    }


class FakeClient:
    def __init__(self, drinks=None, fail_drinks=False):
        self.drinks = [{"id": 1, "name": "Эль", "price_coins": 20, "effect": "recovery", "description": "Бодрит"}] \
            if drinks is None else drinks
        self.fail_drinks = fail_drinks
        self.bought = []
        self.equipment_calls = 0

    def list_drinks(self):
        if self.fail_drinks:
            raise ServerError("нет связи")
        return self.drinks

    def buy_drink(self, character_id, drink_id):
        self.bought.append((character_id, drink_id))
        return {"character": hero(coins=10, hp=120)}

    def get_equipment(self, character_id):
        self.equipment_calls += 1
        return {"weapon": {"name": "Меч"}}

    def get_storage(self, character_id, storage_type="chest1"):
        return {"items": []}

    def get_decks(self, character_id):
        return [{"id": 1, "name": "Основная", "cards": {}}]


class FakeSession:
    def __init__(self, character=None, client=None):
        self.character = hero() if character is None else character
        self.client = client or FakeClient()
        self.characters = [hero(), hero(id=8, name="Маг", type="mage")]
        self.created = []
        self.deleted = []

    def refresh_character(self):
        return self.character

    def list_characters(self):
        return self.characters

    def select_character(self, character):
        self.character = character
        return character

    def create_character(self, name, profession_type="warrior", stats=None):
        if name == "Занято":
            raise ServerError("Имя занято")
        self.created.append((name, profession_type))
        self.character = hero(name=name, type=profession_type)
        return self.character

    def delete_character_with_password(self, character_id, password):
        if password != "верно":
            raise ServerError("Неверный пароль")
        self.deleted.append(character_id)
        self.characters = [item for item in self.characters if item["id"] != character_id]

    def get_card_collection(self):
        return []

    def get_decks(self):
        return []

    def create_deck(self, name, cards):
        return None


def click(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)


def key(code):
    return pygame.event.Event(pygame.KEYDOWN, key=code, mod=0, unicode="")


class ScreenTestCase(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
        self.addCleanup(pygame.quit)
        self.scenes = []

    def tearDown(self):
        for scene in self.scenes:
            scene.close()

    def add(self, scene):
        self.scenes.append(scene)
        return scene


class TestTavern(ScreenTestCase):
    def _tavern(self, **session_kwargs):
        return self.add(TavernScene(FakeSession(**session_kwargs)))

    def test_drinks_come_from_the_world_server_and_prices_are_in_coins(self):
        tavern = self._tavern()

        self.assertEqual(tavern.tavern_shop.drinks, [{
            "id": 1, "name": "Эль", "price": 20, "effect": "recovery", "description": "Бодрит",
        }])

    def test_unreachable_drink_list_keeps_the_built_in_menu(self):
        tavern = self._tavern(client=FakeClient(fail_drinks=True))

        self.assertTrue(tavern.tavern_shop.drinks)
        tavern.draw(self.screen)

    def test_buying_a_drink_updates_the_character_and_both_profile_cards(self):
        session = FakeSession()
        tavern = self.add(TavernScene(session))

        tavern._buy_drink(0)

        self.assertEqual(session.client.bought, [(7, 1)])
        self.assertEqual((session.character["coins"], session.character["hp"]), (10, 120))

    def test_not_enough_money_stops_the_purchase_before_the_server_call(self):
        session = FakeSession(character=hero(coins=5))
        tavern = self.add(TavernScene(session))

        tavern._buy_drink(0)

        self.assertEqual(session.client.bought, [])

    def test_drink_costs_exactly_its_price_in_coins(self):
        session = FakeSession(character=hero(coins=20))
        tavern = self.add(TavernScene(session))

        tavern._buy_drink(0)

        self.assertEqual(session.client.bought, [(7, 1)])

    def test_street_door_rooms_and_backyard_hotspots_navigate(self):
        tavern = self._tavern()
        hotspots = {name: (x, y, w, h, action) for name, x, y, w, h, action in tavern.tavern_hotspots}

        for name, expected in (
            ("Выход на улицу", "world_map"),
            ("Комната отдыха", "character_room"),
            ("Задний двор", "backyard"),
        ):
            with self.subTest(hotspot=name):
                tavern = self._tavern()
                x, y, w, h, _ = hotspots[name]
                tavern.handle_event(click((x + w // 2, y + h // 2)))
                self.assertTrue(tavern.finished)
                self.assertEqual(tavern.navigate, expected)

    def test_battle_button_and_keys_lead_to_the_backyard(self):
        tavern = self._tavern()
        tavern.handle_event(click(tavern.battle_button.center))
        self.assertEqual((tavern.finished, tavern.navigate), (True, "backyard"))

        for code in (pygame.K_RETURN, pygame.K_b):
            tavern = self._tavern()
            tavern.handle_event(key(code))
            self.assertEqual((tavern.finished, tavern.navigate), (True, "backyard"))

    def test_escape_cancels_and_draw_works(self):
        tavern = self._tavern()
        tavern.draw(self.screen)

        tavern.handle_event(key(pygame.K_ESCAPE))

        self.assertTrue(tavern.cancelled)
        self.assertIsNone(tavern.navigate)

    def test_innkeeper_opens_the_shop(self):
        tavern = self._tavern()
        x, y, w, h, _ = next(spot[1:] for spot in tavern.tavern_hotspots if spot[0] == "Хозяин трактира")

        tavern.handle_event(click((x + w // 2, y + h // 2)))
        tavern.draw(self.screen)

        self.assertTrue(tavern.tavern_shop.is_open)
        self.assertFalse(tavern.finished)


class TestCharacterRoom(ScreenTestCase):
    def test_tabs_load_server_data_once_and_draw(self):
        session = FakeSession()
        room = self.add(CharacterRoom(session))
        room.draw(self.screen)

        room.update(0.1)
        room.update(0.1)
        self.assertEqual(session.client.equipment_calls, 1)

        for tab in ("storage", "decks", "equipment"):
            room.handle_event(click(room.tab_rects[tab].center))
            self.assertEqual(room.current_tab, tab)
            room.update(0.1)
            room.draw(self.screen)
        self.assertEqual(room.decks_data[0]["name"], "Основная")

    def test_door_and_escape_leave_the_room(self):
        room = self.add(CharacterRoom(FakeSession()))
        room.draw(self.screen)
        room.handle_event(click(room.action_buttons["back"].center))
        self.assertTrue(room.finished)

        room = self.add(CharacterRoom(FakeSession()))
        room.handle_event(key(pygame.K_ESCAPE))
        self.assertTrue(room.finished)

    def test_chat_appears_only_when_the_session_supports_social_features(self):
        self.assertIsNone(self.add(CharacterRoom(FakeSession())).chat)

        session = FakeSession()
        session.social_snapshot = lambda location, position=None: {
            "occupants": [], "messages": [], "offers": [], "my_application": None, "group_offers": [],
        }
        room = self.add(CharacterRoom(session))
        self.assertEqual(room.chat.location, "character_room")
        room.draw(self.screen)


class TestCharacterSelection(ScreenTestCase):
    def _scene(self):
        return self.add(CharacterScene(FakeSession(character={})))

    def test_list_draws_selection_and_card(self):
        scene = self._scene()
        scene.draw(self.screen)

        scene.handle_event(click(scene.character_rects[1].center))
        scene.draw(self.screen)

        self.assertEqual(scene.selected_character["name"], "Маг")

    def test_continue_selects_the_character_for_the_session(self):
        scene = self._scene()
        scene.draw(self.screen)
        scene.handle_event(click(scene.character_rects[0].center))

        scene.handle_event(click(scene.continue_button.center))

        self.assertTrue(scene.finished)
        self.assertFalse(scene.cancelled)
        self.assertEqual(scene.session.character["id"], 7)

    def test_create_button_asks_for_the_character_creation_screen(self):
        scene = self._scene()

        scene.handle_event(click(scene.create_new_button.center))

        self.assertTrue(scene.finished)
        self.assertTrue(scene.create_new_character)

    def test_delete_needs_the_right_password(self):
        scene = self._scene()
        scene.draw(self.screen)
        scene.handle_event(click(scene.character_rects[0].center))
        scene.handle_event(click(scene.delete_button.center))
        self.assertTrue(scene.show_delete_confirmation)
        scene.draw(self.screen)

        scene.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="не то"))
        scene.handle_event(click(scene.confirm_delete_button.center))
        self.assertEqual(scene.delete_error, "Неверный пароль")
        self.assertEqual(len(scene.characters), 2)

        scene.delete_password = "верно"
        scene.handle_event(click(scene.confirm_delete_button.center))
        self.assertFalse(scene.show_delete_confirmation)
        self.assertEqual([item["id"] for item in scene.characters], [8])


class TestCharacterCreation(ScreenTestCase):
    def _scene(self):
        return self.add(CreateCharacterScene(FakeSession(character={})))

    def test_class_is_chosen_by_clicking_its_tile(self):
        scene = self._scene()
        scene.draw(self.screen)

        scene.handle_event(click(scene.profession_buttons["mage"].center))

        self.assertEqual(scene.profession, "mage")

    def test_character_is_created_with_the_typed_name_and_chosen_class(self):
        scene = self._scene()
        scene.handle_event(click(scene.profession_buttons["necromancer"].center))
        scene.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="Мор"))

        scene.handle_event(click(scene.create_button.center))

        self.assertTrue(scene.finished)
        self.assertFalse(scene.cancelled)
        self.assertEqual(scene.session.created, [("Мор", "necromancer")])
        self.assertEqual(scene.created_character["name"], "Мор")

    def test_empty_name_and_server_errors_keep_the_screen_open(self):
        scene = self._scene()
        scene.handle_event(key(pygame.K_RETURN))
        self.assertEqual((scene.finished, scene.error), (False, "Введите имя персонажа"))

        scene.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="Занято"))
        scene.handle_event(key(pygame.K_RETURN))
        self.assertEqual((scene.finished, scene.error), (False, "Имя занято"))
        scene.draw(self.screen)

    def test_back_and_escape_cancel(self):
        scene = self._scene()
        scene.handle_event(click(scene.back_button.center))
        self.assertEqual((scene.finished, scene.cancelled), (True, True))

        scene = self._scene()
        scene.handle_event(key(pygame.K_ESCAPE))
        self.assertEqual((scene.finished, scene.cancelled), (True, True))


if __name__ == "__main__":
    unittest.main()
