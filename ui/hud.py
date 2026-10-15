import math
import time

import pygame

from core import settings


_upgrade_line_font = None


def upgrade_line_font():
    # Тот же размер, что у плашки «Игроков онлайн» (ServerStatusHUD).
    global _upgrade_line_font
    if _upgrade_line_font is None:
        _upgrade_line_font = pygame.font.SysFont(settings.FONT_NAME, 18)
    return _upgrade_line_font


def draw_city_upgrade_line(screen, font, upgrade, castle_upgrades=None):
    """Строки справа вверху: активные улучшения города и замка с таймером до завершения."""
    items = [upgrade, *(castle_upgrades or [])]
    lines = []
    for item in items:
        if not (item or {}).get("active") or item.get("finish_at") is None:
            continue
        seconds_left = max(0, math.ceil(float(item["finish_at"]) - time.time()))
        hours, rest = divmod(seconds_left, 3600)
        minutes, seconds = divmod(rest, 60)
        timer = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        name = item.get("upgrade_name") or "Улучшение"
        lines.append(f"{name} · осталось {timer}")
    y = 20
    for text in lines:
        surf = font.render(text, True, (255, 200, 90))
        bg = surf.get_rect(topright=(settings.WIDTH - 20, y)).inflate(16, 8)
        bg_surf = pygame.Surface(bg.size, pygame.SRCALPHA)
        pygame.draw.rect(bg_surf, (15, 18, 24, 215), bg_surf.get_rect(), border_radius=5)
        pygame.draw.rect(bg_surf, (220, 180, 70), bg_surf.get_rect(), 1, border_radius=5)
        screen.blit(bg_surf, bg.topleft)
        screen.blit(surf, surf.get_rect(center=bg.center))
        y = bg.bottom + 6


def draw_text(screen, font, text, x, y, color=(230, 230, 230)):
    # x — положение текста по горизонтали:
    # увеличьте x — текст переместится вправо.
    # уменьшите x — текст переместится влево.
    #
    # y — положение текста по вертикали:
    # увеличьте y — текст опустится ниже.
    # уменьшите y — текст поднимется выше.
    surface = font.render(str(text), True, color)
    screen.blit(surface, (x, y))


def draw_button(
    screen,
    rect,
    text,
    font,
    color=(80, 160, 255),
    hover_color=(110, 190, 255),
    text_color=(255, 255, 255),
):
    # rect имеет формат:
    # (X, Y, ШИРИНА, ВЫСОТА)
    #
    # X — положение кнопки влево/вправо.
    # Y — положение кнопки вверх/вниз.
    # ШИРИНА — размер кнопки по горизонтали.
    # ВЫСОТА — размер кнопки по вертикали.
    rect = pygame.Rect(rect)
    hovered = rect.collidepoint(pygame.mouse.get_pos())

    pygame.draw.rect(
        screen,
        hover_color if hovered else color,
        rect,
        border_radius=10,
    )

    surface = font.render(str(text), True, text_color)
    text_rect = surface.get_rect(center=rect.center)
    screen.blit(surface, text_rect)

    return hovered


class FloatingText:
    def __init__(
        self,
        x,
        y,
        text,
        font,
        color=(255, 60, 60),
        duration=60,
        velocity=-1.5,
    ):
        # x и y — начальная позиция всплывающего текста.
        self.x = x
        self.y = y
        self.text = str(text)
        self.font = font
        self.color = color
        self.duration = duration
        self.max_duration = duration

        # Скорость движения текста вверх.
        # Сделайте число более отрицательным — текст будет двигаться быстрее.
        self.vy = velocity

    def update(self):
        self.y += self.vy
        self.duration -= 1

    def draw(self, screen):
        if self.duration <= 0:
            return

        surface = self.font.render(self.text, True, self.color)

        if self.duration < self.max_duration // 2:
            alpha = int(
                255 * self.duration / (self.max_duration // 2)
            )
            surface.set_alpha(alpha)

        rect = surface.get_rect(
            center=(int(self.x), int(self.y))
        )
        screen.blit(surface, rect)


def update_and_draw_floating_texts(screen, floating_texts):
    for floating_text in floating_texts[:]:
        floating_text.update()
        floating_text.draw(screen)

        if floating_text.duration <= 0:
            floating_texts.remove(floating_text)
