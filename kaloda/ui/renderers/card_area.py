import math
import time
from pathlib import Path

import pygame

from kaloda.combat.mechanics import (
    get_critical_chance,
    get_critical_damage_multiplier,
    weapon_fixed_damage,
)
from kaloda.combat.physical_effects import describe_physical_card, max_dice_damage
from kaloda import settings
from kaloda.ui.hud import draw_button, draw_text


class CardAreaRenderer:
    CARD_WIDTH = 150
    CARD_HEIGHT = 200
    GAP = 20
    DRAFT_COLUMNS = 5
    STARTING_DRAFT_COLUMNS = 11
    STARTING_DRAFT_GAP = 8
    RESOURCE_COST_LABELS = {
        "mana": "МАНА",
        "rage": "ЯР.",
        "accuracy": "МЕТ.",
        "concentration": "КОНЦ.",
        "unique": "РЕС.",
    }
    RESOURCE_COST_COLORS = {
        "mana": (115, 190, 240),
        "rage": (235, 105, 95),
        "accuracy": (135, 210, 130),
        "concentration": (190, 145, 235),
        "unique": (120, 220, 135),
    }
    CARD_COST_FONT_SIZE = 16
    TOOLTIP_TITLE_FONT_SIZE = settings.SMALL_FONT_SIZE + 4

    def __init__(self, scene, layout):
        self.scene = scene
        self.layout = layout
        self.details_card = None
        self.details_close_rect = pygame.Rect(0, 0, 0, 0)
        self.details_scroll = 0
        self._draft_slots = []
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
        self.pile_count_font = pygame.font.SysFont(
            settings.FONT_NAME,
            72,
            bold=True,
        )
        self.battle_table_image = None
        table_path = settings.ASSETS_DIR / "combat" / "battle_table.png"
        try:
            self.battle_table_image = pygame.image.load(str(table_path)).convert()
        except (pygame.error, OSError):
            self.battle_table_image = None
        self.card_back_image = None
        back_path = settings.ASSETS_DIR / "cards" / "backs" / "card_back.png"
        try:
            source = pygame.image.load(str(back_path)).convert_alpha()
            self.card_back_image = pygame.transform.smoothscale(source, (self.CARD_WIDTH, self.CARD_HEIGHT))
        except (pygame.error, OSError):
            self.card_back_image = None
        self.face_images = {}
        self.card_face_images = {}

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
        if area == self.layout.card_table and count > 5:
            columns = 8
            width = min(self.CARD_WIDTH, max(50, (area.width - self.GAP * (columns - 1)) // columns))
            row = index // columns
            column = index % columns
            height = min(self.CARD_HEIGHT, max(50, (area.height - self.GAP * 2) // 3))
            start_x = area.centerx - (width * columns + self.GAP * (columns - 1)) // 2
            return pygame.Rect(start_x + column * (width + self.GAP), area.y + row * (height + self.GAP), width, height)
        else:
            # Рука, стол и другие: центрируем по реальному количеству карт
            width = min(self.CARD_WIDTH, max(50, (area.width - self.GAP * max(0, count - 1)) // max(1, count)))
            total_width = width * count + self.GAP * max(0, count - 1)
            start_x = area.centerx - total_width // 2
            height = min(self.CARD_HEIGHT, area.height)
            return pygame.Rect(start_x + index * (width + self.GAP), area.y, width, height)

    def draft_slots(self):
        table_cards = self.scene.battle.table
        if any(card not in self._draft_slots for card in table_cards):
            self._draft_slots = list(table_cards)
        else:
            self._draft_slots = [card if card in table_cards else None for card in self._draft_slots]
        return self._draft_slots

    def draft_slot_rect(self, index):
        table = self.layout.card_table
        if self.scene.battle.draft_mode == "starting":
            columns = self.STARTING_DRAFT_COLUMNS
            gap = self.STARTING_DRAFT_GAP
            width = min(
                self.CARD_WIDTH,
                (table.width - gap * (columns - 1)) // columns,
            )
            height = round(width * self.CARD_HEIGHT / self.CARD_WIDTH)
            total_width = columns * width + (columns - 1) * gap
            left = table.centerx - total_width // 2
            top = table.top + 48
        else:
            columns = self.DRAFT_COLUMNS
            gap = self.GAP
            width = self.CARD_WIDTH
            height = self.CARD_HEIGHT
            total_width = columns * width + (columns - 1) * gap
            total_height = 2 * height + gap
            left = table.centerx - total_width // 2
            top = table.centery - total_height // 2
        row, column = divmod(index, columns)
        return pygame.Rect(
            left + column * (width + gap),
            top + row * (height + gap),
            width,
            height,
        )

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
                message = "Выберите две карты" if is_redraft else "Выберите две стартовые карты"
            draw_text(screen, self.scene.small_font, message, self.layout.card_table.right - 220, self.layout.card_table.y + 16, (170, 170, 170))
            if self.scene.phase == "draft_cleanup":
                elapsed = time.monotonic() - self.scene.draft_cleanup_started
                progress = min(1.0, max(0.0, elapsed / settings.DRAFT_CLEANUP_SECONDS))
                for index, card in enumerate(self.draft_slots()):
                    if card is None:
                        continue
                    source = self.draft_slot_rect(index)
                    center_x = int(source.centerx + (self.layout.deck_rect.centerx - source.centerx) * progress)
                    center_y = int(source.centery + (self.layout.deck_rect.centery - source.centery) * progress)
                    moving_area = pygame.Rect(center_x - self.CARD_WIDTH // 2, center_y - self.CARD_HEIGHT // 2, self.CARD_WIDTH, self.CARD_HEIGHT)
                    self._draw_cards(screen, [card], moving_area, [])
                visible_table = []
            row_area = self.layout.card_table
            if self.scene.phase == "draft_reveal":
                self._draw_reveal_cards(screen, battle.table, elapsed, row_area)
            elif visible_table:
                for index, card in enumerate(self.draft_slots()):
                    if card is not None:
                        self._draw_card_in_rect(screen, card, self.draft_slot_rect(index))
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
            if self.scene.burn_mode and self.scene.burn_card_key is not None:
                burn_card = next(
                    (card for card in visible_hand if card.key == self.scene.burn_card_key),
                    None,
                )
                if burn_card is not None:
                    burn_rect = self.card_rect(
                        self.layout.player_hand,
                        len(visible_hand),
                        visible_hand.index(burn_card),
                    )
                    pygame.draw.rect(screen, (235, 85, 70), burn_rect, 4, border_radius=7)
            enemy_hand = [card for card in battle.hands["enemy"] if card not in battle.selected["enemy"]]
            self._draw_cards(screen, enemy_hand, self.layout.enemy_hand, [], highlight_available=False)
            self._draw_cards(screen, battle.selected["player"], self.layout.player_selected, battle.selected["player"], highlight_available=False)
            button_label = "СЖЕЧЬ КАРТУ" if self.scene.burn_mode else "ЗАКОНЧИТЬ ХОД"
            draw_button(screen, self.layout.play_cards_button, button_label, self.scene.small_font, color=(180, 90, 65) if self.scene.burn_mode else (180, 130, 60))
            if self.scene.burn_mode:
                hint = "Выберите карту в руке, затем нажмите «СЖЕЧЬ КАРТУ»"
                hint_color = (245, 170, 130)
            elif battle.burned_this_turn["player"]:
                hint = "Сжигание карты в этом ходу уже использовано"
                hint_color = (165, 165, 175)
            else:
                hint = "B — выбрать карту для сжигания (+15% маны и ресурса)"
                hint_color = (205, 205, 175)
            draw_text(
                screen,
                self.scene.small_font,
                hint,
                self.layout.play_cards_button.left,
                self.layout.play_cards_button.top - self.scene.small_font.get_linesize() - 3,
                hint_color,
            )
        if self.scene.phase == "card_draw_choice":
            for side, title, color in (
                ("enemy", "КАРТЫ ПРОТИВНИКА", (225, 125, 125)),
                ("player", "ВЫБЕРИТЕ КАРТУ", (140, 220, 155)),
            ):
                area = self.draw_choice_area(side)
                draw_text(screen, self.scene.small_font, title, area.x, area.y - 20, color)
                self._draw_cards(
                    screen,
                    battle.draw_choices[side],
                    area,
                    [],
                    highlight_available=False,
                )
            for side, cards, area in (
                ("player", battle.hands["player"], self.layout.player_hand),
                ("enemy", battle.hands["enemy"], self.layout.enemy_hand),
            ):
                self._draw_cards(
                    screen,
                    cards,
                    area,
                    battle.selected[side],
                    highlight_available=side == "player",
                )
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
        self._draw_draft_timer(screen)
        self._draw_card_hover_tooltip(screen)
        self._draw_card_details(screen)

    def _draw_card_hover_tooltip(self, screen):
        """Рисует всплывающее окно подсказки при наведении курсора мыши на карту."""
        if self.details_card is not None:
            return
        battle = self.scene.battle
        mouse_pos = pygame.mouse.get_pos()
        candidates = []
        if self.scene.phase in ("intro_table", "intro_deck", "draft_reveal", "draft", "draft_transfer", "enemy_transfer", "draft_bonus_transfer", "draft_cleanup"):
            if self.scene.phase not in ("intro_table", "intro_deck", "draft_reveal"):
                for index, card in enumerate(self.draft_slots()):
                    rect = self.draft_slot_rect(index)
                    if card is not None and rect.collidepoint(mouse_pos):
                        self._draw_card_tooltip(screen, card, rect)
                        return
        visible_hand = [card for card in battle.hands["player"] if card not in battle.selected["player"]]
        candidates.append((self.layout.player_hand, visible_hand))
        candidates.append((self.layout.player_selected, list(battle.selected["player"])))
        if self.scene.phase == "card_draw_choice":
            candidates.extend(
                (
                    self.draw_choice_area(side),
                    list(battle.draw_choices[side]),
                )
                for side in ("player", "enemy")
            )
            candidates.append(
                (self.layout.enemy_hand, list(battle.hands["enemy"]))
            )
        for area, cards in candidates:
            for index, card in enumerate(cards):
                rect = self.card_rect(area, len(cards), index)
                if rect.collidepoint(mouse_pos):
                    self._draw_card_tooltip(screen, card, rect)
                    return

    def handle_details_click(self, position):
        if self.details_card is not None:
            return True
        battle = self.scene.battle
        candidates = []
        if self.scene.phase in (
            "draft",
            "draft_transfer",
            "enemy_transfer",
            "draft_bonus_transfer",
            "draft_cleanup",
        ):
            candidates.extend(
                (self.draft_slot_rect(index), card)
                for index, card in enumerate(self.draft_slots())
                if card is not None
            )
        if self.scene.phase == "card_draw_choice":
            candidates.extend(
                (self.card_rect(self.draw_choice_area(side), len(battle.draw_choices[side]), index), card)
                for side in ("player", "enemy")
                for index, card in enumerate(battle.draw_choices[side])
            )
        visible_hand = [card for card in battle.hands["player"] if card not in battle.selected["player"]]
        for area, cards in (
            (self.layout.player_hand, visible_hand),
            (self.layout.player_selected, battle.selected["player"]),
        ):
            candidates.extend(
                (self.card_rect(area, len(cards), index), card)
                for index, card in enumerate(cards)
            )
        if self.scene.phase == "card_draw_choice":
            candidates.extend(
                (
                    self.card_rect(self.layout.enemy_hand, len(battle.hands["enemy"]), index),
                    card,
                )
                for index, card in enumerate(battle.hands["enemy"])
            )
        for rect, card in candidates:
            if rect.collidepoint(position):
                self.details_card = card
                self.details_scroll = 0
                return True
        return False

    def close_details(self):
        self.details_card = None
        self.details_scroll = 0

    def scroll_details(self, direction):
        if self.details_card is not None:
            self.details_scroll = max(0, self.details_scroll - direction * 3)

    def _draw_card_details(self, screen):
        if self.details_card is None:
            return
        card = self.details_card
        font = self.scene.small_font
        lines = self._wrap_lines(self._card_information_lines(card, detailed=True), font, 750)
        line_height = font.get_linesize() + 4
        panel_height = min(settings.HEIGHT - 60, max(200, 112 + len(lines) * line_height))
        panel = pygame.Rect(0, 0, 820, panel_height)
        panel.center = (settings.WIDTH // 2, settings.HEIGHT // 2)
        pygame.draw.rect(screen, (20, 22, 32), panel, border_radius=8)
        pygame.draw.rect(screen, (210, 185, 105), panel, 3, border_radius=8)
        self.details_close_rect = pygame.Rect(panel.right - 45, panel.top + 12, 30, 30)
        pygame.draw.rect(screen, (125, 60, 70), self.details_close_rect, border_radius=4)
        title = self.tooltip_title_font.render(card.name, True, (245, 225, 150))
        screen.blit(title, (panel.x + 18, panel.y + 18))
        content_area = pygame.Rect(
            panel.x + 18,
            panel.y + 58,
            panel.width - 36,
            panel.height - 96,
        )
        previous_clip = screen.get_clip()
        screen.set_clip(content_area)
        max_scroll = max(0, len(lines) * line_height - content_area.height)
        self.details_scroll = min(self.details_scroll * line_height, max_scroll) // line_height
        for index, line in enumerate(lines[self.details_scroll:]):
            screen.blit(
                font.render(line, True, (230, 230, 235)),
                (content_area.x, content_area.y + index * line_height),
            )
        screen.set_clip(previous_clip)
        footer = "Колесо мыши — прокрутка; ЛКМ — закрыть" if max_scroll else "ЛКМ — закрыть"
        draw_text(screen, font, footer, panel.x + 18, panel.bottom - 30, (165, 170, 185))

    @staticmethod
    def _wrap_lines(texts, font, max_width):
        lines = []
        for text in texts:
            current = ""
            for word in str(text).split():
                candidate = f"{current} {word}".strip()
                if current and font.size(candidate)[0] > max_width:
                    lines.append(current)
                    current = word
                else:
                    current = candidate
            if current:
                lines.append(current)
            elif not text:
                lines.append("")
        return lines

    def _card_information_lines(self, card, detailed=False):
        resource_name = {
            "mana": "мана",
            "rage": "ярость",
            "accuracy": "меткость",
            "concentration": "концентрация",
        }.get(card.resource_type, card.resource_type)
        lines = [f"Стоимость: {card.resource_cost} {resource_name}."]
        if card.effect_duration:
            lines.append(f"Длительность: {card.effect_duration} ход(а).")
        lines.extend(self._card_damage_preview(card))
        if lines:
            lines.append("")
        if card.resource_type in ("rage", "accuracy", "concentration"):
            description = describe_physical_card(card)
        else:
            description = self._card_description(card)
        if description:
            lines.extend(("Эффекты:", description))
        if detailed:
            lines.extend(self._card_formula_lines(card))
        return lines

    def _card_damage_preview(self, card):
        attacker = self.scene.player
        defender = self.scene.enemy
        data = card.effect_data
        base_damage = None
        hits = int(data.get("hits", 1))
        is_physical = card.resource_type in ("rage", "accuracy", "concentration")

        if is_physical and data.get("dice"):
            dice_max = max_dice_damage(data["dice"])
            base_damage = (dice_max, dice_max)
            flat_bonus = int(attacker.strength)
            flat_bonus += int(attacker.intuition) * int(data.get("intuition_damage", 0))
            flat_bonus += int(self.scene.battle._buff("enemy", "mark_damage"))
            missing_ratio = (attacker.max_hp - attacker.hp) / max(1, attacker.max_hp)
            flat_bonus += int(
                self.scene.battle._buff("player", "missing_hp_damage")
                * int(missing_ratio * 10)
            )
            base_damage = tuple(value + flat_bonus for value in base_damage)
        elif is_physical and data.get("poison_damage_multiplier"):
            stacks = len(self.scene.battle.poisons["enemy"])
            if stacks:
                base = int(data["poison_damage_multiplier"]) * stacks
                strength_multiplier = stacks if data.get("poison_strength_per_stack") else 1
                base += int(attacker.strength) * strength_multiplier
                base_damage = (base, base)
            else:
                return ["Прямой урон: 0 — на цели нет ядов."]
        elif (
            card.effect_type in (
                "mage_damage",
                "mage_damage_status",
                "mage_area_damage",
                "mage_area_damage_status",
                "mage_stun_status",
            )
            or data.get("damage")
        ):
            base_damage = int(data.get("damage", 0))
            if card.effect_type == "mage_damage":
                base_damage += int(attacker.stats.get("wisdom", 0))
            elif card.effect_type in ("mage_damage_status", "mage_stun_status"):
                base_damage += int(attacker.stats.get("wisdom", 0))
            else:
                base_damage += (
                    int(attacker.stats.get("wisdom", 0))
                    * int(data.get("wisdom_damage", 1))
                )
                base_damage += (
                    int(attacker.stats.get("intellect", 0))
                    * int(data.get("intellect_damage", 0))
                )
            base_damage = (base_damage, base_damage)

        if base_damage is None:
            return []

        weapon = weapon_fixed_damage(getattr(attacker, "equipment", {}))
        raw_range = (
            base_damage[0] + weapon,
            base_damage[1] + weapon,
        )
        if card.effect_type == "mage_damage":
            damage_ratio = float(getattr(attacker, "mage_damage_bonus_ratio", 1))
            raw_range = tuple(math.floor(value * damage_ratio) for value in raw_range)
        damage_range = self._apply_preview_damage_modifiers(raw_range, "player")
        lines = [
            f"Итоговый урон сейчас: {damage_range[0]} "
            f"за попадание после текущих модификаторов, до уклонения/блока."
        ]
        if is_physical:
            critical_range = self._apply_preview_damage_modifiers(
                raw_range,
                "player",
                critical=True,
                card_data=data,
            )
            chance = get_critical_chance(attacker, defender)
            chance += int(attacker.temporary_critical_chance_modifier)
            chance += int(self.scene.battle._buff("player", "crit_chance"))
            if attacker.profession_type == "assassin":
                chance += 2 * len(self.scene.battle.poisons["enemy"])
            if data.get("poison_damage_multiplier"):
                chance += (
                    len(self.scene.battle.poisons["enemy"])
                    * int(data.get("poison_crit_percent", 0))
                )
            chance += (
                int(self.scene.battle._buff("player", "crit_conversion"))
                * (get_critical_damage_multiplier(attacker) - 1)
                * 100
            )
            if self.scene.battle.phys_state["player"].get("guaranteed_crits"):
                chance = 100
            chance = max(0, min(95, int(chance)))
            lines.append(
                f"При крите: {critical_range[0]} урона "
                f"(текущий шанс около {chance}%)."
            )
            damage_percent = int(self.scene.battle._buff("player", "damage_percent"))
            if damage_percent:
                lines.append(f"Учтён текущий бонус урона: {damage_percent:+d}%.")
            if data.get("bleed_percent"):
                bleed_damage = max(
                    1,
                    round(
                        defender.max_hp
                        * (
                            int(data["bleed_percent"])
                            + self.scene.battle._buff("player", "bleed_bonus_percent")
                        )
                        / 100
                        / 2
                    ),
                )
                duration = int(data.get("duration") or 2)
                lines.append(f"Кровотечение: {bleed_damage} HP за тик, {duration} ход(а).")
            if data.get("poison"):
                lines.append(
                    f"Яд: до {int(data['poison'])} стаков; каждый наносит "
                    "ceil(2% от максимального HP цели) в конце её хода."
                )
            if data.get("poison_damage_multiplier"):
                lines.append(
                    f"Ядов на цели сейчас: {len(self.scene.battle.poisons['enemy'])}."
                )
            if hits > 1:
                hits += int(self.scene.battle._buff("player", "extra_hits"))
                lines.append(
                    f"Ударов: {hits}; суммарно при попадании всеми ударами "
                    f"{damage_range[0] * hits}."
                )
            lines.append("Уклонение и блок цели могут уменьшить фактический урон.")
        elif card.effect_type.startswith("mage_") and data.get("status"):
            lines.append(
                f"Статус «{data['status']}»: {data.get('stacks', 1)} ур., "
                f"{data.get('status_duration', card.effect_duration or 1)} ход(а)."
            )
        return lines

    def _apply_preview_damage_modifiers(
        self,
        damage_range,
        side,
        critical=False,
        card_data=None,
    ):
        battle = self.scene.battle
        attacker = self.scene.player if side == "player" else self.scene.enemy
        defender_side = "enemy" if side == "player" else "player"
        defender = self.scene.enemy if side == "player" else self.scene.player
        result = []
        for damage in damage_range:
            if critical:
                crit_bonus = int(battle._buff(side, "crit_damage"))
                if defender.mp <= 0:
                    crit_bonus += int((card_data or {}).get("crit_on_no_mana", 0))
                damage = math.ceil(
                    damage * (get_critical_damage_multiplier(attacker) + crit_bonus / 100)
                )
            damage_percent = int(battle._buff(side, "damage_percent"))
            damage_percent += (
                int(battle.phys_state[side].get("dodge_stacks", 0))
                * int(battle._max_buff(side, "dodge_damage_bonus"))
            )
            damage = math.floor(damage * max(0, 100 + damage_percent) / 100)
            incoming = min(100, max(0, int(battle._buff(defender_side, "incoming_damage_percent"))))
            damage = math.floor(damage * (100 - incoming) / 100)
            outgoing = min(100, max(0, int(battle._buff(side, "outgoing_damage_percent"))))
            damage = math.floor(damage * (100 - outgoing) / 100)
            damage = max(0, damage - int(battle._buff(side, "outgoing_damage_flat")))
            if battle.invulnerable[defender_side]:
                damage = 0
            else:
                damage = max(0, damage - int(battle._buff(defender_side, "incoming_damage_flat")))
                spirit = battle.phys_spirits.get(defender_side)
                if spirit:
                    damage = max(0, damage - int(spirit.get("hp", 0)))
                shield = int(battle.phys_shields[defender_side]) + int(battle.mage_shields[defender_side])
                damage = max(0, damage - shield)
            result.append(damage)
        return min(result), max(result)

    def _card_formula_lines(self, card):
        data = card.effect_data
        if card.resource_type not in ("rage", "accuracy", "concentration"):
            lines = ["Формула и текущие значения:"]
            wisdom = int(self.scene.player.stats.get("wisdom", 0))
            intellect = int(self.scene.player.stats.get("intellect", 0))
            weapon = weapon_fixed_damage(getattr(self.scene.player, "equipment", {}))
            if card.effect_type.startswith("mage_") and data.get("damage") is not None:
                if card.effect_type == "mage_damage":
                    lines.append(
                        f"Урон: floor(({data['damage']} + Мудрость {wisdom} "
                        f"+ оружие {weapon}) × "
                        f"{getattr(self.scene.player, 'mage_damage_bonus_ratio', 1):.2f})."
                    )
                elif card.effect_type in ("mage_damage_status", "mage_stun_status"):
                    lines.append(
                        f"Урон: {data['damage']} + Мудрость {wisdom} "
                        f"+ оружие {weapon}."
                    )
                else:
                    lines.append(
                        f"Урон: {data['damage']} + Мудрость {wisdom} × "
                        f"{data.get('wisdom_damage', 1)} + Интеллект {intellect} × "
                        f"{data.get('intellect_damage', 0)} + оружие {weapon}."
                    )
            for key, label in (
                ("damage", "Базовый урон"),
                ("wisdom_damage", "Множитель Мудрости"),
                ("intellect_damage", "Множитель Интеллекта"),
                ("duration", "Длительность"),
                ("status_duration", "Длительность статуса"),
                ("stacks", "Количество стаков"),
            ):
                if key in data:
                    lines.append(f"{label}: {data[key]}.")
            return lines

        formula = []
        if data.get("dice"):
            formula.append(f"Базовый урон: {max_dice_damage(data['dice'])}")
        if data.get("poison_damage_multiplier"):
            formula.append(f"Множитель яда: {data['poison_damage_multiplier']}")
        formula.extend((
            f"Сила: {self.scene.player.strength}",
            f"Интуиция: {self.scene.player.intuition}",
        ))
        weapon = weapon_fixed_damage(getattr(self.scene.player, "equipment", {}))
        formula.append(f"Оружие: {weapon}")
        if data.get("bleed_percent"):
            formula.append(
                f"Кровотечение: round(макс. HP цели × "
                f"{data['bleed_percent']}% / 2) за тик."
            )
        if data.get("poison"):
            formula.append(
                f"Яд: каждый стак = ceil(макс. HP цели × 2%); "
                f"лимит цели {5 + int(self.scene.battle._buff('enemy', 'poison_cap_bonus'))}."
            )
        if data.get("ultimate"):
            formula.append("Карта помечена как ультимативная.")
        critical_bonus = int(self.scene.battle._buff("player", "crit_damage"))
        if self.scene.player.profession_type == "assassin":
            critical_bonus += 4 * len(self.scene.battle.poisons["enemy"])
        if data.get("poison_damage_multiplier"):
            critical_bonus += (
                len(self.scene.battle.poisons["enemy"])
                * int(data.get("poison_crit_damage_percent", 0))
            )
        crit_multiplier = get_critical_damage_multiplier(self.scene.player) + critical_bonus / 100
        formula.extend((
            f"Критический множитель сейчас: ×{crit_multiplier:.2f}.",
            "Затем применяются бонусы/снижения урона, щит и поглощение призывом.",
            "Точное значение может измениться из-за случайного попадания/оружия, уклонения и блока.",
        ))
        return ["Формула и текущие значения:", *formula]

    def _draw_reveal_cards(self, screen, cards, elapsed, first_row):
        for index, card in enumerate(cards):
            start = settings.DRAFT_REVEAL_START_DELAY_SECONDS + index * settings.DRAFT_CARD_DELAY_SECONDS
            if elapsed < start:
                continue
            progress = min(1.0, (elapsed - start) / settings.CARD_MOVE_SECONDS)
            target = self.draft_slot_rect(index)
            center_x = int(self.layout.deck_rect.centerx + (target.centerx - self.layout.deck_rect.centerx) * progress)
            center_y = int(self.layout.deck_rect.centery + (target.centery - self.layout.deck_rect.centery) * progress)
            self._draw_moving_card(
                screen,
                card,
                center_x,
                center_y,
                progress,
                target_size=target.size,
            )

    def _draw_moving_card(self, screen, card, center_x, center_y, progress, target_size=None):
        """Рисует карту, летящую из колоды с переворотом вокруг вертикальной оси."""
        flip_progress = min(1.0, max(0.0, progress))
        width_scale = abs(2.0 * flip_progress - 1.0)
        target_width, target_height = target_size or (self.CARD_WIDTH, self.CARD_HEIGHT)
        card_width = round(self.CARD_WIDTH + (target_width - self.CARD_WIDTH) * flip_progress)
        card_height = round(self.CARD_HEIGHT + (target_height - self.CARD_HEIGHT) * flip_progress)
        width = max(2, int(card_width * width_scale))
        rect = pygame.Rect(0, 0, width, card_height)
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
                path = settings.PROJECT_ROOT / path
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
        self._draw_pile_count(screen, rect, "ВАША КОЛОДА", len(battle.deck))

    def _draw_discard(self, screen, battle):
        rect = self.layout.discard_rect
        for offset in (8, 5, 2):
            self._draw_card_back(screen, rect.move(-offset, -offset))
        self._draw_pile_count(screen, rect, "ВАШ СБРОС", len(battle.discard))

    def _draw_pile_count(self, screen, rect, title, count):
        title_surface = self.card_cost_font.render(title, True, (245, 225, 160))
        title_rect = title_surface.get_rect(midbottom=(rect.centerx, rect.top - 8))
        screen.blit(title_surface, title_rect)

        count_surface = self.pile_count_font.render(str(count), True, (255, 255, 255))
        count_rect = count_surface.get_rect(center=(rect.centerx, rect.top + 42))
        badge = count_rect.inflate(24, 12)
        badge_surface = pygame.Surface(badge.size, pygame.SRCALPHA)
        badge_surface.fill((15, 17, 24, 205))
        screen.blit(badge_surface, badge)
        pygame.draw.rect(screen, (225, 200, 120), badge, 2, border_radius=8)
        screen.blit(count_surface, count_rect)

    def _draw_draft_timer(self, screen):
        if self.scene.phase not in (
            "draft",
            "draft_transfer",
            "enemy_transfer",
            "draft_bonus_transfer",
        ) or self.scene.turn_deadline is None:
            return None
        remaining = max(0, int(self.scene.turn_deadline - time.monotonic() + 0.999))
        timer = self.scene.small_font.render(f"ОСТАЛОСЬ {remaining} СЕК", True, (245, 225, 150))
        rect = timer.get_rect(topright=(self.layout.card_table.right - 18, self.layout.card_table.y + 12))
        badge = rect.inflate(16, 8)
        pygame.draw.rect(screen, (25, 31, 34), badge, border_radius=5)
        pygame.draw.rect(screen, (105, 150, 110), badge, 1, border_radius=5)
        screen.blit(timer, rect)
        return badge

    def draw_choice_area(self, side):
        area = (
            self.layout.enemy_selected.copy()
            if side == "enemy"
            else self.layout.player_selected.copy()
        )
        area.y += 24
        area.height -= 24
        return area

    def _draw_cards(self, screen, cards, area, selected, highlight_available=False):
        selected_keys = {card.key for card in selected}
        for index, card in enumerate(cards):
            rect = self.card_rect(area, len(cards), index)
            self._draw_card_in_rect(
                screen,
                card,
                rect,
                is_selected=card.key in selected_keys,
                highlight_available=highlight_available,
                enemy_hidden=False,
            )

    def _draw_card_in_rect(
        self,
        screen,
        card,
        rect,
        is_selected=False,
        highlight_available=False,
        enemy_hidden=False,
    ):
        if enemy_hidden:
            self._draw_card_back(screen, rect)
            return
        is_available = highlight_available and self.scene.battle.can_select("player", card)
        color = (55, 135, 80) if is_selected else (45, 105, 68) if is_available else (48, 53, 70)
        face_image = self._card_face_image(card)
        if face_image is not None:
            screen.blit(pygame.transform.smoothscale(face_image, rect.size), rect)
        else:
            pygame.draw.rect(screen, color, rect, border_radius=6)
        pygame.draw.rect(screen, (190, 170, 110), rect, 2, border_radius=6)
        name = str(card.name)
        name_font = self.scene.small_font
        max_width = max(12, rect.width - 12)
        lines = []
        current = ""
        for word in name.split():
            candidate = f"{current} {word}".strip()
            if current and name_font.size(candidate)[0] > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        name_color = self.RESOURCE_COST_COLORS.get(card.resource_type, (245, 235, 210))
        for index, line in enumerate(lines[:3]):
            title = name_font.render(line, True, name_color)
            screen.blit(title, title.get_rect(midtop=(rect.centerx, rect.top + 10 + index * name_font.get_linesize())))
        self._draw_card_costs(screen, card, rect)
        if highlight_available:
            self._draw_card_availability(screen, rect, is_available)

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
        description_font = self.scene.small_font
        title_font = self.tooltip_title_font
        max_width = 380
        lines = self._wrap_lines(
            self._card_hover_information_lines(card),
            description_font,
            max_width - 24,
        )
        content_width = max(title_font.size(card.name)[0], *(description_font.size(line)[0] for line in lines))
        width = max(max_width, content_width + 24)
        title_y = 10
        description_y = title_y + title_font.get_linesize() + 6
        height = description_y + len(lines) * (description_font.get_linesize() + 2) + 10
        mouse_x, mouse_y = pygame.mouse.get_pos()
        tooltip = pygame.Rect(mouse_x + 14, mouse_y + 14, width, height)
        if tooltip.right > settings.WIDTH:
            tooltip.right = mouse_x - 14
        if tooltip.bottom > settings.HEIGHT:
            tooltip.bottom = mouse_y - 14
        tooltip.clamp_ip(screen.get_rect())
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
                    tooltip.y + description_y + index * (description_font.get_linesize() + 2),
                ),
            )

    def _card_hover_information_lines(self, card):
        data = card.effect_data or {}
        lines = []
        previews = self._card_damage_preview(card)
        if previews and previews[0].startswith("Итоговый урон сейчас:"):
            lines.append(previews[0].replace("Итоговый урон сейчас:", "Итоговый урон:", 1))

        duration = int(data.get("duration") or card.effect_duration or 1)
        if data.get("entangle"):
            lines.append(f"Оплетение: {int(data['entangle'])} хода.")
        if data.get("poison"):
            lines.append(f"Яд: до {int(data['poison'])} стаков, 2% максимального HP за тик.")
        if data.get("bleed_percent"):
            bleed = max(1, round(
                self.scene.enemy.max_hp
                * (
                    int(data["bleed_percent"])
                    + self.scene.battle._buff("player", "bleed_bonus_percent")
                )
                / 100
                / 2
            ))
            lines.append(f"Кровотечение: {bleed} HP за тик на {int(data.get('duration') or 2)} хода.")
        if data.get("status"):
            status_duration = int(data.get("status_duration") or card.effect_duration or 1)
            stacks = int(data.get("stacks", 1))
            lines.append(f"Статус «{data['status']}»: {stacks} ур. на {status_duration} хода.")
        if data.get("damage_percent") and card.effect_type in (
            "mage_damage_debuff",
            "mage_damage_resistance",
            "mage_damage_status",
        ):
            percent = float(data["damage_percent"])
            if card.effect_type == "mage_damage_status":
                percent = -percent + int(self.scene.player.stats.get("intellect", 0)) * float(
                    data.get("intellect_percent", 0)
                )
            elif card.effect_type == "mage_damage_debuff":
                percent = -percent + int(self.scene.player.stats.get("harmony", 0)) * float(
                    data.get("harmony_percent", 0)
                )
            elif card.effect_type == "mage_damage_resistance":
                percent = -percent + int(self.scene.player.stats.get("wisdom", 0)) * float(
                    data.get("wisdom_percent", 0)
                )
            label = "Сопротивление урону" if card.effect_type == "mage_damage_resistance" else "Снижение урона врага"
            lines.append(f"{label}: {percent:g}% на {int(data.get('duration') or card.effect_duration or 1)} хода.")
        if data.get("stun_duration"):
            lines.append(f"Оглушение: {int(data['stun_duration'])} ход.")
        for key, label in (
            ("mana_regen_debuff", "Снижение восстановления маны"),
            ("outgoing_damage_percent", "Снижение исходящего урона"),
            ("no_heal_turns", "Запрет лечения"),
            ("forbid_damage_cards", "Запрет атакующих карт"),
        ):
            if data.get(key):
                value = int(data[key])
                lines.append(
                    f"{label}: {value}{'%' if key.endswith('percent') else ''} "
                    f"на {value if key.endswith('turns') else duration} хода."
                )
        if data.get("steal_healing_percent"):
            lines.append(f"Кража лечения: {int(data['steal_healing_percent'])}% на {duration} хода.")
        if data.get("mark_damage"):
            bonus = int(data["mark_damage"]) + self.scene.player.strength // 4 * int(data.get("mark_strength", 1))
            lines.append(f"Метка: +{bonus} получаемого урона на 2 хода.")
        if data.get("dodge_amount"):
            lines.append(
                f"Снижение уклонения: {int(data['dodge_amount'])}% на {duration} хода."
            )
        if data.get("critical_amount"):
            lines.append(
                f"Снижение шанса критического удара: {int(data['critical_amount'])}% "
                f"на {duration} хода."
            )

        heal = int(data.get("heal_flat", 0))
        heal += int(self.scene.player.endurance) * int(data.get("heal_endurance", 0))
        heal += int(self.scene.player.agility) * int(data.get("heal_agility_multiplier", 0))
        if data.get("heal_max_hp_percent"):
            heal += math.ceil(self.scene.player.max_hp * float(data["heal_max_hp_percent"]) / 100)
        if data.get("heal_percent") and not data.get("dice"):
            missing = max(0, self.scene.player.max_hp - self.scene.player.hp)
            heal += math.ceil(missing * float(data["heal_percent"]) / 100)
        if card.effect_type == "heal" and data.get("dice"):
            heal += max_dice_damage(data["dice"])
        if card.effect_type == "mage_heal_missing_hp":
            missing = max(0, self.scene.player.max_hp - self.scene.player.hp)
            heal += math.floor(missing * float(data.get("missing_hp_percent", 0)) / 100)
            heal += int(self.scene.player.stats.get("intellect", 0)) * int(data.get("intellect_hp", 0))
        if heal:
            lines.append(f"Лечение: до {heal} HP.")
        if data.get("heal_per_turn"):
            per_turn = int(data["heal_per_turn"]) + int(self.scene.player.endurance) * int(data.get("endurance_heal", 0))
            lines.append(f"Лечение: {per_turn} HP за ход на {duration} хода.")

        buffs = []
        if data.get("damage_buff_percent"):
            buffs.append(f"урон +{int(data['damage_buff_percent'])}%")
        if data.get("dodge_percent"):
            buffs.append(f"уклонение +{int(data['dodge_percent'])}%")
        if data.get("incoming_damage_percent"):
            buffs.append(f"снижение входящего урона {int(data['incoming_damage_percent'])}%")
        if data.get("agility_bonus"):
            buffs.append(f"ловкость +{int(data['agility_bonus'])}")
        if data.get("crit_chance_percent"):
            buffs.append(f"шанс критического удара +{int(data['crit_chance_percent'])}%")
        if buffs:
            buff_duration = int(data.get("buff_duration") or data.get("duration") or card.effect_duration or 1)
            lines.append(f"Баф: {', '.join(buffs)} на {buff_duration} хода.")
        if data.get("shield_flat") or data.get("shield_hp") or data.get("bonus_hp"):
            shield = int(data.get("shield_flat", data.get("shield_hp", data.get("bonus_hp", 0))))
            shield += int(self.scene.player.agility) * int(data.get("shield_agility", 0))
            shield += int(self.scene.player.stats.get("intellect", 0)) * int(data.get("intellect_shield", 0))
            shield += int(self.scene.player.stats.get("wisdom", 0)) * int(data.get("wisdom_hp", 0))
            lines.append(f"Щит: {shield} HP.")
        if data.get("summon_spirit"):
            lines.append("Призыв: Лесной дух; поддержка союзников в радиусе 3 гексов.")
        elif card.effect_type in ("mage_golem", "mage_cloud"):
            lines.append(f"Призыв: {card.name}.")
        if data.get("guaranteed_dodge"):
            lines.append(f"Гарантированное уклонение: {int(data['guaranteed_dodge'])}.")
        if card.effect_type in ("mage_damage_buff", "mage_team_damage_buff"):
            percent = float(data.get("damage_percent", 0)) + (
                int(self.scene.player.stats.get("intellect", 0))
                * float(data.get("intellect_percent", 0))
            )
            lines.append(
                f"Баф: магический урон +{percent:g}% на "
                f"{int(data.get('duration') or card.effect_duration or 1)} хода."
            )
        if not lines:
            lines.append(f"Эффект: {card.name}.")
        return lines

    @staticmethod
    def _card_description(card):
        data = card.effect_data
        if card.group_name.startswith("Магия:"):
            mana = data.get("mana_cost", 0)
            element = data.get("element", "магии")
            descriptions = {
                "mage_damage_status": f"Наносит {data.get('damage', 0)} прямого урона + Мудрость и накладывает {data.get('stacks', 1)} ур. статуса {data.get('status', 'магии')} на {data.get('status_duration', card.effect_duration or 1)} ход.",
                "mage_damage": f"Наносит {data.get('damage', 0)} прямого урона + Мудрость.",
                "mage_area_damage": f"Всем врагам наносится {data.get('damage', 0)} урона.",
                "mage_area_damage_status": f"Всем врагам наносится {data.get('damage', 0)} урона и накладывается {data.get('stacks', 1)} ур. статуса {data.get('status', element)}." + (f" В начале следующего хода добавляется ещё {data['delayed_stacks']} ур." if data.get("delayed_stacks") else "") + (f" Оглушает на {data['stun_duration']} ход." if data.get("stun_duration") else ""),
                "mage_draw": f"Берёт {data.get('cards', 1)} карт(ы) в начале следующего хода.",
                "mage_damage_resistance": f"Снижает получаемый урон на {data.get('reduction_percent', 0)}% + {data.get('intellect_percent', 0)}% за каждое очко Интеллекта на {card.effect_duration or 2} хода.",
                "mage_damage_debuff": f"Снижает исходящий урон врага на {data.get('damage_percent', 0)}% + {data.get('intellect_percent', 0)}% за каждое очко Интеллекта на {card.effect_duration or 2} хода.",
                "mage_team_damage_buff": f"Даёт +{data.get('damage_percent', 0)}% + {data.get('intellect_percent', 0)}% за каждое очко Интеллекта урона на {card.effect_duration or 2} хода.",
                "mage_wind_gust": f"Наносит {data.get('damage', 0)} урона + Мудрость. Каждый снятый ход статуса врага даёт {data.get('removed_damage', 0)} + Мудрость урона.",
                "mage_cleanse_area": f"Наносит {data.get('damage', 0)} урона + Мудрость. Снимает статусы врага; каждый снятый даёт {data.get('removed_damage', 0)} + Мудрость урона.",
                "mage_dispel": f"Снимает положительные эффекты врага; каждый снятый даёт {data.get('removed_damage', 0)} + Мудрость урона.",
                "mage_heal_missing_hp": f"Восстанавливает {data.get('missing_hp_percent', 0)}% недостающего HP + {data.get('intellect_hp', 0)} HP за Интеллект. Щит: {data.get('shield_hp', 0)} + Интеллект на {4 if data.get('ultimate') else 2} хода.",
                "mage_restore_mana": f"Восстанавливает {data.get('missing_mana_percent', 25)}% недостающей маны + {data.get('harmony_percent', 0)}% за Гармонию. Только при мане до {data.get('max_mana_percent', 30)}%.",
                "mage_stun_status": f"Оглушает врага на {data.get('stun_duration', 1)} ход и накладывает Электричество.",
                "mage_golem": f"Призывает голема: {data.get('hp', 16)} HP + Мудрость, атака {data.get('damage', 2)} + Мудрость.",
                "mage_cloud": f"Туча появляется на {data.get('duration', 2)} хода (+1 ход за каждые {data.get('harmony_duration', 6)} Гармонии), не наносит урона и даёт статус Электричество на 1 ход.",
                "mage_team_health_buff": f"Всем союзникам даёт +{data.get('bonus_hp', 0)} HP + Мудрость на щит.",
                "mage_damage_buff": f"Даёт +{data.get('damage_percent', 0)}% + {data.get('intellect_percent', 0)}% за каждое очко Интеллекта урона на {card.effect_duration or 2} хода.",
                "mage_mana_regen_buff": f"Тратит {data.get('hp_percent', 10)}% макс. HP. Накладывает Холод на {data.get('status_duration', 4)} хода и даёт +{data.get('mana_regen_bonus', 0)} восстановления маны на {card.effect_duration or 4} хода.",
            }
            description = descriptions.get(card.effect_type)
            if description is None:
                parts = [f"Элемент: {element}"]
                if data.get("damage"):
                    parts.append(f"Урон: {data['damage']}")
                if data.get("duration") or card.effect_duration:
                    parts.append(f"Длительность: {data.get('duration', card.effect_duration)} ход.")
                if data.get("remove_statuses"):
                    parts.append("Снимает статусы и зависящие от них бафы.")
                description = " ".join(parts) or "Магический эффект."
            return f"{description} Мана: {mana}."
        damage_text = f"Наносит {data.get('dice', '')} урона."
        duration = max(1, int(card.effect_duration))
        remaining_heal_turns = max(0, card.effect_duration - 1)
        if remaining_heal_turns == 1:
            heal_duration_text = (
                f"Восстанавливает {data.get('dice', '')} HP при розыгрыше "
                "и в начале следующего хода."
            )
        else:
            heal_duration_text = (
                f"Восстанавливает {data.get('dice', '')} HP при розыгрыше "
                f"и в начале следующих {remaining_heal_turns} ходов."
            )
        if duration % 10 == 1 and duration % 100 != 11:
            exchange_word = "размен"
        elif duration % 10 in (2, 3, 4) and duration % 100 not in (12, 13, 14):
            exchange_word = "размена"
        else:
            exchange_word = "разменов"
        duration_text = f"на {duration} {exchange_word}"
        descriptions = {
            "damage": damage_text,
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
        }
        return descriptions.get(card.effect_type, "Особое действие карты.")

    def _draw_card_costs(self, screen, card, rect):
        color = self.RESOURCE_COST_COLORS.get(card.resource_type, (230, 220, 190))
        label = self.RESOURCE_COST_LABELS.get(card.resource_type, "")
        if (
            card.resource_type == "unique"
            and getattr(self.scene.player, "unique_resource_type", None) == "necrotism"
        ):
            label = "НЕКРОТИЗМА"
        cost = self.card_cost_font.render(f"{card.resource_cost} {label}".strip(), True, color)
        screen.blit(cost, cost.get_rect(midbottom=(rect.centerx, rect.bottom - 8)))
