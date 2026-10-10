"""Modular global-map composition of Radburg."""

import pygame

from scenes.city.sprite_modules import city_visual_tier, draw_keep, draw_residence


def _draw_completed_fence(screen, bounds, side, scale, level):
    wood = (82, 54, 34) if level < 5 else (105, 112, 111)
    rail = (158, 109, 61) if level < 5 else (168, 176, 174)
    step = max(5, round(18 * scale))
    if side in (0, 1):
        y = bounds.top if side == 0 else bounds.bottom
        left, right = bounds.left, bounds.right
        gap_left, gap_right = bounds.centerx - max(4, round(24 * scale)), bounds.centerx + max(4, round(24 * scale))
        intervals = ((left, gap_left), (gap_right, right))
        for x1, x2 in intervals:
            pygame.draw.line(screen, wood, (x1, y), (x2, y), max(2, round(5 * scale)))
            pygame.draw.line(screen, rail, (x1, y - 2), (x2, y - 2), max(1, round(2 * scale)))
            for post_x in range(x1, x2 + 1, step):
                pygame.draw.line(screen, wood, (post_x, y - round(7 * scale)),
                                 (post_x, y + round(7 * scale)), max(1, round(2 * scale)))
    else:
        x = bounds.right if side == 2 else bounds.left
        top, bottom = bounds.top, bounds.bottom
        gap_top, gap_bottom = bounds.centery - max(4, round(24 * scale)), bounds.centery + max(4, round(24 * scale))
        intervals = ((top, gap_top), (gap_bottom, bottom))
        for y1, y2 in intervals:
            pygame.draw.line(screen, wood, (x, y1), (x, y2), max(2, round(5 * scale)))
            pygame.draw.line(screen, rail, (x - 2, y1), (x - 2, y2), max(1, round(2 * scale)))
            for post_y in range(y1, y2 + 1, step):
                pygame.draw.line(screen, wood, (x - round(7 * scale), post_y),
                                 (x + round(7 * scale), post_y), max(1, round(2 * scale)))


def _draw_work_logs(screen, bounds, sides, scale):
    color = (145, 97, 53)
    length = max(4, round(14 * scale))
    step = max(8, round(28 * scale))
    for side in sides:
        if side in (0, 1):
            y = bounds.top + 4 if side == 0 else bounds.bottom - 4
            for x in range(bounds.left + 4, bounds.right - 4, step):
                pygame.draw.line(screen, color, (x, y + 2), (x + length, y - 2), max(2, round(3 * scale)))
        else:
            x = bounds.right - 4 if side == 2 else bounds.left + 4
            for y in range(bounds.top + 4, bounds.bottom - 4, step):
                pygame.draw.line(screen, color, (x + 2, y), (x - 2, y + length), max(2, round(3 * scale)))


def _draw_trench(screen, bounds, scale):
    color = (137, 103, 62)
    step = max(8, round(18 * scale))
    trench_length = max(4, round(10 * scale))
    for x in range(bounds.left + 4, bounds.right - 4, step):
        pygame.draw.line(screen, color, (x, bounds.top + 4),
                         (min(x + trench_length, bounds.right - 4), bounds.top + 4), 3)
        pygame.draw.line(screen, color, (x, bounds.bottom - 4),
                         (min(x + trench_length, bounds.right - 4), bounds.bottom - 4), 3)
    for y in range(bounds.top + 4, bounds.bottom - 4, step):
        pygame.draw.line(screen, color, (bounds.left + 4, y),
                         (bounds.left + 4, min(y + trench_length, bounds.bottom - 4)), 3)
        pygame.draw.line(screen, color, (bounds.right - 4, y),
                         (bounds.right - 4, min(y + trench_length, bounds.bottom - 4)), 3)


