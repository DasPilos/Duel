"""Каркас логистического меню Конюшни; расстояния и ресурсы берутся с сервера, расчёты рейсов пока пустые."""

import time
from copy import deepcopy

import pygame

from client.network import ServerError
from core.cart_progress import (
    CART_GRADES,
    CART_UPGRADE_NODES,
    DEFAULT_CART_PROGRESS,
    RESOURCE_ITEM_IDS,
    WAREHOUSE_RESOURCE_LABELS,
    cart_stats,
    grade_two_unlocked,
)
from core import settings
from core.currency import Currency
from core.production_buildings import BUILDINGS
from ui.catalog_icons import draw_building_icon, draw_item_icon
from ui.hud import draw_button
from ui.material_contribution_dialog import MaterialContributionDialog

RESOURCE_COLORS = {
    "wheat": (207, 173, 71), "berries": (154, 75, 135), "flax": (113, 153, 111),
    "cotton": (220, 220, 204), "wood": (130, 88, 52), "iron": (187, 117, 94),
    "stone": (164, 162, 149), "mithril": (111, 174, 202), "obsidian": (124, 85, 158),
    "leather": (155, 111, 72), "meat": (171, 75, 69), "coal": (63, 63, 67),
}
ROUTE_STORAGE_BUILDING_IDS = {"wheat_farm": "farm"}


def _format_duration(seconds):
    hours, remainder = divmod(max(0, int(seconds)), 3600)
    minutes = remainder // 60
    return f"{hours} ч {minutes:02d} мин" if hours else f"{minutes} мин"


