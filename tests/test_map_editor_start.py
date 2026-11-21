import unittest
from unittest import mock

import pygame

from core.map_catalog import (
    catalog_definitions, infrastructure_keys, palette_role_keys, terrain_layer_keys,
    winter_animated_groups, winter_tile_specs,
)
from client.map_editor_state import MapEditorState
from scenes.map_editor_scene import (
    BIOME_TABS, EDITOR_LAYER_COUNT, EDITOR_LAYER_LABELS, MapEditorScene, SECTION_TABS, TOP,
    WATERFALL_KEYS, WATER_BASE_KEYS, WATER_DECOR_KEYS, WINTER_ANIMATED_WATER_KEYS,
)
from scenes.map_palette import BLOCK_PAD, BLOCK_X

ALWAYS_ENABLED = ("new", "drafts", "tower", "exit")


class MapEditorStartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1920, 1080))

    def setUp(self):
        self.scene = MapEditorScene(None, catalog_definitions(), lambda: False)
        self.screen = pygame.display.get_surface()

    def click(self, pos):
        self.scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))

    def test_editor_starts_without_map(self):
        self.assertFalse(self.scene.has_map)
        self.assertEqual(self.scene.status, "Создайте новую карту или загрузите черновик")

    def test_welcome_screen_draws_without_grid(self):
        self.scene.draw(self.screen)
        self.assertFalse(self.scene.has_map)

    def test_clicks_on_grid_do_not_edit_without_map(self):
        self.click((self.screen.get_width() // 2, TOP + 200))
        self.assertEqual(self.scene.state.ground, {})
        self.assertEqual(self.scene.state.overlay, {})
        self.assertEqual(self.scene.state.objects, {})

    def test_menu_editing_items_are_disabled_without_map(self):
        for _title, items in self.scene._menus():
            for item in items:
                if item.get("separator"):
                    continue
                if item["id"] in ALWAYS_ENABLED:
                    continue
                self.assertFalse(item.get("enabled", True), item["id"])

    def test_new_map_button_opens_size_picker(self):
        command, _label, rect = self.scene._welcome_buttons()[0]
        self.assertEqual(command, "new")
        self.click(rect.center)
        self.assertIsNotNone(self.scene.size_picker)

    def test_server_button_disabled_without_saved_draft(self):
        _label, enabled = self.scene._server_button()
        self.assertFalse(enabled)

    def test_server_button_enabled_for_saved_clean_draft(self):
        self.scene.draft_id = "draft-1"
        self.scene._dirty = lambda: False
        _label, enabled = self.scene._server_button()
        self.assertTrue(enabled)

    def test_cancelled_login_reports_map_not_saved(self):
        self.scene.draft_id = "draft-1"
        self.scene._dirty = lambda: False
        self.scene.save_to_server()
        self.assertIn("Карта не сохранена", self.scene.status)

    def test_server_button_click_saves_to_server(self):
        self.scene.has_map = True
        calls = []
        self.scene.save_to_server = lambda: calls.append(True)
        self.click(self.scene.toolbar.server_rect(self.screen.get_width()).center)
        self.assertEqual(calls, [True])

    def test_layer_tabs_select_and_toggle_layer_visibility(self):
        self.scene.has_map = True
        tabs, hide, opacity = self.scene._layer_tab_rects()
        layer, rect = tabs[1]

        self.click(rect.center)
        self.assertEqual(self.scene.active_map_layer, layer)
        self.assertEqual(len(tabs), EDITOR_LAYER_COUNT)
        self.assertIn("сохраняются в черновике", self.scene.status)
        self.click(hide.center)
        self.assertFalse(self.scene.editor_layer_visible[layer])
        self.click(opacity.center)
        self.assertTrue(self.scene.editor_layer_70[layer])
        self.assertEqual(len(tabs), 9)
        self.assertEqual(
            EDITOR_LAYER_LABELS,
            (
                "Вода", "Декор воды", "Основа суши", "Декор суши",
                "Скалы, горы и водопады", "Постройки", "Декор местности", "Животные", "Мобы",
            ),
        )

    def test_palette_size_stays_at_ten_columns_when_ctrl_wheel_is_used(self):
        self.scene.has_map = True
        initial_tile_size = self.scene.palette.tile
        with mock.patch("pygame.mouse.get_pos", return_value=(20, TOP + 10)):
            self.scene._wheel(2, ctrl=True)
        self.assertEqual(self.scene.palette.tile, initial_tile_size)

    def test_minimap_is_400_square_in_the_lower_right_and_can_be_hidden(self):
        self.scene.has_map = True
        minimap = self.scene._minimap_rect()
        grid = self.scene.grid_rect()

        self.assertEqual(minimap.size, (400, 400))
        self.assertEqual(minimap.bottom, grid.bottom - 12)
        self.assertEqual(minimap.right, grid.right - 12)
        edge_tile = self.scene._minimap_tile((minimap.right - 1, minimap.bottom - 1))
        self.assertEqual(
            edge_tile,
            (
                (minimap.w - 1) * self.scene.state.map_w // minimap.w,
                (minimap.h - 1) * self.scene.state.map_h // minimap.h,
            ),
        )

        self.click(self.scene._minimap_button_rect().center)
        self.assertFalse(self.scene.show_minimap)
        self.assertIsNone(self.scene._minimap_rect())

        self.click(self.scene._minimap_button_rect().center)
        self.assertTrue(self.scene.show_minimap)

    def test_palette_context_stages_passability_until_apply_is_confirmed(self):
        self.scene.has_map = True
        self.scene.palette_editing = True
        item = next(
            item for item in self.scene.catalog
            if item["kind"] == "ground" and item["category"] == "grass"
        )
        key = item["item_key"]
        self.scene._open_palette_context(key, (100, TOP + 100))
        rect = self.scene.palette_context["rect"]

        self.scene._palette_context_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=(rect.x + 20, rect.y + 50),
        ))

        self.assertNotIn(key, self.scene.palette_overrides)
        self.assertTrue(self.scene._palette_context_dirty())
        self.scene.draw(self.screen)

        self.scene._palette_context_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=(rect.x + 20, rect.y + 260),
        ))
        self.assertEqual(self.scene.palette_context["confirm"], "apply")
        self.assertNotIn(key, self.scene.palette_overrides)
        self.scene.draw(self.screen)

        self.scene._palette_context_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=(rect.x + 20, rect.y + 260),
        ))
        self.assertEqual(
            self.scene.palette_overrides[key]["blocks"],
            not item["blocks"],
        )

    def test_palette_context_confirmed_cancel_discards_staged_changes(self):
        self.scene.palette_editing = True
        item = next(
            item for item in self.scene.catalog
            if item["kind"] == "ground" and item["category"] == "grass"
        )
        key = item["item_key"]
        self.scene._open_palette_context(key, (100, TOP + 100))
        rect = self.scene.palette_context["rect"]

        self.scene._palette_context_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=(rect.x + 20, rect.y + 50),
        ))
        self.scene._palette_context_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=(rect.right - 20, rect.y + 260),
        ))
        self.assertEqual(self.scene.palette_context["confirm"], "cancel")
        self.assertNotIn(key, self.scene.palette_overrides)

        self.scene._palette_context_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=(rect.x + 20, rect.y + 260),
        ))
        self.assertIsNone(self.scene.palette_context)
        self.assertNotIn(key, self.scene.palette_overrides)

    def test_group_layer_change_sets_one_shared_layer_for_mixed_initial_layers(self):
        self.scene.palette_editing = True
        ground_keys = [
            item["item_key"]
            for item in self.scene.catalog
            if item["kind"] == "ground"
        ]
        first, second = ground_keys[:2]
        self.scene.palette_overrides = {
            first: {"editor_layer": 2},
            second: {"editor_layer": 5},
        }
        self.scene.palette_original_overrides = {
            key: dict(rule)
            for key, rule in self.scene.palette_overrides.items()
        }
        self.scene.palette_selected_keys = {first, second}
        self.scene._open_palette_context(first, (100, TOP + 100))
        context = self.scene.palette_context
        rect = context["rect"]

        self.scene.draw(self.screen)
        self.scene._palette_context_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=(rect.right - 20, rect.y + 90),
        ))

        self.assertEqual(
            {context["rules"][key]["editor_layer"] for key in context["keys"]},
            {3},
        )
        self.assertEqual(
            {self.scene.palette_overrides[key]["editor_layer"] for key in context["keys"]},
            {2, 5},
        )
        self.scene._palette_context_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=(rect.x + 20, rect.y + 260),
        ))
        self.scene._palette_context_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=(rect.x + 20, rect.y + 260),
        ))

        self.assertEqual(
            {self.scene._palette_rule(key)["editor_layer"] for key in context["keys"]},
            {3},
        )

    def test_selected_layer_paints_without_replacing_lower_layer(self):
        self.scene.has_map = True
        water = next(item for item in self.scene.catalog if item["kind"] == "ground" and item["category"] == "water")
        soil = next(item for item in self.scene.catalog if item["kind"] == "ground" and item["category"] != "water")
        self.assertIsNone(self.scene.state.place(water["item_key"], 2, 2, layer="ground"))
        self.scene.active_map_layer = 2
        self.scene.selected = soil["item_key"]

        self.scene._paint((2, 2))

        self.assertEqual(self.scene.state.ground[(2, 2)], water["item_key"])
        self.assertEqual(self.scene.editor_layers[2].ground[(2, 2)], soil["item_key"])

    def test_paint_rejects_an_item_assigned_to_another_artist_layer(self):
        grass = next(item for item in self.scene.catalog if item["kind"] == "ground" and item["category"] == "grass")
        self.scene.selected = grass["item_key"]

        self.scene._paint((2, 2))

        self.assertTrue(all(not layer.to_cells() for layer in self.scene.editor_layers))
        self.assertIn("слою 3 «Основа суши»", self.scene.status)

        self.scene.active_map_layer = 2
        self.scene._paint((2, 2))
        self.assertEqual(self.scene.editor_layers[2].ground[(2, 2)], grass["item_key"])

    def test_artist_layer_assignment_matches_the_nine_layer_scheme(self):
        water = next(item for item in self.scene.catalog if item["kind"] == "ground" and item["category"] == "water")
        land = next(item for item in self.scene.catalog if item["kind"] == "ground" and item["category"] == "grass")
        decor_key = next(iter(palette_role_keys("ground_decor")))
        elevation_key = next(
            key for key in terrain_layer_keys()["elevation"]
            if self.scene.state.items[key]["category"] not in ("grass", "water")
        )
        infra_key = next(iter(infrastructure_keys()))
        winter_water_decor = next(
            key for key, spec in winter_tile_specs().items()
            if spec.get("sheet") == "water_detilazation_v2"
        )
        whole_water_detail = "winter_water_detail_001"
        animal = next(item for item in self.scene.catalog if item["category"] == "animal")
        bush = next(item for item in self.scene.catalog if item["kind"] == "object" and item["category"] == "bush")

        self.assertEqual(self.scene._artist_layer_for_item(water["item_key"], "ground"), 0)
        self.assertEqual(self.scene._artist_layer_for_item(water["item_key"], "overlay"), 1)
        self.assertEqual(self.scene._artist_layer_for_item(next(iter(WATER_BASE_KEYS)), "overlay"), 0)
        self.assertEqual(
            self.scene._artist_layer_for_item(next(iter(WINTER_ANIMATED_WATER_KEYS)), "overlay"),
            1,
        )
        self.assertEqual(self.scene._artist_layer_for_item(land["item_key"], "ground"), 2)
        self.assertEqual(self.scene._artist_layer_for_item(decor_key, "ground"), 3)
        self.assertEqual(self.scene._artist_layer_for_item(elevation_key, "elevation"), 4)
        self.assertEqual(self.scene._artist_layer_for_item(next(iter(WATERFALL_KEYS)), "overlay"), 4)
        self.assertIn(winter_water_decor, WATER_DECOR_KEYS)
        self.assertEqual(self.scene._artist_layer_for_item(winter_water_decor, "overlay"), 1)
        self.assertIn(whole_water_detail, WATER_DECOR_KEYS)
        self.assertEqual(self.scene.state.items[whole_water_detail]["editor_layer"], 2)
        self.assertEqual(self.scene._artist_layer_for_item(whole_water_detail), 1)
        self.assertEqual(self.scene._default_editor_layer(whole_water_detail), 2)
        self.assertEqual(self.scene._artist_layer_for_item(infra_key, "infra"), 5)
        self.assertEqual(self.scene._artist_layer_for_item(bush["item_key"]), 6)
        self.assertEqual(self.scene._artist_layer_for_item(animal["item_key"]), 7)
        self.assertEqual(EDITOR_LAYER_COUNT - 1, 8)

    def test_whole_water_detail_palette_layer_is_fixed_to_water_decor(self):
        key = "winter_water_detail_001"
        self.scene.palette_editing = True
        self.scene._open_palette_context(key, (100, TOP + 100))
        context = self.scene.palette_context
        rect = context["rect"]

        self.scene._palette_context_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=(rect.right - 20, rect.y + 90),
        ))

        self.assertEqual(context["rules"][key]["editor_layer"], 2)
        self.assertEqual(self.scene._palette_rule(key)["editor_layer"], 2)

    def test_legacy_tenth_editor_layer_is_migrated_without_dropping_its_cells(self):
        grass = next(item for item in self.scene.catalog if item["kind"] == "ground" and item["category"] == "grass")
        self.scene.state = MapEditorState(self.scene.catalog, [], 4, 4)
        old_layers = [[] for _ in range(9)]
        old_layers[-1] = [{"layer": "ground", "x": 1, "y": 2, "key": grass["item_key"]}]

        self.scene._restore_editor_layers(old_layers)

        self.assertEqual(self.scene.editor_layers[2].ground[(1, 2)], grass["item_key"])
        self.assertEqual(len(self.scene.editor_layers), EDITOR_LAYER_COUNT)
        self.assertFalse(self.scene._dirty())

    def test_seed_layer_migration_keeps_unsaved_state_when_requested(self):
        grass = next(item for item in self.scene.catalog if item["kind"] == "ground" and item["category"] == "grass")
        self.scene.state = MapEditorState(
            self.scene.catalog,
            [{"layer": "ground", "x": 1, "y": 2, "key": grass["item_key"]}],
            4,
            4,
        )

        self.scene._restore_editor_layers([], mark_saved=False)

        self.assertIn((1, 2), self.scene.editor_layers[2].ground)
        self.assertTrue(self.scene._dirty())

    def test_layer_visibility_and_transparency_are_independent(self):
        self.scene.active_map_layer = 0

        self.scene.editor_layer_70[1] = True
        self.assertEqual(self.scene._layer_alpha(0), 255)
        self.assertEqual(self.scene._layer_alpha(1), round(255 * 0.7))
        self.scene.editor_layer_visible[2] = False
        self.assertEqual(self.scene._layer_alpha(2), 0)

    def test_biome_tabs_show_only_the_selected_biome_catalog(self):
        self.scene.has_map = True
        self.assertEqual(SECTION_TABS[0][1], "Биомы")
        self.assertEqual(
            [label for _biome, label in BIOME_TABS],
            ["Лесной", "Скалистый", "Зимний", "Нежить", "Пустыня"],
        )
        tabs = self.scene._biome_tab_rects()
        winter_tab = next(rect for biome, _label, rect in tabs if biome == "winter")
        self.click(winter_tab.center)

        self.assertEqual(self.scene.biome, "winter")
        self.assertTrue(self.scene.palette.rows)
        winter_keys = {
            item["item_key"]
            for row in self.scene.palette.rows
            if row.kind == "block"
            for _rect, item in row.cells
        }
        self.assertTrue(winter_keys)
        self.assertTrue(all(key.startswith("winter_") for key in winter_keys))
        subtab_bottom = max(rect.bottom for _biome, _label, rect in tabs)
        self.assertGreater(self.scene._add_item_rect().top, subtab_bottom)
        self.assertGreater(self.scene._list_top(), self.scene._add_item_rect().bottom)
        self.assertTrue(all(
            item["category"] != "animal"
            for item in self.scene.biome_catalogs["winter"]
        ))
        undead_tab = next(rect for biome, _label, rect in tabs if biome == "undead")
        self.click(undead_tab.center)

        self.assertEqual(self.scene.biome, "undead")
        undead_keys = {
            item["item_key"]
            for row in self.scene.palette.rows
            if row.kind == "block"
            for _rect, item in row.cells
        }
        self.assertTrue(undead_keys)
        self.assertTrue(all(key.startswith("undead_") for key in undead_keys))
        self.assertTrue(all(
            item["category"] != "animal"
            for item in self.scene.biome_catalogs["undead"]
        ))
        desert_tab = next(rect for biome, _label, rect in tabs if biome == "desert")
        self.click(desert_tab.center)

        self.assertEqual(self.scene.biome, "desert")
        desert_keys = {
            item["item_key"]
            for row in self.scene.palette.rows
            if row.kind == "block"
            for _rect, item in row.cells
        }
        self.assertTrue(desert_keys)
        self.assertTrue(all(key.startswith("desert_") for key in desert_keys))
        self.assertTrue(all(
            item["category"] != "animal"
            for item in self.scene.biome_catalogs["desert"]
        ))

    def test_animals_have_a_separate_top_level_tab(self):
        self.scene.has_map = True
        self.assertIn(("animals", "Животные", 105), SECTION_TABS)
        animals_tab = next(
            rect for section, _label, rect in self.scene._tab_rects()
            if section == "animals"
        )
        self.click(animals_tab.center)

        self.assertEqual(self.scene.section, "animals")
        animal_keys = {
            item["item_key"]
            for row in self.scene._catalog_palette().rows
            if row.kind == "block"
            for _rect, item in row.cells
        }
        expected = {
            item["item_key"] for item in self.scene.catalog
            if item["category"] == "animal"
        }
        self.assertEqual(animal_keys, expected)
        self.assertTrue(all(
            item["category"] != "animal"
            for item in self.scene.biome_catalogs["forest"]
        ))

    def test_extra_editor_layers_are_dirty_and_restore_from_draft_cells(self):
        item = next(item for item in self.scene.catalog if item["kind"] == "ground" and item["category"] != "water")
        self.scene.state = MapEditorState(self.scene.catalog, [], 4, 4)
        self.scene._reset_editor_layers()
        self.scene.editor_layers[2].place(item["item_key"], 1, 2)

        self.assertTrue(self.scene._dirty())
        saved_layers = [layer.to_cells() for layer in self.scene.editor_layers[1:]]
        self.scene.state = MapEditorState(self.scene.catalog, [], 4, 4)
        self.scene._restore_editor_layers(saved_layers)

        self.assertEqual(self.scene.editor_layers[2].ground[(1, 2)], item["item_key"])
        self.assertFalse(self.scene._dirty())

    def test_game_cells_merge_paint_layers_without_mutating_editor_layers(self):
        ground = next(item for item in self.scene.catalog if item["kind"] == "ground" and item["category"] != "water")
        relief = next(item for item in self.scene.catalog if item["kind"] == "ground" and item["category"] == "rock")
        self.scene.state = MapEditorState(self.scene.catalog, [], 4, 4)
        self.scene._reset_editor_layers()
        self.scene.state.place(ground["item_key"], 1, 1, layer="ground")
        self.scene.editor_layers[1].place(relief["item_key"], 1, 1, layer="ground")

        cells = self.scene._game_cells()

        self.assertEqual(
            [cell for cell in cells if cell["x"] == 1 and cell["y"] == 1 and cell["layer"] == "ground"],
            [{"layer": "ground", "x": 1, "y": 1, "key": relief["item_key"]}],
        )
        self.assertEqual(self.scene.state.ground[(1, 1)], ground["item_key"])

    def test_game_cells_validate_water_decor_across_artist_layers(self):
        water = next(
            item for item in self.scene.catalog
            if item["kind"] == "ground" and item["category"] == "water"
            and item["item_key"] not in self.scene.state.overlay_keys
        )
        water_decor = next(
            item for item in self.scene.catalog
            if item["kind"] == "ground" and item["category"] == "water"
            and item["item_key"] in self.scene.state.overlay_keys
            and item["item_key"] not in WATERFALL_KEYS
        )
        self.scene.state.place(water["item_key"], 1, 1, layer="ground")
        self.scene.editor_layers[1].place(water_decor["item_key"], 1, 1, layer="overlay")

        cells = self.scene._game_cells()

        self.assertIn(
            {"layer": "overlay", "x": 1, "y": 1, "key": water_decor["item_key"]},
            cells,
        )
        land = next(
            item for item in self.scene.catalog
            if item["kind"] == "ground" and item["category"] == "grass"
        )
        self.scene.editor_layers[2].place(land["item_key"], 1, 1, layer="ground")
        with self.assertRaisesRegex(ValueError, "Водные эффекты"):
            self.scene._game_cells()

    def test_winter_water_animation_requires_a_base_water_tile(self):
        water_animation = next(
            item for item in self.scene.catalog
            if item["item_key"] in self.scene.state.water_decor_requires_water_keys
            and item["category"] == "floor"
        )
        self.scene.editor_layers[1].place(
            water_animation["item_key"], 1, 1, layer="overlay",
        )

        with self.assertRaisesRegex(ValueError, "Водные эффекты"):
            self.scene._game_cells()

    def test_animation_composition_tooltip_resolves_a_catalog_tile(self):
        self.scene._set_biome("winter")
        composition_key = next(
            group["key"]
            for group in winter_animated_groups()
            if group["key"].endswith("_0232")
        )
        self.assertNotIn(composition_key, self.scene.state.items)
        entries = self.scene.palette.compound_entries(composition_key)
        self.assertTrue(entries)
        stamp = self.scene.state.make_stamp(entries)
        self.assertIsNotNone(stamp)
        self.assertGreater(len(stamp["overlay"]), 1)
        self.scene._hovered_catalog_key = lambda: composition_key
        screen = pygame.Surface((1920, 1080))

        with mock.patch("pygame.mouse.get_pos", return_value=(100, 100)):
            self.scene._draw_item_tooltip(screen)

    def test_animation_tooltip_is_placed_outside_preview(self):
        self.scene._set_biome("winter")
        key = next(
            group["key"]
            for group in winter_animated_groups()
            if group["key"].endswith("_0232")
        )
        palette = self.scene._catalog_palette()
        row, preview = next(
            (row, rect)
            for row in palette.rows
            if row.kind == "block"
            for rect, group in row.previews
            if group["key"] == key
        )
        mouse_pos = (
            BLOCK_X + preview.centerx,
            self.scene._list_top() + row.top + BLOCK_PAD + preview.centery - self.scene.list_scroll,
        )
        anchor = self.scene._catalog_hover_rect(key, mouse_pos)
        viewport = pygame.Rect(
            0,
            self.scene._list_top(),
            self.scene.panel_w,
            self.scene._list_bottom() - self.scene._list_top(),
        )
        tooltip = self.scene._tooltip_rect(
            pygame.Rect(0, 0, 220, 42),
            anchor,
            viewport,
        )

        self.assertEqual(anchor.size, preview.size)
        self.assertTrue(viewport.contains(tooltip))
        self.assertFalse(tooltip.colliderect(anchor))

    def test_artist_palette_drag_stays_in_section_and_reset_clears_positions(self):
        self.scene.palette_editing = True
        self.scene._refresh_palette_views()
        palette = self.scene._catalog_palette()
        section = next(row for row in palette.rows if row.arrange_group is not None)
        group = section.arrange_group
        keys = [
            item["item_key"]
            for _rect, item in section.cells
            if not palette.compound_entries(item["item_key"])
        ]
        first, second = keys[:2]

        source_rect = palette.item_rect(first)
        source_pos = (
            source_rect.centerx,
            self.scene._list_top() + source_rect.centery - self.scene.list_scroll,
        )
        self.scene._panel_down(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                button=1,
                pos=source_pos,
            )
        )
        self.assertEqual(self.scene.drag["mode"], "palette_layout")
        self.assertEqual(self.scene.drag["group"], group)
        positions = palette.arrangement_positions(group)
        target = (0, max(line for _column, line in positions.values()) + 1)
        target_pos = (
            BLOCK_X + target[0] * palette.tile + palette.tile // 2,
            self.scene._list_top() + section.top + BLOCK_PAD + target[1] * palette.tile + palette.tile // 2 - self.scene.list_scroll,
        )
        self.scene._mouse_up(target_pos)
        self.assertEqual(
            self.scene.palette_overrides[first]["palette_position"],
            {"x": target[0], "y": target[1]},
        )
        self.assertNotIn(
            "palette_position",
            self.scene.palette_overrides.get(second, {}),
        )
        self.assertEqual(
            self.scene._catalog_palette().arrangement_item_at((group, *target)),
            first,
        )

        self.scene._place_palette_item(second, group, target)
        self.assertNotIn("palette_position", self.scene.palette_overrides.get(second, {}))
        self.assertIn("занята", self.scene.status.lower())

        self.scene._reset_palette_layout()
        self.assertNotIn(
            "palette_position",
            self.scene.palette_overrides.get(first, {}),
        )
        self.assertIsNotNone(
            next(row for row in self.scene._catalog_palette().rows if row.arrange_group is not None)
        )

    def test_artist_palette_drag_preserves_list_scroll(self):
        self.scene.palette_editing = True
        self.scene._refresh_palette_views()
        max_scroll = self.scene._max_scroll()
        self.assertGreater(max_scroll, 0)
        self.scene.list_scroll = max_scroll // 2
        original_scroll = self.scene.list_scroll
        palette = self.scene._catalog_palette()
        section = next(row for row in palette.rows if row.arrange_group is not None)
        group = section.arrange_group
        key = next(
            item["item_key"]
            for _rect, item in section.cells
            if not palette.compound_entries(item["item_key"])
        )
        occupied = set(palette.arrangement_positions(group).values())
        target = next(
            (column, line)
            for line in range(section.size[1] // palette.tile + 2)
            for column in range(10)
            if (column, line) not in occupied
        )

        self.scene._place_palette_item(key, group, target)

        self.assertEqual(
            self.scene.list_scroll,
            min(original_scroll, self.scene._max_scroll()),
        )

    def test_artist_palette_context_moves_tile_to_selected_section(self):
        palette = self.scene._catalog_palette()
        self.scene._record_palette_defaults(palette)
        key = next(
            item["item_key"]
            for row in palette.rows
            if row.kind == "block"
            for _rect, item in row.cells
            if not palette.compound_entries(item["item_key"])
        )
        self.scene.palette_editing = True
        self.scene.palette_overrides = {
            key: {"palette_position": {"x": 2, "y": 0}}
        }
        self.scene.palette_original_overrides = {}
        self.scene._refresh_palette_views()
        self.scene._open_palette_context(key, (300, 300))
        context = self.scene.palette_context
        current_group = self.scene._palette_rule(key)["palette_group"]
        groups = context["groups"]
        self.assertGreater(len(groups), 1)
        next_group = groups[(groups.index(current_group) + 1) % len(groups)]

        self.scene._palette_context_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=(context["rect"].right - 5, context["rect"].y + 150),
        ))

        self.assertEqual(
            context["rules"][key]["palette_group"],
            next_group,
        )
        self.assertNotIn("palette_group", self.scene.palette_overrides[key])
        self.scene._palette_context_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=(context["rect"].x + 20, context["rect"].y + 260),
        ))
        self.scene._palette_context_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=(context["rect"].x + 20, context["rect"].y + 260),
        ))

        self.assertEqual(self.scene.palette_overrides[key]["palette_group"], next_group)
        self.assertNotIn("palette_position", self.scene.palette_overrides[key])

    def test_artist_palette_marquee_selects_tiles_in_one_section(self):
        self.scene.palette_editing = True
        self.scene._refresh_palette_views()
        palette = self.scene._catalog_palette()
        section = next(row for row in palette.rows if row.arrange_group is not None)
        group = section.arrange_group
        positions = palette.arrangement_positions(group)
        max_line = section.size[1] // palette.tile
        occupied = set(positions.values())
        rectangle = None
        for start_y in range(max_line):
            for start_x in range(10):
                if (start_x, start_y) in occupied:
                    continue
                for end_y in range(start_y, max_line):
                    for end_x in range(start_x, 10):
                        if sum(
                            start_x <= x <= end_x and start_y <= y <= end_y
                            for x, y in positions.values()
                        ) >= 2:
                            rectangle = (start_x, start_y, end_x, end_y)
                            break
                    if rectangle:
                        break
                if rectangle:
                    break
            if rectangle:
                break
        self.assertIsNotNone(rectangle)
        start_x, start_y, end_x, end_y = rectangle
        self.scene.list_scroll = 0
        start_pos = (
            BLOCK_X + start_x * palette.tile + palette.tile // 2,
            self.scene._list_top() + section.top + BLOCK_PAD + start_y * palette.tile + palette.tile // 2,
        )
        end_pos = (
            BLOCK_X + end_x * palette.tile + palette.tile // 2,
            self.scene._list_top() + section.top + BLOCK_PAD + end_y * palette.tile + palette.tile // 2,
        )

        self.scene._panel_down(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=start_pos,
        ))
        self.assertEqual(self.scene.drag["mode"], "palette_select")
        self.scene._mouse_move(pygame.event.Event(
            pygame.MOUSEMOTION,
            pos=end_pos,
        ))
        self.scene._mouse_up(end_pos)

        self.assertEqual(
            self.scene.palette_selected_keys,
            palette.arrangement_items_in_rect(
                group,
                (start_x, start_y),
                (end_x, end_y),
            ),
        )
        self.assertGreaterEqual(len(self.scene.palette_selected_keys), 2)

        selected_key = next(iter(self.scene.palette_selected_keys))
        selected_rect = palette.item_rect(selected_key)
        context_pos = (
            selected_rect.centerx,
            self.scene._list_top() + selected_rect.centery - self.scene.list_scroll,
        )
        self.scene._panel_down(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=3,
            pos=context_pos,
        ))
        context = self.scene.palette_context
        self.assertEqual(context["keys"], self.scene.palette_selected_keys)
        self.scene._palette_context_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=(context["rect"].x + 20, context["rect"].y + 50),
        ))
        self.scene._palette_context_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=(context["rect"].x + 20, context["rect"].y + 260),
        ))
        self.scene._palette_context_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=(context["rect"].x + 20, context["rect"].y + 260),
        ))
        for key in self.scene.palette_selected_keys:
            self.assertEqual(
                self.scene.palette_overrides[key]["blocks"],
                not bool(self.scene.state.items[key]["blocks"]),
            )

    def test_entering_palette_editing_clears_legacy_full_section_positions(self):
        palette = self.scene._catalog_palette()
        title, clusters = next(
            (title, clusters)
            for title, clusters in palette._sections
            if any(cluster.cells for cluster in clusters)
        )
        keys = [
            item["item_key"]
            for cluster in clusters
            for _position, item in cluster.cells
            if not cluster.compound and cluster.preview_group is None
        ]
        self.assertGreater(len(keys), 1)
        legacy_overrides = {
            key: {"palette_position": {"x": index % 10, "y": index // 10}}
            for index, key in enumerate(keys)
        }
        self.scene.client = mock.Mock()
        self.scene.client.get_map_palette.return_value = {
            "version": 4,
            "overrides": legacy_overrides,
        }
        self.scene.ensure_login = lambda: True

        self.scene._enter_palette_editing()

        self.assertTrue(self.scene.palette_editing)
        self.assertTrue(all(
            "palette_position" not in self.scene.palette_overrides.get(key, {})
            for key in keys
        ))
        self.assertTrue(all(
            "palette_position" in self.scene.palette_original_overrides[key]
            for key in keys
        ))
        self.assertIn("восстановлена", self.scene.status.lower())
        self.assertTrue(any(
            row.arrange_group == title
            for row in self.scene._catalog_palette().rows
        ))

    def test_applying_palette_returns_to_normal_artist_mode(self):
        key = self.scene.catalog[0]["item_key"]
        self.scene.palette_editing = True
        self.scene.palette_overrides = {key: {"palette_position": {"x": 1, "y": 0}}}
        self.scene.palette_original_overrides = {}
        self.scene.palette_submit_credentials = ("artist", "password")
        self.scene.client = mock.Mock()
        self.scene.client.apply_map_palette.return_value = {
            "applied": True,
            "version": 2,
        }

        self.scene._apply_palette_changes()

        self.assertFalse(self.scene.palette_editing)
        self.assertIn("сохранена на сервере", self.scene.status)
        self.assertFalse(self.scene._catalog_palette().arrange_mode)

    def test_applying_palette_warns_about_automatically_removed_conflicts(self):
        self.scene.palette_editing = True
        self.scene.palette_submit_credentials = ("artist", "password")
        self.scene.client = mock.Mock()
        self.scene.client.apply_map_palette.return_value = {
            "applied": True,
            "version": 2,
            "removed_cells": [
                {
                    "key": self.scene.catalog[0]["item_key"],
                    "map_name": "Лесные дороги 64",
                    "x": 42,
                    "y": 30,
                },
            ],
        }

        self.scene._apply_palette_changes()

        self.assertIn("автоматически убраны", self.scene.status.lower())
        self.assertIn("Лесные дороги 64", self.scene.status)
        self.assertIn("(42, 30)", self.scene.status)
        self.assertIsNotNone(self.scene.toast)

    def test_invalid_palette_credentials_keep_retry_dialog_open(self):
        self.scene.palette_editing = True
        self.scene.palette_overrides = {"tile": {"blocks": False}}
        self.scene.client = mock.Mock()
        self.scene.client.preview_map_palette.side_effect = ValueError(
            "Неверный логин или пароль"
        )
        dialog = mock.Mock()
        dialog.handle_event.return_value = ("submit", "artist", "wrong")
        dialog.password = "wrong"
        self.scene.palette_credentials = dialog

        self.scene._palette_credentials_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))

        self.assertIs(self.scene.palette_credentials, dialog)
        self.assertEqual(dialog.password, "")
        self.assertEqual(dialog.active_field, 1)
        self.assertEqual(dialog.message_color, (240, 110, 100))
        self.assertIn("Неверный логин или пароль", dialog.message)
        self.assertEqual(self.scene.status_color, (240, 110, 100))
        self.assertTrue(self.scene.palette_editing)

    def test_palette_apply_error_reopens_credentials_for_retry(self):
        self.scene.palette_editing = True
        self.scene.palette_overrides = {"tile": {"blocks": False}}
        self.scene.palette_submit_credentials = ("artist", "wrong")
        self.scene.client = mock.Mock()
        self.scene.client.apply_map_palette.side_effect = ValueError(
            "Неверный логин или пароль"
        )

        self.scene._apply_palette_changes()

        self.assertIsNotNone(self.scene.palette_credentials)
        self.assertEqual(self.scene.palette_credentials.username, "artist")
        self.assertEqual(self.scene.palette_credentials.password, "")
        self.assertEqual(self.scene.palette_credentials.active_field, 1)
        self.assertIn("Неверный логин или пароль", self.scene.palette_credentials.message)
        self.assertEqual(self.scene.palette_credentials.message_color, (240, 110, 100))
        self.assertIsNone(self.scene.palette_submit_credentials)
        self.assertTrue(self.scene.palette_editing)

    def test_higher_paint_layer_covers_lower_without_deleting_it(self):
        ground = next(item for item in self.scene.catalog if item["kind"] == "ground" and item["category"] != "water")
        relief = next(item for item in self.scene.catalog if item["kind"] == "ground" and item["category"] == "rock")
        self.scene.state = MapEditorState(
            self.scene.catalog,
            [
                {"layer": "ground", "x": 0, "y": 0, "key": ground["item_key"]},
                {"layer": "relief", "x": 0, "y": 0, "key": relief["item_key"]},
            ],
            1,
            1,
        )
        self.scene._reset_editor_layers()
        self.scene.active_map_layer = 1
        self.scene.editor_layers[1].ground[(0, 0)] = relief["item_key"]
        self.scene.zoom = 32
        self.scene.origin_x = 0
        self.scene.origin_y = 0
        colors = {ground["item_key"]: (220, 30, 30), relief["item_key"]: (30, 30, 220)}
        self.scene._scaled_at_time = lambda key, _zoom, _ticks: self._solid_tile(colors[key])
        self.scene._draw_map_objects = lambda *_args, **_kwargs: None
        self.scene._draw_mobs = lambda *_args: None
        self.scene._draw_spawns = lambda *_args: None
        self.scene._draw_selection = lambda *_args: None
        self.scene._draw_hover = lambda *_args: None
        screen = pygame.Surface((1920, 1080))

        self.scene._draw_grid(screen)

        pixel = screen.get_at((self.scene.grid_rect().x + 16, self.scene.grid_rect().y + 16))
        self.assertEqual(pixel[:3], colors[relief["item_key"]])
        self.assertEqual(self.scene.state.ground[(0, 0)], ground["item_key"])

    def test_layer_visibility_and_seventy_percent_opacity_affect_render_only(self):
        ground = next(item for item in self.scene.catalog if item["kind"] == "ground" and item["category"] != "water")
        relief = next(item for item in self.scene.catalog if item["kind"] == "ground" and item["category"] == "rock")
        self.scene.state = MapEditorState(
            self.scene.catalog,
            [{"layer": "ground", "x": 0, "y": 0, "key": ground["item_key"]}],
            1,
            1,
        )
        self.scene._reset_editor_layers()
        self.scene.editor_layers[1].ground[(0, 0)] = relief["item_key"]
        self.scene.zoom = 32
        self.scene.origin_x = 0
        self.scene.origin_y = 0
        colors = {ground["item_key"]: (220, 30, 30), relief["item_key"]: (30, 30, 220)}
        self.scene._scaled_at_time = lambda key, _zoom, _ticks: self._solid_tile(colors[key])
        self.scene._draw_map_objects = lambda *_args, **_kwargs: None
        self.scene._draw_mobs = lambda *_args: None
        self.scene._draw_spawns = lambda *_args: None
        self.scene._draw_selection = lambda *_args: None
        self.scene._draw_hover = lambda *_args: None
        self.scene.show_grid = False
        screen = pygame.Surface((1920, 1080))
        target = (
            self.scene.grid_rect().x + 16,
            self.scene.grid_rect().y + 16,
        )

        self.scene.editor_layer_70[1] = True
        self.scene._draw_grid(screen)
        transparent = screen.get_at(target)
        self.assertGreater(transparent.b, transparent.r)
        self.assertGreater(transparent.r, 30)

        self.scene.editor_layer_visible[1] = False
        self.scene._draw_grid(screen)
        self.assertEqual(screen.get_at(target)[:3], colors[ground["item_key"]])
        self.assertIn((0, 0), self.scene.state.ground)

    def test_layer_edits_have_independent_undo_history(self):
        self.scene.active_map_layer = 1
        layer_state = self.scene._active_editor_state()
        bush = next(item for item in self.scene.catalog if item["kind"] == "object" and item["category"] == "bush")
        layer_state.begin_action()
        self.assertIsNone(layer_state.place(bush["item_key"], 2, 2))
        layer_state.end_action()
        self.scene.undo()
        self.assertEqual(layer_state.objects, {})
        self.assertEqual(self.scene.state.objects, {})

    def test_extra_layer_content_marks_draft_dirty_without_changing_base_map(self):
        self.scene.active_map_layer = 2
        soil = next(item for item in self.scene.catalog if item["kind"] == "ground" and item["category"] != "water")
        self.scene.selected = soil["item_key"]
        self.scene._paint((2, 2))

        self.assertIn((2, 2), self.scene.editor_layers[2].ground)
        self.assertEqual(self.scene.state.to_cells(), [])
        self.assertTrue(self.scene._dirty())

    def test_ninth_layer_is_reserved_for_mobs(self):
        self.scene.active_map_layer = EDITOR_LAYER_COUNT - 1
        self.scene.selected_npc = self.scene.npc_list[0]["key"]
        self.scene._place_mob((2, 2))

        self.assertIn((2, 2), self.scene.state.mobs)
        self.assertTrue(all(not layer.to_cells() for layer in self.scene.editor_layers))
        self.assertTrue(self.scene._dirty())

    def test_mobs_cannot_be_placed_on_another_artist_layer(self):
        self.scene.selected_npc = self.scene.npc_list[0]["key"]

        self.scene._place_mob((2, 2))

        self.assertEqual(self.scene.state.mobs, {})
        self.assertIn("только на слое 9", self.scene.status)

    @staticmethod
    def _solid_tile(color):
        tile = pygame.Surface((32, 32))
        tile.fill(color)
        return tile


if __name__ == "__main__":
    unittest.main()
