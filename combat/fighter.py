from combat.character_stats import (
    BASE_STAT_VALUE,
    STARTING_STAT_POINTS,
    adjust_stats,
    calculate_max_hp,
)
from combat.progression import apply_xp


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
            "strength": BASE_STAT_VALUE,
            "agility": BASE_STAT_VALUE,
            "intuition": BASE_STAT_VALUE,
            "endurance": BASE_STAT_VALUE,
        }

        # Очки для распределения
        self.stat_points = STARTING_STAT_POINTS

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
        self.max_hp = calculate_max_hp(self.level, self.endurance)

    def add_stat(self, stat_name):
        """Добавляет одно очко характеристики."""
        updated_state = adjust_stats(
            self.stats,
            self.stat_points,
            self.hp,
            self.max_hp,
            self.level,
            stat_name,
            1,
        )
        if updated_state is None:
            return False

        self.stats.update(updated_state["stats"])
        self.stat_points = updated_state["stat_points"]
        self.hp = updated_state["hp"]
        self.max_hp = updated_state["max_hp"]

        return True

    def remove_stat(self, stat_name):
        """Убирает одно очко характеристики."""
        updated_state = adjust_stats(
            self.stats,
            self.stat_points,
            self.hp,
            self.max_hp,
            self.level,
            stat_name,
            -1,
        )
        if updated_state is None:
            return False

        self.stats.update(updated_state["stats"])
        self.stat_points = updated_state["stat_points"]
        self.hp = updated_state["hp"]
        self.max_hp = updated_state["max_hp"]

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
        return apply_xp(self, 0) > 0
