import pygame

from core import settings


class DuelLayout:
    def __init__(self):
        self.card_table = pygame.Rect(settings.CARD_TABLE_RECT)
        self.player_hand = pygame.Rect(settings.PLAYER_HAND_RECT)
        self.player_selected = pygame.Rect(settings.PLAYER_SELECTED_RECT)
        self.enemy_selected = pygame.Rect(settings.ENEMY_SELECTED_RECT)
        self.enemy_hand = pygame.Rect(settings.ENEMY_HAND_RECT)
        self.player_points = pygame.Rect(settings.PLAYER_POINTS_RECT)
        self.enemy_points = pygame.Rect(settings.ENEMY_POINTS_RECT)
        self.confirm_selection_button = pygame.Rect(settings.CONFIRM_SELECTION_RECT)
        self.play_cards_button = pygame.Rect(settings.PLAY_CARDS_RECT)
        self.turn_bar = pygame.Rect(settings.TURN_BAR_RECT)
        self.deck_rect = pygame.Rect(settings.DECK_RECT)
        self.discard_rect = pygame.Rect(settings.DISCARD_RECT)
        self.hide_player_card_button = pygame.Rect(settings.HIDE_PLAYER_CARD_RECT)
        self.hide_enemy_card_button = pygame.Rect(settings.HIDE_ENEMY_CARD_RECT)
        self.confirm_button = self.confirm_selection_button
        self.new_button = pygame.Rect(settings.NEW_BUTTON_RECT)

        self.player_panel_x = settings.PLAYER_PANEL_X
        self.enemy_panel_x = settings.ENEMY_PANEL_X
        self.battle_player_card = pygame.Rect(settings.PLAYER_CARD_RECT)
        self.battle_enemy_card = pygame.Rect(settings.ENEMY_CARD_RECT)
        self.panel_title_y = settings.PANEL_TITLE_Y
        self.panel_text_x_offset = settings.PANEL_TEXT_X_OFFSET
        self.panel_name_y = settings.PANEL_NAME_Y
        self.panel_hp_y = settings.PANEL_HP_Y
        self.panel_hp_bar_y = settings.PANEL_HP_BAR_Y
        self.panel_mp_y = settings.PANEL_MP_Y
        self.panel_mp_bar_y = settings.PANEL_MP_BAR_Y
        self.silhouette_y = settings.SILHOUETTE_Y

        self.header_x = settings.HEADER_X
        self.header_y = settings.HEADER_Y

        self.attack_title_x = settings.ATTACK_TITLE_X
        self.defense_title_x = settings.DEFENSE_TITLE_X
        self.choice_title_y = settings.CHOICE_TITLE_Y

        self.result_x = settings.RESULT_X
        self.result_y = settings.RESULT_Y

        self.overlay_x = settings.OVERLAY_X
        self.overlay_title_y = settings.OVERLAY_TITLE_Y
        self.overlay_description_x = settings.OVERLAY_DESCRIPTION_X
        self.overlay_description_y = settings.OVERLAY_DESCRIPTION_Y

        self.log_x = settings.LOG_X
        self.log_y = settings.LOG_Y
        self.log_line_height = settings.LOG_LINE_HEIGHT

        self.comments_y = settings.COMMENTS_Y
        self.comment_line_height = settings.COMMENT_LINE_HEIGHT

        self.player_floating_text_x = settings.PLAYER_FLOATING_TEXT_X
        self.enemy_floating_text_x = settings.ENEMY_FLOATING_TEXT_X
        self.floating_text_y = settings.FLOATING_TEXT_Y

        self.stat_confirm_button = pygame.Rect(settings.STAT_CONFIRM_RECT)
