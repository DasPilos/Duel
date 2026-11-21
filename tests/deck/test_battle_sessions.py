import copy
import json
import time
import unittest
from types import SimpleNamespace

from client.network import GameClient, ServerError
from deck.server import battles, social
from tests.deck.server_fixtures import create_test_database, drop_test_database, running_server


def _fighter(character_id, name, *, kind=None):
    profile = {
        "id": character_id,
        "name": name,
        "level": 1,
        "type": "warrior",
        "stats": {
            "strength": 2,
            "agility": 2,
            "intuition": 2,
            "wisdom": 2,
            "intellect": 2,
            "harmony": 2,
            "endurance": 2,
        },
        "hp": 100,
        "mp": 20,
    }
    if kind:
        profile["kind"] = kind
    return profile


class TestServerBattleSessions(unittest.TestCase):
    def test_bot_battle_uses_python_card_rules_and_starting_draft(self):
        player = _fighter("test-player-bot-battle", "Игрок")
        bot = _fighter("bot_test-battle", "Бот", kind="bot")

        battle_id = battles.start(player, bot, opponent_is_bot=True)
        state = battles.snapshot(player["id"], battle_id)

        self.assertEqual(state["phase"], "draft")
        self.assertEqual(len(state["table"]), 22)
        self.assertEqual(state["opponent"]["name"], "Бот")
        self.assertNotIn("hand", state["opponent"])

        for card in state["table"][:2]:
            state = battles.act(player["id"], battle_id, "pick_starting", card["key"])

        self.assertEqual(state["phase"], "planning")
        self.assertEqual(state["turn"], 1)
        self.assertEqual(len(state["hand"]), 5)

    def test_invalid_card_action_does_not_change_battle(self):
        player = _fighter("test-invalid-battle-action", "Игрок")
        bot = _fighter("bot_invalid-battle-action", "Бот", kind="bot")
        battle_id = battles.start(player, bot, opponent_is_bot=True)

        with self.assertRaisesRegex(ValueError, "Карты нет на столе"):
            battles.act(player["id"], battle_id, "pick_starting", "missing-card")

        self.assertEqual(battles.snapshot(player["id"], battle_id)["phase"], "draft")

    def test_confirmed_turn_resolves_on_server_and_advances(self):
        player = _fighter("test-turn-battle", "Игрок")
        bot = _fighter("bot_turn-battle", "Бот", kind="bot")
        battle_id = battles.start(player, bot, opponent_is_bot=True)
        state = battles.snapshot(player["id"], battle_id)
        for card in state["table"][:2]:
            state = battles.act(player["id"], battle_id, "pick_starting", card["key"])

        state = battles.act(player["id"], battle_id, "confirm")

        self.assertGreaterEqual(state["turn"], 2)
        self.assertIn(state["phase"], ("draw", "planning", "draft", "result"))

    def test_expired_draft_ignores_late_action_and_completes_automatically(self):
        player = _fighter("test-late-draft-player", "Игрок")
        opponent = _fighter("test-late-draft-opponent", "Соперник")
        battle_id = battles.start(player, opponent)
        state = battles.snapshot(player["id"], battle_id)
        battles._SESSIONS[battle_id]["deadline"] = time.time() - 1

        updated = battles.act(
            player["id"], battle_id, "pick_starting", state["table"][0]["key"],
        )

        self.assertEqual(updated["phase"], "planning")
        self.assertEqual(updated["turn"], 1)

    def test_third_expired_planning_deadline_forfeits_the_battle(self):
        player = _fighter("test-timeout-player", "Игрок")
        opponent = _fighter("test-timeout-opponent", "Соперник")
        battle_id = battles.start(player, opponent)

        for participant_id in (player["id"], opponent["id"]):
            for _ in range(2):
                state = battles.snapshot(participant_id, battle_id)
                battles.act(
                    participant_id, battle_id, "pick_starting",
                    state["table"][0]["key"],
                )

        session = battles._SESSIONS[battle_id]
        self.assertEqual(battles.snapshot(player["id"], battle_id)["phase"], "planning")
        session["timeouts"]["player"] = battles.TURN_TIMEOUTS_BEFORE_SURRENDER - 1
        session["deadline"] = time.time() - 1

        result = battles.snapshot(player["id"], battle_id)

        self.assertEqual(result["phase"], "result")
        self.assertEqual(result["timeout_count"], battles.TURN_TIMEOUTS_BEFORE_SURRENDER)
        self.assertIn(result["outcome"], ("win", "loss"))

    def test_draft_snapshot_lists_only_the_opponents_current_picks(self):
        player = _fighter("test-draft-picks-player", "Игрок")
        opponent = _fighter("test-draft-picks-opponent", "Соперник")
        battle_id = battles.start(player, opponent)
        self.addCleanup(battles._SESSIONS.pop, battle_id, None)
        self.addCleanup(battles._CHARACTER_SESSIONS.pop, player["id"], None)
        self.addCleanup(battles._CHARACTER_SESSIONS.pop, opponent["id"], None)

        state = battles.snapshot(player["id"], battle_id)
        self.assertEqual(state["phase"], "draft")
        self.assertEqual(state["opponent_draft_picks"], [])

        enemy_key = battles.snapshot(opponent["id"], battle_id)["table"][0]["key"]
        battles.act(opponent["id"], battle_id, "pick_starting", enemy_key)
        player_table = battles.snapshot(player["id"], battle_id)["table"]
        player_key = next(card["key"] for card in player_table if card["key"] != enemy_key)
        battles.act(player["id"], battle_id, "pick_starting", player_key)

        self.assertEqual(battles.snapshot(player["id"], battle_id)["opponent_draft_picks"], [enemy_key])
        self.assertEqual(battles.snapshot(opponent["id"], battle_id)["opponent_draft_picks"], [player_key])

        for participant_id in (player["id"], opponent["id"]):
            key = battles.snapshot(participant_id, battle_id)["table"][0]["key"]
            battles.act(participant_id, battle_id, "pick_starting", key)

        self.assertEqual(battles.snapshot(player["id"], battle_id)["phase"], "planning")
        self.assertEqual(battles.snapshot(player["id"], battle_id)["opponent_draft_picks"], [])
        self.assertEqual(battles.snapshot(opponent["id"], battle_id)["opponent_draft_picks"], [])

    def test_redraft_snapshot_lists_only_picks_made_in_the_current_redraft(self):
        battle = SimpleNamespace(
            draft_mode="redraft",
            hands={
                "player": [],
                "enemy": [SimpleNamespace(key="kept-card"), SimpleNamespace(key="new-card")],
            },
            redraft_picks={"player": 0, "enemy": 1},
        )

        self.assertEqual(battles._draft_picks(battle, "enemy"), ["new-card"])
        battle.redraft_picks["enemy"] = 0
        self.assertEqual(battles._draft_picks(battle, "enemy"), [])
        battle.draft_mode = None
        battle.redraft_picks["enemy"] = 1
        self.assertEqual(battles._draft_picks(battle, "enemy"), [])

    def test_last_draft_picks_show_the_opponents_draft_until_the_turn_resolves(self):
        player = _fighter("test-last-picks-player", "Игрок")
        opponent = _fighter("test-last-picks-opponent", "Соперник")
        battle_id = battles.start(player, opponent)
        self.addCleanup(battles._SESSIONS.pop, battle_id, None)
        self.addCleanup(battles._CHARACTER_SESSIONS.pop, player["id"], None)
        self.addCleanup(battles._CHARACTER_SESSIONS.pop, opponent["id"], None)
        self.assertEqual(battles.snapshot(player["id"], battle_id)["opponent_last_draft_picks"], [])

        enemy_picks = []
        player_picks = []
        for _ in range(2):
            enemy_key = battles.snapshot(opponent["id"], battle_id)["table"][0]["key"]
            battles.act(opponent["id"], battle_id, "pick_starting", enemy_key)
            enemy_picks.append(enemy_key)
            player_table = battles.snapshot(player["id"], battle_id)["table"]
            player_key = next(
                card["key"] for card in player_table if card["key"] not in enemy_picks + player_picks
            )
            battles.act(player["id"], battle_id, "pick_starting", player_key)
            player_picks.append(player_key)

        player_view = battles.snapshot(player["id"], battle_id)
        opponent_view = battles.snapshot(opponent["id"], battle_id)
        self.assertEqual(player_view["phase"], "planning")
        self.assertEqual(player_view["opponent_draft_picks"], [])
        self.assertEqual(player_view["opponent_last_draft_picks"], enemy_picks)
        self.assertEqual(opponent_view["opponent_last_draft_picks"], player_picks)

        battles.act(player["id"], battle_id, "confirm")
        self.assertEqual(battles.snapshot(player["id"], battle_id)["opponent_last_draft_picks"], enemy_picks)

        state = battles.act(opponent["id"], battle_id, "confirm")
        self.assertGreaterEqual(state["turn"], 2)
        self.assertEqual(state["opponent_last_draft_picks"], [])
        self.assertEqual(battles.snapshot(player["id"], battle_id)["opponent_last_draft_picks"], [])

    def test_finish_draft_records_each_sides_picks_before_the_deal_changes_hands(self):
        battle = SimpleNamespace(
            draft_mode="starting",
            hands={
                "player": [SimpleNamespace(key="player-pick")],
                "enemy": [SimpleNamespace(key="enemy-pick-1"), SimpleNamespace(key="enemy-pick-2")],
            },
            redraft_picks={"player": 0, "enemy": 0},
        )

        def finish_starting_deal():
            battle.draft_mode = None
            battle.hands["enemy"].append(SimpleNamespace(key="dealt-card"))

        battle.finish_starting_deal = finish_starting_deal
        session = {"battle": battle}

        battles._finish_draft(session)

        self.assertEqual(
            session["last_draft_picks"],
            {"player": ["player-pick"], "enemy": ["enemy-pick-1", "enemy-pick-2"]},
        )
        self.assertIsNone(battle.draft_mode)

    def test_finish_redraft_records_only_the_picks_of_that_redraft(self):
        finished = []
        battle = SimpleNamespace(
            draft_mode="redraft",
            hands={
                "player": [SimpleNamespace(key="kept"), SimpleNamespace(key="new")],
                "enemy": [SimpleNamespace(key="enemy-kept")],
            },
            redraft_picks={"player": 1, "enemy": 0},
            finish_redraft=lambda: finished.append(True),
        )
        session = {"battle": battle}

        battles._finish_draft(session)

        self.assertEqual(session["last_draft_picks"], {"player": ["new"], "enemy": []})
        self.assertEqual(finished, [True])


