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

    @classmethod
    def to_copper(cls, copper=0, silver=0, gold=0):
        """Convert denomination inputs into the game's single copper-value unit."""
        return (
            int(copper)
            + int(silver) * cls.COPPER_PER_SILVER
            + int(gold) * cls.COPPER_PER_SILVER * cls.SILVER_PER_GOLD
        )

    @property
    def total_silver(self):
        """Whole-silver value of the unified balance, for silver-denominated legacy costs."""
        return self.total_copper() // self.COPPER_PER_SILVER
    
    def total_copper(self):
        """Convert all currency to copper"""
        return self.to_copper(self.copper, self.silver, self.gold)

    @classmethod
    def format_amount(cls, total_copper):
        """Format any price in copper as its normalized gold/silver/copper amount."""
        gold, remainder = divmod(max(0, int(total_copper)), cls.COPPER_PER_SILVER * cls.SILVER_PER_GOLD)
        silver, copper = divmod(remainder, cls.COPPER_PER_SILVER)
        parts = []
        if gold:
            parts.append(f"{gold} {'золото' if gold == 1 else 'золота'}")
        if silver:
            parts.append(f"{silver} {'серебро' if silver == 1 else 'серебра'}")
        if copper or not parts:
            parts.append(f"{copper} {'медь' if copper == 1 else 'меди'}")
        return " ".join(parts)
    
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
        return Currency(copper, silver, gold).normalize().to_dict()

    def add_copper_amount(self, amount):
        self.copper += int(amount)
        return self.normalize()

    def has_enough_copper(self, amount):
        amount = int(amount)
        return amount >= 0 and self.total_copper() >= amount

    def subtract_copper_amount(self, amount):
        amount = int(amount)
        if amount < 0 or not self.has_enough_copper(amount):
            return False
        remaining = self.total_copper() - amount
        self.copper, self.silver, self.gold = remaining, 0, 0
        self.normalize()
        return True
    
    def add(self, copper=0, silver=0, gold=0):
        """Add denomination inputs through the unified copper balance."""
        return self.add_copper_amount(self.to_copper(copper, silver, gold))
    
    def subtract(self, copper=0, silver=0, gold=0):
        """Subtract denomination inputs through the unified copper balance."""
        return self.subtract_copper_amount(self.to_copper(copper, silver, gold))
    
    def has_enough(self, copper=0, silver=0, gold=0):
        """Check denomination inputs against the unified copper balance."""
        return self.has_enough_copper(self.to_copper(copper, silver, gold))
    
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
