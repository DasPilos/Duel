from functools import lru_cache
from pathlib import Path

import pygame


PROFESSION_ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "ui" / "professions"
PROFESSION_ICON_FILES = {
    "warrior": "warrior.png",
    "archer": "archer.png",
    "assassin": "assassin.png",
    "mage": "mage.png",
}
PROFESSION_ICON_SIZE = 32
PROFESSION_ICON_GAP = 4


@lru_cache(maxsize=None)
def profession_icon(profession):
    filename = PROFESSION_ICON_FILES.get(profession)
    if filename is None:
        return None
    image = pygame.image.load(str(PROFESSION_ICON_DIR / filename))
    if pygame.display.get_surface() is not None:
        image = image.convert_alpha()
    if image.get_size() != (PROFESSION_ICON_SIZE, PROFESSION_ICON_SIZE):
        image = pygame.transform.smoothscale(image, (PROFESSION_ICON_SIZE, PROFESSION_ICON_SIZE))
    return image


def draw_profession_icon_before(screen, profession, text_rect, gap=PROFESSION_ICON_GAP):
    """Рисует иконку профессии слева от прямоугольника текста ника. Ничего не делает для профессий без иконки."""
    icon = profession_icon(profession)
    if icon is None:
        return False
    screen.blit(icon, icon.get_rect(midright=(text_rect.left - gap, text_rect.centery)))
    return True
