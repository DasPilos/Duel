# 🧙 Mage Character System Documentation

## Overview

The Mage character system is a new parallel system to the existing Warrior system. It's designed for:
- Mountain Academy location
- Magic-based combat instead of physical
- 4 element specializations instead of diverse stats
- Mana resource management instead of pure endurance

---

## Character Classes

### `BaseCharacter` (core/character/base.py)
Abstract base class that both Warrior and Mage inherit from.

**Key Methods (all subclasses must implement):**
- `get_stats_names()` → List of available stats
- `get_base_stats()` → Starting stat values
- `get_minimum_stat(stat_name, level)` → Minimum value per level
- `get_max_hp(endurance)` → HP calculation
- `validate_stat_change(stat_name, value, delta, points)` → Change validation

### `Warrior` (core/character/warrior.py)
Existing warrior implementation adapted to new architecture.

**Stats (4):**
- Сила (Strength) - damage
- Ловкость (Agility) - attack speed
- Интуиция (Intuition) - crit chance
- Выносливость (Endurance) - health

**Rules:**
- Can't manually increase endurance (only +1 per level)
- Min value 3 for all stats except endurance
- Endurance grows: 4 + (level - 1)

### `Mage` (core/character/mage.py)
New mage character for magic system.

**Base Stats (3):**
- Мудрость (Wisdom) - magic damage (like Strength)
- Духовность (Spirituality) - mana pool & regeneration
- Выносливость (Endurance) - health (same as Warrior)

**Elements (4):**
- Земля (Earth) - physical magic
- Вода (Water) - healing & control
- Огонь (Fire) - damage & offensive
- Воздух (Wind) - mobility & speed

---

## Mage Stats System (core/stats/mage_stats.py)

### Constants
```python
BASE_STAT_VALUE = 3                    # Starting value for Wisdom & Spirituality
STARTING_ENDURANCE_VALUE = 4           # Starting endurance (same as Warrior)
MIN_STAT_VALUE = 3                     # Can't reduce below this
MANA_PER_SPIRITUALITY = 5              # Mana pool = spirituality * 5
ENDURANCE_HP_BONUS = 10                # HP = endurance * 10 (same as Warrior)
```

### Key Functions

#### `minimum_endurance(level: int) -> int`
Returns minimum endurance value at given level.
```python
minimum_endurance(1) → 4
minimum_endurance(2) → 5
minimum_endurance(10) → 13
```

#### `total_stat_points(level: int) -> int`
Returns total available stat points to spend.
```python
total_stat_points(1) → 3              # Starting points
total_stat_points(2) → 6              # 3 + 3 points from level up
total_stat_points(10) → 30            # 3 + (3 * 9 levels)
```

#### `calculate_max_hp(endurance: int) -> int`
```python
calculate_max_mana(int) -> int
calculate_max_hp(4) → 40              # 4 * 10
calculate_max_hp(10) → 100
```

#### `calculate_max_mana(spirituality: int) -> int`
```python
calculate_max_mana(3) → 15            # 3 * 5
calculate_max_mana(10) → 50
```

#### `adjust_mage_stats(stats, stat_points, hp, max_hp, mana, max_mana, level, stat_name, delta)`
Main function to adjust a stat. Returns updated state dict or None.

**Rules:**
- Can't increase endurance manually (delta == +1 returns None)
- Other stats need stat_points to increase
- Can't decrease below minimum
- Updates both HP and Mana when those stats change

**Returns:**
```python
{
    "stats": {"Мудрость": 4, "Духовность": 3, "Выносливость": 4},
    "stat_points": 2,                   # Decreased by 1
    "hp": 40,                           # Updated if Endurance changed
    "max_hp": 40,
    "mana": 15,                         # Updated if Spirituality changed
    "max_mana": 15,
}
```

---

## Element System (TODO for Dev2)

### Concept
Elements are NOT stats, they're specialization tracks. A mage can:
- Invest points in elements (unlike base stats which are on level-up timer)
- Create unique builds: full fire mage, water/earth hybrid, etc.
- Unlock spells based on element levels

### Planned Functions (add to mage_stats.py)
```python
def add_element_level(element_name: str, current_level: int) -> bool:
    """Train an element in the academy
    
    Args:
        element_name: "Земля", "Вода", "Огонь", "Воздух"
        current_level: Current element level (0-X)
        
    Returns:
        True if level increased, False if max reached or invalid
    """
    pass

def get_spells_for_element(element_name: str, element_level: int) -> List[Card]:
    """Get available spells for this element at this level
    
    Example:
        - Earth level 1: "Stone Throw", "Rock Shield"
        - Earth level 2: "Earthquake", "Stone Armor"
    """
    pass

def validate_mage_build(stats: Dict, elements: Dict) -> bool:
    """Validate that mage has valid build
    
    Example rules:
        - Must have at least 1 element at level 1+
        - Can't have all elements at 0
        - Wisdom should match element choices
    """
    pass
```

