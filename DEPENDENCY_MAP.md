# Complete Dependency Map: Duel Combat System

## Architecture Overview

The Duel game uses a unified 7-stat system for all characters (Warriors, Mages, etc.), centered around the `Fighter` class. All gameplay stats, card mechanics, and combat resolution flow through this single system.

---

## Component Hierarchy & Dependencies

### 1. FIGHTER CLASS (Core Character System)
**File:** `/combat/fighter.py`

**Stats System (7 unified stats for all character types):**
```
Fighter.stats = {
    "strength": 3,      # Physical damage output
    "agility": 3,       # Dodge/block chance
    "intuition": 3,     # Critical hit chance
    "wisdom": 3,        # Mage spell damage scaling
    "intellect": 3,     # Max mana pool
    "harmony": 3,       # Magical effects duration/scaling
    "endurance": 3 + (level-1)  # Health pool
}
```

**Dependencies:**

| Component | Field/Method | Purpose |
|-----------|---|---|
| `character_stats.py` → `Fighter.__init__()` | `BASE_STAT_VALUE = 3` | Initialize all 7 stats |
| `character_stats.py` → `Fighter.__init__()` | `STARTING_ENDURANCE_VALUE = 3` | Level-based endurance scaling |
| `character_stats.py` → `Fighter.__init__()` | `STARTING_STAT_POINTS = 5` | Stat points for distribution |
| `character_stats.py` → `calculate_max_hp()` | `ENDURANCE_HP_BONUS = 10` | HP = Endurance × 10 |
| `character_stats.py` → `calculate_max_mana()` | `MANA_PER_INTELLECT = 5` | Mana = Intellect × 5 |
| `Fighter._effective_stat()` | `temporary_stat_modifiers[stat]` | Turn debuffs/buffs |
| `Fighter._effective_stat()` | `equipment_stat_modifiers[stat]` | Item bonuses |

---

### 2. CHARACTER_STATS (Stat Formulas & Constants)
**File:** `/combat/character_stats.py`

**Key Constants:**
```python
BASE_STAT_VALUE = 3
STARTING_ENDURANCE_VALUE = 3
MIN_STAT_VALUE = 3
STARTING_STAT_POINTS = 5
ENDURANCE_HP_BONUS = 10
MANA_PER_INTELLECT = 5
STAT_NAMES = ("strength", "agility", "intuition", "wisdom", "intellect", "harmony", "endurance")
```

**Level Progression Formulas:**

| Formula | Code | Result |
|---------|------|--------|
| **Stat Points at Level N** | `5 + (3 * (N-1))` | Level 1: 5 pts, Level 2: 8 pts, Level 10: 32 pts |
| **Min Endurance at Level N** | `3 + max(0, N-1)` | Level 1: 3, Level 10: 12 |
| **Max HP** | `Endurance × 10` | Endurance 5 = 50 HP |
| **Max Mana** | `Intellect × 5` | Intellect 4 = 20 Mana |

**Functions Used By:**
- `Fighter.__init__()` → calls `total_stat_points(level)`, `calculate_max_hp()`, `calculate_max_mana()`
- `Fighter.recalculate_parameters()` → recalculates HP/Mana from current stats
- `adjust_stats()` → applies stat changes with validation

---

### 3. CARDBATTLE (Combat System)
**File:** `/combat/card_battle.py`

**Core Mechanic Chain:**
```
Turn Start → Generate Action Points → Player Selection → Resolve Cards → Update Stats → Turn End
```

**Action Points Generation (Turn Start):**

| Stat | Formula | Example |
|------|---------|---------|
| All 4 stats | `max(0, stat_value) // 4` + `(remainder × 25% chance)` | Strength 13 → 3 guaranteed + 25% chance for +1 |

**Code Reference:** `points_from_stat(value)` in card_battle.py, lines 31-34

```python
def points_from_stat(value, rng=None):
    guaranteed, remainder = divmod(max(0, int(value)), 4)
    return guaranteed + int(rng.random() < remainder * 0.25)
```

**Dependencies:**

