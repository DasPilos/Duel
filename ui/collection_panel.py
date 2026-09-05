from pathlib import Path

import pygame

from core import settings


class CollectionPanel:
    COLS = 6
    ROWS = 10
    CARD_WIDTH = 250
    CARD_HEIGHT = 350
    GAP = 8
    SCROLL_STEP = 120

    def __init__(self):
        self.is_open = False
        self.cards = []
        self.sort_mode = "slot"
        self.scroll_y = 0
        self.selected_card = None
        self.image_cache = {}
        self.font = pygame.font.SysFont(settings.FONT_NAME, 20)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 16)
        self.panel_width = self.COLS * self.CARD_WIDTH + (self.COLS - 1) * self.GAP
        self.panel_x = (settings.WIDTH - self.panel_width) // 2
        self.viewport = pygame.Rect(self.panel_x, 150, self.panel_width, 800)
        self.sort_button = pygame.Rect(self.panel_x, 96, 260, 40)
        self.close_button = pygame.Rect(self.viewport.right - 140, 96, 140, 40)

    @property
    def content_height(self):
        return self.ROWS * self.CARD_HEIGHT + (self.ROWS - 1) * self.GAP

    @property
    def max_scroll(self):
        return max(0, self.content_height - self.viewport.height)

    def set_cards(self, cards):
        self.cards = list(cards)[: self.COLS * self.ROWS]
        self._sort_cards()
        self.scroll_y = min(self.scroll_y, self.max_scroll)

    def open(self, cards):
        self.set_cards(cards)
        self.is_open = True

    def close(self):
        self.is_open = False
        self.selected_card = None

    def handle_event(self, event):
        if not self.is_open or event.type != pygame.MOUSEWHEEL:
            return False
        if not self.viewport.collidepoint(pygame.mouse.get_pos()):
            return False
        self.scroll_y = max(
            0,
            min(self.max_scroll, self.scroll_y - event.y * self.SCROLL_STEP),
        )
        return True

    def handle_click(self, position):
        if not self.is_open:
            return None
        if self.close_button.collidepoint(position):
            self.close()
            return "close"
        if self.sort_button.collidepoint(position):
            modes = ("slot", "name", "group", "level", "recent")
            index = (modes.index(self.sort_mode) + 1) % len(modes)
            self.sort_mode = modes[index]
            self._sort_cards()
            return "sort"
        if not self.viewport.collidepoint(position):
            self.close()
            return "close"

        for index, card in enumerate(self.cards):
            if self._card_rect(index).collidepoint(position):
                self.selected_card = card
                return card
        return None

    def _sort_cards(self):
        sort_keys = {
            "slot": lambda card: int(card.get("slot_index", 0)),
            "name": lambda card: str(card.get("name", "")).casefold(),
            "group": lambda card: (
                str(card.get("group_name", "")).casefold(),
                str(card.get("name", "")).casefold(),
            ),
            "level": lambda card: (
                int(card.get("level", 1)),
                str(card.get("name", "")).casefold(),
            ),
            "recent": lambda card: -float(card.get("acquired_at", 0)),
        }
        self.cards.sort(key=sort_keys[self.sort_mode])

    def _card_rect(self, index):
        row, col = divmod(index, self.COLS)
        return pygame.Rect(
            self.panel_x + col * (self.CARD_WIDTH + self.GAP),
            self.viewport.y + row * (self.CARD_HEIGHT + self.GAP) - self.scroll_y,
            self.CARD_WIDTH,
            self.CARD_HEIGHT,
        )

    def _load_image(self, image_path):
        if not image_path:
            return None
        if image_path not in self.image_cache:
            path = Path(image_path)
            if not path.is_absolute():
                path = Path(__file__).resolve().parent.parent / path
            try:
                source = pygame.image.load(str(path)).convert_alpha()
                self.image_cache[image_path] = pygame.transform.smoothscale(
                    source,
                    (self.CARD_WIDTH, self.CARD_HEIGHT),
                )
            except (pygame.error, OSError):
                self.image_cache[image_path] = None
        return self.image_cache[image_path]

    def draw(self, screen):
        if not self.is_open:
            return

        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 210))
        screen.blit(overlay, (0, 0))

        title = self.font.render(
            f"КОЛЛЕКЦИЯ КАРТ — {sum(int(card.get('quantity', 1)) for card in self.cards)}",
            True,
            (245, 220, 150),
        )
        screen.blit(title, (self.panel_x, 55))
        sort_labels = {
            "slot": "По ячейкам",
            "name": "По названию",
            "group": "По группе",
            "level": "По уровню",
            "recent": "Сначала новые",
        }
        pygame.draw.rect(screen, (75, 90, 120), self.sort_button, border_radius=5)
        sort_text = self.small_font.render(
            f"Сортировка: {sort_labels[self.sort_mode]}",
            True,
            (240, 240, 240),
        )
        screen.blit(sort_text, sort_text.get_rect(center=self.sort_button.center))
        pygame.draw.rect(screen, (120, 65, 65), self.close_button, border_radius=5)
        close_text = self.small_font.render("ЗАКРЫТЬ", True, (255, 255, 255))
        screen.blit(close_text, close_text.get_rect(center=self.close_button.center))

        previous_clip = screen.get_clip()
        screen.set_clip(self.viewport)
        for index in range(self.COLS * self.ROWS):
            rect = self._card_rect(index)
            if not rect.colliderect(self.viewport):
                continue
            pygame.draw.rect(screen, (43, 50, 68), rect)
            pygame.draw.rect(screen, (130, 140, 165), rect, 2)
            if index >= len(self.cards):
                continue
            card = self.cards[index]
            image = self._load_image(card.get("image_path", ""))
            if image is not None:
                screen.blit(image, rect)
            label_bg = pygame.Surface((rect.width, 66), pygame.SRCALPHA)
            label_bg.fill((10, 12, 18, 215))
            screen.blit(label_bg, (rect.x, rect.bottom - 66))
            name = self.small_font.render(
                str(card.get("name", card.get("key", "Карта"))),
                True,
                (255, 245, 220),
            )
            screen.blit(name, (rect.x + 8, rect.bottom - 58))
            details = self.small_font.render(
                f"Ур. {card.get('level', 1)}",
                True,
                (210, 210, 220),
            )
            screen.blit(details, (rect.x + 8, rect.bottom - 31))
            quantity = int(card.get("quantity", 1))
            if quantity > 1:
                badge = pygame.Rect(rect.right - 58, rect.y + 8, 50, 34)
                pygame.draw.rect(screen, (25, 28, 38), badge, border_radius=8)
                pygame.draw.rect(screen, (235, 205, 105), badge, 2, border_radius=8)
                quantity_text = self.font.render(
                    f"×{quantity}",
                    True,
                    (255, 235, 145),
                )
                screen.blit(
                    quantity_text,
                    quantity_text.get_rect(center=badge.center),
                )
        screen.set_clip(previous_clip)

        if self.max_scroll > 0:
            track = pygame.Rect(self.viewport.right + 8, self.viewport.y, 10, self.viewport.height)
            pygame.draw.rect(screen, (45, 50, 65), track)
            thumb_height = max(40, int(track.height * self.viewport.height / self.content_height))
            thumb_y = track.y + int(
                (track.height - thumb_height) * self.scroll_y / self.max_scroll
            )
            pygame.draw.rect(
                screen,
                (150, 160, 185),
                (track.x, thumb_y, track.width, thumb_height),
                border_radius=4,
            )
