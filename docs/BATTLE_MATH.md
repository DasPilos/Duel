# Battle Math: Source of Truth

This document maps the current world-map battle rules to their implementation and tests. The code and tests are authoritative.

## Shared Character Values

`combat/character_stats.py` defines the seven stats, profession constants, resource caps, and stat progression.

- Starting/minimum stats and starting stat points are constants in that module.
- Stat progression: `level_stat_points`, `total_stat_points`, `minimum_endurance`.
- Carry capacity is calculated in `calculate_carry_capacity`.
- Profession data is in `PROFESSIONS`. Four classes are offered at character creation: Warrior, Archer, Assassin, Mage. The mage stat formulas are a placeholder.

Relevant tests: `tests/test_character_stats.py`.

## World Combat Formulas

Source: `combat/world_stats.py`. Weapon damage range: `combat/weapon_damage.py`. Per-character application: `combat/fighter_profile.py`.

| Value | Formula | Cap / limit |
|---|---|---|
| Attack reach | 45 px + 1 px per intuition | none |
| Move speed | 160 px/s + 5 px/s per agility, times carry multiplier | none |
| Dodge (defender) | 5% per defender agility - 3% per attacker agility | 0–70% |
| Critical (attacker) | 5% per attacker intuition - 3% per defender intuition | 0–95% |
| Base damage | 2 per strength + weapon damage roll | none |
| Critical damage | base × 1.5 | none |
| Block | equipment `block` modifier, only from the front (3 of 8 directions, ±67.5°) | 0–70% |
| Block (normal hit) | full block, damage 0 | none |
| Block (critical hit) | base × 1.5 / 2 | none |
| Defense | 1 per endurance, subtracted from damage | none |
| Max HP | 12 per endurance + equipment HP | none |
| HP regen | 1 HP per 3 s per endurance | none |
| Max mana | 6 per intellect + equipment MP | none |
| Mana regen | 1 per second per intellect | none |
| Magic damage | 2 per wisdom (formula only; no magic attacks on the map yet) | none |

`resolve_world_melee_attack(attacker, defender, rng, defender_facing, attack_vector)` resolves one hit in this order: dodge, then base damage and critical roll, then block, then defense. Damage is never negative.

Block direction: the block works only if the attack comes from the defender's front sector, ±67.5° around its facing. That covers the facing direction and its two neighbours (3 of 8 directions). Attacks from the sides (90°) and from behind are not blocked.

Popups: a normal hit shows white damage. A critical shows red damage at double size. A dodge shows a light-blue «Уворот». A block shows a silver «Блок». A miss shows «Промах».

Relevant tests: `tests/test_world_stats.py`.

## Movement and Attack Timing

Implemented in `core/player_movement.py` (A* tile path) and `scenes/world_map_scene.py`.

- Right click moves the character and sets an attack target on a mob (Dota 2 style).
- Strike timing has three phases, as in Dota 2:
  - Windup: `get_attack_windup` = max(0, 0.5 - 0.02 × intuition). Damage is applied when the windup ends, and only if the target is still in reach. If the target left reach, the windup is not cancelled: it completes and ends as "Промах". Only a player action cancels it (a right click on the ground or a target change).
  - Strike: damage is applied at the end of the windup.
  - Backswing: `get_attack_backswing` = max(0, 0.5 - 0.02 × agility). The next windup cannot start until it ends.
- The same formulas apply to the player and the mob.
- The character and the mob cannot move during the windup or the backswing. A right click during the backswing queues the path; it runs after the backswing ends. A right click during the windup cancels the windup, and the path starts at once.
- A frame's `dt` is spent on the backswing first, and the rest goes to the next windup. The time is not counted twice.
- The attack swing animation is a placeholder arc. It covers only the windup and does not affect the timing.

Relevant tests: `tests/test_player_movement.py`, `tests/test_world_terrain.py`.

## Mob Rules

Constants in `scenes/world_map_scene.py`.

- Mob stats use the same world formulas as a level-1 character with endurance `MOB_ENDURANCE`. Mobs are the imps from the map editor NPC catalog (`core/mob_profiles.py`). Equipment is chosen per mob in the map editor card (weapon and shield from the item database, matched by `equip_slot`). With nothing chosen, the mob has no gear. Parameters come only from the map editor card.
- Mobs exist only on a published map (`map_live_mobs`). A world without a published map has no mobs.
- Patrol: each mob patrols around its spawn point within `MOB_PATROL_RADIUS_TILES` (3 tiles, a 7×7 square). Speed `MOB_PATROL_SPEED` (40 px/s), `MOB_PATROL_PAUSE` (1.5 s) at each waypoint.
- Aggro: a player within `MOB_AGGRO_RADIUS` starts the chase. Chase speed comes from the mob's mode settings.
- Leash: the mob does not move more than `MOB_LEASH_DISTANCE` (40 tiles) from its respawn point.
- Respawn: `MOB_RESPAWN_DELAY` (30 s) after death, at its spawn point.

Mob combat uses `resolve_world_melee_attack` with the same rules as the player.

Relevant tests: `tests/test_world_terrain.py`.

## Required Tests for Formula Changes

Start with the narrowest relevant module:

```powershell
python -m unittest tests.test_world_stats tests.test_player_movement tests.test_world_terrain tests.test_world_events -q
python -m unittest tests.test_character_stats -q
python -m unittest discover -s tests -q
```

Use a seeded/injected RNG for deterministic probability and damage tests. Cover bounds, zero/negative inputs, equipment, and each affected class. Update this document after the implementation and tests establish the new formula.
