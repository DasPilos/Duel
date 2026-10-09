import atexit
import hashlib
import hmac
import json
import secrets
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

from psycopg import errors as pg_errors
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from combat.character_stats import (
    BASE_STAT_VALUE,
    MIN_STAT_VALUE,
    STARTING_STAT_POINTS,
    calculate_carry_capacity,
    calculate_max_hp,
    calculate_max_mana,
    minimum_endurance,
)
from core.currency import Currency
from server import config
from server.migrations import apply_migrations

SYSTEM_USER_ID = 0

# One pool per (dsn, schema) for the whole process: bot chat, bot battles and HTTP handlers share it.
_POOLS = {}
_POOLS_LOCK = threading.Lock()


def _shared_pool(dsn, schema):
    key = (dsn, schema)
    with _POOLS_LOCK:
        entry = _POOLS.get(key)
        if entry is not None:
            return entry
        kwargs = {"row_factory": dict_row}
        if schema:
            kwargs["options"] = f"-c search_path={schema}"
        pool = ConnectionPool(
            dsn,
            min_size=config.DB_POOL_MIN_SIZE,
            max_size=config.DB_POOL_MAX_SIZE,
            kwargs=kwargs,
            check=ConnectionPool.check_connection,
            name=f"game-{schema or 'main'}",
            open=True,
        )
        try:
            pool.wait(timeout=10)
        except Exception as error:
            pool.close()
            raise RuntimeError(f"Нет подключения к PostgreSQL ({dsn}): {error}") from error
        entry = {"pool": pool, "initialized": False, "init_lock": threading.Lock()}
        _POOLS[key] = entry
        return entry


def lock_character(connection, character_id):
    """Serializes concurrent changes of one character until the current transaction ends."""
    connection.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
        (f"character:{int(character_id)}",),
    )


def close_all_pools():
    with _POOLS_LOCK:
        entries = list(_POOLS.values())
        _POOLS.clear()
    for entry in entries:
        entry["pool"].close()


atexit.register(close_all_pools)


