extends RefCounted

# Статусы и призывы боя Калоды: порт плашки под угловой карточкой, панели «ПРИЗЫВЫ» у сброса и полосы щита из
# deck/ui/duel_renderer.py (_draw_banner_effects, _banner_effect_description, _draw_summons_near_discard, щит в
# _draw_resource_bar). Сервер присылает статусы, щит и призывы (deck/server/battles.py, _presentation_fields):
# здесь только тексты, цвета, описания и геометрия. Статусы и призывы клиент не вычисляет.

const TOOLTIP_WIDTH := 270.0  # duel_renderer.py:_draw_status_tooltip (max_width)
const DESIGN_SIZE := Vector2(1920, 1080)  # core/settings.py:2-3
const SUMMON_WIDTH := 176.0  # duel_renderer.py:_draw_summons_near_discard
const SUMMON_TITLE_HEIGHT := 22.0
const SUMMON_ROW_HEIGHT := 40.0  # в Python 34; здесь больше, чтобы строка с деталями не наезжала на имя
const SUMMON_DETAILS_OFFSET := 19.0
const SUMMON_MORE_HEIGHT := 22.0  # строка «и ещё N» по высоте шрифта, иначе текст наезжает на рамку
const SUMMON_MAX_ROWS := 2
const SUMMON_TITLE := "ПРИЗЫВЫ"
const SUMMON_OWNERS := [["player", "Игрок"], ["enemy", "Противник"]]

const POSITIVE_COLOR := Color8(125, 225, 145)  # duel_renderer.py: (125, 225, 145)
const NEGATIVE_COLOR := Color8(245, 135, 125)  # duel_renderer.py: (245, 135, 125)
const MAGE_COLOR := Color8(220, 185, 245)  # duel_renderer.py: статусы мага и облако
const BLEED_COLOR := Color8(245, 125, 115)  # duel_renderer.py: кровотечение, оглушение, заморозка, пропуск
const POISON_COLOR := Color8(180, 220, 100)  # duel_renderer.py: яд
const INVULNERABLE_COLOR := Color8(125, 205, 245)  # duel_renderer.py: неуязвимость
const NEUTRAL_COLOR := Color8(220, 210, 150)  # duel_renderer.py: «Атаки без крита»
const SHIELD_COLOR := Color8(120, 205, 245)  # duel_renderer.py: «Щит +N HP»
const SHIELD_OVERLAY_COLOR := Color8(100, 205, 255, 125)  # duel_renderer.py: overlay.fill((100, 205, 255, 125))
const SUMMON_BACKGROUND := Color8(20, 24, 34)
const SUMMON_BORDER := Color8(150, 170, 125)
const SUMMON_TITLE_COLOR := Color8(190, 215, 150)
const SUMMON_NAME_COLOR := Color8(230, 230, 240)
const SUMMON_DETAILS_COLOR := Color8(125, 225, 145)
const SUMMON_MORE_COLOR := Color8(170, 175, 185)

