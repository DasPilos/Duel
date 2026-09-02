import pygame
from core import settings


class BackpackPanel:
    """Панель инвентаря с сеткой 10x5 (50 ячеек по 50x50 пиксселей)"""
    
    def __init__(self):
        self.is_open = False
        self.cols = 10
        self.rows = 5
        self.cell_size = 50
        self.panel_width = self.cols * self.cell_size
        self.panel_height = self.rows * self.cell_size
        
        # Центрируем панель
        self.panel_x = (settings.WIDTH - self.panel_width) // 2
        self.panel_y = (settings.HEIGHT - self.panel_height) // 2
        
        # Цвет и отступ для ячеек
        self.cell_color = (60, 80, 100)
        self.cell_hover_color = (100, 120, 150)
        self.border_color = (150, 150, 170)
        self.border_width = 2
        self.cell_padding = 2
        
        # Для отслеживания ячеек
        self.cells = []
        self._init_cells()
    
    def _init_cells(self):
        """Инициализация ячеек"""
        self.cells = []
        for row in range(self.rows):
            for col in range(self.cols):
                x = self.panel_x + col * self.cell_size + self.cell_padding
                y = self.panel_y + row * self.cell_size + self.cell_padding
                rect = pygame.Rect(x, y, self.cell_size - 2 * self.cell_padding, self.cell_size - 2 * self.cell_padding)
                self.cells.append({
                    'rect': rect,
                    'row': row,
                    'col': col,
                    'index': row * self.cols + col,
                    'item': None,
                })
    
    def toggle(self):
        """Открыть/закрыть рюкзак"""
        self.is_open = not self.is_open
    
    def open(self):
        """Открыть рюкзак"""
        self.is_open = True
    
    def close(self):
        """Закрыть рюкзак"""
        self.is_open = False
    
    def handle_click(self, position):
        """Обработать клик по ячейке рюкзака"""
        if not self.is_open:
            return None
        
        # Проверяем клик по закрытию (кнопка закрытия или вне панели)
        panel_rect = pygame.Rect(
            self.panel_x - 10,
            self.panel_y - 10,
            self.panel_width + 20,
            self.panel_height + 20
        )
        
        # Если клик за границей панели, закрываем
        if not panel_rect.collidepoint(position):
            self.close()
            return None
        
        # Проверяем клик по ячейкам
        for cell in self.cells:
            if cell['rect'].collidepoint(position):
                return cell['index']
        
        return None
    
    def draw(self, screen):
        """Рисовать панель рюкзака"""
        if not self.is_open:
            return
        
        # Полупрозрачный фон вокруг панели (затемнение экрана)
        overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT))
        overlay.set_alpha(100)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))
        
        # Фон панели
        panel_bg = pygame.Rect(
            self.panel_x - 5,
            self.panel_y - 5,
            self.panel_width + 10,
            self.panel_height + 10
        )
        pygame.draw.rect(screen, (40, 50, 70), panel_bg)
        pygame.draw.rect(screen, self.border_color, panel_bg, self.border_width)
        
        # Рисуем ячейки
        for cell in self.cells:
            # Определяем цвет ячейки
            color = self.cell_color
            if cell['rect'].collidepoint(pygame.mouse.get_pos()):
                color = self.cell_hover_color
            
            # Рисуем ячейку
            pygame.draw.rect(screen, color, cell['rect'])
            pygame.draw.rect(screen, self.border_color, cell['rect'], 1)
