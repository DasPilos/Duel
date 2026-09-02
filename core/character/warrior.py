"""Warrior character class - uses current game stat system"""

from typing import List, Dict
from core.character.base import BaseCharacter


class Warrior(BaseCharacter):
    """Warrior character type with classic stats system
    
    Stats: Strength, Agility, Intuition, Endurance
    - Strength: damage output
    - Agility: attack speed / dodge chance
    - Intuition: critical hit chance
    - Endurance: health points
    """
    
    STAT_NAMES = ["Сила", "Ловкость", "Интуиция", "Выносливость"]
    
    BASE_STATS = {
        "Сила": 3,
        "Ловкость": 3,
        "Интуиция": 3,
        "Выносливость": 4,
    }
    
    ENDURANCE_HP_BONUS = 10
    MIN_STAT_VALUE = 3
    STARTING_STAT_POINTS = 3
    
    @property
    def character_type(self) -> str:
        return "warrior"
    
    def get_stats_names(self) -> List[str]:
        return self.STAT_NAMES.copy()
    
    def get_base_stats(self) -> Dict[str, int]:
        return self.BASE_STATS.copy()
    
    def get_minimum_stat(self, stat_name: str, level: int) -> int:
        """Endurance has minimum based on level, others have fixed minimum"""
        if stat_name == "Выносливость":
            # +1 endurance per level, starting from 4
            return 4 + max(0, int(level) - 1)
        return self.MIN_STAT_VALUE
    
    def get_max_hp(self, endurance: int) -> int:
        """HP = endurance * 10"""
        return self.ENDURANCE_HP_BONUS * int(endurance)
    
    def validate_stat_change(self, stat_name: str, current_value: int,
                            delta: int, stat_points: int) -> bool:
        """Validate warrior stat change rules
        
        Rules:
        - Can't manually increase endurance (only via level up)
        - Can't decrease below minimum
        - Need stat points to increase
        """
        # Can't manually increase endurance
        if stat_name == "Выносливость" and delta > 0:
            return False
        
        # Need stat points to increase
        if delta > 0 and stat_points <= 0:
            return False
        
        minimum = self.get_minimum_stat(stat_name, self.level)
        
        # Can't decrease below minimum
        if delta < 0 and current_value <= minimum:
            return False
        
        return True
