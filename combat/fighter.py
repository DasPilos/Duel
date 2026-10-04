from combat.character_stats import (
    BASE_STAT_VALUE,
    STARTING_ENDURANCE_VALUE,
    STARTING_STAT_POINTS,
    PROFESSIONS,
    UNIQUE_RESOURCE_RECOVERY,
    UNIQUE_RESOURCE_GAIN,
    total_stat_points,
    adjust_stats,
    calculate_max_hp,
    calculate_max_mana,
    calculate_max_unique_resource,
    get_profession_data,
    is_valid_profession,
)
from combat.mechanics import weapon_damage_range
from combat.progression import apply_xp


class Fighter:
    STAT_NAMES = {
        "strength": "Сила",
        "agility": "Ловкость",
        "intuition": "Интуиция",
        "wisdom": "Мудрость",
        "intellect": "Интеллект",
        "harmony": "Гармония",
        "endurance": "Выносливость",
    }

    def __init__(self, name, level=1, profession_type="warrior", auto_allocate=False):
        self.name = name
        self.level = level
        self.character_id = None

        # Профессия персонажа (6 классов)
        if not is_valid_profession(profession_type):
            profession_type = "warrior"  # Default to warrior
        self.profession_type = profession_type
        profession_data = get_profession_data(profession_type)

        # Базовые характеристики — единый набор из 7 статов для всех персонажей
        self.stats = {
            "strength": BASE_STAT_VALUE,
            "agility": BASE_STAT_VALUE,
            "intuition": BASE_STAT_VALUE,
            "wisdom": BASE_STAT_VALUE,
            "intellect": BASE_STAT_VALUE,
            "harmony": BASE_STAT_VALUE,
            "endurance": STARTING_ENDURANCE_VALUE + max(0, int(level) - 1),
        }
        self.temporary_stat_modifiers = {
            stat_name: 0 for stat_name in self.STAT_NAMES
        }
        # Бонусы надетых предметов (не сохраняются в базовые stats)
        self.equipment_stat_modifiers = {}
        # Надетые предметы {слот: предмет} — для слотов на карточке
        self.equipment = {}
        self.temporary_critical_chance_modifier = 0
        self.temporary_dodge_chance_modifier = 0

        # Базовые бонусы класса
        if profession_type == "archer":
            self.temporary_dodge_chance_modifier += 10  # +10% уворота для лучника

        # Очки для распределения
        self.stat_points = total_stat_points(level)

        if auto_allocate:
            self.random_allocate_points()

        # Уникальный ресурс (ярость, меткость, концентрация или мана)
        self.unique_resource_type = profession_data["unique_resource"]
        self.unique_resource_max = calculate_max_unique_resource(profession_type, level, self.intellect)
        self.unique_resource_current = self.unique_resource_max

        # Мана для всех классов (но для магов это main ресурс, для остального минимальная)
        self.max_mp = calculate_max_mana(self.intellect)
        self.mp = self.max_mp

        # Опыт
        self.xp = 0

        # Расчёт параметров и полное здоровье
        self.recalculate_parameters()
        self.hp = self.max_hp

    @property
    def strength(self):
        return self._effective_stat("strength")

    @property
    def agility(self):
        return self._effective_stat("agility")

    @property
    def intuition(self):
        return self._effective_stat("intuition")

    @property
    def wisdom(self):
        return self._effective_stat("wisdom")

    @property
    def intellect(self):
        return self._effective_stat("intellect")

    @property
    def harmony(self):
        return self._effective_stat("harmony")

    @property
    def endurance(self):
        return self._effective_stat("endurance")

    def _effective_stat(self, stat_name):
        return max(
            0,
            self.stats[stat_name]
            + self.temporary_stat_modifiers[stat_name]
            + self.equipment_stat_modifiers.get(stat_name, 0),
        )

    @property
    def weapon_damage(self):
        """(мин, макс) урона надетого оружия или None"""
        return weapon_damage_range(self.equipment)

    def roll_weapon_damage(self, rng):
        """Случайный урон оружия для одного удара (0 без оружия)"""
        damage = self.weapon_damage
        return rng.randint(*damage) if damage else 0

    def adjust_temporary_stat(self, stat_name, amount):
        if stat_name not in self.temporary_stat_modifiers:
            raise ValueError(f"Неизвестная характеристика: {stat_name}")
        self.temporary_stat_modifiers[stat_name] += int(amount)

    def recalculate_parameters(self):
        """Пересчитывает производные параметры бойца."""
        hp_bonus = int(getattr(self, "equipment_stat_modifiers", {}).get("hp", 0))
        mp_bonus = int(getattr(self, "equipment_stat_modifiers", {}).get("mp", 0))
        self.max_hp = calculate_max_hp(self.level, self.endurance) + hp_bonus
        if hasattr(self, "hp"):
            self.hp = min(int(self.hp), self.max_hp)
        self.max_mp = calculate_max_mana(self.intellect) + mp_bonus
        if hasattr(self, "mp"):
            self.mp = min(int(self.mp), self.max_mp)
        # Пересчитать максимум уникального ресурса
        if hasattr(self, "profession_type"):
            self.unique_resource_max = calculate_max_unique_resource(self.profession_type, self.level, self.intellect)
            if hasattr(self, "unique_resource_current"):
                self.unique_resource_current = min(int(self.unique_resource_current), self.unique_resource_max)

    def set_profession(self, profession_type):
        """Сменить класс бойца по профилю персонажа (ресурс класса, бонус лучника)."""
        if profession_type == "mage":  # старый тип персонажа
            profession_type = "battle_mage"
        if not is_valid_profession(profession_type) or profession_type == self.profession_type:
            return
        if self.profession_type == "archer":
            self.temporary_dodge_chance_modifier -= 10
        if profession_type == "archer":
            self.temporary_dodge_chance_modifier += 10
        self.profession_type = profession_type
        self.unique_resource_type = get_profession_data(profession_type)["unique_resource"]
        self.unique_resource_max = calculate_max_unique_resource(profession_type, self.level, self.intellect)
        self.unique_resource_current = self.unique_resource_max

    def spend_unique_resource(self, amount):
        """Потратить уникальный ресурс (ярость, меткость, концентрация, мана)."""
        amount = int(amount)
        if self.unique_resource_current >= amount:
            self.unique_resource_current -= amount
            return True
        return False

    def gain_unique_resource(self, amount):
        """Получить уникальный ресурс."""
        amount = int(amount)
        self.unique_resource_current = min(self.unique_resource_current + amount, self.unique_resource_max)

    def recover_unique_resource(self, level):
        """Восстановить уникальный ресурс в конце хода (для ярости, меткости, концентрации)."""
        if self.unique_resource_type in UNIQUE_RESOURCE_RECOVERY:
            recovery = UNIQUE_RESOURCE_RECOVERY[self.unique_resource_type]
            self.gain_unique_resource(recovery)

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
            character_id=self.character_id,
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
            character_id=self.character_id,
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
