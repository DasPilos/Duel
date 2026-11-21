extends RefCounted

# Правила производственного окна из ui/production_building_window.py: кто стоит на месте, когда склад полон,
# кого поставить на работу, тексты подтверждений и сообщений, таймеры, участки и текст следующего уровня. Сетевых вызовов здесь нет.
# В строках горожан сервер не отдаёт поле working, поэтому проверка not working проходит всегда, как и в Python.

const TAB_PRODUCTION := "production"
const TAB_STORAGE := "storage"
const TAB_UPGRADE := "upgrade"
const ACTION_HIRE := "hire"
const ACTION_FIRE := "fire"
const ACTION_PLAYER := "player"
const PLAYER_PREFIX := "player:"
const CITIZEN_PREFIX := "citizen:"
const CITIZEN_FREE := "Свободен"
const SATISFIED := "satisfied"

const MSG_NO_CITIZENS := "Нет свободных горожан для работы."
const MSG_HIRED := "%s отправлен к месту работы."
const MSG_RECALLED := "Горожанин возвращается в город."
const MSG_STORAGE_FULL := "Склад переполнен, нельзя начать добычу."
const MSG_LEAVE_BLOCKED := "Чтобы покинуть место, завершите работу."
const MSG_BAD_POPULATION := "Некорректный ответ API населения."
const MSG_BUSY := "Подождите завершения текущего запроса."
const MSG_PLOT_FULL := "Нет свободного места. Снимите горожанина правой кнопкой мыши."
const MSG_PLOT_EMPTY := "На этом участке нет рабочего"
const REF := preload("res://scripts/economy_production_reference.gd")


static func player_worker_id(character_id: int) -> String:
	return "%s%d" % [PLAYER_PREFIX, character_id]


static func slots_of(state: Dictionary) -> Array:
	var slots: Variant = state.get("worker_slots", [])
	return slots if slots is Array else []


static func slot_at(state: Dictionary, slot_index: int) -> Dictionary:
	for slot in slots_of(state):
		if slot is Dictionary and int(slot.get("slot_index", -1)) == slot_index:
			return slot
	return {}


static func player_slot(state: Dictionary, character_id: int) -> Dictionary:
	var worker_id := player_worker_id(character_id)
	for slot in slots_of(state):
		if slot is Dictionary and str(slot.get("worker_id", "")) == worker_id:
			return slot
	return {}


static func player_is_working(state: Dictionary, character_id: int) -> bool:
	return not player_slot(state, character_id).is_empty()


# Как storage_is_full в Python: сервер присылает storage_full, иначе считаем по товарам склада.
static func storage_is_full(state: Dictionary) -> bool:
	if state.has("storage_full"):
		return _truthy(state["storage_full"])
	var storage := _dict(state.get("storage", {}))
	var limit := int(storage.get("limit", 0))
	var amounts: Array[int] = []
	for resource in storage:
		if str(resource) != "limit":
			amounts.append(int(storage[resource]))
	if amounts.is_empty():
		return false
	for amount in amounts:
		if amount < limit:
			return false
	return true


# Как slot_storage_is_full в Python: склад полон, если по каждому ресурсу мест достигнут лимит.
static func slot_storage_is_full(slots: Array, storage: Dictionary) -> bool:
	var limit := int(storage.get("limit", 0))
	var resources: Array[String] = []
	for slot in slots:
		if not slot is Dictionary:
			continue
		for resource in _resources_of(slot):
			if not resources.has(resource):
				resources.append(resource)
	if resources.is_empty():
		return false
	for resource in resources:
		if int(storage.get(resource, 0)) < limit:
			return false
	return true


# Нажатие «Встать на добычу» на чужом месте: блокируется полным складом по ресурсам этого места.
static func player_click_blocked(state: Dictionary, slot_index: int, character_id: int) -> bool:
	var slot := slot_at(state, slot_index)
	if slot.is_empty() or str(slot.get("worker_id", "")) == player_worker_id(character_id):
		return false
	return slot_storage_is_full([slot], _dict(state.get("storage", {})))


