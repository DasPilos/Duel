import json
import random
import sqlite3
from dataclasses import dataclass
from pathlib import Path


DATABASE_PATH = Path(__file__).resolve().parent.parent / "cards.sqlite3"
BATTLE_CARD_REWARD_CHANCE = 20


@dataclass(frozen=True)
class Card:
    key: str
    name: str
    group_name: str
    # Затраты action points (старая система для физических карт)
    strength_cost: int
    intuition_cost: int
    agility_cost: int
    endurance_cost: int
    # Новая система: явный тип и затрата ресурса
    resource_type: str = "action_points"  # "action_points", "mana", "rage", "accuracy", "concentration"
    resource_cost: int = 0  # Затрата уникального ресурса (для новых карт)
    # Эффекты
    effect_type: str = ""
    effect_data: dict = None
    level: int = 1
    # Экономика
    price_copper: int = 0
    price_silver: int = 0
    price_gold: int = 0
    drop_chance: float = 0.0
    image_path: str = ""
    effect_duration: int = 0
    # Старое поле мана_cost (для обратной совместимости)
    mana_cost: int = 0

    def __post_init__(self):
        # Убедиться что effect_data не None
        if self.effect_data is None:
            object.__setattr__(self, 'effect_data', {})

    @property
    def costs(self):
        """Затраты action points (для старых карт)."""
        return {
            "strength": self.strength_cost,
            "intuition": self.intuition_cost,
            "agility": self.agility_cost,
            "endurance": self.endurance_cost
        }


# Список карт очищен: будем собирать набор заново с нуля.
# Физические карты бойца (воина) убраны из игры — доступны только магические карты.
BASE_CARDS = ()


def _mage_card(key, name, element, mana_cost, effect_type, effect_data, duration=0):
    """Создать магическую карту (для всех магических классов)."""
    return Card(
        key=key,
        name=name,
        group_name=f"Магия: {element}",
        strength_cost=0,
        intuition_cost=0,
        agility_cost=0,
        endurance_cost=0,
        resource_type="mana",
        resource_cost=mana_cost,
        effect_type=effect_type,
        effect_data={"element": element, **effect_data},
        level=1,
        drop_chance=0,
        effect_duration=duration,
        mana_cost=mana_cost,
    )


def _warrior_card(key, name, style, resource_cost, effect_type, effect_data, duration=0):
    """Создать карту бойца (использует ярость)."""
    return Card(
        key=key,
        name=name,
        group_name=f"Боец: {style}",
        strength_cost=0,
        intuition_cost=0,
        agility_cost=0,
        endurance_cost=0,
        resource_type="rage",
        resource_cost=resource_cost,
        effect_type=effect_type,
        effect_data=effect_data,
        level=1,
        drop_chance=0,
        effect_duration=duration,
    )


def _archer_card(key, name, style, resource_cost, effect_type, effect_data, duration=0):
    """Создать карту лучника (использует меткость)."""
    return Card(
        key=key,
        name=name,
        group_name=f"Лучник: {style}",
        strength_cost=0,
        intuition_cost=0,
        agility_cost=0,
        endurance_cost=0,
        resource_type="accuracy",
        resource_cost=resource_cost,
        effect_type=effect_type,
        effect_data=effect_data,
        level=1,
        drop_chance=0,
        effect_duration=duration,
    )


def _assassin_card(key, name, style, resource_cost, effect_type, effect_data, duration=0):
    """Создать карту асасина (использует концентрацию)."""
    return Card(
        key=key,
        name=name,
        group_name=f"Асасин: {style}",
        strength_cost=0,
        intuition_cost=0,
        agility_cost=0,
        endurance_cost=0,
        resource_type="concentration",
        resource_cost=resource_cost,
        effect_type=effect_type,
        effect_data=effect_data,
        level=1,
        drop_chance=0,
        effect_duration=duration,
    )


