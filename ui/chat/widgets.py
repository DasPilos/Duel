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
        sender = "Вы" if own else message.get("sender", "Персонаж")
        segments = message.get("segments")
        if not segments:
            segments = [{
                "text": f"{sender}: {message.get('text', '')}",
                "color": (150, 210, 255) if own else (215, 215, 225),
            }]
        x = rect.x
        for segment in segments:
            text = str(segment.get("text", ""))
            color = segment.get("color", (215, 215, 225))
            damage_start = text.find(" (Урон:")
            parts = ((text, color),) if damage_start < 0 else (
                (text[:damage_start], (215, 215, 225)),
                (text[damage_start:], color),
            )
            for part_text, part_color in parts:
                surface = font.render(part_text, True, part_color)
                screen.blit(surface, (x, rect.y))
                x += surface.get_width()


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
        self.follow_latest = False
        max_scroll = max(0, len(self.messages) * 26 - self.rect.height + 12)
        self.scroll = max(0, min(max_scroll, self.scroll - direction * 52))


class MessageInput:
    def __init__(self, rect, font):
        self.rect = rect
        self.font = font
        self.text = ""
        self.focused = False
        self.caret_elapsed = 0.0
        self.send_rect = pygame.Rect(rect.right - 70, rect.y, 70, rect.height)

    def update(self, dt):
        self.caret_elapsed = (self.caret_elapsed + max(0.0, dt)) % 1.0

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.focused = self.rect.collidepoint(event.pos)
            return self.focused
        if event.type == pygame.TEXTINPUT:
            if not self.focused:
                return False
            self.text = (self.text + event.text)[:300]
            return True
        if event.type == pygame.KEYDOWN:
            if not self.focused:
                return False
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
                return True
            if event.key == pygame.K_RETURN and not event.mod & pygame.KMOD_SHIFT:
                return "send"
        return False

    def draw(self, screen):
        pygame.draw.rect(screen, (28, 30, 43), self.rect, border_radius=5)
        border_color = (100, 150, 220) if self.focused else (70, 75, 90)
        pygame.draw.rect(screen, border_color, self.rect, width=1, border_radius=5)
        previous_clip = screen.get_clip()
        inner_rect = self.rect.inflate(-14, -4)
        screen.set_clip(inner_rect)
        text_surface = self.font.render(self.text, True, (240, 240, 245))
        text_y = self.rect.centery - text_surface.get_height() // 2
        screen.blit(text_surface, (self.rect.x + 8, text_y))
        if self.focused and self.caret_elapsed < 0.5:
            caret_x = self.rect.x + 8 + text_surface.get_width()
            pygame.draw.line(screen, (240, 240, 245), (caret_x, text_y), (caret_x, text_y + text_surface.get_height()), 1)
        screen.set_clip(previous_clip)
        draw_button(screen, self.send_rect, "ОТПРАВИТЬ", self.font, color=(70, 140, 220))