# Подтверждение «Встать на добычу» блокируется только если игрок нигде не работает и склад полон.
static func player_confirm_blocked(state: Dictionary, slot_index: int) -> bool:
	if state.get("player_work") != null:
		return false
	var slot := slot_at(state, slot_index)
	return not slot.is_empty() and slot_storage_is_full([slot], _dict(state.get("storage", {})))


# Номер горожанина из worker_id вида citizen:N; -1, если на месте не горожанин (как в Python, где нужен префикс citizen:).
static func citizen_id(worker_id: Variant) -> int:
	var text := str(worker_id) if worker_id != null else ""
	if not text.begins_with(CITIZEN_PREFIX):
		return -1
	return int(text.substr(CITIZEN_PREFIX.length()))


# Первый горожанин, которого можно поставить на работу; порядок списка сохраняется, как в hire_worker() Python.
static func hire_candidate(citizens: Variant) -> Dictionary:
	if not citizens is Array:
		return {}
	for row in citizens:
		if not row is Dictionary:
			continue
		var citizen: Dictionary = row
		if _truthy(citizen.get("job_building")) or citizen.get("satisfaction") != SATISFIED:
			continue
		if citizen.get("work_status", CITIZEN_FREE) != CITIZEN_FREE:
			continue
		if _truthy(citizen.get("working")) or _truthy(citizen.get("travel_direction")):
			continue
		return citizen
	return {}


# Текст подтверждения, как _draw_worker_confirmation в Python.
static func confirm_prompt(action: String, state: Dictionary) -> String:
	if action == ACTION_HIRE:
		return "Поставить горожанина на работу?"
	if action == ACTION_FIRE:
		return "Снять горожанина с работы?"
	if action == ACTION_PLAYER:
		return "Остановить вашу добычу?" if _truthy(state.get("player_work")) else "Встать на добычу вместо горожанина?"
	return ""


# Ключ строки статуса, как status() в Python: улучшение, полный склад, работа или нет рабочих.
static func status_key(state: Dictionary) -> String:
	if bool(_dict(state.get("upgrade", {})).get("in_progress", false)):
		return "upgrade"
	if storage_is_full(state):
		return "full"
	if int(state.get("workers", 0)) > 0:
		return "working"
	return "idle"


# Производство в час по ресурсам, как production_per_hour() в Python: только занятые места, не в пути.
static func production_per_hour(state: Dictionary) -> Dictionary:
	var rates := {}
	for slot in slots_of(state):
		if not slot is Dictionary:
			continue
		var timers := _dict(slot.get("timer_sec_by_resource", {}))
		for resource in _resources_of(slot):
			var timer := float(timers.get(resource, 0.0))
			if timer <= 0.0:
				continue
			rates[resource] = float(rates.get(resource, 0.0))
			if bool(slot.get("occupied", false)) and not bool(slot.get("is_travelling", false)):
				rates[resource] += 3600.0 / timer
	return rates


# Часы:минуты:секунды, как в Python для времени в пути и таймеров добычи.
static func clock_text(seconds: int) -> String:
	var total := maxi(0, seconds)
	var hours := total / 3600
	var minutes := (total % 3600) / 60
	var rest := total % 60
	if hours > 0:
		return "%d:%02d:%02d" % [hours, minutes, rest]
	return "%d:%02d" % [minutes, rest]


static func hired_text(citizen_name: String) -> String:
	return MSG_HIRED % citizen_name


static func _resources_of(slot: Dictionary) -> Array[String]:
	var names: Array[String] = []
	var listed: Variant = slot.get("resources")
	if not listed is Array:
		listed = [slot.get("resource")]
	for value in listed:
		var code := str(value) if value != null else ""
		if not code.is_empty():
			names.append(code)
	return names


# Python-подобная истинность: null, пустые словари и списки, нули и пустые строки дают ложь.
static func _truthy(value: Variant) -> bool:
	if value == null:
		return false
	if value is bool:
		return value
	if value is int or value is float:
		return value != 0
	if value is String or value is StringName:
		return not str(value).is_empty()
	if value is Dictionary or value is Array:
		return not value.is_empty()
	return true


static func _dict(value: Variant) -> Dictionary:
	return value if value is Dictionary else {}


# ---------- стадия, таймеры, участки и текст следующего уровня (ui/production_building_window.py) ----------

