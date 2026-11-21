extends RefCounted

# Порт deck/ui/card_tooltip.py: строки подсказки карты и выбор описания.
# Тексты повторяют Python-клиент; _fmt подставляет значения как f-строки Python.

const CURSOR_OFFSET := 16.0
const EDGE_MARGIN := 6.0
const BLEED_TURNS := 2
const DECK_CURRENCY := preload("res://scripts/deck_currency.gd")
const PHYSICAL_RESOURCES := ["rage", "accuracy", "concentration"]
const RESOURCE_NAMES := {
	"mana": "маны",
	"rage": "ярости",
	"accuracy": "меткости",
	"concentration": "концентрации",
	"unique": "уникального ресурса",
}
const PHYSICAL_NAMES := {
	"rage": "ярости",
	"accuracy": "меткости",
	"concentration": "концентрации",
}
const RARITY_LABELS := {
	"basic": "Базовая",
	"common": "Обычная",
	"rare": "Редкая",
	"epic": "Эпическая",
	"legendary": "Легендарная",
}
const SALE_PRICE_COINS := {"basic": 0, "common": 15, "rare": 50, "epic": 150, "legendary": 700}

const UNIVERSAL_DESCRIPTIONS := {
	"universal_trap": "Размещает скрытую ловушку. Она срабатывает только когда на неё наступает противник, и наносит 19 урона без критического удара.",
	"universal_barricade": "Создаёт препятствие размером в 3 гекса на 8 ходов. Сквозь него нельзя перемещаться и применять карты.",
	"universal_dash": "Перемещает персонажа на 3 гекса.",
	"universal_wolf": "Призывает волка с характеристиками волка Древнего энта.",
	"universal_roots_trap": "Размещает ловушку. Наступивший на неё противник получает 8 урона и корни на 2 хода.",
	"universal_resource_recovery": "Восстанавливает 15% уникального ресурса. Следующий полученный урон увеличивается на 25%.",
	"universal_knockback": "Наносит 12 урона без критического удара и отбрасывает цель на 3 гекса.",
	"universal_bonebreaker": "Накладывает на цель сломанные кости на 2 хода. За каждое перемещение цель теряет 4% максимального здоровья.",
	"universal_divine_healing": "Восстанавливает выбранному союзнику 10 HP в начале каждого хода в течение 7 ходов (всего до 70 HP).",
	"universal_dreadful_corruption": "Накладывает на врагов в радиусе 2 гексов: 4 огня, 4 яда, зелёный огонь, слабость (-20% исходящего урона), хрупкость (+20% входящего урона), потерю 10% уникального ресурса и оглушение.",
	"universal_unstable_elixir": "Трижды разыгрывает случайный положительный эффект и трижды случайный отрицательный: лечение/урон 10 HP (30%), случайное перемещение на 2 гекса (30%), щит 12 HP/защита -30% на 2 хода (15%), ресурс +/-10% (10%), регенерация 20 HP/коррозия 15 HP за 4 хода (5%). Эффекты могут повторяться; каждый бросок также может ничего не дать.",
	"universal_evolution": "Выберите союзника или призыв: максимальное HP увеличивается на 35 (призыву — на 20), затем он восстанавливает 5 HP в начале хода в течение 3 ходов.",
	"universal_teleport": "Телепортирует владельца на выбранный свободный гекс. Стоимость — 3 маны за каждый пройденный гекс.",
}

