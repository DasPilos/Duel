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

    def test_population_uses_color_satiety_bars_and_strong_hunger_meter(self):
        from ui.catalog_icons import draw_item_icon

        window = CastleWindow(object())
        window.is_open = True
        window.tab = "population"
        window.state = {
            "population": 4,
            "population_capacity": 10,
            "citizens": [
                {"id": 1, "name": "Красная", "satiety": 8, "strong_hunger": 0,
                 "satisfaction": "starving", "work_status": "Свободен"},
                {"id": 2, "name": "Чёрная", "satiety": 0, "strong_hunger": 35,
                 "satisfaction": "starving", "work_status": "Свободен"},
                {"id": 3, "name": "Жёлтая", "satiety": 25, "strong_hunger": 0,
                 "satisfaction": "irritated", "work_status": "Свободен"},
                {"id": 4, "name": "Зелёная", "satiety": 31, "strong_hunger": 0,
                 "satisfaction": "satisfied", "work_status": "Свободен"},
            ],
            "food_storage": {"wheat": 0, "berries": 0, "meat": 0},
            "food_status": "В городе голод",
            "worksites": [],
        }
        rendered = {}
        original_font = window.small_font

        class Recorder:
            def render(self, text, *args):
                rendered[text] = args[1] if len(args) > 1 else None
                return original_font.render(text, *args)

            def __getattr__(self, name):
                return getattr(original_font, name)

        window.small_font = Recorder()
        screen = pygame.Surface((window.rect.right + 1, window.rect.bottom + 1))
        with patch("ui.castle_window.draw_item_icon", wraps=draw_item_icon) as draw_icon:
            with patch("pygame.mouse.get_pos", return_value=(0, 0)):
                window.draw(screen)

        self.assertEqual(rendered["Сытность 8%"], (226, 66, 58))
        self.assertEqual(rendered["Сильный голод 35%"], (15, 15, 15))
        self.assertEqual(rendered["Сытность 25%"], (232, 184, 48))
        self.assertEqual(rendered["Сытность 31%"], (72, 174, 95))
        self.assertFalse(any("/100" in text for text in rendered))
        self.assertFalse(any("приёма пищи" in text for text in rendered))
        self.assertFalse(any(text.startswith("Довольство:") for text in rendered))
        citizen_icons = [call for call in draw_icon.call_args_list if call.args[1] == "citizen"]
        self.assertEqual(len(citizen_icons), 4)
        self.assertTrue(all(call.args[3] == 32 for call in citizen_icons))

    def test_population_lists_free_citizens_before_workers(self):
        window = CastleWindow(object())
        state = {
            "population": 2,
            "population_capacity": 10,
            "citizens": [
                {"id": 1, "name": "Работает", "satiety": 80, "strong_hunger": 0,
                 "satisfaction": "satisfied", "work_status": "Занят", "job_building": "farm"},
                {"id": 2, "name": "Свободен", "satiety": 75, "strong_hunger": 0,
                 "satisfaction": "satisfied", "work_status": "Свободен", "job_building": None},
            ],
            "food_storage": {},
            "worksites": [],
            "city_upgrade": {
                "active": True, "tick_index": 1, "seconds_left": 500,
                "resource_cost_per_tick": {"wheat": 40, "wood": 40},
            },
        }
        rendered = []
        original_font, original_small_font = window.font, window.small_font

        class Recorder:
            def __init__(self, wrapped):
                self.wrapped = wrapped

            def render(self, text, *args):
                rendered.append(str(text))
                return self.wrapped.render(text, *args)

            def __getattr__(self, name):
                return getattr(self.wrapped, name)

        window.font = Recorder(original_font)
        window.small_font = Recorder(original_small_font)
        screen = pygame.Surface((window.rect.right + 1, window.rect.bottom + 1))
        with patch("pygame.mouse.get_pos", return_value=(0, 0)):
            window._draw_population(screen, state, (0, 0))

        self.assertIn("Население: 2 / 10", rendered)
        self.assertFalse(any(text.startswith("Уровень города:") for text in rendered))
        self.assertFalse(any(text.startswith("Амбар:") for text in rendered))
        self.assertFalse(any(text.startswith("Проверка запасов") for text in rendered))
        self.assertLess(rendered.index("Свободен"), rendered.index("Работает"))

    def test_population_citizen_list_scrolls_to_last_residents(self):
        pygame.display.set_mode((1, 1), pygame.HIDDEN)
        window = CastleWindow(object())
        window.is_open = True
        window.tab = "population"
        citizens = [
            {"id": index, "name": f"Горожанин {index}", "satiety": 80,
             "strong_hunger": 0, "satisfaction": "satisfied",
             "work_status": "Занят", "job_building": "farm"}
            for index in range(1, 25)
        ]
        state = {
            "population": len(citizens), "population_capacity": 30,
            "citizens": citizens, "food_storage": {}, "worksites": [],
            "city_upgrade": {},
        }
        window.state = state
        rendered = []
        original_font = window.small_font

        class Recorder:
            def render(self, text, *args):
                rendered.append(str(text))
                return original_font.render(text, *args)

            def __getattr__(self, name):
                return getattr(original_font, name)

        window.small_font = Recorder()
        screen = pygame.Surface((window.rect.right + 1, window.rect.bottom + 1))
        window._draw_population(screen, state, (0, 0))
        self.assertIn("Горожанин 1", rendered)
        self.assertNotIn("Горожанин 24", rendered)

        list_rect = window.citizen_list_rect()
        visible_rows = list_rect.height // window.CITIZEN_ROW_HEIGHT
        with patch("pygame.mouse.get_pos", return_value=list_rect.center):
            window.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-100))
        self.assertEqual(window.citizen_scroll, len(citizens) - visible_rows)

        rendered.clear()
        window._draw_population(screen, state, (0, 0))
        self.assertIn("Горожанин 24", rendered)
        self.assertIn(24, window.citizen_actions)

    def test_population_scrollbar_is_visible_and_draggable(self):
        pygame.display.set_mode((1, 1), pygame.HIDDEN)
        window = CastleWindow(object())
        window.is_open = True
        window.tab = "population"
        citizens = [
            {"id": index, "name": f"Горожанин {index}", "satiety": 80,
             "strong_hunger": 0, "satisfaction": "satisfied",
             "work_status": "Занят", "job_building": "farm"}
            for index in range(1, 25)
        ]
        state = {
            "population": len(citizens), "population_capacity": 30,
            "citizens": citizens, "food_storage": {}, "worksites": [],
            "city_upgrade": {},
        }
        window.state = state
        thumb = window.citizen_scrollbar_thumb_rect()
        self.assertIsNotNone(thumb)
        self.assertLess(thumb.height, window.citizen_scrollbar_track_rect().height)

        window.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=thumb.center,
        ))
        self.assertTrue(window.citizen_scroll_dragging)
        track = window.citizen_scrollbar_track_rect()
        window.handle_event(pygame.event.Event(
            pygame.MOUSEMOTION, pos=(thumb.centerx, track.bottom), rel=(0, track.height), buttons=(1, 0, 0),
        ))
        self.assertEqual(window.citizen_scroll, window.citizen_max_scroll())
        rendered_row_rects = []
        original_draw_rect = pygame.draw.rect

        def record_rows(surface, color, rect, *args, **kwargs):
            if isinstance(rect, pygame.Rect) and rect.width == window.citizen_list_rect().width \
                    and rect.height == 34:
                rendered_row_rects.append(rect.copy())
            return original_draw_rect(surface, color, rect, *args, **kwargs)

        with patch("pygame.draw.rect", side_effect=record_rows):
            window._draw_population(
                pygame.Surface((window.rect.right + 1, window.rect.bottom + 1)),
                state, (0, 0),
            )
        self.assertTrue(rendered_row_rects)
        self.assertTrue(all(
            window.citizen_list_rect().top <= row.top
            and row.bottom <= window.citizen_list_rect().bottom
            for row in rendered_row_rects
        ))
        window.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONUP, button=1, pos=(thumb.centerx, track.bottom),
        ))
        self.assertFalse(window.citizen_scroll_dragging)

    def test_governor_lists_hourly_rates_and_trends_for_city_resources(self):
        from ui.catalog_icons import draw_item_icon

        window = CastleWindow(object())
        rendered = []
        original_font = window.font

        class Recorder:
            def render(self, text, *args):
                rendered.append(str(text))
                return original_font.render(text, *args)

            def __getattr__(self, name):
                return getattr(original_font, name)

        window.font = Recorder()
        window.small_font = Recorder()
        screen = pygame.Surface((window.rect.right + 1, window.rect.bottom + 1))
        with patch("ui.castle_window.draw_item_icon", wraps=draw_item_icon) as draw_icon:
            window._draw_governor(screen, {
                "city_resource_income_per_hour": {"wheat": 16.0},
                "city_resource_consumption_per_hour": {"wheat": 9.6},
                "city_resource_trend": {"wheat": "surplus"},
            })
            window._draw_governor(screen, {
                "city_resource_income_per_hour": {
                    "wheat": 16.0, "berries": 3.0, "meat": 1.0, "wood": 15.0,
                },
                "city_resource_consumption_per_hour": {
                    "wheat": 9.6, "berries": 2.4, "meat": 2.0, "wood": 0.0,
                },
                "city_resource_trend": {
                    "wheat": "upgrade_ready", "berries": "surplus", "meat": "deficit",
                    "wood": "surplus",
                },
            })

        self.assertLess(rendered.index("Доход в час"), rendered.index("Расход в час"))
        self.assertIn("Пшеница", rendered)
        self.assertIn("16,0 в час", rendered)
        self.assertIn("9,6 в час", rendered)
        self.assertIn("Древесина", rendered)
        self.assertIn("15,0 в час", rendered)
        self.assertIn("Есть небольшой +", rendered)
        self.assertIn("На ап города", rendered)
        self.assertIn("Дефицит", rendered)
        icon_keys = [call.args[1] for call in draw_icon.call_args_list]
        self.assertEqual(icon_keys, ["wheat", "wheat", "berries", "meat", "wood"])


if __name__ == "__main__":
    unittest.main()