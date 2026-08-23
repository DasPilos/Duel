import pygame


class LogRenderer:
    SCROLL_STEP_LINES = 3

    def __init__(self, scene, layout):
        self.scene = scene
        self.layout = layout
        self.background_color = (25, 27, 38)
        self.text_color = (230, 230, 230)
        self.padding = 15
        self.line_spacing = 8
        self._last_total_content_height = 0
        self._last_visible_height = 0
        self._fallback_font = None

    def render(self, screen):
        if getattr(self.scene, "phase", None) == "setup":
            return
        rect = self._get_rect()
        if rect is None:
            return
        pygame.draw.rect(screen, self.background_color, rect, border_radius=10)
        pygame.draw.rect(screen, (60, 65, 80), rect, width=2, border_radius=10)
        comments = self._get_comments()
        font = self._get_font()
        if font is None:
            return
        x = rect.x + self.padding
        max_width = rect.width - self.padding * 2
        visible_top = rect.y + self.padding
        visible_bottom = rect.bottom - self.padding
        visible_height = visible_bottom - visible_top
        lines = self._build_lines(comments=comments, font=font, max_width=max_width)
        line_height = font.get_height() + 4
        total_lines = len(lines)
        total_content_height = total_lines * line_height
        self._last_total_content_height = total_content_height
        self._last_visible_height = visible_height
        max_visible_lines = max(1, visible_height // line_height)
        offset = getattr(self.scene, "log_scroll_offset", 0)
        offset = self._clamp_offset(offset, total_lines, max_visible_lines)
        end_index = total_lines - offset
        start_index = max(0, end_index - max_visible_lines)
        visible_lines = self._slice_lines(lines, start_index, end_index)
        previous_clip = screen.get_clip()
        screen.set_clip(rect)
        y = visible_top
        for line_segments in visible_lines:
            current_x = x
            for segment_pair in line_segments:
                text, color = segment_pair
                surface = font.render(text, True, color)
                screen.blit(surface, (current_x, y))
                current_x += surface.get_width()
            y += line_height
        screen.set_clip(previous_clip)
        if total_lines > max_visible_lines:
            self._draw_scrollbar(screen=screen, rect=rect, total_lines=total_lines, max_visible_lines=max_visible_lines, start_index=start_index)

    def draw(self, screen):
        self.render(screen)

    def update(self):
        pass

    def handle_scroll(self, direction):
        if getattr(self.scene, "phase", None) == "setup":
            return
        current_offset = getattr(self.scene, "log_scroll_offset", 0)
        step = self.SCROLL_STEP_LINES
        if direction > 0:
            new_offset = current_offset + step
        else:
            new_offset = current_offset - step
        self.scene.log_scroll_offset = max(0, new_offset)

    def _clamp_offset(self, offset, total_lines, max_visible_lines):
        max_offset = max(0, total_lines - max_visible_lines)
        if offset < 0:
            offset = 0
        elif offset > max_offset:
            offset = max_offset
        self.scene.log_scroll_offset = offset
        return offset

    def _draw_scrollbar(self, screen, rect, total_lines, max_visible_lines, start_index):
        bar_width = 4
        bar_x = rect.right - self.padding // 2 - bar_width
        track_top = rect.y + self.padding
        track_height = rect.height - self.padding * 2
        pygame.draw.rect(screen, (45, 48, 62), (bar_x, track_top, bar_width, track_height), border_radius=2)
        ratio = max_visible_lines / total_lines
        thumb_height = max(20, int(track_height * ratio))
        max_start = max(1, total_lines - max_visible_lines)
        progress = start_index / max_start if max_start else 0
        thumb_y = track_top + int((track_height - thumb_height) * progress)
        pygame.draw.rect(screen, (100, 105, 125), (bar_x, thumb_y, bar_width, thumb_height), border_radius=2)

    def _build_lines(self, comments, font, max_width):
        lines = []
        comments_list = list(comments)
        total_comments = len(comments_list)
        comment_index = 0
        for comment in comments_list:
            segments = self._extract_segments(comment)
            if segments:
                current_line = []
                current_line_width = 0
                for segment in segments:
                    text = str(segment.get("text", ""))
                    color = segment.get("color", self.text_color)
                    words = text.split(" ")
                    word_count = len(words)
                    word_index = 0
                    for word in words:
                        part = word
                        if word_index < word_count - 1:
                            part = part + " "
                        if part:
                            size_tuple = font.size(part)
                            width_value, height_value = size_tuple
                            needs_wrap = (current_line and current_line_width + width_value > max_width)
                            if needs_wrap:
                                lines.append(current_line)
                                current_line = []
                                current_line_width = 0
                            pair = (part, color)
                            current_line.append(pair)
                            current_line_width += width_value
                        word_index += 1
                if current_line:
                    lines.append(current_line)
            comment_index += 1
            if comment_index < total_comments:
                empty_pair = ("", self.text_color)
                empty_line = [empty_pair]
                lines.append(empty_line)
        return lines

    def _slice_lines(self, lines, start_index, end_index):
        result = []
        index = 0
        for line in lines:
            if index >= start_index and index < end_index:
                result.append(line)
            index += 1
        return result

    def _extract_segments(self, comment):
        if isinstance(comment, str):
            single_segment = {"text": comment, "color": self.text_color}
            return (single_segment,)
        if isinstance(comment, dict):
            segments = comment.get("segments", ())
            has_text_key = "text" in comment
            if not segments and has_text_key:
                fallback_segment = {"text": comment.get("text", ""), "color": comment.get("color", self.text_color)}
                return (fallback_segment,)
            return segments
        return ()

    def _get_rect(self):
        if isinstance(self.layout, pygame.Rect):
            return self.layout
        log_rect = getattr(self.layout, "log_rect", None)
        if isinstance(log_rect, pygame.Rect):
            return log_rect
        log_area = getattr(self.layout, "log_area", None)
        if isinstance(log_area, pygame.Rect):
            return log_area
        return pygame.Rect(560, 760, 800, 280)

    def _get_comments(self):
        possible_names = ("comments", "battle_comments", "combat_comments", "logs", "log_messages")
        for name in possible_names:
            value = getattr(self.scene, name, None)
            if isinstance(value, (list, tuple)):
                return value
        commentator = getattr(self.scene, "commentator", None)
        if commentator is not None:
            for name in possible_names:
                value = getattr(commentator, name, None)
                if isinstance(value, (list, tuple)):
                    return value
        return ()

    def _get_font(self):
        possible_names = ("comment_font", "small_font", "font")
        for name in possible_names:
            font = getattr(self.scene, name, None)
            if isinstance(font, pygame.font.Font):
                return font
        if self._fallback_font is None:
            if not pygame.font.get_init():
                pygame.font.init()
            self._fallback_font = pygame.font.SysFont("arial", 20)
        return self._fallback_font
