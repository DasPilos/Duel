"""Генерирует эталон арены для клиента Godot: состояния боя сервера и геометрию оверлея Python.

Запуск из корня репозитория:  python scripts/export_deck_arena_samples.py

Пишет godot_client/tests/deck_arena_samples.json:
  states   — виды боя из deck/server/arena.py (набор, бой, босс, итог);
  geometry — клетки, центры и шестиугольники из ArenaController (deck/ui/arena_overlay.py);
  hex      — расстояния и соседи из deck/combat/arena_battle.py для проверки deck_arena_rules.gd.
"""

import json
import os
import sys
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES_PATH = os.path.join(ROOT, "godot_client", "tests", "deck_arena_samples.json")

sys.path.insert(0, ROOT)

import pygame  # noqa: E402

pygame.init()

from deck.combat.arena_battle import hex_distance, hex_neighbors  # noqa: E402
from deck.combat.card_database import class_cards_for_type  # noqa: E402
from deck.map_config import TILE_SIZE  # noqa: E402
from deck.server import arena  # noqa: E402
from deck.ui.arena_overlay import ArenaController  # noqa: E402

# Тот же персонаж, что в tests/deck/test_deck_arena_server.py.
PROFILE = {
    "id": 7,
    "name": "Тест",
    "level": 5,
    "type": "warrior",
    "stats": {"strength": 6, "agility": 4, "intuition": 3, "wisdom": 2, "intellect": 2, "harmony": 2, "endurance": 6},
    "hp": 60,
    "mp": 20,
    "talents": {},
    "xp": 0,
    "stat_points": 0,
}
DECK_KEYS = [card.key for card in class_cards_for_type("warrior")]
INVENTORY = [
    {"item_id": 2, "name": "Зелье здоровья", "quantity": 1},
    {"item_id": 4, "name": "Зелье восстановления здоровья", "quantity": 2},
    {"item_id": 5, "name": "Зелье восстановления маны", "quantity": 1},
    {"item_id": 6, "name": "Метательный кинжал", "quantity": 1},
]


def start(source, seed=1):
    tile = arena.ENCOUNTERS[source]["tile"]
    return arena.start_session(
        PROFILE,
        source=source,
        position_x=(tile[0] + 1) * TILE_SIZE + 24,
        position_y=tile[1] * TILE_SIZE + 24,
        equipment={},
        deck_keys=DECK_KEYS,
        seed=seed,
    )


def finish_draft(session):
    while arena.session_view(session)["phase"] == "draft":
        key = arena.session_view(session)["draft_cards"][0]["key"]
        arena.apply_command(session, {"type": "draft", "card_key": key})


def overlay_geometry(battle, tiles):
    controller = ArenaController.__new__(ArenaController)
    controller.battle = battle
    controller.center_world = (0.0, 0.0)
    controller.scene = SimpleNamespace(tile_size=TILE_SIZE)
    rows = []
    for tile in tiles:
        center_x, center_y = controller.tile_center(tile)
        polygon = controller.tile_polygon(tile)
        rows.append({
            "tile": list(tile),
            "center": [center_x, center_y],
            "polygon": [list(point) for point in polygon],
        })
    return rows


def attack_state():
    """Вид в начале хода, когда карта атаки уже доступна: игрок идёт к врагу и завершает ходы."""
    session = start("kobold")
    finish_draft(session)
    for _ in range(40):
        view = arena.session_view(session)
        if view["phase"] == "draw_choice":
            arena.apply_command(session, {"type": "draw_choice", "card_key": view["draw_choices"][0]["key"]})
            continue
        if any(card["role"] == "enemy" and card.get("playable") for card in view["hand"]):
            return view
        if view["result"]:
            break
        enemy = session.battle.positions[session.battle.enemy_ids[0]]
        if view["can_move"]:
            tile = min(view["reachable"], key=lambda item: arena.hex_distance(tuple(item), enemy))
            arena.apply_command(session, {"type": "move", "tile": tile})
        if session.battle.active_side == "player" and not session.battle.is_over():
            arena.apply_command(session, {"type": "end_turn"})
    raise SystemExit("Эталон атаки: за 40 ходов карта атаки не стала доступной")


def main():
    battle_session = start("kobold")
    finish_draft(battle_session)
    battle = battle_session.battle
    board = [tile for tile in arena.session_view(battle_session)["tiles"]]
    tiles = [tuple(tile) for tile in board]

    states = {
        "draft": arena.session_view(start("kobold")),
        "battle": arena.session_view(battle_session),
        "attack": attack_state(),
    }
    boss_session = start("ancient_ent")
    finish_draft(boss_session)
    states["boss"] = arena.session_view(boss_session)

    result_session = start("kobold")
    finish_draft(result_session)
    arena.apply_command(result_session, {"type": "teleport"})
    states["result"] = arena.session_view(result_session)
    if states["result"]["result"] != "teleport":
        raise SystemExit("Эталон итога: телепорт должен завершить бой результатом teleport")
    finished = arena.finish_report(result_session)

    sample_tiles = tiles[:8]
    hex_pairs = [
        {"a": list(a), "b": list(b), "distance": hex_distance(a, b)}
        for a in sample_tiles for b in tiles[:12]
    ]
    neighbors = [{"tile": list(t), "neighbors": [list(n) for n in hex_neighbors(t)]} for t in sample_tiles]

    data = {
        "center": list(battle.arena_center),
        "tile_size": TILE_SIZE,
        "geometry": overlay_geometry(battle, sample_tiles),
        "hex_pairs": hex_pairs,
        "neighbors": neighbors,
        "states": states,
        "finished": finished,
        "inventory": INVENTORY,
    }
    os.makedirs(os.path.dirname(SAMPLES_PATH), exist_ok=True)
    with open(SAMPLES_PATH, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=1)
        file.write("\n")


if __name__ == "__main__":
    main()
