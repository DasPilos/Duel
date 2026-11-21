import math
import os
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from core.npc_catalog import NPC_FRAME, NPC_FRAMES_PER_ROW, NPC_ROW_DOWN, NPC_ROW_LEFT, NPC_ROW_RIGHT, NPC_ROW_UP, npc_catalog, sheet_path
from scenes.world_map_scene import (
    MOB_CORPSE_FALL_MS,
    MOB_CORPSE_FADE_MS,
    MOB_CORPSE_HOLD_MS,
    MOB_WALK_FPS,
    MOB_WALK_HOLD_MS,
    MOB_RENDER_FIGURE_HEIGHT,
    MOB_RENDER_FEET_Y,
    MOB_RENDER_FRAME_SIZE,
    WorldMapScene,
    _mob_display_frame,
    _normalize_mob_frames,
    _mob_facing_row,
    mob_death_frame,
    mob_frame,
)


class MobFacingRowTests(unittest.TestCase):
    def test_angles_map_to_sheet_rows(self):
        self.assertEqual(_mob_facing_row(0.0), NPC_ROW_RIGHT)
        self.assertEqual(_mob_facing_row(math.pi), NPC_ROW_LEFT)
        self.assertEqual(_mob_facing_row(math.pi / 2), NPC_ROW_DOWN)
        self.assertEqual(_mob_facing_row(-math.pi / 2), NPC_ROW_UP)


class MobFrameTests(unittest.TestCase):
    def setUp(self):
        self.frames = {row: [f"walk-{row}-{col}" for col in range(NPC_FRAMES_PER_ROW)] for row in range(4)}
        self.attack = {row: [f"attack-{row}-{col}" for col in range(NPC_FRAMES_PER_ROW)] for row in range(4)}

    def mob(self, moved_at=None, facing=0.0):
        mob = {"frames": self.frames, "attack_frames": self.attack, "facing": facing}
        if moved_at is not None:
            mob["moved_at"] = moved_at
        return mob

    def test_standing_mob_shows_first_frame_of_facing_row(self):
        self.assertEqual(mob_frame(self.mob(moved_at=0, facing=math.pi / 2), 5000), f"walk-{NPC_ROW_DOWN}-0")

    def test_moving_mob_cycles_through_frames(self):
        mob = self.mob(facing=-math.pi / 2)
        seen = set()
        for i in range(NPC_FRAMES_PER_ROW):
            now = 1000 + i * 1000 // MOB_WALK_FPS
            mob["moved_at"] = now  # позиция меняется на каждом кадре
            seen.add(mob_frame(mob, now))
        self.assertEqual(seen, {f"walk-{NPC_ROW_UP}-{col}" for col in range(NPC_FRAMES_PER_ROW)})

    def test_animation_stops_after_hold_time(self):
        mob = self.mob(moved_at=1000, facing=0.0)
        self.assertEqual(mob_frame(mob, 1000 + MOB_WALK_HOLD_MS + 1), f"walk-{NPC_ROW_RIGHT}-0")

    def test_attack_plays_attack_sheet_during_windup(self):
        mob = self.mob(facing=0.0)
        mob.update({"windup": 0.5, "attack_started": 1000, "attack_ms": 500})
        seen = [mob_frame(mob, 1000 + step * 125) for step in range(NPC_FRAMES_PER_ROW)]
        self.assertEqual(seen, [f"attack-{NPC_ROW_RIGHT}-{col}" for col in range(NPC_FRAMES_PER_ROW)])

    def test_mob_without_frames_has_no_frame(self):
        self.assertIsNone(mob_frame({"sprite": object()}, 1000))

    def test_regular_mobs_fit_half_a_tile_and_bosses_are_four_times_as_large(self):
        pygame.init()
        try:
            oversized = pygame.Surface((128, 96), pygame.SRCALPHA)
            self.assertEqual(_mob_display_frame({}, oversized).get_size(), (16, 12))
            self.assertEqual(_mob_display_frame({"is_boss": True}, oversized).get_size(), (64, 48))
        finally:
            pygame.quit()

    def test_giant_rat_palette_frame_is_reduced_to_half_a_tile(self):
        pygame.init()
        try:
            path = (
                Path(__file__).resolve().parents[1]
                / "godot_client"
                / "assets"
                / "base_tails"
                / "LPC"
                / "craftpix-net-415491-giant-rat-4-direction-pixel-character-sprite-pack"
                / "Tiled"
                / "Rat1_Walk_with_shadow.png"
            )
            sheet = pygame.image.load(str(path))
            frame_size = sheet.get_height() // 4
            frame = None
            for y in range(0, sheet.get_height(), frame_size):
                for x in range(0, sheet.get_width(), frame_size):
                    candidate = sheet.subsurface(pygame.Rect(x, y, frame_size, frame_size)).copy()
                    if candidate.get_bounding_rect(min_alpha=1).height > 0:
                        frame = candidate
                        break
                if frame is not None:
                    break
            self.assertIsNotNone(frame)
            normalized = _normalize_mob_frames({0: [frame]})[0][0]
            visible = normalized.get_bounding_rect(min_alpha=1)
            self.assertGreater(visible.height, 0)
            self.assertLessEqual(max(visible.size), MOB_RENDER_FRAME_SIZE)
            self.assertEqual(
                _mob_display_frame({"is_boss": True}, normalized).get_size(),
                (MOB_RENDER_FRAME_SIZE * 4, MOB_RENDER_FRAME_SIZE * 4),
            )
        finally:
            pygame.quit()


