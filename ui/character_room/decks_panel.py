"""
Панель боевых колод
"""

import pygame
from typing import List, Dict, Optional


class DecksPanel:
    """Панель для управления боевыми колодами"""

    def __init__(self, font, small_font):
        self.font = font
        self.small_font = small_font

        # Параметры отображения
        self.start_x = 50
        self.start_y = 220

        # Данные
        self.decks: List[Dict] = []
        self.selected_deck: Optional[Dict] = None
        self.deck_rects: List[pygame.Rect] = []

    def set_decks(self, decks: List[Dict]):
        """Устанавливает список колод"""
        self.decks = decks
        self._update_rects()

    def _update_rects(self):
        """Обновляет прямоугольники для отображения"""
        self.deck_rects = []
        for i in range(len(self.decks)):
            y = self.start_y + i * 120

            rect = pygame.Rect(self.start_x, y, 1800, 100)
            self.deck_rects.append(rect)

    def handle_event(self, event) -> bool:
        """Обрабатывает события"""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos
            for i, rect in enumerate(self.deck_rects):
                if rect.collidepoint(mouse_pos):
                    self.selected_deck = self.decks[i]
                    return True

        return False

    def draw(self, screen):
        """Рисует панель колод"""
        # Заголовок
        title = pygame.font.SysFont("arial", 28).render("📃 БОЕВЫЕ КОЛОДЫ", True, (220, 200, 150))
        screen.blit(title, (self.start_x, self.start_y - 60))

        if not self.decks:
            empty_text = self.font.render("Колоды не созданы", True, (150, 150, 150))
            screen.blit(empty_text, (self.start_x, self.start_y))
            return

        # Рисуем каждую колоду
        for i, deck in enumerate(self.decks):
            y = self.start_y + i * 120
            rect = self.deck_rects[i]

            is_selected = self.selected_deck and self.selected_deck.get("id") == deck.get("id")
            color = (150, 200, 255) if is_selected else (70, 90, 120)

            # Фон ячейки
            pygame.draw.rect(screen, color, rect, border_radius=8, width=2)

            # Статус активности
            marker = "⭐ АКТИВНА" if deck.get("is_active") else "⚪ неактивна"
            marker_text = self.small_font.render(marker, True, (200, 200, 100) if deck.get("is_active") else (100, 100, 100))
            screen.blit(marker_text, (self.start_x + 20, y + 10))

            # Название колоды
            name_text = self.font.render(deck["name"], True, (220, 220, 220))
            screen.blit(name_text, (self.start_x + 200, y + 10))

            # Информация о картах
            cards = deck.get("cards", {})
            total_cards = sum(int(qty) for qty in cards.values()) if isinstance(cards, dict) else len(cards)
            cards_info = self.small_font.render(
                f"Карт в колоде: {total_cards}",
                True,
                (150, 200, 150)
            )
            screen.blit(cards_info, (self.start_x + 20, y + 40))

            # Список типов карт
            card_types_text = self._get_card_types_text(cards)
            card_types_surface = self.small_font.render(card_types_text, True, (180, 180, 180))
            screen.blit(card_types_surface, (self.start_x + 400, y + 40))

            # Кнопки действий
            self._draw_deck_buttons(screen, rect, deck)

    def _get_card_types_text(self, cards) -> str:
        """Получает текст с типами карт в колоде"""
        if isinstance(cards, dict):
            types = ", ".join([f"{card_id}×{qty}" for card_id, qty in cards.items()][:5])
        else:
            types = f"{len(cards)} карт"

        return f"Карты: {types}"

    def _draw_deck_buttons(self, screen, rect, deck):
        """Рисует кнопки действий для колоды"""
        from ui.hud import draw_button

        button_height = 30
        button_width = 100

        # Кнопка "Редактировать"
        edit_rect = pygame.Rect(rect.right - 320, rect.top + 20, button_width, button_height)
        draw_button(screen, edit_rect, "✏️ Редакт.", self.small_font, color=(100, 180, 100))

        # Кнопка "Удалить"
        delete_rect = pygame.Rect(rect.right - 200, rect.top + 20, button_width, button_height)
        draw_button(screen, delete_rect, "🗑️ Удалить", self.small_font, color=(200, 100, 100))

        # Если не активна, кнопка "Активировать"
        if not deck.get("is_active"):
            activate_rect = pygame.Rect(rect.right - 80, rect.top + 20, button_width + 20, button_height)
            draw_button(screen, activate_rect, "✓ Активировать", self.small_font, color=(100, 150, 255))

    def get_selected_deck(self) -> Optional[Dict]:
        """Возвращает выбранную колоду"""
        return self.selected_deck

    def clear_selection(self):
        """Очищает выбор"""
        self.selected_deck = None
