import pygame

from client.network import ServerError
from combat.character_stats import PROFESSIONS
from core import settings
from ui.hud import draw_button, draw_text


class CreateCharacterScene:
    # Emojis and basic info for each class
    CLASS_INFO = {
        "warrior": {"emoji": "⚔️", "name": "БОЕЦ"},
        "archer": {"emoji": "🏹", "name": "ЛУЧНИК"},
        "assassin": {"emoji": "🗡️", "name": "АСАСИН"},
        "battle_mage": {"emoji": "🔥", "name": "БОЙ. МАГ"},
        "support_mage": {"emoji": "💚", "name": "МАГ ПОДД."},
        "harmonist": {"emoji": "🎶", "name": "ГАРМОНИСТ"},
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

        # Profession selection - 6 classes in 2 rows of 3
        self.profession = "warrior"  # Default profession
        self.profession_buttons = {}
        button_width = 280
        button_height = 120
        start_x = 180
        start_y = 170
        spacing_x = 320
        spacing_y = 160

        professions = ["warrior", "archer", "assassin", "battle_mage", "support_mage", "harmonist"]
        for i, prof in enumerate(professions):
            row = i // 3
            col = i % 3
            x = start_x + col * spacing_x
            y = start_y + row * spacing_y
            self.profession_buttons[prof] = pygame.Rect(x, y, button_width, button_height)

        # Action buttons
        self.create_button = pygame.Rect(600, 550, 300, 50)
        self.back_button = pygame.Rect(950, 550, 300, 50)

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

        # Draw all 6 class buttons
        for profession, rect in self.profession_buttons.items():
            is_selected = self.profession == profession
            border_color = (100, 200, 100) if is_selected else (70, 140, 220)

            # Button background
            pygame.draw.rect(screen, (30, 34, 48), rect, border_radius=6)
            pygame.draw.rect(screen, border_color, rect, width=3 if is_selected else 2, border_radius=6)

            # Get profession data
            prof_data = PROFESSIONS.get(profession, {})
            class_info = self.CLASS_INFO.get(profession, {})

            # Class name with emoji
            emoji = class_info.get("emoji", "")
            name = class_info.get("name", profession)
            class_text = self.font.render(f"{emoji} {name}", True, (240, 240, 245))
            screen.blit(class_text, class_text.get_rect(center=(rect.centerx, rect.y + 20)))

            # Class stats
            hp = prof_data.get("hp", 0)
            mana = prof_data.get("mana", 0)
            resource_name = prof_data.get("unique_resource_name", "")

            stats_text = f"HP: {hp} | Мана: {mana}"
            stats_surf = self.tiny_font.render(stats_text, True, (180, 180, 200))
            screen.blit(stats_surf, (rect.x + 10, rect.y + 48))

            resource_text = f"Ресурс: {resource_name}"
            resource_surf = self.tiny_font.render(resource_text, True, (150, 180, 220))
            screen.blit(resource_surf, (rect.x + 10, rect.y + 68))

        # Create button
        draw_button(screen, self.create_button, "СОЗДАТЬ", self.font, color=(70, 140, 220))

        # Back button
        draw_button(screen, self.back_button, "НАЗАД", self.font, color=(220, 100, 100))

        # Error message
        if self.error:
            draw_text(screen, self.small_font, self.error, 640, 620, (255, 100, 100))

    def close(self):
        pass