class MobDeathFrameTests(unittest.TestCase):
    def setUp(self):
        self.frame = pygame.Surface((77, 77), pygame.SRCALPHA)
        self.frame.fill((200, 50, 50, 255))
        self.last = pygame.Surface((77, 77), pygame.SRCALPHA)
        self.last.fill((50, 50, 200, 255))
        self.mob = {"death_frames": [self.frame, self.last], "died_at": 1000}

    def test_death_sheet_plays_then_holds_last_frame(self):
        self.assertIs(mob_death_frame(self.mob, 1000), self.frame)
        self.assertIs(mob_death_frame(self.mob, 1000 + 1000), self.last)
        self.assertIs(mob_death_frame(self.mob, 1000 + MOB_CORPSE_HOLD_MS), self.last)

    def test_corpse_fades_and_disappears_without_touching_shared_frames(self):
        mid = mob_death_frame(self.mob, 1000 + MOB_CORPSE_HOLD_MS + MOB_CORPSE_FADE_MS // 2)
        self.assertLess(mid.get_alpha(), 255)
        self.assertGreater(mid.get_alpha(), 0)
        self.assertEqual(self.last.get_alpha(), 255)
        self.assertIsNone(mob_death_frame(self.mob, 1000 + MOB_CORPSE_HOLD_MS + MOB_CORPSE_FADE_MS))

    def test_mob_without_death_sheet_falls_on_its_side(self):
        self.mob["death_frames"] = None
        self.mob["frames"] = {NPC_ROW_DOWN: [self.frame] * NPC_FRAMES_PER_ROW}
        self.mob["facing"] = math.pi / 2
        self.assertIsNotNone(mob_death_frame(self.mob, 1000 + MOB_CORPSE_FALL_MS))

    def test_mob_without_death_time_has_no_body(self):
        self.mob.pop("died_at")
        self.assertIsNone(mob_death_frame(self.mob, 1000))

    def test_mob_without_death_time_has_no_body(self):
        self.mob.pop("died_at")
        self.assertIsNone(mob_death_frame(self.mob, 1000))


class ImpWalkSheetTests(unittest.TestCase):
    def _set_player_offscreen(self, scene):
        scene.player_x = 500
        scene.player_y = 500
        scene.session = type("Session", (), {"character": None})()
        scene._player_character_frame = lambda _character: None
        scene._draw_player_character = mock.Mock()

    def test_every_imp_has_full_walk_and_attack_sheets(self):
        pygame.init()
        try:
            for npc in npc_catalog():
                for action in ("walk", "attack"):
                    path = sheet_path(npc, action)
                    self.assertTrue(path.is_file(), path)
                    sheet = pygame.image.load(str(path))
                    self.assertEqual(sheet.get_size(), (NPC_FRAME * NPC_FRAMES_PER_ROW, NPC_FRAME * 4), path)
        finally:
            pygame.quit()

    def test_all_walk_directions_have_a_shared_visible_height_and_foot_anchor(self):
        pygame.init()
        try:
            for npc in npc_catalog():
                sheet = pygame.image.load(str(sheet_path(npc, "walk")))
                frames = {
                    row: [
                        sheet.subsurface(pygame.Rect(
                            column * NPC_FRAME, row * NPC_FRAME, NPC_FRAME, NPC_FRAME,
                        )).copy()
                        for column in range(NPC_FRAMES_PER_ROW)
                    ]
                    for row in range(4)
                }
                normalized = _normalize_mob_frames(frames)
                with self.subTest(npc=npc["key"]):
                    for row in range(4):
                        for frame in normalized[row]:
                            bounds = frame.get_bounding_rect(min_alpha=1)
                            self.assertEqual(frame.get_size(), (MOB_RENDER_FRAME_SIZE, MOB_RENDER_FRAME_SIZE))
                            self.assertLessEqual(bounds.width, MOB_RENDER_FRAME_SIZE)
                            self.assertLessEqual(bounds.height, MOB_RENDER_FIGURE_HEIGHT)
                            self.assertEqual(bounds.bottom, MOB_RENDER_FEET_Y)
        finally:
            pygame.quit()

    def test_mobs_are_drawn_behind_only_foreground_overlapping_trees(self):
        pygame.init()
        scene = object.__new__(WorldMapScene)
        scene.animals = {}
        scene.active_entity = None
        scene.hovered_entity = None
        self._set_player_offscreen(scene)
        tree = pygame.Surface((30, 30))
        tree.fill((0, 200, 0))
        mob_sprite = pygame.Surface((20, 20))
        mob_sprite.fill((200, 0, 0))
        scene.world_to_screen = lambda x, y: (int(x), int(y))
        screen = pygame.Surface((100, 100))

        for mob_y, sample, expected in (
            (40, (50, 40), (0, 200, 0)),
            (50, (50, 45), (0, 200, 0)),
            (60, (50, 60), (200, 0, 0)),
        ):
            screen.fill((0, 0, 0))
            scene.mobs = [{"id": "test", "hp": 0, "x": 50, "y": mob_y}]
            with mock.patch("scenes.world_map_scene.mob_death_frame", return_value=mob_sprite):
                scene._draw_mobs(screen, ((55, 50, tree),))
            self.assertEqual(screen.get_at(sample)[:3], expected)

    def test_animals_are_drawn_behind_only_foreground_overlapping_trees(self):
        pygame.init()
        scene = object.__new__(WorldMapScene)
        scene.mobs = []
        scene.animals = {}
        scene.active_entity = None
        scene.hovered_entity = None
        self._set_player_offscreen(scene)
        tree = pygame.Surface((30, 30))
        tree.fill((0, 200, 0))
        animal_sprite = pygame.Surface((20, 20))
        animal_sprite.fill((200, 0, 0))
        scene.world_to_screen = lambda x, y: (int(x), int(y))
        scene._animal_frame_for = lambda *_args: animal_sprite
        screen = pygame.Surface((100, 100))

        for animal_y, sample, expected in (
            (40, (50, 30), (0, 200, 0)),
            (50, (50, 35), (0, 200, 0)),
            (60, (50, 45), (200, 0, 0)),
        ):
            screen.fill((0, 0, 0))
            scene.animals = {
                "test": {"key": "animal_duck", "x": 50, "y": animal_y, "moving": True},
            }
            scene._draw_mobs(screen, ((55, 50, tree),))
            self.assertEqual(screen.get_at(sample)[:3], expected)

    def test_hero_is_drawn_with_trees_at_the_same_depth(self):
        pygame.init()
        scene = object.__new__(WorldMapScene)
        scene.mobs = []
        scene.animals = {}
        scene.active_entity = None
        scene.hovered_entity = None
        scene.session = type("Session", (), {"character": None})()
        scene.world_to_screen = lambda x, y: (int(x), int(y))
        hero_sprite = pygame.Surface((20, 20))
        hero_sprite.fill((200, 0, 0))
        scene._player_character_frame = lambda _character: hero_sprite
        scene._draw_player_character = lambda target, sprite: target.blit(
            sprite, sprite.get_rect(midbottom=(scene.player_x, scene.player_y)),
        )
        tree = pygame.Surface((30, 30))
        tree.fill((0, 200, 0))
        screen = pygame.Surface((100, 100))

        for hero_y, sample, expected in (
            (40, (50, 30), (0, 200, 0)),
            (50, (50, 40), (0, 200, 0)),
            (60, (50, 45), (200, 0, 0)),
        ):
            screen.fill((0, 0, 0))
            scene.player_x = 50
            scene.player_y = hero_y
            scene._draw_mobs(screen, ((55, 50, tree),))
            self.assertEqual(screen.get_at(sample)[:3], expected)


if __name__ == "__main__":
    unittest.main()
