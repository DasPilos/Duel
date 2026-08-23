import pygame

from core import settings
from combat.zones import ZONES


class DuelLayout:
    def __init__(self):
        self.attack_buttons = {}
        self.defense_buttons = {}

        for zone in ZONES:
            y = settings.ZONE_Y[zone]

            ax, _, aw, ah = settings.ATTACK_BUTTON_RECT
            dx, _, dw, dh = settings.DEFENSE_BUTTON_RECT

            self.attack_buttons[zone] = pygame.Rect(ax, y, aw, ah)
            self.defense_buttons[zone] = pygame.Rect(dx, y, dw, dh)

        self.confirm_button = pygame.Rect(settings.CONFIRM_BUTTON_RECT)
        self.new_button = pygame.Rect(settings.NEW_BUTTON_RECT)

        self.player_panel_x = settings.PLAYER_PANEL_X
        self.enemy_panel_x = settings.ENEMY_PANEL_X
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

        # --- Фаза распределения характеристик (setup) ---
        self.stat_setup_title_x = settings.STAT_SETUP_TITLE_X
        self.stat_setup_title_y = settings.STAT_SETUP_TITLE_Y

        self.stat_points_x = settings.STAT_POINTS_X
        self.stat_points_y = settings.STAT_POINTS_Y

        self.stat_label_x = settings.STAT_LABEL_X
        self.stat_value_x = settings.STAT_VALUE_X

        self.stat_plus_buttons = {}
        self.stat_minus_buttons = {}
        self.stat_row_y = {}

        stat_order = [
            "strength",
            "agility",
            "intuition",
            "endurance",
        ]

        for index, stat_name in enumerate(stat_order):
            y = settings.STAT_ROW_Y_START + index * settings.STAT_ROW_HEIGHT
            self.stat_row_y[stat_name] = y

            self.stat_minus_buttons[stat_name] = pygame.Rect(
                settings.STAT_MINUS_X,
                y,
                settings.STAT_BTN_W,
                settings.STAT_BTN_H,
            )

            self.stat_plus_buttons[stat_name] = pygame.Rect(
                settings.STAT_PLUS_X,
                y,
                settings.STAT_BTN_W,
                settings.STAT_BTN_H,
            )

        self.stat_confirm_button = pygame.Rect(settings.STAT_CONFIRM_RECT)
