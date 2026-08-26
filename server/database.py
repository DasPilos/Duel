import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager

from server import config


class Database:
    def __init__(self, path=config.DATABASE_PATH):
        self.path = str(path)
        self.initialize()

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self):
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    last_login_at REAL
                );

                CREATE TABLE IF NOT EXISTS characters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    level INTEGER NOT NULL DEFAULT 1,
                    xp INTEGER NOT NULL DEFAULT 0,
                    hp INTEGER NOT NULL,
                    max_hp INTEGER NOT NULL,
                    mp INTEGER NOT NULL DEFAULT 50,
                    max_mp INTEGER NOT NULL DEFAULT 50,
                    stats_json TEXT NOT NULL,
                    stat_points INTEGER NOT NULL DEFAULT 6,
                    zone TEXT NOT NULL DEFAULT 'town',
                    updated_at REAL NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    last_seen_at REAL NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location TEXT NOT NULL,
                    sender_character_id INTEGER NOT NULL,
                    recipient_character_id TEXT,
                    text TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    deleted_at REAL,
                    deleted_by INTEGER
                );

                CREATE INDEX IF NOT EXISTS idx_chat_messages_location_time
                    ON chat_messages(location, created_at, id);

                CREATE TABLE IF NOT EXISTS chat_reads (
                    character_id INTEGER NOT NULL,
                    location TEXT NOT NULL,
                    last_read_message_id INTEGER NOT NULL DEFAULT 0,
                    last_read_at REAL NOT NULL,
                    PRIMARY KEY(character_id, location)
                );

                CREATE TABLE IF NOT EXISTS chat_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER NOT NULL,
                    reporter_character_id INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chat_mutes (
                    character_id INTEGER NOT NULL,
                    muted_character_id INTEGER NOT NULL,
                    expires_at REAL,
                    PRIMARY KEY(character_id, muted_character_id)
                );
                """
            )
            user_columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
            if "role" not in user_columns:
                connection.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
            self._migrate_characters(connection)

    @staticmethod
    def _migrate_characters(connection):
        columns = connection.execute("PRAGMA table_info(characters)").fetchall()
        if not columns:
            return
        indexes = connection.execute("PRAGMA index_list(characters)").fetchall()
        has_single_character_constraint = False
        for index in indexes:
            if not index[2]:
                continue
            index_columns = connection.execute(
                f"PRAGMA index_info({index[1]})"
            ).fetchall()
            if [item[2] for item in index_columns] == ["user_id"]:
                has_single_character_constraint = True
                break
        if not has_single_character_constraint:
            return
        connection.execute("ALTER TABLE characters RENAME TO characters_legacy")
        connection.execute(
            """
            CREATE TABLE characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                level INTEGER NOT NULL DEFAULT 1,
                xp INTEGER NOT NULL DEFAULT 0,
                hp INTEGER NOT NULL,
                max_hp INTEGER NOT NULL,
                mp INTEGER NOT NULL DEFAULT 50,
                max_mp INTEGER NOT NULL DEFAULT 50,
                stats_json TEXT NOT NULL,
                stat_points INTEGER NOT NULL DEFAULT 6,
                zone TEXT NOT NULL DEFAULT 'tavern',
                updated_at REAL NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO characters
            (id, user_id, name, level, xp, hp, max_hp, mp, max_mp,
             stats_json, stat_points, zone, updated_at)
            SELECT id, user_id, name, level, xp, hp, max_hp, mp, max_mp,
                   stats_json, stat_points, zone, updated_at
            FROM characters_legacy
            """
        )
        connection.execute("DROP TABLE characters_legacy")

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
        with self.connection() as connection:
            try:
                cursor = connection.execute(
                    "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                    (username, self._password_hash(password), now),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("Пользователь уже существует") from error
            row = connection.execute(
                "SELECT id, username FROM users WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return self._user_payload(row)

    def login(self, username, password):
        now = time.time()
        with self.connection() as connection:
            row = connection.execute(
                "SELECT id, username, password_hash FROM users WHERE username = ?",
                (username,),
            ).fetchone()
            if row is None or not self._check_password(password, row["password_hash"]):
                raise ValueError("Неверное имя пользователя или пароль")
            for character in connection.execute(
                "SELECT * FROM characters WHERE user_id = ?",
                (row["id"],),
            ).fetchall():
                self._apply_passive_regen(connection, character, now)
            token = secrets.token_urlsafe(32)
            connection.execute(
                "UPDATE users SET last_login_at = ? WHERE id = ?",
                (now, row["id"]),
            )
            connection.execute(
                "INSERT INTO sessions (token, user_id, created_at, last_seen_at) VALUES (?, ?, ?, ?)",
                (token, row["id"], now, now),
            )
        return {"token": token, "user": self._user_payload(row)}

    def user_id_by_token(self, token):
        if not token:
            raise ValueError("Требуется авторизация")
        now = time.time()
        with self.connection() as connection:
            row = connection.execute(
                "SELECT user_id FROM sessions WHERE token = ? AND last_seen_at > ?",
                (token, now - config.TOKEN_TTL_SECONDS),
            ).fetchone()
            if row is None:
                raise ValueError("Сессия недействительна или истекла")
            connection.execute(
                "UPDATE sessions SET last_seen_at = ? WHERE token = ?",
                (now, token),
            )
        return row["user_id"]

    def create_character(self, user_id, name):
        self.validate_character_name(name)
        now = time.time()
        stats = {
            "strength": 5,
            "agility": 5,
            "intuition": 5,
            "endurance": 5,
        }
        max_hp = 100 + stats["endurance"] * 14
        with self.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO characters
                (user_id, name, hp, max_hp, stats_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, name, max_hp, max_hp, json.dumps(stats), now),
            )
            character_id = cursor.lastrowid
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

    def get_characters(self, user_id):
        now = time.time()
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM characters WHERE user_id = ? ORDER BY id",
                (user_id,),
            ).fetchall()
            return [
                self._character_payload(
                    self._apply_passive_regen(connection, row, now)
                )
                for row in rows
                if not self._has_active_session(connection, user_id, now)
            ] + [
                self._character_payload(row)
                for row in rows
                if self._has_active_session(connection, user_id, now)
            ]

    def add_chat_message(self, character_id, location, text, recipient_id=None):
        now = time.time()
        with self.connection() as connection:
            self._purge_old_chat_messages(connection, now)
            cursor = connection.execute(
                """
                INSERT INTO chat_messages
                (location, sender_character_id, recipient_character_id, text, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (location, character_id, recipient_id, text, now),
            )
            row = connection.execute(
                """
                SELECT chat_messages.*, characters.name AS sender_name
                FROM chat_messages
                JOIN characters ON characters.id = chat_messages.sender_character_id
                WHERE chat_messages.id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
        return self._chat_message_payload(row)

    def ensure_bot_character(self, bot_id, bot_name):
        if bot_id is None:
            raise ValueError("Требуется идентификатор бота")
        synthetic_id = -abs(int(hashlib.md5(str(bot_id).encode("utf-8")).hexdigest()[:8], 16))
        with self.connection() as connection:
            row = connection.execute(
                "SELECT id, name FROM characters WHERE id = ?",
                (synthetic_id,),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO characters
                    (id, user_id, name, level, xp, hp, max_hp, mp, max_mp,
                     stats_json, stat_points, zone, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        synthetic_id,
                        0,
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
                WHERE chat_messages.location = ?
                                    AND chat_messages.created_at >= ?
                  AND chat_messages.deleted_at IS NULL
                  AND (chat_messages.recipient_character_id IS NULL
                       OR chat_messages.recipient_character_id = ?)
            """
            params = [location, cutoff, str(character_id)]
            if before_id is not None:
                query += " AND chat_messages.id < ?"
                params.append(int(before_id))
            query += " ORDER BY chat_messages.id DESC LIMIT ?"
            params.append(limit)
            rows = connection.execute(query, params).fetchall()
            return [self._chat_message_payload(row) for row in reversed(rows)]

    @staticmethod
    def _purge_old_chat_messages(connection, now):
        connection.execute(
            "DELETE FROM chat_messages WHERE created_at < ?",
            (now - config.CHAT_HISTORY_TTL_SECONDS,),
        )

    def mark_chat_read(self, character_id, location, message_id):
        now = time.time()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO chat_reads(character_id, location, last_read_message_id, last_read_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(character_id, location) DO UPDATE SET
                    last_read_message_id = excluded.last_read_message_id,
                    last_read_at = excluded.last_read_at
                """,
                (character_id, location, int(message_id), now),
            )

    def chat_unread_count(self, character_id, location):
        with self.connection() as connection:
            row = connection.execute(
                "SELECT last_read_message_id FROM chat_reads WHERE character_id = ? AND location = ?",
                (character_id, location),
            ).fetchone()
            last_read = row["last_read_message_id"] if row else 0
            count = connection.execute(
                """
                SELECT COUNT(*) AS amount FROM chat_messages
                WHERE location = ? AND id > ? AND deleted_at IS NULL
                AND (recipient_character_id IS NULL OR recipient_character_id = ?)
                """,
                (location, last_read, str(character_id)),
            ).fetchone()
        return count["amount"]

    def report_chat_message(self, message_id, reporter_character_id, reason):
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO chat_reports(message_id, reporter_character_id, reason, created_at) VALUES (?, ?, ?, ?)",
                (int(message_id), reporter_character_id, reason, time.time()),
            )

    def is_moderator(self, user_id):
        with self.connection() as connection:
            row = connection.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
        return row is not None and row["role"] in ("moderator", "admin")

    def delete_chat_message(self, message_id, moderator_id):
        if not self.is_moderator(moderator_id):
            raise ValueError("Недостаточно прав модератора")
        with self.connection() as connection:
            connection.execute(
                "UPDATE chat_messages SET deleted_at = ?, deleted_by = ? WHERE id = ?",
                (time.time(), moderator_id, int(message_id)),
            )

    def mute_character(self, character_id, muted_character_id, moderator_id, seconds=600):
        if not self.is_moderator(moderator_id):
            raise ValueError("Недостаточно прав модератора")
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO chat_mutes(character_id, muted_character_id, expires_at)
                VALUES (?, ?, ?)
                ON CONFLICT(character_id, muted_character_id) DO UPDATE SET expires_at = excluded.expires_at
                """,
                (character_id, muted_character_id, time.time() + max(1, min(seconds, 86400))),
            )

    def is_muted(self, character_id, location):
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT 1 FROM chat_mutes
                WHERE muted_character_id = ? AND expires_at > ?
                """,
                (character_id, time.time()),
            ).fetchone()
        return row is not None

    @staticmethod
    def _chat_message_payload(row):
        return {
            "id": row["id"],
            "location": row["location"],
            "sender_id": row["sender_character_id"],
            "sender": row["sender_name"],
            "recipient_id": row["recipient_character_id"],
            "text": row["text"],
            "created_at": row["created_at"],
        }

    def get_opponents(self, user_id):
        from server.world import get_bot_opponents

        now = time.time()
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM characters WHERE user_id != ? ORDER BY id",
                (user_id,),
            ).fetchall()
            players = [
                self._character_payload(
                    self._apply_passive_regen(connection, row, now)
                )
                if not self._has_active_session(connection, row["user_id"], now)
                else self._character_payload(row)
                for row in rows
            ]
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
                    "SELECT * FROM characters WHERE user_id = ? ORDER BY id LIMIT 1",
                    (user_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT * FROM characters WHERE id = ? AND user_id = ?",
                    (character_id, user_id),
                ).fetchone()
            if row is None:
                return None
            if not self._has_active_session(connection, user_id, now):
                row = self._apply_passive_regen(connection, row, now)
            return self._character_payload(row)

    @staticmethod
    def _has_active_session(connection, user_id, now):
        return connection.execute(
            "SELECT 1 FROM sessions WHERE user_id = ? AND last_seen_at > ? LIMIT 1",
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
            "UPDATE characters SET hp = ?, updated_at = ? WHERE id = ?",
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
        }
        self.validate_character_name(updated["name"])
        self._validate_character(updated)
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE characters SET name = ?, level = ?, xp = ?, hp = ?,
                max_hp = ?, mp = ?, max_mp = ?, stats_json = ?, stat_points = ?,
                zone = ?, updated_at = ? WHERE id = ? AND user_id = ?
                """,
                (
                    updated["name"], updated["level"], updated["xp"], updated["hp"],
                    updated["max_hp"], updated["mp"], updated["max_mp"],
                    json.dumps(updated["stats"]), updated["stat_points"],
                    updated["zone"], time.time(), character_id, user_id,
                ),
            )
        return self.get_character(user_id, character_id)

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

    @staticmethod
    def _character_payload(row):
        return {
            "id": row["id"],
            "name": row["name"],
            "level": row["level"],
            "xp": row["xp"],
            "hp": row["hp"],
            "max_hp": row["max_hp"],
            "mp": row["mp"],
            "max_mp": row["max_mp"],
            "stats": json.loads(row["stats_json"]),
            "stat_points": row["stat_points"],
            "zone": row["zone"],
            "updated_at": row["updated_at"],
        }

    def disconnect(self, token, character_id=None, payload=None):
        user_id = self.user_id_by_token(token)
        if character_id is not None and payload is not None:
            self.save_character(user_id, character_id, payload)
        with self.connection() as connection:
            connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
        return {"saved": True}
