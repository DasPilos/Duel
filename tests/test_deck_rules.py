import random
import unittest

from combat.card_battle import CardBattle
from combat.card_database import (
    BASE_CARDS,
    DECK_SIZE,
    PROFESSION_CARD_GROUPS,
    card_allowed_for,
    cards_for_type,
    deck_validation_error,
    is_mage_profession,
    load_cards,
)
from combat.fighter import Fighter
from client.network import ServerError
from tests.fixtures import create_test_database, drop_test_database, running_server

PROFESSIONS = ("warrior", "archer", "assassin", "battle_mage", "support_mage", "harmonist")


def _play_battle(attacker_type, defender_type, seed):
    rng = random.Random(seed)
    player = Fighter("A", 5, profession_type=attacker_type)
    enemy = Fighter("B", 5, profession_type=defender_type)
    battle = CardBattle(
        player,
        enemy,
        cards=cards_for_type(attacker_type),
        enemy_cards=cards_for_type(defender_type),
        rng=rng,
    )
    battle.mage_mode = is_mage_profession(attacker_type) or is_mage_profession(defender_type)
    while len(battle.hands["player"]) < battle.STARTING_PICK_LIMIT:
        for side in ("player", "enemy"):
            table = battle.table_for(side)
            battle.choose_starting_card(side, table[rng.randrange(len(table))].key)
    battle.finish_starting_deal()
    while not battle.is_over() and battle.turn < 40:
        for side in ("player", "enemy"):
            for card in list(battle.hands[side]):
                battle.select_card(side, card.key)
            battle.confirm_selection(side)
        battle.resolve_turn()
        if not battle.is_over():
            battle.start_next_turn()
    return battle


class CardPoolTests(unittest.TestCase):
    def test_loaded_cards_match_code_definitions(self):
        loaded = {card.key: card for card in load_cards()}
        self.assertEqual(set(loaded), {card.key for card in BASE_CARDS})
        for card in BASE_CARDS:
            self.assertEqual(loaded[card.key], card, card.key)

    def test_each_class_gets_only_its_own_cards(self):
        expected = {"warrior": "warrior_", "archer": "archer_", "assassin": "assassin_"}
        for profession in PROFESSIONS:
            cards = cards_for_type(profession)
            self.assertGreaterEqual(len(cards), DECK_SIZE, profession)
            prefix = expected.get(profession, "mage_")
            self.assertTrue(all(card.key.startswith(prefix) for card in cards), profession)

    def test_unknown_class_gets_no_cards(self):
        self.assertEqual(cards_for_type("unknown"), [])
        self.assertNotIn("unknown", PROFESSION_CARD_GROUPS)

    def test_resource_matches_class(self):
        resources = {"warrior": "rage", "archer": "accuracy", "assassin": "concentration"}
        for profession in PROFESSIONS:
            fighter = Fighter("X", 1, profession_type=profession)
            for card in cards_for_type(profession):
                self.assertEqual(card.resource_type, resources.get(profession, "mana"), card.key)
                self.assertEqual(fighter.unique_resource_type, card.resource_type)


class DeckValidationTests(unittest.TestCase):
    def test_valid_deck_for_each_class(self):
        for profession in PROFESSIONS:
            cards = cards_for_type(profession)
            # Колода из всех обычных карт + ульты, пока не наберётся 22
            regular = [card.key for card in cards if not card.effect_data.get("ultimate")]
            ultimates = [card.key for card in cards if card.effect_data.get("ultimate")]
            deck = (regular + ultimates)[:DECK_SIZE]
            self.assertEqual(deck_validation_error(deck, profession), "", profession)

    def test_foreign_card_rejected(self):
        deck = [card.key for card in cards_for_type("warrior")][:DECK_SIZE - 1] + ["mage_flash"]
        self.assertIn("\u0447\u0443\u0436\u043e\u0433\u043e \u043a\u043b\u0430\u0441\u0441\u0430", deck_validation_error(deck, "warrior"))

    def test_wrong_size_and_duplicates_rejected(self):
        keys = [card.key for card in cards_for_type("archer")]
        self.assertIn("\u0440\u043e\u0432\u043d\u043e", deck_validation_error(keys[:5], "archer"))
        self.assertIn("\u043f\u043e\u0432\u0442\u043e\u0440", deck_validation_error(keys[:21] + keys[:1], "archer"))

    def test_cards_outside_collection_rejected(self):
        keys = [card.key for card in cards_for_type("archer")][:DECK_SIZE]
        self.assertIn("\u043a\u043e\u043b\u043b\u0435\u043a\u0446\u0438\u0438", deck_validation_error(keys, "archer", owned_keys=set(keys[1:])))

    def test_ultimate_needs_five_cards_of_its_style(self):
        cards = cards_for_type("battle_mage")
        fire_ultimate = next(card for card in cards if card.key == "mage_pyromania")
        others = [
            card.key for card in cards
            if not card.group_name.endswith("\u041e\u0433\u043e\u043d\u044c") and not card.effect_data.get("ultimate")
        ]
        fire = [card.key for card in cards if card.group_name.endswith("\u041e\u0433\u043e\u043d\u044c") and not card.effect_data.get("ultimate")]
        deck = [fire_ultimate.key] + fire[:4] + others[: DECK_SIZE - 5]
        self.assertIn("\u0423\u043b\u044c\u0442\u0430", deck_validation_error(deck, "battle_mage"))
        self.assertTrue(card_allowed_for(fire_ultimate, "harmonist"))


