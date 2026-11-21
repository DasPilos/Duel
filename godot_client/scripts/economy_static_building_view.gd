extends VBoxContainer

signal back_requested

const WINDOW_SIZE := Vector2(453, 333)
const BORDER_COLOR := Color8(80, 150, 230)
const BACKGROUND_COLOR := Color8(22, 26, 32)
const NOTICE_BG := Color8(24, 34, 46)
const NOTICE_BORDER := Color8(70, 140, 220)
const DIVIDER_COLOR := Color8(60, 80, 105)
const HEADING_COLOR := Color8(255, 230, 140)
const DESCRIPTION_COLOR := Color8(215, 225, 235)
# Строки возможностей прокручиваются внутри окна, чтобы кнопка возврата оставалась видимой.
const ROWS_HEIGHT := 128.0
const BACK_BUTTON_SIZE := Vector2(187, 29)
const BUTTON_BG := Color8(45, 85, 140)
const BUTTON_HOVER_BG := Color8(70, 130, 200)

# Здания из scenes/city/modals.py, которые в Python не получают данных с сервера: описание, таблица возможностей и возврат в город.
# Эмодзи Python не переносим: в шрифте Godot их нет.
const MODALS := {
	"barracks": {
		"title": "ГОРОДСКИЕ КАЗАРМЫ (УРОВЕНЬ 1)",
		"subtitle": "[ ВОЕННЫЙ ГАРНИЗОН РАДБУРГА • 9х13 ТАЙЛОВ • ВХОД: 84/43 ]",
		"subtitle_color": [130, 200, 255],
		"notice": "Гарнизон на боевом дежурстве: Солдаты содержатся и несут службу на стенах",
		"notice_color": [160, 220, 255],
		"heading": "Содержание и численность солдат гарнизона:",
		"accent": [100, 220, 255],
		"rows": [
			["Регулярные солдаты гарнизона:", "120 / 200 бойцов (пехотинцы, мечники, копейщики)"],
			["Стрелки и стражи стен:", "60 / 100 лучников на крепостных стенах и башнях"],
			["Снабжение провизией из амбара:", "100% суточного довольствия (боеготовность максимальная)"],
			["Оснащение оружием и броней:", "Кузница и мастерская обеспечивают +20% к боевой мощи"],
			["Назначение казарм:", "Оборона ворот города, отражение штурмов и марш армий Света"],
			["Улучшение казарм (Ур. 2):", "Увеличит вместимость до 500 бойцов и откроет наём тяжелых рыцарей"],
		],
	},
	"engineering": {
		"title": "ИНЖЕНЕРНАЯ ПАЛАТА (УРОВЕНЬ 1)",
		"subtitle": "[ ЦЕХ ОБОРОННЫХ СООРУЖЕНИЙ И ОСАДНЫХ МАШИН • 10х8 ТАЙЛОВ • ВХОД: 44/15 ]",
		"subtitle_color": [130, 200, 255],
		"notice": "Цех инженеров активен: чертежи и станки подготовлены к сборке боевых машин",
		"notice_color": [150, 235, 215],
		"heading": "Производство боевых машин и осадной техники:",
		"accent": [120, 225, 210],
		"rows": [
			["Катапульта полевая:", "Метание зажигательных снарядов и камней по вражеским укреплениям"],
			["Осадный таран:", "Пробитие ворот и укреплений противника в наступлении армий Света"],
			["Тяжелый требушет:", "Сверхдальнобойная артиллерия для сокрушения цитаделей Тьмы"],
			["Оборонные турели и баллисты:", "Усиление гарнизона и огневой мощи крепостных стен города"],
			["Требуемые ресурсы со склада:", "Древесина, камень, обработанное железо и канаты"],
			["Улучшение палаты (Ур. 2):", "Откроет автоматические многозарядные баллисты и бронированные башни"],
		],
	},
	"university": {
		"title": "ГОРОДСКОЙ УНИВЕРСИТЕТ (УРОВЕНЬ 1)",
		"subtitle": "[ АКАДЕМИЯ ТЕХНОЛОГИЙ И НАУК РАДБУРГА • 15х11 ТАЙЛОВ • ВХОД: 23/84 ]",
		"subtitle_color": [130, 200, 255],
		"notice": "Академия активна: учёные и архимаги исследуют новые технологии города",
		"notice_color": [160, 225, 255],
		"heading": "Изучение новых технологий и научных открытий:",
		"accent": [160, 225, 255],
		"rows": [
			["Горное дело и металлургия:", "+15% к добыче железной руды и качеству выплавки слитков"],
			["Фортификация и зодчество:", "+20% к прочности крепостных стен, башен и ворот города"],
			["Селекция и агрономия:", "Повышение урожайности пшеничных полей и вместимости амбаров"],
			["Военное искусство и тактика:", "Увеличение атаки и защиты гарнизона регулярной армии"],
			["Свитки древних знаний:", "Открытие редких рецептов крафта, чар и рунических печатей"],
			["Улучшение университета (Ур. 2):", "Откроет высшую алхимию, зачарование экипировки и магические башни"],
		],
	},
	"academy": {
		"title": "ВОЕННАЯ АКАДЕМИЯ (УРОВЕНЬ 1)",
		"subtitle": "[ ЦЕНТР ОБУЧЕНИЯ ВОИНОВ И ПРОКАЧКИ КАРТ • 10х7 ТАЙЛОВ • ВХОД: 19/73 ]",
		"subtitle_color": [255, 180, 150],
		"notice": "Академия открыта: место тренировки бойцов, развития талантов и усиления карт",
		"notice_color": [255, 190, 180],
		"heading": "Обучение воинов и прокачка карт силовой линии:",
		"accent": [255, 190, 180],
		"rows": [
			["Прокачка карт силовой линии:", "Повышение урона, снижение стоимости и открытие комбо-эффектов боевых карт"],
			["Ветви талантов бойца:", "Развитие направлений: Несокрушимый защитник, Берсерк ярости, Мастер клинка"],
			["Открытие новых боевых карт:", "Изучение приёмов: Сокрушительный удар, Парирование, Боевой клич, Раскол брони"],
			["Тренировочные спарринги:", "Отработка тактики боя на полигоне с инструкторами академии"],
			["Подготовка элитных командиров:", "Повышение выучки офицеров гарнизона (+15% к дисциплине отрядов)"],
			["Улучшение академии (Ур. 2):", "Откроет доступ к легендарным картам стоек и ультимативным приёмам"],
		],
	},
	"mage_school": {
		"title": "ШКОЛА СТИХИЙ (УРОВЕНЬ 1)",
		"subtitle": "[ ЦЕНТР ОБУЧЕНИЯ МАГИИ И ПРОКАЧКИ МАГИЧЕСКИХ КАРТ • 15х9 ТАЙЛОВ • ВХОД: 44/66 ]",
		"subtitle_color": [210, 175, 255],
		"notice": "Школа стихий открыта: постижение тайных знаний, концентрация маны и усиление заклинаний",
		"notice_color": [225, 195, 255],
		"heading": "Обучение магии и развитие стихийных карт:",
		"accent": [210, 175, 255],
		"rows": [
			["Стихия Огня:", "Прокачка атакующих карт пламени, взрывов, ожогов и огненного шара"],
			["Стихия Воды:", "Изучение исцеляющих потоков, ледяных оков и очищения разума"],
			["Стихия Воздуха:", "Увеличение скорости каста, молнии, цепные разряды и уклонение"],
			["Стихия Земли:", "Каменная кожа, шипы, защитные барьеры и землетрясения"],
			["Стихия Света:", "Божественные благословения, экзорцизм и рассеивание чар Тьмы"],
			["Прокачка магических карт:", "Снижение расхода маны карт заклинаний, увеличение урона и длительности эффектов"],
			["Улучшение школы (Ур. 2):", "Откроет создание комбинированных стихийных заклинаний и ритуальные круги"],
		],
	},
}

