import pygame
from core import settings
from ui.hud import draw_button


class TavernShop:
    """Магазин хозяина трактира справа с закладками"""
    
    def __init__(self, action_font, small_font):
        self.action_font = action_font
        self.small_font = small_font
        self.is_open = False
        self.current_tab = "drinks"  # "drinks" или "sell"
        self.hovered_drink_index = -1  # Индекс напитка под мышкой
        self.error_message = ""  # Сообщение об ошибке
        self.error_time = 0  # Время отображения ошибки
        self.last_click_time = 0  # Время последнего клика для двойного клика
        self.last_click_index = -1  # Индекс последнего кликнутого товара
        
        # Размеры и позиция (как ENEMY_CARD_RECT, но смещено вниз на 60 пиксельс и уменьшено)
        enemy_rect = settings.ENEMY_CARD_RECT
        self.frame = pygame.Rect(
            enemy_rect[0],
            enemy_rect[1] + 60,  # Смещено вниз на 60 пиксельс для кнопки инвентаря
            enemy_rect[2],
            enemy_rect[3] - 60   # Высота уменьшена на 60 пиксельс
        )
        
        # Кнопка закрытия - внизу панели магазина
        self.close_button = pygame.Rect(
            self.frame.right - 100,
            self.frame.bottom - 49,  # Вниз панели
            85,
            34,
        )
        
        # Закладки больше не нужны в панели - они теперь снаружи
        # Область контента занимает всю панель
        self.content_rect = pygame.Rect(
            self.frame.x,
            self.frame.y,
            self.frame.width,
            self.frame.height
        )
        
        # Напитки (загружаются с сервера)
        self.drinks = [
            {"id": 1, "name": "Эль", "price": 20, "effect": "recovery", "description": "мгновенно восстанавливает 50 HP"},
        ]
        
        # Цвета вкладок
        self.tab_inactive_color = (60, 80, 100)
        self.tab_active_color = (100, 150, 180)
        self.tab_border_color = (150, 150, 170)
        self.hover_color = (120, 160, 200)  # Цвет при наведении
    
    def open(self):
        """Открыть магазин"""
        self.is_open = True
    
    def close(self):
        """Закрыть магазин"""
        self.is_open = False
    
    def update_hover(self, position):
        """Обновить состояние наведения мыши"""
        self.hovered_drink_index = -1
        if not self.is_open or self.current_tab != "drinks":
            return
        
        if self.content_rect.collidepoint(position):
            for i in range(len(self.drinks)):
                y = self.content_rect.y + 70 + i * 60
                rect = pygame.Rect(self.content_rect.x + 10, y, self.content_rect.width - 20, 50)
                if rect.collidepoint(position):
                    self.hovered_drink_index = i
                    break
    
    def show_error(self, message):
        """Показать сообщение об ошибке"""
        self.error_message = message
        self.error_time = 120  # 2 секунды при 60 FPS
    
    def update(self):
        """Обновить состояние (для счетчика времени ошибки)"""
        if self.error_time > 0:
            self.error_time -= 1
    
    def _draw_drink_icon(self, screen, x, y, size=40):
        """Рисует простую иконку напитка"""
        # Кружка (основной корпус)
        cup_rect = pygame.Rect(x, y, size - 10, size)
        pygame.draw.rect(screen, (139, 69, 19), cup_rect, border_radius=4)  # Коричневый цвет кружки
        pygame.draw.rect(screen, (200, 150, 80), cup_rect, 2, border_radius=4)  # Светлый контур
        
        # Жидкость внутри (жидкость)
        liquid_height = int(size * 0.6)
        liquid_rect = pygame.Rect(x + 2, y + size - liquid_height - 2, size - 14, liquid_height)
        pygame.draw.rect(screen, (220, 180, 100), liquid_rect, border_radius=2)  # Светлый пиво
        
        # Ручка кружки
        handle_x = x + size - 10
        handle_y = y + 8
        pygame.draw.arc(screen, (200, 150, 80), pygame.Rect(handle_x, handle_y, 8, 16), 0, 3.14, 2)
    def handle_click(self, position):
        """Обработать клик (возвращает событие или None)"""
        if not self.is_open:
            return None
        
        import time
        current_time = time.time()
        
        # Клик по кнопке закрытия
        if self.close_button.collidepoint(position):
            self.close()
            return "close"
        
        # Клик по товарам в области контента
        if self.content_rect.collidepoint(position):
            if self.current_tab == "drinks":
                for i, drink in enumerate(self.drinks):
                    y = self.content_rect.y + 70 + i * 60
                    rect = pygame.Rect(self.content_rect.x + 10, y, self.content_rect.width - 20, 50)
                    if rect.collidepoint(position):
                        # Проверяем двойной клик (300 мс)
                        if i == self.last_click_index and (current_time - self.last_click_time) < 0.3:
                            self.last_click_index = -1
                            self.last_click_time = 0
                            return f"buy_drink_{i}"
                        
                        self.last_click_index = i
                        self.last_click_time = current_time
                        return "handled"
            elif self.current_tab == "sell":
                # TODO: обработка скупки
                pass
            
            return "handled"
        
        return None
    
    def draw(self, screen):
        """Рисовать магазин"""
        if not self.is_open:
            return
        
        # Фон панели
        pygame.draw.rect(screen, (40, 50, 70), self.frame)
        pygame.draw.rect(screen, self.tab_border_color, self.frame, 2)
        
        # Кнопка закрытия
        draw_button(screen, self.close_button, "ЗАКРЫТЬ", self.small_font, color=(70, 75, 90))
        
        # Контент вкладки "Напитки"
        if self.current_tab == "drinks":
            # Заголовок
            title = self.action_font.render("Напитки бара", True, (100, 200, 255))
            screen.blit(title, (self.content_rect.x + 20, self.content_rect.y + 10))
            
            # Список напитков
            for i, drink in enumerate(self.drinks):
                y = self.content_rect.y + 70 + i * 60
                rect = pygame.Rect(self.content_rect.x + 10, y, self.content_rect.width - 20, 50)
                
                # Выбор цвета в зависимости от наведения
                color = self.hover_color if i == self.hovered_drink_index else (80, 120, 150)
                
                # Кнопка товара
                pygame.draw.rect(screen, color, rect)
                pygame.draw.rect(screen, self.tab_border_color, rect, 1)
                
                # Иконка напитка (слева)
                self._draw_drink_icon(screen, rect.x + 8, rect.y + 5, size=40)
                
                # Текст товара (справа от иконки)
                drink_text = self.small_font.render(f"{drink['name']} - {drink['price']} медяков", True, (255, 255, 255))
                screen.blit(drink_text, (rect.x + 55, rect.y + 15))
            
            # Tooltip при наведении
            if self.hovered_drink_index >= 0 and self.hovered_drink_index < len(self.drinks):
                drink = self.drinks[self.hovered_drink_index]
                if "description" in drink:
                    # Получаем позицию мыши
                    mouse_pos = pygame.mouse.get_pos()
                    
                    # Рисуем tooltip
                    description_text = self.small_font.render(drink["description"], True, (200, 200, 150))
                    tooltip_rect = description_text.get_rect()
                    tooltip_rect.topleft = (mouse_pos[0] + 10, mouse_pos[1] + 10)
                    
                    # Фон tooltip
                    bg_rect = tooltip_rect.inflate(10, 6)
                    pygame.draw.rect(screen, (30, 30, 40), bg_rect)
                    pygame.draw.rect(screen, (150, 150, 170), bg_rect, 1)
                    
                    # Текст tooltip
                    screen.blit(description_text, tooltip_rect)
        
        # Контент вкладки "Скупка"
        elif self.current_tab == "sell":
            # Заголовок
            title = self.action_font.render("Скупка", True, (255, 150, 100))
            screen.blit(title, (self.content_rect.x + 20, self.content_rect.y + 10))
            
            # Информация
            info = self.small_font.render("Кликните на предмет в рюкзаке", True, (200, 200, 200))
            screen.blit(info, (self.content_rect.x + 20, self.content_rect.y + 100))
        
        # Отображение сообщения об ошибке
        if self.error_time > 0:
            error_text = self.small_font.render(self.error_message, True, (255, 100, 100))
            screen.blit(error_text, (self.content_rect.x + 20, self.content_rect.y + 140))