MAGE_CARDS = (
    # Огонь: 6 карт
    _mage_card("mage_flash", "Вспышка", "Огонь", 6, "mage_damage_status", {"damage": 4, "status": "огонь", "status_duration": 1}),
    _mage_card("mage_fireball", "Фаербол", "Огонь", 14, "mage_damage_status", {"damage": 9, "status": "огонь", "status_duration": 2, "stacks": 2}),
    _mage_card("mage_crimson_blood", "Багровая кровь", "Огонь", 16, "mage_reactive_blessing", {"status": "огонь", "status_duration": 2, "retaliation_damage": 2, "retaliation_status_duration": 1}, 2),
    _mage_card("mage_burning_support", "Пылающая поддержка", "Огонь", 10, "mage_damage_buff", {"status": "огонь", "status_duration": 2, "damage_percent": 25, "harmony_percent": 1}, 2),
    _mage_card("mage_fervent_service", "Пылкая услуга", "Огонь", 0, "mage_hp_for_mana", {"hp_percent": 7, "mana_percent": 21}),
    _mage_card("mage_pyromania", "Пиромания", "Огонь", 47, "mage_area_damage_status", {"damage": 5, "wisdom_damage": 2, "status": "огонь", "status_duration": 3, "stacks": 3, "ultimate": True, "cast_turns": 1}, 1),
    # Вода: 6 карт
    _mage_card("mage_water_summon", "Призыв воды", "Вода", 4, "mage_damage_status", {"damage": 3, "status": "вода", "status_duration": 1}),
    _mage_card("mage_rising_flow", "Восходящий поток", "Вода", 9, "mage_area_damage_status", {"damage": 7, "status": "вода", "status_duration": 2}, 2),
    _mage_card("mage_flow_blessing", "Благословение потока", "Вода", 13, "mage_heal_missing_hp", {"missing_hp_percent": 30, "intellect_hp": 1}),
    _mage_card("mage_water_guard", "Водяная защита", "Вода", 13, "mage_health_buff", {"status": "вода", "bonus_hp": 8, "intellect_hp": 2}),
    _mage_card("mage_waterfall", "Водопад", "Вода", 18, "mage_damage_status", {"damage": 12, "status": "вода", "status_duration": 2, "damage_percent": -8, "intellect_percent": 2}, 2),
    _mage_card("mage_gurgling_flow", "Журчащий поток", "Вода", 45, "mage_heal_missing_hp", {"missing_hp_percent": 10, "intellect_hp": 1, "shield_hp": 15, "intellect_shield": 1, "damage_percent": 15, "ultimate": True, "cast_turns": 1}, 1),
    # Земля: 6 карт
    _mage_card("mage_boulder_summon", "Призыв валуна", "Земля", 6, "mage_damage", {"damage": 7}),
    _mage_card("mage_earth_spikes", "Иглы земли", "Земля", 24, "mage_area_damage", {"damage": 15}),
    _mage_card("mage_stone_barrages", "Каменные заслоны", "Земля", 15, "mage_team_health_buff", {"bonus_hp": 10, "wisdom_hp": 1}),
    _mage_card("mage_golem_summon", "Призыв голема", "Земля", 29, "mage_golem", {"hp": 16, "wisdom_hp": 1, "damage": 2, "wisdom_damage": 1, "stun_every": 3, "stun_damage": 8}),
    _mage_card("mage_mineral_armor", "Броня из минералов", "Земля", 18, "mage_damage_resistance", {"damage_percent": -20, "wisdom_percent": 0.5}, 2),
    _mage_card("mage_stone_spikes", "Каменные шипы", "Земля", 0, "mage_damage", {"damage": 40, "wisdom_percent": 3, "ultimate": True, "cast_turns": 1}),
    # Электричество: 6 карт
    _mage_card("mage_lightning_strike", "Удар молнии", "Электричество", 5, "mage_damage_status", {"damage": 4, "status": "электро", "status_duration": 3}),
    _mage_card("mage_thundercloud", "Громовая туча", "Электричество", 14, "mage_cloud", {"duration": 2, "harmony_duration": 6, "damage": 3, "status": "электро"}, 2),
    _mage_card("mage_paralysis", "Паралич", "Электричество", 20, "mage_stun_status", {"stun_duration": 1, "status": "электро", "status_duration": 3}),
    _mage_card("mage_lightning_punishment", "Просвещение молний", "Электричество", 0, "mage_restore_mana", {"missing_mana_percent": 25, "harmony_percent": 0.25, "max_mana_percent": 30}),
    _mage_card("mage_shift", "Сдвиг", "Электричество", 26, "mage_dodge_buff", {"dodge_percent": 30, "intellect_percent": 0.35}, 2),
    _mage_card("mage_raging_storm", "Бушующий шторм", "Электричество", 50, "mage_stun_status", {"damage": 11, "stun_duration": 1, "status": "электро", "status_duration": 3, "ultimate": True, "cast_turns": 1}, 1),
    # Воздух: 6 карт
    _mage_card("mage_wind_gust", "Порыв ветра", "Воздух", 9, "mage_wind_gust", {"damage": 4, "status_reduction": 1, "removed_damage": 3}),
    _mage_card("mage_raging_cyclone", "Бушующий циклон", "Воздух", 17, "mage_cleanse_area", {"damage": 5, "remove_statuses": True}),
    _mage_card("mage_magic_destruction", "Разрушение магии", "Воздух", 21, "mage_cleanse_ally", {"removed_heal": 8}),
    _mage_card("mage_headwind", "Встречный ветер", "Воздух", 18, "mage_damage_debuff", {"damage_percent": -20, "harmony_percent": -1, "duration": 2}, 2),
    _mage_card("mage_tailwind", "Попутный ветер", "Воздух", 11, "mage_team_damage_buff", {"damage_percent": 10, "harmony_percent": 0.5, "duration": 2}, 2),
    _mage_card("mage_wild_wind", "Wild Wind", "Воздух", 53, "mage_cleanse_area", {"damage": 5, "removed_damage": 15, "harmony_damage": 5, "remove_statuses": True, "ultimate": True, "cast_turns": 1}, 1),
    # Холод: 6 карт
    _mage_card("mage_icicle", "Сосулька", "Холод", 5, "mage_damage_status", {"damage": 5, "status": "холод", "status_duration": 1}),
    _mage_card("mage_ice_block", "Ледяная глыба", "Холод", 10, "mage_area_damage_status", {"damage": 8, "status": "холод", "status_duration": 1}),
    _mage_card("mage_ice_pillar", "Ледяная опора", "Холод", 13, "mage_health_buff", {"status": "холод", "bonus_hp": 1, "intellect_hp": 4}),
    _mage_card("mage_frozen_offering", "Ледяное подношение", "Холод", 4, "mage_mana_regen_buff", {"status": "холод", "status_duration": 2, "mana": 5, "intellect_mana": 2}, 2),
    _mage_card("mage_snowball", "Снежный ком", "Холод", 23, "mage_area_damage_status", {"damage": 11, "enemy_damage": 6, "status": "холод", "status_duration": 1}),
    _mage_card("mage_raging_frost", "Бушующая стужа", "Холод", 55, "mage_area_damage", {"damage": 20, "intellect_damage": 4, "ultimate": True, "cast_turns": 1}, 1),
)