var _key := ""


func setup(key: String) -> void:
	_key = key
	var data: Dictionary = MODALS[key]
	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 8)
	margin.add_theme_constant_override("margin_right", 8)
	add_child(margin)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 3)
	margin.add_child(column)
	column.add_child(_label(str(data["subtitle"]), _color(data["subtitle_color"]), 11))
	column.add_child(_divider(DIVIDER_COLOR))
	var notice := PanelContainer.new()
	notice.add_theme_stylebox_override("panel", _box(NOTICE_BG, NOTICE_BORDER, 1, 6, 6.0, 3.0))
	var notice_text := _label(str(data["notice"]), _color(data["notice_color"]), 11)
	notice_text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	notice.add_child(notice_text)
	column.add_child(notice)
	column.add_child(_label(str(data["heading"]), HEADING_COLOR, 13))
	var rows_scroll := ScrollContainer.new()
	rows_scroll.custom_minimum_size.y = ROWS_HEIGHT
	rows_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	column.add_child(rows_scroll)
	var rows := VBoxContainer.new()
	rows.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	rows.add_theme_constant_override("separation", 0)
	rows_scroll.add_child(rows)
	for row in data["rows"]:
		var pair := VBoxContainer.new()
		pair.add_child(_indented(_label(str(row[0]), _color(data["accent"]), 11), 6))
		pair.add_child(_indented(_label(str(row[1]), DESCRIPTION_COLOR, 11), 12))
		rows.add_child(pair)
	var back_button := Button.new()
	back_button.text = "ВЕРНУТЬСЯ В ГОРОД"
	back_button.custom_minimum_size = BACK_BUTTON_SIZE
	back_button.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	_style_back_button(back_button)
	back_button.pressed.connect(func() -> void: back_requested.emit())
	column.add_child(back_button)


