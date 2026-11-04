import json
import random
import sqlite3
from collections import Counter
from contextlib import closing
from dataclasses import dataclass, replace
from pathlib import Path


DATABASE_PATH = Path(__file__).resolve().parent.parent / "cards.sqlite3"
BATTLE_CARD_REWARD_CHANCE = 20


@dataclass(frozen=True)
class Card:
    key: str
    name: str
    group_name: str
    # "unique" uses the current fighter's unique resource regardless of profession.
    resource_type: str
    resource_cost: int
    effect_type: str
    effect_data: dict = None
    level: int = 1
    price_copper: int = 0
    price_silver: int = 0
    price_gold: int = 0
    rarity: str = "unassigned"
    drop_chance: float = 0.0
    image_path: str = ""
    effect_duration: int = 0

    def __post_init__(self):
        if self.effect_data is None:
            object.__setattr__(self, "effect_data", {})


# Список карт очищен: будем собирать набор заново с нуля.
# Физические карты бойца (воина) убраны из игры — доступны только магические карты.
BASE_CARDS = ()


def _mage_card(key, name, element, mana_cost, effect_type, effect_data, duration=0):
    """Создать магическую карту (для всех магических классов)."""
    return Card(
        key=key,
        name=name,
        group_name=f"Магия: {element}",
        resource_type="mana",
        resource_cost=mana_cost,
        effect_type=effect_type,
        effect_data={"element": element, **effect_data},
        level=1,
        drop_chance=0,
        effect_duration=duration,
        rarity="basic",
    )


def _warrior_card(key, name, style, resource_cost, effect_type, effect_data, duration=0):
    """Создать карту бойца (использует ярость)."""
    return Card(
        key=key,
        name=name,
        group_name=f"Боец: {style}",
        resource_type="rage",
        resource_cost=resource_cost,
        effect_type=effect_type,
        effect_data=effect_data,
        level=1,
        drop_chance=0,
        effect_duration=duration,
        rarity="basic",
    )


def _archer_card(key, name, style, resource_cost, effect_type, effect_data, duration=0):
    """Создать карту лучника (использует меткость)."""
    return Card(
        key=key,
        name=name,
        group_name=f"Лучник: {style}",
        resource_type="accuracy",
        resource_cost=resource_cost,
        effect_type=effect_type,
        effect_data=effect_data,
        level=1,
        drop_chance=0,
        effect_duration=duration,
        rarity="basic",
    )


def _assassin_card(key, name, style, resource_cost, effect_type, effect_data, duration=0):
    """Создать карту асасина (использует концентрацию)."""
    return Card(
        key=key,
        name=name,
        group_name=f"Асасин: {style}",
        resource_type="concentration",
        resource_cost=resource_cost,
        effect_type=effect_type,
        effect_data=effect_data,
        level=1,
        drop_chance=0,
        effect_duration=duration,
        rarity="basic",
    )


def _universal_card(
    key, name, resource_cost, effect_type, effect_data, price_silver=0,
    price_copper=0, duration=0, *, resource_type="unique", price_gold=0,
    rarity="unassigned",
):
    return Card(
        key=key,
        name=name,
        group_name="Универсальные: Тактика",
        resource_type=resource_type,
        resource_cost=resource_cost,
        effect_type=effect_type,
        effect_data=effect_data,
        level=1,
        price_copper=price_copper,
        price_silver=price_silver,
        price_gold=price_gold,
        rarity=rarity,
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
    _mage_card("mage_pyromania", "Пиромания", "Огонь", 47, "mage_area_damage_status", {"damage": 5, "wisdom_damage": 2, "status": "огонь", "status_duration": 3, "stacks": 3}, 1),
    # Вода: 6 карт
    _mage_card("mage_water_summon", "Призыв воды", "Вода", 4, "mage_damage_status", {"damage": 3, "status": "вода", "status_duration": 1}),
    _mage_card("mage_rising_flow", "Восходящий поток", "Вода", 9, "mage_area_damage_status", {"damage": 7, "status": "вода", "status_duration": 2}, 2),
    _mage_card("mage_flow_blessing", "Благословение потока", "Вода", 13, "mage_heal_missing_hp", {"missing_hp_percent": 30, "intellect_hp": 1}),
    _mage_card("mage_water_guard", "Водяная защита", "Вода", 13, "mage_health_buff", {"status": "вода", "bonus_hp": 8, "intellect_hp": 2}),
    _mage_card("mage_waterfall", "Водопад", "Вода", 18, "mage_damage_status", {"damage": 12, "status": "вода", "status_duration": 2, "damage_percent": -8, "intellect_percent": 2}, 2),
    _mage_card("mage_gurgling_flow", "Журчащий поток", "Вода", 45, "mage_heal_missing_hp", {"missing_hp_percent": 10, "intellect_hp": 1, "shield_hp": 15, "intellect_shield": 1, "damage_percent": 15}, 1),
    # Земля: 6 карт
    _mage_card("mage_boulder_summon", "Призыв валуна", "Земля", 6, "mage_damage", {"damage": 7}),
    _mage_card("mage_earth_spikes", "Иглы земли", "Земля", 24, "mage_area_damage", {"damage": 15}),
    _mage_card("mage_stone_barrages", "Каменные заслоны", "Земля", 15, "mage_team_health_buff", {"bonus_hp": 10, "wisdom_hp": 1}),
    _mage_card("mage_golem_summon", "Призыв голема", "Земля", 29, "mage_golem", {"hp": 16, "wisdom_hp": 1, "damage": 2, "wisdom_damage": 1, "stun_every": 3, "stun_damage": 8}),
    _mage_card("mage_mineral_armor", "Броня из минералов", "Земля", 18, "mage_damage_resistance", {"damage_percent": -20, "wisdom_percent": 0.5}, 2),
    _mage_card("mage_stone_spikes", "Каменные шипы", "Земля", 55, "mage_damage", {"damage": 40, "wisdom_percent": 3}),
    # Электричество: 6 карт
    _mage_card("mage_lightning_strike", "Удар молнии", "Электричество", 5, "mage_damage_status", {"damage": 4, "status": "электро", "status_duration": 3}),
    _mage_card("mage_thundercloud", "Громовая туча", "Электричество", 14, "mage_cloud", {"duration": 2, "harmony_duration": 6, "damage": 3, "status": "электро"}, 2),
    _mage_card("mage_paralysis", "Паралич", "Электричество", 20, "mage_stun_status", {"stun_duration": 1, "status": "электро", "status_duration": 3}),
    _mage_card("mage_lightning_punishment", "Просвещение молний", "Электричество", 0, "mage_restore_mana", {"missing_mana_percent": 25, "harmony_percent": 0.25, "max_mana_percent": 30}),
    _mage_card("mage_shift", "Сдвиг", "Электричество", 26, "mage_dodge_buff", {"dodge_percent": 30, "intellect_percent": 0.35}, 2),
    _mage_card("mage_raging_storm", "Бушующий шторм", "Электричество", 50, "mage_stun_status", {"damage": 11, "stun_duration": 1, "status": "электро", "status_duration": 3}, 1),
    # Воздух: 6 карт
    _mage_card("mage_wind_gust", "Порыв ветра", "Воздух", 9, "mage_wind_gust", {"damage": 4, "status_reduction": 1, "removed_damage": 3}),
    _mage_card("mage_raging_cyclone", "Бушующий циклон", "Воздух", 17, "mage_cleanse_area", {"damage": 5, "remove_statuses": True}),
    _mage_card("mage_magic_destruction", "Разрушение магии", "Воздух", 21, "mage_cleanse_ally", {"removed_heal": 8}),
    _mage_card("mage_headwind", "Встречный ветер", "Воздух", 18, "mage_damage_debuff", {"damage_percent": -20, "harmony_percent": -1, "duration": 2}, 2),
    _mage_card("mage_tailwind", "Попутный ветер", "Воздух", 11, "mage_team_damage_buff", {"damage_percent": 10, "harmony_percent": 0.5, "duration": 2}, 2),
    _mage_card("mage_wild_wind", "Wild Wind", "Воздух", 53, "mage_cleanse_area", {"damage": 5, "removed_damage": 15, "harmony_damage": 5, "remove_statuses": True}, 1),
    # Холод: 6 карт
    _mage_card("mage_icicle", "Сосулька", "Холод", 5, "mage_damage_status", {"damage": 5, "status": "холод", "status_duration": 1}),
    _mage_card("mage_ice_block", "Ледяная глыба", "Холод", 10, "mage_area_damage_status", {"damage": 8, "status": "холод", "status_duration": 1}),
    _mage_card("mage_ice_pillar", "Ледяная опора", "Холод", 13, "mage_health_buff", {"status": "холод", "bonus_hp": 1, "intellect_hp": 4}),
    _mage_card("mage_frozen_offering", "Ледяное подношение", "Холод", 4, "mage_mana_regen_buff", {"status": "холод", "status_duration": 2, "mana": 5, "intellect_mana": 2}, 2),
    _mage_card("mage_snowball", "Снежный ком", "Холод", 23, "mage_area_damage_status", {"damage": 11, "enemy_damage": 6, "status": "холод", "status_duration": 1}),
    _mage_card("mage_raging_frost", "Бушующая стужа", "Холод", 55, "mage_area_damage", {"damage": 20, "intellect_damage": 4}, 1),
)

