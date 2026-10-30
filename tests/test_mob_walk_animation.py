import math
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from core.npc_catalog import NPC_FRAME, NPC_FRAMES_PER_ROW, NPC_ROW_DOWN, NPC_ROW_LEFT, NPC_ROW_RIGHT, NPC_ROW_UP, npc_catalog, sheet_path
from scenes.world_map_scene import (
    MOB_CORPSE_FALL_MS,
    MOB_CORPSE_FADE_MS,
    MOB_CORPSE_HOLD_MS,
    MOB_WALK_FPS,
    MOB_WALK_HOLD_MS,
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


if __name__ == "__main__":
    unittest.main()
