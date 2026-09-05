import pygame
import time

from core import settings
from ui.music import play_card_move_sound


class DuelInputHandler:
    DOUBLE_CLICK_SECONDS = 0.4

    def __init__(self, scene):
        self.scene = scene
        self.last_instant_click = None

    def handle_event(self, event):
        if self.scene.phase == "result":
            # Прокрутка списков карт
            if event.type == pygame.MOUSEWHEEL:
                # Левая сторона (игрок) - примерно x < 550
                # Правая сторона (противник) - примерно x > 550
                mouse_x = pygame.mouse.get_pos()[0]
                side = "player" if mouse_x < 550 else "enemy"
                scroll_key = f"cards_scroll_{side}"
                
                current_scroll = getattr(self.scene, scroll_key, 0)
                new_scroll = current_scroll - event.y * 20  # event.y > 0 для вверх
                setattr(self.scene, scroll_key, max(0, new_scroll))
                return
            
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                self.scene.return_to_tavern = True
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and getattr(self.scene, "result_button", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                self.scene.return_to_tavern = True
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.scene.return_to_tavern = True
                return

        if event.type == pygame.MOUSEWHEEL:
            self._handle_log_scroll(event.y)
            return

        if (
            event.type != pygame.MOUSEBUTTONDOWN
            or event.button not in (1, 3)
        ):
            return

        from ui.character_card import CharacterCard
        control = CharacterCard.stat_control_at(self.scene.layout.battle_player_card, event.pos)
        if control is not None:
            stat_name, delta = control
            changed = (
                self.scene.player.add_stat(stat_name)
                if delta > 0
                else self.scene.player.remove_stat(stat_name)
            )
            if changed:
                self.scene.save_online_character()
            return

        if self.scene.phase == "resolve":
            return

        if self.scene.layout.hide_player_card_button.collidepoint(event.pos):
            self.scene.player_card_hidden = not self.scene.player_card_hidden
            self.scene.player_card_manual_open = not self.scene.player_card_hidden
            return
        if self.scene.layout.hide_enemy_card_button.collidepoint(event.pos):
            self.scene.enemy_card_hidden = not self.scene.enemy_card_hidden
            self.scene.enemy_card_manual_open = not self.scene.enemy_card_hidden
            return

        if self.scene.phase in ("draft", "planning"):
            self._handle_card_phase(
                event.pos,
                event.button,
                getattr(event, "clicks", 1),
            )
            return

    def _handle_log_scroll(self, direction):
        current_offset = getattr(
            self.scene,
            "log_scroll_offset",
            0,
        )

        self.scene.log_scroll_offset = max(
            0,
            current_offset + (3 if direction > 0 else -3),
        )

    def _handle_card_phase(self, pos, button, clicks=1):
        layout = self.scene.layout
        battle = self.scene.battle
        if self.scene.phase == "draft":
            if self.scene.draft_next_side != "player":
                return
            visible_table = [card for card in battle.table if card.key not in battle.starting_reserved_keys]
            for index, card in enumerate(visible_table):
                if index < 5:
                    row_area = pygame.Rect(
                        layout.card_table.x + 20,
                        layout.card_table.y + 5,
                        layout.card_table.width - 40,
                        self.scene.renderer.card_renderer.CARD_HEIGHT,
                    )
                else:
                    row_area = pygame.Rect(
                        layout.card_table.x + 20,
                        layout.card_table.y + 5 + self.scene.renderer.card_renderer.CARD_HEIGHT + self.scene.renderer.card_renderer.GAP,
                        layout.card_table.width - 40,
                        self.scene.renderer.card_renderer.CARD_HEIGHT,
                    )
                if self.scene.renderer.card_renderer.card_rect(row_area, 5, index % 5).collidepoint(pos):
                    if battle.draft_mode == "starting":
                        battle.choose_starting_card("player", card.key)
                    else:
                        battle.choose_redraft_card("player", card.key)
                    self.scene.draft_next_side = "enemy"
                    self.scene.card_transfer = {
                        "card": card,
                        "started": time.monotonic(),
                        "source": self.scene.renderer.card_renderer.card_rect(row_area, 5, index % 5),
                    }
                    self.scene.phase = "draft_transfer"
                    play_card_move_sound()
                    return
            return

        if button == 1 and layout.play_cards_button.collidepoint(pos):
            battle.confirm_selection("player")
            self.scene.enemy_wait_started = time.monotonic()
            self.scene.phase = "waiting_enemy"
            return

        if button == 1:
            for index, card in enumerate(battle.selected["player"]):
                card_rect = self.scene.renderer.card_renderer.card_rect(layout.player_selected, len(battle.selected["player"]), index)
                if card_rect.collidepoint(pos):
                    self.scene.card_return_transfer = {
                        "card": card,
                        "started": time.monotonic(),
                        "source": card_rect,
                    }
                    self.scene.phase = "card_return"
                    play_card_move_sound()
                    return

        visible_hand = [card for card in battle.hands["player"] if card not in battle.selected["player"]]
        for index, card in enumerate(visible_hand):
            hand_rect = self.scene.renderer.card_renderer.card_rect(layout.player_hand, len(visible_hand), index)
            if hand_rect.collidepoint(pos):
                if button == 1:
                    if card.effect_type.startswith("instant_"):
                        now = time.monotonic()
                        is_double_click = clicks >= 2 or (
                            self.last_instant_click is not None
                            and self.last_instant_click["key"] == card.key
                            and now - self.last_instant_click["time"]
                            <= self.DOUBLE_CLICK_SECONDS
                        )
                        if is_double_click:
                            if battle.activate_instant_card("player", card.key):
                                play_card_move_sound()
                            self.last_instant_click = None
                        else:
                            self.last_instant_click = {
                                "key": card.key,
                                "time": now,
                            }
                    else:
                        self.last_instant_click = None
                        battle.select_card("player", card.key)
                elif button == 3:
                    self.last_instant_click = None
                    battle.deselect_card("player", card.key)
                return
