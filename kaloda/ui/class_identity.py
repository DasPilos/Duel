from functools import lru_cache

import pygame

from kaloda.combat.character_stats import normalize_profession_type
from kaloda import settings


CLASS_PALETTES = {
    "warrior": {
        "background": (68, 32, 38),
        "accent": (220, 95, 100),
        "icon_background": (145, 52, 60),
        "glyph": "В",
    },
    "archer": {
        "background": (31, 58, 41),
        "accent": (105, 190, 105),
        "icon_background": (48, 125, 67),
        "glyph": "Л",
    },
    "assassin": {
        "background": (52, 35, 67),
        "accent": (170, 120, 215),
        "icon_background": (105, 67, 150),
        "glyph": "А",
    },
    "mage": {
        "background": (35, 57, 74),
        "accent": (125, 195, 230),
        "icon_background": (58, 132, 172),
        "glyph": "М",
    },
    "necromancer": {
        "background": (37, 54, 42),
        "accent": (120, 220, 135),
        "icon_background": (54, 120, 69),
        "glyph": "Н",
    },
}


CLASS_ICON_SIZE = 15


def class_palette(profession_type):
    canonical_type = normalize_profession_type(profession_type)
    return CLASS_PALETTES.get(canonical_type, CLASS_PALETTES["warrior"])


@lru_cache(maxsize=len(CLASS_PALETTES))
def _class_icon(canonical_type):
    palette = CLASS_PALETTES.get(canonical_type, CLASS_PALETTES["warrior"])
    icon = pygame.Surface((CLASS_ICON_SIZE, CLASS_ICON_SIZE), pygame.SRCALPHA)
    rect = icon.get_rect()
    pygame.draw.rect(icon, palette["icon_background"], rect, border_radius=3)
    pygame.draw.rect(icon, palette["accent"], rect, width=1, border_radius=3)
    font = pygame.font.SysFont(settings.FONT_NAME, 9, bold=True)
    glyph = font.render(palette["glyph"], True, (250, 250, 250))
    icon.blit(glyph, glyph.get_rect(center=rect.center))
    return icon


def class_icon(profession_type):
    return _class_icon(normalize_profession_type(profession_type))
