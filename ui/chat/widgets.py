import re

import pygame

from ui.hud import draw_button, draw_text


def _split_damage_segments(text, color):
    damage_start = text.find(" (Урон:")
    if damage_start < 0:
        return [(text, color)]
    return [(text[:damage_start], (215, 215, 225)), (text[damage_start:], color)]


def _wrap_segments(segments, font, max_width):
    """Split colored text segments into lines that fit max_width, word by word."""
    lines = []
    current_line = []
    current_width = 0
    for text, color in segments:
        for chunk in re.findall(r"\S+\s*", text):
            chunk_width = font.size(chunk)[0]
            if current_line and current_width + chunk_width > max_width:
                lines.append(current_line)
                current_line = []
                current_width = 0
            current_line.append((chunk, color))
            current_width += chunk_width
    lines.append(current_line)
    return lines



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
    LINE_HEIGHT = 20

    def wrapped_lines(self, message, own, font, max_width):
        sender = "Вы" if own else message.get("sender", "Персонаж")
        segments = message.get("segments")
        if not segments:
            segments = [{
                "text": f"{sender}: {message.get('text', '')}",
                "color": (150, 210, 255) if own else (215, 215, 225),
            }]
        flat_segments = []
        for segment in segments:
            text = str(segment.get("text", ""))
            color = segment.get("color", (215, 215, 225))
            flat_segments.extend(_split_damage_segments(text, color))
        return _wrap_segments(flat_segments, font, max_width)

    def draw(self, screen, lines, rect, font):
        y = rect.y
        for line in lines:
            x = rect.x
            for part_text, part_color in line:
                if not part_text:
                    continue
                surface = font.render(part_text, True, part_color)
                screen.blit(surface, (x, y))
                x += surface.get_width()
            y += self.LINE_HEIGHT
        return y - rect.y


class MessageList:
    def __init__(self, rect, font):
        self.rect = rect
        self.font = font
        self.item = MessageItem()
        self.scroll = 0
        self.follow_latest = True
        self.messages = []
        self._layout = []
        self._layout_own_id = None

    def set_messages(self, messages):
        self.messages = list(messages)
        self._layout_own_id = None

    def _layout_messages(self, own_id):
        max_width = max(40, self.rect.width - 4)
        self._layout = []
        y = 0
        for message in self.messages:
            is_own = message.get("sender_id") == own_id
            lines = self.item.wrapped_lines(message, is_own, self.font, max_width)
            height = max(1, len(lines)) * self.item.LINE_HEIGHT
            self._layout.append((lines, y, height))
            y += height + 4
        self._layout_own_id = own_id

    def _max_scroll(self):
        total_height = self._layout[-1][1] + self._layout[-1][2] if self._layout else 0
        return max(0, total_height - self.rect.height + 8)

    def draw(self, screen, own_id):
        if self._layout_own_id != own_id:
            self._layout_messages(own_id)
            if self.follow_latest:
                self.scroll = self._max_scroll()
        previous_clip = screen.get_clip()
        screen.set_clip(self.rect)
        for lines, y, height in self._layout:
            item_top = self.rect.y + 4 + y - self.scroll
            if item_top + height < self.rect.y or item_top > self.rect.bottom:
                continue
            self.item.draw(screen, lines, pygame.Rect(self.rect.x, item_top, self.rect.width, height), self.font)
        screen.set_clip(previous_clip)
        max_scroll = self._max_scroll()
        if max_scroll <= 0:
            return
        track_rect = pygame.Rect(self.rect.right - 8, self.rect.y + 4, 4, self.rect.height - 8)
        pygame.draw.rect(screen, (50, 55, 66), track_rect, border_radius=3)
        thumb_height = max(18, int((self.rect.height / max(1, self.rect.height + max_scroll)) * (self.rect.height - 10)))
        thumb_y = self.rect.y + 7 + int(self.scroll / max_scroll * (self.rect.height - 14 - thumb_height))
        thumb = pygame.Rect(self.rect.right - 8, thumb_y, 4, thumb_height)
        pygame.draw.rect(screen, (170, 180, 210), thumb, border_radius=3)

    def wheel(self, direction):
        self.follow_latest = False
        self.scroll = max(0, min(self._max_scroll(), self.scroll - direction * 52))



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
