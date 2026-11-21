import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from client import map_drafts
from core import mob_modes
from core.game_modes import DEFAULT_MODE, GAME_MODES, is_mode, mode_name
from core.map_catalog import catalog_definitions
from core.npc_catalog import NPC_CATALOG
from scenes.map_editor_scene import MapEditorScene
from scenes.map_editor_ui import DraftList, EquipmentDialog, MobParamsDialog, SizePicker, draft_details


class GameModesTests(unittest.TestCase):
    def test_tower_is_the_default_mode(self):
        self.assertEqual(DEFAULT_MODE, "tower")
        self.assertTrue(is_mode("tower"))
        self.assertTrue(is_mode("deck"))
        self.assertTrue(is_mode("economy"))
        self.assertFalse(is_mode("unknown"))
        self.assertEqual(mode_name("tower"), "Tower")
        self.assertEqual(mode_name("deck"), "Deck")
        self.assertEqual(mode_name("economy"), "Economy")


class MobSettingsTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

    def test_defaults_are_valid_and_follow_world_formulas(self):
        defaults = mob_modes.default_settings("imp_sword")
        self.assertEqual(mob_modes.validate_settings(defaults), defaults)
        self.assertEqual(defaults["move_speed"], 180.0)  # 160 + 5 * ловкость 4
        self.assertEqual(defaults["windup"], 0.44)  # 0.5 - 0.02 * интуиция 3
        self.assertEqual(defaults["backswing"], 0.42)  # 0.5 - 0.02 * ловкость 4
        self.assertEqual(defaults["state"], "aggressive")
        self.assertIn([0, 0], defaults["patrol"])

    def test_missing_file_gives_defaults(self):
        self.assertEqual(
            mob_modes.load_mob_settings("tower", "imp_sword", self.folder.name),
            mob_modes.default_settings("imp_sword"),
        )

    def test_save_keeps_other_mobs_and_roundtrips(self):
        sword = {**mob_modes.default_settings(), "state": "neutral", "windup": 0.6, "patrol": [[0, 0], [1, -2]]}
        pitchfork = {**mob_modes.default_settings(), "aggro_tiles": 7.0}
        mob_modes.save_mob_settings("tower", "imp_sword", sword, self.folder.name)
        mob_modes.save_mob_settings("tower", "imp_pitchfork", pitchfork, self.folder.name)
        loaded = mob_modes.load_mob_settings("tower", "imp_sword", self.folder.name)
        self.assertEqual((loaded["state"], loaded["windup"], loaded["patrol"]), ("neutral", 0.6, [[1, -2], [0, 0]]))
        self.assertEqual(mob_modes.load_mob_settings("tower", "imp_pitchfork", self.folder.name)["aggro_tiles"], 7.0)
        data = json.loads((Path(self.folder.name) / "tower.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(data["mobs"]), ["imp_pitchfork", "imp_sword"])

    def test_mob_settings_are_isolated_between_modes(self):
        tower_settings = {
            **mob_modes.default_settings("imp_sword"),
            "state": "aggressive",
            "windup": 0.6,
        }
        deck_settings = {
            **mob_modes.default_settings("imp_sword"),
            "state": "neutral",
            "windup": 0.8,
        }

        mob_modes.save_mob_settings("tower", "imp_sword", tower_settings, self.folder.name)
        mob_modes.save_mob_settings("deck", "imp_sword", deck_settings, self.folder.name)

        self.assertEqual(
            mob_modes.load_mob_settings("tower", "imp_sword", self.folder.name)["windup"],
            0.6,
        )
        self.assertEqual(
            mob_modes.load_mob_settings("deck", "imp_sword", self.folder.name)["windup"],
            0.8,
        )
        self.assertEqual(
            mob_modes.load_mob_settings("economy", "imp_sword", self.folder.name),
            mob_modes.default_settings("imp_sword"),
        )

    def test_attack_range_is_a_front_line_only_setting(self):
        settings = mob_modes.default_settings("imp_vanilla")
        mob_modes.save_mob_settings("front_line", "imp_vanilla", {**settings, "attack_range": 250}, self.folder.name)
        loaded = mob_modes.load_mob_settings("front_line", "imp_vanilla", self.folder.name)
        self.assertEqual(loaded["attack_range"], 250)
        self.assertNotIn("attack_range", mob_modes.validate_settings({**settings, "attack_range": 250}, mode="tower"))

    def test_base_damage_is_front_line_only_and_must_be_ordered(self):
        settings = mob_modes.default_settings("imp_vanilla")
        self.assertEqual(mob_modes.validate_settings(settings, mode="front_line")["damage_min"], 0)
        front = mob_modes.validate_settings({**settings, "damage_min": 2, "damage_max": 5}, mode="front_line")
        self.assertEqual((front["damage_min"], front["damage_max"]), (2, 5))
        self.assertNotIn("damage_min", mob_modes.validate_settings({**settings, "damage_min": 2, "damage_max": 5}, mode="tower"))
        with self.assertRaises(ValueError):
            mob_modes.validate_settings({**settings, "damage_min": 6, "damage_max": 5}, mode="front_line")

    def test_attack_range_defaults_to_one_tile_and_rejects_bad_values(self):
        settings = mob_modes.default_settings("imp_vanilla")
        self.assertEqual(mob_modes.load_mob_settings("front_line", "imp_vanilla", self.folder.name)["attack_range"], 100)
        with self.assertRaises(ValueError):
            mob_modes.validate_settings({**settings, "attack_range": 2000}, mode="front_line")
        with self.assertRaises(ValueError):
            mob_modes.validate_settings({**settings, "attack_range": True}, mode="front_line")

    def test_front_line_stats_and_resources_are_not_limited_by_level_or_point_budget(self):
        settings = mob_modes.default_settings("imp_sword")
        settings["level"] = 100
        settings["stats"] = {
            "strength": 1_000_000,
            "agility": 2_000_000,
            "intuition": 3_000_000,
            "wisdom": 4_000_000,
            "intellect": 5_000_000,
            "endurance": 6_000_000,
        }
        settings["max_hp"] = 7_000_000
        settings["max_mp"] = 8_000_000

        checked = mob_modes.validate_settings(settings, mode="front_line")
        saved = mob_modes.save_mob_settings(
            "front_line", "imp_sword", checked, self.folder.name,
        )
        loaded = mob_modes.load_mob_settings(
            "front_line", "imp_sword", self.folder.name,
        )

        self.assertEqual(loaded, saved)
        self.assertEqual(loaded["stats"]["endurance"], 6_000_000)
        self.assertEqual((loaded["max_hp"], loaded["max_mp"]), (7_000_000, 8_000_000))
        with self.assertRaisesRegex(ValueError, "Уровень"):
            mob_modes.validate_settings(settings, mode="tower")

    def test_front_line_resource_values_must_be_valid_integers(self):
        settings = mob_modes.default_settings()
        settings["max_hp"] = 0
        with self.assertRaisesRegex(ValueError, "max_hp"):
            mob_modes.validate_settings(settings, mode="front_line")
        settings["max_hp"] = 100
        settings["max_mp"] = -1
        with self.assertRaisesRegex(ValueError, "max_mp"):
            mob_modes.validate_settings(settings, mode="front_line")
        settings["max_mp"] = 0
        settings["stats"]["endurance"] = -1
        with self.assertRaisesRegex(ValueError, "Выносливость"):
            mob_modes.validate_settings(settings, mode="front_line")

    def test_invalid_settings_are_rejected_and_file_is_untouched(self):
        good = mob_modes.default_settings()
        mob_modes.save_mob_settings("tower", "imp_sword", good, self.folder.name)
        bad_cases = [
            {**good, "move_speed": 9999},
            {**good, "windup": 0},
            {**good, "state": "angry"},
            {**good, "stats": {**good["stats"], "strength": 0}},
            {**good, "patrol": [[40, 0]]},
        ]
        for bad in bad_cases:
            with self.assertRaises(ValueError):
                mob_modes.save_mob_settings("tower", "imp_sword", bad, self.folder.name)
        self.assertEqual(mob_modes.load_mob_settings("tower", "imp_sword", self.folder.name), good)

    def test_unknown_mode_and_broken_file(self):
        with self.assertRaises(mob_modes.ModeFileError):
            mob_modes.load_mob_settings("arena", "imp_sword", self.folder.name)
        (Path(self.folder.name) / "tower.json").write_text("{не json", encoding="utf-8")
        with self.assertRaises(mob_modes.ModeFileError):
            mob_modes.load_mob_settings("tower", "imp_sword", self.folder.name)

    def test_shipped_tower_file_covers_every_npc(self):
        for npc in NPC_CATALOG:
            settings = mob_modes.load_mob_settings("tower", npc["key"])
            self.assertEqual(mob_modes.validate_settings(settings), settings)
        data = json.loads(mob_modes.mode_file("tower").read_text(encoding="utf-8"))
        self.assertEqual(sorted(data["mobs"]), sorted(npc["key"] for npc in NPC_CATALOG))


class MobEquipmentTests(unittest.TestCase):
    def test_item_needs_stats_and_level_from_its_requirements(self):
        club = {"effects": {"requirements": {"strength": 6}}}
        self.assertTrue(mob_modes.item_fits_mob(club, {"strength": 6}, 1))
        self.assertFalse(mob_modes.item_fits_mob(club, {"strength": 5}, 1))
        leveled = {"effects": {"requirements": {"strength": 4, "level": 3}}}
        self.assertFalse(mob_modes.item_fits_mob(leveled, {"strength": 9}, 2))
        self.assertTrue(mob_modes.item_fits_mob(leveled, {"strength": 4}, 3))

    def test_slots_match_the_character_doll(self):
        self.assertEqual(len(mob_modes.MOB_EQUIPMENT_SLOTS), 13)
        self.assertIn("head", mob_modes.MOB_EQUIPMENT_SLOTS)
        self.assertIn("ring_2", mob_modes.MOB_EQUIPMENT_SLOTS)

    def test_picker_offers_only_fitting_items_and_empty(self):
        scene = MapEditorScene(None, catalog_definitions(), lambda: False)
        settings = mob_modes.default_settings("imp_sword")
        settings["stats"]["strength"] = 8
        items = [
            {"id": 23, "name": "Дубина", "equip_slot": "weapon", "effects": {"requirements": {"strength": 6}}},
            {"id": 24, "name": "Лук", "equip_slot": "weapon", "effects": {"requirements": {"agility": 9}}},
        ]
        dialog = MobParamsDialog(scene.font, scene.small, "Бес", "Башня", settings, items)
        window = EquipmentDialog(scene.font, scene.small, "Бес", settings["stats"], settings["level"], dialog.equipment, items)
        self.assertEqual([None if item is None else item["id"] for item in window._eligible("weapon")], [None, 23])

    def test_ring_2_takes_ring_items_and_skips_the_ring_worn_elsewhere(self):
        self.assertEqual(mob_modes.item_slot("ring_2"), "ring")
        self.assertEqual(mob_modes.item_slot("weapon"), "weapon")
        scene = MapEditorScene(None, catalog_definitions(), lambda: False)
        settings = mob_modes.default_settings("imp_sword")
        items = [
            {"id": 60, "name": "Перстень", "equip_slot": "ring", "effects": {}},
            {"id": 61, "name": "Кольцо силы", "equip_slot": "ring", "effects": {}},
        ]
        equipment = {slot: None for slot in mob_modes.MOB_EQUIPMENT_SLOTS}
        equipment["ring"] = 60
        window = EquipmentDialog(scene.font, scene.small, "Бес", settings["stats"], settings["level"], equipment, items)
        self.assertEqual([None if item is None else item["id"] for item in window._eligible("ring_2")], [None, 61])

    def test_drop_unfit_equipment_keeps_fitting_and_unknown_items(self):
        items = [
            {"id": 23, "equip_slot": "weapon", "effects": {"requirements": {"strength": 6}}},
            {"id": 38, "equip_slot": "shield", "effects": {}},
        ]
        equipment = {"weapon": 23, "shield": 38, "ring": 999}
        result = mob_modes.drop_unfit_equipment(equipment, items, {"strength": 3}, 1)
        self.assertIsNone(result["weapon"])
        self.assertEqual(result["shield"], 38)
        self.assertEqual(result["ring"], 999)
        kept = mob_modes.drop_unfit_equipment(equipment, items, {"strength": 6}, 1)
        self.assertEqual(kept["weapon"], 23)


class MobLevelTests(unittest.TestCase):
    def test_level_table_matches_the_rules(self):
        self.assertEqual([mob_modes.endurance_for_level(level) for level in (1, 2, 3, 10)], [4, 5, 6, 13])
        self.assertEqual([mob_modes.free_points_for_level(level) for level in (1, 2, 3, 10)], [3, 6, 9, 30])

    def test_default_imp_is_a_valid_level_one(self):
        defaults = mob_modes.default_settings("imp_sword")
        self.assertEqual(defaults["level"], 1)
        self.assertEqual(defaults["stats"]["endurance"], 4)
        self.assertEqual(mob_modes.free_points(1, defaults["stats"]), 0)

    def test_validation_follows_the_level(self):
        base = {**mob_modes.default_settings(), "stats": {k: 3 for k in mob_modes.DEFAULT_STATS}}
        base["stats"]["endurance"] = 5
        level2 = {**base, "level": 2}
        level2["stats"] = {**base["stats"], "strength": 9}  # вложено 6 из 6
        self.assertEqual(mob_modes.validate_settings(level2)["level"], 2)
        for bad in (
            {**level2, "stats": {**level2["stats"], "strength": 10}},  # вложено 7 из 6
            {**level2, "stats": {**level2["stats"], "endurance": 4}},  # выносливость не по уровню
            {**level2, "level": 0},
            {**level2, "level": 31},
        ):
            with self.assertRaises(ValueError):
                mob_modes.validate_settings(bad)


class MobRespawnTests(unittest.TestCase):
    def test_format_is_hours_minutes_seconds(self):
        self.assertEqual(mob_modes.format_hms(0), "00:00:00")
        self.assertEqual(mob_modes.format_hms(30), "00:00:30")
        self.assertEqual(mob_modes.format_hms(3725), "01:02:05")
        self.assertEqual(mob_modes.format_hms(86399), "23:59:59")

    def test_default_respawn_matches_the_server_delay(self):
        self.assertEqual(mob_modes.default_settings("imp_sword")["respawn_seconds"], 30)

    def test_respawn_is_saved_as_whole_seconds(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        settings = {**mob_modes.default_settings(), "respawn_seconds": 90.0}
        mob_modes.save_mob_settings("tower", "imp_sword", settings, folder.name)
        loaded = mob_modes.load_mob_settings("tower", "imp_sword", folder.name)
        self.assertEqual(loaded["respawn_seconds"], 90)
        self.assertIsInstance(loaded["respawn_seconds"], int)

    def test_respawn_range_is_checked(self):
        base = mob_modes.default_settings()
        for bad in (-1, 86400, "много"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                mob_modes.validate_settings({**base, "respawn_seconds": bad})
        self.assertEqual(mob_modes.validate_settings({**base, "respawn_seconds": 0})["respawn_seconds"], 0)

    def test_dialog_shows_and_changes_respawn(self):
        pygame.init()
        pygame.display.set_mode((1920, 1080))
        dialog = MobParamsDialog(pygame.font.SysFont("arial", 16), pygame.font.SysFont("arial", 13),
                                 "Бес", "Башня", mob_modes.default_settings("imp_sword"))
        self.assertEqual(dialog.values["respawn_seconds"], 30.0)
        dialog.draw(pygame.display.get_surface())
        self.assertEqual(dialog.settings()["respawn_seconds"], 30)
        plus = dialog._field_rects(4)[2]
        dialog.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=plus.center))
        self.assertEqual(dialog.settings()["respawn_seconds"], 35)
        minus = dialog._field_rects(4)[0]
        for _ in range(10):
            dialog.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=minus.center))
        self.assertEqual(dialog.settings()["respawn_seconds"], 0)  # не ниже нуля


class DraftModeTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

    def cells(self):
        return [{"layer": "ground", "x": 0, "y": 0, "key": "a"}]

    def test_mode_is_saved_listed_and_kept_on_resave(self):
        saved = map_drafts.save_draft("Карта", self.cells(), 16, 16, folder=Path(self.folder.name), mode="tower")
        self.assertEqual(saved["mode"], "tower")
        again = map_drafts.save_draft("Карта", self.cells(), 16, 16, saved["id"], Path(self.folder.name))
        self.assertEqual(again["mode"], "tower")
        self.assertEqual(map_drafts.list_drafts(Path(self.folder.name))[0]["mode"], "tower")

    def test_draft_without_mode_defaults_to_tower(self):
        path = Path(self.folder.name) / "old.json"
        path.write_text(json.dumps({
            "id": "old", "name": "Старая", "map_w": 16, "map_h": 16, "updated_at": 1,
            "cells": [], "published": [],
        }), encoding="utf-8")
        self.assertEqual(map_drafts.list_drafts(Path(self.folder.name))[0]["mode"], DEFAULT_MODE)


class DraftListDetailsTests(unittest.TestCase):
    def test_details_show_size_and_mode(self):
        self.assertEqual(draft_details({"map_w": 125, "map_h": 125, "mode": "tower"}), "125×125 · Башня")

    def test_missing_mode_and_size_do_not_break_the_row(self):
        self.assertEqual(draft_details({"map_w": 64, "map_h": 64}), "64×64 · Башня")
        self.assertEqual(draft_details({}), "Башня")

    def test_list_draws_drafts_with_details(self):
        pygame.init()
        screen = pygame.display.set_mode((1920, 1080))
        drafts = [{"id": "a", "name": "Карта" * 20, "map_w": 512, "map_h": 256, "mode": "tower",
                   "updated_at": 1.0, "active_worlds": ["Башня"]}]
        font = pygame.font.SysFont("arial", 16)
        DraftList(font, font, drafts).draw(screen)


class MapEditorMobTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1920, 1080))

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        patcher = patch.object(mob_modes, "MODES_DIR", self.folder)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.scene = MapEditorScene(None, catalog_definitions(), lambda: False)
        self.scene.has_map = True
        self.scene._set_section("npc")

    def down(self, pos, button=1):
        self.scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=button, pos=pos))

    def move(self, pos):
        self.scene.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)))

    def open_dialog(self, row=1):
        rect = self.scene._npc_row_rect(row)
        self.move(rect.center)
        self.down(self.scene._npc_card_button(self.scene._npc_card_rect()).center)
        return self.scene.mob_dialog

    def test_size_picker_returns_the_chosen_mode(self):
        picker = SizePicker(self.scene.font, self.scene.small, modes=GAME_MODES)
        self.assertEqual((picker.width, picker.height), (64, 64))
        rects = [picker._mode_rect(index) for index in range(len(GAME_MODES))]
        self.assertEqual(len(rects), len({rect.x for rect in rects}))
        self.assertTrue(all(picker.box().contains(rect) for rect in rects))
        self.assertTrue(all(
            self.scene.font.size(mode["name"])[0] <= rect.w - 8
            for mode, rect in zip(GAME_MODES, rects)
        ))
        economy_index = next(
            index for index, mode in enumerate(GAME_MODES)
            if mode["key"] == "economy"
        )
        self.assertIsNone(picker.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=picker._mode_rect(economy_index).center,
        )))
        for _ in range(3):
            picker.handle_event(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                button=1,
                pos=picker._dimension_button_rect("width", 1).center,
            ))
        picker.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=picker._dimension_button_rect("height", 1).center,
        ))
        self.assertEqual((picker.width, picker.height), (512, 128))
        picker.draw(pygame.display.get_surface())
        self.assertEqual(
            picker.handle_event(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                button=1,
                pos=picker._create_rect().center,
            )),
            (512, 128, "economy"),
        )

    def test_map_dimensions_follow_steps_and_stop_at_1600(self):
        picker = SizePicker(self.scene.font, self.scene.small, modes=GAME_MODES)
        for _ in range(20):
            picker.handle_event(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                button=1,
                pos=picker._dimension_button_rect("width", 1).center,
            ))
        self.assertEqual(picker.width, 1600)
        picker.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=picker._dimension_button_rect("width", 1).center,
        ))
        self.assertEqual(picker.width, 1600)
        for _ in range(20):
            picker.handle_event(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                button=1,
                pos=picker._dimension_button_rect("height", -1).center,
            ))
        self.assertEqual(picker.height, 64)

    def test_new_map_sets_the_mode(self):
        self.scene.new_map()
        self.down(self.scene.size_picker._create_rect().center)
        self.assertEqual(self.scene.mode, "tower")
        self.assertEqual(
            (self.scene.state.map_w, self.scene.state.map_h),
            (64, 64),
        )
        self.assertIsNone(self.scene.size_picker)

    def test_new_map_sets_deck_and_economy_modes(self):
        for mode_key in ("deck", "economy"):
            with self.subTest(mode=mode_key):
                self.scene.has_map = False
                self.scene.new_map()
                mode_index = next(
                    index for index, mode in enumerate(GAME_MODES)
                    if mode["key"] == mode_key
                )
                self.down(self.scene.size_picker._mode_rect(mode_index).center)
                self.down(self.scene.size_picker._create_rect().center)
                self.assertEqual(self.scene.mode, mode_key)
                if mode_key == "economy":
                    self.assertIn("заглушка", self.scene.status.lower())
                else:
                    self.assertIn("оператор 2", self.scene.status.lower())

    def test_saved_draft_remembers_the_mode(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(map_drafts, "DRAFTS_DIR", Path(folder)):
            saved = map_drafts.save_draft("Карта", [], 16, 16, folder=Path(folder), mode="tower")
            with patch.object(map_drafts, "load_draft", return_value={**saved, "cells": []}):
                self.scene._open_draft(saved["id"])
            self.assertEqual(self.scene.mode, "tower")

    def test_card_appears_on_hover_and_survives_the_gap(self):
        row = self.scene._npc_row_rect(2)
        self.move(row.center)
        self.assertEqual(self.scene.npc_card, "imp_pitchfork")
        card = self.scene._npc_card_rect()
        self.move((row.right + 2, row.centery))
        self.assertEqual(self.scene.npc_card, "imp_pitchfork")
        self.move(card.center)
        self.assertEqual(self.scene.npc_card, "imp_pitchfork")
        self.move((1700, 900))
        self.assertIsNone(self.scene.npc_card)

    def test_button_opens_dialog_and_card_swallows_clicks(self):
        self.move(self.scene._npc_row_rect(1).center)
        card = self.scene._npc_card_rect()
        self.down((card.x + 5, card.y + 5))  # пустое место карточки не рисует на карте
        self.assertIsNone(self.scene.mob_dialog)
        self.down(self.scene._npc_card_button(card).center)
        self.assertIsNotNone(self.scene.mob_dialog)
        self.assertIsNone(self.scene.npc_card)

    def test_dialog_edits_are_saved_to_the_mode_file(self):
        dialog = self.open_dialog()
        self.down(dialog._field_rects(1)[2].center)  # замах +0.05
        self.down(dialog._state_rect(2).center)  # дружественный
        self.down(dialog._preset_rect(0).center)  # очистить патруль
        gx, gy = dialog._grid_origin()
        self.down((gx + 9 * 24 + 4, gy + 9 * 24 + 4))
        self.scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(0, 0)))
        self.down(dialog._save_rect().center)
        self.assertIsNone(self.scene.mob_dialog)
        saved = mob_modes.load_mob_settings("tower", "imp_sword", self.folder)
        self.assertEqual((saved["windup"], saved["state"], saved["patrol"]), (0.49, "friendly", [[0, 0]]))
        self.assertEqual(self.scene._mob_settings("imp_sword")["state"], "friendly")

    def test_cancel_and_escape_change_nothing(self):
        dialog = self.open_dialog()
        self.down(dialog._state_rect(1).center)
        self.down(dialog._cancel_rect().center)
        self.assertIsNone(self.scene.mob_dialog)
        dialog = self.open_dialog()
        self.scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode=""))
        self.assertIsNone(self.scene.mob_dialog)
        self.assertFalse((self.folder / "tower.json").exists())

    def test_invalid_values_keep_the_dialog_open_with_a_message(self):
        dialog = self.open_dialog()
        dialog.values["move_speed"] = 100000.0
        self.down(dialog._save_rect().center)
        self.assertIs(self.scene.mob_dialog, dialog)
        self.assertIn("move_speed", dialog.message)

    def test_steppers_stay_inside_limits(self):
        dialog = self.open_dialog()
        for _ in range(200):
            self.down(dialog._field_rects(3)[0].center)  # агрессия −
        self.assertEqual(dialog.values["aggro_tiles"], 0.0)
        for _ in range(200):
            self.down(dialog._stat_rects(0)[2].center)  # сила +: не больше, чем есть свободных очков
        self.assertEqual(mob_modes.free_points(dialog.level, dialog.stats), 0)
        for _ in range(200):
            self.down(dialog._stat_rects(0)[0].center)  # сила −: не ниже базы
        self.assertEqual(dialog.stats["strength"], mob_modes.STAT_MIN)

    def test_level_up_gives_endurance_and_points(self):
        dialog = self.open_dialog()
        self.assertEqual((dialog.level, dialog.stats["endurance"], mob_modes.free_points(1, dialog.stats)), (1, 4, 0))
        self.down(dialog._level_rects()[2].center)  # уровень +
        self.assertEqual((dialog.level, dialog.stats["endurance"], mob_modes.free_points(2, dialog.stats)), (2, 5, 3))
        self.down(dialog._stat_rects(1)[2].center)  # ловкость +
        self.assertEqual(dialog.stats["agility"], 5)

    def test_level_down_takes_back_extra_points(self):
        dialog = self.open_dialog()
        for _ in range(2):
            self.down(dialog._level_rects()[2].center)  # уровень 3: 9 очков
        for _ in range(5):
            self.down(dialog._stat_rects(3)[2].center)  # мудрость +5
        self.down(dialog._level_rects()[0].center)  # уровень 2: доступно 6, вложено было 8
        self.assertEqual(dialog.level, 2)
        self.assertGreaterEqual(mob_modes.free_points(2, dialog.stats), 0)
        self.assertEqual(dialog.stats["endurance"], 5)

    def test_endurance_is_not_adjustable(self):
        dialog = self.open_dialog()
        self.down(dialog._level_rects()[2].center)
        before = dialog.stats["endurance"]
        self.down(dialog._stat_rects(5)[2].center)
        self.down(dialog._stat_rects(5)[0].center)
        self.assertEqual(dialog.stats["endurance"], before)

    def test_level_is_saved_with_the_settings(self):
        dialog = self.open_dialog()
        self.down(dialog._level_rects()[2].center)
        self.down(dialog._save_rect().center)
        saved = mob_modes.load_mob_settings("tower", "imp_sword", self.folder)
        self.assertEqual((saved["level"], saved["stats"]["endurance"]), (2, 5))

    def test_level_limits(self):
        dialog = self.open_dialog()
        for _ in range(100):
            self.down(dialog._level_rects()[2].center)
        self.assertEqual(dialog.level, mob_modes.LEVEL_CAP)
        for _ in range(100):
            self.down(dialog._level_rects()[0].center)
        self.assertEqual(dialog.level, mob_modes.LEVEL_MIN)
        self.assertEqual(mob_modes.free_points(1, dialog.stats), 0)

    def test_patrol_paint_and_erase(self):
        dialog = self.open_dialog()
        self.down(dialog._preset_rect(0).center)
        gx, gy = dialog._grid_origin()
        self.down((gx + 3 * 24 + 4, gy + 4 * 24 + 4))
        self.assertEqual(dialog.patrol, {(3, 4)})
        self.scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(0, 0)))
        self.down((gx + 3 * 24 + 4, gy + 4 * 24 + 4), button=3)
        self.assertEqual(dialog.patrol, set())

    def test_draw_with_card_and_dialog(self):
        screen = pygame.display.get_surface()
        self.move(self.scene._npc_row_rect(0).center)
        self.scene.draw(screen)
        self.open_dialog(0)
        self.scene.draw(screen)


if __name__ == "__main__":
    unittest.main()