# Подписи бафов и дебафов из duel_renderer.py (positive и negative). sign: true — «+N» (позитивный бафф),
# false — «N» (дебафф; булевы значения выводятся без числа).
const BUFF_LABELS := {
	"damage_percent": ["Урон", "%", true],
	"dodge_percent": ["Уворот", "%", true],
	"crit_chance": ["Шанс крита", "%", true],
	"crit_damage": ["Крит. урон", "%", true],
	"agility_bonus": ["Ловкость", "", true],
	"hit_bonus": ["Меткость", "%", true],
	"incoming_damage_percent": ["Сопротивление урону", "%", true],
	"extra_hits": ["Доп. удары", "", true],
	"regen_per_hit_percent": ["Лечение за удар", "%", true],
	"missing_hp_damage": ["Урон за потерю HP", "", true],
	"bleed_heal_percent": ["Лечение от кровотечения", "%", true],
	"crit_conversion": ["Конверсия крита", "", true],
	"accuracy_gain": ["Меткость за уклонение", "", true],
	"burn_bonus_max_percent": ["Сильное выжигание маны", "%", true],
	"burn_bonus_current_percent": ["Сильное выжигание маны", "%", true],
	"dodge_damage_bonus": ["Урон после уклонения", "%", true],
	"mana_regen_debuff": ["Восст. маны", "%", false],
	"steal_healing_percent": ["Кража лечения", "%", false],
	"outgoing_damage_flat": ["Исходящий урон", "", false],
	"outgoing_damage_percent": ["Исходящий урон", "%", false],
	"healing_blocked": ["Запрет лечения", "", false],
	"forbid_damage_cards": ["Запрет атакующих карт", "", false],
	"entangled": ["Оплетение", "", false],
	"mark_damage": ["Метка уязвимости", " урона", false],
	"poison_cap_bonus": ["Лимит яда увеличен", "", false],
	"dodge_stun": ["Оглушение при уклонении", "", false],
}
# Счётчики состояния (duel_renderer.py: «Гарантированный крит x2» и т. д.).
const COUNTER_LABELS := {
	"guaranteed_crits": "Гарантированный крит",
	"no_crit_attacks": "Атаки без крита",
	"guaranteed_dodges": "Гарантированное уклонение",
	"dodge_stacks": "Заряды после уклонения",
}
# Стихии мага и их подписи (Python выводит имя с заглавной буквы: «Огонь», «Blinding»).
const MAGE_LABELS := {
	"fire": "Огонь",
	"water": "Вода",
	"cold": "Холод",
	"electro": "Электро",
	"air": "Воздух",
	"blinding": "Blinding",
}
const COLOR_BY_ID := {
	"bleed": BLEED_COLOR,
	"delayed_hp_loss": BLEED_COLOR,
	"stun": BLEED_COLOR,
	"freeze": BLEED_COLOR,
	"skip_turn": BLEED_COLOR,
	"poison": POISON_COLOR,
	"invulnerable": INVULNERABLE_COLOR,
	"guaranteed_dodges": INVULNERABLE_COLOR,
	"no_crit_attacks": NEUTRAL_COLOR,
	"storm_cloud": MAGE_COLOR,
	"reactive_blessing": MAGE_COLOR,
}
# Описания из _banner_effect_description (живые в Python): текст статуса плюс это описание.
const BANNER_DESCRIPTIONS := {
	"mana_regen_debuff": "снижает восстановление маны на указанное значение.",
	"steal_healing_percent": "указанная доля лечения цели переходит наложившему эффект бойцу.",
	"outgoing_damage_flat": "уменьшает урон, который цель наносит своими атаками.",
	"outgoing_damage_percent": "уменьшает урон, который цель наносит своими атаками.",
	"dodge_stun": "когда носитель эффекта уклоняется, атакующий оглушается на 1 ход.",
	"incoming_damage_percent": "снижает входящий урон на указанное значение.",
	"missing_hp_damage": "усиливает атаки в зависимости от потерянного здоровья.",
	"bleed_heal_percent": "восстанавливает здоровье от урона, нанесённого кровотечением.",
	"healing_blocked": "цель не может восстанавливать HP, пока действует эффект.",
	"forbid_damage_cards": "цель не может разыгрывать карты, наносящие урон.",
	"entangled": "цель может разыграть не более одной карты за ход.",
	"mark_damage": "каждая атака по цели получает указанный дополнительный урон.",
	"stun": "оглушённая цель пропускает возможность разыграть карты.",
	"freeze": "замороженная цель может разыграть не более одной карты за ход.",
	"bleed": "цель теряет указанное количество HP каждый ход до окончания эффекта.",
	"delayed_heal": "цель восстановит здоровье по истечении указанного числа ходов.",
	"delayed_hp_loss": "указанное количество HP будет потеряно после окончания таймера.",
	"skip_turn": "цель пропустит свой следующий ход.",
}


# Строки статусов для плашки бойца: позитивные, затем строка щита (если есть), затем негативные.
# attacker_type — профессия второго бойца: от неё зависит текст яда (ассасин получает бонус к криту).
static func status_rows(fighter: Dictionary, attacker_type: String) -> Array:
	var positive: Array = []
	var negative: Array = []
	for status_variant in _array_of(fighter.get("statuses", [])):
		var status := _dict_of(status_variant)
		if status.is_empty():
			continue
		var row := _status_row(status, attacker_type)
		if bool(status.get("positive", false)):
			positive.append(row)
		else:
			negative.append(row)
	var shield := _int_of(fighter.get("shield", 0))
	if shield > 0:
		positive.append(shield_row(shield))
	return positive + negative


