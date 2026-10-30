import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
# Рабочие файлы сервера (состояние ботов) лежат вне пакета и не попадают в git
DATA_DIR = Path(os.environ.get("KALODA_DATA_DIR", BASE_DIR / "data" / "kaloda"))
# Пароль здесь не хранится: libpq читает его из pgpass (%APPDATA%\postgresql\pgpass.conf или ~/.pgpass).
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://game@127.0.0.1:5432/game")
DB_POOL_MIN_SIZE = int(os.environ.get("DB_POOL_MIN_SIZE", "1"))
DB_POOL_MAX_SIZE = int(os.environ.get("DB_POOL_MAX_SIZE", "20"))

# Игровые таблицы Колоды живут в собственной схеме, а общие users/sessions/worlds читаются из схемы Оператора 1.
SCHEMA = os.environ.get("KALODA_SCHEMA", "kaloda")
SHARED_SCHEMA = os.environ.get("KALODA_SHARED_SCHEMA", "public")

# Номер мира задаётся явно: значение по умолчанию привело бы процесс в мир Оператора 1.
WORLD_ID = int(os.environ["KALODA_WORLD_ID"]) if os.environ.get("KALODA_WORLD_ID") else None
WORLD_CODE_PREFIX = "kaloda"

HOST = os.environ.get("HOST", "0.0.0.0")
# 8765 занят сервером Оператора 1, поэтому у Колоды свой порт
PORT = int(os.environ.get("KALODA_PORT", "8766"))
# Адрес мира в лобби: на общем сервере его задают явно, локально это тот же компьютер
PUBLIC_URL = os.environ.get("KALODA_PUBLIC_URL") or f"http://127.0.0.1:{PORT}"
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7
ONLINE_PLAYER_TTL_SECONDS = 15
CHAT_MAX_LENGTH = 300
CHAT_RATE_LIMIT_COUNT = 5
CHAT_RATE_LIMIT_WINDOW = 10
PASSIVE_REGEN_FULL_SECONDS = 300
CHAT_HISTORY_TTL_SECONDS = 48 * 60 * 60
SERVER_TIMEZONE = os.environ.get("SERVER_TIMEZONE", "Europe/Kyiv")
