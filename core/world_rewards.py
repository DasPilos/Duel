from collections import Counter


NPC_KILL_XP = {
    "kobold": 3,
    "ancient_ent": 75,
    "skeleton": 15,
    "necromancer": 40,
    "skeleton_guard": 20,
    "skeleton_king": 200,
}

ENCOUNTER_ROSTERS = {
    "kobold": ("kobold",),
    "kobold_camp": ("kobold", "kobold", "kobold"),
    "kobold_camp_2": ("kobold", "kobold", "kobold"),
    "kobold_camp_3": ("kobold", "kobold", "kobold"),
    "ancient_ent": ("ancient_ent",),
    "skeleton": ("skeleton",),
    "necromancer": ("necromancer",),
    "dungeon_room_1": ("skeleton", "skeleton"),
    "dungeon_room_3": ("skeleton", "skeleton", "necromancer"),
    "dungeon_room_5": ("skeleton_guard", "skeleton_guard", "skeleton_king"),
}


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
        if npc_type not in remaining or remaining[npc_type] <= 0:
            raise ValueError("В этой встрече нельзя победить указанное существо")
        remaining[npc_type] -= 1
        reward += NPC_KILL_XP[npc_type]
    return reward