const NECROMANCER_DESCRIPTIONS := {
	"necromancer_familiar": "Призывает фамильяра: 8 HP, 2 маны, перемещение 2 гекса. Усиливает урон союзников в радиусе 2 гексов на 20% и держится рядом с союзником. При смерти накладывает на убийцу 1% зелёного огня.",
	"necromancer_lokrif": "Призывает локрифа: 17 HP, 4 маны, перемещение 3 гекса. Первый входящий урон снижен на 65%. Атака: 8 урона и 2 яда; при HP призывателя не выше 25% локриф лечит его или даёт защиту.",
	"necromancer_bone_hero": "Призывает костяного героя: 45 HP, 20 маны, перемещение 3 гекса. Атакует на 10 урона, может нанести 7 урона и восстановить 5 HP, совершить рывок с уроном по области или пожертвовать собой ради лечения и защиты призывателя.",
	"necromancer_spirit": "Призывает духа: 10 HP, 10 маны, перемещение 3 гекса. Получает на 50% меньше урона от физических атак. Оглушает на 1 ход (перезарядка 4 хода), отбрасывает цель (перезарядка 2 хода) или берёт карту призывателю.",
	"necromancer_lyrk": "Призывает лирка: 15 HP, 10 маны, перемещение 2 гекса, 20% уклонения. Может нанести 3 урона и наложить зелёный огонь, нанести 6 урона с ядом или наложить корни.",
	"necromancer_grave_zink": "Призывает могильного зинка: 30 HP, 5 маны, перемещение 3 гекса. Наносит 12 урона, выжигает 15 маны (если маны нет — дополнительно 8 урона) или восстанавливает себе 10 HP при HP не выше 10.",
	"necromancer_transfer": "Перемещает выбранного союзника, кроме себя, на расстояние до 3 гексов. Дальность выбора цели — 2 гекса.",
	"necromancer_slow_trap": "Ставит ловушку: противник при наступании получает 15 урона и замедляется на 2 хода, теряя 1 гекс перемещения.",
	"necromancer_knockback_trap": "Ставит ловушку: противник при наступании получает 10 урона и отбрасывается на 4 гекса.",
	"necromancer_dead_god_blessing": "Лечит все призванные союзные существа в радиусе 2 гексов от владельца на 35% их максимального HP.",
	"necromancer_in_the_name": "Уничтожает выбранное союзное призванное существо. Восстанавливает владельцу 20% максимального HP и 10% максимального некротизма, вытягивает карту и возвращает 35% стоимости призыва.",
	"necromancer_familiar_search": "Находит карту призыва в колоде и усиливает следующее призванное существо: +20% HP, +10% урона и 10% защиты.",
	"necromancer_necrotic_charge": "Наносит цели 10 урона.",
	"necromancer_fragility_curse": "На 3 хода снижает защиту цели на 30%.",
	"necromancer_gravestones": "Создаёт линию из 3 препятствий на 6 ходов.",
	"necromancer_screamer": "Наносит 5 урона и оглушает цель и существ в радиусе 1 гекса на 1 ход.",
	"necromancer_grave_soil": "Создаёт область могильной почвы на 3 гексах на 15 ходов: нежить восстанавливает 3 HP, остальные существа замедляются.",
	"necromancer_dead_god_sacrifice": "Тратит 25% максимального HP владельца и восстанавливает 25% максимального некротизма.",
	"necromancer_dead_god_curse": "Накладывает на цель вечный зелёный огонь: в начале её хода он наносит 2% текущего HP и не вступает в реакции.",
	"necromancer_dead_grip": "Наносит 5 урона и накладывает корни на 2 хода.",
	"necromancer_dead_god_bargain": "Накладывает на владельца зелёный огонь и увеличивает получаемый некротизм на 20% до конца боя.",
	"necromancer_bone_dragon": "Призывает костяного дракона: 80 HP, 40 маны, перемещение 3 гекса. Наносит 20 урона, атакует зелёным пламенем по области и оглушает существ вокруг себя; при критически низком HP лечит себя.",
}

const PHYSICAL_LABELS := [
	["bleed_healing_percent", "Лечит {}% урона от ваших кровотечений"],
	["bleed_increase", "Ваши кровотечения +{}%"],
	["extra_hits", "+{} удар у многоударных карт"],
	["regen_percent", "Лечит {}% HP за каждый удар"],
	["missing_hp_damage", "+{} урона за каждые 10% потерянного HP"],
	["damage_buff_percent", "+{}% урона"],
	["dodge_percent", "+{}% уворота"],
	["stun_after_hits", "Оглушает врага после {} ударов"],
	["steal_healing_percent", "Враг отдаёт вам {}% своего лечения"],
	["mana_regen_debuff", "Восстановление маны врага -{}%"],
	["crit_chance_percent", "+{}% шанса крита"],
	["crit_damage_percent", "+{}% крит. урона"],
]


