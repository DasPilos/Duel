"""Окно магазина припасов."""

import pygame

from client.network import ServerError
from kaloda import settings
from kaloda.currency import format_coins
from kaloda.ui.hud import draw_button


class SuppliesShopWindow:
    WIDTH = 760
    HEIGHT = 440

    def __init__(self, scene):
        self.scene = scene
        self.is_open = False
        self.items = []
        self.selected_index = 0
        self.message = None
        self.rect = pygame.Rect(0, 0, self.WIDTH, self.HEIGHT)
        self.rect.center = (settings.WIDTH // 2, settings.HEIGHT // 2)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 28, bold=True)
        self.font = pygame.font.SysFont(settings.FONT_NAME, 19)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 16)
        self.close_rect = pygame.Rect(self.rect.right - 46, self.rect.top + 12, 34, 34)
        self.buy_rect = pygame.Rect(self.rect.right - 220, self.rect.bottom - 62, 196, 42)

    def open(self):
        self.is_open = True
        self.message = None
        client = getattr(self.scene.session, "client", None)
        try:
            self.items = client.get_supplies_shop_catalog()
        except (ServerError, AttributeError, OSError) as error:
            self.items = []
            self.message = f"Не удалось загрузить ассортимент: {error}"
        self.selected_index = min(self.selected_index, max(0, len(self.items) - 1))

    def close(self):
        self.is_open = False

    def handle_event(self, event):
        if not self.is_open:
            return False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.close()
            return True
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL, pygame.KEYDOWN)
        if self.close_rect.collidepoint(event.pos) or not self.rect.collidepoint(event.pos):
            self.close()
            return True
        for index, rect in enumerate(self.item_rows()):
            if rect.collidepoint(event.pos):
                self.selected_index = index
                self.message = None
                return True
        if self.buy_rect.collidepoint(event.pos):
            self._buy()
        return True

    def item_rows(self):
        return [
            pygame.Rect(self.rect.left + 24, self.rect.top + 86 + index * 64, self.rect.width - 48, 56)
            for index in range(len(self.items))
        ]

    def _buy(self):
        if not self.items:
            self.message = "Товары не загружены"
            return
        character = getattr(self.scene.session, "character", None)
        if not isinstance(character, dict) or character.get("id") is None:
            self.message = "Персонаж не загружен"
            return
        try:
            result = self.scene.session.client.buy_supplies_item(
                character["id"], self.items[self.selected_index]["item_id"]
            )
        except (ServerError, AttributeError, KeyError, OSError) as error:
            self.message = f"Не удалось купить товар: {error}"
            return
        character.update(result.get("character") or {})
        self.message = f"Куплено: {self.items[self.selected_index]['name']}"

    def draw(self, screen):
        if not self.is_open:
            return
        shade = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 140))
        screen.blit(shade, (0, 0))
        pygame.draw.rect(screen, (20, 31, 44), self.rect, border_radius=10)
        pygame.draw.rect(screen, (80, 155, 220), self.rect, 3, border_radius=10)
        screen.blit(self.title_font.render("Магазин с припасами", True, (140, 205, 255)),
                    (self.rect.left + 24, self.rect.top + 18))
        character = getattr(self.scene.session, "character", None)
        balance = int(character.get("coins", 0)) if isinstance(character, dict) else 0
        balance_text = self.small_font.render(
            f"У вас: {format_coins(balance)}", True, (240, 210, 115)
        )
        screen.blit(balance_text, (self.rect.left + 24, self.rect.top + 55))
        pygame.draw.rect(screen, (120, 60, 50), self.close_rect, border_radius=6)
        cross = self.font.render("×", True, (255, 255, 255))
        screen.blit(cross, cross.get_rect(center=self.close_rect.center))
        for index, (item, row) in enumerate(zip(self.items, self.item_rows())):
            selected = index == self.selected_index
            pygame.draw.rect(screen, (45, 76, 102) if selected else (32, 48, 64), row, border_radius=6)
            pygame.draw.rect(screen, (105, 185, 240) if selected else (70, 100, 125), row, 2, border_radius=6)
            screen.blit(self.font.render(item["name"], True, (240, 245, 250)),
                        (row.left + 12, row.top + 5))
            screen.blit(self.small_font.render(item["description"], True, (190, 205, 220)),
                        (row.left + 12, row.top + 31))
            price = self.small_font.render(
                format_coins(item.get("price", 0)), True, (240, 210, 115)
            )
            screen.blit(price, (row.right - price.get_width() - 12, row.top + 18))
        draw_button(screen, self.buy_rect, "КУПИТЬ", self.font,
                    color=(50, 115, 165), hover_color=(65, 145, 195))
        if self.message:
            screen.blit(self.small_font.render(self.message, True, (245, 220, 140)),
                        (self.rect.left + 24, self.rect.bottom - 52))
