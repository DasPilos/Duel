import time
from pathlib import Path

import pygame

from ui.hud import FloatingImage, FloatingText
from ui.music import play_critical_hit_sound, play_dodge_sound, play_damage_sound
from core import settings


class DuelResolver:
    def __init__(self, scene):
        self.scene = scene
        self.critical_font = self._load_critical_font()
        self.damage_image = self._load_result_image("damage_result.png")
        self.dodged_image = self._load_result_image("dodged_result.png")

    @staticmethod
    def _load_result_image(name):
        path = Path(__file__).resolve().parent.parent / "assets" / "combat" / name
        try:
            return pygame.image.load(str(path)).convert_alpha()
        except (pygame.error, OSError):
            return None

    @staticmethod
    def _load_critical_font():
        font_path = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "BritannicBold.ttf"
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
                    if scene.chat is not None:
                        scene.chat.channel = "Лог боя"
                        scene.chat.message_list.set_messages(scene.chat._visible_messages())
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
        next_y = {"player": settings.FLOATING_TEXT_Y, "enemy": settings.FLOATING_TEXT_Y}
        for event in battle.last_exchange:
            if event.get("effect_cards"):
                x = settings.PLAYER_FLOATING_TEXT_X if event["side"] == "player" else settings.ENEMY_FLOATING_TEXT_X
                for card_name in event["effect_cards"]:
                    self._add_floating_effect(x, card_name, next_y[event["side"]])
                    next_y[event["side"]] += 30
            if event.get("effect_text"):
                x = settings.PLAYER_FLOATING_TEXT_X if event["side"] == "player" else settings.ENEMY_FLOATING_TEXT_X
                self._add_floating_effect(x, event["effect_text"], next_y[event["side"]])
                next_y[event["side"]] += 30
            if event.get("dodge_bonus", 0) > 0:
                x = settings.PLAYER_FLOATING_TEXT_X if event["side"] == "player" else settings.ENEMY_FLOATING_TEXT_X
                self._add_floating_bonus(x, event["dodge_bonus"], next_y[event["side"]])
                next_y[event["side"]] += 30
            if event.get("healed", 0) > 0:
                x = (
                    settings.PLAYER_FLOATING_TEXT_X + 50
                    if event["side"] == "player"
                    else settings.ENEMY_FLOATING_TEXT_X - 50
                )
                self._add_floating_heal(x, event["healed"], next_y[event["side"]])
                next_y[event["side"]] += 30
            if event.get("attack_dodged"):
                target_side = "enemy" if event["side"] == "player" else "player"
                x = settings.ENEMY_FLOATING_TEXT_X if target_side == "enemy" else settings.PLAYER_FLOATING_TEXT_X
                play_dodge_sound()
                self._add_combat_result(x, "HP-0", next_y[target_side], settings.DODGE_COLOR, self.dodged_image)
                next_y[target_side] += 30
            if event["damage"] <= 0 and not event.get("critical_attack"):
                continue
            target_side = "enemy" if event["side"] == "player" else "player"
            x = settings.ENEMY_FLOATING_TEXT_X if target_side == "enemy" else settings.PLAYER_FLOATING_TEXT_X
            play_damage_sound()
            if event.get("critical"):
                play_critical_hit_sound()
            if event.get("critical_attack"):
                self._add_combat_result(x, f"HP-{event['damage']}", next_y[target_side], settings.DAMAGE_COLOR, self.damage_image)
            else:
                self._add_floating_text(x, event["damage"], event["dodged"], event["critical"], next_y[target_side])
            next_y[target_side] += 30

    def _add_combat_result(self, x, text, y, color, image):
        if image is None:
            self.scene.active_floating_texts.append(
                FloatingText(x, y, text, self.critical_font, color=color, duration=settings.FPS * 6, velocity=-1.5)
            )
            return
        self.scene.active_floating_texts.append(
            FloatingImage(x, y, image, text, self.critical_font, color, duration=settings.FPS * 6, velocity=-1.5)
        )

    def _add_floating_bonus(self, x, amount, y):
        self.scene.active_floating_texts.append(
            FloatingText(
                x,
                y,
                f"+{amount}%",
                self.scene.big,
                color=settings.DODGE_COLOR,
                duration=settings.FLOATING_TEXT_DURATION,
                velocity=1.5,
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
                duration=settings.FLOATING_TEXT_DURATION,
                velocity=1.5,
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
                duration=settings.FLOATING_TEXT_DURATION,
                velocity=1.5,
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
                duration=settings.FLOATING_TEXT_DURATION,
                velocity=-1.5,
            )
        )
