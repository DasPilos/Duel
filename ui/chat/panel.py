import pygame
import time

from client.network import ServerError
from core import settings
from ui.chat.widgets import ChannelList, ChatHeader, MessageInput, MessageList, UnreadBadge
from ui.hud import draw_bar, draw_button, draw_text
from ui.sprite_loader import FighterSprite


class ChatPanel:
    ROOM_NAMES = {
        "tavern": "ТРАКТИР",
        "backyard": "ЗАДНИЙ ДВОР",
    }

    def __init__(self, session, location, battle_source=None):
        self.session = session
        self.location = location
        self.battle_source = battle_source
        self.collapsed = False
        self.channel = "Общий"
        self.occupants = []
        self.messages = []
        self.offers = []
        self.my_application = None
        self.selected = None
        self.private_target = None
        self.profile_open = False
        self.duel_accepted = None
        self.last_character_click = 0
        self.last_character_position = None
        self.error = ""
        self.elapsed = 0.0
        self.fighter_sprite = FighterSprite()
        self.panel_rect = pygame.Rect(settings.CHAT_PANEL_X, settings.CHAT_PANEL_Y, settings.CHAT_PANEL_WIDTH, settings.CHAT_PANEL_HEIGHT)
        self._layout_widgets()
        self.unread_badge = UnreadBadge()
        self.refresh()

    @property
    def room_name(self):
        return self.ROOM_NAMES.get(self.location, self.location.upper())

    def _layout_widgets(self):
        channel_width = 120
        people_width = 150
        gap = 15
        content_y = self.panel_rect.y + 58
        content_height = self.panel_rect.height - 110
        message_x = self.panel_rect.x + 12
        people_x = self.panel_rect.right - people_width - gap
        message_width = people_x - message_x - gap
        font_header = pygame.font.SysFont("arial", 12)
        font_channel = pygame.font.SysFont("arial", 14)
        font_message = pygame.font.SysFont("arial", 15)
        self.header = ChatHeader(self.panel_rect, font_header)
        self.channels = ChannelList(
            pygame.Rect(self.panel_rect.x + 12, self.panel_rect.y + 10, 220, 25),
            font_channel,
        )
        self.message_list = MessageList(
            pygame.Rect(message_x, content_y, max(240, message_width), content_height),
            font_message,
        )
        self.message_input = MessageInput(
            pygame.Rect(
                self.panel_rect.x + 5,
                self.panel_rect.bottom - 30,
                max(240, people_x - self.panel_rect.x - 10),
                25,
            ),
            pygame.font.SysFont("arial", 15),
        )
        self.people_rect = pygame.Rect(
            people_x,
            content_y,
            people_width,
            content_height,
        )

    def refresh(self):
        try:
            self.session.update_presence(self.location)
            self.occupants = sorted(self.session.list_occupants(self.location), key=lambda item: item.get("name", "").casefold())
            self.messages = self.session.list_messages(self.location)
            self.message_list.set_messages(self._visible_messages())
            board = self.session.duel_board(self.location)
            self.offers = board.get("offers", [])
            server_application = board.get("my_application")
            if server_application is not None:
                self.my_application = server_application
            elif self.my_application is not None:
                created_at = float(self.my_application.get("created_at", 0))
                if time.time() - created_at >= settings.DUEL_APPLICATION_TTL_SECONDS:
                    self.my_application = None
            self.error = ""
        except ServerError as error:
            self.error = str(error)

    def update(self, dt):
        self.message_input.update(dt)
        self.elapsed += dt
        if self.elapsed >= 2:
            self.elapsed = 0
            self.refresh()

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL and not self.collapsed:
            if self.message_list.rect.collidepoint(pygame.mouse.get_pos()):
                self.message_list.wheel(event.y)
                return True
        if event.type == pygame.KEYDOWN and not self.collapsed:
            result = self.message_input.handle_event(event)
            if result == "send":
                self.send_message()
                return True
            if result:
                return True
            if event.key == pygame.K_ESCAPE and self.profile_open:
                self.profile_open = False
                self.selected = None
                return True
        if event.type == pygame.TEXTINPUT and not self.collapsed:
            return self.message_input.handle_event(event)
        if event.type != pygame.MOUSEBUTTONDOWN:
            return False
        if self.profile_open and self.selected is not None:
            profile_close = self._profile_close_rect()
            if profile_close.collidepoint(event.pos):
                self.profile_open = False
                self.selected = None
                return True
        if self.collapsed:
            return False
        for index, occupant in enumerate(self.occupants):
            rect = pygame.Rect(self.people_rect.x, self.people_rect.y + index * 28, self.people_rect.width, 25)
            if rect.collidepoint(event.pos):
                self.selected = occupant
                if event.button == 3:
                    self.profile_open = True
                elif event.button == 1 and occupant.get("kind") == "bot" and self.location == "backyard":
                    self._challenge_bot(occupant)
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
            pygame.draw.rect(screen, (25, 27, 38), pygame.Rect(self.panel_rect.x, self.panel_rect.y, self.panel_rect.width, 44), border_radius=8)
            self.header.draw(screen, self.location, True)
            return
        pygame.draw.rect(screen, (25, 27, 38), self.panel_rect, border_radius=8)
        pygame.draw.rect(screen, (60, 65, 80), self.panel_rect, width=2, border_radius=8)
        pygame.draw.line(screen, (60, 65, 80), (self.people_rect.x - 8, self.panel_rect.y), (self.people_rect.x - 8, self.panel_rect.bottom), 2)
        self.channels.draw(screen, self.channel, {"Общий": 0, "Личные": 0})
        own_id = self.session.character["id"] if self.session.character else None
        self.message_list.draw(screen, own_id)
        self.message_input.draw(screen)
        people_x = self.people_rect.x
        draw_text(screen, pygame.font.SysFont("arial", 17), self.room_name, people_x, self.panel_rect.y + 14, (255, 220, 120))
        for index, occupant in enumerate(self.occupants):
            draw_text(screen, pygame.font.SysFont("arial", 16), occupant.get("name", ""), people_x, self.people_rect.y + index * 28, (215, 215, 225))
        if self.error:
            draw_text(screen, pygame.font.SysFont("arial", 14), self.error, self.panel_rect.x + 12, self.panel_rect.bottom - 20, (255, 120, 100))
        if self.profile_open and self.selected is not None:
            self.draw_profile(screen)

    def draw_profile(self, screen):
        rect = self._profile_rect(screen)
        pygame.draw.rect(screen, (30, 32, 45), rect, border_radius=8)
        pygame.draw.rect(screen, (100, 105, 125), rect, width=2, border_radius=8)
        target = self.selected
        name_font = pygame.font.SysFont("arial", 24)
        info_font = pygame.font.SysFont("arial", 16)
        draw_text(screen, name_font, target.get("name", ""), rect.x + 20, rect.y + 18, (240, 240, 245))
        draw_text(screen, info_font, f"Уровень {target.get('level', 1)}", rect.x + 20, rect.y + 55, (210, 215, 225))
        hp = target.get("hp", 0)
        max_hp = target.get("max_hp", 0)
        mp = target.get("mp", 0)
        max_mp = target.get("max_mp", 0)
        draw_text(screen, info_font, f"HP: {hp}/{max_hp}", rect.x + 20, rect.y + 82, (220, 225, 235))
        draw_bar(screen, rect.x + 20, rect.y + 106, 280, 12, hp, max_hp, fg=(210, 80, 80))
        draw_text(screen, info_font, f"MP: {mp}/{max_mp}", rect.x + 20, rect.y + 130, (220, 225, 235))
        draw_bar(screen, rect.x + 20, rect.y + 154, 280, 12, mp, max_mp, fg=(60, 140, 220))
        self.fighter_sprite.draw(screen, rect.x + 160, rect.y + 282, scale=settings.FIGHTER_SPRITE_SCALE)
        draw_text(screen, info_font, "ХАРАКТЕРИСТИКИ", rect.x + 350, rect.y + 82, (210, 100, 90))
        stats = target.get("stats", {})
        for index, (key, label) in enumerate((("strength", "Сила"), ("agility", "Ловкость"), ("intuition", "Интуиция"), ("endurance", "Выносливость"))):
            draw_text(screen, info_font, f"{label}: {stats.get(key, 0)}", rect.x + 350, rect.y + 114 + index * 28, (215, 220, 225))
        draw_button(screen, self._profile_close_rect(screen), "X", info_font, color=(130, 70, 65))

    @staticmethod
    def _profile_rect(screen=None):
        screen_width = screen.get_width() if screen is not None else settings.WIDTH
        return pygame.Rect(screen_width - 620, 450, 600, 310)

    @classmethod
    def _profile_close_rect(cls, screen=None):
        rect = cls._profile_rect(screen)
        return pygame.Rect(rect.right - 55, rect.y + 10, 35, 30)
