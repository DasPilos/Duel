"""Profession selection scene - choose between Warrior or Mage"""

import pygame
from core import settings
from ui.hud import draw_button, draw_text


class ProfessionSelectScene:
    """Scene for selecting character profession before creation"""
    
    def __init__(self, session):
        self.session = session
        self.character_name = ""
        self.selected_profession = None  # 'warrior' or 'mage'
        self.finished = False
        self.cancelled = False
        self.error = ""
        
        # Fonts
        self.font = pygame.font.SysFont(settings.FONT_NAME, 22)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 18)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 42)
        self.description_font = pygame.font.SysFont(settings.FONT_NAME, 16)
        
        # UI Elements
        self.title_y = 100
        self.subtitle_y = 200
        
        # Name input
        self.name_input_rect = pygame.Rect(960 - 200, 280, 400, 50)
        self.name_input_active = False
        self.name_input_placeholder = "Введите имя персонажа"
        
        # Profession buttons
        self.warrior_button = pygame.Rect(400, 400, 300, 300)
        self.mage_button = pygame.Rect(1200, 400, 300, 300)
        
        # Create button
        self.create_button = pygame.Rect(960 - 150, 900, 300, 60)
        
        # Colors
        self.color_warrior = (100, 60, 40)
        self.color_warrior_hover = (150, 80, 50)
        self.color_warrior_selected = (200, 100, 60)
        
        self.color_mage = (60, 40, 100)
        self.color_mage_hover = (80, 50, 150)
        self.color_mage_selected = (100, 60, 200)
        
        self.color_text = (220, 220, 220)
        self.color_text_dark = (100, 100, 100)

    def handle_event(self, event):
        """Handle input events"""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.cancelled = True
                self.finished = True
                return
            elif event.key == pygame.K_BACKSPACE and self.name_input_active:
                self.character_name = self.character_name[:-1]
                return
            elif event.key == pygame.K_RETURN:
                if self.name_input_active and self.character_name.strip():
                    # Switch to profession selection if not already
                    self.name_input_active = False
                    return
                elif self.selected_profession and self.character_name.strip():
                    self.create()
                return
                
        elif event.type == pygame.TEXTINPUT and self.name_input_active:
            if len(self.character_name) < 20:
                self.character_name += event.text
                return
        
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            
            # Click on name input
            if self.name_input_rect.collidepoint(pos):
                self.name_input_active = True
                return
            
            # Click on profession buttons
            if self.warrior_button.collidepoint(pos):
                self.selected_profession = "warrior"
                return
            
            if self.mage_button.collidepoint(pos):
                self.selected_profession = "mage"
                return
            
            # Click on create button
            if self.create_button.collidepoint(pos):
                if self.selected_profession and self.character_name.strip():
                    self.create()
                return

    def create(self):
        """Create character with selected profession"""
        name = self.character_name.strip()
        profession = self.selected_profession
        
        try:
            # Pass profession type to session.create_character
            self.session.create_character(name, profession_type=profession)
            self.finished = True
        except Exception as error:
            self.error = str(error)

    def update(self, dt):
        """Update scene state"""
        pass

    def draw(self, screen):
        """Draw the profession selection screen"""
        screen.fill((16, 18, 28))
        
        # Title
        title = self.title_font.render("ВЫБОР ПРОФЕССИИ", True, (240, 240, 255))
        screen.blit(title, title.get_rect(center=(960, self.title_y)))
        
        # Subtitle
        subtitle = self.small_font.render("Создайте своего героя и выберите его путь", True, (170, 170, 170))
        screen.blit(subtitle, subtitle.get_rect(center=(960, self.subtitle_y)))
        
        # Name input section
        draw_text(screen, self.small_font, "Имя персонажа:", 400, 270, (170, 170, 170))
        
        # Draw name input box
        input_color = (100, 120, 150) if self.name_input_active else (80, 80, 100)
        pygame.draw.rect(screen, input_color, self.name_input_rect, 2)
        pygame.draw.rect(screen, (30, 30, 50), self.name_input_rect)
        
        # Draw name text
        if self.character_name:
            name_text = self.font.render(self.character_name, True, self.color_text)
            screen.blit(name_text, (self.name_input_rect.x + 10, self.name_input_rect.y + 12))
        else:
            placeholder = self.font.render(self.name_input_placeholder, True, self.color_text_dark)
            screen.blit(placeholder, (self.name_input_rect.x + 10, self.name_input_rect.y + 12))
        
        # Cursor
        if self.name_input_active:
            cursor_x = self.name_input_rect.x + 10 + (len(self.character_name) * 13)
            pygame.draw.line(screen, (200, 200, 200), (cursor_x, self.name_input_rect.y + 5), 
                           (cursor_x, self.name_input_rect.y + 45), 2)
        
        # Draw profession cards
        mouse_pos = pygame.mouse.get_pos()
        
        # WARRIOR CARD
        warrior_hover = self.warrior_button.collidepoint(mouse_pos)
        warrior_color = self.color_warrior_selected if self.selected_profession == "warrior" else \
                       (self.color_warrior_hover if warrior_hover else self.color_warrior)
        
        pygame.draw.rect(screen, warrior_color, self.warrior_button)
        pygame.draw.rect(screen, (150, 100, 80) if self.selected_profession != "warrior" else (200, 150, 100), 
                        self.warrior_button, 3)
        
        # Warrior icon and text
        warrior_title = self.title_font.render("⚔️", True, (240, 200, 150))
        screen.blit(warrior_title, warrior_title.get_rect(center=(self.warrior_button.centerx, self.warrior_button.y + 60)))
        
        warrior_name = self.font.render("ВОИН", True, self.color_text)
        screen.blit(warrior_name, warrior_name.get_rect(center=(self.warrior_button.centerx, self.warrior_button.y + 140)))
        
        warrior_desc_lines = [
            "Сила и выносливость",
            "Карты боевых действий",
            "Прямые атаки"
        ]
        y_offset = self.warrior_button.y + 180
        for line in warrior_desc_lines:
            desc = self.description_font.render(line, True, (200, 200, 200))
            screen.blit(desc, desc.get_rect(center=(self.warrior_button.centerx, y_offset)))
            y_offset += 30
        
        # MAGE CARD
        mage_hover = self.mage_button.collidepoint(mouse_pos)
        mage_color = self.color_mage_selected if self.selected_profession == "mage" else \
                    (self.color_mage_hover if mage_hover else self.color_mage)
        
        pygame.draw.rect(screen, mage_color, self.mage_button)
        pygame.draw.rect(screen, (100, 80, 150) if self.selected_profession != "mage" else (150, 120, 200), 
                        self.mage_button, 3)
        
        # Mage icon and text
        mage_title = self.title_font.render("🧙", True, (150, 200, 240))
        screen.blit(mage_title, mage_title.get_rect(center=(self.mage_button.centerx, self.mage_button.y + 60)))
        
        mage_name = self.font.render("МАГ", True, self.color_text)
        screen.blit(mage_name, mage_name.get_rect(center=(self.mage_button.centerx, self.mage_button.y + 140)))
        
        mage_desc_lines = [
            "Магия и элементы",
            "Система заклинаний",
            "Магические эффекты"
        ]
        y_offset = self.mage_button.y + 180
        for line in mage_desc_lines:
            desc = self.description_font.render(line, True, (200, 200, 200))
            screen.blit(desc, desc.get_rect(center=(self.mage_button.centerx, y_offset)))
            y_offset += 30
        
        # Create button (only enabled if profession selected and name entered)
        is_ready = bool(self.selected_profession and self.character_name.strip())
        
        button_color = (80, 120, 80) if is_ready else (60, 60, 80)
        button_text_color = (200, 255, 200) if is_ready else (150, 150, 150)
        
        pygame.draw.rect(screen, button_color, self.create_button)
        pygame.draw.rect(screen, (100, 150, 100) if is_ready else (100, 100, 100), self.create_button, 2)
        
        create_text = self.font.render("СОЗДАТЬ", True, button_text_color)
        screen.blit(create_text, create_text.get_rect(center=self.create_button.center))
        
        # Error message
        if self.error:
            error_text = self.small_font.render(f"Ошибка: {self.error}", True, (255, 100, 100))
            screen.blit(error_text, error_text.get_rect(center=(960, 1000)))
        
        # Instructions
        instructions = "ESC - Отмена | Нажмите на профессию для выбора | Введите имя и нажмите Создать"
        instr_text = self.description_font.render(instructions, True, (120, 120, 120))
        screen.blit(instr_text, instr_text.get_rect(center=(960, 1050)))
