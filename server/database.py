import atexit
import base64
import binascii
import hashlib
import hmac
import json
import secrets
import struct
import threading
import time
import uuid
from urllib.parse import urlparse
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo
import zlib

from psycopg import errors as pg_errors
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from combat.character_stats import (
    BASE_STAT_VALUE,
    MIN_STAT_VALUE,
    calculate_carry_capacity,
    calculate_max_hp,
    calculate_max_mana,
    creation_stats,
    minimum_endurance,
)
from core.currency import Currency
from core.game_modes import is_mode
from core.map_editor_assets import read_catalog_asset
from server import config, map_editor
from server import map_palette
from server.migrations import apply_migrations
from server.mode_registry import get_mode

SYSTEM_USER_ID = 0
CUSTOM_TILE_CATEGORIES = frozenset({"grass", "mountain", "water", "road", "forest"})
CUSTOM_TILE_SIZE = 16
CUSTOM_TILE_MAX_BYTES = 64 * 1024
CUSTOM_TILE_GROUP_MAX_BYTES = 256 * 1024


def _decode_custom_tile_png(encoded):
    if not isinstance(encoded, str):
        raise ValueError("Каждый тайл группы должен быть PNG-изображением")
    try:
        image = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("Некорректное кодирование PNG тайла") from None
    if len(image) > CUSTOM_TILE_MAX_BYTES or not image.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("PNG тайла повреждён или слишком велик")

    offset = 8
    image_data = bytearray()
    width = height = color_type = 0
    seen_header = seen_end = False
    while offset + 12 <= len(image):
        chunk_size = struct.unpack_from(">I", image, offset)[0]
        chunk_end = offset + 12 + chunk_size
        if chunk_end > len(image):
            raise ValueError("PNG тайла содержит неполный блок")
        chunk_type = image[offset + 4:offset + 8]
        chunk_data = image[offset + 8:offset + 8 + chunk_size]
        expected_crc = struct.unpack_from(">I", image, offset + 8 + chunk_size)[0]
        if zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF != expected_crc:
            raise ValueError("PNG тайла содержит неверную контрольную сумму")
        if chunk_type == b"IHDR":
            if seen_header or chunk_size != 13:
                raise ValueError("PNG тайла содержит неверный заголовок")
            width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", chunk_data
            )
            if (
                width != CUSTOM_TILE_SIZE or height != CUSTOM_TILE_SIZE
                or bit_depth != 8 or color_type not in (2, 6)
                or compression != 0 or filtering != 0 or interlace != 0
            ):
                raise ValueError("Каждый тайл группы должен быть PNG 16×16 с 8-битным цветом")
            seen_header = True
        elif chunk_type == b"IDAT":
            if not seen_header or seen_end:
                raise ValueError("PNG тайла содержит неверный порядок блоков")
            image_data.extend(chunk_data)
        elif chunk_type == b"IEND":
            if chunk_size != 0 or not seen_header:
                raise ValueError("PNG тайла содержит неверный конец")
            seen_end = True
            offset = chunk_end
            break
        elif chunk_type[0] & 0x20 == 0:
            raise ValueError("PNG тайла содержит неподдерживаемый блок")
        elif not seen_header or seen_end:
            raise ValueError("PNG тайла содержит неверный порядок блоков")
        offset = chunk_end
    if not seen_end or offset != len(image) or not image_data:
        raise ValueError("PNG тайла не завершён")

    expected_size = height * (1 + width * (4 if color_type == 6 else 3))
    decompressor = zlib.decompressobj()
    decoded = decompressor.decompress(bytes(image_data), expected_size + 1)
    if len(decoded) > expected_size or decompressor.unconsumed_tail:
        raise ValueError("Содержимое PNG тайла имеет неверный размер")
    decoded += decompressor.flush()
    if not decompressor.eof or len(decoded) != expected_size:
        raise ValueError("PNG тайла содержит неверные пиксельные данные")
    return image

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
            kwargs["options"] = f"-c search_path={schema},public"
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


# Правило только экономического сервера (Economy): монеты нового персонажа при создании.
# Другие режимы (Front Line и далее) этим значением не управляют: их стартовый кошелёк задаётся в своём коде.
STARTING_CHARACTER_COPPER = 1000