# Карты воина (22 карты: 3 стиля, в «Танце клинка» 8 карт)
WARRIOR_CARDS = (
    # Искусство войны: Кровавая жатва (7 карт)
    _warrior_card("warrior_slash", "Разрез", "Кровавая жатва", 11, "damage", {"dice": "1d8", "bleed_percent": 8}),
    _warrior_card("warrior_hack", "Рубка", "Кровавая жатва", 20, "damage", {"dice": "2d8", "bleed_percent": 12}),
    _warrior_card("warrior_bleeding_strike", "Кровоточащий удар", "Кровавая жатва", 15, "damage", {"dice": "1d6", "hits": 3, "bleed_percent": 8}),
    _warrior_card("warrior_crimson_harvest", "Багровая жатва", "Кровавая жатва", 17, "damage_buff", {"bleed_healing_percent": 15}, 2),
    _warrior_card("warrior_arterial_cut", "Артериальный разрез", "Кровавая жатва", 20, "damage_debuff", {"dice": "1d4", "bleed_percent": 6, "duration": 3}),
    _warrior_card("warrior_blood_ritual", "Кровавый ритуал", "Кровавая жатва", 0, "damage_recoil", {"hp_percent": 9, "bleed_increase": 3}, 3),
    _warrior_card("warrior_blood_frenzy", "Кровавое безумие", "Кровавая жатва", 48, "damage", {"dice": "2d10", "bleed_percent": 20, "follow_up_bleed": 10}),

    # Танец клинка Урииля (7 карт)
    _warrior_card("warrior_quick_slash", "Быстрый разрез", "Танец клинка", 9, "damage", {"dice": "1d8", "hits": 2}),
    _warrior_card("warrior_multi_strike", "Множественный удар", "Танец клинка", 16, "damage", {"dice": "1d6", "hits": 3, "target_count": 3}),
    _warrior_card("warrior_marked_cut", "Меченый разрез", "Танец клинка", 23, "damage", {"dice": "1d6", "hits": 2, "mark_damage": 4, "mark_strength": 1}),
    _warrior_card("warrior_stun_counter", "Оглушающий ответ", "Танец клинка", 11, "damage_buff", {"hit_bonus": 1, "stun_after_hits": 8}, 2),
    _warrior_card("warrior_flurry", "Град ударов", "Танец клинка", 9, "damage_buff", {"extra_hits": 1}, 2),
    _warrior_card("warrior_dance_regen", "Танец регенерации", "Танец клинка", 0, "damage_buff", {"regen_percent": 1, "regen_max_hp": 1}, 3),
    _warrior_card("warrior_uriel_dance", "Танец Урииля", "Танец клинка", 58, "damage", {"dice": "1d6", "hits": 6, "target_count": 4}),
    _warrior_card("warrior_blade_strike", "Удар клинком", "Танец клинка", 10, "damage", {"dice": "1d10"}),

    # Стиль бога Валентайна (7 карт)
    _warrior_card("warrior_valen_strike", "Удар Валентайна", "Стиль Валентайна", 12, "damage", {"dice": "1d10", "heal_percent": 4}),
    _warrior_card("warrior_valen_cleave", "Раскол Валентайна", "Стиль Валентайна", 22, "damage", {"dice": "2d8", "heal_percent": 10}),
    _warrior_card("warrior_valen_sweep", "Размах Валентайна", "Стиль Валентайна", 19, "damage", {"dice": "1d8", "hits": 3, "heal_percent": 3}),
    _warrior_card("warrior_bleeding_blessing", "Кровавое благословение", "Стиль Валентайна", 9, "damage_buff", {"missing_hp_damage": 1, "duration": 3}),
    _warrior_card("warrior_blood_pact", "Кровавый договор", "Стиль Валентайна", 0, "damage_recoil", {"hp_percent": 20, "damage_buff_percent": 23, "duration": 3}),
    _warrior_card("warrior_blessing_theft", "Кража благословения", "Стиль Валентайна", 25, "damage", {"dice": "2d6", "steal_healing_percent": 50, "duration": 2}),
    _warrior_card("warrior_valentine_transcendence", "Трансценденция Валентайна", "Стиль Валентайна", 68, "damage", {"dice": "1d12", "full_heal": True, "damage_buff_percent": 21}, 2),
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
    _archer_card("archer_soul_transcendence", "Трансценденция Стрел", "Стрела Души", 0, "damage", {"dice": "4d8", "spiritual": True, "spiritual_split": 65, "hunt": True}),

    # Бог Севера (7 карт - манальное выжигание)
    _archer_card("archer_north_strike", "Удар Севера", "Бог Севера", 7, "damage", {"dice": "1d8", "burn_mana": 7, "burn_damage_percent": 3}),
    _archer_card("archer_north_blast", "Взрыв Севера", "Бог Севера", 12, "damage", {"dice": "2d8", "burn_mana": 12, "burn_damage_percent": 5}),
    _archer_card("archer_north_salvo", "Залп Севера", "Бог Севера", 15, "damage", {"dice": "1d4", "hits": 3, "burn_mana": 12, "burn_damage_percent": 7}),
    _archer_card("archer_north_mana_burn", "Сжигание Маны", "Бог Севера", 9, "damage_buff", {"burn_mana_percent": 2, "duration": 2}),
    _archer_card("archer_north_drain", "Слив Маны", "Бог Севера", 0, "damage", {"burn_mana_percent": 50}),
    _archer_card("archer_north_weakening", "Ослабление Севера", "Бог Севера", 24, "damage", {"dice": "1d8", "burn_mana": 8, "mana_regen_debuff": 30, "duration": 2}),
    _archer_card("archer_north_devastation", "Опустошение Севера", "Бог Севера", 39, "damage", {"dice": "2d8", "burn_mana": 20, "burn_mana_percent": 20, "burn_damage_percent": 11, "hunt": True}),

    # Проворный герой (7 карт - уворот и крит)
    _archer_card("archer_quick_shot", "Быстрый выстрел", "Проворный герой", 8, "damage", {"dice": "1d10", "hit_bonus": 10}),
    _archer_card("archer_piercing_shot", "Пронзающий выстрел", "Проворный герой", 14, "damage", {"dice": "2d8", "hit_bonus": 0, "stun_on_dodge": True}),
    _archer_card("archer_barrage", "Град Стрел", "Проворный герой", 20, "damage", {"dice": "1d6", "hits": 8, "hit_bonus_scale": 1, "crit_bonus_scale": 2}),
    _archer_card("archer_dodge_counter", "Ответ на Уклонение", "Проворный герой", 21, "damage_buff", {"dodge_damage_bonus": 10, "damage_buff_percent": 10, "duration": 1}),
    _archer_card("archer_hunt_stance", "Охота", "Проворный герой", 35, "damage", {"dice": "3d8", "no_miss": True, "hunt": True}),
    _archer_card("archer_blood_sacrifice", "Кровавая Жертва", "Проворный герой", 0, "damage_debuff", {"hp_percent": 20, "mana_percent": 25, "accuracy_bonus": 10}),
    _archer_card("archer_forest_spirit", "Лесной Дух", "Проворный герой", 36, "damage", {"summon_spirit": True, "spirit_hp": 30, "spirit_mana": 15, "spirit_dodge": 15}),
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
    _assassin_card("assassin_poison_execution", "Ядовитая Казнь", "Ядовитый Бог", 26, "damage", {"poison_damage_multiplier": 8, "poison_crit_percent": 2, "poison_crit_damage_percent": 4}),

    # Роковой проблеск (8 карт)
    _assassin_card("assassin_fate_strike", "Роковой Удар", "Роковой проблеск", 5, "damage", {"dice": "1d6", "crit_damage_percent": 15}, 2),
    _assassin_card("assassin_fate_combo", "Роковой Комбо", "Роковой проблеск", 9, "damage", {"dice": "1d6", "hits": 2, "crit_chance_percent": 5}, 2),
    _assassin_card("assassin_fate_blade", "Роковой Клинок", "Роковой проблеск", 18, "damage", {"dice": "2d8"}),
    _assassin_card("assassin_fate_enhance", "Роковое Улучшение", "Роковой проблеск", 26, "damage_buff", {"crit_damage_conversion": 0.1, "duration": 5}),
    _assassin_card("assassin_fate_crit_synergy", "Роковая Синергия", "Роковой проблеск", 12, "damage", {"dice": "1d8", "crit_guarantee": True, "crit_damage_buff": 20}),
    _assassin_card("assassin_fate_precision", "Роковая Точность", "Роковой проблеск", 10, "damage", {"dice": "1d6", "hits": 2, "damage_split": "targets"}),
    _assassin_card("assassin_thirst_blood", "Жажда Крови", "Роковой проблеск", 0, "damage_buff", {"crit_chance_guarantee": 100, "next_hits_no_crit": 2}),
    _assassin_card("assassin_fate_transcendence", "Роковая Трансценденция", "Роковой проблеск", 50, "damage", {"dice": "3d8", "stance": True}),

    # Бог Севера (7 карт - манальное выжигание + крит)
    _assassin_card("assassin_north_puncture", "Прокол Севера", "Бог Севера", 7, "damage", {"dice": "1d8", "burn_mana": 9, "crit_on_no_mana": 30}),
    _assassin_card("assassin_north_double", "Двойной Удар Севера", "Бог Севера", 12, "damage", {"dice": "1d6", "hits": 2, "burn_mana": 7, "crit_on_no_mana": 40}),
    _assassin_card("assassin_north_spear", "Копье Севера", "Бог Севера", 19, "damage", {"dice": "2d8", "burn_mana": 5, "crit_on_no_mana": 40}),
    _assassin_card("assassin_north_burn_infusion", "Сжигание Инфузия", "Бог Севера", 6, "damage_buff", {"burn_mana_percent": 5, "duration": 2}),
    _assassin_card("assassin_north_drain_crit", "Дренаж Крита", "Бог Севера", 15, "damage", {"burn_mana": 15, "crit_chance_percent": 15, "crit_damage_percent": 10}),
    _assassin_card("assassin_north_cold_drain", "Холодный Дренаж", "Бог Севера", 23, "damage", {"burn_mana_percent": 100, "mana_restore_percent": 20}),
    _assassin_card("assassin_north_chaos", "Хаос Севера", "Бог Севера", 47, "damage", {"dice": "1d8", "burn_mana": 35, "burn_mana_percent": 20, "crit_on_no_mana": 50}),
)

