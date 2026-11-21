import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
# Рабочие файлы сервера (состояние ботов) лежат вне пакета и не попадают в git
DATA_DIR = Path(os.environ.get("DECK_DATA_DIR", BASE_DIR / "data" / "deck"))
# Пароль здесь не хранится: libpq читает его из pgpass (%APPDATA%\postgresql\pgpass.conf или ~/.pgpass).
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://game@127.0.0.1:5432/game")
DB_POOL_MIN_SIZE = int(os.environ.get("DB_POOL_MIN_SIZE", "1"))
DB_POOL_MAX_SIZE = int(os.environ.get("DB_POOL_MAX_SIZE", "20"))

# Игровые таблицы Deck живут в собственной схеме; общие users/sessions/worlds читаются из public.
SCHEMA = os.environ.get("DECK_SCHEMA", "deck")
SHARED_SCHEMA = os.environ.get("DECK_SHARED_SCHEMA", "public")

# Номер мира задаётся явно: значение по умолчанию привело бы процесс в мир Оператора 1.
WORLD_ID = int(os.environ["DECK_WORLD_ID"]) if os.environ.get("DECK_WORLD_ID") else None
WORLD_CODE_PREFIX = "deck"

HOST = os.environ.get("HOST", "0.0.0.0")
# These values are used only when running the backend directly for development.
PORT = int(os.environ.get("DECK_PORT", "8766"))
PUBLIC_URL = os.environ.get("DECK_PUBLIC_URL") or f"http://127.0.0.1:{PORT}"
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7
ONLINE_PLAYER_TTL_SECONDS = 15
CHAT_MAX_LENGTH = 300
CHAT_RATE_LIMIT_COUNT = 5
CHAT_RATE_LIMIT_WINDOW = 10
PASSIVE_REGEN_FULL_SECONDS = 300
CHAT_HISTORY_TTL_SECONDS = 48 * 60 * 60
SERVER_TIMEZONE = os.environ.get("SERVER_TIMEZONE", "Europe/Kyiv")
