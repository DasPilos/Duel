import time
from pathlib import Path

import pygame

from core import settings
from ui.hud import draw_button, draw_text


class CardAreaRenderer:
    CARD_WIDTH = 150
    CARD_HEIGHT = 200
    GAP = 20
    POINT_ICON_SIZE = 60
    POINT_ICON_GAP = 20
    CARD_COST_FONT_SIZE = 21
    CARD_COST_COLOR = (0, 0, 0)
    CARD_COST_GLOW_COLOR = (255, 255, 255)
    CARD_COST_GLOW_RADIUS = 1
    STRENGTH_COST_TOP_OFFSET = 9
    ENDURANCE_COST_BOTTOM_OFFSET = 10
    AGILITY_COST_LEFT_OFFSET = 12
    INTUITION_COST_RIGHT_OFFSET = 12
    TOOLTIP_TITLE_FONT_SIZE = settings.SMALL_FONT_SIZE + 4

    def __init__(self, scene, layout):
        self.scene = scene
        self.layout = layout
        self.card_cost_font = pygame.font.SysFont(
            settings.FONT_NAME,
            self.CARD_COST_FONT_SIZE,
            bold=True,
        )
        self.tooltip_title_font = pygame.font.SysFont(
            settings.FONT_NAME,
            self.TOOLTIP_TITLE_FONT_SIZE,
            bold=True,
        )
        self.point_font = pygame.font.SysFont(
            settings.FONT_NAME,
            72,
            bold=True,
        )
        self.battle_table_image = None
        table_path = Path(__file__).resolve().parent.parent.parent / "assets" / "combat" / "battle_table.png"
        try:
            self.battle_table_image = pygame.image.load(str(table_path)).convert()
        except (pygame.error, OSError):
            self.battle_table_image = None
        self.card_back_image = None
        back_path = Path(__file__).resolve().parent.parent.parent / "assets" / "cards" / "backs" / "card_back.png"
        try:
            source = pygame.image.load(str(back_path)).convert_alpha()
            self.card_back_image = pygame.transform.smoothscale(source, (self.CARD_WIDTH, self.CARD_HEIGHT))
        except (pygame.error, OSError):
            self.card_back_image = None
        self.strength_number_images = {}
        strength_number_path = Path(__file__).resolve().parent.parent.parent / "assets" / "cards" / "numbers" / "strength"
        try:
            for value in range(6):
                image_path = strength_number_path / f"S{value}.png"
                if image_path.exists():
                    source = pygame.image.load(str(image_path)).convert_alpha()
                    self.strength_number_images[value] = pygame.transform.smoothscale(
                        source,
                        (self.POINT_ICON_SIZE, self.POINT_ICON_SIZE),
                    )
        except (pygame.error, OSError):
            self.strength_number_images = {}
        self.endurance_number_images = {}
        endurance_number_path = Path(__file__).resolve().parent.parent.parent / "assets" / "cards" / "numbers" / "endurance"
        try:
            for value in range(6):
                image_path = endurance_number_path / f"V{value}.png"
                if image_path.exists():
                    source = pygame.image.load(str(image_path)).convert_alpha()
                    self.endurance_number_images[value] = pygame.transform.smoothscale(
                        source,
                        (self.POINT_ICON_SIZE, self.POINT_ICON_SIZE),
                    )
        except (pygame.error, OSError):
            self.endurance_number_images = {}
        self.intuition_number_images = {}
        intuition_number_path = Path(__file__).resolve().parent.parent.parent / "assets" / "cards" / "numbers" / "intuition"
        try:
            for value in range(6):
                image_path = intuition_number_path / f"I{value}.png"
                if image_path.exists():
                    source = pygame.image.load(str(image_path)).convert_alpha()
                    self.intuition_number_images[value] = pygame.transform.smoothscale(
                        source,
                        (self.POINT_ICON_SIZE, self.POINT_ICON_SIZE),
                    )
        except (pygame.error, OSError):
            self.intuition_number_images = {}
        self.face_images = {}
        self.card_face_images = {}
        face_names = {
            "Сила": "strength",
            "Ловкость": "agility",
            "Интуиция": "intuition",
            "Выносливость": "endurance",
        }
        face_path = Path(__file__).resolve().parent.parent.parent / "assets" / "cards" / "faces"
        for group_name, filename in face_names.items():
            try:
                source = pygame.image.load(str(face_path / f"{filename}.png")).convert_alpha()
                self.face_images[group_name] = pygame.transform.smoothscale(source, (self.CARD_WIDTH, self.CARD_HEIGHT))
            except (pygame.error, OSError):
                pass
        self.agility_number_images = {}
        agility_number_path = Path(__file__).resolve().parent.parent.parent / "assets" / "cards" / "numbers" / "agility"
        try:
            for value in range(6):
                image_path = agility_number_path / f"L{value}.png"
                if image_path.exists():
                    source = pygame.image.load(str(image_path)).convert_alpha()
                    self.agility_number_images[value] = pygame.transform.smoothscale(
                        source,
                        (self.POINT_ICON_SIZE, self.POINT_ICON_SIZE),
                    )
        except (pygame.error, OSError):
            self.agility_number_images = {}

    def card_rect(self, area, count, index):
        """Рисует карту в нужной позиции.
        - Для зон с 5 карт (драфт): фиксированные 5 позиций
        - Для руки и других: реальное центрирование по count
        """
        # Проверяем если это зона с фиксированными 5 карт (подсказка: если count == 5 и area внутри card_table)
        # Это будет зона драфта
        is_draft_area = (count == 5 and 
                         area.x >= self.layout.card_table.x and 
                         area.right <= self.layout.card_table.right)
        
        if is_draft_area:
            # Драфт: всегда 5 позиций для фиксированного расположения
            width = min(self.CARD_WIDTH, max(50, (area.width - self.GAP * 4) // 5))
            total_width = width * 5 + self.GAP * 4
            start_x = area.centerx - total_width // 2
            height = min(self.CARD_HEIGHT, area.height)
            return pygame.Rect(start_x + index * (width + self.GAP), area.y, width, height)
        else:
            # Рука, стол и другие: центрируем по реальному количеству карт
            width = min(self.CARD_WIDTH, max(50, (area.width - self.GAP * max(0, count - 1)) // max(1, count)))
            total_width = width * count + self.GAP * max(0, count - 1)
            start_x = area.centerx - total_width // 2
            height = min(self.CARD_HEIGHT, area.height)
            return pygame.Rect(start_x + index * (width + self.GAP), area.y, width, height)

    def draw(self, screen):
        battle = self.scene.battle
        if self.scene.phase != "result":
            if self.battle_table_image is not None:
                screen.blit(self.battle_table_image, self.layout.card_table)
            else:
                pygame.draw.rect(screen, (27, 31, 43), self.layout.card_table, border_radius=8)
            self._draw_deck(screen, battle)
            self._draw_discard(screen, battle)
        if self.scene.phase in ("intro_table", "intro_deck", "draft_reveal", "draft", "draft_transfer", "enemy_transfer", "draft_bonus_transfer", "draft_cleanup"):
            if self.scene.phase in ("intro_table", "intro_deck"):
                visible_table = []
            elif self.scene.phase == "draft_reveal":
                elapsed = time.monotonic() - self.scene.draft_reveal_started
                visible_table = []
            else:
                visible_table = battle.table
            pygame.draw.rect(screen, (125, 111, 76), self.layout.card_table, 2, border_radius=8)
            is_redraft = battle.draft_mode == "redraft"
            title = "ПОВТОРНЫЙ ДРАФТ" if is_redraft else "СТАРТОВЫЙ ДРАФТ"
            draw_text(screen, self.scene.font, title, self.layout.card_table.x + 20, self.layout.card_table.y + 12, (230, 210, 150))
            if self.scene.phase == "draft_cleanup":
                message = "Возврат в колоду..."
            else:
                message = "Выберите две карты" if is_redraft else "Выберите до трёх карт"
            draw_text(screen, self.scene.small_font, message, self.layout.card_table.right - 220, self.layout.card_table.y + 16, (170, 170, 170))
            if self.scene.phase == "draft_cleanup":
                elapsed = time.monotonic() - self.scene.draft_cleanup_started
                progress = min(1.0, max(0.0, elapsed / settings.DRAFT_CLEANUP_SECONDS))
                for index, card in enumerate(battle.table):
                    source_area = pygame.Rect(
                        self.layout.card_table.x + 20,
                        self.layout.card_table.y + 5 + (self.CARD_HEIGHT + self.GAP if index >= 5 else 0),
                        self.layout.card_table.width - 40,
                        self.CARD_HEIGHT,
                    )
                    source = self.card_rect(source_area, 5, index % 5)
                    center_x = int(source.centerx + (self.layout.deck_rect.centerx - source.centerx) * progress)
                    center_y = int(source.centery + (self.layout.deck_rect.centery - source.centery) * progress)
                    moving_area = pygame.Rect(center_x - self.CARD_WIDTH // 2, center_y - self.CARD_HEIGHT // 2, self.CARD_WIDTH, self.CARD_HEIGHT)
                    self._draw_cards(screen, [card], moving_area, [])
                visible_table = []
            row_area = pygame.Rect(self.layout.card_table.x + 20, self.layout.card_table.y + 5, self.layout.card_table.width - 40, self.CARD_HEIGHT)
            if self.scene.phase == "draft_reveal":
                self._draw_reveal_cards(screen, battle.table, elapsed, row_area)
            else:
                self._draw_cards(screen, visible_table[:5], row_area, [])
            row_area.y += self.CARD_HEIGHT + self.GAP
            if self.scene.phase != "draft_reveal":
                self._draw_cards(screen, visible_table[5:], row_area, [])
            enemy_hand = list(battle.hands["enemy"])
            player_hand = list(battle.hands["player"])
            if self.scene.phase == "enemy_transfer" and self.scene.enemy_card_transfer is not None:
                enemy_hand.remove(self.scene.enemy_card_transfer["card"])
            if self.scene.phase == "draft_transfer" and self.scene.card_transfer is not None:
                player_hand.remove(self.scene.card_transfer["card"])
            self._draw_cards(screen, enemy_hand, self.layout.enemy_hand, enemy_hand, highlight_available=False)
            self._draw_cards(screen, player_hand, self.layout.player_hand, player_hand, highlight_available=False)
            if self.scene.phase == "draft_transfer" and self.scene.card_transfer is not None:
                transfer = self.scene.card_transfer
                target = self.card_rect(self.layout.player_hand, len(battle.hands["player"]), len(battle.hands["player"]) - 1)
                progress = min(1.0, max(0.0, (time.monotonic() - transfer["started"]) / settings.PLAYER_DRAFT_PICK_MOVE_SECONDS))
                center_x = int(transfer["source"].centerx + (target.centerx - transfer["source"].centerx) * progress)
                center_y = int(transfer["source"].centery + (target.centery - transfer["source"].centery) * progress)
                moving_area = pygame.Rect(center_x - self.CARD_WIDTH // 2, center_y - self.CARD_HEIGHT // 2, self.CARD_WIDTH, self.CARD_HEIGHT)
                self._draw_cards(screen, [transfer["card"]], moving_area, [])
            if self.scene.phase == "draft_bonus_transfer" and self.scene.card_transfer is not None:
                transfer = self.scene.card_transfer
                target_area = self.layout.player_hand if transfer["target_side"] == "player" else self.layout.enemy_hand
                hand = battle.hands[transfer["target_side"]]
                target = self.card_rect(target_area, len(hand) + 1, len(hand))
                progress = min(1.0, max(0.0, (time.monotonic() - transfer["started"]) / settings.TABLE_TO_HAND_MOVE_SECONDS))
                center_x = int(transfer["source"].centerx + (target.centerx - transfer["source"].centerx) * progress)
                center_y = int(transfer["source"].centery + (target.centery - transfer["source"].centery) * progress)
                moving_area = pygame.Rect(center_x - self.CARD_WIDTH // 2, center_y - self.CARD_HEIGHT // 2, self.CARD_WIDTH, self.CARD_HEIGHT)
                self._draw_cards(screen, [transfer["card"]], moving_area, [])
            if self.scene.phase == "enemy_transfer" and self.scene.enemy_card_transfer is not None:
                transfer = self.scene.enemy_card_transfer
                target = self.card_rect(self.layout.enemy_hand, len(battle.hands["enemy"]), len(battle.hands["enemy"]) - 1)
                progress = min(1.0, max(0.0, (time.monotonic() - transfer["started"]) / settings.TABLE_TO_HAND_MOVE_SECONDS))
                center_x = int(transfer["source"].centerx + (target.centerx - transfer["source"].centerx) * progress)
                center_y = int(transfer["source"].centery + (target.centery - transfer["source"].centery) * progress)
                moving_area = pygame.Rect(center_x - self.CARD_WIDTH // 2, center_y - self.CARD_HEIGHT // 2, self.CARD_WIDTH, self.CARD_HEIGHT)
                self._draw_cards(screen, [transfer["card"]], moving_area, [])

        if self.scene.phase in ("planning", "card_return"):
            visible_hand = [card for card in battle.hands["player"] if card not in battle.selected["player"]]
            self._draw_cards(screen, visible_hand, self.layout.player_hand, [], highlight_available=True)
            enemy_hand = [card for card in battle.hands["enemy"] if card not in battle.selected["enemy"]]
            self._draw_cards(screen, enemy_hand, self.layout.enemy_hand, [], highlight_available=False)
            self._draw_cards(screen, battle.selected["player"], self.layout.player_selected, battle.selected["player"], highlight_available=False)
            draw_button(screen, self.layout.play_cards_button, "ЗАКОНЧИТЬ ХОД", self.scene.small_font, color=(180, 130, 60))
        if self.scene.phase == "waiting_enemy":
            # Рисуем руку игрока и выбранные карты
            visible_hand = [card for card in battle.hands["player"] if card not in battle.selected["player"]]
            self._draw_cards(screen, visible_hand, self.layout.player_hand, [], highlight_available=True)
            enemy_hand = [card for card in battle.hands["enemy"] if card not in battle.selected["enemy"]]
            self._draw_cards(screen, enemy_hand, self.layout.enemy_hand, [], highlight_available=False)
            self._draw_cards(screen, battle.selected["enemy"], self.layout.enemy_selected, battle.selected["enemy"], highlight_available=False)
            self._draw_cards(screen, battle.selected["player"], self.layout.player_selected, battle.selected["player"], highlight_available=False)
        if self.scene.phase == "clash":
            # Просто рисуем карты без анимации движения
            self._draw_cards(screen, battle.selected["player"], self.layout.player_selected, battle.selected["player"], highlight_available=False)
            self._draw_cards(screen, battle.selected["enemy"], self.layout.enemy_selected, battle.selected["enemy"], highlight_available=False)
        if self.scene.phase in ("damage", "deck_shuffle"):
            # Рисуем руки и выбранные карты во время подсчета урона и перетасовки
            visible_hand = [card for card in battle.hands["player"] if card not in battle.selected["player"]]
            self._draw_cards(screen, visible_hand, self.layout.player_hand, [], highlight_available=True)
            enemy_hand = [card for card in battle.hands["enemy"] if card not in battle.selected["enemy"]]
            self._draw_cards(screen, enemy_hand, self.layout.enemy_hand, [], highlight_available=False)
            self._draw_cards(screen, battle.selected["player"], self.layout.player_selected, battle.selected["player"], highlight_available=False)
            self._draw_cards(screen, battle.selected["enemy"], self.layout.enemy_selected, battle.selected["enemy"], highlight_available=False)
        if self.scene.phase == "card_draw":
            # Рисуем руки и выбранные карты во время добора
            visible_hand = [card for card in battle.hands["player"] if card not in battle.selected["player"]]
            if self.scene.draw_transfer is not None and self.scene.draw_transfer["side"] == "player":
                visible_hand = [card for card in visible_hand if card != self.scene.draw_transfer["card"]]
            self._draw_cards(screen, visible_hand, self.layout.player_hand, [], highlight_available=True)
             
            enemy_hand = [card for card in battle.hands["enemy"] if card not in battle.selected["enemy"]]
            if self.scene.draw_transfer is not None and self.scene.draw_transfer["side"] == "enemy":
                enemy_hand = [card for card in enemy_hand if card != self.scene.draw_transfer["card"]]
            self._draw_cards(screen, enemy_hand, self.layout.enemy_hand, [], highlight_available=False)
             
            self._draw_cards(screen, battle.selected["player"], self.layout.player_selected, battle.selected["player"], highlight_available=False)
            self._draw_cards(screen, battle.selected["enemy"], self.layout.enemy_selected, battle.selected["enemy"], highlight_available=False)
             
            # Рисуем летящую карту
            if self.scene.draw_transfer is not None:
                transfer = self.scene.draw_transfer
                target_area = self.layout.player_hand if transfer["side"] == "player" else self.layout.enemy_hand
                hand = battle.hands[transfer["side"]]
                target = self.card_rect(target_area, len(hand) + 1, len(hand))
                progress = min(1.0, max(0.0, (time.monotonic() - transfer["started"]) / settings.CARD_MOVE_SECONDS))
                center_x = int(self.layout.deck_rect.centerx + (target.centerx - self.layout.deck_rect.centerx) * progress)
                center_y = int(self.layout.deck_rect.centery + (target.centery - self.layout.deck_rect.centery) * progress)
                self._draw_moving_card(screen, transfer["card"], center_x, center_y, progress)
        self._draw_points(screen, battle.action_points["player"], self.layout.player_points, "")
        self._draw_points(screen, battle.action_points["enemy"], self.layout.enemy_points, "")

    def _draw_reveal_cards(self, screen, cards, elapsed, first_row):
        for index, card in enumerate(cards[:10]):
            start = settings.DRAFT_REVEAL_START_DELAY_SECONDS + index * settings.DRAFT_CARD_DELAY_SECONDS
            if elapsed < start:
                continue
            progress = min(1.0, (elapsed - start) / settings.CARD_MOVE_SECONDS)
            row = first_row if index < 5 else first_row.move(0, self.CARD_HEIGHT + self.GAP)
            target = self.card_rect(row, 5, index % 5)
            center_x = int(self.layout.deck_rect.centerx + (target.centerx - self.layout.deck_rect.centerx) * progress)
            center_y = int(self.layout.deck_rect.centery + (target.centery - self.layout.deck_rect.centery) * progress)
            self._draw_moving_card(screen, card, center_x, center_y, progress)

    def _draw_moving_card(self, screen, card, center_x, center_y, progress):
        """Рисует карту, летящую из колоды с переворотом вокруг вертикальной оси."""
        flip_progress = min(1.0, max(0.0, progress))
        width_scale = abs(2.0 * flip_progress - 1.0)
        width = max(2, int(self.CARD_WIDTH * width_scale))
        rect = pygame.Rect(0, 0, width, self.CARD_HEIGHT)
        rect.center = (center_x, center_y)
        if flip_progress < 0.5:
            self._draw_card_back(screen, rect)
        else:
            self._draw_card_front_scaled(screen, card, rect)

    def _draw_rotating_card(self, screen, card, center_x, center_y, progress):
        """Рисует карту с переворотом во время полёта в сток: 0% = лицо, 100% = рубашка."""
        # progress от 0 (лицо) до 1 (рубашка)
        # Масштабируем ширину для эффекта переворота
        width_scale = abs(2.0 * progress - 1.0)
        width = max(2, int(self.CARD_WIDTH * width_scale))
        rect = pygame.Rect(0, 0, width, self.CARD_HEIGHT)
        rect.center = (center_x, center_y)
        # На первой половине показываем лицо, на второй - рубашку
        if progress < 0.5:
            self._draw_card_front_scaled(screen, card, rect)
        else:
            self._draw_card_back(screen, rect)

    def _draw_card_back(self, screen, rect):
        if self.card_back_image is not None and rect.width > 0 and rect.height > 0:
            scaled_back = pygame.transform.scale(self.card_back_image, (int(rect.width), int(rect.height)))
            screen.blit(scaled_back, rect)
            pygame.draw.rect(screen, (190, 170, 110), rect, 2, border_radius=6)
            return
        pygame.draw.rect(screen, (57, 63, 88), rect, border_radius=6)
        pygame.draw.rect(screen, (190, 170, 110), rect, 2, border_radius=6)
        inner = rect.inflate(-12, -12)
        pygame.draw.rect(screen, (43, 48, 70), inner, 2, border_radius=4)
        if rect.width > 12:
            pygame.draw.line(screen, (190, 170, 110), inner.topleft, inner.bottomright, 1)
            pygame.draw.line(screen, (190, 170, 110), inner.topright, inner.bottomleft, 1)

    def _draw_card_front_scaled(self, screen, card, rect):
        face_image = self._card_face_image(card)
        if face_image is not None:
            image = pygame.transform.smoothscale(face_image, rect.size)
            screen.blit(image, rect)
        else:
            pygame.draw.rect(screen, (48, 53, 70), rect, border_radius=6)
        pygame.draw.rect(screen, (190, 170, 110), rect, 2, border_radius=6)
        if rect.width < 20:
            return
        self._draw_card_costs(screen, card, rect)

    def _card_face_image(self, card):
        image_path = getattr(card, "image_path", "")
        if not image_path:
            return self.face_images.get(card.group_name)
        if image_path not in self.card_face_images:
            path = Path(image_path)
            if not path.is_absolute():
                path = Path(__file__).resolve().parent.parent.parent / path
            try:
                source = pygame.image.load(str(path)).convert_alpha()
                self.card_face_images[image_path] = pygame.transform.smoothscale(
                    source,
                    (self.CARD_WIDTH, self.CARD_HEIGHT),
                )
            except (pygame.error, OSError):
                self.card_face_images[image_path] = self.face_images.get(card.group_name)
        return self.card_face_images[image_path]

    def _draw_deck(self, screen, battle):
        rect = self.layout.deck_rect
        for offset in (8, 5, 2):
            self._draw_card_back(screen, rect.move(-offset, -offset))
        self._draw_pile_count(screen, rect, "КОЛОДА", len(battle.deck))

    def _draw_discard(self, screen, battle):
        rect = self.layout.discard_rect
        for offset in (8, 5, 2):
            self._draw_card_back(screen, rect.move(-offset, -offset))
        self._draw_pile_count(screen, rect, "СБРОС", len(battle.discard))

    def _draw_pile_count(self, screen, rect, title, count):
        title_surface = self.card_cost_font.render(title, True, (245, 225, 160))
        title_rect = title_surface.get_rect(midbottom=(rect.centerx, rect.top - 8))
        screen.blit(title_surface, title_rect)

        count_surface = self.point_font.render(str(count), True, (255, 255, 255))
        count_rect = count_surface.get_rect(center=(rect.centerx, rect.top + 42))
        badge = count_rect.inflate(24, 12)
        badge_surface = pygame.Surface(badge.size, pygame.SRCALPHA)
        badge_surface.fill((15, 17, 24, 205))
        screen.blit(badge_surface, badge)
        pygame.draw.rect(screen, (225, 200, 120), badge, 2, border_radius=8)
        screen.blit(count_surface, count_rect)

    def _draw_points(self, screen, points, rect, title):
        if title:
            draw_text(screen, self.scene.small_font, title, rect.x, rect.y, (210, 210, 210))
        labels = (
            ("strength", settings.STRENGTH_COLOR, self.strength_number_images),
            ("endurance", settings.ENDURANCE_COLOR, self.endurance_number_images),
            ("agility", settings.AGILITY_COLOR, self.agility_number_images),
            ("intuition", settings.INTUITION_COLOR, self.intuition_number_images),
        )
        total_width = (
            len(labels) * self.POINT_ICON_SIZE
            + (len(labels) - 1) * self.POINT_ICON_GAP
        )
        start_x = rect.centerx - total_width // 2
        for index, (key, color, images) in enumerate(labels):
            value = points[key]
            image = images.get(value)
            center = (
                start_x
                + index * (self.POINT_ICON_SIZE + self.POINT_ICON_GAP)
                + self.POINT_ICON_SIZE // 2,
                rect.centery,
            )
            if image is not None:
                screen.blit(image, image.get_rect(center=center))
            else:
                text = self.point_font.render(str(value), True, color)
                screen.blit(text, text.get_rect(center=center))

    def _draw_cards(self, screen, cards, area, selected, highlight_available=False):
        selected_keys = {card.key for card in selected}
        hovered_card = None
        hovered_rect = None
        for index, card in enumerate(cards):
            rect = self.card_rect(area, len(cards), index)
            is_selected = card.key in selected_keys
            if card.effect_type.startswith("instant_"):
                is_available = (
                    highlight_available
                    and self.scene.battle.can_activate_instant("player", card)
                )
            else:
                is_available = (
                    highlight_available
                    and self.scene.battle.can_select("player", card)
                )
            if is_selected:
                color = (55, 135, 80)
            elif is_available:
                color = (45, 105, 68)
            else:
                color = (48, 53, 70)
            face_image = self._card_face_image(card)
            if face_image is not None:
                screen.blit(pygame.transform.smoothscale(face_image, rect.size), rect)
            else:
                pygame.draw.rect(screen, color, rect, border_radius=6)
            pygame.draw.rect(screen, (190, 170, 110), rect, 2, border_radius=6)
            self._draw_card_costs(screen, card, rect)
            if highlight_available:
                self._draw_card_availability(screen, rect, is_available)
            if rect.collidepoint(pygame.mouse.get_pos()):
                hovered_card = card
                hovered_rect = rect

        if hovered_card is not None:
            self._draw_card_tooltip(screen, hovered_card, hovered_rect)

    def _draw_card_availability(self, screen, rect, is_available):
        if is_available:
            glow = pygame.Surface((rect.width + 8, rect.height + 8), pygame.SRCALPHA)
            glow_rect = glow.get_rect()
            pygame.draw.rect(glow, (80, 235, 125, 80), glow_rect, 4, border_radius=8)
            screen.blit(glow, rect.move(-4, -4))
            pygame.draw.rect(screen, (115, 255, 145), rect.inflate(4, 4), 2, border_radius=8)
            marker = pygame.Rect(rect.right - 19, rect.top + 8, 12, 12)
            pygame.draw.circle(screen, (30, 52, 34), marker.center, 7)
            pygame.draw.circle(screen, (115, 255, 145), marker.center, 5)
            return
        overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
        overlay.fill((5, 7, 12, 105))
        screen.blit(overlay, rect)
        pygame.draw.rect(screen, (90, 82, 75), rect, 2, border_radius=6)

    def _draw_card_tooltip(self, screen, card, card_rect):
        description = self._card_description(card)
        description_font = self.scene.small_font
        title_font = self.tooltip_title_font
        max_width = 300
        lines = []
        current = ""
        for word in description.split():
            candidate = f"{current} {word}".strip()
            if current and description_font.size(candidate)[0] > max_width - 24:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)

        content_width = max(
            title_font.size(card.name)[0],
            max(description_font.size(line)[0] for line in lines),
        )
        width = max(max_width, content_width + 24)
        title_y = 10
        description_y = title_y + title_font.get_linesize() + 6
        height = description_y + len(lines) * description_font.get_linesize() + 10
        mouse_x, mouse_y = pygame.mouse.get_pos()
        tooltip = pygame.Rect(mouse_x + 14, mouse_y + 14, width, height)
        if tooltip.right > settings.WIDTH:
            tooltip.right = mouse_x - 14
        if tooltip.bottom > settings.HEIGHT:
            tooltip.bottom = mouse_y - 14
        pygame.draw.rect(screen, (22, 25, 36), tooltip, border_radius=6)
        pygame.draw.rect(screen, (210, 185, 105), tooltip, 2, border_radius=6)
        title = title_font.render(card.name, True, (245, 225, 150))
        screen.blit(title, (tooltip.x + 12, tooltip.y + title_y))
        for index, line in enumerate(lines):
            text = description_font.render(line, True, (230, 230, 235))
            screen.blit(
                text,
                (
                    tooltip.x + 12,
                    tooltip.y + description_y + index * description_font.get_linesize(),
                ),
            )

    @staticmethod
    def _card_description(card):
        data = card.effect_data
        damage_text = f"Наносит {data.get('dice', '')} урона."
        duration = max(1, int(card.effect_duration))
        if duration % 10 == 1 and duration % 100 != 11:
            exchange_word = "размен"
        elif duration % 10 in (2, 3, 4) and duration % 100 not in (12, 13, 14):
            exchange_word = "размена"
        else:
            exchange_word = "разменов"
        duration_text = f"на {duration} {exchange_word}"
        stat_names = {
            "strength": "Силу",
            "endurance": "Выносливость",
            "agility": "Ловкость",
            "intuition": "Интуицию",
        }
        instant_stat_names = {
            "strength": "Силы",
            "endurance": "Выносливости",
            "agility": "Ловкости",
            "intuition": "Интуиции",
        }
        descriptions = {
            "damage": damage_text,
            "damage_stat_debuff": (
                f"{damage_text} При попадании снижает "
                f"{stat_names.get(data.get('stat'), 'характеристику')} противника "
                f"на {data.get('amount', 0)} {duration_text}."
            ),
            "damage_critical_debuff": (
                f"{damage_text} При попадании снижает шанс критического удара "
                f"противника на {data.get('amount', 0)}% {duration_text}."
            ),
            "damage_dodge_debuff": (
                f"{damage_text} При попадании снижает шанс уворота противника "
                f"на {data.get('amount', 0)}% {duration_text}."
            ),
            "damage_dodge_critical_debuff": (
                f"{damage_text} При попадании снижает шанс уворота противника "
                f"на {data.get('dodge_amount', 0)}% и шанс критического удара "
                f"противника на {data.get('critical_amount', 0)}% {duration_text}."
            ),
            "multi_damage": f"Наносит {data.get('hits', 2)} отдельных удара по броску {data.get('dice', '')}.",
            "damage_recoil": f"Наносит урон по броску {data.get('dice', '')}. При некритическом ударе вы получаете {data.get('recoil', 0)} урона.",
            "damage_reduce": f"{damage_text} Следующая атака по вам наносит на {data.get('reduce', 0)} урона меньше.",
            "heal": f"Восстанавливает здоровье по броску {data.get('dice', '')}.",
            "dodge": f"Увеличивает уклонение на {data.get('bonus', 0)}%.",
            "anti_dodge": f"Снижает уклонение противника на {data.get('bonus', 0)}%.",
            "damage_dodge": f"Наносит {data.get('dice', '')} урона и увеличивает уклонение на {data.get('bonus', 0)}%.",
            "critical": f"Увеличивает шанс критического удара на {data.get('bonus', 0)}%.",
            "damage_resistance": f"Снижает получаемый урон до {int(data.get('ratio', 1) * 100)}% от обычного.",
            "extra_action_points": "Повторно начисляет очки хода. Один раз за бой.",
            "heal_duration": f"Восстанавливает {data.get('dice', '')} HP и лечит ещё {data.get('duration', 0)} хода.",
            "instant_action_points": (
                "Двойной ЛКМ во время подготовки: мгновенно добавляет "
                f"{data.get('amount', 0)} очка "
                f"{instant_stat_names.get(data.get('stat'), 'характеристики')}. "
                "Стоимость списывается сразу, карта уходит в сброс и занимает "
                "одно из двух мест карт текущего размена."
            ),
        }
        return descriptions.get(card.effect_type, "Особое действие карты.")

    def _draw_card_costs(self, screen, card, rect):
        costs = zip(
            (
                card.strength_cost,
                card.endurance_cost,
                card.agility_cost,
                card.intuition_cost,
            ),
            self._card_cost_layout(rect),
        )
        for value, (position, anchor) in costs:
            glow = self.card_cost_font.render(
                str(value),
                True,
                self.CARD_COST_GLOW_COLOR,
            )
            text = self.card_cost_font.render(
                str(value),
                True,
                self.CARD_COST_COLOR,
            )
            text_rect = text.get_rect(**{anchor: position})
            radius = self.CARD_COST_GLOW_RADIUS
            for offset_x, offset_y in (
                (-radius, -radius),
                (0, -radius),
                (radius, -radius),
                (-radius, 0),
                (radius, 0),
                (-radius, radius),
                (0, radius),
                (radius, radius),
            ):
                screen.blit(glow, text_rect.move(offset_x, offset_y))
            screen.blit(text, text_rect)

    @staticmethod
    def _card_cost_layout(rect):
        return (
            (
                (rect.centerx, rect.top + CardAreaRenderer.STRENGTH_COST_TOP_OFFSET),
                "midtop",
            ),
            (
                (
                    rect.centerx,
                    rect.bottom - CardAreaRenderer.ENDURANCE_COST_BOTTOM_OFFSET,
                ),
                "midbottom",
            ),
            (
                (rect.left + CardAreaRenderer.AGILITY_COST_LEFT_OFFSET, rect.centery),
                "midleft",
            ),
            (
                (
                    rect.right - CardAreaRenderer.INTUITION_COST_RIGHT_OFFSET,
                    rect.centery,
                ),
                "midright",
            ),
        )
