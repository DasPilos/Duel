"""
Панель инвентаря персонажа - открывает карточку персонажа с закладками
"""

import pygame
from core import settings
from ui.character_card import CharacterCard


class InventoryPanel:
    """Панель инвентаря с карточкой персонажа и закладками"""
    
    def __init__(self, session, small_font, font, large_font=None):
        self.session = session
        self.small_font = small_font
        self.font = font
        self.large_font = large_font or pygame.font.SysFont(settings.FONT_NAME, 32)
        self.visible = False
        
        # Карточка персонажа
        self.character_card = CharacterCard()
        self.card_frame = pygame.Rect(40, 30, 430, 550)
        
        # Кнопка открытия инвентаря (верхний правый угол)
        self.open_button = pygame.Rect(settings.WIDTH - 60, 10, 50, 50)
    
    def toggle_visibility(self):
        """Переключить видимость панели"""
        self.visible = not self.visible
        if self.visible:
            self._load_inventory()
    
    def handle_event(self, event):
        """Обработка событий"""
        if not self.visible:
            return False
        
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.visible = False
                return True
        
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos
            
            # Клик по закладкам
            for tab_idx, tab_name in enumerate(["character", "inventory", "personal", "battle"]):
                tab_rect = self.character_card.get_tab_rect(self.card_frame, tab_idx)
                if tab_rect.collidepoint(mouse_pos):
                    self.character_card.set_tab(tab_name)
                    return True
        
        return False
    
    def draw(self, screen):
        """Рисует панель инвентаря"""
        # Кнопка открытия инвентаря в верхнем правом углу
        pygame.draw.rect(screen, (100, 100, 120), self.open_button)
        pygame.draw.rect(screen, (150, 150, 170), self.open_button, 2)
        btn_text = self.font.render("📦", True, (255, 255, 255))
        btn_rect = btn_text.get_rect(center=self.open_button.center)
        screen.blit(btn_text, btn_rect)
        
        if not self.visible:
            return
        
        # Фон (полупрозрачный оверлей)
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        screen.blit(overlay, (0, 0))
        
        # Рисуем карточку персонажа с закладками
        self.character_card.draw(
            screen,
            self.card_frame,
            profile=self.session.character,
            border_color=(100, 180, 120),
            editable=False,
            show_tabs=True  # Показываем закладки!
        )
    
    def _load_inventory(self):
        """Загружает инвентарь с сервера"""
        try:
            # TODO: загружать реальные данные инвентаря
            pass
        except Exception as e:
            print(f"Ошибка загрузки инвентаря: {e}")
