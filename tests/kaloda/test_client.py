import unittest

from client.session import OnlineSession
from kaloda.client import KalodaClient, KalodaSession
from kaloda.combat.fighter import Fighter

RESPONSE = {
    "items": ["item"], "cards": ["card"], "collection": ["owned"], "decks": ["deck"],
    "deck": {"id": 1}, "reward": ["reward"], "character": {"id": 7, "talents": {"3": "x"}},
    "opponents": ["bot"], "opponent": {"id": "bot_1"}, "offers": ["offer"], "terrain": {"map_version": 5},
    "drinks": ["ale"], "game": "kaloda",
}


class RecordingClient(KalodaClient):
    def __init__(self):
        super().__init__("http://server")
        self.token = "token"
        self.calls = []

    def _request(self, method, path, payload=None, authenticated=False, timeout=None):
        self.calls.append((method, path, payload, authenticated, timeout))
        return dict(RESPONSE)


def _last(client):
    return client.calls[-1]


class TestKalodaClient(unittest.TestCase):
    def setUp(self):
        self.client = RecordingClient()

    def test_every_game_call_is_authenticated_and_lives_under_the_kaloda_prefix(self):
        client = self.client
        calls = (
            lambda: client.get_game_info(),
            lambda: client.get_supplies_shop_catalog(),
            lambda: client.buy_supplies_item(7, 4),
            lambda: client.get_card_shop_catalog(),
            lambda: client.buy_card(7, "universal_trap"),
            lambda: client.get_dungeon_card_shop_catalog(),
            lambda: client.buy_dungeon_card(7, "universal_bonebreaker"),
            lambda: client.claim_dungeon_treasure(7, "req"),
            lambda: client.claim_npc_kill_xp(7, "kobold", ["kobold"], "req"),
            lambda: client.claim_guild_quest_reward(7, "kill_kobold", "req"),
            lambda: client.list_item_catalog(),
            lambda: client.choose_character_talent(7, 3, "x"),
            lambda: client.get_card_collection(7),
            lambda: client.get_decks(7),
            lambda: client.create_deck(7, "Колода", {"a": 1}),
            lambda: client.delete_deck(7, 2),
            lambda: client.award_battle_card(7, ["a"]),
            lambda: client.report_battle_result(7, "win", 1, 50, 10),
            lambda: client.list_opponents(),
            lambda: client.save_opponent({"id": "bot_1"}),
            lambda: client.social_snapshot("backyard", 7),
            lambda: client.offer_duel(7, "backyard", 9),
            lambda: client.create_duel_application(7, "backyard"),
            lambda: client.cancel_duel_application(7, "backyard"),
            lambda: client.duel_board("backyard"),
            lambda: client.list_duel_offers("backyard"),
            lambda: client.respond_duel_offer(7, 5, True),
            lambda: client.list_group_battles(),
            lambda: client.create_group_battle(7),
            lambda: client.join_group_battle(5, 7),
            lambda: client.leave_group_battle(5, 7),
        )
        for index, call in enumerate(calls):
            with self.subTest(call=index):
                call()
                _method, path, _payload, authenticated, _timeout = _last(client)
                self.assertTrue(path.startswith("/api/kaloda/"), path)
                self.assertTrue(authenticated)

    def test_catalog_calls_unwrap_the_server_payload(self):
        self.assertEqual(self.client.get_card_shop_catalog(), ["card"])
        self.assertEqual(self.client.get_supplies_shop_catalog(), ["item"])
        self.assertEqual(self.client.list_item_catalog(), ["item"])
        self.assertEqual(self.client.get_card_collection(7), ["owned"])
        self.assertEqual(self.client.get_decks(7), ["deck"])
        self.assertEqual(self.client.create_deck(7, "Колода", {}), {"id": 1})
        self.assertEqual(self.client.list_duel_offers("backyard"), ["offer"])
        self.assertEqual(self.client.choose_character_talent(7, 3, "x"), RESPONSE["character"])

    def test_request_payloads_keep_the_server_contract(self):
        self.client.buy_card(7, "universal_trap")
        self.assertEqual(_last(self.client)[:3], ("POST", "/api/kaloda/card-shop/buy",
                                                  {"character_id": 7, "card_key": "universal_trap"}))
        self.client.claim_npc_kill_xp(7, "dungeon_room_1", ("skeleton",), "req")
        self.assertEqual(_last(self.client)[2], {
            "character_id": 7, "encounter_id": "dungeon_room_1",
            "defeated_types": ["skeleton"], "request_id": "req",
        })
        self.client.delete_deck(7, 2)
        self.assertEqual(_last(self.client)[:3], ("DELETE", "/api/kaloda/decks/2", {"character_id": 7}))

    def test_battle_report_adds_opponent_fields_only_for_players(self):
        self.client.report_battle_result(7, "win", 2, 50, 10)
        self.assertNotIn("opponent_id", _last(self.client)[2])

        self.client.report_battle_result(7, "loss", 2, 50, 10, opponent_id=9, opponent_hp=3, opponent_mp=1,
                                         battle_record={"turns": 3}, battle_id="b1")
        payload = _last(self.client)[2]
        self.assertEqual((payload["opponent_id"], payload["opponent_hp"], payload["opponent_mp"]), (9, 3, 1))
        self.assertEqual((payload["battle_id"], payload["battle_record"]), ("b1", {"turns": 3}))

    def test_social_snapshot_passes_position_only_when_given(self):
        self.client.social_snapshot("backyard", 7)
        self.assertEqual(_last(self.client)[1], "/api/kaloda/social/snapshot?location=backyard&character_id=7")

        self.client.social_snapshot("backyard", 7, position={"position_x": 1, "ignored": 2})
        self.assertIn("position_x=1", _last(self.client)[1])
        self.assertNotIn("ignored", _last(self.client)[1])

    def test_map_terrain_is_requested_with_a_longer_timeout(self):
        terrain = self.client.get_map_terrain()

        self.assertEqual(terrain, {"map_version": 5})
        self.assertEqual(_last(self.client)[1], "/api/kaloda/map/terrain")
        self.assertGreaterEqual(_last(self.client)[4], 15)

    def test_server_introduces_itself_as_kaloda(self):
        self.assertEqual(self.client.get_game_info()["game"], "kaloda")
        self.assertEqual(_last(self.client)[:2], ("GET", "/api/kaloda/info"))

    def test_tavern_drinks_use_the_shared_endpoints(self):
        self.assertEqual(self.client.list_drinks(), ["ale"])
        self.assertEqual(_last(self.client)[:2], ("GET", "/api/drinks"))
        self.assertTrue(_last(self.client)[3])

        self.client.buy_drink(7, 2)
        self.assertEqual(_last(self.client)[:3], (
            "POST", "/api/character/buy_drink", {"character_id": 7, "drink_id": 2}))
        self.assertTrue(_last(self.client)[3])

    def test_base_item_lookup_by_ids_is_not_overridden(self):
        self.client.get_item_catalog([3, 4])

        self.assertEqual(_last(self.client)[1], "/api/items/catalog?ids=3,4")


