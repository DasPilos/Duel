import pygame

from core import settings
from ui.character_card import CharacterCard
from ui.hud import draw_button
from ui.backpack_panel import BackpackPanel
from ui.collection_panel import CollectionPanel


class CharacterProfileOverlay:
    """Reusable right-side profile card opened by any UI surface."""

    def __init__(self, action_font, collection_loader=None):
        self.action_font = action_font
        self.collection_loader = collection_loader
        self.player_card = CharacterCard()
        self.card = CharacterCard()
        self.player_frame = pygame.Rect(settings.PLAYER_CARD_RECT)
        self.frame = pygame.Rect(settings.ENEMY_CARD_RECT)
        self.close_button = pygame.Rect(
            self.frame.right - 100,
            self.frame.y + 15,
            85,
            34,
        )
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
            button = pygame.Rect(
                self.player_frame.right + 5,
                self.player_frame.y + 50 + i * 45,
                100,
                40,
            )
            self.slot_buttons.append(button)
        
        # Панель рюкзака
        self.backpack_panel = BackpackPanel()
        self.collection_panel = CollectionPanel()
        
        self.profile = None
        self.counterpart = None

    @property
    def is_open(self):
        return self.profile is not None

    def open(self, profile, counterpart=None):
        self.profile = dict(profile)
        self.counterpart = dict(counterpart) if isinstance(counterpart, dict) else counterpart

    def close(self):
        self.backpack_panel.close()
        self.collection_panel.close()
        self.profile = None
        self.counterpart = None

    def handle_event(self, event):
        return self.collection_panel.handle_event(event)

    def update_counterpart(self, profile):
        self.counterpart = dict(profile)
    
    def update_profile(self, profile):
        """Обновить основной профиль (левую панель)"""
        self.profile = dict(profile)

    def handle_click(self, position):
        if self.collection_panel.is_open:
            self.collection_panel.handle_click(position)
            return "handled", None

        # Обработка клика по рюкзаку (приоритет выше всего)
        if self.backpack_panel.is_open:
            cell_index = self.backpack_panel.handle_click(position)
            if cell_index is not None:
                return f"backpack_cell_{cell_index}", None
            # Если рюкзак был закрыт кликом вне панели, возвращаем handled
            if not self.backpack_panel.is_open:
                return "handled", None
            return "handled", None
        
        if self.is_open and self.close_button.collidepoint(position):
            self.close()
            return "close", None
        
        # Обработка клика по кнопке рюкзака
        if self.is_open and self.backpack_button.collidepoint(position):
            self.backpack_panel.toggle()
            return "backpack", None
        
        # Обработка клика по слотам (1-9)
        for i, button in enumerate(self.slot_buttons):
            if self.is_open and button.collidepoint(position):
                if i == 0:
                    cards = self.collection_loader() if self.collection_loader else []
                    self.collection_panel.open(cards)
                    return "handled", None
                return f"slot_{i+1}", None
        
        if not self.is_open:
            return None, None

        level_delta = self.player_card.level_control_at(self.player_frame, position)
        if level_delta is not None:
            if self.player_card.adjust_level(level_delta):
                return "stat_change", self.player_card.data
            return "handled", None

        change = self.player_card.stat_control_at(self.player_frame, position)
        if change is None:
            return None, None
        stat_name, delta = change
        if self.player_card.adjust_stat(stat_name, delta):
            return "stat_change", self.player_card.data
        return "handled", None

    def draw(self, screen, opponent=None, show_counterpart=True, show_player_only=False):
        if not self.is_open:
            return
        opponent = self.counterpart if self.counterpart is not None else opponent
        
        # Если show_player_only=True, показываем только левую панель (ТЕКУЩИЙ ИГРОК)
        if show_player_only:
            self.player_card.sync(self.profile, title="ТЕКУЩИЙ ИГРОК", kind="player")
            self.player_card.draw(
                screen,
                self.player_frame,
                border_color=(80, 180, 120),
                editable=True,
                opponent=None,
            )
            draw_button(screen, self.close_button, "ЗАКРЫТЬ", self.action_font, color=(70, 75, 90))
            # Кнопка рюкзака в верхнем правом углу
            draw_button(screen, self.backpack_button, "РЮКЗАК", self.action_font, color=(210, 100, 90))
            # 9 слотов вертикально вниз
            for i, button in enumerate(self.slot_buttons):
                label = "КОЛЛЕКЦИЯ" if i == 0 else str(i + 1)
                draw_button(screen, button, label, self.action_font, color=(210, 100, 90))
            # Рюкзак (над всем остальным)
            self.backpack_panel.draw(screen)
            self.collection_panel.draw(screen)
            return
        
        if show_counterpart and opponent is not None:
            self.player_card.sync(opponent, title="ТЕКУЩИЙ ИГРОК", kind="player")
            self.player_card.draw(
                screen,
                self.player_frame,
                border_color=(80, 180, 120),
                editable=True,
                opponent=self.profile,
            )
        self.card.sync(self.profile, title="ПРОФИЛЬ ПЕРСОНАЖА", kind=self.profile.get("kind", "player"))
        self.card.draw(
            screen,
            self.frame,
            border_color=(210, 100, 90),
            editable=False,
            opponent=opponent,
        )
        draw_button(screen, self.close_button, "ЗАКРЫТЬ", self.action_font, color=(70, 75, 90))
        # Кнопка рюкзака в верхнем правом углу (слева на левой карточке)
        draw_button(screen, self.backpack_button, "РЮКЗАК", self.action_font, color=(210, 100, 90))
        # 9 слотов вертикально вниз
        for i, button in enumerate(self.slot_buttons):
            label = "КОЛЛЕКЦИЯ" if i == 0 else str(i + 1)
            draw_button(screen, button, label, self.action_font, color=(210, 100, 90))
        # Рюкзак (над всем остальным)
        self.backpack_panel.draw(screen)
        self.collection_panel.draw(screen)
