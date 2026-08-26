import pygame
import time

from client.network import ServerError
from core import settings
from ui.chat import ChatPanel
from ui.character_comparison import CharacterComparison
from ui.character_profile_overlay import CharacterProfileOverlay
from ui.renderers.backyard import BackyardRenderer


class BackyardScene:
    def __init__(self, session):
        self.session = session
        self.finished = False
        self.cancelled = False
        self.error = ""
        self.font = pygame.font.SysFont(settings.FONT_NAME, 22)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 18)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 36)
        self.profile_overlay = CharacterProfileOverlay(self.small_font)
        self.chat = ChatPanel(session, "backyard", profile_overlay=self.profile_overlay)
        self.navigate = None
        self.navigation_buttons = [
            {"rect": pygame.Rect(1640, 35, 220, 45), "label": "ТРАКТИР", "target": "tavern"},
        ]
        self.tavern_button = self.navigation_buttons[0]["rect"]
        self.application_frame = pygame.Rect(560, 40, 800, 560)
        self.application_button = pygame.Rect(560, 620, 220, 40)
        self.group_battle_button = pygame.Rect(800, 620, 220, 40)
        self.group_offers = []
        self.group_elapsed = 0.0
        self.group_application_id = None
        self.group_application = None
        self.application_menu = None
        self.application_ttl = None
        self.group_menu_size = None
        self.group_menu_ttl = None
        self.application_popup = None
        self.profile_comparison = CharacterComparison(self.small_font)
        self.renderer = BackyardRenderer(self)

    def handle_event(self, event):
        if self.chat.handle_event(event):
            if self.profile_overlay.is_open:
                self.application_popup = None
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for button in self.navigation_buttons:
                if button["rect"].collidepoint(event.pos):
                    self.navigate = button["target"]
                    self.finished = True
                    return
            if self.application_menu is not None:
                self._handle_application_menu(event.pos)
                return
            if self.application_popup is not None:
                action, profile = self.profile_comparison.handle_click(event.pos, self.session.character)
                if action == "stat_change":
                    self._save_profile_card(profile)
                    return
                if action == "handled":
                    return
                if action == "close":
                    self.application_popup = None
                    return
                if action == "challenge":
                    self._challenge_selected()
                    return
            if self.application_button.collidepoint(event.pos):
                self._submit_application()
                return
            if self.group_battle_button.collidepoint(event.pos):
                self._create_group_battle()
                return
            for index, offer in enumerate(self._application_offers()):
                row = pygame.Rect(
                    self.application_frame.x + 25,
                    self.application_frame.y + 75 + index * 42,
                    self.application_frame.width - 50,
                    34,
                )
                if row.collidepoint(event.pos):
                    self._open_application(offer)
                    return
            group_start = self.application_frame.y + 275
            for index, offer in enumerate(self.group_offers):
                row = pygame.Rect(self.application_frame.x + 25, group_start + index * 42, self.application_frame.width - 50, 34)
                if row.collidepoint(event.pos):
                    self._join_group_battle(offer)
                    return
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_b):
                if self.chat.duel_accepted is not None:
                    self.finished = True
            elif event.key == pygame.K_ESCAPE:
                self.cancelled = True
                self.finished = True

    def update(self, dt):
        self.chat.update(dt)
        self.group_elapsed += dt
        if self.group_elapsed >= 2:
            self.group_elapsed = 0.0
            try:
                self.group_offers = self.session.list_group_battles()
                if self.group_application_id is None:
                    character_id = self.session.character["id"]
                    own_offer = next(
                        (
                            offer for offer in self.group_offers
                            if any(item["id"] == character_id for item in offer.get("participants", []))
                        ),
                        None,
                    )
                    if own_offer is not None:
                        self.group_application_id = own_offer["id"]
                        self.group_application = own_offer
            except ServerError:
                pass
        if self.chat.duel_accepted is not None:
            accepted = self.chat.duel_accepted
            self.chat.duel_accepted = None
            if accepted is not None:
                self.opponent = accepted
                self.finished = True
            else:
                self.error = "Соперник больше не находится в этой локации"

    def _respond_application(self, accepted):
        if not self.chat.offers:
            self.error = "Нет активных заявок"
            return
        offer = self.chat.offers[0]
        try:
            self.session.respond_duel_offer(offer["id"], accepted)
            if accepted:
                self.opponent = next(
                    (item for item in self.chat.occupants if item.get("character_id") == offer["sender_id"]),
                    None,
                )
                if self.opponent is None:
                    self.error = "Соперник больше не находится в локации"
                    return
                self.finished = True
            else:
                self.error = "Заявка отклонена"
            self.chat.refresh()
        except ServerError as error:
            self.error = str(error)

    def _submit_application(self):
        if self.group_application_id is not None:
            self.error = "Сначала отмените сбор стенка на стенку"
            return
        if self.chat.my_application is None:
            self.application_menu = "duel"
            return
        try:
            self.session.cancel_duel_application("backyard")
            self.chat.my_application = None
        except ServerError as error:
            self.error = str(error)

    def _create_group_battle(self):
        if self.group_application_id is not None:
            try:
                self.session.leave_group_battle(self.group_application_id)
                self.group_application_id = None
                self.group_application = None
                self.group_offers = self.session.list_group_battles()
            except ServerError as error:
                self.error = str(error)
            return
        if self.chat.my_application is not None:
            self.error = "Сначала отмените заявку один на один"
            return
        self.application_menu = "group"

    def _handle_application_menu(self, pos):
        menu = pygame.Rect(700, 270, 520, 280 if self.application_menu == "duel" else 410)
        if not menu.collidepoint(pos):
            self.application_menu = None
            return
        option_height = 42
        if self.application_menu == "duel":
            options = (120, 300, 600, 900, 1200, 1800)
            start_y = menu.y + 65
            for index, seconds in enumerate(options):
                rect = pygame.Rect(menu.x + 25 + (index % 3) * 160, start_y + (index // 3) * option_height, 145, 34)
                if rect.collidepoint(pos):
                    self.application_ttl = seconds
                    try:
                        result = self.session.create_duel_application("backyard", seconds)
                        self.chat.my_application = result.get("application") or {
                            "created_at": time.time(),
                            "ttl": seconds,
                            "status": "pending",
                        }
                        self.chat.my_application.setdefault("ttl", seconds)
                    except ServerError as error:
                        self.error = str(error)
                    self.application_menu = None
                    return
        else:
            sizes = (6, 8, 10)
            times = (120, 600, 1800)
            for index, size in enumerate(sizes):
                rect = pygame.Rect(menu.x + 25 + index * 160, menu.y + 85, 145, 34)
                if rect.collidepoint(pos):
                    self.group_menu_size = size
                    return
            for index, seconds in enumerate(times):
                rect = pygame.Rect(menu.x + 25 + index * 160, menu.y + 155, 145, 34)
                if rect.collidepoint(pos):
                    self.group_menu_ttl = seconds
                    return
            if self.group_menu_size is not None and self.group_menu_ttl is not None:
                confirm = pygame.Rect(menu.x + 160, menu.y + 330, 200, 40)
                if confirm.collidepoint(pos):
                    try:
                        result = self.session.create_group_battle("backyard", self.group_menu_ttl, self.group_menu_size)
                        self.group_application_id = result["offer"]["id"]
                        self.group_application = result["offer"]
                        self.group_offers = self.session.list_group_battles()
                    except ServerError as error:
                        self.error = str(error)
                    self.application_menu = None
                    self.group_menu_size = None
                    self.group_menu_ttl = None
                    return

    def _join_group_battle(self, offer):
        try:
            result = self.session.join_group_battle(offer["id"], "backyard")
            if result.get("offer", {}).get("status") == "ready":
                self.error = "Команды сформированы"
            else:
                self.error = "Вы присоединились к групповому бою"
            self.group_offers = self.session.list_group_battles()
            if result.get("offer", {}).get("status") == "waiting":
                self.group_application_id = result["offer"]["id"]
                self.group_application = result["offer"]
        except ServerError as error:
            self.error = str(error)

    def _open_application(self, offer):
        self.profile_overlay.close()
        self.application_popup = next(
            (
                item for item in self.chat.occupants
                if str(item.get("character_id")) == str(offer["sender_id"])
            ),
            {"name": offer["sender"], "level": 1, "stats": {}},
        )

    def _challenge_selected(self):
        target = self.application_popup
        if target is None:
            return
        if self.chat.my_application is not None:
            self.error = "Пока активна ваша заявка, бросить вызов нельзя"
            return
        try:
            result = self.session.offer_duel("backyard", target.get("character_id"))
            if result.get("accepted"):
                self.opponent = target
                self.finished = True
            else:
                self.error = "Вызов отправлен сопернику"
            self.application_popup = None
        except ServerError as error:
            self.error = str(error)

    def draw(self, screen):
        self.renderer.draw(screen)

    def close(self):
        pass

    def _application_offers(self):
        offers = list(self.chat.offers)
        own_application = self.chat.my_application
        if own_application is not None and not any(
            offer.get("id") == own_application.get("id") for offer in offers
        ):
            offers.append({
                **own_application,
                "sender_id": self.session.character["id"],
                "sender": self.session.character["name"],
            })
        offers.sort(key=lambda offer: float(offer.get("created_at", 0)), reverse=True)
        return offers

    def _save_profile_card(self, profile):
        try:
            self.session.save_character_profile(profile)
        except ServerError as error:
            self.error = str(error)
