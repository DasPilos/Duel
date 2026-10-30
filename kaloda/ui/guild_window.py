"""Окно гильдии искателей приключений: список заданий, принятие и сдача."""

import uuid

import pygame

from client.network import ServerError
from kaloda import settings
from kaloda.currency import format_coins
from kaloda.quests import QUESTS, quest_log_for
from kaloda.ui.hud import draw_button


class GuildWindow:
    WIDTH = 820
    HEIGHT = 520

    def __init__(self, scene):
        self.scene = scene
        self.is_open = False
        self.view = "main"
        self.selected_id = QUESTS[0].id
        self.rect = pygame.Rect(0, 0, self.WIDTH, self.HEIGHT)
        self.rect.center = (settings.WIDTH // 2, settings.HEIGHT // 2)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 28, bold=True)
        self.font = pygame.font.SysFont(settings.FONT_NAME, 20)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 17)
        self.close_rect = pygame.Rect(self.rect.right - 46, self.rect.top + 12, 34, 34)
        self.quests_button = pygame.Rect(self.rect.left + 24, self.rect.top + 74, 200, 46)
        self.action_button = pygame.Rect(self.rect.right - 284, self.rect.bottom - 70, 260, 48)
        self.message = None

    @property
    def quest_log(self):
        return quest_log_for(self.scene.session)

    def open(self):
        self.is_open = True
        self.view = "main"
        self.message = None

    def close(self):
        self.is_open = False

    def quest_rows(self):
        top = self.rect.top + 136
        return [
            (quest, pygame.Rect(self.rect.left + 24, top + index * 62, 300, 54))
            for index, quest in enumerate(QUESTS)
        ]

    def selected_quest(self):
        return next(quest for quest in QUESTS if quest.id == self.selected_id)

    def action_label(self):
        status = self.quest_log.status(self.selected_id)
        return {
            "available": "ПРИНЯТЬ ЗАДАНИЕ",
            "active": "ЗАДАНИЕ ВЗЯТО",
            "completed": "СДАТЬ ЗАДАНИЕ",
        }[status]

    # ------------------------------------------------------------------ ввод

    def handle_event(self, event):
        """Окно модальное: поглощает все события мыши и клавиатуры, пока открыто."""
        if not self.is_open:
            return False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.close()
            return True
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL, pygame.KEYDOWN)
        if self.close_rect.collidepoint(event.pos) or not self.rect.collidepoint(event.pos):
            self.close()
            return True
        if self.quests_button.collidepoint(event.pos):
            self.view = "quests"
            self.message = None
            return True
        if self.view != "quests":
            return True
        for quest, rect in self.quest_rows():
            if rect.collidepoint(event.pos):
                self.selected_id = quest.id
                self.message = None
                return True
        if self.action_button.collidepoint(event.pos):
            self._act()
        return True

    def _act(self):
        log = self.quest_log
        quest = self.selected_quest()
        status = log.status(quest.id)
        if status == "available":
            log.accept(quest.id)
            self.message = f"Задание «{quest.title}» принято"
        elif status == "completed":
            character = getattr(self.scene.session, "character", None)
            client = getattr(self.scene.session, "client", None)
            if not isinstance(character, dict) or character.get("id") is None:
                self.message = "Персонаж не загружен"
                return
            try:
                result = client.claim_guild_quest_reward(
                    character["id"], quest.id, str(uuid.uuid4())
                )
            except (ServerError, AttributeError, KeyError, OSError) as error:
                self.message = f"Не удалось сдать задание: {error}"
                return
            character.update(result.get("character") or {})
            reward = int(result.get("reward_coins", 0))
            log.claim(quest.id)
            self.message = (
                "Это задание уже было сдано"
                if result.get("already_claimed")
                else f"Получено: {format_coins(reward)}"
            )

    # ------------------------------------------------------------------ отрисовка

    def draw(self, screen):
        if not self.is_open:
            return
        shade = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 120))
        screen.blit(shade, (0, 0))
        pygame.draw.rect(screen, (30, 27, 18), self.rect, border_radius=10)
        pygame.draw.rect(screen, (220, 180, 60), self.rect, 3, border_radius=10)
        title = self.title_font.render("Гильдия искателей приключений", True, (255, 215, 90))
        screen.blit(title, (self.rect.left + 24, self.rect.top + 18))
        pygame.draw.rect(screen, (120, 60, 50), self.close_rect, border_radius=6)
        cross = self.font.render("×", True, (255, 255, 255))
        screen.blit(cross, cross.get_rect(center=self.close_rect.center))

        active = self.view == "quests"
        draw_button(screen, self.quests_button, "ЗАДАНИЯ", self.font,
                    color=(190, 145, 55) if active else (120, 95, 40), hover_color=(210, 165, 70))

        if not active:
            lines = (
                "Добро пожаловать, искатель приключений!",
                "Здесь можно взять задания и получить за них награду.",
                "Нажмите «ЗАДАНИЯ», чтобы посмотреть доступные поручения.",
            )
            for index, line in enumerate(lines):
                surf = self.font.render(line, True, (230, 225, 205))
                screen.blit(surf, (self.rect.left + 250, self.rect.top + 84 + index * 32))
            return

        log = self.quest_log
        status_text = {"available": "доступно", "active": "взято", "completed": "выполнено!"}
        for quest, rect in self.quest_rows():
            selected = quest.id == self.selected_id
            status = log.status(quest.id)
            pygame.draw.rect(screen, (70, 58, 28) if selected else (44, 38, 24), rect, border_radius=6)
            pygame.draw.rect(screen, (230, 190, 70) if selected else (110, 95, 55), rect, 2, border_radius=6)
            screen.blit(self.font.render(quest.title, True, (245, 235, 210)), (rect.left + 12, rect.top + 6))
            color = (120, 230, 130) if status == "completed" else (200, 190, 160)
            screen.blit(self.small_font.render(status_text[status], True, color), (rect.left + 12, rect.top + 30))

        quest = self.selected_quest()
        status = log.status(quest.id)
        left = self.rect.left + 350
        top = self.rect.top + 136
        screen.blit(self.title_font.render(quest.title, True, (255, 225, 140)), (left, top))
        y = top + 44
        for line in self._wrap(quest.description, self.rect.right - left - 30):
            screen.blit(self.font.render(line, True, (230, 225, 205)), (left, y))
            y += 28
        y += 10
        screen.blit(
            self.font.render(
                f"Награда: {format_coins(quest.reward_coins)}",
                True,
                (220, 220, 235),
            ),
            (left, y),
        )
        if status != "available":
            done = log.progress.get(quest.id, 0)
            screen.blit(self.font.render(f"Прогресс: {done}/{quest.count}", True, (150, 225, 160)), (left, y + 32))

        enabled = status != "active"
        draw_button(
            screen, self.action_button, self.action_label(), self.font,
            color=(70, 140, 80) if status == "completed" else (190, 145, 55) if enabled else (70, 70, 74),
            hover_color=(90, 165, 100) if status == "completed" else (210, 165, 70) if enabled else (70, 70, 74),
            text_color=(255, 255, 255) if enabled else (160, 160, 165),
        )
        if self.message:
            surf = self.small_font.render(self.message, True, (255, 225, 140))
            screen.blit(surf, (self.rect.left + 24, self.rect.bottom - 52))

    def _wrap(self, text, width):
        lines, current = [], ""
        for word in text.split():
            candidate = f"{current} {word}".strip()
            if self.font.size(candidate)[0] <= width:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines
