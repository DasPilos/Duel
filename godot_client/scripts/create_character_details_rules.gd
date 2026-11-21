extends RefCounted

# Карточка создания из scenes/create_character_scene.py: HP и MP (_card_profile, _draw_resource), иконка класса
# (ui/profession_icons.py), слоты экипировки (ui/equipment_slots.py), строки веса, скорости и дальности удара
# (_draw_info_lines). Tower и Economy считают по character_profile_rules.gd, Deck по deck_character_rules.gd
# (deck/combat/character_stats.py). В Deck нет правил веса, скорости и дальности удара (deck/ui/character_profile.py),
# поэтому этих строк на карточке Deck нет.

const PROFILE_RULES := preload("res://scripts/character_profile_rules.gd")
const DECK_RULES := preload("res://scripts/deck_character_rules.gd")
const CLASS_RULES := preload("res://scripts/deck_class_card_rules.gd")

const CARD_WIDTH := 450.0
const CARD_HEIGHT := 1000.0
# combat/world_stats.py: BASE_ATTACK_REACH и REACH_PER_INTUITION
const BASE_ATTACK_REACH := 45.0
const REACH_PER_INTUITION := 1.0
# deck/combat/character_stats.py: BASE_STAT_VALUE. Сервер Deck создаёт интеллект этим значением
const DECK_BASE_STAT_VALUE := 2
const ICON_DIR := "ui/professions"
const ICON_SIZE := 32
const ICON_GAP := 4
# Полосы HP и MP в create_character_scene.py _draw_header: x = 20, y = 100 и 140, ширина 360, высота 14
const HP_BAR := Rect2(20.0, 100.0, 360.0, 14.0)
const MP_BAR := Rect2(20.0, 140.0, 360.0, 14.0)
# Строки веса и скорости начинаются на 6 px ниже слота обуви; между строками 2 px, поля плашки 6 и 2 px
const INFO_GAP := 6.0
const CHIP_GAP := 2.0
const CHIP_PAD_X := 6.0
const CHIP_PAD_Y := 2.0
# (ключ, подпись, колонка, ряд) из equipment_slots.SLOT_LAYOUT
const SLOT_LAYOUT := [
	["ears", "Серьги", 0, 0], ["head", "Голова", 2, 0], ["neck", "Шея", 4, 0],
	["back", "Плащ", 0, 1], ["body", "Доспех", 2, 1], ["ring", "Кольцо", 4, 1],
	["hands", "Руки", 0, 2], ["shield", "П рука", 1, 2], ["belt", "Пояс", 2, 2],
	["weapon", "Л рука", 3, 2], ["ring_2", "Кольцо", 4, 2],
	["legs", "Ноги", 2, 3], ["feet", "Обувь", 2, 4],
]
const SLOT_SIZE := Vector2(66.0, 62.0)
# equipment_slots.slot_rects: центры колонок из эталона 440 px, сдвиг середины ряда на 8 px от центра зоны куклы
const SLOT_COLUMN_CENTERS := [48.0, 143.0, 220.0, 308.0, 389.0]
const SLOT_REFERENCE_WIDTH := 440.0
const SLOT_REFERENCE_CENTER := 220.0
const AREA_TOP_OFFSET := 151.0
const AREA_BOTTOM_OFFSET := 180.0
const MIDDLE_ROW_SHIFT := 8.0
const ROW_OFFSETS := [-172.0, -86.0, 0.0, 86.0, 172.0]


# Прямоугольники слотов в координатах карточки (левый верхний угол карточки — 0, 0).
static func slot_rects(card_width: float = CARD_WIDTH) -> Dictionary:
	var scale := card_width / SLOT_REFERENCE_WIDTH
	var center_x := floorf(card_width / 2.0)
	var columns: Array[float] = []
	for center in SLOT_COLUMN_CENTERS:
		columns.append(roundf(center_x + (float(center) - SLOT_REFERENCE_CENTER) * scale - SLOT_SIZE.x / 2.0))
	var middle_row_top := floorf(slot_area_center_y() - MIDDLE_ROW_SHIFT)
	var result := {}
	for entry in SLOT_LAYOUT:
		var row_top := middle_row_top + float(ROW_OFFSETS[int(entry[3])])
		result[str(entry[0])] = Rect2(Vector2(columns[int(entry[2])], row_top), SLOT_SIZE)
	return result


