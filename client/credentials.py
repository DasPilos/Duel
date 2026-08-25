import json
from pathlib import Path


CREDENTIALS_PATH = Path.home() / ".mini_duel_login.json"


def load_credentials():
    try:
        data = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {"username": "", "password": ""}
    return {
        "username": str(data.get("username", "")),
        "password": str(data.get("password", "")),
    }


def save_credentials(username, password):
    try:
        CREDENTIALS_PATH.write_text(
            json.dumps({"username": username, "password": password}),
            encoding="utf-8",
        )
    except OSError:
        pass


def clear_credentials():
    try:
        CREDENTIALS_PATH.unlink(missing_ok=True)
    except OSError:
        pass
