"""Присутствие, заявки на бой, групповые заявки и боты сервера Колоды (kaloda.server.social / kaloda.server.bots).

Модули хранят состояние в памяти процесса, поэтому каждый тест начинает с чистого состояния и подменяет
файл состояния ботов и папку архива боёв на временную папку (системная временная директория, не репозиторий).
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from kaloda.combat.card_database import cards_for_type
from kaloda.server import bot_chat, bots, config, duel_offers, group_offers, social
from tests.kaloda.server_fixtures import create_test_database, drop_test_database

ROOT = Path(__file__).resolve().parents[2]
BOT_IDS = {"bot_elpachino_fred", "bot_stealth_joe", "bot_fierce_karlo", "bot_wise_victor"}


def make_character(character_id, name="Воин", **extra):
    return {
        "id": character_id, "name": name, "type": "warrior", "level": 1, "xp": 0,
        "hp": 100, "max_hp": 100, "mp": 20, "max_mp": 20,
        "stats": {"strength": 3, "agility": 2, "intuition": 2, "endurance": 4},
        "stat_points": 0, "zone": "world_map",
        "position_x": 10.0, "position_y": 20.0, "position_direction": "s",
        "coins": 10315,
        **extra,
    }


def sender_of(character):
    return {"character_id": character["id"], "name": character["name"]}


class StubDatabase:
    """Минимум базы, который нужен ботам: профиль игрока для боя и запись реплик в чат."""

    def __init__(self, characters=None):
        self.characters = dict(characters or {})
        self.messages = []

    def get_character_for_battle(self, character_id):
        character = self.characters.get(character_id)
        return None if character is None else {"user_id": 1, "character": character}

    def ensure_bot_character(self, bot_id, bot_name):
        return f"stub:{bot_id}"

    def add_chat_message(self, character_id, location, text, recipient_id=None):
        message = {"sender_id": character_id, "location": location, "text": text}
        self.messages.append(message)
        return message


class SocialTestCase(unittest.TestCase):
    """Чистые заявки, присутствие и боты; файл состояния ботов уходит во временную папку."""

    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix="social_")
        self.addCleanup(scratch.cleanup)
        self.scratch = Path(scratch.name)
        self.state_path = self.scratch / "nested" / "bot_state.json"
        patcher = patch.object(bots, "BOT_STATE_PATH", self.state_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.clear_memory()
        previous_database = bots.bind_database(None)
        self.addCleanup(bots.bind_database, previous_database)
        # Выполняется до снятия подмен: следующие тесты получают ботов в начальном состоянии
        self.addCleanup(self.clear_memory)

    @staticmethod
    def clear_memory():
        social.PRESENCE.clear()
        social.DUEL_OFFERS.clear()
        social.GROUP_BATTLE_OFFERS.clear()
        bots.reset_bot_state()
        bots.get_bot_opponents()

    def bot_state(self, bot_id):
        return next(bot for bot in bots.get_bot_opponents() if bot["id"] == bot_id)


class ImportTests(unittest.TestCase):
    def test_importing_bots_and_social_has_no_filesystem_side_effects(self):
        with tempfile.TemporaryDirectory(prefix="social_") as scratch:
            data_dir = Path(scratch) / "data"
            result = subprocess.run(
                [sys.executable, "-c", "import kaloda.server.social, kaloda.server.bots"],
                cwd=ROOT, env={**os.environ, "KALODA_DATA_DIR": str(data_dir)},
                capture_output=True, text=True, timeout=120,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(data_dir.exists())

    def test_bot_state_file_lives_in_the_configured_data_dir(self):
        self.assertEqual(bots.BOT_STATE_PATH, config.DATA_DIR / "bot_state.json")


class PresenceTests(SocialTestCase):
    def test_first_update_reports_a_new_arrival_and_repeats_do_not(self):
        character = make_character(1)

        self.assertTrue(social.update_presence("token-1", 10, character, "tavern"))
        self.assertFalse(social.update_presence("token-1", 10, character, "tavern"))
        self.assertFalse(social.update_presence("token-2", 10, character, "tavern"))

    def test_occupants_hide_tokens_and_account_ids(self):
        social.update_presence("secret-token", 10, make_character(1, "Один"), "tavern")

        players = [item for item in social.occupants(10, "tavern") if item["kind"] == "player"]

        self.assertEqual([item["name"] for item in players], ["Один"])
        self.assertEqual(players[0]["character_id"], 1)
        self.assertNotIn("token", players[0])
        self.assertNotIn("user_id", players[0])
        self.assertNotIn("coins", players[0])

    def test_presence_keeps_profile_talents_and_deck_for_the_opponent_client(self):
        character = make_character(1, talents={"3": "x"}, deck={"warrior_strike": 2})
        social.update_presence("token", 10, character, "backyard")
        character["deck"]["warrior_strike"] = 5

        entry = next(item for item in social.occupants(10, "backyard") if item["kind"] == "player")

        self.assertEqual(entry["talents"], {"3": "x"})
        self.assertEqual(entry["deck"], {"warrior_strike": 2})

    def test_occupants_are_filtered_by_location(self):
        social.update_presence("a", 10, make_character(1, "Таверна"), "tavern")
        social.update_presence("b", 11, make_character(2, "Карта"), "world_map")

        self.assertEqual([item["name"] for item in social.occupants(10, "world_map")], ["Карта"])
        self.assertEqual(
            [item["name"] for item in social.occupants(10, "tavern") if item["kind"] == "player"], ["Таверна"]
        )
        self.assertEqual(social.occupants(10, "character_room"), [])

    def test_bots_are_listed_only_in_the_location_they_stand_in(self):
        backyard = [item for item in social.occupants(10, "backyard") if item["kind"] == "bot"]

        self.assertEqual({item["character_id"] for item in backyard}, BOT_IDS)
        self.assertEqual([item for item in social.occupants(10, "tavern") if item["kind"] == "bot"], [])
        self.assertEqual(social.occupants(10, "world_map"), [])

        # Здоровые боты сразу возвращаются на задний двор, в таверне остаётся только раненый
        bots.update_bot("bot_stealth_joe", 20)
        bots.BOT_STATE["bot_stealth_joe"]["zone"] = "tavern"
        tavern = [item for item in social.occupants(10, "tavern") if item["kind"] == "bot"]
        backyard = [item for item in social.occupants(10, "backyard") if item["kind"] == "bot"]

        self.assertEqual([item["character_id"] for item in tavern], ["bot_stealth_joe"])
        self.assertEqual({item["character_id"] for item in backyard}, BOT_IDS - {"bot_stealth_joe"})
        self.assertTrue(all(item["location"] == "tavern" for item in tavern))

    def test_new_token_replaces_the_stale_entry_of_the_same_character(self):
        character = make_character(1)
        social.update_presence("old-token", 10, character, "tavern")
        social.update_presence("new-token", 10, character, "backyard")

        self.assertEqual(list(social.PRESENCE), ["new-token"])
        self.assertEqual(social.get_character_presence(1)["location"], "backyard")

    def test_live_entry_expires_after_ttl_but_afk_entry_stays(self):
        social.update_presence("live", 10, make_character(1, "Живой"), "tavern")
        social.mark_afk("away", 11, make_character(2, "Афк"))
        for entry in social.PRESENCE.values():
            entry["seen_at"] -= social.PRESENCE_TTL + 1

        self.assertIsNone(social.get_character_presence(1))
        self.assertTrue(social.get_character_presence(2)["afk"])

    def test_mark_afk_keeps_last_reported_location_and_returns_with_the_next_login(self):
        character = make_character(1, zone="world_map")
        social.update_presence("token", 10, character, "backyard")
        social.mark_afk("token", 10, character)

        entry = social.get_character_presence(1)
        self.assertTrue(entry["afk"])
        self.assertEqual(entry["location"], "backyard")

        self.assertTrue(social.update_presence("next-token", 10, character, "tavern"))
        self.assertEqual(list(social.PRESENCE), ["next-token"])
        self.assertFalse(social.get_character_presence(1)["afk"])

    def test_mark_afk_without_previous_presence_uses_the_saved_zone(self):
        social.mark_afk("token", 10, make_character(1, zone="character_room"))

        self.assertEqual(social.get_character_presence(1)["location"], "character_room")
        self.assertIsNone(social.get_character_presence(2))

    def test_update_afk_character_applies_battle_result_and_moves_to_the_saved_zone(self):
        character = make_character(1, zone="backyard")
        social.mark_afk("token", 10, character)

        updated = social.update_afk_character({**character, "hp": 1, "zone": "world_map", "position_x": None})

        self.assertEqual((updated["hp"], updated["location"], updated["position_x"]), (1, "world_map", None))
        self.assertEqual(social.get_character_presence(1)["hp"], 1)
        self.assertEqual(social.update_afk_character(1, {"hp": 5})["hp"], 5)
        self.assertIsNone(social.update_afk_character(2, {"hp": 5}))

    def test_update_afk_character_ignores_online_players(self):
        social.update_presence("token", 10, make_character(1), "tavern")

        self.assertIsNone(social.update_afk_character(make_character(1, hp=3)))
        self.assertEqual(social.get_character_presence(1)["hp"], 100)

    def test_remove_character_presence_drops_every_entry_of_the_character(self):
        social.mark_afk("token", 10, make_character(1))

        self.assertTrue(social.remove_character_presence("1"))
        self.assertFalse(social.remove_character_presence(1))
        self.assertIsNone(social.get_character_presence(1))

    def test_presence_survives_concurrent_updates_and_listing(self):
        errors = []

        def worker(index):
            try:
                for step in range(150):
                    character = make_character(index * 1000 + step % 15)
                    social.update_presence(f"token-{index}-{step}", index, character, "tavern")
                    social.occupants(index, "tavern")
            except Exception as error:
                errors.append(error)

        threads = [threading.Thread(target=worker, args=(index,)) for index in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        self.assertEqual(errors, [])


class DuelOfferTests(SocialTestCase):
    def setUp(self):
        super().setUp()
        self.alice = make_character(1, "Алиса")
        self.bob = make_character(2, "Боб")

    def test_duel_application_is_public_and_expires(self):
        application = social.add_public_duel_offer(sender_of(self.alice), "backyard")

        self.assertIn(application["id"], {offer["id"] for offer in social.public_offers("backyard")})
        user_offer = next(offer for offer in social.DUEL_OFFERS if offer["id"] == application["id"])
        user_offer["created_at"] -= social.DUEL_OFFER_TTL + 1

        self.assertNotIn(application["id"], {offer["id"] for offer in social.public_offers("backyard")})
        self.assertEqual(user_offer["status"], "expired")

    def test_public_application_is_unique_per_sender_and_hidden_from_its_owner(self):
        first = social.add_public_duel_offer(sender_of(self.alice), "backyard")
        second = social.add_public_duel_offer(sender_of(self.alice), "backyard")

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(social.DUEL_OFFERS), 1)
        self.assertEqual(social.public_offers("backyard", exclude_character_id=1), [])
        self.assertEqual(social.pending_public_offer(1, "backyard")["id"], first["id"])
        self.assertEqual(social.public_offers("tavern"), [])

    def test_public_offer_getters_return_copies(self):
        offer = social.add_public_duel_offer(sender_of(self.alice), "backyard")
        offer["status"] = "accepted"
        social.public_offers("backyard")[0]["status"] = "accepted"

        self.assertEqual(social.pending_public_offer(1, "backyard")["status"], "pending")

    def test_cancel_public_application(self):
        social.add_public_duel_offer(sender_of(self.alice), "backyard")

        cancelled = social.cancel_public_duel_offer(1, "backyard")

        self.assertEqual(cancelled["status"], "cancelled")
        self.assertIsNone(social.pending_public_offer(1, "backyard"))
        with self.assertRaises(ValueError):
            social.cancel_public_duel_offer(1, "backyard")

    def test_own_public_offer_returns_pending_and_just_accepted_application(self):
        offer = social.add_public_duel_offer(sender_of(self.alice), "backyard")
        self.assertEqual(social.own_public_offer(1, "backyard")["status"], "pending")

        social.accept_public_offer(offer["id"], 2)
        accepted = social.own_public_offer(1, "backyard")

        self.assertEqual((accepted["status"], accepted["accepted_by"]), ("accepted", 2))
        self.assertIsNone(social.own_public_offer(2, "backyard"))

    def test_target_offer_can_be_accepted_or_declined_only_by_its_target(self):
        offer = social.add_duel_offer(sender_of(self.alice), 2, "backyard")

        self.assertEqual([item["id"] for item in social.offers_for(2)], [offer["id"]])
        self.assertEqual(social.offers_for(1), [])
        with self.assertRaises(ValueError):
            social.respond_duel_offer(3, offer["id"], True)
        with self.assertRaises(ValueError):
            social.respond_duel_offer(1, offer["id"], True)

        accepted = social.respond_duel_offer(2, offer["id"], True)

        self.assertEqual((accepted["status"], accepted["accepted_by"]), ("accepted", 2))
        self.assertEqual(social.offers_for(2), [])
        with self.assertRaises(ValueError):
            social.respond_duel_offer(2, offer["id"], False)

    def test_declined_offer_has_no_accepter(self):
        offer = social.add_duel_offer(sender_of(self.alice), 2, "backyard")

        declined = social.respond_duel_offer(2, offer["id"], False)

        self.assertEqual((declined["status"], declined["accepted_by"]), ("declined", None))

    def test_expired_offer_cannot_be_answered(self):
        offer = social.add_duel_offer(sender_of(self.alice), 2, "backyard", created_at=time.time() - 500)

        with self.assertRaises(ValueError):
            social.respond_duel_offer(2, offer["id"], True)

    def test_anyone_but_the_sender_can_accept_a_public_offer_through_respond(self):
        offer = social.add_public_duel_offer(sender_of(self.alice), "backyard")

        with self.assertRaises(ValueError):
            social.respond_duel_offer(1, offer["id"], True)

        self.assertEqual(social.respond_duel_offer(2, offer["id"], True)["status"], "accepted")

    def test_direct_offer_target_id_from_json_may_be_a_numeric_string(self):
        offer = social.add_duel_offer(sender_of(self.alice), "2", "backyard")

        self.assertEqual(offer["target_id"], 2)
        self.assertEqual(len(social.offers_for(2)), 1)

    def test_direct_offer_can_be_created_already_accepted(self):
        offer = social.add_duel_offer(sender_of(self.alice), "bot_fierce_karlo", "backyard", accepted_by="bot_fierce_karlo")

        self.assertEqual((offer["status"], offer["accepted_by"]), ("accepted", "bot_fierce_karlo"))
        self.assertEqual(social.offers_for("bot_fierce_karlo"), [])
        self.assertIsNone(social.pending_public_offer(1, "backyard"))

    def test_hurt_bot_application_is_withdrawn_from_the_board(self):
        offer = social.add_public_duel_offer({"character_id": "bot_fierce_karlo", "name": "Карло"}, "backyard")
        self.assertEqual([item["id"] for item in social.public_offers("backyard")], [offer["id"]])

        bots.update_bot("bot_fierce_karlo", 40)

        self.assertEqual(social.public_offers("backyard"), [])
        self.assertEqual(social.DUEL_OFFERS[0]["status"], "expired")

    def test_bot_and_player_applications_are_listed_separately(self):
        social.add_public_duel_offer({"character_id": "bot_fierce_karlo", "name": "Карло"}, "backyard")
        social.add_public_duel_offer(sender_of(self.alice), "backyard")

        self.assertEqual([offer["sender_id"] for offer in social.pending_bot_public_offers("backyard")], ["bot_fierce_karlo"])
        self.assertEqual([offer["sender_id"] for offer in social.pending_player_public_offers("backyard")], [1])

    def test_backyard_duel_requires_equal_levels_and_no_equipment(self):
        bot = self.bot_state("bot_fierce_karlo")

        self.assertIsNone(social.backyard_duel_error({"level": 1, "equipment": {}}, bot))
        self.assertIn("одного уровня", social.backyard_duel_error({"level": 2, "equipment": {}}, bot))
        self.assertIn("без экипировки", social.backyard_duel_error({"level": 1, "equipment": {"weapon": {"id": 1}}}, bot))

    def test_closed_offers_are_pruned_after_the_retention_period_keeping_the_same_list(self):
        offers_list = social.DUEL_OFFERS
        accepted = social.add_public_duel_offer(sender_of(self.alice), "backyard")
        social.accept_public_offer(accepted["id"], 2)
        waiting = social.add_public_duel_offer(sender_of(self.bob), "backyard")

        social.public_offers("backyard")
        self.assertEqual(len(social.DUEL_OFFERS), 2)

        stored = next(offer for offer in social.DUEL_OFFERS if offer["id"] == accepted["id"])
        stored["closed_at"] -= duel_offers.CLOSED_OFFER_RETENTION + 1
        social.public_offers("backyard")

        self.assertIs(social.DUEL_OFFERS, offers_list)
        self.assertEqual([offer["id"] for offer in social.DUEL_OFFERS], [waiting["id"]])

    def test_has_active_application_covers_duel_and_group_applications(self):
        self.assertFalse(social.has_active_application(1))

        social.add_public_duel_offer(sender_of(self.alice), "backyard")
        social.create_group_battle_offer(self.bob)

        self.assertTrue(social.has_active_application(1))
        self.assertTrue(social.has_active_application(2))
        social.cancel_public_duel_offer(1, "backyard")
        self.assertFalse(social.has_active_application(1))


class GroupOfferTests(SocialTestCase):
    def fill(self, offer_id, count):
        for index in range(2, count + 1):
            social.join_group_battle_offer(offer_id, make_character(index, f"Боец {index}"))

    def expire(self, offer_id):
        stored = next(offer for offer in social.GROUP_BATTLE_OFFERS if offer["id"] == offer_id)
        stored["created_at"] -= stored["ttl"] + 1

    def test_participants_do_not_expose_money(self):
        offer = social.create_group_battle_offer(make_character(1, "Хозяин"))
        offer = social.join_group_battle_offer(offer["id"], make_character(2, "Гость"))

        for participant in offer["participants"]:
            self.assertNotIn("coins", participant)
            self.assertIn("stats", participant)
        self.assertEqual(
            [item["id"] for item in social.group_battle_offers()[0]["participants"]], [1, 2]
        )

    def test_creating_twice_returns_the_same_waiting_offer(self):
        first = social.create_group_battle_offer(make_character(1))
        second = social.create_group_battle_offer(make_character(1))

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(social.group_battle_offers()), 1)

    def test_join_is_idempotent_and_respects_the_limit(self):
        offer = social.create_group_battle_offer(make_character(1), max_participants=6)
        self.fill(offer["id"], 6)
        self.assertEqual(len(social.join_group_battle_offer(offer["id"], make_character(3))["participants"]), 6)

        with self.assertRaises(ValueError):
            social.join_group_battle_offer(offer["id"], make_character(7))
        with self.assertRaises(ValueError):
            social.join_group_battle_offer("missing", make_character(8))

    def test_participant_leaves_and_owner_leaving_cancels_the_offer(self):
        offer = social.create_group_battle_offer(make_character(1))
        self.fill(offer["id"], 3)

        left = social.leave_group_battle_offer(offer["id"], 2)
        self.assertEqual([item["id"] for item in left["participants"]], [1, 3])
        self.assertFalse(social.has_active_application(2))

        cancelled = social.leave_group_battle_offer(offer["id"], 1)
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(social.group_battle_offers(), [])
        with self.assertRaises(ValueError):
            social.leave_group_battle_offer(offer["id"], 3)
        with self.assertRaises(ValueError):
            social.join_group_battle_offer(offer["id"], make_character(9))

    def test_offer_with_enough_participants_becomes_ready_with_balanced_teams(self):
        offer = social.create_group_battle_offer(make_character(1), max_participants=8)
        self.fill(offer["id"], 7)
        self.expire(offer["id"])

        self.assertEqual(social.group_battle_offers(), [])
        ready = social.group_battle_offer(offer["id"])

        self.assertEqual(ready["status"], "ready")
        self.assertEqual([len(team) for team in ready["teams"]], [3, 3])
        self.assertEqual(len(ready["participants"]), 6)
        self.assertFalse(social.has_active_application(1))

    def test_offer_without_enough_participants_expires(self):
        offer = social.create_group_battle_offer(make_character(1))
        self.fill(offer["id"], 5)
        self.expire(offer["id"])

        self.assertEqual(social.group_battle_offer(offer["id"])["status"], "expired")
        self.assertIsNone(social.group_battle_offer("missing"))

    def test_finished_offers_are_pruned_after_the_retention_period(self):
        offers_list = social.GROUP_BATTLE_OFFERS
        offer = social.create_group_battle_offer(make_character(1))
        self.expire(offer["id"])
        self.assertEqual(social.group_battle_offer(offer["id"])["status"], "expired")

        social.GROUP_BATTLE_OFFERS[0]["created_at"] -= group_offers.CLOSED_OFFER_RETENTION

        self.assertIsNone(social.group_battle_offer(offer["id"]))
        self.assertIs(social.GROUP_BATTLE_OFFERS, offers_list)
        self.assertEqual(offers_list, [])


class BotStateTests(SocialTestCase):
    def test_nothing_is_written_until_a_bot_changes(self):
        bots.get_bot_opponents()
        bots.run_bot_battle_tick(time.time())

        self.assertFalse(self.state_path.parent.exists())

    def test_regeneration_does_not_rewrite_the_state_file(self):
        bots.update_bot("bot_fierce_karlo", 0)
        saved = self.state_path.read_text(encoding="utf-8")
        started = bots.BOT_UPDATED_AT["bot_fierce_karlo"]

        bots._regenerate_bots(started + 100)
        bots.get_bot_opponents()

        self.assertGreater(bots.BOT_STATE["bot_fierce_karlo"]["hp"], 0)
        self.assertEqual(self.state_path.read_text(encoding="utf-8"), saved)

    def test_update_bot_creates_the_directory_and_persists_state(self):
        updated = bots.update_bot("bot_fierce_karlo", {"hp": 100, "mp": 3})

        self.assertEqual((updated["hp"], updated["mp"]), (100, 3))
        saved = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["bot_fierce_karlo"]["hp"], 100)
        self.assertEqual(set(saved), BOT_IDS)
        self.assertFalse(self.state_path.with_name("bot_state.json.tmp").exists())

    def test_saved_state_is_loaded_once_on_first_use(self):
        bots.update_bot("bot_fierce_karlo", 100)
        bots.BOT_STATE["bot_stealth_joe"]["zone"] = "tavern"
        bots.update_bot("bot_stealth_joe", 20)
        bots.reset_bot_state()
        self.assertEqual(bots.BOT_STATE, {})

        loaded = {bot["id"]: bot for bot in bots.get_bot_opponents()}

        self.assertEqual(loaded["bot_fierce_karlo"]["hp"], 100)
        self.assertEqual(loaded["bot_stealth_joe"]["hp"], 20)
        self.assertEqual(loaded["bot_stealth_joe"]["zone"], "tavern")

        self.state_path.write_text("{}", encoding="utf-8")
        self.assertEqual(self.bot_state("bot_fierce_karlo")["hp"], 100)

    def test_bots_keep_healing_for_the_time_the_server_was_down(self):
        saved_at = time.time() - 300
        payload = {"bot_fierce_karlo": {
            "id": "bot_fierce_karlo", "hp": 0, "max_hp": 140, "zone": "backyard",
            "updated_at": saved_at, "last_attack_at": saved_at,
        }}
        self.state_path.parent.mkdir(parents=True)
        self.state_path.write_text(json.dumps(payload), encoding="utf-8")
        bots.reset_bot_state()

        karlo = self.bot_state("bot_fierce_karlo")

        self.assertAlmostEqual(karlo["hp"], 70, delta=2)
        self.assertEqual(bots.BOT_LAST_ATTACK_AT["bot_fierce_karlo"], saved_at)

    def test_broken_state_file_falls_back_to_defaults(self):
        self.state_path.parent.mkdir(parents=True)
        self.state_path.write_text("не json", encoding="utf-8")
        bots.reset_bot_state()

        self.assertEqual(self.bot_state("bot_fierce_karlo")["hp"], 140)

    def test_broken_record_of_one_bot_does_not_affect_the_others(self):
        payload = {
            "bot_fierce_karlo": {"id": "bot_fierce_karlo", "hp": "много", "max_hp": 140, "zone": "tavern"},
            "bot_stealth_joe": {"id": "bot_stealth_joe", "hp": 10, "max_hp": 45, "zone": "nowhere"},
            "bot_unknown": {"id": "bot_unknown", "hp": 1},
        }
        self.state_path.parent.mkdir(parents=True)
        self.state_path.write_text(json.dumps(payload), encoding="utf-8")
        bots.reset_bot_state()

        karlo, joe = self.bot_state("bot_fierce_karlo"), self.bot_state("bot_stealth_joe")

        self.assertEqual((karlo["hp"], karlo["zone"]), (140, "backyard"))
        self.assertEqual((joe["hp"], joe["zone"]), (10, "backyard"))
        self.assertEqual({bot["id"] for bot in bots.get_bot_opponents()}, BOT_IDS)

    def test_locked_bots_only_change_health_and_mana(self):
        before = self.bot_state("bot_fierce_karlo")

        updated = bots.update_bot(
            "bot_fierce_karlo",
            {"level": 9, "xp": 500, "stats": {"strength": 99, "endurance": 99}, "stat_points": 7, "hp": 50},
        )

        self.assertEqual(updated["hp"], 50)
        for key in ("level", "xp", "stats", "stat_points", "max_hp"):
            self.assertEqual(updated[key], before[key])

    def test_update_bot_clamps_health_and_rejects_unknown_bots(self):
        self.assertEqual(bots.update_bot("bot_fierce_karlo", 10_000)["hp"], 140)
        self.assertEqual(bots.update_bot("bot_fierce_karlo", -5)["hp"], 0)
        with self.assertRaises(ValueError):
            bots.update_bot("bot_missing", 1)

    def test_get_bot_opponents_returns_independent_copies(self):
        bots.get_bot_opponents()[0]["hp"] = 1
        bots.get_bot_opponents()[0]["stats"]["strength"] = 99

        self.assertEqual(self.bot_state("bot_elpachino_fred")["hp"], 65)
        self.assertEqual(self.bot_state("bot_elpachino_fred")["stats"]["strength"], 3)

    def test_wounded_bot_heals_faster_in_the_tavern_and_returns_to_the_backyard(self):
        bots.update_bot("bot_fierce_karlo", 0)
        bots.update_bot("bot_stealth_joe", 0)
        bots.BOT_STATE["bot_stealth_joe"]["zone"] = "tavern"
        started = bots.BOT_UPDATED_AT["bot_fierce_karlo"]
        bots.BOT_UPDATED_AT["bot_stealth_joe"] = started

        bots._regenerate_bots(started + bots.BOT_TAVERN_FULL_REGEN_SECONDS + 1)

        karlo, joe = bots.BOT_STATE["bot_fierce_karlo"], bots.BOT_STATE["bot_stealth_joe"]
        self.assertEqual((joe["hp"], joe["zone"]), (joe["max_hp"], "backyard"))
        self.assertAlmostEqual(karlo["hp"], karlo["max_hp"] / 2, delta=1)

        bots._regenerate_bots(started + 2 * bots.BOT_FULL_REGEN_SECONDS)
        self.assertEqual(karlo["hp"], karlo["max_hp"])

    def test_regeneration_keeps_fractional_progress_between_frequent_calls(self):
        bots.update_bot("bot_fierce_karlo", 0)
        started = bots.BOT_UPDATED_AT["bot_fierce_karlo"]

        for second in range(1, 31):
            bots._regenerate_bots(started + second)

        self.assertGreaterEqual(bots.BOT_STATE["bot_fierce_karlo"]["hp"], 5)


class BotProfileTests(SocialTestCase):
    def test_bot_roster_has_one_locked_level_one_bot_per_class(self):
        opponents = {bot["id"]: bot for bot in bots.get_bot_opponents()}

        self.assertEqual({bot["name"] for bot in bots.BOT_OPPONENTS}, {bot["name"] for bot in opponents.values()})
        self.assertEqual(set(opponents), BOT_IDS)
        self.assertEqual({bot["type"] for bot in opponents.values()}, {"archer", "assassin", "warrior", "mage"})
        for bot in opponents.values():
            self.assertEqual((bot["kind"], bot["level"], bot["xp"], bot["zone"]), ("bot", 1, 0, "backyard"))
            self.assertTrue(bot["locked_level"])
            self.assertEqual(bot["hp"], bot["max_hp"])

    def test_bot_decks_use_only_cards_of_their_class(self):
        opponents = {bot["id"]: bot for bot in bots.get_bot_opponents()}
        archer = opponents["bot_elpachino_fred"]

        self.assertEqual(set(archer["deck"]), {card.key for card in cards_for_type("archer")})
        self.assertEqual(set(opponents["bot_fierce_karlo"]["deck"]), {card.key for card in cards_for_type("warrior")})
        mage_keys = {card.key for card in cards_for_type("mage")}
        self.assertTrue(set(opponents["bot_wise_victor"]["deck"]) <= mage_keys)

    def test_bot_stats_and_health(self):
        opponents = {bot["name"]: bot for bot in bots.get_bot_opponents()}

        archer = opponents["Ельпачино Фред"]
        self.assertEqual((archer["type"], archer["max_hp"]), ("archer", 65))
        self.assertEqual(
            {name: archer["stats"][name] for name in ("strength", "agility", "intuition", "endurance")},
            {"strength": 3, "agility": 5, "intuition": 4, "endurance": 4},
        )
        fighter = bots._fighter_from_profile(archer)
        self.assertEqual(fighter.unique_resource_type, "accuracy")
        self.assertEqual(fighter.max_hp, 65)
        self.assertEqual(opponents["Скрытный Джо"]["stats"]["agility"], 6)
        self.assertEqual(opponents["Мудрый Виктор"]["stats"]["wisdom"], 6)

    def test_warrior_bot_hp_uses_warrior_base_health(self):
        karlo = self.bot_state("bot_fierce_karlo")

        self.assertEqual((karlo["type"], karlo["hp"], karlo["max_hp"]), ("warrior", 140, 140))
        self.assertEqual(karlo["stats"]["endurance"], 7)


class BotBoardTests(SocialTestCase):
    def tick_twice(self, start):
        self.assertIsNone(bots.run_bot_battle_tick(start))
        return bots.run_bot_battle_tick(start + 1)

    def test_locked_bots_hold_the_longest_application_on_the_backyard_board(self):
        start = time.time()

        self.assertIsNone(self.tick_twice(start))

        offers = social.pending_bot_public_offers("backyard")
        self.assertEqual({offer["sender_id"] for offer in offers}, BOT_IDS)
        self.assertTrue(all(offer["ttl"] == bots.LOCKED_BOT_APPLICATION_TTL_SECONDS for offer in offers))
        self.assertEqual({offer["sender_id"] for offer in social.public_offers("backyard")}, BOT_IDS)
        # Повторные вызовы не плодят заявки
        bots.run_bot_battle_tick(start + 2)
        self.assertEqual(len(social.DUEL_OFFERS), 4)
        self.assertTrue(self.state_path.exists())

    def test_accepted_application_of_a_locked_bot_is_replaced_by_a_new_one(self):
        start = time.time()
        self.tick_twice(start)
        offer = next(item for item in social.pending_bot_public_offers("backyard") if item["sender_id"] == "bot_fierce_karlo")
        social.respond_duel_offer(7, offer["id"], True)

        bots.run_bot_battle_tick(start + 2)

        fresh = [item for item in social.pending_bot_public_offers("backyard") if item["sender_id"] == "bot_fierce_karlo"]
        self.assertEqual(len(fresh), 1)
        self.assertNotEqual(fresh[0]["id"], offer["id"])

    def test_wounded_bot_does_not_post_an_application(self):
        bots.update_bot("bot_fierce_karlo", 10)

        self.tick_twice(time.time())

        senders = {offer["sender_id"] for offer in social.pending_bot_public_offers("backyard")}
        self.assertEqual(senders, BOT_IDS - {"bot_fierce_karlo"})

    def test_matching_bot_takes_a_player_application_after_the_wait(self):
        start = time.time()
        stub = StubDatabase({101: make_character(101, "Игрок")})
        bots.bind_database(stub)
        offer = social.add_public_duel_offer({"character_id": 101, "name": "Игрок"}, "backyard", created_at=start)
        self.tick_twice(start)

        self.assertIsNone(bots.run_bot_battle_tick(start + bots.PLAYER_APPLICATION_WAIT_SECONDS - 1))
        self.assertEqual(social.own_public_offer(101, "backyard")["status"], "pending")

        result = bots.run_bot_battle_tick(start + bots.PLAYER_APPLICATION_WAIT_SECONDS + 1)

        self.assertEqual(result, {"status": "accepted_by_bot", "player_id": 101, "bot_id": "bot_fierce_karlo"})
        accepted = social.own_public_offer(101, "backyard")
        self.assertEqual((accepted["id"], accepted["status"], accepted["accepted_by"]), (offer["id"], "accepted", "bot_fierce_karlo"))
        # Бой с игроком идёт интерактивно: бот остаётся на заднем дворе
        self.assertEqual(self.bot_state("bot_fierce_karlo")["zone"], "backyard")

    def test_bot_takes_only_applications_it_can_fight(self):
        start = time.time()
        cases = {
            "other class": make_character(101, type="necromancer"),
            "other level": make_character(101, level=2),
            "equipped player": make_character(101, equipment={"weapon": {"id": 1}}),
        }
        for label, character in cases.items():
            with self.subTest(label):
                social.DUEL_OFFERS.clear()
                bots.reset_bot_state()
                bots.bind_database(StubDatabase({101: character}))
                social.add_public_duel_offer({"character_id": 101, "name": "Игрок"}, "backyard", created_at=start)
                self.tick_twice(start)

                result = bots.run_bot_battle_tick(start + bots.PLAYER_APPLICATION_WAIT_SECONDS + 1)

                self.assertIsNone(result)
                self.assertEqual(social.own_public_offer(101, "backyard")["status"], "pending")

    def test_application_of_a_player_missing_from_the_database_is_cancelled(self):
        start = time.time()
        bots.bind_database(StubDatabase())
        social.add_public_duel_offer({"character_id": 101, "name": "Призрак"}, "backyard", created_at=start)
        self.tick_twice(start)

        bots.run_bot_battle_tick(start + bots.PLAYER_APPLICATION_WAIT_SECONDS + 1)

        self.assertIsNone(social.own_public_offer(101, "backyard"))
        self.assertEqual(social.DUEL_OFFERS[0]["status"], "cancelled")

    def test_bot_can_only_take_the_application_while_it_is_healthy(self):
        start = time.time()
        bots.bind_database(StubDatabase({101: make_character(101)}))
        bots.update_bot("bot_fierce_karlo", 100)
        social.add_public_duel_offer({"character_id": 101, "name": "Игрок"}, "backyard", created_at=start)
        self.tick_twice(start)

        self.assertIsNone(bots.run_bot_battle_tick(start + bots.PLAYER_APPLICATION_WAIT_SECONDS + 1))


class BotBattleTests(SocialTestCase):
    """Бои бот-против-бота возможны только для незаблокированных ботов; в составе их сейчас нет, поэтому подставляем своих."""

    def setUp(self):
        super().setUp()
        pair = tuple(
            {**bots._bot(bot_id, name, "warrior", {"strength": 4, "endurance": 5}), "locked_level": False}
            for bot_id, name in (("bot_test_a", "Тестовый А"), ("bot_test_b", "Тестовый Б"))
        )
        target = patch.object(bots, "BOT_OPPONENTS", pair)
        target.start()
        self.addCleanup(target.stop)
        self.clear_memory()

    def replies_by_bot(self, stub):
        return {message["sender_id"]: message["text"] for message in stub.messages}

    def test_reply_lists_do_not_overlap(self):
        replies = bot_chat.BOT_TAVERN_REPLIES

        self.assertEqual(set(replies), {"win", "loss", "draw"})
        self.assertEqual(len({text for texts in replies.values() for text in texts}), sum(len(texts) for texts in replies.values()))

    def test_battle_finishes_updates_both_bots_and_posts_opposite_replies(self):
        stub = StubDatabase()
        bots.bind_database(stub)
        now = time.time()

        result = bots._resolve_bot_battle("bot_test_a", "bot_test_b", now)

        self.assertEqual((result["status"], result["attacker_id"], result["defender_id"]), ("accepted", "bot_test_a", "bot_test_b"))
        self.assertLessEqual(result["turns"], bots.MAX_BOT_BATTLE_TURNS)
        for bot_id in ("bot_test_a", "bot_test_b"):
            bot = bots.BOT_STATE[bot_id]
            self.assertEqual((bot["zone"], bots.BOT_LAST_BATTLE_AT[bot_id]), ("tavern", now))
        replies = self.replies_by_bot(stub)
        self.assertEqual(set(replies), {"stub:bot_test_a", "stub:bot_test_b"})
        self.assertTrue(all(message["location"] == "tavern" for message in stub.messages))
        texts = bot_chat.BOT_TAVERN_REPLIES
        if result["winner"] == "Тестовый А":
            self.assertIn(replies["stub:bot_test_a"], texts["win"])
            self.assertIn(replies["stub:bot_test_b"], texts["loss"])
        elif result["winner"] == "Тестовый Б":
            self.assertIn(replies["stub:bot_test_a"], texts["loss"])
            self.assertIn(replies["stub:bot_test_b"], texts["win"])
        else:
            self.assertIn(replies["stub:bot_test_a"], texts["draw"])
            self.assertIn(replies["stub:bot_test_b"], texts["draw"])
        self.assertFalse((self.scratch / "archive").exists())
        self.assertTrue(self.state_path.exists())

    def test_battle_works_for_mixed_classes_and_mages(self):
        pair = tuple(
            {**bots._bot(bot_id, name, bot_type, {"endurance": 5}), "locked_level": False}
            for bot_id, name, bot_type in (
                ("bot_test_a", "Лучник", "archer"), ("bot_test_b", "Маг", "mage"),
            )
        )
        with patch.object(bots, "BOT_OPPONENTS", pair):
            bots.bind_database(StubDatabase())
            for _ in range(5):
                bots.reset_bot_state()
                self.state_path.unlink(missing_ok=True)
                result = bots._resolve_bot_battle("bot_test_a", "bot_test_b", time.time())
                self.assertEqual(result["status"], "accepted")
                self.assertLessEqual(result["turns"], bots.MAX_BOT_BATTLE_TURNS)

    def test_scheduler_matches_two_free_bots_of_the_same_class(self):
        stub = StubDatabase()
        bots.bind_database(stub)
        start = time.time()
        self.assertIsNone(bots.run_bot_battle_tick(start))

        posted = bots.run_bot_battle_tick(start + bots.BOT_BATTLE_INTERVAL_SECONDS + 1)
        self.assertEqual(posted["status"], "posted")
        offer_id = posted["offer_id"]

        result = bots.run_bot_battle_tick(start + 2 * bots.BOT_BATTLE_INTERVAL_SECONDS + 2)

        self.assertEqual(result["status"], "accepted")
        self.assertEqual({result["attacker_id"], result["defender_id"]}, {"bot_test_a", "bot_test_b"})
        self.assertEqual(len(stub.messages), 2)
        stale = next(offer for offer in social.DUEL_OFFERS if offer["id"] == offer_id)
        self.assertEqual(stale["status"], "cancelled")
        self.assertEqual(social.pending_bot_public_offers("backyard"), [])


class DatabaseSocialTests(SocialTestCase):
    def setUp(self):
        super().setUp()
        self.database = create_test_database()
        self.addCleanup(drop_test_database, self.database)
        previous_database = bots.bind_database(self.database)
        self.addCleanup(bots.bind_database, previous_database)

    def character(self, username, name="Воин", level=1):
        user = self.database.register(username, "password")
        character = self.database.create_character(user["id"], name)
        if level != 1:
            with self.database.connection() as connection:
                connection.execute("UPDATE characters SET level = %s WHERE id = %s", (level, character["id"]))
            character = self.database.get_character(user["id"], character["id"])
        return user, character

    def test_backyard_lists_all_bot_profiles_for_a_player(self):
        user, _ = self.character("tester")

        opponents = self.database.get_opponents(user["id"])

        bot_profiles = {item["name"]: item for item in opponents if item["kind"] == "bot"}
        self.assertEqual(set(bot_profiles), {bot["name"] for bot in bots.BOT_OPPONENTS})
        self.assertEqual(bot_profiles["Ельпачино Фред"]["type"], "archer")
        self.assertEqual(bot_profiles["Сверепый Карло"]["stats"]["endurance"], 7)
        self.assertEqual(bot_profiles["Скрытный Джо"]["stats"]["agility"], 6)

    def test_warrior_bot_hp_uses_warrior_base_health(self):
        user, _ = self.character("hpcheck")

        karlo = next(item for item in self.database.get_opponents(user["id"]) if item["id"] == "bot_fierce_karlo")

        self.assertEqual((karlo["hp"], karlo["max_hp"]), (140, 140))

    def test_database_update_bot_goes_through_the_bot_state(self):
        user, _ = self.character("botfight")

        self.database.update_bot(user["id"], "bot_fierce_karlo", {"hp": 40})

        karlo = next(item for item in self.database.get_opponents(user["id"]) if item["id"] == "bot_fierce_karlo")
        self.assertEqual(karlo["hp"], 40)

    def test_bot_accepts_only_equal_level_duel_on_the_backyard(self):
        user, hero = self.character("botuser", "Равный боец")
        strong_user, strong = self.character("strong", "Сильный", level=2)

        occupants = {str(item["character_id"]): item for item in social.occupants(user["id"], "backyard")}
        bot = occupants["bot_fierce_karlo"]

        self.assertEqual(bot["kind"], "bot")
        self.assertIsNone(social.backyard_duel_error(hero, bot))
        self.assertIn("одного уровня", social.backyard_duel_error(strong, bot))
        offer = social.add_duel_offer(sender_of(hero), bot["character_id"], "backyard", accepted_by=bot["character_id"])
        self.assertEqual((offer["status"], offer["accepted_by"]), ("accepted", "bot_fierce_karlo"))

    def test_bot_takes_a_stored_players_application_only_at_the_same_level(self):
        start = time.time()
        _, hero = self.character("equal", "Равный")
        _, strong = self.character("tough", "Сильный", level=2)
        social.add_public_duel_offer(sender_of(strong), "backyard", created_at=start)
        bots.run_bot_battle_tick(start)
        bots.run_bot_battle_tick(start + 1)

        self.assertIsNone(bots.run_bot_battle_tick(start + bots.PLAYER_APPLICATION_WAIT_SECONDS + 1))

        social.cancel_public_duel_offer(strong["id"], "backyard")
        social.add_public_duel_offer(sender_of(hero), "backyard", created_at=start)
        result = bots.run_bot_battle_tick(start + bots.PLAYER_APPLICATION_WAIT_SECONDS + 2)

        self.assertEqual(result, {"status": "accepted_by_bot", "player_id": hero["id"], "bot_id": "bot_fierce_karlo"})
        self.assertEqual(social.own_public_offer(hero["id"], "backyard")["accepted_by"], "bot_fierce_karlo")

    def test_bot_tavern_reply_is_persisted_in_database(self):
        _, character = self.character("botchat", "Зритель")

        message = social.record_bot_tavern_reply("bot_test", "Тестовый бот", "win", location="tavern", db=self.database)

        history = self.database.get_chat_history(character["id"], "tavern")
        self.assertTrue(any(item["sender"] == "Тестовый бот" for item in history))
        self.assertIn(message["text"], bot_chat.BOT_TAVERN_REPLIES["win"])

    def test_bot_reply_uses_the_bound_database_and_unknown_outcome_means_a_draw(self):
        _, character = self.character("botchat2", "Зритель")

        message = bot_chat.record_bot_tavern_reply("bot_test", "Тестовый бот", "unknown")

        self.assertIn(message["text"], bot_chat.BOT_TAVERN_REPLIES["draw"])
        self.assertEqual(len(self.database.get_chat_history(character["id"], "tavern")), 1)

    def test_bot_reply_failure_is_not_fatal(self):
        class BrokenDatabase:
            def ensure_bot_character(self, bot_id, bot_name):
                raise RuntimeError("база недоступна")

        with patch("builtins.print"):
            self.assertIsNone(social.record_bot_tavern_reply("bot_test", "Бот", "win", db=BrokenDatabase()))

    def test_bot_battle_replies_reach_the_tavern_chat(self):
        _, viewer = self.character("viewer", "Зритель")
        pair = tuple(
            {**bots._bot(bot_id, name, "warrior", {"strength": 4, "endurance": 5}), "locked_level": False}
            for bot_id, name in (("bot_test_a", "Тестовый А"), ("bot_test_b", "Тестовый Б"))
        )
        with patch.object(bots, "BOT_OPPONENTS", pair):
            bots.reset_bot_state()

            bots._resolve_bot_battle("bot_test_a", "bot_test_b", time.time())

        history = self.database.get_chat_history(viewer["id"], "tavern")
        self.assertEqual({item["sender"] for item in history}, {"Тестовый А", "Тестовый Б"})

    def test_deleting_character_clears_cached_afk_presence(self):
        user, character = self.character("presence-delete", "AFK персонаж")
        social.mark_afk("deleted-character-token", user["id"], character)
        self.assertIsNotNone(social.get_character_presence(character["id"]))

        self.database.delete_character(user["id"], character["id"])

        self.assertIsNone(social.get_character_presence(character["id"]))

    def test_presence_accepts_a_character_straight_from_the_database(self):
        user, character = self.character("presence-db", "Из базы")

        self.assertTrue(social.update_presence("token", user["id"], character, "backyard"))

        entry = next(item for item in social.occupants(user["id"], "backyard") if item["kind"] == "player")
        self.assertEqual((entry["name"], entry["type"], entry["level"]), ("Из базы", "warrior", 1))
        self.assertEqual(entry["stats"], character["stats"])
        self.assertNotIn("coins", entry)

    def test_group_offer_built_from_database_characters_is_public_safe(self):
        _, character = self.character("grouper", "Групповой")

        offer = social.create_group_battle_offer(character)

        self.assertEqual(offer["participants"][0]["id"], character["id"])
        self.assertNotIn("coins", offer["participants"][0])


if __name__ == "__main__":
    unittest.main()
