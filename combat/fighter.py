class Fighter:
    STAT_NAMES = {
        "strength": "Сила",
        "agility": "Ловкость",
        "intuition": "Интуиция",
        "endurance": "Выносливость",
    }

    def __init__(self, name, level=1, auto_allocate=False):
        self.name = name
        self.level = level

        # Базовые характеристики
        self.stats = {
            "strength": 5,
            "agility": 5,
            "intuition": 5,
            "endurance": 5,
        }

        # Очки для распределения
        self.stat_points = 6

        if auto_allocate:
            self.random_allocate_points()

        # Мана
        self.mp = 50
        self.max_mp = 50

        # Опыт
        self.xp = 0

        # Расчёт параметров и полное здоровье
        self.recalculate_parameters()
        self.hp = self.max_hp

    @property
    def strength(self):
        return self.stats["strength"]

    @property
    def agility(self):
        return self.stats["agility"]

    @property
    def intuition(self):
        return self.stats["intuition"]

    @property
    def endurance(self):
        return self.stats["endurance"]

    def recalculate_parameters(self):
        """Пересчитывает производные параметры бойца."""
        self.max_hp = (
            100
            + 20 * (self.level - 1)
            + self.endurance * 14
        )

        self.attack = 18 + 3 * (self.level - 1)
        self.defense = 8 + 2 * (self.level - 1)

    def add_stat(self, stat_name):
        """Добавляет одно очко характеристики."""
        if stat_name not in self.stats:
            return False

        if self.stat_points <= 0:
            return False

        self.stats[stat_name] += 1
        self.stat_points -= 1

        old_max_hp = self.max_hp
        self.recalculate_parameters()

        # При распределении характеристик здоровье должно быть полным.
        # Особенно важно при увеличении выносливости.
        if stat_name == "endurance":
            self.hp += self.max_hp - old_max_hp
        else:
            self.hp = min(self.hp, self.max_hp)

        return True

    def remove_stat(self, stat_name):
        """Убирает одно очко характеристики."""
        if stat_name not in self.stats:
            return False

        # Нельзя уменьшить характеристику ниже 4
        if self.stats[stat_name] <= 4:
            return False

        self.stats[stat_name] -= 1
        self.stat_points += 1

        self.recalculate_parameters()

        # Если максимум уменьшился, текущее здоровье
        # не должно превышать новый максимум.
        self.hp = min(self.hp, self.max_hp)

        return True

    def random_allocate_points(self):
        """Случайно распределяет свободные очки."""
        import random

        while self.stat_points > 0:
            stat_name = random.choice(list(self.stats.keys()))
            self.stats[stat_name] += 1
            self.stat_points -= 1

    def is_ready(self):
        """Проверяет, распределены ли все очки."""
        return self.stat_points == 0

    def is_dead(self):
        """Проверяет, погиб ли боец."""
        return self.hp <= 0

    def take_damage(self, amount):
        """Наносит урон бойцу."""
        self.hp = max(0, self.hp - int(amount))

    def gain_xp(self, amount):
        """Добавляет опыт."""
        self.xp += amount

    def try_level_up(self):
        """Повышает уровень при достаточном количестве опыта."""
        leveled_up = False

        while self.xp >= 60:
            current_hp = self.hp
            self.xp -= 60
            self.level += 1
            self.stat_points += 6

            self.recalculate_parameters()

            # После повышения уровня здоровье полностью восстанавливается
            self.hp = min(current_hp, self.max_hp)
            leveled_up = True

        return leveled_up
