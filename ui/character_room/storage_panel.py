"""
Панель сундуков (хранилище)
"""

import pygame
from typing import List, Dict, Optional


class StoragePanel:
    """Панель для управления сундуками персонажа"""

    def __init__(self, font, small_font):
        self.font = font
        self.small_font = small_font

        # Параметры отображения
        self.start_x = 50
        self.start_y = 220
        self.items_per_row = 5
        self.item_width = 320

        # Сундуки
        self.storages = [
            ("chest1", "📚 СУНДУК 1 - КАРТЫ И СВИТКИ (100 ячеек)", 80),
            ("chest2", "📚 СУНДУК 2 - МАТЕРИАЛЫ И ДОП. (100 ячеек)", 100),
        ]

        # Данные
        self.storage_items: Dict[str, List[Dict]] = {}
        self.selected_item: Optional[Dict] = None
        self.selected_storage: str = "chest1"
        self.item_rects: List[pygame.Rect] = []

        # Прокрутка
        self.scroll_offset = 0
        self.scroll_speed = 50

    def set_storage(self, storage_type: str, items: List[Dict]):
        """Устанавливает содержимое сундука"""
        self.storage_items[storage_type] = items
        self._update_rects()

    def _update_rects(self):
        """Обновляет прямоугольники для отображения"""
        self.item_rects = []
        current_items = self.storage_items.get(self.selected_storage, [])

        for i in range(len(current_items)):
            row = i // self.items_per_row
            col = i % self.items_per_row

            x = self.start_x + 20 + col * self.item_width
            y = self.start_y + 60 + row * 120 - self.scroll_offset

            rect = pygame.Rect(x, y, self.item_width - 20, 100)
            self.item_rects.append(rect)

    def handle_event(self, event) -> bool:
        """Обрабатывает события"""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 4:  # Скролл вверх
                self.scroll_offset = max(0, self.scroll_offset - self.scroll_speed)
                self._update_rects()
                return True

            if event.button == 5:  # Скролл вниз
                current_items = self.storage_items.get(self.selected_storage, [])
                max_offset = max(0, (len(current_items) - 5) // self.items_per_row * 120)
                self.scroll_offset = min(max_offset, self.scroll_offset + self.scroll_speed)
                self._update_rects()
                return True

            if event.button == 1:  # Левый клик
                mouse_pos = event.pos

                # Проверяем клики по сундукам
                for i, (storage_type, label, _) in enumerate(self.storages):
                    y = self.start_y + i * 250
                    chest_rect = pygame.Rect(self.start_x, y, 1800, 40)
                    if chest_rect.collidepoint(mouse_pos):
                        self.selected_storage = storage_type
                        self.scroll_offset = 0
                        self._update_rects()
                        return True

                # Проверяем клики по предметам
                current_items = self.storage_items.get(self.selected_storage, [])
                for i, rect in enumerate(self.item_rects):
                    if rect.collidepoint(mouse_pos) and i < len(current_items):
                        self.selected_item = current_items[i]
                        return True

        return False

    def draw(self, screen):
        """Рисует панель сундуков"""
        # Заголовок
        title = pygame.font.SysFont("arial", 28).render("📚 СУНДУКИ", True, (220, 200, 150))
        screen.blit(title, (self.start_x, self.start_y - 60))

        # Рисуем вкладки сундуков
        for i, (storage_type, label, capacity) in enumerate(self.storages):
            y = self.start_y + i * 250

            is_selected = storage_type == self.selected_storage
            color = (150, 200, 255) if is_selected else (70, 90, 120)

            # Название сундука
            chest_rect = pygame.Rect(self.start_x, y, 1800, 40)
            pygame.draw.rect(screen, color, chest_rect, border_radius=8, width=2)

            chest_text = self.font.render(label, True, (220, 200, 150))
            screen.blit(chest_text, (self.start_x + 20, y + 8))

            # Если это активный сундук, показываем содержимое
            if is_selected:
                current_items = self.storage_items.get(storage_type, [])

                # Счётчик
                count_text = self.small_font.render(
                    f"Вмещение: {len(current_items)}/{capacity}",
                    True,
                    (150, 150, 150)
                )
                screen.blit(count_text, (self.start_x, y + 50))

                # Клипируем область отображения
                clip_area = pygame.Rect(self.start_x - 10, y + 60, 1900, 180)
                screen_rect = screen.get_clip()
                screen.set_clip(clip_area)

                # Сетка предметов
                for j, item in enumerate(current_items):
                    rect = self.item_rects[j] if j < len(self.item_rects) else None
                    if not rect:
                        break

                    # Пропускаем если за пределами экрана
                    if rect.y < y + 50 or rect.y > y + 230:
                        continue

                    is_selected_item = self.selected_item and self.selected_item.get("item_id") == item["item_id"]
                    item_color = (150, 200, 255) if is_selected_item else (70, 90, 120)

                    # Ячейка предмета
                    pygame.draw.rect(screen, item_color, rect, border_radius=6, width=2)

                    # Иконка
                    icon_text = self.small_font.render(item.get("icon", "📦"), True, (255, 255, 255))
                    screen.blit(icon_text, (rect.x + 10, rect.y + 10))

                    # Название
                    name_text = self.small_font.render(item["name"][:18], True, (220, 220, 220))
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
                    screen.blit(rarity_text, (rect.x + 50, rect.y + 30))

                    # Количество
                    qty_text = self.small_font.render(f"×{item.get('quantity', 1)}", True, (200, 200, 200))
                    screen.blit(qty_text, (rect.x + 10, rect.y + 55))

                # Восстанавливаем клипирование
                screen.set_clip(screen_rect)

    def get_selected_item(self) -> Optional[Dict]:
        """Возвращает выбранный предмет"""
        return self.selected_item

    def clear_selection(self):
        """Очищает выбор"""
        self.selected_item = None
