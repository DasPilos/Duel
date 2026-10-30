"""Окно карточной лавки."""

import pygame

from client.network import ServerError
from kaloda import settings
from kaloda.currency import format_coins
from kaloda.ui.card_tooltip import card_from_catalog, draw_card_tooltip
from kaloda.ui.hud import draw_button


CARD_CATEGORIES = (
    ("all", "Все"),
    ("movement", "Передвижение"),
    ("traps", "Ловушки"),
    ("damage", "Урон"),
    ("healing", "Лечение/ресурс"),
    ("defense", "Защита"),
    ("summons", "Призывы"),
    ("control", "Контроль"),
)

CARD_CATEGORY_BY_KEY = {
    "universal_dash": "movement",
    "universal_trap": "traps",
    "universal_roots_trap": "traps",
    "universal_knockback": "damage",
    "universal_bonebreaker": "control",
    "universal_resource_recovery": "healing",
    "universal_barricade": "defense",
    "universal_wolf": "summons",
}


def _card_description(card):
    data = card.get("effect_data") or {}
    key = card.get("key")
    descriptions = {
        "universal_trap": "Ловушка: 19 урона без крита при наступании врага",
        "universal_barricade": "Баррикада на 3 гекса, 8 ходов; блокирует движение и карты",
        "universal_dash": "Перемещение на 3 гекса",
        "universal_wolf": "Призывает волка с характеристиками волка Древнего ента",
        "universal_roots_trap": "Ловушка: 8 урона и корни на 2 хода",
        "universal_resource_recovery": "Восстанавливает 15% ресурса; следующий урон +25%",
        "universal_knockback": "12 урона без крита и отбрасывание на 3 гекса",
    }
    description = descriptions.get(key, card.get("name", "Карта"))
    return f"{description}. Дальность: {data.get('range', 0)} гекс.; ресурс: {card.get('resource_cost', 0)}"


