"""Shared drawing and coordinate helpers for the city and world map scenes."""

import pygame

from core import settings


def screen_px_to_world(sx, sy, zoom, camera_x, camera_y):
    """Преобразование экранных пикселей в мировые координаты."""
    wx = (sx - settings.WIDTH / 2) / zoom + camera_x
    wy = (sy - settings.HEIGHT / 2) / zoom + camera_y
    return wx, wy


def draw_map_badge(font, screen, cx, bottom_y, text, border_color):
    """Рисует плашку с подписью над объектом карты, если она попадает в экран."""
    surf = font.render(text, True, (240, 240, 240))
    bg = surf.get_rect(midbottom=(cx, bottom_y)).inflate(10, 4)
    if -50 <= bg.centerx <= settings.WIDTH + 50 and -50 <= bg.centery <= settings.HEIGHT + 50:
        pygame.draw.rect(screen, (12, 14, 18, 220), bg, border_radius=3)
        pygame.draw.rect(screen, border_color, bg, 1, border_radius=3)
        screen.blit(surf, surf.get_rect(center=bg.center))