static func tooltip_lines(card: Dictionary) -> PackedStringArray:
	var key := str(card.get("key", ""))
	var resource_type := str(card.get("resource_type", ""))
	var description := ""
	if UNIVERSAL_DESCRIPTIONS.has(key):
		description = UNIVERSAL_DESCRIPTIONS[key]
	elif NECROMANCER_DESCRIPTIONS.has(key):
		description = NECROMANCER_DESCRIPTIONS[key]
	elif PHYSICAL_RESOURCES.has(resource_type):
		description = describe_physical_card(card)
	else:
		description = card_description(card)
	var lines := PackedStringArray([description])
	if _effect_data(card).get("range") != null:
		lines.append(_fmt("Дальность: {} гекс.", [_effect_data(card)["range"]]))
	var resource := str(RESOURCE_NAMES.get(resource_type, resource_type))
	if str(card.get("group_name", "")).begins_with("Некромант:"):
		resource = "некротизма"
	lines.append(_fmt("Стоимость розыгрыша: {} {}.", [card.get("resource_cost", 0), resource]))
	var rarity := str(card.get("rarity", "unassigned"))
	if RARITY_LABELS.has(rarity):
		lines.append(_fmt("Редкость: {}. Цена продажи: {}.", [
			RARITY_LABELS[rarity],
			format_coins(int(SALE_PRICE_COINS[rarity])),
		]))
	return lines


