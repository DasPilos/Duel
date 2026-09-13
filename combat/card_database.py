import json
import random
import sqlite3
from dataclasses import dataclass
from pathlib import Path


DATABASE_PATH = Path(__file__).resolve().parent.parent / "cards.sqlite3"


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

    @property
    def costs(self):
        return {"strength": self.strength_cost, "intuition": self.intuition_cost, "agility": self.agility_cost, "endurance": self.endurance_cost}


# Список карт очищен: будем собирать набор заново с нуля.
BASE_CARDS = (
    Card(
        key="podsechka",
        name="Подсечка",
        group_name="Сила",
        strength_cost=2,
        intuition_cost=0,
        agility_cost=0,
        endurance_cost=0,
        effect_type="damage",
        effect_data={"dice": "1d4"},
        level=1,
        price_silver=2,
        drop_chance=20,
        image_path="assets/cards/faces/podsechka.png",
        effect_duration=0,
    ),
    Card(
        key="straight_punch",
        name="Прямой удар",
        group_name="Сила",
        strength_cost=3,
        intuition_cost=0,
        agility_cost=0,
        endurance_cost=0,
        effect_type="damage",
        effect_data={"dice": "1d6"},
        level=1,
        price_silver=3,
        drop_chance=18,
        image_path="assets/cards/faces/straight_punch.png",
        effect_duration=0,
    ),
    Card(
        key="knock_down",
        name="Сбить с ног",
        group_name="Сила",
        strength_cost=4,
        intuition_cost=1,
        agility_cost=2,
        endurance_cost=0,
        effect_type="damage_stat_debuff",
        effect_data={
            "dice": "1d4",
            "stat": "agility",
            "amount": 4,
        },
        level=3,
        price_silver=15,
        drop_chance=4,
        image_path="assets/cards/faces/knock_down.png",
        effect_duration=2,
    ),
    Card(
        key="heavy_strike",
        name="Тяжелый удар",
        group_name="Сила",
        strength_cost=4,
        intuition_cost=1,
        agility_cost=0,
        endurance_cost=0,
        effect_type="damage",
        effect_data={"dice": "2d6"},
        level=2,
        price_silver=6,
        drop_chance=15,
        image_path="assets/cards/faces/heavy_strike.png",
        effect_duration=0,
    ),
    Card(
        key="windmill",
        name="Мельница",
        group_name="Сила",
        strength_cost=4,
        intuition_cost=0,
        agility_cost=1,
        endurance_cost=0,
        effect_type="damage",
        effect_data={"dice": "1d10"},
        level=2,
        price_silver=6,
        drop_chance=15,
        image_path="assets/cards/faces/windmill.png",
        effect_duration=0,
    ),
    Card(
        key="reveal_threat",
        name="Разкрыть угрозу",
        group_name="Сила",
        strength_cost=3,
        intuition_cost=2,
        agility_cost=1,
        endurance_cost=0,
        effect_type="damage_critical_debuff",
        effect_data={
            "dice": "3d4",
            "amount": 20,
        },
        level=3,
        price_silver=6,
        drop_chance=15,
        image_path="assets/cards/faces/reveal_threat.png",
        effect_duration=1,
    ),
    Card(
        key="uppercut",
        name="Апперкот",
        group_name="Сила",
        strength_cost=4,
        intuition_cost=0,
        agility_cost=0,
        endurance_cost=0,
        effect_type="damage",
        effect_data={"dice": "1d12"},
        level=2,
        price_silver=5,
        drop_chance=17,
        image_path="assets/cards/faces/uppercut.png",
        effect_duration=0,
    ),
    Card(
        key="concussion",
        name="Сотресение мозга",
        group_name="Сила",
        strength_cost=6,
        intuition_cost=0,
        agility_cost=1,
        endurance_cost=0,
        effect_type="damage_dodge_debuff",
        effect_data={
            "dice": "1d18",
            "amount": 20,
        },
        level=3,
        price_silver=8,
        drop_chance=14,
        image_path="assets/cards/faces/concussion.png",
        effect_duration=2,
    ),
    Card(
        key="shadow_boxing",
        name="Бой с тенью",
        group_name="Сила",
        strength_cost=3,
        intuition_cost=0,
        agility_cost=2,
        endurance_cost=0,
        effect_type="damage_dodge_debuff",
        effect_data={
            "dice": "2d4",
            "amount": 20,
        },
        level=2,
        price_silver=6,
        drop_chance=16,
        image_path="assets/cards/faces/shadow_boxing.png",
        effect_duration=2,
    ),
    Card(
        key="punish_foolishness",
        name="Наказание глупости",
        group_name="Сила",
        strength_cost=3,
        intuition_cost=2,
        agility_cost=0,
        endurance_cost=0,
        effect_type="damage",
        effect_data={"dice": "1d9"},
        level=2,
        price_silver=5,
        drop_chance=16,
        image_path="assets/cards/faces/punish_foolishness.png",
        effect_duration=0,
    ),
    Card(
        key="verdict",
        name="Приговор",
        group_name="Сила",
        strength_cost=6,
        intuition_cost=1,
        agility_cost=1,
        endurance_cost=4,
        effect_type="damage_dodge_critical_debuff",
        effect_data={
            "dice": "3d8",
            "dodge_amount": 20,
            "critical_amount": 20,
        },
        level=4,
        price_silver=12,
        drop_chance=7,
        image_path="assets/cards/faces/verdict.png",
        effect_duration=1,
    ),
    Card(
        key="combat_recon",
        name="Разведка боем",
        group_name="Сила",
        strength_cost=2,
        intuition_cost=0,
        agility_cost=0,
        endurance_cost=2,
        effect_type="damage_critical_debuff",
        effect_data={
            "dice": "1d6",
            "amount": 30,
        },
        level=2,
        price_silver=6,
        drop_chance=15,
        image_path="assets/cards/faces/combat_recon.png",
        effect_duration=1,
    ),
    Card(
        key="heaviest_hook",
        name="Тяжелейший хук",
        group_name="Сила",
        strength_cost=4,
        intuition_cost=2,
        agility_cost=0,
        endurance_cost=3,
        effect_type="damage_critical_debuff",
        effect_data={
            "dice": "1d14",
            "amount": 20,
        },
        level=3,
        price_silver=10,
        drop_chance=8,
        image_path="assets/cards/faces/heaviest_hook.png",
        effect_duration=1,
    ),
    Card(
        key="double_strike",
        name="Двойной удар",
        group_name="Сила",
        strength_cost=4,
        intuition_cost=1,
        agility_cost=1,
        endurance_cost=2,
        effect_type="damage_critical_debuff",
        effect_data={
            "dice": "2d8",
            "amount": 20,
        },
        level=3,
        price_silver=10,
        drop_chance=8,
        image_path="assets/cards/faces/double_strike.png",
        effect_duration=1,
    ),
    Card(
        key="strength_in_fist",
        name="Силу в кулак",
        group_name="Сила",
        strength_cost=0,
        intuition_cost=1,
        agility_cost=1,
        endurance_cost=2,
        effect_type="instant_action_points",
        effect_data={
            "stat": "strength",
            "amount": 4,
        },
        level=2,
        price_silver=7,
        drop_chance=14,
        image_path="assets/cards/faces/strength_in_fist.png",
        effect_duration=0,
    ),
)


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
        effect_data={"element": element, "mana_cost": mana_cost, **effect_data},
        level=1,
        drop_chance=0,
        effect_duration=duration,
    )