# Карты воина (21 карта: 3 стиля × 7 карт)
WARRIOR_CARDS = (
    # Искусство войны: Кровавая жатва (7 карт)
    _warrior_card("warrior_slash", "Разрез", "Кровавая жатва", 11, "damage", {"dice": "1d8", "bleed_percent": 8}),
    _warrior_card("warrior_hack", "Рубка", "Кровавая жатва", 20, "damage", {"dice": "2d8", "bleed_percent": 12}),
    _warrior_card("warrior_bleeding_strike", "Кровоточащий удар", "Кровавая жатва", 15, "damage", {"dice": "1d6", "hits": 3, "bleed_percent": 8}),
    _warrior_card("warrior_crimson_harvest", "Багровая жатва", "Кровавая жатва", 17, "damage_buff", {"bleed_healing_percent": 15}, 2),
    _warrior_card("warrior_arterial_cut", "Артериальный разрез", "Кровавая жатва", 20, "damage_debuff", {"dice": "1d4", "bleed_percent": 6, "duration": 3}),
    _warrior_card("warrior_blood_ritual", "Кровавый ритуал", "Кровавая жатва", 0, "damage_recoil", {"hp_percent": 9, "bleed_increase": 3}, 3),
    _warrior_card("warrior_blood_frenzy", "Кровавое безумие", "Кровавая жатва", 48, "damage", {"dice": "2d10", "bleed_percent": 20, "follow_up_bleed": 10, "ultimate": True}),

    # Танец клинка Урииля (7 карт)
    _warrior_card("warrior_quick_slash", "Быстрый разрез", "Танец клинка", 9, "damage", {"dice": "1d8", "hits": 2}),
    _warrior_card("warrior_multi_strike", "Множественный удар", "Танец клинка", 16, "damage", {"dice": "1d6", "hits": 3, "target_count": 3}),
    _warrior_card("warrior_marked_cut", "Меченый разрез", "Танец клинка", 23, "damage", {"dice": "1d6", "hits": 2, "mark_damage": 4, "mark_strength": 1}),
    _warrior_card("warrior_stun_counter", "Оглушающий ответ", "Танец клинка", 11, "damage_buff", {"hit_bonus": 1, "stun_after_hits": 8}, 2),
    _warrior_card("warrior_flurry", "Град ударов", "Танец клинца", 9, "damage_buff", {"extra_hits": 1}, 2),
    _warrior_card("warrior_dance_regen", "Танец регенерации", "Танец клинка", 0, "damage_buff", {"regen_percent": 1, "regen_max_hp": 1}, 3),
    _warrior_card("warrior_uriel_dance", "Танец Урииля", "Танец клинка", 58, "damage", {"dice": "1d6", "hits": 6, "target_count": 4, "ultimate": True}),

    # Стиль бога Валентайна (7 карт)
    _warrior_card("warrior_valen_strike", "Удар Валентайна", "Стиль Валентайна", 12, "damage", {"dice": "1d10", "heal_percent": 4}),
    _warrior_card("warrior_valen_cleave", "Раскол Валентайна", "Стиль Валентайна", 22, "damage", {"dice": "2d8", "heal_percent": 10}),
    _warrior_card("warrior_valen_sweep", "Размах Валентайна", "Стиль Валентайна", 19, "damage", {"dice": "1d8", "hits": 3, "heal_percent": 3}),
    _warrior_card("warrior_bleeding_blessing", "Кровавое благословение", "Стиль Валентайна", 9, "damage_buff", {"missing_hp_damage": 1, "duration": 3}),
    _warrior_card("warrior_blood_pact", "Кровавый договор", "Стиль Валентайна", 0, "damage_recoil", {"hp_percent": 20, "damage_buff_percent": 23, "duration": 3}),
    _warrior_card("warrior_blessing_theft", "Кража благословения", "Стиль Валентайна", 25, "damage", {"dice": "2d6", "steal_healing_percent": 50, "duration": 2}),
    _warrior_card("warrior_valentine_transcendence", "Трансценденция Валентайна", "Стиль Валентайна", 68, "damage", {"dice": "1d12", "full_heal": True, "damage_buff_percent": 21, "ultimate": True}, 2),
)