static func slot_area_center_y() -> float:
	return (AREA_TOP_OFFSET + CARD_HEIGHT - AREA_BOTTOM_OFFSET) / 2.0


static func info_top(slots: Dictionary) -> float:
	var feet: Rect2 = slots["feet"]
	return feet.end.y + INFO_GAP


# Строки Tower и Economy по распределению: тот же расчёт, что _card_profile и _draw_info_lines в Python.
# Выносливость и интеллект приходят из creation_stats, поэтому строки меняются вместе с очками.
static func tower_details(stats: Dictionary) -> Dictionary:
	var max_hp := PROFILE_RULES.calculate_max_hp(int(stats.get("endurance", 0)))
	var max_mp := PROFILE_RULES.calculate_max_mana(int(stats.get("intellect", 0)))
	var profile := {"stats": stats, "equipment_bonuses": {}, "carried_weight_kg": 0.0}
	var carried := float(profile["carried_weight_kg"])
	var capacity := PROFILE_RULES.carry_capacity(profile)
	var speeds := PROFILE_RULES.combat_speed_values(profile)
	var attack_seconds := float(speeds["attack_seconds"])
	var move_speed := int(speeds["move_speed"])
	var reach := BASE_ATTACK_REACH + REACH_PER_INTUITION * float(int(stats.get("intuition", 0)))
	return {
		"hp": max_hp,
		"max_hp": max_hp,
		"mp": max_mp,
		"max_mp": max_mp,
		"hp_text": "HP %d/%d" % [max_hp, max_hp],
		"mp_text": "MP %d/%d" % [max_mp, max_mp],
		"carried_kg": carried,
		"capacity_kg": capacity,
		"weight_text": "Грузоподъёмность: %s/%d кг" % [DECK_RULES.format_g(carried), capacity],
		"weight_color": PROFILE_RULES.load_color(carried, float(capacity)),
		"attack_seconds": attack_seconds,
		"attack_text": "Скорость атаки: %s с" % DECK_RULES.format_g(attack_seconds),
		"move_speed": move_speed,
		"move_text": "Скорость передвижения: %d px/с" % move_speed,
		"reach": reach,
		"reach_text": "Дальность удара: %s px" % DECK_RULES.format_g(reach),
	}


# Front Line: дальность атаки в единицах (1 тайл = 100 ед.), игроку показывается одно число. Формула как в
# front_line/server/combat.py: база по классу и +5 ед. за каждое очко интуиции сверх 3.
const FRONT_LINE_BASE_RANGE := {"warrior": 100, "archer": 500, "mage": 500}
const FRONT_LINE_RANGE_PER_INTUITION := 5
const FRONT_LINE_BASE_INTUITION := 3


static func front_line_attack_range(profession: String, intuition: int) -> int:
	var base := int(FRONT_LINE_BASE_RANGE.get(profession, FRONT_LINE_BASE_RANGE["warrior"]))
	return maxi(0, base + FRONT_LINE_RANGE_PER_INTUITION * (intuition - FRONT_LINE_BASE_INTUITION))


# Deck: сервер создаёт персонажа с выносливостью minimum_endurance(1) (deck/server/database.py create_character).
# HP и мана зависят от класса: calculate_max_hp и calculate_max_mana из deck/combat/character_stats.py.
static func deck_details(profession: String) -> Dictionary:
	var max_hp := DECK_RULES.calculate_max_hp(1, DECK_RULES.minimum_endurance(1), profession)
	var max_mp := DECK_RULES.calculate_max_mana(DECK_BASE_STAT_VALUE, profession)
	return {
		"hp": max_hp,
		"max_hp": max_hp,
		"mp": max_mp,
		"max_mp": max_mp,
		"hp_text": "HP %d/%d" % [max_hp, max_hp],
		"mp_text": "MP %d/%d" % [max_mp, max_mp],
	}


# Путь к иконке класса в ../assets/ui/professions. У некроманта иконки нет, поэтому путь пустой.
static func class_icon_path(assets_root: String, profession: String) -> String:
	var info: Dictionary = CLASS_RULES.CLASS_INFO.get(CLASS_RULES.normalize_class(profession), {})
	var file_name := str(info.get("icon", ""))
	if assets_root.is_empty() or file_name.is_empty():
		return ""
	return assets_root.path_join(ICON_DIR).path_join(file_name)
