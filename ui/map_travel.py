"""World-map rendering helpers for traveling citizens and wagon convoys."""

import math
import time
from pathlib import Path

import pygame

from core import settings
from core.production_buildings import PRODUCTION_ITEM_IDS, RESOURCES


ROAD_BUILDING_IDS = {
    "farm": "wheat_farm",
    "lumber_camp": "lumber_camp",
    "mountain_rift": "mountain_rift",
    "barnyard": "barnyard",
    "black_pit": "black_pit",
}

_TRANSPORT_SPRITES = {}


def _format_eta(seconds):
    hours, remainder = divmod(max(0, int(seconds)), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _format_phase_eta(entity):
    phase = entity.get("phase")
    labels = {
        "loading": "До конца погрузки",
        "unloading": "До конца разгрузки",
        "resting": "До конца пополнения провизии",
        "waiting_for_resources": "Повторная проверка через",
    }
    label = labels.get(phase, "До прибытия")
    return f"{label}: {_format_eta(entity.get('eta_seconds', 0))}"


def _route_progress_percent(entity):
    progress = entity.get("progress_percent")
    if progress is None:
        total = max(1, int(entity.get("travel_seconds", entity.get("total_seconds", 1))))
        eta = max(0, int(entity.get("eta_seconds", entity.get("seconds_remaining", 0))))
        direction = entity.get("direction", "outbound")
        progress = 100 * (1 - eta / total if direction == "outbound" else eta / total)
    return max(0, min(100, int(round(float(progress)))))


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
        progress = _route_progress_percent({**convoy, "seconds_remaining": eta})
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
            "progress_percent": progress,
            "route_name": convoy.get("route_name", route.get("name", "Маршрут")),
            "movement_text": convoy.get("movement_text", convoy.get(
                "status", "Едет к загородному объекту" if direction == "outbound"
                else "Возвращается в город",
            )),
        })
    _separate_nearby_convoys(result, scene.tile_size)
    return result


def _separate_nearby_convoys(entities, tile_size):
    convoys = [
        entity for entity in entities
        if entity.get("entity_kind") == "wagon"
    ]
    remaining = set(range(len(convoys)))
    directions = {
        "n": (0, -1), "ne": (0.707, -0.707), "e": (1, 0), "se": (0.707, 0.707),
        "s": (0, 1), "sw": (-0.707, 0.707), "w": (-1, 0), "nw": (-0.707, -0.707),
    }
    close_distance = max(1.0, float(tile_size) * 1.5)
    lane_spacing = max(1.0, float(tile_size) * 0.9)
    while remaining:
        anchor_index = min(remaining)
        anchor = convoys[anchor_index]
        cluster = [
            index for index in remaining
            if convoys[index].get("destination_building_id")
            == anchor.get("destination_building_id")
            and math.hypot(
                float(convoys[index]["position_x"]) - float(anchor["position_x"]),
                float(convoys[index]["position_y"]) - float(anchor["position_y"]),
            ) <= close_distance
        ]
        remaining.difference_update(cluster)
        if len(cluster) < 2:
            continue
        direction = anchor.get("position_direction", "s")
        dx, dy = directions.get(direction, (0, 1))
        perpendicular = (-dy, dx)
        cluster.sort(key=lambda index: str(convoys[index].get("id", index)))
        midpoint = (len(cluster) - 1) / 2
        for lane, index in enumerate(cluster):
            entity = convoys[index]
            offset = (lane - midpoint) * lane_spacing
            entity["display_position_x"] = float(entity["position_x"]) + perpendicular[0] * offset
            entity["display_position_y"] = float(entity["position_y"]) + perpendicular[1] * offset


def mobile_entity_at(scene, screen_position, location="world_map"):
    from ui.afk_presence import active_player_entities

    x, y = screen_position
    for occupant in active_player_entities(scene, location):
        sx, sy = scene.world_to_screen(occupant["position_x"], occupant["position_y"])
        if pygame.Rect(sx - 22, sy - 58, 44, 62).collidepoint(x, y):
            return {**occupant, "entity_kind": "player", "eta_seconds": None}
    for entity in traveling_entities(scene, location):
        sx, sy = scene.world_to_screen(
            entity.get("display_position_x", entity["position_x"]),
            entity.get("display_position_y", entity["position_y"]),
        )
        if pygame.Rect(sx - 34, sy - 48, 68, 64).collidepoint(x, y):
            return entity
    return None