class CardShopWindow:
    WIDTH = 820
    HEIGHT = 590
    ROW_HEIGHT = 48
    ROW_GAP = 5
    CONTENT_TOP = 138
    CONTENT_BOTTOM = HEIGHT - 74

    def __init__(self, scene):
        self.scene = scene
        self.is_open = False
        self.cards = []
        self.owned = {}
        self.selected_index = 0
        self.selected_category = "all"
        self.scroll_offset = 0
        self.message = None
        self.rect = pygame.Rect(0, 0, self.WIDTH, self.HEIGHT)
        self.rect.center = (settings.WIDTH // 2, settings.HEIGHT // 2)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 28, bold=True)
        self.font = pygame.font.SysFont(settings.FONT_NAME, 18)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 15)
        self.close_rect = pygame.Rect(self.rect.right - 46, self.rect.top + 12, 34, 34)
        self.buy_rect = pygame.Rect(self.rect.right - 220, self.rect.bottom - 62, 196, 42)
        self.category_rects = self._category_rects()

    def _category_rects(self):
        gap = 5
        columns = 4
        width = (self.rect.width - 40 - gap * (columns - 1)) // columns
        return {
            key: pygame.Rect(
                self.rect.left + 20 + index % columns * (width + gap),
                self.rect.top + 78 + index // columns * 26,
                width,
                22,
            )
            for index, (key, _) in enumerate(CARD_CATEGORIES)
        }

    @property
    def filtered_cards(self):
        return [
            card for card in self.cards
            if self.selected_category == "all"
            or CARD_CATEGORY_BY_KEY.get(card.get("key"), "control") == self.selected_category
        ]

    @property
    def visible_row_count(self):
        return max(1, (self.CONTENT_BOTTOM - self.CONTENT_TOP + self.ROW_GAP)
                   // (self.ROW_HEIGHT + self.ROW_GAP))

    def open(self):
        self.is_open = True
        self.message = None
        client = getattr(self.scene.session, "client", None)
        character = getattr(self.scene.session, "character", None)
        try:
            self.cards = client.get_card_shop_catalog()
            collection = client.get_card_collection(character["id"])
            self.owned = {
                entry["card_key"]: int(entry.get("quantity", 0))
                for entry in collection
            }
        except (ServerError, AttributeError, KeyError, OSError) as error:
            self.cards = []
            self.owned = {}
            self.message = f"Не удалось загрузить ассортимент: {error}"
        self.selected_index = min(self.selected_index, max(0, len(self.filtered_cards) - 1))
        self.scroll_offset = 0

    def close(self):
        self.is_open = False

    def item_rows(self):
        count = min(self.visible_row_count, max(0, len(self.filtered_cards) - self.scroll_offset))
        return [
            pygame.Rect(
                self.rect.left + 20,
                self.rect.top + self.CONTENT_TOP + index * (self.ROW_HEIGHT + self.ROW_GAP),
                self.rect.width - 40,
                self.ROW_HEIGHT,
            )
            for index in range(count)
        ]

    def handle_event(self, event):
        if not self.is_open:
            return False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.close()
            return True
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_UP, pygame.K_DOWN):
            self._scroll(-1 if event.key == pygame.K_UP else 1)
            return True
        if event.type == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(pygame.mouse.get_pos()):
                self._scroll(-event.y)
            return True
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL, pygame.KEYDOWN)
        if self.close_rect.collidepoint(event.pos) or not self.rect.collidepoint(event.pos):
            self.close()
            return True
        for category, rect in self.category_rects.items():
            if rect.collidepoint(event.pos):
                self.selected_category = category
                self.selected_index = 0
                self.scroll_offset = 0
                self.message = None
                return True
        for index, rect in enumerate(self.item_rows()):
            if rect.collidepoint(event.pos):
                self.selected_index = self.scroll_offset + index
                self.message = None
                return True
        if self.buy_rect.collidepoint(event.pos):
            self._buy()
        return True

    def _scroll(self, amount):
        maximum = max(0, len(self.filtered_cards) - self.visible_row_count)
        self.scroll_offset = max(0, min(maximum, self.scroll_offset + int(amount)))
        self.selected_index = max(
            self.scroll_offset,
            min(self.selected_index, max(self.scroll_offset, len(self.filtered_cards) - 1)),
        )

    def _buy(self):
        cards = self.filtered_cards
        if not cards:
            return
        character = getattr(self.scene.session, "character", None)
        if not isinstance(character, dict) or character.get("id") is None:
            self.message = "Персонаж не загружен"
            return
        card = cards[self.selected_index]
        try:
            result = self.scene.session.client.buy_card(character["id"], card["key"])
            character.update(result.get("character") or {})
            self.owned[card["key"]] = self.owned.get(card["key"], 0) + 1
            self.message = f"Куплено: {card['name']}"
        except (ServerError, AttributeError, KeyError, OSError) as error:
            self.message = f"Не удалось купить карту: {error}"

    def draw(self, screen):
        if not self.is_open:
            return
        shade = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        screen.blit(shade, (0, 0))
        pygame.draw.rect(screen, (30, 24, 40), self.rect, border_radius=10)
        pygame.draw.rect(screen, (170, 115, 210), self.rect, 3, border_radius=10)
        screen.blit(self.title_font.render("Карточная лавка", True, (220, 175, 245)),
                    (self.rect.left + 22, self.rect.top + 16))
        character = getattr(self.scene.session, "character", None)
        balance = int(character.get("coins", 0)) if isinstance(character, dict) else 0
        screen.blit(self.small_font.render(
            f"У вас: {format_coins(balance)}", True, (240, 210, 115)
        ), (self.rect.left + 22, self.rect.top + 52))
        for category, label in CARD_CATEGORIES:
            rect = self.category_rects[category]
            active = category == self.selected_category
            pygame.draw.rect(
                screen,
                (95, 60, 125) if active else (45, 37, 54),
                rect,
                border_radius=5,
            )
            pygame.draw.rect(
                screen,
                (190, 145, 225) if active else (95, 75, 110),
                rect,
                1,
                border_radius=5,
            )
            label_surface = self.small_font.render(label, True, (245, 240, 250))
            screen.blit(label_surface, label_surface.get_rect(center=rect.center))
        pygame.draw.rect(screen, (120, 60, 50), self.close_rect, border_radius=6)
        screen.blit(self.font.render("×", True, (255, 255, 255)),
                    self.font.render("×", True, (255, 255, 255)).get_rect(center=self.close_rect.center))
        cards = self.filtered_cards
        rows = self.item_rows()
        hovered_card = None
        mouse_pos = pygame.mouse.get_pos()
        for row_index, (card, row) in enumerate(
            zip(cards[self.scroll_offset:], rows)
        ):
            selected = self.scroll_offset + row_index == self.selected_index
            pygame.draw.rect(screen, (65, 48, 78) if selected else (42, 36, 52), row, border_radius=6)
            pygame.draw.rect(screen, (190, 145, 225) if selected else (95, 75, 110), row, 2, border_radius=6)
            screen.blit(self.font.render(card["name"], True, (245, 240, 250)),
                        (row.left + 10, row.top + 4))
            description = _card_description(card)
            description_surface = self.small_font.render(description, True, (205, 195, 215))
            available_width = row.width - 20
            if description_surface.get_width() > available_width:
                while description and self.small_font.size(description + "…")[0] > available_width:
                    description = description[:-1]
                description += "…"
            screen.blit(self.small_font.render(description, True, (205, 195, 215)),
                        (row.left + 10, row.top + 28))
            owned = self.owned.get(card["key"], 0)
            price = format_coins(card["price"])
            status = f"В коллекции: {owned}   {price}"
            text = self.small_font.render(status, True, (240, 210, 115))
            screen.blit(text, (row.right - text.get_width() - 10, row.top + 7))
            if row.collidepoint(mouse_pos):
                hovered_card = card
        if len(cards) > self.visible_row_count:
            scroll_label = self.small_font.render(
                f"{self.scroll_offset + 1}–{min(len(cards), self.scroll_offset + self.visible_row_count)} / {len(cards)}",
                True,
                (190, 180, 200),
            )
            screen.blit(scroll_label, (self.rect.left + 22, self.rect.bottom - 54))
        draw_button(screen, self.buy_rect, "КУПИТЬ", self.font,
                    color=(95, 60, 125), hover_color=(125, 80, 160))
        if self.message:
            screen.blit(self.small_font.render(self.message, True, (245, 220, 150)),
                        (self.rect.left + 22, self.rect.bottom - 52))
        if hovered_card is not None:
            draw_card_tooltip(
                screen,
                card_from_catalog(hovered_card),
                mouse_pos,
                self.small_font,
            )