| Component | Field/Method | Purpose |
|-----------|---|---|
| `Fighter.strength` property | `_effective_stat("strength")` | Action points generation |
| `Fighter.agility` property | `_effective_stat("agility")` | Action points generation |
| `Fighter.intuition` property | `_effective_stat("intuition")` | Action points generation |
| `Fighter.endurance` property | `_effective_stat("endurance")` | Action points generation |
| `Fighter.wisdom` property | `_effective_stat("wisdom")` | Mage damage scaling |
| `Fighter.intellect` property | `_effective_stat("intellect")` | Mana pool cap |
| `Fighter.harmony` property | `_effective_stat("harmony")` | Mage effect duration |
| `Fighter.mp` | Mana points | Mage card cost deduction |
| `Card.mana_cost` | Mage card resource | Deducted from `Fighter.mp` |
| `Card.costs` property | Stat action point costs | Deducted from `action_points[stat]` |

---

### 4. CARD DATABASE (Card Definition & Loading)
**File:** `/combat/card_database.py`

**Card Dataclass Fields:**
```python
@dataclass(frozen=True)
class Card:
    key: str                    # Unique ID like "mage_flash"
    name: str                   # Display name
    group_name: str             # Category (e.g., "Магия: Огонь")
    strength_cost: int          # Action points required
    intuition_cost: int
    agility_cost: int
    endurance_cost: int
    effect_type: str            # Type like "mage_damage_status"
    effect_data: dict           # Effect parameters (JSON)
    level: int                  # Card level
    mana_cost: int = 0          # Mage card mana cost (NEW FIELD)
    price_copper/silver/gold: int   # Currency costs
    drop_chance: float          # Battle reward probability
    image_path: str             # Asset path
    effect_duration: int        # Effect duration in turns
```

**Mana Cost Handling:**
- **Previous System:** Mana cost buried in `effect_data["mana_cost"]` ❌
- **New System:** Direct `card.mana_cost` field ✅
- **Usage:** `can_select()` checks `fighter.mp >= card.mana_cost` before allowing play
- **Deduction:** `_resolve_card()` deducts `card.mana_cost` from `fighter.mp` when card executes

**Database Schema (SQLite):**
```
cards table:
  key TEXT PRIMARY KEY
  name TEXT
  group_name TEXT
  strength/intuition/agility/endurance_cost INTEGER
  effect_type TEXT
  effect_data TEXT (JSON string)
  level INTEGER
  price_* INTEGER
  drop_chance REAL
  image_path TEXT
  effect_duration INTEGER
  mana_cost INTEGER (NEW COLUMN)
  enabled INTEGER
```

**Data Flow:**
1. `_mage_card()` helper creates Card objects with mana_cost field
2. `initialize_database()` creates/migrates schema, adds mana_cost column
3. `load_cards()` reads cards from DB, reconstructs Card objects with all fields
4. Cards returned to `CardBattle.__init__()`

---

### 5. MECHANICS (Combat Calculations)
**File:** `/combat/mechanics.py`

**Dodge Calculation:**
```
base_dodge = Agility × 2.0 %
clamped_max = 70%
```

**Critical Damage Multiplier:**
```
base = 1.5
intuition_bonus = Intuition × 0.05
total = 1.5 + (Intuition × 0.05)

Example: Intuition 10 = 1.5 + 0.5 = 2.0× damage
```

**Functions:**
- `get_dodge_chance(attacker, defender)` → Returns base dodge % based on stats
- `get_critical_chance(attacker, defender)` → Returns base critical % (5% fixed)
- `get_critical_damage_multiplier(attacker)` → Returns total multiplier from intuition
- `weapon_damage_range(weapon_data)` → Rolls weapon dice

**Used By CardBattle:**
- `_resolve_card()` calls these functions for each hit calculation (lines 1137-1226)

---

## Stat Effectiveness Reference

### Action Points (Per-Turn Generation)
**Source:** Each of 4 stats generate points per turn
**Formula:** `(Stat ÷ 4) + (Remainder × 25% chance)`
**Cap:** No hard cap, scales infinitely with stats
**Usage:** Pay action points to play cards

| Stat | Purpose | Secondary |
|------|---------|-----------|
| **Strength** | Phys damage | Action points |
| **Agility** | Dodge % | Action points |
| **Intuition** | Critical multiplier | Action points |
| **Endurance** | Health pool | Cannot be manually increased |

