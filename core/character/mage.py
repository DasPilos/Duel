"""Mage character class - new character type for mountain academy"""

from typing import List, Dict
from core.character.base import BaseCharacter


class Mage(BaseCharacter):
    """Mage character type from mountain academy
    
    Stats:
    - Wisdom (Мудрость): magic damage (like Strength for warriors)
    - Spirituality (Духовность): mana pool and regeneration
    - Endurance (Выносливость): health points
    
    Elements (specializations):
    - Earth (Земля)
    - Water (Вода)
    - Fire (Огонь)
    - Wind/Air (Воздух/Ветер)
    """
    
    STAT_NAMES = ["Мудрость", "Духовность", "Выносливость"]
    ELEMENT_NAMES = ["Земля", "Вода", "Огонь", "Воздух"]
    
    BASE_STATS = {
        "Мудрость": 3,          # Magic damage (like Strength)
        "Духовность": 3,        # Mana and regeneration
        "Выносливость": 4,      # Health points
    }
    
    BASE_ELEMENTS = {
        "Земля": 0,
        "Вода": 0,
        "Огонь": 0,
        "Воздух": 0,
    }
    
    ENDURANCE_HP_BONUS = 10     # Same as warrior for now
    MIN_STAT_VALUE = 3
    STARTING_STAT_POINTS = 3
    MANA_PER_SPIRITUALITY = 5   # Mana pool calculation
    
    @property
    def character_type(self) -> str:
        return "mage"
    
    def get_stats_names(self) -> List[str]:
        return self.STAT_NAMES.copy()
    
    def get_element_names(self) -> List[str]:
        """Return list of elemental specializations"""
        return self.ELEMENT_NAMES.copy()
    
    def get_base_stats(self) -> Dict[str, int]:
        return self.BASE_STATS.copy()
    
    def get_base_elements(self) -> Dict[str, int]:
        """Return base element levels (all 0 initially)"""
        return self.BASE_ELEMENTS.copy()
    
    def get_all_stats(self) -> Dict[str, int]:
        """Return all stats including elements"""
        all_stats = self.get_base_stats()
        all_stats.update(self.get_base_elements())
        return all_stats
    
    def get_minimum_stat(self, stat_name: str, level: int) -> int:
        """Endurance has minimum based on level, others have fixed minimum"""
        if stat_name == "Выносливость":
            # +1 endurance per level, starting from 4
            return 4 + max(0, int(level) - 1)
        return self.MIN_STAT_VALUE
    
    def get_max_hp(self, endurance: int) -> int:
        """HP = endurance * 10 (same as warrior)"""
        return self.ENDURANCE_HP_BONUS * int(endurance)
    
    def get_max_mana(self, spirituality: int) -> int:
        """Mana pool = spirituality * 5"""
        return self.MANA_PER_SPIRITUALITY * int(spirituality)
    
    def validate_stat_change(self, stat_name: str, current_value: int,
                            delta: int, stat_points: int) -> bool:
        """Validate mage stat change rules
        
        Rules:
        - Can't manually increase endurance (only via level up)
        - Can't decrease below minimum
        - Need stat points to increase base stats (not elements)
        - Elements can be leveled separately (by training in academy)
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
    
    def validate_element_increase(self, element_name: str, 
                                 current_level: int, 
                                 required_points: int) -> bool:
        """Validate if element can be increased in academy
        
        Elements are trained in academy, not with stat points.
        This is for Dev2 to implement in academy scene.
        """
        if element_name not in self.ELEMENT_NAMES:
            return False
        
        # Element levels have no minimum/maximum (yet - Dev2 can add limits)
        return True
