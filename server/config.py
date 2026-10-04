import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
# Password is never stored here: libpq reads it from pgpass (%APPDATA%\postgresql\pgpass.conf or ~/.pgpass).
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://game@127.0.0.1:5432/game")
DB_POOL_MIN_SIZE = int(os.environ.get("DB_POOL_MIN_SIZE", "1"))
DB_POOL_MAX_SIZE = int(os.environ.get("DB_POOL_MAX_SIZE", "20"))
WORLD_ID = int(os.environ.get("WORLD_ID", "1"))
LEGACY_SQLITE_PATH = BASE_DIR / "server_data.sqlite3"
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8765"))
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7
CHAT_MAX_LENGTH = 300
CHAT_RATE_LIMIT_COUNT = 5
CHAT_RATE_LIMIT_WINDOW = 10
PASSIVE_REGEN_FULL_SECONDS = 300
CHAT_HISTORY_TTL_SECONDS = 48 * 60 * 60
