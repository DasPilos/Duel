import pygame
import time

from client.network import ServerError
from core import settings
from ui.hud import draw_bar, draw_button, draw_text
from ui.chat import ChatPanel
from ui.sprite_loader import FighterSprite


class BackyardScene:
    def __init__(self, session):
        self.session = session
        self.finished = False
        self.cancelled = False
        self.error = ""
        self.font = pygame.font.SysFont(settings.FONT_NAME, 22)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 18)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 36)
        self.chat = ChatPanel(session, "backyard")
        self.navigate = None
        self.tavern_button = pygame.Rect(1640, 35, 220, 45)
        self.application_frame = pygame.Rect(560, 40, 800, 560)
        self.application_button = pygame.Rect(560, 620, 220, 40)
        self.application_popup = None
        self.sprite = FighterSprite()
        profile_top = 120
        profile_bottom = settings.CHAT_PANEL_Y + settings.CHAT_PANEL_HEIGHT
        profile_height = profile_bottom - profile_top
        self.player_profile_frame = pygame.Rect(20, profile_top, 500, profile_height)
        self.opponent_profile_frame = pygame.Rect(1400, profile_top, 500, profile_height)
        self._update_opponent_buttons()

    def _update_opponent_buttons(self):
        self.opponent_close_button = pygame.Rect(
            self.opponent_profile_frame.right - 100,
            self.opponent_profile_frame.y + 15,
            85,
            34,
        )
        self.opponent_challenge_button = pygame.Rect(
            1140,
            self.application_button.y,
            self.application_button.width,
            self.application_button.height,
        )

    def handle_event(self, event):
        if self.chat.handle_event(event):
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.application_popup is not None:
                if self.opponent_close_button.collidepoint(event.pos):
                    self.application_popup = None
                    return
                if self.opponent_challenge_button.collidepoint(event.pos):
                    self._challenge_selected()
                    return
            if self.application_button.collidepoint(event.pos):
                self._submit_application()
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
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.tavern_button.collidepoint(event.pos):
            self.navigate = "tavern"
            self.finished = True
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
        try:
            if self.chat.my_application is None:
                result = self.session.create_duel_application("backyard")
                self.chat.my_application = result.get("application") or {
                    "sender_id": self.session.character["id"],
                    "sender": self.session.character["name"],
                    "created_at": time.time(),
                    "status": "pending",
                }
                self.error = ""
            else:
                self.session.cancel_duel_application("backyard")
                self.chat.my_application = None
                self.error = ""
        except ServerError as error:
            self.error = str(error)

    def _open_application(self, offer):
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
        screen.fill((22, 29, 25))
        draw_button(screen, self.tavern_button, "ТРАКТИР", self.small_font, color=(110, 75, 50))
        self._draw_applications(screen)
        if self.error:
            draw_text(screen, self.small_font, self.error, 600, 690, (255, 100, 100))
        self.chat.draw(screen)

    def close(self):
        pass

    def _draw_applications(self, screen):
        overlay = pygame.Surface(self.application_frame.size, pygame.SRCALPHA)
        overlay.fill((45, 56, 48, 190))
        screen.blit(overlay, self.application_frame.topleft)
        pygame.draw.rect(screen, (100, 125, 95), self.application_frame, width=2, border_radius=8)
        draw_text(screen, self.font, "ЗАЯВКИ НА ПОЕДИНОК", self.application_frame.x + 25, self.application_frame.y + 20, (255, 220, 120))
        offers = self._application_offers()
        if not offers:
            draw_text(screen, self.small_font, "Активных заявок пока нет", self.application_frame.x + 25, self.application_frame.y + 75, (190, 195, 185))
        for index, offer in enumerate(offers):
            row = pygame.Rect(self.application_frame.x + 25, self.application_frame.y + 75 + index * 42, self.application_frame.width - 50, 34)
            pygame.draw.rect(screen, (35, 42, 38), row, border_radius=5)
            is_own_offer = str(offer.get("sender_id")) == str(self.session.character.get("id"))
            is_new_offer = time.time() - float(offer.get("created_at", 0)) <= 30
            sender_label = offer["sender"]
            if is_own_offer:
                sender_label += " (ваша заявка)"
            elif is_new_offer:
                sender_label += " (новая)"
            sender_color = (255, 235, 150) if is_own_offer or is_new_offer else (230, 235, 225)
            draw_text(screen, self.small_font, sender_label, row.x + 12, row.y + 8, sender_color)
            draw_text(screen, self.small_font, "Нажмите для просмотра", row.right - 190, row.y + 8, (175, 190, 170))
        button_text = "ОТОЗВАТЬ ЗАЯВКУ" if self.chat.my_application is not None else "ПОДАТЬ ЗАЯВКУ"
        button_color = (130, 70, 65) if self.chat.my_application is not None else (150, 95, 55)
        draw_button(screen, self.application_button, button_text, self.small_font, color=button_color)
        if self.chat.my_application is not None:
            seconds_left = max(
                0,
                int(float(self.chat.my_application.get("created_at", time.time())) + settings.DUEL_APPLICATION_TTL_SECONDS - time.time()),
            )
            timer = self.small_font.render(f"Заявка активна: {seconds_left // 60}:{seconds_left % 60:02d}", True, (255, 100, 100))
            timer_rect = timer.get_rect(midtop=(self.application_button.centerx, self.application_button.bottom + 5))
            screen.blit(timer, timer_rect)
        if self.application_popup is not None:
            self._draw_profile_comparison(screen)

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

    def _draw_profile_comparison(self, screen):
        self._draw_profile_card(screen, self.player_profile_frame, self.session.character, "ВАШ ПЕРСОНАЖ", (80, 180, 120))
        self._draw_profile_card(screen, self.opponent_profile_frame, self.application_popup, "СОПЕРНИК", (210, 100, 90))
        draw_button(screen, self.opponent_challenge_button, "БРОСИТЬ ВЫЗОВ", self.small_font, color=(150, 75, 65))
        draw_button(screen, self.opponent_close_button, "ЗАКРЫТЬ", self.small_font, color=(70, 75, 90))

    def _draw_profile_card(self, screen, frame, profile, title, color):
        profile = profile or {}
        overlay = pygame.Surface(frame.size, pygame.SRCALPHA)
        overlay.fill((30, 32, 45, 225))
        screen.blit(overlay, frame.topleft)
        pygame.draw.rect(screen, color, frame, width=2, border_radius=8)

        bar_x = frame.x + 20
        bar_width = 280
        bar_height = 11

        # Единый порядок карточки: ник, уровень, HP, MP, спрайт, характеристики.
        draw_text(screen, self.font, profile.get("name", "Персонаж"), bar_x, frame.y + 20, (240, 240, 245))
        draw_text(screen, self.small_font, f"Уровень {profile.get('level', 1)}", bar_x, frame.y + 52, (210, 215, 225))

        hp_y = frame.y + 100
        mp_y = frame.y + 146
        draw_text(screen, self.small_font, f"HP: {profile.get('hp', 0)}/{profile.get('max_hp', 0)}", bar_x, hp_y - 24, (220, 225, 235))
        draw_bar(
            screen,
            bar_x,
            hp_y,
            bar_width,
            bar_height,
            profile.get("hp", 0),
            profile.get("max_hp", 0),
            fg=(210, 80, 80),
        )
        draw_text(screen, self.small_font, f"MP: {profile.get('mp', 0)}/{profile.get('max_mp', 0)}", bar_x, mp_y - 24, (220, 225, 235))
        draw_bar(
            screen,
            bar_x,
            mp_y,
            bar_width,
            bar_height,
            profile.get("mp", 0),
            profile.get("max_mp", 0),
            fg=(60, 140, 220),
        )

        stats_header_y = frame.bottom - 120
        sprite_center_y = (mp_y + bar_height + stats_header_y) / 2
        sprite_height = self.sprite.image.get_height() * settings.FIGHTER_SPRITE_SCALE if self.sprite.image is not None else 0
        sprite_feet_y = int(sprite_center_y + sprite_height / 2)
        self.sprite.draw(screen, frame.centerx, sprite_feet_y, scale=settings.FIGHTER_SPRITE_SCALE)

        draw_text(screen, self.small_font, "ХАРАКТЕРИСТИКИ", bar_x, stats_header_y, color)
        stat_names = (
            ("strength", "Сила"),
            ("agility", "Ловкость"),
            ("intuition", "Интуиция"),
            ("endurance", "Выносливость"),
        )
        stats = profile.get("stats", {})
        for index, (name, label) in enumerate(stat_names):
            draw_text(
                screen,
                self.small_font,
                f"{label}: {stats.get(name, 0)}",
                bar_x,
                frame.bottom - 92 + index * 20,
                (215, 220, 225),
            )
