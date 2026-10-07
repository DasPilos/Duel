"""Asynchronous, local-only battle commentary for the shared game chat."""

import json
import logging
import os
import queue
import re
import threading
import time
import urllib.error
import urllib.request

from server import config
from server.database import SYSTEM_USER_ID


LOGGER = logging.getLogger(__name__)
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b-instruct")
OLLAMA_KEEP_ALIVE = os.environ.get("OLLAMA_KEEP_ALIVE", "24h")
COMMENTARY_LOCATION = "world"
COMMENTARY_TIMEOUT_SECONDS = 60
COMMENTARY_DEDUPE_SECONDS = 45
COMMENTARY_QUEUE_SIZE = 32
MAX_COMMENT_LENGTH = 220
COMMENTARY_ENABLED = os.environ.get("AI_BATTLE_COMMENTARY", "1").strip().lower() not in {
    "0", "false", "no", "off",
}
_PROFESSION_NAMES = {
    "warrior": "боец",
    "archer": "лучник",
    "assassin": "асассин",
    "battle_mage": "боевой маг",
    "support_mage": "маг поддержки",
    "harmonist": "гармонист",
}
_QUEUE = queue.Queue(maxsize=COMMENTARY_QUEUE_SIZE)
_LOCK = threading.Lock()
_RECENT_EVENTS = {}
_WORKER_STARTED = False


_SYSTEM_PROMPT = (
    "Ты выбираешь реплику комментатора для русскоязычной RPG. "
    "Событие подтверждено сервером. Выбери ровно одну строку из allowed_lines "
    "и верни её дословно. Не добавляй слова, детали, урон или числа. "
    "Верни только выбранную строку, без кавычек и пояснений."
)


def _clean_text(value, limit=48):
    text = " ".join(str(value or "").split())
    text = "".join(character for character in text if character.isprintable())
    return text[:limit].strip()


def _character_brief(character):
    return {
        "name": _clean_text(character.get("name"), 32) or "Игрок",
        "class": _PROFESSION_NAMES.get(character.get("type"), "путник"),
    }


def _build_event(database, character_id, opponent_id, outcome):
    if outcome not in {"win", "loss", "draw"}:
        return None
    try:
        character_id, opponent_id = int(character_id), int(opponent_id)
    except (TypeError, ValueError):
        return None
    if character_id <= 0 or opponent_id <= 0 or character_id == opponent_id:
        return None

    actor_record = database.get_character_for_battle(character_id)
    opponent_record = database.get_character_for_battle(opponent_id)
    if actor_record is None or opponent_record is None:
        return None
    if actor_record["user_id"] == SYSTEM_USER_ID or opponent_record["user_id"] == SYSTEM_USER_ID:
        return None

    actor = _character_brief(actor_record["character"])
    opponent = _character_brief(opponent_record["character"])
    if outcome == "draw":
        return {"result": "draw", "players": [actor, opponent]}
    winner, loser = (actor, opponent) if outcome == "win" else (opponent, actor)
    return {"result": "win", "winner": winner, "loser": loser}


def _battle_key(world_id, character_id, opponent_id):
    first, second = sorted((int(character_id), int(opponent_id)))
    return int(world_id), first, second


def _claim_event(key, now=None):
    now = time.monotonic() if now is None else float(now)
    with _LOCK:
        expired = [event_key for event_key, stamp in _RECENT_EVENTS.items()
                   if now - stamp >= COMMENTARY_DEDUPE_SECONDS]
        for event_key in expired:
            del _RECENT_EVENTS[event_key]
        previous = _RECENT_EVENTS.get(key)
        if previous is not None and now - previous < COMMENTARY_DEDUPE_SECONDS:
            return False
        _RECENT_EVENTS[key] = now
        return True


def _release_event(key):
    with _LOCK:
        _RECENT_EVENTS.pop(key, None)


def _fallback_comment(event):
    if event["result"] == "draw":
        first, second = event["players"]
        return f"Бой между {first['name']} и {second['name']} завершился вничью."
    return f"Бой завершён: победа {event['winner']['name']} над {event['loser']['name']}."


def _commentary_prompt(event):
    return json.dumps({
        "event": event,
        "allowed_lines": _allowed_comments(event),
    }, ensure_ascii=False, separators=(",", ":"))


def _allowed_comments(event):
    if event["result"] == "draw":
        first, second = (player["name"] for player in event["players"])
        return [
            f"Ничья. Участники: {first} и {second}.",
            f"Победителя нет: {first} и {second} сыграли вничью.",
            f"Дуэль между {first} и {second} завершилась вничью.",
        ]
    winner, loser = event["winner"]["name"], event["loser"]["name"]
    return [
        f"Победитель дуэли: {winner}. Противник: {loser}.",
        f"{winner} выигрывает дуэль. {loser} терпит поражение.",
        f"Дуэль завершена. Победитель: {winner}; второй участник: {loser}.",
    ]


