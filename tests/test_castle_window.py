import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pygame

from ui.castle_window import CastleWindow


class CastleWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.font.init()

    def test_assignment_and_recall_require_confirmation(self):
        citizen = {
            "id": 7,
            "name": "Горожанин 7",
            "job_building": None,
            "job_slot": None,
            "travel_direction": None,
        }
        state = {
            "citizens": [citizen],
            "worksites": [{"building": "farm", "free_slots": [0], "capacity": 1}],
        }

        class Client:
            assigned = 0
            recalled = 0

            def assign_city_citizen(self, character_id, citizen_id, building, slot_index):
                self.assigned += 1
                citizen.update(job_building=building, job_slot=slot_index,
                               travel_direction="outbound")
                return state

            def recall_city_citizen(self, character_id, citizen_id):
                self.recalled += 1
                citizen["travel_direction"] = "returning"
                return state

        client = Client()
        scene = SimpleNamespace(
            session=SimpleNamespace(client=client, character={"id": 1}),
            city_population_count=4,
        )
        window = CastleWindow(scene)
        window.is_open = True
        window.tab = "population"
        window.state = state
        window.citizen_actions = {7: pygame.Rect(500, 200, 120, 30)}
        window.worksite_buttons = {"farm": pygame.Rect(100, 500, 180, 50)}
        window.confirm_button = pygame.Rect(600, 400, 160, 36)

        click = lambda rect: pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center
        )
        window.handle_event(click(window.citizen_actions[7]))
        window.handle_event(click(window.worksite_buttons["farm"]))
        self.assertEqual(client.assigned, 0)
        self.assertEqual(window.pending_action["kind"], "assign")

        window.handle_event(click(window.confirm_button))
        self.assertEqual(client.assigned, 1)

        window.citizen_actions = {7: pygame.Rect(500, 200, 120, 30)}
        window.handle_event(click(window.citizen_actions[7]))
        self.assertEqual(client.recalled, 0)
        self.assertEqual(window.pending_action["kind"], "recall")

        window.handle_event(click(window.confirm_button))
        self.assertEqual(client.recalled, 1)

    def test_treasury_transfers_are_limited_and_confirmed(self):
        class Client:
            def __init__(self):
                self.calls = []

            def transfer_city_treasury(self, character_id, direction, amount_copper):
                self.calls.append((character_id, direction, amount_copper))
                return state

        state = {
            "treasury_copper": 150,
            "treasury_text": "1 серебро 50 меди",
            "personal_currency_copper": 250,
            "personal_currency_text": "2 серебра 50 меди",
        }
        client = Client()
        scene = SimpleNamespace(
            session=SimpleNamespace(client=client, character={"id": 9}),
            city_population_count=4,
        )
        window = CastleWindow(scene)
        window.is_open = True
        window.state = state
        window.tab = "treasury"
        self.assertEqual(tuple(window.tabs)[1:3], ("population", "treasury"))

        window._open_treasury_transfer("deposit")
        self.assertEqual(window.treasury_transfer["maximum"], 250)
        window.treasury_track_rect = pygame.Rect(100, 100, 200, 8)
        window.treasury_confirm_button = pygame.Rect(400, 200, 120, 36)
        window.treasury_cancel_button = pygame.Rect(260, 200, 120, 36)
        window.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1,
            pos=(window.treasury_track_rect.right, window.treasury_track_rect.centery),
        ))
        window.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=window.treasury_confirm_button.center,
        ))
        self.assertEqual(client.calls, [(9, "deposit", 250)])

        window.state = {**state, "treasury_copper": 150}
        window._open_treasury_transfer("withdraw")
        self.assertEqual(window.treasury_transfer["maximum"], 150)
        window.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1,
            pos=(window.treasury_track_rect.left + window.treasury_track_rect.width // 2,
                 window.treasury_track_rect.centery),
        ))
        window.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=window.treasury_confirm_button.center,
        ))
        self.assertEqual(client.calls[-1], (9, "withdraw", 75))

    def test_treasury_transfer_refreshes_cached_character_wallet(self):
        class Client:
            def transfer_city_treasury(self, _character_id, _direction, _amount_copper):
                return {"personal_currency": {"copper": 25, "silver": 3, "gold": 0}}

        character = {"id": 9, "copper": 0, "silver": 2, "gold": 0}
        class ProfileOverlay:
            profile = None
            counterpart = None

            def update_profile(self, value):
                self.profile = dict(value)

            def update_counterpart(self, value):
                self.counterpart = dict(value)

        profile_overlay = ProfileOverlay()
        scene = SimpleNamespace(
            session=SimpleNamespace(client=Client(), character=character),
            city_population_count=4,
            profile_overlay=profile_overlay,
        )
        window = CastleWindow(scene)
        window.is_open = True
        window.treasury_transfer = {"direction": "withdraw", "maximum": 100}
        window.treasury_quantity = 125
        window.treasury_confirm_button = pygame.Rect(400, 200, 120, 36)

        window.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=window.treasury_confirm_button.center,
        ))

        self.assertEqual(character, {"id": 9, "copper": 25, "silver": 3, "gold": 0})
        self.assertEqual(profile_overlay.profile["silver"], 3)
        self.assertEqual(profile_overlay.counterpart["copper"], 25)

    def test_treasury_tax_timer_shows_expected_income(self):
        window = CastleWindow(object())
        state = {
            "treasury": {"copper": 0, "silver": 0, "gold": 0},
            "treasury_text": "1 серебро",
            "personal_currency_text": "2 серебра",
            "tax_tick_seconds_left": 60,
            "expected_tax_text": "2 серебра 20 меди",
        }
        rendered = []
        original_font = window.small_font

        class Recorder:
            def render(self, text, *args):
                rendered.append(text)
                return original_font.render(text, *args)

            def __getattr__(self, name):
                return getattr(original_font, name)

        window.small_font = Recorder()
        screen = pygame.Surface((window.rect.right + 1, window.rect.bottom + 1))
        with patch("pygame.mouse.get_pos", return_value=(0, 0)):
            window._draw_treasury(screen, state)

        self.assertIn(
            "До сбора налогов: 00:01:00 (ожидается: 2 серебра 20 меди)",
            rendered,
        )
        self.assertIn("ПОПОЛНИТЬ КАЗНУ", rendered)
        self.assertIn("ВЗЯТЬ С КАЗНЫ", rendered)
        self.assertNotIn("Ваши монеты: 2 серебра", rendered)
        self.assertFalse(any(text.startswith("За тик:") for text in rendered))


if __name__ == "__main__":
    unittest.main()