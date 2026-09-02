import json
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

    @property
    def costs(self):
        return {"strength": self.strength_cost, "intuition": self.intuition_cost, "agility": self.agility_cost, "endurance": self.endurance_cost}


BASE_CARDS = (
    ("straight_punch", "Прямой удар", "Сила", 1, 0, 0, 0, "damage", {"dice": "1d5"}, 1),
    ("kick", "Удар ногой", "Сила", 2, 0, 0, 0, "damage", {"dice": "2d4"}, 1),
    ("jaw_strike", "Удар в челюсть", "Сила", 3, 0, 0, 0, "damage", {"dice": "2d8"}, 2),
    ("light_push", "Лёгкий толчок", "Сила", 1, 0, 0, 0, "damage", {"dice": "1d5"}, 1),
    ("heel_strike", "Удар пяткой", "Сила", 2, 0, 0, 0, "damage", {"dice": "3d3"}, 1),
    ("sweep", "Подсечка", "Сила", 1, 0, 1, 0, "damage", {"dice": "1d5", "anti_dodge": 3}, 1),
    ("elbow_strike", "Удар локтем", "Сила", 3, 2, 0, 0, "damage", {"dice": "3d5"}, 3),
    ("sentence", "Приговор", "Сила", 4, 1, 1, 3, "damage", {"dice": "3d8", "anti_dodge": 3, "critical_bonus": 3}, 4),
    ("uppercut", "Апперкот", "Сила", 2, 0, 1, 0, "damage", {"dice": "2d6"}, 2),
    ("hook", "Хук", "Сила", 2, 1, 0, 0, "damage", {"dice": "2d6"}, 2),
    ("side_step", "Шаг в сторону", "Ловкость", 0, 0, 2, 0, "dodge", {"bonus": 20}, 1),
    ("whirlwind", "Вихрь", "Ловкость", 0, 0, 3, 0, "dodge", {"bonus": 40}, 2),
    ("feint", "Ложное движение", "Ловкость", 0, 1, 2, 1, "anti_dodge", {"bonus": 20}, 2),
    ("flexible_turn", "Гибкий разворот", "Ловкость", 0, 0, 2, 1, "anti_dodge", {"bonus": 20}, 2),
    ("back_attack", "Заход за спину", "Ловкость", 0, 0, 3, 1, "anti_dodge", {"bonus": 20, "critical_bonus": 5}, 2),
    ("snake_reaction", "Реакция змеи", "Ловкость", 0, 1, 2, 1, "dodge", {"bonus": 40}, 3),
    ("illusion_step", "Шаг иллюзии", "Ловкость", 1, 0, 2, 0, "damage_dodge", {"dice": "1d5", "bonus": 30}, 2),
    ("wind_dance", "Танец ветра", "Ловкость", 0, 0, 4, 1, "dodge", {"bonus": 100}, 4),
    ("blood_thirst", "Жажда крови", "Интуиция", 0, 4, 1, 0, "critical", {"bonus": 100}, 4),
    ("perfect_moment", "Идеальный момент", "Интуиция", 0, 3, 0, 1, "critical", {"bonus": 30}, 3),
    ("scorpion_sting", "Жало скорпиона", "Интуиция", 0, 3, 0, 2, "critical", {"bonus": 40}, 3),
    ("insight", "Прозрения", "Интуиция", 0, 2, 1, 0, "critical", {"bonus": 20}, 2),
    ("predator_eye", "Око хищника", "Интуиция", 0, 2, 0, 0, "critical", {"bonus": 15}, 1),
    ("hunter_mark", "Метка охотника", "Интуиция", 0, 3, 1, 0, "critical", {"bonus": 30}, 3),
    ("remind_pain", "Напомнить о боли", "Интуиция", 0, 2, 1, 0, "critical", {"bonus": 20}, 2),
    ("collect_teeth", "Собрать зубы", "Выносливость", 0, 0, 0, 2, "heal", {"dice": "3d3"}, 1),
    ("wipe_sweat", "Стереть пот", "Выносливость", 0, 0, 0, 3, "heal", {"dice": "3d5"}, 2),
    ("second_chance", "Второй шанс", "Выносливость", 0, 1, 1, 1, "extra_action_points", {}, 2),
    ("block", "Блок", "Выносливость", 0, 0, 0, 1, "damage_resistance", {"ratio": 0.7}, 1),
    ("hold_line", "Держать строй", "Выносливость", 0, 0, 0, 2, "damage_resistance", {"ratio": 0.5}, 1),
    ("deaf_defense", "Глухая оборона", "Выносливость", 0, 0, 0, 3, "damage_resistance", {"ratio": 0.2}, 2),
    ("heal_wounds", "Залечить раны", "Выносливость", 0, 2, 2, 4, "heal_duration", {"dice": "3d3", "duration": 3}, 4),
)


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
        connection.execute("DELETE FROM cards")
        connection.executemany(
            """INSERT OR IGNORE INTO cards
            (key, name, group_name, strength_cost, intuition_cost, agility_cost,
             endurance_cost, effect_type, effect_data, level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(*row[:-2], json.dumps(row[-2], ensure_ascii=False), row[-1]) for row in BASE_CARDS],
        )
        connection.commit()


def load_cards(path=DATABASE_PATH):
    initialize_database(path)
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT key, name, group_name, strength_cost, intuition_cost, agility_cost, endurance_cost, effect_type, effect_data, level FROM cards WHERE enabled = 1 ORDER BY rowid"
        ).fetchall()
    return [Card(*row[:-2], json.loads(row[-2]), row[-1]) for row in rows]