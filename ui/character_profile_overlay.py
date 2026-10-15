import pygame

from core import settings
from ui.character_card import CharacterCard
from ui.hud import draw_button


class CharacterProfileOverlay:
    """Reusable right-side profile card opened by any UI surface."""

    def __init__(self, action_font):
        self.action_font = action_font
        self.player_card = CharacterCard()
        self.card = CharacterCard()
        self.player_frame = pygame.Rect(settings.PLAYER_CARD_RECT)
        self.frame = pygame.Rect(settings.ENEMY_CARD_RECT)
        # Крестик рисуется в правом верхнем углу той карточки, которая показана сейчас
        self._player_only = False
        # Кнопка рюкзака на верхней части рамки игрока, снаружи справа
        self.backpack_button = pygame.Rect(
            self.player_frame.right + 5,
            self.player_frame.y,
            130,
            40,
        )
        # 9 дополнительных кнопок вертикально вниз
        self.slot_buttons = []
        for i in range(9):
            slot_offset = i * 45 if i == 0 else i * 45 + 45
            button = pygame.Rect(
                self.player_frame.right + 5,
                self.player_frame.y + 50 + slot_offset,
                100,
                40,
            )
            self.slot_buttons.append(button)
        
        # Окно инвентаря глобальное (main.py): кнопка лишь просит его открыть
        self.inventory_requested = False
        
        self.profile = None
        self.counterpart = None

    @property
    def is_open(self):
        return self.profile is not None

    @property
    def close_button(self):
        frame = self.player_frame if self._player_only else self.frame
        return pygame.Rect(frame.right - 34, frame.y + 10, 24, 24)

    @staticmethod
    def _draw_close_cross(screen, rect):
        pygame.draw.rect(screen, (60, 36, 40), rect, border_radius=4)
        pygame.draw.rect(screen, (200, 70, 70), rect, width=1, border_radius=4)
        pygame.draw.line(screen, (240, 200, 200), (rect.x + 7, rect.y + 7), (rect.right - 7, rect.bottom - 7), 2)
        pygame.draw.line(screen, (240, 200, 200), (rect.right - 7, rect.y + 7), (rect.x + 7, rect.bottom - 7), 2)

    def open(self, profile, counterpart=None):
        self.profile = dict(profile)
        self.counterpart = dict(counterpart) if isinstance(counterpart, dict) else counterpart

    def close(self):
        self.profile = None
        self.counterpart = None

    def update_counterpart(self, profile):
        self.counterpart = dict(profile)
    
    def update_profile(self, profile):
        """Обновить основной профиль (левую панель)"""
        self.profile = dict(profile)

    @staticmethod
    def _card_for_profile(profile, current_card):
        if current_card is not None:
            return current_card
        character_id = profile.get("character_id", profile.get("id")) if isinstance(profile, dict) else None
        return CharacterCard.get_or_create(character_id)

    @staticmethod
    def _draw_card(card, screen, frame, *, border_color, editable, title=None, kind="player"):
        card.sync(card.state if card.state else {}, title=title, kind=kind)
        card.draw(
            screen,
            frame,
            border_color=border_color,
            editable=editable,
        )

    def handle_click(self, position):
        if self.is_open and self.close_button.collidepoint(position):
            self.close()
            return "close", None
        
        # Обработка клика по кнопке рюкзака
        if self.is_open and self.backpack_button.collidepoint(position):
            self.inventory_requested = True
            return "handled", None
        
        # Обработка клика по слотам (2-9); слот 1 пока не используется
        for i, button in enumerate(self.slot_buttons):
            if self.is_open and button.collidepoint(position):
                if i == 0:
                    return "handled", None
                return f"slot_{i+1}", None
        
        if not self.is_open:
            return None, None

        card = self.player_card
        frame = self.player_frame
        if self.frame.collidepoint(position) and self.profile is not None:
            card = self.card
            frame = self.frame

        level_delta = None
        if hasattr(card, "level_control_at"):
            level_delta = card.level_control_at(frame, position)
        if level_delta is not None:
            if card.adjust_level(level_delta):
                if card is self.card:
                    self.profile = dict(card.data)
                return "stat_change", card.data
            return "handled", None

        if not hasattr(card, "stat_control_at"):
            return None, None
        change = card.stat_control_at(frame, position)
        if change is None:
            return None, None
        stat_name, delta = change
        if card.adjust_stat(stat_name, delta):
            if card is self.card:
                self.profile = dict(card.data)
            return "stat_change", card.data
        return "handled", None

    def draw(self, screen, opponent=None, show_counterpart=True, show_player_only=False):
        if not self.is_open:
            return
        self._player_only = show_player_only
        opponent = self.counterpart if self.counterpart is not None else opponent
        self.player_card = self._card_for_profile(opponent or self.profile, self.player_card)
        self.card = self._card_for_profile(self.profile, self.card)
        
        # Если show_player_only=True, показываем только левую панель (ТЕКУЩИЙ ИГРОК)
        if show_player_only:
            # opponent приходит свежим каждый кадр (например, session.character) — используем его,
            # чтобы бонусы от экипировки и другие изменения сразу отражались на карточке.
            self.player_card.sync(opponent if opponent is not None else self.profile, title="ТЕКУЩИЙ ИГРОК", kind="player")
            self._draw_card(
                self.player_card,
                screen,
                self.player_frame,
                border_color=(80, 180, 120),
                editable=True,
            )
            self._draw_close_cross(screen, self.close_button)
            self._draw_side_buttons(screen)
            return
        
        if show_counterpart and opponent is not None:
            self.player_card.sync(opponent, title="ТЕКУЩИЙ ИГРОК", kind="player")
            self._draw_card(
                self.player_card,
                screen,
                self.player_frame,
                border_color=(80, 180, 120),
                editable=True,
            )
        self.card.sync(self.profile, title="ПРОФИЛЬ ПЕРСОНАЖА", kind=self.profile.get("kind", "player"))
        self._draw_card(
            self.card,
            screen,
            self.frame,
            border_color=(210, 100, 90),
            editable=False,
        )
        self._draw_close_cross(screen, self.close_button)
        self._draw_side_buttons(screen)

    def _draw_side_buttons(self, screen):
        # Кнопка рюкзака в верхнем правом углу (слева на левой карточке)
        draw_button(screen, self.backpack_button, "РЮКЗАК", self.action_font, color=(210, 100, 90))
        # Слоты 2-9 вертикально вниз; слот 1 пока пустой
        for i, button in enumerate(self.slot_buttons):
            if i == 0:
                continue
            draw_button(screen, button, str(i + 1), self.action_font, color=(210, 100, 90))