static func shield_row(shield: int) -> Dictionary:
	var text := "Щит +%d HP" % shield
	return {"id": "shield", "positive": true, "text": text, "color": SHIELD_COLOR, "description": "Активный эффект: %s." % text}


# Надпись на полосе HP при щите: «HP: 106/120 + ЩИТ 12» (duel_renderer.py:_draw_resource_bar).
static func shield_bar_suffix(shield: int) -> String:
	return " + ЩИТ %d" % shield if shield > 0 else ""


static func status_text(status: Dictionary) -> String:
	var id := str(status.get("id", ""))
	var turns_suffix := ""
	if _has(status, "turns"):
		turns_suffix = " (%d х.)" % _num(status, "turns")
	if BUFF_LABELS.has(id):
		var spec: Array = BUFF_LABELS[id]
		var label := str(spec[0])
		if not _has(status, "amount"):
			return label + turns_suffix
		var sign_text := "+" if bool(spec[2]) else ""
		return "%s %s%d%s%s" % [label, sign_text, _num(status, "amount"), str(spec[1]), turns_suffix]
	if COUNTER_LABELS.has(id):
		var counter := str(COUNTER_LABELS[id])
		return "%s x%d" % [counter, _num(status, "stacks")] if _has(status, "stacks") else counter
	match id:
		"poison":
			return "Яд x%d (2%% HP при завершении хода)" % _num(status, "stacks")
		"bleed":
			return "Кровотечение -%d/ход%s" % [_num(status, "amount"), turns_suffix]
		"regeneration":
			return "Лечение %d HP/ход%s" % [_num(status, "amount"), turns_suffix]
		"delayed_heal":
			return "Отложенное лечение%s" % turns_suffix
		"delayed_hp_loss":
			return "Отложенная потеря %d HP%s" % [_num(status, "amount"), turns_suffix]
		"stun":
			return "Оглушение%s" % turns_suffix
		"freeze":
			return "Заморозка%s" % turns_suffix
		"invulnerable":
			return "Неуязвимость"
		"skip_turn":
			return "Пропуск следующего хода"
		"mage_damage_bonus":
			return "Магический урон +%d%%%s" % [_num(status, "amount"), turns_suffix]
		"storm_cloud":
			return "Грозовая туча: %d х." % _num(status, "turns")
		"reactive_blessing":
			return "Ответное благословение: %d х." % _num(status, "turns")
	if MAGE_LABELS.has(id) or id.ends_with("_immunity"):
		var mage_label := str(MAGE_LABELS.get(id, _capitalize(id)))
		var stacks_suffix := " x%d" % _num(status, "stacks") if _num(status, "stacks") > 1 else ""
		return mage_label + stacks_suffix + turns_suffix
	# Неизвестный ключ бафа: тот же вывод, что у Python (ключ с пробелами, первая буква заглавная).
	var generic := _capitalize(id.replace("_", " "))
	if _has(status, "amount"):
		generic += ": %d" % _num(status, "amount")
	return generic + turns_suffix


static func status_color(status: Dictionary) -> Color:
	var id := str(status.get("id", ""))
	if COLOR_BY_ID.has(id):
		return COLOR_BY_ID[id]
	if MAGE_LABELS.has(id) or id.ends_with("_immunity"):
		return MAGE_COLOR
	return POSITIVE_COLOR if bool(status.get("positive", false)) else NEGATIVE_COLOR


# Описание для всплывающей подсказки: текст статуса и описание из Python; яд — со стаками и бонусом ассасина.
static func status_description(status: Dictionary, text: String, attacker_type: String) -> String:
	var id := str(status.get("id", ""))
	if id == "poison":
		return poison_description(_num(status, "stacks"), attacker_type)
	if BANNER_DESCRIPTIONS.has(id):
		return "%s: %s" % [text, str(BANNER_DESCRIPTIONS[id])]
	return "Активный эффект: %s." % text


