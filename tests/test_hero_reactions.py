import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from core import settings
from scenes.player_sprites import (
    PLAYER_DIRECTIONS,
    WARRIOR_ATTACK_ANIMATIONS,
    WARRIOR_REACTION_ANIMATIONS,
    load_warrior_directional_frames,
    player_anim_state,
    player_frame,
)
from tests.test_dash import make_snapshot


def _warrior():
    return {"type": "warrior", "stats": {"strength": 10, "endurance": 10}, "carried_weight_kg": 0}


class HeroReactionFramesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    def test_hit_and_death_cover_all_directions(self):
        frames = load_warrior_directional_frames()
        expected = {"gothit": 6, "death": 8}
        for anim in WARRIOR_REACTION_ANIMATIONS:
            for direction in PLAYER_DIRECTIONS:
                self.assertEqual(len(frames[anim][direction]), expected[anim], (anim, direction))

    def test_reactions_share_the_wide_canvas_with_attacks(self):
        frames = load_warrior_directional_frames()
        sizes = {
            frames[anim][d][0].get_size()
            for anim in WARRIOR_ATTACK_ANIMATIONS + WARRIOR_REACTION_ANIMATIONS
            for d in PLAYER_DIRECTIONS
        }
        self.assertEqual(len(sizes), 1, sizes)

    def test_hit_and_death_follow_progress_and_death_holds_the_last_frame(self):
        frames = load_warrior_directional_frames()
        scene = SimpleNamespace()
        hero = _warrior()
        first = player_frame(scene, hero, "s", 0.0, moving=False, hit_progress=0.0)
        last = player_frame(scene, hero, "s", 0.0, moving=False, hit_progress=1.0)
        self.assertIs(first, frames["gothit"]["s"][0])
        self.assertIs(last, frames["gothit"]["s"][-1])
        start = player_frame(scene, hero, "e", 0.0, moving=False, death_progress=0.0)
        end = player_frame(scene, hero, "e", 0.0, moving=False, death_progress=1.0)
        self.assertIs(start, frames["death"]["e"][0])
        self.assertIs(end, frames["death"]["e"][-1])
        beyond = player_frame(scene, hero, "e", 0.0, moving=False, death_progress=5.0)
        self.assertIs(beyond, end)

    def test_priority_is_death_then_hit_then_attack(self):
        hero = _warrior()
        self.assertEqual(player_anim_state(hero, True, attacking=True, hit=True, dead=True), "death")
        self.assertEqual(player_anim_state(hero, True, attacking=True, hit=True), "gothit")
        self.assertEqual(player_anim_state(hero, True, attacking=True), "attack")
        self.assertEqual(player_anim_state(hero, False), "idle")

    def test_other_professions_have_no_hit_or_death_states(self):
        mage = {"type": "mage"}
        self.assertEqual(player_anim_state(mage, False, hit=True, dead=True), "idle")
        self.assertEqual(player_anim_state(mage, True, hit=True), "run")


class HeroReactionSceneTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
        from scenes.world_map_scene import HERO_DEATH_SECONDS, HERO_HIT_SECONDS, WorldMapScene

        self.hit_seconds, self.death_seconds = HERO_HIT_SECONDS, HERO_DEATH_SECONDS
        self.server_hp = 50

        def world_sync(*args):
            snap = make_snapshot()
            snap["player"]["hp"] = self.server_hp
            return snap

        client = SimpleNamespace(world_sync=world_sync)
        self.scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т", "type": "warrior"}, client=client))

    def tearDown(self):
        pygame.quit()

    def test_first_snapshot_only_sets_the_baseline(self):
        self.scene._track_player_hp(30)
        self.assertEqual(self.scene.hit_timer, 0.0)
        self.assertIsNone(self.scene.death_timer)

    def test_losing_health_starts_the_hit_animation(self):
        self.scene._track_player_hp(100)
        self.scene._track_player_hp(70)
        self.assertEqual(self.scene.hit_timer, self.hit_seconds)
        self.assertEqual(self.scene._hero_reaction_progress(), (0.0, None))
        self.scene.hit_timer = self.hit_seconds / 2
        self.assertAlmostEqual(self.scene._hero_reaction_progress()[0], 0.5)

    def test_regeneration_does_not_start_a_hit(self):
        self.scene._track_player_hp(50)
        self.scene._track_player_hp(53)
        self.assertEqual(self.scene.hit_timer, 0.0)

    def test_zero_health_starts_death_and_revival_ends_it(self):
        self.scene._track_player_hp(20)
        self.scene._track_player_hp(0)
        self.assertEqual(self.scene.death_timer, 0.0)
        self.assertEqual(self.scene.hit_timer, 0.0)
        self.scene.death_timer = self.death_seconds * 3
        self.assertEqual(self.scene._hero_reaction_progress()[1], 1.0)
        self.scene._track_player_hp(0)
        self.assertEqual(self.scene.death_timer, self.death_seconds * 3)  # уже мёртв: смерть не перезапускается
        self.scene._track_player_hp(4)
        self.assertIsNone(self.scene.death_timer)

    def test_snapshot_with_lower_health_triggers_the_hit(self):
        self.scene._apply_world_snapshot(make_snapshot())  # hp 50: точка отсчёта
        snap = make_snapshot()
        snap["player"]["hp"] = 35
        self.scene._apply_world_snapshot(snap)
        self.assertEqual(self.scene.hit_timer, self.hit_seconds)
        snap["player"]["hp"] = 0
        self.scene._apply_world_snapshot(snap)
        self.assertEqual(self.scene.death_timer, 0.0)

    def test_timers_run_in_update_and_the_scene_draws_every_state(self):
        screen = pygame.display.get_surface()
        self.scene._track_player_hp(50)
        self.server_hp = 30
        self.scene._track_player_hp(30)
        self.scene.update(0.1)
        self.assertAlmostEqual(self.scene.hit_timer, self.hit_seconds - 0.1)
        self.scene.draw(screen)
        self.server_hp = 0
        self.scene._track_player_hp(0)
        self.scene.update(0.2)
        self.assertAlmostEqual(self.scene.death_timer, 0.2)
        self.scene.draw(screen)


if __name__ == "__main__":
    unittest.main()
