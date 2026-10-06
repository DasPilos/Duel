"""World-map rendering helpers for traveling citizens and wagon convoys."""

import math
import time
from pathlib import Path

import pygame

from core import settings


ROAD_BUILDING_IDS = {
    "farm": "wheat_farm",
    "lumber_camp": "lumber_camp",
    "mountain_rift": "mountain_rift",
    "barnyard": "barnyard",
    "black_pit": "black_pit",
}

_WAGON_IMAGE = None
_WAGON_IMAGE_LOADED = False


def route_position(tiles, progress, tile_size):
    points = [((float(tile[0]) + 0.5) * tile_size,
               (float(tile[1]) + 0.5) * tile_size) for tile in tiles]
    if not points:
        return None
    if len(points) == 1:
        return points[0][0], points[0][1], "s"
    segments = [(a, b, math.hypot(b[0] - a[0], b[1] - a[1]))
                for a, b in zip(points, points[1:])]
    total = sum(length for _a, _b, length in segments)
    if total <= 0:
        return points[0][0], points[0][1], "s"
    distance = max(0.0, min(1.0, float(progress))) * total
    for start, end, length in segments:
        if distance <= length:
            fraction = 0.0 if length == 0 else distance / length
            dx, dy = end[0] - start[0], end[1] - start[1]
            direction = "s"
            if abs(dx) > abs(dy) * 2:
                direction = "e" if dx > 0 else "w"
            elif abs(dy) > abs(dx) * 2:
                direction = "s" if dy > 0 else "n"
            elif dx and dy:
                direction = ("s" if dy > 0 else "n") + ("e" if dx > 0 else "w")
            return start[0] + dx * fraction, start[1] + dy * fraction, direction
        distance -= length
    return points[-1][0], points[-1][1], "s"


def _route(scene, building):
    route_id = ROAD_BUILDING_IDS.get(str(building), str(building))
    return next((route for route in getattr(scene, "road_routes", [])
                 if route.get("building_id") == route_id), None)


def traveling_entities(scene, location="world_map"):
    chat = getattr(scene, "chat", None)
    if chat is None or location != "world_map":
        return []
    result = []
    for citizen in getattr(chat, "travelers", []):
        if citizen.get("position_x") is None or citizen.get("position_y") is None:
            continue
        result.append({
            **citizen,
            "entity_kind": "citizen",
            "eta_seconds": int(citizen.get("eta_seconds", citizen.get("travel_seconds_left", 0))),
        })

    for convoy in getattr(chat, "traveling_convoys", []):
        route = _route(scene, convoy.get("destination_building_id", convoy.get("building_id")))
        if not route or not route.get("tiles"):
            continue
        eta = max(0, int(convoy.get("seconds_remaining", 0)
                         - max(0.0, time.monotonic() - float(getattr(chat, "convoys_received_at", 0)))))
        total = max(1, int(convoy.get("travel_seconds", convoy.get("total_seconds", eta or 1))))
        direction = convoy.get("direction", "outbound")
        progress = convoy.get("progress_percent")
        if progress is None:
            progress = 100 * (1 - eta / total if direction == "outbound" else eta / total)
        position = route_position(route["tiles"], float(progress) / 100, scene.tile_size)
        if position is None:
            continue
        result.append({
            **convoy,
            "entity_kind": "wagon",
            "position_x": position[0],
            "position_y": position[1],
            "position_direction": position[2],
            "eta_seconds": eta,
            "route_name": convoy.get("route_name", route.get("name", "Маршрут")),
            "movement_text": "Едет к загородному объекту" if direction == "outbound" else "Возвращается в город",
        })
    return result


def mobile_entity_at(scene, screen_position, location="world_map"):
    from ui.afk_presence import active_player_entities

    x, y = screen_position
    for occupant in active_player_entities(scene, location):
        sx, sy = scene.world_to_screen(occupant["position_x"], occupant["position_y"])
        if pygame.Rect(sx - 22, sy - 58, 44, 62).collidepoint(x, y):
            return {**occupant, "entity_kind": "player", "eta_seconds": None}
    for entity in traveling_entities(scene, location):
        sx, sy = scene.world_to_screen(entity["position_x"], entity["position_y"])
        if pygame.Rect(sx - 20, sy - 34, 40, 38).collidepoint(x, y):
            return entity
    return None


