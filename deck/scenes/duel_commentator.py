import random


ZONES_ACCUSATIVE = {
    "head": "голову",
    "body": "корпус",
    "waist": "пояс",
    "thigh": "бедро",
    "shin": "голень",
}


DEFAULT_COLOR = (230, 230, 230)
CRIT_COLOR = (255, 40, 40)
DODGE_COLOR = (150, 220, 255)

COMBO_COLORS = {
    2: (255, 255, 50),
    3: (255, 165, 0),
    4: (181, 101, 29),
    5: (255, 40, 40),
}


class DuelCommentator:
    ENEMY_DODGE_PHRASES = (
        "вы ловко ушли от атаки противника (Урон: 0 HP).",
        "вы увернулись от удара и остались целы (Урон: 0 HP).",
        "вы отскочили с линии удара противника (Урон: 0 HP).",
        "атака противника прошла мимо цели (Урон: 0 HP).",
        "вы избежали удара противника (Урон: 0 HP).",
    )
    ENEMY_BLOCK_PHRASES = (
        "вы остановили удар противника в {zone} (Урон: 0 HP).",
        "ваша защита выдержала атаку противника в {zone} (Урон: 0 HP).",
        "вы приняли удар противника в {zone} на защиту (Урон: 0 HP).",
        "вы не позволили атаке противника в {zone} пробить оборону (Урон: 0 HP).",
        "атака противника в {zone} разбилась о вашу защиту (Урон: 0 HP).",
    )
    ENEMY_HIT_PHRASES = (
        "противник нанёс{combo} яростный удар в {zone} (Урон: {damage} HP).",
        "оппонент пробил вашу защиту ударом в {zone} (Урон: {damage} HP).",
        "удар противника в {zone} оказался болезненно точным (Урон: {damage} HP).",
        "противник достал вас атакой в {zone} (Урон: {damage} HP).",
        "вы пропустили удар противника в {zone}, и это было зря (Урон: {damage} HP).",
    )
    ENEMY_CRITICAL_PHRASES = (
        "противник нанёс сокрушительный критический удар в {zone} (Урон: {damage} HP).",
        "оппонент нашёл уязвимое место и нанёс критический удар в {zone} (Урон: {damage} HP).",
        "критическая атака противника в {zone} прошла особенно убедительно (Урон: {damage} HP).",
        "противник пробил защиту критическим ударом в {zone} (Урон: {damage} HP).",
        "оппонент вложил всю злость в критический удар по {zone} (Урон: {damage} HP).",
    )
    PLAYER_DODGE_PHRASES = (
        "И ваш удар ушёл мимо цели, зато враг цел (Урон: 0 HP).",
        "И вы попытались ответить, но противник ловко отскочил (Урон: 0 HP).",
        "И атака в {zone} рассекла только воздух (Урон: 0 HP).",
        "И враг увернулся от удара в {zone} в последний момент (Урон: 0 HP).",
        "И противник избежал удара в {zone}; красиво, но неприятно (Урон: 0 HP).",
    )
    PLAYER_BLOCK_PHRASES = (
        "И ваш удар в {zone} был остановлен защитой противника (Урон: 0 HP).",
        "И противник заблокировал атаку в {zone} (Урон: 0 HP).",
        "И удар в {zone} встретил крепкую защиту (Урон: 0 HP).",
        "И атака в {zone} не пробила оборону противника (Урон: 0 HP).",
        "И ваша атака в {zone} разбилась о защиту (Урон: 0 HP).",
    )
    PLAYER_HIT_PHRASES = (
        "И вы{combo} пробили защиту противника ударом в {zone} (Урон: {damage} HP).",
        "И ваша атака в {zone} достигла цели (Урон: {damage} HP).",
        "И удар в {zone} заставил противника пересмотреть планы (Урон: {damage} HP).",
        "И вы точно попали в {zone}, оставив противнику синяк (Урон: {damage} HP).",
        "И защита противника не выдержала удара в {zone} (Урон: {damage} HP).",
    )
    PLAYER_CRITICAL_PHRASES = (
        "И вы со всего размаху пробили уязвимую точку противника (Урон: {damage} HP).",
        "И ваш критический удар нашёл самое неприятное место (Урон: {damage} HP).",
        "И противник познакомился с критическим ударом (Урон: {damage} HP).",
        "И вы попали критически точно, словно репетировали этот момент (Урон: {damage} HP).",
        "И ваша атака превратилась в критический аргумент (Урон: {damage} HP).",
    )
    PLAYER_ACTION_PHRASES = (
        "Вы, как следует размахнувшись, нанесли болезненный удар в {zone} противника (Урон: {damage} HP).",
        "Вы метко ударили противника в {zone}, и тот наверняка запомнит этот момент (Урон: {damage} HP).",
        "Вы вложили силу в удар и попали противнику в {zone} (Урон: {damage} HP).",
        "Вы обрушили атаку на {zone} противника (Урон: {damage} HP).",
        "Вы провели точную атаку в {zone} и нанесли урон (Урон: {damage} HP).",
    )
    PLAYER_ACTION_CRITICAL_PHRASES = (
        "Вы нанесли сокрушительный критический удар в уязвимое место противника (Урон: {damage} HP).",
        "Вы разглядели слабое место и безжалостно ударили туда (Урон: {damage} HP).",
        "Вы провели критически точную атаку, от которой противнику стало не до шуток (Урон: {damage} HP).",
        "Вы вложили всё в один удар и попали критически точно (Урон: {damage} HP).",
        "Ваша атака угодила в уязвимую точку противника (Урон: {damage} HP).",
    )
    PLAYER_ACTION_BLOCK_PHRASES = (
        "Вы замахнулись, но противник остановил ваш удар в {zone} (Урон: 0 HP).",
        "Вы атаковали в {zone}, однако защита противника выдержала (Урон: 0 HP).",
        "Ваш удар в {zone} достиг защиты противника и на этом закончился (Урон: 0 HP).",
        "Вы попытались пробить защиту ударом в {zone}, но безуспешно (Урон: 0 HP).",
        "Атака в {zone} выглядела многообещающе, но противник её заблокировал (Урон: 0 HP).",
    )
    PLAYER_ACTION_DODGE_PHRASES = (
        "Вы попытались ударить в {zone}, но противник ловко увернулся (Урон: 0 HP).",
        "Вы атаковали в {zone}, однако противник успел отскочить (Урон: 0 HP).",
        "Ваш удар в {zone} прошёл мимо цели (Урон: 0 HP).",
        "Вы нацелились в {zone}, но противник избежал удара (Урон: 0 HP).",
        "Атака в {zone} рассекла воздух: противник оказался проворнее (Урон: 0 HP).",
    )
    def __init__(self, scene):
        self.scene = scene

        if not isinstance(
            getattr(self.scene, "comments", None),
            list,
        ):
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

    def _damage_segments(self, text, damage_color):
        marker = " (-"
        damage_start = text.find(marker)
        if damage_start < 0:
            return [self._make_segment(text, DEFAULT_COLOR)]
        return [
            self._make_segment(text[:damage_start], DEFAULT_COLOR),
            self._make_segment(text[damage_start:], damage_color),
        ]

    @staticmethod
    def _pick_phrase(phrases, **values):
        return random.choice(phrases).format(**values)

    def add_combat_comments(self):
        battle = self.scene.battle
        if not getattr(battle, "last_exchange", None):
            return
        player = self.scene.player
        enemy = self.scene.enemy
        segments = []
        for index, event in enumerate(battle.last_exchange):
            if index:
                segments.append(self._make_segment(" ", DEFAULT_COLOR))
            actor = player if event["side"] == "player" else enemy
            target = enemy if event["side"] == "player" else player
            if event.get("skipped"):
                text = f"{actor.name} не предпринимает попыток в этот ход"
                color = DEFAULT_COLOR
            elif event["damage"]:
                text = f"{actor.name} применил {event['card']}. {target.name} потерял здоровье (-{event['damage']} хп)"
                color = CRIT_COLOR if event["critical"] else DEFAULT_COLOR
            elif event["dodged"]:
                text = f"{actor.name} применил {event['card']}, но {target.name} избежал удара (-0 хп)"
                color = DODGE_COLOR
            elif event["healed"]:
                text = f"{actor.name} применил {event['card']} и восстановил {event['healed']} хп"
                color = DEFAULT_COLOR
            else:
                text = f"{actor.name} применил {event['card']}"
                color = DEFAULT_COLOR
            segments.append(self._make_segment(text, DEFAULT_COLOR))
            if "(-" in text:
                marker = text[text.rfind("(-"):]
                segments[-1] = self._make_segment(text[:-len(marker)], DEFAULT_COLOR)
                segments.append(self._make_segment(marker, color))
        self.scene.comments.append({"segments": segments, "large": False})
