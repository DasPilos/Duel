import pygame

from client.network import ServerError
from kaloda import settings
from kaloda.combat.talents import talent_tree_for
from kaloda.ui.hud import draw_button


class TalentTreeWindow:
    WIDTH = 980
    HEIGHT = 660
    ROW_HEIGHT = 62
    ROW_GAP = 5

    def __init__(self, scene):
        self.scene = scene
        self.is_open = False
        self.message = None
        self.scroll_offset = 0
        self.rect = pygame.Rect(
            0, 0,
            min(self.WIDTH, settings.WIDTH - 32),
            min(self.HEIGHT, settings.HEIGHT - 32),
        )
        self.rect.center = (settings.WIDTH // 2, settings.HEIGHT // 2)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 26, bold=True)
        self.font = pygame.font.SysFont(settings.FONT_NAME, 17)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 14)
        self.option_fonts = tuple(
            pygame.font.SysFont(settings.FONT_NAME, size)
            for size in (12, 11, 10)
        )
        self.close_rect = pygame.Rect(
            self.rect.right - 42, self.rect.top + 10, 30, 30
        )
        self.content_top = self.rect.top + 98
        self.content_bottom = self.rect.bottom - 70

    @property
    def character(self):
        return getattr(self.scene.session, "character", None)

    @property
    def tree(self):
        character = self.character or {}
        return talent_tree_for(character.get("type", "warrior"))

    @property
    def visible_count(self):
        return max(
            1,
            (self.content_bottom - self.content_top + self.ROW_GAP)
            // (self.ROW_HEIGHT + self.ROW_GAP),
        )

    def open(self):
        self.is_open = True
        self.message = None
        self.scroll_offset = 0
        character = self.character
        client = getattr(self.scene.session, "client", None)
        if not isinstance(character, dict) or character.get("id") is None:
            self.message = "Персонаж не загружен"
            return
        try:
            character.update(client.load_character(character["id"]))
        except (ServerError, AttributeError, OSError) as error:
            self.message = f"Не удалось обновить данные персонажа: {error}"

    def close(self):
        self.is_open = False

    def _row_rects(self):
        start = self.scroll_offset
        end = min(len(self.tree), start + self.visible_count)
        return [
            pygame.Rect(
                self.rect.left + 18,
                self.content_top + index * (self.ROW_HEIGHT + self.ROW_GAP),
                self.rect.width - 36,
                self.ROW_HEIGHT,
            )
            for index in range(end - start)
        ]

    def _option_rects(self, row):
        left = row.left + 152
        gap = 8
        width = (row.right - left - gap - 12) // 2
        return (
            pygame.Rect(left, row.top + 5, width, row.height - 10),
            pygame.Rect(left + width + gap, row.top + 5, width, row.height - 10),
        )

    def _wrap_text(self, text, max_width):
        words = str(text).split()
        for font in self.option_fonts:
            lines = []
            line = ""
            for word in words:
                candidate = f"{line} {word}".strip()
                if line and font.size(candidate)[0] > max_width:
                    lines.append(line)
                    line = word
                else:
                    line = candidate
            if line:
                lines.append(line)
            if len(lines) <= 2:
                return font, lines

        font = self.option_fonts[-1]
        lines = []
        line = ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if line and font.size(candidate)[0] > max_width:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        return font, lines[:2]

    def handle_event(self, event):
        if not self.is_open:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.close()
                return True
            if event.key in (pygame.K_UP, pygame.K_DOWN):
                self._scroll(-1 if event.key == pygame.K_UP else 1)
                return True
        if event.type == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(pygame.mouse.get_pos()):
                self._scroll(-event.y)
            return True
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return event.type in (
                pygame.MOUSEBUTTONDOWN,
                pygame.MOUSEBUTTONUP,
                pygame.MOUSEWHEEL,
                pygame.KEYDOWN,
            )
        if self.close_rect.collidepoint(event.pos) or not self.rect.collidepoint(event.pos):
            self.close()
            return True
        start = self.scroll_offset
        for index, row_rect in enumerate(self._row_rects()):
            entry = self.tree[start + index]
            if entry.get("passive"):
                continue
            for option, option_rect in zip(entry["options"], self._option_rects(row_rect)):
                if option_rect.collidepoint(event.pos):
                    self._choose(entry, option)
                    return True
        return True

    def _scroll(self, amount):
        maximum = max(0, len(self.tree) - self.visible_count)
        self.scroll_offset = max(
            0, min(maximum, self.scroll_offset + int(amount))
        )

    def _choose(self, entry, option):
        character = self.character
        if not isinstance(character, dict):
            self.message = "Персонаж не загружен"
            return
        level = int(entry["level"])
        if int(character.get("level", 1)) < level:
            self.message = f"Это улучшение доступно с {level}-го уровня"
            return
        if str(level) in character.get("talents", {}):
            self.message = "На этом уровне улучшение уже выбрано"
            return
        try:
            updated = self.scene.session.client.choose_character_talent(
                character["id"], level, option["id"]
            )
        except (ServerError, AttributeError, KeyError, OSError) as error:
            self.message = f"Не удалось выбрать улучшение: {error}"
            return
        character.update(updated)
        self.message = f"Выбрано: {option['name']}"

    def draw(self, screen):
        if not self.is_open:
            return
        shade = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        screen.blit(shade, (0, 0))
        pygame.draw.rect(screen, (24, 35, 29), self.rect, border_radius=10)
        pygame.draw.rect(screen, (125, 185, 110), self.rect, 3, border_radius=10)
        title = self.title_font.render("Древо талантов", True, (205, 235, 170))
        screen.blit(title, (self.rect.left + 22, self.rect.top + 14))
        character = self.character or {}
        level = int(character.get("level", 1))
        screen.blit(
            self.font.render(
                f"{character.get('type', '').capitalize()} — уровень {level}",
                True,
                (220, 225, 210),
            ),
            (self.rect.left + 24, self.rect.top + 53),
        )
        pygame.draw.rect(screen, (120, 60, 50), self.close_rect, border_radius=6)
        cross = self.font.render("×", True, (255, 255, 255))
        screen.blit(cross, cross.get_rect(center=self.close_rect.center))

        selected = character.get("talents", {})
        for offset, row_rect in enumerate(self._row_rects()):
            entry = self.tree[self.scroll_offset + offset]
            talent_level = int(entry["level"])
            unlocked = level >= talent_level
            choice = selected.get(str(talent_level))
            pygame.draw.rect(
                screen,
                (43, 61, 46) if unlocked else (35, 42, 37),
                row_rect,
                border_radius=6,
            )
            pygame.draw.rect(screen, (91, 126, 85), row_rect, 1, border_radius=6)
            level_label = f"Ур. {talent_level}"
            screen.blit(
                self.font.render(level_label, True, (219, 231, 205)),
                (row_rect.left + 12, row_rect.top + 7),
            )
            if entry.get("passive"):
                label = "ПАССИВНОЕ УЛУЧШЕНИЕ"
                screen.blit(
                    self.small_font.render(label, True, (174, 218, 147)),
                    (row_rect.left + 12, row_rect.top + 34),
                )
                screen.blit(
                    self.small_font.render(
                        entry["description"], True, (207, 216, 199)
                    ),
                    (row_rect.left + 160, row_rect.top + 22),
                )
                continue
            for option, button_rect in zip(
                entry["options"], self._option_rects(row_rect)
            ):
                chosen = choice == option["id"]
                color = (
                    (73, 112, 67) if chosen
                    else (54, 72, 56) if unlocked and choice is None
                    else (43, 47, 43)
                )
                draw_button(
                    screen,
                    button_rect,
                    "",
                    self.small_font,
                    color=color,
                    hover_color=(83, 132, 76) if unlocked and choice is None else color,
                    text_color=(235, 240, 225) if unlocked else (130, 137, 128),
                )
                text = option["name"] if chosen else option["description"]
                font, lines = (
                    (self.small_font, [text])
                    if chosen
                    else self._wrap_text(text, button_rect.width - 20)
                )
                line_height = font.get_linesize()
                first_y = button_rect.centery - len(lines) * line_height // 2
                text_color = (235, 240, 225) if unlocked else (130, 137, 128)
                for line_index, line in enumerate(lines):
                    surface = font.render(line, True, text_color)
                    screen.blit(
                        surface,
                        surface.get_rect(
                            center=(
                                button_rect.centerx,
                                first_y + line_index * line_height + line_height // 2,
                            )
                        ),
                    )
        if len(self.tree) > self.visible_count:
            label = self.small_font.render(
                f"{self.scroll_offset + 1}–"
                f"{min(len(self.tree), self.scroll_offset + self.visible_count)} / {len(self.tree)}",
                True,
                (190, 205, 180),
            )
            screen.blit(label, (self.rect.left + 22, self.rect.bottom - 58))
        if self.message:
            screen.blit(
                self.small_font.render(self.message, True, (238, 220, 155)),
                (self.rect.left + 250, self.rect.bottom - 58),
            )
