# Complete Dependency Map: World Combat System

## Architecture Overview

The only combat mode is world-map combat (`scenes/world_map_scene.py`). Card battles, duels, decks, and the card database have been removed.

```
WorldMapScene
 ├─ core/player_movement.py      A* tile path, follow_path
 ├─ combat/world_stats.py        all combat formulas
 ├─ combat/weapon_damage.py      weapon damage range
 ├─ combat/fighter_profile.py    applies a character profile to a Fighter
 ├─ combat/fighter.py            Fighter object (equipment, derived values)
 ├─ combat/character_stats.py    stat constants, progression, carry capacity
 ├─ combat/progression.py        level/XP progression
 └─ core/carry_weight.py         movement multiplier from carried weight
```

## Component Hierarchy & Dependencies

### 1. FIGHTER CLASS (Core Character System)

`combat/fighter.py` holds a character's stats, equipment modifiers, and current HP/MP. `recalculate_parameters` sets derived values, so world values (`get_world_max_hp`, `get_world_max_mana`) are applied after it.

### 2. CHARACTER_STATS (Stat Formulas & Constants)

`combat/character_stats.py` defines the seven stats (strength, agility, intuition, endurance, wisdom, intellect, plus the free points), profession data, stat-point progression, and carry capacity.

- Starting stats and free points are defined here.
- Four classes are offered at character creation: Warrior, Archer, Assassin, Mage.

### 3. WORLD_STATS (Combat Formulas)

`combat/world_stats.py` is the single source for combat values:

- Reach and move speed (`get_attack_reach`, `get_move_speed`).
- Dodge and critical chances, which depend on both attacker and defender (`get_world_dodge_chance`, `get_world_crit_chance`).
- Base damage and defense (`get_world_base_damage`, `get_defense`).
- HP, mana, and their regeneration (`get_world_max_hp`, `get_hp_regen_per_second`, `get_world_max_mana`, `get_mana_regen_per_second`).
- The hit resolver `resolve_world_melee_attack(attacker, defender, rng)`.

Imports: `random`, `math`. Used by `scenes/world_map_scene.py` and the character panel (`ui/character_profile_overlay.py`, `ui/character_profile.py`).

### 4. WEAPON_DAMAGE & FIGHTER_PROFILE

- `combat/weapon_damage.py`: `weapon_damage_range(equipment)` reads the equipped weapon's damage range.
- `combat/fighter_profile.py`: `apply_fighter_profile(fighter, profile)` copies the character's stats onto the Fighter, using the base stat value from `character_stats`.

### 5. WORLD_MAP_SCENE (Combat Driver)

`scenes/world_map_scene.py` owns:

- Right-click movement and attack targeting (`_set_move_target`, `_set_attack_target`, `_update_attack_target`).
- The windup and backswing movement gate: the character does not move while `attack_windup > 0` or `attack_backswing > 0` (`update`).
- Striking a mob (`_strike_mob`) and the swing animation placeholder (`_start_attack_swing`).
- Mob patrol, aggro, leash, chase, and respawn (`_update_mobs`, `_update_mob_patrol`, `_update_mob_chase`, `_respawn_mob`).
- Damage numbers (lasting `DAMAGE_NUMBER_DURATION`).

Constants: `MOB_*`, `PLAYER_*`, and `DAMAGE_NUMBER_DURATION` at the top of the file.

### 6. PLAYER_MOVEMENT (Pathfinding)

`core/player_movement.py`:

- `find_tile_path` builds an A* path over the tile grid.
- `follow_path` moves the character along it.

Movement is tile-based; the path is recalculated when the target moves.

## Stat Effectiveness Reference

| Stat | Effect |
|---|---|
| Strength | +2 base damage per point |
| Agility | +5% dodge per point; +5 px/s move speed |
| Intuition | +5% crit per point; +1 px attack reach |
| Endurance | +12 max HP; +1 defense; +1 HP regen per 3 s |
| Wisdom | +2 magic damage per point (no magic attacks on the map yet) |
| Intellect | +6 max mana; +1 mana regen per second |

Opponent stats reduce the chance: −3% dodge per opponent agility point, −3% crit per opponent intuition point.

## Damage Calculation Flow

`resolve_world_melee_attack(attacker, defender, rng)`:

1. Dodge roll against `get_world_dodge_chance(defender, attacker)`. A dodge ends the attack.
2. Base damage: `get_world_base_damage` (strength × 2 + weapon roll).
3. Critical roll against `get_world_crit_chance(attacker, defender)`. A critical multiplies base damage by 1.5.
4. Block roll against the defender's equipment `block` modifier, only if the attack comes from the front sector (±67.5° around `defender_facing`). A block on a non-critical hit ends the attack with damage 0. A block on a critical hit halves the critical damage.
5. Defense: subtract `get_defense(defender)` from the damage, never below 0.

## Mob Behavior

| Parameter | Value |
|---|---|
| Stats | level-1 character formulas, endurance `MOB_ENDURANCE` |
| Weapon | club from the forge catalog (`MOB_CLUB_ITEM`) |
| Patrol square | 7×7 tiles around `MOB_PATROL_CENTER_TILE` |
| Patrol speed | `MOB_PATROL_SPEED` (40 px/s), 1.5 s pause per waypoint |
| Aggro | player enters the patrol square |
| Chase speed | `MOB_CHASE_SPEED` = `BASE_MOVE_SPEED` (160 px/s) |
| Leash | `MOB_LEASH_RADIUS_TILES` (40 tiles from the respawn point) |
| Respawn | `MOB_RESPAWN_DELAY` (30 s), at the center of the square |

## Timed Effects

The attack windup is the only timed effect in world combat:

- A windup (`attack_windup`, `get_attack_windup`: 0.5 s base minus 0.02 s per intuition point) runs before each strike. The strike applies when it ends, if the target is still in reach; otherwise the attack ends as a miss. A windup is cancelled only by a player action (a right click on the ground or a target change), or by the mob returning past its leash.
- A backswing (`attack_backswing`, `get_attack_backswing`: 0.5 s base minus 0.02 s per agility point) runs after each strike. The next windup cannot start during it.
- While the windup or backswing is above 0, the character does not move. When both end, a queued path resumes.
- Regeneration (HP and mana) runs each frame in `update`.

## Consistency Verification Checklist

- [ ] Formula changes are made in `combat/world_stats.py`, not inline in the scene.
- [ ] `BATTLE_MATH.md` and this file match the code.
- [ ] `tests/test_world_stats.py` covers bounds, zero and negative inputs, and equipment.
- [ ] `tests/test_world_terrain.py` covers the windup movement gate.
- [ ] `tests/test_player_movement.py` covers A* paths and stall handling.
- [ ] The character panel (`ui/character_profile_overlay.py`) shows values from `world_stats`.
