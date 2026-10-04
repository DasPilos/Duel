"""Временные PNG-затычки для полей Крестьянского поселения (позже заменить спрайтами).

Для каждой культуры 4 стадии цикла: 1 пашня, 2 всходы, 3 спелая культура, 4 уборка.
Запуск: python scripts/create_farm_field_placeholders.py
"""
import random
from pathlib import Path

import pygame

OUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "town" / "farm"
SIZE = 256
FURROW_STEP = 16

SPROUT_COLORS = {"wheat": (78, 170, 64), "flax": (70, 150, 110), "cotton": (60, 130, 60)}
STUBBLE_COLORS = {"wheat": (150, 122, 62), "flax": (120, 110, 70), "cotton": (110, 90, 60)}


def _soil(surface, base=(42, 31, 22), dark=(24, 17, 11), light=(62, 47, 33)):
    surface.fill(base)
    for y in range(0, SIZE, FURROW_STEP):
        pygame.draw.line(surface, dark, (0, y), (SIZE, y), 5)
        pygame.draw.line(surface, light, (0, y + 6), (SIZE, y + 6), 1)


def _ripe(surface, crop, rng):
    if crop == "wheat":
        surface.fill((196, 160, 58))
        for _ in range(900):
            x, y = rng.randrange(SIZE), rng.randrange(SIZE)
            pygame.draw.line(surface, (226, 190, 82), (x, y), (x + rng.choice((-1, 0, 1)), y - 10), 1)
            pygame.draw.circle(surface, (244, 212, 112), (x, y - 11), 2)
    elif crop == "flax":
        surface.fill((70, 120, 70))
        for _ in range(700):
            x, y = rng.randrange(SIZE), rng.randrange(SIZE)
            pygame.draw.line(surface, (95, 150, 85), (x, y), (x, y - 12), 1)
        for _ in range(420):
            x, y = rng.randrange(SIZE), rng.randrange(SIZE)
            pygame.draw.circle(surface, (110, 140, 230), (x, y), 3)
            pygame.draw.circle(surface, (200, 210, 255), (x, y), 1)
    else:
        surface.fill((55, 95, 50))
        for _ in range(160):
            x, y = rng.randrange(SIZE), rng.randrange(SIZE)
            pygame.draw.circle(surface, (40, 80, 40), (x, y), 9)
        for _ in range(520):
            x, y = rng.randrange(SIZE), rng.randrange(SIZE)
            pygame.draw.circle(surface, (240, 240, 235), (x, y), 4)
            pygame.draw.circle(surface, (205, 205, 200), (x + 1, y + 1), 2)


def stage_sowing(crop, rng):
    surface = pygame.Surface((SIZE, SIZE))
    _soil(surface)
    return surface


def stage_sprouts(crop, rng):
    surface = pygame.Surface((SIZE, SIZE))
    _soil(surface, (52, 39, 27), (30, 22, 14), (70, 54, 38))
    color = SPROUT_COLORS[crop]
    light = tuple(min(255, c + 40) for c in color)
    for y in range(4, SIZE, FURROW_STEP):
        for x in range(rng.randrange(4, 10), SIZE, 10):
            height = rng.randrange(4, 9)
            pygame.draw.line(surface, color, (x, y), (x - 2, y - height), 2)
            pygame.draw.line(surface, light, (x, y), (x + 2, y - height + 1), 1)
    return surface


def stage_ripe(crop, rng):
    surface = pygame.Surface((SIZE, SIZE))
    _ripe(surface, crop, rng)
    return surface


def stage_harvest(crop, rng):
    # Убранная часть (стерня) ниже диагонали, неубранная культура — выше
    surface = pygame.Surface((SIZE, SIZE))
    stubble = STUBBLE_COLORS[crop]
    surface.fill(stubble)
    dark = tuple(max(0, c - 30) for c in stubble)
    for _ in range(700):
        x, y = rng.randrange(SIZE), rng.randrange(SIZE)
        pygame.draw.line(surface, dark, (x, y), (x, y - 3), 1)
    uncut = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    _ripe(uncut, crop, rng)
    mask = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255), [(0, 0), (SIZE, 0), (SIZE, SIZE // 3), (0, SIZE * 2 // 3)])
    uncut.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surface.blit(uncut, (0, 0))
    bundle = {"wheat": (214, 178, 76), "flax": (150, 150, 110), "cotton": (235, 235, 230)}[crop]
    for _ in range(8):
        x, y = rng.randrange(20, SIZE - 20), rng.randrange(SIZE // 2, SIZE - 20)
        pygame.draw.ellipse(surface, bundle, (x, y, 14, 9))
        pygame.draw.ellipse(surface, dark, (x, y, 14, 9), 1)
    return surface


def house():
    surface = pygame.Surface((32, 32), pygame.SRCALPHA)
    pygame.draw.rect(surface, (150, 105, 65), (6, 14, 20, 15))
    pygame.draw.rect(surface, (90, 60, 35), (6, 14, 20, 15), 1)
    pygame.draw.polygon(surface, (160, 60, 45), [(3, 15), (16, 4), (29, 15)])
    pygame.draw.polygon(surface, (100, 35, 25), [(3, 15), (16, 4), (29, 15)], 1)
    pygame.draw.rect(surface, (70, 45, 25), (14, 20, 5, 9))
    pygame.draw.rect(surface, (240, 210, 120), (8, 17, 4, 4))
    return surface


def main():
    pygame.init()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stages = (stage_sowing, stage_sprouts, stage_ripe, stage_harvest)
    for crop_index, crop in enumerate(("wheat", "flax", "cotton")):
        for stage_index, make in enumerate(stages, start=1):
            image = make(crop, random.Random(crop_index * 10 + stage_index))
            pygame.image.save(image, str(OUT_DIR / f"field_{crop}_stage_{stage_index}.png"))
    pygame.image.save(house(), str(OUT_DIR / "house.png"))
    pygame.quit()
    print(f"saved to {OUT_DIR}")


if __name__ == "__main__":
    main()
