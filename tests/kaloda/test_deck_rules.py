import random
import unittest
from unittest.mock import patch

import pygame

from kaloda.combat.card_battle import CardBattle
from kaloda.combat.card_database import (
    BASE_CARDS,
    DECK_SIZE,
    INACTIVE_WARRIOR_CARD_KEYS,
    PROFESSION_CARD_GROUPS,
    card_allowed_for,
    class_cards_for_type,
    cards_for_type,
    deck_validation_error,
    expand_deck_card_keys,
    is_mage_profession,
    is_universal_card,
    load_cards,
)
from kaloda.combat.fighter import Fighter
from client.network import ServerError
from kaloda.ui.character_profile_overlay import CharacterProfileOverlay
from kaloda.ui.card_tooltip import card_tooltip_lines
from kaloda.ui.deck_selection_panel import DeckSelectionPanel
from tests.kaloda.server_fixtures import create_test_database, drop_test_database, running_server

PROFESSIONS = ("warrior", "archer", "assassin", "mage", "necromancer")


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
                if battle.remaining_card_slots(side) <= 0:
                    break
                if battle.can_select(side, card):
                    battle.select_card(side, card.key)
            battle.confirm_selection(side)
        battle.resolve_turn()
        if battle.is_over():
            break
        battle.begin_next_turn()
        for draw_side in ("player", "enemy"):
            draw_choices = battle.prepare_draw_choice(draw_side)
            if draw_choices:
                draw_choice = draw_choices[rng.randrange(len(draw_choices))]
                battle.choose_draw_card(draw_side, draw_choice.key)
    return battle


class CardPoolTests(unittest.TestCase):
    def test_loaded_cards_match_code_definitions(self):
        loaded = {card.key: card for card in load_cards()}
        self.assertEqual(set(loaded), {card.key for card in BASE_CARDS})
        for card in BASE_CARDS:
            self.assertEqual(loaded[card.key], card, card.key)

    def test_each_class_gets_only_its_own_cards(self):
        expected = {
            "warrior": "warrior_",
            "archer": "archer_",
            "assassin": "assassin_",
            "necromancer": "necromancer_",
        }
        for profession in PROFESSIONS:
            cards = cards_for_type(profession)
            self.assertGreaterEqual(len(cards), DECK_SIZE, profession)
            prefix = expected.get(profession, "mage_")
            self.assertTrue(all(
                is_universal_card(card) or card.key.startswith(prefix)
                for card in cards
            ), profession)

    def test_warrior_pool_is_valentine_style_with_requested_duplicates(self):
        cards = class_cards_for_type("warrior")
        self.assertEqual(len(cards), DECK_SIZE)
        self.assertTrue(all(card.group_name == "Боец: Стиль Валентайна" for card in cards))
        self.assertFalse(any(card.key in INACTIVE_WARRIOR_CARD_KEYS for card in cards))
        names = [card.name for card in cards]
        for name in (
            "Удар Валентайна", "Целительный выпад", "Слабость - сила",
            "Бросок кинжала", "Могильная стужа", "Благоволение крови", "Узы охотника",
        ):
            with self.subTest(card=name):
                self.assertEqual(names.count(name), 2)

    def test_unknown_class_gets_no_cards(self):
        self.assertEqual(cards_for_type("unknown"), [])
        self.assertNotIn("unknown", PROFESSION_CARD_GROUPS)

    def test_resource_matches_class(self):
        resources = {"warrior": "rage", "archer": "accuracy", "assassin": "concentration"}
        for profession in PROFESSIONS:
            fighter = Fighter("X", 1, profession_type=profession)
            for card in cards_for_type(profession):
                if is_universal_card(card):
                    # Универсальные карты тратят текущий ресурс класса, а часть из них — ману.
                    self.assertIn(card.resource_type, ("unique", "mana"), card.key)
                elif profession == "necromancer":
                    self.assertEqual(card.resource_type, "unique", card.key)
                else:
                    self.assertEqual(card.resource_type, resources.get(profession, "mana"), card.key)
                    self.assertEqual(fighter.unique_resource_type, card.resource_type)

    def test_universal_card_spends_each_professions_current_resource(self):
        card = next(card for card in cards_for_type("warrior") if card.key == "universal_trap")
        for profession in PROFESSIONS:
            fighter = Fighter("X", 1, profession_type=profession)
            fighter.mp = 100
            fighter.unique_resource_current = 100
            battle = CardBattle(fighter, Fighter("Enemy", 1, profession_type="warrior"), cards=[])
            battle.hands["player"] = [card]
            with self.subTest(profession=profession):
                self.assertTrue(battle.can_select("player", card))
                battle._spend_points("player", card)
                if fighter.unique_resource_type == "mana":
                    self.assertEqual(fighter.mp, 100 - card.resource_cost)
                else:
                    self.assertEqual(
                        fighter.unique_resource_current, 100 - card.resource_cost
                    )


