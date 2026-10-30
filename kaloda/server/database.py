import atexit
import hashlib
import hmac
import json
import secrets
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

from psycopg import errors as pg_errors
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from core.map_catalog import catalog_definitions
from kaloda.combat.character_stats import (
    BASE_STAT_VALUE,
    MIN_STAT_VALUE,
    STARTING_STAT_POINTS,
    calculate_max_hp,
    calculate_max_mana,
    is_valid_profession,
    minimum_endurance,
    normalize_profession_type,
)
from kaloda.combat.fighter import Fighter
from kaloda.combat.progression import apply_xp, battle_xp
from kaloda.combat.talents import derived_talent_values, talent_option
from kaloda.currency import spend_coins
from kaloda.game_modes import DEFAULT_MODE, GAME_MODES, is_mode
from kaloda.quests import QUESTS_BY_ID
from kaloda.rewards import npc_kill_xp
from kaloda.server import config, map_editor
from kaloda.server.migrations import apply_migrations

SYSTEM_USER_ID = 0
# Колонки общей таблицы worlds, без которых Колода не работает; их добавляют миграции Оператора 1
SHARED_WORLD_COLUMNS = ("mode", "test_only", "server_url", "opens_at", "closes_at")
# Код мира, созданного редактором карт: начинается с кода Колоды, чтобы сервер его принял
MAP_WORLD_CODE_PREFIX = "kaloda_map"
# Стартовый кошелёк нового героя в монетах (в старой Колоде это были 100 монет)
STARTING_COINS = 100
# One pool per (dsn, search_path) for the whole process: bot chat, bot battles and HTTP handlers share it.
_POOLS = {}
_POOLS_LOCK = threading.Lock()


