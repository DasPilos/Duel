"""Per-resource storage indicator used by city and production stores."""

import pygame


def storage_fill_color(amount, capacity):
    ratio = 0 if int(capacity) <= 0 else max(0, int(amount)) / int(capacity)
    if ratio <= 0.20:
        return 218, 69, 65
    if ratio <= 0.40:
        return 232, 191, 67
    if ratio <= 0.70:
        return 75, 190, 100
    return 116, 218, 245


def draw_storage_meter(screen, rect, amount, capacity, charging=False):
    pygame.draw.rect(screen, (24, 29, 31), rect, border_radius=2)
    inner = rect.inflate(-2, -2)
    if inner.width <= 0 or inner.height <= 0:
        return
    ratio = 0 if int(capacity) <= 0 else min(1.0, max(0, int(amount)) / int(capacity))
    fill_width = int(round(inner.width * ratio))
    color = storage_fill_color(amount, capacity)
    if charging:
        color = (246, 255, 250) if pygame.time.get_ticks() // 350 % 2 else (48, 225, 105)
    if fill_width > 0:
        pygame.draw.rect(screen, color, (inner.x, inner.y, fill_width, inner.height), border_radius=1)
    marker_color = (150, 163, 164)
    for boundary in (0.20, 0.40, 0.70):
        marker_x = inner.x + round(inner.width * boundary)
        pygame.draw.line(
            screen, marker_color, (marker_x, inner.y), (marker_x, inner.bottom - 1), 1
        )