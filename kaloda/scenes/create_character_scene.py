import pygame

from client.network import ServerError
from kaloda import settings
from kaloda.combat.character_stats import PROFESSIONS
from kaloda.ui.class_identity import class_icon, class_palette
from kaloda.ui.hud import draw_button, draw_text


class CreateCharacterScene:
    CLASS_INFO = {
        "warrior": {"name": "БОЕЦ"},
        "archer": {"name": "ЛУЧНИК"},
        "assassin": {"name": "АСАСИН"},
        "mage": {"name": "МАГ"},
        "necromancer": {"name": "НЕКРОМАНТ"},
    }

    def __init__(self, session):
        self.session = session
        self.finished = False
        self.cancelled = False
        self.error = ""
        self.created_character = None
        self.font = pygame.font.SysFont(settings.FONT_NAME, 22)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 16)
        self.tiny_font = pygame.font.SysFont(settings.FONT_NAME, 14)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 36)

        # Character name input
        self.name = ""
        self.name_rect = pygame.Rect(640, 80, 600, 46)

        # Six square class tiles arranged in a 3x2 grid, centered on screen.
        self.profession = "warrior"  # Default profession
        self.profession_buttons = {}
        button_size = 190
        gap = 28
        grid_left = settings.WIDTH // 2 - (button_size * 3 + gap * 2) // 2
        grid_top = 170

        professions = ["warrior", "archer", "assassin", "mage", "necromancer"]
        for i, prof in enumerate(professions):
            row, col = divmod(i, 3)
            x = grid_left + col * (button_size + gap)
            y = grid_top + row * (button_size + gap)
            self.profession_buttons[prof] = pygame.Rect(x, y, button_size, button_size)

        # Action buttons
        self.create_button = pygame.Rect(600, 650, 300, 50)
        self.back_button = pygame.Rect(950, 650, 300, 50)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                # Back to character selection
                self.cancelled = True
                self.finished = True
            elif event.key == pygame.K_BACKSPACE:
                self.name = self.name[:-1]
            elif event.key == pygame.K_RETURN:
                self.create()
        elif event.type == pygame.TEXTINPUT:
            if len(self.name) < 15:
                self.name += event.text
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Select profession - check all 6 class buttons
            for profession, rect in self.profession_buttons.items():
                if rect.collidepoint(event.pos):
                    self.profession = profession
                    return

            # Create button
            if self.create_button.collidepoint(event.pos):
                self.create()
                return

            # Back button
            if self.back_button.collidepoint(event.pos):
                self.cancelled = True
                self.finished = True
                return

            # Click on name input
            if self.name_rect.collidepoint(event.pos):
                pass  # Name input is always active

    def create(self):
        name = self.name.strip()
        if not name:
            self.error = "Введите имя персонажа"
            return
        
        try:
            character = self.session.create_character(name, profession_type=self.profession)
            self.created_character = character
            self.finished = True
        except ServerError as error:
            self.error = str(error)

    def update(self, dt):
        pass

    def draw(self, screen):
        screen.fill((16, 18, 28))

        # Title
        title = self.title_font.render("СОЗДАНИЕ ПЕРСОНАЖА", True, (240, 240, 255))
        screen.blit(title, title.get_rect(center=(960, 30)))

        # Name input label
        draw_text(screen, self.small_font, "Имя персонажа:", 450, 60, (200, 200, 200))

        # Name input field
        pygame.draw.rect(screen, (28, 30, 43), self.name_rect, border_radius=6)
        pygame.draw.rect(screen, (70, 140, 220), self.name_rect, width=2, border_radius=6)
        draw_text(screen, self.font, self.name, self.name_rect.x + 12, self.name_rect.y + 8, (240, 240, 245))

        # Profession selection label
        draw_text(screen, self.small_font, "Выберите класс:", 450, 150, (200, 200, 200))

        # Draw all class tiles in their class colors
        for profession, rect in self.profession_buttons.items():
            is_selected = self.profession == profession
            palette = class_palette(profession)

            pygame.draw.rect(screen, palette["background"], rect)
            pygame.draw.rect(screen, palette["accent"], rect, width=5 if is_selected else 2)

            # Class icon (same as in game) followed by the class name
            prof_data = PROFESSIONS.get(profession, {})
            name = self.CLASS_INFO.get(profession, {}).get("name", profession)
            icon = class_icon(profession)
            name_surf = self.font.render(name, True, palette["accent"])
            name_width = icon.get_width() + 8 + name_surf.get_width()
            name_left = rect.centerx - name_width // 2
            name_y = rect.y + 34
            screen.blit(icon, icon.get_rect(midleft=(name_left, name_y)))
            screen.blit(name_surf, name_surf.get_rect(midleft=(name_left + icon.get_width() + 8, name_y)))

            # Class stats
            hp = prof_data.get("hp", 0)
            mana = prof_data.get("mana", 0)
            resource_name = prof_data.get("unique_resource_name", "")

            stats_surf = self.tiny_font.render(f"HP: {hp} | Мана: {mana}", True, (225, 225, 235))
            screen.blit(stats_surf, stats_surf.get_rect(center=(rect.centerx, rect.y + 86)))

            resource_surf = self.tiny_font.render(f"Ресурс: {resource_name}", True, palette["accent"])
            screen.blit(resource_surf, resource_surf.get_rect(center=(rect.centerx, rect.y + 112)))

        # Create button
        draw_button(screen, self.create_button, "СОЗДАТЬ", self.font, color=(70, 140, 220))

        # Back button
        draw_button(screen, self.back_button, "НАЗАД", self.font, color=(220, 100, 100))

        # Error message
        if self.error:
            draw_text(screen, self.small_font, self.error, 640, 720, (255, 100, 100))

    def close(self):
        pass
