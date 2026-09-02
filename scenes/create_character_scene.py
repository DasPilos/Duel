import pygame

from client.network import ServerError
from core import settings
from ui.hud import draw_button, draw_text


class CreateCharacterScene:
    def __init__(self, session):
        self.session = session
        self.finished = False
        self.cancelled = False
        self.error = ""
        self.created_character = None
        self.font = pygame.font.SysFont(settings.FONT_NAME, 22)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 18)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 36)
        
        # Character name input
        self.name = ""
        self.name_rect = pygame.Rect(640, 200, 600, 46)
        
        # Profession selection
        self.profession = "warrior"  # Default profession
        self.warrior_button = pygame.Rect(400, 350, 250, 80)
        self.mage_button = pygame.Rect(1200, 350, 250, 80)
        
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
            # Select profession
            if self.warrior_button.collidepoint(event.pos):
                self.profession = "warrior"
                return
            if self.mage_button.collidepoint(event.pos):
                self.profession = "mage"
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
        screen.blit(title, title.get_rect(center=(960, 80)))
        
        # Name input label
        draw_text(screen, self.font, "Имя персонажа:", 640, 160, (200, 200, 200))
        
        # Name input field
        pygame.draw.rect(screen, (28, 30, 43), self.name_rect, border_radius=6)
        pygame.draw.rect(screen, (70, 140, 220), self.name_rect, width=2, border_radius=6)
        draw_text(screen, self.font, self.name, self.name_rect.x + 12, self.name_rect.y + 10, (240, 240, 245))
        
        # Profession selection label
        draw_text(screen, self.font, "Выберите профессию:", 500, 300, (200, 200, 200))
        
        # Warrior button
        warrior_border = (100, 200, 100) if self.profession == "warrior" else (70, 140, 220)
        pygame.draw.rect(screen, (30, 34, 48), self.warrior_button, border_radius=6)
        pygame.draw.rect(screen, warrior_border, self.warrior_button, width=3, border_radius=6)
        warrior_text = self.font.render("⚔️ БОЕЦ", True, (240, 240, 245))
        screen.blit(warrior_text, warrior_text.get_rect(center=self.warrior_button.center))
        
        # Mage button
        mage_border = (100, 200, 100) if self.profession == "mage" else (70, 140, 220)
        pygame.draw.rect(screen, (30, 34, 48), self.mage_button, border_radius=6)
        pygame.draw.rect(screen, mage_border, self.mage_button, width=3, border_radius=6)
        mage_text = self.font.render("🔮 МАГ", True, (240, 240, 245))
        screen.blit(mage_text, mage_text.get_rect(center=self.mage_button.center))
        
        # Create button
        draw_button(screen, self.create_button, "СОЗДАТЬ", self.font, color=(70, 140, 220))
        
        # Back button
        draw_button(screen, self.back_button, "НАЗАД", self.font, color=(220, 100, 100))
        
        # Error message
        if self.error:
            draw_text(screen, self.small_font, self.error, 640, 620, (255, 100, 100))

    def close(self):
        pass
