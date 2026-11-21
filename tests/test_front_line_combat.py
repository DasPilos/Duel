import unittest
from types import SimpleNamespace

from front_line.server.combat import resolve_melee_attack
from front_line.server.world import FrontLineWorldService


def _fighter(**overrides):
    values = dict(
        strength=0,
        agility=0,
        intuition=0,
        endurance=0,
        weapon_damage=(10, 10),
        equipment={},
        equipment_stat_modifiers={},
    )
    values.update(overrides)
    return SimpleNamespace(**values)


class FixedRoll:
    def __init__(self, *values):
        self.values = iter(values)

    def uniform(self, _minimum, _maximum):
        return next(self.values)

    def randint(self, _minimum, maximum):
        return maximum


class FrontLineCombatTests(unittest.TestCase):
    def test_equipment_adjusts_critical_chance_and_power_only_in_front_line(self):
        attacker = _fighter(equipment={
            "weapon": {"effects": {"crit": 20, "crit_power": 100}},
        })
        defender = _fighter()

        result = resolve_melee_attack(attacker, defender, FixedRoll(99, 0, 99))

        self.assertTrue(result["critical"])
        self.assertEqual(result["damage"], 20)

    def test_equipment_dodge_and_anti_dodge_are_used(self):
        defender = _fighter(equipment_stat_modifiers={"dodge": 25})
        attacker = _fighter(equipment={
            "weapon": {"effects": {"anti_dodge": 10}},
        })

        result = resolve_melee_attack(attacker, defender, FixedRoll(14))

        self.assertEqual(result["outcome"], "dodge")

    def test_block_fully_cancels_a_critical_hit_in_front_line(self):
        attacker = _fighter(
            intuition=20,
            equipment={"weapon": {"effects": {"crit": 100}}},
        )
        defender = _fighter(equipment_stat_modifiers={"block": 50})

        result = resolve_melee_attack(
            attacker,
            defender,
            FixedRoll(99, 0, 0),
            defender_facing=0.0,
            attack_vector=(1, 0),
        )

        self.assertEqual(result["outcome"], "block")
        self.assertTrue(result["critical"])
        self.assertEqual(result["damage"], 0)

    def test_front_line_strike_applies_direct_and_ally_aura_lifesteal(self):
        player = SimpleNamespace(
            x=0.0,
            y=0.0,
            dirty=False,
            fighter=_fighter(equipment={
                "weapon": {"effects": {"lifesteal_percent": 25}},
                "ring": {"effects": {"aura": {
                    "type": "vampirism",
                    "target": "allies",
                    "radius_px": 100,
                    "lifesteal_percent": 20,
                }}},
            }),
        )
        player.fighter.hp = 50
        player.fighter.max_hp = 100

        class Mob:
            def __init__(self):
                self.x = 1.0
                self.y = 0.0
                self.facing = 0.0
                self.log_names = {"nom": "враг", "dat": "врага", "gen": "врага"}
                self.fighter = _fighter()
                self.fighter.hp = 100
                self.provoker = None

            @property
            def alive(self):
                return self.fighter.hp > 0

        mob = Mob()
        service = object.__new__(FrontLineWorldService)
        service._rng = FixedRoll(99, 99, 99)
        service._players = {1: player}
        service._emit_label = lambda *_args: None
        service._emit_log = lambda *_args: None
        service._emit_number = lambda *_args: None
        service._damage_mob = lambda target, damage, _attacker: (
            setattr(target.fighter, "hp", target.fighter.hp - damage) or damage
        )

        service._strike_mob(player, mob)

        self.assertEqual(player.fighter.hp, 54)


if __name__ == "__main__":
    unittest.main()
