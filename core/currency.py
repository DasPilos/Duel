"""Currency system for the game"""


class Currency:
    """Manages game currency (copper, silver, gold)
    
    Exchange rates:
    - 100 copper = 1 silver
    - 100 silver = 1 gold
    """
    
    COPPER_PER_SILVER = 100
    SILVER_PER_GOLD = 100
    
    def __init__(self, copper=0, silver=0, gold=0):
        """Initialize currency with given amounts"""
        self.copper = int(copper)
        self.silver = int(silver)
        self.gold = int(gold)
    
    @classmethod
    def from_dict(cls, data):
        """Create Currency from dictionary"""
        return cls(
            copper=data.get("copper", 0),
            silver=data.get("silver", 0),
            gold=data.get("gold", 0),
        )
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "copper": self.copper,
            "silver": self.silver,
            "gold": self.gold,
        }
    
    def total_copper(self):
        """Convert all currency to copper"""
        return (
            self.copper +
            self.silver * self.COPPER_PER_SILVER +
            self.gold * self.COPPER_PER_SILVER * self.SILVER_PER_GOLD
        )
    
    def normalize(self):
        """Normalize currency (convert excess copper to silver/gold)"""
        total = self.total_copper()
        
        self.gold = total // (self.COPPER_PER_SILVER * self.SILVER_PER_GOLD)
        remaining = total % (self.COPPER_PER_SILVER * self.SILVER_PER_GOLD)
        
        self.silver = remaining // self.COPPER_PER_SILVER
        self.copper = remaining % self.COPPER_PER_SILVER
        
        return self
    
    @staticmethod
    def normalize_dict(copper, silver, gold):
        """Normalize currency values and return as dict"""
        total = copper + silver * 100 + gold * 10000
        new_gold = total // 10000
        remaining = total % 10000
        new_silver = remaining // 100
        new_copper = remaining % 100
        return {"copper": new_copper, "silver": new_silver, "gold": new_gold}
    
    def add(self, copper=0, silver=0, gold=0):
        """Add currency"""
        self.copper += copper
        self.silver += silver
        self.gold += gold
        self.normalize()
    
    def subtract(self, copper=0, silver=0, gold=0):
        """Subtract currency, returns True if successful"""
        total_needed = (
            copper +
            silver * self.COPPER_PER_SILVER +
            gold * self.COPPER_PER_SILVER * self.SILVER_PER_GOLD
        )
        
        if self.total_copper() < total_needed:
            return False
        
        self.copper -= copper
        self.silver -= silver
        self.gold -= gold
        
        # Handle negative values
        while self.copper < 0:
            if self.silver > 0:
                self.silver -= 1
                self.copper += self.COPPER_PER_SILVER
            else:
                return False
        
        while self.silver < 0:
            if self.gold > 0:
                self.gold -= 1
                self.silver += self.SILVER_PER_GOLD
            else:
                return False
        
        return True
    
    def has_enough(self, copper=0, silver=0, gold=0):
        """Check if player has enough currency"""
        total_needed = (
            copper +
            silver * self.COPPER_PER_SILVER +
            gold * self.COPPER_PER_SILVER * self.SILVER_PER_GOLD
        )
        return self.total_copper() >= total_needed
    
    def __str__(self):
        """String representation"""
        parts = []
        if self.gold > 0:
            parts.append(f"{self.gold}з")
        if self.silver > 0:
            parts.append(f"{self.silver}с")
        if self.copper > 0 or not parts:
            parts.append(f"{self.copper}м")
        return " ".join(parts)
    
    def __repr__(self):
        return f"Currency(copper={self.copper}, silver={self.silver}, gold={self.gold})"
