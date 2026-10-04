"""
Общая «кукла» экипировки для карточек всех персонажей (воин, маг и любые будущие классы).

Спрайт персонажа и две колонки слотов по бокам от него. Раскладка, отрисовка и поиск слота
под курсором живут только здесь: любое изменение слотов сразу применяется ко всем персонажам.
Рюкзак (InventoryWindow) использует те же функции, чтобы принимать перетаскивание в слоты.
"""

import pygame

from core import settings


# (ключ, подпись, колонка, ряд) вокруг спрайта
SLOT_LAYOUT = (
    ("ears", "Серьги", 0, 0), ("head", "Голова", 2, 0), ("neck", "Шея", 4, 0),
    ("back", "Плащ", 0, 1), ("body", "Доспех", 2, 1), ("ring", "Кольцо", 4, 1),
    ("hands", "Руки", 0, 2), ("shield", "П рука", 1, 2), ("belt", "Пояс", 2, 2),
    ("weapon", "Л рука", 3, 2), ("ring_2", "Кольцо", 4, 2),
    ("legs", "Ноги", 2, 3), ("feet", "Обувь", 2, 4),
)
SLOT_LABELS = {slot: label for slot, label, _, _ in SLOT_LAYOUT}

SLOT_WIDTH = 66
SLOT_HEIGHT = 62
SLOT_OPACITY = 65

# Вертикальная зона куклы на карточке: между полосой MP/валютой и блоком характеристик
AREA_TOP_OFFSET = 151
AREA_BOTTOM_OFFSET = 180

SLOT_BG = (48, 44, 48)
SLOT_HOVER = (70, 64, 70)
SLOT_BORDER = (85, 78, 80)
SLOT_HIGHLIGHT = (120, 220, 120)
LABEL_COLOR = (150, 142, 130)
RARITY_COLORS = {
    "common": (205, 205, 205),
    "rare": (80, 150, 255),
    "epic": (180, 100, 240),
    "legendary": (255, 170, 40),
}


def area_center_y(frame):
    frame = pygame.Rect(frame)
    return (frame.y + AREA_TOP_OFFSET + frame.bottom - AREA_BOTTOM_OFFSET) / 2


def slot_rects(frame):
    """Позиции экипировки вокруг спрайта: {слот: Rect}."""
    frame = pygame.Rect(frame)
    scale = frame.width / 440
    reference_column_centers = (48, 143, 220, 308, 389)
    column_x = tuple(
        round(frame.centerx + (center - 220) * scale - SLOT_WIDTH / 2)
        for center in reference_column_centers
    )
    middle_row_top = int(area_center_y(frame) - 8)
    row_top = (
        middle_row_top - 172,
        middle_row_top - 86,
        middle_row_top,
        middle_row_top + 86,
        middle_row_top + 172,
    )
    rects = {}
    for slot, _, column, row in SLOT_LAYOUT:
        rects[slot] = pygame.Rect(column_x[column], row_top[row], SLOT_WIDTH, SLOT_HEIGHT)
    return rects


def slot_at(frame, position):
    """Ключ слота экипировки под точкой или None"""
    for slot, rect in slot_rects(frame).items():
        if rect.collidepoint(position):
            return slot
    return None


def draw_paperdoll(screen, frame, sprite, icons, font, equipment, highlight=None, dragged=None):
    """Рисует спрайт персонажа и слоты вокруг него. Возвращает y верхнего края спрайта."""
    frame = pygame.Rect(frame)
    center_y = area_center_y(frame)
    sprite_height = sprite.image.get_height() * settings.FIGHTER_SPRITE_SCALE if sprite.image is not None else 0
    sprite.draw(screen, frame.centerx, int(center_y + sprite_height / 2), scale=settings.FIGHTER_SPRITE_SCALE)
    draw_slots(screen, frame, icons, font, equipment, highlight, dragged)
    return center_y - sprite_height / 2


def draw_slots(screen, frame, icons, font, equipment, highlight=None, dragged=None):
    rects = slot_rects(frame)
    equipment = equipment if isinstance(equipment, dict) else {}
    mouse = pygame.mouse.get_pos()
    for slot, rect in rects.items():
        item = equipment.get(slot)
        color = SLOT_HOVER if rect.collidepoint(mouse) else SLOT_BG
        background = pygame.Surface(rect.size, pygame.SRCALPHA)
        background.fill((*color, round(255 * SLOT_OPACITY / 100)))
        screen.blit(background, rect.topleft)
        border = RARITY_COLORS.get(item.get("rarity"), SLOT_BORDER) if item else SLOT_BORDER
        if slot == highlight:
            border = SLOT_HIGHLIGHT
        pygame.draw.rect(screen, border, rect, 3 if slot == highlight else 2, border_radius=6)
        if item:
            icon = icons.get(item.get("icon"), min(rect.width, rect.height))
            if slot == dragged:
                icon = icon.copy()
                icon.set_alpha(70)
            screen.blit(icon, icon.get_rect(center=rect.center))
        else:
            label = font.render(SLOT_LABELS[slot], True, LABEL_COLOR)
            if label.get_width() > rect.width - 6:
                width = rect.width - 6
                label = pygame.transform.smoothscale(label, (width, max(1, int(label.get_height() * width / label.get_width()))))
            screen.blit(label, label.get_rect(center=rect.center))
