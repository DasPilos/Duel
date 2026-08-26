from pathlib import Path
import time

import pygame

from core import settings
from ui.hud import (
    draw_text,
    draw_button,
    update_and_draw_floating_texts,
)

from ui.character_card import CharacterCard
from ui.renderers.setup_area import SetupAreaRenderer
from ui.renderers.choice_area import ChoiceAreaRenderer
from ui.renderers.duel_result import DuelResultRenderer


class DuelRenderer:
    def __init__(self, scene):
        self.scene = scene
        self.layout = scene.layout

        self.player_card = CharacterCard()
        self.enemy_card = CharacterCard()

        self.setup_renderer = SetupAreaRenderer(
            scene,
            self.layout,
        )

        self.choice_renderer = ChoiceAreaRenderer(
            scene,
            self.layout,
        )
        self.result_renderer = DuelResultRenderer(scene, self.layout)
        self.hit_placeholder = None
        placeholder_path = Path(__file__).resolve().parent.parent / "assets" / "combat" / "hit_placeholder.png"
        try:
            self.hit_placeholder = pygame.image.load(str(placeholder_path)).convert_alpha()
        except (pygame.error, OSError):
            self.hit_placeholder = None

    def draw(self, screen):
        screen.fill((16, 18, 28))

        self.draw_header(screen)

        self.player_card.update_from_fighter(self.scene.player, title="ИГРОК", kind="player")
        self.player_card.draw(
            screen,
            self.layout.battle_player_card,
            border_color=(80, 180, 120),
            editable=self.scene.phase == "setup",
        )

        self.enemy_card.update_from_fighter(self.scene.enemy, title="ПРОТИВНИК", kind="enemy")
        self.enemy_card.draw(
            screen,
            self.layout.battle_enemy_card,
            border_color=(210, 80, 80),
        )

        if self.scene.phase == "setup":
            self.setup_renderer.draw(screen)

        elif self.scene.phase == "choose":
            self.choice_renderer.draw(screen)
            self.draw_turn_timer(screen)

        elif self.scene.phase == "resolve":
            self.draw_resolve_overlay(screen)

        elif self.scene.phase == "result":
            self.result_renderer.draw(screen)

        if self.scene.chat is not None:
            self.scene.chat.draw(screen)
            self.scene.profile_overlay.draw(screen)

        update_and_draw_floating_texts(
            screen,
            self.scene.active_floating_texts,
        )

    def draw_header(self, screen):
        draw_text(
            screen,
            self.scene.big,
            "МИНИ-ДУЭЛЬ",
            self.layout.header_x,
            self.layout.header_y,
            (240, 240, 255),
        )

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
        bar = pygame.Rect(760, 500, 390, 12)
        pygame.draw.rect(screen, (55, 58, 68), bar, border_radius=5)
        fill = bar.copy()
        fill.width = int(bar.width * remaining / settings.TURN_DECISION_SECONDS)
        pygame.draw.rect(screen, color, fill, border_radius=5)
        label = self.scene.small_font.render(f"Время на ход: {remaining // 60}:{remaining % 60:02d}", True, color)
        screen.blit(label, label.get_rect(midtop=(bar.centerx, bar.bottom + 8)))