# Активная базовая колода воина: стиль Валентайна, 22 карты с оплатой яростью.
WARRIOR_CARDS = (
    _warrior_card("warrior_valen_strike", "Удар Валентайна", "Стиль Валентайна", 11, "damage", {"dice": 7, "heal_percent": 4}),
    _warrior_card("warrior_valen_strike_copy", "Удар Валентайна", "Стиль Валентайна", 11, "damage", {"dice": 7, "heal_percent": 4}),
    _warrior_card("warrior_valen_cleave", "Целительный выпад", "Стиль Валентайна", 22, "damage", {"dice": 13, "heal_percent": 10}),
    _warrior_card("warrior_valen_cleave_copy", "Целительный выпад", "Стиль Валентайна", 22, "damage", {"dice": 13, "heal_percent": 10}),
    _warrior_card("warrior_valen_sweep", "Полуночный натиск", "Стиль Валентайна", 19, "damage", {"dice": 3, "hits": 3, "heal_percent": 3}),
    _warrior_card("warrior_weakness_strength", "Слабость - сила", "Стиль Валентайна", 9, "damage_buff", {"missing_hp_damage": 1, "duration": 2}),
    _warrior_card("warrior_weakness_strength_copy", "Слабость - сила", "Стиль Валентайна", 9, "damage_buff", {"missing_hp_damage": 1, "duration": 2}),
    _warrior_card("warrior_blood_pact", "Кровавый договор", "Стиль Валентайна", 0, "damage_recoil", {"hp_percent": 20, "damage_buff_percent": 23, "duration": 2}),
    _warrior_card("warrior_fog_curse", "Туманное проклятие", "Стиль Валентайна", 25, "damage", {"dice": 11, "steal_healing_percent": 40, "duration": 2}),
    _warrior_card("warrior_valentine_transcendence", "Алое восстание", "Стиль Валентайна", 68, "damage", {"dice": 12, "full_heal": True, "damage_buff_percent": 21}, 2),
    _warrior_card("warrior_dagger_throw", "Бросок кинжала", "Стиль Валентайна", 6, "damage", {"dice": 4, "heal_percent": 2}),
    _warrior_card("warrior_dagger_throw_copy", "Бросок кинжала", "Стиль Валентайна", 6, "damage", {"dice": 4, "heal_percent": 2}),
    _warrior_card("warrior_severe_demeanor", "Суровый нрав", "Стиль Валентайна", 9, "damage_debuff", {"outgoing_damage_flat": 2, "duration": 1}),
    _warrior_card("warrior_grave_frost", "Могильная стужа", "Стиль Валентайна", 10, "heal_over_time", {"heal_per_turn": 4, "endurance_heal": 1, "duration": 3}),
    _warrior_card("warrior_grave_frost_copy", "Могильная стужа", "Стиль Валентайна", 10, "heal_over_time", {"heal_per_turn": 4, "endurance_heal": 1, "duration": 3}),
    _warrior_card("warrior_blood_favor", "Благоволение крови", "Стиль Валентайна", 13, "damage", {"dice": 5, "heal_percent": 5}),
    _warrior_card("warrior_blood_favor_copy", "Благоволение крови", "Стиль Валентайна", 13, "damage", {"dice": 5, "heal_percent": 5}),
    _warrior_card("warrior_hunter_bonds", "Узы охотника", "Стиль Валентайна", 4, "damage_buff", {"hp_percent": 10, "delayed_heal_percent": 15, "delay_turns": 2}),
    _warrior_card("warrior_hunter_bonds_copy", "Узы охотника", "Стиль Валентайна", 4, "damage_buff", {"hp_percent": 10, "delayed_heal_percent": 15, "delay_turns": 2}),
    _warrior_card("warrior_scarlet_throne", "Алый трон", "Стиль Валентайна", 47, "damage_buff", {"hp_current_percent": 40, "heal_max_hp_percent": 10, "damage_buff_percent": 10, "incoming_damage_percent": 10, "duration": 2}),
    _warrior_card("warrior_buried_alive", "Погребение заживо", "Стиль Валентайна", 27, "guard", {"invulnerable": True, "skip_next_turn": True}),
    _warrior_card("warrior_no_losses", "Нет потерям", "Стиль Валентайна", 90, "team_revive", {"team_only": True, "hp_max_percent": 25, "sacrifice_max_hp_percent": 50}),
)
INACTIVE_WARRIOR_CARD_KEYS = ()

# Базовая колода лучника: 22 карты с оплатой меткостью.
ARCHER_CARDS = (
    _archer_card("archer_quick_shot", "Быстрый выстрел", "Проворный герой", 8, "damage", {"dice": 5, "hit_bonus": 10}),
    _archer_card("archer_quick_shot_copy", "Быстрый выстрел", "Проворный герой", 8, "damage", {"dice": 5, "hit_bonus": 10}),
    _archer_card("archer_piercing_shot", "Ветвистый выстрел", "Проворный герой", 14, "damage", {"dice": 9, "stun_on_dodge": True}),
    _archer_card("archer_piercing_shot_copy", "Ветвистый выстрел", "Проворный герой", 14, "damage", {"dice": 9, "stun_on_dodge": True}),
    _archer_card("archer_barrage", "Туманный град", "Проворный герой", 20, "damage", {"dice": 1, "hits": 8, "hit_bonus_scale": 1, "crit_bonus_scale": 2}),
    _archer_card("archer_barrage_copy", "Туманный град", "Проворный герой", 20, "damage", {"dice": 1, "hits": 8, "hit_bonus_scale": 1, "crit_bonus_scale": 2}),
    _archer_card("archer_dodge_counter", "Коренное наследие", "Проворный герой", 21, "damage_buff", {"damage_buff_percent": 10, "dodge_stun": True, "duration": 1}),
    _archer_card("archer_hunt_stance", "Охота", "Проворный герой", 35, "damage", {"dice": 24, "no_miss": True, "hunt": True}),
    _archer_card("archer_blood_sacrifice", "Лесной контракт", "Проворный герой", 10, "damage_buff", {"hp_percent": 20, "mana_percent": 25, "agility_bonus": 10, "duration": 3}),
    _archer_card("archer_forest_spirit", "Лесной Дух", "Проворный герой", 40, "damage", {"summon_spirit": True, "spirit_hp": 30, "spirit_dodge": 15}),
    _archer_card("archer_healing_moss", "Лечебный мох", "Проворный герой", 15, "heal", {"heal_flat": 10, "heal_endurance": 1}),
    _archer_card("archer_entangling_vine", "Сдерживающая лоза", "Проворный герой", 10, "damage", {"dice": 4, "entangle": 1}),
    _archer_card("archer_entangling_vine_copy", "Сдерживающая лоза", "Проворный герой", 10, "damage", {"dice": 4, "entangle": 1}),
    _archer_card("archer_forest_rest", "Лесной покой", "Проворный герой", 20, "damage_buff", {"heal_per_turn": 5, "duration": 4, "damage_buff_percent": 5, "hit_chance_bonus": 5, "buff_duration": 2}),
    _archer_card("archer_hidden_step", "Скрытый шаг", "Проворный герой", 15, "damage_buff", {"guaranteed_dodge": 1, "duration": 1}),
    _archer_card("archer_elven_song", "Эльфийская песнь", "Проворный герой", 27, "heal", {"heal_agility_multiplier": 2, "heal_flat": 1, "incoming_damage_percent": 10, "duration": 3}),
    _archer_card("archer_oak_bulwark", "Дубовый заслон", "Проворный герой", 10, "damage_buff", {"shield_flat": 10, "shield_agility": 1}),
    _archer_card("archer_oak_bulwark_copy", "Дубовый заслон", "Проворный герой", 10, "damage_buff", {"shield_flat": 10, "shield_agility": 1}),
    _archer_card("archer_healing_fern", "Целительный папоротник", "Проворный герой", 10, "damage_buff", {"cleanse": True}),
    _archer_card("archer_heather", "Вереск", "Проворный герой", 14, "damage", {"dice": 2, "poison": 2}),
    _archer_card("archer_heather_copy", "Вереск", "Проворный герой", 14, "damage", {"dice": 2, "poison": 2}),
    _archer_card("archer_poison_ivy", "Ядовитый плющ", "Проворный герой", 10, "damage_buff", {"poison": 2, "poison_damage": 2, "entangle": 2}),
)

