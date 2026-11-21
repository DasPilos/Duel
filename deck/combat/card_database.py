import random
from collections import Counter
from dataclasses import dataclass, replace


BATTLE_CARD_REWARD_CHANCE = 20
# Цена продажи карты в монетах по редкости.
SALE_PRICE_COINS = {"basic": 0, "common": 15, "rare": 50, "epic": 150, "legendary": 700}


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
    price_coins: int = 0
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
    key, name, resource_cost, effect_type, effect_data, price_coins=0,
    duration=0, *, resource_type="unique", rarity="unassigned",
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
        price_coins=price_coins,
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
    _mage_card("mage_stone_spikes", "Каменные шипы", "Земля", 55, "mage_damage", {"damage": 40, "wisdom_percent": 3, "ultimate": True, "cast_turns": 1}),
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

# Карты воина (22 карты: 3 стиля, в «Танце клинка» 8 карт)
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
    _warrior_card("warrior_flurry", "Град ударов", "Танец клинка", 9, "damage_buff", {"extra_hits": 1}, 2),
    _warrior_card("warrior_dance_regen", "Танец регенерации", "Танец клинка", 0, "damage_buff", {"regen_percent": 1, "regen_max_hp": 1}, 3),
    _warrior_card("warrior_uriel_dance", "Танец Урииля", "Танец клинка", 58, "damage", {"dice": "1d6", "hits": 6, "target_count": 4, "ultimate": True}),
    _warrior_card("warrior_blade_strike", "Удар клинком", "Танец клинка", 10, "damage", {"dice": "1d10"}),

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
    _warrior_card("warrior_valentine_transcendence", "Алое восстание", "Стиль Валентайна", 68, "damage", {"dice": 12, "full_heal": True, "damage_buff_percent": 21, "ultimate": True}, 2),
    _warrior_card("warrior_dagger_throw", "Бросок кинжала", "Стиль Валентайна", 6, "damage", {"dice": 4, "heal_percent": 2}),
    _warrior_card("warrior_dagger_throw_copy", "Бросок кинжала", "Стиль Валентайна", 6, "damage", {"dice": 4, "heal_percent": 2}),
    _warrior_card("warrior_severe_demeanor", "Суровый нрав", "Стиль Валентайна", 9, "damage_debuff", {"outgoing_damage_flat": 2, "duration": 1}),
    _warrior_card("warrior_grave_frost", "Могильная стужа", "Стиль Валентайна", 10, "heal_over_time", {"heal_per_turn": 4, "endurance_heal": 1, "duration": 3}),
    _warrior_card("warrior_grave_frost_copy", "Могильная стужа", "Стиль Валентайна", 10, "heal_over_time", {"heal_per_turn": 4, "endurance_heal": 1, "duration": 3}),
    _warrior_card("warrior_blood_favor", "Благоволение крови", "Стиль Валентайна", 13, "damage", {"dice": 5, "heal_percent": 5}),
    _warrior_card("warrior_blood_favor_copy", "Благоволение крови", "Стиль Валентайна", 13, "damage", {"dice": 5, "heal_percent": 5}),
    _warrior_card("warrior_hunter_bonds", "Узы охотника", "Стиль Валентайна", 4, "damage_buff", {"hp_percent": 10, "delayed_heal_percent": 15, "delay_turns": 2}),
    _warrior_card("warrior_hunter_bonds_copy", "Узы охотника", "Стиль Валентайна", 4, "damage_buff", {"hp_percent": 10, "delayed_heal_percent": 15, "delay_turns": 2}),
    _warrior_card("warrior_scarlet_throne", "Алый трон", "Стиль Валентайна", 25, "damage_buff", {"hp_current_percent": 40, "heal_max_hp_percent": 10, "damage_buff_percent": 10, "incoming_damage_percent": 10, "duration": 2}),
    _warrior_card("warrior_buried_alive", "Погребение заживо", "Стиль Валентайна", 27, "guard", {"invulnerable": True, "skip_next_turn": True}),
    _warrior_card("warrior_no_losses", "Нет потерям", "Стиль Валентайна", 100, "team_revive", {"team_only": True, "hp_max_percent": 25, "sacrifice_max_hp_percent": 50}),
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
    _archer_card("archer_forest_spirit", "Лесной Дух", "Проворный герой", 40, "damage", {"summon_spirit": True, "spirit_hp": 30, "spirit_dodge": 15, "ultimate": True}),
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
    _assassin_card("assassin_poison_execution", "Глубочайший порез", "Ядовитый Бог", 39, "damage", {"poison_damage_multiplier": 8, "ultimate": True}),
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
        {"range": 2, "damage": 19, "trap_kind": "damage", "cannot_crit": True}, 300,
        rarity="common",
    ),
    _universal_card(
        "universal_barricade", "Баррикада", 16, "arena_barrier",
        {"range": 2, "size": 3}, 200, duration=8, rarity="common",
    ),
    _universal_card(
        "universal_dash", "Рывок", 5, "arena_dash",
        {"range": 3, "distance": 3}, 100, rarity="common",
    ),
    _universal_card(
        "universal_wolf", "Призыв волка", 21, "arena_wolf",
        {"range": 1}, 550, rarity="rare",
    ),
    _universal_card(
        "universal_roots_trap", "Плетущие корни", 8, "arena_trap",
        {"range": 2, "damage": 8, "trap_kind": "roots", "root_turns": 2}, 100,
        rarity="common",
    ),
    _universal_card(
        "universal_resource_recovery", "Медитация", 0, "arena_resource_recovery",
        {"resource_percent": 15, "next_damage_taken_bonus_percent": 25}, 320,
        rarity="epic",
    ),
    _universal_card(
        "universal_knockback", "Откидывание", 16, "arena_knockback",
        {"range": 1, "damage": 12, "knockback": 3, "cannot_crit": True}, 280,
        rarity="rare",
    ),
    _universal_card(
        "universal_bonebreaker", "Костолом", 13, "arena_bonebreaker",
        {"range": 1, "duration": 2, "movement_max_hp_percent": 4}, price_coins=250, rarity="epic",
    ),
    _universal_card(
        "universal_divine_healing", "Божественное исцеление", 50,
        "arena_divine_healing", {"range": 5, "heal_per_turn": 10, "duration": 7},
        resource_type="mana", price_coins=75, rarity="rare",
    ),
    _universal_card(
        "universal_dreadful_corruption", "Страшная порча", 59,
        "arena_dreadful_corruption",
        {
            "range": 4, "aoe_radius": 2, "fire_stacks": 4, "poison_stacks": 4,
            "outgoing_damage_reduction": 20, "incoming_damage_bonus": 20,
            "resource_loss_percent": 10, "stun_turns": 1,
        },
        price_coins=1100, rarity="legendary",
    ),
    _universal_card(
        "universal_unstable_elixir", "Нестабильное зелье", 5,
        "arena_unstable_elixir", {"aoe_radius": 2, "rolls": 3},
        price_coins=150, rarity="epic",
    ),
    _universal_card(
        "universal_evolution", "Эволюция", 21,
        "arena_evolution",
        {"range": 5, "fighter_max_hp": 35, "summon_max_hp": 20,
         "heal_per_turn": 5, "duration": 3},
        price_coins=170, rarity="epic",
    ),
    _universal_card(
        "universal_teleport", "Телепорт", 0, "arena_teleport",
        {"range": None, "mana_per_hex": 3},
        resource_type="mana", price_coins=200, rarity="epic",
    ),
)
DUNGEON_CARD_KEYS = frozenset({
    "universal_bonebreaker",
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

def load_cards():
    """Все карты из кода: отдельного файла-кэша нет, справочник и так лежит в модуле."""
    return list(BASE_CARDS)


MAGE_GROUP_PREFIX = "Магия:"


def is_mage_card(card):
    return card.group_name.startswith(MAGE_GROUP_PREFIX)


DECK_SIZE = 22
ULTIMATE_STYLE_CARDS_REQUIRED = 5
DECK_COPY_LIMIT = 2
DECK_COPY_LIMITS = {
    "mage_flash": 2,
    "mage_shift": 2,
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


def cards_for_type(character_type):
    """Все карты, доступные классу персонажа. Пулы классов никогда не смешиваются."""
    return [card for card in load_cards() if card_allowed_for(card, character_type)]


def class_cards_for_type(character_type):
    """Карты класса без универсальных — используются для стартовых выдач."""
    prefix = PROFESSION_CARD_GROUPS.get(character_type)
    if prefix is None:
        return []
    return [
        card for card in load_cards()
        if card.group_name.startswith(prefix)
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


def deck_validation_error(card_keys, character_type, owned_keys=None):
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
    by_key = {card.key: card for card in load_cards()}
    if any(key not in by_key for key in counts):
        return "Колода содержит неизвестную карту"
    if any(not card_allowed_for(by_key[key], character_type) for key in counts):
        return "Колода содержит карты чужого класса"
    for key, quantity in counts.items():
        copy_limit = DECK_COPY_LIMITS.get(key, DECK_COPY_LIMIT)
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
    for key, quantity in counts.items():
        card = by_key[key]
        if not card.effect_data.get("ultimate"):
            continue
        style = card_style(card)
        same_style = sum(
            count
            for other, count in counts.items()
            if card_style(by_key[other]) == style
            and not by_key[other].effect_data.get("ultimate")
        )
        if same_style < ULTIMATE_STYLE_CARDS_REQUIRED:
            return (
                f"Ульта «{card.name}» требует минимум {ULTIMATE_STYLE_CARDS_REQUIRED} "
                f"обычных карт стиля «{style}»"
            )
    return ""


def card_to_dict(card):
    return {
        "key": card.key,
        "name": card.name,
        "group_name": card.group_name,
        "effect_type": card.effect_type,
        "effect_data": dict(card.effect_data),
        "level": card.level,
        "price_coins": card.price_coins,
        "rarity": card.rarity,
        "sale_price_coins": SALE_PRICE_COINS.get(card.rarity, 0),
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