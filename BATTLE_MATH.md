# Battle Math: Source of Truth

This document maps current battle rules to their implementation and tests. The code and tests are authoritative; older example formulas in archived reports are not specifications.

## Shared Character Values

`combat/character_stats.py` defines the seven stats, profession constants, resource caps, and stat progression.

- Starting/minimum stats and starting stat points are constants in that module.
- Maximum HP is `ENDURANCE_HP_BONUS * endurance`.
- Maximum mana is `MANA_PER_INTELLECT * intellect`.
- Physical unique-resource capacity is profession base plus level bonus; mana capacity comes from intellect.
- Carry capacity is calculated in `calculate_carry_capacity`.
- Profession base HP, mana, dodge, critical values, and unique resource are data in `PROFESSIONS`; do not assume a single formula applies to every profession.

Relevant tests: `tests/test_character_stats.py`, `tests/test_combat.py`.

## Chance and Weapon Helpers

`combat/mechanics.py` is the source for shared chance and weapon helpers:

- `clamp_chance(value, maximum=95.0)` clamps to `[0, maximum]`.
- `get_dodge_chance` uses the defender's agility, profession base dodge, and equipment dodge, capped at 70%.
- `get_block_chance` uses equipment block, capped at 70%.
- `get_critical_chance` currently returns the fixed base critical chance; stats do not increase the chance.
- `get_critical_damage_multiplier` is `1.5 + attacker.intuition * 0.05`.
- `weapon_damage_range` reads the equipped weapon's `effects.damage`, with the documented shield fallback.

Card-specific and temporary modifiers are resolved by battle code; do not treat a helper's base value as the final chance after effects.

## Card Battle

`combat/card_battle.py` owns deck/draft flow, card validation, turn resolution, random rolls, and battle state. `roll_dice` parses `NdM` and rolls each die with the supplied RNG. `PhysicalEffectsMixin` in `combat/physical_effects.py` applies physical class resources and effects. Mage-specific effects are resolved in `CardBattle`.

When changing damage, healing, critical, dodge, resource costs, or turn order, trace the actual card effect type through its resolver. Card data is loaded by `combat/card_database.py`; formulas may be data-driven and effect-specific.

## Physical Resources

`UNIQUE_RESOURCE_RECOVERY` and `UNIQUE_RESOURCE_GAIN` in `combat/character_stats.py` define baseline physical-resource recovery/gain. `combat/physical_effects.py` applies card effects, durations, bleed, poison, delayed HP loss, mana drain, and temporary modifiers. Duration handling and event order are part of the behavior; tests should cover turn boundaries.

## Required Tests for Formula Changes

Start with the narrowest relevant module, then run the full suite:

```powershell
python -m unittest tests.test_combat tests.test_character_stats -q
python -m unittest tests.test_card_battle tests.test_physical_effects -q
python -m unittest discover -s tests -q
```

Use a seeded/injected RNG for deterministic probability and damage tests. Cover bounds, zero/negative inputs, equipment, temporary effects, and each affected profession. Update this document only after the implementation and tests establish the new formula.