static func describe_physical_card(card: Dictionary) -> String:
	var data := _effect_data(card)
	var effect_type := str(card.get("effect_type", ""))
	var effect_duration: Variant = card.get("effect_duration", 0)
	var parts := PackedStringArray()
	if _truthy(data.get("dice")):
		var hits := _int(data.get("hits", 1))
		var extra := _fmt(", {} удара", [hits]) if hits > 1 else ""
		parts.append(_fmt("Урон {} + Сила", [_max_dice_damage(data["dice"])]) + extra + ".")
	if _truthy(data.get("poison_damage_multiplier")):
		var damage := _py_str(data["poison_damage_multiplier"])
		if _truthy(data.get("poison_strength_per_stack")):
			damage += " + Сила"
		parts.append(_fmt("Урон {} за каждый яд на цели.", [damage]))
	if _truthy(data.get("bleed_percent")):
		parts.append(_fmt("Кровотечение {}% макс. HP цели за {} хода.", [
			data["bleed_percent"],
			_int(_or(data.get("duration"), BLEED_TURNS)),
		]))
	if _truthy(data.get("poison")):
		var poison_limit := 5 + _int(data.get("poison_cap_bonus", 0))
		parts.append(_fmt("Яд x{}: 2% максимального HP за ход, максимум {} стаков; в конце хода снимается 1 стак. Холод приостанавливает урон и спад стаков.", [
			data["poison"],
			poison_limit,
		]))
	if _truthy(data.get("burn_mana")) or _truthy(data.get("burn_mana_percent")):
		var amount: Variant = data.get("burn_mana", 0)
		var percent: Variant = data.get("burn_mana_percent", 0)
		var pieces := PackedStringArray()
		if _truthy(amount):
			pieces.append(_py_str(amount))
		if _truthy(percent):
			pieces.append(_fmt("{}% текущей", [percent]))
		parts.append(_fmt("Выжигает {} маны врага.", [" + ".join(pieces)]))
	if _truthy(data.get("burn_damage_percent")):
		parts.append(_fmt("Если у врага 0 маны: +{}% его текущего HP урона.", [data["burn_damage_percent"]]))
	if _truthy(data.get("crit_on_no_mana")):
		parts.append(_fmt("Если у врага 0 маны: +{}% крит. урона.", [data["crit_on_no_mana"]]))
	if _truthy(data.get("heal_percent")):
		parts.append(_fmt("Лечит {}% недостающего HP.", [data["heal_percent"]]))
	if _truthy(data.get("hp_percent")):
		parts.append(_fmt("Стоит {}% вашего HP.", [data["hp_percent"]]))
	if _truthy(data.get("hp_current_percent")):
		parts.append(_fmt("Тратит {}% текущего HP.", [data["hp_current_percent"]]))
	if _truthy(data.get("heal_max_hp_percent")):
		parts.append(_fmt("Лечит {}% максимального HP.", [data["heal_max_hp_percent"]]))
	if _truthy(data.get("delayed_heal_percent")):
		parts.append(_fmt("Через {} хода лечит {}% максимального HP.", [
			data.get("delay_turns", 1),
			data["delayed_heal_percent"],
		]))
	if _truthy(data.get("heal_per_turn")):
		parts.append(_fmt("Лечит {} HP + Выносливость каждый ход {} хода.", [
			data["heal_per_turn"],
			data.get("duration", _or(effect_duration, 1)),
		]))
	if _truthy(data.get("outgoing_damage_flat")):
		parts.append(_fmt("Урон врага снижается на {} на его следующий ход.", [data["outgoing_damage_flat"]]))
	if _truthy(data.get("incoming_damage_percent")):
		parts.append(_fmt("Получаемый урон снижен на {}%.", [data["incoming_damage_percent"]]))
	if _truthy(data.get("invulnerable")):
		parts.append("Неуязвимость до завершения следующего хода соперника.")
	if _truthy(data.get("skip_next_turn")):
		parts.append("Следующий свой ход пропускается.")
	if _truthy(data.get("team_only")):
		parts.append("Только для командного боя.")
	if _truthy(data.get("hit_bonus")) and _truthy(data.get("dice")):
		parts.append(_fmt("+{}% к попаданию.", [data["hit_bonus"]]))
	if _truthy(data.get("no_miss")):
		parts.append("Нельзя увернуться.")
	if _truthy(data.get("stun_on_dodge")):
		parts.append("Если враг увернулся — он оглушён на 1 ход.")
	for label in PHYSICAL_LABELS:
		if _truthy(data.get(label[0])):
			parts.append(_fmt(label[1], [data[label[0]]]) + ".")
	if _truthy(data.get("mark_damage")):
		parts.append(_fmt("Метка: +{} урона по цели (+1 за 4 Силы) на 2 хода.", [data["mark_damage"]]))
	if _truthy(data.get("dodge_damage_bonus")):
		if _truthy(data.get("dodge_stacks")):
			parts.append(_fmt("После уворота следующая атака +{}% (до {} раз).", [
				data["dodge_damage_bonus"],
				data["dodge_stacks"],
			]))
		else:
			parts.append("При вашем увороте атакующий оглушён.")
	if _truthy(data.get("crit_chance_guarantee")):
		parts.append(_fmt("Следующий удар — крит, затем {} атаки без крита.", [data.get("next_hits_no_crit", 0)]))
	if _truthy(data.get("poison_extraction")):
		parts.append(_fmt("Снимает все яды с врага: +{}% крита и +{}% крит. урона за каждый на {} хода.", [
			data.get("extraction_crit_chance_per_stack", 2),
			data.get("extraction_crit_damage_per_stack", 4),
			data.get("extraction_duration", 3),
		]))
	if _truthy(data.get("full_heal")):
		parts.append("Полностью лечит, позже вылеченное HP теряется (остаётся минимум 1).")
	if _truthy(data.get("summon_spirit")):
		parts.append(_fmt("Лесной дух (20 HP + Ловкость призывателя) живёт, пока его не убьют: +{}% уворота и +10% урона, пока он жив.", [
			data.get("spirit_dodge", 15),
		]))
	if _truthy(data.get("heal_flat")) or _truthy(data.get("heal_endurance")) or _truthy(data.get("heal_agility_multiplier")):
		var formula := PackedStringArray()
		if _truthy(data.get("heal_flat")):
			formula.append(_py_str(data.get("heal_flat", 0)))
		if _truthy(data.get("heal_endurance")):
			formula.append(_fmt("{} × Выносливость", [data["heal_endurance"]]))
		if _truthy(data.get("heal_agility_multiplier")):
			formula.append(_fmt("{} × Ловкость", [data["heal_agility_multiplier"]]))
		parts.append(_fmt("Лечит {} HP.", [" + ".join(formula)]))
	if _truthy(data.get("entangle")):
		parts.append(_fmt("Оплетение: цель может разыграть только 1 карту за ход, {} хода.", [data["entangle"]]))
	if _truthy(data.get("no_heal_turns")):
		parts.append(_fmt("Запрещает лечение на {} хода.", [data["no_heal_turns"]]))
	if _truthy(data.get("stun_if_poison_at_least")):
		parts.append(_fmt("Оглушает, если на цели минимум {} стаков яда.", [data["stun_if_poison_at_least"]]))
	if _truthy(data.get("forbid_damage_cards")):
		parts.append(_fmt("Противник не может разыгрывать атакующие карты {} хода.", [data["forbid_damage_cards"]]))
	if _truthy(data.get("poison_cap_bonus")):
		parts.append(_fmt("Повышает лимит яда на цели до {} на {} хода.", [
			5 + _int(data["poison_cap_bonus"]),
			data.get("poison_cap_duration", 3),
		]))
	if _truthy(data.get("poison_outgoing_damage_percent")):
		parts.append(_fmt("Снижает исходящий урон врага на {}% за каждый стак яда.", [data["poison_outgoing_damage_percent"]]))
	if _truthy(data.get("dispel_positive_effect")):
		parts.append("Снимает 1 положительный эффект с противника.")
	if _truthy(data.get("shield_flat")):
		parts.append(_fmt("Щит {} HP + {} × Ловкость.", [data["shield_flat"], data.get("shield_agility", 0)]))
	if _truthy(data.get("cleanse")):
		parts.append("Снимает с вас все отрицательные эффекты.")
	if _truthy(data.get("guaranteed_dodge")):
		parts.append("Гарантированно уклоняется от следующей атаки.")
	if _truthy(data.get("agility_bonus")):
		parts.append(_fmt("+{} Ловкости на {} хода.", [data["agility_bonus"], data.get("duration", 1)]))
	if _truthy(data.get("hit_chance_bonus")):
		parts.append(_fmt("+{}% к попаданию на {} хода.", [data["hit_chance_bonus"], data.get("buff_duration", 1)]))
	if _truthy(data.get("dodge_stun")):
		parts.append("При вашем уклонении атакующий оглушается на 1 ход.")
	var duration: Variant = _or(data.get("duration"), effect_duration)
	if _truthy(duration) and effect_type != "damage":
		parts.append(_fmt("Длительность: {} ход.", [duration]))
	if _truthy(data.get("ultimate")):
		parts.append("УЛЬТА.")
	parts.append(_fmt("Стоимость: {} {}.", [card.get("resource_cost", 0), PHYSICAL_NAMES.get(str(card.get("resource_type", "")), "")]))
	return " ".join(parts)


