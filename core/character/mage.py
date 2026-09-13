"""Mage character class - new character type for mountain academy"""

from typing import List, Dict
from core.character.base import BaseCharacter


class Mage(BaseCharacter):
    """Mage character type from mountain academy
    
    Stats:
    - Wisdom (Мудрость): magic damage (like Strength for warriors)
    - Intellect (Интеллект): mana pool and regeneration
    - Harmony (Гармония): magical balance
    - Endurance (Выносливость): health points
    """
    
    STAT_NAMES = ["Мудрость", "Интеллект", "Гармония", "Выносливость"]
    
    BASE_STATS = {
        "Мудрость": 3,          # Magic damage (like Strength)
        "Интеллект": 3,         # Mana and regeneration
        "Гармония": 3,          # Magical balance
        "Выносливость": 4,      # Health points
    }
    
    ENDURANCE_HP_BONUS = 10     # Same as warrior for now
    MIN_STAT_VALUE = 3
    STARTING_STAT_POINTS = 3
    MANA_PER_INTELLECT = 5      # Mana pool calculation
    
    @property
    def character_type(self) -> str:
        return "mage"
    
    def get_stats_names(self) -> List[str]:
        return self.STAT_NAMES.copy()
    
    def get_base_stats(self) -> Dict[str, int]:
        return self.BASE_STATS.copy()
    
    def get_all_stats(self) -> Dict[str, int]:
        """Return all mage stats."""
        return self.get_base_stats()
    
    def get_minimum_stat(self, stat_name: str, level: int) -> int:
        """Endurance has minimum based on level, others have fixed minimum"""
        if stat_name == "Выносливость":
            # +1 endurance per level, starting from 4
            return 4 + max(0, int(level) - 1)
        return self.MIN_STAT_VALUE
    
    def get_max_hp(self, endurance: int) -> int:
        """HP = endurance * 10 (same as warrior)"""
        return self.ENDURANCE_HP_BONUS * int(endurance)
    
    def get_max_mana(self, intellect: int) -> int:
        """Mana pool = intellect * 5"""
        return self.MANA_PER_INTELLECT * int(intellect)
    
    def validate_stat_change(self, stat_name: str, current_value: int,
                            delta: int, stat_points: int) -> bool:
        """Validate mage stat change rules
        
        Rules:
        - Can't manually increase endurance (only via level up)
        - Can't decrease below minimum
        - Need stat points to increase mage stats
        - Harmony is a regular mage stat
        """
        # Can't manually increase endurance
        if stat_name == "Выносливость" and delta > 0:
            return False
        
        # For base stats: need stat points to increase
        if stat_name in self.STAT_NAMES and delta > 0 and stat_points <= 0:
            return False
        
        minimum = self.get_minimum_stat(stat_name, self.level)
        
        # Can't decrease below minimum (only for base stats)
        if stat_name in self.STAT_NAMES and delta < 0 and current_value <= minimum:
            return False
        
        return True

