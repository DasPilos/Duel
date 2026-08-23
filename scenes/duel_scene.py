import pygame

from combat.fighter import Fighter
from combat.battle import Battle
from combat.zones import ZONES
from core import settings
from ui.layout import DuelLayout
from ui.duel_renderer import DuelRenderer

from scenes.duel_input import DuelInputHandler
from scenes.duel_resolver import DuelResolver
from scenes.duel_commentator import DuelCommentator


class DuelScene:
    def __init__(self):
        self.font = pygame.font.SysFont(
            settings.FONT_NAME,
            settings.FONT_SIZE,
        )
        self.small_font = pygame.font.SysFont(
            settings.FONT_NAME,
            settings.SMALL_FONT_SIZE,
        )
        self.big = pygame.font.SysFont(
            settings.FONT_NAME,
            settings.BIG_FONT_SIZE,
        )
        self.comment_font = pygame.font.SysFont(
            settings.FONT_NAME,
            settings.COMMENT_FONT_SIZE,
        )

        self.zone_names = list(ZONES.keys())
        self.layout = DuelLayout()

        self.restart(initial=True)

        self.input_handler = DuelInputHandler(self)
        self.resolver = DuelResolver(self)
        self.commentator = DuelCommentator(self)
        self.renderer = DuelRenderer(self)

    def restart(self, initial=False):
        level = 1 if initial else self.player.level

        self.log_scroll_offset = 0

        self.player = Fighter("Игрок", level)
        self.enemy = Fighter(
            "Противник",
            level,
            auto_allocate=True,
        )
        self.battle = Battle(self.player, self.enemy)

        self.phase = "setup"
        self.attack_zone = None
        self.defense_zones = []

        self.comments = []
        self.last_used_comments = {}

        self.resolve_state = None
        self.resolve_elapsed = 0.0
        self.resolve_calc_time = settings.RESOLVE_CALC_TIME
        self.resolve_comments_time = settings.RESOLVE_COMMENTS_TIME
        self.resolve_end_time = settings.RESOLVE_END_TIME

        self.turn_calculated = False
        self.comments_added = False

        if initial:
            self.active_floating_texts = []
            self.ui_logs = []
        else:
            self.active_floating_texts.clear()

    def start_battle_comments(self):
        """Запускает комментарий только после начала боя."""
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

    def handle_event(self, event):
        self.input_handler.handle_event(event)

    def update(self, dt):
        self.resolver.update(dt)

    def draw(self, screen):
        self.renderer.draw(screen)
