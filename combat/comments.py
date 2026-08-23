


ZONES_ACCUSATIVE = {
    "head": "голову",
    "body": "корпус",
    "waist": "пояс",
    "thigh": "бедро",
    "shin": "голень",
}

DEFAULT_COLOR = (230, 230, 230)
CRIT_COLOR = (255, 40, 40)

COMBO_COLORS = {
    2: (255, 255, 50),
    3: (255, 165, 0),
    4: (181, 101, 29),
    5: (255, 40, 40),
}


class DuelCommentator:
    def __init__(self, scene):
        self.scene = scene

        if not isinstance(getattr(self.scene, "comments", None), list):
            self.scene.comments = []

    def _get_combo_color(self, combo):
        try:
            combo = int(combo or 1)
        except (TypeError, ValueError):
            combo = 1

        if combo >= 5:
            return COMBO_COLORS.get(5)

        return COMBO_COLORS.get(combo, DEFAULT_COLOR)

    def _get_action_color(self, combo, critical):
        if critical:
            return CRIT_COLOR

        try:
            combo = int(combo or 1)
        except (TypeError, ValueError):
            combo = 1

        if combo >= 5:
            return CRIT_COLOR

        return self._get_combo_color(combo)

    def _get_enemy_combo_text(self, combo):
        try:
            combo = int(combo or 1)
        except (TypeError, ValueError):
            combo = 1

        if combo == 2:
            return " второй подряд"

        if combo == 3:
            return " третий подряд"

        if combo >= 4:
            return f" {combo}-й подряд"

        return ""

    def _get_player_combo_text(self, combo):
        try:
            combo = int(combo or 1)
        except (TypeError, ValueError):
            combo = 1

        if combo == 2:
            return " продолжая серию"

        if combo == 3:
            return " сохраняя серию ударов"

        if combo >= 4:
            return " не сбавляя натиска"

        return ""

    def _make_segment(self, text, color):
        return {
            "text": str(text),
            "color": color,
        }

    def add_combat_comments(self):
        battle = self.scene.battle

        if getattr(battle, "last_player_attack", None) is None:
            return

        player_hit = getattr(battle, "last_player_hit", False)
        player_damage = getattr(battle, "last_player_damage", 0)
        player_dodged = getattr(battle, "last_enemy_dodged", False)
        player_critical = getattr(battle, "last_player_critical", False)
        player_combo = getattr(battle, "last_player_combo", 1)

        enemy_hit = getattr(battle, "last_enemy_hit", False)
        enemy_damage = getattr(battle, "last_enemy_damage", 0)
        enemy_dodged = getattr(battle, "last_player_dodged", False)
        enemy_critical = getattr(battle, "last_enemy_critical", False)
        enemy_combo = getattr(battle, "last_enemy_combo", 1)

        player_zone = ZONES_ACCUSATIVE.get(
            battle.last_player_attack,
            "цель"
        )

        enemy_zone = ZONES_ACCUSATIVE.get(
            getattr(battle, "last_enemy_attack", None),
            "цель"
        )

        enemy_color = self._get_action_color(
            enemy_combo,
            enemy_critical
        )

        player_color = self._get_action_color(
            player_combo,
            player_critical
        )

        if enemy_dodged:
            enemy_text = (
                "ВЫ: ловко отскочили от атаки противника "
                "(Урон: 0 HP)."
            )
        elif not enemy_hit:
            enemy_text = (
                f"ВЫ: успешно заблокировали удар противника "
                f"в {enemy_zone} (Урон: 0 HP)."
            )
        elif enemy_critical:
            enemy_text = (
                "ВЫ: не смогли сдержать сокрушительный "
                "критический удар противника в пах "
                f"(Урон: {enemy_damage} HP)."
            )
        else:
            combo_text = self._get_enemy_combo_text(enemy_combo)
            enemy_text = (
                f"ВЫ: не смогли сдержать{combo_text} "
                f"яростный удар противника в {enemy_zone} "
                f"(Урон: {enemy_damage} HP)."
            )

        if player_dodged:
            player_text = (
                "Но вы попытались ударить в ответ, "
                "однако враг ловко ушёл от атаки "
                "(Урон: 0 HP)."
            )
        elif not player_hit:
            player_text = (
                f"Но ваш удар в {player_zone} "
                "был остановлен защитой противника "
                "(Урон: 0 HP)."
            )
        elif player_critical:
            player_text = (
                "Но вы со всего размаху пробили "
                "уязвимую точку противника "
                f"(Урон: {player_damage} HP)."
            )
        else:
            combo_text = self._get_player_combo_text(player_combo)
            player_text = (
                f"Но вы{combo_text} пробили защиту "
                f"противника ударом в {player_zone} "
                f"(Урон: {player_damage} HP)."
            )

        self.scene.comments.append({
            "segments": [
                self._make_segment(
                    enemy_text + " ",
                    enemy_color
                ),
                self._make_segment(
                    player_text,
                    player_color
                ),
            ],
            "large": False,
        })

        enemy = getattr(self.scene, "enemy", None)
        player = getattr(self.scene, "player", None)

        if enemy is not None and enemy.is_dead():
            self.scene.comments.append({
                "segments": [
                    self._make_segment(
                        "Победа! Враг рухнул на землю.",
                        (255, 215, 0)
                    )
                ],
                "large": False,
            })

        elif player is not None and player.is_dead():
            self.scene.comments.append({
                "segments": [
                    self._make_segment(
                        "В глазах темнеет... Вы проиграли.",
                        CRIT_COLOR
                    )
                ],
                "large": False,
            })

        # Храним только последние 2 комментария боя
        self.scene.comments = self.scene.comments[-2:]
