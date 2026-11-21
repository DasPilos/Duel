extends RefCounted

# Задания гильдии из deck/quests.py. Принятие и прогресс ведёт клиент, награду выдаёт сервер
# (POST /api/deck/guild/quest-reward). Прогресс живёт, пока открыт мир, как сессия в Python.

const QUESTS := [
	{
		"id": "kill_kobold",
		"title": "Убить кобольда",
		"description": "Кобольды тревожат путников. Победите одного кобольда на арене.",
		"target": "kobold",
		"count": 1,
		"reward_coins": 10,
	},
	{
		"id": "kill_3_kobolds",
		"title": "Убить 3 кобольдов",
		"description": "Кобольды собрались в лагерь. Победите трёх кобольдов — в лагере или поодиночке.",
		"target": "kobold",
		"count": 3,
		"reward_coins": 40,
	},
	{
		"id": "kill_ancient_ent",
		"title": "Убить Древнего энта",
		"description": "Найдите Древнего энта и победите его.",
		"target": "ancient_ent",
		"count": 1,
		"reward_coins": 160,
	},
	{
		"id": "kill_skeleton",
		"title": "Убить скелета",
		"description": "Очистите кладбище от скелета.",
		"target": "skeleton",
		"count": 1,
		"reward_coins": 45,
	},
	{
		"id": "kill_necromancer",
		"title": "Убить некромансера",
		"description": "Победите некромансера, обосновавшегося на кладбище.",
		"target": "necromancer",
		"count": 1,
		"reward_coins": 100,
	},
	{
		"id": "clear_dungeon",
		"title": "Зачистить подземелье",
		"description": "Пройдите все комнаты подземелья, победите Короля скелетов и заберите сокровища.",
		"target": "dungeon_clear",
		"count": 1,
		"reward_coins": 780,
	},
]

# quest_id -> сколько раз выполнено; есть только у принятых заданий.
var progress: Dictionary = {}


static func quest_by_id(quest_id: String) -> Dictionary:
	for quest in QUESTS:
		if str(quest["id"]) == quest_id:
			return quest
	return {}


func status(quest_id: String) -> String:
	if not progress.has(quest_id):
		return "available"
	if int(progress[quest_id]) >= int(quest_by_id(quest_id)["count"]):
		return "completed"
	return "active"


func progress_of(quest_id: String) -> int:
	return int(progress.get(quest_id, 0))


func accept(quest_id: String) -> bool:
	if quest_by_id(quest_id).is_empty() or progress.has(quest_id):
		return false
	progress[quest_id] = 0
	return true


# Возвращает id заданий, которые этим обновлением стали выполненными.
func record_progress(target: String, amount := 1) -> Array:
	var finished: Array = []
	for quest_id in progress.keys():
		var quest := quest_by_id(str(quest_id))
		var done := int(progress[quest_id])
		if str(quest["target"]) != target or done >= int(quest["count"]):
			continue
		progress[quest_id] = mini(int(quest["count"]), done + amount)
		if int(progress[quest_id]) >= int(quest["count"]):
			finished.append(str(quest_id))
	return finished


# Сдача локально, после подтверждения сервером. Возвращает награду из каталога или 0.
func claim(quest_id: String) -> int:
	if status(quest_id) != "completed":
		return 0
	var reward := int(quest_by_id(quest_id)["reward_coins"])
	progress.erase(quest_id)
	return reward
