from collections import deque

import pygame

from core import settings
from ui.chat.widgets import _wrap_segments
from ui.hud import draw_text

HISTORY_LIMIT = 500
LINE_HEIGHT = 18
FULL_LOG_BACKGROUND_ALPHA = 220


class CombatLog:
    """Лог боя справа: записи появляются по одной, каждая видна 30 с и затем плавно гаснет."""

    def __init__(self):
        self.rect = pygame.Rect(settings.COMBAT_LOG_RECT)
        self.font = pygame.font.SysFont("arial", 14)
        self.title_font = pygame.font.SysFont("arial", 14, bold=True)
        self.clock = 0.0
        self.appear_timer = 0.0
        self.pending = deque()
        self.visible_entries = []
        self.history = deque(maxlen=HISTORY_LIMIT)
        self.full_open = False
        self.full_scroll = 0

    def add(self, text, color=(230, 230, 230)):
        entry = {"text": text, "color": color}
        self.pending.append(entry)
        self.history.append(entry)

    def captures_keyboard(self):
        return self.full_open

    def update(self, dt):
        self.clock += dt
        self.appear_timer += dt
        if self.pending and self.appear_timer >= settings.COMBAT_LOG_APPEAR_INTERVAL:
            self.appear_timer = 0.0
            entry = self.pending.popleft()
            entry["shown_at"] = self.clock
            self.visible_entries.append(entry)
        lifetime = settings.COMBAT_LOG_VISIBLE_SECONDS + settings.COMBAT_LOG_FADE_SECONDS
        self.visible_entries = [entry for entry in self.visible_entries if self.clock - entry["shown_at"] < lifetime]

    def entry_alpha(self, entry):
        age = self.clock - entry["shown_at"]
        if age < settings.COMBAT_LOG_VISIBLE_SECONDS:
            return 255
        fade = (age - settings.COMBAT_LOG_VISIBLE_SECONDS) / settings.COMBAT_LOG_FADE_SECONDS
        return max(0, int(255 * (1 - fade)))

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_l:
                self.toggle_full()
                return True
            if event.key == pygame.K_ESCAPE and self.full_open:
                self.full_open = False
                return True
            return self.full_open
        if self.full_open and event.type == pygame.MOUSEWHEEL:
            self.full_scroll = max(0, self.full_scroll - event.y * 3)
            return True
        if self.full_open and event.type in (pygame.MOUSEBUTTONDOWN, pygame.TEXTINPUT):
            return True
        return False

    def toggle_full(self):
        self.full_open = not self.full_open
        self.full_scroll = 0

    def _wrap(self, text, width):
        return ["".join(chunk for chunk, _ in line) for line in _wrap_segments([(text, (255, 255, 255))], self.font, width)]

    def draw(self, screen):
        self._draw_side_panel(screen)
        if self.full_open:
            self._draw_full_log(screen)

    def _draw_side_panel(self, screen):
        bottom = self.rect.bottom - 8
        for entry in reversed(self.visible_entries):
            lines = self._wrap(entry["text"], self.rect.width - 20)
            alpha = self.entry_alpha(entry)
            if alpha <= 0:
                continue
            for line in reversed(lines):
                if bottom - LINE_HEIGHT < self.rect.y + 8:
                    return
                bottom -= LINE_HEIGHT
                surface = self.font.render(line, True, entry["color"])
                surface.set_alpha(alpha)
                screen.blit(surface, (self.rect.x + 10, bottom))

    def _draw_full_log(self, screen):
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        screen.blit(overlay, (0, 0))
        panel = pygame.Rect(0, 0, 720, 640)
        panel.center = screen.get_rect().center
        background = pygame.Surface(panel.size, pygame.SRCALPHA)
        background.fill((22, 24, 34, FULL_LOG_BACKGROUND_ALPHA))
        screen.blit(background, panel.topleft)
        draw_text(screen, self.title_font, "Полный лог боя (L или ESC - закрыть, колесо - прокрутка)", panel.x + 14, panel.y + 12, (220, 200, 140))
        lines = []
        for entry in self.history:
            for line in self._wrap(entry["text"], panel.width - 28):
                lines.append((line, entry["color"]))
        visible_lines = (panel.height - 50) // LINE_HEIGHT
        max_scroll = max(0, len(lines) - visible_lines)
        self.full_scroll = min(self.full_scroll, max_scroll)
        start = max(0, len(lines) - visible_lines - self.full_scroll)
        y = panel.y + 42
        for line, color in lines[start:start + visible_lines]:
            draw_text(screen, self.font, line, panel.x + 14, y, color)
            y += LINE_HEIGHT