static func card_description(card: Dictionary) -> String:
	var data := _effect_data(card)
	var effect_type := str(card.get("effect_type", ""))
	var effect_duration: Variant = card.get("effect_duration", 0)
	if not str(card.get("group_name", "")).begins_with("Магия:"):
		return _generic_description(effect_type, data, effect_duration)
	var element: Variant = data.get("element", "магии")
	var description := _magic_description(effect_type, data, effect_duration, element)
	if description.is_empty():
		var parts := PackedStringArray([_fmt("Элемент: {}", [element])])
		if _truthy(data.get("damage")):
			parts.append(_fmt("Урон: {}", [data["damage"]]))
		if _truthy(data.get("duration")) or _truthy(effect_duration):
			parts.append(_fmt("Длительность: {} ход.", [data.get("duration", effect_duration)]))
		if _truthy(data.get("remove_statuses")):
			parts.append("Снимает статусы и зависящие от них бафы.")
		description = " ".join(parts)
		if description.is_empty():
			description = "Магический эффект."
	return _fmt("{} Мана: {}.", [description, data.get("mana_cost", 0)])


static func _magic_description(effect_type: String, data: Dictionary, effect_duration: Variant, element: Variant) -> String:
	match effect_type:
		"mage_damage_status":
			return _fmt("Наносит {} прямого урона + Мудрость и накладывает {} ур. статуса {} на {} ход.", [
				data.get("damage", 0),
				data.get("stacks", 1),
				data.get("status", "магии"),
				data.get("status_duration", _or(effect_duration, 1)),
			])
		"mage_damage":
			return _fmt("Наносит {} прямого урона + Мудрость.", [data.get("damage", 0)])
		"mage_area_damage":
			return _fmt("Всем врагам наносится {} урона.", [data.get("damage", 0)])
		"mage_area_damage_status":
			var text := _fmt("Всем врагам наносится {} урона и накладывается {} ур. статуса {}.", [
				data.get("damage", 0),
				data.get("stacks", 1),
				data.get("status", element),
			])
			if _truthy(data.get("delayed_stacks")):
				text += _fmt(" В начале следующего хода добавляется ещё {} ур.", [data["delayed_stacks"]])
			if _truthy(data.get("stun_duration")):
				text += _fmt(" Оглушает на {} ход.", [data["stun_duration"]])
			return text
		"mage_draw":
			return _fmt("Берёт {} карт(ы) в начале следующего хода.", [data.get("cards", 1)])
		"mage_damage_resistance":
			return _fmt("Снижает получаемый урон на {}% + {}% за каждое очко Интеллекта на {} хода.", [
				data.get("reduction_percent", 0),
				data.get("intellect_percent", 0),
				_or(effect_duration, 2),
			])
		"mage_damage_debuff":
			return _fmt("Снижает исходящий урон врага на {}% + {}% за каждое очко Интеллекта на {} хода.", [
				data.get("damage_percent", 0),
				data.get("intellect_percent", 0),
				_or(effect_duration, 2),
			])
		"mage_team_damage_buff", "mage_damage_buff":
			return _fmt("Даёт +{}% + {}% за каждое очко Интеллекта урона на {} хода.", [
				data.get("damage_percent", 0),
				data.get("intellect_percent", 0),
				_or(effect_duration, 2),
			])
		"mage_wind_gust":
			return _fmt("Наносит {} урона + Мудрость. Каждый снятый ход статуса врага даёт {} + Мудрость урона.", [
				data.get("damage", 0),
				data.get("removed_damage", 0),
			])
		"mage_cleanse_area":
			return _fmt("Наносит {} урона + Мудрость. Снимает статусы врага; каждый снятый даёт {} + Мудрость урона.", [
				data.get("damage", 0),
				data.get("removed_damage", 0),
			])
		"mage_dispel":
			return _fmt("Снимает положительные эффекты врага; каждый снятый даёт {} + Мудрость урона.", [
				data.get("removed_damage", 0),
			])
		"mage_heal_missing_hp":
			return _fmt("Восстанавливает {}% недостающего HP + {} HP за Интеллект. Щит: {} + Интеллект на {} хода.", [
				data.get("missing_hp_percent", 0),
				data.get("intellect_hp", 0),
				data.get("shield_hp", 0),
				4 if _truthy(data.get("ultimate")) else 2,
			])
		"mage_restore_mana":
			return _fmt("Восстанавливает {}% недостающей маны + {}% за Гармонию. Только при мане до {}%.", [
				data.get("missing_mana_percent", 25),
				data.get("harmony_percent", 0),
				data.get("max_mana_percent", 30),
			])
		"mage_stun_status":
			return _fmt("Оглушает врага на {} ход и накладывает Электричество.", [data.get("stun_duration", 1)])
		"mage_golem":
			return _fmt("Призывает голема: {} HP + Мудрость, атака {} + Мудрость.", [
				data.get("hp", 16),
				data.get("damage", 2),
			])
		"mage_cloud":
			return _fmt("Туча появляется на {} хода (+1 ход за каждые {} Гармонии), не наносит урона и даёт статус Электричество на 1 ход.", [
				data.get("duration", 2),
				data.get("harmony_duration", 6),
			])
		"mage_team_health_buff":
			return _fmt("Всем союзникам даёт +{} HP + Мудрость на щит.", [data.get("bonus_hp", 0)])
		"mage_mana_regen_buff":
			return _fmt("Тратит {}% макс. HP. Накладывает Холод на {} хода и даёт +{} восстановления маны на {} хода.", [
				data.get("hp_percent", 10),
				data.get("status_duration", 4),
				data.get("mana_regen_bonus", 0),
				_or(effect_duration, 4),
			])
	return ""


