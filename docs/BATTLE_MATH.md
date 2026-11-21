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
| Attack reach (Tower) | 45 px + 1 px per intuition | none |
| Attack range (Front Line) | 100 units warrior, 500 archer, 500 mage; +5 per intuition above 3; 1 tile = 100 units | none |
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

- Right click moves the character and sets an attack target on a mob (Dota 2 style). In Front Line a right click on a mob is an attack order; a right click on the ground is a move.
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

- Mob stats use the same world formulas as a level-1 character with endurance `MOB_ENDURANCE`. Mobs are the imps from the map editor NPC catalog (`core/mob_profiles.py`). Equipment is chosen per mob in the map editor card: the «Экипировка» window has 13 slots, and each slot lists only items from the item database whose `equip_slot` matches and whose requirements (`effects.requirements`: level and stats) the mob meets. Empty slots stay empty. The Tower server checks the same rules when it builds mobs (`_build_mobs` in `tower/server/world_mobs.py`). A ring fills either ring slot (`ring` or `ring_2`), but not both with the same ring. Parameters come only from the map editor card.
- Mobs exist only on a published map (`map_live_mobs`). A world without a published map has no mobs.
- Patrol: each mob patrols around its spawn point within `MOB_PATROL_RADIUS_TILES` (3 tiles, a 7×7 square), or within the zone from the editor. The mob walks a route over free zone cells, moving between neighbouring cells; each segment is checked against terrain, so the route goes around walls and the mob never passes through them. Speed `MOB_PATROL_SPEED` (40 px/s); `MOB_PATROL_PAUSE` (1.5 s) at the end of each route.
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

## Front Line: бой как в Dota 2

- Замах героя: (база класса − 0,02 с × интуиция) × 0,5 (`FRONT_LINE_WINDUP_SCALE`), база класса: воин 1,0 с, лучник 1,4 с, маг 2,4 с, не меньше 0,05 с. Откат: (0,5 с − 0,02 с × ловкость) × 2 (`FRONT_LINE_BACKSWING_SCALE`), не меньше 0,05 с. Общие формулы Tower (`get_attack_windup`, `get_attack_backswing`) не меняются.

- Orders: a new order (ground click, another target, S, H, A) carries a new `order_id`. The server cancels the windup on a new `order_id`: no strike, no backswing. A repeated order keeps the windup.
- S stops everything. H holds position: steps are refused, the hero still strikes targets in reach. A + click is attack-move: the hero walks to the point and attacks the nearest enemy in reach plus 32 px on the way.
- Auto-attack: a hero without an order strikes the nearest living mob in reach (`AUTO_ATTACK_ENABLED`). It does not chase.
- Out of reach at the end of the windup: no "Промах" and no backswing; the target is kept and the hero catches up. The reach at the end has an 8 px tolerance (`ATTACK_RANGE_BUFFER_PX`).
- Turning: the hero turns toward the target at 12 rad/s (`HERO_TURN_RATE`); the windup starts once it faces the target. A turning hero can still move (a deliberate choice: no visible reason for a snap-back).
- Projectiles: an arrow flies at 600 units/s (192 px/s) and an orb at 500 units/s (160 px/s) (`PROJECTILE_SPEED_UNITS`), toward the target's current position. It hits when it reaches the target's body edge. If the target dies in flight, an arrow vanishes and an orb explodes at the last known point. After 3 s without a hit it vanishes (`PROJECTILE_MAX_SECONDS`).
- Armour: damage after armour = base × (1 − k·A / (1 + k·A)), A = 8 × endurance, k = 0.06 (`damage_after_armor`). At endurance 4 that is about 66%. A hit always does at least 1 damage.
- Hero speed: the world speed × 0.6 (`HERO_MOVE_SPEED_SCALE`). Tower is unchanged.

## Front Line: единицы дальности

- Игрок видит дальность одним числом в единицах: 1 тайл = 100 ед. Пиксели используются только внутри сервера и клиента (`front_line/server/combat.py`, `range_units_to_px`, тайл = 32 px).
- Базовая дальность: воин 100, лучник 500, маг 500. Каждое очко интуиции сверх 3 добавляет 5 ед.
- Расстояние считается от центра атакующего до края круглого тела цели: `max(0, расстояние_центров - радиус_цели)`. Когда герой бьёт моба, вычитается радиус тела моба для дальности (20 px, босс ×4; это ближе к видимому спрайту, чем радиус коллизий 16 px). Когда моб бьёт героя, вычитается радиус героя (10 px).
- Моб бьёт на 100 ед. (32 px до края тела героя). Крысы окружают героя кольцом: первое кольцо на 34 px от центра (8 мест), второе на 66 px (14 мест). Место в кольце достижимо только при чистом рельефе до него.
- Маг выпускает огненный шар: в точке попадания он взрывается и бьёт всех живых мобов в радиусе 100 ед. (1 тайл) от центра взрыва. Радиус считается до края тела моба, своих героев взрыв не задевает, мёртвая цель не мешает взрыву. Урон каждому мобу считается отдельно по обычным правилам удара.
- Лучник выпускает стрелу: урон приходит при попадании в одну цель. Скорость стрелы 600 ед. в секунду, полный выстрел лучника (500 ед.) летит около 0,8 с. Если цель умерла в полёте, снаряд пропадает без урона.
- Тесты: `tests/test_front_line_world.py::FrontLineRangeTests`.