class DeckValidationTests(unittest.TestCase):
    def test_necromancer_has_full_twenty_two_card_class_deck(self):
        cards = cards_for_type("necromancer")
        class_cards = class_cards_for_type("necromancer")
        universal_cards = [card for card in cards if is_universal_card(card)]

        self.assertEqual(len(class_cards), DECK_SIZE)
        self.assertEqual(len(cards), len(class_cards) + len(universal_cards))
        self.assertTrue(all(card.group_name.startswith("Некромант:") for card in class_cards))
        self.assertFalse(any(card.group_name.startswith("Магия:") for card in class_cards))
        costs = {card.key: card.resource_cost for card in class_cards}
        self.assertEqual(costs["necromancer_familiar"], 14)
        self.assertEqual(costs["necromancer_lokrif"], 24)
        self.assertEqual(costs["necromancer_bone_hero"], 43)
        self.assertEqual(costs["necromancer_spirit"], 20)
        self.assertEqual(costs["necromancer_lyrk"], 15)
        self.assertEqual(costs["necromancer_grave_zink"], 38)
        self.assertEqual(costs["necromancer_bone_dragon"], 70)

    def test_necromancer_tooltip_explains_green_flame_and_resource_cost(self):
        card = next(
            card for card in cards_for_type("necromancer")
            if card.key == "necromancer_dead_god_curse"
        )

        lines = card_tooltip_lines(card)

        self.assertTrue(any("2% текущего HP" in line for line in lines))
        self.assertTrue(any("25 некротизма" in line for line in lines))

    def test_deck_panel_can_select_multiple_owned_copies(self):
        cards = cards_for_type("warrior")
        collection = [
            {
                "key": card.key,
                "name": card.name,
                "quantity": 2 if index == 0 else 1,
            }
            for index, card in enumerate(cards)
        ]
        panel = DeckSelectionPanel(None, None, card_loader=lambda: collection)
        panel.open([], "warrior")
        panel.handle_click(panel.create_button.center)
        panel.handle_click(panel.element_rects[0].center)

        for index in range(21):
            panel.handle_click(panel.card_rects[index].center)
        panel.handle_click(panel.card_rects[0].center)
        self.assertEqual(len(panel.selected_cards), DECK_SIZE)
        self.assertEqual(panel.selected_cards.count(cards[0].key), 2)

        panel.handle_click(panel.card_rects[0].center)
        self.assertEqual(len(panel.selected_cards), DECK_SIZE - 1)
        self.assertEqual(panel.selected_cards.count(cards[0].key), 1)