# Индекс стадии 0..3 для текстуры участка: сервер считает стадию по заполнению склада.
static func stage_index(state: Dictionary) -> int:
	return clampi(int(state.get("stage", 0)), 0, REF.PLOT_STAGE_COUNT - 1)


# Файл текстуры участка, как _texture в Python: field_<ресурс>_stage_<стадия+1>.png.
static func texture_file(resource: String, stage: int) -> String:
	return "field_%s_stage_%d.png" % [resource, stage + 1]


static func has_plot_view(building: String) -> bool:
	return REF.BUILDINGS.has(building)


static func label_lower(resource: String) -> String:
	return str(REF.RESOURCE_LABELS.get(resource, resource)).to_lower()


# Цикл ресурса в месте: из слота (с бонусом сервера), иначе базовый из справочника.
static func resource_timer(slot: Dictionary, resource: String) -> float:
	var timers := _dict(slot.get("timer_sec_by_resource", {}))
	if timers.has(resource):
		return _float_of(timers[resource])
	return float(REF.RESOURCE_TIMERS.get(resource, 0))


static func resource_progress(slot: Dictionary, resource: String) -> float:
	var progress := _dict(slot.get("resource_progress_sec", {}))
	return _float_of(progress.get(resource, slot.get("progress_sec", 0)))


# Таймеры занятого места вне пути: по каждому ресурсу с циклом; самоцветы пропускаются, как в Python.
static func timer_entries(slot: Dictionary) -> Array:
	var entries: Array = []
	if not bool(slot.get("occupied", false)) or bool(slot.get("is_travelling", false)):
		return entries
	for resource in _resources_of(slot):
		if REF.RESOURCE_TIMERS.has(resource):
			entries.append({
				"resource": resource,
				"timer": resource_timer(slot, resource),
				"progress": resource_progress(slot, resource),
			})
	return entries


# Секунды до следующей единицы: max(0, ceil(timer - (progress + elapsed) % timer)), как в draw_worker_stats Python.
static func seconds_left(timer: float, progress: float, elapsed: float) -> int:
	if timer <= 0.0:
		return 0
	return maxi(0, int(ceil(timer - fposmod(progress + elapsed, timer))))


static func count_occupied(slots: Array) -> int:
	var count := 0
	for slot in slots:
		if bool(slot.get("occupied", false)):
			count += 1
	return count


# Группы участков как _build_groups в Python: у разлома и загона один участок на вид, места складываются.
static func plot_groups(building: String) -> Array:
	var group_by_kind := bool(_dict(REF.BUILDINGS.get(building, {})).get("group_by_kind", false))
	var groups: Array = []
	var by_kind := {}
	var first_slot := 0
	for plot in _plots_of(building):
		var resources := _resources_of_plot(plot[2])
		var kind := str(plot[3])
		var group: Dictionary = by_kind.get(kind, {}) if group_by_kind else {}
		if group.is_empty():
			group = {"level": int(plot[0]), "resource": resources[0], "resources": resources, "kind": kind, "slots": [], "places": 0}
			groups.append(group)
			by_kind[kind] = group
		var places := int(plot[1])
		for slot_index in range(first_slot, first_slot + places):
			group["slots"].append(slot_index)
		group["places"] = int(group["places"]) + places
		first_slot += places
	return groups


static func plot_name(building: String, group: Dictionary) -> String:
	var view := _dict(REF.BUILDINGS.get(building, {}))
	var by_kind := bool(view.get("group_by_kind", false))
	var key := str(group["kind"]) if by_kind else "%s/%s" % [group["resource"], group["kind"]]
	var title := str(_dict(view.get("plot_names", {})).get(key, ""))
	if by_kind:
		return title
	return "%s (%s)" % [title, label_lower(str(group["resource"]))]


