"""
Панель инвентаря персонажа - доступна везде через кнопку в верхнем углу
Показывает карточку персонажа слева и инвентарь справа
"""

import pygame
from pathlib import Path
from core import settings


class InventoryPanel:
    """Панель инвентаря с карточкой персонажа и табуляцией"""
    
    def __init__(self, session, small_font, font, large_font):
        self.session = session
        self.small_font = small_font
        self.font = font
        self.large_font = large_font
        self.visible = False
        self.current_tab = "inventory"
        
        # Инвентарь
        self.inventory_data = []
        self.selected_item = None
        
        # Портрет персонажа
        self.portrait = None
        self._load_portrait()
        
        # Кнопка открытия инвентаря (верхний правый угол)
        self.open_button = pygame.Rect(settings.WIDTH - 60, 10, 50, 50)
        
        # Закладки (вкладки) - под информацией о персонаже
        self.tab_buttons = {
            "inventory": pygame.Rect(50, 550, 140, 40),
            "personal": pygame.Rect(200, 550, 140, 40),
            "battle": pygame.Rect(350, 550, 160, 40),
        }
        
        self.tab_labels = {
            "inventory": "🎒 РЮКЗАК",
            "personal": "👤 ЛИЧНЫЕ",
            "battle": "⚔️ БОЕВЫЕ",
        }
        
        # Позиция карточки (левая сторона)
        self.card_width = 420
        self.card_height = 520
        self.card_x = 40
        self.card_y = 30
        self.card_rect = pygame.Rect(self.card_x, self.card_y, self.card_width, self.card_height)
    
    def _load_portrait(self):
        """Загружает портрет персонажа"""
        try:
            char = self.session.character
            char_name = char.get('name', 'Unknown').lower()
            portrait_path = Path(__file__).resolve().parent.parent / "assets" / "characters" / f"{char_name}.png"
            
            if portrait_path.exists():
                self.portrait = pygame.image.load(str(portrait_path)).convert_alpha()
        except Exception:
            self.portrait = None
    
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
            for tab_key, rect in self.tab_buttons.items():
                if rect.collidepoint(mouse_pos):
                    self.current_tab = tab_key
                    self.selected_item = None
                    return True
            
            # Клик по ячейкам сетки (справа от карточки)
            col, row = self._get_clicked_inventory_cell(mouse_pos)
            if col is not None and row is not None:
                index = row * 5 + col  # 5 колонок справа
                if index < len(self.inventory_data):
                    self.selected_item = self.inventory_data[index]
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
        
        # Рисуем карточку персонажа
        self._draw_character_card(screen)
        
        # Рисуем закладки
        self._draw_tabs(screen)
        
        # Рисуем инвентарь (справа от карточки)
        self._draw_inventory_content(screen)
    
    def _draw_character_card(self, screen):
        """Рисует карточку персонажа слева"""
        # Фон карточки с рамкой
        pygame.draw.rect(screen, (30, 25, 20), self.card_rect)
        pygame.draw.rect(screen, (100, 180, 255), self.card_rect, 3)
        
        char = self.session.character
        y = self.card_y + 15
        
        # Имя и ID
        name_text = self.large_font.render(char['name'], True, (220, 200, 150))
        screen.blit(name_text, (self.card_x + 15, y))
        
        id_text = self.small_font.render(f"ID: {char.get('id', 0)}", True, (150, 150, 150))
        screen.blit(id_text, (self.card_x + 200, y))
        
        # Уровень и XP
        y += 35
        level_text = self.small_font.render(
            f"Уровень {char.get('level', 1)}",
            True,
            (200, 200, 200)
        )
        screen.blit(level_text, (self.card_x + 15, y))
        
        xp = char.get('experience', 0)
        xp_next = char.get('experience_to_next', 100)
        xp_text = self.small_font.render(
            f"XP: {xp}/{xp_next}",
            True,
            (255, 150, 100)
        )
        screen.blit(xp_text, (self.card_x + 200, y))
        
        # HP полоса
        y += 40
        hp_label = self.small_font.render("HP", True, (200, 100, 100))
        screen.blit(hp_label, (self.card_x + 15, y))
        
        hp_max = char.get('max_health', 100)
        hp_current = char.get('health', hp_max)
        hp_text = self.small_font.render(f"{hp_current}/{hp_max}", True, (200, 100, 100))
        screen.blit(hp_text, (self.card_x + 330, y))
        
        bar_width = self.card_width - 30
        bar_height = 15
        bar_x = self.card_x + 15
        bar_y = y + 22
        
        pygame.draw.rect(screen, (50, 30, 30), (bar_x, bar_y, bar_width, bar_height))
        
        if hp_max > 0:
            hp_fill = int((hp_current / hp_max) * bar_width)
            pygame.draw.rect(screen, (220, 80, 80), (bar_x, bar_y, hp_fill, bar_height))
        
        pygame.draw.rect(screen, (150, 100, 100), (bar_x, bar_y, bar_width, bar_height), 2)
        
        # MP полоса
        y += 50
        mp_label = self.small_font.render("MP", True, (100, 150, 200))
        screen.blit(mp_label, (self.card_x + 15, y))
        
        mp_max = char.get('max_mana', 50)
        mp_current = char.get('mana', mp_max)
        mp_text = self.small_font.render(f"{mp_current}/{mp_max}", True, (100, 150, 200))
        screen.blit(mp_text, (self.card_x + 330, y))
        
        bar_y = y + 22
        
        pygame.draw.rect(screen, (30, 50, 80), (bar_x, bar_y, bar_width, bar_height))
        
        if mp_max > 0:
            mp_fill = int((mp_current / mp_max) * bar_width)
            pygame.draw.rect(screen, (100, 180, 255), (bar_x, bar_y, mp_fill, bar_height))
        
        pygame.draw.rect(screen, (100, 150, 200), (bar_x, bar_y, bar_width, bar_height), 2)
    
    def _draw_tabs(self, screen):
        """Рисует закладки"""
        for tab_key, rect in self.tab_buttons.items():
            is_active = tab_key == self.current_tab
            
            bg_color = (100, 160, 255) if is_active else (80, 100, 140)
            text_color = (255, 255, 255) if is_active else (150, 150, 150)
            
            pygame.draw.rect(screen, bg_color, rect, border_radius=4)
            pygame.draw.rect(screen, (150, 150, 170), rect, 2, border_radius=4)
            
            label = self.tab_labels[tab_key]
            label_surface = self.small_font.render(label, True, text_color)
            label_rect = label_surface.get_rect(center=rect.center)
            screen.blit(label_surface, label_rect)
    
    def _draw_inventory_content(self, screen):
        """Рисует содержимое инвентаря справа от карточки"""
        # Сетка предметов (5 колонок, 10 рядов) справа от карточки
        content_x = self.card_x + self.card_width + 40
        content_y = self.card_y + 50
        
        cols = 5
        rows = 10
        cell_size = 50
        
        # Фон сетки
        grid_width = cols * cell_size
        grid_height = rows * cell_size
        grid_rect = pygame.Rect(content_x, content_y, grid_width, grid_height)
        pygame.draw.rect(screen, (20, 20, 30), grid_rect)
        pygame.draw.rect(screen, (100, 100, 120), grid_rect, 2)
        
        # Ячейки
        for row in range(rows):
            for col in range(cols):
                x = content_x + col * cell_size
                y = content_y + row * cell_size
                cell_rect = pygame.Rect(x, y, cell_size, cell_size)
                
                index = row * cols + col
                
                if index < len(self.inventory_data):
                    item = self.inventory_data[index]
                    is_selected = self.selected_item and self.selected_item.get("item_id") == item.get("item_id")
                    cell_color = (150, 200, 255) if is_selected else (70, 90, 120)
                    pygame.draw.rect(screen, cell_color, cell_rect)
                    
                    # Иконка
                    icon_text = self.font.render(item.get("icon", "📦"), True, (255, 255, 255))
                    icon_rect = icon_text.get_rect(center=cell_rect.center)
                    screen.blit(icon_text, icon_rect)
                else:
                    pygame.draw.rect(screen, (50, 50, 60), cell_rect)
                
                pygame.draw.rect(screen, (100, 100, 120), cell_rect, 1)
        
        # Информация о выбранном предмете
        if self.selected_item:
            info_y = content_y + grid_height + 15
            item_name = self.font.render(f"🔹 {self.selected_item['name']}", True, (220, 200, 150))
            screen.blit(item_name, (content_x, info_y))
    
    def _get_clicked_inventory_cell(self, mouse_pos):
        """Определяет какая ячейка была кликнута"""
        content_x = self.card_x + self.card_width + 40
        content_y = self.card_y + 50
        cols = 5
        rows = 10
        cell_size = 50
        
        x, y = mouse_pos
        
        grid_end_x = content_x + cols * cell_size
        grid_end_y = content_y + rows * cell_size
        
        if x < content_x or x > grid_end_x or y < content_y or y > grid_end_y:
            return None, None
        
        col = (x - content_x) // cell_size
        row = (y - content_y) // cell_size
        
        return col, row
    
    def _load_inventory(self):
        """Загружает инвентарь с сервера"""
        try:
            self.inventory_data = self.session.client.get_inventory(self.session.character["id"])
        except Exception as e:
            print(f"Ошибка загрузки инвентаря: {e}")
            self.inventory_data = []
