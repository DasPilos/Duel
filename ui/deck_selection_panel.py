import pygame

from combat.card_database import DECK_SIZE, cards_for_type, deck_validation_error


class DeckSelectionPanel:
    GRID_COLUMNS = 4
    GRID_TOP = 300
    ROW_HEIGHT = 62
    VISIBLE_ROWS = 7

    def __init__(self, font, small_font, card_loader=None):
        self.font = font
        self.small_font = small_font
        self.is_open = False
        self.decks = []
        self.rects = []
        self.selected_deck = None
        self.creating = False
        self.name = ""
        self.create_requested = False
        self.card_loader = card_loader
        self.collection = []
        self.selected_cards = []
        self.error = ""
        self.scroll_row = 0
        self.character_type = "warrior"
        self.create_button = pygame.Rect(430, 215, 220, 40)
        self.name_rect = pygame.Rect(680, 215, 500, 40)
        self.save_button = pygame.Rect(1190, 215, 170, 40)
        self.panel = pygame.Rect(380, 180, 1160, 620)
        self.close_button = pygame.Rect(1370, 205, 140, 40)

    def open(self, decks, character_type=None):
        self.decks = list(decks or [])
        if character_type is not None:
            self.character_type = character_type
        self.selected_deck = next((deck for deck in self.decks if deck.get("is_active")), None)
        self.is_open = True
        self.creating = False
        self.error = ""
        self.rects = [pygame.Rect(430, 280 + index * 72, 1060, 58) for index in range(len(self.decks))]

    def close(self):
        self.is_open = False
        self.creating = False

    def handle_event(self, event):
        if not self.is_open or not self.creating:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.name = self.name[:-1]
            elif event.key == pygame.K_RETURN:
                return self._try_create()
        elif event.type == pygame.TEXTINPUT and len(self.name) < 32:
            self.name += event.text
        elif event.type == pygame.MOUSEWHEEL:
            self._scroll(-event.y)
        return True

    def _try_create(self):
        self.error = self.validation_error()
        return "handled" if self.error else "create"

    def _max_scroll_row(self):
        rows = (len(self.collection) + self.GRID_COLUMNS - 1) // self.GRID_COLUMNS
        return max(0, rows - self.VISIBLE_ROWS)

    def _scroll(self, rows):
        self.scroll_row = max(0, min(self._max_scroll_row(), self.scroll_row + rows))
        self._layout_cards()

    def _layout_cards(self):
        self.rects = []
        for index in range(len(self.collection)):
            row = index // self.GRID_COLUMNS - self.scroll_row
            if 0 <= row < self.VISIBLE_ROWS:
                rect = pygame.Rect(430 + (index % self.GRID_COLUMNS) * 260, self.GRID_TOP + row * self.ROW_HEIGHT, 240, 50)
            else:
                rect = pygame.Rect(0, 0, 0, 0)  # вне видимой области — не рисуется и не кликается
            self.rects.append(rect)

    def _load_collection(self):
        class_cards = cards_for_type(self.character_type)
        class_keys = {card.key for card in class_cards}
        try:
            owned = list(self.card_loader() if self.card_loader else [])
        except Exception as error:  # сеть/сервер недоступны — не роняем клиент
            self.error = str(error)
            owned = []
        if self.card_loader is None:
            # Офлайн: коллекции нет, доступны все карты класса
            owned = [{"key": card.key, "name": card.name, "quantity": 1} for card in class_cards]
        collection = []
        for entry in owned:
            key = entry.get("key", entry.get("card_key"))
            if key in class_keys:
                collection.append({**entry, "key": key})
        return collection

    def handle_click(self, position):
        if not self.is_open:
            return None
        if self.close_button.collidepoint(position):
            self.close()
            return "close"
        if self.create_button.collidepoint(position):
            self.creating = True
            self.name = ""
            self.error = ""
            self.collection = self._load_collection()
            if not self.collection and not self.error:
                self.error = "В коллекции нет карт вашего класса"
            self.selected_cards = []
            self.scroll_row = 0
            self._layout_cards()
            return "handled"
        if self.creating:
            if self.save_button.collidepoint(position):
                return self._try_create()
            for rect, card in zip(self.rects, self.collection):
                key = card["key"]
                if rect.collidepoint(position):
                    if key in self.selected_cards:
                        self.selected_cards.remove(key)
                    elif len(self.selected_cards) < DECK_SIZE:
                        self.selected_cards.append(key)
                    self.error = ""
                    return "handled"
            return "handled"
        for index, (rect, deck) in enumerate(zip(self.rects, self.decks)):
            if rect.collidepoint(position):
                delete_rect = pygame.Rect(rect.right - 120, rect.y + 8, 105, 42)
                if delete_rect.collidepoint(position):
                    return "delete_deck", deck
                self.selected_deck = deck
                self.close()
                return deck
        return "handled"

    def validation_error(self):
        owned = {card["key"] for card in self.collection}
        error = deck_validation_error(self.selected_cards, self.character_type, owned)
        if error:
            return error
        if not self.name.strip():
            return "Введите название колоды"
        return ""

    def draw(self, screen):
        if not self.is_open:
            return
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        screen.blit(overlay, (0, 0))
        pygame.draw.rect(screen, (30, 25, 42), self.panel, border_radius=10)
        pygame.draw.rect(screen, (150, 100, 200), self.panel, 2, border_radius=10)
        screen.blit(self.font.render("ВЫБОР КОЛОДЫ", True, (240, 220, 255)), (430, 215))
        pygame.draw.rect(screen, (70, 120, 150), self.create_button, border_radius=5)
        screen.blit(self.small_font.render("СОЗДАТЬ КОЛОДУ", True, (255, 255, 255)), (450, 227))
        pygame.draw.rect(screen, (110, 65, 75), self.close_button, border_radius=5)
        screen.blit(self.small_font.render("ЗАКРЫТЬ", True, (255, 255, 255)), (1400, 217))
        if self.creating:
            pygame.draw.rect(screen, (245, 245, 250), self.name_rect, border_radius=4)
            screen.blit(self.small_font.render(self.name or "Введите название", True, (30, 30, 40)), (self.name_rect.x + 10, self.name_rect.y + 11))
            pygame.draw.rect(screen, (65, 120, 85), self.save_button, border_radius=5)
            screen.blit(self.small_font.render("СОХРАНИТЬ", True, (255, 255, 255)), (self.save_button.x + 18, self.save_button.y + 12))
            screen.blit(self.small_font.render(f"Выбрано карт: {len(self.selected_cards)}/{DECK_SIZE}", True, (245, 220, 150)), (430, 255))
            screen.blit(self.small_font.render("Ульта требует 5 обычных карт своего стиля", True, (190, 200, 215)), (430, 275))
            if self.error:
                screen.blit(self.small_font.render(self.error, True, (255, 100, 100)), (900, 255))
            for rect, card in zip(self.rects, self.collection):
                if not rect.width:
                    continue
                key = card["key"]
                selected = key in self.selected_cards
                pygame.draw.rect(screen, (65, 120, 85) if selected else (50, 55, 75), rect, border_radius=5)
                pygame.draw.rect(screen, (160, 220, 170) if selected else (120, 130, 155), rect, 2, border_radius=5)
                screen.blit(self.small_font.render(str(card.get("name", key)), True, (245, 240, 225)), (rect.x + 8, rect.y + 8))
                group = str(card.get("group_name", key)).split(":", 1)[-1].strip()
                screen.blit(self.small_font.render(group, True, (190, 200, 215)), (rect.x + 8, rect.y + 28))
            if self._max_scroll_row():
                screen.blit(self.small_font.render("Прокрутка колесом мыши", True, (170, 170, 190)), (430, 740))
            return
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