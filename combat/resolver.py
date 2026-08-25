import math
import random
from combat.mechanics import roll_2d6, roll_critical_d8, get_dodge_chance, get_critical_chance

def resolve_attack(attacker, defender, blocked, current_combo):
    # Уворот полностью отменяет атаку
    if random.random() * 100 < get_dodge_chance(attacker, defender):
        return {
            "damage": 0, "dice": (0, 0), "critical": False,
            "critical_dice": None, "critical_multiplier": 1,
            "blocked": False, "dodged": True, "combo_level": 0,
        }

    # Бросок костей и базовый урон
    dice = roll_2d6()
    base_damage = max(
        1, attacker.attack + attacker.strength * 0.5 - defender.defense - defender.strength * 0.5 + sum(dice)
    )

    # Определение уровня серии
    combo_level = current_combo + 1
    combo_multiplier = 1.0
    if combo_level == 2: combo_multiplier = 1.2
    elif combo_level == 3: combo_multiplier = 1.5
    elif combo_level >= 4: combo_multiplier = 2.0

    damage = int(base_damage * combo_multiplier)

    # Критический удар (5-е попадание всегда крит)
    guaranteed_critical = combo_level >= 5
    critical = guaranteed_critical or random.random() * 100 < get_critical_chance(attacker, defender)

    critical_dice = None
    critical_multiplier = 1

    if critical:
        critical_dice = roll_critical_d8()
        critical_multiplier = critical_dice
        damage = math.ceil(damage * critical_multiplier)

    # Блокировка
    if blocked:
        if critical:
            damage = math.ceil(damage / 2) # Крит пробивает блок наполовину
        else:
            return { # Обычная атака полностью блокируется
                "damage": 0, "dice": (0, 0), "critical": False,
                "critical_dice": None, "critical_multiplier": 1,
                "blocked": True, "dodged": False, "combo_level": 0,
            }

    return {
        "damage": damage, "dice": dice, "critical": critical,
        "critical_dice": critical_dice, "critical_multiplier": critical_multiplier,
        "blocked": blocked, "dodged": False, "combo_level": combo_level,
    }
