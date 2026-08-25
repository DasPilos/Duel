import random
import unittest

from combat.fighter import Fighter
from combat.resolver import resolve_attack


ARCHETYPES = {
    "balanced": {"strength": 2, "agility": 2, "intuition": 1, "endurance": 1},
    "strength": {"strength": 6, "agility": 0, "intuition": 0, "endurance": 0},
    "agility": {"strength": 0, "agility": 6, "intuition": 0, "endurance": 0},
    "intuition": {"strength": 0, "agility": 0, "intuition": 6, "endurance": 0},
    "endurance": {"strength": 0, "agility": 0, "intuition": 0, "endurance": 6},
}


def make_fighter(allocation):
    fighter = Fighter("simulated")
    for stat_name, points in allocation.items():
        fighter.stats[stat_name] += points
    fighter.stat_points = 0
    fighter.recalculate_parameters()
    fighter.hp = fighter.max_hp
    return fighter


def simulate(first_allocation, second_allocation):
    first = make_fighter(first_allocation)
    second = make_fighter(second_allocation)
    first_combo = 0
    second_combo = 0
    turns = 0
    while first.hp > 0 and second.hp > 0 and turns < 100:
        turns += 1
        first_result = resolve_attack(first, second, False, first_combo)
        second_result = resolve_attack(second, first, False, second_combo)
        second.hp = max(0, second.hp - first_result["damage"])
        if second.hp > 0:
            first.hp = max(0, first.hp - second_result["damage"])
        first_combo = first_result["combo_level"] if first_result["damage"] > 0 else 0
        second_combo = second_result["combo_level"] if second_result["damage"] > 0 else 0
    return first.hp > 0, turns


def run_simulations(count=1000):
    random.seed(20260824)
    names = list(ARCHETYPES)
    results = {}
    for first_name in names:
        results[first_name] = {}
        for second_name in names:
            if first_name == second_name:
                continue
            wins = 0
            total_turns = 0
            for _ in range(count):
                first_won, turns = simulate(
                    ARCHETYPES[first_name],
                    ARCHETYPES[second_name],
                )
                wins += int(first_won)
                total_turns += turns
            results[first_name][second_name] = {
                "win_rate": wins / count,
                "avg_turns": total_turns / count,
            }
    return results


if __name__ == "__main__":
    results = run_simulations()
    print("Symmetric pairwise results: 1000 battles per order")
    names = list(ARCHETYPES)
    for index, first_name in enumerate(names):
        for second_name in names[index + 1:]:
            first_order = results[first_name][second_name]["win_rate"]
            second_order = 1 - results[second_name][first_name]["win_rate"]
            win_rate = (first_order + second_order) / 2
            print(f"{first_name:10} vs {second_name:10} {win_rate * 100:5.1f}%")


class BalanceSimulationTests(unittest.TestCase):
    def test_simulation_has_expected_archetypes(self):
        self.assertEqual(len(ARCHETYPES), 5)
        self.assertEqual(sum(ARCHETYPES["balanced"].values()), 6)


if __name__ == "__main__":
    unittest.main()
