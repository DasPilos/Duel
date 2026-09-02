"""
Панель инвентаря (рюкзак)
"""

import pygame
from typing import List, Dict, Optional


class InventoryPanel:
    """Панель для управления инвентарём (рюкзак - носит на себе)"""

    def __init__(self, font, small_font):
        self.font = font
        self.small_font = small_font

        # Параметры отображения
        self.start_x = 50
        self.start_y = 220
        self.items_per_row = 6
        self.item_width = 280
        self.item_height = 100

        # Данные
        self.items: List[Dict] = []
        self.selected_item: Optional[Dict] = None
        self.item_rects: List[pygame.Rect] = []

        # Прокрутка
        self.scroll_offset = 0
        self.max_visible_rows = 3
        self.scroll_speed = 50

    def set_items(self, items: List[Dict]):
        """Устанавливает список предметов"""
        self.items = items
        self._update_rects()

    def _update_rects(self):
        """Обновляет прямоугольники для отображения"""
        self.item_rects = []
        for i in range(len(self.items)):
            row = i // self.items_per_row
            col = i % self.items_per_row

            x = self.start_x + col * self.item_width
            y = self.start_y + row * (self.item_height + 20) - self.scroll_offset

            rect = pygame.Rect(x, y, self.item_width - 20, self.item_height)
            self.item_rects.append(rect)

    def handle_event(self, event, screen_height) -> bool:
        """Обрабатывает события. Возвращает True если событие обработано"""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 4:  # Скролл вверх
                self.scroll_offset = max(0, self.scroll_offset - self.scroll_speed)
                self._update_rects()
                return True

            if event.button == 5:  # Скролл вниз
                max_offset = max(0, len(self.items) // self.items_per_row * (self.item_height + 20))
                self.scroll_offset = min(max_offset, self.scroll_offset + self.scroll_speed)
                self._update_rects()
                return True

            if event.button == 1:  # Левый клик
                mouse_pos = event.pos
                for i, rect in enumerate(self.item_rects):
                    if rect.collidepoint(mouse_pos):
                        self.selected_item = self.items[i]
                        return True

        return False

    def draw(self, screen):
        """Рисует панель инвентаря"""
        # Заголовок
        title = pygame.font.SysFont("arial", 28).render("📦 РЮКЗАК (50 ячеек)", True, (220, 200, 150))
        screen.blit(title, (self.start_x, self.start_y - 60))

        # Счётчик
        count_text = self.small_font.render(
            f"Предметов: {len(self.items)}/50",
            True,
            (150, 150, 150)
        )
        screen.blit(count_text, (self.start_x, self.start_y - 30))

        # Клипируем область отображения (чтобы не было обрезки при скролле)
        clip_area = pygame.Rect(self.start_x - 10, self.start_y, 1800, 400)
        screen_rect = screen.get_clip()
        screen.set_clip(clip_area)

        # Сетка предметов
        for i, item in enumerate(self.items):
            rect = self.item_rects[i]

            # Пропускаем если за пределами экрана
            if rect.y < self.start_y - self.item_height or rect.y > self.start_y + 400:
                continue

            is_selected = self.selected_item and self.selected_item.get("item_id") == item["item_id"]

            # Цвет ячейки
            color = (150, 200, 255) if is_selected else (70, 90, 120)
            pygame.draw.rect(screen, color, rect, border_radius=8, width=2)

            # Иконка предмета
            icon_text = self.small_font.render(item.get("icon", "📦"), True, (255, 255, 255))
            screen.blit(icon_text, (rect.x + 10, rect.y + 10))

            # Название предмета
            name_text = self.small_font.render(item["name"][:20], True, (220, 220, 220))
            screen.blit(name_text, (rect.x + 50, rect.y + 10))

            # Редкость
            rarity_colors = {
                "common": (150, 150, 150),
                "rare": (100, 150, 255),
                "epic": (200, 100, 255),
                "legendary": (255, 200, 0)
            }
            rarity_color = rarity_colors.get(item.get("rarity"), (150, 150, 150))
            rarity_text = self.small_font.render(f"★ {item.get('rarity', 'unknown')}", True, rarity_color)
            screen.blit(rarity_text, (rect.x + 50, rect.y + 35))

            # Количество и вес
            qty_text = self.small_font.render(f"×{item.get('quantity', 1)}", True, (200, 200, 200))
            screen.blit(qty_text, (rect.x + 10, rect.y + 60))

            weight_text = self.small_font.render(f"{item.get('weight', 0)}кг", True, (150, 150, 150))
            screen.blit(weight_text, (rect.x + 50, rect.y + 60))

        # Восстанавливаем клипирование
        screen.set_clip(screen_rect)

    def get_selected_item(self) -> Optional[Dict]:
        """Возвращает выбранный предмет"""
        return self.selected_item

    def clear_selection(self):
        """Очищает выбор"""
        self.selected_item = None
