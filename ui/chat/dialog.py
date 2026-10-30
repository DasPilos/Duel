import pygame

from client.network import ServerError
from core import settings
from ui.chat.widgets import MessageInput, MessageList
from ui.hud import draw_button, draw_text

TABS = ("Общий", "Личный")
ENTER_KEYS = (pygame.K_RETURN, pygame.K_KP_ENTER)
WHISPER_COMMAND = "/w"


def parse_whisper(text, occupants):
    """Разбирает «/w <имя> текст». Имя ищется среди игроков локации, самое длинное совпадение побеждает.

    Возвращает (получатель, текст, ошибка); при ошибке получатель None.
    """
    body = text[len(WHISPER_COMMAND):].strip()
    if not body:
        return None, "", "Формат: /w <имя> текст"
    for occupant in sorted(occupants, key=lambda item: len(item.get("name", "")), reverse=True):
        name = occupant.get("name", "")
        if not name or body[:len(name)].casefold() != name.casefold():
            continue
        rest = body[len(name):]
        if rest and not rest[0].isspace():
            continue
        message = rest.strip()
        if not message:
            return occupant, "", "Введите текст сообщения после имени"
        return occupant, message, ""
    return None, "", f"Игрок не найден в локации: {body.split()[0]}"


class ChatDialog:
    """Диалог чата в стиле MMO: открывается Enter, вкладки «Общий» и «Личный», фон полупрозрачный."""

    def __init__(self, session, location, presence):
        self.session = session
        self.location = location
        self.presence = presence
        self.rect = pygame.Rect(settings.CHAT_DIALOG_RECT)
        self.visible = False
        self.tab = TABS[0]
        self.whisper_target = None
        self.status = ""
        self.font_tab = pygame.font.SysFont("arial", 14)
        self.font_status = pygame.font.SysFont("arial", 13)
        self.font_message = pygame.font.SysFont("arial", 15)
        self.message_input = MessageInput(pygame.Rect(0, 0, 10, 10), self.font_message)
        self.message_list = MessageList(pygame.Rect(0, 0, 10, 10), self.font_message)
        self.tab_rects = {}
        self.close_rect = pygame.Rect(0, 0, 0, 0)
        self._messages_source = None
        self._messages_tab = None
        self._layout()

    def _layout(self):
        self.close_rect = pygame.Rect(self.rect.right - 30, self.rect.y + 8, 22, 22)
        self.tab_rects = {
            name: pygame.Rect(self.rect.x + 10 + index * 110, self.rect.y + 8, 104, 26)
            for index, name in enumerate(TABS)
        }
        input_rect = pygame.Rect(self.rect.x + 10, self.rect.bottom - 40, self.rect.width - 20, 30)
        self.message_input.set_rect(input_rect)
        self.status_y = input_rect.y - 22
        list_top = self.rect.y + 42
        self.message_list.set_rect(pygame.Rect(self.rect.x + 10, list_top, self.rect.width - 20, self.status_y - list_top - 4))

    def captures_keyboard(self):
        return self.visible

    def contains(self, position):
        return self.visible and self.rect.collidepoint(position)

    def open(self):
        self.visible = True
        self.message_input.focused = True
        self._messages_source = None
        self._sync_messages()

    def hide(self):
        self.visible = False
        self.message_input.focused = False

    def open_from_key(self, event):
        """Enter открывает диалог. Вызывается только тогда, когда клавиша не нужна открытым окнам сцены."""
        if self.visible or event.type != pygame.KEYDOWN or event.key not in ENTER_KEYS:
            return False
        self.open()
        return True

    def handle_event(self, event):
        if not self.visible:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.hide()
                return True
            if event.key in ENTER_KEYS:
                if self.message_input.text.strip():
                    self._submit()
                else:
                    self.hide()
                return True
            if event.key == pygame.K_BACKSPACE:
                self.message_input.handle_event(event)
            # Пока открыт чат, клавиши не двигают персонажа и не работают как хоткеи сцены
            return True
        if event.type == pygame.TEXTINPUT:
            self.message_input.handle_event(event)
            return True
        if event.type == pygame.MOUSEWHEEL:
            if self.message_list.rect.collidepoint(pygame.mouse.get_pos()):
                self.message_list.wheel(event.y)
            return self.rect.collidepoint(pygame.mouse.get_pos())
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._handle_click(event.pos)
        return False

    def _handle_click(self, position):
        if not self.rect.collidepoint(position):
            return False
        if self.close_rect.collidepoint(position):
            self.hide()
            return True
        for name, rect in self.tab_rects.items():
            if rect.collidepoint(position):
                self._select_tab(name)
                return True
        if self.message_input.send_rect.collidepoint(position):
            self._submit()
            return True
        self.message_input.focused = self.message_input.rect.collidepoint(position)
        return True

    def _select_tab(self, name):
        self.tab = name
        self.status = ""
        self._messages_source = None
        self._sync_messages()

    def _submit(self):
        text = self.message_input.text.strip()
        if not text:
            self.status = "Сообщение не может быть пустым"
            return
        recipient_id = None
        if text == WHISPER_COMMAND or text.startswith(WHISPER_COMMAND + " "):
            target, body, error = parse_whisper(text, self.presence.occupants)
            if error:
                self.status = error
                return
            self.whisper_target = target
            recipient_id = target.get("character_id")
            text = body
        elif self.tab == "Личный":
            if self.whisper_target is None:
                self.status = "Напишите /w <имя> текст, чтобы начать личный диалог"
                return
            recipient_id = self.whisper_target.get("character_id")
        try:
            self.session.send_message(self.location, text, recipient_id)
        except ServerError as error:
            self.status = str(error)
            return
        self.message_input.text = ""
        self.status = ""
        if recipient_id is not None:
            self.tab = "Личный"
        self.presence.refresh()
        self._messages_source = None
        self._sync_messages()

    def _visible_messages(self):
        messages = self.presence.messages
        if self.tab == "Общий":
            return [message for message in messages if message.get("recipient_id") is None]
        character = getattr(self.session, "character", None)
        own_id = str(character["id"]) if character else None
        return [
            message for message in messages
            if message.get("recipient_id") is not None
            and own_id in (str(message.get("sender_id")), str(message.get("recipient_id")))
        ]

    def _sync_messages(self):
        source = self.presence.messages
        if source is self._messages_source and self.tab == self._messages_tab:
            return
        self._messages_source = source
        self._messages_tab = self.tab
        self.message_list.set_messages(self._visible_messages())

    def update(self, dt):
        self.message_input.update(dt)
        self._sync_messages()

    def draw(self, screen):
        if not self.visible:
            return
        background = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        background.fill((22, 24, 34, settings.CHAT_BACKGROUND_ALPHA))
        pygame.draw.rect(background, (90, 100, 130, settings.CHAT_BACKGROUND_ALPHA), background.get_rect(), width=1, border_radius=8)
        screen.blit(background, self.rect.topleft)
        for name, rect in self.tab_rects.items():
            draw_button(screen, rect, name, self.font_tab, color=(90, 145, 220) if name == self.tab else (55, 58, 72))
        draw_button(screen, self.close_rect, "X", self.font_tab, color=(120, 60, 60))
        character = getattr(self.session, "character", None)
        self.message_list.draw(screen, character["id"] if character else None)
        if self.status:
            draw_text(screen, self.font_status, self.status, self.rect.x + 12, self.status_y, (255, 120, 100))
        elif self.tab == "Личный" and self.whisper_target is not None:
            draw_text(screen, self.font_status, f"Собеседник: {self.whisper_target.get('name', '')}", self.rect.x + 12, self.status_y, (255, 220, 120))
        self.message_input.draw(screen)
