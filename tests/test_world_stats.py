import random
import unittest
from types import SimpleNamespace

from combat import world_stats as ws


def _fighter(**overrides):
    values = dict(
        strength=3, agility=3, intuition=3, endurance=4, wisdom=3, intellect=3,
        weapon_damage=None, equipment_stat_modifiers={},
    )
    values.update(overrides)
    return SimpleNamespace(**values)


class WorldStatsTests(unittest.TestCase):
    def test_reach_is_45_plus_intuition(self):
        self.assertEqual(ws.get_attack_reach(_fighter(intuition=3)), 48.0)

    def test_move_speed_scales_with_agility_and_carry(self):
        fighter = _fighter(agility=3)
        self.assertEqual(ws.get_move_speed(fighter, 1.0), 175.0)
        self.assertEqual(ws.get_move_speed(fighter, 0.5), 87.5)

    def test_dodge_uses_defender_minus_attacker_agility(self):
        defender = _fighter(agility=10)
        attacker = _fighter(agility=4)
        self.assertEqual(ws.get_world_dodge_chance(defender, attacker), 50 - 12)

    def test_dodge_is_clamped(self):
        self.assertEqual(ws.get_world_dodge_chance(_fighter(agility=50), _fighter(agility=0)), ws.MAX_DODGE_CHANCE)
        self.assertEqual(ws.get_world_dodge_chance(_fighter(agility=0), _fighter(agility=50)), 0.0)

    def test_crit_uses_attacker_minus_defender_intuition(self):
        attacker = _fighter(intuition=10)
        defender = _fighter(intuition=4)
        self.assertEqual(ws.get_world_crit_chance(attacker, defender), 50 - 12)

    def test_base_damage_is_strength_plus_weapon(self):
        fighter = _fighter(strength=3, weapon_damage=(5, 5))
        self.assertEqual(ws.get_world_base_damage(fighter, random.Random(1)), 6 + 5)

    def test_base_damage_without_weapon_uses_strength_only(self):
        self.assertEqual(ws.get_world_base_damage(_fighter(strength=3), random.Random(1)), 6)

    def test_hp_mana_and_regen(self):
        fighter = _fighter(endurance=4, intellect=3)
        self.assertEqual(ws.get_world_max_hp(fighter, 20), 48 + 20)
        self.assertEqual(ws.get_defense(fighter), 4)
        self.assertAlmostEqual(ws.get_hp_regen_per_second(fighter), 4 / 3)
        self.assertEqual(ws.get_world_max_mana(fighter, 5), 18 + 5)
        self.assertEqual(ws.get_mana_regen_per_second(fighter), 3.0)

    def test_magic_damage_is_two_per_wisdom(self):
        self.assertEqual(ws.get_world_magic_damage(_fighter(wisdom=3)), 6)

    def test_defense_reduces_damage_to_zero_floor(self):
        attacker = _fighter(strength=0, weapon_damage=(1, 1), agility=0, intuition=0)
        defender = _fighter(endurance=10, agility=0, intuition=0)
        result = ws.resolve_world_melee_attack(attacker, defender, _FixedRng(rolls=[99.0, 99.0, 99.0]))
        self.assertEqual(result["outcome"], "hit")
        self.assertEqual(result["damage"], 0)

    def test_dodge_roll_returns_dodge_outcome(self):
        attacker = _fighter(agility=0)
        defender = _fighter(agility=20)
        result = ws.resolve_world_melee_attack(attacker, defender, _FixedRng(rolls=[0.0]))
        self.assertEqual(result["outcome"], "dodge")
        self.assertEqual(result["damage"], 0)

    def test_block_without_crit_stops_hit(self):
        attacker = _fighter(agility=0, intuition=0, weapon_damage=(4, 4))
        defender = _fighter(agility=0, intuition=0, equipment_stat_modifiers={"block": 50})
        result = ws.resolve_world_melee_attack(attacker, defender, _FixedRng(rolls=[99.0, 99.0, 0.0]))
        self.assertEqual(result["outcome"], "block")
        self.assertEqual(result["damage"], 0)

    def test_crit_blocked_deals_half_of_crit_damage(self):
        attacker = _fighter(strength=0, weapon_damage=(10, 10), agility=0, intuition=20)
        defender = _fighter(strength=0, weapon_damage=None, agility=0, intuition=0,
                            endurance=0, equipment_stat_modifiers={"block": 50})
        result = ws.resolve_world_melee_attack(attacker, defender, _FixedRng(rolls=[99.0, 0.0, 0.0]))
        self.assertEqual(result["outcome"], "hit")
        self.assertTrue(result["critical"])
        self.assertEqual(result["damage"], 8)

    def test_front_and_adjacent_attacks_are_blockable(self):
        # Защитник смотрит на восток (0 рад): фронт — E, NE, SE (3 из 8 направлений)
        self.assertTrue(ws.is_attack_from_front(0.0, (1, 0)))
        self.assertTrue(ws.is_attack_from_front(0.0, (1, -1)))
        self.assertTrue(ws.is_attack_from_front(0.0, (1, 1)))

    def test_perpendicular_and_back_attacks_are_not_blockable(self):
        self.assertFalse(ws.is_attack_from_front(0.0, (0, 1)))
        self.assertFalse(ws.is_attack_from_front(0.0, (0, -1)))
        self.assertFalse(ws.is_attack_from_front(0.0, (-1, 0)))
        self.assertFalse(ws.is_attack_from_front(0.0, (-1, 1)))
        self.assertFalse(ws.is_attack_from_front(0.0, (-1, -1)))

    def test_block_does_not_apply_to_back_attack(self):
        attacker = _fighter(agility=0, intuition=0, weapon_damage=(4, 4))
        defender = _fighter(agility=0, intuition=0, weapon_damage=None, endurance=0,
                            equipment_stat_modifiers={"block": 50})
        result = ws.resolve_world_melee_attack(
            attacker, defender, _FixedRng(rolls=[99.0, 99.0, 0.0]),
            defender_facing=0.0, attack_vector=(-1, 0),
        )
        self.assertEqual(result["outcome"], "hit")
        self.assertEqual(result["damage"], result["base_damage"] - result["defense"])
        self.assertGreater(result["damage"], 0)

    def test_block_applies_to_front_attack_with_direction(self):
        attacker = _fighter(agility=0, intuition=0, weapon_damage=(4, 4))
        defender = _fighter(agility=0, intuition=0, equipment_stat_modifiers={"block": 50})
        result = ws.resolve_world_melee_attack(
            attacker, defender, _FixedRng(rolls=[99.0, 99.0, 0.0]),
            defender_facing=0.0, attack_vector=(1, 0),
        )
        self.assertEqual(result["outcome"], "block")

    def test_windup_base_is_half_second_and_intuition_shortens_it(self):
        self.assertAlmostEqual(ws.get_attack_windup(_fighter(intuition=0)), 0.5)
        self.assertAlmostEqual(ws.get_attack_windup(_fighter(intuition=3)), 0.44)

    def test_windup_never_goes_below_zero(self):
        self.assertEqual(ws.get_attack_windup(_fighter(intuition=100)), 0.0)

    def test_backswing_base_is_half_second_and_agility_shortens_it(self):
        self.assertAlmostEqual(ws.get_attack_backswing(_fighter(agility=0)), 0.5)
        self.assertAlmostEqual(ws.get_attack_backswing(_fighter(agility=3)), 0.44)

    def test_backswing_never_goes_below_zero(self):
        self.assertEqual(ws.get_attack_backswing(_fighter(agility=100)), 0.0)


class _FixedRng:
    """Подменяет uniform: отдаёт заранее заданные значения по очереди."""

    def __init__(self, rolls):
        self._rolls = list(rolls)

    def uniform(self, a, b):
        return self._rolls.pop(0)

    def randint(self, a, b):
        return b


if __name__ == "__main__":
    unittest.main()
