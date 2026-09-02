"""Profession selection scene - choose between Warrior or Mage"""

import pygame
from core import settings
from ui.hud import draw_button, draw_text


class ProfessionSelectScene:
    """Scene for selecting character profession before creation"""
    
    def __init__(self, session, character_name, character_id):
        self.session = session
        self.character_name = character_name
        self.character_id = character_id  # ID персонажа, который был создан
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
        
        # Profession buttons
        self.warrior_button = pygame.Rect(400, 400, 300, 300)
        self.mage_button = pygame.Rect(1200, 400, 300, 300)
        
        # Create button
        self.create_button = pygame.Rect(960 - 150, 900, 300, 60)
        
        # Back button
        self.back_button = pygame.Rect(50, 50, 120, 50)
        
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
                self.cancel()
                return
            elif event.key == pygame.K_RETURN:
                if self.selected_profession:
                    self.create()
                return
        
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            
            # Click on back button
            if self.back_button.collidepoint(pos):
                self.cancel()
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
                if self.selected_profession:
                    self.create()
                return

    def cancel(self):
        """Cancel profession selection and delete the character"""
        try:
            # Delete the character since user cancelled profession selection
            self.session.delete_character(self.character_id)
        except Exception as e:
            print(f"Error deleting character: {e}")
        
        self.cancelled = True
        self.finished = True

    def create(self):
        """Update character profession after selection"""
        profession = self.selected_profession
        
        try:
            # Update character with the selected profession
            self.session.update_character_profession(self.character_id, profession)
            self.finished = True
        except Exception as error:
            self.error = str(error)

    def update(self, dt):
        """Update scene state"""
        pass

    def draw(self, screen):
        """Draw the profession selection screen"""
        screen.fill((16, 18, 28))
        
        # Draw back button
        mouse_pos = pygame.mouse.get_pos()
        back_hover = self.back_button.collidepoint(mouse_pos)
        back_color = (100, 120, 150) if back_hover else (80, 90, 120)
        
        pygame.draw.rect(screen, back_color, self.back_button)
        pygame.draw.rect(screen, (120, 140, 170) if back_hover else (100, 110, 140), self.back_button, 2)
        
        back_text = self.small_font.render("НАЗАД", True, (200, 200, 200))
        screen.blit(back_text, back_text.get_rect(center=self.back_button.center))
        
        # Title
        title = self.title_font.render("ВЫБОР ПРОФЕССИИ", True, (240, 240, 255))
        screen.blit(title, title.get_rect(center=(960, self.title_y)))
        
        # Subtitle with character name
        subtitle = self.small_font.render(f"Персонаж: {self.character_name} - Выберите путь", True, (170, 170, 170))
        screen.blit(subtitle, subtitle.get_rect(center=(960, self.subtitle_y)))
        
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
        instructions = "ESC/Назад - Отмена | Нажмите на профессию для выбора | Введите имя и нажмите Создать"
        instr_text = self.description_font.render(instructions, True, (120, 120, 120))
        screen.blit(instr_text, instr_text.get_rect(center=(960, 1050)))
    
    def close(self):
        """Cleanup when scene closes"""
        pass
