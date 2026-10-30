import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from core import settings
from ui.chat.dialog import ChatDialog, parse_whisper
from ui.combat_log import CombatLog


def key_event(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0)


class FakeSession:
    def __init__(self):
        self.character = {"id": 1}
        self.sent = []

    def send_message(self, location, text, recipient_id=None):
        self.sent.append((location, text, recipient_id))


class FakePresence:
    def __init__(self, occupants=(), messages=()):
        self.occupants = list(occupants)
        self.messages = list(messages)
        self.refresh_calls = 0

    def refresh(self):
        self.refresh_calls += 1


class ParseWhisperTests(unittest.TestCase):
    OCCUPANTS = [
        {"name": "Ива", "character_id": "2"},
        {"name": "Ива Смит", "character_id": "3"},
    ]

    def test_parses_name_and_message(self):
        target, message, error = parse_whisper("/w Ива привет", self.OCCUPANTS)
        self.assertEqual(target["character_id"], "2")
        self.assertEqual(message, "привет")
        self.assertEqual(error, "")

    def test_longest_name_wins(self):
        target, message, error = parse_whisper("/w Ива Смит как дела", self.OCCUPANTS)
        self.assertEqual(target["character_id"], "3")
        self.assertEqual(message, "как дела")
        self.assertEqual(error, "")

    def test_unknown_player_reports_error(self):
        target, _, error = parse_whisper("/w Бор привет", self.OCCUPANTS)
        self.assertIsNone(target)
        self.assertIn("Бор", error)

    def test_name_without_message_reports_error(self):
        target, _, error = parse_whisper("/w Ива", self.OCCUPANTS)
        self.assertEqual(target["character_id"], "2")
        self.assertTrue(error)

    def test_empty_command_reports_format(self):
        target, _, error = parse_whisper("/w", self.OCCUPANTS)
        self.assertIsNone(target)
        self.assertIn("/w", error)


class ChatDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def make_dialog(self, presence=None):
        session = FakeSession()
        presence = presence or FakePresence(occupants=[{"name": "Ива", "character_id": "2"}])
        return ChatDialog(session, "tavern", presence), session

    def test_enter_opens_and_escape_hides(self):
        dialog, _ = self.make_dialog()
        self.assertFalse(dialog.visible)
        self.assertTrue(dialog.open_from_key(key_event(pygame.K_RETURN)))
        self.assertTrue(dialog.visible)
        self.assertTrue(dialog.captures_keyboard())
        self.assertTrue(dialog.handle_event(key_event(pygame.K_ESCAPE)))
        self.assertFalse(dialog.visible)

    def test_open_from_key_ignores_other_keys(self):
        dialog, _ = self.make_dialog()
        self.assertFalse(dialog.open_from_key(key_event(pygame.K_a)))
        self.assertFalse(dialog.visible)

    def test_general_tab_hides_whispers(self):
        messages = [
            {"id": 1, "sender_id": "5", "recipient_id": None, "text": "всем привет"},
            {"id": 2, "sender_id": "1", "recipient_id": "2", "text": "личное"},
            {"id": 3, "sender_id": "3", "recipient_id": "4", "text": "чужое"},
        ]
        dialog, _ = self.make_dialog(FakePresence(messages=messages))
        dialog.open()
        self.assertEqual([m["id"] for m in dialog._visible_messages()], [1])

    def test_private_tab_shows_only_own_whispers(self):
        messages = [
            {"id": 1, "sender_id": "5", "recipient_id": None, "text": "всем привет"},
            {"id": 2, "sender_id": "1", "recipient_id": "2", "text": "мое"},
            {"id": 3, "sender_id": "2", "recipient_id": "1", "text": "ответ"},
            {"id": 4, "sender_id": "3", "recipient_id": "4", "text": "чужое"},
        ]
        dialog, _ = self.make_dialog(FakePresence(messages=messages))
        dialog.open()
        dialog._select_tab("Личный")
        self.assertEqual([m["id"] for m in dialog._visible_messages()], [2, 3])

    def test_whisper_command_sends_to_recipient(self):
        dialog, session = self.make_dialog()
        dialog.open()
        dialog.message_input.text = "/w Ива привет"
        dialog._submit()
        self.assertEqual(session.sent, [("tavern", "привет", "2")])
        self.assertEqual(dialog.message_input.text, "")
        self.assertEqual(dialog.tab, "Личный")

    def test_private_tab_without_target_asks_for_whisper(self):
        dialog, session = self.make_dialog()
        dialog.open()
        dialog._select_tab("Личный")
        dialog.message_input.text = "привет"
        dialog._submit()
        self.assertEqual(session.sent, [])
        self.assertTrue(dialog.status)


class CombatLogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_entries_appear_one_by_one(self):
        log = CombatLog()
        log.add("first")
        log.add("second")
        log.update(0.1)
        self.assertEqual(len(log.visible_entries), 0)
        log.update(settings.COMBAT_LOG_APPEAR_INTERVAL)
        self.assertEqual([e["text"] for e in log.visible_entries], ["first"])
        log.update(settings.COMBAT_LOG_APPEAR_INTERVAL)
        self.assertEqual([e["text"] for e in log.visible_entries], ["first", "second"])

    def test_entry_stays_then_fades_then_disappears(self):
        log = CombatLog()
        log.add("hit")
        log.update(settings.COMBAT_LOG_APPEAR_INTERVAL)
        entry = log.visible_entries[0]
        self.assertEqual(log.entry_alpha(entry), 255)

        log.update(settings.COMBAT_LOG_VISIBLE_SECONDS - 1)
        self.assertEqual(log.entry_alpha(entry), 255)

        log.update(settings.COMBAT_LOG_FADE_SECONDS / 2)
        self.assertTrue(0 < log.entry_alpha(entry) < 255)

        log.update(settings.COMBAT_LOG_FADE_SECONDS)
        self.assertEqual(log.visible_entries, [])

    def test_l_toggles_full_log_and_escape_closes(self):
        log = CombatLog()
        self.assertTrue(log.handle_event(key_event(pygame.K_l)))
        self.assertTrue(log.full_open)
        self.assertTrue(log.captures_keyboard())
        self.assertTrue(log.handle_event(key_event(pygame.K_ESCAPE)))
        self.assertFalse(log.full_open)

    def test_full_log_keeps_history_after_entries_fade(self):
        log = CombatLog()
        log.add("old")
        log.update(settings.COMBAT_LOG_APPEAR_INTERVAL)
        log.update(settings.COMBAT_LOG_VISIBLE_SECONDS + settings.COMBAT_LOG_FADE_SECONDS + 1)
        self.assertEqual(log.visible_entries, [])
        self.assertEqual([e["text"] for e in log.history], ["old"])


if __name__ == "__main__":
    unittest.main()