def _transport_sprite(name, size, direction="n"):
    key = (name, int(size), direction)
    if key in _TRANSPORT_SPRITES:
        return _TRANSPORT_SPRITES[key]
    path = Path(__file__).resolve().parent.parent / "assets" / "ui" / "transport" / f"{name}.png"
    try:
        image = pygame.image.load(str(path)).convert_alpha()
        image = pygame.transform.smoothscale(image, (int(size), int(size)))
        vectors = {
            "n": (0, -1), "ne": (1, -1), "e": (1, 0), "se": (1, 1),
            "s": (0, 1), "sw": (-1, 1), "w": (-1, 0), "nw": (-1, -1),
        }
        dx, dy = vectors.get(direction, (0, -1))
        angle = math.degrees(math.atan2(dx, -dy))
        sprite = pygame.transform.rotate(image, -angle) if angle else image
    except (pygame.error, OSError, FileNotFoundError):
        sprite = None
    _TRANSPORT_SPRITES[key] = sprite
    return sprite


def _blit_transport_sprite(screen, name, size, center, direction="n"):
    sprite = _transport_sprite(name, size, direction)
    if sprite is not None:
        screen.blit(sprite, sprite.get_rect(center=(round(center[0]), round(center[1]))))


def draw_transport_cart_icon(screen, sprite_key="light", position=(0, 0), size=24):
    sprite = _transport_sprite(f"cart_{sprite_key}", size, "n")
    if sprite is None:
        return None
    rect = sprite.get_rect(topleft=(round(position[0]), round(position[1])))
    screen.blit(sprite, rect)
    return rect


def draw_transport_horse_icon(screen, position=(0, 0), size=32):
    sprite = _transport_sprite("horse", size, "n")
    if sprite is None:
        return None
    rect = sprite.get_rect(topleft=(round(position[0]), round(position[1])))
    screen.blit(sprite, rect)
    return rect