# Карты лучника (24 карты: 3 стиля × 8 карт)
ARCHER_CARDS = (
    # Стрела Души (8 карт - духовный урон)
    _archer_card("archer_soul_arrow", "Стрела Души", "Стрела Души", 14, "damage", {"dice": "2d8", "spiritual": True}),
    _archer_card("archer_soul_volley", "Залп Стрел Души", "Стрела Души", 22, "damage", {"dice": "3d8", "spiritual": True}),
    _archer_card("archer_soul_rain", "Дождь Стрел Душ", "Стрела Души", 11, "damage", {"dice": "1d6", "hits": 3, "spiritual": True}),
    _archer_card("archer_soul_evasion", "Уклонение Души", "Стрела Души", 10, "damage_buff", {"dodge_percent": 20, "duration": 2}),
    _archer_card("archer_soul_precision", "Точность Души", "Стрела Души", 14, "damage_buff", {"accuracy_bonus": 1, "accuracy_strength": 5, "duration": 4}),
    _archer_card("archer_soul_mark", "Метка Души", "Стрела Души", 30, "damage", {"dice": "2d8", "spiritual": True, "spiritual_split": 50}),
    _archer_card("archer_soul_dodge_counter", "Ответ на Уклонение", "Стрела Души", 15, "damage_buff", {"dodge_damage_bonus": 15, "dodge_stacks": 2, "duration": 2}),
    _archer_card("archer_soul_transcendence", "Трансценденция Стрел", "Стрела Души", 0, "damage", {"dice": "4d8", "spiritual": True, "spiritual_split": 65, "hunt": True, "ultimate": True}),

    # Бог Севера (7 карт - манальное выжигание)
    _archer_card("archer_north_strike", "Удар Севера", "Бог Севера", 7, "damage", {"dice": "1d8", "burn_mana": 7, "burn_damage_percent": 3}),
    _archer_card("archer_north_blast", "Взрыв Севера", "Бог Севера", 12, "damage", {"dice": "2d8", "burn_mana": 12, "burn_damage_percent": 5}),
    _archer_card("archer_north_salvo", "Залп Севера", "Бог Севера", 15, "damage", {"dice": "1d4", "hits": 3, "burn_mana": 12, "burn_damage_percent": 7}),
    _archer_card("archer_north_mana_burn", "Сжигание Маны", "Бог Севера", 9, "damage_buff", {"burn_mana_percent": 2, "duration": 2}),
    _archer_card("archer_north_drain", "Слив Маны", "Бог Севера", 0, "damage", {"burn_mana_percent": 50}),
    _archer_card("archer_north_weakening", "Ослабление Севера", "Бог Севера", 24, "damage", {"dice": "1d8", "burn_mana": 8, "mana_regen_debuff": 30, "duration": 2}),
    _archer_card("archer_north_devastation", "Опустошение Севера", "Бог Севера", 39, "damage", {"dice": "2d8", "burn_mana": 20, "burn_mana_percent": 20, "burn_damage_percent": 11, "hunt": True, "ultimate": True}),

    # Проворный герой (7 карт - уворот и крит)
    _archer_card("archer_quick_shot", "Быстрый выстрел", "Проворный герой", 8, "damage", {"dice": "1d10", "hit_bonus": 10}),
    _archer_card("archer_piercing_shot", "Пронзающий выстрел", "Проворный герой", 14, "damage", {"dice": "2d8", "hit_bonus": 0, "stun_on_dodge": True}),
    _archer_card("archer_barrage", "Град Стрел", "Проворный герой", 20, "damage", {"dice": "1d6", "hits": 8, "hit_bonus_scale": 1, "crit_bonus_scale": 2}),
    _archer_card("archer_dodge_counter", "Ответ на Уклонение", "Проворный герой", 21, "damage_buff", {"dodge_damage_bonus": 10, "damage_buff_percent": 10, "duration": 1}),
    _archer_card("archer_hunt_stance", "Охота", "Проворный герой", 35, "damage", {"dice": "3d8", "no_miss": True, "hunt": True}),
    _archer_card("archer_blood_sacrifice", "Кровавая Жертва", "Проворный герой", 0, "damage_debuff", {"hp_percent": 20, "mana_percent": 25, "accuracy_bonus": 10}),
    _archer_card("archer_forest_spirit", "Лесной Дух", "Проворный герой", 36, "damage", {"summon_spirit": True, "spirit_hp": 30, "spirit_mana": 15, "spirit_dodge": 15, "ultimate": True}),
)

