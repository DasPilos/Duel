import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pygame

from core import settings
from ui import sfx


class FakeWorldClient:
    """Сервер мира: отдаёт снимок с позицией клиента и текущими полями игрока."""

    def __init__(self):
        self.seq = 0
        self.player = {
            "x": 1000.0, "y": 1000.0, "hp": 50, "max_hp": 50, "mp": 10, "max_mp": 10, "facing": "s",
            "windup": 0.0, "windup_total": 0.0, "swing_id": 0, "backswing": 0.0,
            "attack_target": None, "windup_target": None, "dash_active": False,
            "dash_cooldown": 0.0, "reach": 60, "move_speed": 200, "carry_multiplier": 1.0,
        }

    def world_sync(self, character_id, x, y, attack_id, dash_target, since):
        self.seq += 1
        return {"seq": self.seq, "accepted": True, "player": dict(self.player, x=x, y=y),
                "mobs": [], "trails": [], "events": []}


class SwingSoundTests(unittest.TestCase):
    def test_sword_club_and_hammer_get_their_own_sound_sets(self):
        self.assertEqual(sfx.swing_sounds_for_weapon({"name": "Железный меч"}), sfx.SWORD_SWING_SOUNDS)
        self.assertEqual(sfx.swing_sounds_for_weapon({"name": "Стальной меч"}), sfx.SWORD_SWING_SOUNDS)
        self.assertEqual(sfx.swing_sounds_for_weapon({"name": "Дубина"}), sfx.CLUB_SWING_SOUNDS)
        self.assertEqual(sfx.swing_sounds_for_weapon({"name": "Боевой молот"}), sfx.CLUB_SWING_SOUNDS)
        self.assertEqual(sfx.swing_sounds_for_weapon({"name": "Кинжал"}), sfx.KNIFE_SWING_SOUNDS)
        self.assertEqual(sfx.swing_sounds_for_weapon({"name": "Стальной нож"}), sfx.KNIFE_SWING_SOUNDS)
        self.assertEqual(sfx.swing_sounds_for_weapon({"name": "Простой лук"}), ())
        self.assertEqual(sfx.swing_sounds_for_weapon(None), ())

    def test_sword_sound_files_exist(self):
        for name in sfx.SWORD_SWING_SOUNDS + sfx.CLUB_SWING_SOUNDS + sfx.KNIFE_SWING_SOUNDS:
            self.assertTrue((sfx.SFX_DIR / name).is_file(), name)

    def test_play_random_sound_picks_from_the_given_set(self):
        pygame.init()
        try:
            pygame.mixer.init()
            with patch("ui.sfx.random.choice", side_effect=lambda names: names[1]), \
                    patch.object(pygame.mixer, "Sound") as sound_cls:
                sfx._sound_cache.clear()
                sfx.play_random_sound(sfx.SWORD_SWING_SOUNDS)
            sound_cls.assert_called_once_with(str(sfx.SFX_DIR / sfx.SWORD_SWING_SOUNDS[1]))
            sound_cls.return_value.play.assert_called_once()
        finally:
            sfx._sound_cache.clear()
            pygame.quit()

    def test_run_sound_loops_while_walking_and_stops_when_idle(self):
        pygame.init()
        try:
            pygame.mixer.init()
            channel = MagicMock()
            channel.get_busy.return_value = True
            sfx._sound_cache.clear()
            sfx._run_channel = None
            with patch.object(pygame.mixer, "Sound") as sound_cls:
                sound_cls.return_value.play.return_value = channel
                sfx.set_run_sound(True)
                sfx.set_run_sound(True)
                sound_cls.return_value.play.assert_called_once_with(loops=-1)
                sfx.set_run_sound(False)
            channel.stop.assert_called_once()
            self.assertIsNone(sfx._run_channel)
        finally:
            sfx._sound_cache.clear()
            sfx._run_channel = None
            pygame.quit()

    def test_world_map_requests_run_sound_while_walking(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=FakeWorldClient()))
            scene.move_path = [(scene.player_x + 40, scene.player_y)]
            with patch("scenes.world_map_scene.set_run_sound") as run_sound:
                scene.update(0.05)
            run_sound.assert_called_with(scene.player_state == "walk")
            self.assertTrue(run_sound.called)
        finally:
            pygame.quit()

    def test_swing_sound_plays_when_server_reports_new_swing_for_equipped_weapon(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            client = FakeWorldClient()
            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=client))
            scene.combat_fighter.equipment = {"weapon": {"name": "Железный меч"}}
            scene._world_sync_request(0.0, force=True)
            with patch("scenes.world_map_scene.play_random_sound") as play:
                scene._world_sync_request(0.0, force=True)
                play.assert_not_called()
                client.player["swing_id"] = 1
                scene._world_sync_request(0.0, force=True)
            play.assert_called_once_with(sfx.SWORD_SWING_SOUNDS)
        finally:
            pygame.quit()


class DashSoundTests(unittest.TestCase):
    def test_dash_sound_files_exist(self):
        self.assertTrue((sfx.SFX_DIR / sfx.DASH_SOUND).is_file())
        self.assertTrue((sfx.SFX_DIR / sfx.DASH_WHIRL_SOUND).is_file())

    def test_whirl_event_plays_whirl_sound(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=FakeWorldClient()))
            with patch("scenes.world_map_scene.play_dash_whirl_sound") as play:
                scene._apply_world_event({"type": "whirl"})
            play.assert_called_once_with()
        finally:
            pygame.quit()

    def test_dash_sound_plays_when_dash_is_fired(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=FakeWorldClient()))
            with patch("scenes.world_map_scene.play_dash_sound") as play:
                scene._fire_dash((scene.player_x + 300, scene.player_y))
            play.assert_called_once_with()
        finally:
            pygame.quit()

    def test_dash_sound_does_not_play_when_target_is_too_close(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=FakeWorldClient()))
            with patch("scenes.world_map_scene.play_dash_sound") as play:
                scene._fire_dash((scene.player_x + 1, scene.player_y))
            play.assert_not_called()
        finally:
            pygame.quit()


if __name__ == "__main__":
    unittest.main()