# Базовая колода ассасина: стиль Ядовитого Бога (22 карты), оплата концентрацией.
ASSASSIN_CARDS = (
    _assassin_card("assassin_poison_strike", "Удар кинжалом", "Ядовитый Бог", 5, "damage", {"dice": 4, "poison": 1}),
    _assassin_card("assassin_poison_strike_copy", "Удар кинжалом", "Ядовитый Бог", 5, "damage", {"dice": 4, "poison": 1}),
    _assassin_card("assassin_poison_blade", "Ядовитый выпад", "Ядовитый Бог", 11, "damage", {"dice": 8, "poison": 2}),
    _assassin_card("assassin_poison_blade_copy", "Ядовитый выпад", "Ядовитый Бог", 11, "damage", {"dice": 8, "poison": 2}),
    _assassin_card("assassin_poison_rain", "Ядовитый натиск", "Ядовитый Бог", 13, "damage", {"dice": 2, "hits": 3, "poison": 1, "poison_per_hit": True}),
    _assassin_card("assassin_poison_rain_copy", "Ядовитый натиск", "Ядовитый Бог", 13, "damage", {"dice": 2, "hits": 3, "poison": 1, "poison_per_hit": True}),
    _assassin_card("assassin_poison_infusion", "Диковиный настой", "Ядовитый Бог", 9, "damage_buff", {"crit_chance_percent": 16, "duration": 2}),
    _assassin_card("assassin_poison_infusion_copy", "Диковиный настой", "Ядовитый Бог", 9, "damage_buff", {"crit_chance_percent": 16, "duration": 2}),
    _assassin_card("assassin_poison_cascade", "Ядовитая колба", "Ядовитый Бог", 14, "damage", {"poison": 3}),
    _assassin_card("assassin_poison_extraction", "Милосердия - нет", "Ядовитый Бог", 11, "damage", {"poison_extraction": True, "extraction_crit_chance_per_stack": 2, "extraction_crit_damage_per_stack": 4, "extraction_duration": 3}),
    _assassin_card("assassin_poison_execution", "Глубочайший порез", "Ядовитый Бог", 39, "damage", {"poison_damage_multiplier": 8}),
    _assassin_card("assassin_numbness", "Онемение", "Ядовитый Бог", 14, "damage", {"dice": 5, "no_heal_turns": 3}),
    _assassin_card("assassin_wormwood", "Полынь", "Ядовитый Бог", 10, "heal", {"heal_flat": 2, "heal_endurance": 3}),
    _assassin_card("assassin_wormwood_copy", "Полынь", "Ядовитый Бог", 10, "heal", {"heal_flat": 2, "heal_endurance": 3}),
    _assassin_card("assassin_hemlock", "Болиголов", "Ядовитый Бог", 8, "damage", {"poison": 1, "stun_if_poison_at_least": 5}),
    _assassin_card("assassin_hemlock_copy", "Болиголов", "Ядовитый Бог", 8, "damage", {"poison": 1, "stun_if_poison_at_least": 5}),
    _assassin_card("assassin_datura", "Дурман", "Ядовитый Бог", 7, "damage", {"poison_outgoing_damage_percent": 5, "duration": 2}),
    _assassin_card("assassin_poison_vines", "Ядовитые лозы", "Ядовитый Бог", 10, "damage", {"entangle": 2, "poison": 2}),
    _assassin_card("assassin_poison_vines_copy", "Ядовитые лозы", "Ядовитый Бог", 10, "damage", {"entangle": 2, "poison": 2}),
    _assassin_card("assassin_neurotoxins", "Нейротоксины", "Ядовитый Бог", 24, "damage", {"forbid_damage_cards": 2}),
    _assassin_card("assassin_overdose", "Передозировка яда", "Ядовитый Бог", 18, "damage", {"dice": 2, "intuition_damage": 2, "poison": 2, "poison_cap_bonus": 4, "poison_cap_duration": 4}),
    _assassin_card("assassin_antidote_dispel", "Развеивание антидота", "Ядовитый Бог", 13, "damage", {"dice": 7, "dispel_positive_effect": True}),
)


def _necromancer_card(key, name, resource_cost, effect_type, effect_data, duration=0):
    return Card(
        key=key,
        name=name,
        group_name="Некромант: Некротизм",
        resource_type="unique",
        resource_cost=resource_cost,
        effect_type=effect_type,
        effect_data=effect_data,
        level=1,
        drop_chance=0,
        effect_duration=duration,
        rarity="basic",
    )


UNIVERSAL_CARDS = (
    _universal_card(
        "universal_trap", "Ловушка", 10, "arena_trap",
        {"range": 2, "damage": 19, "trap_kind": "damage", "cannot_crit": True}, 3,
        price_gold=50, rarity="common",
    ),
    _universal_card(
        "universal_barricade", "Баррикада", 16, "arena_barrier",
        {"range": 2, "size": 3}, 2, duration=8, price_gold=40, rarity="common",
    ),
    _universal_card(
        "universal_dash", "Рывок", 5, "arena_dash",
        {"range": 3, "distance": 3}, 1, price_gold=15, rarity="common",
    ),
    _universal_card(
        "universal_wolf", "Призыв волка", 21, "arena_wolf",
        {"range": 1}, 5, price_gold=100, rarity="rare",
    ),
    _universal_card(
        "universal_roots_trap", "Плетущие корни", 8, "arena_trap",
        {"range": 2, "damage": 8, "trap_kind": "roots", "root_turns": 2}, 1,
        price_gold=45, rarity="common",
    ),
    _universal_card(
        "universal_resource_recovery", "Медитация", 0, "arena_resource_recovery",
        {"resource_percent": 15, "next_damage_taken_bonus_percent": 25}, 3,
        price_gold=220, rarity="epic",
    ),
    _universal_card(
        "universal_knockback", "Откидывание", 16, "arena_knockback",
        {"range": 1, "damage": 12, "knockback": 3, "cannot_crit": True}, 2,
        price_gold=90, rarity="rare",
    ),
    _universal_card(
        "universal_bonebreaker", "Костолом", 13, "arena_bonebreaker",
        {"range": 1, "duration": 2, "movement_max_hp_percent": 4}, 4,
    ),
    _universal_card(
        "universal_necrotic_activity", "Некротическая активность", 0, "arena_necro_activity",
        {"resource_percent": 50, "requires_ally_summon": True}, 6,
    ),
    _universal_card(
        "universal_divine_healing", "Божественное исцеление", 50,
        "arena_divine_healing", {"range": 5, "heal_per_turn": 10, "duration": 7},
        resource_type="mana", price_gold=75, rarity="rare",
    ),
    _universal_card(
        "universal_dreadful_corruption", "Страшная порча", 59,
        "arena_dreadful_corruption",
        {
            "range": 4, "aoe_radius": 2, "fire_stacks": 4, "poison_stacks": 4,
            "outgoing_damage_reduction": 20, "incoming_damage_bonus": 20,
            "resource_loss_percent": 10, "stun_turns": 1,
        },
        price_gold=1100, rarity="legendary",
    ),
    _universal_card(
        "universal_unstable_elixir", "Нестабильное зелье", 5,
        "arena_unstable_elixir", {"aoe_radius": 2, "rolls": 3},
        price_gold=150, rarity="epic",
    ),
    _universal_card(
        "universal_evolution", "Эволюция", 21,
        "arena_evolution",
        {"range": 5, "fighter_max_hp": 35, "summon_max_hp": 20,
         "heal_per_turn": 5, "duration": 3},
        price_gold=170, rarity="epic",
    ),
    _universal_card(
        "universal_teleport", "Телепорт", 0, "arena_teleport",
        {"range": None, "mana_per_hex": 3},
        resource_type="mana", price_gold=200, rarity="epic",
    ),
)
DUNGEON_CARD_KEYS = frozenset({
    "universal_bonebreaker",
    "universal_necrotic_activity",
})

NECROMANCER_CARDS = (
    _necromancer_card(
        "necromancer_familiar", "Призыв фамильяра", 14, "necromancer_summon",
        {"summon_kind": "familiar", "range": 1},
    ),
    _necromancer_card(
        "necromancer_lokrif", "Призыв локрифа", 24, "necromancer_summon",
        {"summon_kind": "lokrif", "range": 1},
    ),
    _necromancer_card(
        "necromancer_bone_hero", "Призыв костяного героя", 43, "necromancer_summon",
        {"summon_kind": "bone_hero", "range": 1},
    ),
    _necromancer_card(
        "necromancer_spirit", "Призыв духа", 20, "necromancer_summon",
        {"summon_kind": "spirit", "range": 1},
    ),
    _necromancer_card(
        "necromancer_lyrk", "Призыв лирка", 15, "necromancer_summon",
        {"summon_kind": "lyrk", "range": 1},
    ),
    _necromancer_card(
        "necromancer_grave_zink", "Призыв могильного зинка", 38, "necromancer_summon",
        {"summon_kind": "grave_zink", "range": 1},
    ),
    _necromancer_card(
        "necromancer_transfer", "Перенос", 7, "necromancer_transfer",
        {"range": 2, "distance": 3},
    ),
    _necromancer_card(
        "necromancer_slow_trap", "Ловушка замедления", 10, "necromancer_trap",
        {"range": 2, "damage": 15, "trap_kind": "slow", "slow_turns": 2},
    ),
    _necromancer_card(
        "necromancer_knockback_trap", "Ловушка отбрасывания", 11, "necromancer_trap",
        {"range": 1, "damage": 10, "trap_kind": "knockback", "knockback": 4},
    ),
    _necromancer_card(
        "necromancer_dead_god_blessing", "Благословение мёртвого бога", 15,
        "necromancer_summon_heal", {"range": 2, "heal_percent": 35},
    ),
    _necromancer_card(
        "necromancer_in_the_name", "Во имя владыки", 0, "necromancer_sacrifice",
        {"heal_percent": 20, "resource_percent": 10, "refund_percent": 35, "draw": 1},
    ),
    _necromancer_card(
        "necromancer_familiar_search", "Поиск фамильяра", 16,
        "necromancer_summon_search", {"range": 0, "hp_percent": 20, "damage_percent": 10,
                                      "damage_reduction_percent": 10},
    ),
    _necromancer_card(
        "necromancer_necrotic_charge", "Заряд некротизма", 12, "necromancer_damage",
        {"range": 2, "damage": 10},
    ),
    _necromancer_card(
        "necromancer_fragility_curse", "Проклятие хрупкости", 15,
        "necromancer_defense_curse", {"range": 2, "reduction_percent": 30, "duration": 3},
    ),
    _necromancer_card(
        "necromancer_gravestones", "Могильные плиты", 20, "necromancer_barrier",
        {"range": 1, "duration": 6},
    ),
    _necromancer_card(
        "necromancer_screamer", "Скример", 14, "necromancer_screamer",
        {"range": 3, "damage": 5, "stun_turns": 1, "aoe_radius": 1},
    ),
    _necromancer_card(
        "necromancer_grave_soil", "Могильная почва", 30, "necromancer_grave_soil",
        {"range": 2, "radius": 3, "duration": 15, "undead_heal": 3, "living_slow": 1},
    ),
    _necromancer_card(
        "necromancer_dead_god_sacrifice", "Жертва мёртвому богу", 0,
        "necromancer_resource_sacrifice", {"hp_percent": 25, "resource_percent": 25},
    ),
    _necromancer_card(
        "necromancer_dead_god_curse", "Проклятие мёртвого бога", 25,
        "necromancer_green_flame", {"range": 2, "damage_percent": 2, "permanent": True},
    ),
    _necromancer_card(
        "necromancer_dead_grip", "Хватка мёртвых", 8, "necromancer_damage_roots",
        {"range": 3, "damage": 5, "root_turns": 2},
    ),
    _necromancer_card(
        "necromancer_dead_god_bargain", "Сделка с мёртвым богом", 13,
        "necromancer_bargain", {"gain_percent": 20, "green_flame_damage_percent": 1},
    ),
    _necromancer_card(
        "necromancer_bone_dragon", "Призыв костяного дракона", 70,
        "necromancer_summon", {"summon_kind": "bone_dragon", "range": 1},
    ),
)

