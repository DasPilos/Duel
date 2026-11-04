import pygame

from kaloda.combat.card_database import (
    DECK_COPY_LIMIT,
    DECK_COPY_LIMITS,
    DECK_SIZE,
    card_style,
    cards_for_type,
    deck_validation_error,
)
from kaloda.ui.class_identity import class_palette
from kaloda.ui.card_tooltip import draw_card_tooltip


ELEMENT_COLORS = {
    "Огонь": (205, 90, 45),
    "Вода": (55, 125, 205),
    "Земля": (125, 95, 55),
    "Электричество": (230, 200, 60),
    "Воздух": (165, 215, 225),
    "Холод": (110, 170, 220),
}
ULTIMATE_BORDER = (235, 190, 70)
UNKNOWN_ELEMENT = "Прочее"


class DeckSelectionPanel:
    def __init__(self, font, small_font, card_loader=None):
        self.font = font
        self.small_font = small_font
        self.is_open = False
        self.decks = []
        self.rects = []
        self.selected_deck = None
        self.creating = False
        self.view = "elements"
        self.selected_element = None
        self.name = ""
        self.on_save = None
        self.card_loader = card_loader
        self.collection = []
        self.owned = {}
        self.card_names = {}
        self.card_info = {}
        self.cards_by_key = {}
        self.pool_order = {}
        self.element_order = []
        self.elements = []
        self.element_rects = []
        self.visible_keys = []
        self.card_rects = []
        self.selected_cards = []
        self.error = ""
        self.character_type = "warrior"
        self.create_button = pygame.Rect(430, 215, 220, 40)
        self.back_button = pygame.Rect(430, 215, 50, 40)
        self.name_rect = pygame.Rect(495, 215, 330, 40)
        self.save_button = pygame.Rect(840, 215, 160, 40)
        self.panel = pygame.Rect(380, 180, 1160, 620)
        self.close_button = pygame.Rect(1370, 205, 140, 40)

    def open(self, decks, character_type=None):
        self.decks = list(decks or [])
        if character_type is not None:
            self.character_type = character_type
        self.selected_deck = next((deck for deck in self.decks if deck.get("is_active")), None)
        self.is_open = True
        self.rects = [pygame.Rect(430, 280 + index * 72, 1060, 58) for index in range(len(self.decks))]

    def close(self):
        self.is_open = False
        self._leave_creation()

    def finish_creation(self, decks):
        self._leave_creation()
        self.open(decks)

    def handle_event(self, event):
        if not self.is_open or not self.creating:
            return False
        # Поглощаем только клавиатуру (ввод названия); клики обрабатывает handle_click
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.name = self.name[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.on_save:
                self.on_save()
            return True
        if event.type == pygame.TEXTINPUT:
            if len(self.name) < 32:
                self.name += event.text
            return True
        return event.type == pygame.KEYUP

    def handle_click(self, position):
        if not self.is_open:
            return None
        if self.close_button.collidepoint(position):
            self.close()
            return "close"
        if self.creating:
            return self._handle_creation_click(position)
        if self.create_button.collidepoint(position):
            self._start_creation()
            return "handled"
        for rect, deck in zip(self.rects, self.decks):
            if rect.collidepoint(position):
                delete_rect = pygame.Rect(rect.right - 120, rect.y + 8, 105, 42)
                if delete_rect.collidepoint(position):
                    return "delete_deck", deck
                self.selected_deck = deck
                self.close()
                return deck
        return "handled"

    def validation_error(self):
        error = deck_validation_error(self.selected_cards, self.character_type, self.owned)
        if error:
            return error
        if not self.name.strip():
            return "Введите название колоды"
        return ""

    def _handle_creation_click(self, position):
        if self.back_button.collidepoint(position):
            if self.view == "cards":
                self.view = "elements"
                self.error = ""
            else:
                self._leave_creation()
            return "handled"
        if self.save_button.collidepoint(position):
            if self.on_save:
                self.on_save()
            return "handled"
        if self.view == "elements":
            for rect, element in zip(self.element_rects, self.elements):
                if rect.collidepoint(position):
                    self.selected_element = element
                    self.view = "cards"
                    self._layout_cards()
                    return "handled"
            return "handled"
        for rect, key in zip(self.card_rects, self.visible_keys):
            if rect.collidepoint(position):
                self._toggle_card(key)
                return "handled"
        return "handled"

    def _start_creation(self):
        self.creating = True
        self.view = "elements"
        self.selected_element = None
        self.name = ""
        self.error = ""
        self.selected_cards = []
        self.collection = list(self.card_loader() if self.card_loader else [])
        if not self.collection:
            self.collection = [
                {"key": card.key, "name": card.name, "quantity": 1}
                for card in cards_for_type(self.character_type)
            ]
        self.owned = {
            str(card.get("key", card.get("card_key"))): int(card.get("quantity", 1))
            for card in self.collection
        }
        self.card_names = {
            str(card.get("key", card.get("card_key"))): str(card.get("name", card.get("key")))
            for card in self.collection
        }
        self._index_pool()
        self.elements = self._elements()
        self.element_rects = [
            pygame.Rect(430 + (index % 3) * 340, 300 + (index // 3) * 120, 320, 100)
            for index in range(len(self.elements))
        ]

    def _index_pool(self):
        pool = cards_for_type(self.character_type)
        self.pool_order = {card.key: index for index, card in enumerate(pool)}
        self.cards_by_key = {card.key: card for card in pool}
        self.card_info = {
            card.key: (card_style(card), bool((card.effect_data or {}).get("ultimate")))
            for card in pool
        }
        self.element_order = []
        for card in pool:
            style = card_style(card)
            if style not in self.element_order:
                self.element_order.append(style)

    def _elements(self):
        owned_styles = {self._style_of(key) for key in self.owned}
        ordered = [style for style in self.element_order if style in owned_styles]
        ordered += sorted(owned_styles - set(ordered))
        return ordered

    def _layout_cards(self):
        keys = [key for key in self.owned if self._style_of(key) == self.selected_element]
        keys.sort(key=lambda key: self.pool_order.get(key, len(self.pool_order)))
        self.visible_keys = keys
        self.card_rects = [
            pygame.Rect(430 + (index % 4) * 260, 300 + (index // 4) * 62, 240, 50)
            for index in range(len(keys))
        ]

    def _toggle_card(self, key):
        self.error = ""
        selected_count = self.selected_cards.count(key)
        quantity = min(
            self.owned.get(key, 1),
            DECK_COPY_LIMITS.get(key, DECK_COPY_LIMIT),
        )
        if selected_count < quantity and len(self.selected_cards) < DECK_SIZE:
            self.selected_cards.append(key)
        elif selected_count:
            self.selected_cards.remove(key)

    def _leave_creation(self):
        self.creating = False
        self.view = "elements"
        self.selected_element = None
        self.selected_cards = []
        self.name = ""
        self.error = ""

    def _style_of(self, key):
        return self.card_info.get(key, (UNKNOWN_ELEMENT, False))[0]

    def _is_ultimate(self, key):
        return self.card_info.get(key, (UNKNOWN_ELEMENT, False))[1]

    def _element_color(self, element):
        if element in ELEMENT_COLORS:
            return ELEMENT_COLORS[element]
        return class_palette(self.character_type)["accent"]

    @staticmethod
    def _text_color_on(color):
        return (30, 30, 40) if sum(color) > 450 else (250, 250, 250)

    def draw(self, screen):
        if not self.is_open:
            return
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        screen.blit(overlay, (0, 0))
        pygame.draw.rect(screen, (30, 25, 42), self.panel, border_radius=10)
        pygame.draw.rect(screen, (150, 100, 200), self.panel, 2, border_radius=10)
        pygame.draw.rect(screen, (110, 65, 75), self.close_button, border_radius=5)
        screen.blit(self.small_font.render("ЗАКРЫТЬ", True, (255, 255, 255)), (1400, 217))
        if self.creating:
            self._draw_creation(screen)
        else:
            self._draw_list(screen)

    def _draw_list(self, screen):
        screen.blit(self.font.render("ВЫБОР КОЛОДЫ", True, (240, 220, 255)), (430, 215))
        pygame.draw.rect(screen, (70, 120, 150), self.create_button, border_radius=5)
        screen.blit(self.small_font.render("СОЗДАТЬ КОЛОДУ", True, (255, 255, 255)), (450, 227))
        if not self.decks:
            screen.blit(self.small_font.render("Колоды не созданы", True, (180, 180, 190)), (430, 290))
            return
        for rect, deck in zip(self.rects, self.decks):
            active = self.selected_deck and deck.get("id") == self.selected_deck.get("id")
            pygame.draw.rect(screen, (70, 120, 150) if active else (50, 55, 75), rect, border_radius=6)
            name = str(deck.get("name", "Колода"))
            cards = deck.get("cards", {})
            count = sum(int(value) for value in cards.values()) if isinstance(cards, dict) else len(cards)
            screen.blit(self.small_font.render(name, True, (245, 240, 220)), (rect.x + 18, rect.y + 10))
            screen.blit(self.small_font.render(f"Карт: {count}  {'АКТИВНА' if deck.get('is_active') else ''}", True, (190, 210, 220)), (rect.x + 18, rect.y + 34))
            delete_rect = pygame.Rect(rect.right - 120, rect.y + 8, 105, 42)
            pygame.draw.rect(screen, (125, 60, 70), delete_rect, border_radius=5)
            screen.blit(self.small_font.render("УДАЛИТЬ", True, (255, 235, 235)), (delete_rect.x + 12, delete_rect.y + 11))

    def _draw_creation(self, screen):
        pygame.draw.rect(screen, (70, 65, 90), self.back_button, border_radius=5)
        center_x, center_y = self.back_button.center
        pygame.draw.lines(screen, (240, 220, 255), False, [(center_x + 6, center_y - 10), (center_x - 6, center_y), (center_x + 6, center_y + 10)], 3)

        pygame.draw.rect(screen, (245, 245, 250), self.name_rect, border_radius=4)
        name_color = (30, 30, 40) if self.name else (120, 120, 130)
        screen.blit(self.small_font.render(self.name or "Название колоды", True, name_color), (self.name_rect.x + 10, self.name_rect.y + 11))

        pygame.draw.rect(screen, (60, 130, 80), self.save_button, border_radius=5)
        screen.blit(self.small_font.render("СОХРАНИТЬ", True, (255, 255, 255)), (self.save_button.x + 22, self.save_button.y + 11))
        screen.blit(self.small_font.render(f"Выбрано: {len(self.selected_cards)}/{DECK_SIZE}", True, (245, 220, 150)), (1020, 225))

        if self.view == "cards":
            heading_color = self._element_color(self.selected_element)
            screen.blit(self.font.render(str(self.selected_element), True, heading_color), (430, 262))
            for rect, key in zip(self.card_rects, self.visible_keys):
                self._draw_card_tile(screen, rect, key)
        else:
            screen.blit(self.small_font.render("Выберите элемент", True, (190, 200, 215)), (430, 265))
            for rect, element in zip(self.element_rects, self.elements):
                self._draw_element_button(screen, rect, element)

        if self.error:
            screen.blit(self.small_font.render(self.error, True, (255, 100, 100)), (430, 762))
        if self.view == "cards":
            mouse_pos = pygame.mouse.get_pos()
            for rect, key in zip(self.card_rects, self.visible_keys):
                if rect.collidepoint(mouse_pos):
                    card = self.cards_by_key.get(key)
                    if card is not None:
                        draw_card_tooltip(screen, card, mouse_pos, self.small_font)
                    break

    def _draw_element_button(self, screen, rect, element):
        color = self._element_color(element)
        text_color = self._text_color_on(color)
        pygame.draw.rect(screen, color, rect, border_radius=8)
        pygame.draw.rect(screen, (245, 240, 225), rect, 2, border_radius=8)
        title = self.font.render(str(element), True, text_color)
        screen.blit(title, title.get_rect(center=(rect.centerx, rect.centery - 12)))
        chosen = sum(self.selected_cards.count(key) for key in self.owned if self._style_of(key) == element)
        counter = self.small_font.render(f"Выбрано: {chosen}", True, text_color)
        screen.blit(counter, counter.get_rect(center=(rect.centerx, rect.centery + 18)))

    def _draw_card_tile(self, screen, rect, key):
        element_color = self._element_color(self._style_of(key))
        selected_count = self.selected_cards.count(key)
        fill = tuple(int(channel * 0.55) for channel in element_color) if selected_count else (50, 55, 75)
        pygame.draw.rect(screen, fill, rect, border_radius=5)
        if self._is_ultimate(key):
            pygame.draw.rect(screen, ULTIMATE_BORDER, rect, 3, border_radius=5)
        else:
            pygame.draw.rect(screen, element_color if selected_count else (120, 130, 155), rect, 2, border_radius=5)
        name = str(self.card_names.get(key, key))
        screen.blit(self.small_font.render(name, True, (245, 240, 225)), (rect.x + 8, rect.y + 6))
        counter = f"{selected_count}/{self.owned.get(key, 1)}"
        screen.blit(self.small_font.render(counter, True, (190, 200, 215)), (rect.x + 8, rect.y + 27))