### Mage-Only Stats
**Source:** Mages use same 7-stat system as Warriors
**Additional Uses:**

| Stat | Formula | Effect |
|------|---------|--------|
| **Wisdom** | Direct bonus | Mage damage output |
| **Intellect** | `× 5` | Max mana pool |
| **Harmony** | `÷ 6` (duration), `× 0.25` (bonus) | Mage effect duration/scaling |

**Mana Regen (Per Turn in Mage Mode):**
```
Restored = 8 + (Wisdom ÷ 2)
```

---

## Damage Calculation Flow

**File:** `/combat/card_battle.py` lines 1137-1226 (`_resolve_card()`)

```
For each hit in card.hits:
├─ 1. DODGE CHECK
│  ├─ base_dodge = get_dodge_chance(attacker, defender)
│  ├─ + defender.card_dodge_bonus
│  ├─ + defender.temporary_dodge_chance_modifier
│  ├─ - attacker.card_anti_dodge_bonus - card.anti_dodge
│  └─ If dodged → continue to next hit
│
├─ 2. DAMAGE ROLL
│  └─ damage = roll_dice(card.dice) + attacker.strength + weapon_roll
│
├─ 3. CRITICAL CHECK
│  ├─ crit_chance = get_critical_chance(attacker, defender)
│  ├─ + attacker.card_critical_bonus + card.critical_bonus
│  ├─ + attacker.temporary_critical_chance_modifier
│  └─ If critical:
│     ├─ multiplier = get_critical_damage_multiplier(attacker)
│     ├─ damage *= multiplier * card.critical_multiplier
│     └─ damage += card.critical_bonus_damage
│
├─ 4. APPLY DAMAGE
│  ├─ total_damage = floor(total_damage * defender.card_damage_ratio)
│  ├─ reduction = defender.card_damage_reduce
│  └─ defender.take_damage(max(0, total_damage - reduction))
│
└─ 5. SPECIAL EFFECTS
   ├─ damage_stat_debuff → reduce opponent's stat
   ├─ damage_critical_debuff → reduce opponent's crit%
   ├─ damage_dodge_debuff → reduce opponent's dodge%
   ├─ damage_recoil → attacker takes damage
   └─ damage_dodge_critical_debuff → both penalties
```

---

## Mage-Specific Systems

**File:** `/combat/card_battle.py`

### Mana Cost System
- **Storage:** `Fighter.mp` (current), `Fighter.max_mp` (calculated from intellect)
- **Per-card cost:** `Card.mana_cost` field (mage cards have non-zero values)
- **Checking:** `can_select()` method line 615 checks `fighter.mp >= card.mana_cost`
- **Deduction:** `_resolve_card()` line 957 deducts `card.mana_cost` from `fighter.mp`
- **Regen:** `_start_turn()` adds `8 + wisdom//2` to mana per turn (mage mode only)
- **Burn card:** Can burn a card to restore `20% of max_mp`

### Mage Status Effects
- **Storage:** `mage_statuses[side]` list
- **Types:** "огонь" (fire), "вода" (water), "холод" (cold), "электро" (electro)
- **Applied:** Via mage effect resolution (lines 1005-1134)
- **Duration:** Tracked per status with countdown

### Mage Shields
- **Storage:** `mage_shields[side]` (HP pool separate from fighter HP)
- **Applied:** When shield > 0, damage goes to shield first
- **Duration:** Expires after N turns via `timed_damage_ratio_effects`

### Mage Damage Bonuses
- **Storage:** `mage_damage_bonus_ratio` on Fighter
- **Applied:** Multiplied into mage damage calculations
- **Duration:** Tracked in `timed_damage_ratio_effects[side]`

### Mage Golems
- **Storage:** `mage_golems[side]` list
- **Stats:** HP (scaled by wisdom), damage (scaled by wisdom), stun ability
- **Behavior:** Attacks defender, can stun

### Mage Clouds
- **Storage:** `mage_clouds[side]` list
- **Damage:** Per-turn damage to enemy
- **Duration:** Scaled by harmony stat

---

## Timed Effects System

