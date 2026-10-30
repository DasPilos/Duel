"""Затемнённое окно при потере связи с сервером и при устаревшей версии клиента."""

import math

import pygame

from client.connection import ConnectionMonitor
from core import settings
from ui.hud import draw_button


class ConnectionOverlay:
    PANEL_COLOR = (22, 24, 36)
    BORDER_COLOR = (92, 104, 128)
    TITLE_COLOR = (240, 220, 150)
    TEXT_COLOR = (230, 226, 211)

    def __init__(self):
        self.panel_rect = pygame.Rect(0, 0, 560, 230)
        self.panel_rect.center = (settings.WIDTH // 2, settings.HEIGHT // 2)
        self.reload_button = pygame.Rect(0, 0, 280, 44)
        self.reload_button.center = (self.panel_rect.centerx, self.panel_rect.bottom - 42)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 30)
        self.text_font = pygame.font.SysFont(settings.FONT_NAME, 20)
        self.button_font = pygame.font.SysFont(settings.FONT_NAME, 20)
        self.dim = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        self.dim.fill((0, 0, 0, 170))

    def handle_event(self, monitor, event):
        if (monitor.state == ConnectionMonitor.OUTDATED and event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1 and self.reload_button.collidepoint(event.pos)):
            return "reload"
        return None

    def draw(self, screen, monitor):
        if not monitor.is_blocking:
            return
        screen.blit(self.dim, (0, 0))
        pygame.draw.rect(screen, self.PANEL_COLOR, self.panel_rect, border_radius=10)
        pygame.draw.rect(screen, self.BORDER_COLOR, self.panel_rect, 2, border_radius=10)
        if monitor.state == ConnectionMonitor.OUTDATED:
            self._draw_outdated(screen)
        else:
            self._draw_offline(screen, monitor)

    def _draw_offline(self, screen, monitor):
        seconds = math.ceil(monitor.remaining_seconds() or 0)
        self._blit_center(screen, self.title_font, "Связь с сервером потеряна", self.TITLE_COLOR, 60)
        self._blit_center(screen, self.text_font, "Пытаемся переподключиться...", self.TEXT_COLOR, 110)
        self._blit_center(screen, self.text_font, f"Игра закроется через {seconds} с", self.TEXT_COLOR, 150)

    def _draw_outdated(self, screen):
        self._blit_center(screen, self.title_font, "Клиент устарел", self.TITLE_COLOR, 50)
        self._blit_center(screen, self.text_font, "На сервере обновлена версия игры.", self.TEXT_COLOR, 95)
        self._blit_center(screen, self.text_font, "Перезагрузите клиент, чтобы продолжить.", self.TEXT_COLOR, 125)
        draw_button(screen, self.reload_button, "Перезагрузить клиент", self.button_font,
                    color=(84, 111, 83), hover_color=(103, 143, 98), text_color=(245, 241, 224))

    def _blit_center(self, screen, font, text, color, top_offset):
        surface = font.render(text, True, color)
        screen.blit(surface, surface.get_rect(midtop=(self.panel_rect.centerx, self.panel_rect.top + top_offset)))
