"""Иконка монеты: рисуется процедурно, поэтому не зависит от файлов ассетов."""

import pygame

_CACHE = {}


def money_icon(size):
    """Золотая монета с ободком; одна и та же поверхность для всех мест, где показываются монеты."""
    size = int(size)
    if size not in _CACHE:
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        center = (size // 2, size // 2)
        radius = size // 2 - 1
        pygame.draw.circle(surface, (196, 150, 40), center, radius)
        pygame.draw.circle(surface, (120, 84, 20), center, radius, max(1, size // 12))
        pygame.draw.circle(surface, (255, 215, 120), center, max(1, radius * 2 // 3), max(1, size // 14))
        _CACHE[size] = surface
    return _CACHE[size]
