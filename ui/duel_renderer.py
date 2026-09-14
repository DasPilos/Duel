from pathlib import Path
import time

import pygame

from core import settings
from ui.hud import draw_text, draw_button, update_and_draw_floating_texts

from ui.character_card import CharacterCard
from ui.renderers.card_area import CardAreaRenderer


class DuelRenderer:
    def __init__(self, scene):
        self.scene = scene
        self.layout = scene.layout

        self.player_card = CharacterCard()
        self.enemy_card = CharacterCard()

        self.card_renderer = CardAreaRenderer(
            scene,
            self.layout,
        )
        self.background = None
        background_path = Path(__file__).resolve().parent.parent / "assets" / "combat" / "background.png"
        try:
            source = pygame.image.load(str(background_path)).convert()
            self.background = pygame.transform.smoothscale(source, (settings.WIDTH, settings.HEIGHT))
        except (pygame.error, OSError):
            self.background = None
        self.hit_placeholder = None
        placeholder_path = Path(__file__).resolve().parent.parent / "assets" / "combat" / "hit_placeholder.png"
        try:
            self.hit_placeholder = pygame.image.load(str(placeholder_path)).convert_alpha()
        except (pygame.error, OSError):
            self.hit_placeholder = None
        self.mage_status_icons = self._load_mage_status_icons()

    def _load_mage_status_icons(self):
        icon_dir = Path(__file__).resolve().parent.parent / "assets" / "mage" / "statuses"
        icons = {}
        for status in ("water", "fire", "electric", "cold"):
            path = icon_dir / f"{status}.png"
            try:
                icons[status] = pygame.transform.smoothscale(
                    pygame.image.load(str(path)).convert_alpha(),
                    (34, 34),
                )
            except (pygame.error, OSError):
                pass
        return icons

    def draw(self, screen):
        if self.background is None or screen.get_size() != self.background.get_size():
            screen.fill((16, 18, 28))
        else:
            screen.blit(self.background, (0, 0))

        if self.scene.phase == "result":
            self.draw_result(screen)
            return
        
        if self.scene.phase in ("result_transition", "battle_start_transition"):
            if self.scene.phase_transition.draw(screen):
                return

        if getattr(self.scene, "mage_battle", False):
            screen.fill((24, 20, 34))

        self.draw_header(screen)

        if self.scene.phase in ("intro_table", "intro_deck", "draft_reveal", "draft", "draft_transfer", "enemy_transfer", "draft_bonus_transfer", "draft_cleanup", "planning", "waiting_enemy", "clash", "damage", "deck_shuffle", "card_draw", "card_return"):
            self.card_renderer.draw(screen)

        elif self.scene.phase == "resolve":
            self.draw_resolve_overlay(screen)


        if self.scene.chat is not None:
            self.scene.chat.draw(screen)

        # Рисуем статические характеристики в углах вместо всплывающих карточек
        self.draw_battle_stats(screen)

        update_and_draw_floating_texts(
            screen,
            self.scene.active_floating_texts,
        )

        # Кнопка инвентаря в верхнем правом углу
        pygame.draw.rect(screen, (100, 100, 120), self.scene.inventory_button)
        pygame.draw.rect(screen, (150, 150, 170), self.scene.inventory_button, 2)
        inv_text = self.scene.font.render("📦", True, (255, 255, 255))
        inv_rect = inv_text.get_rect(center=self.scene.inventory_button.center)
        screen.blit(inv_text, inv_rect)

        # Если открыто через инвентарь (counterpart is None), показываем только левую панель
        show_player_only = self.scene.profile_overlay.counterpart is None
        self.scene.profile_overlay.draw(
            screen,
            opponent=self.scene.player,
            show_counterpart=False,
            show_player_only=show_player_only,
        )

    def draw_result(self, screen):
        scene = self.scene
        screen_width, screen_height = screen.get_size()
        
        # Фон панели
        pygame.draw.rect(screen, (25, 27, 38), pygame.Rect(0, 0, screen_width, screen_height))
        
        # Заголовок результата (в центре вверху)
        outcome = scene.battle.outcome()
        title = {"win": "ПОБЕДА", "loss": "ПОРАЖЕНИЕ", "draw": "НИЧЬЯ"}.get(outcome, "БОЙ ОКОНЧЕН")
        title_color = (110, 235, 120) if outcome == "win" else (235, 110, 100) if outcome == "loss" else (255, 220, 120)
        title_surface = scene.big.render(title, True, title_color)
        screen.blit(title_surface, title_surface.get_rect(center=(screen_width // 2, 40)))
        
        # Информация о победителе
        winner_text = f"Победитель: {scene.battle.winner_name() or 'Ничья'}"
        draw_text(screen, scene.small_font, winner_text, screen_width // 2 - 100, 100, (220, 220, 225))
        if scene.card_reward is not None:
            reward_text = f"Карта отправлена в Коллекцию: {scene.card_reward['name']}"
            reward_surface = scene.small_font.render(
                reward_text,
                True,
                (245, 210, 110),
            )
            screen.blit(
                reward_surface,
                reward_surface.get_rect(center=(screen_width // 2, 130)),
            )
        
        # Параметры панелей с информацией о игроке и противнике
        left_margin = 50
        right_margin = 50
        usable_width = screen_width - left_margin - right_margin
        half_width = usable_width // 2 - 25  # 25px gap между панелями
        
        player_x = left_margin
        enemy_x = left_margin + half_width + 50
        y_start = 150
        
        for index, side in enumerate(("player", "enemy")):
            stats = scene.battle.stats[side]
            fighter = scene.player if side == "player" else scene.enemy
            
            if side == "player":
                x, side_color = player_x, (80, 180, 120)
            else:
                x, side_color = enemy_x, (210, 100, 90)
            
            # Имя и статистика
            draw_text(screen, scene.font, fighter.name, x, y_start, (255, 220, 120))
            
            stats_lines = (
                f"Критов: {stats['critical']}",
                f"Уворотов: {stats['dodges']}",
                f"Ударов прошло: {stats['hits']}",
                f"Урона нанесено: {stats['damage']}",
                f"Восстановлено: {stats['healed']} HP",
                f"Карт использовано: {stats['cards_played']}",
            )
            
            for line_idx, line in enumerate(stats_lines):
                draw_text(screen, scene.small_font, line, x, y_start + 35 + line_idx * 25, (215, 220, 230))
            
            # Рисуем карты в столбик
            cards_y = y_start + 35 + len(stats_lines) * 25 + 20
            draw_text(screen, scene.small_font, "Карты:", x, cards_y, side_color)
            
            # Скролл для карт
            cards_panel_height = screen_height - cards_y - 110
            card_height = 24
            max_visible_cards = max(1, cards_panel_height // card_height)
            
            # Получаем уникальные карты (без дубликатов)
            unique_cards = []
            seen = set()
            for card_name in stats["cards"]:
                if card_name not in seen:
                    unique_cards.append(card_name)
                    seen.add(card_name)
            
            # Скролл для карт (сохраняем в scene если его еще нет)
            scroll_key = f"cards_scroll_{side}"
            if not hasattr(scene, scroll_key):
                setattr(scene, scroll_key, 0)
            
            scroll_offset = getattr(scene, scroll_key)
            max_scroll = max(0, len(unique_cards) * card_height - cards_panel_height)
            scroll_offset = min(scroll_offset, max_scroll)
            setattr(scene, scroll_key, scroll_offset)
            
            # Рисуем карты с уроном
            for card_idx, card_name in enumerate(unique_cards):
                card_y = cards_y + 30 + card_idx * card_height - scroll_offset
                
                # Проверяем видимость карты
                if card_y + card_height < cards_y + 30 or card_y > screen_height - 110:
                    continue
                
                # Урон нанесен этой картой (если есть)
                damage = stats["card_damage"].get(card_name, 0)
                card_text = f"{card_name}" + (f" ({damage} урон)" if damage > 0 else "")
                
                draw_text(screen, scene.small_font, card_text, x, card_y, (215, 220, 230))
        
        # Кнопка "В ТАВЕРНУ"
        scene.result_button = pygame.Rect(screen_width // 2 - 160, screen_height - 75, 320, 45)
        draw_button(screen, scene.result_button, "В ТАВЕРНУ", scene.font, color=(75, 105, 155))

    def draw_header(self, screen):
        self.draw_turn_timer(screen)

    def draw_resolve_overlay(self, screen):
        if self.hit_placeholder is None:
            return
        image = pygame.transform.smoothscale(self.hit_placeholder, (128, 128))
        image_rect = image.get_rect(center=(960, 520))
        screen.blit(image, image_rect)

    def draw_turn_timer(self, screen):
        if self.scene.turn_deadline is None:
            return
        remaining = max(0, int(self.scene.turn_deadline - time.monotonic()))
        if remaining <= settings.TURN_WARNING_RED_SECONDS:
            color = (220, 70, 70)
        elif remaining <= settings.TURN_WARNING_YELLOW_SECONDS:
            color = (230, 190, 70)
        else:
            color = (80, 200, 120)
        bar = self.layout.turn_bar
        pygame.draw.rect(screen, (55, 58, 68), bar, border_radius=5)
        fill = bar.copy()
        fill.width = int(bar.width * remaining / settings.TURN_DECISION_SECONDS)
        pygame.draw.rect(screen, color, fill, border_radius=5)

    def draw_battle_stats(self, screen):
        """Рисует статистику боцов как в карточке персонажа - в верхних углах и характеристики внизу."""
        from ui.character_profile import normalize_character_profile, derived_values
        screen_width, screen_height = screen.get_size()
        
        # Левый верхний угол - Игрок (зелёный)
        player_profile = normalize_character_profile(self.scene.player)
        enemy_profile = normalize_character_profile(self.scene.enemy)
        if getattr(self.scene, "mage_battle", False):
            self._draw_mage_battle_stats(screen, player_profile, enemy_profile)
            return
        player_effective_profile = self._effective_profile_for_derived(
            self.scene.player,
            player_profile,
        )
        enemy_effective_profile = self._effective_profile_for_derived(
            self.scene.enemy,
            enemy_profile,
        )
        player_derived = derived_values(
            player_effective_profile,
            enemy_effective_profile,
        )
        player_derived = self._apply_chance_modifiers(
            player_derived,
            self.scene.player,
        )
        player_stats_x, player_stats_width = self._stats_frame_geometry(
            "player",
            screen_width,
        )
        
        self._draw_corner_fighter_card(
            screen,
            fighter=self.scene.player,
            profile=player_profile,
            derived=player_derived,
            x=10,
            y=10,
            border_color=(80, 180, 120),
            align="left"
        )
        
        # Правый верхний угол - Противник (красный)
        enemy_derived = derived_values(
            enemy_effective_profile,
            player_effective_profile,
        )
        enemy_derived = self._apply_chance_modifiers(
            enemy_derived,
            self.scene.enemy,
        )
        enemy_stats_x, enemy_stats_width = self._stats_frame_geometry(
            "enemy",
            screen_width,
        )
        
        self._draw_corner_fighter_card(
            screen,
            fighter=self.scene.enemy,
            profile=enemy_profile,
            derived=enemy_derived,
            x=screen_width - 320,
            y=10,
            border_color=(210, 80, 80),
            align="right"
        )
        
        # Левый нижний угол - Характеристики Игрока
        self._draw_corner_stats(
            screen,
            profile=player_profile,
            derived=player_derived,
            side="player",
            x=player_stats_x,
            y=screen_height - 130,
            width=player_stats_width,
            border_color=(80, 180, 120)
        )
        
        # Правый нижний угол - Характеристики Противника
        self._draw_corner_stats(
            screen,
            profile=enemy_profile,
            derived=enemy_derived,
            side="enemy",
            x=enemy_stats_x,
            y=screen_height - 130,
            width=enemy_stats_width,
            border_color=(210, 80, 80)
        )

    def _draw_mage_battle_stats(self, screen, player_profile, enemy_profile):
        screen_width, screen_height = screen.get_size()
        for profile, x, color, align in (
            (player_profile, 390, (80, 180, 120), "left"),
            (enemy_profile, screen_width - 700, (210, 80, 80), "right"),
        ):
            self._draw_corner_fighter_card(screen, self.scene.player if align == "left" else self.scene.enemy, profile, {}, x, 10, color, align)
            side = "player" if align == "left" else "enemy"
            self._draw_mage_status(screen, x + 12, 370, color, align, side)
            stats = profile.get("stats", {})
            frame = pygame.Rect(10 if align == "left" else screen_width - 320, screen_height - 115, 310, 95)
            pygame.draw.rect(screen, (20, 24, 34, 210), frame, border_radius=8)
            pygame.draw.rect(screen, color, frame, 2, border_radius=8)
            labels = (
                f"Мудрость: {stats.get('wisdom', 2)}",
                f"Интеллект: {stats.get('intellect', 2)}",
                f"Гармония: {stats.get('harmony', 2)}",
                f"Выносливость: {stats.get('endurance', 2)}",
            )
            for index, label in enumerate(labels):
                draw_text(screen, self.scene.small_font, label, frame.x + 8 + (index % 2) * 145, frame.y + 8 + (index // 2) * 24, color)
            summon_x = 270 if align == "left" else screen_width - 550
            self._draw_mage_summons(screen, summon_x, 705, side, color)

    def _draw_mage_summons(self, screen, x, y, side, border_color):
        golems = getattr(self.scene.battle, "mage_golems", {}).get(side, [])
        clouds = getattr(self.scene.battle, "mage_clouds", {}).get(side, [])
        panel = pygame.Rect(x, y, 280, 105)
        pygame.draw.rect(screen, (20, 24, 34), panel, border_radius=8)
        pygame.draw.rect(screen, border_color, panel, 2, border_radius=8)
        draw_text(screen, self.scene.small_font, "ПРИЗВАННЫЕ", x + 10, y + 7, border_color)
        if not golems and not clouds:
            draw_text(screen, self.scene.small_font, "нет существ", x + 10, y + 43, (150, 155, 170))
            return
        row_y = y + 34
        for golem in golems[:2]:
            name = golem.get("name", "Голем земли")
            hp = int(golem.get("hp", 0))
            max_hp = max(1, int(golem.get("max_hp", hp)))
            mana = int(golem.get("mana", 0))
            max_mana = int(golem.get("max_mana", 0))
            draw_text(screen, self.scene.small_font, name, x + 10, row_y, (230, 230, 240))
            draw_text(screen, self.scene.small_font, f"HP: {hp}/{max_hp}", x + 10, row_y + 22, (110, 235, 120))
            draw_text(screen, self.scene.small_font, f"МАНА: {mana}/{max_mana}", x + 135, row_y + 22, (100, 190, 255))
            row_y += 46
        for cloud in clouds[:2]:
            remaining = int(cloud.get("remaining", 0))
            icon = self.mage_status_icons.get("electric")
            if icon is not None:
                screen.blit(icon, (x + 8, row_y - 5))
            else:
                self._draw_mage_status_fallback(screen, "electric", (x + 25, row_y + 12))
            draw_text(screen, self.scene.small_font, f"ГРОМОВАЯ ТУЧА: {remaining} хода", x + 48, row_y + 5, (225, 225, 235))
            row_y += 32

    def _draw_mage_status(self, screen, x, y, color, align, side):
        draw_text(screen, self.scene.small_font, "СТАТУСЫ", x, y, color)
        effects = getattr(self.scene.battle, "mage_statuses", {}).get(side, [])
        if not effects:
            draw_text(screen, self.scene.small_font, "нет эффектов", x, y + 24, (150, 155, 170))
        for index, effect in enumerate(effects[:4]):
            icon_key = self._mage_status_icon_key(effect.get("name", ""))
            icon = self.mage_status_icons.get(icon_key)
            row_y = y + 22 + index * 36
            icon_x = x if align == "left" else x + 210
            if icon is not None:
                screen.blit(icon, (icon_x, row_y - 5))
            else:
                self._draw_mage_status_fallback(screen, icon_key, (icon_x + 17, row_y + 12))
            remaining = int(effect.get("remaining", 0))
            stacks = int(effect.get("stacks", 1))
            label = f"{effect.get('name', '').upper()}  {remaining} хода  x{stacks}"
            text_x = x + 42 if align == "left" else x
            draw_text(screen, self.scene.small_font, label, text_x, row_y + 2, (225, 225, 235))
        bonuses = getattr(self.scene.battle, "mage_damage_bonuses", {}).get(side, [])
        effect_line_y = y + 28 + min(4, len(effects)) * 36
        if bonuses:
            total = sum(float(bonus.get("percent", 0)) for bonus in bonuses)
            turns = max(1, max(int(bonus.get("remaining", 0)) for bonus in bonuses) - 1)
            draw_text(screen, self.scene.small_font, f"ДОП. УРОН: {total:+g}% ({turns} ход.)", x, effect_line_y, (255, 215, 120))
            effect_line_y += 28
        shields = getattr(self.scene.battle, "mage_shield_effects", {}).get(side, [])
        if shields:
            shield = sum(int(effect.get("amount", 0)) for effect in shields)
            turns = max(1, max(int(effect.get("remaining", 0)) for effect in shields) - 1)
            draw_text(screen, self.scene.small_font, f"ЩИТ: +{shield} HP ({turns} ход.)", x, effect_line_y, (100, 210, 255))

    @staticmethod
    def _mage_status_icon_key(status):
        status = status.lower()
        if "вод" in status:
            return "water"
        if "огн" in status or "огон" in status:
            return "fire"
        if "элект" in status or "молни" in status:
            return "electric"
        if "холод" in status or "лед" in status:
            return "cold"
        return None

    @staticmethod
    def _draw_mage_status_fallback(screen, icon_key, center):
        x, y = center
        if icon_key == "water":
            pygame.draw.polygon(screen, (40, 180, 240), ((x, y - 15), (x - 10, y + 3), (x - 7, y + 11), (x, y + 15), (x + 8, y + 10), (x + 10, y + 2)))
        elif icon_key == "fire":
            pygame.draw.polygon(screen, (245, 55, 35), ((x, y + 15), (x - 12, y + 7), (x - 5, y - 3), (x - 3, y - 16), (x + 5, y - 5), (x + 13, y - 13), (x + 10, y + 5)))
        elif icon_key == "electric":
            pygame.draw.polygon(screen, (195, 55, 220), ((x + 5, y - 17), (x - 11, y + 1), (x - 2, y + 1), (x - 8, y + 17), (x + 12, y - 5), (x + 3, y - 5)))
        else:
            pygame.draw.polygon(screen, (65, 225, 235), ((x, y - 17), (x + 13, y - 5), (x + 10, y + 11), (x, y + 17), (x - 12, y + 8), (x - 12, y - 7)))

    def _draw_corner_fighter_card(self, screen, fighter, profile, derived, x, y, border_color, align):
        """Рисует укороченную карточку боца в углу (Имя, Уровень, HP/MP бары)."""
        width = 310
        height = 170
        
        # Фон с полупрозрачностью
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((30, 32, 45, 200))
        screen.blit(overlay, (x, y))
        
        # Рамка
        pygame.draw.rect(screen, border_color, pygame.Rect(x, y, width, height), width=2, border_radius=8)
        
        inner_x = x + 12
        
        # Имя (большой шрифт как на карточке)
        name_surface = self.scene.small_font.render(fighter.name, True, (240, 240, 245))
        name_rect = name_surface.get_rect(topleft=(inner_x, y + 8))
        screen.blit(name_surface, name_rect)
        
        # ID рядом с именем
        id_text = f"ID: {fighter.character_id or 'N/A'}"
        draw_text(screen, self.scene.small_font, id_text, name_rect.right + 15, y + 10, (170, 175, 185))
        
        # Уровень
        level_text = f"Уровень {fighter.level}"
        draw_text(screen, self.scene.small_font, level_text, inner_x, y + 28, (210, 215, 225))
        
        # HP шкала (опущена вниз чтобы не наплывать на текст)
        hp_y = y + 65
        bar_width = 280
        bar_height = 11
        self._draw_resource_bar(
            screen,
            inner_x,
            hp_y,
            bar_width,
            bar_height,
            "HP",
            profile["hp"],
            profile["max_hp"],
            (210, 80, 80)
        )
        if getattr(self.scene, "mage_battle", False):
            side = "player" if fighter is self.scene.player else "enemy"
            shield = int(getattr(self.scene.battle, "mage_shields", {}).get(side, 0))
            if shield:
                draw_text(screen, self.scene.small_font, f"ЩИТ: +{shield} HP", inner_x, y + 84, (100, 210, 255))
        
        # MP шкала ниже HP
        mp_y = y + 105
        self._draw_resource_bar(
            screen,
            inner_x,
            mp_y,
            bar_width,
            bar_height,
            "MP",
            profile["mp"],
            profile["max_mp"],
            (60, 140, 220)
        )

    def _stats_frame_geometry(self, side, screen_width):
        margin = 10
        default_width = 310
        area = (
            self.scene.layout.player_hand
            if side == "player"
            else self.scene.layout.enemy_hand
        )
        max_hand_size = self.scene.battle.MAX_HAND_SIZE
        first_card = self.card_renderer.card_rect(area, max_hand_size, 0)
        last_card = self.card_renderer.card_rect(
            area,
            max_hand_size,
            max_hand_size - 1,
        )
        if side == "player":
            return margin, max(default_width, first_card.left - 6 - margin)
        x = last_card.right + 6
        return x, max(default_width, screen_width - margin - x)

    def _draw_corner_stats(self, screen, profile, derived, side, x, y, width, border_color):
        """Рисует характеристики боца в углу (Урон, Уворот, Крит, HP) как на карточке."""
        height = 100
        
        # Фон с полупрозрачностью
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((30, 32, 45, 200))
        screen.blit(overlay, (x, y))
        
        # Рамка
        pygame.draw.rect(screen, border_color, pygame.Rect(x, y, width, height), width=2, border_radius=8)
        
        inner_x = x + 12
        header_y = y + 8
        
        # Заголовок "ХАРАКТЕРИСТИКИ"
        draw_text(screen, self.scene.small_font, "ХАРАКТЕРИСТИКИ", inner_x, header_y, border_color)
        
        # Характеристики как на карточке (в 2 колонки)
        stats = profile.get("stats", {})
        stat_names = (
            ("strength", "Сила", "Урон"),
            ("agility", "Ловкость", "Уворот"),
            ("intuition", "Интуиция", "Крит"),
            ("endurance", "Выносливость", "HP"),
        )
        
        stat_value_colors = {
            "Урон": (255, 255, 255),
            "Уворот": (150, 220, 255),
            "Крит": (255, 90, 90),
            "HP": (110, 235, 120),
        }
        
        # Левая колонка (имена статов)
        col1_x = inner_x
        # Правая колонка (производные значения)
        col2_x = inner_x + 150
        active_effects = self._active_effect_statuses(side)
        
        for index, (key, label, derived_key) in enumerate(stat_names):
            row_y = header_y + 22 + index * 16
            
            # Левая: название стата и значение
            stat_text = f"{label}: {stats.get(key, 0)}"
            draw_text(screen, self.scene.small_font, stat_text, col1_x, row_y, (215, 220, 225))
            stat_status_x = col1_x + self.scene.small_font.size(stat_text)[0] + 8
            for status_text, status_color in active_effects[key]:
                draw_text(
                    screen,
                    self.scene.small_font,
                    status_text,
                    stat_status_x,
                    row_y,
                    status_color,
                )
                stat_status_x += self.scene.small_font.size(status_text)[0] + 8
            
            # Правая: производное значение (Урон, Уворот, Крит, HP)
            derived_text = f"{derived_key}: {derived[derived_key]}"
            color = stat_value_colors.get(derived_key, (220, 70, 70))
            draw_text(screen, self.scene.small_font, derived_text, col2_x, row_y, color)
            status_x = col2_x + self.scene.small_font.size(derived_text)[0] + 15
            for status_text, status_color in active_effects[derived_key]:
                draw_text(
                    screen,
                    self.scene.small_font,
                    status_text,
                    status_x,
                    row_y,
                    status_color,
                )
                status_x += self.scene.small_font.size(status_text)[0] + 8

    def _active_effect_statuses(self, side):
        battle = self.scene.battle
        statuses = {
            "strength": [],
            "agility": [],
            "intuition": [],
            "endurance": [],
            "Урон": [],
            "Уворот": [],
            "Крит": [],
            "HP": [],
        }

        for effect in battle.timed_stat_effects[side]:
            amount = int(effect["amount"])
            color = (90, 230, 120) if amount > 0 else (245, 90, 90)
            sign = "+" if amount > 0 else ""
            statuses[effect["stat"]].append((f"{sign}{amount}", color))

        for effect in battle.timed_dodge_effects[side]:
            turns = max(1, int(effect["expires_after_turn"]) - battle.turn + 1)
            statuses["Уворот"].append(
                self._format_effect_status(int(effect["amount"]), "%", turns)
            )

        for effect in battle.timed_critical_effects[side]:
            turns = max(1, int(effect["expires_after_turn"]) - battle.turn + 1)
            statuses["Крит"].append(
                self._format_effect_status(int(effect["amount"]), "%", turns)
            )

        for effect in battle.regen_effects[side]:
            turns = max(1, int(effect["remaining"]))
            text = f"+{effect['dice']} на {turns} {self._turn_word(turns)}"
            statuses["HP"].append((text, (90, 230, 120)))
        return statuses

    @staticmethod
    def _effective_profile_for_derived(fighter, profile):
        effective_profile = dict(profile)
        effective_profile["stats"] = {
            stat_name: getattr(fighter, stat_name)
            for stat_name in ("strength", "agility", "intuition", "endurance")
        }
        return effective_profile

    @staticmethod
    def _apply_chance_modifiers(derived, fighter):
        adjusted = dict(derived)
        dodge = int(str(adjusted["Уворот"]).rstrip("%"))
        critical = int(str(adjusted["Крит"]).rstrip("%"))
        adjusted["Уворот"] = (
            f"{max(0, dodge + fighter.temporary_dodge_chance_modifier)}%"
        )
        adjusted["Крит"] = (
            f"{max(0, critical + fighter.temporary_critical_chance_modifier)}%"
        )
        return adjusted

    @staticmethod
    def _format_effect_status(amount, suffix, turns):
        color = (90, 230, 120) if amount > 0 else (245, 90, 90)
        sign = "+" if amount > 0 else ""
        text = f"{sign}{amount}{suffix} на {turns} {DuelRenderer._turn_word(turns)}"
        return text, color

    @staticmethod
    def _turn_word(turns):
        if turns % 10 == 1 and turns % 100 != 11:
            return "ход"
        if turns % 10 in (2, 3, 4) and turns % 100 not in (12, 13, 14):
            return "хода"
        return "ходов"

    def _draw_resource_bar(self, screen, x, y, bar_width, bar_height, label, current, maximum, color):
        """Рисует полосу ресурса (HP/MP) как на карточке."""
        # Текст выше бара (как на карточке)
        text = f"{label}: {int(current)}/{int(maximum)}"
        draw_text(screen, self.scene.small_font, text, x, y - 15, (220, 225, 235))
        
        # Бары опущены на 4px вниз (y + 4)
        bar_y = y + 4
        
        # Фон шкалы
        pygame.draw.rect(screen, (50, 50, 50), pygame.Rect(x, bar_y, bar_width, bar_height), border_radius=2)
        
        # Полоска ресурса
        if maximum > 0:
            ratio = max(0, min(1.0, current / maximum))
            filled_width = int(bar_width * ratio)
            pygame.draw.rect(screen, color, pygame.Rect(x, bar_y, filled_width, bar_height), border_radius=2)