BASE_CARDS = (
    BASE_CARDS + MAGE_CARDS + WARRIOR_CARDS + ARCHER_CARDS
    + ASSASSIN_CARDS + UNIVERSAL_CARDS + NECROMANCER_CARDS
)

# Ranges are measured in hex steps. Self/team effects and summons use their own targeting rules.
CARD_RANGES = {
    "mage_flash": 4,
    "mage_fireball": 4,
    "mage_crimson_blood": 3,
    "mage_burning_support": 3,
    "mage_pyromania": 4,
    "mage_water_summon": 5,
    "mage_rising_flow": 4,
    "mage_flow_blessing": 4,
    "mage_water_guard": 4,
    "mage_waterfall": 5,
    "mage_gurgling_flow": 4,
    "mage_boulder_summon": 4,
    "mage_earth_spikes": 3,
    "mage_mineral_armor": 0,
    "mage_stone_spikes": 4,
    "mage_lightning_strike": 4,
    "mage_paralysis": 4,
    "mage_raging_storm": 4,
    "mage_wind_gust": 4,
    "mage_raging_cyclone": 3,
    "mage_magic_destruction": 3,
    "mage_headwind": 4,
    "mage_wild_wind": 4,
    "mage_icicle": 4,
    "mage_ice_block": 3,
    "mage_ice_pillar": 3,
    "mage_frozen_offering": 3,
    "mage_snowball": 3,
    "mage_raging_frost": 4,
    "warrior_valen_strike": 1,
    "warrior_valen_strike_copy": 1,
    "warrior_valen_cleave": 1,
    "warrior_valen_cleave_copy": 1,
    "warrior_valen_sweep": 1,
    "warrior_valentine_transcendence": 1,
    "warrior_weakness_strength": 3,
    "warrior_weakness_strength_copy": 3,
    "warrior_fog_curse": 1,
    "warrior_dagger_throw": 3,
    "warrior_dagger_throw_copy": 3,
    "warrior_severe_demeanor": 1,
    "warrior_grave_frost": 3,
    "warrior_grave_frost_copy": 3,
    "warrior_blood_favor": 1,
    "warrior_blood_favor_copy": 1,
    "warrior_hunter_bonds": 0,
    "warrior_hunter_bonds_copy": 0,
    "warrior_scarlet_throne": 0,
    "warrior_buried_alive": 0,
    "warrior_no_losses": 1,
    "archer_quick_shot": 4,
    "archer_quick_shot_copy": 4,
    "archer_piercing_shot": 4,
    "archer_piercing_shot_copy": 4,
    "archer_barrage": 4,
    "archer_barrage_copy": 4,
    "archer_dodge_counter": 3,
    "archer_hunt_stance": 5,
    "archer_healing_moss": 3,
    "archer_entangling_vine": 3,
    "archer_entangling_vine_copy": 3,
    "archer_forest_rest": 3,
    "archer_hidden_step": 3,
    "archer_elven_song": 3,
    "archer_oak_bulwark": 3,
    "archer_oak_bulwark_copy": 3,
    "archer_healing_fern": 3,
    "archer_heather": 4,
    "archer_heather_copy": 4,
    "archer_poison_ivy": 4,
    "assassin_poison_strike": 1,
    "assassin_poison_strike_copy": 1,
    "assassin_poison_blade": 1,
    "assassin_poison_blade_copy": 1,
    "assassin_poison_rain": 1,
    "assassin_poison_rain_copy": 1,
    "assassin_poison_infusion": 0,
    "assassin_poison_infusion_copy": 0,
    "assassin_poison_cascade": 3,
    "assassin_poison_extraction": 2,
    "assassin_poison_execution": 1,
    "assassin_numbness": 1,
    "assassin_wormwood": 3,
    "assassin_wormwood_copy": 3,
    "assassin_hemlock": 2,
    "assassin_hemlock_copy": 2,
    "assassin_datura": 2,
    "assassin_poison_vines": 3,
    "assassin_poison_vines_copy": 3,
    "assassin_neurotoxins": 3,
    "assassin_overdose": 2,
    "assassin_antidote_dispel": 3,
}
BASE_CARDS = tuple(
    replace(card, effect_data={**card.effect_data, "range": CARD_RANGES[card.key]})
    if card.key in CARD_RANGES else card
    for card in BASE_CARDS
)

