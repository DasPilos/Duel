# 🎮 Dual Developer Workflow - Duel Game Architecture

## Overview

This project is structured for **2 parallel developers** to work independently without conflicts:

- **Dev1 (You)**: City system (tavern, blacksmith, shops), Warrior character system
- **Dev2 (Coming soon)**: Mountain Academy, Mage character system

---

## 📁 File Structure & Responsibilities

### **Dev1 Only (City/Warrior)**
```
server/town/                   ← Server endpoints for city locations
scenes/town/                   ← UI scenes for city
core/character/warrior.py      ← Warrior class (stats, abilities)
core/cards/warrior_card.py     ← Warrior card system
```

### **Dev2 Only (Academy/Mage)**
```
server/academy/                ← Server endpoints for academy
scenes/academy/                ← UI scenes for academy  
core/character/mage.py         ← Mage class (stats, elements)
core/cards/magic_card.py       ← Mage card system
core/stats/mage_stats.py       ← Mage stat progression system
```

### **Shared/Core (Both developers coordinate)**
```
core/character/base.py         ← Abstract base class (DO NOT modify without approval)
core/character/__init__.py     ← Exports
main.py                        ← Game entry point (merge conflicts possible)
server/main.py                 ← Server entry point (merge conflicts possible)
```

---

## 🔄 Git Workflow

### Branch Structure
```
main                           ← Always working, Dev1 has priority
├── feature/town              ← Dev1 works here (warrior content)
└── feature/academy           ← Dev2 works here (mage content)
```

### Daily Workflow

**Dev1 (Morning):**
```bash
# Start fresh
git checkout main
git pull origin main
```

**Dev2 (Morning):**
```bash
# Always sync with Dev1's work first
git checkout feature/academy
git pull origin main  # ← Get Dev1's updates
pip install -r requirements.txt
```

**Dev2 (Submitting PR):**
```bash
git pull origin main  # Final sync
git push origin feature/academy
# Create Pull Request → feature/academy to main
# Dev1 reviews and merges
```

---

## ⚙️ Adding Dependencies

### If you need a new package:

1. Add to `requirements.txt` in your branch
2. Test it works locally
3. During PR, include the requirement update
4. Dev1 reviews and approves the new dependency

**Example:**
```bash
# Dev2 wants to add a magic library
echo "magic-elements-lib==1.0.0" >> requirements.txt
# Commit and include in PR
```

---

## 🛡️ Preventing Conflicts

### Rule 1: Separate File Owners
```
✅ GOOD: core/cards/warrior_card.py (Dev1) + core/cards/magic_card.py (Dev2)
❌ BAD:  Both editing core/cards/base.py at same time
```

### Rule 2: Extend, Don't Modify Base Classes
```python
# core/character/base.py (read-only after initial setup)
class BaseCharacter(ABC):
    @abstractmethod
    def get_stats_names(self) -> List[str]:
        pass

# warrior.py (Dev1 extends)
class Warrior(BaseCharacter):
    def get_stats_names(self) -> List[str]:
        return ["Сила", "Ловкость", "Интуиция", "Выносливость"]

# mage.py (Dev2 extends)
class Mage(BaseCharacter):
    def get_stats_names(self) -> List[str]:
        return ["Мудрость", "Духовность", "Выносливость"]
```

### Rule 3: Isolated Database Tables
```sql
-- warrior_schema.py (Dev1)
CREATE TABLE warrior_cards (...)

-- mage_schema.py (Dev2)
CREATE TABLE mage_cards (...)
```

---

## 📊 Mage Stats System (Dev2 Reference)

The mage system is prepared in `core/stats/mage_stats.py` and `core/character/mage.py`.

### Base Stats (3 stats like Warrior):
- **Wisdom (Мудрость)**: Magic damage (like Strength)
- **Spirituality (Духовность)**: Mana pool (new stat)
- **Endurance (Выносливость)**: Health (same as Warrior)

### Element Specializations (4 elements):
- **Earth (Земля)**
- **Water (Вода)**
- **Fire (Огонь)**
- **Wind (Воздух)**

### Key Functions:
```python
# Already implemented for Dev2:
- minimum_endurance(level)      ← Endurance per level
- total_stat_points(level)      ← Available points to spend
- calculate_max_hp(endurance)   ← HP calculation
- calculate_max_mana(spirituality)  ← Mana calculation
- adjust_mage_stats(...)        ← Main stat adjustment (like warrior's adjust_stats)
```

**TODO for Dev2** (marked in file):
```python
- add_element_level()           ← Train elements in academy
- element_affects_cards()       ← Which spells available by element
- element_build_validation()    ← Check valid mage builds
- element_to_card_mapping()     ← Map elements to spell cards
```

---

## ✅ Checklist Before Committing

- [ ] All Python files compile: `python -m py_compile *.py`
- [ ] No modifications to other dev's files
- [ ] Only modifying files in your assigned folder
- [ ] If you modified `core/character/base.py` → discuss with other dev
- [ ] Git status shows only your changes: `git status`

---

## 🚨 If You Break Something

1. Don't panic! Roll back: `git revert <commit-hash>`
2. Run tests: `python -m pytest tests/`
3. Check game still starts: `python main.py`
4. Inform the team
5. Create fix in new commit

---

## 🔗 Current Architecture

### Character System
```
BaseCharacter (abstract)
├── Warrior (Dev1)
│   ├── 4 base stats (Strength, Agility, Intuition, Endurance)
│   ├── Warriors cards
│   └── Warrior battle system
│
└── Mage (Dev2)
    ├── 3 base stats (Wisdom, Spirituality, Endurance)
    ├── 4 elements (Earth, Water, Fire, Wind)
    ├── Magic cards
    └── Magic battle system
```

### Scene Routing
```
Main Menu
├── "ГОРОД" (Dev1)
│   ├── Tavern
│   ├── Blacksmith
│   └── Shops
│
└── "АКАДЕМИЯ МАГИИ" (Dev2)
    ├── Academy Hub
    ├── Element Training
    └── Spell Selection
```

---

## 📞 Questions?

- **Syntax error in your code?** → Run `python -m py_compile your_file.py`
- **Git conflict?** → Use VS Code merge tool or ask for help
- **Not sure if you should edit a file?** → Check this document or ask
- **Need to modify base class?** → Discuss with other dev first

---

**Last Updated**: 2026-09-01
**Status**: ✅ Architecture Ready for Dev2