class DeckCreationFlowTests(unittest.TestCase):
    def setUp(self):
        pygame.font.init()

    @classmethod
    def setUpClass(cls):
        pygame.font.init()

    @staticmethod
    def _collection(profession):
        return [
            {"key": card.key, "name": card.name, "quantity": 1}
            for card in cards_for_type(profession)
        ]

    def test_mage_elements_are_offered_before_cards(self):
        panel = DeckSelectionPanel(None, None, card_loader=lambda: self._collection("mage"))
        panel.open([], "mage")
        panel.handle_click(panel.create_button.center)
        self.assertEqual(panel.view, "elements")
        self.assertEqual(len(panel.element_rects), 7)
        self.assertIn("Тактика", panel.elements)
        self.assertNotIn("Прочее", panel.elements)

    def test_hovering_a_deck_card_draws_its_effect_description(self):
        pygame.init()
        pygame.display.set_mode((1920, 1080), pygame.HIDDEN)
        try:
            collection = self._collection("mage")
            panel = DeckSelectionPanel(
                pygame.font.Font(None, 18),
                pygame.font.Font(None, 16),
                card_loader=lambda: collection,
            )
            panel.open([], "mage")
            panel.handle_click(panel.create_button.center)
            panel.handle_click(panel.element_rects[0].center)
            hovered_card_rect = panel.card_rects[0]

            with (
                patch("kaloda.ui.deck_selection_panel.pygame.mouse.get_pos", return_value=hovered_card_rect.center),
                patch("kaloda.ui.deck_selection_panel.draw_card_tooltip") as draw_tooltip,
            ):
                panel.draw(pygame.Surface((1920, 1080)))

            draw_tooltip.assert_called_once()
            self.assertIn(panel.visible_keys[0], panel.cards_by_key)
        finally:
            pygame.quit()

    def test_back_from_cards_returns_to_elements_and_keeps_selection(self):
        panel = DeckSelectionPanel(None, None, card_loader=lambda: self._collection("mage"))
        panel.open([], "mage")
        panel.handle_click(panel.create_button.center)
        panel.handle_click(panel.element_rects[0].center)
        panel.handle_click(panel.card_rects[0].center)
        panel.handle_click(panel.back_button.center)
        self.assertTrue(panel.creating)
        self.assertEqual(panel.view, "elements")
        self.assertEqual(len(panel.selected_cards), 1)

    def test_back_from_elements_cancels_creation(self):
        panel = DeckSelectionPanel(None, None, card_loader=lambda: self._collection("mage"))
        panel.open([], "mage")
        panel.handle_click(panel.create_button.center)
        panel.handle_click(panel.back_button.center)
        self.assertFalse(panel.creating)

    def test_mouse_clicks_are_not_swallowed_while_creating(self):
        panel = DeckSelectionPanel(None, None, card_loader=lambda: self._collection("mage"))
        panel.open([], "mage")
        panel.handle_click(panel.create_button.center)
        self.assertTrue(panel.creating)
        click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=panel.element_rects[0].center)
        self.assertFalse(panel.handle_event(click), "клик должен дойти до handle_click")
        key = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, unicode="a", mod=0)
        self.assertTrue(panel.handle_event(key), "ввод имени колоды остаётся у панели")

    def test_save_saves_through_overlay_and_returns_to_list(self):
        saved = []
        decks = [{"id": 7, "name": "Новая", "cards": {}}]
        overlay = CharacterProfileOverlay(
            pygame.font.Font(None, 18),
            collection_loader=lambda: self._collection("warrior"),
            deck_loader=lambda: decks,
            deck_creator=lambda name, cards: saved.append((name, cards)),
        )
        panel = overlay.deck_panel
        panel.open([], "warrior")
        panel.handle_click(panel.create_button.center)
        panel.handle_click(panel.element_rects[0].center)
        for index in range(DECK_SIZE):
            panel.handle_click(panel.card_rects[index].center)
        panel.name = "Тест"
        expected_cards = list(panel.selected_cards)
        panel.on_save()
        self.assertEqual(saved, [("Тест", expected_cards)])
        self.assertFalse(panel.creating)
        self.assertEqual(panel.decks, decks)

    def test_save_with_invalid_deck_keeps_creation_open(self):
        saved = []
        overlay = CharacterProfileOverlay(
            pygame.font.Font(None, 18),
            collection_loader=lambda: self._collection("warrior"),
            deck_loader=lambda: [],
            deck_creator=lambda name, cards: saved.append((name, cards)),
        )
        panel = overlay.deck_panel
        panel.open([], "warrior")
        panel.handle_click(panel.create_button.center)
        panel.name = "Пустая"
        panel.on_save()
        self.assertEqual(saved, [])
        self.assertTrue(panel.creating)
        self.assertTrue(panel.error)

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

    def test_wrong_size_rejected_and_duplicates_allowed(self):
        keys = [
            card.key
            for card in cards_for_type("archer")
            if not card.effect_data.get("ultimate")
        ]
        self.assertIn("\u0440\u043e\u0432\u043d\u043e", deck_validation_error(keys[:5], "archer"))
        self.assertEqual(
            deck_validation_error(keys[:21] + keys[:1], "archer"),
            "",
        )

    def test_duplicate_cards_count_toward_deck_size_and_must_be_owned(self):
        keys = [
            card.key
            for card in cards_for_type("warrior")
            if not card.effect_data.get("ultimate")
        ]
        deck = keys[:21] + [keys[0]]
        owned = {key: 1 for key in set(deck)}
        owned[keys[0]] = 2

        self.assertEqual(deck_validation_error(deck, "warrior", owned), "")
        self.assertIn(
            "больше копий",
            deck_validation_error(deck, "warrior", {**owned, keys[0]: 1}),
        )
        self.assertEqual(
            expand_deck_card_keys({keys[0]: 2, keys[1]: 1}),
            [keys[0], keys[0], keys[1]],
        )

    def _mage_deck_with(self, limited_key, copies):
        filler = [
            card.key
            for card in cards_for_type("mage")
            if not card.effect_data.get("ultimate") and card.key != limited_key
        ]
        deck = {limited_key: copies}
        for key in filler[: DECK_SIZE - copies]:
            deck[key] = 1
        return deck

    def test_copy_limit_rejects_extra_copies_of_limited_card(self):
        deck = self._mage_deck_with("mage_flash", 3)
        self.assertIn("не больше 2", deck_validation_error(deck, "mage"))
        self.assertEqual(deck_validation_error(self._mage_deck_with("mage_flash", 2), "mage"), "")

    def test_shift_allows_two_copies(self):
        self.assertEqual(deck_validation_error(self._mage_deck_with("mage_shift", 2), "mage"), "")
        self.assertIn("не больше 2", deck_validation_error(self._mage_deck_with("mage_shift", 3), "mage"))

    def test_deck_panel_caps_copies_at_limit(self):
        collection = [{"key": "universal_trap", "name": "Ловушка", "quantity": 5}]
        panel = DeckSelectionPanel(None, None, card_loader=lambda: collection)
        panel.open([], "mage")
        panel.owned = {"universal_trap": 5}
        panel.selected_cards = []
        for _ in range(4):
            panel._toggle_card("universal_trap")
        self.assertEqual(panel.selected_cards.count("universal_trap"), 2)

    def test_cards_outside_collection_rejected(self):
        keys = [card.key for card in cards_for_type("archer")][:DECK_SIZE]
        self.assertIn("\u043a\u043e\u043b\u043b\u0435\u043a\u0446\u0438\u0438", deck_validation_error(keys, "archer", owned_keys=set(keys[1:])))

    def test_ultimate_needs_five_cards_of_its_style(self):
        cards = cards_for_type("mage")
        fire_ultimate = next(card for card in cards if card.key == "mage_pyromania")
        others = [
            card.key for card in cards
            if not card.group_name.endswith("\u041e\u0433\u043e\u043d\u044c") and not card.effect_data.get("ultimate")
        ]
        fire = [card.key for card in cards if card.group_name.endswith("\u041e\u0433\u043e\u043d\u044c") and not card.effect_data.get("ultimate")]
        deck = [fire_ultimate.key] + fire[:4] + others[: DECK_SIZE - 5]
        self.assertIn("\u0423\u043b\u044c\u0442\u0430", deck_validation_error(deck, "mage"))
        self.assertTrue(card_allowed_for(fire_ultimate, "mage"))


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
        player = Fighter("A", 5, profession_type="mage")
        enemy = Fighter("B", 5, profession_type="warrior")
        battle = CardBattle(player, enemy, cards=[], rng=random.Random(1))
        battle.mage_mode = True
        card = next(card for card in cards_for_type("mage") if card.key == "mage_fireball")
        player.mp = 30
        battle._resolve_card("player", card)
        self.assertEqual(player.mp, 30 - card.resource_cost)

    def test_two_selected_cards_cannot_overspend_resource(self):
        player = Fighter("A", 1, profession_type="warrior")
        enemy = Fighter("B", 1, profession_type="warrior")
        battle = CardBattle(player, enemy, cards=[], rng=random.Random(1))
        by_key = {card.key: card for card in cards_for_type("warrior")}
        strike, cleave = by_key["warrior_valen_strike"], by_key["warrior_valen_cleave"]
        player.unique_resource_current = strike.resource_cost + cleave.resource_cost - 1
        battle.hands["player"] = [strike, cleave]
        self.assertTrue(battle.select_card("player", strike.key))
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
            self.assertEqual(sorted(keys), sorted(card.key for card in class_cards_for_type("archer")))
            # \u041f\u043e\u0432\u0442\u043e\u0440\u043d\u044b\u0439 \u0437\u0430\u043f\u0440\u043e\u0441 \u043d\u0435 \u0434\u0443\u0431\u043b\u0438\u0440\u0443\u0435\u0442 \u0441\u0442\u0430\u0440\u0442\u043e\u0432\u044b\u0439 \u043d\u0430\u0431\u043e\u0440
            self.assertEqual(len(client.get_card_collection(character["id"])), len(keys))

            with self.assertRaisesRegex(ServerError, "\u0447\u0443\u0436\u043e\u0433\u043e \u043a\u043b\u0430\u0441\u0441\u0430"):
                client.create_deck(character["id"], "\u0427\u0443\u0436\u0430\u044f", keys[:DECK_SIZE - 1] + ["warrior_valen_strike"])
            deck = client.create_deck(character["id"], "\u0421\u0432\u043e\u044f", keys[:DECK_SIZE])
            self.assertEqual(len(deck["cards"]), DECK_SIZE)
            self.database.add_card_to_collection(character["id"], keys[0])
            duplicate_deck = client.create_deck(
                character["id"],
                "\u041f\u043e\u0432\u0442\u043e\u0440\u044b",
                keys[:DECK_SIZE - 1] + [keys[0]],
            )
            self.assertEqual(sum(duplicate_deck["cards"].values()), DECK_SIZE)
            self.assertEqual(duplicate_deck["cards"][keys[0]], 2)

    def test_card_shop_purchases_universal_card_and_spends_price(self):
        with running_server(self.database) as client:
            client.register("shopuser", "password")
            client.login("shopuser", "password")
            character = client.create_character("Герой", "warrior")
            with self.database.connection() as connection:
                connection.execute("UPDATE characters SET coins = 1000 WHERE id = %s", (character["id"],))

            catalog = client.get_card_shop_catalog()
            catalog_keys = {card["key"] for card in catalog}
            self.assertNotIn("universal_bonebreaker", catalog_keys)
            with self.assertRaisesRegex(ServerError, "только в подземелье"):
                client.buy_card(character["id"], "universal_bonebreaker")
            dungeon_catalog = client.get_dungeon_card_shop_catalog()
            self.assertEqual({card["key"] for card in dungeon_catalog}, {"universal_bonebreaker"})
            self.assertTrue(dungeon_catalog[0]["available"])
            self.assertEqual(dungeon_catalog[0]["price"], 250)

            trap = next(card for card in catalog if card["key"] == "universal_trap")
            self.assertEqual(trap["price"], 300)
            result = client.buy_card(character["id"], trap["key"])

            self.assertEqual(result["character"]["coins"], 700)
            entry = next(
                card for card in client.get_card_collection(character["id"])
                if card["key"] == trap["key"]
            )
            self.assertEqual(entry["quantity"], 1)


if __name__ == "__main__":
    unittest.main()
