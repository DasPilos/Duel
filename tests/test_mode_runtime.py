import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from server import map_worlds
from server.migrations import apply_migrations
from server.mode_registry import MODES, get_mode
from core.game_modes import GAME_MODES
from tower.server.api import TowerRequestHandler
from economy.server.api import EconomyRequestHandler
from front_line.server.api import FrontLineRequestHandler
from tests.fixtures import create_test_database, drop_test_database


class FakeProcess:
    def poll(self):
        return None


class FakeCursor:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def __iter__(self):
        return iter(self.rows)


class FakeMigrationConnection:
    def __init__(self):
        self.statements = []

    def execute(self, statement, params=None):
        if statement == "SELECT version FROM schema_migrations":
            return FakeCursor([{"version": "0077_lobby_sessions"}])
        if statement == "SELECT applied_at FROM public.schema_migrations WHERE version = %s":
            return FakeCursor([{"applied_at": 123.0}])
        self.statements.append((statement, params))
        return FakeCursor()


class ModeRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        self.admin = self.database.register("mode-runtime-admin", "password123")
        with self.database.connection() as connection:
            connection.execute("UPDATE users SET role='admin' WHERE id=%s", (self.admin["id"],))
        map_worlds._processes.clear()

    def tearDown(self):
        map_worlds._processes.clear()
        drop_test_database(self.database)

    def test_deck_world_uses_its_standalone_server_entrypoint(self):
        world = self.database.create_map_world("Карточный мир", "deck", self.admin["id"])
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(map_worlds, "LOG_DIR", Path(temp_dir)), \
                    patch.object(map_worlds, "free_port", return_value=8800), \
                    patch.object(map_worlds.subprocess, "Popen", return_value=FakeProcess()) as popen:
                result = map_worlds.start_world(self.database, self.admin["id"], world["id"])

        self.assertTrue(result["started"])
        command = popen.call_args.args[0]
        environment = popen.call_args.kwargs["env"]
        self.assertEqual(command[-2:], ["-m", "deck.server.main"])
        self.assertEqual(environment["DECK_WORLD_ID"], str(world["id"]))
        self.assertEqual(environment["DECK_PORT"], "8800")
        self.assertNotIn("WORLD_ID", environment)
        self.assertTrue(world["code"].startswith("deck"))

    def test_mode_names_and_order_include_front_line_map_authoring_mode(self):
        expected = [
            ("tower", "Tower"),
            ("economy", "Economy"),
            ("deck", "Deck"),
            ("front_line", "Front Line"),
        ]

        self.assertEqual([(mode["key"], mode["name"]) for mode in GAME_MODES], expected)
        self.assertEqual([(mode["key"], mode["name"]) for mode in MODES], expected)
        front_line = get_mode("front_line")
        self.assertTrue(front_line["runtime_ready"])
        self.assertEqual(front_line["schema"], "tower")
        self.assertEqual(front_line["entrypoint"], "front_line.server.main")

    def test_tower_and_economy_worlds_use_their_own_database_schemas(self):
        for mode in ("tower", "economy"):
            world = self.database.create_map_world(f"{mode}-world", mode, self.admin["id"])
            with tempfile.TemporaryDirectory() as temp_dir:
                with patch.object(map_worlds, "LOG_DIR", Path(temp_dir)), \
                        patch.object(map_worlds, "free_port", return_value=8801), \
                        patch.object(map_worlds.subprocess, "Popen", return_value=FakeProcess()) as popen:
                    map_worlds.start_world(self.database, self.admin["id"], world["id"])
            environment = popen.call_args.kwargs["env"]
            self.assertEqual(environment["GAME_SCHEMA"], mode)
            self.assertEqual(environment["WORLD_ID"], str(world["id"]))

    def test_test_world_is_marked_so_it_is_not_the_main_tower_world(self):
        world = self.database.create_map_world("Тестовая Башня", "tower", self.admin["id"], test_only=True)
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(map_worlds, "LOG_DIR", Path(temp_dir)), \
                    patch.object(map_worlds, "free_port", return_value=8802), \
                    patch.object(map_worlds.subprocess, "Popen", return_value=FakeProcess()) as popen:
                map_worlds.start_world(self.database, self.admin["id"], world["id"])

        self.assertEqual(popen.call_args.kwargs["env"]["WORLD_TEST"], "1")

    def test_world_id_two_is_the_tower_only_for_a_non_test_world(self):
        root = Path(__file__).resolve().parent.parent
        for test_flag, expected in (("0", "True"), ("1", "False")):
            environment = {**os.environ, "WORLD_ID": "2", "WORLD_TEST": test_flag}
            result = subprocess.run(
                [sys.executable, "-c", "from server import world_map; print(world_map.IS_TOWER_WORLD)"],
                cwd=root, env=environment, capture_output=True, text=True, check=True,
            )
            self.assertEqual(result.stdout.strip(), expected)

    def test_mode_schema_records_central_schema_migration_before_startup(self):
        connection = FakeMigrationConnection()

        apply_migrations(connection, schema="tower")

        self.assertIn(
            (
                "INSERT INTO schema_migrations (version, applied_at) VALUES (%s, %s)",
                ("0078_mode_database_schemas", 123.0),
            ),
            connection.statements,
        )

    def test_tower_and_economy_have_separate_entrypoints_and_routes(self):
        tower = get_mode("tower")
        economy = get_mode("economy")
        self.assertEqual(tower["entrypoint"], "tower.server.main")
        self.assertEqual(economy["entrypoint"], "economy.server.main")

        tower_handler = TowerRequestHandler.__new__(TowerRequestHandler)
        economy_handler = EconomyRequestHandler.__new__(EconomyRequestHandler)

        tower_handler.path = "/api/buildings/farm/1"
        economy_handler.path = "/api/world/sync"
        self.assertFalse(tower_handler._mode_route_allowed("GET"))
        self.assertFalse(economy_handler._mode_route_allowed("POST"))

        tower_handler.path = "/api/login"
        economy_handler.path = "/api/register"
        self.assertFalse(tower_handler._mode_route_allowed("POST"))
        self.assertFalse(economy_handler._mode_route_allowed("POST"))

        tower_handler.path = "/api/map/terrain"
        economy_handler.path = "/api/map/terrain"
        self.assertTrue(tower_handler._mode_route_allowed("GET"))
        self.assertTrue(economy_handler._mode_route_allowed("GET"))

    def test_front_line_character_draft_route_is_mode_specific(self):
        tower_handler = TowerRequestHandler.__new__(TowerRequestHandler)
        front_line_handler = FrontLineRequestHandler.__new__(FrontLineRequestHandler)
        tower_handler.path = "/api/front-line/character-draft"
        front_line_handler.path = "/api/front-line/character-draft"

        self.assertFalse(tower_handler._mode_route_allowed("POST"))
        self.assertTrue(front_line_handler._mode_route_allowed("POST"))

    def test_front_line_character_draft_route_checks_ownership_and_submits_choice(self):
        handler = FrontLineRequestHandler.__new__(FrontLineRequestHandler)
        handler.database = MagicMock()
        handler.world = MagicMock()
        handler.database.user_id_by_token.return_value = 7
        handler.database.character_belongs_to_user.return_value = True
        handler.world.submit_character_draft.return_value = {"active": True, "selected": True}
        handler._token = MagicMock(return_value="session-token")
        handler._send = MagicMock()
        body = {
            "character_id": 12,
            "profession_type": "assassin",
            "stats": {"strength": 4},
        }

        handled = handler._dispatch_mode_api("POST", "/api/front-line/character-draft", body)

        self.assertTrue(handled)
        handler.world.submit_character_draft.assert_called_once_with(7, 12, "assassin", body["stats"])
        handler._send.assert_called_once_with(
            200, {"draft": {"active": True, "selected": True}},
        )

        handler.database.character_belongs_to_user.return_value = False
        with self.assertRaisesRegex(ValueError, "Персонаж не найден"):
            handler._dispatch_mode_api("POST", "/api/front-line/character-draft", body)


if __name__ == "__main__":
    unittest.main()
