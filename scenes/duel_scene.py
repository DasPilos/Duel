import pygame
import time

from combat.fighter import Fighter
from combat.character_stats import BASE_STAT_VALUE
from combat.card_battle import CardBattle
from combat.card_database import cards_for_type, is_mage_profession
from core import settings
from ui.layout import DuelLayout
from ui.duel_renderer import DuelRenderer
from ui.phase_transition import PhaseTransition

from scenes.duel_input import DuelInputHandler
from scenes.duel_resolver import DuelResolver
from scenes.duel_commentator import DuelCommentator
from ui.chat import ChatPanel
from ui.character_profile_overlay import CharacterProfileOverlay
from ui.music import (
    play_draft_music,
    stop_draft_music,
    play_battle_music,
    stop_battle_music,
    play_card_move_sound,
    play_draft_cards_deal_sound,
    duck_battle_music,
    update_music_ducking,
)
from combat.battle_archive import build_battle_record, write_battle_record
from client.network import ServerError


class DuelScene:
    def __init__(self, online_session=None, opponent=None):
        self.online_session = online_session
        self.opponent_profile = opponent
        self.return_to_tavern = False
        self.result_ready = False
        self.chat = None
        self.online_character = None
        self.font = pygame.font.SysFont(
            settings.FONT_NAME,
            settings.FONT_SIZE,
        )
        self.small_font = pygame.font.SysFont(
            settings.FONT_NAME,
            settings.SMALL_FONT_SIZE,
        )
        self.gained_points_font = pygame.font.SysFont(
            settings.FONT_NAME,
            settings.GAINED_POINTS_FONT_SIZE,
            bold=True,
        )
        self.big = pygame.font.SysFont(
            settings.FONT_NAME,
            settings.BIG_FONT_SIZE,
        )
        self.comment_font = pygame.font.SysFont(
            settings.FONT_NAME,
            settings.COMMENT_FONT_SIZE,
        )

        self.layout = DuelLayout()
        self.phase_transition = PhaseTransition()
        self.attack_zone = None
        self.defense_zones = set()

        self.restart(initial=True)

        self.inventory_button = pygame.Rect(settings.WIDTH - 70, 10, 50, 50)
        collection_loader = (
            getattr(online_session, "get_card_collection", None)
            if online_session is not None
            else None
        )
        self.profile_overlay = CharacterProfileOverlay(
            self.gained_points_font,
            collection_loader=collection_loader,
            deck_loader=getattr(online_session, "get_decks", None),
            deck_creator=getattr(online_session, "create_deck", None),
        )
        if online_session is not None:
            self.chat = ChatPanel(online_session, "backyard", self, profile_overlay=self.profile_overlay)
            self.start_battle_comments()
            self.chat.collapsed = True

        self.input_handler = DuelInputHandler(self)
        self.resolver = DuelResolver(self)
        self.commentator = DuelCommentator(self)
        self.renderer = DuelRenderer(self)

    def _apply_online_character(self):
        if self.online_session is None:
            return

        self.online_character = self.online_session.character
        self._apply_fighter_profile(self.player, self.online_character)

    @staticmethod
    def _apply_fighter_profile(fighter, profile):
        fighter.set_profession(profile.get("type"))
        fighter.name = profile["name"]
        fighter.level = profile["level"]
        fighter.xp = profile.get("xp", 0)
        fighter.stats = dict(profile["stats"])
        # Единый набор из 7 статов для всех персонажей — подстраховка для старых
        # сохранений, где часть характеристик ещё не была сохранена.
        for stat_name in fighter.STAT_NAMES:
            fighter.stats.setdefault(stat_name, BASE_STAT_VALUE)
        fighter.stat_points = profile.get("stat_points", 0)
        fighter.character_id = profile.get("id", profile.get("character_id"))
        fighter.equipment_stat_modifiers = {
            stat_name: int(value)
            for stat_name, value in profile.get("equipment_bonuses", {}).items()
            if stat_name in fighter.STAT_NAMES or stat_name in ("hp", "mp", "dodge", "block")
        }
        fighter.equipment = dict(profile.get("equipment", {}))
        fighter.recalculate_parameters()
        # Бой начинается с полным ресурсом класса для текущего уровня
        fighter.unique_resource_current = fighter.unique_resource_max
        hp = profile.get("hp", fighter.max_hp)
        if hp >= profile.get("max_hp", hp):
            # Полное здоровье остаётся полным и с бонусом выносливости от экипировки
            hp = fighter.max_hp
        fighter.hp = min(hp, fighter.max_hp)
        fighter.mp = min(profile.get("mp", fighter.max_mp), fighter.max_mp)

    def save_online_character(self):
        # После конца боя прогресс сохраняет только finish_battle через сервер
        if self.online_session is None or self.battle.is_over():
            return
        try:
            self.online_session.save_fighter(self.player)
        except ServerError as error:
            print(f"Персонаж не сохранён: {error}")

    def close(self):
        stop_draft_music()
        stop_battle_music()
        if self.chat is not None:
            self.chat.close()
        # Only disconnect if battle is complete; if battle is still ongoing, leave player AFK on server
        if self.online_session is not None and self.phase == "result":
            self.online_session.disconnect(self.player)

    def finish_battle(self):
        if self.battle_completion_saved:
            return
        self.battle_completion_saved = True

        if self.online_session is not None and self.opponent_profile is not None:
            self.opponent_profile.update({
                "level": self.enemy.level,
                "xp": self.enemy.xp,
                "hp": self.enemy.hp,
                "max_hp": self.enemy.max_hp,
                "mp": self.enemy.mp,
                "max_mp": self.enemy.max_mp,
                "stats": dict(self.enemy.stats),
                "stat_points": self.enemy.stat_points,
            })
            opponent_id = str(self.opponent_profile.get("id", ""))
            if self.opponent_profile.get("kind") == "bot" or opponent_id.startswith("bot_"):
                self.online_session.save_opponent(self.opponent_profile)
        
        # Выдача награды за победу
        if (
            self.online_session is not None
            and self.player.hp > 0
            and self.enemy.hp <= 0
        ):
            self.card_reward = self.online_session.award_battle_card(
                self.battle.reward_card_keys,
            )

        outcome = self.battle.outcome()
        archive_record = build_battle_record(self.battle, source="duel_scene")
        if self.online_session is not None and outcome is not None:
            # Опыт и деньги начисляет сервер; клиент только сообщает исход
            try:
                result = self.online_session.report_battle_result(
                    self.player, outcome, self.enemy.level, self.opponent_profile,
                    battle_record=archive_record,
                )
                self.currency_reward = dict(result.get("currency", self.currency_reward))
            except ServerError as error:
                print(f"Результат боя не сохранён: {error}")
                # Откатываем локально начисленный опыт, иначе сервер отклонит следующее сохранение
                character = self.online_session.character or {}
                for field in ("level", "xp", "stat_points"):
                    if field in character:
                        setattr(self.player, field, character[field])
                if "stats" in character:
                    self.player.stats = dict(character["stats"])
                    self.player.recalculate_parameters()

        write_battle_record(archive_record)

    def restart(self, initial=False):
        level = 1 if initial else self.player.level

        self.log_scroll_offset = 0

        self.player = Fighter("Игрок", level)
        self.enemy = Fighter(
            "Противник",
            level,
            auto_allocate=True,
        )
        if self.online_session is not None:
            self._apply_online_character()
        if self.opponent_profile is not None:
            self._apply_fighter_profile(self.enemy, self.opponent_profile)
        battle_cards = None
        selected_deck = getattr(self.online_session, "selected_deck", None)
        # Без онлайн-персонажа (офлайн) бой идёт на магических картах.
        character_type = self.online_character.get("type") if self.online_character else "mage"
        class_cards = cards_for_type(character_type)
        if selected_deck:
            card_keys = selected_deck.get("cards", {})
            if isinstance(card_keys, dict):
                card_keys = card_keys.keys()
            allowed = set(card_keys or ())
            # Старая или чужая колода не протащит в бой карты другого класса.
            battle_cards = [card for card in class_cards if card.key in allowed]
            if len(battle_cards) < CardBattle.STARTING_TABLE_SIZE:
                battle_cards = None
        if battle_cards is None:
            battle_cards = class_cards
        enemy_type = (self.opponent_profile or {}).get("type") or character_type
        # Своя колода и свой стол у каждой стороны: противник другого класса не получит чужих карт.
        enemy_cards = cards_for_type(enemy_type)
        enemy_deck_keys = set((self.opponent_profile or {}).get("deck") or ())
        if enemy_deck_keys:
            enemy_deck = [card for card in enemy_cards if card.key in enemy_deck_keys]
            if len(enemy_deck) >= CardBattle.STARTING_TABLE_SIZE:
                enemy_cards = enemy_deck
        if len(enemy_cards) < CardBattle.STARTING_TABLE_SIZE:
            enemy_cards = battle_cards
        self.battle = CardBattle(self.player, self.enemy, cards=battle_cards, enemy_cards=enemy_cards)
        if is_mage_profession(character_type) or is_mage_profession(enemy_type):
            self.battle.mage_mode = True
        self.attack_zone = None
        self.defense_zones = set()

        self.phase = "intro_table"
        self.intro_started = time.monotonic()
        self.draft_reveal_started = None
        self.draft_deal_sound_played = False
        self.draft_next_side = self.battle.draft_first_side()
        self.draft_cleanup_started = None
        self.card_transfer = None
        self.enemy_card_transfer = None
        self.card_return_transfer = None
        self.enemy_wait_started = None
        self.clash_started = None
        self.damage_started = None
        self.deck_shuffle_started = None
        self.draw_queue = []
        self.draw_transfer = None
        
        # Анимация карт при урон
        self.card_animation_started = None
        self.card_animation_phase = None  # "flying_to_discard"
        self.card_animation_start_pos = {}  # Начальные позиции карт {side: (x, y)}
        self.card_animation_sound_played = False  # Флаг для звука переворота
        self.player_card_hidden = True
        self.enemy_card_hidden = True
        self.player_card_manual_open = False
        self.enemy_card_manual_open = False
        self.player_selected_card_keys = []
        self.turn_deadline = None

        self.comments = []
        self.last_used_comments = {}

        self.resolve_state = None
        self.resolve_elapsed = 0.0
        self.resolve_calc_time = settings.RESOLVE_CALC_TIME
        self.resolve_comments_time = settings.RESOLVE_COMMENTS_TIME
        self.resolve_end_time = settings.RESOLVE_END_TIME

        self.turn_calculated = False
        self.comments_added = False
        self.timeout_count = 0
        self.afk_turns = 0
        self.timeout_surrender = False
        self.pending_phase_transition = None
        self.pending_transition_target = None
        self.battle_completion_saved = False
        self.card_reward = None
        self.currency_reward = {"copper": 0, "silver": 0, "gold": 0}

        if initial:
            self.active_floating_texts = []
            self.delayed_floating_texts = []
            self.ui_logs = []
        else:
            self.active_floating_texts.clear()
            self.delayed_floating_texts.clear()

    def start_battle_comments(self):
        """Закрепляет чат дуэли на канале боевого лога."""
        if not self.comments:
            self.comments = [
                {
                    "segments": [
                        {
                            "text": "Бой начался.",
                            "color": (230, 230, 230),
                        }
                    ],
                    "large": False,
                }
            ]
        if self.chat is not None:
            self.chat.channel = "Лог боя"
            self.chat.message_list.set_messages(self.chat._visible_messages())

    def handle_event(self, event):
        if self.profile_overlay.handle_event(event):
            return
        if self._handle_profile_click(event):
            return
        if self.chat is not None and self.chat.handle_event(event):
            return
        self.input_handler.handle_event(event)

    def _handle_profile_click(self, event):
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False

        if self.profile_overlay.is_open:
            action, _ = self.profile_overlay.handle_click(event.pos)
            if action == "close":
                return True
            if action is not None:
                return True

        # Обработка клика по кнопке инвентаря
        if self.inventory_button.collidepoint(event.pos):
            if self.online_session is not None:
                profile = self.online_character or self.online_session.character
                self.profile_overlay.open(profile, None)
            return True

        action, _ = self.profile_overlay.handle_click(event.pos)
        return action is not None

    def update(self, dt):
        now = time.monotonic()
        update_music_ducking(dt)
        if self.phase == "intro_table" and now - self.intro_started >= 1:
            self.phase = "intro_deck"
            self.intro_started = now
            return
        if self.phase == "intro_deck" and now - self.intro_started >= 1:
            self.phase = "draft_reveal"
            self.draft_reveal_started = now
            play_draft_music()
            return
        if self.phase == "draft_reveal":
            elapsed = now - self.draft_reveal_started
            if not self.draft_deal_sound_played and elapsed >= settings.DRAFT_REVEAL_START_DELAY_SECONDS:
                play_draft_cards_deal_sound()
                self.draft_deal_sound_played = True
            # Должно совпадать со временем прилёта последней карты в _draw_reveal_cards,
            # иначе фаза сменится раньше, чем карты долетят, и они будут резко "телепортироваться".
            reveal_duration = settings.DRAFT_REVEAL_START_DELAY_SECONDS + settings.DRAFT_CARD_DELAY_SECONDS * 9 + settings.CARD_MOVE_SECONDS + 0.05
            if elapsed >= reveal_duration:
                self.phase = "draft"
                self.turn_deadline = now + settings.DRAFT_TIMEOUT_SECONDS
                if self.enemy.intuition > self.player.intuition:
                    self._start_enemy_card_transfer()
            return
        if self.phase == "waiting_enemy":
            if now - self.enemy_wait_started >= 0.5:
                self._prepare_enemy_cards()
                self.clash_started = now
                self.phase = "clash"
                duck_battle_music(settings.ATTACK_ANIMATION_SECONDS + settings.DAMAGE_ANIMATION_SECONDS)
            return
        if self.phase == "clash":
            if now - self.clash_started >= settings.ATTACK_ANIMATION_SECONDS:
                self.battle.resolve_turn()
                self.resolver._add_floating_damage()
                self.commentator.add_combat_comments()
                if self.chat is not None:
                    self.chat.channel = "Лог боя"
                    self.chat.message_list.set_messages(self.chat._visible_messages())
                self.damage_started = now
                self.player_card_hidden = False
                self.enemy_card_hidden = False
                # Инициализируем анимацию карт для отброса в сток
                self.card_animation_started = now
                self.card_animation_phase = "flying_to_discard"
                self.card_animation_sound_played = False  # Сбрасываем флаг звука
                # Сохраняем позицию центра боевого стола как стартовую позицию
                self.card_animation_start_pos = {
                    "player": (self.layout.card_table.centerx, self.layout.card_table.centery),
                    "enemy": (self.layout.card_table.centerx, self.layout.card_table.centery),
                }
                self.cards_to_animate = {
                    "player": list(self.battle.selected["player"]),
                    "enemy": list(self.battle.selected["enemy"]),
                }
                self.phase = "damage"
            return
        if self.phase == "damage":
            if now - self.damage_started >= settings.DAMAGE_ANIMATION_SECONDS:
                if self.battle.is_over():
                    self.battle.outcome()
                    self.finish_battle()
                    self.pending_phase_transition = "result_transition"
                    self.pending_transition_target = "result"
                    stop_battle_music()
                    return
                self.deck_shuffle_started = now
                self.phase = "deck_shuffle"
            return
        if self.phase == "deck_shuffle":
            if now - self.deck_shuffle_started >= settings.DECK_SHUFFLE_SECONDS:
                if self.battle.is_over():
                    self.pending_phase_transition = "result_transition"
                    self.pending_transition_target = "result"
                    stop_battle_music()
                    return
                if self.battle.prepare_redraft():
                    self.draft_next_side = self.battle.draft_first_side()
                    self.turn_deadline = now + settings.DRAFT_TIMEOUT_SECONDS
                    self.phase = "draft"
                    play_draft_music()
                    self._after_starting_pick()
                    return
                self.battle.begin_next_turn()
                self.turn_deadline = now + settings.TURN_DECISION_SECONDS
                if not self.player_card_manual_open:
                    self.player_card_hidden = True
                if not self.enemy_card_manual_open:
                    self.enemy_card_hidden = True
                first = "player" if self.player.agility >= self.enemy.agility else "enemy"
                self.draw_queue = [first, "enemy" if first == "player" else "player"]
                self._start_next_card_draw(now)
            return
        if self.phase == "card_draw":
            if now - self.draw_transfer["started"] >= settings.CARD_MOVE_SECONDS:
                side = self.draw_transfer["side"]
                self.battle.draw_next_turn_card(side)
                self.draw_transfer = None
                self._start_next_card_draw(now)
            return

        if self.phase == "draft_cleanup":
            if time.monotonic() - self.draft_cleanup_started >= settings.DRAFT_CLEANUP_SECONDS:
                if self.battle.draft_mode == "starting":
                    self.battle.finish_starting_deal()
                    # Таймер драфта не переносится на первый размен: новый стартует после заставки
                    self.turn_deadline = None
                    self.pending_phase_transition = "battle_start_transition"
                    self.pending_transition_target = "planning"
                    self.draft_cleanup_started = None
                    stop_draft_music()
                elif self.battle.draft_mode == "redraft":
                    self.battle.finish_redraft()
                    self.phase = "planning"
                    self.turn_deadline = now + settings.TURN_DECISION_SECONDS
                    self.draft_cleanup_started = None
                    stop_draft_music()
            return
        if self.phase == "draft_transfer":
            if time.monotonic() - self.card_transfer["started"] >= settings.PLAYER_DRAFT_PICK_MOVE_SECONDS:
                self.phase = "draft"
                self.card_transfer = None
                self._after_starting_pick()
            return
        if self.phase == "draft_bonus_transfer":
            if now - self.card_transfer["started"] >= settings.TABLE_TO_HAND_MOVE_SECONDS:
                self.battle.hands[self.card_transfer["target_side"]].append(self.card_transfer["card"])
                self.card_transfer = None
                self.phase = "draft_cleanup"
                self.draft_cleanup_started = now
            return
        if self.phase == "enemy_transfer":
            if now - self.enemy_card_transfer["started"] >= settings.TABLE_TO_HAND_MOVE_SECONDS:
                self.enemy_card_transfer = None
                self.draft_next_side = "player"
                self.phase = "draft"
                self._after_starting_pick()
            return
        if self.phase == "card_return":
            if now - self.card_return_transfer["started"] >= 1:
                self.battle.deselect_card("player", self.card_return_transfer["card"].key)
                self.card_return_transfer = None
                self.phase = "planning"
            return
        if self.phase == "draft" and self.turn_deadline is not None and now >= self.turn_deadline:
            self._finish_afk_draft()
            return
        if self.phase in ("draft", "planning", "ready") and self.turn_deadline is not None:
            if time.monotonic() >= self.turn_deadline:
                self._handle_turn_timeout()
        
        # Обработка фаз переходов
        if self.phase == "result_transition":
            new_phase = self.phase_transition.update(dt)
            if new_phase is not None:
               self.phase = new_phase
               self.result_ready = True
            return
        
        if self.phase == "battle_start_transition":
            new_phase = self.phase_transition.update(dt)
            if new_phase is not None:
               self.phase = new_phase
               self.turn_deadline = time.monotonic() + settings.TURN_DECISION_SECONDS
               from ui.music import play_battle_music, _reset_music_volume
               import pygame
               # Явно останавливаем музыку и сбрасываем громкость перед новой музыкой
               try:
                   pygame.mixer.music.stop()
               except pygame.error:
                   pass
               _reset_music_volume()
               play_battle_music()
            return
        
        self.resolver.update(dt)
        if self.chat is not None:
            self.chat.update(dt)

    def draw(self, screen):
        # Проверяем флаги для инициирования переходов между фазами
        if self.pending_phase_transition is not None and not self.phase_transition.active:
            self.phase = self.pending_phase_transition
            self.phase_transition.start(screen, self.pending_transition_target)
            self.pending_phase_transition = None
            self.pending_transition_target = None
        
        self.renderer.draw(screen)

    def _handle_turn_timeout(self):
        self.timeout_count += 1
        self.afk_turns += 1
        self.turn_deadline = None
        if self.timeout_count >= settings.TURN_TIMEOUTS_BEFORE_SURRENDER:
            self.timeout_surrender = True
            self.player.hp = 0
            self.finish_battle()
            self.phase = "result"
            self.result_ready = True
            stop_battle_music()
            return

        self.battle.confirm_selection("player")
        self._prepare_enemy_cards()
        self.enemy_wait_started = time.monotonic()
        self.phase = "waiting_enemy"

    def _finish_afk_draft(self):
        self.turn_deadline = None
        stop_draft_music()
        if self.battle.draft_mode == "starting":
            self.battle.finish_afk_starting_deal()
            message = (
                f"{self.player.name} не участвовал в драфте "
                "и начинает бой без карт."
            )
        else:
            self.battle.finish_afk_redraft()
            message = (
                f"{self.player.name} не выбрал карты повторного драфта; "
                "карты распределены автоматически."
            )
        self.comments.append({
            "segments": [{
                "text": message,
                "color": (230, 230, 230),
            }],
            "large": False,
        })
        self.phase = "planning"
        self.turn_deadline = time.monotonic() + settings.TURN_DECISION_SECONDS
        self.start_battle_comments()
        play_battle_music()

    def _prepare_enemy_cards(self):
        if self.battle.confirmed["enemy"]:
            return
        self.battle.selected["enemy"] = []
        for card in list(self.battle.hands["enemy"]):
            if self.battle.remaining_card_slots("enemy") <= 0:
                break
            if self.battle.can_select("enemy", card):
                self.battle.selected["enemy"].append(card)
        self.battle.confirm_selection("enemy")

    def _start_next_card_draw(self, now):
        while self.draw_queue:
            side = self.draw_queue.pop(0)
            if not self.battle.can_draw_next_turn_card(side):
                continue
            card = self.battle.peek_card(side)
            if card is None:
                continue
            self.draw_transfer = {"side": side, "started": now, "card": card}
            self.phase = "card_draw"
            play_card_move_sound()
            return
        self.draw_transfer = None
        self.phase = "planning"

    def _auto_starting_pick(self):
        if self.draft_next_side == "enemy":
            self._start_enemy_card_transfer()

    def _auto_starting_pick_one(self):
        source = self.battle.table_for("enemy")
        if not source:
            return
        card = source[self.battle.rng.randrange(len(source))]
        if self.battle.draft_mode == "starting":
            if len(self.battle.hands["enemy"]) >= self.battle.STARTING_PICK_LIMIT:
                return
            self.battle.choose_starting_card("enemy", card.key)
        elif (
            self.battle.redraft_picks["enemy"]
            < self.battle.redraft_pick_limit("enemy")
        ):
            self.battle.choose_redraft_card("enemy", card.key)

    def _start_enemy_card_transfer(self):
        source_cards = self.battle.table_for("enemy")
        if not source_cards:
            self.draft_next_side = "player"
            self._after_starting_pick()
            return
        if self.battle.draft_mode == "starting":
            if len(self.battle.hands["enemy"]) >= self.battle.STARTING_PICK_LIMIT:
                return
        elif (
            self.battle.redraft_picks["enemy"]
            >= self.battle.redraft_pick_limit("enemy")
        ):
            return
        index = self.battle.rng.randrange(len(source_cards))
        card = source_cards[index]
        # Стол противника скрыт — его карта вылетает из верхнего края стола
        source = pygame.Rect(0, 0, self.renderer.card_renderer.CARD_WIDTH, self.renderer.card_renderer.CARD_HEIGHT)
        source.midtop = self.layout.card_table.midtop
        if self.battle.draft_mode == "starting":
            self.battle.choose_starting_card("enemy", card.key)
        else:
            self.battle.choose_redraft_card("enemy", card.key)
        self.enemy_card_transfer = {"card": card, "started": time.monotonic(), "source": source}
        self.phase = "enemy_transfer"
        play_card_move_sound()

    def _after_starting_pick(self):
        if self.battle.current_draft_complete():
            bonus = self.battle.take_draft_bonus_card()
            if bonus is not None:
                stronger, bonus_card = bonus
                if self.battle.draft_mode == "starting":
                    self.battle.starting_bonus_awarded = True
                    self.battle.starting_bonus_side = stronger
                self.card_transfer = {
                    "card": bonus_card,
                    "started": time.monotonic(),
                    "source": self.renderer.card_renderer.draft_slot_rect(0),
                    "target_side": stronger,
                }
                self.phase = "draft_bonus_transfer"
                play_card_move_sound()
            else:
                self.draft_cleanup_started = time.monotonic()
                self.phase = "draft_cleanup"
            return
        if self.battle.draft_mode == "redraft":
            if (
                self.battle.redraft_picks[self.draft_next_side]
                >= self.battle.redraft_pick_limit(self.draft_next_side)
            ):
                self.draft_next_side = (
                    "enemy" if self.draft_next_side == "player" else "player"
                )
        if self.draft_next_side == "enemy":
            self._start_enemy_card_transfer()
