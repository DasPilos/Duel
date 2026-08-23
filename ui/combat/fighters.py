class Fighter:
    def __init__(self, name, level=1):
        self.name = name
        self.level = level

        self.max_hp = 100 + 20 * (level - 1)
        self.hp = self.max_hp

        self.attack = 18 + 3 * (level - 1)
        self.defense = 8 + 2 * (level - 1)

        self.xp = 0

    def is_dead(self):
        return self.hp <= 0

    def take_damage(self, dmg):
        self.hp = max(0, self.hp - dmg)

    def gain_xp(self, amount):
        self.xp += amount

    def try_level_up(self):
        leveled = False
        while self.xp >= 60:
            self.xp -= 60
            self.level += 1
            self.max_hp += 20
            self.attack += 3
            self.defense += 2
            self.hp = self.max_hp
            leveled = True
        return leveled