# Карты асасина (24 карты: 3 стиля × 8 карт)
ASSASSIN_CARDS = (
    # Ядовитый Бог (7 карт)
    _assassin_card("assassin_poison_strike", "Ядовитый удар", "Ядовитый Бог", 5, "damage", {"dice": "1d6", "poison": 1}),
    _assassin_card("assassin_poison_blade", "Ядовитый клинок", "Ядовитый Бог", 13, "damage", {"dice": "1d8", "poison": 2}),
    _assassin_card("assassin_poison_rain", "Ядовитый дождь", "Ядовитый Бог", 8, "damage", {"dice": "1d4", "hits": 3, "poison": 1}),
    _assassin_card("assassin_poison_infusion", "Ядовитое Внедрение", "Ядовитый Бог", 15, "damage_buff", {"crit_chance_percent": 15}),
    _assassin_card("assassin_poison_cascade", "Ядовитый Каскад", "Ядовитый Бог", 16, "damage", {"poison": 3, "poison_spread": 2}),
    _assassin_card("assassin_poison_extraction", "Ядовитое Извлечение", "Ядовитый Бог", 5, "damage", {"poison_extraction": True, "crit_chance_percent": 2, "crit_damage_percent": 4}),
    _assassin_card("assassin_poison_execution", "Ядовитая Казнь", "Ядовитый Бог", 26, "damage", {"poison_damage_multiplier": 8, "poison_crit_percent": 2, "poison_crit_damage_percent": 4, "ultimate": True}),

    # Роковой проблеск (8 карт)
    _assassin_card("assassin_fate_strike", "Роковой Удар", "Роковой проблеск", 5, "damage", {"dice": "1d6", "crit_damage_percent": 15}, 2),
    _assassin_card("assassin_fate_combo", "Роковой Комбо", "Роковой проблеск", 9, "damage", {"dice": "1d6", "hits": 2, "crit_chance_percent": 5}, 2),
    _assassin_card("assassin_fate_blade", "Роковой Клинок", "Роковой проблеск", 18, "damage", {"dice": "2d8"}),
    _assassin_card("assassin_fate_enhance", "Роковое Улучшение", "Роковой проблеск", 26, "damage_buff", {"crit_damage_conversion": 0.1, "duration": 5}),
    _assassin_card("assassin_fate_crit_synergy", "Роковая Синергия", "Роковой проблеск", 12, "damage", {"dice": "1d8", "crit_guarantee": True, "crit_damage_buff": 20}),
    _assassin_card("assassin_fate_precision", "Роковая Точность", "Роковой проблеск", 10, "damage", {"dice": "1d6", "hits": 2, "damage_split": "targets"}),
    _assassin_card("assassin_thirst_blood", "Жажда Крови", "Роковой проблеск", 0, "damage_buff", {"crit_chance_guarantee": 100, "next_hits_no_crit": 2}),
    _assassin_card("assassin_fate_transcendence", "Роковая Трансценденция", "Роковой проблеск", 50, "damage", {"dice": "3d8", "stance": True, "ultimate": True}),

    # Бог Севера (7 карт - манальное выжигание + крит)
    _assassin_card("assassin_north_puncture", "Прокол Севера", "Бог Севера", 7, "damage", {"dice": "1d8", "burn_mana": 9, "crit_on_no_mana": 30}),
    _assassin_card("assassin_north_double", "Двойной Удар Севера", "Бог Севера", 12, "damage", {"dice": "1d6", "hits": 2, "burn_mana": 7, "crit_on_no_mana": 40}),
    _assassin_card("assassin_north_spear", "Копье Севера", "Бог Севера", 19, "damage", {"dice": "2d8", "burn_mana": 5, "crit_on_no_mana": 40}),
    _assassin_card("assassin_north_burn_infusion", "Сжигание Инфузия", "Бог Севера", 6, "damage_buff", {"burn_mana_percent": 5, "duration": 2}),
    _assassin_card("assassin_north_drain_crit", "Дренаж Крита", "Бог Севера", 15, "damage", {"burn_mana": 15, "crit_chance_percent": 15, "crit_damage_percent": 10}),
    _assassin_card("assassin_north_cold_drain", "Холодный Дренаж", "Бог Севера", 23, "damage", {"burn_mana_percent": 100, "mana_restore_percent": 20}),
    _assassin_card("assassin_north_chaos", "Хаос Севера", "Бог Севера", 47, "damage", {"dice": "1d8", "burn_mana": 35, "burn_mana_percent": 20, "crit_on_no_mana": 50, "ultimate": True}),
)

