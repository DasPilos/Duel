import pygame

from core import settings
from ui.character_card import CharacterCard
from ui.mage_card import MageCard
from ui.hud import draw_button
from ui.backpack_panel import BackpackPanel
from ui.collection_panel import CollectionPanel
from ui.deck_selection_panel import DeckSelectionPanel


class CharacterProfileOverlay:
    """Reusable right-side profile card opened by any UI surface."""

    def __init__(self, action_font, collection_loader=None, deck_loader=None):
        self.action_font = action_font
        self.collection_loader = collection_loader
        self.deck_loader = deck_loader
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
            slot_offset = i * 45 if i == 0 else i * 45 + 45
            button = pygame.Rect(
                self.player_frame.right + 5,
                self.player_frame.y + 50 + slot_offset,
                100,
                40,
            )
            self.slot_buttons.append(button)
        
        # Панель рюкзака
        self.backpack_panel = BackpackPanel()
        self.collection_panel = CollectionPanel()
        self.deck_panel = DeckSelectionPanel(action_font, action_font, collection_loader)
        self.selected_deck = None
        self.deck_button = pygame.Rect(
            self.player_frame.right + 5,
            self.player_frame.y + 95,
            100,
            40,
        )
        
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
        self.deck_panel.close()
        self.profile = None
        self.counterpart = None

    def handle_event(self, event):
        deck_action = self.deck_panel.handle_event(event)
        if deck_action == "create":
            self.deck_panel.create_requested = True
            return True
        if deck_action:
            return deck_action
        return self.collection_panel.handle_event(event)

    def take_create_deck_request(self):
        if not self.deck_panel.create_requested:
            return None
        self.deck_panel.create_requested = False
        name = self.deck_panel.name.strip()
        self.deck_panel.creating = False
        if not name:
            return None
        return name, list(self.deck_panel.selected_cards)

    def update_counterpart(self, profile):
        self.counterpart = dict(profile)
    
    def update_profile(self, profile):
        """Обновить основной профиль (левую панель)"""
        self.profile = dict(profile)

    @staticmethod
    def _is_mage(profile):
        return isinstance(profile, dict) and profile.get("type") == "mage"

    @staticmethod
    def _is_warrior(profile):
        return isinstance(profile, dict) and profile.get("type", "warrior") == "warrior"

    def _card_for_profile(self, profile, current_card):
        card_type = MageCard if self._is_mage(profile) else CharacterCard
        if not isinstance(current_card, card_type):
            return card_type()
        return current_card

    @staticmethod
    def _draw_card(card, screen, frame, *, border_color, editable, opponent=None, title=None, kind="player"):
        if isinstance(card, MageCard):
            card.draw(
                screen,
                frame,
                border_color=border_color,
                title=title,
                editable=editable,
            )
            return
        card.sync(card.state if card.state else {}, title=title, kind=kind)
        card.draw(
            screen,
            frame,
            border_color=border_color,
            editable=editable,
            opponent=opponent if CharacterProfileOverlay._is_warrior(opponent) else None,
        )

    def handle_click(self, position):
        if self.collection_panel.is_open:
            self.collection_panel.handle_click(position)
            return "handled", None
        if self.deck_panel.is_open:
            selected = self.deck_panel.handle_click(position)
            if isinstance(selected, dict):
                self.selected_deck = selected
                return "deck_selected", selected
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
        if self.is_open and self.deck_button.collidepoint(position):
            decks = self.deck_loader() if self.deck_loader else []
            self.deck_panel.open(decks)
            return "handled", None
        
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
        opponent = self.counterpart if self.counterpart is not None else opponent
        self.player_card = self._card_for_profile(opponent or self.profile, self.player_card)
        self.card = self._card_for_profile(self.profile, self.card)
        
        # Если show_player_only=True, показываем только левую панель (ТЕКУЩИЙ ИГРОК)
        if show_player_only:
            self.player_card.sync(self.profile, title="ТЕКУЩИЙ ИГРОК", kind="player")
            self._draw_card(
                self.player_card,
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
            draw_button(screen, self.deck_button, "КОЛОДА", self.action_font, color=(90, 120, 190))
            # Рюкзак (над всем остальным)
            self.backpack_panel.draw(screen)
            self.collection_panel.draw(screen)
            self.deck_panel.draw(screen)
            return
        
        if show_counterpart and opponent is not None:
            self.player_card.sync(opponent, title="ТЕКУЩИЙ ИГРОК", kind="player")
            self._draw_card(
                self.player_card,
                screen,
                self.player_frame,
                border_color=(80, 180, 120),
                editable=True,
                opponent=self.profile,
            )
        self.card.sync(self.profile, title="ПРОФИЛЬ ПЕРСОНАЖА", kind=self.profile.get("kind", "player"))
        self._draw_card(
            self.card,
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
        draw_button(screen, self.deck_button, "КОЛОДА", self.action_font, color=(90, 120, 190))
        # Рюкзак (над всем остальным)
        self.backpack_panel.draw(screen)
        self.collection_panel.draw(screen)
        self.deck_panel.draw(screen)