static func _generic_description(effect_type: String, data: Dictionary, effect_duration: Variant) -> String:
	var dice: Variant = data.get("dice", "")
	var damage_text := _fmt("Наносит {} урона.", [dice])
	var duration := maxi(1, _int(effect_duration))
	var exchange_word := "разменов"
	if duration % 10 == 1 and duration % 100 != 11:
		exchange_word = "размен"
	elif duration % 10 in [2, 3, 4] and not (duration % 100 in [12, 13, 14]):
		exchange_word = "размена"
	var duration_text := _fmt("на {} {}", [duration, exchange_word])
	match effect_type:
		"damage":
			return damage_text
		"damage_critical_debuff":
			return _fmt("{} При попадании снижает шанс критического удара противника на {}% {}.", [
				damage_text,
				data.get("amount", 0),
				duration_text,
			])
		"damage_dodge_debuff":
			return _fmt("{} При попадании снижает шанс уворота противника на {}% {}.", [
				damage_text,
				data.get("amount", 0),
				duration_text,
			])
		"damage_dodge_critical_debuff":
			return _fmt("{} При попадании снижает шанс уворота противника на {}% и шанс критического удара противника на {}% {}.", [
				damage_text,
				data.get("dodge_amount", 0),
				data.get("critical_amount", 0),
				duration_text,
			])
		"multi_damage":
			return _fmt("Наносит {} отдельных удара по броску {}.", [data.get("hits", 2), dice])
		"damage_recoil":
			return _fmt("Наносит урон по броску {}. При некритическом ударе вы получаете {} урона.", [
				dice,
				data.get("recoil", 0),
			])
		"damage_reduce":
			return _fmt("{} Следующая атака по вам наносит на {} урона меньше.", [damage_text, data.get("reduce", 0)])
		"heal":
			return _fmt("Восстанавливает здоровье по броску {}.", [dice])
		"dodge":
			return _fmt("Увеличивает уклонение на {}%.", [data.get("bonus", 0)])
		"anti_dodge":
			return _fmt("Снижает уклонение противника на {}%.", [data.get("bonus", 0)])
		"damage_dodge":
			return _fmt("Наносит {} урона и увеличивает уклонение на {}%.", [dice, data.get("bonus", 0)])
		"critical":
			return _fmt("Увеличивает шанс критического удара на {}%.", [data.get("bonus", 0)])
	return "Особое действие карты."