class BattleSmokeTests(unittest.TestCase):
    def test_every_class_pair_plays_without_errors(self):
        for attacker in PROFESSIONS:
            for defender in PROFESSIONS:
                for seed in range(3):
                    with self.subTest(attacker=attacker, defender=defender, seed=seed):
                        battle = _play_battle(attacker, defender, seed)
                        player_keys = {card.key for card in battle.hands["player"] + battle.discard}
                        self.assertTrue(all(key in {c.key for c in cards_for_type(attacker)} for key in player_keys))

    def test_mana_spent_once(self):
        player = Fighter("A", 5, profession_type="battle_mage")
        enemy = Fighter("B", 5, profession_type="warrior")
        battle = CardBattle(player, enemy, cards=[], rng=random.Random(1))
        battle.mage_mode = True
        card = next(card for card in cards_for_type("battle_mage") if card.key == "mage_fireball")
        player.mp = 30
        battle._resolve_card("player", card)
        self.assertEqual(player.mp, 30 - card.resource_cost)

    def test_two_selected_cards_cannot_overspend_resource(self):
        player = Fighter("A", 1, profession_type="warrior")
        enemy = Fighter("B", 1, profession_type="warrior")
        battle = CardBattle(player, enemy, cards=[], rng=random.Random(1))
        by_key = {card.key: card for card in cards_for_type("warrior")}
        hack, cleave = by_key["warrior_hack"], by_key["warrior_valen_cleave"]
        player.unique_resource_current = hack.resource_cost + cleave.resource_cost - 1
        battle.hands["player"] = [hack, cleave]
        self.assertTrue(battle.select_card("player", hack.key))
        self.assertFalse(battle.select_card("player", cleave.key))

    def test_profile_sets_profession(self):
        fighter = Fighter("A", 3)
        fighter.set_profession("archer")
        self.assertEqual(fighter.unique_resource_type, "accuracy")
        fighter.set_profession("mage")
        self.assertEqual(fighter.unique_resource_type, "mana")


class DeckApiTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()

    def tearDown(self):
        drop_test_database(self.database)

    def test_class_cards_granted_and_deck_rules_enforced_by_server(self):
        with running_server(self.database) as client:
            client.register("deckuser", "password")
            client.login("deckuser", "password")
            character = client.create_character("\u041b\u0443\u0447\u043d\u0438\u043a", "archer")
            collection = client.get_card_collection(character["id"])
            keys = [entry["key"] for entry in collection]
            self.assertEqual(sorted(keys), sorted(card.key for card in cards_for_type("archer")))
            # \u041f\u043e\u0432\u0442\u043e\u0440\u043d\u044b\u0439 \u0437\u0430\u043f\u0440\u043e\u0441 \u043d\u0435 \u0434\u0443\u0431\u043b\u0438\u0440\u0443\u0435\u0442 \u0441\u0442\u0430\u0440\u0442\u043e\u0432\u044b\u0439 \u043d\u0430\u0431\u043e\u0440
            self.assertEqual(len(client.get_card_collection(character["id"])), len(keys))

            with self.assertRaisesRegex(ServerError, "\u0447\u0443\u0436\u043e\u0433\u043e \u043a\u043b\u0430\u0441\u0441\u0430"):
                client.create_deck(character["id"], "\u0427\u0443\u0436\u0430\u044f", keys[:DECK_SIZE - 1] + ["warrior_slash"])
            deck = client.create_deck(character["id"], "\u0421\u0432\u043e\u044f", keys[:DECK_SIZE])
            self.assertEqual(len(deck["cards"]), DECK_SIZE)


if __name__ == "__main__":
    unittest.main()
