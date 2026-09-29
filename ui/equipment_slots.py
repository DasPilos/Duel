"""
Общая «кукла» экипировки для карточек всех персонажей (воин, маг и любые будущие классы).

Спрайт персонажа и две колонки слотов по бокам от него. Раскладка, отрисовка и поиск слота
под курсором живут только здесь: любое изменение слотов сразу применяется ко всем персонажам.
Рюкзак (InventoryWindow) использует те же функции, чтобы принимать перетаскивание в слоты.
"""

import pygame

from core import settings


# Колонки слотов вокруг спрайта: (ключ, подпись)
LEFT_SLOTS = (("head", "Голова"), ("neck", "Шея"), ("back", "Плащ"), ("body", "Доспех"), ("belt", "Пояс"), ("legs", "Ноги"))
RIGHT_SLOTS = (("ears", "Серьги"), ("hands", "Руки"), ("ring", "Кольцо"), ("weapon", "Оружие"), ("shield", "Щит"), ("feet", "Обувь"))
SLOT_LABELS = dict(LEFT_SLOTS + RIGHT_SLOTS)

SLOT_WIDTH = 66
SLOT_HEIGHT = 62
SLOT_GAP = 6
COLUMN_PADDING = 6
COLUMN_MARGIN = 8

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
    """Ячейки экипировки двумя колонками по бокам от спрайта: {слот: Rect}"""
    frame = pygame.Rect(frame)
    column_height = len(LEFT_SLOTS) * (SLOT_HEIGHT + SLOT_GAP) - SLOT_GAP
    top = int(area_center_y(frame) - column_height / 2)
    left_x = frame.x + COLUMN_MARGIN + COLUMN_PADDING
    right_x = frame.right - COLUMN_MARGIN - COLUMN_PADDING - SLOT_WIDTH
    rects = {}
    for column_x, slots in ((left_x, LEFT_SLOTS), (right_x, RIGHT_SLOTS)):
        for index, (slot, _) in enumerate(slots):
            rects[slot] = pygame.Rect(column_x, top + index * (SLOT_HEIGHT + SLOT_GAP), SLOT_WIDTH, SLOT_HEIGHT)
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
    for slots in (LEFT_SLOTS, RIGHT_SLOTS):
        column = rects[slots[0][0]].unionall([rects[slot] for slot, _ in slots])
        column = column.inflate(COLUMN_PADDING * 2, COLUMN_PADDING * 2)
        backdrop = pygame.Surface(column.size, pygame.SRCALPHA)
        backdrop.fill((20, 20, 26, 170))
        screen.blit(backdrop, column.topleft)
    mouse = pygame.mouse.get_pos()
    for slot, rect in rects.items():
        item = equipment.get(slot)
        pygame.draw.rect(screen, SLOT_HOVER if rect.collidepoint(mouse) else SLOT_BG, rect, border_radius=6)
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
