"""In-memory server maintenance/restart notice state."""

import math
import threading
import time


DEFAULT_RESTART_DELAY_SECONDS = 180
MAX_RESTART_DELAY_SECONDS = 30 * 60

_LOCK = threading.Lock()
_NOTICE = None
_CLIENT_RELOAD = None


def schedule_restart(*, delay_seconds=DEFAULT_RESTART_DELAY_SECONDS, message=None, now=None):
    delay_seconds = int(delay_seconds)
    if not 1 <= delay_seconds <= MAX_RESTART_DELAY_SECONDS:
        raise ValueError("Интервал перезапуска должен быть от 1 до 30 минут")
    now = time.time() if now is None else float(now)
    notice = {
        "restart_at": now + delay_seconds,
        "message": message or "Сервер получил обновление и будет перезагружен.",
    }
    with _LOCK:
        global _NOTICE
        _NOTICE = notice
    return public_notice(now=now)


def cancel_restart():
    global _NOTICE
    with _LOCK:
        _NOTICE = None


def restart_due(*, now=None):
    now = time.time() if now is None else float(now)
    with _LOCK:
        return _NOTICE is not None and now >= _NOTICE["restart_at"]


def public_notice(*, now=None):
    now = time.time() if now is None else float(now)
    with _LOCK:
        if _NOTICE is None:
            return None
        return {
            **_NOTICE,
            "seconds_remaining": max(0, math.ceil(_NOTICE["restart_at"] - now)),
        }


def request_client_reload(*, message=None, now=None):
    """Просит все клиенты перезагрузиться. id по времени, чтобы не совпадал после перезапуска сервера."""
    now = time.time() if now is None else float(now)
    notice = {
        "id": int(now * 1000),
        "message": message or "Сервер получил важное обновление. Перезагрузите клиент.",
    }
    global _CLIENT_RELOAD
    with _LOCK:
        _CLIENT_RELOAD = notice
    return dict(notice)


def cancel_client_reload():
    global _CLIENT_RELOAD
    with _LOCK:
        _CLIENT_RELOAD = None


def public_client_reload():
    with _LOCK:
        return dict(_CLIENT_RELOAD) if _CLIENT_RELOAD is not None else None