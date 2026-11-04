import unittest

import pygame

from kaloda.editor.catalog import catalog_definitions
from kaloda.editor.mobs import MOB_KINDS
from kaloda.editor.previews import draw_mob, mob_image
from kaloda.editor.scene import MAP_SIZE_PRESETS, WELCOME_BUTTONS, MapEditorScene
from kaloda.editor.structures import structures
from kaloda.map_config import MAP_HEIGHT_TILES, MAP_WIDTH_TILES


class PreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1920, 1080))

    def test_every_mob_kind_has_a_picture_of_the_requested_size(self):
        for kind in MOB_KINDS:
            for side in (64, 128):
                self.assertEqual(mob_image(kind, side).get_size(), (side, side), kind)

    def test_pictures_are_cached_and_drawn_with_some_pixels(self):
        self.assertIs(mob_image("kobold", 64), mob_image("kobold", 64))
        picture = mob_image("kobold_camp", 112)
        self.assertTrue(any(picture.get_at((x, y)).a for x in range(0, 112, 4) for y in range(0, 112, 4)))

    def test_unknown_kind_is_refused(self):
        with self.assertRaises(ValueError):
            mob_image("imp_sword", 64)

    def test_camp_draws_more_than_one_kobold(self):
        single = pygame.Surface((112, 112), pygame.SRCALPHA)
        camp = pygame.Surface((112, 112), pygame.SRCALPHA)
        draw_mob(single, "kobold", 56, 70, 48)
        draw_mob(camp, "kobold_camp", 56, 70, 48)
        self.assertGreater(
            sum(1 for x in range(112) for y in range(112) if camp.get_at((x, y)).a),
            sum(1 for x in range(112) for y in range(112) if single.get_at((x, y)).a),
        )


class StructureTests(unittest.TestCase):
    def test_structures_have_unique_ids_and_tiles_inside_the_world(self):
        items = structures()
        ids = [item["id"] for item in items]
        self.assertEqual(len(ids), len(set(ids)))
        for item in items:
            self.assertTrue(item["tiles"], item["id"])
            for x, y in item["tiles"]:
                self.assertTrue(0 <= x < MAP_WIDTH_TILES and 0 <= y < MAP_HEIGHT_TILES, (item["id"], x, y))

    def test_structures_cover_the_kaloda_layout(self):
        ids = {item["id"] for item in structures()}
        self.assertTrue({"city_walls", "city_gate", "crystal_of_life", "guild", "supplies_shop",
                         "card_shop", "tavern", "library", "dungeon_entrance"} <= ids)

    def test_structures_are_not_catalog_items(self):
        catalog_keys = {item["item_key"] for item in catalog_definitions()}
        self.assertFalse({item["id"] for item in structures()} & catalog_keys)


class SceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1920, 1080))

    def setUp(self):
        self.scene = MapEditorScene(None, catalog_definitions(), lambda: False)
        self.screen = pygame.display.get_surface()

    def test_welcome_offers_the_kaloda_world_map(self):
        labels = dict(WELCOME_BUTTONS)
        self.assertEqual(labels["world"], "Карта мира Колоды с сервера")
        self.assertNotIn("tower", labels)

    def test_map_sizes_start_with_the_kaloda_world(self):
        width, height, _label = MAP_SIZE_PRESETS[0]
        self.assertEqual((width, height), (MAP_WIDTH_TILES, MAP_HEIGHT_TILES))

    def test_new_map_is_the_kaloda_world_size(self):
        self.assertEqual((self.scene.state.map_w, self.scene.state.map_h), (MAP_WIDTH_TILES, MAP_HEIGHT_TILES))

    def test_structures_toggle_from_the_view_menu_and_draw(self):
        self.scene.has_map = True
        self.scene.origin_x = self.scene.origin_y = 0
        self.scene.zoom = 16
        self.assertTrue(self.scene.show_structures)
        self.scene.draw(self.screen)
        self.scene._command("structures")
        self.assertFalse(self.scene.show_structures)
        self.scene._command("structures")
        self.assertTrue(self.scene.show_structures)
        self.scene.draw(self.screen)

    def test_structures_key_is_h_and_menu_lists_them(self):
        view = next(items for title, items in self.scene._build_menus() if title == "Вид")
        self.assertTrue(any(item.get("id") == "structures" for item in view))

    def test_item_creation_is_gone_from_the_catalog_panel(self):
        self.assertFalse(hasattr(self.scene, "item_dialog"))
        self.assertFalse(hasattr(self.scene, "_draw_add_item_button"))

    def test_mob_section_lists_kaloda_mobs_and_draws(self):
        self.scene.has_map = True
        self.scene._set_section("npc")
        self.assertEqual({npc["key"] for npc in self.scene.npc_list}, MOB_KINDS)
        self.scene.selected_npc = "necromancer"
        self.scene.draw(self.screen)


if __name__ == "__main__":
    unittest.main()
