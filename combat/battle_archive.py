"""Persists finished battles to disk so real fights can be analyzed for balance,
the same way tests/balance_simulation.py analyzes simulated ones."""
import json
import time
import uuid
from pathlib import Path

ARCHIVE_DIR = Path(__file__).resolve().parent.parent / "battle_archive"


def _fighter_snapshot(fighter):
    return {
        "name": fighter.name,
        "level": fighter.level,
        "stats": dict(fighter.stats),
        "hp": fighter.hp,
        "max_hp": fighter.max_hp,
    }


def record_battle(battle, *, source, extra=None):
    """Write one finished Battle as a JSON file under battle_archive/."""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "id": uuid.uuid4().hex,
        "timestamp": time.time(),
        "source": source,
        "turns": battle.turn,
        "winner": battle.winner_name(),
        "player": _fighter_snapshot(battle.player),
        "enemy": _fighter_snapshot(battle.enemy),
        "stats": battle.stats,
    }
    if extra:
        record.update(extra)
    path = ARCHIVE_DIR / f"{int(record['timestamp'])}_{record['id']}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_battles():
    """Read every archived battle record, oldest first."""
    if not ARCHIVE_DIR.exists():
        return []
    records = []
    for path in sorted(ARCHIVE_DIR.glob("*.json")):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return records
