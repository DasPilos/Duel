import pygame

from ui.catalog_icons import draw_item_icon
from ui.hud import draw_button


class MaterialContributionDialog:
    WIDTH = 560
    HEIGHT = 260

    def __init__(self, scene):
        self.scene = scene
        self.is_open = False
        self.item_key = None
        self.label = ""
        self.available = 0
        self.maximum = 0
        self.quantity = 0
        self.dragging = False
        self.rect = pygame.Rect(0, 0, self.WIDTH, self.HEIGHT)
        self.track_rect = pygame.Rect(0, 0, 0, 0)
        self.confirm_button = pygame.Rect(0, 0, 0, 0)
        self.cancel_button = pygame.Rect(0, 0, 0, 0)

    def open(self, item_key, label, available, remaining):
        self.item_key = item_key
        self.label = label
        self.available = max(0, int(available))
        self.maximum = min(self.available, max(0, int(remaining)))
        self.quantity = 0
        self.dragging = False
        self.is_open = True

    def handle_event(self, event):
        if not self.is_open:
            return None
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.is_open = False
            self.dragging = False
            return None
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
            return None
        if event.type == pygame.MOUSEMOTION and self.dragging:
            self._set_quantity_from_x(event.pos[0])
            return None
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return None
        if self.confirm_button.collidepoint(event.pos):
            if self.quantity > 0:
                result = self.item_key, self.quantity
                self.is_open = False
                self.dragging = False
                return result
            return None
        if self.cancel_button.collidepoint(event.pos):
            self.is_open = False
            self.dragging = False
            return None
        if self.track_rect.inflate(24, 24).collidepoint(event.pos):
            self.dragging = True
            self._set_quantity_from_x(event.pos[0])
            return None
        if not self.rect.collidepoint(event.pos):
            self.is_open = False
            self.dragging = False
        return None

    def _set_quantity_from_x(self, x):
        if self.maximum <= 0:
            self.quantity = 0
            return
        ratio = (x - self.track_rect.left) / max(1, self.track_rect.width)
        self.quantity = round(max(0.0, min(1.0, ratio)) * self.maximum)

    def draw(self, screen):
        if not self.is_open:
            return
        self.rect.center = (screen.get_width() // 2, screen.get_height() // 2)
        shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 170))
        screen.blit(shade, (0, 0))
        pygame.draw.rect(screen, (30, 33, 29), self.rect, border_radius=6)
        pygame.draw.rect(screen, (177, 147, 91), self.rect, 2, border_radius=6)

        scene = self.scene
        draw_item_icon(screen, self.item_key, (self.rect.left + 24, self.rect.top + 17), 30)
        screen.blit(scene.font.render(f"Взнос: {self.label}", True, (230, 215, 184)),
                (self.rect.left + 62, self.rect.top + 20))
        screen.blit(scene.small_font.render(f"В рюкзаке: {self.available}", True, (190, 187, 170)),
                    (self.rect.left + 24, self.rect.top + 76))
        chosen = scene.small_font.render(f"Внести: {self.quantity} / {self.maximum}", True,
                                         (224, 211, 178))
        screen.blit(chosen, chosen.get_rect(topright=(self.rect.right - 24, self.rect.top + 76)))

        self.track_rect = pygame.Rect(self.rect.left + 28, self.rect.top + 120, self.rect.width - 56, 8)
        pygame.draw.rect(screen, (68, 72, 63), self.track_rect, border_radius=4)
        progress = 0 if self.maximum == 0 else self.quantity / self.maximum
        fill = pygame.Rect(self.track_rect.left, self.track_rect.top,
                           round(self.track_rect.width * progress), self.track_rect.height)
        if fill.width:
            pygame.draw.rect(screen, (145, 174, 104), fill, border_radius=4)
        knob_x = self.track_rect.left + round(self.track_rect.width * progress)
        pygame.draw.circle(screen, (229, 215, 182), (knob_x, self.track_rect.centery), 11)
        pygame.draw.circle(screen, (91, 88, 72), (knob_x, self.track_rect.centery), 11, 1)
        note = scene.small_font.render("Внесённые материалы нельзя забрать обратно", True, (186, 151, 126))
        screen.blit(note, (self.rect.left + 24, self.rect.top + 151))

        self.cancel_button = pygame.Rect(self.rect.right - 278, self.rect.bottom - 58, 112, 36)
        self.confirm_button = pygame.Rect(self.rect.right - 152, self.rect.bottom - 58, 128, 36)
        draw_button(screen, self.cancel_button, "ОТМЕНА", scene.small_font, color=(58, 55, 49))
        draw_button(screen, self.confirm_button, "ВНЕСТИ", scene.small_font,
                    color=(74, 126, 69) if self.quantity else (51, 54, 48),
                    text_color=(238, 235, 217) if self.quantity else (142, 144, 134))