**Storage Structures:**
```
timed_stat_effects[side] = [
    {"stat": "strength", "amount": -2, "expires_after_turn": 5},
    ...
]

timed_critical_effects[side] = [
    {"amount": -10, "expires_after_turn": 5},
    ...
]

timed_dodge_effects[side] = [
    {"amount": -15, "expires_after_turn": 5},
    ...
]

timed_damage_ratio_effects[side] = [
    {"ratio": 0.8, "expires_after_turn": 5},
    ...
]
```

**Expiration Check (line 1259-1281):**
- Each turn, effects with `expires_after_turn <= current_turn` are removed
- Stat modifiers are reversed on the Fighter object
- Damage ratio effects are recalculated

---

## Card Selection & Validation Flow

**File:** `/combat/card_battle.py`

### Selection Process
1. **`can_select(side, card)` checks:**
   - Line 610-617
   - Verify freeze/stun status
   - Calculate action point costs: `sum(item.costs[stat] for item in selected[side])`
   - Check remaining points: `action_points[side][stat] - used[stat] >= cost`
   - Check mana (if mage): `fighter.mp >= card.mana_cost`

2. **`select_card(side, card_key)` action:**
   - Add card to `selected[side]`
   - Reserve action points (not deducted until turn resolves)

3. **`confirm_selection(side)` action:**
   - Lock in selection, prevent changes
   - Cards stay in `selected[side]` until `resolve_turn()`

4. **`_spend_points(side, card)` deduction (line 1314-1316):**
   - Called during `_resolve_card()`
   - Deduct stat costs: `action_points[side][stat] -= cost`
   - Deduct mana: `fighter.mp -= card.mana_cost` (inside mage card handlers)

---

## Removed Components

**Removed Files (No longer used, conflicting constants):**
- ❌ `/core/character/base.py` - Abstract base class (unused)
- ❌ `/core/character/warrior.py` - Had 4-stat system with STARTING_ENDURANCE = 4
- ❌ `/core/character/mage.py` - Had unused `get_all_stats()`, `get_max_mana()` methods
- ❌ `/core/stats/mage_stats.py` - Duplicated constants with wrong values

**Reason:** Fighter class is the active, unified system. Core/character and core/stats added confusion with conflicting constants and duplicate code.

---

## Summary: Complete Dependency Chain

```
GameLoop
├─ Fighter (Combat participant)
│  ├─ character_stats.py (Formulas for HP, Mana, Stat Points)
│  ├─ mechanics.py (Dodge, Critical, Weapon damage)
│  └─ Fighter.stats (7-stat dict)
│
├─ CardBattle (Turn resolution)
│  ├─ Fighter.strength/agility/intuition/wisdom/intellect/harmony/endurance (Action point generation)
│  ├─ Fighter.mp (Mana check for mage cards)
│  ├─ Card.mana_cost (Direct mana resource)
│  ├─ Card.costs (Action point costs)
│  ├─ Card.effect_type (Damage, status, buff, etc.)
│  ├─ Card.effect_data (Effect parameters)
│  ├─ mechanics.py (Dodge/crit calculations)
│  ├─ Fighter.temporary_stat_modifiers (Debuff tracking)
│  ├─ mage_* effects (Status, shields, clouds, golems)
│  └─ timed_*_effects (Duration tracking)
│
└─ Card Database
   ├─ load_cards() (Load from SQLite)
   ├─ Card dataclass (7 stat costs + mana_cost)
   └─ Card.group_name ("Магия: *" for mage cards)
```

---

## Consistency Verification Checklist

✅ **Fighter System** - Unified 7-stat system
✅ **Action Points** - Generated from 4 primary stats per turn
✅ **HP System** - Calculated from Endurance (× 10)
✅ **Mana System** - Calculated from Intellect (× 5)
✅ **Mana Cost** - Card.mana_cost field (no longer buried in effect_data)
✅ **Mage Stats** - Wisdom/Intellect/Harmony scale mage effects
✅ **Level Scaling** - Endurance increases with level
✅ **Stat Points** - 5 starting + 3 per level
✅ **Database Schema** - Includes mana_cost column
✅ **No Dead Code** - Removed unused core/character/ and core/stats/ directories
✅ **Consistent Constants** - All in character_stats.py

