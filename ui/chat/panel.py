import pygame
import time

from client.network import ServerError
from client.background_polling import BackgroundPoller
from core import settings
from ui.chat.widgets import ChannelList, ChatHeader, MessageInput, MessageList, UnreadBadge
from ui.hud import draw_button, draw_text


class ChatPanel:
    ROOM_NAMES = {
        "tavern": "ТРАКТИР",
        "backyard": "ЗАДНИЙ ДВОР",
    }

    def __init__(self, session, location, battle_source=None, profile_overlay=None):
        self.session = session
        self.location = location
        self.battle_source = battle_source
        # Единственная карточка профиля: чат не владеет собственным отдельным попапом.
        self.profile_overlay = profile_overlay
        self.collapsed = False
        self.channel = "Общий"
        self.occupants = []
        self.messages = []
        self.offers = []
        self.group_offers = []
        self.my_application = None
        self.private_target = None
        self.duel_accepted = None
        self.last_character_click = 0
        self.last_character_position = None
        self.people_scroll = 0
        self.error = ""
        self.elapsed = 0.0
        self.background_poller = None
        self.panel_rect = pygame.Rect(settings.CHAT_PANEL_X, settings.CHAT_PANEL_Y, settings.CHAT_PANEL_WIDTH, settings.CHAT_PANEL_HEIGHT)
        self.toggle_rect = pygame.Rect(self.panel_rect.right - 116, self.panel_rect.y + 9, 104, 26)
        self.divider_x = self.panel_rect.right - settings.CHAT_PEOPLE_WIDTH - settings.CHAT_DIVIDER_GAP * 2 - settings.CHAT_DIVIDER_WIDTH
        self.dragging_divider = False
        self._layout_widgets()
        self.unread_badge = UnreadBadge()
        if hasattr(session, "client"):
            self.background_poller = BackgroundPoller(self._fetch_remote_state)
            self.background_poller.start()
        else:
            self.refresh()

    @property
    def room_name(self):
        return self.ROOM_NAMES.get(self.location, self.location.upper())

    def _layout_widgets(self):
        content_y = self.panel_rect.y + 58
        input_y = self.panel_rect.bottom - 35
        content_height = max(80, input_y - content_y - 10)
        message_x = self.panel_rect.x + 12
        self.divider_x = self._clamp_divider_x(self.divider_x)
        self.divider_rect = pygame.Rect(
            self.divider_x,
            content_y,
            settings.CHAT_DIVIDER_WIDTH,
            content_height,
        )
        people_x = self.divider_rect.right + settings.CHAT_DIVIDER_GAP
        people_width = self.panel_rect.right - settings.CHAT_DIVIDER_GAP - people_x
        message_right = self.divider_rect.left - settings.CHAT_DIVIDER_GAP
        message_width = message_right - message_x
        font_header = pygame.font.SysFont("arial", 12)
        font_channel = pygame.font.SysFont("arial", 14)
        font_message = pygame.font.SysFont("arial", 15)
        self.header = ChatHeader(self.panel_rect, font_header)
        self.channels = ChannelList(
            pygame.Rect(self.panel_rect.x + 12, self.panel_rect.y + 10, 220, 25),
            font_channel,
        )
        input_rect = pygame.Rect(self.panel_rect.x + 5, input_y, message_right - self.panel_rect.x - 5, 25)
        message_rect = pygame.Rect(message_x, content_y, message_width, content_height)
        if hasattr(self, "message_input"):
            self.message_input.set_rect(input_rect)
            self.message_list.set_rect(message_rect)
        else:
            self.message_input = MessageInput(input_rect, pygame.font.SysFont("arial", 15))
            self.message_list = MessageList(message_rect, font_message)
        self.people_rect = pygame.Rect(
            people_x,
            content_y,
            people_width,
            content_height,
        )

    def _clamp_divider_x(self, divider_x):
        minimum_x = self.panel_rect.x + 12 + settings.CHAT_MIN_CHAT_WIDTH + settings.CHAT_DIVIDER_GAP
        maximum_x = self.panel_rect.right - settings.CHAT_DIVIDER_GAP - settings.CHAT_MIN_PEOPLE_WIDTH - settings.CHAT_DIVIDER_GAP - settings.CHAT_DIVIDER_WIDTH
        return max(minimum_x, min(maximum_x, int(divider_x)))

    def _move_divider(self, mouse_x):
        self.divider_x = self._clamp_divider_x(mouse_x - settings.CHAT_DIVIDER_WIDTH // 2)
        self._layout_widgets()

    def refresh(self):
        state, error = self._fetch_remote_state_with_error()
        if error is not None:
            self.error = str(error)
            return
        self._apply_remote_state(state)

    def _fetch_remote_state(self):
        state, error = self._fetch_remote_state_with_error()
        if error is not None:
            raise error
        return state

    def _fetch_remote_state_with_error(self):
        try:
            if hasattr(self.session, "social_snapshot"):
                return self.session.social_snapshot(self.location), None
            self.session.update_presence(self.location)
            occupants = sorted(self.session.list_occupants(self.location), key=lambda item: item.get("name", "").casefold())
            messages = self.session.list_messages(self.location)
            board = self.session.duel_board(self.location)
            return {"occupants": occupants, "messages": messages, "offers": board.get("offers", []), "my_application": board.get("my_application")}, None
        except ServerError as error:
            return None, error

    def _apply_remote_state(self, state):
        self.occupants = state["occupants"]
        self.messages = state["messages"]
        self.message_list.set_messages(self._visible_messages())
        self.offers = state["offers"]
        self.group_offers = state.get("group_offers", [])
        server_application = state["my_application"]
        if server_application is not None and server_application.get("status") == "accepted" and self.duel_accepted is None:
            self._resolve_application_opponent(server_application)
        self.my_application = server_application if server_application is not None and server_application.get("status") == "pending" else None
        self.error = ""

    def _resolve_application_opponent(self, application):
        """Заявка игрока была принята (например, ботом по истечении срока ожидания) — запускаем бой."""
        accepted_by = application.get("accepted_by")
        opponent = next(
            (item for item in self.occupants if str(item.get("character_id")) == str(accepted_by)),
            None,
        )
        if opponent is not None:
            self.duel_accepted = opponent

    def _clear_expired_application(self):
        if self.my_application is None or self.my_application.get("status", "pending") != "pending":
            return
        created_at = float(self.my_application.get("created_at", 0))
        ttl = float(self.my_application.get("ttl", settings.DUEL_APPLICATION_TTL_SECONDS))
        if time.time() >= created_at + ttl:
            self.my_application = None

    def update(self, dt):
        self._clear_expired_application()
        self.message_input.update(dt)
        if self.background_poller is not None:
            state, error = self.background_poller.poll()
            if error is not None:
                self.error = str(error)
            elif state is not None:
                self._apply_remote_state(state)
            return
        self.elapsed += dt
        if self.elapsed >= 2:
            self.elapsed = 0
            self.refresh()

    def handle_event(self, event):
        if pygame.display.get_surface() is not None:
            screen = pygame.display.get_surface()
            if self.collapsed:
                self.toggle_rect = pygame.Rect(screen.get_width() - 80, screen.get_height() - 25, 70, 25)
            else:
                self.toggle_rect = pygame.Rect(self.panel_rect.right - 80, self.panel_rect.bottom - 30, 70, 25)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.toggle_rect.collidepoint(event.pos):
            self.collapsed = not self.collapsed
            if not self.collapsed:
                self.message_list.set_messages(self._visible_messages())
            return True
        if event.type == pygame.MOUSEMOTION and self.dragging_divider:
            self._move_divider(event.pos[0])
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging_divider:
            self.dragging_divider = False
            return True
        if event.type == pygame.MOUSEWHEEL and not self.collapsed:
            if self.message_list.rect.collidepoint(pygame.mouse.get_pos()):
                self.message_list.wheel(event.y)
                return True
            if self.people_rect.collidepoint(pygame.mouse.get_pos()):
                row_height = 28
                visible_rows = max(1, self.people_rect.height // row_height)
                max_scroll = max(0, len(self.occupants) - visible_rows)
                self.people_scroll = max(0, min(max_scroll, self.people_scroll - event.y))
                return True
        if event.type == pygame.KEYDOWN and not self.collapsed:
            result = self.message_input.handle_event(event)
            if result == "send":
                self.send_message()
                return True
            if result:
                return True
        if event.type == pygame.TEXTINPUT and not self.collapsed:
            return self.message_input.handle_event(event)
        if event.type != pygame.MOUSEBUTTONDOWN:
            return False
        if self.collapsed:
            return False
        if event.button == 1 and self.divider_rect.inflate(6, 0).collidepoint(event.pos):
            self.dragging_divider = True
            return True
        row_height = 28
        visible_rows = max(1, self.people_rect.height // row_height)
        for visible_index, occupant in enumerate(self.occupants[self.people_scroll:self.people_scroll + visible_rows]):
            rect = pygame.Rect(self.people_rect.x, self.people_rect.y + visible_index * row_height, self.people_rect.width, 25)
            if rect.collidepoint(event.pos):
                if event.button == 3 and self.profile_overlay is not None:
                    self.profile_overlay.open(occupant, counterpart=self.session.character)
                elif event.button == 1 and self._is_double_character_click(event.pos):
                    self.private_target = occupant
                    self.channel = "Личные"
                    self.message_list.set_messages(self._visible_messages())
                return True

        if event.button != 1:
            return False
        for index, channel in enumerate(self.channels.channels):
            rect = pygame.Rect(
                self.channels.rect.x + index * 75,
                self.channels.rect.y,
                70,
                25,
            )
            if rect.collidepoint(event.pos):
                self.channel = channel
                self.message_list.set_messages(self._visible_messages())
                return True
        if self.message_input.send_rect.collidepoint(event.pos):
            self.send_message()
            self.message_input.focused = False
            return True
        if self.message_input.rect.collidepoint(event.pos):
            self.message_input.focused = True
            return True
        return False

    def _challenge_bot(self, bot):
        try:
            result = self.session.offer_duel(self.location, bot.get("character_id"))
            if result.get("accepted"):
                self.duel_accepted = bot
            else:
                self.error = result.get("message", "Бот не принял вызов")
        except ServerError as error:
            self.error = str(error)

    def _is_double_character_click(self, position):
        now = pygame.time.get_ticks()
        is_double = (
            now - self.last_character_click <= 400
            and self.last_character_position == position
        )
        self.last_character_click = now
        self.last_character_position = position
        return is_double

    def send_message(self):
        if self.channel == "Личные" and self.private_target is None:
            self.error = "Сначала выберите персонажа двойным левым кликом"
            return
        if self.channel == "Лог боя":
            self.error = "В лог боя нельзя отправлять сообщения"
            return
        text = self.message_input.text.strip()
        if not text:
            self.error = "Сообщение не может быть пустым"
            return
        try:
            recipient_id = None
            if self.channel == "Личные":
                recipient_id = self.private_target.get("character_id")
            self.session.send_message(self.location, text, recipient_id)
            self.message_input.text = ""
            self.refresh()
        except ServerError as error:
            self.error = str(error)

    def close(self):
        if self.background_poller is not None:
            self.background_poller.stop()

    def _visible_messages(self):
        if self.channel == "Общий":
            return self.messages
        if self.channel == "Лог боя" and self.battle_source is not None:
            result = []
            for index, comment in enumerate(self.battle_source.comments):
                segments = comment.get("segments", [])
                if segments:
                    result.append({
                        "id": f"battle-{index}",
                        "sender_id": "commentator",
                        "sender": "Комментатор",
                        "segments": [
                            {"text": "Комментатор: ", "color": (170, 170, 170)},
                            *segments,
                        ],
                        "created_at": index,
                    })
            return result
        return []

    def draw(self, screen):
        if self.collapsed:
            self.toggle_rect = pygame.Rect(screen.get_width() - 80, screen.get_height() - 25, 70, 25)
            draw_button(screen, self.toggle_rect, "ЛОГ БОЯ", pygame.font.SysFont("arial", 12), color=(75, 105, 155))
            return
        pygame.draw.rect(screen, (25, 27, 38), self.panel_rect, border_radius=8)
        pygame.draw.rect(screen, (60, 65, 80), self.panel_rect, width=2, border_radius=8)
        self.toggle_rect = pygame.Rect(self.panel_rect.right - 80, self.panel_rect.bottom - 30, 70, 25)
        draw_button(screen, self.toggle_rect, "СВЕРНУТЬ", pygame.font.SysFont("arial", 13), color=(75, 105, 155))
        divider_color = (120, 170, 230) if self.dragging_divider or self.divider_rect.inflate(6, 0).collidepoint(pygame.mouse.get_pos()) else (60, 65, 80)
        pygame.draw.rect(screen, divider_color, self.divider_rect, border_radius=3)
        self.channels.draw(screen, self.channel, {"Общий": 0, "Личные": 0})
        own_id = self.session.character["id"] if self.session.character else None
        self.message_list.draw(screen, own_id)
        self.message_input.draw(screen)
        people_x = self.people_rect.x
        draw_text(screen, pygame.font.SysFont("arial", 17), self.room_name, people_x, self.panel_rect.y + 14, (255, 220, 120))
        previous_clip = screen.get_clip()
        track_rect = pygame.Rect(self.people_rect.right - 8, self.people_rect.y + 4, 4, self.people_rect.height - 8)
        pygame.draw.rect(screen, (50, 55, 66), track_rect, border_radius=3)
        row_height = 28
        visible_rows = max(1, self.people_rect.height // row_height)
        max_scroll = max(0, len(self.occupants) - visible_rows)
        self.people_scroll = max(0, min(max_scroll, self.people_scroll))
        if max_scroll:
            thumb_height = max(18, int((visible_rows / max(1, len(self.occupants))) * (self.people_rect.height - 14)))
            thumb_y = self.people_rect.y + 7 + int(self.people_scroll / max_scroll * (self.people_rect.height - 14 - thumb_height))
            thumb = pygame.Rect(self.people_rect.right - 8, thumb_y, 4, thumb_height)
            pygame.draw.rect(screen, (170, 180, 210), thumb, border_radius=3)
        screen.set_clip(self.people_rect.inflate(-12, 0))
        for visible_index, occupant in enumerate(self.occupants[self.people_scroll:self.people_scroll + visible_rows]):
            draw_text(
                screen,
                pygame.font.SysFont("arial", 16),
                occupant.get("name", ""),
                people_x + settings.CHAT_PEOPLE_TEXT_LEFT_PADDING,
                self.people_rect.y + visible_index * row_height + 4,
                (215, 215, 225),
            )
        screen.set_clip(previous_clip)
        if self.error:
            draw_text(screen, pygame.font.SysFont("arial", 14), self.error, self.panel_rect.x + 12, self.panel_rect.bottom - 20, (255, 120, 100))