func window_title() -> String:
	return str(MODALS[_key]["title"])


func _label(text: String, color: Color, font_size: int) -> Label:
	var label := Label.new()
	label.text = text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	return label


func _color(values: Array) -> Color:
	return Color8(int(values[0]), int(values[1]), int(values[2]))


func _style_back_button(button: Button) -> void:
	button.add_theme_stylebox_override("normal", _box(BUTTON_BG, BUTTON_BG, 0, 6, 8.0, 3.0))
	button.add_theme_stylebox_override("hover", _box(BUTTON_HOVER_BG, BUTTON_HOVER_BG, 0, 6, 8.0, 3.0))
	button.add_theme_stylebox_override("pressed", _box(BUTTON_HOVER_BG, BUTTON_HOVER_BG, 0, 6, 8.0, 3.0))
	button.add_theme_stylebox_override("focus", _box(BUTTON_BG, BUTTON_BG, 0, 6, 8.0, 3.0))
	button.add_theme_color_override("font_color", Color.WHITE)
	button.add_theme_color_override("font_hover_color", Color.WHITE)
	button.add_theme_color_override("font_pressed_color", Color.WHITE)
	button.add_theme_color_override("font_focus_color", Color.WHITE)
	button.add_theme_font_size_override("font_size", 12)


static func _box(bg: Color, border: Color, border_width: int, radius: int, margin_x: float, margin_y: float) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = bg
	style.border_color = border
	style.set_border_width_all(border_width)
	style.set_corner_radius_all(radius)
	style.content_margin_left = margin_x
	style.content_margin_right = margin_x
	style.content_margin_top = margin_y
	style.content_margin_bottom = margin_y
	return style


static func _divider(color: Color) -> ColorRect:
	var rule := ColorRect.new()
	rule.color = color
	rule.custom_minimum_size = Vector2(0, 1)
	return rule


static func _indented(child: Control, left: int) -> MarginContainer:
	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", left)
	margin.add_child(child)
	return margin