# Места участка из состояния сервера (включая бонусные и дополнительные) или null, пока участок закрыт.
static func plot_slots(state: Dictionary, building: String, index: int) -> Variant:
	var groups := plot_groups(building)
	if index < 0 or index >= groups.size():
		return null
	var by_index := {}
	for slot in slots_of(state):
		if slot is Dictionary:
			by_index[int(slot.get("slot_index", -1))] = slot
	var slots: Array = []
	for slot_index in groups[index]["slots"]:
		_append_slot(slots, by_index, int(slot_index))
	if building == "farm":
		var upgrades := _dict(state.get("farm_upgrades", {}))
		if _int_list(upgrades.get("ration_plots", [])).has(index):
			_append_slot(slots, by_index, REF.BONUS_SLOT_BASE + index)
		var extra := int(_float_of(_dict(upgrades.get("extra_places", {})).get(str(index), 0)))
		for place_number in range(1, extra + 1):
			_append_slot(slots, by_index, REF.FARM_EXTRA_SLOT_BASE + index * REF.FARM_EXTRA_SLOT_STRIDE + place_number)
	elif building == "lumber_camp":
		if _int_list(_dict(state.get("lumber_camp_upgrades", {})).get("bonus_plots", [])).has(index):
			_append_slot(slots, by_index, REF.BONUS_SLOT_BASE + index)
	return slots if not slots.is_empty() else null


# Левый клик по участку, как click_plot в Python: закрытый участок — сообщение, свободное место — найм.
static func plot_click(state: Dictionary, building: String, index: int) -> Dictionary:
	var groups := plot_groups(building)
	if index < 0 or index >= groups.size():
		return {}
	var slots: Variant = plot_slots(state, building, index)
	if not slots is Array:
		var group: Dictionary = groups[index]
		return {"message": "%s откроется на %d уровне" % [plot_name(building, group), int(group["level"])]}
	for slot in slots:
		if not bool(slot.get("occupied", false)):
			return {"action": ACTION_HIRE, "slot_index": int(slot.get("slot_index", 0))}
	return {"message": MSG_PLOT_FULL}


# Правый клик, как remove_plot_worker в Python: снимается последний горожанин, игрок сам себя не снимает.
static func plot_remove(state: Dictionary, building: String, index: int) -> Dictionary:
	var slots: Variant = plot_slots(state, building, index)
	if not slots is Array:
		return {}
	for i in range(slots.size() - 1, -1, -1):
		var slot: Dictionary = slots[i]
		if bool(slot.get("occupied", false)) and not bool(slot.get("is_player", false)):
			return {"action": ACTION_FIRE, "slot_index": int(slot.get("slot_index", 0))}
	return {"message": MSG_PLOT_EMPTY}


# Подсказка при наведении, как tooltip в _draw_plots, _draw_digs, _draw_pen и _draw_rift в Python.
static func plot_hint(state: Dictionary, building: String, index: int, character_id: int) -> String:
	var groups := plot_groups(building)
	if index < 0 or index >= groups.size():
		return ""
	var group: Dictionary = groups[index]
	var shape := _shape_of(building)
	var title := plot_name(building, group)
	var level := int(group["level"])
	var group_places := int(group["places"])
	var slots: Variant = plot_slots(state, building, index)
	if not slots is Array:
		if shape == "rift":
			return "%s, мест до %d. Откроется на %d уровне" % [title, group_places, level]
		return "%s, мест: %d. Откроется на %d уровне" % [title, group_places, level]
	var workers := count_occupied(slots)
	if shape == "digs":
		var digs_action := "снять" if workers == group_places else "отправить"
		return "%s: горняков %d / %d. Клик — %s горожанина" % [title, workers, group_places, digs_action]
	var places: int = slots.size()
	var action := "снять" if workers == places else "отправить"
	var more := " (до %d с улучшениями)" % group_places if places < group_places else ""
	if shape == "pen":
		return "Загон: горожан %d / %d%s. Клик — %s горожанина" % [workers, places, more, action]
	if shape == "rift":
		return "%s: горожан %d / %d%s. Клик — %s горожанина" % [title, workers, places, more, action]
	var player_id := player_worker_id(character_id)
	var player_working := false
	var npc_available := false
	for slot in slots:
		if str(slot.get("worker_id", "")) == player_id:
			player_working = true
		if bool(slot.get("occupied", false)) and not bool(slot.get("is_player", false)):
			npc_available = true
	var verb := "остановить вашу добычу" if player_working else ("заменить горожанина собой" if npc_available else "встать на добычу")
	return "%s: работников %d / %d. Клик — %s" % [title, workers, places, verb]