static func poison_description(stacks: int, attacker_type: String) -> String:
	var text := "Яд: %d стак(а/ов). В конце хода отравленной стороны наносит 2%% максимального HP и снимает один стак." % stacks
	if attacker_type == "assassin":
		text += " Ассасин, атакующий эту цель, получает за каждый стак +%d%% шанса крита и +%d%% критического урона." % [
			2 * stacks,
			4 * stacks,
		]
	return text


# Панель призывов у сброса: сначала призывы игрока, затем соперника; показаны первые две строки, дальше «и ещё N».
static func summon_panel(player_summons: Array, enemy_summons: Array, discard: Rect2) -> Dictionary:
	var rows: Array = []
	var groups := {"player": player_summons, "enemy": enemy_summons}
	for owner in SUMMON_OWNERS:
		for summon_variant in _array_of(groups[owner[0]]):
			var summon := _dict_of(summon_variant)
			rows.append({
				"name": "%s: %s" % [str(owner[1]), str(summon.get("name", ""))],
				"details": summon_details(summon),
			})
	var shown := rows.slice(0, SUMMON_MAX_ROWS)
	var extra := rows.size() - shown.size()
	var height := SUMMON_TITLE_HEIGHT + shown.size() * SUMMON_ROW_HEIGHT + (SUMMON_MORE_HEIGHT if extra > 0 else 0.0)
	# clamp_ip из Python: панель не выходит за экран.
	var x := clampf(maxf(6.0, discard.position.x - SUMMON_WIDTH - 8.0), 0.0, DESIGN_SIZE.x - SUMMON_WIDTH)
	var y := clampf(discard.end.y + 8.0, 0.0, DESIGN_SIZE.y - height)
	return {
		"visible": not rows.is_empty(),
		"rect": Rect2(x, y, SUMMON_WIDTH, height),
		"title": SUMMON_TITLE,
		"rows": shown,
		"more": "и ещё %d" % extra if extra > 0 else "",
	}


static func summon_details(summon: Dictionary) -> String:
	var details := "HP %d/%d" % [_int_of(summon.get("hp", 0)), _int_of(summon.get("max_hp", 0))]
	var turns := _int_of(summon.get("turns", 0))
	if turns > 0:
		details += ", %d хода" % turns
	return details


# Прямоугольник заливки щита на полосе HP (duel_renderer.py:_draw_resource_bar): после заполненной части, не дальше
# правого края. Пустой прямоугольник — щита нет или максимум HP равен нулю.
static func shield_overlay_rect(bar: Rect2, current: float, maximum: float, shield: int) -> Rect2:
	if shield <= 0 or maximum <= 0.0:
		return Rect2()
	var filled := float(int(bar.size.x * clampf(current / maximum, 0.0, 1.0)))
	var width := minf(bar.size.x, maxf(1.0, float(int(bar.size.x * float(shield) / maximum))))
	var x := bar.position.x + filled
	if x + width > bar.end.x:
		x = bar.end.x - width
	return Rect2(x, bar.position.y, width, bar.size.y)


static func _status_row(status: Dictionary, attacker_type: String) -> Dictionary:
	var text := status_text(status)
	return {
		"id": str(status.get("id", "")),
		"positive": bool(status.get("positive", false)),
		"text": text,
		"color": status_color(status),
		"description": status_description(status, text, attacker_type),
	}


static func _capitalize(text: String) -> String:
	return text.substr(0, 1).to_upper() + text.substr(1).to_lower()


static func _has(status: Dictionary, key: String) -> bool:
	var value: Variant = status.get(key, null)
	return value is int or value is float


static func _num(status: Dictionary, key: String) -> int:
	return _int_of(status.get(key, 0))


static func _dict_of(value: Variant) -> Dictionary:
	if value is Dictionary:
		return value
	return {}


static func _array_of(value: Variant) -> Array:
	if value is Array:
		return value
	return []


static func _int_of(value: Variant) -> int:
	if value is int or value is float:
		return int(value)
	return 0
