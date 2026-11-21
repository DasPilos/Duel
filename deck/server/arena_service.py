"""Серверная часть арены: проверка персонажа, награды после боя и возрождение противников.

Награды и здоровье повторяют _claim_npc_kill_xp и _finish_arena в deck/scenes/world_map_scene.py.
Возрождение (KOBOLD_RESPAWN_SECONDS, у древнего энта навсегда) раньше жило только в клиенте;
теперь его проверяет сервер, чтобы опыт нельзя было фармить повторными боями.
Возрождение, как и сами бои, хранится в памяти процесса.
"""

import math
import threading
import time

from deck.map_config import KOBOLD_RESPAWN_SECONDS, RESPAWN_CRYSTAL, TILE_SIZE
from deck.server.arena import (
    DUNGEON_APPROACH_POSITION,
    DUNGEON_ROOM_BATTLES,
    ENCOUNTERS,
    ArenaError,
    ArenaRegistry,
    dungeon_actor_tile,
    dungeon_room_contains,
    session_view,
)

PERMANENT = math.inf
CRYSTAL_POSITION = RESPAWN_CRYSTAL["approach_pos"]


def _tile(x, y):
    return int(x // TILE_SIZE), int(y // TILE_SIZE)


def _chebyshev(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _position(character):
    x, y = character.get("position_x"), character.get("position_y")
    if x is None or y is None:
        raise ArenaError("Положение персонажа на карте не известно")
    return float(x), float(y)


def _vitals_payload(character, finished):
    """Здоровье и место после боя: победа оставляет игрока на месте, поражение и телепорт — у кристалла."""
    result = finished["result"]
    if result == "loss":
        payload = {"hp": int(character["max_hp"]), "mp": finished["player_mp"]}
    else:
        payload = {"hp": max(1, finished["player_hp"]), "mp": finished["player_mp"]}
    if result != "win":
        x, y = CRYSTAL_POSITION
        payload.update(position_x=float(x), position_y=float(y), position_direction="s")
    return payload


def _dungeon_vitals_payload(character, finished):
    """Подземелье: победа сохраняет здоровье, поражение — полное здоровье, телепорт — только место. Всё у входа, как exit_dungeon."""
    result = finished["result"]
    if result == "win":
        return {"hp": max(1, finished["player_hp"]), "mp": finished["player_mp"]}
    x, y = DUNGEON_APPROACH_POSITION
    payload = {"position_x": float(x), "position_y": float(y), "position_direction": "s"}
    if result == "loss":
        payload.update(hp=int(character["max_hp"]), mp=finished["player_mp"])
    return payload


class ArenaService:
    def __init__(self, database, items_database, registry=None):
        self.database = database
        self.items_database = items_database
        self.registry = registry or ArenaRegistry()
        self._lock = threading.Lock()
        self._respawn_at = {}
        self._dungeon_runs = {}

    def start(self, user_id, character_id, source, *, now=None, seed=None, position_x=None, position_y=None):
        now = time.time() if now is None else now
        character, deck_keys = self._battle_inputs(user_id, character_id)
        if source in DUNGEON_ROOM_BATTLES:
            return self._start_dungeon_battle(character, deck_keys, source, position_x, position_y, now, seed)
        encounter = ENCOUNTERS.get(source)
        if encounter is None:
            raise ArenaError("Этот противник не участвует в бою на арене")
        if character.get("zone") != "world_map":
            raise ArenaError("Бой на арене начинается на карте мира")
        if not self.alive(character["id"], source, now):
            raise ArenaError("Противник ещё не возродился")
        x, y = _position(character)
        if _chebyshev(_tile(x, y), encounter["tile"]) > encounter["radius"]:
            raise ArenaError("Подойдите ближе к противнику")
        session = self.registry.start(
            character, source=source, position_x=x, position_y=y,
            equipment=character.get("equipment"), deck_keys=deck_keys, seed=seed, now=now,
        )
        return session_view(session)

    def _start_dungeon_battle(self, character, deck_keys, source, position_x, position_y, now, seed):
        """Бой в комнате подземелья: нужен вход в подземелье, порядок комнат и игрок рядом с противником внутри комнаты."""
        character_id = int(character["id"])
        with self._lock:
            run = self._dungeon_runs.get(character_id)
        if run is None:
            raise ArenaError("Сначала войдите в подземелье")
        if source in run:
            raise ArenaError("Эта комната уже пройдена")
        previous = DUNGEON_ROOM_BATTLES[source]["previous"]
        if previous is not None and previous not in run:
            raise ArenaError("Сначала пройдите предыдущую комнату")
        if position_x is None or position_y is None:
            raise ArenaError("Подойдите ближе к противнику")
        x, y = float(position_x), float(position_y)
        tile = _tile(x, y)
        if not dungeon_room_contains(tile):
            raise ArenaError("Игрок должен стоять в комнате подземелья")
        if _chebyshev(tile, dungeon_actor_tile()) > 1:
            raise ArenaError("Подойдите ближе к противнику")
        session = self.registry.start(
            character, source=source, position_x=x, position_y=y,
            equipment=character.get("equipment"), deck_keys=deck_keys, seed=seed, now=now,
        )
        return session_view(session)

    def dungeon_enter(self, character_id):
        """Новый проход подземелья: все комнаты снова не пройдены."""
        character_id = int(character_id)
        with self._lock:
            if self.registry.active(character_id) is not None:
                raise ArenaError("Сначала завершите бой на арене")
            self._dungeon_runs[character_id] = set()
        return {"rooms": []}

    def dungeon_exit(self, character_id):
        character_id = int(character_id)
        with self._lock:
            if self.registry.active(character_id) is not None:
                raise ArenaError("Сначала завершите бой на арене")
            self._dungeon_runs.pop(character_id, None)
        return {"ok": True}

    def active(self, character_id, *, now=None):
        session = self.registry.active(character_id, now=now)
        return None if session is None else session_view(session)

    def status(self, character_id, *, now=None):
        now = time.time() if now is None else now
        return [self._encounter_status(character_id, source, now) for source in ENCOUNTERS]

    def action(self, user_id, character_id, session_id, command, *, now=None):
        now = time.time() if now is None else now
        outcome = self.registry.command(
            character_id, session_id, command, remove_item=self._take_item, now=now,
        )
        finished = outcome["finished"]
        if finished is not None:
            finished = self.apply_rewards(user_id, character_id, finished, now=now)
        return {
            "notice": outcome["result"]["notice"],
            "log": outcome["result"]["log"],
            "state": outcome["state"],
            "finished": finished,
        }

    def apply_rewards(self, user_id, character_id, finished, *, now=None):
        """Опыт за убитых, здоровье и место после боя; возвращает итог для клиента."""
        now = time.time() if now is None else now
        source = finished["encounter_id"]
        dungeon = source in DUNGEON_ROOM_BATTLES
        if dungeon:
            self._finish_dungeon_run(character_id, source, finished)
        elif finished["result"] == "win":
            self._mark_defeated(character_id, source, now)
        report = {key: value for key, value in finished.items() if key != "reward_request_id"}
        report.update(xp_awarded=0, xp_error=None, save_error=None)
        if finished["defeated_npc_types"]:
            try:
                claim = self.database.report_npc_kill_xp(
                    user_id, character_id, source, finished["defeated_npc_types"], finished["reward_request_id"],
                )
                report["xp_awarded"] = int(claim["xp"])
            except Exception as error:
                report["xp_error"] = f"Опыт не начислен: {error}"
        try:
            character = self.database.get_character(user_id, character_id)
            payload = _dungeon_vitals_payload(character, finished) if dungeon else _vitals_payload(character, finished)
            self.database.save_character(user_id, character_id, payload)
        except Exception as error:
            report["save_error"] = f"Здоровье не сохранено: {error}"
        try:
            report["character"] = self.database.get_character(user_id, character_id)
        except Exception:
            report["character"] = None
        return report

    def _finish_dungeon_run(self, character_id, source, finished):
        """Победа засчитывает комнату; поражение и телепорт завершают проход подземелья."""
        character_id = int(character_id)
        with self._lock:
            run = self._dungeon_runs.get(character_id)
            if run is None:
                return
            if finished["result"] == "win":
                run.add(source)
            else:
                self._dungeon_runs.pop(character_id, None)

    def alive(self, character_id, source, now):
        with self._lock:
            respawn = self._respawn_at.get((int(character_id), source))
        return respawn is None or now >= respawn

    def _take_item(self, character_id, item_id, quantity):
        if not self.items_database.remove_from_inventory(character_id, item_id, quantity):
            raise ArenaError("Предмет не найден в инвентаре")

    def _mark_defeated(self, character_id, source, now):
        respawn = PERMANENT if source == "ancient_ent" else now + KOBOLD_RESPAWN_SECONDS
        with self._lock:
            self._respawn_at[(int(character_id), source)] = respawn

    def _encounter_status(self, character_id, source, now):
        with self._lock:
            respawn = self._respawn_at.get((int(character_id), source))
        if respawn is None or now >= respawn:
            return {"source": source, "alive": True, "respawn_in": None}
        if respawn == PERMANENT:
            return {"source": source, "alive": False, "respawn_in": None}
        return {"source": source, "alive": False, "respawn_in": math.ceil(respawn - now)}

    def _battle_inputs(self, user_id, character_id):
        battle_character = self.database.get_character_for_battle(int(character_id))
        if battle_character is None or battle_character["user_id"] != user_id:
            raise ArenaError("Персонаж не найден")
        active_deck = self.items_database.get_active_deck(int(character_id))
        return battle_character["character"], (active_deck["cards"] if active_deck else None)
