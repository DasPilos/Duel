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
from ui.chat import ChatPanel


class DuelScene:
    def __init__(self, online_session=None, opponent=None):
        self.online_session = online_session
        self.opponent_profile = opponent
        self.return_to_tavern = False
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

        if online_session is not None:
            self.chat = ChatPanel(online_session, "backyard", self)

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
        fighter.name = profile["name"]
        fighter.level = profile["level"]
        fighter.xp = profile.get("xp", 0)
        fighter.stats = dict(profile["stats"])
        fighter.stat_points = profile.get("stat_points", 0)
        fighter.recalculate_parameters()
        fighter.hp = min(profile.get("hp", fighter.max_hp), fighter.max_hp)
        fighter.mp = min(profile.get("mp", fighter.max_mp), fighter.max_mp)

    def save_online_character(self):
        if self.online_session is not None:
            self.online_session.save_fighter(self.player)

    def close(self):
        if self.online_session is not None:
            self.online_session.disconnect(self.player)

    def finish_battle(self):
        if self.online_session is not None and self.opponent_profile is not None:
            self.opponent_profile["hp"] = self.enemy.hp
            opponent_id = str(self.opponent_profile.get("id", ""))
            if self.opponent_profile.get("kind") == "bot" or opponent_id.startswith("bot_"):
                self.online_session.save_opponent(self.opponent_profile)
        self.save_online_character()

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
        if self.chat is not None and self.chat.handle_event(event):
            return
        self.input_handler.handle_event(event)

    def update(self, dt):
        self.resolver.update(dt)
        if self.chat is not None:
            self.chat.update(dt)

    def draw(self, screen):
        self.renderer.draw(screen)
