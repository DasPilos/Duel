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
    strength_cost: int
    intuition_cost: int
    agility_cost: int
    endurance_cost: int
    effect_type: str
    effect_data: dict
    level: int
    price_copper: int = 0
    price_silver: int = 0
    price_gold: int = 0
    drop_chance: float = 0.0
    image_path: str = ""
    effect_duration: int = 0
    mana_cost: int = 0

    @property
    def costs(self):
        return {"strength": self.strength_cost, "intuition": self.intuition_cost, "agility": self.agility_cost, "endurance": self.endurance_cost}


# Список карт очищен: будем собирать набор заново с нуля.
# Физические карты бойца (воина) убраны из игры — доступны только магические карты.
BASE_CARDS = ()


def _mage_card(key, name, element, mana_cost, effect_type, effect_data, duration=0):
    return Card(
        key=key,
        name=name,
        group_name=f"Магия: {element}",
        strength_cost=0,
        intuition_cost=0,
        agility_cost=0,
        endurance_cost=0,
        effect_type=effect_type,
        effect_data={"element": element, **effect_data},
        level=1,
        drop_chance=0,
        effect_duration=duration,
        mana_cost=mana_cost,
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

BASE_CARDS = BASE_CARDS + MAGE_CARDS


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