def _session():
    session = KalodaSession("user", "pass", "", "http://server")
    session.client = RecordingClient()
    session.character = {"id": 7, "name": "Герой"}
    return session


class TestKalodaSession(unittest.TestCase):
    def test_adopt_keeps_login_state_but_swaps_in_the_game_client(self):
        lobby = OnlineSession("user", "pass", "", "http://world:9000")
        lobby.client.token = "abc"
        lobby.character = {"id": 7}

        adopted = KalodaSession.adopt(lobby)

        self.assertIsInstance(adopted.client, KalodaClient)
        self.assertEqual((adopted.client.base_url, adopted.client.token), ("http://world:9000", "abc"))
        self.assertEqual((adopted.username, adopted.character), ("user", {"id": 7}))
        self.assertIsNot(adopted.client, lobby.client)

    def test_new_session_uses_the_game_client(self):
        self.assertIsInstance(KalodaSession("user", "pass", "", "http://server").client, KalodaClient)

    def test_character_scoped_wrappers_use_the_current_character(self):
        session = _session()

        session.get_decks()
        self.assertEqual(_last(session.client)[1], "/api/kaloda/decks/7")
        session.create_deck("Колода", {"a": 1})
        self.assertEqual(_last(session.client)[2]["character_id"], 7)
        session.character = None
        self.assertEqual(session.get_decks(), [])
        self.assertIsNone(session.create_deck("x", {}))

    def test_report_battle_result_syncs_the_fighter_with_the_server_character(self):
        session = _session()
        fighter = Fighter("Герой")
        stats = dict(fighter.stats, strength=fighter.stats["strength"] + 1)
        server_character = {"id": 7, "level": 2, "xp": 5, "stat_points": 3, "hp": 80, "mp": 20, "stats": stats}
        session.client.report_battle_result = lambda *args, **kwargs: {
            "character": server_character, "currency": {"coins": 120},
        }

        result = session.report_battle_result(fighter, "win", 1, opponent={"id": "bot_3"})

        self.assertEqual(result["currency"]["coins"], 120)
        self.assertEqual((fighter.level, fighter.xp, fighter.stat_points), (2, 5, 3))
        self.assertEqual(fighter.stats["strength"], stats["strength"])
        self.assertEqual(session.character, server_character)

    def test_disconnect_saves_the_fighter_before_leaving(self):
        session = _session()
        fighter = Fighter("Герой")

        session.disconnect(fighter)

        methods_and_paths = [(method, path) for method, path, *_ in session.client.calls]
        self.assertEqual(methods_and_paths, [
            ("PUT", "/api/characters/7"),
            ("POST", "/api/sessions/disconnect"),
        ])
        self.assertIsNone(session.character)

    def test_refresh_equipment_state_copies_server_inventory_into_the_character(self):
        session = _session()
        session.client.get_inventory = lambda character_id: {"equipment": {"weapon": 3}, "bonuses": {"hp": 5}}

        session.refresh_equipment_state()

        self.assertEqual(session.character["equipment"], {"weapon": 3})
        self.assertEqual(session.character["equipment_bonuses"], {"hp": 5})

    def test_duel_actions_refresh_the_character_first(self):
        session = _session()

        session.offer_duel("backyard", 9)

        self.assertEqual(session.client.calls[0][:2], ("GET", "/api/characters/7"))
        self.assertEqual(session.client.calls[1][1], "/api/kaloda/social/duel-offers")


if __name__ == "__main__":
    unittest.main()