def draw_convoy_sprite_group(screen, center, sprite_key="light", direction="w", size=96, spacing=None):
    vectors = {
        "n": (0, -1), "ne": (0.707, -0.707), "e": (1, 0), "se": (0.707, 0.707),
        "s": (0, 1), "sw": (-0.707, 0.707), "w": (-1, 0), "nw": (-0.707, -0.707),
    }
    dx, dy = vectors.get(direction, (-1, 0))
    spacing = max(10, int(size * 0.48)) if spacing is None else int(spacing)
    wagon_center = (center[0] - dx * spacing, center[1] - dy * spacing)
    horse_center = (center[0] + dx * spacing, center[1] + dy * spacing)
    _blit_transport_sprite(screen, f"cart_{sprite_key}", size, wagon_center, direction)
    _blit_transport_sprite(screen, f"harness_{sprite_key}", size, center, direction)
    _blit_transport_sprite(screen, "horse", size, horse_center, direction)
    _blit_transport_sprite(screen, "driver", max(10, size // 2), wagon_center, direction)
    return {"wagon": wagon_center, "horse": horse_center, "harness": center}


def draw_traveling_entities(scene, screen, location="world_map"):
    entities = traveling_entities(scene, location)
    for entity in entities:
        sx, sy = scene.world_to_screen(
            entity.get("display_position_x", entity["position_x"]),
            entity.get("display_position_y", entity["position_y"]),
        )
        if not (-80 <= sx <= settings.WIDTH + 80 and -100 <= sy <= settings.HEIGHT + 20):
            continue
        if entity["entity_kind"] == "wagon":
            direction = entity.get("position_direction", "s")
            vectors = {
                "n": (0, -1), "ne": (0.707, -0.707), "e": (1, 0), "se": (0.707, 0.707),
                "s": (0, 1), "sw": (-0.707, 0.707), "w": (-1, 0), "nw": (-0.707, -0.707),
            }
            dx, dy = vectors.get(direction, (0, 1))
            size = max(16, int(scene.tile_size * 0.7))
            sprite_key = entity.get("cart_sprite_key", "light")
            draw_convoy_sprite_group(
                screen, (sx, sy), sprite_key, direction, size,
                spacing=max(10, int(scene.tile_size * 0.32)),
            )
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
        label_rect = label.get_rect(midbottom=(sx, sy - 28))
        sprite_key = entity.get("cart_sprite_key", "light")
        icon_size = 32
        icon_rect = draw_transport_cart_icon(
            screen, sprite_key,
            (label_rect.left - icon_size - 4, label_rect.centery - icon_size // 2),
            icon_size,
        )
        if icon_rect is not None:
            label_rect.left = icon_rect.right + 4
        screen.blit(label, label_rect)


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
    if entity.get("entity_kind") == "wagon":
        _draw_wagon_hover_card(scene, screen, entity)
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
        lines.append((f"Экипаж: {entity.get('driver_name', '—')}", (188, 207, 181)))
        horses = ", ".join(horse.get("name", "Лошадь") for horse in entity.get("horses", [])) or "—"
        lines.append((f"Лошади: {horses}", (188, 207, 181)))
        cargo = entity.get("cargo", {})
        if isinstance(cargo, list):
            cargo_text = ", ".join(
                f"{slot.get('resource_id', 'ресурс')}: {slot.get('quantity', 0)}"
                for slot in cargo
            ) or "нет"
        elif isinstance(cargo, dict):
            cargo_text = ", ".join(f"{name}: {amount}" for name, amount in cargo.items()) or "нет"
        else:
            cargo_text = str(cargo or "нет")
        lines.append((f"Груз: {cargo_text}", (217, 197, 155)))
    lines.append((_format_phase_eta(entity),
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
        line_y = panel.top + padding + index * line_height
        screen.blit(scene.small_font.render(str(text), True, color), (panel.left + padding, line_y))


def _draw_wagon_hover_card(scene, screen, entity):
    width, padding, line_height = 340, 12, 36
    bar_height, bar_gap = 8, 5
    content_height = padding * 2 + line_height * 6 + bar_gap + bar_height + 1
    mouse_x, mouse_y = pygame.mouse.get_pos()
    left = min(mouse_x + 16, screen.get_width() - width - 8)
    top = min(mouse_y + 16, screen.get_height() - content_height - 8)
    panel = pygame.Rect(max(8, left), max(8, top), width, content_height)
    pygame.draw.rect(screen, (18, 24, 32), panel, border_radius=6)
    pygame.draw.rect(screen, (80, 190, 255), panel, 2, border_radius=6)

    line_y = panel.top + padding
    icon = draw_transport_cart_icon(
        screen, entity.get("cart_sprite_key", "light"),
        (panel.left + padding, line_y), 32,
    )
    cart_label = str(entity.get("cart_name", entity.get("name", "Лёгкая повозка")))
    screen.blit(scene.small_font.render(cart_label, True, (244, 217, 164)),
                (icon.right + 6 if icon else panel.left + padding, line_y + 8))
    line_y += line_height

    movement = str(entity.get("movement_text", entity.get("status", "В пути")))
    screen.blit(scene.small_font.render(movement, True, (128, 203, 245)),
                (panel.left + padding, line_y))
    line_y += line_height

    route_name = str(entity.get("route_name", "—"))
    route_text = f"Маршрут: {route_name}"
    screen.blit(scene.small_font.render(route_text, True, (210, 210, 196)),
                (panel.left + padding, line_y))
    line_y += line_height

    cargo = entity.get("cargo", [])
    if isinstance(cargo, list):
        cargo_slots = [slot for slot in cargo if isinstance(slot, dict)]
        resource_names = []
        for slot in cargo_slots:
            resource_id = str(slot.get("resource_id", ""))
            label = RESOURCES.get(resource_id, {}).get("label", resource_id or "Ресурс")
            quantity = int(slot.get("quantity", 0) or 0)
            resource_names.append(f"{label} ×{quantity}" if quantity else label)
        cargo_name = ", ".join(resource_names) or "нет"
        cargo_weight = float(entity.get("cargo_kg", 0) or 0)
    elif isinstance(cargo, dict):
        cargo_name = ", ".join(
            f"{RESOURCES.get(str(name), {}).get('label', name)} ×{amount}"
            for name, amount in cargo.items()
        ) or "нет"
        cargo_weight = float(entity.get("cargo_kg", 0) or 0)
    else:
        cargo_name = "нет"
        cargo_weight = float(entity.get("cargo_kg", 0) or 0)

    cargo_icon = None
    first_resource = next((slot.get("resource_id") for slot in cargo_slots), None) if isinstance(cargo, list) else None
    if first_resource:
        from ui.catalog_icons import draw_item_icon

        item_id = PRODUCTION_ITEM_IDS.get(str(first_resource))
        cargo_icon = draw_item_icon(screen, item_id or str(first_resource),
                                    (panel.left + padding, line_y - 1), 32)
    cargo_text = f"{cargo_name} · общий вес {cargo_weight:g} кг"
    cargo_x = cargo_icon.get_width() + panel.left + padding + 6 if cargo_icon else panel.left + padding
    screen.blit(scene.small_font.render(f"Груз: {cargo_text}", True, (217, 197, 155)), (cargo_x, line_y))
    line_y += line_height

    percent = _route_progress_percent(entity)
    direction = entity.get("direction", "outbound")
    progress_label = "Путь в город" if direction == "returning" else "Путь к объекту"
    progress_text = f"{progress_label}: {percent}%"
    screen.blit(scene.small_font.render(progress_text, True, (192, 205, 180)),
                (panel.left + padding, line_y))
    line_y += scene.small_font.get_height() + bar_gap
    track = pygame.Rect(panel.left + padding, line_y, width - padding * 2, bar_height)
    pygame.draw.rect(screen, (55, 61, 65), track, border_radius=3)
    fill = track.copy()
    fill.width = round(track.width * percent / 100)
    if fill.width:
        bar_color = (118, 193, 111) if direction == "outbound" else (95, 166, 203)
        pygame.draw.rect(screen, bar_color, fill, border_radius=3)
    line_y += bar_height + 1
    screen.blit(scene.small_font.render(_format_phase_eta(entity), True, (192, 205, 180)),
                (panel.left + padding, line_y))