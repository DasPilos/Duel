"""Base abstract character class for Warrior and Mage"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseCharacter(ABC):
    """Abstract base class for all character types (Warrior, Mage, etc.)
    
    Defines the interface that all character classes must implement.
    Ensures consistent behavior across different character types.
    """
    
    def __init__(self, character_id: int, name: str, level: int):
        self.character_id = character_id
        self.name = name
        self.level = level
    
    @property
    @abstractmethod
    def character_type(self) -> str:
        """Return character type: 'warrior' or 'mage'"""
        pass
    
    @abstractmethod
    def get_stats_names(self) -> List[str]:
        """Return list of stat names for this character type
        
        Returns:
            List of stat names (e.g., ["Сила", "Ловкость", ...])
        """
        pass
    
    @abstractmethod
    def get_base_stats(self) -> Dict[str, int]:
        """Return base stats values for this character type
        
        Returns:
            Dict with stat names as keys and base values as values
        """
        pass
    
    @abstractmethod
    def get_minimum_stat(self, stat_name: str, level: int) -> int:
        """Return minimum value for a stat at given level
        
        Args:
            stat_name: Name of the stat
            level: Character level
            
        Returns:
            Minimum stat value (can't be reduced below this)
        """
        pass
    
    @abstractmethod
    def get_max_hp(self, endurance: int) -> int:
        """Calculate maximum HP based on endurance/equivalent stat
        
        Args:
            endurance: Endurance stat value
            
        Returns:
            Maximum HP value
        """
        pass
    
    @abstractmethod
    def validate_stat_change(self, stat_name: str, current_value: int, 
                            delta: int, stat_points: int) -> bool:
        """Validate if a stat change is allowed
        
        Args:
            stat_name: Name of stat to change
            current_value: Current stat value
            delta: Change amount (-1 or +1)
            stat_points: Available stat points
            
        Returns:
            True if change is allowed, False otherwise
        """
        pass
