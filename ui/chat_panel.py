import pygame

from client.network import ServerError
from core import settings
from client.state import ChatState
from ui.hud import draw_button, draw_text


class ChatPanel:
    def __init__(self, session, location):
        self.session = session
        self.location = location
        self.occupants = []
        self.messages = []
        self.selected = None
        self.popup = False
        self.input_text = ""
        self.error = ""
        self.offers = []
        self.duel_accepted = None
        self.elapsed = 0.0
        self.scale = 1.0
        self.scroll_offset = 0
        self.message_scroll = 0
        self.people_scroll = 0
        self.state = ChatState()
        self.unread = 0
        self.loading = False
        self.send_error = ""
        self.people_line_height = 30
        self.dragging = False
        self.resizing = False
        self.divider_dragging = False
        self.drag_offset = (0, 0)
        self.resize_start = (0, 0)
        self.resize_size = (0, 0)
        self.divider_start = (0, 0)
        self.divider_chat_width = 0
        self._layout()
        self.refresh()

    def _layout(self):
        x = settings.CHAT_PANEL_X
        y = settings.CHAT_PANEL_Y
        width = int(getattr(self, "panel_width", settings.CHAT_PANEL_WIDTH) * self.scale)
        height = int(getattr(self, "panel_height", settings.CHAT_PANEL_HEIGHT) * self.scale)
        people_width = int(getattr(self, "people_width", settings.CHAT_PEOPLE_WIDTH) * self.scale)
        people_width = max(
            int(settings.CHAT_MIN_PEOPLE_WIDTH * self.scale),
            min(
                people_width,
                width - int(settings.CHAT_MIN_CHAT_WIDTH * self.scale),
            ),
        )
        self.panel_rect = pygame.Rect(x, y, width, height)
        self.chat_rect = pygame.Rect(
            x,
            y,
            width - people_width,
            height,
        )
        self.people_rect = pygame.Rect(
            x + width - people_width,
            y,
            people_width,
            height,
        )
        popup_x = 670
        popup_y = 470
        self.close_rect = pygame.Rect(popup_x + 540, popup_y + 10, 45, 32)
        self.send_rect = pygame.Rect(popup_x + 20, popup_y + 195, 140, 40)
        self.trade_rect = pygame.Rect(popup_x + 170, popup_y + 195, 185, 40)
        self.duel_rect = pygame.Rect(popup_x + 365, popup_y + 195, 210, 40)
        action_y = self.panel_rect.bottom - 48
        self.application_rect = pygame.Rect(self.chat_rect.x + 15, action_y, 230, 40)
        self.accept_rect = pygame.Rect(self.chat_rect.x + 255, action_y, 135, 40)
        self.decline_rect = pygame.Rect(self.chat_rect.x + 400, action_y, 135, 40)
        self.move_rect = pygame.Rect(self.panel_rect.x, self.panel_rect.y, self.panel_rect.width, 28)
        self.resize_rect = pygame.Rect(self.panel_rect.right - 18, self.panel_rect.bottom - 18, 18, 18)
        self.divider_rect = pygame.Rect(self.people_rect.x - 8, y + 28, 16, height - 46)

    def refresh(self):
        try:
            self.session.update_presence(self.location)
            self.state.connection_status = "connected"
            self.occupants = self.session.list_occupants(self.location)
            self.occupants.sort(key=lambda occupant: occupant.get("name", "").casefold())
            self.messages = self.session.list_messages(self.location)
            self.state.replace_messages(self.location, self.messages)
            self.messages = self.state.messages_by_channel[self.location]
            self.unread = self.session.unread_count(self.location)
            if self.messages:
                self.session.mark_chat_read(self.location, self.messages[-1]["id"])
                self.unread = 0
                visible_height = self.chat_rect.height - 65
                max_scroll = max(0, len(self.messages) * 32 - visible_height)
                self.message_scroll = max_scroll
            self.offers = self.session.list_duel_offers(self.location)
            self.error = ""
        except ServerError as error:
            self.error = str(error)
            self.state.connection_status = "disconnected"

    def update(self, dt):
        self.elapsed += dt
        if self.elapsed >= 2.0:
            self.elapsed = 0.0
            self.refresh()

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL and not self.popup:
            mouse_pos = pygame.mouse.get_pos()
            if self.chat_rect.collidepoint(mouse_pos):
                self.message_scroll = max(0, self.message_scroll - event.y * 2)
                return True
            if self.people_rect.collidepoint(mouse_pos):
                max_scroll = max(
                    0,
                    len(self.occupants) * self.people_line_height
                    - (self.people_rect.height - 55),
                )
                self.people_scroll = max(
                    0,
                    min(max_scroll, self.people_scroll - event.y * 2),
                )
                return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not self.popup:
            if self.divider_rect.collidepoint(event.pos):
                self.divider_dragging = True
                self.divider_start = event.pos
                self.divider_chat_width = self.chat_rect.width
                return True
            if self.resize_rect.collidepoint(event.pos):
                self.resizing = True
                self.resize_start = event.pos
                self.resize_size = (
                    getattr(self, "panel_width", settings.CHAT_PANEL_WIDTH),
                    getattr(self, "panel_height", settings.CHAT_PANEL_HEIGHT),
                )
                return True
            if self.move_rect.collidepoint(event.pos):
                self.dragging = True
                self.drag_offset = (
                    event.pos[0] - self.panel_rect.x,
                    event.pos[1] - self.panel_rect.y,
                )
                return True
        if event.type == pygame.MOUSEMOTION:
            if self.divider_dragging:
                divider_delta = event.pos[0] - self.divider_start[0]
                chat_width = max(
                    int(settings.CHAT_MIN_CHAT_WIDTH * self.scale),
                    min(
                        self.panel_rect.width - int(settings.CHAT_MIN_PEOPLE_WIDTH * self.scale),
                        self.divider_chat_width + divider_delta,
                    ),
                )
                self.people_width = (self.panel_rect.width - chat_width) / self.scale
                self._layout()
                return True
            if self.dragging:
                settings.CHAT_PANEL_X = max(0, event.pos[0] - self.drag_offset[0])
                settings.CHAT_PANEL_Y = max(0, event.pos[1] - self.drag_offset[1])
                self._layout()
                return True
            if self.resizing:
                self.panel_width = max(700, self.resize_size[0] + event.pos[0] - self.resize_start[0])
                self.panel_height = max(180, self.resize_size[1] + event.pos[1] - self.resize_start[1])
                self._layout()
                return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging or self.resizing or self.divider_dragging:
                self.dragging = False
                self.resizing = False
                self.divider_dragging = False
                return True
        if event.type == pygame.KEYDOWN and event.mod & pygame.KMOD_CTRL:
            if event.key == pygame.K_LEFT:
                settings.CHAT_PANEL_X -= 10
                self._layout()
            elif event.key == pygame.K_RIGHT:
                settings.CHAT_PANEL_X += 10
                self._layout()
            elif event.key == pygame.K_UP:
                settings.CHAT_PANEL_Y -= 10
                self._layout()
            elif event.key == pygame.K_DOWN:
                settings.CHAT_PANEL_Y += 10
                self._layout()
            elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self.scale = max(settings.CHAT_MIN_SCALE, self.scale - settings.CHAT_SCALE_STEP)
                self._layout()
            elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                self.scale = min(settings.CHAT_MAX_SCALE, self.scale + settings.CHAT_SCALE_STEP)
                self._layout()
            else:
                return False
            return True
        if event.type == pygame.TEXTINPUT and self.popup:
            if len(self.input_text) < 300:
                self.input_text += event.text
            return True
        if event.type == pygame.KEYDOWN and self.popup:
            if event.key == pygame.K_BACKSPACE:
                self.input_text = self.input_text[:-1]
            elif event.key == pygame.K_RETURN:
                self.send_private()
            elif event.key == pygame.K_ESCAPE:
                self.popup = False
            return True
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False

        if self.popup and self.selected is not None:
            if self.close_rect.collidepoint(event.pos):
                self.popup = False
                self.selected = None
                self.input_text = ""
                return True
            if self.send_rect.collidepoint(event.pos):
                self.send_private()
                return True
            if self.duel_rect.collidepoint(event.pos):
                self.offer_duel()
                return True
            if self.trade_rect.collidepoint(event.pos):
                self.error = "Обмен предметами будет добавлен позже"
                return True

        if self.location == "backyard" and self.application_rect.collidepoint(event.pos):
            try:
                self.session.create_duel_application(self.location)
                self.error = "Заявка на поединок опубликована на 2 минуты"
                self.refresh()
            except ServerError as error:
                self.error = str(error)
            return True

        if self.offers:
            if self.accept_rect.collidepoint(event.pos):
                offer = self.offers[0]
                self.session.respond_duel_offer(offer["id"], True)
                self.duel_accepted = next(
                    (item for item in self.occupants if item.get("character_id") == offer["sender_id"]),
                    None,
                )
                self.refresh()
                return True
            if self.decline_rect.collidepoint(event.pos):
                self.session.respond_duel_offer(self.offers[0]["id"], False)
                self.refresh()
                return True

        for index, occupant in enumerate(self.occupants):
            rect = pygame.Rect(
                self.people_rect.x + 15,
                self.people_rect.y + 35 + index * self.people_line_height - self.people_scroll,
                max(1, self.people_rect.width - 30),
                26,
            )
            if rect.collidepoint(event.pos):
                self.selected = occupant
                self.popup = True
                self.input_text = ""
                return True
        return False

    def send_private(self):
        if self.selected is None or not self.input_text.strip():
            return
        try:
            self.session.send_message(self.location, self.input_text.strip(), self.selected.get("character_id"))
            self.input_text = ""
            self.refresh()
        except ServerError as error:
            self.send_error = str(error)
            self.error = self.send_error

    def offer_duel(self):
        if self.selected is None or self.location != "backyard":
            return
        try:
            result = self.session.offer_duel(self.location, self.selected.get("character_id"))
            if not result.get("accepted", False):
                self.error = result.get("message", "Соперник отказался от боя")
            else:
                self.error = "Соперник принял предложение"
                self.duel_accepted = self.selected
        except ServerError as error:
            self.error = str(error)

    def draw(self, screen):
        pygame.draw.rect(screen, (25, 27, 38), self.panel_rect, border_radius=8)
        pygame.draw.rect(screen, (60, 65, 80), self.panel_rect, width=2, border_radius=8)
        pygame.draw.rect(screen, (100, 105, 125), self.resize_rect, border_radius=3)
        pygame.draw.line(
            screen,
            (60, 65, 80),
            (self.people_rect.x, self.panel_rect.y),
            (self.people_rect.x, self.panel_rect.bottom),
            2,
        )
        draw_text(screen, pygame.font.SysFont("arial", 18), "ЧАТ ЛОКАЦИИ", self.chat_rect.x + 15, self.chat_rect.y + 10, (255, 220, 120))
        draw_text(screen, pygame.font.SysFont("arial", 18), "ПЕРСОНАЖИ В ЛОКАЦИИ", self.people_rect.x + 15, self.people_rect.y + 10, (255, 220, 120))
        previous_clip = screen.get_clip()
        screen.set_clip(self.panel_rect)
        y = self.chat_rect.y + 38 - self.message_scroll
        for message in self.messages[-50:]:
            prefix = f"{message['sender']}: "
            draw_text(screen, pygame.font.SysFont("arial", 16), prefix + message["text"], self.chat_rect.x + 15, y, (220, 220, 225))
            y += 32
        hovered = None
        mouse_pos = pygame.mouse.get_pos()
        for index, occupant in enumerate(self.occupants):
            name = occupant["name"]
            rect = pygame.Rect(
                self.people_rect.x + 15,
                self.people_rect.y + 35 + index * self.people_line_height - self.people_scroll,
                max(1, self.people_rect.width - 30),
                26,
            )
            color = (255, 220, 120) if occupant is self.selected else (210, 215, 225)
            draw_text(screen, pygame.font.SysFont("arial", 18), name, rect.x, rect.y, color)
            if rect.collidepoint(mouse_pos):
                hovered = occupant
        screen.set_clip(previous_clip)
        if hovered is not None and not self.popup:
            self._draw_profile_tooltip(screen, hovered, mouse_pos)
        if self.error:
            draw_text(screen, pygame.font.SysFont("arial", 16), self.error, self.chat_rect.x + 15, self.chat_rect.bottom - 28, (255, 120, 100))
        if self.offers:
            draw_text(screen, pygame.font.SysFont("arial", 16), f"Заявка на бой: {self.offers[0]['sender']}", self.chat_rect.x + 15, self.panel_rect.bottom - 78, (255, 190, 120))
            draw_button(screen, self.accept_rect, "ПРИНЯТЬ", pygame.font.SysFont("arial", 16), color=(70, 140, 90))
            draw_button(screen, self.decline_rect, "ОТКАЗАТЬ", pygame.font.SysFont("arial", 16), color=(130, 70, 65))
        if self.location == "backyard":
            draw_button(screen, self.application_rect, "ПОДАТЬ ЗАЯВКУ НА БОЙ", pygame.font.SysFont("arial", 16), color=(150, 95, 55))
        if self.popup and self.selected is not None:
            self._draw_popup(screen)

    def _draw_box(self, screen, rect, title):
        pygame.draw.rect(screen, (25, 27, 38), rect, border_radius=8)
        pygame.draw.rect(screen, (60, 65, 80), rect, width=2, border_radius=8)
        draw_text(screen, pygame.font.SysFont("arial", 18), title, rect.x + 15, rect.y + 10, (255, 220, 120))

    def _draw_popup(self, screen):
        rect = pygame.Rect(670, 470, 600, 250)
        pygame.draw.rect(screen, (30, 32, 45), rect, border_radius=8)
        pygame.draw.rect(screen, (100, 105, 125), rect, width=2, border_radius=8)
        target = self.selected
        draw_button(screen, self.close_rect, "X", pygame.font.SysFont("arial", 16), color=(130, 70, 65))
        draw_text(screen, pygame.font.SysFont("arial", 20), target["name"], rect.x + 20, rect.y + 18, (240, 240, 245))
        stats = target.get("stats", {})
        draw_text(screen, pygame.font.SysFont("arial", 16), f"HP: {target.get('hp', 0)}/{target.get('max_hp', 0)}", rect.x + 20, rect.y + 55, (220, 220, 225))
        draw_text(screen, pygame.font.SysFont("arial", 16), " ".join(f"{key}: {value}" for key, value in stats.items()), rect.x + 20, rect.y + 82, (200, 205, 215))
        if target.get("kind") == "npc" or target.get("character_id") == self.session.character.get("id"):
            draw_text(screen, pygame.font.SysFont("arial", 16), "Выберите действие", rect.x + 20, rect.y + 125, (190, 195, 205))
        pygame.draw.rect(screen, (28, 30, 43), (rect.x + 20, rect.y + 155, 380, 38), border_radius=5)
        draw_text(screen, pygame.font.SysFont("arial", 16), self.input_text, rect.x + 28, rect.y + 165, (240, 240, 245))
        draw_button(screen, self.send_rect, "ОТПРАВИТЬ", pygame.font.SysFont("arial", 16), color=(70, 140, 220))
        draw_button(screen, self.trade_rect, "ПРЕДЛОЖИТЬ ОБМЕН", pygame.font.SysFont("arial", 16), color=(110, 100, 70))
        if self.location == "backyard" and target.get("kind") != "npc":
            draw_button(screen, self.duel_rect, "ПРЕДЛОЖИТЬ ПОЕДИНОК", pygame.font.SysFont("arial", 16), color=(150, 75, 65))

    def _draw_profile_tooltip(self, screen, target, mouse_pos):
        rect = pygame.Rect(mouse_pos[0] - 330, mouse_pos[1] - 145, 320, 125)
        rect.x = max(10, min(rect.x, screen.get_width() - rect.width - 10))
        rect.y = max(10, rect.y)
        pygame.draw.rect(screen, (30, 32, 45), rect, border_radius=6)
        pygame.draw.rect(screen, (100, 105, 125), rect, width=2, border_radius=6)
        draw_text(screen, pygame.font.SysFont("arial", 17), target["name"], rect.x + 12, rect.y + 10, (240, 240, 245))
        draw_text(screen, pygame.font.SysFont("arial", 15), f"HP: {target.get('hp', 0)}/{target.get('max_hp', 0)}", rect.x + 12, rect.y + 40, (220, 225, 235))
        stats = target.get("stats", {})
        draw_text(screen, pygame.font.SysFont("arial", 14), " ".join(f"{key}: {value}" for key, value in stats.items()), rect.x + 12, rect.y + 68, (200, 205, 215))
