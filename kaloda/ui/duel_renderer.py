import time
from types import SimpleNamespace

import pygame

from kaloda import settings
from kaloda.ui.hud import draw_text, draw_button, update_and_draw_floating_texts

from kaloda.ui.character_card import CharacterCard
from kaloda.ui.character_profile import normalize_character_profile, derived_values
from kaloda.ui.class_identity import class_icon, class_palette
from kaloda.ui.money_icon import money_icon
from kaloda.ui.renderers.card_area import CardAreaRenderer


class DuelRenderer:
    REWARD_MONEY_ICON_SIZE = 70
    REWARD_CARD_SIZE = (150, 200)
    STATS_PANEL_HEIGHT = 200
    STATS_ROW_HEIGHT = 22
    BAR_TOP = 62
    BAR_STEP = 36
    ALL_STATS = (
        ("strength", "Сила"),
        ("agility", "Ловкость"),
        ("intuition", "Интуиция"),
        ("wisdom", "Мудрость"),
        ("intellect", "Интеллект"),
        ("harmony", "Гармония"),
        ("endurance", "Выносливость"),
    )
    RESOURCE_BARS = {
        "rage": ("Ярость", (200, 100, 80)),
        "accuracy": ("Меткость", (105, 190, 105)),
        "concentration": ("Концентрация", (180, 120, 200)),
    }

    def __init__(self, scene):
        self.scene = scene
        self.layout = scene.layout

        self.player_card = CharacterCard()
        self.enemy_card = CharacterCard()
        self.reward_money_icon = money_icon(self.REWARD_MONEY_ICON_SIZE)

        self.card_renderer = CardAreaRenderer(
            scene,
            self.layout,
        )
        self.background = None
        background_path = settings.ASSETS_DIR / "combat" / "background.png"
        try:
            source = pygame.image.load(str(background_path)).convert()
            self.background = pygame.transform.smoothscale(source, (settings.WIDTH, settings.HEIGHT))
        except (pygame.error, OSError):
            self.background = None
        self.hit_placeholder = None
        placeholder_path = settings.ASSETS_DIR / "combat" / "hit_placeholder.png"
        try:
            self.hit_placeholder = pygame.image.load(str(placeholder_path)).convert_alpha()
        except (pygame.error, OSError):
            self.hit_placeholder = None

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

        self.draw_header(screen)

        if self.scene.phase in ("intro_table", "intro_deck", "draft_reveal", "draft", "draft_transfer", "enemy_transfer", "draft_bonus_transfer", "draft_cleanup", "planning", "waiting_enemy", "clash", "damage", "deck_shuffle", "card_draw", "card_draw_choice", "card_return"):
            self.card_renderer.draw(screen)

        elif self.scene.phase == "resolve":
            self.draw_resolve_overlay(screen)


        if self.scene.chat is not None:
            self.scene.chat.draw(screen)

        # Рисуем статические характеристики в углах вместо всплывающих карточек
        self.draw_battle_stats(screen)
        self._draw_summons_near_discard(screen)

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
        draw_text(screen, scene.small_font, winner_text, screen_width // 2 - 100, 80, (220, 220, 225))

        currency_reward = getattr(scene, "currency_reward", {"coins": 0})
        coins = int(currency_reward.get("coins", 0))
        if coins > 0:
            reward_label = scene.small_font.render(
                "Денежная награда:",
                True,
                (245, 210, 110),
            )
            screen.blit(
                reward_label,
                reward_label.get_rect(center=(screen_width // 2, 112)),
            )
            amount_surface = scene.font.render(f"+{coins}", True, (245, 210, 110))
            entry_width = self.REWARD_MONEY_ICON_SIZE + 8 + amount_surface.get_width()
            cursor_x = (screen_width - entry_width) // 2
            screen.blit(self.reward_money_icon, (cursor_x, 125))
            amount_rect = amount_surface.get_rect(
                midleft=(
                    cursor_x + self.REWARD_MONEY_ICON_SIZE + 8,
                    125 + self.REWARD_MONEY_ICON_SIZE // 2,
                ),
            )
            screen.blit(amount_surface, amount_rect)

        if scene.card_reward is not None:
            reward_card = SimpleNamespace(
                name=scene.card_reward.get("name", ""),
                image_path=scene.card_reward.get("image_path", ""),
                group_name=scene.card_reward.get("group_name", ""),
                resource_type=scene.card_reward.get("resource_type", ""),
                resource_cost=int(scene.card_reward.get("resource_cost", 0)),
            )
            reward_card_rect = pygame.Rect(
                0,
                210,
                *self.REWARD_CARD_SIZE,
            )
            reward_card_rect.centerx = screen_width // 2
            self.card_renderer._draw_card_front_scaled(
                screen,
                reward_card,
                reward_card_rect,
            )
            reward_text = f"Карта отправлена в Коллекцию: {scene.card_reward['name']}"
            reward_surface = scene.small_font.render(
                reward_text,
                True,
                (245, 210, 110),
            )
            screen.blit(
                reward_surface,
                reward_surface.get_rect(center=(screen_width // 2, 425)),
            )
        
        # Параметры панелей с информацией о игроке и противнике
        left_margin = 50
        right_margin = 50
        usable_width = screen_width - left_margin - right_margin
        half_width = usable_width // 2 - 25  # 25px gap между панелями
        
        player_x = left_margin
        enemy_x = left_margin + half_width + 50
        y_start = 460 if scene.card_reward is not None else 245
        
        for index, side in enumerate(("player", "enemy")):
            stats = scene.battle.stats[side]
            fighter = scene.player if side == "player" else scene.enemy
            
            if side == "player":
                x, side_color = player_x, (80, 180, 120)
            else:
                x, side_color = enemy_x, (210, 100, 90)
            
            # Имя и статистика
            icon = class_icon(fighter.profession_type)
            screen.blit(icon, (x, y_start + 6))
            draw_text(screen, scene.font, fighter.name, x + icon.get_width() + 7, y_start, (255, 220, 120))
            
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
                healing = stats["card_healing"].get(card_name, 0)
                card_text = f"{card_name}" + (f" ({damage} урон)" if damage > 0 else "")

                draw_text(screen, scene.small_font, card_text, x, card_y, (215, 220, 230))
                if healing > 0:
                    healing_x = x + scene.small_font.size(card_text)[0] + 8
                    draw_text(
                        screen,
                        scene.small_font,
                        f"+{healing} HP",
                        healing_x,
                        card_y,
                        (90, 230, 120),
                    )
        
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
        if self.scene.phase not in ("planning", "waiting_enemy", "card_draw_choice"):
            return
        bar = self.layout.turn_bar
        pygame.draw.rect(screen, (55, 58, 68), bar, border_radius=5)
        if self.scene.phase == "card_draw_choice":
            deadline = self.scene.draw_choice_deadline
            total_time = settings.DRAW_CHOICE_SECONDS
        else:
            deadline = self.scene.turn_deadline
            total_time = settings.TURN_DECISION_SECONDS
        if deadline is not None:
            remaining = max(0, int(deadline - time.monotonic()))
            if remaining <= settings.TURN_WARNING_RED_SECONDS:
                color = (220, 70, 70)
            elif remaining <= settings.TURN_WARNING_YELLOW_SECONDS:
                color = (230, 190, 70)
            else:
                color = (80, 200, 120)
            fill = bar.copy()
            fill.width = int(bar.width * min(1.0, remaining / total_time))
            pygame.draw.rect(screen, color, fill, border_radius=5)
            if self.scene.phase == "card_draw_choice":
                label = f"ВЫБОР КАРТЫ: {remaining} СЕК"
            else:
                label = "ВАШ ХОД"
        else:
            label = "ВАШ ХОД"
        text = self.scene.small_font.render(label, True, (245, 240, 225))
        screen.blit(text, text.get_rect(center=bar.center))

    def draw_battle_stats(self, screen):
        """Рисует статистику боцов как в карточке персонажа - в верхних углах и характеристики внизу."""
        screen_width, screen_height = screen.get_size()
        
        # Левый верхний угол - Игрок (зелёный)
        player_profile = normalize_character_profile(self.scene.player)
        enemy_profile = normalize_character_profile(self.scene.enemy)
        player_effective_profile = self._effective_profile_for_derived(
            self.scene.player,
            player_profile,
        )
        enemy_effective_profile = self._effective_profile_for_derived(
            self.scene.enemy,
            enemy_profile,
        )
        player_derived = derived_values(player_effective_profile)
        player_derived = self._apply_chance_modifiers(
            player_derived,
            self.scene.player,
            self.scene.battle._buff("player", "agility_bonus"),
            *self._combat_critical_bonuses("player"),
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
        enemy_derived = derived_values(enemy_effective_profile)
        enemy_derived = self._apply_chance_modifiers(
            enemy_derived,
            self.scene.enemy,
            self.scene.battle._buff("enemy", "agility_bonus"),
            *self._combat_critical_bonuses("enemy"),
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
            y=screen_height - self.STATS_PANEL_HEIGHT - 30,
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
            y=screen_height - self.STATS_PANEL_HEIGHT - 30,
            width=enemy_stats_width,
            border_color=(210, 80, 80)
        )

    def _draw_summons_near_discard(self, screen):
        battle = self.scene.battle
        summons = []
        for side, owner_name in (("player", "Игрок"), ("enemy", "Противник")):
            spirit = getattr(battle, "phys_spirits", {}).get(side)
            if spirit and int(spirit.get("hp", 0)) > 0:
                summons.append((
                    f"{owner_name}: Лесной дух",
                    int(spirit["hp"]),
                    int(spirit.get("max_hp", spirit["hp"])),
                    int(spirit.get("remaining", 0)),
                ))
            for golem in getattr(battle, "mage_golems", {}).get(side, []):
                if int(golem.get("hp", 0)) > 0:
                    summons.append((
                        f"{owner_name}: {golem.get('name', 'Голем')}",
                        int(golem["hp"]),
                        int(golem.get("max_hp", golem["hp"])),
                        0,
                    ))
        if not summons:
            return None

        discard = self.layout.discard_rect
        width = 176
        row_height = 34
        shown = summons[:2]
        extra_height = 14 if len(summons) > len(shown) else 0
        panel = pygame.Rect(
            max(6, discard.left - width - 8),
            discard.bottom + 8,
            width,
            22 + len(shown) * row_height + extra_height,
        )
        panel.clamp_ip(screen.get_rect())
        pygame.draw.rect(screen, (20, 24, 34), panel, border_radius=5)
        pygame.draw.rect(screen, (150, 170, 125), panel, 1, border_radius=5)
        draw_text(screen, self.scene.small_font, "ПРИЗЫВЫ", panel.x + 7, panel.y + 4, (190, 215, 150))
        for index, (name, hp, max_hp, remaining) in enumerate(shown):
            row_y = panel.y + 22 + index * row_height
            draw_text(screen, self.scene.small_font, name, panel.x + 7, row_y, (230, 230, 240))
            details = f"HP {hp}/{max_hp}"
            if remaining:
                details += f", {remaining} хода"
            draw_text(screen, self.scene.small_font, details, panel.x + 7, row_y + 15, (125, 225, 145))
        if extra_height:
            draw_text(screen, self.scene.small_font, f"и ещё {len(summons) - len(shown)}", panel.x + 7, panel.bottom - 14, (170, 175, 185))
        return panel

    def _draw_corner_fighter_card(self, screen, fighter, profile, derived, x, y, border_color, align):
        """Рисует укороченную карточку боца в углу (Имя, Уровень, HP/MP бары)."""
        width = 310
        height = 170
        class_type = profile.get("profession_type") or fighter.profession_type
        palette = class_palette(class_type)
        
        # Фон с полупрозрачностью
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((*palette["background"], 200))
        screen.blit(overlay, (x, y))
        
        # Рамка
        pygame.draw.rect(screen, palette["accent"], pygame.Rect(x, y, width, height), width=2, border_radius=8)
        
        inner_x = x + 12
        
        # Имя (большой шрифт как на карточке)
        name_surface = self.scene.small_font.render(fighter.name, True, (240, 240, 245))
        icon = class_icon(class_type)
        screen.blit(icon, (inner_x, y + 8))
        name_rect = name_surface.get_rect(topleft=(inner_x + icon.get_width() + 6, y + 8))
        screen.blit(name_surface, name_rect)
        
        # ID рядом с именем
        id_text = f"ID: {fighter.character_id or 'N/A'}"
        draw_text(screen, self.scene.small_font, id_text, name_rect.right + 15, y + 10, (170, 175, 185))
        
        # Уровень
        level_text = f"Уровень {fighter.level}"
        draw_text(screen, self.scene.small_font, level_text, inner_x, y + 28, (210, 215, 225))
        
        # Три полосы (HP, MP, ресурс класса) с одинаковым шагом, подпись над каждой
        hp_y = y + self.BAR_TOP
        mp_y = hp_y + self.BAR_STEP
        unique_y = mp_y + self.BAR_STEP
        bar_width = 280
        bar_height = 11
        side = "player" if fighter is self.scene.player else "enemy"
        shield = int(getattr(self.scene.battle, "mage_shields", {}).get(side, 0))
        shield += int(getattr(self.scene.battle, "phys_shields", {}).get(side, 0))
        self._draw_resource_bar(
            screen,
            inner_x,
            hp_y,
            bar_width,
            bar_height,
            "HP",
            profile["hp"],
            profile["max_hp"],
            (210, 80, 80),
            overlay_value=shield,
        )

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

        resource = self.RESOURCE_BARS.get(getattr(fighter, "unique_resource_type", None))
        if resource is not None:
            label, color = resource
            self._draw_resource_bar(
                screen,
                inner_x,
                unique_y,
                bar_width,
                bar_height,
                label,
                int(getattr(fighter, "unique_resource_current", 0)),
                int(getattr(fighter, "unique_resource_max", 1)),
                color
            )
        self._draw_banner_effects(screen, side, x, y + 174, width - 20)

    def _draw_banner_effects(self, screen, side, x, y, max_width):
        battle = self.scene.battle
        entries = []
        positive = {
            "damage_percent": ("Урон", "%"),
            "dodge_percent": ("Уворот", "%"),
            "crit_chance": ("Шанс крита", "%"),
            "crit_damage": ("Крит. урон", "%"),
            "agility_bonus": ("Ловкость", ""),
            "hit_bonus": ("Меткость", "%"),
            "incoming_damage_percent": ("Сопротивление урону", "%"),
            "extra_hits": ("Доп. удары", ""),
            "regen_per_hit_percent": ("Лечение за удар", "%"),
            "missing_hp_damage": ("Урон за потерю HP", ""),
            "bleed_heal_percent": ("Лечение от кровотечения", "%"),
            "crit_conversion": ("Конверсия крита", ""),
            "accuracy_gain": ("Меткость за уклонение", ""),
            "burn_bonus_max_percent": ("Сильное выжигание маны", "%"),
            "burn_bonus_current_percent": ("Сильное выжигание маны", "%"),
            "dodge_damage_bonus": ("Урон после уклонения", "%"),
        }
        negative = {
            "mana_regen_debuff": ("Восст. маны", "%"),
            "steal_healing_percent": ("Кража лечения", "%"),
            "outgoing_damage_flat": ("Исходящий урон", ""),
            "outgoing_damage_percent": ("Исходящий урон", "%"),
            "healing_blocked": ("Запрет лечения", ""),
            "forbid_damage_cards": ("Запрет атакующих карт", ""),
            "entangled": ("Оплетение", ""),
            "mark_damage": ("Метка уязвимости", " урона"),
            "poison_cap_bonus": ("Лимит яда увеличен", ""),
            "dodge_stun": ("Оглушение при уклонении", ""),
        }
        for buff in battle.phys_buffs[side]:
            turns = 1 if buff.get("expire_after_turn") else max(1, int(buff.get("remaining", 1)))
            for key, value in buff.items():
                if key in {"remaining", "fresh", "expire_after_turn", "forest_spirit", "entangle_source", "dodge_stack_limit"} or not value:
                    continue
                if key in positive:
                    label, suffix = positive[key]
                    color = (125, 225, 145)
                    text = f"{label} +{value}{suffix}"
                elif key in negative:
                    label, suffix = negative[key]
                    color = (245, 135, 125)
                    text = f"{label} {value}{suffix}" if not isinstance(value, bool) else label
                else:
                    label = key.replace("_", " ").capitalize()
                    color = (220, 210, 150)
                    text = f"{label}: {value}"
                entries.append((f"{text} ({turns} х.)", color))

        crit_chance_bonus = int(battle._buff(side, "crit_chance"))
        crit_damage_bonus = int(battle._buff(side, "crit_damage"))
        if crit_chance_bonus or crit_damage_bonus:
            entries.append((
                f"Бонус крита: +{crit_chance_bonus}% шанс / +{crit_damage_bonus}% урон",
                (255, 205, 120),
            ))

        fighter = self.scene.player if side == "player" else self.scene.enemy
        opponent_side = "enemy" if side == "player" else "player"
        poison_stacks_on_target = len(battle.poisons[opponent_side])
        if fighter.profession_type == "assassin" and poison_stacks_on_target:
            entries.append((
                f"Крит от яда цели: +{2 * poison_stacks_on_target}% шанс / +{4 * poison_stacks_on_target}% урон",
                (180, 220, 100),
            ))

        poison_count = len(battle.poisons[side])
        if poison_count:
            entries.append((f"Яд x{poison_count} (2% HP при завершении хода)", (180, 220, 100)))
        bleed = sum(int(effect["damage"]) for effect in battle.bleeds[side])
        if bleed:
            turns = max(int(effect["remaining"]) for effect in battle.bleeds[side])
            entries.append((f"Кровотечение -{bleed}/ход ({turns} х.)", (245, 125, 115)))
        for effect in battle.regenerations[side]:
            entries.append((
                f"Лечение {effect['heal_per_turn']} HP/ход ({effect['remaining']} х.)",
                (125, 225, 145),
            ))
        for effect in battle.delayed_heals[side]:
            entries.append((f"Отложенное лечение ({effect['remaining']} х.)", (125, 225, 145)))
        for effect in battle.delayed_hp_loss[side]:
            entries.append((f"Отложенная потеря {effect['amount']} HP ({effect['remaining']} х.)", (245, 125, 115)))
        for effect in battle.mage_statuses.get(side, []):
            stacks = int(effect.get("stacks", 1))
            suffix = f" x{stacks}" if stacks > 1 else ""
            entries.append((
                f"{effect['name'].capitalize()}{suffix} ({effect.get('remaining', 1)} х.)",
                (220, 185, 245),
            ))
        for label, turns in (("Оглушение", battle.mage_stuns.get(side, 0)), ("Заморозка", battle.mage_freeze.get(side, 0))):
            if turns:
                entries.append((f"{label} ({turns} х.)", (245, 125, 115)))
        if battle.invulnerable.get(side):
            entries.append(("Неуязвимость", (125, 205, 245)))
        state = battle.phys_state[side]
        for key, label, color in (
            ("guaranteed_crits", "Гарантированный крит", (125, 225, 145)),
            ("no_crit_attacks", "Атаки без крита", (220, 210, 150)),
            ("guaranteed_dodges", "Гарантированное уклонение", (125, 205, 245)),
            ("dodge_stacks", "Заряды после уклонения", (125, 225, 145)),
        ):
            if state.get(key, 0):
                entries.append((f"{label} x{state[key]}", color))
        if battle.skip_next_turn[side]:
            entries.append(("Пропуск следующего хода", (245, 125, 115)))
        shield = int(battle.phys_shields[side]) + int(battle.mage_shields[side])
        if shield:
            entries.append((f"Щит +{shield} HP", (120, 205, 245)))
        if battle.phys_spirits[side]:
            spirit = battle.phys_spirits[side]
            entries.append((f"Лесной дух HP {spirit['hp']}/{spirit['max_hp']}", (125, 225, 145)))
        for golem in battle.mage_golems.get(side, []):
            entries.append((f"{golem.get('name', 'Голем')} HP {golem['hp']}/{golem['max_hp']}", (125, 225, 145)))
        for bonus in battle.mage_damage_bonuses.get(side, []):
            entries.append((f"Магический урон +{bonus.get('percent', 0)}% ({bonus.get('remaining', 1)} х.)", (125, 225, 145)))
        for cloud in battle.mage_clouds.get(side, []):
            entries.append((f"Грозовая туча: {cloud.get('remaining', 1)} х.", (220, 185, 245)))
        for blessing in battle.mage_reactive_blessings.get(side, []):
            entries.append((
                f"Ответное благословение: {blessing.get('remaining', 1)} х.",
                (220, 185, 245),
            ))

        if not entries:
            return
        font = self.scene.small_font
        wrapped = []
        opponent = self.scene.enemy if side == "player" else self.scene.player
        opponent_side = "enemy" if side == "player" else "player"
        hovered_status = None
        for text, color in entries:
            description = self._banner_effect_description(text)
            if text.startswith("Яд x"):
                attacker = opponent
                stacks = len(battle.poisons[side])
                description = (
                    f"Яд: {stacks} стак(а/ов). В конце хода отравленной стороны наносит "
                    f"2% максимального HP и снимает один стак."
                )
                if attacker.profession_type == "assassin":
                    description += (
                        f" Ассасин, атакующий эту цель, получает за каждый стак "
                        f"+{2 * stacks}% шанса крита и +{4 * stacks}% критического урона."
                    )
            elif text.startswith("Крит от яда цели"):
                description = (
                    f"На противнике {poison_stacks_on_target} стаков яда: "
                    f"+{2 * poison_stacks_on_target}% к шансу крита и "
                    f"+{4 * poison_stacks_on_target}% к критическому урону."
                )
            elif text.startswith("Бонус крита:"):
                description = (
                    f"Временные эффекты дают +{crit_chance_bonus}% к шансу крита "
                    f"и +{crit_damage_bonus}% к критическому урону."
                )
            current = ""
            for word in text.split():
                candidate = f"{current} {word}".strip()
                if current and font.size(candidate)[0] > max_width - 12:
                    wrapped.append((current, color, description))
                    current = word
                else:
                    current = candidate
            if current:
                wrapped.append((current, color, description))
        line_height = font.get_linesize()
        panel = pygame.Rect(x + 10, y, max_width, 8 + len(wrapped) * line_height)
        pygame.draw.rect(screen, (20, 24, 34, 220), panel, border_radius=5)
        pygame.draw.rect(screen, (100, 110, 125), panel, 1, border_radius=5)
        for index, (text, color, description) in enumerate(wrapped):
            hovered_status = self._draw_effect_status(
                screen,
                text,
                color,
                description,
                panel.x + 6,
                panel.y + 4 + index * line_height,
            ) or hovered_status
        if hovered_status:
            self._draw_status_tooltip(screen, hovered_status)

    @staticmethod
    def _banner_effect_description(text):
        if text.startswith("Восст. маны"):
            return f"{text}: снижает восстановление маны на указанное значение."
        if text.startswith("Кража лечения"):
            return f"{text}: указанная доля лечения цели переходит наложившему эффект бойцу."
        if text.startswith("Исходящий урон"):
            return f"{text}: уменьшает урон, который цель наносит своими атаками."
        if text.startswith("Оглушение при уклонении"):
            return f"{text}: когда носитель эффекта уклоняется, атакующий оглушается на 1 ход."
        if text.startswith("Сопротивление урону"):
            return f"{text}: снижает входящий урон на указанное значение."
        if text.startswith("Урон за потерю HP"):
            return f"{text}: усиливает атаки в зависимости от потерянного здоровья."
        if text.startswith("Лечение от кровотечения"):
            return f"{text}: восстанавливает здоровье от урона, нанесённого кровотечением."
        if text.startswith("Запрет лечения"):
            return f"{text}: цель не может восстанавливать HP, пока действует эффект."
        if text.startswith("Запрет атакующих карт"):
            return f"{text}: цель не может разыгрывать карты, наносящие урон."
        if text.startswith("Оплетение"):
            return f"{text}: цель может разыграть не более одной карты за ход."
        if text.startswith("Метка уязвимости") or text.startswith("Метка +"):
            return f"{text}: каждая атака по цели получает указанный дополнительный урон."
        if text.startswith("Оглушение"):
            return f"{text}: оглушённая цель пропускает возможность разыграть карты."
        if text.startswith("Заморозка"):
            return f"{text}: замороженная цель может разыграть не более одной карты за ход."
        if text.startswith("Кровотечение"):
            return f"{text}: цель теряет указанное количество HP каждый ход до окончания эффекта."
        if text.startswith("Отложенное лечение"):
            return f"{text}: цель восстановит здоровье по истечении указанного числа ходов."
        if text.startswith("Отложенная потеря"):
            return f"{text}: указанное количество HP будет потеряно после окончания таймера."
        if text.startswith("Пропуск следующего хода"):
            return f"{text}: цель пропустит свой следующий ход."
        if text.startswith("Яд x"):
            return f"{text}: в конце хода отравленной стороны яд наносит 2% максимального HP и снимает стак."
        return f"Активный эффект: {text}."

    def _stats_frame_geometry(self, side, screen_width):
        margin = 10
        default_width = 310
        area = (
            self.scene.layout.player_hand
            if side == "player"
            else self.scene.layout.enemy_hand
        )
        max_hand_size = self.scene.battle.hand_limit_for(side)
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
        """Все 7 характеристик бойца слева и производные значения справа."""
        height = self.STATS_PANEL_HEIGHT
        
        # Фон с полупрозрачностью
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((30, 32, 45, 200))
        screen.blit(overlay, (x, y))
        
        # Рамка
        pygame.draw.rect(screen, border_color, pygame.Rect(x, y, width, height), width=2, border_radius=8)
        
        inner_x = x + 12
        header_y = y + 8
        draw_text(screen, self.scene.small_font, "ХАРАКТЕРИСТИКИ", inner_x, header_y, border_color)

        stats = profile.get("stats", {})
        stat_value_colors = {
            "Урон": (255, 255, 255),
            "Уворот": (150, 220, 255),
            "Крит": (255, 90, 90),
            "Маг Урон": (180, 140, 240),
        }
        col1_x = inner_x
        col2_x = inner_x + 190
        for index, (key, label) in enumerate(self.ALL_STATS):
            row_y = header_y + 24 + index * self.STATS_ROW_HEIGHT
            stat_text = f"{label}: {stats.get(key, 0)}"
            draw_text(screen, self.scene.small_font, stat_text, col1_x, row_y, (215, 220, 225))

        derived_keys = [key for key in stat_value_colors if key in derived]
        for index, derived_key in enumerate(derived_keys):
            row_y = header_y + 24 + index * self.STATS_ROW_HEIGHT
            derived_text = f"{derived_key}: {derived[derived_key]}"
            draw_text(screen, self.scene.small_font, derived_text, col2_x, row_y, stat_value_colors[derived_key])

    def _active_effect_statuses(self, side):
        """Активные эффекты карт бойца/лучника/асасина рядом с нужной строкой характеристик."""
        battle = self.scene.battle
        statuses = {
            "strength": [], "agility": [], "Урон": [], "Уворот": [], "Крит": [],
            "HP": [], "Отрицательные": [],
        }
        for buff in battle.phys_buffs[side]:
            turns = 1 if buff.get("expire_after_turn") else max(1, int(buff["remaining"]))
            for key, row in (
                ("damage_percent", "Урон"),
                ("dodge_percent", "Уворот"),
                ("crit_chance", "Крит"),
                ("agility_bonus", "agility"),
            ):
                if buff.get(key):
                    amount = int(buff[key])
                    suffix = "" if key == "agility_bonus" else "%"
                    label = "ловкость" if key == "agility_bonus" else key.replace("_", " ")
                    description = f"{label}: {amount:+d}{suffix}. Длительность: {turns} {self._turn_word(turns)}."
                    statuses[row].append(self._format_effect_status(amount, suffix, turns, description))
            negative_effects = (
                ("mana_regen_debuff", f"Мана -{int(buff.get('mana_regen_debuff', 0))}%", "Снижает восстановление маны.") ,
                ("steal_healing_percent", f"Кража лечения {int(buff.get('steal_healing_percent', 0))}%", "Часть лечения цели переходит противнику.") ,
                ("outgoing_damage_flat", f"Урон -{int(buff.get('outgoing_damage_flat', 0))}", "Снижает урон следующей атаки.") ,
                ("entangled", "Оплетение", "Отрицательный эффект: можно разыграть только 1 карту за ход."),
                ("mark_damage", f"Метка +{int(buff.get('mark_damage', 0))} урона", "Каждая атака по отмеченной цели получает дополнительный урон."),
            )
            for key, label, description in negative_effects:
                if buff.get(key):
                    status_turns = turns
                    status_text = f"{label} · {status_turns} {self._turn_word(status_turns)}"
                    statuses["Отрицательные"].append((status_text, (245, 105, 100), description))
        missing_ratio = (
            max(0, self.scene.player.max_hp - self.scene.player.hp)
            / max(1, self.scene.player.max_hp)
            if side == "player"
            else max(0, self.scene.enemy.max_hp - self.scene.enemy.hp)
            / max(1, self.scene.enemy.max_hp)
        )
        damage_bonus = battle._buff(side, "missing_hp_damage") * int(missing_ratio * 10)
        if damage_bonus:
            statuses["Урон"].append((
                f"+{damage_bonus}", (90, 230, 120),
                "Дополнительный урон растёт пропорционально потерянному здоровью.",
            ))
        bleed = sum(effect["damage"] for effect in battle.bleeds[side])
        if bleed:
            statuses["HP"].append((f"Кровотечение -{bleed}/ход", (245, 90, 90)))
            turns = max(effect["remaining"] for effect in battle.bleeds[side])
            statuses["Отрицательные"].append((
                f"Кровотечение -{bleed}/ход · {turns} хода",
                (245, 105, 100),
                f"Наносит {bleed} урона в конце хода. Осталось до {turns} ходов.",
            ))
        if battle.poisons[side]:
            statuses["HP"].append((f"Яд x{len(battle.poisons[side])}", (150, 220, 90)))
            turns = len(battle.poisons[side])
            statuses["Отрицательные"].append((
                f"Яд x{turns} · 2% HP/ход",
                (180, 220, 100),
                "В конце хода наносит 2% максимального HP независимо от числа стаков. "
                "Максимум 5 стаков; в конце каждого незамороженного хода снимается 1. Холод приостанавливает урон и спад стаков.",
            ))
        if battle.delayed_hp_loss[side]:
            amount = sum(int(item["amount"]) for item in battle.delayed_hp_loss[side])
            turns = min(int(item["remaining"]) for item in battle.delayed_hp_loss[side])
            statuses["Отрицательные"].append((
                f"Потеря HP -{amount} · {turns} {self._turn_word(turns)}",
                (245, 105, 100),
                f"Через {turns} ходов вы потеряете {amount} HP, но останетесь живы.",
            ))
        if battle.skip_next_turn[side]:
            statuses["Отрицательные"].append((
                "Пропуск хода",
                (245, 105, 100),
                "В следующий ход нельзя разыгрывать карты.",
            ))
        for status in battle.mage_statuses.get(side, []):
            name = status["name"]
            remaining = max(1, int(status.get("remaining", 1)))
            labels = {
                "огонь": ("Огонь", "В конце хода наносит 2 урона за каждый стак; после этого стаки сбрасываются до 1, при 1 стаке огонь гаснет."),
                "вода": ("Вода", "Снижает уворот владельца на 15%; участвует в реакциях."),
                "холод": ("Холод", "Пока действует, яд не наносит урон и не теряет стаки."),
                "электро": ("Электро", "Электрический статус; повторное наложение не сбрасывает отсчёт до оглушения."),
                "blinding": ("Ослепление", "Снижает точность атак на 20%."),
            }
            if name in labels:
                label, description = labels[name]
                stacks = int(status.get("stacks", 0))
                stack_text = f" x{stacks}" if stacks > 1 else ""
                statuses["Отрицательные"].append((
                    f"{label}{stack_text} · {remaining} {self._turn_word(remaining)}",
                    (245, 105, 100),
                    f"{description} Длительность: {remaining} {self._turn_word(remaining)}.",
                ))
        if battle.mage_stuns.get(side, 0):
            turns = int(battle.mage_stuns[side])
            statuses["Отрицательные"].append((
                f"Оглушение · {turns} {self._turn_word(turns)}",
                (245, 105, 100),
                "Оглушённый боец не может разыгрывать карты.",
            ))
        if battle.mage_freeze.get(side, 0):
            turns = int(battle.mage_freeze[side])
            statuses["Отрицательные"].append((
                f"Заморозка · {turns} {self._turn_word(turns)}",
                (145, 195, 245),
                "Замороженный боец может разыграть не более одной карты за ход.",
            ))
        return statuses

    @staticmethod
    def _effective_profile_for_derived(fighter, profile):
        # Статы бойца уже включают временные эффекты и бонусы предметов —
        # бонусы не прибавляем второй раз
        effective_profile = dict(profile)
        effective_profile["stats"] = {
            stat_name: getattr(fighter, stat_name)
            for stat_name in ("strength", "agility", "intuition", "wisdom", "endurance")
            if hasattr(fighter, stat_name)
        }
        effective_profile["equipment_bonuses"] = {
            "block": int(getattr(fighter, "equipment_stat_modifiers", {}).get("block", 0)),
        }
        return effective_profile

    def _combat_critical_bonuses(self, side):
        battle = self.scene.battle
        fighter = self.scene.player if side == "player" else self.scene.enemy
        target_side = "enemy" if side == "player" else "player"
        poison_stacks = len(battle.poisons[target_side]) if fighter.profession_type == "assassin" else 0
        return (
            int(battle._buff(side, "crit_chance")) + poison_stacks * 2,
            int(battle._buff(side, "crit_damage")) + poison_stacks * 4,
        )

    @staticmethod
    def _apply_chance_modifiers(
        derived,
        fighter,
        agility_bonus=0,
        crit_chance_bonus=0,
        crit_damage_bonus=0,
    ):
        adjusted = dict(derived)
        try:
            dodge = int(str(adjusted["Уворот"]).rstrip("%"))
        except (KeyError, TypeError, ValueError):
            pass
        else:
            adjusted["Уворот"] = (
                f"{max(0, dodge + fighter.temporary_dodge_chance_modifier + int(agility_bonus))}%"
            )

        try:
            critical_text, separator, critical_damage_text = str(adjusted["Крит"]).partition(" × ")
            critical = int(critical_text.rstrip("%"))
            critical_damage = int(critical_damage_text.rstrip("%")) if separator else 0
        except (KeyError, TypeError, ValueError):
            pass
        else:
            # Critical chance and damage include temporary combat and poison bonuses.
            adjusted["Крит"] = (
                f"{max(0, critical + fighter.temporary_critical_chance_modifier + int(crit_chance_bonus))}%"
                f" × {max(0, critical_damage + int(crit_damage_bonus))}%"
            )
        return adjusted

    @staticmethod
    def _format_effect_status(amount, suffix, turns, description=None):
        color = (90, 230, 120) if amount > 0 else (245, 90, 90)
        sign = "+" if amount > 0 else ""
        text = f"{sign}{amount}{suffix} на {turns} {DuelRenderer._turn_word(turns)}"
        return text, color, description or f"Временное изменение на {amount:+d}{suffix}. Длительность: {turns} {DuelRenderer._turn_word(turns)}."

    def _draw_effect_status(self, screen, text, color, description, x, y):
        surface = self.scene.small_font.render(text, True, color)
        rect = surface.get_rect(topleft=(x, y))
        screen.blit(surface, rect)
        if rect.collidepoint(pygame.mouse.get_pos()):
            return description
        return None

    def _draw_status_tooltip(self, screen, description):
        font = self.scene.small_font
        max_width = 270
        lines = []
        current = ""
        for word in description.split():
            candidate = f"{current} {word}".strip()
            if current and font.size(candidate)[0] > max_width - 16:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        width = min(max_width, max(font.size(line)[0] for line in lines) + 16)
        height = len(lines) * (font.get_height() + 2) + 12
        mouse_x, mouse_y = pygame.mouse.get_pos()
        tooltip = pygame.Rect(mouse_x + 14, mouse_y + 14, width, height)
        tooltip.clamp_ip(screen.get_rect())
        if tooltip.collidepoint((mouse_x, mouse_y)):
            tooltip.bottomright = (mouse_x - 8, mouse_y - 8)
            tooltip.clamp_ip(screen.get_rect())
        pygame.draw.rect(screen, (22, 25, 31), tooltip, border_radius=5)
        pygame.draw.rect(screen, (170, 150, 115), tooltip, 1, border_radius=5)
        for index, line in enumerate(lines):
            rendered = font.render(line, True, (240, 235, 220))
            screen.blit(rendered, (tooltip.x + 8, tooltip.y + 6 + index * (font.get_height() + 2)))

    @staticmethod
    def _turn_word(turns):
        if turns % 10 == 1 and turns % 100 != 11:
            return "ход"
        if turns % 10 in (2, 3, 4) and turns % 100 not in (12, 13, 14):
            return "хода"
        return "ходов"

    def _draw_resource_bar(self, screen, x, y, bar_width, bar_height, label, current, maximum, color, overlay_value=0):
        """Рисует полосу ресурса (HP/MP) как на карточке."""
        # Текст выше бара (как на карточке)
        text = f"{label}: {int(current)}/{int(maximum)}"
        if label == "HP" and overlay_value > 0:
            text += f" + ЩИТ {int(overlay_value)}"
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
            if label == "HP" and overlay_value > 0:
                shield_width = min(bar_width, max(1, int(bar_width * overlay_value / maximum)))
                if shield_width:
                    shield_x = x + filled_width
                    if shield_x + shield_width > x + bar_width:
                        shield_x = x + bar_width - shield_width
                    overlay = pygame.Surface((shield_width, bar_height), pygame.SRCALPHA)
                    overlay.fill((100, 205, 255, 125))
                    screen.blit(overlay, (shield_x, bar_y))
