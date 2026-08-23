import pygame


class DuelInputHandler:
    def __init__(self, scene):
        self.scene = scene

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if (
                event.key == pygame.K_r
                and self.scene.phase == "result"
            ):
                self.scene.restart()
                return

        if event.type == pygame.MOUSEWHEEL:
            self._handle_log_scroll(event.y)
            return

        if (
            event.type != pygame.MOUSEBUTTONDOWN
            or event.button != 1
        ):
            return

        if self.scene.phase == "resolve":
            return

        if self.scene.phase == "result":
            if self.scene.layout.new_button.collidepoint(event.pos):
                self.scene.restart()
            return

        if self.scene.phase == "setup":
            self._handle_setup_phase(event.pos)
            return

        if self.scene.phase == "choose":
            self._handle_choose_phase(event.pos)
            return

    def _handle_log_scroll(self, direction):
        if self.scene.phase == "setup":
            return

        renderer = getattr(self.scene, "renderer", None)

        if renderer is not None:
            if hasattr(renderer, "handle_scroll"):
                renderer.handle_scroll(direction)
                return

            for name in (
                "log_renderer",
                "log_area",
                "comment_renderer",
            ):
                log_renderer = getattr(renderer, name, None)

                if (
                    log_renderer is not None
                    and hasattr(log_renderer, "handle_scroll")
                ):
                    log_renderer.handle_scroll(direction)
                    return

        # Запасной вариант: изменяем позицию напрямую.
        current_offset = getattr(
            self.scene,
            "log_scroll_offset",
            0,
        )

        self.scene.log_scroll_offset = max(
            0,
            current_offset + (3 if direction > 0 else -3),
        )

    def _handle_setup_phase(self, pos):
        for stat_name, rect in (
            self.scene.layout.stat_plus_buttons.items()
        ):
            if rect.collidepoint(pos):
                self.scene.player.add_stat(stat_name)
                return

        for stat_name, rect in (
            self.scene.layout.stat_minus_buttons.items()
        ):
            if rect.collidepoint(pos):
                self.scene.player.remove_stat(stat_name)
                return

        if (
            self.scene.layout.stat_confirm_button.collidepoint(pos)
            and self.scene.player.is_ready()
        ):
            self.scene.phase = "choose"
            self.scene.comments = []

    def _handle_choose_phase(self, pos):
        for zone, rect in (
            self.scene.layout.attack_buttons.items()
        ):
            if rect.collidepoint(pos):
                self.scene.attack_zone = zone
                return

        for zone, rect in (
            self.scene.layout.defense_buttons.items()
        ):
            if rect.collidepoint(pos):
                if zone in self.scene.defense_zones:
                    self.scene.defense_zones.remove(zone)
                elif len(self.scene.defense_zones) < 2:
                    self.scene.defense_zones.append(zone)
                return

        ready = (
            self.scene.player.is_ready()
            and self.scene.attack_zone is not None
            and len(self.scene.defense_zones) == 2
        )

        if (
            self.scene.layout.confirm_button.collidepoint(pos)
            and ready
        ):
            self.scene.battle.choose_player_zones(
                self.scene.attack_zone,
                self.scene.defense_zones,
            )

            self.scene.phase = "resolve"
            self.scene.resolve_state = "CALC"
            self.scene.resolve_elapsed = 0.0
            self.scene.turn_calculated = False
            self.scene.comments_added = False

            self.scene.start_battle_comments()
