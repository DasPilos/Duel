import pygame

from client.network import ServerError
from core import settings
from ui.hud import draw_button, draw_text


class CharacterScene:
    def __init__(self, session):
        self.session = session
        self.characters = []
        self.finished = False
        self.cancelled = False
        self.error = ""
        self.name = ""
        self.active = "name"
        self.font = pygame.font.SysFont(settings.FONT_NAME, 22)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 18)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 36)
        self.name_rect = pygame.Rect(760, 770, 400, 46)
        self.create_button = pygame.Rect(760, 840, 400, 50)
        self.character_list_rect = pygame.Rect(700, 240, 520, 500)
        self.character_rects = []
        self.character_scroll = 0
        self.max_visible_characters = 5
        self.refresh()

    def refresh(self):
        try:
            self.characters = self.session.list_characters()
            self.error = ""
        except ServerError as error:
            self.error = str(error)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.cancelled = True
                self.finished = True
            elif event.key == pygame.K_BACKSPACE:
                self.name = self.name[:-1]
            elif event.key == pygame.K_RETURN:
                self.create()
        elif event.type == pygame.TEXTINPUT:
            if len(self.name) < 15:
                self.name += event.text
        elif event.type == pygame.MOUSEWHEEL:
            if self.character_list_rect.collidepoint(pygame.mouse.get_pos()):
                max_scroll = max(0, len(self.characters) - self.max_visible_characters)
                self.character_scroll = max(0, min(max_scroll, self.character_scroll - event.y * 1))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for visible_index, rect in enumerate(self.character_rects):
                if rect.collidepoint(event.pos):
                    actual_index = visible_index + self.character_scroll
                    if 0 <= actual_index < len(self.characters):
                        self.session.select_character(self.characters[actual_index])
                        self.finished = True
                    return
            if self.name_rect.collidepoint(event.pos):
                self.active = "name"
            elif self.create_button.collidepoint(event.pos):
                self.create()

    def create(self):
        name = self.name.strip()
        try:
            self.session.create_character(name)
        except ServerError as error:
            self.error = str(error)
            return
        self.finished = True

    def update(self, dt):
        pass

    def draw(self, screen):
        screen.fill((16, 18, 28))
        title = self.title_font.render("ПЕРСОНАЖИ", True, (240, 240, 255))
        screen.blit(title, title.get_rect(center=(960, 130)))
        draw_text(screen, self.small_font, "Выберите героя или создайте нового", 760, 180, (170, 170, 170))

        max_scroll = max(0, len(self.characters) - self.max_visible_characters)
        self.character_scroll = min(self.character_scroll, max_scroll)
        visible_characters = self.characters[self.character_scroll:self.character_scroll + self.max_visible_characters]
        self.character_rects = []
        for visible_index, character in enumerate(visible_characters):
            rect = pygame.Rect(700, 240 + visible_index * 82, 520, 62)
            self.character_rects.append(rect)
            pygame.draw.rect(screen, (30, 34, 48), rect, border_radius=6)
            pygame.draw.rect(screen, (70, 140, 220), rect, width=2, border_radius=6)
            draw_text(screen, self.font, character["name"], rect.x + 18, rect.y + 8, (240, 240, 245))
            draw_text(screen, self.small_font, f"Уровень {character['level']}   HP {character['hp']}/{character['max_hp']}", rect.x + 18, rect.y + 34, (180, 185, 200))

        if len(self.characters) > self.max_visible_characters:
            bar_height = 360
            bar_x = 1235
            bar_y = 240
            pygame.draw.rect(screen, (30, 34, 48), pygame.Rect(bar_x, bar_y, 8, bar_height), border_radius=6)
            track = max(0, bar_height - 36)
            thumb_height = max(24, int(track * (self.max_visible_characters / max(1, len(self.characters)))))
            thumb_top = bar_y + 18 + int((track - thumb_height) * (self.character_scroll / max(1, max_scroll)))
            pygame.draw.rect(screen, (110, 150, 220), pygame.Rect(bar_x, thumb_top, 8, thumb_height), border_radius=6)

        draw_text(screen, self.font, "Имя нового персонажа", 760, 735, (205, 205, 215))
        pygame.draw.rect(screen, (28, 30, 43), self.name_rect, border_radius=6)
        pygame.draw.rect(screen, (70, 140, 220), self.name_rect, width=2, border_radius=6)
        draw_text(screen, self.font, self.name, self.name_rect.x + 12, self.name_rect.y + 10, (240, 240, 245))
        draw_button(screen, self.create_button, "СОЗДАТЬ И ВОЙТИ", self.font, color=(70, 140, 220))
        if self.error:
            draw_text(screen, self.small_font, self.error, 760, 920, (255, 100, 100))

    def close(self):
        pass
