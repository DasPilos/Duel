import time
import unittest
from types import SimpleNamespace

import pygame

from core import settings
from scenes.character_scene import CharacterScene
from scenes.hall_of_fame_scene import HallOfFameScene


class HallOfFameSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_paginates_archive_and_opens_turn_history(self):
        records = [
            {
                "id": index + 1,
                "player_name": f"Игрок {index}",
                "opponent_name": "Соперник",
                "player_level": 4,
                "opponent_level": 4,
                "winner_name": f"Игрок {index}",
                "outcome": "win",
                "turns": 1,
                "created_at": 1_700_000_000 + index,
            }
            for index in range(13)
        ]

        class FakeSession:
            def list_battle_archive(self, limit, offset):
                return {"battles": records[offset:offset + limit], "total": len(records)}

            def get_battle_archive_record(self, record_id):
                summary = records[int(record_id) - 1]
                return {
                    **summary,
                    "replay_json": {
                        "history": [{"turn": 1, "events": [{"side": "player", "card": "Удар", "damage": 5}]}],
                        "stats": {"player": {"damage": 5}, "enemy": {"damage": 0}},
                        "player": {"name": summary["player_name"], "hp": 10},
                        "enemy": {"name": summary["opponent_name"], "hp": 0},
                    },
                }

        scene = HallOfFameScene(FakeSession())
        scene.draw(self.screen)
        self.assertEqual(len(scene.records), 12)
        self.assertEqual(scene.total, 13)

        scene.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=scene.next_page_button.center,
        ))
        self.assertEqual(scene.offset, 12)
        self.assertEqual(len(scene.records), 1)

        scene.draw(self.screen)
        scene.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=scene.row_rects[0].center,
        ))
        self.assertEqual(scene.selected["id"], 13)
        events, history_count = scene._history_events()
        self.assertEqual(history_count, 1)
        self.assertIn("Удар", events[0])

        scene.handle_event(pygame.event.Event(
            pygame.KEYDOWN, key=pygame.K_ESCAPE,
        ))
        self.assertTrue(scene.finished)

    def test_character_selection_button_opens_hall_of_fame_route(self):
        class FakeSession:
            def list_characters(self):
                return []

        scene = CharacterScene(FakeSession())
        scene.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=scene.hall_of_fame_button.center,
        ))

        self.assertTrue(scene.finished)
        self.assertTrue(scene.hall_of_fame_requested)


if __name__ == "__main__":
    unittest.main()