class TestBattleSnapshotPresentation(unittest.TestCase):
    NEW_FIGHTER_KEYS = ("shield", "statuses", "summons")

    def setUp(self):
        self.player = _fighter("presentation-player", "Игрок")
        self.opponent = _fighter("presentation-opponent", "Противник")
        self.battle_id = battles.start(self.player, self.opponent)
        self.addCleanup(battles._SESSIONS.pop, self.battle_id, None)
        self.addCleanup(battles._CHARACTER_SESSIONS.pop, self.player["id"], None)
        self.addCleanup(battles._CHARACTER_SESSIONS.pop, self.opponent["id"], None)
        self.battle = battles._SESSIONS[self.battle_id]["battle"]

    def _state(self, character_id=None):
        return battles.snapshot(character_id or self.player["id"], self.battle_id)

    def test_fresh_battle_has_empty_presentation_fields(self):
        state = self._state()

        for fighter in (state["fighter"], state["opponent"]):
            self.assertEqual(fighter["shield"], 0)
            self.assertEqual(fighter["statuses"], [])
            self.assertEqual(fighter["summons"], [])

    def test_existing_fighter_fields_are_unchanged(self):
        state = self._state()

        for key in self.NEW_FIGHTER_KEYS:
            self.assertIn(key, state["fighter"])
        existing = {key: value for key, value in state["fighter"].items() if key not in self.NEW_FIGHTER_KEYS}
        self.assertEqual(existing, battles._public_fighter(self.battle.player))
        existing_opponent = {key: value for key, value in state["opponent"].items() if key not in self.NEW_FIGHTER_KEYS}
        self.assertEqual(existing_opponent, battles._public_fighter(self.battle.enemy))

    def test_shield_is_physical_plus_magic_for_each_side(self):
        self.battle.phys_shields["player"] = 4
        self.battle.mage_shields["player"] = 6
        self.battle.mage_shields["enemy"] = 3

        state = self._state()
        enemy_view = self._state(self.opponent["id"])

        self.assertEqual(state["fighter"]["shield"], 10)
        self.assertEqual(state["opponent"]["shield"], 3)
        self.assertEqual(enemy_view["fighter"]["shield"], 3)
        self.assertEqual(enemy_view["opponent"]["shield"], 10)

    def test_buff_statuses_keep_polarity_turns_and_amounts(self):
        self.battle.phys_buffs["player"] = [
            {"remaining": 2, "fresh": False, "damage_percent": 10},
            {"remaining": 1, "fresh": False, "forest_spirit": True, "dodge_percent": 15},
            {"remaining": 99, "fresh": False, "expire_after_turn": True, "outgoing_damage_flat": 4},
            {"remaining": 1, "fresh": False, "entangled": 1, "entangle_source": "enemy_card"},
            {"remaining": 3, "fresh": False, "healing_blocked": True},
        ]

        statuses = self._state()["fighter"]["statuses"]

        self.assertEqual(statuses, [
            {"id": "damage_percent", "positive": True, "turns": 2, "stacks": None, "amount": 10},
            {"id": "dodge_percent", "positive": True, "turns": 1, "stacks": None, "amount": 15},
            {"id": "outgoing_damage_flat", "positive": False, "turns": 1, "stacks": None, "amount": 4},
            {"id": "entangled", "positive": False, "turns": 1, "stacks": None, "amount": 1},
            {"id": "healing_blocked", "positive": False, "turns": 3, "stacks": None, "amount": None},
        ])

    def test_damage_over_time_and_control_statuses_follow_the_banner_order(self):
        self.battle.poisons["player"] = [{"source": "enemy"}, {"source": "enemy"}]
        self.battle.bleeds["player"] = [
            {"damage": 3, "remaining": 2, "source": "enemy"},
            {"damage": 5, "remaining": 4, "source": "enemy"},
        ]
        self.battle.regenerations["player"] = [
            {"heal_per_turn": 6, "remaining": 3, "endurance_heal": 0, "card": "Регенерация", "fresh": False},
        ]
        self.battle.delayed_heals["player"] = [{"amount": 10, "remaining": 2, "card": "Отложенное"}]
        self.battle.delayed_hp_loss["player"] = [{"amount": 7, "remaining": 1, "card": "Полное"}]
        self.battle.mage_stuns["player"] = 2
        self.battle.mage_freeze["player"] = 1
        self.battle.invulnerable["player"] = True
        self.battle.phys_state["player"]["guaranteed_crits"] = 1
        self.battle.phys_state["player"]["no_crit_attacks"] = 2
        self.battle.skip_next_turn["player"] = True

        statuses = self._state()["fighter"]["statuses"]

        self.assertEqual([status["id"] for status in statuses], [
            "poison", "bleed", "regeneration", "delayed_heal", "delayed_hp_loss",
            "stun", "freeze", "invulnerable", "guaranteed_crits", "no_crit_attacks", "skip_turn",
        ])
        by_id = {status["id"]: status for status in statuses}
        self.assertEqual(by_id["poison"], {"id": "poison", "positive": False, "turns": None, "stacks": 2, "amount": None})
        self.assertEqual(by_id["bleed"], {"id": "bleed", "positive": False, "turns": 4, "stacks": None, "amount": 8})
        self.assertEqual(by_id["regeneration"], {"id": "regeneration", "positive": True, "turns": 3, "stacks": None, "amount": 6})
        self.assertEqual(by_id["delayed_heal"], {"id": "delayed_heal", "positive": True, "turns": 2, "stacks": None, "amount": None})
        self.assertEqual(by_id["delayed_hp_loss"], {"id": "delayed_hp_loss", "positive": False, "turns": 1, "stacks": None, "amount": 7})
        self.assertEqual(by_id["stun"], {"id": "stun", "positive": False, "turns": 2, "stacks": None, "amount": None})
        self.assertEqual(by_id["freeze"], {"id": "freeze", "positive": False, "turns": 1, "stacks": None, "amount": None})
        self.assertEqual(by_id["invulnerable"], {"id": "invulnerable", "positive": True, "turns": None, "stacks": None, "amount": None})
        self.assertEqual(by_id["guaranteed_crits"], {"id": "guaranteed_crits", "positive": True, "turns": None, "stacks": 1, "amount": None})
        self.assertEqual(by_id["no_crit_attacks"], {"id": "no_crit_attacks", "positive": False, "turns": None, "stacks": 2, "amount": None})
        self.assertEqual(by_id["skip_turn"], {"id": "skip_turn", "positive": False, "turns": None, "stacks": None, "amount": None})

    def test_mage_statuses_use_ids_stacks_and_polarity(self):
        self.battle.mage_statuses["enemy"] = [
            {"name": "огонь", "remaining": 3, "stacks": 2},
            {"name": "электро", "remaining": 1},
            {"name": "electric_cold_immunity", "remaining": 1},
        ]
        self.battle.mage_damage_bonuses["enemy"] = [{"percent": 15, "remaining": 2}]
        self.battle.mage_clouds["enemy"] = [{"remaining": 2, "damage": 3}]
        self.battle.mage_reactive_blessings["enemy"] = [{"remaining": 1}]

        statuses = self._state()["opponent"]["statuses"]

        self.assertEqual(statuses, [
            {"id": "fire", "positive": False, "turns": 3, "stacks": 2, "amount": None},
            {"id": "electro", "positive": False, "turns": 1, "stacks": 1, "amount": None},
            {"id": "electric_cold_immunity", "positive": True, "turns": 1, "stacks": 1, "amount": None},
            {"id": "mage_damage_bonus", "positive": True, "turns": 2, "stacks": None, "amount": 15},
            {"id": "storm_cloud", "positive": True, "turns": 2, "stacks": None, "amount": None},
            {"id": "reactive_blessing", "positive": True, "turns": 1, "stacks": None, "amount": None},
        ])

    def test_summons_list_living_spirit_then_golems_for_each_side(self):
        self.battle.phys_spirits["player"] = {"hp": 9, "max_hp": 12, "remaining": 2}
        self.battle.mage_golems["player"] = [
            {"name": "Голем земли", "hp": 0, "max_hp": 16},
            {"name": "Голем земли", "hp": 11, "max_hp": 16},
        ]
        self.battle.phys_spirits["enemy"] = {"hp": 4, "max_hp": 10}

        state = self._state()

        self.assertEqual(state["fighter"]["summons"], [
            {"kind": "spirit", "name": "Лесной дух", "hp": 9, "max_hp": 12, "turns": 2},
            {"kind": "golem", "name": "Голем земли", "hp": 11, "max_hp": 16, "turns": None},
        ])
        self.assertEqual(state["opponent"]["summons"], [
            {"kind": "spirit", "name": "Лесной дух", "hp": 4, "max_hp": 10, "turns": None},
        ])
        self.assertEqual(self._state(self.opponent["id"])["opponent"]["summons"], state["fighter"]["summons"])

    def test_dead_spirit_is_not_listed(self):
        self.battle.phys_spirits["player"] = {"hp": 0, "max_hp": 12, "remaining": 1}

        self.assertEqual(self._state()["fighter"]["summons"], [])

    def test_snapshot_does_not_change_battle_state_and_is_json_serializable(self):
        self.battle.phys_buffs["player"] = [{"remaining": 2, "fresh": False, "damage_percent": 10}]
        self.battle.poisons["player"] = [{"source": "enemy"}]
        self.battle.phys_spirits["player"] = {"hp": 9, "max_hp": 12, "remaining": 2}
        self.battle.phys_shields["player"] = 4
        watched = [
            self.battle.phys_buffs, self.battle.poisons, self.battle.phys_spirits,
            self.battle.phys_shields, self.battle.mage_shields,
        ]
        before = copy.deepcopy(watched)

        state = self._state()
        self._state(self.opponent["id"])

        self.assertEqual(copy.deepcopy(watched), before)
        json.dumps(state, allow_nan=False)