def _shared_pool(dsn, search_path):
    key = (dsn, search_path)
    with _POOLS_LOCK:
        entry = _POOLS.get(key)
        if entry is not None:
            return entry
        pool = ConnectionPool(
            dsn,
            min_size=config.DB_POOL_MIN_SIZE,
            max_size=config.DB_POOL_MAX_SIZE,
            kwargs={"row_factory": dict_row, "options": f"-c search_path={search_path}"},
            check=ConnectionPool.check_connection,
            name=f"kaloda-{search_path}",
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
    def __init__(self, dsn=None, *, schema=None, shared_schema=None, world_id=None):
        self.dsn = dsn or config.DATABASE_URL
        self.schema = schema or config.SCHEMA
        self.shared_schema = shared_schema or config.SHARED_SCHEMA
        world_id = config.WORLD_ID if world_id is None else world_id
        if world_id is None:
            raise RuntimeError("Не задан мир Колоды: укажите номер мира в KALODA_WORLD_ID")
        self.world_id = int(world_id)
        # Свои таблицы ищутся первыми, общие users/sessions/worlds — в схеме Оператора 1
        self.search_path = f"{self.schema},{self.shared_schema}"
        self._entry = _shared_pool(self.dsn, self.search_path)
        self.initialize()

    @contextmanager
    def connection(self):
        # Commits when the block succeeds, rolls back on any exception.
        with self._entry["pool"].connection() as connection:
            yield connection

    def close(self):
        """Closes the shared pool. Only for throwaway databases (test schemas)."""
        with _POOLS_LOCK:
            _POOLS.pop((self.dsn, self.search_path), None)
        self._entry["pool"].close()

    def initialize(self):
        with self._entry["init_lock"]:
            if not self._entry["initialized"]:
                self._initialize_schema()
                self._entry["initialized"] = True
        with self.connection() as connection:
            world = connection.execute("SELECT code FROM worlds WHERE id = %s", (self.world_id,)).fetchone()
        if world is None:
            raise RuntimeError(f"Мир WORLD_ID={self.world_id} не найден в таблице worlds")
        if not str(world["code"]).startswith(config.WORLD_CODE_PREFIX):
            raise RuntimeError(
                f"Мир {world['code']} принадлежит не Колоде: код мира Колоды начинается с «{config.WORLD_CODE_PREFIX}»"
            )

    def _initialize_schema(self):
        with self.connection() as connection:
            shared = connection.execute(
                "SELECT to_regclass(%s) AS worlds", (f'"{self.shared_schema}".worlds',)
            ).fetchone()
            if shared["worlds"] is None:
                raise RuntimeError(
                    f"В схеме «{self.shared_schema}» нет общих таблиц (users, sessions, worlds): "
                    "их создаёт сервер Оператора 1, запустите его хотя бы один раз"
                )
            self._check_shared_world_columns(connection)
            apply_migrations(connection, self.schema)
            self._initialize_drinks(connection)
            self._initialize_map_catalog(connection)
            self._normalize_character_stats(connection)

    def _check_shared_world_columns(self, connection):
        rows = connection.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = 'worlds'",
            (self.shared_schema,),
        ).fetchall()
        present = {row["column_name"] for row in rows}
        missing = [column for column in SHARED_WORLD_COLUMNS if column not in present]
        if missing:
            raise RuntimeError(
                f"В таблице worlds схемы «{self.shared_schema}» нет колонок: {', '.join(missing)}. "
                "Запустите сервер Оператора 1, чтобы применились его миграции"
            )

    @staticmethod
    def _initialize_map_catalog(connection):
        """Обновляет каталог тайлов и объектов редактора карт по файлам assets/map."""
        items = catalog_definitions()
        for item in items:
            connection.execute(
                """INSERT INTO map_catalog
                   (item_key, kind, category, asset, footprint_w, footprint_h, blocks, sort_order)
                   VALUES (%(item_key)s, %(kind)s, %(category)s, %(asset)s,
                           %(footprint_w)s, %(footprint_h)s, %(blocks)s, %(sort_order)s)
                   ON CONFLICT (item_key) DO UPDATE SET
                       kind = EXCLUDED.kind, category = EXCLUDED.category, asset = EXCLUDED.asset,
                       footprint_w = EXCLUDED.footprint_w, footprint_h = EXCLUDED.footprint_h,
                       blocks = EXCLUDED.blocks, sort_order = EXCLUDED.sort_order""",
                item,
            )
        connection.execute(
            """DELETE FROM map_catalog WHERE NOT (item_key = ANY(%s))
               AND item_key NOT IN (SELECT item_key FROM map_live_cells)""",
            ([item["item_key"] for item in items],),
        )

    @staticmethod
    def _rescale_hp(current_hp, old_max_hp, new_max_hp):
        current_hp = max(0, int(current_hp))
        old_max_hp = int(old_max_hp)
        new_max_hp = max(1, int(new_max_hp))
        if old_max_hp <= 0 or current_hp >= old_max_hp:
            return new_max_hp if current_hp >= old_max_hp else min(current_hp, new_max_hp)
        return min(new_max_hp, current_hp * new_max_hp // old_max_hp)

    @staticmethod
    def _normalize_character_stats(connection):
        """Fill in any missing stats so every character (warrior or mage) has all 7."""
        rows = connection.execute(
            "SELECT id, type, level, hp, max_hp, mp, stats_json FROM characters"
        ).fetchall()
        for row in rows:
            character_type = normalize_profession_type(row["type"])
            stored = json.loads(row["stats_json"] or "{}") if row["stats_json"] else {}
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
            max_hp = calculate_max_hp(level, stats["endurance"], character_type)
            if stats == stored and row["type"] == character_type and int(row["max_hp"]) == max_hp:
                continue
            max_mp = calculate_max_mana(stats["intellect"], character_type)
            connection.execute(
                """UPDATE characters
                         SET type = %s, stats_json = %s, max_hp = %s, hp = LEAST(hp, %s),
                      mp = LEAST(mp, %s), max_mp = %s
                   WHERE id = %s""",
                (character_type, json.dumps(stats), max_hp, max_hp, row["mp"], max_mp, row["id"]),
            )

    @staticmethod
    def _initialize_drinks(connection):
        """Инициализирует напитки в БД"""
        now = time.time()
        drinks = [
            ("Эль", "Восстанавливает 50 жизней", 20, "heal", 50),
        ]
        for name, description, price_coins, effect, value in drinks:
            connection.execute(
                """INSERT INTO drinks (name, description, price_coins, effect, effect_value, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (name) DO NOTHING""",
                (name, description, price_coins, effect, value, now),
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

    def set_server_url(self, server_url):
        """Публикует адрес мира в общей таблице: лобби предлагает мир, только пока адрес есть."""
        with self.connection() as connection:
            connection.execute("UPDATE worlds SET server_url = %s WHERE id = %s", (server_url, self.world_id))

    # ------------------------------------------------------------------ миры Колоды и карты редактора

    def list_worlds(self, now=None, viewer_id=None):
        """Миры Колоды с вычисленным открыт/закрыт. Тестовые миры видят только модераторы и админы."""
        now = time.time() if now is None else float(now)
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT id, code, name, status, opens_at, closes_at, server_url, test_only FROM worlds
                   WHERE mode = ANY(%s) ORDER BY id""",
                ([mode["key"] for mode in GAME_MODES],),
            ).fetchall()
        if viewer_id is None or not self.is_moderator(viewer_id):
            rows = [row for row in rows if not row["test_only"]]
        return [self._world_payload(row, now) for row in rows]

    @staticmethod
    def _world_payload(row, now):
        is_open = (
            row["status"] == "open"
            and (row["opens_at"] is None or row["opens_at"] <= now)
            and (row["closes_at"] is None or row["closes_at"] > now)
        )
        return {
            "id": row["id"],
            "code": row["code"],
            "name": row["name"],
            "is_open": is_open,
            "opens_at": row["opens_at"],
            "closes_at": row["closes_at"],
            "server_url": row["server_url"],
        }

    def is_admin(self, user_id):
        with self.connection() as connection:
            row = connection.execute("SELECT role FROM users WHERE id = %s", (user_id,)).fetchone()
        return row is not None and row["role"] == "admin"

    def can_enter_current_world(self, user_id):
        """Тестовый мир этого сервера открыт только модераторам и админам."""
        with self.connection() as connection:
            row = connection.execute("SELECT test_only FROM worlds WHERE id = %s", (self.world_id,)).fetchone()
        if row is None or not row["test_only"]:
            return True
        return self.is_moderator(user_id)

    def world_info(self, world_id):
        with self.connection() as connection:
            row = connection.execute(
                "SELECT id, code, name, status, mode, server_url, test_only FROM worlds WHERE id = %s", (world_id,)
            ).fetchone()
        if row is None:
            raise ValueError("Мир не найден")
        return dict(row)

    def map_catalog(self):
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT item_key, kind, category, asset, footprint_w, footprint_h, blocks, sort_order
                   FROM map_catalog ORDER BY sort_order, item_key"""
            ).fetchall()
        return [dict(row) for row in rows]

    def map_live_cells(self):
        """Опубликованная карта текущего мира; пустой список, если карта не публиковалась."""
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT layer, x, y, item_key AS key FROM map_live_cells
                   WHERE world_id = %s ORDER BY layer, y, x""",
                (self.world_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def published_map(self):
        """Сведения о карте, опубликованной в текущий мир; None, если мир играет процедурным рельефом."""
        with self.connection() as connection:
            row = connection.execute(
                "SELECT name, map_w, map_h, published_at, mode FROM map_world_publish WHERE world_id = %s",
                (self.world_id,),
            ).fetchone()
        return None if row is None else dict(row)

    def linked_world_ids(self, saved_id):
        """Миры, в которых сейчас опубликована заготовка saved_id (их обновляют при сохранении заготовки)."""
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT world_id FROM map_world_publish WHERE saved_id = %s ORDER BY world_id", (saved_id,)
            ).fetchall()
        return [row["world_id"] for row in rows]

    def save_saved_map(self, saved_id, name, mode, map_w, map_h, cells, mobs, moderator_id, spawns=None):
        """Сохраняет карту на сервере как заготовку для мира: мир не создаётся."""
        if not self.is_moderator(moderator_id):
            raise ValueError("Недостаточно прав модератора")
        name = str(name or "").strip()
        if not 1 <= len(name) <= 64:
            raise ValueError("Название карты: от 1 до 64 символов")
        if not is_mode(mode):
            raise ValueError("Неизвестный режим игры")
        map_editor.check_map_size(map_w, map_h)
        cell_rows = map_editor.validate_cells(cells, self.map_catalog(), map_w, map_h)
        mob_rows = map_editor.validate_mobs(mobs, map_w, map_h)
        spawn_rows = map_editor.validate_spawns(spawns, map_w, map_h)
        cells_json = json.dumps([{"layer": l, "x": x, "y": y, "key": k} for l, x, y, k in cell_rows], ensure_ascii=False)
        mobs_json = json.dumps([{"kind": k, "x": x, "y": y} for k, x, y in mob_rows], ensure_ascii=False)
        spawns_json = json.dumps([{"x": x, "y": y} for x, y in spawn_rows], ensure_ascii=False)
        now = time.time()
        with self.connection() as connection:
            if saved_id:
                row = connection.execute(
                    """UPDATE map_saved SET name = %s, mode = %s, map_w = %s, map_h = %s,
                       cells_json = %s, mobs_json = %s, spawns_json = %s, updated_at = %s WHERE id = %s RETURNING id""",
                    (name, mode, map_w, map_h, cells_json, mobs_json, spawns_json, now, saved_id),
                ).fetchone()
                if row is None:
                    raise ValueError("Карта на сервере не найдена")
                return row["id"]
            row = connection.execute(
                """INSERT INTO map_saved (name, mode, map_w, map_h, cells_json, mobs_json, spawns_json, created_by, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (name, mode, map_w, map_h, cells_json, mobs_json, spawns_json, moderator_id, now, now),
            ).fetchone()
        return row["id"]

    def get_saved_map(self, saved_id):
        with self.connection() as connection:
            row = connection.execute(
                "SELECT id, name, mode, map_w, map_h, cells_json, mobs_json, spawns_json FROM map_saved WHERE id = %s",
                (saved_id,),
            ).fetchone()
        if row is None:
            raise ValueError("Карта на сервере не найдена")
        data = dict(row)
        data["cells"] = json.loads(data.pop("cells_json"))
        data["mobs"] = json.loads(data.pop("mobs_json"))
        data["spawns"] = json.loads(data.pop("spawns_json"))
        return data

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

    def create_map_world(self, name, mode, moderator_id, test_only=False):
        """Новый мир Колоды из карты: id по порядку, код kaloda_map<id>, режим карты. Тестовый мир создаёт только админ."""
        if not self.is_moderator(moderator_id):
            raise ValueError("Недостаточно прав модератора")
        if test_only and not self.is_admin(moderator_id):
            raise ValueError("Тестовый мир создаёт только админ")
        with self.connection() as connection:
            next_id = connection.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM worlds").fetchone()["next_id"]
            code = f"{MAP_WORLD_CODE_PREFIX}{next_id}"
            connection.execute(
                """INSERT INTO worlds (id, code, name, status, created_at, mode, test_only)
                   VALUES (%s, %s, %s, 'open', %s, %s, %s)""",
                (next_id, code, name, time.time(), mode, bool(test_only)),
            )
        return {"id": next_id, "code": code, "name": name, "mode": mode}

    def delete_map_world(self, world_id):
        """Удаляет только миры карт: откат, если карта не прошла проверку."""
        with self.connection() as connection:
            connection.execute(
                "DELETE FROM worlds WHERE id = %s AND starts_with(code, %s)", (world_id, MAP_WORLD_CODE_PREFIX)
            )

    def publish_map(self, cells, world_id, name, map_w, map_h, moderator_id, mobs=None, mode=DEFAULT_MODE,
                    spawns=None, saved_id=None):
        """Размещает карту редактора в мире Колоды world_id: клетки, NPC и режим. Заменяет живую карту этого мира."""
        if not self.is_moderator(moderator_id):
            raise ValueError("Недостаточно прав модератора")
        name = str(name or "").strip()
        if not 1 <= len(name) <= 64:
            raise ValueError("Название карты: от 1 до 64 символов")
        map_editor.check_map_size(map_w, map_h)
        rows = map_editor.validate_cells(cells, self.map_catalog(), map_w, map_h)
        if not rows:
            raise ValueError("Карта пустая, нечего размещать")
        mob_rows = map_editor.validate_mobs(mobs, map_w, map_h)
        spawn_rows = map_editor.validate_spawns(spawns, map_w, map_h)
        if not is_mode(mode):
            raise ValueError("Неизвестный режим игры")
        published_at = time.time()
        with self.connection() as connection:
            target = connection.execute("SELECT id, name, code, mode FROM worlds WHERE id = %s", (world_id,)).fetchone()
            if target is None:
                raise ValueError("Мир не найден")
            if not self._is_kaloda_world(target):
                raise ValueError("Мир не принадлежит Колоде: карту можно опубликовать только в мир Колоды")
            connection.execute("DELETE FROM map_live_cells WHERE world_id = %s", (target["id"],))
            for layer, x, y, key in rows:
                connection.execute(
                    """INSERT INTO map_live_cells (world_id, layer, x, y, item_key)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (target["id"], layer, x, y, key),
                )
            connection.execute("DELETE FROM map_live_spawns WHERE world_id = %s", (target["id"],))
            for x, y in spawn_rows:
                connection.execute(
                    "INSERT INTO map_live_spawns (world_id, x, y) VALUES (%s, %s, %s)",
                    (target["id"], x, y),
                )
            connection.execute("DELETE FROM map_live_mobs WHERE world_id = %s", (target["id"],))
            for kind, x, y in mob_rows:
                connection.execute(
                    "INSERT INTO map_live_mobs (world_id, kind, x, y) VALUES (%s, %s, %s, %s)",
                    (target["id"], kind, x, y),
                )
            connection.execute(
                """INSERT INTO map_world_publish (world_id, name, map_w, map_h, published_at, mode, saved_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (world_id) DO UPDATE SET
                       name = EXCLUDED.name, map_w = EXCLUDED.map_w,
                       map_h = EXCLUDED.map_h, published_at = EXCLUDED.published_at,
                       mode = EXCLUDED.mode, saved_id = EXCLUDED.saved_id""",
                (target["id"], name, map_w, map_h, published_at, mode, saved_id),
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

    @staticmethod
    def _is_kaloda_world(row):
        return str(row["code"]).startswith(config.WORLD_CODE_PREFIX) and is_mode(row["mode"])

    def create_character(self, user_id, name, profession_type="warrior"):
        self.validate_character_name(name)
        profession_type = normalize_profession_type(profession_type)
        if not is_valid_profession(profession_type):
            raise ValueError("Профессия должна быть одной из: warrior, archer, assassin, mage, necromancer")

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
        
        max_hp = calculate_max_hp(1, stats["endurance"], profession_type)
        max_mp = calculate_max_mana(stats["intellect"], profession_type)
        stat_points = STARTING_STAT_POINTS
        try:
            with self.connection() as connection:
                character_id = connection.execute(
                    """
                    INSERT INTO characters
                    (user_id, world_id, name, type, hp, max_hp, mp, max_mp, stats_json, stat_points, coins, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (user_id, self.world_id, name, profession_type, max_hp, max_hp, max_mp, max_mp,
                     json.dumps(stats), stat_points, STARTING_COINS, now),
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
        from kaloda.server.social import remove_character_presence

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
        profession_type = normalize_profession_type(profession_type)
        if not is_valid_profession(profession_type):
            raise ValueError("Профессия должна быть одной из: warrior, archer, assassin, mage, necromancer")
        
        with self.connection() as connection:
            row = connection.execute(
                "SELECT user_id, level, hp, stats_json FROM characters WHERE id = %s AND world_id = %s",
                (character_id, self.world_id),
            ).fetchone()
            if row is None or row["user_id"] != user_id:
                raise ValueError("Персонаж не найден")
            stats = json.loads(row["stats_json"] or "{}")
            max_hp = calculate_max_hp(
                row["level"],
                stats.get("endurance", minimum_endurance(row["level"])),
                profession_type,
            )
            connection.execute(
                "UPDATE characters SET type = %s, max_hp = %s, hp = LEAST(hp, %s) WHERE id = %s",
                (profession_type, max_hp, max_hp, character_id),
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
                character["equipment_bonuses"] = self.equipment_bonuses(connection, row["id"])
                character["equipment"] = self.equipped_items(connection, row["id"])
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
        from kaloda.server.bots import get_bot_opponents

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
        from kaloda.server.bots import update_bot

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
            character["equipment_bonuses"] = self.equipment_bonuses(connection, row["id"])
            character["equipment"] = self.equipped_items(connection, row["id"])
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
        return {"user_id": row["user_id"], "character": character}

    @staticmethod
    def equipped_items(connection, character_id):
        """Надетые предметы: {слот: предмет}. Отдаются вместе с любым персонажем,
        чтобы слоты на карточке были заполнены у всех, независимо от класса."""
        from kaloda.server.items_database import _ITEM_COLUMNS, _item_payload, display_equipment_hands

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
        
        updated = {
            "name": str(payload.get("name", current["name"])),
            "type": normalize_profession_type(str(payload.get("type", current.get("type", "warrior")))),
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
            "talents": dict(current.get("talents", {})),
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
        derived = derived_talent_values(
            updated["type"], level, updated["stats"], updated["talents"]
        )
        updated["max_hp"] = derived["max_hp"]
        updated["hp"] = min(updated["hp"], updated["max_hp"])
        updated["max_mp"] = derived["max_mp"]
        updated["mp"] = min(updated["mp"], updated["max_mp"])
        self.validate_character_name(updated["name"])
        self._validate_character(updated)
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE characters SET name = %s, level = %s, xp = %s, hp = %s,
                max_hp = %s, mp = %s, max_mp = %s, stats_json = %s, stat_points = %s,
                zone = %s, position_x = %s, position_y = %s, position_direction = %s,
                updated_at = %s
                WHERE id = %s AND user_id = %s AND world_id = %s
                """,
                (
                    updated["name"], updated["level"], updated["xp"], updated["hp"],
                    updated["max_hp"], updated["mp"], updated["max_mp"],
                    json.dumps(updated["stats"]), updated["stat_points"],
                    updated["zone"], updated["position_x"], updated["position_y"],
                    updated["position_direction"], time.time(),
                    character_id, user_id, self.world_id,
                ),
            )
        return self.get_character(user_id, character_id)

    def choose_character_talent(self, user_id, character_id, level, choice_id):
        level = int(level)
        if not 1 <= level <= 10:
            raise ValueError("Уровень таланта должен быть от 1 до 10")
        with self.connection() as connection:
            lock_character(connection, character_id)
            row = connection.execute(
                """SELECT type, level, talents_json FROM characters
                   WHERE id = %s AND user_id = %s AND world_id = %s
                   FOR UPDATE""",
                (character_id, user_id, self.world_id),
            ).fetchone()
            if row is None:
                raise ValueError("Персонаж не найден")
            if int(row["level"]) < level:
                raise ValueError("Для этого таланта уровень персонажа недостаточен")
            option = talent_option(row["type"], level, choice_id)
            if option is None:
                raise ValueError("Такого выбора на этом уровне нет")
            talents = json.loads(row["talents_json"] or "{}")
            if not isinstance(talents, dict):
                raise ValueError("Данные талантов персонажа повреждены")
            if str(level) in talents:
                raise ValueError("На этом уровне улучшение уже выбрано")
            talents[str(level)] = option["id"]
            connection.execute(
                """UPDATE characters SET talents_json = %s, updated_at = %s
                   WHERE id = %s AND user_id = %s AND world_id = %s""",
                (
                    json.dumps(talents, ensure_ascii=False),
                    time.time(),
                    character_id,
                    user_id,
                    self.world_id,
                ),
            )
        return self.get_character(user_id, character_id)

    def report_battle_result(self, user_id, character_id, outcome, opponent_level, hp, mp, request_id):
        """Apply combat progress and victory coins once per battle request."""
        outcome = str(outcome)
        if outcome not in {"win", "draw", "loss"}:
            raise ValueError("Некорректный результат боя")
        request_id = str(request_id or "").strip()
        if not request_id or len(request_id) > 128:
            raise ValueError("Некорректный идентификатор боя")

        with self.connection() as connection:
            lock_character(connection, character_id)
            row = connection.execute(
                """SELECT * FROM characters
                   WHERE id = %s AND user_id = %s AND world_id = %s
                   FOR UPDATE""",
                (character_id, user_id, self.world_id),
            ).fetchone()
            if row is None:
                raise ValueError("Персонаж не найден")
            if connection.execute(
                """SELECT 1 FROM battle_result_receipts
                   WHERE character_id = %s AND request_id = %s""",
                (character_id, request_id),
            ).fetchone():
                raise ValueError("Результат боя уже засчитан")

            current_level = int(row["level"])
            character_type = normalize_profession_type(row["type"])
            stats = json.loads(row["stats_json"] or "{}")
            fighter = Fighter(row["name"], current_level, profession_type=character_type)
            fighter.stats = {
                "strength": max(MIN_STAT_VALUE, int(stats.get("strength", BASE_STAT_VALUE))),
                "agility": max(MIN_STAT_VALUE, int(stats.get("agility", BASE_STAT_VALUE))),
                "intuition": max(MIN_STAT_VALUE, int(stats.get("intuition", BASE_STAT_VALUE))),
                "wisdom": max(MIN_STAT_VALUE, int(stats.get("wisdom", BASE_STAT_VALUE))),
                "intellect": max(MIN_STAT_VALUE, int(stats.get("intellect", BASE_STAT_VALUE))),
                "harmony": max(MIN_STAT_VALUE, int(stats.get("harmony", BASE_STAT_VALUE))),
                "endurance": max(
                    minimum_endurance(current_level),
                    int(stats.get("endurance", minimum_endurance(current_level))),
                ),
            }
            fighter.talents = json.loads(row["talents_json"] or "{}")
            fighter.xp = int(row["xp"])
            fighter.stat_points = int(row["stat_points"])
            fighter.recalculate_parameters()
            fighter.hp = min(max(0, int(hp)), fighter.max_hp)
            fighter.mp = min(max(0, int(mp)), fighter.max_mp)

            xp_awarded = battle_xp(current_level, int(opponent_level), outcome)
            levels_gained = apply_xp(fighter, xp_awarded)
            currency_reward = {"coins": 0}
            now = time.time()

            connection.execute(
                """INSERT INTO battle_result_receipts
                   (character_id, request_id, created_at) VALUES (%s, %s, %s)""",
                (character_id, request_id, now),
            )
            connection.execute(
                """UPDATE characters
                   SET level = %s, xp = %s, hp = %s, max_hp = %s, mp = %s,
                       max_mp = %s, stats_json = %s, stat_points = %s, updated_at = %s
                   WHERE id = %s AND user_id = %s AND world_id = %s""",
                (
                    fighter.level, fighter.xp, fighter.hp, fighter.max_hp,
                    fighter.mp, fighter.max_mp, json.dumps(fighter.stats),
                    fighter.stat_points, now, character_id, user_id, self.world_id,
                ),
            )

        return {
            "character": self.get_character(user_id, character_id),
            "xp": xp_awarded,
            "levels_gained": levels_gained,
            "currency": currency_reward,
        }

    def report_npc_kill_xp(self, user_id, character_id, encounter_id, defeated_types, request_id):
        """Award fixed XP for defeated encounter enemies once per battle."""
        encounter_id = str(encounter_id)
        defeated_types = tuple(str(npc_type) for npc_type in defeated_types)
        xp_awarded = npc_kill_xp(encounter_id, defeated_types)
        request_id = str(request_id or "").strip()
        if not request_id or len(request_id) > 128:
            raise ValueError("Некорректный идентификатор боя")
        try:
            uuid.UUID(request_id)
        except ValueError as error:
            raise ValueError("Некорректный идентификатор боя") from error

        with self.connection() as connection:
            lock_character(connection, character_id)
            row = connection.execute(
                """SELECT * FROM characters
                   WHERE id = %s AND user_id = %s AND world_id = %s
                   FOR UPDATE""",
                (character_id, user_id, self.world_id),
            ).fetchone()
            if row is None:
                raise ValueError("Персонаж не найден")
            receipt = connection.execute(
                """INSERT INTO npc_kill_xp_receipts
                   (character_id, request_id, encounter_id, xp_awarded, created_at)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (character_id, request_id) DO NOTHING
                   RETURNING request_id""",
                (character_id, request_id, encounter_id, xp_awarded, time.time()),
            ).fetchone()
            if receipt is None:
                raise ValueError("Опыт за это убийство уже начислен")

            level = int(row["level"])
            character_type = normalize_profession_type(row["type"])
            stored_stats = json.loads(row["stats_json"] or "{}")
            fighter = Fighter(row["name"], level, profession_type=character_type)
            fighter.stats = {
                stat: max(MIN_STAT_VALUE, int(stored_stats.get(stat, BASE_STAT_VALUE)))
                for stat in (
                    "strength", "agility", "intuition", "wisdom",
                    "intellect", "harmony", "endurance",
                )
            }
            fighter.talents = json.loads(row["talents_json"] or "{}")
            fighter.xp = int(row["xp"])
            fighter.stat_points = int(row["stat_points"])
            fighter.recalculate_parameters()
            fighter.hp = min(int(row["hp"]), fighter.max_hp)
            fighter.mp = min(int(row["mp"]), fighter.max_mp)
            levels_gained = apply_xp(fighter, xp_awarded)
            connection.execute(
                """UPDATE characters
                   SET level = %s, xp = %s, hp = %s, max_hp = %s, mp = %s,
                       max_mp = %s, stats_json = %s, stat_points = %s, updated_at = %s
                   WHERE id = %s AND user_id = %s AND world_id = %s""",
                (
                    fighter.level, fighter.xp, fighter.hp, fighter.max_hp,
                    fighter.mp, fighter.max_mp, json.dumps(fighter.stats),
                    fighter.stat_points, time.time(), character_id, user_id,
                    self.world_id,
                ),
            )

        return {
            "character": self.get_character(user_id, character_id),
            "xp": xp_awarded,
            "levels_gained": levels_gained,
        }

    def claim_guild_quest_reward(self, user_id, character_id, quest_id, request_id):
        quest = QUESTS_BY_ID.get(str(quest_id))
        if quest is None:
            raise ValueError("Неизвестное задание гильдии")
        request_id = str(request_id or "").strip()
        if not request_id or len(request_id) > 128:
            raise ValueError("Некорректный идентификатор сдачи задания")

        with self.connection() as connection:
            lock_character(connection, character_id)
            character = connection.execute(
                """SELECT coins FROM characters
                   WHERE id = %s AND user_id = %s AND world_id = %s
                   FOR UPDATE""",
                (character_id, user_id, self.world_id),
            ).fetchone()
            if character is None:
                raise ValueError("Персонаж не найден")

            receipt = connection.execute(
                """SELECT quest_id FROM guild_quest_reward_receipts
                   WHERE character_id = %s AND request_id = %s""",
                (character_id, request_id),
            ).fetchone()
            already_claimed = False
            if receipt is not None:
                if receipt["quest_id"] != quest.id:
                    raise ValueError("Идентификатор уже использован для другого задания")
            else:
                claimed = connection.execute(
                    """SELECT 1 FROM guild_quest_reward_receipts
                       WHERE character_id = %s AND quest_id = %s""",
                    (character_id, quest.id),
                ).fetchone()
                if claimed is not None:
                    already_claimed = True
                else:
                    now = time.time()
                    connection.execute(
                        """UPDATE characters SET coins = %s, updated_at = %s
                           WHERE id = %s AND user_id = %s AND world_id = %s""",
                        (
                            int(character["coins"]) + quest.reward_coins, now,
                            character_id, user_id, self.world_id,
                        ),
                    )
                    connection.execute(
                        """INSERT INTO guild_quest_reward_receipts
                           (character_id, request_id, quest_id, created_at)
                           VALUES (%s, %s, %s, %s)""",
                        (character_id, request_id, quest.id, now),
                    )

        return (
            self.get_character(user_id, character_id),
            0 if already_claimed else quest.reward_coins,
            already_claimed,
        )

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
                "SELECT battle_data, opponent_afk FROM active_battles WHERE player_id = %s AND opponent_id = %s",
                (player_id, opponent_id),
            ).fetchone()
            if row:
                return {
                    "battle_data": json.loads(row["battle_data"]),
                    "opponent_afk": bool(row["opponent_afk"]),
                }
            return None

    def delete_active_battle(self, player_id, opponent_id):
        with self.connection() as connection:
            connection.execute(
                "DELETE FROM active_battles WHERE player_id = %s AND opponent_id = %s",
                (player_id, opponent_id),
            )

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
        if character.get("coins", 0) < 0:
            raise ValueError("Валюта не может быть отрицательной")

    @staticmethod
    def _character_payload(row):
        row_dict = dict(row)
        stats = json.loads(row["stats_json"])
        character_type = normalize_profession_type(row["type"] if "type" in row.keys() else "warrior")
        talents = json.loads(row_dict.get("talents_json") or "{}")
        derived = derived_talent_values(
            character_type,
            row["level"],
            {
                **stats,
                "endurance": stats.get(
                    "endurance", minimum_endurance(row["level"])
                ),
            },
            talents,
        )
        max_hp = derived["max_hp"]
        max_mp = derived["max_mp"]

        # Монеты неотрицательны
        coins = int(row_dict.get("coins") or 0)

        return {
            "id": row["id"],
            "name": row["name"],
            "type": character_type,
            "level": row["level"],
            "xp": row["xp"],
            "hp": Database._rescale_hp(row["hp"], row["max_hp"], max_hp),
            "max_hp": max_hp,
            "mp": min(row["mp"], max_mp),
            "max_mp": max_mp,
            "stats": stats,
            "talents": talents,
            "unique_resource_max": derived["max_resource"],
            "stat_points": row["stat_points"],
            "zone": row["zone"],
            "position_x": row_dict.get("position_x"),
            "position_y": row_dict.get("position_y"),
            "position_direction": row_dict.get("position_direction"),
            "coins": coins,
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
                "SELECT id, name, description, price_coins, effect, effect_value FROM drinks ORDER BY id"
            ).fetchall()
            return [dict(row) for row in rows]
    
    def buy_drink(self, user_id, character_id, drink_id):
        """Напиток оплачивается сразу и действует сразу, в рюкзак он не попадает."""
        with self.connection() as connection:
            lock_character(connection, character_id)
            drink = connection.execute(
                "SELECT price_coins, effect, effect_value FROM drinks WHERE id = %s",
                (int(drink_id),),
            ).fetchone()
            if drink is None:
                raise ValueError("Напиток не найден")
            row = connection.execute(
                """SELECT * FROM characters
                   WHERE id = %s AND user_id = %s AND world_id = %s
                   FOR UPDATE""",
                (character_id, user_id, self.world_id),
            ).fetchone()
            if row is None:
                raise ValueError("Персонаж не найден")
            row = self._apply_passive_regen(connection, row, time.time())
            character = self._character_payload(row)
            hp, max_hp = character["hp"], character["max_hp"]
            if hp >= max_hp:
                # Хозяин трактира отвечает в чат таверны; клиент сообщение об ошибке не показывает
                bartender_id = self.ensure_bot_character("tavern_bartender", "Хозяин трактира")
                self.add_chat_message(
                    bartender_id, "tavern",
                    "Тебе уже хватит, иди проспись и приходи в чувство!! ХА-ХА-ХА",
                )
                raise ValueError("БАРМАН_ПОЛНОЕ_ЗДОРОВЬЕ")
            coins = spend_coins(row["coins"], drink["price_coins"])
            if drink["effect"] == "heal":
                hp = min(hp + int(drink["effect_value"]), max_hp)
            connection.execute(
                """UPDATE characters SET coins = %s, hp = %s, updated_at = %s
                   WHERE id = %s AND user_id = %s AND world_id = %s""",
                (coins, hp, time.time(),
                 character_id, user_id, self.world_id),
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
