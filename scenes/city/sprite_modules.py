"""Reusable PNG modules for Radburg's first two city tiers."""

from functools import lru_cache
from pathlib import Path

import pygame

ASSET_ROOT = Path(__file__).resolve().parents[2] / "assets"
MAX_RENDERED_CITY_LEVEL = 2


def city_visual_tier(city_level):
    return max(1, min(MAX_RENDERED_CITY_LEVEL, int(city_level)))


@lru_cache(maxsize=3)
def _load_module(module):
    paths = {
        "farm_house": ASSET_ROOT / "town" / "farm" / "house.png",
        "lumber_house": ASSET_ROOT / "town" / "lumber_camp" / "house.png",
        "keep": ASSET_ROOT / "fighters" / "equipment" / "placeholders" / "building_town_radburg.png",
    }
    return pygame.image.load(str(paths[module]))


def draw_residence(screen, rect, city_level, residence_index=0):
    """Draw one opaque, replaceable house module in its reserved footprint."""
    tier = city_visual_tier(city_level)
    module = "farm_house" if tier == 1 else "lumber_house"
    wall = (132, 94, 64) if tier == 1 else (145, 119, 83)
    pygame.draw.rect(screen, wall, rect)
    pygame.draw.rect(screen, (61, 48, 38), rect, max(1, rect.width // 24))
    screen.blit(pygame.transform.scale(_load_module(module), rect.size), rect.topleft)
    if tier == 2:
        flag_x = rect.centerx + (residence_index % 3 - 1) * max(2, rect.width // 5)
        flag_top = rect.top + max(2, rect.height // 10)
        pygame.draw.line(screen, (65, 47, 34), (flag_x, flag_top),
                         (flag_x, flag_top + max(3, rect.height // 4)), 1)
        pygame.draw.polygon(screen, (220, 194, 106), [
            (flag_x, flag_top),
            (flag_x + max(3, rect.width // 5), flag_top + max(1, rect.height // 12)),
            (flag_x, flag_top + max(2, rect.height // 6)),
        ])


def draw_keep(screen, rect, city_level):
    """Draw the shared central-keep PNG, with a bell tower added at L2."""
    tier = city_visual_tier(city_level)
    screen.blit(pygame.transform.scale(_load_module("keep"), rect.size), rect.topleft)
    if tier == 1:
        return
    tower_width = max(8, rect.width // 5)
    tower_height = max(12, int(rect.height * 0.30))
    tower = pygame.Rect(rect.centerx - tower_width // 2, rect.top + 2,
                        tower_width, tower_height)
    pygame.draw.rect(screen, (60, 70, 79), tower)
    pygame.draw.rect(screen, (27, 34, 42), tower, max(1, tower_width // 12))
    roof = [tower.topleft, (tower.centerx, tower.top - max(4, tower_height // 3)), tower.topright]
    pygame.draw.polygon(screen, (87, 55, 40), roof)
    pygame.draw.lines(screen, (47, 36, 29), True, roof, max(1, tower_width // 16))
    pygame.draw.circle(screen, (225, 184, 75),
                       (tower.centerx, tower.top + tower.height // 2), max(2, tower_width // 6))