### Database Schema (TODO)
```sql
-- Add to database when creating mage
CREATE TABLE mage_stats (
    user_id INTEGER PRIMARY KEY,
    wisdom INTEGER,
    spirituality INTEGER,
    endurance INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE mage_elements (
    user_id INTEGER PRIMARY KEY,
    earth_level INTEGER DEFAULT 0,
    water_level INTEGER DEFAULT 0,
    fire_level INTEGER DEFAULT 0,
    wind_level INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE mage_spells (
    id INTEGER PRIMARY KEY,
    name TEXT,
    element TEXT,  -- "Земля", "Вода", "Огонь", "Воздух"
    min_element_level INTEGER,
    damage_base INTEGER,
    mana_cost INTEGER,
    description TEXT
);
```

---

## Migration Path (For Future)

### Phase 1: Architecture (DONE ✅)
- [x] Create BaseCharacter abstract class
- [x] Implement Warrior class
- [x] Implement Mage class
- [x] Create mage_stats.py with stat system
- [x] Create placeholder folders for academy/mage content

### Phase 2: Battle System (Dev2)
- [ ] Create MageBattle class (parallel to WarriorBattle)
- [ ] Implement magic card system
- [ ] Create mana management during battle
- [ ] Implement element interactions

### Phase 3: Academy Scene (Dev2)
- [ ] Create academy_scene.py
- [ ] Implement element training UI
- [ ] Create spell selection screen
- [ ] Add mage progression system

### Phase 4: Full Mage Content (Dev2)
- [ ] Mage NPCs and questlines
- [ ] Unique mage items and equipment
- [ ] Mage-specific challenges
- [ ] Mage guild/community features

---

## Compatibility Notes

### With Existing Warrior System
✅ No changes to existing Warrior/Fighter classes  
✅ No changes to existing battle system  
✅ Mage system is completely parallel  
✅ Database can have warrior_stats AND mage_stats tables  

### Client-Server Communication
```python
# Server sends character info
{
    "character_id": 123,
    "type": "mage",                    # or "warrior"
    "name": "Aldor",
    "level": 5,
    "stats": {
        "Мудрость": 4,
        "Духовность": 5,
        "Выносливость": 4
    },
    "elements": {
        "Огонь": 2,
        "Вода": 1,
        "Земля": 0,
        "Воздух": 0
    }
}
```

---

## Testing Mage System

```python
# Test basic stat calculation
from core.stats.mage_stats import calculate_max_hp, calculate_max_mana

assert calculate_max_hp(4) == 40
assert calculate_max_mana(3) == 15
assert calculate_max_mana(10) == 50

# Test stat adjustment
from core.stats.mage_stats import adjust_mage_stats

result = adjust_mage_stats(
    stats={"Мудрость": 3, "Духовность": 3, "Выносливость": 4},
    stat_points=3,
    hp=40,
    max_hp=40,
    mana=15,
    max_mana=15,
    level=1,
    stat_name="Мудрость",
    delta=1
)

assert result["stats"]["Мудрость"] == 4
assert result["stat_points"] == 2
assert result["mana"] == 15  # Didn't change

# Test endurance increase is blocked
result = adjust_mage_stats(..., stat_name="Выносливость", delta=1)
assert result is None  # ✓ Correctly blocked
```

---

## Common Questions

**Q: Can a mage train elements while in battle?**  
A: No, elements are trained in the Academy scene only. Use server/academy/ endpoints.

**Q: Do elements affect base stat requirements?**  
A: Not yet. This could be a future feature (e.g., "requires Wisdom 5 to learn Fire").

**Q: Can mages use warrior cards?**  
A: No, they have separate card systems. Warrior cards are warrior-only.

**Q: How do mages compete with warriors?**  
A: Different strength curves. Warriors are straightforward, mages have resource management.

**Q: What's the endurance equivalent for mages?**  
A: Same as warrior - it's endurance. But mages also have Spirituality for mana.

---

## Files to Review Before Starting Dev2 Work

1. **core/character/base.py** - Understand abstract methods
2. **core/character/mage.py** - Review Mage class structure
3. **core/stats/mage_stats.py** - Review stat functions
4. **core/character/warrior.py** - See how Warrior implements BaseCharacter
5. **DEVELOPER_GUIDE.md** - Git workflow and file structure

---

**Last Updated**: 2026-09-01  
**Ready for Dev2**: ✅ YES
