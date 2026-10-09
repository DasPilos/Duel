"""Окно городского хранилища (Амбар, Склад): список товаров, заполненность и улучшение. Данные — с сервера."""

import pygame

from core import settings
from core.production_buildings import RESOURCES, building_config, building_level_info, building_resources
from ui.hud import draw_button
from ui.catalog_icons import draw_building_icon, draw_item_icon
from ui.production_building_window import ProductionBuildingWindow
from ui.storage_meter import draw_storage_meter

STORAGE_VIEW = {"object_id": None, "shape": "none", "harvest_label": "", "plot_names": {}}


class CityStorageWindow(ProductionBuildingWindow):
    """Без горожан и производства: вкладки «Склад» и «Улучшение»."""

    def __init__(self, scene, building):
        super().__init__(scene, building, view=STORAGE_VIEW)
        self.tab = "storage"
        self.rect = pygame.Rect(settings.WIDTH // 2 - 450, settings.HEIGHT // 2 - 380, 900, 760)
        self.close_button = pygame.Rect(self.rect.right - 44, self.rect.top + 12, 32, 32)
        self.storage_tab = pygame.Rect(self.rect.left + 24, self.rect.top + 92, 190, 30)
        self.upgrade_tab = pygame.Rect(self.rect.left + 220, self.rect.top + 92, 190, 30)
        self.storage_deposit_buttons = {}
        self.storage_withdraw_buttons = {}

    @property
    def unit(self):
        return building_config(self.building)["unit"]

    def _state(self):
        state = super()._state()
        storage = state.get("storage")
        if storage is not None:
            self.resources = tuple(
                resource for resource in building_resources(self.building) if resource in storage
            )
        return state

    def production_desc(self, level):
        return f"Вместимость каждого товара: {building_level_info(level, self.building)['storage']} {self.unit}"

    def handle_event(self, event):
        if self.contribution_dialog.is_open:
            result = self.contribution_dialog.handle_event(event)
            if result is not None:
                target, quantity = result
                if isinstance(target, tuple) and target[0] in ("storage", "storage_withdraw"):
                    action = "storage/withdraw" if target[0] == "storage_withdraw" else "storage/deposit"
                    self._request(action, {"resource": target[1], "quantity": quantity})
                else:
                    self.deposit_material(target, quantity)
            return
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                self.is_open = False
            return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        pos = event.pos
        if self.close_button.collidepoint(pos):
            self.is_open = False
        elif self.storage_tab.collidepoint(pos):
            self.tab = "storage"
        elif self.upgrade_tab.collidepoint(pos):
            self.tab = "upgrade"
            self.load()
        elif self.tab == "storage":
            for resource, button in self.storage_withdraw_buttons.items():
                if button.collidepoint(pos):
                    quantity = int(self._state().get("storage", {}).get(resource, 0))
                    withdrawable = self._state().get("storage_withdrawable", {}).get(resource, {})
                    self.contribution_dialog.open(
                        ("storage_withdraw", resource),
                        RESOURCES.get(resource, {}).get("label", resource),
                        quantity, withdrawable.get("max_withdraw", 0), mode="withdraw",
                        weight_state=withdrawable,
                        item_weight_kg=withdrawable.get("item_weight_kg", 0),
                    )
                    return
            for resource, button in self.storage_deposit_buttons.items():
                if button.collidepoint(pos):
                    depositable = self._state().get("storage_depositable", {}).get(resource, {})
                    self.contribution_dialog.open(
                        ("storage", resource),
                        RESOURCES.get(resource, {}).get("label", resource),
                        depositable.get("in_backpack", 0),
                        depositable.get("max_deposit", 0),
                        mode="deposit",
                    )
                    return
        elif self.tab == "upgrade":
            for item_id, button in self.deposit_buttons.items():
                if button.collidepoint(pos):
                    upgrade = self._state().get("upgrade") or {}
                    material = next((entry for entry in upgrade.get("materials", [])
                                     if entry["item_id"] == item_id), None)
                    if material:
                        self.contribution_dialog.open(
                            item_id,
                            material["name"],
                            material["in_warehouse"],
                            material["required"] - material["deposited"],
                        )
                    return
            if self.upgrade_button.collidepoint(pos):
                self.start_upgrade()

    def draw(self, screen):
        scene = self.scene
        self._refresh_if_due()
        overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 18, 215))
        screen.blit(overlay, (0, 0))
        rect = self.rect
        modal = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(modal, (24, 26, 18, 250), (0, 0, rect.width, rect.height), border_radius=12)
        pygame.draw.rect(modal, (220, 185, 70), (0, 0, rect.width, rect.height), width=2, border_radius=12)
        screen.blit(modal, rect.topleft)
        m_pos = pygame.mouse.get_pos()

        title = self.name if self.state else f"{self.name} (нет связи с сервером)"
        building_icon = draw_building_icon(screen, self.building, (rect.left + 14, rect.top + 9), 32)
        title_x = rect.left + 54 if building_icon else rect.left + 24
        screen.blit(scene.large_font.render(title, True, (255, 225, 130)), (title_x, rect.top + 16))
        screen.blit(scene.font.render(f"Уровень {self.level()}", True, (215, 205, 170)), (rect.left + 24, rect.top + 56))
        for tab, button, label in (("storage", self.storage_tab, "СКЛАД"), ("upgrade", self.upgrade_tab, "УЛУЧШЕНИЕ")):
            draw_button(screen, button, label, scene.small_font, color=(75, 120, 155) if self.tab == tab else (45, 50, 58))

        hover = self.close_button.collidepoint(m_pos)
        pygame.draw.rect(screen, (160, 45, 45) if hover else (45, 30, 35), self.close_button, border_radius=4)
        pygame.draw.rect(screen, (220, 100, 100), self.close_button, 1, border_radius=4)
        cross = self.close_button.inflate(-14, -14)
        pygame.draw.line(screen, (255, 255, 255), cross.topleft, cross.bottomright, 3)
        pygame.draw.line(screen, (255, 255, 255), cross.topright, cross.bottomleft, 3)
        if self.message:
            screen.blit(scene.small_font.render(self.message, True, (240, 150, 120)), (rect.left + 440, rect.top + 98))

        curr_y = rect.top + 136
        pygame.draw.line(screen, (100, 90, 55), (rect.left + 22, curr_y), (rect.right - 22, curr_y), 1)
        curr_y += 16
        if self.tab == "upgrade":
            self._draw_upgrade_tab(screen, curr_y, m_pos)
        else:
            self._draw_storage_tab(screen, curr_y)
        self.contribution_dialog.draw(screen)

    def _draw_storage_tab(self, screen, curr_y):
        """Таблица: слева товар, справа количество; в шапке — заполненность."""
        scene = self.scene
        storage = self._state().get("storage", {})
        depositable = self._state().get("storage_depositable", {})
        city_upgrade = self._state().get("city_upgrade", {})
        charging_resources = set(city_upgrade.get("charging_resources", []))
        limit = storage.get("limit", building_level_info(self.level(), self.building)["storage"])
        table = pygame.Rect(self.rect.left + 24, curr_y, self.rect.width - 48, 0)
        row_height = 36
        header = pygame.Rect(table.left, curr_y, table.width, 34)
        pygame.draw.rect(screen, (44, 46, 34), header)
        screen.blit(scene.font.render("Товары:", True, (255, 225, 130)), (header.left + 12, header.top + 6))
        curr_y = header.bottom
        self.storage_deposit_buttons = {}
        self.storage_withdraw_buttons = {}
        for index, resource in enumerate(self.resources):
            row = pygame.Rect(table.left, curr_y, table.width, row_height)
            pygame.draw.rect(screen, (32, 34, 26) if index % 2 else (38, 40, 30), row)
            draw_item_icon(screen, resource, (row.left + 12, row.top + 2), 32)
            screen.blit(scene.font.render(RESOURCES[resource]["label"], True, (215, 215, 205)), (row.left + 50, row.top + 8))
            amount = int(storage.get(resource, 0))
            amount_surface = scene.font.render(f"{amount} / {limit}", True, (235, 235, 225))
            amount_rect = amount_surface.get_rect(midright=(row.right - 230, row.centery))
            screen.blit(amount_surface, amount_rect)
            draw_storage_meter(
                screen, pygame.Rect(row.left + 260, row.centery - 9,
                                    max(1, amount_rect.left - row.left - 272), 18),
                amount, limit, resource in charging_resources,
            )
            available = depositable.get(resource, {})
            maximum = int(available.get("max_deposit", 0))
            if amount > 0:
                button = pygame.Rect(row.right - 220, row.top + 2, 96, row.height - 4)
                draw_button(screen, button, "ВЗЯТЬ", scene.small_font,
                            color=(69, 98, 72), text_color=(235, 245, 230))
                self.storage_withdraw_buttons[resource] = button
            if maximum > 0:
                button = pygame.Rect(row.right - 116, row.top + 2, 104, row.height - 4)
                draw_button(screen, button, "ВНЕСТИ", scene.small_font,
                            color=(68, 112, 60), text_color=(235, 245, 230))
                self.storage_deposit_buttons[resource] = button
            curr_y = row.bottom
        pygame.draw.rect(screen, (100, 90, 55), (table.left, header.top, table.width, curr_y - header.top), 1)
