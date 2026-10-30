import time

import pygame

from kaloda.ui.hud import FloatingImage, FloatingText
from kaloda.ui.music import play_critical_hit_sound, play_dodge_sound, play_damage_sound
from kaloda import settings


class DuelResolver:
    FLOATING_TEXT_DURATION = settings.FPS * 10
    FLOATING_TEXT_LINE_HEIGHT = 30
    FLOATING_TEXT_PANEL_GAP = 18

    def __init__(self, scene):
        self.scene = scene
        self.critical_font = self._load_critical_font()
        self.damage_image = self._load_result_image("damage_result.png")
        self.dodged_image = self._load_result_image("dodged_result.png")

    @staticmethod
    def _load_result_image(name):
        path = settings.ASSETS_DIR / "combat" / name
        try:
            return pygame.image.load(str(path)).convert_alpha()
        except (pygame.error, OSError):
            return None

    @staticmethod
    def _load_critical_font():
        font_path = settings.ASSETS_DIR / "fonts" / "BritannicBold.ttf"
        if font_path.is_file():
            try:
                return pygame.font.Font(str(font_path), 25)
            except pygame.error:
                pass
        return pygame.font.SysFont("arial", 25)

    def update(self, dt):
        scene = self.scene

        self._update_delayed_floating_texts(dt)

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
                    scene.result_ready = True
                else:
                    scene.phase = "planning"
                    scene.turn_deadline = time.monotonic() + settings.TURN_DECISION_SECONDS
                    scene.resolve_state = None
                    scene.resolve_elapsed = 0.0
                    scene.turn_calculated = False
                    scene.comments_added = False

    def _add_floating_damage(self):
        battle = self.scene.battle
        stats_panel_top = self._floating_text_panel_top()
        next_y = {
            "player": stats_panel_top - self.FLOATING_TEXT_PANEL_GAP,
            "enemy": stats_panel_top - self.FLOATING_TEXT_PANEL_GAP,
        }

        def stack_line(side):
            x = self._floating_text_x(side)
            y = next_y[side]
            occupied = self.scene.active_floating_texts
            while any(
                text.duration > 0
                and text.x == x
                and abs(text.y - y) < self.FLOATING_TEXT_LINE_HEIGHT
                for text in occupied
            ):
                y -= self.FLOATING_TEXT_LINE_HEIGHT
            next_y[side] -= self.FLOATING_TEXT_LINE_HEIGHT
            next_y[side] = min(next_y[side], y - self.FLOATING_TEXT_LINE_HEIGHT)
            return y

        for event in battle.last_exchange:
            if event.get("effect_cards"):
                x = self._floating_text_x(event["side"])
                for card_name in event["effect_cards"]:
                    self._add_floating_effect(x, card_name, stack_line(event["side"]))
            if event.get("effect_text"):
                x = self._floating_text_x(event["side"])
                self._add_floating_effect(x, event["effect_text"], stack_line(event["side"]))
            if event.get("dodge_bonus", 0) > 0:
                x = self._floating_text_x(event["side"])
                self._add_floating_bonus(x, event["dodge_bonus"], stack_line(event["side"]))
            if event.get("healed", 0) > 0:
                x = self._floating_text_x(event["side"])
                self._add_floating_heal(x, event["healed"], stack_line(event["side"]))
            hit_results = event.get("hit_results")
            if hit_results:
                target_side = "enemy" if event["side"] == "player" else "player"
                x = self._floating_text_x(target_side)
                if any(hit.get("dodged") for hit in hit_results):
                    play_dodge_sound()
                if any(int(hit.get("damage", 0)) > 0 for hit in hit_results):
                    play_damage_sound()
                if any(hit.get("critical") and int(hit.get("damage", 0)) > 0 for hit in hit_results):
                    play_critical_hit_sound()
                for hit in hit_results:
                    if hit.get("dodged"):
                        self._add_floating_text(x, 0, True, False, stack_line(target_side))
                    elif hit.get("blocked"):
                        self._add_combat_result(
                            x,
                            "БЛОК",
                            stack_line(target_side),
                            settings.DODGE_COLOR,
                            None,
                        )
                    else:
                        self._add_floating_text(
                            x,
                            int(hit.get("damage", 0)),
                            False,
                            bool(hit.get("critical")),
                            stack_line(target_side),
                        )
                continue
            if event.get("attack_dodged"):
                target_side = "enemy" if event["side"] == "player" else "player"
                x = self._floating_text_x(target_side)
                play_dodge_sound()
                self._add_combat_result(
                    x, "HP-0", stack_line(target_side), settings.DODGE_COLOR, self.dodged_image
                )
            if event["damage"] <= 0 and not event.get("critical_attack"):
                continue
            target_side = "enemy" if event["side"] == "player" else "player"
            x = self._floating_text_x(target_side)
            play_damage_sound()
            if event.get("critical"):
                play_critical_hit_sound()
            if event.get("critical_attack"):
                self._add_combat_result(
                    x, f"HP-{event['damage']}", stack_line(target_side), settings.DAMAGE_COLOR,
                    self.damage_image,
                )
            else:
                self._add_floating_text(
                    x, event["damage"], event["dodged"], event["critical"], stack_line(target_side)
                )

    def _floating_text_x(self, side):
        panel_x, panel_width = self.scene.renderer._stats_frame_geometry(side, settings.WIDTH)
        return panel_x + panel_width // 2

    def _floating_text_panel_top(self):
        return settings.HEIGHT - self.scene.renderer.STATS_PANEL_HEIGHT - 30

    def _add_combat_result(self, x, text, y, color, image):
        if image is None:
            self.scene.active_floating_texts.append(
                FloatingText(
                    x, y, text, self.critical_font, color=color,
                    duration=self.FLOATING_TEXT_DURATION, velocity=0, fade_out=False,
                )
            )
            return
        self.scene.active_floating_texts.append(
            FloatingImage(
                x, y, image, text, self.critical_font, color,
                duration=self.FLOATING_TEXT_DURATION, velocity=0, fade_out=False,
            )
        )

    def _add_floating_bonus(self, x, amount, y):
        self.scene.active_floating_texts.append(
            FloatingText(
                x,
                y,
                f"+{amount}%",
                self.scene.big,
                color=settings.DODGE_COLOR,
                duration=self.FLOATING_TEXT_DURATION,
                velocity=0,
                fade_out=False,
            )
        )

    def _add_floating_effect(self, x, text, y):
        self.scene.active_floating_texts.append(
            FloatingText(
                x,
                y,
                text,
                self.scene.big,
                color=(255, 220, 120),
                duration=self.FLOATING_TEXT_DURATION,
                velocity=0,
                fade_out=False,
            )
        )

    def _add_floating_heal(self, x, amount, y=settings.FLOATING_TEXT_Y):
        self.scene.active_floating_texts.append(
            FloatingText(
                x,
                y,
                f"+{amount} HP",
                self.scene.big,
                color=(110, 235, 120),
                duration=self.FLOATING_TEXT_DURATION,
                velocity=0,
                fade_out=False,
            )
        )

    def _update_delayed_floating_texts(self, dt):
        pending = self.scene.delayed_floating_texts
        for item in pending[:]:
            item["remaining"] -= max(0.0, dt)
            if item["remaining"] <= 0:
                self._add_floating_text(item["x"], item["damage"], item["dodged"], item["critical"])
                pending.remove(item)

    def _add_floating_text(self, x, damage, dodged, critical, y=settings.FLOATING_TEXT_Y):
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
                y,
                text,
                self.scene.big,
                color=color,
                duration=self.FLOATING_TEXT_DURATION,
                velocity=0,
                fade_out=False,
            )
        )