def _generate_allowed_line(context, allowed_lines):
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({
                "event": context,
                "allowed_lines": list(allowed_lines),
            }, ensure_ascii=False, separators=(",", ":"))},
        ],
        "stream": False,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": {"temperature": 0.4, "top_p": 0.85, "num_ctx": 2048, "num_predict": 56},
    }
    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=COMMENTARY_TIMEOUT_SECONDS) as response:
        result = json.loads(response.read().decode("utf-8"))
    message = result.get("message", {}).get("content", "")
    message = re.sub(r"\s+", " ", str(message)).strip().strip("\"'` ")
    message = message[:MAX_COMMENT_LENGTH].strip()
    if message not in allowed_lines:
        raise ValueError("Ollama returned commentary outside the verified templates")
    return message


def _generate_comment(event):
    return _generate_allowed_line(event, _allowed_comments(event))


def _warm_model():
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": "Ответь одним словом: готово.",
        "stream": False,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": {"temperature": 0, "num_ctx": 2048, "num_predict": 1},
    }
    request = urllib.request.Request(
        OLLAMA_URL.removesuffix("/api/chat") + "/api/generate",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=COMMENTARY_TIMEOUT_SECONDS) as response:
            response.read()
        LOGGER.info("Local battle commentator model is warm")
    except Exception as error:
        LOGGER.warning("Could not warm local battle commentator: %s", error)


def prewarm_local_model():
    """Warm the local model asynchronously so first battle commentary is fast."""
    if not COMMENTARY_ENABLED:
        return
    threading.Thread(target=_warm_model, name="local-ai-warmup", daemon=True).start()


def _post_comment(database, event):
    try:
        comment = _generate_comment(event)
    except Exception as error:
        LOGGER.warning("Local battle commentator unavailable: %s", error)
        comment = _fallback_comment(event)
    world_id = int(database.world_id)
    commentator_id = database.ensure_bot_character(
        f"battle-commentator-{world_id}", "Летописец",
    )
    database.add_chat_message(commentator_id, COMMENTARY_LOCATION, comment)


def _post_world_comment(database, event_key, context, allowed_lines):
    key = ("world", int(database.world_id), str(event_key))
    if not _claim_event(key):
        return
    try:
        comment = _generate_allowed_line(context, allowed_lines)
    except Exception as error:
        LOGGER.warning("Local world narrator unavailable: %s", error)
        comment = allowed_lines[0]
    try:
        narrator_id = database.ensure_bot_character(
            f"world-narrator-{int(database.world_id)}", "Летописец",
        )
        database.add_chat_message(narrator_id, "world", comment)
    except Exception:
        _release_event(key)
        raise


def _worker():
    while True:
        task = _QUEUE.get()
        task_type = task[0]
        key = task[-1]
        try:
            if task_type == "battle":
                _process_event(*task[1:])
            else:
                _post_world_comment(*task[1:-1])
        except Exception:
            LOGGER.exception("Could not publish local battle commentary")
            _release_event(key)
        finally:
            _QUEUE.task_done()


def _ensure_worker():
    global _WORKER_STARTED
    with _LOCK:
        if _WORKER_STARTED:
            return
        thread = threading.Thread(target=_worker, name="local-battle-commentator", daemon=True)
        thread.start()
        _WORKER_STARTED = True


def enqueue_battle_comment(database, character_id, opponent_id, outcome):
    """Queue one server-accepted human-versus-human result without blocking HTTP."""
    if not COMMENTARY_ENABLED or outcome not in {"win", "loss", "draw"}:
        return False
    try:
        key = _battle_key(database.world_id, character_id, opponent_id)
    except (TypeError, ValueError):
        return False
    if key[1] <= 0 or key[2] <= 0 or key[1] == key[2]:
        return False
    try:
        _QUEUE.put_nowait(("battle", database, int(character_id), int(opponent_id), str(outcome), key))
    except queue.Full:
        LOGGER.warning("Local battle commentary queue is full; dropping event %s", key)
        return False
    _ensure_worker()
    return True


def enqueue_world_comment(database, event_key, context, allowed_lines):
    """Queue a server-observed world event for the server-only global chat feed."""
    if not COMMENTARY_ENABLED or not event_key:
        return False
    lines = tuple(str(line).strip()[:MAX_COMMENT_LENGTH] for line in allowed_lines)
    if not 1 <= len(lines) <= 5 or any(not line for line in lines):
        return False
    key = ("world", int(database.world_id), str(event_key))
    try:
        _QUEUE.put_nowait(("world", database, str(event_key), context, lines, key))
    except queue.Full:
        LOGGER.warning("Local world narrator queue is full; dropping event %s", key)
        return False
    _ensure_worker()
    return True


def _process_event(database, character_id, opponent_id, outcome, key):
    event = _build_event(database, character_id, opponent_id, outcome)
    if event is None:
        _release_event(key)
        return
    if not _claim_event(key):
        return
    _post_comment(database, event)
