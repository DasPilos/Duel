import math

import pygame

HOTBAR_KEYS = (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5,
               pygame.K_6, pygame.K_7, pygame.K_8, pygame.K_9, pygame.K_0)
HOTBAR_LABELS = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0")
HOTBAR_SLOT_SIZE = 64
HOTBAR_SLOT_GAP = 6
HOTBAR_BOTTOM_MARGIN = 10
HOTBAR_FLASH_DURATION = 0.15


def hotbar_slot_rects(screen_width, screen_height):
    count = len(HOTBAR_KEYS)
    step = HOTBAR_SLOT_SIZE + HOTBAR_SLOT_GAP
    total = count * HOTBAR_SLOT_SIZE + (count - 1) * HOTBAR_SLOT_GAP
    left = (screen_width - total) // 2
    top = screen_height - HOTBAR_BOTTOM_MARGIN - HOTBAR_SLOT_SIZE
    return [pygame.Rect(left + index * step, top, HOTBAR_SLOT_SIZE, HOTBAR_SLOT_SIZE) for index in range(count)]


def hotbar_index_for_key(key):
    if key in HOTBAR_KEYS:
        return HOTBAR_KEYS.index(key)
    return None


def draw_hotbar(screen, rects, font, flashed_index=None, slots=None):
    """slots: None или список из len(rects) элементов; элемент None или dict с name, cooldown, cooldown_total, active."""
    for index, rect in enumerate(rects):
        slot = slots[index] if slots else None
        pygame.draw.rect(screen, (18, 16, 14), rect)
        active = bool(slot and slot.get("active"))
        if active:
            border = (255, 215, 60)
        elif index == flashed_index:
            border = (235, 205, 120)
        else:
            border = (110, 92, 60)
        pygame.draw.rect(screen, border, rect, 2)
        label = font.render(HOTBAR_LABELS[index], True, (230, 220, 190))
        screen.blit(label, (rect.x + 5, rect.y + 3))
        if slot is None:
            continue
        name = slot.get("name")
        if name:
            name_surface = font.render(name, True, (230, 220, 190))
            screen.blit(name_surface, name_surface.get_rect(midbottom=(rect.centerx, rect.bottom - 3)))
        cooldown = slot.get("cooldown", 0.0)
        total = slot.get("cooldown_total", 0.0)
        if cooldown > 0 and total > 0:
            ratio = min(1.0, cooldown / total)
            overlay_height = int(rect.height * ratio)
            if overlay_height > 0:
                overlay = pygame.Surface((rect.width - 4, overlay_height), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 150))
                screen.blit(overlay, (rect.x + 2, rect.y + 2))
            seconds = math.ceil(cooldown)
            seconds_surface = font.render(str(seconds), True, (255, 245, 210))
            screen.blit(seconds_surface, seconds_surface.get_rect(center=rect.center))
