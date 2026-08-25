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

        # --- Панели характеристик внутри боевых карточек ---
        self.stat_row_y = {}
        self.stat_plus_buttons = {"player": {}, "enemy": {}}
        self.stat_minus_buttons = {"player": {}, "enemy": {}}

        stat_order = [
            "strength",
            "agility",
            "intuition",
            "endurance",
        ]

        # Якоря блока характеристик: сдвиг только по X.
        # Игрок: 10px от левого края экрана.
        # Противник: 10px правее рамки списка персонажей в чате.
        chat_people_right = settings.CHAT_PANEL_X + settings.CHAT_PANEL_WIDTH - 15
        stat_x_positions = {
            "player": 10,
            "enemy": chat_people_right + 30,
        }

        for index, stat_name in enumerate(stat_order):
            y = settings.STAT_PANEL_Y + index * settings.STAT_ROW_HEIGHT
            self.stat_row_y[stat_name] = y

            for side, base_x in stat_x_positions.items():
                self.stat_minus_buttons[side][stat_name] = pygame.Rect(
                    base_x + 130,
                    y + 4,
                    settings.STAT_BTN_W,
                    settings.STAT_BTN_H,
                )
                self.stat_plus_buttons[side][stat_name] = pygame.Rect(
                    base_x + 150,
                    y + 4,
                    settings.STAT_BTN_W,
                    settings.STAT_BTN_H,
                )

        self.stat_label_x = {
            "player": stat_x_positions["player"],
            "enemy": stat_x_positions["enemy"],
        }
        self.stat_value_x = {
            "player": stat_x_positions["player"] + settings.STAT_VALUE_OFFSET_X,
            "enemy": stat_x_positions["enemy"] + settings.STAT_VALUE_OFFSET_X,
        }
        self.stat_points_x = {
            "player": stat_x_positions["player"],
            "enemy": stat_x_positions["enemy"],
        }
        self.stat_points_y = settings.STAT_PANEL_Y + settings.STAT_POINTS_OFFSET_Y

        self.stat_confirm_button = pygame.Rect(settings.STAT_CONFIRM_RECT)