MAGE_CARDS = (
    _mage_card("mage_flash", "Вспышка", "Огонь", 6, "mage_damage_status", {"damage": 4, "status": "огонь", "status_duration": 1}),
    _mage_card("mage_fireball", "Фаербол", "Огонь", 14, "mage_damage_status", {"damage": 9, "status": "огонь", "status_duration": 2}),
    _mage_card("mage_crimson_blood", "Багровая кровь", "Огонь", 16, "mage_reactive_blessing", {"status": "огонь", "status_duration": 2, "retaliation_damage": 2, "retaliation_status_duration": 1}, 2),
    _mage_card("mage_burning_support", "Пылающая поддержка", "Огонь", 10, "mage_damage_buff", {"status": "огонь", "status_duration": 2, "damage_percent": 25, "harmony_percent": 1}, 2),
    _mage_card("mage_fervent_service", "Пылкая услуга", "Огонь", 0, "mage_hp_for_mana", {"hp_percent": 7, "mana_percent": 21}),
    _mage_card("mage_water_summon", "Призыв воды", "Вода", 4, "mage_damage_status", {"damage": 3, "status": "вода", "status_duration": 1}),
    _mage_card("mage_rising_flow", "Восходящий поток", "Вода", 9, "mage_area_damage_status", {"damage": 7, "status": "вода", "status_duration": 2}, 2),
    _mage_card("mage_flow_blessing", "Благословение потока", "Вода", 13, "mage_heal_missing_hp", {"missing_hp_percent": 30, "intellect_hp": 1}),
    _mage_card("mage_water_guard", "Водяная защита", "Вода", 13, "mage_health_buff", {"status": "вода", "bonus_hp": 8, "intellect_hp": 2}),
    _mage_card("mage_boulder_summon", "Призыв валуна", "Земля", 6, "mage_damage", {"damage": 7}),
    _mage_card("mage_earth_spikes", "Иглы земли", "Земля", 24, "mage_area_damage", {"damage": 15}),
    _mage_card("mage_stone_barrages", "Каменные заслоны", "Земля", 15, "mage_team_health_buff", {"bonus_hp": 10, "wisdom_hp": 1}),
    _mage_card("mage_golem_summon", "Призыв голема", "Земля", 29, "mage_golem", {"hp": 16, "wisdom_hp": 1, "damage": 2, "wisdom_damage": 1, "stun_every": 3, "stun_damage": 8}),
    _mage_card("mage_lightning_strike", "Удар молнии", "Электричество", 5, "mage_damage_status", {"damage": 4, "status": "электро", "status_duration": 3}),
    _mage_card("mage_thundercloud", "Громовая туча", "Электричество", 14, "mage_cloud", {"duration": 2, "harmony_duration": 6, "damage": 3, "status": "электро"}, 2),
    _mage_card("mage_paralysis", "Паралич", "Электричество", 20, "mage_stun_status", {"stun_duration": 1, "status": "электро", "status_duration": 3}),
    _mage_card("mage_lightning_punishment", "Просвещение молний", "Электричество", 0, "mage_restore_mana", {"missing_mana_percent": 25, "harmony_percent": 0.25, "max_mana_percent": 30}),
    _mage_card("mage_wind_gust", "Порыв ветра", "Воздух", 9, "mage_wind_gust", {"damage": 4, "status_reduction": 1, "removed_damage": 3}),
    _mage_card("mage_raging_cyclone", "Бушующий циклон", "Воздух", 17, "mage_cleanse_area", {"damage": 5, "remove_statuses": True}),
    _mage_card("mage_magic_destruction", "Разрушение магии", "Воздух", 21, "mage_cleanse_ally", {"removed_heal": 8}),
    _mage_card("mage_headwind", "Встречный ветер", "Воздух", 18, "mage_damage_debuff", {"damage_percent": -20, "harmony_percent": -1, "duration": 2}, 2),
    _mage_card("mage_tailwind", "Попутный ветер", "Воздух", 11, "mage_team_damage_buff", {"damage_percent": 10, "harmony_percent": 0.5, "duration": 2}, 2),
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
        connection.executemany(
            """INSERT INTO cards
            (key, name, group_name, strength_cost, intuition_cost, agility_cost,
             endurance_cost, effect_type, effect_data, level, price_copper,
             price_silver, price_gold, drop_chance, image_path, effect_duration)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                )
                for card in BASE_CARDS
            ],
        )
        connection.commit()


def load_cards(path=DATABASE_PATH):
    initialize_database(path)
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            """SELECT key, name, group_name, strength_cost, intuition_cost,
                      agility_cost, endurance_cost, effect_type, effect_data,
                      level, price_copper, price_silver, price_gold, drop_chance,
                      image_path, effect_duration
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
    }


def choose_battle_reward(cards, rng=None):
    rng = random if rng is None else rng
    successful = [
        card
        for card in cards
        if card.drop_chance > 0 and rng.random() * 100 < card.drop_chance
    ]
    return rng.choice(successful) if successful else None