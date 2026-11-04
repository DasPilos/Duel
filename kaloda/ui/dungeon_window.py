"""Room interactions for the linear graveyard dungeon."""

import uuid

import pygame

from client.network import ServerError
from kaloda import settings
from kaloda.combat.card_database import DUNGEON_CARD_KEYS
from kaloda.currency import format_coins
from kaloda.ui.card_tooltip import card_from_catalog, draw_card_tooltip
from kaloda.ui.hud import draw_button


class DungeonRoomWindow:
    WIDTH = 820
    HEIGHT = 500

    def __init__(self, scene):
        self.scene = scene
        self.is_open = False
        self.room = None
        self.items = []
        self.cards = []
        self.selected_index = 0
        self.message = None
        self.treasure_opened = False
        self.treasure_request_id = None
        self.treasure_rewards = []
        self.rect = pygame.Rect(0, 0, self.WIDTH, self.HEIGHT)
        self.rect.center = (settings.WIDTH // 2, settings.HEIGHT // 2)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 27, bold=True)
        self.font = pygame.font.SysFont(settings.FONT_NAME, 18)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 15)
        self.close_rect = pygame.Rect(self.rect.right - 44, self.rect.top + 10, 32, 32)
        self.buy_rect = pygame.Rect(self.rect.right - 226, self.rect.bottom - 58, 194, 40)
        self.continue_rect = pygame.Rect(self.rect.left + 30, self.rect.bottom - 58, 194, 40)
        self.action_rect = pygame.Rect(self.rect.right - 226, self.rect.bottom - 58, 194, 40)

    def open(self, room):
        previous_room = self.room
        self.room = int(room)
        self.is_open = True
        self.message = None
        self.selected_index = 0
        if previous_room != self.room:
            self.treasure_opened = False
            self.treasure_rewards = []
        if self.room == 2:
            client = getattr(self.scene.session, "client", None)
            try:
                self.items = client.get_supplies_shop_catalog()
                self.cards = [
                    card for card in client.get_dungeon_card_shop_catalog()
                    if card.get("key") in DUNGEON_CARD_KEYS
                ]
            except (ServerError, AttributeError, KeyError, OSError) as error:
                self.items = []
                self.cards = []
                self.message = f"Не удалось загрузить ассортимент: {error}"
        elif self.room == 6:
            if self.treasure_request_id is None:
                self.treasure_request_id = str(uuid.uuid4())

    def close(self):
        self.is_open = False

    def update(self, _dt):
        pass

    def _rows(self):
        return [
            pygame.Rect(
                self.rect.left + 24,
                self.rect.top + 92 + index * 47,
                self.rect.width - 48,
                41,
            )
            for index in range(len(self.items) + len(self.cards))
        ]

    def handle_event(self, event):
        if not self.is_open:
            return False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.close()
            return True
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return event.type in (
                pygame.MOUSEBUTTONDOWN,
                pygame.MOUSEBUTTONUP,
                pygame.MOUSEWHEEL,
                pygame.KEYDOWN,
            )
        if not self.rect.collidepoint(event.pos):
            return True
        if self.close_rect.collidepoint(event.pos):
            self.close()
            return True
        if self.room == 2:
            for index, row in enumerate(self._rows()):
                if row.collidepoint(event.pos):
                    self.selected_index = index
                    self.message = None
                    return True
            if self.buy_rect.collidepoint(event.pos):
                self._buy_selected()
            elif self.continue_rect.collidepoint(event.pos):
                self.scene.advance_dungeon_room()
            return True
        if self.room == 4:
            if self.continue_rect.collidepoint(event.pos):
                self.scene.advance_dungeon_room()
            return True
        if self.room == 6:
            if self.treasure_opened and self.continue_rect.collidepoint(event.pos):
                self.scene.exit_dungeon()
            elif not self.treasure_opened and self.action_rect.collidepoint(event.pos):
                self._open_treasure()
            return True
        return True

    def _sync_coins(self, result):
        character = getattr(self.scene.session, "character", None)
        saved = result.get("character") or {}
        if isinstance(character, dict) and "coins" in saved:
            character["coins"] = saved["coins"]

    def _buy_selected(self):
        item_count = len(self.items)
        if self.selected_index < item_count:
            item = self.items[self.selected_index]
            character = getattr(self.scene.session, "character", None)
            if not isinstance(character, dict) or character.get("id") is None:
                self.message = "Персонаж не загружен"
                return
            try:
                result = self.scene.session.client.buy_supplies_item(
                    character["id"], item["item_id"]
                )
            except (ServerError, AttributeError, KeyError, OSError) as error:
                self.message = f"Не удалось купить товар: {error}"
                return
            self._sync_coins(result)
            self.message = f"Куплено: {item['name']}"
            return
        card = self.cards[self.selected_index - item_count]
        if not card.get("available", False):
            self.message = "Эта карта пока недоступна для покупки"
            return
        character = getattr(self.scene.session, "character", None)
        if not isinstance(character, dict) or character.get("id") is None:
            self.message = "Персонаж не загружен"
            return
        try:
            result = self.scene.session.client.buy_dungeon_card(character["id"], card["key"])
        except (ServerError, AttributeError, KeyError, OSError) as error:
            self.message = f"Не удалось купить карту: {error}"
            return
        self._sync_coins(result)
        self.message = f"Куплена карта: {card['name']}"

    def _open_treasure(self):
        character = getattr(self.scene.session, "character", None)
        if not isinstance(character, dict) or character.get("id") is None:
            self.message = "Персонаж не загружен"
            return
        try:
            result = self.scene.session.client.claim_dungeon_treasure(
                character["id"], self.treasure_request_id
            )
        except (ServerError, AttributeError, KeyError, OSError) as error:
            self.message = f"Не удалось открыть сундук: {error}"
            return
        self._sync_coins(result)
        self.treasure_rewards = result.get("rewards", [])
        self.treasure_opened = True
        self.message = "Награды добавлены в инвентарь"

    def draw(self, screen):
        if not self.is_open:
            return
        shade = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 155))
        screen.blit(shade, (0, 0))
        pygame.draw.rect(screen, (27, 29, 35), self.rect, border_radius=12)
        pygame.draw.rect(screen, (115, 112, 101), self.rect, 3, border_radius=12)
        title = {
            2: "Подземный торговец",
            4: "Целебный фонтан",
            6: "Сундук павшего короля",
        }[self.room]
        screen.blit(
            self.title_font.render(title, True, (230, 222, 200)),
            (self.rect.left + 24, self.rect.top + 18),
        )
        character = getattr(self.scene.session, "character", None)
        balance = int(character.get("coins", 0)) if isinstance(character, dict) else 0
        balance_text = self.small_font.render(
            f"У вас: {format_coins(balance)}",
            True,
            (238, 208, 118),
        )
        screen.blit(balance_text, (self.rect.left + 24, self.rect.top + 56))
        if self.room == 2:
            hovered_card = None
            mouse_pos = pygame.mouse.get_pos()
            for index, row in enumerate(self._rows()):
                selected = index == self.selected_index
                pygame.draw.rect(
                    screen,
                    (64, 69, 78) if selected else (42, 44, 51),
                    row,
                    border_radius=5,
                )
                name, price = self._merchant_entry(index)
                screen.blit(self.small_font.render(name, True, (238, 235, 222)),
                            (row.left + 10, row.top + 11))
                screen.blit(self.small_font.render(price, True, (238, 208, 118)),
                            (row.right - 120, row.top + 11))
                if index >= len(self.items) and row.collidepoint(mouse_pos):
                    hovered_card = self.cards[index - len(self.items)]
            draw_button(screen, self.buy_rect, "КУПИТЬ", self.font, color=(100, 83, 48))
            draw_button(screen, self.continue_rect, "ЗАКРЫТЬ МАГАЗИН", self.small_font, color=(55, 100, 70))
            if hovered_card is not None:
                draw_card_tooltip(
                    screen,
                    card_from_catalog(hovered_card),
                    mouse_pos,
                    self.small_font,
                )
        elif self.room == 4:
            self._draw_centered(screen, "Фонтан полностью восстанавливает здоровье и ману.",
                                self.rect.top + 168)
            draw_button(screen, self.continue_rect, "ДАЛЬШЕ", self.font, color=(55, 100, 70))
        elif self.room == 6:
            if not self.treasure_opened:
                self._draw_centered(screen, "Откройте сундук, чтобы получить все выпавшие награды.",
                                    self.rect.top + 168)
                draw_button(screen, self.action_rect, "ОТКРЫТЬ СУНДУК", self.font, color=(125, 88, 37))
            else:
                for index, reward in enumerate(self.treasure_rewards[:6]):
                    self._draw_centered(screen, str(reward), self.rect.top + 128 + index * 34)
                draw_button(screen, self.continue_rect, "ВЫЙТИ", self.font, color=(55, 100, 70))
        if self.message:
            self._draw_centered(screen, self.message, self.rect.bottom - 90, (245, 220, 150))

    def _merchant_entry(self, index):
        if index < len(self.items):
            item = self.items[index]
            return item["name"], format_coins(item.get("price", 0))
        card = self.cards[index - len(self.items)]
        price = format_coins(card.get("price", 0)) if card.get("available") else "временно недоступно"
        return card["name"], price

    def _draw_centered(self, screen, text, y, color=(215, 215, 207)):
        image = self.small_font.render(text, True, color)
        screen.blit(image, image.get_rect(center=(self.rect.centerx, y)))
