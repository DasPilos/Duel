import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from client import map_drafts
from client.map_editor_state import MapEditorState
from combat.progression import LEVEL_CAP
from core.map_catalog import catalog_definitions
from core.mob_catalog import MOB_KEYS
from server import map_editor, map_worlds
from tests.fixtures import create_test_database, drop_test_database

CATALOG = catalog_definitions()
GROUND = next(item["item_key"] for item in CATALOG if item["kind"] == "ground")


class SpawnStateTests(unittest.TestCase):
    def test_click_adds_then_removes_a_spawn(self):
        state = MapEditorState(CATALOG, [], 16, 16)
        self.assertEqual(state.toggle_spawn(3, 4), "added")
        self.assertEqual(state.toggle_spawn(3, 4), "removed")
        self.assertEqual(state.spawns, [])

    def test_several_spawns_keep_their_order(self):
        state = MapEditorState(CATALOG, [], 16, 16)
        state.toggle_spawn(1, 1)
        state.toggle_spawn(5, 2)
        self.assertEqual(state.to_spawns(), [{"x": 1, "y": 1}, {"x": 5, "y": 2}])

    def test_spawn_outside_the_map_is_refused(self):
        state = MapEditorState(CATALOG, [], 16, 16)
        self.assertEqual(state.toggle_spawn(16, 0), "Клетка вне карты")

    def test_spawns_are_undoable_and_mark_the_map_dirty(self):
        state = MapEditorState(CATALOG, [], 16, 16)
        state.mark_saved()
        state.begin_action()
        state.toggle_spawn(2, 2)
        self.assertTrue(state.end_action())
        self.assertTrue(state.dirty)
        state.undo()
        self.assertEqual(state.spawns, [])
        state.redo()
        self.assertEqual(state.spawns, [(2, 2)])

    def test_loading_skips_duplicates_and_points_outside_the_map(self):
        state = MapEditorState(CATALOG, [], 16, 16)
        state.load_spawns([{"x": 1, "y": 1}, {"x": 1, "y": 1}, {"x": 40, "y": 0}])
        self.assertEqual(state.spawns, [(1, 1)])

    def test_draft_keeps_spawns(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            spawns = [{"x": 3, "y": 4}]
            saved = map_drafts.save_draft("Спаун", [], 16, 16, folder=folder, spawns=spawns)
            self.assertEqual(map_drafts.load_draft(saved["id"], folder)["spawns"], spawns)


class SpawnValidationTests(unittest.TestCase):
    def test_valid_legacy_spawns_keep_their_coordinates(self):
        self.assertEqual(
            map_editor.validate_spawns([{"x": 0, "y": 0}, {"x": 15, "y": 3}], 16, 16),
            [{"x": 0, "y": 0}, {"x": 15, "y": 3}],
        )
        self.assertEqual(map_editor.validate_spawns(None, 16, 16), [])

    def test_mob_spawn_settings_are_validated_and_normalized(self):
        payload = [{
            "x": 4,
            "y": 5,
            "type": "mob",
            "settings": {
                "level": 7,
                "mob_key": "imp_vanilla",
                "count": 12,
                "interval_seconds": 45,
                "reward_xp": 10,
                "reward_copper": 10,
            },
        }]
        normalized = map_editor.validate_spawns(payload, 16, 16, include_settings=True)
        self.assertEqual(
            normalized[0]["settings"]["waves"],
            [{
                **payload[0]["settings"],
                "start_after_seconds": 0,
                "squad_min": 1,
                "squad_max": 1,
                "reward_xp": 10,
                "reward_copper": 10,
            }],
        )
        with self.assertRaisesRegex(ValueError, "нельзя публиковать"):
            map_editor.validate_spawns(payload, 16, 16)

    def test_front_line_waves_accept_palette_mobs_and_keep_their_keys(self):
        mob_key = "mob|goblin sprite-pack|g1"
        payload = [{
            "x": 4,
            "y": 5,
            "type": "mob",
            "settings": {
                "waves": [{
                    "level": 1,
                    "mob_key": mob_key,
                    "count": 2,
                    "interval_seconds": 30,
                }],
            },
        }]

        normalized = map_editor.validate_spawns(
            payload, 16, 16, include_settings=True, mode="front_line",
        )

        self.assertEqual(normalized[0]["settings"]["waves"][0]["mob_key"], mob_key)
        with self.assertRaisesRegex(ValueError, "отсутствует в каталоге"):
            map_editor.validate_spawns(payload, 16, 16, include_settings=True, mode="tower")

    def test_front_line_squads_survive_normalization(self):
        mob_key = "mob|goblin sprite-pack|g1"
        wave = {"level": 1, "mob_key": mob_key, "count": 100, "interval_seconds": 30}
        payload = [{"x": 4, "y": 5, "type": "mob", "settings": {"waves": [
            {**wave, "squad_min": 2, "squad_max": 8},
        ]}}]
        normalized = map_editor.validate_spawns(payload, 16, 16, include_settings=True, mode="front_line")
        saved = normalized[0]["settings"]["waves"][0]
        self.assertEqual((saved["squad_min"], saved["squad_max"]), (2, 8))
        plain = [{"x": 4, "y": 5, "type": "mob", "settings": {"waves": [wave]}}]
        plain_saved = map_editor.validate_spawns(plain, 16, 16, include_settings=True, mode="front_line")
        self.assertEqual((plain_saved[0]["settings"]["waves"][0]["squad_min"], plain_saved[0]["settings"]["waves"][0]["squad_max"]), (1, 1))
        broken = [{"x": 4, "y": 5, "type": "mob", "settings": {"waves": [
            {**wave, "squad_min": 5, "squad_max": 3},
        ]}}]
        with self.assertRaisesRegex(ValueError, "минимума"):
            map_editor.validate_spawns(broken, 16, 16, include_settings=True, mode="front_line")

    def test_front_line_wave_without_a_mob_has_actionable_error(self):
        payload = [{
            "x": 4,
            "y": 5,
            "type": "mob",
            "settings": {"waves": [{"level": 1, "mob_key": "", "count": 1, "interval_seconds": 30}]},
        }]

        with self.assertRaisesRegex(ValueError, "Для волны 1 не сохранён выбор моба"):
            map_editor.validate_spawns(
                payload, 16, 16, include_settings=True, mode="front_line",
            )

    def test_front_line_waves_accept_catalog_rat_and_report_unknown_mob_key(self):
        rat_key = next(key for key in MOB_KEYS if "|rat1" in key)
        spawn = {
            "x": 4,
            "y": 5,
            "type": "mob",
            "settings": {
                "waves": [{
                    "level": 1,
                    "mob_key": rat_key,
                    "count": 1,
                    "interval_seconds": 30,
                }],
            },
        }

        normalized = map_editor.validate_spawns(
            [spawn], 16, 16, include_settings=True, mode="front_line",
        )
        self.assertEqual(normalized[0]["settings"]["waves"][0]["mob_key"], rat_key)

        spawn["settings"]["waves"][0]["mob_key"] = "mob|unknown-pack|rat"
        with self.assertRaisesRegex(ValueError, "mob\\|unknown-pack\\|rat.*Front Line"):
            map_editor.validate_spawns(
                [spawn], 16, 16, include_settings=True, mode="front_line",
            )

    def test_mob_spawn_settings_enforce_runtime_limits(self):
        wave_settings = {
            "level": LEVEL_CAP,
            "mob_key": "imp_vanilla",
            "count": map_editor.MAX_MOB_SPAWN_COUNT,
            "interval_seconds": map_editor.MAX_MOB_SPAWN_INTERVAL_SECONDS,
            "reward_xp": map_editor.MAX_MOB_SPAWN_REWARD,
            "reward_copper": map_editor.MAX_MOB_SPAWN_REWARD,
        }
        settings = {"waves": [wave_settings]}
        valid = [{"x": 1, "y": 1, "type": "mob", "settings": settings}]
        self.assertEqual(
            map_editor.validate_spawns(valid, 16, 16, include_settings=True)[0]["settings"],
            {"waves": [{**wave_settings, "start_after_seconds": 0, "squad_min": 1, "squad_max": 1}]},
        )
        for key, value in (
            ("level", LEVEL_CAP + 1),
            ("count", map_editor.MAX_MOB_SPAWN_COUNT + 1),
            ("interval_seconds", map_editor.MAX_MOB_SPAWN_INTERVAL_SECONDS + 1),
            ("start_after_seconds", map_editor.MAX_MOB_SPAWN_START_DELAY_SECONDS + 1),
            ("reward_xp", map_editor.MAX_MOB_SPAWN_REWARD + 1),
            ("reward_copper", map_editor.MAX_MOB_SPAWN_REWARD + 1),
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                map_editor.validate_spawns(
                    [{"x": 1, "y": 1, "type": "mob", "settings": {"waves": [{**wave_settings, key: value}]}}],
                    16,
                    16,
                    include_settings=True,
                )

    def test_multiple_waves_are_validated_independently_and_legacy_settings_are_supported(self):
        waves = [
            {
                "level": 2, "mob_key": "imp_vanilla", "count": 3,
                "interval_seconds": 10, "start_after_seconds": 15,
            },
            {
                "level": 8, "mob_key": "imp_vanilla", "count": 5,
                "interval_seconds": 30, "start_after_seconds": 900,
            },
        ]
        normalized = map_editor.validate_spawns(
            [{"x": 1, "y": 1, "type": "mob", "settings": {"waves": waves}}],
            16,
            16,
            include_settings=True,
        )
        self.assertEqual(
            normalized[0]["settings"]["waves"],
            [
                {**waves[0], "squad_min": 1, "squad_max": 1, "reward_xp": 10, "reward_copper": 10},
                {**waves[1], "squad_min": 1, "squad_max": 1, "reward_xp": 10, "reward_copper": 10},
            ],
        )
        legacy = map_editor.validate_spawns(
            [{
                "x": 1, "y": 1, "type": "mob",
                "settings": {
                    "level": 2, "mob_key": "imp_vanilla", "count": 3,
                    "interval_seconds": 10,
                },
            }],
            16,
            16,
            include_settings=True,
        )
        self.assertEqual(len(legacy[0]["settings"]["waves"]), 1)
        self.assertEqual(legacy[0]["settings"]["waves"][0]["count"], 3)

    def test_mob_spawn_target_is_front_line_only_and_validated(self):
        spawn = {
            "x": 1,
            "y": 1,
            "type": "mob",
            "settings": {
                "level": 1,
                "mob_key": "imp_vanilla",
                "count": 1,
                "interval_seconds": 30,
                "target": "both",
            },
        }
        normalized = map_editor.validate_spawns(
            [spawn], 16, 16, include_settings=True, mode="front_line",
        )
        self.assertEqual(normalized[0]["settings"]["waves"][0]["target"], "both")
        self.assertEqual(
            map_editor.validate_spawns(
                [{**spawn, "settings": {key: value for key, value in spawn["settings"].items() if key != "target"}}],
                16,
                16,
                include_settings=True,
                mode="front_line",
            )[0]["settings"]["waves"][0]["target"],
            "objective",
        )
        with self.assertRaisesRegex(ValueError, "только в режиме Front Line"):
            map_editor.validate_spawns(
                [spawn], 16, 16, include_settings=True, mode="tower",
            )
        for target in ("", "heroes", 1, None):
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, "Цель спауна"):
                map_editor.validate_spawns(
                    [{**spawn, "settings": {**spawn["settings"], "target": target}}],
                    16,
                    16,
                    include_settings=True,
                    mode="front_line",
                )

    def test_front_line_boss_and_spell_slot_settings_are_validated(self):
        boss_settings = {
            "enabled": True,
            "max_hp": 4321,
            "max_mp": 765,
            "reward_xp": 987,
            "spell_slots": [{
                "spell_key": "",
                "range": 8,
                "damage": 120,
                "cooldown_seconds": 7,
                "area_radius": 4,
                "mana_cost": 25,
            }],
            "drop_slots": [{"item_id": 1, "chance_percent": 15}],
        }
        normalized = map_editor.validate_spawns(
            [{
                "x": 1,
                "y": 1,
                "type": "mob",
                "settings": {
                    "waves": [{
                        "mob_key": "imp_vanilla",
                        "level": 1,
                        "count": 1,
                        "interval_seconds": 10,
                        "boss": boss_settings,
                    }],
                },
            }],
            16,
            16,
            include_settings=True,
            mode="front_line",
        )
        boss = normalized[0]["settings"]["waves"][0]["boss"]
        self.assertTrue(boss["enabled"])
        self.assertEqual((boss["max_hp"], boss["max_mp"], boss["reward_xp"]), (4321, 765, 987))
        self.assertEqual(boss["spell_slots"][0]["damage"], 120)
        self.assertEqual(boss["spell_slots"][0]["cooldown_seconds"], 7)
        self.assertEqual(len(boss["spell_slots"]), map_editor.MAX_BOSS_SPELL_SLOTS)
        self.assertEqual(len(boss["drop_slots"]), map_editor.MAX_BOSS_DROP_SLOTS)
        self.assertEqual(boss["drop_slots"][0], {"item_id": 1, "chance_percent": 15})
        for invalid_boss in (
            {"enabled": "yes"},
            {"enabled": True, "max_hp": 0},
            {"enabled": True, "max_mp": -1},
            {"enabled": True, "spell_slots": [{}] * (map_editor.MAX_BOSS_SPELL_SLOTS + 1)},
            {"enabled": True, "spell_slots": [{"damage": map_editor.MAX_BOSS_SPELL_DAMAGE + 1}]},
            {"enabled": True, "drop_slots": [{"item_id": 999999, "chance_percent": 10}]},
            {"enabled": True, "drop_slots": [{"item_id": 1, "chance_percent": 101}]},
            {"enabled": True, "drop_slots": [{"item_id": 1, "chance_percent": 60}] * 2},
            {"enabled": True, "drop_slots": [{"item_id": 1, "chance_percent": 10}] * (map_editor.MAX_BOSS_DROP_SLOTS + 1)},
        ):
            with self.subTest(boss=invalid_boss), self.assertRaises(ValueError):
                map_editor.validate_spawns(
                    [{
                        "x": 1,
                        "y": 1,
                        "type": "mob",
                        "settings": {
                            "waves": [{
                                "mob_key": "imp_vanilla",
                                "count": 1,
                                "interval_seconds": 10,
                                "boss": invalid_boss,
                            }],
                        },
                    }],
                    16,
                    16,
                    include_settings=True,
                    mode="front_line",
                )
        with self.assertRaisesRegex(ValueError, "только в режиме Front Line"):
            map_editor.validate_spawns(
                [{
                    "x": 1,
                    "y": 1,
                    "type": "mob",
                    "settings": {
                        "waves": [{
                            "mob_key": "imp_vanilla",
                            "count": 1,
                            "interval_seconds": 10,
                            "boss": boss_settings,
                        }],
                    },
                }],
                16,
                16,
                include_settings=True,
                mode="tower",
            )

    def test_bad_spawns_are_rejected(self):
        for spawns in ([{"x": 16, "y": 0}], [{"x": 1, "y": 1}, {"x": 1, "y": 1}], ["не объект"]):
            with self.assertRaises(ValueError, msg=repr(spawns)):
                map_editor.validate_spawns(spawns, 16, 16)
        invalid_settings = [
            {"level": 0, "mob_key": "skeleton", "count": 1, "interval_seconds": 5},
            {"level": 1, "mob_key": "", "count": 1, "interval_seconds": 5},
            {"level": 1, "mob_key": "mob|test|skeleton", "count": 1, "interval_seconds": 5},
            {"level": 1, "mob_key": "skeleton", "count": 0, "interval_seconds": 5},
            {"level": 1, "mob_key": "skeleton", "count": 1, "interval_seconds": 0},
            {"level": 1, "mob_key": "skeleton", "count": 1, "interval_seconds": 5, "reward_xp": -1},
            {"level": 1, "mob_key": "skeleton", "count": 1, "interval_seconds": 5, "reward_copper": -1},
        ]
        for settings in invalid_settings:
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                map_editor.validate_spawns(
                    [{"x": 1, "y": 1, "type": "mob", "settings": settings}],
                    16,
                    16,
                    include_settings=True,
                )


class SpawnServerTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        self.admin = self.database.register("spawn-admin", "password")
        with self.database.connection() as connection:
            connection.execute("UPDATE users SET role = 'admin' WHERE id = %s", (self.admin["id"],))
        self.body = {
            "name": "Спаун-карта", "mode": "tower", "map_w": 16, "map_h": 16,
            "cells": [{"layer": "ground", "x": 0, "y": 0, "key": GROUND}],
            "mobs": [], "spawns": [{"x": 2, "y": 3}, {"x": 9, "y": 9}],
        }

    def tearDown(self):
        drop_test_database(self.database)

    def test_saved_map_keeps_its_spawns(self):
        saved = map_worlds.save_map(self.database, self.admin["id"], self.body)
        self.assertEqual(self.database.get_saved_map(saved["saved_id"])["spawns"], [{"x": 2, "y": 3}, {"x": 9, "y": 9}])

    def test_front_line_draft_persists_mob_spawn_configuration(self):
        payload = {
            **self.body,
            "mode": "front_line",
            "spawns": [
                {"x": 2, "y": 3, "type": "hero", "name": "Площадь"},
                {
                    "x": 4,
                    "y": 5,
                    "type": "mob",
                    "name": "Лесной вход",
                    "settings": {
                        "waves": [
                            {
                                "level": 7,
                                "mob_key": "imp_vanilla",
                                "count": 12,
                                "interval_seconds": 45,
                                "start_after_seconds": 0,
                                "reward_xp": 75,
                                "reward_copper": 38,
                                "target": "characters",
                            },
                            {
                                "level": 11,
                                "mob_key": "imp_vanilla",
                                "count": 3,
                                "interval_seconds": 90,
                                "start_after_seconds": 120,
                                "reward_xp": 200,
                                "reward_copper": 100,
                                "target": "both",
                                "boss": {
                                    "enabled": True,
                                    "max_hp": 4321,
                                    "max_mp": 765,
                                    "reward_xp": 987,
                                    "spell_slots": [{
                                        "spell_key": "",
                                        "range": 8,
                                        "damage": 120,
                                        "cooldown_seconds": 7,
                                        "area_radius": 4,
                                        "mana_cost": 25,
                                    }],
                                },
                            },
                        ],
                    },
                },
            ],
        }
        saved = map_worlds.save_map(self.database, self.admin["id"], payload)
        self.assertEqual(
            self.database.get_saved_map(saved["saved_id"])["spawns"],
            map_editor.validate_spawns(
                payload["spawns"], 16, 16, include_settings=True, mode="front_line",
            ),
        )
        world = map_worlds.create_test_world(
            self.database, self.admin["id"], {"saved_id": saved["saved_id"]},
        )
        with self.database.connection() as connection:
            published = connection.execute(
                "SELECT mode, saved_id FROM map_world_publish WHERE world_id = %s",
                (world["world_id"],),
            ).fetchone()
            hero_spawns = connection.execute(
                "SELECT x, y FROM map_live_spawns WHERE world_id = %s",
                (world["world_id"],),
            ).fetchall()
        self.assertEqual((published["mode"], published["saved_id"]), ("front_line", saved["saved_id"]))
        self.assertEqual([(spawn["x"], spawn["y"]) for spawn in hero_spawns], [(2, 3)])

    def test_non_front_line_world_rejects_mob_spawns_on_publish(self):
        payload = {
            **self.body,
            "spawns": [
                {"x": 2, "y": 3},
                {
                    "x": 4,
                    "y": 5,
                    "type": "mob",
                    "settings": {
                        "level": 1,
                        "mob_key": "imp_vanilla",
                        "count": 1,
                        "interval_seconds": 30,
                    },
                },
            ],
        }
        saved = map_worlds.save_map(self.database, self.admin["id"], payload)
        with self.assertRaisesRegex(ValueError, "нельзя публиковать"):
            map_worlds.create_test_world(
                self.database, self.admin["id"], {"saved_id": saved["saved_id"]},
            )

    def test_test_world_gets_the_spawns_of_its_map(self):
        saved = map_worlds.save_map(self.database, self.admin["id"], self.body)
        world = map_worlds.create_test_world(self.database, self.admin["id"], {"saved_id": saved["saved_id"]})
        with self.database.connection() as connection:
            rows = connection.execute(
                "SELECT x, y FROM map_live_spawns WHERE world_id = %s ORDER BY x", (world["world_id"],)).fetchall()
        self.assertEqual([(row["x"], row["y"]) for row in rows], [(2, 3), (9, 9)])

    def test_out_of_map_spawn_is_rejected_and_nothing_is_saved(self):
        with self.assertRaises(ValueError):
            map_worlds.save_map(self.database, self.admin["id"], {**self.body, "spawns": [{"x": 99, "y": 0}]})


class SpawnTabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1920, 1080))

    def setUp(self):
        from scenes.map_editor_scene import MapEditorScene
        self.scene = MapEditorScene(None, CATALOG, lambda: True)
        self.scene.has_map = True

    def test_spawn_tab_is_inside_the_palette_panel(self):
        panel = self.scene.panel_rect()
        spawn_tabs = [rect for section, _label, rect in self.scene._tab_rects() if section == "spawn"]
        self.assertEqual(len(spawn_tabs), 1)
        self.assertTrue(panel.contains(spawn_tabs[0]), (panel, spawn_tabs[0]))

    def test_all_three_tabs_fit_without_overlap(self):
        rects = [rect for _section, _label, rect in self.scene._tab_rects()]
        for index, rect in enumerate(rects):
            self.assertTrue(self.scene.panel_rect().contains(rect), rect)
            for other in rects[index + 1:]:
                self.assertFalse(rect.colliderect(other), (rect, other))

    def test_clicking_a_tile_in_the_spawn_tab_places_a_spawn(self):
        self.scene._set_section("spawn")
        self.scene._grid_primary((4, 5))
        self.assertEqual(self.scene.state.spawns, [(4, 5)])
        self.scene._grid_secondary((4, 5))
        self.assertEqual(self.scene.state.spawns, [])

    def test_the_grid_draws_spawns(self):
        screen = pygame.display.get_surface()
        self.scene._set_section("spawn")
        self.scene._grid_primary((2, 2))
        self.scene.hover = (3, 3)
        self.scene.draw(screen)


if __name__ == "__main__":
    unittest.main()