class Database:
    def __init__(self, dsn=None, *, schema=None, world_id=None):
        self.dsn = dsn or config.DATABASE_URL
        self.schema = schema
        self.world_id = config.WORLD_ID if world_id is None else int(world_id)
        self._entry = _shared_pool(self.dsn, schema)
        self.initialize()

    @contextmanager
    def connection(self):
        # Commits when the block succeeds, rolls back on any exception.
        with self._entry["pool"].connection() as connection:
            yield connection

    def close(self):
        """Closes the shared pool. Only for throwaway databases (test schemas)."""
        with _POOLS_LOCK:
            _POOLS.pop((self.dsn, self.schema), None)
        self._entry["pool"].close()

    def initialize(self):
        with self._entry["init_lock"]:
            if not self._entry["initialized"]:
                self._initialize_schema()
                self._entry["initialized"] = True
        with self.connection() as connection:
            if connection.execute("SELECT 1 FROM worlds WHERE id = %s", (self.world_id,)).fetchone() is None:
                raise RuntimeError(f"Мир WORLD_ID={self.world_id} не найден в таблице worlds")

    def _initialize_schema(self):
        with self.connection() as connection:
            apply_migrations(connection)
            self._initialize_drinks(connection)
            self._normalize_character_stats(connection)

    @staticmethod
    def _normalize_character_stats(connection):
        """Fill in any missing stats so every character (warrior or mage) has all 7."""
        rows = connection.execute(
            "SELECT id, level, hp, mp, stats_json FROM characters"
        ).fetchall()
        for row in rows:
            stored = json.loads(row["stats_json"] or "{}")
            level = row["level"]
            stats = {
                "strength": max(MIN_STAT_VALUE, int(stored.get("strength", BASE_STAT_VALUE))),
                "agility": max(MIN_STAT_VALUE, int(stored.get("agility", BASE_STAT_VALUE))),
                "intuition": max(MIN_STAT_VALUE, int(stored.get("intuition", BASE_STAT_VALUE))),
                "wisdom": max(MIN_STAT_VALUE, int(stored.get("wisdom", BASE_STAT_VALUE))),
                "intellect": max(MIN_STAT_VALUE, int(stored.get("intellect", BASE_STAT_VALUE))),
                "harmony": max(MIN_STAT_VALUE, int(stored.get("harmony", BASE_STAT_VALUE))),
                "endurance": max(minimum_endurance(level), int(stored.get("endurance", minimum_endurance(level)))),
            }
            if stats == stored:
                continue
            max_hp = calculate_max_hp(level, stats["endurance"])
            max_mp = calculate_max_mana(stats["intellect"])
            connection.execute(
                """UPDATE characters
                   SET stats_json = %s, max_hp = %s, hp = LEAST(hp, %s),
                      mp = LEAST(mp, %s), max_mp = %s
                   WHERE id = %s""",
                (json.dumps(stats), max_hp, max_hp, row["mp"], max_mp, row["id"]),
            )

    @staticmethod
    def _initialize_drinks(connection):
        """Инициализирует напитки в БД"""
        now = time.time()
        drinks = [
            ("Эль", "Восстанавливает 50 жизней", 20, "heal", 50),
        ]
        for name, description, price_copper, effect, value in drinks:
            connection.execute(
                """INSERT INTO drinks (name, description, price_copper, effect, effect_value, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (name) DO NOTHING""",
                (name, description, price_copper, effect, value, now),
            )

    @staticmethod
    def _password_hash(password):
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            200_000,
        )
        return f"{salt.hex()}${digest.hex()}"

    @staticmethod
    def _check_password(password, stored):
        salt_hex, digest_hex = stored.split("$", 1)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            200_000,
        )
        return hmac.compare_digest(digest.hex(), digest_hex)

    @staticmethod
    def _user_payload(row):
        return {"id": row["id"], "username": row["username"], "role": row["role"] if "role" in row.keys() else "user"}

    def register(self, username, password):
        now = time.time()
        try:
            with self.connection() as connection:
                row = connection.execute(
                    "INSERT INTO users (username, password_hash, created_at) VALUES (%s, %s, %s) RETURNING id, username",
                    (username, self._password_hash(password), now),
                ).fetchone()
        except pg_errors.UniqueViolation as error:
            raise ValueError("Пользователь уже существует") from error
        return self._user_payload(row)

    def login(self, username, password):
        now = time.time()
        with self.connection() as connection:
            row = connection.execute(
                "SELECT id, username, password_hash FROM users WHERE username = %s AND id <> %s",
                (username, SYSTEM_USER_ID),
            ).fetchone()
            if row is None or not self._check_password(password, row["password_hash"]):
                raise ValueError("Неверное имя пользователя или пароль")
            for character in connection.execute(
                "SELECT * FROM characters WHERE user_id = %s AND world_id = %s",
                (row["id"], self.world_id),
            ).fetchall():
                self._apply_passive_regen(connection, character, now)
            token = secrets.token_urlsafe(32)
            connection.execute(
                "UPDATE users SET last_login_at = %s WHERE id = %s",
                (now, row["id"]),
            )
            connection.execute(
                "INSERT INTO sessions (token, user_id, world_id, created_at, last_seen_at) VALUES (%s, %s, %s, %s, %s)",
                (token, row["id"], self.world_id, now, now),
            )
        return {"token": token, "user": self._user_payload(row)}

    def user_id_by_token(self, token):
        if not token:
            raise ValueError("Требуется авторизация")
        now = time.time()
        with self.connection() as connection:
            row = connection.execute(
                "SELECT user_id FROM sessions WHERE token = %s AND world_id = %s AND last_seen_at > %s",
                (token, self.world_id, now - config.TOKEN_TTL_SECONDS),
            ).fetchone()
            if row is None:
                raise ValueError("Сессия недействительна или истекла")
            connection.execute(
                "UPDATE sessions SET last_seen_at = %s WHERE token = %s",
                (now, token),
            )
        return row["user_id"]

    def online_player_count(self, now=None):
        """Count recently active human accounts, deduplicating concurrent sessions."""
        now = time.time() if now is None else float(now)
        with self.connection() as connection:
            row = connection.execute(
                """SELECT COUNT(DISTINCT user_id) AS amount FROM sessions
                   WHERE user_id <> %s AND last_seen_at > %s""",
                (SYSTEM_USER_ID, now - config.ONLINE_PLAYER_TTL_SECONDS),
            ).fetchone()
        return int(row["amount"])
    
    def get_user(self, user_id):
        """Get user by ID with password hash"""
        with self.connection() as connection:
            row = connection.execute(
                "SELECT id, username, password_hash FROM users WHERE id = %s",
                (user_id,),
            ).fetchone()
        return row

    def create_character(self, user_id, name, profession_type="warrior"):
        self.validate_character_name(name)
        valid_professions = ["warrior", "archer", "assassin", "battle_mage", "support_mage", "harmonist"]
        if profession_type not in valid_professions:
            raise ValueError(f"Профессия должна быть одной из: {', '.join(valid_professions)}")
        
        now = time.time()
        
        # Единый набор из 7 характеристик для всех персонажей независимо от профессии
        stats = {
            "strength": BASE_STAT_VALUE,
            "agility": BASE_STAT_VALUE,
            "intuition": BASE_STAT_VALUE,
            "wisdom": BASE_STAT_VALUE,
            "intellect": BASE_STAT_VALUE,
            "harmony": BASE_STAT_VALUE,
            "endurance": minimum_endurance(1),
        }
        
        max_hp = calculate_max_hp(1, stats["endurance"])
        max_mp = calculate_max_mana(stats["intellect"])
        stat_points = STARTING_STAT_POINTS
        try:
            with self.connection() as connection:
                character_id = connection.execute(
                    """
                    INSERT INTO characters
                    (user_id, world_id, name, type, hp, max_hp, mp, max_mp, stats_json, stat_points, copper, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (user_id, self.world_id, name, profession_type, max_hp, max_hp, max_mp, max_mp,
                     json.dumps(stats), stat_points, 1000, now),
                ).fetchone()["id"]
        except pg_errors.UniqueViolation as error:
            if error.diag.constraint_name == "uq_characters_user_world":
                raise ValueError("В этом мире у вас уже есть персонаж") from error
            if error.diag.constraint_name == "uq_characters_world_name":
                raise ValueError("Это имя уже занято в этом мире") from error
            raise
        return self.get_character(user_id, character_id)

    def delete_character(self, user_id, character_id):
        """Delete a character"""
        with self.connection() as connection:
            row = connection.execute(
                "SELECT user_id FROM characters WHERE id = %s AND world_id = %s",
                (character_id, self.world_id),
            ).fetchone()
            if row is None or row["user_id"] != user_id:
                raise ValueError("Персонаж не найден")
            # Items, equipment, cards, farm and chat rows are removed by ON DELETE CASCADE.
            connection.execute(
                "DELETE FROM characters WHERE id = %s",
                (character_id,),
            )
        from server.social import remove_character_presence

        remove_character_presence(character_id)
    
    def delete_character_with_password(self, user_id, character_id, password):
        """Delete a character with password verification"""
        # First verify the password
        user = self.get_user(user_id)
        if user is None:
            raise ValueError("Пользователь не найден")
        
        # Verify password hash using existing method
        if not self._check_password(password, user["password_hash"]):
            raise ValueError("Неверный пароль")
        
        # Password is correct, delete the character
        self.delete_character(user_id, character_id)

    def update_character_profession(self, user_id, character_id, profession_type):
        """Update the profession marker without changing character stats."""
        valid_professions = ["warrior", "archer", "assassin", "battle_mage", "support_mage", "harmonist"]
        if profession_type not in valid_professions:
            raise ValueError(f"Профессия должна быть одной из: {', '.join(valid_professions)}")
        
        with self.connection() as connection:
            row = connection.execute(
                "SELECT user_id FROM characters WHERE id = %s AND world_id = %s",
                (character_id, self.world_id),
            ).fetchone()
            if row is None or row["user_id"] != user_id:
                raise ValueError("Персонаж не найден")
            # Preserve stats; new characters receive them in create_character.
            connection.execute(
                "UPDATE characters SET type = %s WHERE id = %s",
                (profession_type, character_id),
            )
        
        return self.get_character(user_id, character_id)
    
    @staticmethod
    def validate_character_name(name):
        forbidden = {
            "дурак", "идиот", "дебил", "тупой", "мразь", "сука",
            "блядь", "блять", "хуй", "пизд", "fuck", "shit",
            "idiot", "stupid",
        }
        normalized = "".join(character_name for character_name in name.lower() if character_name.isalpha())
        if not 1 <= len(name) <= 15:
            raise ValueError("Имя персонажа: от 1 до 15 символов")
        if any(word in normalized for word in forbidden):
            raise ValueError("Это имя нельзя использовать")

    @staticmethod
    def _inventory_rows_for_character(connection, character_id):
        return connection.execute(
            """SELECT ci.id as slot, d.id as drink_id, d.name, d.effect, d.effect_value, ci.quantity
            FROM character_inventory ci
            JOIN drinks d ON ci.drink_id = d.id
            WHERE ci.character_id = %s
            ORDER BY ci.id""",
            (character_id,),
        ).fetchall()

    def get_characters(self, user_id):
        now = time.time()
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM characters WHERE user_id = %s AND world_id = %s ORDER BY id",
                (user_id, self.world_id),
            ).fetchall()
            characters = []
            for original_row in rows:
                row = self._apply_passive_regen(connection, original_row, now)
                character = self._character_payload(row)

                inventory_rows = self._inventory_rows_for_character(connection, row["id"])

                inventory = {}
                for idx, inv_row in enumerate(inventory_rows, 1):
                    inventory[str(idx)] = {
                        "name": inv_row["name"],
                        "quantity": inv_row["quantity"],
                        "effect": inv_row["effect"],
                    }
                character["inventory"] = inventory
                character["equipment_bonuses"] = self.equipment_bonuses(connection, row["id"])
                character["equipment"] = self.equipped_items(connection, row["id"])
                self._update_carry_capacity(character)
                characters.append(character)

            return characters

    def add_chat_message(self, character_id, location, text, recipient_id=None):
        now = time.time()
        with self.connection() as connection:
            self._purge_old_chat_messages(connection, now)
            message_id = connection.execute(
                """
                INSERT INTO chat_messages
                (world_id, location, sender_character_id, recipient_character_id, text, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (self.world_id, location, character_id, recipient_id, text, now),
            ).fetchone()["id"]
            row = connection.execute(
                """
                SELECT chat_messages.*, characters.name AS sender_name
                FROM chat_messages
                JOIN characters ON characters.id = chat_messages.sender_character_id
                WHERE chat_messages.id = %s
                """,
                (message_id,),
            ).fetchone()
        return self._chat_message_payload(row)

    def ensure_bot_character(self, bot_id, bot_name):
        if bot_id is None:
            raise ValueError("Требуется идентификатор бота")
        synthetic_id = -abs(int(hashlib.md5(str(bot_id).encode("utf-8")).hexdigest()[:8], 16))
        with self.connection() as connection:
            # NPC rows are shared by all worlds; concurrent first messages must not collide.
            connection.execute(
                """
                INSERT INTO characters
                (id, user_id, world_id, name, level, xp, hp, max_hp, mp, max_mp,
                 stats_json, stat_points, zone, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    synthetic_id,
                    SYSTEM_USER_ID,
                    self.world_id,
                    str(bot_name),
                    1,
                    0,
                    200,
                    200,
                    50,
                    50,
                    json.dumps({"strength": 5, "agility": 5, "intuition": 5, "endurance": 5}),
                    0,
                    "tavern",
                    time.time(),
                ),
            )
        return synthetic_id

    def get_chat_history(self, character_id, location, before_id=None, limit=50):
        limit = max(1, min(100, int(limit)))
        cutoff = time.time() - config.CHAT_HISTORY_TTL_SECONDS
        with self.connection() as connection:
            self._purge_old_chat_messages(connection, time.time())
            query = """
                SELECT chat_messages.*, characters.name AS sender_name
                FROM chat_messages
                JOIN characters ON characters.id = chat_messages.sender_character_id
                WHERE chat_messages.world_id = %s
                                    AND chat_messages.location IN (%s, 'world')
                  AND chat_messages.created_at >= %s
                  AND chat_messages.deleted_at IS NULL
                  AND (chat_messages.recipient_character_id IS NULL
                       OR chat_messages.recipient_character_id = %s
                       OR chat_messages.sender_character_id = %s)
            """
            params = [self.world_id, location, cutoff, str(character_id), character_id]
            if before_id is not None:
                query += " AND chat_messages.id < %s"
                params.append(int(before_id))
            query += " ORDER BY chat_messages.id DESC LIMIT %s"
            params.append(limit)
            rows = connection.execute(query, params).fetchall()
            return [self._chat_message_payload(row) for row in reversed(rows)]

    @staticmethod
    def _purge_old_chat_messages(connection, now):
        connection.execute(
            "DELETE FROM chat_messages WHERE created_at < %s",
            (now - config.CHAT_HISTORY_TTL_SECONDS,),
        )

    @staticmethod
    def _purge_old_battle_logs(connection, now):
        """Удаляет логи боя старше 24 часов"""
        connection.execute(
            "DELETE FROM battle_logs WHERE expires_at < %s",
            (now,),
        )

    def mark_chat_read(self, character_id, location, message_id):
        now = time.time()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO chat_reads(character_id, location, last_read_message_id, last_read_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT(character_id, location) DO UPDATE SET
                    last_read_message_id = excluded.last_read_message_id,
                    last_read_at = excluded.last_read_at
                """,
                (character_id, location, int(message_id), now),
            )

    def chat_unread_count(self, character_id, location):
        with self.connection() as connection:
            row = connection.execute(
                "SELECT last_read_message_id FROM chat_reads WHERE character_id = %s AND location = %s",
                (character_id, location),
            ).fetchone()
            last_read = row["last_read_message_id"] if row else 0
            count = connection.execute(
                """
                SELECT COUNT(*) AS amount FROM chat_messages
                WHERE world_id = %s AND location = %s AND id > %s AND deleted_at IS NULL
                AND (recipient_character_id IS NULL OR recipient_character_id = %s)
                """,
                (self.world_id, location, last_read, str(character_id)),
            ).fetchone()
        return count["amount"]

    def report_chat_message(self, message_id, reporter_character_id, reason):
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO chat_reports(message_id, reporter_character_id, reason, created_at) VALUES (%s, %s, %s, %s)",
                (int(message_id), reporter_character_id, reason, time.time()),
            )

    def is_moderator(self, user_id):
        with self.connection() as connection:
            row = connection.execute("SELECT role FROM users WHERE id = %s", (user_id,)).fetchone()
        return row is not None and row["role"] in ("moderator", "admin")

    def delete_chat_message(self, message_id, moderator_id):
        if not self.is_moderator(moderator_id):
            raise ValueError("Недостаточно прав модератора")
        with self.connection() as connection:
            connection.execute(
                "UPDATE chat_messages SET deleted_at = %s, deleted_by = %s WHERE id = %s",
                (time.time(), moderator_id, int(message_id)),
            )

    def mute_character(self, character_id, muted_character_id, moderator_id, seconds=600):
        if not self.is_moderator(moderator_id):
            raise ValueError("Недостаточно прав модератора")
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO chat_mutes(character_id, muted_character_id, expires_at)
                VALUES (%s, %s, %s)
                ON CONFLICT(character_id, muted_character_id) DO UPDATE SET expires_at = excluded.expires_at
                """,
                (character_id, muted_character_id, time.time() + max(1, min(seconds, 86400))),
            )

    def is_muted(self, character_id, location):
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT 1 FROM chat_mutes
                WHERE muted_character_id = %s AND expires_at > %s
                """,
                (character_id, time.time()),
            ).fetchone()
        return row is not None

    @staticmethod
    def _chat_message_payload(row):
        sent_at = float(row["created_at"])
        return {
            "id": row["id"],
            "location": row["location"],
            "sender_id": row["sender_character_id"],
            "sender": row["sender_name"],
            "recipient_id": row["recipient_character_id"],
            "text": row["text"],
            "created_at": sent_at,
            "time_text": datetime.fromtimestamp(
                sent_at, ZoneInfo(config.SERVER_TIMEZONE)
            ).strftime("%H:%M:%S"),
        }

    def get_opponents(self, user_id):
        from server.world import get_bot_opponents

        now = time.time()
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM characters WHERE user_id <> %s AND user_id <> %s AND world_id = %s ORDER BY id",
                (user_id, SYSTEM_USER_ID, self.world_id),
            ).fetchall()
            players = [
                self._character_payload(
                    self._apply_passive_regen(connection, row, now)
                )
                for row in rows
            ]
            for opponent in players:
                opponent["equipment"] = self.equipped_items(connection, opponent["id"])
        for opponent in players:
            opponent["kind"] = "player"
        return get_bot_opponents() + players

    def update_bot(self, user_id, opponent_id, payload):
        from server.world import update_bot

        return update_bot(opponent_id, payload.get("hp", 0))

    def get_character(self, user_id, character_id=None):
        now = time.time()
        with self.connection() as connection:
            if character_id is None:
                row = connection.execute(
                    "SELECT * FROM characters WHERE user_id = %s AND world_id = %s ORDER BY id LIMIT 1",
                    (user_id, self.world_id),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT * FROM characters WHERE id = %s AND user_id = %s AND world_id = %s",
                    (character_id, user_id, self.world_id),
                ).fetchone()
            if row is None:
                return None
            row = self._apply_passive_regen(connection, row, now)
            character = self._character_payload(row)

            inventory_rows = self._inventory_rows_for_character(connection, row["id"])

            inventory = {}
            for idx, inv_row in enumerate(inventory_rows, 1):
                inventory[str(idx)] = {
                    "name": inv_row["name"],
                    "quantity": inv_row["quantity"],
                    "effect": inv_row["effect"],
                }
            character["inventory"] = inventory
            character["equipment_bonuses"] = self.equipment_bonuses(connection, row["id"])
            character["equipment"] = self.equipped_items(connection, row["id"])
            self._update_carry_capacity(character)

            return character

    def get_character_for_battle(self, character_id):
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM characters WHERE id = %s AND world_id = %s",
                (int(character_id), self.world_id),
            ).fetchone()
            if row is None:
                return None
            character = self._character_payload(row)
            character["equipment_bonuses"] = self.equipment_bonuses(connection, row["id"])
            character["equipment"] = self.equipped_items(connection, row["id"])
            self._update_carry_capacity(character)
        return {"user_id": row["user_id"], "character": character}

    @staticmethod
    def _update_carry_capacity(character):
        stats = character.get("stats", {})
        bonuses = character.get("equipment_bonuses", {})
        strength = int(stats.get("strength", BASE_STAT_VALUE)) + int(bonuses.get("strength", 0))
        endurance = int(stats.get("endurance", minimum_endurance(character.get("level", 1))))
        endurance += int(bonuses.get("endurance", 0))
        character["carry_capacity_kg"] = calculate_carry_capacity(strength, endurance)

    @staticmethod
    def equipped_items(connection, character_id):
        """Надетые предметы: {слот: предмет}. Отдаются вместе с любым персонажем,
        чтобы слоты на карточке были заполнены у всех, независимо от класса."""
        from server.items_database import _ITEM_COLUMNS, _item_payload, display_equipment_hands

        rows = connection.execute(
            f"""SELECT e.slot, e.item_id, {_ITEM_COLUMNS}
                FROM character_equipment e
                JOIN items_catalog c ON c.id = e.item_id
                WHERE e.character_id = %s""",
            (character_id,),
        ).fetchall()
        equipment = {row["slot"]: _item_payload(row) for row in rows}
        return display_equipment_hands(equipment)

    @staticmethod
    def equipment_bonuses(connection, character_id):
        """Суммарные бонусы к статам от надетых предметов: {"strength": 2, ...}"""
        rows = connection.execute(
            """SELECT c.bonuses_json FROM character_equipment e
               JOIN items_catalog c ON c.id = e.item_id
               WHERE e.character_id = %s""",
            (character_id,),
        ).fetchall()
        bonuses = {}
        for row in rows:
            for stat, value in json.loads(row["bonuses_json"] or "{}").items():
                bonuses[stat] = bonuses.get(stat, 0) + int(value)
        return bonuses

    @staticmethod
    def _has_active_session(connection, user_id, now):
        return connection.execute(
            "SELECT 1 FROM sessions WHERE user_id = %s AND last_seen_at > %s LIMIT 1",
            (user_id, now - config.TOKEN_TTL_SECONDS),
        ).fetchone() is not None

    @staticmethod
    def _apply_passive_regen(connection, row, now):
        hp = int(row["hp"])
        max_hp = int(row["max_hp"])
        if hp >= max_hp:
            return row
        recovered_hp = min(
            max_hp,
            hp + int(max(0.0, now - float(row["updated_at"])) * max_hp / config.PASSIVE_REGEN_FULL_SECONDS),
        )
        if recovered_hp == hp:
            return row
        connection.execute(
            "UPDATE characters SET hp = %s, updated_at = %s WHERE id = %s",
            (recovered_hp, now, row["id"]),
        )
        updated = dict(row)
        updated["hp"] = recovered_hp
        updated["updated_at"] = now
        return updated

    def save_character(self, user_id, character_id, payload):
        current = self.get_character(user_id, character_id)
        if current is None:
            raise ValueError("Персонаж не найден")
        
        # Нормализуем валюту перед сохранением
        currency = Currency(
            copper=int(payload.get("copper", current["copper"])),
            silver=int(payload.get("silver", current["silver"])),
            gold=int(payload.get("gold", current["gold"])),
        )
        currency.normalize()
        
        updated = {
            "name": str(payload.get("name", current["name"])),
            "level": int(payload.get("level", current["level"])),
            "xp": int(payload.get("xp", current["xp"])),
            "hp": int(payload.get("hp", current["hp"])),
            "max_hp": int(payload.get("max_hp", current["max_hp"])),
            "mp": int(payload.get("mp", current["mp"])),
            "max_mp": int(payload.get("max_mp", current["max_mp"])),
            "stats": payload.get("stats", current["stats"]),
            "stat_points": int(payload.get("stat_points", current["stat_points"])),
            "zone": str(payload.get("zone", current["zone"])),
            "position_x": (None if payload.get("position_x", current.get("position_x")) is None
                           else float(payload.get("position_x", current.get("position_x")))),
            "position_y": (None if payload.get("position_y", current.get("position_y")) is None
                           else float(payload.get("position_y", current.get("position_y")))),
            "position_direction": payload.get("position_direction", current.get("position_direction")),
            "copper": currency.copper,
            "silver": currency.silver,
            "gold": currency.gold,
        }
        # Единая проверка характеристик для всех типов персонажей (5 стартовых + 3 за уровень)
        level = updated["level"]
        raw_stats = updated["stats"] if isinstance(updated["stats"], dict) else {}
        updated["stats"] = {
            "strength": max(MIN_STAT_VALUE, int(raw_stats.get("strength", BASE_STAT_VALUE))),
            "agility": max(MIN_STAT_VALUE, int(raw_stats.get("agility", BASE_STAT_VALUE))),
            "intuition": max(MIN_STAT_VALUE, int(raw_stats.get("intuition", BASE_STAT_VALUE))),
            "wisdom": max(MIN_STAT_VALUE, int(raw_stats.get("wisdom", BASE_STAT_VALUE))),
            "intellect": max(MIN_STAT_VALUE, int(raw_stats.get("intellect", BASE_STAT_VALUE))),
            "harmony": max(MIN_STAT_VALUE, int(raw_stats.get("harmony", BASE_STAT_VALUE))),
            "endurance": max(minimum_endurance(level), int(raw_stats.get("endurance", minimum_endurance(level)))),
        }
        updated["max_hp"] = calculate_max_hp(level, updated["stats"]["endurance"])
        updated["hp"] = min(updated["hp"], updated["max_hp"])
        updated["max_mp"] = calculate_max_mana(updated["stats"]["intellect"])
        updated["mp"] = min(updated["mp"], updated["max_mp"])
        self.validate_character_name(updated["name"])
        self._validate_character(updated)
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE characters SET name = %s, level = %s, xp = %s, hp = %s,
                max_hp = %s, mp = %s, max_mp = %s, stats_json = %s, stat_points = %s,
                zone = %s, position_x = %s, position_y = %s, position_direction = %s,
                copper = %s, silver = %s, gold = %s, updated_at = %s
                WHERE id = %s AND user_id = %s AND world_id = %s
                """,
                (
                    updated["name"], updated["level"], updated["xp"], updated["hp"],
                    updated["max_hp"], updated["mp"], updated["max_mp"],
                    json.dumps(updated["stats"]), updated["stat_points"],
                    updated["zone"], updated["position_x"], updated["position_y"],
                    updated["position_direction"], updated["copper"], updated["silver"], updated["gold"],
                    time.time(), character_id, user_id, self.world_id,
                ),
            )
        return self.get_character(user_id, character_id)

    def save_active_battle(self, player_id, opponent_id, battle_data):
        """Сохраняет состояние активного боя"""
        now = time.time()
        with self.connection() as connection:
            cursor = connection.execute(
                "SELECT id FROM active_battles WHERE player_id = %s AND opponent_id = %s",
                (player_id, opponent_id),
            )
            row = cursor.fetchone()
            if row:
                connection.execute(
                    "UPDATE active_battles SET battle_data = %s, updated_at = %s WHERE id = %s",
                    (json.dumps(battle_data), now, row["id"]),
                )
            else:
                connection.execute(
                    "INSERT INTO active_battles (player_id, opponent_id, battle_data, created_at, updated_at) VALUES (%s, %s, %s, %s, %s)",
                    (player_id, opponent_id, json.dumps(battle_data), now, now),
                )

    def mark_player_afk(self, player_id, opponent_id, is_afk=True):
        """Отмечает игрока как АФК в боевой системе"""
        with self.connection() as connection:
            connection.execute(
                "UPDATE active_battles SET player_afk = %s WHERE player_id = %s AND opponent_id = %s",
                (1 if is_afk else 0, player_id, opponent_id),
            )

    def mark_opponent_afk(self, player_id, opponent_id, is_afk=True):
        with self.connection() as connection:
            connection.execute(
                "UPDATE active_battles SET opponent_afk = %s WHERE player_id = %s AND opponent_id = %s",
                (1 if is_afk else 0, player_id, opponent_id),
            )

    def get_active_battle(self, player_id, opponent_id):
        """Получает сохраненное состояние боя"""
        with self.connection() as connection:
            row = connection.execute(
                "SELECT battle_data, player_afk, opponent_afk FROM active_battles WHERE player_id = %s AND opponent_id = %s",
                (player_id, opponent_id),
            ).fetchone()
            if row:
                return {
                    "battle_data": json.loads(row["battle_data"]),
                    "player_afk": bool(row["player_afk"]),
                    "opponent_afk": bool(row["opponent_afk"]),
                }
            return None

    def delete_active_battle(self, player_id, opponent_id):
        """Архивирует завершенный бой в логи (вместо удаления)"""
        with self.connection() as connection:
            # Получаем данные боя перед удалением
            battle = connection.execute(
                "SELECT battle_data, player_afk, opponent_afk FROM active_battles WHERE player_id = %s AND opponent_id = %s",
                (player_id, opponent_id),
            ).fetchone()
            
            if battle:
                now = time.time()
                expires_at = now + 24 * 60 * 60  # 24 часа
                
                # Архивируем в battle_logs
                connection.execute(
                    """INSERT INTO battle_logs 
                    (player_id, opponent_id, battle_data, player_afk, opponent_afk, created_at, expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (player_id, opponent_id, battle["battle_data"], battle["player_afk"], 
                     battle["opponent_afk"], now, expires_at),
                )
                
                # Удаляем из активных боев
                connection.execute(
                    "DELETE FROM active_battles WHERE player_id = %s AND opponent_id = %s",
                    (player_id, opponent_id),
                )
                
                # Автоочистка старых логов (старше 24 часов)
                self._purge_old_battle_logs(connection, now)

    def get_battle_log(self, player_id, opponent_id):
        """Получает сохраненный лог боя"""
        with self.connection() as connection:
            row = connection.execute(
                """SELECT battle_data, player_afk, opponent_afk, created_at 
                FROM battle_logs 
                WHERE player_id = %s AND opponent_id = %s
                AND expires_at > %s
                ORDER BY created_at DESC LIMIT 1""",
                (player_id, opponent_id, time.time()),
            ).fetchone()
            if row:
                return {
                    "battle_data": json.loads(row["battle_data"]),
                    "player_afk": bool(row["player_afk"]),
                    "opponent_afk": bool(row["opponent_afk"]),
                    "created_at": row["created_at"],
                }
            return None

    def save_battle_archive(self, character_id, opponent_id, outcome, replay):
        if outcome not in ("win", "draw", "loss"):
            raise ValueError("Некорректный исход боя")
        if not isinstance(replay, dict) or not replay.get("id"):
            raise ValueError("Некорректная запись боя")
        player = replay.get("player")
        enemy = replay.get("enemy")
        if not isinstance(player, dict) or not isinstance(enemy, dict):
            raise ValueError("В записи боя отсутствуют участники")
        try:
            replay_json = json.dumps(replay, ensure_ascii=False, allow_nan=False)
            player_level = max(1, int(player["level"]))
            opponent_level = max(1, int(enemy["level"]))
            turns = max(0, int(replay.get("turns", 0)))
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Некорректные данные записи боя") from error
        now = time.time()
        with self.connection() as connection:
            character = connection.execute(
                "SELECT name FROM characters WHERE id=%s AND world_id=%s",
                (int(character_id), self.world_id),
            ).fetchone()
            if character is None:
                raise ValueError("Персонаж не найден")
            opponent_character_id = None
            if opponent_id is not None:
                opponent_row = connection.execute(
                    "SELECT id FROM characters WHERE id=%s AND world_id=%s",
                    (int(opponent_id), self.world_id),
                ).fetchone()
                if opponent_row is not None:
                    opponent_character_id = int(opponent_row["id"])
            connection.execute(
                """INSERT INTO battle_archive
                   (world_id,battle_key,player_character_id,opponent_character_id,
                    player_name,opponent_name,player_level,opponent_level,winner_name,
                    outcome,turns,replay_json,created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
                   ON CONFLICT (world_id,battle_key) DO NOTHING""",
                (self.world_id, str(replay["id"]), int(character_id), opponent_character_id,
                 character["name"], str(enemy.get("name", "Противник")), player_level,
                 opponent_level, str(replay.get("winner", "")), outcome, turns,
                 replay_json, now),
            )
            row = connection.execute(
                "SELECT id FROM battle_archive WHERE world_id=%s AND battle_key=%s",
                (self.world_id, str(replay["id"])),
            ).fetchone()
        return int(row["id"])

    def list_battle_archive(self, limit=50, offset=0):
        limit = max(1, min(100, int(limit)))
        offset = max(0, int(offset))
        with self.connection() as connection:
            total = int(connection.execute(
                "SELECT COUNT(*) AS amount FROM battle_archive WHERE world_id=%s",
                (self.world_id,),
            ).fetchone()["amount"])
            rows = connection.execute(
                """SELECT id,battle_key,player_name,opponent_name,player_level,
                          opponent_level,winner_name,outcome,turns,created_at
                   FROM battle_archive WHERE world_id=%s
                   ORDER BY created_at DESC,id DESC LIMIT %s OFFSET %s""",
                (self.world_id, limit, offset),
            ).fetchall()
        return {"battles": [dict(row) for row in rows], "total": total,
                "limit": limit, "offset": offset}

    def get_battle_archive(self, archive_id):
        with self.connection() as connection:
            row = connection.execute(
                """SELECT id,battle_key,player_name,opponent_name,player_level,
                          opponent_level,winner_name,outcome,turns,created_at,replay_json
                   FROM battle_archive WHERE world_id=%s AND id=%s""",
                (self.world_id, int(archive_id)),
            ).fetchone()
        return None if row is None else dict(row)

    @staticmethod
    def _validate_character(character):
        if not 1 <= character["level"] <= 1000:
            raise ValueError("Некорректный уровень персонажа")
        if character["xp"] < 0 or character["stat_points"] < 0:
            raise ValueError("XP и очки характеристик не могут быть отрицательными")
        if not 0 <= character["hp"] <= character["max_hp"]:
            raise ValueError("Некорректное значение HP")
        if not 0 <= character["mp"] <= character["max_mp"]:
            raise ValueError("Некорректное значение MP")
        if not isinstance(character["stats"], dict):
            raise ValueError("Характеристики должны быть объектом")
        # Валюта неотрицательна
        if character.get("copper", 0) < 0 or character.get("silver", 0) < 0 or character.get("gold", 0) < 0:
            raise ValueError("Валюта не может быть отрицательной")

    @staticmethod
    def _character_payload(row):
        row_dict = dict(row)
        stats = json.loads(row["stats_json"])
        character_type = row["type"] if "type" in row.keys() else "warrior"
        max_hp = calculate_max_hp(row["level"], stats.get("endurance", minimum_endurance(row["level"])))
        max_mp = calculate_max_mana(stats.get("intellect", BASE_STAT_VALUE))

        # Нормализуем валюту
        currency = Currency(
            copper=int(row_dict.get("copper", 0)) if row_dict.get("copper") is not None else 0,
            silver=int(row_dict.get("silver", 0)) if row_dict.get("silver") is not None else 0,
            gold=int(row_dict.get("gold", 0)) if row_dict.get("gold") is not None else 0,
        )
        currency.normalize()

        return {
            "id": row["id"],
            "name": row["name"],
            "type": character_type,
            "level": row["level"],
            "xp": row["xp"],
            "hp": min(row["hp"], max_hp),
            "max_hp": max_hp,
            "mp": min(row["mp"], max_mp),
            "max_mp": max_mp,
            "stats": stats,
            "carry_capacity_kg": calculate_carry_capacity(
                stats.get("strength", BASE_STAT_VALUE),
                stats.get("endurance", minimum_endurance(row["level"])),
            ),
            "stat_points": row["stat_points"],
            "zone": row["zone"],
            "position_x": row_dict.get("position_x"),
            "position_y": row_dict.get("position_y"),
            "position_direction": row_dict.get("position_direction"),
            "copper": currency.copper,
            "silver": currency.silver,
            "gold": currency.gold,
            "updated_at": row["updated_at"],
        }

    def disconnect(self, token, character_id=None, payload=None):
        user_id = self.user_id_by_token(token)
        if character_id is not None and payload is not None:
            self.save_character(user_id, character_id, payload)
        with self.connection() as connection:
            connection.execute("DELETE FROM sessions WHERE token = %s", (token,))
        return {"saved": True}
    
    def get_drinks_list(self):
        """Получить список всех напитков"""
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT id, name, description, price_copper, effect, effect_value FROM drinks ORDER BY id"
            ).fetchall()
            return [dict(row) for row in rows]
    
    def buy_drink(self, user_id, character_id, drink_id):
        """Купить напиток - вычесть цену и применить эффект сразу (НЕ добавлять в инвентарь)"""
        from core.currency import Currency
        
        with self.connection() as connection:
            # Получаем информацию о напитке
            drink = connection.execute(
                "SELECT price_copper, effect, effect_value FROM drinks WHERE id = %s",
                (drink_id,)
            ).fetchone()
            
            if drink is None:
                raise ValueError("Напиток не найден")
            
            # Получаем персонажа
            character = self.get_character(user_id, character_id)
            if character is None:
                raise ValueError("Персонаж не найден")
            
            # ПРОВЕРЯЕМ: полное ли здоровье?
            current_hp = character.get("hp", 0)
            max_hp = character.get("max_hp", 100)
            if current_hp >= max_hp:
                # Отправляем сообщение бармена в чат таверны
                bartender_id = "tavern_bartender"
                self.ensure_bot_character(bartender_id, "Хозяин трактира")
                bartender_character_id = -abs(int(hashlib.md5(str(bartender_id).encode("utf-8")).hexdigest()[:8], 16))
                self.add_chat_message(
                    bartender_character_id,
                    "tavern",
                    "Тебе уже хватит, прогуляйся на задний двор прийди в чуство!! ХА-ХА-ХА"
                )
                raise ValueError("БАРМАН_ПОЛНОЕ_ЗДОРОВЬЕ")
            
            # Проверяем деньги
            current = Currency.from_dict(character)
            if not current.has_enough_copper(drink["price_copper"]):
                raise ValueError("Недостаточно денег")
            
            # Вычитаем деньги
            current.subtract_copper_amount(drink["price_copper"])
            character.update(current.to_dict())
            
            # Применяем эффект напитка (восстанавливаем HP, но не больше max_hp)
            if drink["effect"] == "heal":
                healing = drink["effect_value"]
                new_hp = min(current_hp + healing, max_hp)
                character["hp"] = new_hp
            
            # Сохраняем персонажа с эффектом и без денег
            self.save_character(user_id, character_id, character)
            
            # Возвращаем обновленного персонажа
            return self.get_character(user_id, character_id)
    
    def get_character_inventory(self, character_id):
        """Получить инвентарь персонажа"""
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT ci.id, d.id as drink_id, d.name, d.effect, d.effect_value, ci.quantity
                FROM character_inventory ci
                JOIN drinks d ON ci.drink_id = d.id
                WHERE ci.character_id = %s
                ORDER BY d.name""",
                (character_id,)
            ).fetchall()
            return [dict(row) for row in rows]
    
    def use_drink(self, user_id, character_id, inventory_item_id):
        """Использовать напиток из инвентаря"""
        with self.connection() as connection:
            # Получаем предмет из инвентаря
            item = connection.execute(
                """SELECT ci.id, d.effect, d.effect_value, ci.drink_id
                FROM character_inventory ci
                JOIN drinks d ON ci.drink_id = d.id
                WHERE ci.id = %s AND ci.character_id = %s""",
                (inventory_item_id, character_id)
            ).fetchone()
            
            if item is None:
                raise ValueError("Предмет не найден в инвентаре")
            
            # Получаем персонажа
            character = self.get_character(user_id, character_id)
            if character is None:
                raise ValueError("Персонаж не найден")
            
            # Применяем эффект
            if item["effect"] == "heal":
                character["hp"] = min(character["hp"] + item["effect_value"], character["max_hp"])
            
            # Сохраняем изменения
            self.save_character(user_id, character_id, character)
            
            # Удаляем из инвентаря или уменьшаем количество
            connection.execute(
                "UPDATE character_inventory SET quantity = quantity - 1 WHERE id = %s",
                (inventory_item_id,)
            )
            connection.execute(
                "DELETE FROM character_inventory WHERE quantity <= 0"
            )
            
            return self.get_character(user_id, character_id)

    def get_card_collection(self, character_id):
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT id, card_key, quantity, slot_index, acquired_at
                   FROM character_card_collection
                   WHERE character_id = %s
                   ORDER BY slot_index""",
                (character_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def ensure_starter_cards(self, character_id, card_keys):
        """Один раз кладёт в коллекцию карты класса, чтобы из них можно было собрать колоду."""
        with self.connection() as connection:
            lock_character(connection, character_id)
            granted = connection.execute(
                "SELECT 1 FROM character_card_grants WHERE character_id = %s",
                (character_id,),
            ).fetchone()
            if granted:
                return False
            rows = connection.execute(
                "SELECT card_key, slot_index FROM character_card_collection WHERE character_id = %s",
                (character_id,),
            ).fetchall()
            owned = {row["card_key"] for row in rows}
            free_slots = iter(sorted(set(range(60)) - {row["slot_index"] for row in rows}))
            now = time.time()
            for card_key in card_keys:
                if card_key in owned:
                    continue
                slot_index = next(free_slots, None)
                if slot_index is None:
                    break
                connection.execute(
                    """INSERT INTO character_card_collection
                       (character_id, card_key, quantity, slot_index, acquired_at)
                       VALUES (%s, %s, 1, %s, %s)""",
                    (character_id, card_key, slot_index, now),
                )
            connection.execute(
                "INSERT INTO character_card_grants (character_id, starter_cards_at) VALUES (%s, %s)",
                (character_id, now),
            )
            return True

    def add_card_to_collection(self, character_id, card_key):
        with self.connection() as connection:
            lock_character(connection, character_id)
            existing = connection.execute(
                """SELECT id, quantity, slot_index
                   FROM character_card_collection
                   WHERE character_id = %s AND card_key = %s""",
                (character_id, card_key),
            ).fetchone()
            if existing is not None:
                connection.execute(
                    """UPDATE character_card_collection
                       SET quantity = quantity + 1, acquired_at = %s
                       WHERE id = %s""",
                    (time.time(), existing["id"]),
                )
                return {
                    "id": existing["id"],
                    "card_key": card_key,
                    "quantity": existing["quantity"] + 1,
                    "slot_index": existing["slot_index"],
                }

            used_slots = {
                row["slot_index"]
                for row in connection.execute(
                    """SELECT slot_index
                       FROM character_card_collection
                       WHERE character_id = %s""",
                    (character_id,),
                ).fetchall()
            }
            slot_index = next((slot for slot in range(60) if slot not in used_slots), None)
            if slot_index is None:
                raise ValueError("В коллекции нет свободных ячеек")
            now = time.time()
            entry_id = connection.execute(
                """INSERT INTO character_card_collection
                   (character_id, card_key, quantity, slot_index, acquired_at)
                   VALUES (%s, %s, 1, %s, %s)
                   RETURNING id""",
                (character_id, card_key, slot_index, now),
            ).fetchone()["id"]
            return {
                "id": entry_id,
                "card_key": card_key,
                "quantity": 1,
                "slot_index": slot_index,
                "acquired_at": now,
            }
