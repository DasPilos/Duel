import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pygame

from client.network import ServerError
from kaloda import entry, settings
from kaloda.map_config import (
    DUNGEON_ENTRANCE_BOUNDS,
    TAVERN_BOUNDS,
    TAVERN_EXIT_POS,
    TILE_SIZE as T,
    tile_center,
)
from kaloda.scenes import world_flow
from kaloda.scenes.backyard_scene import BackyardScene
from kaloda.scenes.character_room import CharacterRoom
from kaloda.scenes.character_scene import CharacterScene
from kaloda.scenes.create_character_scene import CreateCharacterScene
from kaloda.scenes.tavern_scene import TavernScene
from kaloda.scenes.world_flow import KalodaWorld
from kaloda.scenes.world_map_scene import WorldMapScene
from kaloda.world_map import terrain_payload


class FakeClient:
    def __init__(self):
        self.saved = []

    def save_character(self, character):
        self.saved.append(dict(character))

    def get_map_terrain(self):
        return terrain_payload()

    def list_drinks(self):
        return []

    def get_equipment(self, character_id):
        return {}

    def get_storage(self, character_id, storage_type="chest1"):
        return {}

    def get_decks(self, character_id):
        return []

    def get_inventory(self, character_id):
        return {"inventory": [], "equipment": {"weapon": {"name": "Меч"}}, "bonuses": {}}


class FakeSession:
    def __init__(self, character=None, profession="warrior"):
        self.client = FakeClient()
        self.characters = [hero(type=profession)]
        self.character = character
        self.equipment_loads = 0

    def list_characters(self):
        return self.characters

    def select_character(self, character):
        self.character = character
        return character

    def refresh_character(self):
        return self.character

    def refresh_equipment_state(self):
        self.equipment_loads += 1
        return None

    def get_card_collection(self):
        return []

    def get_decks(self):
        return []

    def create_deck(self, name, cards):
        return None


def hero(**fields):
    return {
        "id": 7, "name": "Герой", "type": "warrior", "level": 1,
        "hp": 40, "max_hp": 120, "mp": 5, "max_mp": 30, **fields,
    }


class FakeDuel:
    def __init__(self, session, opponent):
        self.session = session
        self.opponent = opponent
        self.return_to_tavern = False
        self.player = SimpleNamespace(
            hp=10, mp=3, max_hp=120, max_mp=30, name="Герой", level=2, xp=15,
            stats={"strength": 3}, stat_points=1,
        )
        self.closed = False

    def handle_event(self, event):
        pass

    def update(self, dt):
        pass

    def draw(self, screen):
        pass

    def close(self):
        self.closed = True


class FakeMageDuel(FakeDuel):
    pass


def key(code):
    return pygame.event.Event(pygame.KEYDOWN, key=code, mod=0, unicode="")


def click(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)