_OLD_CARD_CATALOG = BASE_CARDS
_STARTER_CLASS_PREFIXES = ("Магия:", "Боец:", "Лучник:", "Асасин:", "Некромант:")
_KEPT_NECROMANCER_KEYS = {"necromancer_spirit", "necromancer_lokrif"}
REMOVED_SHOP_CARD_KEYS = frozenset({
    "mage_crimson_blood", "mage_thundercloud", "mage_headwind",
    "mage_raging_cyclone", "mage_raging_frost", "mage_wild_wind",
    "warrior_blood_favor", "warrior_blood_favor_copy",
    "warrior_valentine_transcendence",
    "archer_entangling_vine", "archer_entangling_vine_copy",
    "archer_dodge_counter", "archer_oak_bulwark", "archer_oak_bulwark_copy",
    "assassin_poison_vines", "assassin_poison_vines_copy",
    "assassin_wormwood", "assassin_wormwood_copy",
    "assassin_hemlock", "assassin_hemlock_copy", "assassin_datura",
})
SHOP_CARD_PRICES = {
    "mage_flash": (45, "common"),
    "mage_fireball": (40, "common"),
    "mage_lightning_strike": (40, "common"),
    "mage_icicle": (40, "common"),
    "mage_snowball": (80, "rare"),
    "mage_shift": (40, "common"),
    "mage_magic_destruction": (120, "rare"),
    "mage_fervent_service": (230, "epic"),
    "mage_burning_support": (50, "common"),
    "mage_lightning_punishment": (250, "epic"),
    "mage_golem_summon": (200, "epic"),
    "mage_water_summon": (20, "common"),
    "mage_boulder_summon": (45, "common"),
    "mage_wind_gust": (85, "rare"),
    "mage_tailwind": (160, "rare"),
    "mage_pyromania": (720, "legendary"),
    "mage_paralysis": (190, "epic"),
    "mage_frozen_offering": (150, "rare"),
    "mage_ice_pillar": (70, "rare"),
    "mage_ice_block": (180, "epic"),
    "mage_stone_spikes": (850, "legendary"),
    "mage_stone_barrages": (320, "epic"),
    "mage_earth_spikes": (300, "epic"),
    "mage_gurgling_flow": (950, "legendary"),
    "mage_rising_flow": (85, "rare"),
    "mage_water_guard": (110, "rare"),
    "mage_waterfall": (210, "epic"),
    "mage_raging_storm": (750, "legendary"),
    "mage_mineral_armor": (240, "epic"),
    "mage_flow_blessing": (190, "epic"),
    "warrior_valen_cleave": (75, "rare"),
    "warrior_valen_cleave_copy": (75, "rare"),
    "warrior_hunter_bonds": (180, "epic"),
    "warrior_hunter_bonds_copy": (180, "epic"),
    "warrior_valen_strike": (45, "common"),
    "warrior_valen_strike_copy": (45, "common"),
    "warrior_fog_curse": (300, "epic"),
    "warrior_severe_demeanor": (95, "rare"),
    "warrior_weakness_strength": (160, "epic"),
    "warrior_weakness_strength_copy": (160, "epic"),
    "warrior_valen_sweep": (230, "epic"),
    "warrior_buried_alive": (270, "epic"),
    "warrior_no_losses": (1000, "legendary"),
    "warrior_grave_frost": (110, "rare"),
    "warrior_grave_frost_copy": (110, "rare"),
    "warrior_blood_pact": (170, "epic"),
    "warrior_dagger_throw": (50, "common"),
    "warrior_dagger_throw_copy": (50, "common"),
    "warrior_scarlet_throne": (900, "legendary"),
    "archer_poison_ivy": (80, "rare"),
    "archer_elven_song": (250, "epic"),
    "archer_healing_fern": (170, "epic"),
    "archer_barrage": (140, "rare"),
    "archer_barrage_copy": (140, "rare"),
    "archer_hidden_step": (85, "rare"),
    "archer_hunt_stance": (200, "epic"),
    "archer_healing_moss": (100, "rare"),
    "archer_forest_rest": (70, "rare"),
    "archer_blood_sacrifice": (160, "epic"),
    "archer_forest_spirit": (180, "rare"),
    "archer_piercing_shot": (50, "common"),
    "archer_piercing_shot_copy": (50, "common"),
    "archer_heather": (55, "common"),
    "archer_heather_copy": (55, "common"),
    "archer_quick_shot": (40, "common"),
    "archer_quick_shot_copy": (40, "common"),
    "assassin_poison_rain": (60, "rare"),
    "assassin_poison_rain_copy": (60, "rare"),
    "assassin_poison_blade": (45, "common"),
    "assassin_poison_blade_copy": (45, "common"),
    "assassin_poison_cascade": (80, "rare"),
    "assassin_poison_extraction": (60, "rare"),
    "assassin_poison_execution": (0, "legendary"),
    "assassin_numbness": (90, "rare"),
    "assassin_overdose": (190, "epic"),
    "assassin_antidote_dispel": (70, "rare"),
    "assassin_neurotoxins": (180, "epic"),
    "assassin_poison_infusion": (45, "common"),
    "assassin_poison_infusion_copy": (45, "common"),
    "necromancer_dead_grip": (55, "common"),
    "necromancer_screamer": (70, "rare"),
    "necromancer_dead_god_bargain": (150, "epic"),
    "necromancer_fragility_curse": (80, "rare"),
    "necromancer_dead_god_curse": (180, "epic"),
    "necromancer_familiar": (130, "rare"),
    "necromancer_grave_zink": (500, "legendary"),
    "necromancer_lyrk": (320, "epic"),
    "necromancer_bone_dragon": (1000, "legendary"),
    "necromancer_bone_hero": (650, "legendary"),
    "necromancer_familiar_search": (60, "rare"),
    "necromancer_transfer": (60, "common"),
    "necromancer_gravestones": (120, "rare"),
    "necromancer_grave_soil": (280, "epic"),
    "necromancer_knockback_trap": (75, "rare"),
    "necromancer_slow_trap": (65, "rare"),
    "necromancer_necrotic_charge": (40, "common"),
    "necromancer_dead_god_sacrifice": (130, "rare"),
    "necromancer_in_the_name": (230, "epic"),
    "necromancer_dead_god_blessing": (100, "rare"),
}
SHOP_CARD_EFFECTS = {
    "mage_magic_destruction": {"name": "Разрушитель магии"},
    "mage_snowball": {"effect_data": {"vector_beam": True}},
    "mage_pyromania": {
        "effect_data": {
            "damage": 12, "fixed_damage": 12, "status": "огонь",
            "status_duration": 3, "stacks": 5, "delayed_stacks": 3,
            "range": 2, "aoe_radius": 3,
        },
        "remove_effect_data": ("wisdom_damage",),
    },
    "mage_tailwind": {
        "effect_data": {"damage_percent": 10, "intellect_percent": 1, "duration": 2},
        "remove_effect_data": ("harmony_percent",),
    },
    "mage_frozen_offering": {
        "resource_cost": 0,
        "effect_data": {
            "hp_percent": 10, "status": "холод", "status_duration": 2,
            "mana_regen_bonus": 3, "duration": 2,
        },
        "remove_effect_data": ("mana", "intellect_mana"),
    },
    "mage_ice_pillar": {"effect_data": {"bonus_hp": 10, "intellect_hp": 2}},
    "mage_ice_block": {
        "resource_cost": 24,
        "effect_data": {"damage": 15, "fixed_damage": 15, "range": 3, "aoe_radius": 1},
        "remove_effect_data": ("status", "status_duration"),
    },
    "mage_stone_spikes": {"effect_data": {"damage": 55}},
    "mage_stone_barrages": {
        "effect_data": {"bonus_hp": 15, "wisdom_hp": 1, "range": 3, "aoe_radius": 2},
    },
    "mage_earth_spikes": {
        "effect_data": {"damage": 18, "fixed_damage": 18, "range": 2, "aoe_radius": 2},
    },
    "mage_gurgling_flow": {
        "effect_data": {
            "max_hp_percent": 25, "intellect_max_hp_percent": 1,
            "shield_hp": 20, "intellect_shield": 1,
            "damage_percent": 35, "intellect_percent": 1,
            "next_attack_damage_bonus": 25, "cleanse_negative_effects": 1,
            "status": "вода", "status_permanent": True, "duration": 2,
            "target_self": True,
        },
        "remove_effect_data": ("missing_hp_percent", "intellect_hp"),
    },
    "mage_rising_flow": {
        "effect_data": {"damage": 8, "fixed_damage": 8, "range": 5, "aoe_radius": 1},
    },
    "mage_water_guard": {"effect_data": {"bonus_hp": 13, "intellect_hp": 1}},
    "mage_waterfall": {
        "effect_data": {
            "damage": 13, "fixed_damage": 13, "range": 5, "aoe_radius": 1,
            "status": "вода", "status_duration": 2, "knockback": 2,
        },
        "remove_effect_data": ("damage_percent", "intellect_percent"),
    },
    "mage_raging_storm": {
        "name": "Королевская молния",
        "effect_type": "mage_area_damage_status",
        "resource_cost": 60,
        "effect_data": {
            "damage": 40, "fixed_damage": 40, "status": "электро",
            "status_duration": 4, "range": 3, "aoe_radius": 2,
        },
        "remove_effect_data": ("stun_duration",),
    },
    "mage_mineral_armor": {
        "effect_data": {"reduction_percent": 24, "wisdom_percent": 1},
        "remove_effect_data": ("damage_percent",),
    },
    "warrior_valen_sweep": {
        "effect_data": {"dice": 5, "hits": 2, "heal_max_hp_percent_per_hit": 5},
        "remove_effect_data": ("heal_percent",),
    },
    "warrior_severe_demeanor": {
        "effect_data": {"outgoing_damage_percent": 20, "duration": 2, "aoe_center_self": True, "aoe_radius": 2},
        "remove_effect_data": ("outgoing_damage_flat",),
    },
    "warrior_weakness_strength": {
        "effect_data": {"missing_hp_damage_per_10": 1, "duration": 3},
        "remove_effect_data": ("missing_hp_damage",),
    },
    "warrior_weakness_strength_copy": {
        "effect_data": {"missing_hp_damage_per_10": 1, "duration": 3},
        "remove_effect_data": ("missing_hp_damage",),
    },
    "warrior_buried_alive": {
        "effect_data": {"invulnerable": True, "skip_next_turn": True, "duration": 2},
    },
    "warrior_blood_pact": {
        "effect_data": {"hp_percent": 20, "damage_buff_percent": 25, "strength_percent": 1, "duration": 2},
    },
    "warrior_scarlet_throne": {
        "resource_cost": 47,
        "effect_data": {
            "landscape_radius": 2, "heal_per_turn": 8, "rage_per_turn": 8,
            "damage_buff_percent": 30, "incoming_damage_percent": 20,
            "duration": 2, "target_self": True,
        },
        "remove_effect_data": ("hp_current_percent", "heal_max_hp_percent"),
    },
    "archer_poison_ivy": {
        "effect_type": "arena_trap",
        "effect_data": {
            "range": 4, "trap_kind": "poison_ivy", "poison": 2,
            "poison_damage": 2, "entangle": 2,
        },
    },
    "archer_elven_song": {
        "resource_cost": 19,
        "effect_data": {"aoe_center_self": True, "aoe_radius": 1, "target_self": True},
    },
    "archer_healing_fern": {
        "resource_cost": 15,
        "effect_data": {"range": 2},
    },
    "archer_hidden_step": {
        "resource_cost": 6,
        "effect_data": {"guaranteed_dodge": 1, "duration": 2, "target_self": True},
    },
    "archer_healing_moss": {
        "effect_type": "archer_healing_moss",
        "effect_data": {"range": 3, "landscape_radius": 1, "heal_per_turn": 2, "resource_per_turn": 1, "duration": 4},
    },
    "archer_forest_rest": {
        "effect_data": {"range": 2, "resource_regen_per_turn": 5, "duration": 4},
        "remove_effect_data": ("heal_per_turn", "damage_buff_percent", "hit_chance_bonus", "buff_duration"),
    },
    "archer_blood_sacrifice": {"effect_data": {"duration": 5}},
    "archer_forest_spirit": {"resource_cost": 31},
    "archer_heather": {"resource_cost": 9},
    "archer_heather_copy": {"resource_cost": 9},
    "assassin_poison_cascade": {
        "effect_data": {"damage": 6, "fixed_damage": 6, "poison": 3, "aoe_radius": 1},
    },
    "assassin_poison_extraction": {
        "effect_data": {"extraction_duration": 4},
    },
    "assassin_poison_execution": {
        "effect_data": {"poison_damage_multiplier": 9, "poison_crit_damage_percent": 5},
    },
    "assassin_numbness": {"effect_data": {"range": 2}},
    "assassin_antidote_dispel": {
        "resource_cost": 11,
        "effect_data": {"range": 2},
    },
    "assassin_neurotoxins": {
        "resource_cost": 21,
        "effect_data": {"range": 2},
    },
}


