"""Main castle population and city status window."""

import time

import pygame

from client.network import ServerError
from core import settings
from core.currency import Currency
from ui.catalog_icons import draw_building_icon, draw_item_icon
from ui.hud import draw_button


TABS = (
    ("governor", "ГУБЕРНАТОР"),
    ("population", "НАСЕЛЕНИЕ"),
    ("treasury", "КАЗНА"),
    ("tasks", "ЗАДАНИЯ"),
    ("upgrades", "УЛУЧШЕНИЯ"),
)
MOOD_LABELS = {
    "satisfied": ("Сыт", (100, 215, 125)),
    "irritated": ("Проголодался", (240, 205, 85)),
    "starving": ("Голоден", (240, 100, 90)),
}
FOOD_STATUS_COLORS = {
    "Пищи достаточно": (115, 215, 125),
    "Население не доедает": (245, 205, 80),
    "В городе голод": (235, 95, 85),
}
WORK_COLORS = {"Свободен": (120, 195, 230), "Занят": (120, 215, 130),
               "В пути": (90, 165, 245), "Возвращается": (235, 170, 105),
               "В городе": (220, 185, 115), "Ведёт повозку": (215, 176, 112)}
WORKSITE_LABELS = {
    "farm": "Ферма", "lumber_camp": "Лесопилка", "mountain_rift": "Рудник",
    "barnyard": "Зверинец", "black_pit": "Чёрная яма",
}


