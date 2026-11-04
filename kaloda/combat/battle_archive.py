"""Запись завершённого боя для архива сервера.

Клиент собирает запись и отправляет её вместе с результатом боя; сервер сохраняет её в таблицу battle_archive.
Файлов на диске больше не пишем.
"""
import time
import uuid


def _fighter_snapshot(fighter):
    return {
        "name": fighter.name,
        "level": fighter.level,
        "stats": dict(fighter.stats),
        "hp": fighter.hp,
        "max_hp": fighter.max_hp,
    }


def build_battle_record(battle, *, source, extra=None):
    """Return the portable JSON payload for a finished battle."""
    record = {
        "battle_version": 2 if hasattr(battle, "hands") else 1,
        "id": uuid.uuid4().hex,
        "timestamp": time.time(),
        "source": source,
        "turns": battle.turn,
        "winner": battle.winner_name(),
        "player": _fighter_snapshot(battle.player),
        "enemy": _fighter_snapshot(battle.enemy),
        "stats": battle.stats,
    }
    if hasattr(battle, "hands"):
        record["hands"] = {
            side: [card.key for card in cards]
            for side, cards in battle.hands.items()
        }
        record["history"] = battle.history
    if extra:
        record.update(extra)
    return record