def _legacy_shop_card(card):
    data = dict(card.effect_data)
    revision = SHOP_CARD_EFFECTS.get(card.key, {})
    for key in revision.get("remove_effect_data", ()):
        data.pop(key, None)
    data.update(revision.get("effect_data", {}))
    price, rarity = SHOP_CARD_PRICES.get(card.key, (0, "unassigned"))
    updates = {
        key: value
        for key, value in revision.items()
        if key not in {"effect_data", "remove_effect_data"}
    }
    return replace(
        card,
        price_copper=0,
        price_silver=0,
        price_gold=price,
        rarity=rarity,
        drop_chance=0,
        effect_data=data,
        **updates,
    )


LEGACY_SHOP_CARDS = tuple(
    _legacy_shop_card(card)
    for card in _OLD_CARD_CATALOG
    if card.group_name.startswith(_STARTER_CLASS_PREFIXES)
    and card.key not in _KEPT_NECROMANCER_KEYS
    and card.key not in REMOVED_SHOP_CARD_KEYS
)
KEPT_NECROMANCER_CARDS = tuple(
    replace(
        card,
        resource_cost=26 if card.key == "necromancer_spirit" else 19,
    )
    for card in _OLD_CARD_CATALOG
    if card.key in _KEPT_NECROMANCER_KEYS
)

STARTER_MAGE_CARDS = (
    _mage_card("mage_mana_charge", "Заряд маны", "Основы", 10, "mage_damage",
               {"damage": 5, "fixed_damage": 5, "range": 3}),
    _mage_card("mage_mana_burst", "Взрыв накопленной маны", "Основы", 21, "mage_area_damage",
               {"damage": 10, "fixed_damage": 10, "range": 2, "aoe_radius": 1}),
    _mage_card("mage_mana_shield", "Щит из маны", "Основы", 14, "mage_mana_shield",
               {"shield_hp": 8, "intellect_shield": 1, "target_self": True}),
    _mage_card("mage_heal", "Лечение", "Основы", 12, "mage_heal_flat",
               {"heal_flat": 12, "target_self": True}),
    _mage_card("mage_force_push", "Отталкивающий удар", "Основы", 15, "mage_force_push",
               {"damage": 8, "fixed_damage": 8, "range": 2, "knockback": 1}),
    _mage_card("mage_flow", "Поток", "Основы", 0, "mage_restore_mana_flat",
               {"restore_flat": 10, "target_self": True}),
    _mage_card("mage_next_attack", "Усиление", "Основы", 6, "mage_damage_buff",
               {"next_attack_damage_bonus": 5, "target_self": True}),
    _mage_card("mage_arcane_beam", "Аркейн бим", "Основы", 42, "mage_damage",
               {"damage": 22, "fixed_damage": 22, "range": 3, "vector_beam": True}),
)

STARTER_WARRIOR_CARDS = (
    _warrior_card("warrior_lunge", "Выпад", "Основы", 10, "damage",
                  {"damage": 6, "fixed_damage": 6, "range": 1}),
    _warrior_card("warrior_power_attack", "Сильная атака", "Основы", 20, "damage",
                  {"damage": 11, "fixed_damage": 11, "range": 1}),
    _warrior_card("warrior_circular_sweep", "Круговой взмах", "Основы", 13, "damage",
                  {"damage": 6, "fixed_damage": 6, "range": 1, "aoe_radius": 1,
                   "aoe_center_self": True, "target_self": True}),
    _warrior_card("warrior_bandages", "Бинты", "Основы", 11, "heal",
                  {"heal_flat": 13, "target_self": True}),
    _warrior_card("warrior_block", "Блок", "Основы", 16, "damage_buff",
                  {"shield_flat": 8, "shield_endurance": 2, "target_self": True}),
    _warrior_card("warrior_adaptation", "Адаптация", "Основы", 0, "damage_buff",
                  {"resource_gain": 6, "heal_flat": 5, "target_self": True}),
    _warrior_card("warrior_vulnerability_strike", "Удар в уязвимость", "Основы", 5,
                  "damage_buff", {"next_attack_damage_bonus": 5, "target_self": True}),
    _warrior_card("warrior_dash_strike", "Удар с рывка", "Основы", 30,
                  "arena_dash_strike", {"damage": 18, "fixed_damage": 18, "range": 2,
                                        "distance": 2, "aoe_radius": 1}),
)

STARTER_ARCHER_CARDS = (
    _archer_card("archer_shot", "Выстрел", "Основы", 9, "damage",
                 {"damage": 6, "fixed_damage": 6, "range": 3}),
    _archer_card("archer_aimed_shot", "Прицельный выстрел", "Основы", 19, "damage",
                 {"damage": 11, "fixed_damage": 11, "range": 4}),
    _archer_card("archer_arrow_hail", "Град стрел", "Основы", 12, "damage",
                 {"damage": 6, "fixed_damage": 6, "range": 2, "aoe_radius": 1}),
    _archer_card("archer_bandages", "Латки", "Основы", 11, "heal",
                 {"heal_flat": 10, "target_self": True}),
    _archer_card("archer_agility", "Проворность", "Основы", 12, "damage_buff",
                 {"dodge_percent": 15, "duration": 2, "target_self": True}, duration=2),
    _archer_card("archer_heightened_attention", "Повышенное внимание", "Основы", 0,
                 "damage_buff", {"resource_gain": 11, "target_self": True}),
    _archer_card("archer_weak_point", "В слабую точку", "Основы", 5, "damage_buff",
                 {"next_attack_damage_bonus": 5, "target_self": True}),
    _archer_card("archer_lightning_shot", "Молниеносный выстрел", "Основы", 40,
                 "damage", {"damage": 29, "fixed_damage": 29, "range": None, "no_miss": True}),
)

STARTER_ASSASSIN_CARDS = (
    _assassin_card("assassin_throw_blade", "Метнуть клинок", "Основы", 9, "damage",
                   {"damage": 6, "fixed_damage": 6, "range": 2}),
    _assassin_card("assassin_hidden_lunge", "Потайной выпад", "Основы", 19, "damage",
                   {"damage": 11, "fixed_damage": 11, "range": 1}),
    _assassin_card("assassin_dagger_hail", "Град кинжалов", "Основы", 12, "damage",
                   {"damage": 7, "fixed_damage": 7, "range": 2, "aoe_radius": 1}),
    _assassin_card("assassin_healing", "Исцеление", "Основы", 11, "heal",
                   {"heal_flat": 10, "target_self": True}),
    _assassin_card("assassin_stealth", "Скрытность", "Основы", 12, "damage_buff",
                   {"dodge_percent": 8, "duration": 3, "target_self": True}, duration=3),
    _assassin_card("assassin_observation", "Наблюдение", "Основы", 0, "damage_buff",
                   {"resource_gain": 6, "next_attack_damage_bonus": 2, "target_self": True}),
    _assassin_card("assassin_experience", "Опыт", "Основы", 9, "damage_buff",
                   {"next_attack_crit_chance_percent": 10,
                    "next_attack_crit_damage_percent": 25, "target_self": True}),
    _assassin_card("assassin_fatal_strike", "Роковой удар", "Основы", 31, "damage",
                   {"damage": 18, "fixed_damage": 18, "range": 1,
                    "attack_crit_chance_percent": 10, "attack_crit_damage_percent": 35}),
)

STARTER_NECROMANCER_CARDS = (
    _necromancer_card("necromancer_skull_throw", "Бросок черепа", 9, "damage",
                      {"damage": 5, "fixed_damage": 5, "range": 2}),
    _necromancer_card("necromancer_otherworldly_beam", "Потусторонний луч", 15, "damage",
                      {"damage": 10, "fixed_damage": 10, "range": 2}),
    _necromancer_card("necromancer_area_of_suffering", "Область страданий", 12, "damage",
                      {"damage": 7, "fixed_damage": 7, "range": 3, "aoe_radius": 1}),
    _necromancer_card("necromancer_bond", "Связь", 9, "necromancer_team_heal",
                      {"heal_flat": 6, "range": None}),
    _necromancer_card("necromancer_fear_shield", "Щит из страха", 14,
                      "necromancer_fear_shield",
                      {"shield_hp": 8, "intellect_shield": 1, "range": 2}),
    _necromancer_card("necromancer_fear_sense", "Чувство страха", 0,
                      "necromancer_fear_sense", {"resource_gain": 10, "target_self": True}),
    _necromancer_card("necromancer_max_health", "Увеличение максимального здоровья", 16,
                      "necromancer_max_health",
                      {"bonus_hp": 7, "harmony_hp": 1, "range": 2}),
    _necromancer_card("necromancer_torment", "Страшные муки", 40, "damage",
                      {"damage": 10, "fixed_damage": 10, "range": 3,
                       "green_flame_stacks": 2}),
)

STARTER_CARD_QUANTITIES = {
    "mage_mana_charge": 3,
    "mage_mana_burst": 3,
    "mage_mana_shield": 3,
    "mage_heal": 3,
    "mage_force_push": 3,
    "mage_flow": 2,
    "mage_next_attack": 3,
    "mage_arcane_beam": 2,
    "warrior_lunge": 3,
    "warrior_power_attack": 3,
    "warrior_circular_sweep": 3,
    "warrior_bandages": 3,
    "warrior_block": 3,
    "warrior_adaptation": 2,
    "warrior_vulnerability_strike": 3,
    "warrior_dash_strike": 2,
    "archer_shot": 3,
    "archer_aimed_shot": 3,
    "archer_arrow_hail": 3,
    "archer_bandages": 3,
    "archer_agility": 3,
    "archer_heightened_attention": 2,
    "archer_weak_point": 3,
    "archer_lightning_shot": 2,
    "assassin_throw_blade": 3,
    "assassin_hidden_lunge": 3,
    "assassin_dagger_hail": 3,
    "assassin_healing": 3,
    "assassin_stealth": 2,
    "assassin_observation": 3,
    "assassin_experience": 3,
    "assassin_fatal_strike": 2,
    "necromancer_skull_throw": 3,
    "necromancer_otherworldly_beam": 3,
    "necromancer_area_of_suffering": 3,
    "necromancer_spirit": 1,
    "necromancer_lokrif": 1,
    "necromancer_bond": 3,
    "necromancer_fear_shield": 2,
    "necromancer_fear_sense": 2,
    "necromancer_max_health": 2,
    "necromancer_torment": 2,
}

