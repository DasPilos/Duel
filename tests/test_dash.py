import random
import unittest
from types import SimpleNamespace

import pygame

from combat.dash import (
    DASH_COOLDOWN,
    DASH_DAMAGE_MAX,
    DASH_DAMAGE_MIN,
    DASH_RANGE,
    dash_damage_roll,
    dash_end_point,
    point_segment_distance,
)
from core import settings


class DashMathTests(unittest.TestCase):
    def test_target_inside_range_still_flies_full_range_in_its_direction(self):
        end = dash_end_point((0, 0), (100, 0))
        self.assertAlmostEqual(end[0], DASH_RANGE)
        self.assertAlmostEqual(end[1], 0.0)

    def test_target_beyond_range_is_clamped_on_the_same_line(self):
        end = dash_end_point((0, 0), (500, 0))
        self.assertAlmostEqual(end[0], DASH_RANGE)
        self.assertAlmostEqual(end[1], 0.0)

    def test_diagonal_clamp_keeps_direction(self):
        end = dash_end_point((0, 0), (300, 400))
        self.assertAlmostEqual((end[0] ** 2 + end[1] ** 2) ** 0.5, DASH_RANGE)
        self.assertAlmostEqual(end[0] / end[1], 300 / 400)

    def test_point_segment_distance_perpendicular_and_past_ends(self):
        self.assertAlmostEqual(point_segment_distance((50, 30), (0, 0), (100, 0)), 30.0)
        self.assertAlmostEqual(point_segment_distance((130, 40), (0, 0), (100, 0)), 50.0)
        self.assertAlmostEqual(point_segment_distance((-30, 40), (0, 0), (100, 0)), 50.0)

    def test_zero_length_segment_is_a_point(self):
        self.assertAlmostEqual(point_segment_distance((3, 4), (0, 0), (0, 0)), 5.0)

    def test_damage_roll_stays_in_12_to_18(self):
        rng = random.Random(7)
        rolls = [dash_damage_roll(rng) for _ in range(500)]
        self.assertGreaterEqual(min(rolls), DASH_DAMAGE_MIN)
        self.assertLessEqual(max(rolls), DASH_DAMAGE_MAX)
        self.assertEqual(DASH_DAMAGE_MIN, 12)
        self.assertEqual(DASH_DAMAGE_MAX, 18)


def make_snapshot(seq=1, x=1000.0, y=1000.0, accepted=True, dash_active=False, dash_cooldown=0.0, trails=(), mobs=(), events=()):
    return {
        "seq": seq,
        "accepted": accepted,
        "player": {
            "x": x, "y": y, "hp": 50, "max_hp": 50, "mp": 10, "max_mp": 10, "facing": "s",
            "windup": 0.0, "windup_total": 0.0, "swing_id": 0, "backswing": 0.0,
            "attack_target": None, "windup_target": None, "dash_active": dash_active,
            "dash_cooldown": dash_cooldown, "reach": 60, "move_speed": 200, "carry_multiplier": 1.0,
        },
        "mobs": list(mobs),
        "trails": list(trails),
        "events": list(events),
    }


class FakeWorldClient:
    """Сервер мира: эхо позиции клиента, если не задано иное через reply."""

    def __init__(self):
        self.calls = []
        self.reply = {}

    def world_sync(self, character_id, x, y, attack_id, dash_target, since):
        self.calls.append({"x": x, "y": y, "attack_id": attack_id, "dash_target": dash_target})
        return make_snapshot(seq=len(self.calls), **{"x": x, "y": y, **self.reply})


class DashSceneTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
        from scenes.world_map_scene import WorldMapScene

        self.client = FakeWorldClient()
        self.scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=self.client))
        self.scene.player_x, self.scene.player_y = 1000.0, 1000.0

    def tearDown(self):
        pygame.quit()

    def test_digit_one_toggles_aim_and_escape_cancels(self):
        self.scene._press_hotbar_slot(0)
        self.assertTrue(self.scene.dash_aiming)
        self.scene._press_hotbar_slot(0)
        self.assertFalse(self.scene.dash_aiming)
        self.scene._press_hotbar_slot(0)
        self.scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="", scancode=0))
        self.assertFalse(self.scene.dash_aiming)

    def test_other_digits_do_not_start_aim(self):
        self.scene._press_hotbar_slot(4)
        self.assertFalse(self.scene.dash_aiming)

    def test_fire_sends_dash_direction_to_server_and_clears_attack_target(self):
        self.scene._press_hotbar_slot(0)
        self.scene._fire_dash((1500.0, 1000.0))
        self.assertFalse(self.scene.dash_aiming)
        self.assertEqual(self.client.calls[-1]["dash_target"], {"x": 1500.0, "y": 1000.0})
        self.assertIsNone(self.scene.attack_target)

    def test_too_short_dash_is_not_sent(self):
        self.scene._fire_dash((1002.0, 1000.0))
        self.assertEqual(self.client.calls, [])

    def test_server_cooldown_blocks_next_dash_aim(self):
        self.client.reply = {"dash_cooldown": 40.0}
        self.scene._fire_dash((1500.0, 1000.0))
        self.assertEqual(self.scene.dash_cooldown, 40.0)
        self.scene._press_hotbar_slot(0)
        self.assertFalse(self.scene.dash_aiming)

    def test_snapshot_adopts_server_position_during_dash(self):
        self.client.reply = {"x": 1200.0, "y": 1000.0, "dash_active": True}
        self.scene._world_sync_request(0.0, force=True)
        self.assertTrue(self.scene.world_dash_active)
        self.assertEqual((self.scene.player_x, self.scene.player_y), (1200.0, 1000.0))

    def test_rejected_move_snaps_player_to_server_position(self):
        self.client.reply = {"x": 900.0, "y": 1000.0, "accepted": False}
        self.scene._world_sync_request(0.0, force=True)
        self.assertEqual(self.scene.player_x, 900.0)

    def test_trail_timer_comes_from_server_ttl_and_expires(self):
        self.client.reply = {"trails": [{"x": 1100.0, "y": 1000.0, "ttl": 5.0}]}
        self.scene._world_sync_request(0.0, force=True)
        self.assertEqual(self.scene.whirlwinds, [{"x": 1100.0, "y": 1000.0, "timer": 5.0}])
        self.client.reply = {"trails": []}
        self.scene._world_sync_request(0.0, force=True)
        self.assertEqual(self.scene.whirlwinds, [])

    def test_hotbar_slot_state_reports_cooldown_and_aim(self):
        self.scene.dash_cooldown = 12.0
        self.scene.dash_aiming = True
        state = self.scene._hotbar_slot_states()[0]
        self.assertEqual(state["name"], "Рывок")
        self.assertEqual(state["cooldown"], 12.0)
        self.assertEqual(state["cooldown_total"], DASH_COOLDOWN)
        self.assertTrue(state["active"])

    def test_draw_with_aim_trail_and_cooldown_does_not_fail(self):
        self.scene.dash_aiming = True
        self.scene.dash_cooldown = 10.0
        self.scene.whirlwinds = [{"x": 1100.0, "y": 1000.0, "timer": 3.0}]
        self.scene.draw(pygame.display.get_surface())


if __name__ == "__main__":
    unittest.main()