class TestBattleHttpApi(unittest.TestCase):
    def setUp(self):
        with battles._LOCK:
            battles._SESSIONS.clear()
            battles._CHARACTER_SESSIONS.clear()
        self.database = create_test_database()

    def tearDown(self):
        drop_test_database(self.database)
        with battles._LOCK:
            battles._SESSIONS.clear()
            battles._CHARACTER_SESSIONS.clear()

    def test_accepted_duel_can_start_and_both_clients_read_shared_state(self):
        with running_server(self.database) as client:
            client.register("battle-api-user", "password")
            client.login("battle-api-user", "password")
            sender = client.create_character("BattleSender", "warrior")
            target_client = GameClient(client.base_url)
            target_client.register("battle-api-target", "password")
            target_client.login("battle-api-target", "password")
            target = target_client.create_character("BattleTarget", "warrior")
            offer = social.add_duel_offer(
                {"character_id": sender["id"], "name": sender["name"]},
                target["id"],
                "backyard",
            )
            social.respond_duel_offer(target["id"], offer["id"], True)

            started = target_client._request(
                "POST",
                "/api/deck/battle/start",
                {"character_id": target["id"], "offer_id": offer["id"]},
                authenticated=True,
            )["battle"]
            active = client._request(
                "GET",
                f"/api/deck/battle/active?character_id={sender['id']}",
                authenticated=True,
            )["battle"]

        self.assertEqual(started["phase"], "draft")
        self.assertEqual(started["battle_id"], active["battle_id"])
        self.assertEqual(active["side"], "enemy")

    def test_active_battle_is_restored_from_database_after_server_rebind(self):
        with running_server(self.database) as client:
            client.register("battle-persist-user", "password")
            client.login("battle-persist-user", "password")
            sender = client.create_character("PersistSender", "warrior")
            target_client = GameClient(client.base_url)
            target_client.register("battle-persist-target", "password")
            target_client.login("battle-persist-target", "password")
            target = target_client.create_character("PersistTarget", "warrior")
            offer = social.add_duel_offer(
                {"character_id": sender["id"], "name": sender["name"]},
                target["id"],
                "backyard",
            )
            social.respond_duel_offer(target["id"], offer["id"], True)
            started = target_client._request(
                "POST",
                "/api/deck/battle/start",
                {"character_id": target["id"], "offer_id": offer["id"]},
                authenticated=True,
            )["battle"]
            selected_key = started["table"][0]["key"]
            target_client._request(
                "POST",
                "/api/deck/battle/action",
                {
                    "character_id": target["id"],
                    "battle_id": started["battle_id"],
                    "action": "pick_starting",
                    "card_key": selected_key,
                },
                authenticated=True,
            )

            from deck.server.main import bind_database

            bind_database(None)
            bind_database(self.database)
            restored = target_client._request(
                "GET",
                f"/api/deck/battle/active?character_id={target['id']}",
                authenticated=True,
            )["battle"]
            second_key = restored["table"][0]["key"]
            continued = target_client._request(
                "POST",
                "/api/deck/battle/action",
                {
                    "character_id": target["id"],
                    "battle_id": restored["battle_id"],
                    "action": "pick_starting",
                    "card_key": second_key,
                },
                authenticated=True,
            )["battle"]

        self.assertEqual(restored["battle_id"], started["battle_id"])
        self.assertEqual(restored["phase"], "draft")
        self.assertIn(selected_key, [card["key"] for card in restored["hand"]])
        self.assertNotIn(selected_key, [card["key"] for card in restored["table"]])
        self.assertIn(second_key, [card["key"] for card in continued["hand"]])

    def test_finished_battle_saves_both_players_and_releases_active_session(self):
        with running_server(self.database) as client:
            client.register("battle-finish-user", "password")
            client.login("battle-finish-user", "password")
            sender = client.create_character("FinishSender", "warrior")
            target_client = GameClient(client.base_url)
            target_client.register("battle-finish-target", "password")
            target_client.login("battle-finish-target", "password")
            target = target_client.create_character("FinishTarget", "warrior")
            offer = social.add_duel_offer(
                {"character_id": sender["id"], "name": sender["name"]},
                target["id"],
                "backyard",
            )
            social.respond_duel_offer(target["id"], offer["id"], True)
            battle_id = target_client._request(
                "POST",
                "/api/deck/battle/start",
                {"character_id": target["id"], "offer_id": offer["id"]},
                authenticated=True,
            )["battle"]["battle_id"]

            engine = battles._SESSIONS[battle_id]["battle"]
            engine.enemy.hp = 0
            outcome = engine.outcome()
            session = battles._SESSIONS[battle_id]
            session["finished"] = True
            session["outcome"] = outcome
            result = target_client._request(
                "POST",
                "/api/deck/battle/finish",
                {"character_id": target["id"], "battle_id": battle_id},
                authenticated=True,
            )
            sender_character = self.database.get_character_for_battle(sender["id"])["character"]
            active = target_client._request(
                "GET",
                f"/api/deck/battle/active?character_id={target['id']}",
                authenticated=True,
            )["battle"]

        self.assertEqual(result["outcome"], "win")
        self.assertIsNotNone(result["battle_archive_id"])
        self.assertLess(sender_character["xp"], sender["xp"] + 100)
        self.assertIsNone(active)

    def test_battle_actions_require_an_accepted_offer_session(self):
        with running_server(self.database) as client:
            client.register("battle-api-reject", "password")
            client.login("battle-api-reject", "password")
            character = client.create_character("Без заявки", "warrior")
            with self.assertRaisesRegex(ServerError, "Бой не найден"):
                client._request(
                    "POST",
                    "/api/deck/battle/action",
                    {
                        "character_id": character["id"],
                        "battle_id": "not-a-session",
                        "action": "confirm",
                    },
                    authenticated=True,
                )

    def test_ready_group_offer_starts_a_server_managed_pair_match(self):
        with running_server(self.database) as first_client:
            clients = []
            characters = []
            for index in range(6):
                client = first_client if index == 0 else GameClient(first_client.base_url)
                clients.append(client)
                username = f"group-user-{index}"
                client.register(username, "password")
                client.login(username, "password")
                character = client.create_character(f"GroupHero{index}", "warrior")
                characters.append(character)

            offer = first_client._request(
                "POST",
                "/api/deck/social/group-battles",
                {
                    "character_id": characters[0]["id"],
                    "location": "backyard",
                    "ttl": 300,
                    "max_participants": 6,
                },
                authenticated=True,
            )["offer"]
            for index in range(1, 6):
                clients[index]._request(
                    "POST",
                    f"/api/deck/social/group-battles/{offer['id']}/join",
                    {"character_id": characters[index]["id"], "location": "backyard"},
                    authenticated=True,
                )

            state = first_client._request(
                "POST",
                "/api/deck/battle/start",
                {"character_id": characters[0]["id"], "group_id": offer["id"]},
                authenticated=True,
            )["battle"]
            pair_states = [state]
            for index in range(1, len(characters)):
                pair_states.append(clients[index]._request(
                    "POST",
                    "/api/deck/battle/start",
                    {
                        "character_id": characters[index]["id"],
                        "group_id": offer["id"],
                    },
                    authenticated=True,
                )["battle"])

            self.assertEqual(state["group_id"], offer["id"])
            self.assertEqual(state["phase"], "draft")
            battle_ids = {pair["battle_id"] for pair in pair_states}
            self.assertEqual(len(battle_ids), 3)
            participants = []
            for battle_id in battle_ids:
                session = battles._SESSIONS[battle_id]
                self.assertEqual(len(session["participants"]), 2)
                self.assertEqual(session["group_id"], offer["id"])
                participants.extend(session["participants"])
            self.assertCountEqual(participants, [str(character["id"]) for character in characters])


if __name__ == "__main__":
    unittest.main()
