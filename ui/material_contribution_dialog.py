import pygame

from core.carry_weight import GREEN, RED, YELLOW
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
        self.mode = "contribute"
        self.carried_weight_kg = 0.0
        self.carry_capacity_kg = 0.0
        self.item_weight_kg = 0.0
        self.dragging = False
        self.rect = pygame.Rect(0, 0, self.WIDTH, self.HEIGHT)
        self.track_rect = pygame.Rect(0, 0, 0, 0)
        self.confirm_button = pygame.Rect(0, 0, 0, 0)
        self.cancel_button = pygame.Rect(0, 0, 0, 0)

    def open(self, item_key, label, available, remaining, mode="deposit",
             weight_state=None, item_weight_kg=0.0):
        self.item_key = item_key
        self.label = label
        self.mode = mode
        self.available = max(0, int(available))
        self.maximum = min(self.available, max(0, int(remaining)))
        self.quantity = 0
        weight_state = weight_state or {}
        self.carried_weight_kg = float(weight_state.get("carried_weight_kg", 0))
        self.carry_capacity_kg = float(weight_state.get("carry_capacity_kg", 0))
        self.item_weight_kg = max(0.0, float(item_weight_kg or 0))
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
        title = {"withdraw": "Забрать", "deposit": "Пополнение склада"}.get(self.mode, "Взнос")
        screen.blit(scene.font.render(f"{title}: {self.label}", True, (230, 215, 184)),
                (self.rect.left + 62, self.rect.top + 20))
        available_label = "На складе" if self.mode == "withdraw" else "В рюкзаке"
        available_text = f"{available_label}: {self.available}"
        if self.mode == "withdraw":
            available_text += f" · можно взять сейчас: {self.maximum}"
        screen.blit(scene.small_font.render(available_text, True, (190, 187, 170)),
                    (self.rect.left + 24, self.rect.top + 76))
        chosen_label = "Забрать" if self.mode == "withdraw" else "Внести"
        chosen_total = self.available if self.mode == "withdraw" else self.maximum
        chosen = scene.small_font.render(f"{chosen_label}: {self.quantity} / {chosen_total}", True,
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
        if self.mode == "withdraw":
            resulting_weight = self.carried_weight_kg + self.quantity * self.item_weight_kg
            if resulting_weight >= self.carry_capacity_kg and self.carry_capacity_kg > 0:
                weight_color = RED
            elif (self.carry_capacity_kg > 0
                  and resulting_weight / self.carry_capacity_kg > 0.8):
                weight_color = YELLOW
            else:
                weight_color = GREEN
            weight_text = (f"Вес после забора: {resulting_weight:g} / "
                           f"{self.carry_capacity_kg:g} кг")
            screen.blit(scene.small_font.render(weight_text, True, weight_color),
                        (self.rect.left + 24, self.rect.top + 145))
            note_text = "Выбранное количество будет помещено в рюкзак"
        elif self.mode == "deposit":
            note_text = "Выбранное количество поступит в общий запас здания"
        else:
            note_text = "Внесённые материалы пойдут на улучшение здания"
        note = scene.small_font.render(note_text, True, (186, 191, 174))
        screen.blit(note, (self.rect.left + 24, self.rect.top + (170 if self.mode == "withdraw" else 151)))

        self.cancel_button = pygame.Rect(self.rect.right - 278, self.rect.bottom - 58, 112, 36)
        self.confirm_button = pygame.Rect(self.rect.right - 152, self.rect.bottom - 58, 128, 36)
        draw_button(screen, self.cancel_button, "ОТМЕНА", scene.small_font, color=(58, 55, 49))
        confirm_label = "ЗАБРАТЬ" if self.mode == "withdraw" else "ВНЕСТИ"
        draw_button(screen, self.confirm_button, confirm_label, scene.small_font,
                    color=(74, 126, 69) if self.quantity else (51, 54, 48),
                    text_color=(238, 235, 217) if self.quantity else (142, 144, 134))