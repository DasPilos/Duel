import pygame


class DeckSelectionPanel:
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
        self.create_button = pygame.Rect(430, 215, 220, 40)
        self.name_rect = pygame.Rect(680, 215, 500, 40)
        self.panel = pygame.Rect(380, 180, 1160, 620)
        self.close_button = pygame.Rect(1370, 205, 140, 40)

    def open(self, decks):
        self.decks = list(decks or [])
        self.selected_deck = next((deck for deck in self.decks if deck.get("is_active")), None)
        self.is_open = True
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
                self.error = self.validation_error()
                if not self.error:
                    return "create"
        elif event.type == pygame.TEXTINPUT and len(self.name) < 32:
            self.name += event.text
        return True

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
            self.collection = list(self.card_loader() if self.card_loader else [])
            if not self.collection:
                from combat.card_database import MAGE_CARDS
                self.collection = [
                    {"key": card.key, "name": card.name, "quantity": 1}
                    for card in MAGE_CARDS
                ]
            self.selected_cards = []
            self.rects = [pygame.Rect(430 + (index % 4) * 260, 290 + (index // 4) * 62, 240, 50) for index in range(len(self.collection))]
            return "handled"
        if self.creating:
            for rect, card in zip(self.rects, self.collection):
                key = card.get("key", card.get("card_key"))
                if rect.collidepoint(position):
                    if key in self.selected_cards:
                        self.selected_cards.remove(key)
                    elif len(self.selected_cards) < 22:
                        self.selected_cards.append(key)
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
        if len(self.selected_cards) != 22:
            return "Нужно выбрать ровно 22 уникальные карты"
        selected = {str(key) for key in self.selected_cards}
        from combat.card_database import MAGE_CARDS
        by_key = {card.key: card for card in MAGE_CARDS}
        missing = [key for key in selected if key not in by_key]
        if missing:
            return "В колоде есть неизвестная карта"
        for key in selected:
            card = by_key[key]
            if card.effect_data.get("ultimate"):
                element = card.effect_data.get("element")
                count = sum(
                    1 for selected_key in selected
                    if by_key[selected_key].effect_data.get("element") == element
                    and not by_key[selected_key].effect_data.get("ultimate")
                )
                if count < 5:
                    return f"Ульта «{card.name}» требует минимум 5 карт элемента «{element}»"
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
            error = self.validation_error()
            if error:
                self.error = error
            pygame.draw.rect(screen, (245, 245, 250), self.name_rect, border_radius=4)
            screen.blit(self.small_font.render(self.name or "Введите название", True, (30, 30, 40)), (self.name_rect.x + 10, self.name_rect.y + 11))
            screen.blit(self.small_font.render(f"Выбрано карт: {len(self.selected_cards)}/22", True, (245, 220, 150)), (430, 255))
            screen.blit(self.small_font.render("Ульта требует 5 обычных карт своего элемента", True, (190, 200, 215)), (430, 275))
            if self.error:
                screen.blit(self.small_font.render(self.error, True, (255, 100, 100)), (900, 255))
            for rect, card in zip(self.rects, self.collection):
                key = card.get("key", card.get("card_key"))
                selected = key in self.selected_cards
                pygame.draw.rect(screen, (65, 120, 85) if selected else (50, 55, 75), rect, border_radius=5)
                pygame.draw.rect(screen, (160, 220, 170) if selected else (120, 130, 155), rect, 2, border_radius=5)
                screen.blit(self.small_font.render(str(card.get("name", key)), True, (245, 240, 225)), (rect.x + 8, rect.y + 8))
                screen.blit(self.small_font.render(f"{key} x{card.get('quantity', 1)}", True, (190, 200, 215)), (rect.x + 8, rect.y + 28))
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