"""Mage character statistics system - for mountain academy mages
Dev2 will use this file to implement mage leveling and element training
"""

from typing import Dict, Tuple, Optional


# Base stat constants for mages (similar to warrior constants in combat/character_stats.py)
BASE_STAT_VALUE = 3
STARTING_ENDURANCE_VALUE = 4
MIN_STAT_VALUE = 3
STARTING_STAT_POINTS = 3
ENDURANCE_HP_BONUS = 10
MANA_PER_SPIRITUALITY = 5


class MageStats:
    """Statistics system for mage characters
    
    Base Stats:
    - Wisdom (Мудрость): Magic damage output (like Strength for warriors)
    - Spirituality (Духовность): Mana pool and mana regeneration
    - Endurance (Выносливость): Health points
    
    Element Levels (trained in academy):
    - Earth (Земля): Physical/defensive magic
    - Water (Вода): Healing and control magic
    - Fire (Огонь): Offensive magic and damage
    - Wind (Воздух): Speed and mobility magic
    """
    
    BASE_STATS = {
        "Мудрость": BASE_STAT_VALUE,
        "Духовность": BASE_STAT_VALUE,
        "Выносливость": STARTING_ENDURANCE_VALUE,
    }
    
    ELEMENTS = {
        "Земля": 0,
        "Вода": 0,
        "Огонь": 0,
        "Воздух": 0,
    }


def minimum_endurance(level: int) -> int:
    """Return endurance permanently granted by character level
    
    Mage endurance grows same as warrior: base 4 + (level - 1)
    """
    return STARTING_ENDURANCE_VALUE + max(0, int(level) - 1)


def total_stat_points(level: int) -> int:
    """Return all free stat points available at specified level"""
    # Same as warrior: 3 starting + 3 per level
    return STARTING_STAT_POINTS + sum(3 for _ in range(2, int(level) + 1))


def calculate_max_hp(endurance: int) -> int:
    """Return maximum health determined by endurance
    
    Same as warrior: endurance * 10
    """
    return ENDURANCE_HP_BONUS * int(endurance)


def calculate_max_mana(spirituality: int) -> int:
    """Return maximum mana pool determined by spirituality"""
    return MANA_PER_SPIRITUALITY * int(spirituality)


def validate_stat_increase(stat_name: str, current_value: int, 
                          stat_points: int, level: int) -> bool:
    """Validate if base stat can be increased
    
    Rules:
    - Can't increase endurance manually (only via level up)
    - Other stats need stat points
    
    Returns:
        True if increase is allowed, False otherwise
    """
    # Can't manually increase endurance
    if stat_name == "Выносливость":
        return False
    
    # Other stats need stat points
    if stat_points <= 0:
        return False
    
    return True


def validate_stat_decrease(stat_name: str, current_value: int, 
                          level: int) -> bool:
    """Validate if base stat can be decreased
    
    Rules:
    - Can't decrease below minimum value for stat
    
    Returns:
        True if decrease is allowed, False otherwise
    """
    minimum = MIN_STAT_VALUE
    
    # Can't decrease below minimum
    if current_value <= minimum:
        return False
    
    return True


def adjust_mage_stats(stats: Dict[str, int], 
                     stat_points: int, 
                     hp: int, 
                     max_hp: int, 
                     mana: int,
                     max_mana: int,
                     level: int, 
                     stat_name: str, 
                     delta: int,
                     character_id: Optional[int] = None) -> Optional[Dict]:
    """Return updated stat state for mage, or None when change is invalid
    
    This is the main function for mage stat adjustments.
    Similar to adjust_stats() in combat/character_stats.py but for mages.
    
    Args:
        stats: Current stat dict {stat_name: value}
        stat_points: Available stat points
        hp: Current health
        max_hp: Maximum health
        mana: Current mana
        max_mana: Maximum mana
        level: Character level
        stat_name: Name of stat to adjust
        delta: Change amount (-1 or +1)
        character_id: Character ID for debug checks
        
    Returns:
        Dict with updated stats or None if invalid
    """
    # Validate inputs
    if stat_name not in stats or delta not in (-1, 1):
        return None
    
    # Can't manually increase endurance
    if stat_name == "Выносливость" and delta > 0:
        return None
    
    # Need stat points to increase
    if delta > 0 and stat_points <= 0:
        return None
    
    minimum_value = minimum_endurance(level) if stat_name == "Выносливость" else MIN_STAT_VALUE
    
    # Can't decrease below minimum
    if delta < 0 and stats[stat_name] <= minimum_value:
        return None
    
    # Create updated stats
    updated_stats = dict(stats)
    updated_stats[stat_name] += delta
    
    # Update HP if endurance changed (shouldn't happen but safe to check)
    updated_max_hp = calculate_max_hp(updated_stats["Выносливость"])
    updated_hp = int(hp)
    if stat_name == "Выносливость" and delta > 0:
        updated_hp += updated_max_hp - int(max_hp)
    
    # Update mana if spirituality changed
    updated_max_mana = calculate_max_mana(updated_stats["Духовность"])
    updated_mana = int(mana)
    if stat_name == "Духовность" and delta > 0:
        updated_mana += updated_max_mana - int(max_mana)
    
    return {
        "stats": updated_stats,
        "stat_points": int(stat_points) - delta,
        "hp": min(updated_hp, updated_max_hp),
        "max_hp": updated_max_hp,
        "mana": min(updated_mana, updated_max_mana),
        "max_mana": updated_max_mana,
    }


# TODO for Dev2: 
# - add_element_level(element_name, current_level) - train element in academy
# - element_affects_cards() - which cards are available based on element levels
# - element_build_validation() - validate mage build based on element choices
# - element_to_card_mapping() - map elements to spell cards
