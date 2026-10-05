"""Global online count and scheduled server-restart notice."""

import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pygame

from client.network import ServerError
from core import settings
from ui.hud import draw_button


class ServerStatusHUD:
    POLL_SECONDS = 5.0
    PANEL_COLOR = (25, 29, 31)
    BORDER_COLOR = (113, 133, 126)
    TEXT_COLOR = (230, 226, 211)
    NOTICE_COLOR = (255, 220, 144)

    def __init__(self):
        self.status = None
        self.session = None
        self.poll_elapsed = self.POLL_SECONDS
        self.notice_received_at = time.monotonic()
        self.server_time = None
        self.server_time_received_at = time.monotonic()
        self.server_timezone = "Europe/Kyiv"
        self.panel_rect = pygame.Rect(0, 0, 260, 38)
        self.restart_button = pygame.Rect(0, 0, 188, 30)
        self.font = pygame.font.SysFont(settings.FONT_NAME, 18)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 14)
        self.button_font = pygame.font.SysFont(settings.FONT_NAME, 15)

    def update(self, session, dt, *, visible):
        if session is None or not getattr(session, "character", None):
            self.session = None
            return
        self.session = session
        self.poll_elapsed += max(0.0, float(dt))
        if self.poll_elapsed < self.POLL_SECONDS:
            return
        self.poll_elapsed = 0.0
        try:
            status = session.client.get_server_status()
        except (ServerError, AttributeError, OSError):
            return
        old_notice = (self.status or {}).get("restart_notice")
        new_notice = status.get("restart_notice")
        if (old_notice or {}).get("restart_at") != (new_notice or {}).get("restart_at"):
            self.notice_received_at = time.monotonic()
        self.status = status
        if status.get("server_time") is not None:
            self.server_time = float(status["server_time"])
            self.server_time_received_at = time.monotonic()
            self.server_timezone = status.get("server_timezone", "Europe/Kyiv")

    def _server_clock_text(self):
        if self.server_time is None:
            return "--:--:--"
        estimated = self.server_time + max(0.0, time.monotonic() - self.server_time_received_at)
        return datetime.fromtimestamp(estimated, ZoneInfo(self.server_timezone)).strftime("%H:%M:%S")

    def handle_event(self, event):
        notice = (self.status or {}).get("restart_notice")
        if (notice and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.restart_button.collidepoint(event.pos)):
            return "restart_client"
        return None

    def draw(self, screen):
        if self.status is None:
            return
        notice = self.status.get("restart_notice")
        if notice:
            width, height = min(settings.WIDTH - 24, 760), 76
            self.panel_rect = pygame.Rect((settings.WIDTH - width) // 2, 10, width, height)
            self.restart_button = pygame.Rect(
                self.panel_rect.right - 204, self.panel_rect.centery - 15, 188, 30
            )
        else:
            width, height = 250, 36
            self.panel_rect = pygame.Rect((settings.WIDTH - width) // 2, 10, width, height)

        pygame.draw.rect(screen, self.PANEL_COLOR, self.panel_rect, border_radius=5)
        pygame.draw.rect(screen, self.BORDER_COLOR, self.panel_rect, 1, border_radius=5)
        online = max(0, int(self.status.get("online_players", 0)))
        server_clock = self._server_clock_text()
        if notice:
            elapsed = max(0, int(time.monotonic() - self.notice_received_at))
            remaining = max(0, int(notice.get("seconds_remaining", 0)) - elapsed)
            minutes, seconds = divmod(remaining, 60)
            title = f"{notice.get('message', 'Сервер получил обновление.')} Перезапуск через {minutes}:{seconds:02d}"
            screen.blit(self.small_font.render(title, True, self.NOTICE_COLOR),
                        (self.panel_rect.left + 14, self.panel_rect.top + 12))
            screen.blit(self.small_font.render(
                f"Онлайн: {online} · Сервер: {server_clock}. Если нужно, перезапустите клиент.",
                True, self.TEXT_COLOR,
            ), (self.panel_rect.left + 14, self.panel_rect.top + 42))
            draw_button(screen, self.restart_button, "Перезапустить клиент", self.button_font,
                        color=(84, 111, 83), hover_color=(103, 143, 98), text_color=(245, 241, 224))
        else:
            text = self.font.render(f"Игроков онлайн: {online}   {server_clock}", True, self.TEXT_COLOR)
            screen.blit(text, text.get_rect(center=self.panel_rect.center))