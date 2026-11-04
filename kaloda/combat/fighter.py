from kaloda.combat.character_stats import (
    BASE_STAT_VALUE,
    UNIQUE_RESOURCE_RECOVERY,
    total_stat_points,
    adjust_stats,
    calculate_max_hp,
    calculate_max_mana,
    calculate_max_unique_resource,
    get_profession_data,
    is_valid_profession,
    minimum_endurance,
    normalize_profession_type,
)
from kaloda.combat.talents import talent_effects
from kaloda.combat.mechanics import weapon_damage_range, weapon_fixed_damage
from kaloda.combat.progression import apply_xp


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
        self.talents = {}

        # Профессия персонажа
        profession_type = normalize_profession_type(profession_type)
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
            "endurance": minimum_endurance(level),
        }
        self._talent_effects = talent_effects(
            self.profession_type, self.talents, self.level
        )
        self.temporary_stat_modifiers = {
            stat_name: 0 for stat_name in self.STAT_NAMES
        }
        # Бонусы надетых предметов (не сохраняются в базовые stats)
        self.equipment_stat_modifiers = {}
        # Надетые предметы {слот: предмет} — для слотов на карточке
        self.equipment = {}
        self.temporary_critical_chance_modifier = 0
        self.temporary_dodge_chance_modifier = 0
        self.next_damage_taken_bonus_percent = 0
        self.next_damage_reduction_percent = 0
        self.incoming_damage_reduction_percent = 0
        self.incoming_damage_bonus_percent = 0
        self.outgoing_damage_bonus_percent = 0
        self.arena_move_range_bonus = 0

        # Базовые бонусы класса
        if profession_type == "archer":
            self.temporary_dodge_chance_modifier += 10  # +10% уворота для лучника

        # Очки для распределения
        self.stat_points = total_stat_points(level)

        if auto_allocate:
            self.random_allocate_points()

        # Уникальный ресурс (ярость, меткость, концентрация или мана)
        self.unique_resource_type = profession_data["unique_resource"]

        # Мана для всех классов (но для магов это main ресурс, для остального минимальная)
        self.max_mp = calculate_max_mana(self.intellect, profession_type)
        self.mp = self.max_mp
        self._unique_resource_max = calculate_max_unique_resource(profession_type, level, self.intellect)
        self._unique_resource_current = self._unique_resource_max

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
            + self.equipment_stat_modifiers.get(stat_name, 0)
            + self._talent_effects["all_stats"],
        )

    @property
    def weapon_damage(self):
        """(мин, макс) урона надетого оружия или None"""
        return weapon_damage_range(self.equipment)

    def roll_weapon_damage(self, rng=None):
        """Фиксированный урон оружия для одного удара (максимум, 0 без оружия)"""
        return weapon_fixed_damage(self.equipment)

    def adjust_temporary_stat(self, stat_name, amount):
        if stat_name not in self.temporary_stat_modifiers:
            raise ValueError(f"Неизвестная характеристика: {stat_name}")
        self.temporary_stat_modifiers[stat_name] += int(amount)

    def recalculate_parameters(self):
        """Пересчитывает производные параметры бойца."""
        self._talent_effects = talent_effects(
            self.profession_type, self.talents, self.level
        )
        bonuses = self._talent_effects
        hp_bonus = int(getattr(self, "equipment_stat_modifiers", {}).get("hp", 0))
        mp_bonus = int(getattr(self, "equipment_stat_modifiers", {}).get("mp", 0))
        hp_bonus += bonuses["max_hp"] + bonuses["strength_max_hp"] * self.strength
        self.max_hp = calculate_max_hp(self.level, self.endurance, self.profession_type) + hp_bonus
        if hasattr(self, "hp"):
            self.hp = min(int(self.hp), self.max_hp)
        mp_bonus += bonuses["max_mana"] + bonuses["wisdom_max_mana"] * self.wisdom
        if self.unique_resource_type == "mana":
            mp_bonus += bonuses["max_resource"]
        self.max_mp = calculate_max_mana(self.intellect, self.profession_type) + mp_bonus
        if hasattr(self, "mp"):
            self.mp = min(int(self.mp), self.max_mp)
        # Пересчитать максимум уникального ресурса
        if self.unique_resource_type != "mana":
            self._unique_resource_max = (
                calculate_max_unique_resource(
                    self.profession_type, self.level, self.intellect
                )
                + bonuses["max_resource"]
            )
        if hasattr(self, "unique_resource_current"):
            self.unique_resource_current = min(
                int(self.unique_resource_current), self.unique_resource_max
            )

    def set_profession(self, profession_type):
        """Сменить класс бойца по профилю персонажа (ресурс класса, бонус лучника)."""
        profession_type = normalize_profession_type(profession_type)
        if not is_valid_profession(profession_type) or profession_type == self.profession_type:
            return
        if self.profession_type == "archer":
            self.temporary_dodge_chance_modifier -= 10
        if profession_type == "archer":
            self.temporary_dodge_chance_modifier += 10
        self.profession_type = profession_type
        self.unique_resource_type = get_profession_data(profession_type)["unique_resource"]
        self._unique_resource_max = calculate_max_unique_resource(profession_type, self.level, self.intellect)
        self._unique_resource_current = self._unique_resource_max
        self.recalculate_parameters()

    def set_talents(self, talents):
        self.talents = dict(talents or {})
        self.recalculate_parameters()

    @property
    def unique_resource_max(self):
        # У мага уникальный ресурс — это мана, отдельного пула нет
        if self.unique_resource_type == "mana":
            return self.max_mp
        return self._unique_resource_max

    @unique_resource_max.setter
    def unique_resource_max(self, value):
        self._unique_resource_max = value

    @property
    def unique_resource_current(self):
        if self.unique_resource_type == "mana":
            return self.mp
        return self._unique_resource_current

    @unique_resource_current.setter
    def unique_resource_current(self, value):
        if self.unique_resource_type == "mana":
            self.mp = value
        else:
            self._unique_resource_current = value

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
        """Восстановить уникальный ресурс в конце хода."""
        bonus = self._talent_effects["resource_regen"]
        if self.unique_resource_type == "necrotism":
            self.gain_unique_resource(8 + int(level) + bonus)
            return
        if self.unique_resource_type in UNIQUE_RESOURCE_RECOVERY:
            recovery = UNIQUE_RESOURCE_RECOVERY[self.unique_resource_type]
            self.gain_unique_resource(recovery + bonus)

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
            profession_type=self.profession_type,
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
            profession_type=self.profession_type,
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