# Надпись закрытого участка, как в Python: ресурс или название прииска и уровень открытия.
static func plot_lock_caption(building: String, index: int) -> String:
	var groups := plot_groups(building)
	if index < 0 or index >= groups.size():
		return ""
	var group: Dictionary = groups[index]
	var level := int(group["level"])
	match _shape_of(building):
		"digs":
			return "Копанка · ур. %d" % level
		"rift":
			return "%s · ур. %d" % [plot_name(building, group), level]
	return "%s · ур. %d" % [str(REF.RESOURCE_LABELS.get(group["resource"], group["resource"])), level]


# Склад и горожане уровня, как building_level_info в Python: у фермы на 1 горожанина больше со 2 уровня.
static func level_info(building: String, level: int) -> Dictionary:
	var table: Dictionary = REF.BLACK_PIT_LEVELS if building == "black_pit" else REF.BUILDING_LEVELS
	var info := _dict(table.get(level, table[1])).duplicate()
	if building == "farm" and level >= REF.FARM_EXTRA_WORKERS_LEVEL:
		info["max_workers"] = int(info["max_workers"]) + 1
	return info


# Ресурсы здания в порядке первого появления на участках, затем самоцветы бонуса, как building_resources в Python.
static func building_resources(building: String) -> Array:
	var names: Array = []
	for plot in _plots_of(building):
		for resource in _resources_of_plot(plot[2]):
			if not names.has(resource):
				names.append(resource)
	var weights := _dict(_dict(REF.BONUSES.get(building, {})).get("weights", {}))
	var levels := weights.keys()
	levels.sort()
	for level in levels:
		for gem in _dict(weights[level]):
			if not names.has(gem):
				names.append(gem)
	return names


# Текст следующего уровня, как production_desc в Python: циклы ресурсов, бонус, склад и горожане.
static func production_desc(building: String, level: int) -> String:
	var info := level_info(building, level)
	var per_unit := PackedStringArray()
	for resource in building_resources(building):
		if REF.RESOURCE_TIMERS.has(resource):
			per_unit.append("%s 1 ед. за %d с" % [label_lower(resource), int(REF.RESOURCE_TIMERS[resource])])
	var text := ", ".join(per_unit)
	var bonus := _dict(REF.BONUSES.get(building, {}))
	var chance := _float_of(_dict(bonus.get("unit_bonus_chance", {})).get(level, 0.0))
	if chance > 0.0:
		var weights := _dict(_dict(bonus.get("weights", {})).get(level, {}))
		var gems := PackedStringArray()
		for gem in weights:
			gems.append("%s %d%%" % [label_lower(str(gem)), int(weights[gem])])
		text += ". Бонусный самоцвет: шанс %s%% на каждую добытую единицу угля (%s; каждый 1 кг)" % [
			_format_general(chance * 100.0), ", ".join(gems),
		]
	return "Горожанин: %s. Вместимость каждого товара: %d. Горожан: %d." % [
		text if not text.is_empty() else "ресурсы не добываются",
		int(info["storage"]),
		int(info["max_workers"]),
	]


static func _plots_of(building: String) -> Array:
	return _array_of(_dict(REF.BUILDINGS.get(building, {})).get("plots", []))


static func _shape_of(building: String) -> String:
	return str(_dict(REF.BUILDINGS.get(building, {})).get("shape", ""))


static func _resources_of_plot(value: Variant) -> Array:
	if value is Array:
		return value.duplicate()
	return [str(value)]


static func _append_slot(slots: Array, by_index: Dictionary, slot_index: int) -> void:
	if by_index.has(slot_index):
		slots.append(by_index[slot_index])


static func _int_list(value: Variant) -> Array:
	var numbers: Array = []
	if value is Array:
		for item in value:
			if item is int or item is float:
				numbers.append(int(item))
	return numbers


static func _float_of(value: Variant) -> float:
	return float(value) if value is int or value is float else 0.0


static func _array_of(value: Variant) -> Array:
	return value if value is Array else []


# Формат Python ":g" для шанса бонуса: до шести знаков после запятой, лишние нули убираются.
static func _format_general(value: float) -> String:
	var text := "%.6f" % value
	if text.contains("."):
		text = text.rstrip("0").rstrip(".")
	return text