static func rarity_label(rarity: String) -> String:
	return str(RARITY_LABELS.get(rarity, "—"))


static func format_coins(amount: int) -> String:
	return DECK_CURRENCY.format_coins(amount)


static func tooltip_position(mouse: Vector2, tooltip_size: Vector2, screen_size: Vector2) -> Vector2:
	var x := mouse.x + CURSOR_OFFSET
	var y := mouse.y + CURSOR_OFFSET
	if x + tooltip_size.x > screen_size.x - EDGE_MARGIN:
		x = mouse.x - tooltip_size.x - CURSOR_OFFSET
	if y + tooltip_size.y > screen_size.y - EDGE_MARGIN:
		y = screen_size.y - tooltip_size.y - EDGE_MARGIN
	return Vector2(maxf(EDGE_MARGIN, x), maxf(EDGE_MARGIN, y))


static func _effect_data(card: Dictionary) -> Dictionary:
	var data: Variant = card.get("effect_data", {})
	return data if data is Dictionary else {}


static func _max_dice_damage(expression: Variant) -> int:
	if expression is int or expression is float:
		return int(expression)
	var found := RegEx.create_from_string("^(\\d+)d(\\d+)$").search(str(expression))
	if found == null:
		return 0
	return int(found.get_string(1)) * int(found.get_string(2))


static func _fmt(template: String, args: Array) -> String:
	var result := ""
	var rest := template
	for arg in args:
		var index := rest.find("{}")
		if index < 0:
			break
		result += rest.substr(0, index) + _py_str(arg)
		rest = rest.substr(index + 2)
	return result + rest


static func _py_str(value: Variant) -> String:
	if value == null:
		return "None"
	if value is bool:
		return "True" if value else "False"
	if value is float and value == floorf(value):
		return str(int(value))
	return str(value)


static func _truthy(value: Variant) -> bool:
	if value == null:
		return false
	if value is bool:
		return value
	if value is int or value is float:
		return value != 0
	if value is String:
		return not value.is_empty()
	if value is Array or value is Dictionary or value is PackedStringArray:
		return not value.is_empty()
	return true


static func _or(value: Variant, fallback: Variant) -> Variant:
	return value if _truthy(value) else fallback


static func _int(value: Variant) -> int:
	if value == null:
		return 0
	return int(value)
