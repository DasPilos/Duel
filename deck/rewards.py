"""Награды за убийства существ и сундук короля скелетов: сервер считает их сам, клиент только просит."""

import random
from collections import Counter

NPC_KILL_XP = {
    "kobold": 3,
    "ancient_ent": 75,
    "skeleton": 15,
    "necromancer": 40,
    "skeleton_guard": 20,
    "skeleton_king": 200,
}

# Кого можно победить в каждой встрече: клиент не может заявить больше существ, чем там стоит
ENCOUNTER_ROSTERS = {
    "kobold": ("kobold",),
    "kobold_camp": ("kobold", "kobold", "kobold"),
    "kobold_camp_2": ("kobold", "kobold", "kobold"),
    "ancient_ent": ("ancient_ent",),
    "skeleton": ("skeleton",),
    "necromancer": ("necromancer",),
    "dungeon_room_1": ("skeleton", "skeleton"),
    "dungeon_room_3": ("skeleton", "skeleton", "necromancer"),
    "dungeon_room_5": ("skeleton_guard", "skeleton_guard", "skeleton_king"),
}

DUNGEON_TREASURE_COINS = 830
# (id предмета, название, шанс в процентах, количество)
DUNGEON_TREASURE_ITEMS = (
    (901, "Карта скелета-стража", 70, 1),
    (902, "Статуя короля скелетов", 60, 1),
    (901, "Карта скелета-стража", 50, 2),
    (903, "Копьё скелета-стража", 25, 1),
    (904, "Карта короля скелетов", 10, 1),
    (905, "Корона короля скелетов", 5, 1),
    (906, "Наследие павшего короля", 1, 1),
)


def npc_kill_xp(encounter_id, defeated_types):
    roster = ENCOUNTER_ROSTERS.get(str(encounter_id))
    if roster is None:
        raise ValueError("Неизвестный тип встречи")
    defeated_types = tuple(str(npc_type) for npc_type in defeated_types)
    if not defeated_types or len(defeated_types) > len(roster):
        raise ValueError("Некорректный список побеждённых существ")
    remaining = Counter(roster)
    reward = 0
    for npc_type in defeated_types:
        if remaining[npc_type] <= 0:
            raise ValueError("В этой встрече нельзя победить указанное существо")
        remaining[npc_type] -= 1
        reward += NPC_KILL_XP[npc_type]
    return reward


def roll_dungeon_treasure(rng=None):
    """Каждая награда выпадает независимо, поэтому один сундук может дать всё сразу."""
    rng = random if rng is None else rng
    items = []
    for item_id, name, chance_percent, quantity in DUNGEON_TREASURE_ITEMS:
        if rng.random() * 100 < chance_percent:
            items.append({"item_id": item_id, "name": name, "quantity": quantity})
    return {"coins": DUNGEON_TREASURE_COINS, "items": items}
