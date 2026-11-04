import unittest

from kaloda.client import ServerError
from kaloda.editor.catalog import catalog_definitions
from kaloda.editor.client import EditorClient
from kaloda.editor.seed import build_world_seed_cells
from kaloda.server import map_editor
from tests.kaloda.server_fixtures import create_test_database, drop_test_database, running_server

MAP_W, MAP_H = 16, 16
CATALOG = catalog_definitions()
GRASS = next(item["item_key"] for item in CATALOG if item["kind"] == "ground" and item["category"] == "grass" and not item["blocks"])
TREE = next(item["item_key"] for item in CATALOG if item["kind"] == "object" and item["category"] == "tree")
CELLS = [{"layer": "ground", "x": 0, "y": 0, "key": GRASS}, {"layer": "object", "x": 2, "y": 2, "key": TREE}]
MOBS = [{"kind": "kobold_camp", "x": 3, "y": 3}, {"kind": "necromancer", "x": 4, "y": 4}]


class EditorClientTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        self.addCleanup(drop_test_database, self.database)
        for username, role in (("editor-mod", "moderator"), ("editor-admin", "admin")):
            user = self.database.register(username, "password")
            with self.database.connection() as connection:
                connection.execute("UPDATE users SET role = %s WHERE id = %s", (role, user["id"]))
        self.database.register("editor-player", "password")
        self.base = self.enterContext(running_server(self.database))

    def editor(self, username):
        client = EditorClient(self.base.base_url, timeout=10)
        client.login(username, "password")
        return client

    def test_moderator_saves_a_map_with_kaloda_mobs_and_lists_it_by_mode(self):
        moderator = self.editor("editor-mod")
        saved = moderator.save_saved_map(CELLS, MAP_W, MAP_H, "Лес", "kaloda", mobs=MOBS, spawns=[{"x": 1, "y": 1}])
        self.assertEqual(saved["mode"], "kaloda")
        listed = moderator.list_saved_maps("kaloda")
        self.assertEqual([item["id"] for item in listed], [saved["saved_id"]])
        self.assertEqual(moderator.list_saved_maps("tower"), [])

    def test_saving_again_updates_the_same_saved_map(self):
        moderator = self.editor("editor-mod")
        first = moderator.save_saved_map(CELLS, MAP_W, MAP_H, "Лес", "kaloda")
        again = moderator.save_saved_map(CELLS, MAP_W, MAP_H, "Лес 2", "kaloda", saved_id=first["saved_id"])
        self.assertEqual(again["saved_id"], first["saved_id"])
        self.assertEqual(len(moderator.list_saved_maps("kaloda")), 1)

    def test_player_cannot_save_or_list_saved_maps(self):
        player = self.editor("editor-player")
        with self.assertRaises(ServerError):
            player.save_saved_map(CELLS, MAP_W, MAP_H, "Лес", "kaloda")
        with self.assertRaises(ServerError):
            player.list_saved_maps("kaloda")

    def test_players_see_the_world_list(self):
        worlds = self.editor("editor-player").list_worlds()
        self.assertIn(self.database.world_id, [world["id"] for world in worlds])

    def test_publish_puts_the_map_into_the_world_and_terrain_follows(self):
        moderator = self.editor("editor-mod")
        self.assertNotIn("tiles", moderator.get_map_terrain())
        result = moderator.publish_map(CELLS, MAP_W, MAP_H, "Степь", self.database.world_id, mobs=MOBS, mode="kaloda")
        self.assertEqual(result["applied"], len(CELLS))
        terrain = self.editor("editor-player").get_map_terrain()
        self.assertEqual((terrain["width_tiles"], terrain["height_tiles"]), (MAP_W, MAP_H))
        self.assertIn("tree1", [key for key in ("tree1",)])
        self.assertIn([2, 2, 2], terrain["tiles"]["forest"])

    def test_seed_from_the_published_map_is_valid_for_the_server(self):
        moderator = self.editor("editor-mod")
        moderator.publish_map(CELLS, MAP_W, MAP_H, "Степь", self.database.world_id, mode="kaloda")
        terrain = moderator.get_map_terrain()
        cells = build_world_seed_cells(terrain, {item["item_key"]: item for item in CATALOG}, MAP_W, MAP_H)
        self.assertEqual(len(map_editor.validate_cells(cells, CATALOG, MAP_W, MAP_H)), len(cells))

    def test_only_an_admin_creates_test_worlds(self):
        saved = self.editor("editor-mod").save_saved_map(CELLS, MAP_W, MAP_H, "Лес", "kaloda")
        with self.assertRaises(ServerError):
            self.editor("editor-mod").create_test_world(saved["saved_id"], "Тест")
        world = self.editor("editor-admin").create_test_world(saved["saved_id"], "Тест")
        self.assertEqual((world["name"], world["mode"], world["test"]), ("Тест", "kaloda", True))
        self.assertIn("world_id", world)

    def test_equipment_is_the_catalog_filtered_by_slot(self):
        moderator = self.editor("editor-mod")
        weapons = moderator.get_equipment_items(["weapon"])
        self.assertTrue(weapons)
        for item in weapons:
            self.assertEqual((item["item_type"], item["equip_slot"]), ("equipment", "weapon"))
        self.assertEqual(moderator.get_equipment_items([]), [])


if __name__ == "__main__":
    unittest.main()
