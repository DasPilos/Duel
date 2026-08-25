import pygame

from ui.hud import draw_button, draw_text


class ChatHeader:
    def __init__(self, rect, font):
        self.rect = rect
        self.font = font
        self.collapse_rect = pygame.Rect(rect.right - 42, rect.y + 8, 30, 26)

    def draw(self, screen, location, collapsed):
        return


class ChannelList:
    def __init__(self, rect, font):
        self.rect = rect
        self.font = font
        self.channels = ("Общий", "Личные", "Лог боя")

    def draw(self, screen, selected, unread):
        for index, channel in enumerate(self.channels):
            color = (90, 145, 220) if channel == selected else (55, 58, 72)
            item = pygame.Rect(
                self.rect.x + index * 75,
                self.rect.y,
                70,
                25,
            )
            draw_button(screen, item, channel, self.font, color=color)


class UnreadBadge:
    def draw(self, screen, rect, count, font):
        if count > 0:
            draw_text(screen, font, f"Новых: {count}", rect.x, rect.y, (255, 220, 120))


class MessageItem:
    def draw(self, screen, message, rect, own, font):
        color = (150, 210, 255) if own else (215, 215, 225)
        sender = "Вы" if own else message.get("sender", "Персонаж")
        draw_text(screen, font, f"{sender}: {message.get('text', '')}", rect.x, rect.y, color)


class MessageList:
    def __init__(self, rect, font):
        self.rect = rect
        self.font = font
        self.item = MessageItem()
        self.scroll = 0
        self.follow_latest = True

    def set_messages(self, messages):
        self.messages = list(messages)
        if self.follow_latest:
            self.scroll = max(0, len(self.messages) * 26 - self.rect.height + 12)

    def draw(self, screen, own_id):
        previous_clip = screen.get_clip()
        screen.set_clip(self.rect)
        y = self.rect.y + 4 - self.scroll
        for message in self.messages:
            self.item.draw(screen, message, pygame.Rect(self.rect.x, y, self.rect.width, 24), message.get("sender_id") == own_id, self.font)
            y += 26
        screen.set_clip(previous_clip)

    def wheel(self, direction):
        self.follow_latest = direction > 0
        max_scroll = max(0, len(self.messages) * 26 - self.rect.height + 12)
        self.scroll = max(0, min(max_scroll, self.scroll - direction * 52))


class MessageInput:
    def __init__(self, rect, font):
        self.rect = rect
        self.font = font
        self.text = ""
        self.send_rect = pygame.Rect(rect.right - 70, rect.y, 70, rect.height)

    def handle_event(self, event):
        if event.type == pygame.TEXTINPUT:
            self.text = (self.text + event.text)[:300]
            return True
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
                return True
            if event.key == pygame.K_RETURN and not event.mod & pygame.KMOD_SHIFT:
                return "send"
        return False

    def draw(self, screen):
        pygame.draw.rect(screen, (28, 30, 43), self.rect, border_radius=5)
        pygame.draw.rect(screen, (70, 75, 90), self.rect, width=1, border_radius=5)
        draw_text(screen, self.font, self.text, self.rect.x + 8, self.rect.y + 9, (240, 240, 245))
        draw_button(screen, self.send_rect, "ОТПРАВИТЬ", self.font, color=(70, 140, 220))