def draw_city_exterior(screen, rect, visual_state):
    """Compose walls, gates, corner towers, keep, homes, and AP stage."""
    tier = city_visual_tier(visual_state.get("city_level", 1))
    active = bool(visual_state.get("active"))
    phase = min(3, int(visual_state.get("phase_index", 0))) if active else -1
    scale = max(0.2, min(rect.width, rect.height) / 480)
    inset = max(3, round(12 * scale))
    bounds = rect.inflate(-2 * inset, -2 * inset)

    pygame.draw.ellipse(screen, (12, 17, 15),
                        (bounds.left + inset, bounds.bottom - inset,
                         max(1, bounds.width - 2 * inset), max(5, inset * 3)))
    ground = (49, 57, 56) if tier < 5 else (62, 66, 65)
    pygame.draw.rect(screen, ground, bounds)
    pygame.draw.rect(screen, (102, 115, 110), bounds, max(1, round(2 * scale)))

    tower_size = max(12, round(72 * scale))
    tower_color = (86 + min(tier * 2, 24), 94 + min(tier * 2, 24), 92 + min(tier * 2, 24))
    tower_positions = (
        (bounds.left, bounds.top), (bounds.right - tower_size, bounds.top),
        (bounds.left, bounds.bottom - tower_size),
        (bounds.right - tower_size, bounds.bottom - tower_size),
    )
    for tower_x, tower_y in tower_positions:
        tower = pygame.Rect(tower_x, tower_y, tower_size, tower_size)
        pygame.draw.rect(screen, tower_color, tower)
        pygame.draw.rect(screen, (35, 42, 43), tower, max(1, round(2 * scale)))
        merlon = max(4, round(9 * scale))
        for x in range(tower.left + 3, tower.right - merlon, merlon * 2):
            pygame.draw.rect(screen, (34, 40, 41), (x, tower.top - 2, merlon, merlon // 2 + 1))

    if tier >= 2:
        completed_sides = (0, 1, 2, 3)
    elif not active or phase == 0:
        completed_sides = ()
    elif phase == 2:
        completed_sides = (1, 2)
    else:
        completed_sides = (1, 2, 3) if phase == 3 else ()

    for side in completed_sides:
        _draw_completed_fence(screen, bounds, side, scale, tier)

    if active and tier == 1:
        if phase == 0:
            _draw_trench(screen, bounds, scale)
        else:
            incomplete = tuple(side for side in (0, 1, 2, 3) if side not in completed_sides)
            _draw_work_logs(screen, bounds, incomplete, scale)

    gate_width = max(8, round(48 * scale))
    gate_height = max(6, round(24 * scale))
    gates = (
        pygame.Rect(bounds.centerx - gate_width // 2, bounds.top - 1, gate_width, gate_height),
        pygame.Rect(bounds.centerx - gate_width // 2, bounds.bottom - gate_height + 1,
                    gate_width, gate_height),
        pygame.Rect(bounds.left - 1, bounds.centery - gate_width // 2, gate_height, gate_width),
        pygame.Rect(bounds.right - gate_height + 1, bounds.centery - gate_width // 2,
                    gate_height, gate_width),
    )
    for gate in gates:
        pygame.draw.rect(screen, (29, 34, 34), gate)
        pygame.draw.rect(screen, (224, 184, 95), gate, 1)

    house_spots = (
        (0.17, 0.17), (0.83, 0.17), (0.17, 0.83), (0.83, 0.83),
        (0.50, 0.14), (0.50, 0.86), (0.14, 0.50), (0.86, 0.50),
        (0.27, 0.17), (0.73, 0.83),
    )
    house_size = max(7, round(42 * scale))
    house_count = 4 if tier == 1 else 7
    for index, (fx, fy) in enumerate(house_spots[:house_count]):
        house = pygame.Rect(0, 0, house_size, house_size)
        house.center = (round(bounds.left + bounds.width * fx), round(bounds.top + bounds.height * fy))
        draw_residence(screen, house, tier, index)

    keep_size = max(24, round(min(bounds.width, bounds.height) * 0.38))
    keep = pygame.Rect(0, 0, keep_size, keep_size)
    keep.center = bounds.center
    draw_keep(screen, keep, 1)