def _wagon_image(size):
    global _WAGON_IMAGE, _WAGON_IMAGE_LOADED
    if not _WAGON_IMAGE_LOADED:
        path = Path(__file__).resolve().parent.parent / "assets" / "ui" / "wagon_placeholder.png"
        try:
            _WAGON_IMAGE = pygame.image.load(str(path)).convert_alpha()
        except (pygame.error, OSError, FileNotFoundError):
            _WAGON_IMAGE = None
        _WAGON_IMAGE_LOADED = True
    if _WAGON_IMAGE is None:
        return None
    return pygame.transform.smoothscale(_WAGON_IMAGE, size)


def draw_traveling_entities(scene, screen, location="world_map"):
    entities = traveling_entities(scene, location)
    for entity in entities:
        sx, sy = scene.world_to_screen(entity["position_x"], entity["position_y"])
        if not (-80 <= sx <= settings.WIDTH + 80 and -100 <= sy <= settings.HEIGHT + 20):
            continue
        if entity["entity_kind"] == "wagon":
            sprite = _wagon_image((42, 30))
            if sprite is not None:
                screen.blit(sprite, sprite.get_rect(center=(sx, sy - 8)))
            else:
                pygame.draw.rect(screen, (130, 84, 45), (sx - 16, sy - 22, 32, 16), border_radius=3)
                pygame.draw.circle(screen, (48, 42, 34), (sx - 10, sy - 3), 5)
                pygame.draw.circle(screen, (48, 42, 34), (sx + 10, sy - 3), 5)
        else:
            direction = entity.get("position_direction", "s")
            frames = getattr(scene, "player_run_directional_frames", {}).get(direction, [])
            if not frames:
                frames = getattr(scene, "player_directional_frames", {}).get(direction, [])
            if frames:
                frame = frames[int(time.monotonic() * 8) % len(frames)]
                screen.blit(frame, frame.get_rect(midbottom=(sx, sy)))
            else:
                pygame.draw.ellipse(screen, (13, 15, 17), (sx - 10, sy - 3, 20, 7))
                pygame.draw.circle(screen, (217, 188, 151), (sx, sy - 20), 6)
                pygame.draw.rect(screen, (112, 133, 103), (sx - 5, sy - 14, 10, 14), border_radius=2)
        name = entity.get("cart_name", entity.get("name", "Повозка"))
        label = scene.grid_font.render(str(name), True, (237, 214, 164))
        screen.blit(label, label.get_rect(midbottom=(sx, sy - 28)))


def draw_mobile_hover_card(scene, screen, entity):
    if entity.get("entity_kind") == "player":
        from ui.character_card import CharacterCard

        profile = dict(entity)
        profile["id"] = entity.get("character_id", entity.get("id"))
        profile["character_id"] = profile["id"]
        card = CharacterCard.get_or_create(profile["id"])
        card.draw(screen, pygame.Rect(settings.ENEMY_CARD_RECT), profile=profile,
                  border_color=(95, 174, 225), title="ИГРОК РЯДОМ", editable=False)
        return
    lines = [
        (entity.get("cart_name", entity.get("name", "Горожанин")), (244, 217, 164)),
        (entity.get("movement_text", "В пути"), (128, 203, 245)),
        (f"Маршрут: {entity.get('route_name', '—')}", (210, 210, 196)),
    ]
    if entity.get("entity_kind") == "citizen":
        lines.append((f"Работа: {entity.get('job_building', '—')}", (188, 207, 181)))
        lines.append(("Груз: нет", (190, 190, 180)))
    else:
        cargo = entity.get("cargo", {})
        if isinstance(cargo, dict):
            cargo_text = ", ".join(f"{name}: {amount}" for name, amount in cargo.items()) or "нет"
        else:
            cargo_text = str(cargo or "нет")
        lines.append((f"Груз: {cargo_text}", (217, 197, 155)))
    lines.append((f"До прибытия: {int(entity.get('eta_seconds', 0)) // 60} мин",
                  (192, 205, 180)))
    width, line_height, padding = 340, 22, 12
    mouse_x, mouse_y = pygame.mouse.get_pos()
    height = padding * 2 + len(lines) * line_height
    left = min(mouse_x + 16, screen.get_width() - width - 8)
    top = min(mouse_y + 16, screen.get_height() - height - 8)
    panel = pygame.Rect(max(8, left), max(8, top), width, height)
    pygame.draw.rect(screen, (18, 24, 32), panel, border_radius=6)
    pygame.draw.rect(screen, (80, 190, 255), panel, 2, border_radius=6)
    for index, (text, color) in enumerate(lines):
        screen.blit(scene.small_font.render(str(text), True, color),
                    (panel.left + padding, panel.top + padding + index * line_height))