class WorldTestCase(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
        self.addCleanup(pygame.quit)
        self.worlds = []

    def tearDown(self):
        for world in self.worlds:
            world.close()

    def world(self, character=None, profession="warrior", started=True):
        session = FakeSession(character, profession)
        if started and character is not None:
            session.characters = [character]
        world = KalodaWorld(session)
        self.worlds.append(world)
        return world

    def settle(self, world, limit=60):
        """Прогоняет кадры, пока не закончится запланированный переход между экранами."""
        for _ in range(limit):
            world.update(0.25)
            world.draw(self.screen)
            if world._queued is None and not world.transition.active:
                return
        self.fail("переход между экранами не завершился")


class TestEntering(WorldTestCase):
    def test_world_starts_with_the_character_list_and_new_hero_opens_on_the_map(self):
        world = self.world()
        self.assertIsInstance(world.scene, CharacterScene)

        world.handle_event(click(world.scene.create_new_button.center))
        self.settle(world)
        self.assertIsInstance(world.scene, CreateCharacterScene)

        world.scene.finished, world.scene.cancelled = True, True
        self.settle(world)
        self.assertIsInstance(world.scene, CharacterScene)

        world.session.character = hero()
        world.go("create")
        self.settle(world)
        world.scene.finished = True
        self.settle(world)
        self.assertEqual(world.name, "world_map")
        self.assertIsInstance(world.scene, WorldMapScene)
        self.assertEqual((int(world.scene.player_x // T), int(world.scene.player_y // T)), (12, 36))

    def test_chosen_character_returns_to_the_saved_place(self):
        cases = [
            (hero(zone="tavern"), TavernScene, "tavern"),
            (hero(zone="character_room"), CharacterRoom, "character_room"),
            (hero(zone="backyard"), BackyardScene, "backyard"),
            (hero(zone="city", position_x=1, position_y=1), WorldMapScene, "world_map"),
            (hero(), WorldMapScene, "world_map"),
        ]
        for character, scene_class, name in cases:
            with self.subTest(zone=character.get("zone")):
                world = self.world(character)
                world.scene.selected_character = character
                world.handle_event(key(pygame.K_RETURN))
                self.settle(world)
                self.assertEqual(world.name, name)
                self.assertIsInstance(world.scene, scene_class)

    def test_map_hero_spawns_at_the_saved_coordinates(self):
        x, y = 20 * T + 5, 30 * T + 7
        world = self.world(hero(zone="world_map", position_x=x, position_y=y, position_direction="e"))
        world.scene.selected_character = world.session.characters[0]
        world.handle_event(key(pygame.K_RETURN))
        self.settle(world)

        self.assertEqual((world.scene.player_x, world.scene.player_y), (x, y))
        self.assertEqual(world.scene.player_direction, "e")

    def test_escape_in_the_character_list_does_not_close_the_world(self):
        world = self.world()
        world.handle_event(key(pygame.K_ESCAPE))
        self.settle(world)

        self.assertIsInstance(world.scene, CharacterScene)
        self.assertFalse(world.scene.finished)

    def test_open_world_returns_kaloda_only_for_a_kaloda_server(self):
        base_session = SimpleNamespace(client=SimpleNamespace(base_url="http://x", timeout=3, token="t"))

        class Client:
            def __init__(self, info):
                self.info = info

            def get_game_info(self):
                if isinstance(self.info, Exception):
                    raise self.info
                return self.info

        def adopted(info):
            return SimpleNamespace(client=Client(info))

        with patch.object(entry.KalodaSession, "adopt", return_value=adopted({"game": "kaloda"})), \
                patch.object(entry, "KalodaWorld", return_value="kaloda") as kaloda_world:
            self.assertEqual(entry.open_world(base_session), "kaloda")
        kaloda_world.assert_called_once()

        for info in ({}, {"game": "operator1"}, ServerError("404")):
            with patch.object(entry.KalodaSession, "adopt", return_value=adopted(info)), \
                    patch.object(entry, "CharacterScene", return_value="base") as base_scene:
                self.assertEqual(entry.open_world(base_session), "base")
            base_scene.assert_called_once_with(base_session)


class TestTown(WorldTestCase):
    def _on_map(self, **fields):
        world = self.world(hero(zone="world_map", **fields))
        world.scene.selected_character = world.session.characters[0]
        world.handle_event(key(pygame.K_RETURN))
        self.settle(world)
        return world

    def test_tavern_door_leads_inside_and_the_street_exit_returns_to_the_door(self):
        world = self._on_map()
        left, top, width, _ = TAVERN_BOUNDS
        scene = world.scene
        scene.player_x, scene.player_y = (left + width + 0.5) * T, (top + 0.5) * T
        scene._last_player_tile = scene._player_tile()
        scene.player_x = (left + width - 0.5) * T
        scene._check_kobold_encounter()
        self.settle(world)
        self.assertIsInstance(world.scene, TavernScene)
        self.assertEqual(world.session.character["zone"], "tavern")

        world.scene.navigate, world.scene.finished = "world_map", True
        self.settle(world)
        self.assertIsInstance(world.scene, WorldMapScene)
        self.assertEqual((world.scene.player_x, world.scene.player_y), TAVERN_EXIT_POS)
        self.assertFalse(world.scene.finished)

    def test_tavern_rooms_lead_back_to_the_tavern(self):
        world = self.world(hero(zone="tavern"))
        world.scene.selected_character = world.session.characters[0]
        world.handle_event(key(pygame.K_RETURN))
        self.settle(world)

        for target, scene_class in (("character_room", CharacterRoom), ("backyard", BackyardScene)):
            with self.subTest(target=target):
                world.scene.navigate, world.scene.finished = target, True
                self.settle(world)
                self.assertIsInstance(world.scene, scene_class)
                self.assertEqual(world.session.character["zone"], target)
                world.scene.finished = True
                world.scene.navigate = "tavern"
                self.settle(world)
                self.assertIsInstance(world.scene, TavernScene)

    def test_escape_in_the_tavern_stays_inside(self):
        world = self.world(hero(zone="tavern"))
        world.scene.selected_character = world.session.characters[0]
        world.handle_event(key(pygame.K_RETURN))
        self.settle(world)

        world.scene.cancelled = world.scene.finished = True
        self.settle(world)
        self.assertIsInstance(world.scene, TavernScene)
        self.assertFalse(world.scene.finished)

    def test_backyard_leave_button_returns_to_the_tavern(self):
        world = self.world(hero(zone="backyard"))
        world.scene.selected_character = world.session.characters[0]
        world.handle_event(key(pygame.K_RETURN))
        self.settle(world)
        world.draw(self.screen)

        world.handle_event(click(world.scene.tavern_button.center))
        self.settle(world)

        self.assertIsInstance(world.scene, TavernScene)

    def test_backyard_without_an_opponent_returns_to_the_tavern(self):
        world = self.world(hero(zone="backyard"))
        world.scene.selected_character = world.session.characters[0]
        world.handle_event(key(pygame.K_RETURN))
        self.settle(world)

        world.scene.finished = True
        self.settle(world)
        self.assertIsInstance(world.scene, TavernScene)


class TestBattles(WorldTestCase):
    def _duel(self, profession="warrior", hp=40):
        world = self.world(hero(zone="backyard", hp=hp, type=profession), profession=profession)
        world.scene.selected_character = world.session.characters[0]
        with patch.object(world_flow, "DuelScene", FakeDuel), patch.object(world_flow, "MageBattleScene", FakeMageDuel):
            world.handle_event(key(pygame.K_RETURN))
            self.settle(world)
            world.scene.opponent = {"id": 55, "name": "Соперник"}
            world.scene.finished = True
            self.settle(world)
        return world

    def test_accepted_challenge_starts_the_class_specific_battle(self):
        warrior = self._duel("warrior")
        self.assertEqual(warrior.name, "duel")
        self.assertIs(type(warrior.scene), FakeDuel)
        self.assertEqual(warrior.scene.opponent["id"], 55)

        mage = self._duel("mage")
        self.assertIs(type(mage.scene), FakeMageDuel)

    def test_battle_hands_the_fighter_to_the_saved_character(self):
        world = self._duel()
        world.update(0.1)

        character = world.session.character
        self.assertEqual(character["zone"], "backyard")
        self.assertEqual((character["hp"], character["xp"], character["level"]), (10, 15, 2))

    def test_leaving_a_battle_returns_to_the_tavern_and_a_defeated_hero_is_healed(self):
        world = self._duel()
        world.scene.return_to_tavern = True
        self.settle(world)
        self.assertIsInstance(world.scene, TavernScene)
        self.assertEqual(world.session.client.saved, [])

        world = self._duel()
        world.scene.player.hp = 0
        world.scene.return_to_tavern = True
        self.settle(world)
        self.assertIsInstance(world.scene, TavernScene)
        self.assertEqual(world.session.character["hp"], 120)
        self.assertEqual(world.session.client.saved[-1]["hp"], 120)

    def test_closed_scenes_release_their_resources(self):
        world = self._duel()
        duel = world.scene
        world.scene.return_to_tavern = True
        self.settle(world)

        self.assertTrue(duel.closed)


class TestCheckpoint(WorldTestCase):
    def test_map_position_is_written_for_the_shared_exit_save(self):
        world = self.world(hero(zone="world_map", position_x=500, position_y=1500, position_direction="n"))
        world.scene.selected_character = world.session.characters[0]
        world.handle_event(key(pygame.K_RETURN))
        self.settle(world)
        world.scene.player_x, world.scene.player_y, world.scene.player_direction = 700.0, 1700.0, "w"

        world.update(0.1)

        character = world.session.character
        self.assertEqual(
            (character["zone"], character["position_x"], character["position_y"], character["position_direction"]),
            ("world_map", 700.0, 1700.0, "w"),
        )

    def test_position_inside_the_dungeon_is_saved_at_its_entrance(self):
        world = self.world(hero(zone="world_map", position_x=500, position_y=1500))
        world.scene.selected_character = world.session.characters[0]
        world.handle_event(key(pygame.K_RETURN))
        self.settle(world)
        world.scene.dungeon_entrance_bounds = DUNGEON_ENTRANCE_BOUNDS
        world.scene._enter_dungeon()
        self.assertIsNotNone(world.scene.dungeon_room)

        world.update(0.1)

        left, top, _, height = DUNGEON_ENTRANCE_BOUNDS
        expected = tile_center(left - 1, top + height // 2)
        character = world.session.character
        self.assertEqual((character["position_x"], character["position_y"]), tuple(map(float, expected)))


class TestInventoryAndChat(WorldTestCase):
    def _screen(self, zone):
        world = self.world(hero(zone=zone))
        world.scene.selected_character = world.session.characters[0]
        world.handle_event(key(pygame.K_RETURN))
        self.settle(world)
        return world

    def test_key_i_opens_the_profile_in_the_town_but_not_in_the_backyard(self):
        for zone in ("tavern", "character_room", "world_map"):
            with self.subTest(zone=zone):
                world = self._screen(zone)
                world.handle_event(key(pygame.K_i))
                self.assertTrue(world.scene.profile_overlay.is_open)
                world.handle_event(key(pygame.K_i))
                self.assertFalse(world.scene.profile_overlay.is_open)

        world = self._screen("backyard")
        world.handle_event(key(pygame.K_i))
        self.assertFalse(world.scene.profile_overlay.is_open)

    def test_open_profile_loads_the_equipment_once(self):
        world = self._screen("tavern")
        world.handle_event(key(pygame.K_i))

        world.update(0.1)
        world.update(0.1)

        self.assertEqual(world.session.equipment_loads, 1)
        self.assertEqual(world.session.character["equipment"], {})

    def test_backpack_button_in_the_profile_opens_the_inventory_window(self):
        world = self._screen("tavern")
        opened = []
        world.inventory.open = lambda session: opened.append(session)
        world.scene.profile_overlay.inventory_requested = True

        world.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(1, 1), rel=(0, 0), buttons=(0, 0, 0)))

        self.assertEqual(opened, [world.session])
        self.assertFalse(world.scene.profile_overlay.inventory_requested)

    def test_typing_in_the_chat_keeps_the_i_key_for_the_chat(self):
        world = self._screen("tavern")
        chat = world.chat
        self.assertIsNotNone(chat)
        self.assertFalse(chat.captures_keyboard())

        chat.message_input.focused = True
        self.assertTrue(chat.captures_keyboard())
        world.handle_event(key(pygame.K_i))
        self.assertFalse(world.scene.profile_overlay.is_open)

        chat.hide()
        self.assertFalse(chat.captures_keyboard())

    def test_inventory_and_events_are_ignored_during_a_transition(self):
        world = self._screen("tavern")
        world.go("backyard")
        world.draw(self.screen)
        self.assertTrue(world.transition.active)

        world.handle_event(key(pygame.K_i))
        world.draw(self.screen)

        self.assertFalse(world.scene.profile_overlay.is_open)


if __name__ == "__main__":
    unittest.main()