STARTER_CARDS = (
    *STARTER_MAGE_CARDS,
    *STARTER_WARRIOR_CARDS,
    *STARTER_ARCHER_CARDS,
    *STARTER_ASSASSIN_CARDS,
    *STARTER_NECROMANCER_CARDS,
    *KEPT_NECROMANCER_CARDS,
)
SHOP_CARD_KEYS = frozenset(
    card.key for card in (*LEGACY_SHOP_CARDS, *UNIVERSAL_CARDS)
    if card.price_gold > 0
)
BASE_CARDS = (
    *LEGACY_SHOP_CARDS,
    *STARTER_CARDS,
    *UNIVERSAL_CARDS,
)

_INITIALIZED_PATHS = set()


CARD_COLUMNS = (
    "key", "name", "group_name", "resource_type", "resource_cost", "effect_type",
    "effect_data", "level", "price_copper", "price_silver", "price_gold",
    "rarity", "drop_chance", "image_path", "effect_duration",
)


def initialize_database(path=DATABASE_PATH):
    """Таблица карт — кэш справочника из кода: при смене схемы пересоздаётся."""
    with closing(sqlite3.connect(path)) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(cards)")]
        if columns and columns != [*CARD_COLUMNS, "enabled"]:
            connection.execute("DROP TABLE cards")
        connection.execute("""CREATE TABLE IF NOT EXISTS cards (
            key TEXT PRIMARY KEY, name TEXT NOT NULL, group_name TEXT NOT NULL,
            resource_type TEXT NOT NULL, resource_cost INTEGER NOT NULL,
            effect_type TEXT NOT NULL, effect_data TEXT NOT NULL,
            level INTEGER NOT NULL, price_copper INTEGER NOT NULL,
            price_silver INTEGER NOT NULL, price_gold INTEGER NOT NULL,
            rarity TEXT NOT NULL, drop_chance REAL NOT NULL, image_path TEXT NOT NULL,
            effect_duration INTEGER NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1)""")
        placeholders = ", ".join("?" for _ in CARD_COLUMNS)
        updates = ", ".join(f"{column} = excluded.{column}" for column in CARD_COLUMNS[1:])
        connection.executemany(
            f"""INSERT INTO cards ({", ".join(CARD_COLUMNS)}) VALUES ({placeholders})
            ON CONFLICT(key) DO UPDATE SET {updates}, enabled = 1""",
            [
                tuple(
                    json.dumps(card.effect_data, ensure_ascii=False) if column == "effect_data" else getattr(card, column)
                    for column in CARD_COLUMNS
                )
                for card in BASE_CARDS
            ],
        )
        valid_keys = [card.key for card in BASE_CARDS]
        connection.execute(
            f"DELETE FROM cards WHERE key NOT IN ({','.join('?' for _ in valid_keys)})",
            valid_keys,
        )
        connection.commit()


def load_cards(path=DATABASE_PATH):
    # Таблица пересобирается из кода один раз за процесс
    if path not in _INITIALIZED_PATHS:
        initialize_database(path)
        _INITIALIZED_PATHS.add(path)
    with closing(sqlite3.connect(path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"SELECT {', '.join(CARD_COLUMNS)} FROM cards WHERE enabled = 1 ORDER BY rowid"
        ).fetchall()
    cards = []
    for row in rows:
        fields = dict(row)
        fields["effect_data"] = json.loads(fields["effect_data"])
        cards.append(Card(**fields))
    return cards


MAGE_GROUP_PREFIX = "Магия:"


def is_mage_card(card):
    return card.group_name.startswith(MAGE_GROUP_PREFIX)


DECK_SIZE = 22
DECK_COPY_LIMIT = 3
DECK_COPY_LIMITS = {}
RARITY_COPY_LIMITS = {
    "basic": 3,
    "common": 3,
    "rare": 2,
    "epic": 2,
    "legendary": 1,
    "unassigned": 3,
}

# Каждый класс пользуется только картами своей группы ("Магия: Огонь" -> "Магия:").
PROFESSION_CARD_GROUPS = {
    "warrior": "Боец:",
    "archer": "Лучник:",
    "assassin": "Асасин:",
    "battle_mage": MAGE_GROUP_PREFIX,
    "support_mage": MAGE_GROUP_PREFIX,
    "harmonist": MAGE_GROUP_PREFIX,
    "mage": MAGE_GROUP_PREFIX,  # старый тип персонажа
    "necromancer": "Некромант:",
}


def is_mage_profession(character_type):
    return PROFESSION_CARD_GROUPS.get(character_type) == MAGE_GROUP_PREFIX


def deck_copy_limit(card):
    return RARITY_COPY_LIMITS.get(card.rarity, DECK_COPY_LIMIT)


def starter_card_quantities_for_type(character_type):
    prefix = PROFESSION_CARD_GROUPS.get(character_type)
    if prefix is None:
        return {}
    return {
        card.key: STARTER_CARD_QUANTITIES[card.key]
        for card in STARTER_CARDS
        if card.group_name.startswith(prefix)
    }


def card_allowed_for(card, character_type):
    prefix = PROFESSION_CARD_GROUPS.get(character_type)
    return prefix is not None and (
        is_universal_card(card) or card.group_name.startswith(prefix)
    )


def is_universal_card(card):
    return card.group_name.startswith("Универсальные:")


def card_style(card):
    """Стиль/элемент карты — по нему считается требование ульты."""
    return card.group_name.split(":", 1)[-1].strip()


def cards_for_type(character_type, path=DATABASE_PATH):
    """Все карты, доступные классу персонажа. Пулы классов никогда не смешиваются."""
    return [card for card in load_cards(path) if card_allowed_for(card, character_type)]


def class_cards_for_type(character_type, path=DATABASE_PATH):
    """Карты класса без универсальных — используются для стартовых выдач."""
    quantities = starter_card_quantities_for_type(character_type)
    by_key = {card.key: card for card in load_cards(path)}
    return [
        by_key[key]
        for key, quantity in quantities.items()
        if key in by_key
        for _ in range(quantity)
    ]


def expand_deck_card_keys(cards):
    """Expand a saved card-count mapping into one key per deck card."""
    if isinstance(cards, dict):
        expanded = []
        for key, quantity in cards.items():
            if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
                raise ValueError("Некорректное количество карт в колоде")
            expanded.extend([str(key)] * quantity)
        return expanded
    if isinstance(cards, (list, tuple)):
        return [str(key) for key in cards]
    return []


def deck_validation_error(card_keys, character_type, owned_keys=None, path=DATABASE_PATH):
    """Текст ошибки колоды или пустая строка. Используется и сервером, и клиентом."""
    try:
        if isinstance(card_keys, dict):
            counts = Counter({
                str(key): int(quantity)
                for key, quantity in card_keys.items()
            })
        else:
            counts = Counter(str(key) for key in card_keys)
    except (TypeError, ValueError):
        return "Некорректное количество карт в колоде"
    if any(quantity < 1 for quantity in counts.values()):
        return "Количество каждой карты должно быть не меньше 1"
    if sum(counts.values()) != DECK_SIZE:
        return f"В колоде должно быть ровно {DECK_SIZE} карты"
    by_key = {card.key: card for card in load_cards(path)}
    if any(key not in by_key for key in counts):
        return "Колода содержит неизвестную карту"
    if any(not card_allowed_for(by_key[key], character_type) for key in counts):
        return "Колода содержит карты чужого класса"
    for key, quantity in counts.items():
        copy_limit = deck_copy_limit(by_key[key])
        if quantity > copy_limit:
            return f"Карты «{by_key[key].name}» можно взять не больше {copy_limit}"
    if owned_keys is not None:
        for key, quantity in counts.items():
            if key not in owned_keys:
                return "Колода содержит карты, которых нет в коллекции"
            if isinstance(owned_keys, dict):
                try:
                    owned_quantity = int(owned_keys[key])
                except (TypeError, ValueError):
                    return "Некорректное количество карт в коллекции"
                if quantity > owned_quantity:
                    return "В колоде больше копий карты, чем есть в коллекции"
    return ""


def card_to_dict(card):
    class_key = next(
        (
            key for key, prefix in (
                ("mage", "Магия:"),
                ("warrior", "Боец:"),
                ("archer", "Лучник:"),
                ("assassin", "Асасин:"),
                ("necromancer", "Некромант:"),
                ("universal", "Универсальные:"),
            )
            if card.group_name.startswith(prefix)
        ),
        "universal",
    )
    return {
        "key": card.key,
        "name": card.name,
        "group_name": card.group_name,
        "class_key": class_key,
        "effect_type": card.effect_type,
        "effect_data": dict(card.effect_data),
        "level": card.level,
        "price_copper": card.price_copper,
        "price_silver": card.price_silver,
        "price_gold": card.price_gold,
        "rarity": card.rarity,
        "sale_price_coins": {
            "basic": 0, "common": 15, "rare": 35,
            "epic": 120, "legendary": 450,
        }.get(card.rarity, 0),
        "drop_chance": card.drop_chance,
        "image_path": card.image_path,
        "effect_duration": card.effect_duration,
        "resource_type": card.resource_type,
        "resource_cost": card.resource_cost,
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