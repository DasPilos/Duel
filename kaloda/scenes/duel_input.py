import pygame
import time

from kaloda.ui.music import play_card_move_sound


class DuelInputHandler:
    def __init__(self, scene):
        self.scene = scene

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
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and getattr(self.scene, "result_button", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                self.scene.return_to_tavern = True
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.scene.burn_mode:
                    self.scene.burn_mode = False
                    self.scene.burn_card_key = None
                    return
                self.scene.return_to_tavern = True
                return
            if event.key == pygame.K_b and self.scene.phase == "planning":
                battle = self.scene.battle
                if battle.burned_this_turn["player"]:
                    return
                if self.scene.burn_mode and self.scene.burn_card_key is not None:
                    if battle.burn_card("player", self.scene.burn_card_key):
                        self.scene.burn_mode = False
                        self.scene.burn_card_key = None
                    return
                if self.scene.burn_mode:
                    self.scene.burn_mode = False
                    self.scene.burn_card_key = None
                else:
                    self.scene.burn_mode = True
                    self.scene.burn_card_key = None
                return

        if event.type == pygame.MOUSEWHEEL:
            card_renderer = self.scene.renderer.card_renderer
            if card_renderer.details_card is not None:
                card_renderer.scroll_details(event.y)
            else:
                self._handle_log_scroll(event.y)
            return

        if (
            event.type != pygame.MOUSEBUTTONDOWN
            or event.button not in (1, 3)
        ):
            return

        card_renderer = self.scene.renderer.card_renderer
        if card_renderer.details_card is not None:
            if event.button == 1:
                card_renderer.close_details()
            return

        from kaloda.ui.character_card import CharacterCard
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

        if event.button == 3 and card_renderer.handle_details_click(event.pos):
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
            self._handle_card_phase(event.pos, event.button)
            return
        if self.scene.phase == "card_draw_choice":
            self._handle_draw_choice(event.pos, event.button)
            return

    def _handle_draw_choice(self, pos, button):
        if button != 1:
            return
        choices = self.scene.battle.draw_choices["player"]
        choice_area = self.scene.renderer.card_renderer.draw_choice_area("player")
        for index, card in enumerate(choices):
            rect = self.scene.renderer.card_renderer.card_rect(
                choice_area,
                len(choices),
                index,
            )
            if rect.collidepoint(pos):
                self.scene.choose_draw_choice(card.key)
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

    def _handle_card_phase(self, pos, button):
        layout = self.scene.layout
        battle = self.scene.battle
        if self.scene.phase == "draft":
            if self.scene.draft_next_side != "player":
                return
            card_renderer = self.scene.renderer.card_renderer
            for index, card in enumerate(card_renderer.draft_slots()):
                slot_rect = card_renderer.draft_slot_rect(index)
                if card is not None and slot_rect.collidepoint(pos):
                    if battle.draft_mode == "starting":
                        battle.choose_starting_card("player", card.key)
                    else:
                        battle.choose_redraft_card("player", card.key)
                    self.scene.draft_next_side = "enemy"
                    self.scene.card_transfer = {
                        "card": card,
                        "started": time.monotonic(),
                        "source": slot_rect,
                    }
                    self.scene.phase = "draft_transfer"
                    play_card_move_sound()
                    return
            return

        if button == 1 and layout.play_cards_button.collidepoint(pos):
            if self.scene.burn_mode:
                card_key = self.scene.burn_card_key
                if card_key is not None and battle.burn_card("player", card_key):
                    self.scene.burn_mode = False
                    self.scene.burn_card_key = None
                return
            self.scene.submit_player_turn()
            return

        if self.scene.burn_mode:
            if button == 1:
                burn_card = next(
                    (card for card in battle.hands["player"] if card.key == self.scene.burn_card_key),
                    None,
                )
                if burn_card is not None:
                    burn_rect = self.scene.renderer.card_renderer.card_rect(
                        layout.player_selected, 1, 0
                    )
                    if burn_rect.collidepoint(pos):
                        self.scene.burn_card_key = None
                        return
                visible_hand = [card for card in battle.hands["player"] if card not in battle.selected["player"]]
                for index, card in enumerate(visible_hand):
                    hand_rect = self.scene.renderer.card_renderer.card_rect(
                        layout.player_hand, len(visible_hand), index
                    )
                    if hand_rect.collidepoint(pos):
                        self.scene.burn_card_key = (
                            None if self.scene.burn_card_key == card.key else card.key
                        )
                        return
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
                    battle.select_card("player", card.key)
                return