class StableWindow:
    WIDTH = 1600
    HEIGHT = 900
    HEADER_HEIGHT = 152
    ROUTE_ROW_HEIGHT = 104
    REFRESH_SECONDS = 5

    def __init__(self, scene):
        self.scene = scene
        self.rect = pygame.Rect((settings.WIDTH - self.WIDTH) // 2, (settings.HEIGHT - self.HEIGHT) // 2,
                                self.WIDTH, self.HEIGHT)
        self.close_button = pygame.Rect(self.rect.right - 48, self.rect.top + 15, 30, 30)
        self.tabs = {
            "transport": pygame.Rect(self.rect.left + 24, self.rect.top + 104, 180, 32),
            "routes": pygame.Rect(self.rect.left + 212, self.rect.top + 104, 170, 32),
            "carts": pygame.Rect(self.rect.left + 390, self.rect.top + 104, 170, 32),
            "stalls": pygame.Rect(self.rect.left + 568, self.rect.top + 104, 150, 32),
            "upgrades": pygame.Rect(self.rect.left + 726, self.rect.top + 104, 180, 32),
        }
        self.tab = "transport"
        self.upgrade_tab = "transport"
        self.is_open = False
        self.routes = []
        self.route_state = None
        self.state = None
        self.inventory_state = None
        self.cart_progress = deepcopy(DEFAULT_CART_PROGRESS)
        self.selected_cart_node = "wheels"
        self.cart_grade_cards = {}
        self.cart_node_buttons = {}
        self.cart_purchase_buttons = {}
        self.cart_contribution_areas = {}
        self.cart_upgrade_button = pygame.Rect(0, 0, 230, 38)
        self.state_received_at = time.monotonic()
        self.last_state_refresh = 0.0
        self.selected_route = 0
        self.route_scroll = 0
        self.transport_scroll = 0
        self.stall_scroll = 0
        self.message = None
        self.transport_draft = {"cart_id": None, "horse_ids": [], "destination_id": None, "resource_ids": []}
        self.transport_popup = None
        self.transport_popup_rect = pygame.Rect(0, 0, 0, 0)
        self.transport_popup_options = {}
        self.transport_buttons = {}
        self.transport_start_button = pygame.Rect(0, 0, 240, 38)
        self.destination_state = None
        self.deposit_buttons = {}
        self.stall_upgrade_buttons = {}
        self.stall_contribution_buttons = {}
        self.contribution_dialog = MaterialContributionDialog(scene)
        self.source_picker = None
        self.source_picker_buttons = {}
        self.source_picker_cancel_button = pygame.Rect(0, 0, 112, 34)
        self.pending_contribution_source = None
        self.upgrade_button = pygame.Rect(0, 0, 220, 36)
        self.stall_buy_buttons = {}
        self.route_panel = pygame.Rect(self.rect.left + 24, self.rect.top + self.HEADER_HEIGHT,
                                       500, self.rect.height - self.HEADER_HEIGHT - 24)
        self.detail_panel = pygame.Rect(self.route_panel.right + 18, self.route_panel.top,
                                        self.rect.right - self.route_panel.right - 42, self.route_panel.height)
        self.stalls_panel = pygame.Rect(self.rect.left + 24, self.rect.top + self.HEADER_HEIGHT,
                        self.rect.width - 48, self.rect.height - self.HEADER_HEIGHT - 24)

    def open(self):
        self.is_open = True
        self.message = None
        try:
            self.state = self.scene.session.client.get_building(
                "stable", self.scene.session.character["id"]
            )
            self._sync_cart_progress()
            self.state_received_at = time.monotonic()
            self.last_state_refresh = self.state_received_at
        except (ServerError, AttributeError, KeyError, OSError) as error:
            self.state = None
            self.message = str(error)
        try:
            terrain = self.scene.session.client.get_map_terrain()
            self.routes = terrain.get("roads", {}).get("routes", [])
            if self.selected_route >= len(self.routes):
                self.selected_route = 0
            self._load_selected_route_state()
        except (ServerError, AttributeError, KeyError, OSError) as error:
            self.routes = []
            self.message = self.message or str(error)
        self._load_player_inventory()

    def _load_player_inventory(self):
        try:
            self.inventory_state = self.scene.session.client.get_inventory(
                self.scene.session.character["id"]
            )
            self.scene.session.character["carried_weight_kg"] = float(
                self.inventory_state.get("carried_weight_kg", 0)
            )
        except (ServerError, AttributeError, KeyError, OSError) as error:
            self.inventory_state = None
            self.message = self.message or str(error)

    def _sync_cart_progress(self):
        server_progress = (self.state or {}).get("cart_progress")
        if not server_progress:
            return
        selected_grade = self.cart_progress.get("selected_grade", 1)
        self.cart_progress = deepcopy(server_progress)
        self.cart_progress["selected_grade"] = selected_grade

    def handle_event(self, event):
        if self.source_picker is not None:
            self._handle_source_picker_event(event)
            return
        if self.contribution_dialog.is_open:
            result = self.contribution_dialog.handle_event(event)
            if result is not None:
                target, quantity = result
                source = self.pending_contribution_source or "warehouse"
                self.pending_contribution_source = None
                if isinstance(target, tuple):
                    upgrade_id, resource = target
                    if upgrade_id == "cart_grade_1":
                        self._building_action("cart/contribute", {
                            "resource": resource, "quantity": quantity, "source": source,
                        })
                        return
                    self._building_action("stall-upgrade/contribute", {
                        "upgrade_id": upgrade_id, "resource": resource,
                        "quantity": quantity, "source": source,
                    })
                else:
                    self._building_action("upgrade/deposit", {
                        "item_id": target, "quantity": quantity, "source": source,
                    })
            return
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
            if self.transport_popup is not None:
                self.transport_popup = None
                return
            self.is_open = False
            return
        if event.type == pygame.MOUSEWHEEL and self.is_open:
            if self.tab == "routes" and self.route_panel.collidepoint(pygame.mouse.get_pos()):
                self.route_scroll = max(0, min(max(0, len(self.routes) - 1), self.route_scroll - event.y))
            elif self.tab == "stalls" and self.stalls_panel.collidepoint(pygame.mouse.get_pos()):
                capacity = (self.state or {}).get("stall_capacity", 4)
                self.stall_scroll = max(0, min(max(0, capacity - 1), self.stall_scroll - event.y))
            elif self.tab == "transport":
                self.transport_scroll = max(0, self.transport_scroll - event.y)
            return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if self.tab == "transport" and self.transport_popup is not None:
            if not self.transport_popup_rect.collidepoint(event.pos):
                self.transport_popup = None
                return
            for option, button in self.transport_popup_options.items():
                if button.collidepoint(event.pos):
                    self._select_transport_option(option)
                    return
            return
        if self.close_button.collidepoint(event.pos):
            self.is_open = False
            return
        for key, rect in self.tabs.items():
            if rect.collidepoint(event.pos):
                self.tab = key
                return
        if self.tab == "transport":
            for field, button in self.transport_buttons.items():
                if button.collidepoint(event.pos):
                    self.transport_popup = field
                    return
            if self.transport_start_button.collidepoint(event.pos) and self._transport_can_start():
                self.message = "Серверная отправка транспортных рейсов ещё не подключена."
                return
        if self.tab == "routes":
            for index, rect in enumerate(self._route_row_rects()):
                if rect.collidepoint(event.pos):
                    self.selected_route = self.route_scroll + index
                    self._load_selected_route_state()
                    return
        elif self.tab == "upgrades":
            for key, rect in self._upgrade_subtabs().items():
                if rect.collidepoint(event.pos):
                    self.upgrade_tab = key
                    return
        if self.tab == "upgrades":
            if self.upgrade_tab == "transport":
                for node_id, button in self.cart_node_buttons.items():
                    if button.collidepoint(event.pos):
                        self.selected_cart_node = node_id
                        return
            elif self.upgrade_tab == "stalls":
                for (upgrade_id, resource), button in self.stall_contribution_buttons.items():
                    if button.collidepoint(event.pos):
                        upgrade = (self.state or {}).get("stall_upgrades", {}).get(upgrade_id, {})
                        is_wood = resource == "wood"
                        remaining = (upgrade.get("wood_cost", 0) - upgrade.get("wood_deposited", 0)
                                     if is_wood else
                                     upgrade.get("silver_cost", 0) - upgrade.get("silver_deposited", 0))
                        sources = (
                            [{"source": "warehouse", "label": "Склад",
                              "available": upgrade.get("wood_in_warehouse", 0)},
                             {"source": "backpack", "label": "Рюкзак",
                              "available": upgrade.get("wood_in_backpack", 0)}]
                            if is_wood else
                            [{"source": "treasury", "label": "Казна",
                              "available": upgrade.get("treasury_silver_available", 0)},
                             {"source": "wallet", "label": "Кошелёк",
                              "available": upgrade.get("silver_available", 0)}]
                        )
                        self._open_source_picker(
                            (upgrade_id, resource), "Древесина" if is_wood else "Серебро",
                            remaining, sources,
                        )
                        return
                for upgrade_id, button in self.stall_upgrade_buttons.items():
                    if button.collidepoint(event.pos):
                        self._building_action(
                            "stall-upgrade/purchase", {"upgrade_id": upgrade_id}
                        )
                        return
            for item_id, button in self.deposit_buttons.items():
                if button.collidepoint(event.pos):
                    upgrade = (self.state or {}).get("upgrade") or {}
                    material = next((item for item in upgrade.get("materials", [])
                                     if item["item_id"] == item_id), None)
                    if material:
                        self._open_source_picker(
                            item_id, material["name"], material["required"] - material["deposited"],
                            [{"source": "warehouse", "label": "Склад",
                              "available": material.get("in_warehouse", 0)},
                             {"source": "backpack", "label": "Рюкзак",
                              "available": material.get("in_backpack", 0)}],
                        )
                    return
            if self.upgrade_tab == "building" and self.upgrade_button.collidepoint(event.pos):
                self._building_action("upgrade/start", {})
        elif self.tab == "stalls":
            for slot_index, button in self.stall_buy_buttons.items():
                if button.collidepoint(event.pos):
                    self._building_action("horse/purchase", {"slot_index": slot_index})
                    return
        elif self.tab == "carts":
            for resource, area in self.cart_contribution_areas.items():
                if area.collidepoint(event.pos):
                    g1 = self.cart_progress["grades"]["1"]
                    if resource == "wood":
                        wood_needed = max(0, 100 - g1.get("wood_deposited", 0))
                        wood_available = (self.state or {}).get("warehouse_storage", {}).get("wood", 0)
                        wood_backpack = (self.state or {}).get("backpack_resource_amounts", {}).get("wood", 0)
                        if wood_needed > 0:
                            self._open_source_picker(
                                ("cart_grade_1", "wood"), "Древесина", wood_needed,
                                [{"source": "warehouse", "label": "Склад", "available": wood_available},
                                 {"source": "backpack", "label": "Рюкзак", "available": wood_backpack}],
                            )
                        elif wood_needed <= 0:
                            self.message = "Древесина для повозки уже полностью внесена (100/100)!"
                        else:
                            self.message = "В вашем рюкзаке нет древесины для внесения."
                    elif resource == "silver":
                        silver_needed = max(0, 20 - g1.get("silver_deposited", 0))
                        silver_avail = (self.state or {}).get("silver_available", 0)
                        treasury_avail = (self.state or {}).get("treasury_silver_available", 0)
                        if silver_needed > 0:
                            self._open_source_picker(
                                ("cart_grade_1", "silver"), "Серебро", silver_needed,
                                [{"source": "treasury", "label": "Казна", "available": treasury_avail},
                                 {"source": "wallet", "label": "Кошелёк", "available": silver_avail}],
                            )
                        elif silver_needed <= 0:
                            self.message = "Серебро для повозки уже полностью внесено (20/20)!"
                        else:
                            self.message = "У вас нет серебра для внесения."
                    return
            for grade, button in self.cart_purchase_buttons.items():
                if button.collidepoint(event.pos):
                    if grade == 1:
                        g1 = self.cart_progress["grades"]["1"]
                        wood_dep = g1.get("wood_deposited", 0)
                        silver_dep = g1.get("silver_deposited", 0)
                        wood_cost = CART_GRADES["1"].get("wood_cost", 100)
                        silver_cost = CART_GRADES["1"].get("silver_cost", 20)
                        if wood_dep >= wood_cost and silver_dep >= silver_cost:
                            self._building_action("cart/purchase", {"grade": grade})
                        else:
                            wood_needed = max(0, wood_cost - wood_dep)
                            silver_needed = max(0, silver_cost - silver_dep)
                            wood_available = (self.state or {}).get("warehouse_storage", {}).get("wood", 0)
                            wood_backpack = (self.state or {}).get("backpack_resource_amounts", {}).get("wood", 0)
                            silver_avail = (self.state or {}).get("silver_available", 0)
                            treasury_avail = (self.state or {}).get("treasury_silver_available", 0)
                            if wood_needed > 0:
                                self._open_source_picker(
                                    ("cart_grade_1", "wood"), "Древесина", wood_needed,
                                    [{"source": "warehouse", "label": "Склад", "available": wood_available},
                                     {"source": "backpack", "label": "Рюкзак", "available": wood_backpack}],
                                )
                            elif silver_needed > 0:
                                self._open_source_picker(
                                    ("cart_grade_1", "silver"), "Серебро", silver_needed,
                                    [{"source": "treasury", "label": "Казна", "available": treasury_avail},
                                     {"source": "wallet", "label": "Кошелёк", "available": silver_avail}],
                                )
                            else:
                                self.message = f"Недостаточно материалов: требуется Древесина ({wood_dep}/{wood_cost}) и Серебро ({silver_dep}/{silver_cost})."
                    else:
                        self.message = "Стоимость чертежа в Инженерной палате ещё не задана."
                    return
            for grade, button in self.cart_grade_cards.items():
                if button.collidepoint(event.pos):
                    if grade == 1 or grade_two_unlocked(self.cart_progress):
                        self.cart_progress["selected_grade"] = grade
                    return

    def _building_action(self, action, payload):
        try:
            self.state = self.scene.session.client.building_action(
                "stable", self.scene.session.character["id"], action, payload
            )
            self._sync_cart_progress()
            self.state_received_at = time.monotonic()
            self.message = None
            if action == "cart/contribute":
                self.message = "Взнос внесён со склада." if payload.get("resource") == "wood" else "Серебро внесено."
        except (ServerError, AttributeError, KeyError, OSError) as error:
            self.message = str(error)

    def _open_source_picker(self, target, label, remaining, sources):
        self.source_picker = {
            "target": target,
            "label": str(label),
            "remaining": max(0, int(remaining)),
            "sources": sources,
        }
        self.source_picker_buttons = {}

    def _handle_source_picker_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.source_picker = None
            self.source_picker_buttons = {}
            return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if self.source_picker_cancel_button.collidepoint(event.pos):
            self.source_picker = None
            self.source_picker_buttons = {}
            return
        for source, button in self.source_picker_buttons.items():
            if not button.collidepoint(event.pos):
                continue
            option = next(item for item in self.source_picker["sources"]
                          if item["source"] == source)
            if int(option["available"]) <= 0:
                self.message = f"В источнике «{option['label']}» ресурса нет."
                return
            picker = self.source_picker
            self.pending_contribution_source = source
            self.contribution_dialog.open(
                picker["target"], picker["label"], option["available"],
                picker["remaining"], mode="contribute",
            )
            self.source_picker = None
            self.source_picker_buttons = {}
            return
        self.source_picker = None
        self.source_picker_buttons = {}

    def _draw_source_picker(self, screen):
        picker = self.source_picker
        if picker is None:
            self.source_picker_buttons = {}
            return
        scene = self.scene
        shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 155))
        screen.blit(shade, (0, 0))
        panel = pygame.Rect(0, 0, 610, 220)
        panel.center = (screen.get_width() // 2, screen.get_height() // 2)
        pygame.draw.rect(screen, (31, 34, 30), panel, border_radius=6)
        pygame.draw.rect(screen, (174, 145, 91), panel, 2, border_radius=6)
        title = scene.font.render(f"Источник: {picker['label']}", True, (226, 210, 177))
        screen.blit(title, (panel.left + 22, panel.top + 18))
        self.source_picker_buttons = {}
        for index, option in enumerate(picker["sources"]):
            button = pygame.Rect(panel.left + 22 + index * 286, panel.top + 72, 270, 62)
            available = int(option["available"])
            label = f"{option['label']}: {available} / {picker['remaining']}"
            color = (62, 91, 61) if available else (48, 50, 46)
            draw_button(screen, button, label, scene.small_font, color=color,
                        hover_color=(82, 118, 76))
            self.source_picker_buttons[option["source"]] = button
        self.source_picker_cancel_button = pygame.Rect(panel.right - 132, panel.bottom - 48, 110, 32)
        draw_button(screen, self.source_picker_cancel_button, "ОТМЕНА", scene.small_font,
                    color=(67, 56, 48), hover_color=(104, 69, 56))

    def _load_selected_route_state(self):
        if not self.routes or not 0 <= self.selected_route < len(self.routes):
            self.route_state = None
            return
        route = self.routes[self.selected_route]
        building = ROUTE_STORAGE_BUILDING_IDS.get(route["building_id"], route["building_id"])
        try:
            self.route_state = self.scene.session.client.get_building(
                building, self.scene.session.character["id"]
            )
            self.message = None
        except (ServerError, AttributeError, KeyError, OSError) as error:
            self.route_state = None
            self.message = str(error)

    def draw(self, screen):
        if self.is_open and time.monotonic() - self.last_state_refresh >= self.REFRESH_SECONDS:
            try:
                self.state = self.scene.session.client.get_building(
                    "stable", self.scene.session.character["id"]
                )
                self._sync_cart_progress()
                self.state_received_at = time.monotonic()
                self.last_state_refresh = self.state_received_at
                if self.tab == "upgrades" and self.upgrade_tab == "transport":
                    self._load_player_inventory()
                elif self.tab == "routes":
                    self._load_selected_route_state()
            except (ServerError, AttributeError, KeyError, OSError) as error:
                self.message = str(error)
            else:
                self._sync_cart_progress()
        scene = self.scene
        rect = self.rect
        overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        overlay.fill((7, 10, 14, 218))
        screen.blit(overlay, (0, 0))
        modal = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(modal, (25, 27, 25, 252), (0, 0, rect.width, rect.height), border_radius=8)
        pygame.draw.rect(modal, (191, 155, 91), (0, 0, rect.width, rect.height), 2, border_radius=8)
        screen.blit(modal, rect.topleft)

        scene_title = scene.large_font.render("Конюшня", True, (239, 218, 176))
        draw_building_icon(screen, "stable_building", (rect.left + 18, rect.top + 7), 40)
        screen.blit(scene_title, (rect.left + 66, rect.top + 18))
        level = self.state["level"] if self.state else 1
        level_title = scene.font.render(f"Уровень {level}", True, (208, 196, 166))
        screen.blit(level_title, (rect.left + 28, rect.top + 61))

        for key, label in (("transport", "ТРАНСПОРТ"), ("routes", "МАРШРУТЫ"),
                   ("carts", "ПОВОЗКИ"), ("stalls", "СТОЙЛО"),
                   ("upgrades", "УЛУЧШЕНИЯ")):
            draw_button(screen, self.tabs[key], label, scene.small_font,
                        color=(105, 91, 64) if self.tab == key else (48, 51, 48))

        cross = self.close_button.inflate(-14, -14)
        pygame.draw.rect(screen, (48, 38, 34), self.close_button, border_radius=4)
        pygame.draw.rect(screen, (185, 111, 88), self.close_button, 1, border_radius=4)
        pygame.draw.line(screen, (239, 229, 213), cross.topleft, cross.bottomright, 2)
        pygame.draw.line(screen, (239, 229, 213), cross.topright, cross.bottomleft, 2)
        pygame.draw.line(screen, (98, 91, 75), (rect.left + 20, rect.top + self.HEADER_HEIGHT - 1),
                         (rect.right - 20, rect.top + self.HEADER_HEIGHT - 1), 1)
        if self.message:
            screen.blit(scene.small_font.render(self.message, True, (232, 130, 110)),
                        (self.close_button.left - 340, self.close_button.top + 6))

        if self.tab == "transport":
            self._draw_transport(screen)
        elif self.tab == "carts":
            self._draw_carts(screen)
        elif self.tab == "routes":
            self._draw_routes(screen)
        elif self.tab == "upgrades":
            self._draw_upgrades(screen)
        else:
            self._draw_stalls(screen)
        self.contribution_dialog.draw(screen)
        self._draw_source_picker(screen)

    def _draw_stalls(self, screen):
        """Список стойл ограничен вместимостью, которую прислал сервер."""
        panel = self.stalls_panel
        self._panel(screen, panel, "Стойла")
        capacity = (self.state or {}).get("stall_capacity", 4)
        level = (self.state or {}).get("level", 1)
        occupied = (self.state or {}).get("occupied_stalls", 0)
        summary_color = (231, 112, 94) if occupied >= capacity else (229, 215, 183)
        summary = self.scene.font.render(f"Стойла: занято {occupied} / {capacity} мест",
                                         True, summary_color)
        screen.blit(summary, (panel.left + 14, panel.top + 45))
        feed_rate = (self.state or {}).get("feed_consumption_kg_per_hour", 0)
        feed_label = (self.state or {}).get("feed_resource_label", "Пшеница")
        feed_resource_id = RESOURCE_ITEM_IDS.get((self.state or {}).get("feed_resource", "wheat"))
        draw_item_icon(screen, feed_resource_id, (panel.left + 14, panel.top + 68), 22)
        feed = self.scene.small_font.render(f"Расход корма: -{feed_rate} кг {feed_label} / час",
                                            True, (201, 192, 166))
        screen.blit(feed, (panel.left + 42, panel.top + 70))

        table = pygame.Rect(panel.left + 12, panel.top + 104, panel.width - 24, panel.height - 118)
        row_height = 58
        y = self._table_header(screen, table, table.top, (
            ("№", table.left + 12, "left"),
            ("Лошадь / кличка / порода", table.left + 80, "left"),
            ("Статус", table.left + 680, "left"),
            ("Действие", table.right - 14, "right"),
        ))
        rows_top = y
        visible = max(1, (table.bottom - rows_top) // row_height)
        slots = (self.state or {}).get("stall_slots", [])
        self.stall_buy_buttons = {}
        for index in range(self.stall_scroll, min(len(slots), self.stall_scroll + visible)):
            slot = slots[index]
            row = pygame.Rect(table.left + 1, y, table.width - 2, row_height)
            pygame.draw.rect(screen, (41, 43, 37) if index % 2 == 0 else (35, 38, 33), row)
            if not slot["unlocked"]:
                shackle = pygame.Rect(row.left + 15, row.top + 14, 13, 13)
                pygame.draw.arc(screen, (150, 145, 130), shackle, 0, 3.14, 2)
                pygame.draw.rect(screen, (150, 145, 130), (row.left + 12, row.top + 23, 19, 15), border_radius=2)
                locked = self.scene.small_font.render(
                    f"Доступно на {slot['unlock_level']} уровне Конюшни", True, (150, 145, 130)
                )
                screen.blit(locked, (row.left + 80, row.top + 18))
            else:
                screen.blit(self.scene.small_font.render(f"{index + 1:02d}", True, (198, 191, 172)),
                            (row.left + 12, row.top + 18))
                horse = slot.get("horse")
                if horse:
                    pygame.draw.ellipse(screen, (142, 101, 67), (row.left + 86, row.top + 18, 28, 15))
                    horse_name = self.scene.small_font.render(
                        f"{horse.get('name', 'Без клички')} / {horse.get('breed', 'Порода не указана')}",
                        True, (211, 197, 169),
                    )
                    screen.blit(horse_name, (row.left + 126, row.top + 18))
                    status_text = horse.get("status", "Отдыхает")
                    color = (154, 187, 138)
                else:
                    horse_name = self.scene.small_font.render("Пустое стойло", True, (156, 153, 140))
                    screen.blit(horse_name, (row.left + 80, row.top + 18))
                    status_text = "Свободно"
                    color = (148, 166, 137)
                status = self.scene.small_font.render(status_text, True, color)
                screen.blit(status, (row.left + 680, row.top + 18))
                purchase_area = pygame.Rect(row.right - 204, row.top + 12, 190, 34)
                price = (self.state or {}).get("horse_price_next_silver", 50)
                silver = (self.state or {}).get("silver_available", 0)
                can_afford = silver >= price
                button_color = (78, 62, 48) if horse else (59, 92, 53) if can_afford else (47, 48, 44)
                text_color = (220, 195, 165) if horse else (220, 215, 190) if can_afford else (135, 137, 128)
                label = "ПРОДАТЬ ЛОШАДЬ" if horse else ""
                button = (purchase_area.copy() if horse else
                          pygame.Rect(purchase_area.left, purchase_area.top, 82, purchase_area.height))
                draw_button(screen, button, label or "КУПИТЬ", self.scene.small_font,
                            color=button_color, text_color=text_color)
                if not horse:
                    price_badge = pygame.Rect(button.right + 5, purchase_area.top,
                                              purchase_area.right - button.right - 5,
                                              purchase_area.height)
                    pygame.draw.rect(screen, (43, 45, 39), price_badge, border_radius=6)
                    pygame.draw.rect(screen, (83, 82, 68), price_badge, 1, border_radius=6)
                    price_surface = self.scene.small_font.render(str(price), True, text_color)
                    icon_size = 22
                    content_width = icon_size + 5 + price_surface.get_width()
                    content_left = price_badge.centerx - content_width // 2
                    draw_item_icon(
                        screen, "silver",
                        (content_left, price_badge.centery - icon_size // 2),
                        icon_size,
                    )
                    screen.blit(
                        price_surface,
                        price_surface.get_rect(midleft=(content_left + icon_size + 5, price_badge.centery)),
                    )
                if not horse and can_afford:
                    self.stall_buy_buttons[slot["slot_index"]] = button
            y += row_height
        pygame.draw.rect(screen, (78, 77, 65), table, 1)

    def _panel(self, screen, rect, title):
        scene = self.scene
        pygame.draw.rect(screen, (31, 34, 30), rect, border_radius=4)
        pygame.draw.rect(screen, (80, 78, 64), rect, 1, border_radius=4)
        screen.blit(scene.font.render(title, True, (222, 204, 166)), (rect.left + 14, rect.top + 12))

    def _table_header(self, screen, rect, y, columns):
        scene = self.scene
        header = pygame.Rect(rect.left + 12, y, rect.width - 24, 32)
        pygame.draw.rect(screen, (52, 53, 45), header)
        for text, x, align in columns:
            label = scene.small_font.render(text, True, (205, 193, 164))
            target = label.get_rect(midleft=(x, header.centery)) if align == "left" else label.get_rect(midright=(x, header.centery))
            screen.blit(label, target)
        return header.bottom

    def _available_transport_carts(self):
        return (self.state or {}).get("available_carts", [])

    def _available_transport_horses(self):
        return [slot["horse"] for slot in (self.state or {}).get("stall_slots", [])
                if slot.get("unlocked") and slot.get("horse")]

    def _selected_transport_cart(self):
        cart_id = self.transport_draft["cart_id"]
        return next((cart for cart in self._available_transport_carts()
                     if cart.get("id") == cart_id), None)

    def _selected_transport_route(self):
        route_id = self.transport_draft["destination_id"]
        return next((route for route in self.routes if route.get("building_id") == route_id), None)

    def _transport_popup_items(self):
        kind, slot_index = self.transport_popup
        if kind == "cart":
            return [(cart["id"], cart.get("name", "Повозка"))
                    for cart in self._available_transport_carts()]
        if kind == "horse":
            selected = set(self.transport_draft["horse_ids"])
            return [(horse["id"], horse.get("name", "Лошадь"))
                    for horse in self._available_transport_horses()
                    if horse.get("id") not in selected]
        if kind == "destination":
            return [(route["building_id"], route["name"]) for route in self.routes]
        route = self._selected_transport_route() or {}
        return [(resource["id"], resource["label"]) for resource in route.get("resources", [])]

    def _select_transport_option(self, option):
        kind, slot_index, value = option
        if kind == "cart":
            cart = next((item for item in self._available_transport_carts()
                         if item.get("id") == value), None)
            self.transport_draft = {
                "cart_id": value,
                "horse_ids": [None] * max(0, int((cart or {}).get("horse_slots", 0))),
                "destination_id": None,
                "resource_ids": [],
            }
            self.destination_state = None
        elif kind == "horse":
            self.transport_draft["horse_ids"][slot_index] = value
        elif kind == "destination":
            self.transport_draft["destination_id"] = value
            route = self._selected_transport_route()
            resource_slots = max(0, int((self._selected_transport_cart() or {}).get("resource_slots", 1)))
            self.transport_draft["resource_ids"] = [None] * resource_slots
            self.destination_state = None
            if route:
                try:
                    self.destination_state = self.scene.session.client.get_building(
                        route["building_id"], self.scene.session.character["id"]
                    )
                except (ServerError, AttributeError, KeyError, OSError) as error:
                    self.message = str(error)
        elif kind == "resource":
            self.transport_draft["resource_ids"][slot_index] = value
        self.transport_popup = None

    def _transport_can_start(self):
        cart = self._selected_transport_cart()
        if not cart or not cart.get("can_travel", False):
            return False
        horse_ids = self.transport_draft["horse_ids"]
        horses = self._available_transport_horses()
        selected_horses = [next((horse for horse in horses if horse.get("id") == horse_id), None)
                           for horse_id in horse_ids]
        if not horse_ids or any(not horse or not horse.get("can_travel", False) for horse in selected_horses):
            return False
        if not self._selected_transport_route():
            return False
        resource_ids = self.transport_draft["resource_ids"]
        return bool(resource_ids) and all(resource_id is not None for resource_id in resource_ids)

    def _draw_transport_popup(self, screen, builder):
        if self.transport_popup is None:
            self.transport_popup_options = {}
            return
        scene = self.scene
        kind, slot_index = self.transport_popup
        items = self._transport_popup_items()
        popup = pygame.Rect(0, 0, 470, min(380, 138 + 46 * len(items)))
        popup.center = builder.center
        self.transport_popup_rect = popup
        shade = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 145))
        screen.blit(shade, (0, 0))
        pygame.draw.rect(screen, (31, 34, 30), popup, border_radius=5)
        pygame.draw.rect(screen, (174, 145, 91), popup, 2, border_radius=5)
        title = {"cart": "Выбор повозки", "horse": "Выбор лошади",
                 "destination": "Пункт назначения", "resource": "Ресурс для погрузки"}[kind]
        screen.blit(scene.font.render(title, True, (226, 210, 177)), (popup.left + 18, popup.top + 16))
        self.transport_popup_options = {}
        if not items:
            message = ("У вас нет свободного транспорта" if kind == "cart"
                       else "У вас нет свободных лошадей" if kind == "horse"
                       else "Нет доступных вариантов")
            label = scene.small_font.render(message, True, (188, 181, 163))
            screen.blit(label, label.get_rect(center=(popup.centerx, popup.centery + 12)))
            return
        for index, (value, label) in enumerate(items[:5]):
            button = pygame.Rect(popup.left + 14, popup.top + 54 + index * 46, popup.width - 28, 38)
            draw_button(screen, button, label, scene.small_font, color=(48, 51, 44))
            self.transport_popup_options[(kind, slot_index, value)] = button

    def _draw_transport(self, screen):
        scene = self.scene
        panel = pygame.Rect(self.rect.left + 24, self.rect.top + self.HEADER_HEIGHT + 18,
                            self.rect.width - 48, self.rect.height - self.HEADER_HEIGHT - 42)
        self._panel(screen, panel, "Транспортные рейсы")
        carts = self._available_transport_carts()
        convoys = (self.state or {}).get("transport_convoys", [])
        traveling = [convoy for convoy in convoys if convoy.get("status") == "В пути"]
        summary_y = panel.top + 44
        summary_width = (panel.width - 36) // 3
        summary_labels = (
            f"Повозок всего: {len(carts)}",
            f"Свободно: {sum(1 for cart in carts if cart.get('status') == 'Свободна')}",
            f"В пути: {len(traveling)}",
        )
        for index, label in enumerate(summary_labels):
            cell = pygame.Rect(panel.left + 12 + index * summary_width, summary_y, summary_width - 8, 38)
            pygame.draw.rect(screen, (39, 42, 37), cell)
            pygame.draw.rect(screen, (75, 77, 65), cell, 1)
            text = scene.font.render(label, True, (220, 213, 192))
            screen.blit(text, text.get_rect(center=cell.center))

        table = pygame.Rect(panel.left + 12, summary_y + 46, panel.width - 24, 232)
        y = self._table_header(screen, table, table.top, (
            ("Повозка / маршрут", table.left + 12, "left"), ("Груз", table.left + 430, "left"),
            ("Лошади: сытость", table.left + 760, "left"), ("Прогресс", table.left + 1080, "left"),
            ("Осталось", table.right - 14, "right"),
        ))
        if not convoys:
            empty = scene.small_font.render("Сейчас нет повозок в пути", True, (151, 150, 136))
            screen.blit(empty, empty.get_rect(center=(table.centerx, y + 72)))
        else:
            for index, convoy in enumerate(convoys[:4]):
                row = pygame.Rect(table.left + 1, y, table.width - 2, 43)
                pygame.draw.rect(screen, (41, 43, 37) if index % 2 == 0 else (35, 38, 33), row)
                satiety = ", ".join(str(horse.get("satiety", "—"))
                                    for horse in convoy.get("horses", [])) or "—"
                values = (
                    f"{convoy.get('cart_name', 'Повозка')} / {convoy.get('destination_name', '—')}",
                    f"{convoy.get('cargo_kg', '—')} / {convoy.get('capacity_kg', '—')} кг",
                    satiety,
                    f"{convoy.get('progress_percent', '—')}%",
                    _format_duration(convoy["seconds_remaining"])
                    if convoy.get("seconds_remaining") is not None else "—",
                )
                positions = (row.left + 12, row.left + 430, row.left + 760,
                             row.left + 1080, row.right - 14)
                for column, (value, x) in enumerate(zip(values, positions)):
                    label = scene.small_font.render(str(value), True, (205, 199, 182))
                    target = label.get_rect(midleft=(x, row.centery)) if column < 4 else label.get_rect(midright=(x, row.centery))
                    screen.blit(label, target)
                y += row.height
        pygame.draw.rect(screen, (78, 77, 65), table, 1)

        builder = pygame.Rect(panel.left + 12, table.bottom + 12, panel.width - 24,
                              panel.bottom - table.bottom - 24)
        self._panel(screen, builder, "Собрать экипаж")
        self.transport_buttons = {}
        cart = self._selected_transport_cart()
        route = self._selected_transport_route()
        button_y = builder.top + 48

        cart_button = pygame.Rect(builder.left + 12, button_y, 260, 38)
        draw_button(screen, cart_button, cart.get("name", "Выбрать повозку") if cart else "Выбрать повозку",
                    scene.small_font, color=(67, 64, 50) if carts else (45, 47, 42),
                    text_color=(224, 211, 178) if carts else (151, 150, 138))
        self.transport_buttons[("cart", None)] = cart_button

        destination_button = pygame.Rect(builder.left + 290, button_y, 300, 38)
        draw_button(screen, destination_button,
                    route.get("name", "Выбрать пункт назначения") if route else "Выбрать пункт назначения",
                    scene.small_font, color=(67, 64, 50) if cart else (45, 47, 42),
                    text_color=(224, 211, 178) if cart else (151, 150, 138))
        self.transport_buttons[("destination", None)] = destination_button

        horses = self._available_transport_horses()
        for slot_index, horse_id in enumerate(self.transport_draft["horse_ids"]):
            horse = next((item for item in horses if item.get("id") == horse_id), None)
            x = builder.left + 12 + (slot_index % 2) * 132
            y = button_y + 48 + (slot_index // 2) * 35
            button = pygame.Rect(x, y, 122, 31)
            label = horse.get("name", "Выбрать лошадь") if horse else f"Лошадь {slot_index + 1}: выбрать"
            draw_button(screen, button, label, scene.small_font,
                        color=(67, 64, 50) if horses else (45, 47, 42),
                        text_color=(224, 211, 178) if horses else (151, 150, 138))
            self.transport_buttons[("horse", slot_index)] = button

        if route and cart:
            labels = {item["id"]: item["label"] for item in route.get("resources", [])}
            for slot_index, resource_id in enumerate(self.transport_draft["resource_ids"]):
                x = destination_button.left + (slot_index % 2) * 152
                y = button_y + 48 + (slot_index // 2) * 35
                button = pygame.Rect(x, y, 144, 31)
                label = labels.get(resource_id, f"Ресурс {slot_index + 1}: выбрать")
                draw_button(screen, button, label, scene.small_font, color=(67, 64, 50))
                self.transport_buttons[("resource", slot_index)] = button

        summary_x = builder.left + 620
        summary_y = button_y + 2
        if cart and route:
            distance_text = f"Маршрут: {route['distance_tiles']:.2f} тайла"
            seconds_per_tile = cart.get("seconds_per_tile")
            time_text = (f"В пути без груза: {_format_duration(route['distance_tiles'] * seconds_per_tile)}"
                         if seconds_per_tile is not None else "Время пути: —")
        else:
            distance_text, time_text = "Маршрут: не выбран", "Время пути: —"
        capacity_text = f"Грузоподъёмность: {cart.get('capacity_kg', '—') if cart else '—'} кг"
        for index, text in enumerate((capacity_text, distance_text, time_text)):
            screen.blit(scene.small_font.render(text, True, (195, 189, 170)),
                        (summary_x, summary_y + index * 28))

        ready = self._transport_can_start()
        self.transport_start_button.topleft = (builder.right - 264, builder.bottom - 48)
        draw_button(screen, self.transport_start_button, "ОТПРАВИТЬ В РЕЙС", scene.small_font,
                    color=(68, 132, 76) if ready else (48, 52, 46),
                    text_color=(239, 245, 226) if ready else (143, 145, 134))
        self._draw_transport_popup(screen, builder)

    def _draw_carts(self, screen):
        scene = self.scene
        left = pygame.Rect(self.rect.left + 24, self.rect.top + self.HEADER_HEIGHT + 18,
                           430, self.rect.height - self.HEADER_HEIGHT - 42)
        right = pygame.Rect(left.right + 18, left.top, self.rect.right - left.right - 42, left.height)
        self._panel(screen, left, "Повозки к покупке")
        self._panel(screen, right, "Характеристики")

        progress = self.cart_progress
        grade_one = progress["grades"]["1"]
        grade_two_ready = grade_two_unlocked(progress)
        self.cart_grade_cards = {}
        self.cart_purchase_buttons = {}
        self.cart_contribution_areas = {}
        for grade, y in ((1, left.top + 48), (2, left.top + 276)):
            config = CART_GRADES[str(grade)]
            card = pygame.Rect(left.left + 10, y, left.width - 20, 210)
            locked = grade == 2 and not grade_two_ready
            active = progress["selected_grade"] == grade
            pygame.draw.rect(screen, (52, 48, 38) if active else (39, 42, 37), card)
            pygame.draw.rect(screen, (161, 132, 81) if active else (76, 76, 64), card, 1)
            title = scene.font.render(config["name"], True,
                                      (225, 211, 179) if not locked else (137, 137, 128))
            screen.blit(title, (card.left + 14, card.top + 14))
            if grade == 1:
                req_text = "требование: уровень конюшни 1"
                screen.blit(scene.small_font.render(req_text, True, (191, 185, 166)),
                            (card.left + 14, card.top + 46))

                wood_deposited = grade_one.get("wood_deposited", 0)
                wood_cost = config.get("wood_cost", 100)
                silver_deposited = grade_one.get("silver_deposited", 0)
                silver_cost = config.get("silver_cost", 20)
                wood_sources_available = (
                    int((self.state or {}).get("warehouse_storage", {}).get("wood", 0))
                    + int((self.state or {}).get("backpack_resource_amounts", {}).get("wood", 0))
                )
                silver_sources_available = (
                    int((self.state or {}).get("treasury_silver_available", 0))
                    + int((self.state or {}).get("silver_available", 0))
                )

                screen.blit(scene.small_font.render("Цена:", True, (207, 198, 173)),
                            (card.left + 14, card.top + 76))
                
                # Иконка дерева и строка
                draw_item_icon(screen, "wood", (card.left + 64, card.top + 73), 22)
                wood_str = f"Древесина:   {wood_deposited}/{wood_cost}"
                screen.blit(scene.small_font.render(wood_str, True, (215, 205, 180)),
                            (card.left + 90, card.top + 76))

                wood_done = wood_deposited >= wood_cost
                wood_btn = pygame.Rect(card.left + 262, card.top + 71, 105, 26)
                draw_button(screen, wood_btn, "ВНЕСЕНО" if wood_done else "ВНЕСТИ", scene.small_font,
                            color=(52, 60, 48) if wood_done else
                                (68, 112, 60) if wood_sources_available else (49, 51, 46),
                            text_color=(160, 180, 150) if wood_done else (235, 245, 230))

                # Иконка серебра и строка
                draw_item_icon(screen, "silver", (card.left + 64, card.top + 103), 22)
                silver_str = f"Серебро:       {silver_deposited}/{silver_cost}"
                screen.blit(scene.small_font.render(silver_str, True, (215, 205, 180)),
                            (card.left + 90, card.top + 106))

                silver_done = silver_deposited >= silver_cost
                silver_btn = pygame.Rect(card.left + 262, card.top + 101, 105, 26)
                draw_button(screen, silver_btn, "ВНЕСЕНО" if silver_done else "ВНЕСТИ", scene.small_font,
                            color=(52, 60, 48) if silver_done else
                                (68, 112, 60) if silver_sources_available else (49, 51, 46),
                            text_color=(160, 180, 150) if silver_done else (235, 245, 230))

                self.cart_contribution_areas["wood"] = wood_btn.inflate(8, 6)
                self.cart_contribution_areas["silver"] = silver_btn.inflate(8, 6)

                button = pygame.Rect(card.left + 14, card.bottom - 46, 112, 36)
                btn_color = (68, 132, 76) if (wood_done and silver_done) else (78, 82, 56)
                draw_button(screen, button, "КУПИТЬ", scene.small_font,
                            color=btn_color, text_color=(223, 212, 177))
                self.cart_purchase_buttons[grade] = button
                self.cart_grade_cards[grade] = card
            else:
                if locked:
                    shackle = pygame.Rect(card.left + 14, card.top + 55, 14, 14)
                    pygame.draw.arc(screen, (144, 142, 130), shackle, 0, 3.14, 2)
                    pygame.draw.rect(screen, (144, 142, 130),
                                     (card.left + 11, card.top + 64, 20, 15), border_radius=2)
                    status_lines = ("Заблокировано.", "Изучите все улучшения", "Лёгкой повозки.")
                    for index, line in enumerate(status_lines):
                        screen.blit(scene.small_font.render(line, True, (145, 143, 132)),
                                    (card.left + 42, card.top + 52 + index * 24))
                else:
                    screen.blit(scene.small_font.render("Чертёж доступен", True, (147, 190, 133)),
                                (card.left + 12, card.top + 52))
                    button = pygame.Rect(card.left + 12, card.bottom - 52, card.width - 24, 38)
                    draw_button(screen, button, "КУПИТЬ ЧЕРТЁЖ", scene.small_font,
                                color=(78, 82, 56), text_color=(223, 212, 177))
                    self.cart_purchase_buttons[grade] = button
                    self.cart_grade_cards[grade] = card

        selected_grade = str(progress["selected_grade"])
        selected_progress = progress["grades"][selected_grade]
        stats = cart_stats(selected_progress["upgrades"])
        grade_config = CART_GRADES[selected_grade]
        screen.blit(scene.small_font.render(grade_config["name"], True,
                                            (207, 198, 173)), (right.left + 14, right.top + 42))
        specs = (
            ("Слотов для товаров", grade_config.get("resource_slots"), ""),
            ("Число лошадей", grade_config.get("horse_count"), ""),
            ("Число горожан", grade_config.get("villagers_required"), ""),
            ("Грузоподъёмность", stats["capacity_kg"], "кг"),
            ("Скорость пустой повозки", stats["empty_tiles_per_hour"], "тайлов/час"),
            ("Падение скорости при полной загрузке", stats["full_load_speed_penalty_percent"], "%"),
            ("Погрузка / разгрузка", grade_config.get("load_kg_per_20_seconds"), "кг/20 сек"),
        )
        spec_width = (right.width - 40) // 2
        for index, (label, value, unit) in enumerate(specs):
            column, row_index = index % 2, index // 2
            cell = pygame.Rect(right.left + 12 + column * (spec_width + 12),
                               right.top + 72 + row_index * 35, spec_width, 31)
            pygame.draw.rect(screen, (39, 42, 37), cell)
            name = scene.small_font.render(label, True, (174, 172, 157))
            screen.blit(name, (cell.left + 8, cell.top + 7))
            if value is None:
                value_text = f"не задано {unit}".strip()
            elif label == "Скорость пустой повозки":
                value_text = f"{value} {unit}"
            elif label == "Погрузка / разгрузка":
                value_text = f"{value} кг/20 сек ({grade_config['load_kg_per_minute']} кг/мин)"
            else:
                value_text = f"{value} {unit}".strip()
            amount = scene.small_font.render(value_text, True, (224, 211, 178))
            screen.blit(amount, amount.get_rect(midright=(cell.right - 8, cell.centery)))

        self.cart_node_buttons = {}

    def _route_row_rects(self):
        top = self.route_panel.top + 48
        visible = max(1, (self.route_panel.height - 62) // self.ROUTE_ROW_HEIGHT)
        return [pygame.Rect(self.route_panel.left + 8, top + row * self.ROUTE_ROW_HEIGHT,
                            self.route_panel.width - 16, self.ROUTE_ROW_HEIGHT - 5)
                for row in range(min(visible, max(0, len(self.routes) - self.route_scroll)))]

    def _draw_resource_icon(self, screen, resource_id, label, x, y):
        draw_item_icon(screen, resource_id, (x, y - 4), 22)
        text = self.scene.small_font.render(label, True, (208, 204, 190))
        screen.blit(text, (x + 27, y + 1))
        return x + 31 + text.get_width()

    def _draw_routes(self, screen):
        self._panel(screen, self.route_panel, "Загородные объекты")
        self._panel(screen, self.detail_panel, "Настройка рейса")
        scene = self.scene
        for visible_index, row_rect in enumerate(self._route_row_rects()):
            index = self.route_scroll + visible_index
            route = self.routes[index]
            active = index == self.selected_route
            pygame.draw.rect(screen, (62, 59, 46) if active else (39, 42, 37), row_rect)
            pygame.draw.rect(screen, (169, 143, 92) if active else (74, 76, 65), row_rect, 1)
            title = scene.small_font.render(route["name"], True, (230, 218, 188))
            screen.blit(title, (row_rect.left + 10, row_rect.top + 8))
            distance = scene.small_font.render(f"{route['distance_tiles']:.2f} тайла", True, (193, 190, 174))
            screen.blit(distance, distance.get_rect(topright=(row_rect.right - 10, row_rect.top + 8)))
            icon_x, icon_y = row_rect.left + 10, row_rect.top + 37
            for resource in route.get("resources", []):
                icon_x = self._draw_resource_icon(screen, resource["id"], resource["label"], icon_x, icon_y)
                if icon_x > row_rect.right - 90:
                    icon_x, icon_y = row_rect.left + 10, icon_y + 22

        if not self.routes:
            empty = scene.small_font.render("Нет данных о загородных маршрутах", True, (160, 155, 140))
            screen.blit(empty, empty.get_rect(center=(self.route_panel.centerx, self.route_panel.centery)))
            return
        self._draw_route_detail(screen, self.routes[self.selected_route])

    def _draw_route_detail(self, screen, route):
        scene = self.scene
        panel = self.detail_panel
        y = panel.top + 48
        title = scene.font.render(route["name"], True, (235, 220, 186))
        screen.blit(title, (panel.left + 16, y))
        y += 34
        screen.blit(scene.small_font.render(
            f"Расстояние: {route['distance_tiles']:.2f} тайла ({route['distance_pixels']} px)",
            True, (192, 188, 171)), (panel.left + 16, y))
        y += 35

        goods_height = 34 + 27 * len(route.get("resources", []))
        goods = pygame.Rect(panel.left + 12, y, panel.width - 24, goods_height)
        pygame.draw.rect(screen, (35, 38, 33), goods)
        pygame.draw.rect(screen, (73, 75, 64), goods, 1)
        y = self._table_header(screen, goods, goods.top, (
            ("Ресурс", goods.left + 12, "left"), ("На складе", goods.right - 14, "right"),
        ))
        for index, resource in enumerate(route.get("resources", [])):
            row = pygame.Rect(goods.left + 1, y, goods.width - 2, 27)
            if index % 2 == 0:
                pygame.draw.rect(screen, (42, 44, 37), row)
            self._draw_resource_icon(screen, resource["id"], resource["label"], row.left + 12, row.top + 3)
            storage = (self.route_state or {}).get("storage", {})
            amount = storage.get(resource["id"])
            amount_text = "—" if amount is None else f"{amount:,}".replace(",", " ")
            value = scene.font.render(amount_text, True,
                                      (205, 198, 176) if amount is not None else (160, 158, 145))
            screen.blit(value, value.get_rect(midright=(row.right - 14, row.centery)))
            y += row.height

        timeline = pygame.Rect(panel.left + 12, goods.bottom + 14, panel.width - 24, 174)
        pygame.draw.rect(screen, (35, 38, 33), timeline)
        pygame.draw.rect(screen, (73, 75, 64), timeline, 1)
        y = self._table_header(screen, timeline, timeline.top, (
            ("Таймлайн рейса", timeline.left + 12, "left"), ("Время", timeline.right - 14, "right"),
        ))
        for label in ("Путь туда (пустая повозка)", "Погрузка", "Путь обратно (с грузом)", "Разгрузка в городе"):
            row = pygame.Rect(timeline.left + 1, y, timeline.width - 2, 27)
            screen.blit(scene.small_font.render(label, True, (204, 199, 184)), (row.left + 12, row.top + 5))
            value = scene.small_font.render("—", True, (150, 148, 138))
            screen.blit(value, value.get_rect(midright=(row.right - 14, row.centery)))
            y += row.height

        free_cart = pygame.Rect(panel.left + 14, timeline.bottom + 12, 260, 32)
        send_button = pygame.Rect(panel.right - 238, timeline.bottom + 10, 224, 36)
        draw_button(screen, free_cart, "Повозка: — свободная", scene.small_font,
                    color=(42, 45, 40), text_color=(156, 154, 141))
        draw_button(screen, send_button, "ОТПРАВИТЬ ПОВОЗКУ", scene.small_font,
                    color=(53, 54, 49), text_color=(145, 143, 132))

    def _upgrade_subtabs(self):
        detail_left = self.rect.left + 24 + 340 + 18
        top = self.rect.top + self.HEADER_HEIGHT + 70
        return {
            "transport": pygame.Rect(detail_left + 14, top, 190, 32),
            "stalls": pygame.Rect(detail_left + 212, top, 160, 32),
            "building": pygame.Rect(detail_left + 380, top, 190, 32),
        }

    def _draw_upgrades(self, screen):
        scene = self.scene
        left = pygame.Rect(self.rect.left + 24, self.rect.top + self.HEADER_HEIGHT + 18, 340, self.rect.height - self.HEADER_HEIGHT - 42)
        right = pygame.Rect(left.right + 18, left.top, self.rect.right - left.right - 42, left.height)
        self._panel(screen, left, "Развитие конюшни")
        self._panel(screen, right, "Параметры улучшений")
        self.stall_upgrade_buttons = {}
        tab_labels = {"transport": "ТРАНСПОРТ", "stalls": "СТОЙЛО", "building": "КОНЮШНЯ"}
        for key, button in self._upgrade_subtabs().items():
            draw_button(screen, button, tab_labels[key], scene.small_font,
                        color=(105, 91, 64) if self.upgrade_tab == key else (48, 51, 48))

        if self.upgrade_tab == "building":
            entries = [
                ("Уровень здания", "Стоимость: материалы   Эффект: уровень"),
                ("Вместимость стойл", "Стоимость: материалы   Эффект: +2 места/уровень"),
                ("Разгрузочные рампы", "Стоимость: —   Эффект: —"),
            ]
        elif self.upgrade_tab == "stalls":
            entries = [
                (upgrade["name"], f"Древесина: {upgrade['wood_cost']}   Цена: {Currency.format_amount(Currency.to_copper(silver=upgrade['silver_cost']))}   +1 место")
                for upgrade in BUILDINGS["stable"]["stall_upgrades"].values()
            ]
        else:
            entries = [(node["name"], f"Эффект: {node['effect']}")
                       for node in CART_UPGRADE_NODES.values()]
        header_y = left.top + 98
        table = pygame.Rect(left.left + 10, header_y, left.width - 20, left.height - 112)
        y = self._table_header(screen, table, table.top, (("Улучшение", table.left + 10, "left"),))
        for index, (name, description) in enumerate(entries):
            row = pygame.Rect(table.left + 1, y, table.width - 2, 58)
            pygame.draw.rect(screen, (41, 43, 37) if index % 2 == 0 else (35, 38, 33), row)
            screen.blit(scene.small_font.render(name, True, (210, 204, 187)), (row.left + 10, row.top + 8))
            screen.blit(scene.small_font.render(description, True, (143, 143, 132)),
                        (row.left + 10, row.top + 31))
            y += row.height

        if self.upgrade_tab == "building":
            self._draw_building_upgrade(screen, right)
        elif self.upgrade_tab == "stalls":
            self._draw_stall_upgrades(screen, right)
        else:
            self._draw_cart_upgrade_tree(screen, right)

    def _draw_stall_upgrades(self, screen, panel):
        scene = self.scene
        state = self.state or {}
        capacity = state.get("stall_capacity", 4)
        bonus = state.get("stall_capacity_bonus", 0)
        screen.blit(scene.font.render(f"Вместимость: {capacity} мест (+{bonus} от улучшений)",
                                      True, (219, 205, 175)), (panel.left + 18, panel.top + 106))
        upgrades = state.get("stall_upgrades", {})
        self.stall_upgrade_buttons = {}
        self.stall_contribution_buttons = {}
        for index, (upgrade_id, config) in enumerate(BUILDINGS["stable"]["stall_upgrades"].items()):
            card = pygame.Rect(panel.left + 14, panel.top + 150 + index * 204, panel.width - 28, 190)
            pygame.draw.rect(screen, (39, 42, 37), card)
            pygame.draw.rect(screen, (75, 77, 65), card, 1)
            screen.blit(scene.font.render(config["name"], True, (224, 211, 178)),
                        (card.left + 16, card.top + 10))
            screen.blit(scene.small_font.render("Увеличивает вместимость стойла на 1 лошадь",
                                                True, (175, 183, 158)),
                        (card.left + 16, card.top + 39))
            progress = upgrades.get(upgrade_id, {})
            purchased = progress.get("purchased", False)
            wood_deposited = progress.get("wood_deposited", 0)
            silver_deposited = progress.get("silver_deposited", 0)
            wood_remaining = max(0, config["wood_cost"] - wood_deposited)
            silver_remaining = max(0, config["silver_cost"] - silver_deposited)
            wood_label = (f"Древесина: {wood_deposited}/{config['wood_cost']}   "
                          f"склад: {progress.get('wood_in_warehouse', 0)} · "
                          f"рюкзак: {progress.get('wood_in_backpack', 0)}")
            silver_label = (
                f"Внесено: {Currency.format_amount(Currency.to_copper(silver=silver_deposited))} / "
                f"{Currency.format_amount(Currency.to_copper(silver=config['silver_cost']))}   "
                f"казна: {Currency.format_amount(Currency.to_copper(silver=progress.get('treasury_silver_available', 0)))} · "
                f"кошелёк: {Currency.format_amount(Currency.to_copper(silver=progress.get('silver_available', 0)))}"
            )
            draw_item_icon(screen, "wood", (card.left + 16, card.top + 66), 22)
            screen.blit(scene.small_font.render(wood_label, True, (198, 190, 168)),
                        (card.left + 44, card.top + 68))
            draw_item_icon(screen, "silver", (card.left + 16, card.top + 92), 22)
            screen.blit(scene.small_font.render(silver_label, True, (198, 190, 168)),
                        (card.left + 44, card.top + 94))
            if purchased:
                if progress.get("in_progress", False):
                    seconds_left = max(0, progress.get("seconds_left", 0)
                                       - (time.monotonic() - self.state_received_at))
                    status_text = f"Идёт улучшение: осталось {_format_duration(seconds_left)}"
                    status_color = (230, 194, 120)
                else:
                    status_text = "УСТАНОВЛЕНО"
                    status_color = (142, 190, 130)
                status = scene.small_font.render(status_text, True, status_color)
                screen.blit(status, (card.left + 16, card.top + 126))
            else:
                duration = _format_duration(config["time_seconds"])
                screen.blit(scene.small_font.render(f"Время улучшения: {duration}", True, (185, 181, 164)),
                            (card.left + 16, card.top + 124))
                wood_button = pygame.Rect(card.left + 16, card.bottom - 46, 190, 32)
                silver_button = pygame.Rect(card.left + 218, card.bottom - 46, 190, 32)
                activate_button = pygame.Rect(card.right - 208, card.bottom - 46, 190, 32)
                wood_sources_available = (progress.get("wood_in_warehouse", 0)
                                          + progress.get("wood_in_backpack", 0))
                silver_sources_available = (progress.get("silver_available", 0)
                                            + progress.get("treasury_silver_available", 0))
                draw_button(screen, wood_button, "ВНЕСТИ ДРЕВЕСИНУ", scene.small_font,
                            color=(62, 83, 53) if wood_remaining and wood_sources_available else (49, 51, 46),
                            text_color=(224, 219, 199))
                draw_button(screen, silver_button, "ВНЕСТИ СЕРЕБРО", scene.small_font,
                            color=(62, 83, 53) if silver_remaining and silver_sources_available else (49, 51, 46),
                            text_color=(224, 219, 199))
                self.stall_contribution_buttons[(upgrade_id, "wood")] = wood_button
                self.stall_contribution_buttons[(upgrade_id, "silver")] = silver_button
                ready = progress.get("ready", False)
                draw_button(screen, activate_button, "УСТАНОВИТЬ", scene.small_font,
                            color=(77, 123, 67) if ready else (49, 51, 46),
                            text_color=(230, 225, 202) if ready else (137, 139, 130))
                if ready:
                    self.stall_upgrade_buttons[upgrade_id] = activate_button

    def _draw_cart_upgrade_tree(self, screen, panel):
        scene = self.scene
        selected_grade = str(self.cart_progress["selected_grade"])
        upgrades = self.cart_progress["grades"][selected_grade]["upgrades"]
        node_width = (panel.width - 44) // 3
        self.cart_node_buttons = {}
        for index, (node_id, node) in enumerate(CART_UPGRADE_NODES.items()):
            x = panel.left + 12 + index * (node_width + 10)
            button = pygame.Rect(x, panel.top + 108, node_width, 126)
            level = upgrades.get(node_id, 0)
            selected = node_id == self.selected_cart_node
            pygame.draw.rect(screen, (59, 53, 41) if selected else (39, 42, 37), button)
            pygame.draw.rect(screen, (163, 137, 89) if selected else (74, 76, 65), button, 1)
            title = scene.small_font.render(node["name"], True, (223, 211, 184))
            screen.blit(title, title.get_rect(center=(button.centerx, button.top + 27)))
            effect = scene.small_font.render(node["effect"], True, (164, 177, 148))
            screen.blit(effect, effect.get_rect(center=(button.centerx, button.top + 59)))
            level_text = scene.font.render(f"{level}/3", True, (238, 220, 175))
            screen.blit(level_text, level_text.get_rect(center=(button.centerx, button.top + 98)))
            self.cart_node_buttons[node_id] = button

        detail = pygame.Rect(panel.left + 12, panel.top + 246, panel.width - 24, panel.height - 260)
        self._panel(screen, detail, "Материалы для улучшения")
        node = CART_UPGRADE_NODES[self.selected_cart_node]
        warehouse = (self.state or {}).get("warehouse_storage", {})
        y = detail.top + 48
        screen.blit(scene.small_font.render(node["name"], True, (219, 204, 171)),
                    (detail.left + 14, y))
        for resource_id in node["resources"]:
            y += 35
            self._draw_resource_icon(screen, resource_id, WAREHOUSE_RESOURCE_LABELS[resource_id],
                                     detail.left + 14, y)
            amount = scene.small_font.render(
                f"На складе: {warehouse.get(resource_id, 0)}",
                                             True, (193, 188, 170))
            screen.blit(amount, (detail.left + 300, y + 1))

    def _draw_building_upgrade(self, screen, panel):
        scene = self.scene
        state = self.state or {}
        capacity = state.get("stall_capacity", 4)
        screen.blit(scene.font.render(f"Вместимость сейчас: {capacity} стойла", True, (219, 205, 175)),
                    (panel.left + 18, panel.top + 106))
        upgrade = state.get("upgrade")
        self.deposit_buttons = {}
        if upgrade is None:
            screen.blit(scene.font.render("Максимальный уровень здания", True, (195, 195, 175)),
                        (panel.left + 18, panel.top + 150))
            return

        y = panel.top + 150
        screen.blit(scene.font.render(f"Улучшение до уровня {upgrade['next_level']}", True, (255, 225, 130)),
                    (panel.left + 18, y))
        y += 38
        screen.blit(scene.small_font.render("Взнос можно сделать со склада или из рюкзака", True, (220, 210, 170)),
                    (panel.left + 18, y))
        y += 30
        for material in upgrade["materials"]:
            draw_item_icon(screen, material.get("item_id", material.get("name")), (panel.left + 18, y + 2), 24)
            text = (f"{material['name']}: {material['deposited']} / {material['required']}   "
                    f"склад: {material['in_warehouse']} · рюкзак: {material.get('in_backpack', 0)}")
            screen.blit(scene.small_font.render(text, True, (215, 210, 192)), (panel.left + 48, y + 5))
            if material["deposited"] < material["required"] and not upgrade["in_progress"]:
                button = pygame.Rect(panel.right - 140, y, 120, 28)
                enabled = material["in_warehouse"] > 0 or material.get("in_backpack", 0) > 0
                draw_button(screen, button, "ВНЕСТИ", scene.small_font,
                            color=(80, 140, 85) if enabled else (55, 55, 60))
                self.deposit_buttons[material["item_id"]] = button
            y += 36

        y += 8
        if upgrade["in_progress"]:
            seconds_left = max(0, upgrade["seconds_left"] - (time.monotonic() - self.state_received_at))
            screen.blit(scene.font.render(f"Идёт улучшение: осталось {format_duration(seconds_left)}",
                                          True, (120, 190, 240)), (panel.left + 18, y))
            return
        self.upgrade_button.topleft = (panel.left + 18, y)
        ready = upgrade["ready"]
        draw_button(screen, self.upgrade_button, "УЛУЧШИТЬ", scene.small_font,
                    color=(80, 140, 85) if ready else (55, 55, 60),
                    text_color=(255, 255, 255) if ready else (150, 150, 155))
