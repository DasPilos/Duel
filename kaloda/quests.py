"""Задания гильдии (прогресс хранится в сессии клиента, награду выдаёт сервер)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Quest:
    id: str
    title: str
    description: str
    target: str
    count: int
    reward_coins: int


QUESTS = (
    Quest("kill_kobold", "Убить кобольда",
          "Кобольды тревожат путников. Победите одного кобольда на арене.",
          "kobold", 1, 10),
    Quest("kill_3_kobolds", "Убить 3 кобольдов",
          "Кобольды собрались в лагерь. Победите трёх кобольдов — в лагере или поодиночке.",
          "kobold", 3, 40),
    Quest("kill_ancient_ent", "Убить Древнего энта",
          "Найдите Древнего энта и победите его.",
          "ancient_ent", 1, 160),
    Quest("kill_skeleton", "Убить скелета",
          "Очистите кладбище от скелета.",
          "skeleton", 1, 45),
    Quest("kill_necromancer", "Убить некромансера",
          "Победите некромансера, обосновавшегося на кладбище.",
          "necromancer", 1, 100),
    Quest("clear_dungeon", "Зачистить подземелье",
          "Пройдите все комнаты подземелья, победите Короля скелетов и заберите сокровища.",
          "dungeon_clear", 1, 780),
)
QUESTS_BY_ID = {quest.id: quest for quest in QUESTS}


class QuestLog:
    """Локальный прогресс принятых заданий."""

    def __init__(self):
        self.progress = {}

    def status(self, quest_id):
        if quest_id not in self.progress:
            return "available"
        if self.progress[quest_id] >= QUESTS_BY_ID[quest_id].count:
            return "completed"
        return "active"

    def accept(self, quest_id):
        if quest_id not in QUESTS_BY_ID or quest_id in self.progress:
            return False
        self.progress[quest_id] = 0
        return True

    def record_progress(self, target, amount=1):
        """Advance matching objectives and return quests completed by this update."""
        finished = []
        for quest_id, done in self.progress.items():
            quest = QUESTS_BY_ID[quest_id]
            if quest.target != target or done >= quest.count:
                continue
            self.progress[quest_id] = min(quest.count, done + amount)
            if self.progress[quest_id] >= quest.count:
                finished.append(quest)
        return finished

    def claim(self, quest_id):
        """Сдать выполненное задание локально после подтверждения награды сервером."""
        if self.status(quest_id) != "completed":
            return 0
        reward = QUESTS_BY_ID[quest_id].reward_coins
        del self.progress[quest_id]
        return reward

    def active_quests(self):
        return [(QUESTS_BY_ID[quest_id], done) for quest_id, done in self.progress.items()]


def quest_log_for(session):
    log = getattr(session, "quest_log", None)
    if log is None:
        log = QuestLog()
        try:
            session.quest_log = log
        except AttributeError:
            pass
    return log
