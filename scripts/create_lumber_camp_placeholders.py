"""Временные PNG-затычки для участков Лагеря лесорубов (позже заменить спрайтами).

Лес: 1 стоящий лес, 2 рубка, 3 брёвна, 4 вывоз. Ягоды: 1 кусты, 2 цветение, 3 спелые, 4 сбор.
Запуск: python scripts/create_lumber_camp_placeholders.py
"""
import random
from pathlib import Path

import pygame

OUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "town" / "lumber_camp"
SIZE = 256


def _ground(surface, rng, base=(48, 62, 34)):
    surface.fill(base)
    for _ in range(900):
        x, y = rng.randrange(SIZE), rng.randrange(SIZE)
        shade = rng.randrange(-12, 12)
        color = tuple(max(0, min(255, c + shade)) for c in base)
        pygame.draw.line(surface, color, (x, y), (x + rng.choice((-1, 1)), y - 3), 1)


def _tree(surface, x, y, rng, radius=None):
    radius = radius or rng.randrange(13, 20)
    pygame.draw.circle(surface, (14, 34, 16), (x + 3, y + 4), radius)
    pygame.draw.circle(surface, (30, 78, 34), (x, y), radius)
    pygame.draw.circle(surface, (48, 108, 50), (x - radius // 3, y - radius // 3), radius // 2)


def _stump(surface, x, y):
    pygame.draw.circle(surface, (96, 66, 38), (x, y), 6)
    pygame.draw.circle(surface, (176, 140, 92), (x, y), 4)
    pygame.draw.circle(surface, (130, 96, 58), (x, y), 2, 1)


def _log(surface, x, y, length=34):
    pygame.draw.rect(surface, (110, 74, 42), (x, y, length, 8), border_radius=3)
    pygame.draw.line(surface, (80, 52, 28), (x + 2, y + 3), (x + length - 4, y + 3), 1)
    pygame.draw.circle(surface, (186, 150, 100), (x + length, y + 4), 4)


def _forest(surface, rng, keep=lambda x, y: True):
    for y in range(-10, SIZE + 10, 22):
        for x in range(-10, SIZE + 10, 22):
            tx, ty = x + rng.randrange(-6, 7), y + rng.randrange(-6, 7)
            if keep(tx, ty):
                _tree(surface, tx, ty, rng)


def wood_standing(rng):
    surface = pygame.Surface((SIZE, SIZE))
    _ground(surface, rng, (24, 44, 22))
    _forest(surface, rng)
    return surface


def wood_chopping(rng):
    # Вырубка в нижней трети, часть деревьев лежит
    surface = pygame.Surface((SIZE, SIZE))
    _ground(surface, rng)
    _forest(surface, rng, keep=lambda x, y: y < SIZE * 0.62)
    for _ in range(14):
        _stump(surface, rng.randrange(10, SIZE - 10), rng.randrange(int(SIZE * 0.65), SIZE - 8))
    for _ in range(4):
        _log(surface, rng.randrange(10, SIZE - 50), rng.randrange(int(SIZE * 0.68), SIZE - 14), 40)
    return surface


def wood_logs(rng):
    surface = pygame.Surface((SIZE, SIZE))
    _ground(surface, rng, (64, 70, 38))
    for _ in range(26):
        _stump(surface, rng.randrange(8, SIZE - 8), rng.randrange(8, SIZE - 8))
    for stack in range(4):
        sx, sy = 20 + (stack % 2) * 120, 30 + (stack // 2) * 120
        for row in range(4):
            _log(surface, sx + row * 3, sy + row * 10, 70)
    return surface


def wood_hauling(rng):
    surface = pygame.Surface((SIZE, SIZE))
    _ground(surface, rng, (70, 74, 40))
    for _ in range(26):
        _stump(surface, rng.randrange(8, SIZE - 8), rng.randrange(8, SIZE - 8))
    # Колея и телега с брёвнами
    pygame.draw.line(surface, (92, 70, 44), (0, SIZE // 2 - 10), (SIZE, SIZE // 2 - 10), 6)
    pygame.draw.line(surface, (92, 70, 44), (0, SIZE // 2 + 14), (SIZE, SIZE // 2 + 14), 6)
    pygame.draw.rect(surface, (120, 84, 48), (90, SIZE // 2 - 22, 80, 30))
    for row in range(3):
        _log(surface, 92, SIZE // 2 - 30 + row * 8, 74)
    for wx in (100, 160):
        pygame.draw.circle(surface, (50, 36, 22), (wx, SIZE // 2 + 12), 10)
        pygame.draw.circle(surface, (130, 100, 60), (wx, SIZE // 2 + 12), 10, 2)
    _log(surface, 20, 40, 60)
    return surface


def _bushes(surface, rng, dots=None, dot_size=3):
    for y in range(8, SIZE, 30):
        for x in range(8, SIZE, 30):
            bx, by = x + rng.randrange(-6, 7), y + rng.randrange(-6, 7)
            pygame.draw.circle(surface, (24, 60, 26), (bx + 2, by + 3), 13)
            pygame.draw.circle(surface, (44, 100, 44), (bx, by), 13)
            if dots:
                for _ in range(rng.randrange(4, 9)):
                    pygame.draw.circle(surface, rng.choice(dots), (bx + rng.randrange(-9, 10), by + rng.randrange(-9, 10)), dot_size)


def berries_bushes(rng):
    surface = pygame.Surface((SIZE, SIZE))
    _ground(surface, rng, (66, 98, 46))
    _bushes(surface, rng)
    return surface


def berries_flowers(rng):
    surface = pygame.Surface((SIZE, SIZE))
    _ground(surface, rng, (70, 104, 48))
    _bushes(surface, rng, dots=((245, 245, 240), (250, 210, 230)), dot_size=2)
    return surface


def berries_ripe(rng):
    surface = pygame.Surface((SIZE, SIZE))
    _ground(surface, rng, (70, 104, 48))
    _bushes(surface, rng, dots=((200, 30, 50), (120, 40, 140), (40, 50, 150)), dot_size=3)
    return surface


def berries_picking(rng):
    surface = berries_ripe(rng)
    # Обобранная часть кустов и корзины
    picked = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    _bushes(picked, rng)
    mask = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255), [(0, SIZE * 2 // 3), (SIZE, SIZE // 3), (SIZE, SIZE), (0, SIZE)])
    picked.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surface.blit(picked, (0, 0))
    for _ in range(5):
        x, y = rng.randrange(20, SIZE - 30), rng.randrange(SIZE // 2, SIZE - 24)
        pygame.draw.ellipse(surface, (150, 110, 60), (x, y, 22, 14))
        pygame.draw.ellipse(surface, (180, 30, 50), (x + 3, y + 1, 16, 6))
    return surface


def house():
    # Шалаш лесоруба
    surface = pygame.Surface((32, 32), pygame.SRCALPHA)
    pygame.draw.polygon(surface, (120, 82, 46), [(3, 29), (16, 5), (29, 29)])
    pygame.draw.polygon(surface, (70, 46, 24), [(3, 29), (16, 5), (29, 29)], 2)
    for offset in (-6, 0, 6):
        pygame.draw.line(surface, (86, 58, 30), (16, 7), (16 + offset * 2, 29), 1)
    pygame.draw.polygon(surface, (40, 26, 14), [(12, 29), (16, 18), (20, 29)])
    return surface


def main():
    pygame.init()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stages = {
        "wood": (wood_standing, wood_chopping, wood_logs, wood_hauling),
        "berries": (berries_bushes, berries_flowers, berries_ripe, berries_picking),
    }
    for resource_index, (resource, makers) in enumerate(stages.items()):
        for stage_index, make in enumerate(makers, start=1):
            image = make(random.Random(resource_index * 10 + stage_index))
            pygame.image.save(image, str(OUT_DIR / f"field_{resource}_stage_{stage_index}.png"))
    pygame.image.save(house(), str(OUT_DIR / "house.png"))
    pygame.quit()
    print(f"saved to {OUT_DIR}")


if __name__ == "__main__":
    main()