BASE_CARDS = BASE_CARDS + MAGE_CARDS + WARRIOR_CARDS + ARCHER_CARDS + ASSASSIN_CARDS


def initialize_database(path=DATABASE_PATH):
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS cards (
            key TEXT PRIMARY KEY, name TEXT NOT NULL, group_name TEXT NOT NULL,
            strength_cost INTEGER NOT NULL, intuition_cost INTEGER NOT NULL,
            agility_cost INTEGER NOT NULL, endurance_cost INTEGER NOT NULL,
            effect_type TEXT NOT NULL, effect_data TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1)""")
        columns = {row[1] for row in connection.execute("PRAGMA table_info(cards)")}
        if "level" not in columns:
            connection.execute("ALTER TABLE cards ADD COLUMN level INTEGER NOT NULL DEFAULT 1")
        if "price_copper" not in columns:
            connection.execute("ALTER TABLE cards ADD COLUMN price_copper INTEGER NOT NULL DEFAULT 0")
        if "price_silver" not in columns:
            connection.execute("ALTER TABLE cards ADD COLUMN price_silver INTEGER NOT NULL DEFAULT 0")
        if "price_gold" not in columns:
            connection.execute("ALTER TABLE cards ADD COLUMN price_gold INTEGER NOT NULL DEFAULT 0")
        if "drop_chance" not in columns:
            connection.execute("ALTER TABLE cards ADD COLUMN drop_chance REAL NOT NULL DEFAULT 0")
        if "image_path" not in columns:
            connection.execute("ALTER TABLE cards ADD COLUMN image_path TEXT NOT NULL DEFAULT ''")
        if "effect_duration" not in columns:
            connection.execute(
                "ALTER TABLE cards ADD COLUMN effect_duration INTEGER NOT NULL DEFAULT 0"
            )
        if "mana_cost" not in columns:
            connection.execute(
                "ALTER TABLE cards ADD COLUMN mana_cost INTEGER NOT NULL DEFAULT 0"
            )
        connection.executemany(
            """INSERT INTO cards
            (key, name, group_name, strength_cost, intuition_cost, agility_cost,
             endurance_cost, effect_type, effect_data, level, price_copper,
             price_silver, price_gold, drop_chance, image_path, effect_duration, mana_cost)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                name = excluded.name,
                group_name = excluded.group_name,
                strength_cost = excluded.strength_cost,
                intuition_cost = excluded.intuition_cost,
                agility_cost = excluded.agility_cost,
                endurance_cost = excluded.endurance_cost,
                effect_type = excluded.effect_type,
                effect_data = excluded.effect_data,
                level = excluded.level,
                price_copper = excluded.price_copper,
                price_silver = excluded.price_silver,
                price_gold = excluded.price_gold,
                drop_chance = excluded.drop_chance,
                image_path = excluded.image_path,
                effect_duration = excluded.effect_duration,
                mana_cost = excluded.mana_cost,
                enabled = 1""",
            [
                (
                    card.key,
                    card.name,
                    card.group_name,
                    card.strength_cost,
                    card.intuition_cost,
                    card.agility_cost,
                    card.endurance_cost,
                    card.effect_type,
                    json.dumps(card.effect_data, ensure_ascii=False),
                    card.level,
                    card.price_copper,
                    card.price_silver,
                    card.price_gold,
                    card.drop_chance,
                    card.image_path,
                    card.effect_duration,
                    card.mana_cost,
                )
                for card in BASE_CARDS
            ],
        )
        # Отключаем/удаляем устаревшие карты, которых больше нет в коде.
        valid_keys = [card.key for card in BASE_CARDS]
        placeholders = ",".join("?" for _ in valid_keys)
        connection.execute(
            f"DELETE FROM cards WHERE key NOT IN ({placeholders})",
            valid_keys,
        )
        connection.commit()


def load_cards(path=DATABASE_PATH):
    initialize_database(path)
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            """SELECT key, name, group_name, strength_cost, intuition_cost,
                      agility_cost, endurance_cost, effect_type, effect_data,
                      level, price_copper, price_silver, price_gold, drop_chance,
                      image_path, effect_duration, mana_cost
               FROM cards
               WHERE enabled = 1
               ORDER BY rowid"""
        ).fetchall()
    return [
        Card(
            *row[:8],
            json.loads(row[8]),
            *row[9:],
        )
        for row in rows
    ]


MAGE_GROUP_PREFIX = "Магия:"


def is_mage_card(card):
    return card.group_name.startswith(MAGE_GROUP_PREFIX)


def cards_for_type(character_type, path=DATABASE_PATH):
    """Cards eligible for a character's class, so warrior and mage pools never mix
    (mage cards cost 0 in every stat field, so they'd be "free" in a warrior's draft)."""
    cards = load_cards(path)
    if character_type == "mage":
        return [card for card in cards if is_mage_card(card)]
    return [card for card in cards if not is_mage_card(card)]


def card_to_dict(card):
    return {
        "key": card.key,
        "name": card.name,
        "group_name": card.group_name,
        "costs": card.costs,
        "effect_type": card.effect_type,
        "effect_data": dict(card.effect_data),
        "level": card.level,
        "price_copper": card.price_copper,
        "price_silver": card.price_silver,
        "price_gold": card.price_gold,
        "drop_chance": card.drop_chance,
        "image_path": card.image_path,
        "effect_duration": card.effect_duration,
        "mana_cost": card.mana_cost,
    }


def choose_battle_reward(cards, rng=None):
    rng = random if rng is None else rng
    eligible = [card for card in cards if card.drop_chance > 0]
    if not eligible or rng.random() * 100 >= BATTLE_CARD_REWARD_CHANCE:
        return None

    total_weight = sum(card.drop_chance for card in eligible)
    roll = rng.random() * total_weight
    cumulative = 0
    for card in eligible:
        cumulative += card.drop_chance
        if roll < cumulative:
            return card
    return eligible[-1]