class Database:
    def __init__(self, dsn=None, *, schema=None, world_id=None, central=False):
        self.dsn = dsn or config.DATABASE_URL
        self.central = bool(central)
        self.schema = schema if schema is not None else (None if self.central else config.GAME_SCHEMA)
        if central and world_id is not None:
            raise ValueError("A central database connection cannot be bound to a gameplay world")
        configured_world = None if central else (config.WORLD_ID if world_id is None else world_id)
        self.world_id = None if configured_world is None else int(configured_world)
        self._entry = _shared_pool(self.dsn, self.schema)
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
            if self.world_id is not None and connection.execute(
                "SELECT 1 FROM worlds WHERE id = %s", (self.world_id,)
            ).fetchone() is None:
                raise RuntimeError(f"Мир WORLD_ID={self.world_id} не найден в таблице worlds")

    def _initialize_schema(self):
        with self.connection() as connection:
            apply_migrations(connection, schema=None if self.central else self.schema)
            self._initialize_map_catalog(connection)
            if not self.central:
                self._initialize_drinks(connection)
                self._normalize_character_stats(connection)

    @staticmethod
    def _initialize_map_catalog(connection):
        """Обновляет каталог тайлов и объектов редактора карт по файлам assets/map."""
        items = map_editor.catalog_definitions()
        for item in items:
            connection.execute(
                """INSERT INTO map_catalog
                   (item_key, kind, category, asset, footprint_w, footprint_h, blocks, sort_order, editor_layer)
                   VALUES (%(item_key)s, %(kind)s, %(category)s, %(asset)s,
                           %(footprint_w)s, %(footprint_h)s, %(blocks)s, %(sort_order)s, %(editor_layer)s)
                   ON CONFLICT (item_key) DO UPDATE SET
                       kind = EXCLUDED.kind, category = EXCLUDED.category, asset = EXCLUDED.asset,
                       footprint_w = EXCLUDED.footprint_w, footprint_h = EXCLUDED.footprint_h,
                       blocks = EXCLUDED.blocks, sort_order = EXCLUDED.sort_order,
                       editor_layer = EXCLUDED.editor_layer""",
                item,
            )
        connection.execute(
            """DELETE FROM map_catalog WHERE NOT (item_key = ANY(%s))
               AND item_key NOT IN (SELECT item_key FROM map_live_cells)""",
            ([item["item_key"] for item in items],),
        )

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
        return {
            "id": row["id"],
            "username": row["username"],
            "role": row["role"] if "role" in row.keys() else "user",
            "game_nickname": row["game_nickname"] if "game_nickname" in row.keys() else "",
        }

    def register(self, username, password):
        now = time.time()
        try:
            with self.connection() as connection:
                row = connection.execute(
                    """INSERT INTO users (username, password_hash, created_at)
                       VALUES (%s, %s, %s) RETURNING id, username, game_nickname""",
                    (username, self._password_hash(password), now),
                ).fetchone()
        except pg_errors.UniqueViolation as error:
            raise ValueError("Пользователь уже существует") from error
        return self._user_payload(row)

    def login(self, username, password):
        now = time.time()
        with self.connection() as connection:
            row = connection.execute(
                """SELECT id, username, password_hash, role, game_nickname
                   FROM users WHERE username = %s AND id <> %s""",
                (username, SYSTEM_USER_ID),
            ).fetchone()
            if row is None or not self._check_password(password, row["password_hash"]):
                raise ValueError("Неверное имя пользователя или пароль")
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

    def change_password(self, user_id, token, current_password, new_password):
        if not 6 <= len(new_password) <= 128:
            raise ValueError("Новый пароль должен содержать 6-128 символов")
        with self.connection() as connection:
            session = connection.execute(
                "SELECT 1 FROM sessions WHERE token = %s AND user_id = %s AND world_id IS NULL",
                (token, user_id),
            ).fetchone()
            if session is None:
                raise ValueError("Сессия аккаунта недействительна")
            row = connection.execute(
                "SELECT password_hash FROM users WHERE id = %s AND id <> %s",
                (user_id, SYSTEM_USER_ID),
            ).fetchone()
            if row is None or not self._check_password(current_password, row["password_hash"]):
                raise ValueError("Текущий пароль указан неверно")
            connection.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (self._password_hash(new_password), user_id),
            )
            connection.execute(
                "DELETE FROM sessions WHERE user_id = %s AND token <> %s",
                (user_id, token),
            )
            user = connection.execute(
                "SELECT id, username, role, game_nickname FROM users WHERE id = %s",
                (user_id,),
            ).fetchone()
        return self._user_payload(user)

    def change_game_nickname(self, user_id, token, game_nickname):
        if not self.central:
            raise RuntimeError("Game nicknames are changed only in the central database")
        nickname = str(game_nickname).strip()
        if not 2 <= len(nickname) <= 24 or any(ord(char) < 32 or ord(char) == 127 for char in nickname):
            raise ValueError("Игровой псевдоним должен содержать 2-24 символа")
        with self.connection() as connection:
            session = connection.execute(
                "SELECT 1 FROM sessions WHERE token = %s AND user_id = %s AND world_id IS NULL",
                (token, user_id),
            ).fetchone()
            if session is None:
                raise ValueError("Сессия аккаунта недействительна")
            user = connection.execute(
                """UPDATE users SET game_nickname = %s WHERE id = %s
                   RETURNING id, username, role, game_nickname""",
                (nickname, user_id),
            ).fetchone()
        if user is None:
            raise ValueError("Пользователь не найден")
        return self._user_payload(user)

    def connect_to_world(self, central_token, world_id):
        if not self.central:
            raise RuntimeError("Only the central server can create a world session")
        user_id = self.user_id_by_token(central_token)
        now = time.time()
        with self.connection() as connection:
            world = connection.execute(
                """SELECT id, code, name, status, mode, server_url, test_only, opens_at, closes_at
                   FROM worlds WHERE id = %s""",
                (int(world_id),),
            ).fetchone()
            if world is None or world["code"] == "lobby":
                raise ValueError("Игровой мир не найден")
            if not self._world_payload(world, now)["is_open"]:
                raise ValueError("Мир закрыт")
            if not world["server_url"]:
                raise ValueError("Сервер мира еще не запущен")
            if world["test_only"] and not self.is_moderator(user_id):
                raise ValueError("Этот мир пока тестовый: вход открыт модераторам и админам")
            token = secrets.token_urlsafe(32)
            connection.execute(
                """INSERT INTO sessions (token, user_id, world_id, created_at, last_seen_at)
                   VALUES (%s, %s, %s, %s, %s)""",
                (token, user_id, int(world_id), now, now),
            )
            account = connection.execute(
                "SELECT id, username, role, game_nickname FROM users WHERE id = %s", (user_id,)
            ).fetchone()
        return {"token": token, "user": self._user_payload(account)}

    def game_nicknames(self, user_ids):
        ids = sorted({int(user_id) for user_id in user_ids if int(user_id) > 0})
        if not ids:
            return {}
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT id, game_nickname FROM users WHERE id = ANY(%s)",
                (ids,),
            ).fetchall()
        return {int(row["id"]): row["game_nickname"] for row in rows}

    def user_id_by_token(self, token):
        if not token:
            raise ValueError("Требуется авторизация")
        now = time.time()
        with self.connection() as connection:
            row = connection.execute(
                "SELECT user_id FROM sessions WHERE token = %s AND world_id IS NOT DISTINCT FROM %s AND last_seen_at > %s",
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

    def list_worlds(self, now=None, viewer_id=None):
        """Все миры с вычисленным открыт/закрыт. Тестовые миры видят только модераторы и админы."""
        now = time.time() if now is None else float(now)
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT id, code, name, mode, status, opens_at, closes_at, server_url, test_only, started_at "
                "FROM worlds ORDER BY id"
            ).fetchall()
            online_rows = connection.execute(
                """SELECT world_id, COUNT(DISTINCT user_id) AS amount FROM sessions
                   WHERE world_id IS NOT NULL AND user_id <> %s AND last_seen_at > %s
                   GROUP BY world_id""",
                (SYSTEM_USER_ID, now - config.ONLINE_PLAYER_TTL_SECONDS),
            ).fetchall()
        online = {row["world_id"]: int(row["amount"]) for row in online_rows}
        if viewer_id is None or not self.is_moderator(viewer_id):
            rows = [row for row in rows if not row["test_only"]]
        return [self._world_list_payload(row, now, online.get(row["id"], 0)) for row in rows]

    def _world_list_payload(self, row, now, online_players):
        payload = self._world_payload(row, now)
        payload.update({
            "test_only": bool(row["test_only"]),
            "started_at": row["started_at"],
            "online_players": online_players,
        })
        return payload


    def _world_payload(self, row, now):
        is_open = (
            row["status"] == "open"
            and (row["opens_at"] is None or row["opens_at"] <= now)
            and (row["closes_at"] is None or row["closes_at"] > now)
        )
        return {
            "id": row["id"],
            "code": row["code"],
            "name": row["name"],
            "mode": row["mode"],
            "is_open": is_open,
            "opens_at": row["opens_at"],
            "closes_at": row["closes_at"],
            "server_url": row["server_url"],
        }

    def lobby_members(self, now=None):
        """Accounts with a recently active session in any world."""
        now = time.time() if now is None else float(now)
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT u.id AS user_id, u.username
                   FROM sessions s JOIN users u ON u.id = s.user_id
                   WHERE s.user_id <> %s AND s.last_seen_at > %s
                   GROUP BY u.id, u.username
                   ORDER BY u.username""",
                (SYSTEM_USER_ID, now - config.ONLINE_PLAYER_TTL_SECONDS),
            ).fetchall()
        return [{"user_id": row["user_id"], "username": row["username"]} for row in rows]

    def lobby_chat_history(self, limit=50, viewer_id=None):
        """Общие сообщения лобби и личные сообщения, в которых участвует viewer_id."""
        if not self.central:
            raise RuntimeError("Lobby chat is available only in the central database")
        limit = max(1, min(100, int(limit)))
        cutoff = time.time() - config.CHAT_HISTORY_TTL_SECONDS
        with self.connection() as connection:
            connection.execute(
                "DELETE FROM lobby_chat_messages WHERE created_at < %s",
                (cutoff,),
            )
            rows = connection.execute(
                """SELECT lobby_chat_messages.id, lobby_chat_messages.sender_user_id,
                          sender.username, lobby_chat_messages.recipient_user_id,
                          recipient.username AS recipient_username,
                          lobby_chat_messages.text, lobby_chat_messages.created_at
                   FROM lobby_chat_messages
                   JOIN users sender ON sender.id = lobby_chat_messages.sender_user_id
                   LEFT JOIN users recipient ON recipient.id = lobby_chat_messages.recipient_user_id
                   WHERE lobby_chat_messages.created_at >= %s
                     AND (lobby_chat_messages.recipient_user_id IS NULL
                          OR lobby_chat_messages.sender_user_id = %s
                          OR lobby_chat_messages.recipient_user_id = %s)
                   ORDER BY lobby_chat_messages.id DESC
                   LIMIT %s""",
                (cutoff, viewer_id, viewer_id, limit),
            ).fetchall()
        return [self._lobby_chat_payload(row) for row in reversed(rows)]

    def add_lobby_chat_message(self, user_id, text, recipient_user_id=None):
        if not self.central:
            raise RuntimeError("Lobby chat is available only in the central database")
        message = str(text or "").strip()
        if not message or len(message) > config.CHAT_MAX_LENGTH:
            raise ValueError(f"Сообщение должно содержать от 1 до {config.CHAT_MAX_LENGTH} символов")
        recipient = None
        if recipient_user_id not in (None, ""):
            try:
                recipient = int(recipient_user_id)
            except (TypeError, ValueError) as error:
                raise ValueError("Некорректный получатель личного сообщения") from error
            if recipient == user_id:
                raise ValueError("Нельзя отправить личное сообщение самому себе")
        now = time.time()
        cutoff = now - config.CHAT_HISTORY_TTL_SECONDS
        rate_cutoff = now - config.CHAT_RATE_LIMIT_WINDOW
        with self.connection() as connection:
            connection.execute(
                "DELETE FROM lobby_chat_messages WHERE created_at < %s",
                (cutoff,),
            )
            if recipient is not None and connection.execute(
                "SELECT id FROM users WHERE id = %s AND id <> %s", (recipient, SYSTEM_USER_ID)
            ).fetchone() is None:
                raise ValueError("Получатель личного сообщения не найден")
            recent = connection.execute(
                """SELECT COUNT(*) AS amount FROM lobby_chat_messages
                   WHERE sender_user_id = %s AND created_at >= %s""",
                (user_id, rate_cutoff),
            ).fetchone()["amount"]
            if recent >= config.CHAT_RATE_LIMIT_COUNT:
                raise ValueError("Слишком много сообщений. Попробуйте позже.")
            message_id = connection.execute(
                """INSERT INTO lobby_chat_messages (sender_user_id, recipient_user_id, text, created_at)
                   VALUES (%s, %s, %s, %s) RETURNING id""",
                (user_id, recipient, message, now),
            ).fetchone()["id"]
            row = connection.execute(
                """SELECT lobby_chat_messages.id, lobby_chat_messages.sender_user_id,
                          sender.username, lobby_chat_messages.recipient_user_id,
                          recipient.username AS recipient_username,
                          lobby_chat_messages.text, lobby_chat_messages.created_at
                   FROM lobby_chat_messages
                   JOIN users sender ON sender.id = lobby_chat_messages.sender_user_id
                   LEFT JOIN users recipient ON recipient.id = lobby_chat_messages.recipient_user_id
                   WHERE lobby_chat_messages.id = %s""",
                (message_id,),
            ).fetchone()
        return self._lobby_chat_payload(row)

    def save_avatar(self, user_id, png):
        if not self.central:
            raise RuntimeError("Account avatars are stored only in the central database")
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO user_avatars (user_id, png, updated_at) VALUES (%s, %s, %s)
                   ON CONFLICT (user_id) DO UPDATE SET png = EXCLUDED.png, updated_at = EXCLUDED.updated_at""",
                (user_id, bytes(png), time.time()),
            )

    def get_avatar(self, user_id):
        if not self.central:
            raise RuntimeError("Account avatars are stored only in the central database")
        with self.connection() as connection:
            row = connection.execute(
                "SELECT png FROM user_avatars WHERE user_id = %s", (user_id,)
            ).fetchone()
        return None if row is None else bytes(row["png"])

    @staticmethod
    def _lobby_chat_payload(row):
        return {
            "id": row["id"],

            "sender_user_id": row["sender_user_id"],
            "username": row["username"],
            "recipient_user_id": row["recipient_user_id"],
            "recipient_username": row["recipient_username"],
            "text": row["text"],
            "created_at": row["created_at"],
        }
    
    def get_user(self, user_id):
        """Get user by ID with password hash"""
        with self.connection() as connection:
            row = connection.execute(
                "SELECT id, username, password_hash FROM users WHERE id = %s",
                (user_id,),
            ).fetchone()
        return row

    def create_character(self, user_id, name, profession_type="warrior", allocation=None):
        self.validate_character_name(name)
        valid_professions = ["warrior", "archer", "assassin", "mage"]
        if profession_type not in valid_professions:
            raise ValueError(f"Профессия должна быть одной из: {', '.join(valid_professions)}")

        now = time.time()

        
        stats, stat_points = creation_stats(allocation)
        max_hp = calculate_max_hp(1, stats["endurance"])
        max_mp = calculate_max_mana(stats["intellect"])
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
                     json.dumps(stats), stat_points, STARTING_CHARACTER_COPPER, now),
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
        valid_professions = ["warrior", "archer", "assassin", "mage"]
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

    def apply_front_line_draft(self, user_id, character_id, profession_type, allocation):
        """Apply the Front Line class and starting-stat draft to a character in this world."""
        valid_professions = ("warrior", "archer", "assassin", "mage")
        if profession_type not in valid_professions:
            raise ValueError(f"Профессия должна быть одной из: {', '.join(valid_professions)}")
        stats, free_points = creation_stats(allocation)
        with self.connection() as connection:
            row = connection.execute(
                """SELECT level FROM characters
                   WHERE id = %s AND user_id = %s AND world_id = %s""",
                (int(character_id), int(user_id), self.world_id),
            ).fetchone()
            if row is None:
                raise ValueError("Персонаж не найден")
            level = int(row["level"])
            stats["endurance"] = max(stats["endurance"], minimum_endurance(level))
            max_hp = calculate_max_hp(level, stats["endurance"])
            max_mp = calculate_max_mana(stats["intellect"])
            connection.execute(
                """UPDATE characters
                   SET type = %s, stats_json = %s, stat_points = %s, hp = %s, max_hp = %s,
                       mp = %s, max_mp = %s, updated_at = %s
                   WHERE id = %s AND user_id = %s AND world_id = %s""",
                (
                    profession_type, json.dumps(stats), free_points, max_hp, max_hp, max_mp, max_mp,
                    time.time(), int(character_id), int(user_id), self.world_id,
                ),
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
                row = self._apply_passive_regen(original_row, now)
                bonuses = self.equipment_bonuses(connection, row["id"])
                character = self._character_payload(row, int(bonuses.get("hp", 0)))

                inventory_rows = self._inventory_rows_for_character(connection, row["id"])

                inventory = {}
                for idx, inv_row in enumerate(inventory_rows, 1):
                    inventory[str(idx)] = {
                        "name": inv_row["name"],
                        "quantity": inv_row["quantity"],
                        "effect": inv_row["effect"],
                    }
                character["inventory"] = inventory
                character["equipment_bonuses"] = bonuses
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

    def map_catalog(self):
        with self.connection() as connection:
            rows = connection.execute(
                """                SELECT item_key, kind, category, asset, footprint_w, footprint_h, blocks, sort_order,
                          editor_layer
                   FROM map_catalog ORDER BY sort_order, item_key"""
            ).fetchall()
            custom_rows = connection.execute(
                """
                SELECT asset.item_key, asset.group_id, asset.tile_x, asset.tile_y,
                       tile_group.name AS group_name, tile_group.category, tile_group.tile_rows
                FROM map_custom_tile_assets AS asset
                JOIN map_custom_tile_groups AS tile_group USING (group_id)
                ORDER BY tile_group.created_at, asset.tile_y, asset.tile_x
                """
            ).fetchall()
        catalog = [dict(row) for row in rows]
        catalog.extend({
            "item_key": row["item_key"],
            "kind": "ground",
            "category": row["category"],
            "asset": f"custom_tiles/{row['item_key']}.png",
            "footprint_w": 1,
            "footprint_h": 1,
            "blocks": False,
            "sort_order": 100_000,
            "editor_layer": 1,
            "tile_group_id": row["group_id"],
            "tile_x": int(row["tile_x"]),
            "tile_y": int(row["tile_y"]),
            "tile_rows": int(row["tile_rows"]),
            "tile_group_name": row["group_name"],
        } for row in custom_rows)
        overrides = self.map_palette_state()["overrides"]
        by_key = {item["item_key"]: item for item in catalog}
        for key, values in overrides.items():
            item = by_key.get(key)
            if item is not None:
                item.update(values)
        return catalog

    def custom_tile_groups(self):
        with self.connection() as connection:
            groups = connection.execute(
                """
                SELECT group_id, name, category, tile_rows
                FROM map_custom_tile_groups
                ORDER BY created_at, group_id
                """
            ).fetchall()
            tile_rows = connection.execute(
                """
                SELECT group_id, tile_x, tile_y, item_key
                FROM map_custom_tile_assets
                ORDER BY group_id, tile_y, tile_x
                """
            ).fetchall()
        tiles_by_group = {}
        for tile in tile_rows:
            tiles_by_group.setdefault(tile["group_id"], []).append(tile)
        result = []
        for group in groups:
            rows = int(group["tile_rows"])
            tile_keys = [["" for _ in range(3)] for _ in range(rows)]
            for tile in tiles_by_group.get(group["group_id"], []):
                tile_keys[int(tile["tile_y"])][int(tile["tile_x"])] = tile["item_key"]
            result.append({
                "group_id": group["group_id"],
                "name": group["name"],
                "category": group["category"],
                "tile_rows": rows,
                "tile_keys": tile_keys,
            })
        return result

    def map_asset(self, item_key):
        with self.connection() as connection:
            row = connection.execute(
                "SELECT png_bytes FROM map_custom_tile_assets WHERE item_key = %s",
                (str(item_key),),
            ).fetchone()
        if row is not None:
            return bytes(row["png_bytes"])
        return read_catalog_asset(self.map_catalog(), item_key)

    def save_custom_tile_group(self, user_id, payload):
        if not self.is_moderator(user_id):
            raise ValueError("Недостаточно прав модератора для публикации группы тайлов")
        if not isinstance(payload, dict):
            raise ValueError("Данные группы тайлов должны быть объектом")
        name = str(payload.get("name", "")).strip()
        category = str(payload.get("category", ""))
        rows = payload.get("tile_rows")
        tiles = payload.get("tiles")
        if not name or len(name) > 48:
            raise ValueError("Название группы должно содержать от 1 до 48 символов")
        if category not in CUSTOM_TILE_CATEGORIES:
            raise ValueError("Выберите допустимую категорию поверхности")
        if not isinstance(rows, int) or isinstance(rows, bool) or rows not in (3, 4, 5):
            raise ValueError("Группа должна иметь формат 3×3, 3×4 или 3×5")
        if not isinstance(tiles, list) or len(tiles) != 3 * rows:
            raise ValueError("Для публикации нужны все тайлы выбранной группы")

        decoded_tiles = {}
        for tile in tiles:
            if not isinstance(tile, dict):
                raise ValueError("Данные каждого тайла должны быть объектом")
            tile_x, tile_y = tile.get("x"), tile.get("y")
            if (
                not isinstance(tile_x, int) or isinstance(tile_x, bool)
                or not isinstance(tile_y, int) or isinstance(tile_y, bool)
                or not 0 <= tile_x < 3 or not 0 <= tile_y < rows
            ):
                raise ValueError("Координата тайла выходит за пределы группы")
            tile_position = (tile_x, tile_y)
            if tile_position in decoded_tiles:
                raise ValueError("Группа содержит повторяющиеся координаты тайлов")
            decoded_tiles[tile_position] = _decode_custom_tile_png(tile.get("png"))
        if sum(len(image) for image in decoded_tiles.values()) > CUSTOM_TILE_GROUP_MAX_BYTES:
            raise ValueError("Суммарный размер группы тайлов слишком велик")

        group_id = uuid.uuid4().hex
        item_rows = []
        for tile_y in range(rows):
            for tile_x in range(3):
                item_rows.append((
                    f"custom_tile_{group_id}_{tile_x}_{tile_y}",
                    tile_x,
                    tile_y,
                    decoded_tiles[(tile_x, tile_y)],
                ))
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO map_custom_tile_groups
                    (group_id, name, category, tile_rows, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (group_id, name, category, rows, int(user_id), time.time()),
            )
            for item_key, tile_x, tile_y, png_bytes in item_rows:
                connection.execute(
                    """
                    INSERT INTO map_custom_tile_assets
                        (item_key, group_id, tile_x, tile_y, png_bytes)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (item_key, group_id, tile_x, tile_y, png_bytes),
                )
        return {
            "group": {
                "group_id": group_id,
                "name": name,
                "category": category,
                "tile_rows": rows,
                "tile_keys": [
                    [f"custom_tile_{group_id}_{x}_{y}" for x in range(3)]
                    for y in range(rows)
                ],
            },
            "items": [
                {
                    "item_key": item_key,
                    "kind": "ground",
                    "category": category,
                    "asset": f"custom_tiles/{item_key}.png",
                    "footprint_w": 1,
                    "footprint_h": 1,
                    "blocks": False,
                    "sort_order": 100_000,
                    "editor_layer": 1,
                    "tile_group_id": group_id,
                    "tile_x": tile_x,
                    "tile_y": tile_y,
                    "tile_rows": rows,
                    "tile_group_name": name,
                }
                for item_key, tile_x, tile_y, _png_bytes in item_rows
            ],
        }

    def map_palette_state(self):
        with self.connection() as connection:
            row = connection.execute(
                "SELECT version, overrides_json FROM map_palette_settings WHERE singleton = TRUE"
            ).fetchone()
        if row is None:
            raise RuntimeError("Настройки палитры не инициализированы")
        return {
            "version": int(row["version"]),
            "overrides": json.loads(row["overrides_json"]),
        }

    def _verify_palette_publisher(self, user_id, username, password):
        if not self.is_moderator(user_id):
            raise ValueError("Недостаточно прав модератора для изменения общей палитры")
        with self.connection() as connection:
            row = connection.execute(
                "SELECT id, password_hash FROM users WHERE username = %s",
                (str(username).strip(),),
            ).fetchone()
        if row is None or row["id"] != user_id or not self._check_password(str(password), row["password_hash"]):
            raise ValueError("Неверный логин или пароль для подтверждения палитры")

    def preview_map_palette(self, user_id, username, password, overrides):
        self._verify_palette_publisher(user_id, username, password)
        catalog = self.map_catalog()
        normalized = map_palette.validate_overrides(overrides, catalog)
        current = self.map_palette_state()
        conflicts = []
        with self.connection() as connection:
            saved_maps = connection.execute(
                "SELECT id, name, cells_json FROM map_saved ORDER BY id"
            ).fetchall()
            for saved in saved_maps:
                cells = json.loads(saved["cells_json"])
                _remapped, found, _removed = map_palette.remap_cells(
                    cells, catalog, current["overrides"], normalized, context=f"saved:{saved['id']}",
                )
                for conflict in found:
                    conflict["map_name"] = saved["name"]
                conflicts.extend(found)
            live = connection.execute(
                """SELECT c.world_id, w.name, c.layer, c.x, c.y, c.item_key AS key
                   FROM map_live_cells c JOIN worlds w ON w.id = c.world_id
                   ORDER BY c.world_id, c.layer, c.y, c.x"""
            ).fetchall()
        by_world = {}
        world_names = {}
        for row in live:
            world_id = int(row["world_id"])
            by_world.setdefault(world_id, []).append({
                "layer": row["layer"], "x": row["x"], "y": row["y"], "key": row["key"],
            })
            world_names[world_id] = row["name"]
        for world_id, cells in by_world.items():
            _remapped, found, _removed = map_palette.remap_cells(
                cells, catalog, current["overrides"], normalized, context=f"world:{world_id}",
            )
            for conflict in found:
                conflict["map_name"] = world_names[world_id]
            conflicts.extend(found)
        return {
            "version": current["version"],
            "conflicts": conflicts,
            "affected_saved_maps": len(saved_maps),
            "affected_worlds": len(by_world),
        }

    def apply_map_palette(self, user_id, username, password, overrides, expected_version, resolutions):
        self._verify_palette_publisher(user_id, username, password)
        catalog = self.map_catalog()
        normalized = map_palette.validate_overrides(overrides, catalog)
        if not isinstance(resolutions, dict):
            raise ValueError("Решения конфликтов должны быть объектом")
        world_ids = []
        updated_saved = 0
        removed_cells = []
        world_names = {}
        with self.connection() as connection:
            state = connection.execute(
                "SELECT version, overrides_json FROM map_palette_settings WHERE singleton = TRUE FOR UPDATE"
            ).fetchone()
            if int(state["version"]) != int(expected_version):
                raise ValueError("Палитра уже изменена другим пользователем; обновите настройки и повторите")
            current_overrides = json.loads(state["overrides_json"])
            saved_maps = connection.execute(
                "SELECT id, name, map_w, map_h, cells_json FROM map_saved ORDER BY id FOR UPDATE"
            ).fetchall()
            live_catalog = [
                {**item, **normalized.get(item["item_key"], {})}
                for item in catalog
            ]
            saved_updates = []
            conflicts = []
            for saved in saved_maps:
                cells = json.loads(saved["cells_json"])
                remapped, found, removed = map_palette.remap_cells(
                    cells, catalog, current_overrides, normalized, resolutions,
                    context=f"saved:{saved['id']}",
                )
                conflicts.extend(found)
                for cell in removed:
                    cell["map_name"] = saved["name"]
                removed_cells.extend(removed)
                saved_updates.append((saved, cells, remapped))
            live_rows = connection.execute(
                """SELECT c.world_id, w.name AS map_name, c.layer, c.x, c.y, c.item_key AS key
                   FROM map_live_cells c JOIN worlds w ON w.id = c.world_id
                   ORDER BY c.world_id, c.layer, c.y, c.x FOR UPDATE"""
            ).fetchall()
            live_by_world = {}
            for row in live_rows:
                world_id = int(row["world_id"])
                live_by_world.setdefault(world_id, []).append({
                    "layer": row["layer"], "x": row["x"], "y": row["y"], "key": row["key"],
                })
                world_names[world_id] = row["map_name"]
            live_updates = {}
            for world_id, cells in live_by_world.items():
                remapped, found, removed = map_palette.remap_cells(
                    cells, catalog, current_overrides, normalized, resolutions,
                    context=f"world:{world_id}",
                )
                conflicts.extend(found)
                for cell in removed:
                    cell["map_name"] = world_names[world_id]
                removed_cells.extend(removed)
                live_updates[world_id] = remapped
            if conflicts:
                return {"applied": False, "conflicts": conflicts}
            for saved, original_cells, cells in saved_updates:
                if not map_palette.same_cells(original_cells, cells):
                    map_editor.validate_cells(
                        cells,
                        live_catalog,
                        saved["map_w"],
                        saved["map_h"],
                    )
            for saved, _original_cells, cells in saved_updates:
                connection.execute(
                    "UPDATE map_saved SET cells_json = %s, updated_at = %s WHERE id = %s",
                    (json.dumps(cells, ensure_ascii=False), time.time(), saved["id"]),
                )
                updated_saved += 1
            for world_id, cells in live_updates.items():
                published = connection.execute(
                    "SELECT map_w, map_h FROM map_world_publish WHERE world_id = %s",
                    (world_id,),
                ).fetchone()
                if published is None:
                    raise ValueError(f"У мира {world_id} отсутствуют данные опубликованной карты")
                original_cells = live_by_world[world_id]
                if not map_palette.same_cells(original_cells, cells):
                    map_editor.validate_cells(
                        cells,
                        live_catalog,
                        published["map_w"],
                        published["map_h"],
                    )
                connection.execute("DELETE FROM map_live_cells WHERE world_id = %s", (world_id,))
                for cell in cells:
                    connection.execute(
                        """INSERT INTO map_live_cells (world_id, layer, x, y, item_key)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (world_id, cell["layer"], cell["x"], cell["y"], cell["key"]),
                    )
                world_ids.append(world_id)
                connection.execute(
                    "UPDATE map_world_publish SET published_at = %s WHERE world_id = %s",
                    (time.time(), world_id),
                )
            connection.execute(
                """UPDATE map_palette_settings
                   SET version = version + 1, overrides_json = %s
                   WHERE singleton = TRUE""",
                (json.dumps(normalized, ensure_ascii=False),),
            )
        return {
            "applied": True,
            "version": int(expected_version) + 1,
            "updated_saved_maps": updated_saved,
            "updated_world_ids": world_ids,
            "removed_cells": removed_cells,
        }

    def material_item_ids(self, mode=None):
        """Id материалов каталога предметов: допустимый лут кристаллов."""
        if self.central:
            if mode is None:
                raise ValueError("Для центральной базы нужно указать режим карты")
            schema_mode = "deck" if mode == "deck" else mode
            if schema_mode == "deck":
                raise ValueError("Карты Deck обрабатываются отдельным сервером режима")
            schema = get_mode(schema_mode)["schema"]
            if schema is None:
                return set()
            query = f'SELECT id FROM "{schema}".items_catalog WHERE item_type = %s'
        else:
            query = "SELECT id FROM items_catalog WHERE item_type = %s"
        with self.connection() as connection:
            rows = connection.execute(query, ("material",)).fetchall()
        return {int(row["id"]) for row in rows}

    def load_world_crystal_states(self, published_at):
        """Состояние кристаллов мира для публикации published_at; записи старых публикаций удаляются.

        Возвращает {(x, y): {color, stage, elapsed, harvested}}.
        """
        with self.connection() as connection:
            connection.execute(
                "DELETE FROM world_crystal_state WHERE world_id = %s AND published_at <> %s",
                (self.world_id, published_at),
            )
            rows = connection.execute(
                """SELECT tile_x, tile_y, color, stage, elapsed, harvested FROM world_crystal_state
                   WHERE world_id = %s AND published_at = %s""",
                (self.world_id, published_at),
            ).fetchall()
        return {
            (int(row["tile_x"]), int(row["tile_y"])): {
                "color": row["color"],
                "stage": int(row["stage"]),
                "elapsed": float(row["elapsed"]),
                "harvested": bool(row["harvested"]),
            }
            for row in rows
        }

    def save_world_crystal_state(self, published_at, tile, color, stage, elapsed):
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO world_crystal_state (world_id, tile_x, tile_y, published_at, color, stage, elapsed)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (world_id, tile_x, tile_y) DO UPDATE SET
                       published_at = EXCLUDED.published_at, color = EXCLUDED.color,
                       stage = EXCLUDED.stage, elapsed = EXCLUDED.elapsed""",
                (self.world_id, int(tile[0]), int(tile[1]), published_at, color, int(stage), float(elapsed)),
            )

    def mark_world_crystal_harvested(self, published_at, tile):
        with self.connection() as connection:
            connection.execute(
                """UPDATE world_crystal_state SET harvested = TRUE
                   WHERE world_id = %s AND tile_x = %s AND tile_y = %s AND published_at = %s""",
                (self.world_id, int(tile[0]), int(tile[1]), published_at),
            )

    def map_live_mobs(self):
        """NPC опубликованной карты текущего мира; пустой список, если карта без NPC или не публиковалась."""
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT kind, x, y FROM map_live_mobs WHERE world_id = %s ORDER BY y, x""",
                (self.world_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def world_mode(self):
        """Режим текущего мира (worlds.mode): по нему берутся настройки мобов."""
        with self.connection() as connection:
            row = connection.execute("SELECT mode FROM worlds WHERE id = %s", (self.world_id,)).fetchone()
        return row["mode"] if row is not None else "front_line"

    def map_live_spawns(self):
        """Точки спауна опубликованной карты текущего мира: [(x, y)] в клетках."""
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT x, y FROM map_live_spawns WHERE world_id = %s ORDER BY y, x", (self.world_id,)
            ).fetchall()
        return [(row["x"], row["y"]) for row in rows]

    def map_live_cells(self):
        """Опубликованная карта текущего мира, которую читает игра; пустой список, если карта не публиковалась."""
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT layer, x, y, item_key AS key FROM map_live_cells
                   WHERE world_id = %s ORDER BY layer, y, x""",
                (self.world_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_saved_map(self, saved_id, name, mode, map_w, map_h, cells, mobs, moderator_id, spawns=None,
                       crystals=None, harvest_enabled=False, editor_layers=None):
        """Сохраняет карту на сервере как заготовку для мира: мир не создаётся и сервер не запускается."""
        if not self.is_moderator(moderator_id):
            raise ValueError("Недостаточно прав модератора")
        name = str(name or "").strip()
        if not 1 <= len(name) <= 64:
            raise ValueError("Название карты: от 1 до 64 символов")
        if not is_mode(mode):
            raise ValueError("Неизвестный режим игры")
        map_editor.check_map_size(map_w, map_h)
        catalog = self.map_catalog()
        cell_rows = map_editor.validate_cells(cells, catalog, map_w, map_h)
        mob_rows = map_editor.validate_mobs(mobs, map_w, map_h)
        spawn_rows = map_editor.validate_spawns(
            spawns, map_w, map_h, include_settings=True, mode=mode,
        )
        crystal_settings = map_editor.validate_crystals(crystals, catalog, self.material_item_ids(mode))
        cells_json = json.dumps([{"layer": l, "x": x, "y": y, "key": k} for l, x, y, k in cell_rows], ensure_ascii=False)
        mobs_json = json.dumps([{"kind": k, "x": x, "y": y} for k, x, y in mob_rows], ensure_ascii=False)
        spawns_json = json.dumps(spawn_rows, ensure_ascii=False, allow_nan=False)
        crystals_json = json.dumps(crystal_settings, ensure_ascii=False)
        editor_layers_json = json.dumps(editor_layers or [], ensure_ascii=False, allow_nan=False)
        harvest = bool(harvest_enabled)
        now = time.time()
        with self.connection() as connection:
            if saved_id:
                row = connection.execute(
                    """UPDATE map_saved SET name = %s, mode = %s, map_w = %s, map_h = %s,
                       cells_json = %s, mobs_json = %s, spawns_json = %s, crystal_settings_json = %s,
                       editor_layers_json = %s, harvest_enabled = %s, updated_at = %s
                       WHERE id = %s RETURNING id""",
                    (
                        name, mode, map_w, map_h, cells_json, mobs_json, spawns_json,
                        crystals_json, editor_layers_json, harvest, now, saved_id,
                    ),
                ).fetchone()
                if row is None:
                    raise ValueError("Карта на сервере не найдена")
                return row["id"]
            row = connection.execute(
                """INSERT INTO map_saved (name, mode, map_w, map_h, cells_json, mobs_json, spawns_json,
                   crystal_settings_json, editor_layers_json, harvest_enabled, created_by, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (
                    name, mode, map_w, map_h, cells_json, mobs_json, spawns_json,
                    crystals_json, editor_layers_json, harvest, moderator_id, now, now,
                ),
            ).fetchone()
        return row["id"]

    def get_saved_map(self, saved_id):
        with self.connection() as connection:
            row = connection.execute(
                """SELECT id, name, mode, map_w, map_h, cells_json, mobs_json, spawns_json,
                   crystal_settings_json, editor_layers_json, harvest_enabled
                   FROM map_saved WHERE id = %s""",
                (saved_id,),
            ).fetchone()
        if row is None:
            raise ValueError("Карта на сервере не найдена")
        data = dict(row)
        data["cells"] = json.loads(data.pop("cells_json"))
        data["mobs"] = json.loads(data.pop("mobs_json"))
        data["spawns"] = json.loads(data.pop("spawns_json"))
        data["crystals"] = json.loads(data.pop("crystal_settings_json"))
        data["editor_layers"] = json.loads(data.pop("editor_layers_json"))
        data["harvest_enabled"] = bool(data["harvest_enabled"])
        return data

    def create_map_world(self, name, mode, moderator_id, test_only=False):
        """Create a world with a code namespace accepted by its mode runtime."""
        if not self.is_moderator(moderator_id):
            raise ValueError("Недостаточно прав модератора")
        if not test_only and not self.is_admin(moderator_id):
            raise ValueError("Публичный мир создаёт только админ")
        if not is_mode(mode):
            raise ValueError("Неизвестный режим игры")
        with self.connection() as connection:
            next_id = connection.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM worlds").fetchone()["next_id"]
            code = f"deck_map{next_id}" if mode == "deck" else f"map{next_id}"
            connection.execute(
                """INSERT INTO worlds (id, code, name, status, created_at, mode, test_only)
                   VALUES (%s, %s, %s, 'open', %s, %s, %s)""",
                (next_id, code, name, time.time(), mode, bool(test_only)),
            )
        return {"id": next_id, "code": code, "name": name, "mode": mode}

    def ensure_front_line_world(self):
        """Return the single persistent public world used by automatic Front Line matchmaking."""
        with self.connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(%s)", (7_421_000_02,))
            row = connection.execute(
                "SELECT id, code, name, status, mode, server_url, test_only "
                "FROM worlds WHERE code = %s",
                ("front_line_matchmaking",),
            ).fetchone()
            if row is None:
                world_id = connection.execute(
                    "SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM worlds"
                ).fetchone()["next_id"]
                row = connection.execute(
                    """INSERT INTO worlds (id, code, name, status, created_at, mode, test_only)
                       VALUES (%s, %s, %s, 'open', %s, 'front_line', FALSE)
                       RETURNING id, code, name, status, mode, server_url, test_only""",
                    (world_id, "front_line_matchmaking", "Front Line", time.time()),
                ).fetchone()
        return dict(row)

    def is_admin(self, user_id):
        with self.connection() as connection:
            row = connection.execute("SELECT role FROM users WHERE id = %s", (user_id,)).fetchone()
        return row is not None and row["role"] == "admin"

    def can_enter_current_world(self, user_id):
        """Тестовый мир текущего сервера открыт только модераторам и админам."""
        with self.connection() as connection:
            row = connection.execute("SELECT test_only FROM worlds WHERE id = %s", (self.world_id,)).fetchone()
        if row is None or not row["test_only"]:
            return True
        return self.is_moderator(user_id)

    def user_role(self, user_id):
        with self.connection() as connection:
            row = connection.execute(
                "SELECT id, username, role, game_nickname FROM users WHERE id = %s", (user_id,)
            ).fetchone()
        return None if row is None else dict(row)

    def list_saved_maps(self, mode=None):
        """Сохранённые карты, новые сверху; mode — только карты этого режима."""
        with self.connection() as connection:
            if mode:
                rows = connection.execute(
                    "SELECT id, name, mode, map_w, map_h, updated_at FROM map_saved WHERE mode = %s ORDER BY updated_at DESC",
                    (mode,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT id, name, mode, map_w, map_h, updated_at FROM map_saved ORDER BY updated_at DESC"
                ).fetchall()
        return [dict(row) for row in rows]

    def first_saved_map(self, mode):
        """Load the earliest saved map in a mode until explicit map ordering is available."""
        with self.connection() as connection:
            row = connection.execute(
                """SELECT id, name, mode, map_w, map_h, cells_json, mobs_json, spawns_json,
                          crystal_settings_json, editor_layers_json, harvest_enabled
                   FROM map_saved WHERE mode = %s ORDER BY id ASC LIMIT 1""",
                (mode,),
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        for field in ("cells", "mobs", "spawns", "crystals", "editor_layers"):
            json_field = "crystal_settings_json" if field == "crystals" else f"{field}_json"
            data[field] = json.loads(data.pop(json_field))
        data["harvest_enabled"] = bool(data["harvest_enabled"])
        return data

    def update_map_world(self, world_id, name, mode, moderator_id):
        """Обновляет название и режим мира карты; обычные миры этим не меняются."""
        if not self.is_moderator(moderator_id):
            raise ValueError("Недостаточно прав модератора")
        if not self.world_info(world_id)["code"].startswith("map"):
            raise ValueError("Этот мир создан не из карты редактора")
        with self.connection() as connection:
            connection.execute("UPDATE worlds SET name = %s, mode = %s WHERE id = %s", (name, mode, world_id))

    def world_info(self, world_id):
        with self.connection() as connection:
            row = connection.execute(
                "SELECT id, code, name, status, mode, server_url, test_only FROM worlds WHERE id = %s", (world_id,)
            ).fetchone()
        if row is None:
            raise ValueError("Мир не найден")
        return dict(row)

    def set_world_server(self, world_id, server_url):
        started_at = time.time() if server_url else None
        with self.connection() as connection:
            connection.execute(
                "UPDATE worlds SET server_url = %s, started_at = %s WHERE id = %s",
                (server_url, started_at, world_id),
            )

    def delete_map_world(self, world_id):
        """Удаляет только миры карт: откат, если карта не прошла проверку."""
        with self.connection() as connection:
            connection.execute("DELETE FROM worlds WHERE id = %s AND code LIKE 'map%%'", (world_id,))

    def used_ports(self):
        """Порты, которые уже заняты мирами по server_url."""
        with self.connection() as connection:
            rows = connection.execute("SELECT server_url FROM worlds WHERE server_url IS NOT NULL").fetchall()
        return {urlparse(row["server_url"]).port for row in rows if urlparse(row["server_url"]).port}

    def published_map(self):
        """Сведения о карте, опубликованной в текущий мир; None, если мир играет процедурным рельефом."""
        with self.connection() as connection:
            row = connection.execute(
                """SELECT name, map_w, map_h, published_at, mode, crystal_settings_json, harvest_enabled, saved_id
                   FROM map_world_publish WHERE world_id = %s""",
                (self.world_id,),
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["crystals"] = json.loads(data.pop("crystal_settings_json"))
        data["harvest_enabled"] = bool(data["harvest_enabled"])
        return data

    def linked_world_ids(self, saved_id):
        """Миры, в которых сейчас опубликована заготовка saved_id (их обновляют при сохранении заготовки)."""
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT world_id FROM map_world_publish WHERE saved_id = %s ORDER BY world_id", (saved_id,)
            ).fetchall()
        return [row["world_id"] for row in rows]

    def publish_map(self, cells, world_id, name, map_w, map_h, moderator_id, mobs=None, mode="front_line", spawns=None,
                    saved_id=None, crystals=None, harvest_enabled=False):
        """Размещает карту редактора в мире world_id: клетки, NPC и режим. Заменяет живую карту этого мира."""
        if not self.is_moderator(moderator_id):
            raise ValueError("Недостаточно прав модератора")
        name = str(name or "").strip()
        if not 1 <= len(name) <= 64:
            raise ValueError("Название карты: от 1 до 64 символов")
        map_editor.check_map_size(map_w, map_h)
        catalog = self.map_catalog()
        rows = map_editor.validate_cells(cells, catalog, map_w, map_h)
        if not rows:
            raise ValueError("Карта пустая, нечего размещать")
        mob_rows = map_editor.validate_mobs(mobs, map_w, map_h)
        spawn_rows = map_editor.validate_spawns(
            spawns, map_w, map_h, include_settings=mode == "front_line", mode=mode,
        )
        if not is_mode(mode):
            raise ValueError("Неизвестный режим игры")
        crystal_settings = map_editor.validate_crystals(crystals, catalog, self.material_item_ids(mode))
        harvest = bool(harvest_enabled)
        published_at = time.time()
        with self.connection() as connection:
            target = connection.execute("SELECT id, name FROM worlds WHERE id = %s", (world_id,)).fetchone()
            if target is None:
                raise ValueError("Мир не найден")
            connection.execute("DELETE FROM map_live_cells WHERE world_id = %s", (target["id"],))
            for layer, x, y, key in rows:
                connection.execute(
                    """INSERT INTO map_live_cells (world_id, layer, x, y, item_key)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (target["id"], layer, x, y, key),
                )
            connection.execute("DELETE FROM map_live_spawns WHERE world_id = %s", (target["id"],))
            for spawn in spawn_rows:
                if spawn.get("type") == "mob":
                    continue
                connection.execute(
                    """INSERT INTO map_live_spawns (world_id, x, y) VALUES (%s, %s, %s)""",
                    (target["id"], spawn["x"], spawn["y"]),
                )
            connection.execute("DELETE FROM map_live_mobs WHERE world_id = %s", (target["id"],))
            for kind, x, y in mob_rows:
                connection.execute(
                    """INSERT INTO map_live_mobs (world_id, kind, x, y) VALUES (%s, %s, %s, %s)""",
                    (target["id"], kind, x, y),
                )
            connection.execute(
                """INSERT INTO map_world_publish (world_id, name, map_w, map_h, published_at, mode, saved_id,
                   crystal_settings_json, harvest_enabled)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (world_id) DO UPDATE SET
                       name = EXCLUDED.name, map_w = EXCLUDED.map_w,
                       map_h = EXCLUDED.map_h, published_at = EXCLUDED.published_at,
                       mode = EXCLUDED.mode, saved_id = EXCLUDED.saved_id""",
                (target["id"], name, map_w, map_h, published_at, mode, saved_id,
                 json.dumps(crystal_settings, ensure_ascii=False), harvest),
            )
        return {
            "world_id": target["id"],
            "world_name": target["name"],
            "name": name,
            "map_w": map_w,
            "map_h": map_h,
            "applied": len(rows),
            "mobs": len(mob_rows),
            "mode": mode,
            "published_at": published_at,
        }

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

    def character_belongs_to_user(self, user_id, character_id):
        with self.connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM characters WHERE id = %s AND user_id = %s AND world_id = %s",
                (character_id, user_id, self.world_id),
            ).fetchone()
        return row is not None

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
            row = self._apply_passive_regen(row, now)
            bonuses = self.equipment_bonuses(connection, row["id"])
            character = self._character_payload(row, int(bonuses.get("hp", 0)))

            inventory_rows = self._inventory_rows_for_character(connection, row["id"])

            inventory = {}
            for idx, inv_row in enumerate(inventory_rows, 1):
                inventory[str(idx)] = {
                    "name": inv_row["name"],
                    "quantity": inv_row["quantity"],
                    "effect": inv_row["effect"],
                }
            character["inventory"] = inventory
            character["equipment_bonuses"] = bonuses
            character["equipment"] = self.equipped_items(connection, row["id"])
            self._update_carry_capacity(character)

            return character

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
    def _apply_passive_regen(row, now):
        # Регенерация считается от сохранённой контрольной точки (hp, mp, updated_at).
        # В БД она попадает при живой регенерации сервера мира или при сохранении персонажа.
        hp, max_hp = int(row["hp"]), int(row["max_hp"])
        mp, max_mp = int(row["mp"]), int(row["max_mp"])
        if hp >= max_hp and mp >= max_mp:
            return row
        full_seconds = config.passive_regen_full_seconds(row["zone"])
        elapsed = max(0.0, now - float(row["updated_at"]))
        updated = dict(row)
        updated["hp"] = min(max_hp, hp + int(elapsed * max_hp / full_seconds))
        updated["mp"] = min(max_mp, mp + int(elapsed * max_mp / full_seconds))
        return updated

    def save_character(self, user_id, character_id, payload):
        with self.connection() as connection:
            current, equipment_hp = self._load_character_for_save(connection, user_id, character_id)
        
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
            "endurance": max(minimum_endurance(level), int(raw_stats.get("endurance", minimum_endurance(level)))),
        }
        updated["max_hp"] = calculate_max_hp(level, updated["stats"]["endurance"]) + equipment_hp
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

    def save_world_vitals(self, user_id, character_id, hp, mp):
        """HP/MP живого мира. Пишутся вместе с меткой времени: от неё считается регенерация при чтении."""
        character = self.get_character(user_id, character_id)
        if character is None:
            raise ValueError("Персонаж не найден")
        hp = max(0, min(int(hp), int(character["max_hp"])))
        mp = max(0, min(int(mp), int(character["max_mp"])))
        with self.connection() as connection:
            connection.execute(
                """UPDATE characters SET hp = %s, mp = %s, updated_at = %s
                   WHERE id = %s AND user_id = %s AND world_id = %s""",
                (hp, mp, time.time(), character_id, user_id, self.world_id),
            )
        return {"hp": hp, "mp": mp, "max_hp": character["max_hp"], "max_mp": character["max_mp"]}

    def rest_character(self, user_id, character_id):
        character = self.get_character(user_id, character_id)
        if character is None:
            raise ValueError("Персонаж не найден")
        return self.save_world_vitals(user_id, character_id, character["max_hp"], character["max_mp"])

    def add_world_currency(self, user_id, character_id, copper):
        """Начисляет медь (награда за моба). updated_at не трогает: это метка регенерации HP/MP."""
        with self.connection() as connection:
            row = connection.execute(
                """SELECT copper, silver, gold FROM characters
                   WHERE id = %s AND user_id = %s AND world_id = %s FOR UPDATE""",
                (character_id, user_id, self.world_id),
            ).fetchone()
            if row is None:
                raise ValueError("Персонаж не найден")
            currency = Currency(
                copper=int(row["copper"] or 0),
                silver=int(row["silver"] or 0),
                gold=int(row["gold"] or 0),
            )
            currency.add_copper_amount(copper)
            connection.execute(
                """UPDATE characters SET copper = %s, silver = %s, gold = %s
                   WHERE id = %s AND user_id = %s AND world_id = %s""",
                (currency.copper, currency.silver, currency.gold,
                 character_id, user_id, self.world_id),
            )
        return currency.to_dict()

    def set_world_currency(self, user_id, character_id, copper, silver, gold):
        """Устанавливает кошелёк персонажа (стартовый кошелёк Front Line на входе и на выходе из игры)."""
        with self.connection() as connection:
            self._store_character_currency(
                connection, user_id, character_id, Currency(copper=int(copper), silver=int(silver), gold=int(gold)))

    def save_world_progression(self, user_id, character_id, level, xp, stats, stat_points, max_hp):
        """Уровень, опыт и характеристики после награды за моба. updated_at не трогает: это метка регенерации."""
        with self.connection() as connection:
            connection.execute(
                """UPDATE characters SET level = %s, xp = %s, stats_json = %s, stat_points = %s, max_hp = %s
                   WHERE id = %s AND user_id = %s AND world_id = %s""",
                (level, xp, json.dumps(stats), stat_points, max_hp,
                 character_id, user_id, self.world_id),
            )

    def _lock_character_currency(self, connection, user_id, character_id):
        row = connection.execute(
            """SELECT copper, silver, gold FROM characters
               WHERE id = %s AND user_id = %s AND world_id = %s FOR UPDATE""",
            (character_id, user_id, self.world_id),
        ).fetchone()
        if row is None:
            raise ValueError("Персонаж не найден")
        return Currency(copper=int(row["copper"] or 0), silver=int(row["silver"] or 0), gold=int(row["gold"] or 0))

    def _store_character_currency(self, connection, user_id, character_id, currency):
        connection.execute(
            """UPDATE characters SET copper = %s, silver = %s, gold = %s
               WHERE id = %s AND user_id = %s AND world_id = %s""",
            (currency.copper, currency.silver, currency.gold, character_id, user_id, self.world_id),
        )

    def create_player_corpse(self, user_id, character_id, x, y, coin_percent):
        """Гибель: coin_percent % монет персонажа уходят в труп на месте гибели. None, если терять нечего."""
        with self.connection() as connection:
            currency = self._lock_character_currency(connection, user_id, character_id)
            lost = currency.total_copper() * coin_percent // 100
            if lost <= 0:
                return None
            currency.subtract_copper_amount(lost)
            self._store_character_currency(connection, user_id, character_id, currency)
            corpse = connection.execute(
                """INSERT INTO world_player_corpses (world_id, character_id, x, y, copper, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, x, y, copper""",
                (self.world_id, character_id, float(x), float(y), lost, time.time()),
            ).fetchone()
        corpse_payload = {
            "id": int(corpse["id"]),
            "x": float(corpse["x"]),
            "y": float(corpse["y"]),
            "copper": int(corpse["copper"]),
        }
        return corpse_payload, currency.to_dict()

    def list_player_corpses(self, character_id):
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT id, x, y, copper FROM world_player_corpses
                   WHERE world_id = %s AND character_id = %s ORDER BY id""",
                (self.world_id, character_id),
            ).fetchall()
        return [
            {"id": int(row["id"]), "x": float(row["x"]), "y": float(row["y"]), "copper": int(row["copper"])}
            for row in rows
        ]

    def loot_player_corpse(self, user_id, character_id, corpse_id):
        """Монеты трупа переходят в кошелёк персонажа, труп удаляется. Возвращает кошелёк и сумму добычи."""
        with self.connection() as connection:
            currency = self._lock_character_currency(connection, user_id, character_id)
            corpse = connection.execute(
                """SELECT copper FROM world_player_corpses
                   WHERE id = %s AND character_id = %s AND world_id = %s FOR UPDATE""",
                (corpse_id, character_id, self.world_id),
            ).fetchone()
            if corpse is None:
                raise ValueError("Труп не найден")
            looted = int(corpse["copper"])
            currency.add_copper_amount(looted)
            self._store_character_currency(connection, user_id, character_id, currency)
            connection.execute("DELETE FROM world_player_corpses WHERE id = %s", (corpse_id,))
        return currency.to_dict(), looted

    def _load_character_for_save(self, connection, user_id, character_id):
        row = connection.execute(
            "SELECT * FROM characters WHERE id = %s AND user_id = %s AND world_id = %s",
            (character_id, user_id, self.world_id),
        ).fetchone()
        if row is None:
            raise ValueError("Персонаж не найден")
        row = self._apply_passive_regen(row, time.time())
        equipment_hp = int(self.equipment_bonuses(connection, character_id).get("hp", 0))
        return self._character_payload(row, equipment_hp), equipment_hp

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
    def _character_payload(row, equipment_hp=0):
        row_dict = dict(row)
        stats = json.loads(row["stats_json"])
        character_type = row["type"] if "type" in row.keys() else "warrior"
        max_hp = calculate_max_hp(row["level"], stats.get("endurance", minimum_endurance(row["level"]))) + equipment_hp
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
                    "Тебе уже хватит, иди проспись и приходи в чувство!! ХА-ХА-ХА"
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


# Замеры: медленные запросы к базе видны в логе мира (см. server/perf_probe.py).
from server.perf_probe import timed as _timed  # noqa: E402

Database.save_world_vitals = _timed("БД: сохранение HP и MP")(Database.save_world_vitals)
Database.add_world_currency = _timed("БД: начисление монет")(Database.add_world_currency)
Database.get_character = _timed("БД: чтение персонажа")(Database.get_character)
Database.save_world_crystal_state = _timed("БД: сохранение кристаллов")(Database.save_world_crystal_state)
