import json
import unittest
from unittest.mock import MagicMock, patch

from server import ai_commentator


class BattleCommentatorTests(unittest.TestCase):
    def setUp(self):
        ai_commentator._RECENT_EVENTS.clear()
        self.database = MagicMock()
        self.database.world_id = 1
        self.database.get_character_for_battle.side_effect = lambda character_id: {
            10: {"user_id": 1, "character": {"id": 10, "name": "Лучник", "type": "archer"}},
            20: {"user_id": 2, "character": {"id": 20, "name": "Страж", "type": "warrior"}},
            30: {"user_id": 0, "character": {"id": 30, "name": "NPC", "type": "warrior"}},
        }.get(character_id)

    def test_server_result_maps_winner_and_loser(self):
        event = ai_commentator._build_event(self.database, 10, 20, "win")

        self.assertEqual(event["winner"]["name"], "Лучник")
        self.assertEqual(event["loser"]["name"], "Страж")
        self.assertEqual(event["winner"]["class"], "лучник")

    def test_loss_swaps_winner_and_loser(self):
        event = ai_commentator._build_event(self.database, 10, 20, "loss")

        self.assertEqual(event["winner"]["name"], "Страж")
        self.assertEqual(event["loser"]["name"], "Лучник")

    def test_draw_contains_both_players_without_declaring_winner(self):
        event = ai_commentator._build_event(self.database, 10, 20, "draw")

        self.assertEqual(event["result"], "draw")
        self.assertEqual([player["name"] for player in event["players"]], ["Лучник", "Страж"])
        self.assertNotIn("winner", event)

    def test_npc_results_are_not_published_as_player_pvp(self):
        self.assertIsNone(ai_commentator._build_event(self.database, 10, 30, "win"))

    def test_valid_pvp_result_is_queued_without_waiting_for_model(self):
        with patch.object(ai_commentator._QUEUE, "put_nowait") as put_event, \
                patch.object(ai_commentator, "_ensure_worker"):
            queued = ai_commentator.enqueue_battle_comment(self.database, 10, 20, "win")

        self.assertTrue(queued)
        self.assertEqual(put_event.call_args.args[0][:5], ("battle", self.database, 10, 20, "win"))

    def test_unknown_result_is_not_queued(self):
        with patch.object(ai_commentator._QUEUE, "put_nowait") as put_event:
            queued = ai_commentator.enqueue_battle_comment(self.database, 10, 20, "unknown")

        self.assertFalse(queued)
        put_event.assert_not_called()

    def test_event_claim_deduplicates_opposite_reports_for_one_match(self):
        key = ai_commentator._battle_key(1, 10, 20)
        ai_commentator._RECENT_EVENTS.clear()

        self.assertTrue(ai_commentator._claim_event(key, now=100))
        self.assertFalse(ai_commentator._claim_event(ai_commentator._battle_key(1, 20, 10), now=110))
        self.assertTrue(ai_commentator._claim_event(key, now=150))

    def test_fallback_uses_only_confirmed_winner_and_loser(self):
        text = ai_commentator._fallback_comment({
            "result": "win",
            "winner": {"name": "Лучник"},
            "loser": {"name": "Страж"},
        })

        self.assertEqual(text, "Бой завершён: победа Лучник над Страж.")

    def test_server_accepted_event_is_posted_to_world_chat(self):
        key = ai_commentator._battle_key(1, 10, 20)
        with patch.object(ai_commentator, "_generate_comment", return_value="Лучник празднует победу!"):
            ai_commentator._process_event(self.database, 10, 20, "win", key)

        self.database.ensure_bot_character.assert_called_once_with(
            "battle-commentator-1", "Летописец",
        )
        self.database.add_chat_message.assert_called_once_with(
            self.database.ensure_bot_character.return_value,
            "world",
            "Лучник празднует победу!",
        )

    def test_model_failure_posts_confirmed_result_fallback(self):
        event = ai_commentator._build_event(self.database, 10, 20, "loss")
        with patch.object(ai_commentator, "_generate_comment", side_effect=OSError("offline")):
            ai_commentator._post_comment(self.database, event)

        self.database.add_chat_message.assert_called_once()
        self.assertEqual(
            self.database.add_chat_message.call_args.args[2],
            "Бой завершён: победа Страж над Лучник.",
        )

    def test_world_comment_is_published_to_the_global_feed(self):
        lines = ["Город испытывает нехватку пищи.", "Запасы еды в городе на исходе."]
        with patch.object(ai_commentator, "_generate_allowed_line", return_value=lines[1]):
            ai_commentator._post_world_comment(
                self.database, "food:shortage", {"status": "shortage"}, lines,
            )

        self.database.ensure_bot_character.assert_called_once_with(
            "world-narrator-1", "Летописец",
        )
        self.database.add_chat_message.assert_called_once_with(
            self.database.ensure_bot_character.return_value, "world", lines[1],
        )

    def test_world_event_queue_is_nonblocking_and_server_scoped(self):
        lines = ["Склад предприятия заполнен."]
        with patch.object(ai_commentator._QUEUE, "put_nowait") as put_event, \
                patch.object(ai_commentator, "_ensure_worker"):
            queued = ai_commentator.enqueue_world_comment(
                self.database, "storage-full:farm", {"building": "farm"}, lines,
            )

        self.assertTrue(queued)
        task = put_event.call_args.args[0]
        self.assertEqual(task[0], "world")
        self.assertEqual(task[1:5], (
            self.database, "storage-full:farm", {"building": "farm"}, tuple(lines),
        ))

    def test_world_event_queue_rejects_empty_templates(self):
        with patch.object(ai_commentator._QUEUE, "put_nowait") as put_event:
            queued = ai_commentator.enqueue_world_comment(
                self.database, "invalid", {}, [],
            )

        self.assertFalse(queued)
        put_event.assert_not_called()

    def test_world_event_worker_posts_the_allowlisted_line_once(self):
        lines = ["Жители недоедают.", "В городе нехватка пищи."]
        with patch.object(ai_commentator, "_generate_allowed_line", return_value=lines[1]):
            ai_commentator._post_world_comment(
                self.database, "food:shortage", {"event": "food_shortage"}, lines,
            )

        self.database.ensure_bot_character.assert_called_once_with(
            "world-narrator-1", "Летописец",
        )
        self.database.add_chat_message.assert_called_once_with(
            self.database.ensure_bot_character.return_value, "world", lines[1],
        )

    def test_ollama_output_is_cleaned_and_bounded(self):
        response = MagicMock()
        event = {
            "result": "win",
            "winner": {"name": "Лучник"},
            "loser": {"name": "Страж"},
        }
        allowed_line = ai_commentator._allowed_comments(event)[0]
        response.__enter__.return_value.read.return_value = (
            json.dumps({"message": {"content": f'  "{allowed_line}\n  '}}).encode("utf-8")
        )
        with patch.object(ai_commentator.urllib.request, "urlopen", return_value=response):
            text = ai_commentator._generate_comment(event)

        self.assertEqual(text, allowed_line)
        self.assertLessEqual(len(text), ai_commentator.MAX_COMMENT_LENGTH)

    def test_ollama_cannot_add_unverified_battle_claims(self):
        response = MagicMock()
        event = {
            "result": "win",
            "winner": {"name": "Лучник"},
            "loser": {"name": "Страж"},
        }
        response.__enter__.return_value.read.return_value = json.dumps({
            "message": {"content": "Лучник как всегда одержал победу после мощного выстрела."},
        }).encode("utf-8")
        with patch.object(ai_commentator.urllib.request, "urlopen", return_value=response):
            with self.assertRaisesRegex(ValueError, "verified templates"):
                ai_commentator._generate_comment(event)


if __name__ == "__main__":
    unittest.main()
