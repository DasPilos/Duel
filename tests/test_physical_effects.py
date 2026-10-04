import unittest

from combat.card_battle import CardBattle
from combat.card_database import cards_for_type
from combat.fighter import Fighter


class FixedRandom:
    """random() >= любые шансы уворота/крита: всё попадает и без критов."""

    def __init__(self, value=0.99):
        self.value = value

    def random(self):
        return self.value

    @staticmethod
    def randint(start, _end):
        return start

    @staticmethod
    def shuffle(_items):
        return None

    @staticmethod
    def randrange(stop):
        return 0


def _card(profession, key):
    return next(card for card in cards_for_type(profession) if card.key == key)


def _battle(attacker="warrior", defender="warrior", rng=None):
    player = Fighter("A", 5, profession_type=attacker)
    enemy = Fighter("B", 5, profession_type=defender)
    for fighter in (player, enemy):
        fighter.unique_resource_current = 999
        fighter.temporary_dodge_chance_modifier = 0
    battle = CardBattle(player, enemy, cards=[], rng=rng or FixedRandom())
    return battle, player, enemy


class PhysicalEffectTests(unittest.TestCase):
    def test_bleed_ticks_next_turns_and_is_not_lethal(self):
        battle, _player, enemy = _battle()
        battle._resolve_card("player", _card("warrior", "warrior_slash"))
        self.assertEqual(len(battle.bleeds["enemy"]), 1)
        hp = enemy.hp
        battle._tick_physical_effects()
        self.assertLess(enemy.hp, hp)
        enemy.hp = 1
        battle._tick_physical_effects()
        self.assertEqual(enemy.hp, 1)
        self.assertEqual(battle.bleeds["enemy"], [])

    def test_poison_stacks_and_execution_uses_them(self):
        battle, _player, enemy = _battle("assassin", "warrior")
        battle._resolve_card("player", _card("assassin", "assassin_poison_cascade"))
        self.assertEqual(len(battle.poisons["enemy"]), 3)
        hp = enemy.hp
        event = battle._resolve_card("player", _card("assassin", "assassin_poison_execution"))
        self.assertGreaterEqual(event["damage"], 24)
        self.assertLess(enemy.hp, hp)

    def test_poison_extraction_converts_poison_to_crit(self):
        battle, _player, _enemy = _battle("assassin", "warrior")
        battle._resolve_card("player", _card("assassin", "assassin_poison_cascade"))
        battle._resolve_card("player", _card("assassin", "assassin_poison_extraction"))
        self.assertEqual(battle.poisons["enemy"], [])
        self.assertEqual(battle._buff("player", "crit_chance"), 6)

    def test_mana_burn_and_bonus_on_empty_mana(self):
        battle, _player, enemy = _battle("archer", "battle_mage")
        enemy.mp = 5
        hp = enemy.hp
        event = battle._resolve_card("player", _card("archer", "archer_north_strike"))
        self.assertEqual(enemy.mp, 0)
        self.assertIn("МАНЫ", event["effect_text"])
        self.assertLess(enemy.hp, hp - 1)

    def test_buff_cards_do_not_burn_mana_immediately(self):
        battle, _player, enemy = _battle("archer", "battle_mage")
        mana = enemy.mp
        battle._resolve_card("player", _card("archer", "archer_north_mana_burn"))
        self.assertEqual(enemy.mp, mana)
        self.assertEqual(battle._buff("player", "burn_bonus_max_percent"), 2)

    def test_heal_percent_heals_missing_hp(self):
        battle, player, _enemy = _battle()
        player.hp = player.max_hp // 2
        event = battle._resolve_card("player", _card("warrior", "warrior_valen_cleave"))
        self.assertGreater(event["healed"], 0)

    def test_blessing_theft_redirects_enemy_healing(self):
        battle, player, enemy = _battle()
        battle._resolve_card("player", _card("warrior", "warrior_blessing_theft"))
        enemy.hp = 10
        player.hp = 10
        healed = battle._heal("enemy", 20)
        self.assertEqual(healed, 10)
        self.assertEqual(player.hp, 20)

    def test_buffs_expire(self):
        battle, _player, _enemy = _battle()
        battle._resolve_card("player", _card("warrior", "warrior_blood_pact"))
        self.assertEqual(battle._buff("player", "damage_percent"), 23)
        for _ in range(3):
            battle._tick_physical_effects()
        self.assertEqual(battle._buff("player", "damage_percent"), 0)

    def test_stun_blocks_card_selection(self):
        battle, _player, _enemy = _battle("archer", "warrior")
        battle._stun("enemy")
        card = _card("warrior", "warrior_slash")
        battle.hands["enemy"] = [card]
        self.assertFalse(battle.can_select("enemy", card))

    def test_no_miss_ignores_dodge(self):
        battle, _player, enemy = _battle("archer", "archer", rng=FixedRandom(0.0))
        enemy.temporary_dodge_chance_modifier = 100
        event = battle._resolve_card("player", _card("archer", "archer_hunt_stance"))
        self.assertFalse(event["dodged"])
        self.assertGreater(event["damage"], 0)

    def test_thirst_for_blood_guarantees_crit(self):
        battle, _player, _enemy = _battle("assassin", "warrior")
        battle._resolve_card("player", _card("assassin", "assassin_thirst_blood"))
        event = battle._resolve_card("player", _card("assassin", "assassin_fate_blade"))
        self.assertTrue(event["critical"])

    def test_full_heal_is_taken_back_later(self):
        battle, player, _enemy = _battle()
        player.hp = 10
        battle._resolve_card("player", _card("warrior", "warrior_valentine_transcendence"))
        self.assertEqual(player.hp, player.max_hp)
        for _ in range(3):
            battle._tick_physical_effects()
        self.assertLess(player.hp, player.max_hp)
        self.assertGreaterEqual(player.hp, 1)

    def test_every_physical_card_resolves(self):
        for profession in ("warrior", "archer", "assassin"):
            for card in cards_for_type(profession):
                with self.subTest(card=card.key):
                    battle, _player, _enemy = _battle(profession, "battle_mage")
                    event = battle._resolve_card("player", card)
                    self.assertTrue(event["effect_text"] or event["damage"] or event["dodged"])


if __name__ == "__main__":
    unittest.main()