def _format_clock(seconds):
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class CastleWindow:
    REFRESH_SECONDS = 5.0

    def __init__(self, scene):
        self.scene = scene
        self.rect = pygame.Rect(settings.WIDTH // 2 - 540, settings.HEIGHT // 2 - 380, 1080, 760)
        self.close_button = pygame.Rect(self.rect.right - 46, self.rect.top + 14, 30, 30)
        tab_gap = 8
        tab_width = (self.rect.width - 48 - tab_gap * (len(TABS) - 1)) // len(TABS)
        self.tabs = {
            key: pygame.Rect(self.rect.left + 24 + index * (tab_width + tab_gap),
                             self.rect.top + 84, tab_width, 34)
            for index, (key, _label) in enumerate(TABS)
        }
        self.is_open = False
        self.tab = "governor"
        self.state = None
        self.message = None
        self.selected_citizen_id = None
        self.pending_action = None
        self.last_refresh = 0.0
        self.citizen_actions = {}
        self.worksite_buttons = {}
        self.confirm_button = pygame.Rect(0, 0, 160, 36)
        self.cancel_button = pygame.Rect(0, 0, 160, 36)
        self.treasury_buttons = {}
        self.treasury_transfer = None
        self.treasury_quantity = 0
        self.treasury_dragging = False
        self.treasury_track_rect = pygame.Rect(0, 0, 0, 0)
        self.treasury_confirm_button = pygame.Rect(0, 0, 0, 0)
        self.treasury_cancel_button = pygame.Rect(0, 0, 0, 0)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 28, bold=True)
        self.font = pygame.font.SysFont(settings.FONT_NAME, 19)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 16)
        self.tiny_font = pygame.font.SysFont(settings.FONT_NAME, 14)

    def open(self):
        self.is_open = True
        self.load()

    def load(self):
        try:
            self.state = self.scene.session.client.get_city_population(
                self.scene.session.character["id"]
            )
            self.scene.city_population_count = int(self.state.get("population", 4))
            self.last_refresh = time.monotonic()
            self.message = None
            self._clear_invalid_selection()
            return True
        except (ServerError, AttributeError, KeyError, OSError) as error:
            self.message = str(error)
            return False

    def _refresh_if_due(self):
        if time.monotonic() - self.last_refresh >= self.REFRESH_SECONDS:
            self.load()

    def _clear_invalid_selection(self):
        citizens = (self.state or {}).get("citizens", [])
        if self.selected_citizen_id not in {item["id"] for item in citizens}:
            self.selected_citizen_id = None

    def handle_event(self, event):
        if not self.is_open:
            return
        if self.treasury_transfer is not None:
            self._handle_treasury_transfer_event(event)
            return
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
            if self.pending_action:
                self.pending_action = None
            else:
                self.is_open = False
            return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if self.close_button.collidepoint(event.pos):
            self.is_open = False
            self.pending_action = None
            return
        if self.pending_action:
            if self.confirm_button.collidepoint(event.pos):
                action = self.pending_action
                self.pending_action = None
                if action["kind"] == "assign":
                    self._assign(action["citizen_id"], action["building"], action["slot_index"])
                else:
                    self._recall(action["citizen_id"])
            elif self.cancel_button.collidepoint(event.pos):
                self.pending_action = None
            return
        for key, rect in self.tabs.items():
            if rect.collidepoint(event.pos):
                self.tab = key
                self.selected_citizen_id = None
                return
        if self.tab == "treasury":
            for direction, rect in self.treasury_buttons.items():
                if rect.collidepoint(event.pos):
                    self._open_treasury_transfer(direction)
                    return
            return
        if self.tab != "population":
            return
        for citizen_id, rect in self.citizen_actions.items():
            if not rect.collidepoint(event.pos):
                continue
            citizen = next((item for item in (self.state or {}).get("citizens", [])
                            if item["id"] == citizen_id), None)
            if citizen is None:
                return
            if citizen.get("work_status") == "Ведёт повозку":
                self.message = "Участник экипажа занят транспортным рейсом."
                return
            if citizen.get("job_building"):
                if citizen.get("travel_direction") == "returning":
                    self.message = "Горожанин уже возвращается в город."
                else:
                    self.pending_action = {"kind": "recall", "citizen_id": citizen_id}
            else:
                self.selected_citizen_id = citizen_id
            return
        for building, rect in self.worksite_buttons.items():
            if not rect.collidepoint(event.pos):
                continue
            site = next((item for item in (self.state or {}).get("worksites", [])
                         if item["building"] == building), None)
            if site is None or not site.get("free_slots"):
                self.message = "Нет свободных рабочих мест на этом объекте."
                return
            if self.selected_citizen_id is not None:
                self.pending_action = {
                    "kind": "assign", "citizen_id": self.selected_citizen_id,
                    "building": building, "slot_index": site["free_slots"][0],
                }
            return

    def _assign(self, citizen_id, building, slot_index):
        try:
            self.state = self.scene.session.client.assign_city_citizen(
                self.scene.session.character["id"], citizen_id, building, slot_index
            )
            self.message = "Горожанин отправлен к месту работы."
            self.last_refresh = time.monotonic()
            self.selected_citizen_id = None
        except (ServerError, AttributeError, KeyError, OSError) as error:
            self.message = str(error)

    def _recall(self, citizen_id):
        try:
            self.state = self.scene.session.client.recall_city_citizen(
                self.scene.session.character["id"], citizen_id
            )
            self.message = "Горожанин возвращается в город."
            self.last_refresh = time.monotonic()
        except (ServerError, AttributeError, KeyError, OSError) as error:
            self.message = str(error)

    def draw(self, screen):
        if not self.is_open:
            return
        self._refresh_if_due()
        state = self.state or {}
        overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 18, 215))
        screen.blit(overlay, (0, 0))
        pygame.draw.rect(screen, (24, 27, 25), self.rect, border_radius=9)
        pygame.draw.rect(screen, (197, 164, 103), self.rect, 2, border_radius=9)

        draw_building_icon(screen, "main_castle", (self.rect.left + 20, self.rect.top + 16), 42)
        title = self.title_font.render("Замок Радбурка", True, (243, 218, 158))
        screen.blit(title, (self.rect.left + 72, self.rect.top + 19))
        screen.blit(self.font.render(f"Уровень {state.get('castle_level', 1)}", True, (220, 209, 184)),
                    (self.rect.left + 74, self.rect.top + 52))
        pygame.draw.line(screen, (86, 80, 62),
                         (self.rect.left + 22, self.rect.top + 75),
                         (self.rect.right - 22, self.rect.top + 75), 1)

        mouse = pygame.mouse.get_pos()
        for key, label in TABS:
            rect = self.tabs[key]
            draw_button(screen, rect, label, self.small_font,
                        color=(104, 88, 58) if self.tab == key else (45, 49, 46),
                        hover_color=(128, 108, 69))
        self.close_button = pygame.Rect(self.rect.right - 46, self.rect.top + 16, 28, 28)
        draw_button(screen, self.close_button, "×", self.font, color=(75, 47, 42), hover_color=(145, 65, 55))
        if self.message:
            screen.blit(self.small_font.render(self.message, True, (242, 170, 115)),
                        (self.rect.left + 24, self.rect.bottom - 30))

        if self.tab == "population":
            self._draw_population(screen, state, mouse)
        elif self.tab == "treasury":
            self._draw_treasury(screen, state)
        elif self.tab == "governor":
            pass
        elif self.tab == "tasks":
            self._draw_placeholder(screen, "Заданий пока нет.")
        else:
            self._draw_placeholder(screen, "Улучшения замка появятся позже.")
        if self.pending_action:
            self._draw_confirmation(screen, state)
        if self.treasury_transfer is not None:
            self._draw_treasury_transfer(screen, state)

    def _open_treasury_transfer(self, direction):
        state = self.state or {}
        available = (state.get("personal_currency_copper", 0) if direction == "deposit"
                     else state.get("treasury_copper", 0))
        if int(available) <= 0:
            self.message = "Нет доступных монет для перевода."
            return
        self.treasury_transfer = {"direction": direction, "maximum": int(available)}
        self.treasury_quantity = 0
        self.treasury_dragging = False

    def _set_treasury_quantity(self, x):
        if self.treasury_transfer is None:
            return
        maximum = self.treasury_transfer["maximum"]
        ratio = (x - self.treasury_track_rect.left) / max(1, self.treasury_track_rect.width)
        self.treasury_quantity = round(max(0.0, min(1.0, ratio)) * maximum)

    def _handle_treasury_transfer_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.treasury_transfer = None
            self.treasury_dragging = False
            return
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.treasury_dragging = False
            return
        if event.type == pygame.MOUSEMOTION and self.treasury_dragging:
            self._set_treasury_quantity(event.pos[0])
            return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if self.treasury_confirm_button.collidepoint(event.pos):
            if self.treasury_quantity <= 0:
                return
            transfer = self.treasury_transfer
            try:
                self.state = self.scene.session.client.transfer_city_treasury(
                    self.scene.session.character["id"],
                    transfer["direction"], self.treasury_quantity,
                )
                wallet = self.state.get("personal_currency")
                character = self.scene.session.character
                if wallet and character is not None:
                    character.update(wallet)
                    profile_overlay = getattr(self.scene, "profile_overlay", None)
                    if profile_overlay is not None:
                        profile_overlay.update_profile(character)
                        profile_overlay.update_counterpart(character)
                self.last_refresh = time.monotonic()
                self.message = ("Монеты внесены в казну."
                                if transfer["direction"] == "deposit"
                                else "Монеты выданы из казны.")
            except (ServerError, AttributeError, KeyError, OSError) as error:
                self.message = str(error)
            self.treasury_transfer = None
            self.treasury_dragging = False
        elif self.treasury_cancel_button.collidepoint(event.pos):
            self.treasury_transfer = None
            self.treasury_dragging = False
        elif self.treasury_track_rect.inflate(24, 24).collidepoint(event.pos):
            self.treasury_dragging = True
            self._set_treasury_quantity(event.pos[0])

    def _draw_treasury(self, screen, state):
        left = self.rect.left + 32
        top = self.rect.top + 142
        screen.blit(self.font.render("Городская казна:", True, (243, 218, 158)), (left, top))
        treasury = state.get("treasury", {})
        coin_x = left + 174
        for currency, amount in (("copper", treasury.get("copper", 0)),
                                 ("silver", treasury.get("silver", 0)),
                                 ("gold", treasury.get("gold", 0))):
            draw_item_icon(screen, currency, (coin_x, top + 1), 22)
            amount_surface = self.font.render(str(amount), True, (232, 225, 205))
            screen.blit(amount_surface, (coin_x + 26, top + 1))
            coin_x += 82
        seconds = state.get("tax_tick_seconds_left", 0)
        expected_tax = state.get("expected_tax_text", "0 меди")
        screen.blit(self.small_font.render(
            f"До сбора налогов: {_format_clock(seconds)} (ожидается: {expected_tax})",
            True, (190, 205, 184)), (left, top + 58))
        self.treasury_buttons = {
            "deposit": pygame.Rect(left, top + 104, 220, 42),
            "withdraw": pygame.Rect(left + 232, top + 104, 220, 42),
        }
        draw_button(screen, self.treasury_buttons["deposit"], "ПОПОЛНИТЬ КАЗНУ", self.small_font,
                    color=(64, 105, 68), hover_color=(83, 132, 85))
        draw_button(screen, self.treasury_buttons["withdraw"], "ВЗЯТЬ С КАЗНЫ", self.small_font,
                    color=(75, 82, 64), hover_color=(105, 115, 77))

    def _draw_treasury_transfer(self, screen, state):
        transfer = self.treasury_transfer
        panel = pygame.Rect(self.rect.centerx - 280, self.rect.centery - 140, 560, 280)
        pygame.draw.rect(screen, (17, 21, 19), panel, border_radius=7)
        pygame.draw.rect(screen, (197, 164, 103), panel, 2, border_radius=7)
        deposit = transfer["direction"] == "deposit"
        title = "Внести монеты в казну" if deposit else "Забрать монеты из казны"
        source = state.get("personal_currency_text", "0 меди") if deposit else state.get("treasury_text", "0 меди")
        label = self.font.render(title, True, (243, 218, 158))
        screen.blit(label, label.get_rect(center=(panel.centerx, panel.top + 40)))
        screen.blit(self.small_font.render(f"Доступно: {source}", True, (201, 200, 185)),
                    (panel.left + 26, panel.top + 78))
        maximum = transfer["maximum"]
        selected = Currency.format_amount(self.treasury_quantity)
        maximum_text = Currency.format_amount(maximum)
        screen.blit(self.small_font.render(f"Перевести: {selected} / {maximum_text}",
                                           True, (224, 211, 178)),
                    (panel.left + 26, panel.top + 104))
        self.treasury_track_rect = pygame.Rect(panel.left + 28, panel.top + 146, panel.width - 56, 8)
        pygame.draw.rect(screen, (68, 72, 63), self.treasury_track_rect, border_radius=4)
        progress = 0 if maximum <= 0 else self.treasury_quantity / maximum
        fill = pygame.Rect(self.treasury_track_rect.left, self.treasury_track_rect.top,
                           round(self.treasury_track_rect.width * progress), self.treasury_track_rect.height)
        if fill.width:
            pygame.draw.rect(screen, (145, 174, 104), fill, border_radius=4)
        knob_x = self.treasury_track_rect.left + round(self.treasury_track_rect.width * progress)
        pygame.draw.circle(screen, (229, 215, 182), (knob_x, self.treasury_track_rect.centery), 11)
        self.treasury_cancel_button = pygame.Rect(panel.right - 278, panel.bottom - 54, 112, 36)
        self.treasury_confirm_button = pygame.Rect(panel.right - 152, panel.bottom - 54, 128, 36)
        draw_button(screen, self.treasury_cancel_button, "ОТМЕНА", self.small_font, color=(58, 55, 49))
        draw_button(screen, self.treasury_confirm_button, "ПЕРЕВЕСТИ", self.small_font,
                    color=(74, 126, 69) if self.treasury_quantity else (51, 54, 48),
                    text_color=(238, 235, 217) if self.treasury_quantity else (142, 144, 134))

    def _draw_placeholder(self, screen, text):
        surface = self.font.render(text, True, (205, 199, 185))
        screen.blit(surface, surface.get_rect(center=(self.rect.centerx, self.rect.centery + 20)))

    def _draw_population(self, screen, state, mouse):
        left = self.rect.left + 28
        top = self.rect.top + 137
        food = state.get("food_storage", {})
        summary = (f"Население: {state.get('population', 0)} / "
                   f"{state.get('population_capacity', 10)}")
        growth_eta = state.get("new_citizen_eta_seconds")
        if growth_eta is not None:
            elapsed = time.monotonic() - self.last_refresh
            growth_eta = max(0, int(growth_eta - elapsed))
            summary += f"  (Следующий житель: {_format_clock(growth_eta)})"
        screen.blit(self.font.render(summary, True, (225, 216, 187)), (left, top))
        food_text = (f"Амбар: пшеница {food.get('wheat', 0)} · ягоды {food.get('berries', 0)}"
                     f" · мясо {food.get('meat', 0)}")
        food_surface = self.small_font.render(food_text, True, (190, 210, 177))
        screen.blit(food_surface, (left, top + 30))
        food_status = state.get("food_status")
        if food_status:
            status_color = FOOD_STATUS_COLORS.get(food_status, (190, 190, 180))
            status_surface = self.small_font.render(f"({food_status})", True, status_color)
            screen.blit(status_surface, (left + food_surface.get_width() + 10, top + 30))
        self.citizen_actions = {}
        row_top = top + 67
        row_height = 39
        for index, citizen in enumerate(state.get("citizens", [])):
            row = pygame.Rect(left, row_top + index * row_height, self.rect.width - 56, 34)
            pygame.draw.rect(screen, (38, 42, 39) if index % 2 else (33, 37, 35), row)
            screen.blit(self.small_font.render(citizen["name"], True, (226, 225, 211)),
                        (row.left + 10, row.top + 8))
            satiety = int(citizen.get("satiety", 0))
            strong_hunger = int(citizen.get("strong_hunger", 0))
            if satiety == 0:
                meter_label = f"Сильный голод {strong_hunger}%"
                meter_color = (15, 15, 15)
            else:
                meter_label = f"Сытность {satiety}%"
                meter_color = ((226, 66, 58) if satiety <= 10 else
                               (232, 184, 48) if satiety <= 30 else
                               (72, 174, 95))
            screen.blit(self.small_font.render(meter_label, True, meter_color),
                        (row.left + 220, row.top + 3))
            meter = pygame.Rect(row.left + 220, row.top + 24, 150, 8)
            pygame.draw.rect(screen, (95, 98, 91), meter, border_radius=3)
            meter_value = strong_hunger if satiety == 0 else satiety
            fill = meter.copy()
            fill.width = round((meter.width - 2) * max(0, min(100, meter_value)) / 100)
            fill.left += 1
            fill.top += 1
            fill.height -= 2
            if fill.width:
                pygame.draw.rect(screen, meter_color, fill, border_radius=2)
            mood, mood_color = MOOD_LABELS.get(citizen.get("satisfaction"), ("—", (180, 180, 180)))
            screen.blit(self.small_font.render(f"Довольство: {mood}", True, mood_color),
                        (row.left + 405, row.top + 8))
            work_status = citizen.get("work_status", "Свободен")
            worksite = WORKSITE_LABELS.get(citizen.get("job_building"))
            work_label = f"{worksite} · {work_status}" if worksite else work_status
            if citizen.get("travel_direction"):
                seconds_left = max(
                    0, int(citizen.get("travel_seconds_left", 0)
                           - (time.monotonic() - self.last_refresh))
                )
                work_label += f" {_format_clock(seconds_left)}"
            screen.blit(self.small_font.render(work_label, True, WORK_COLORS.get(work_status, (200, 200, 200))),
                        (row.left + 635, row.top + 8))
            action_rect = pygame.Rect(row.right - 142, row.top + 3, 132, 28)
            is_convoy_driver = work_status == "Ведёт повозку"
            if not is_convoy_driver:
                self.citizen_actions[int(citizen["id"])] = action_rect
            label = ("В РЕЙСЕ" if is_convoy_driver else
                     "ДОМОЙ" if citizen.get("job_building") else "НАЗНАЧИТЬ")
            if citizen.get("travel_direction") == "returning":
                label = "В ПУТИ ДОМОЙ"
            draw_button(screen, action_rect, label, self.small_font,
                        color=(73, 104, 75) if label == "НАЗНАЧИТЬ" else (75, 74, 62),
                        hover_color=(96, 135, 93))

        self.worksite_buttons = {}
        if self.selected_citizen_id is None:
            return
        worksite_y = self.rect.bottom - 108
        screen.blit(self.small_font.render("Куда отправить:", True, (228, 215, 178)),
                    (left, worksite_y - 24))
        worksite_width = (self.rect.width - 56 - 8 * (len(state.get("worksites", [])) - 1)) // max(1, len(state.get("worksites", [])))
        for index, site in enumerate(state.get("worksites", [])):
            rect = pygame.Rect(left + index * (worksite_width + 8), worksite_y,
                               worksite_width, 54)
            self.worksite_buttons[site["building"]] = rect
            free = site.get("free_slots", [])
            capacity = int(site.get("capacity", 0))
            occupied = max(0, capacity - len(free))
            hovered = rect.collidepoint(mouse) and bool(free)
            color = (83, 125, 86) if hovered else (62, 90, 65) if free else (48, 50, 47)
            pygame.draw.rect(screen, color, rect, border_radius=5)
            pygame.draw.rect(screen, (92, 105, 91), rect, 1, border_radius=5)
            name = self.tiny_font.render(site["name"], True, (230, 225, 205))
            count = self.tiny_font.render(
                f"Свободно: {len(free)} · занято: {occupied}", True, (202, 211, 195)
            )
            screen.blit(name, name.get_rect(midtop=(rect.centerx, rect.top + 6)))
            screen.blit(count, count.get_rect(midbottom=(rect.centerx, rect.bottom - 5)))

    def _draw_confirmation(self, screen, state):
        pending = self.pending_action
        citizen = next((item for item in state.get("citizens", [])
                        if item["id"] == pending["citizen_id"]), {})
        panel = pygame.Rect(self.rect.centerx - 250, self.rect.centery - 105, 500, 210)
        pygame.draw.rect(screen, (17, 21, 19), panel, border_radius=7)
        pygame.draw.rect(screen, (197, 164, 103), panel, 2, border_radius=7)
        if pending["kind"] == "assign":
            site = next((item for item in state.get("worksites", [])
                         if item["building"] == pending["building"]), {})
            title_text = f"Отправить {citizen.get('name', 'горожанина')} на работу?"
            detail_text = (f"{site.get('name', '')} · путь в одну сторону: "
                           f"{_format_clock(site.get('travel_seconds', 0))}")
            confirm_label = "ОТПРАВИТЬ"
        else:
            site = next((item for item in state.get("worksites", [])
                         if item["building"] == citizen.get("job_building")), {})
            title_text = f"Вернуть {citizen.get('name', 'горожанина')} в город?"
            detail_text = f"Путь домой: {_format_clock(site.get('travel_seconds', 0))}"
            confirm_label = "ВЕРНУТЬ"
        title = self.font.render(title_text, True, (243, 218, 158))
        detail = self.small_font.render(detail_text, True, (205, 199, 185))
        screen.blit(title, title.get_rect(center=(panel.centerx, panel.top + 58)))
        screen.blit(detail, detail.get_rect(center=(panel.centerx, panel.top + 94)))
        self.confirm_button = pygame.Rect(panel.left + 58, panel.bottom - 54, 170, 36)
        self.cancel_button = pygame.Rect(panel.right - 228, panel.bottom - 54, 170, 36)
        draw_button(screen, self.confirm_button, confirm_label, self.small_font,
                    color=(65, 105, 68), hover_color=(83, 132, 85))
        draw_button(screen, self.cancel_button, "ОТМЕНА", self.small_font,
                    color=(86, 59, 51), hover_color=(127, 71, 61))