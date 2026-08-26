import time

from ui.hud import FloatingText
from core import settings


class DuelResolver:
    def __init__(self, scene):
        self.scene = scene

    def update(self, dt):
        scene = self.scene

        if scene.phase != "resolve":
            return

        scene.resolve_elapsed += dt

        if scene.resolve_state == "CALC":
            if scene.resolve_elapsed >= scene.resolve_calc_time:
                if not scene.turn_calculated:
                    scene.battle.resolve_turn()
                    self._add_floating_damage()
                    scene.save_online_character()
                    scene.turn_calculated = True

                scene.resolve_state = "COMMENTS"
                scene.resolve_elapsed = 0.0
                return

        if scene.resolve_state == "COMMENTS":
            if scene.resolve_elapsed >= scene.resolve_comments_time:
                if not scene.comments_added:
                    scene.commentator.add_combat_comments()
                    scene.comments_added = True

                if scene.battle.is_over():
                    scene.finish_battle()
                    scene.phase = "result"
                else:
                    scene.phase = "choose"
                    scene.turn_deadline = time.monotonic() + settings.TURN_DECISION_SECONDS
                    scene.attack_zone = None
                    scene.defense_zones = []
                    scene.resolve_state = None
                    scene.resolve_elapsed = 0.0
                    scene.turn_calculated = False
                    scene.comments_added = False

        if scene.phase == "result":
            # Логи и комментарии сохраняются, ничего не очищаем.
            return

    def _add_floating_damage(self):
        battle = self.scene.battle

        self._add_floating_text(
            settings.ENEMY_FLOATING_TEXT_X,
            battle.last_player_damage,
            battle.last_player_dodged,
            battle.last_player_critical,
        )
        self._add_floating_text(
            settings.PLAYER_FLOATING_TEXT_X,
            battle.last_enemy_damage,
            battle.last_enemy_dodged,
            battle.last_enemy_critical,
        )

    def _add_floating_text(self, x, damage, dodged, critical):
        if dodged:
            text = "УВОРОТ"
            color = settings.DODGE_COLOR
        elif critical:
            text = f"-{damage} HP"
            color = settings.DAMAGE_COLOR
        else:
            text = f"-{damage} HP"
            color = settings.TEXT_COLOR

        self.scene.active_floating_texts.append(
            FloatingText(
                x,
                settings.FLOATING_TEXT_Y,
                text,
                self.scene.big,
                color=color,
                duration=settings.FLOATING_TEXT_DURATION,
            )
        )
