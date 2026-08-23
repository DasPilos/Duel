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
                    scene.phase = "result"
                else:
                    scene.phase = "choose"
                    scene.attack_zone = None
                    scene.defense_zones = []
                    scene.resolve_state = None
                    scene.resolve_elapsed = 0.0
                    scene.turn_calculated = False
                    scene.comments_added = False

        if scene.phase == "result":
            # Логи и комментарии сохраняются, ничего не очищаем.
            return
