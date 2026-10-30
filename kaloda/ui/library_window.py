"""Интерактивный справочник по игровым существам и содержимому."""

import pygame

from client.network import ServerError
from kaloda import settings
from kaloda.currency import format_coins
from kaloda.combat.arena_battle import (
    ANCIENT_ENT_DECK,
    ANCIENT_ENT_MAX_HP,
    ANCIENT_ENT_MAX_MP,
    BONE_DOG_DECK,
    BONE_DOG_MAX_HP,
    BONE_DOG_MAX_MP,
    KOBOLD_DECK,
    KOBOLD_MAX_HP,
    NECROMANCER_DECK,
    NECROMANCER_MAX_HP,
    NECROMANCER_MAX_MP,
    SKELETON_DECK,
    SKELETON_MAX_HP,
    SKELETON_MAX_MP,
    SKULL_MAX_HP,
    WOLF_DECK,
    WOLF_MAX_HP,
)
from kaloda.combat.card_database import BASE_CARDS
from kaloda.combat.character_stats import PROFESSIONS
from kaloda.ui.hud import draw_button


_CARD_FIELDS = {
    "damage": "урон",
    "dice": "кубики урона",
    "heal": "лечение",
    "heal_percent": "лечение",
    "heal_flat": "базовое лечение",
    "heal_endurance": "лечение за выносливость",
    "heal_agility_multiplier": "лечение за ловкость",
    "heal_max_hp_percent": "лечение от максимального HP",
    "heal_per_turn": "лечение за ход",
    "range": "дальность",
    "duration": "длительность",
    "buff_duration": "длительность бафа",
    "stacks": "заряды",
    "poison": "яд",
    "bleed": "кровотечение",
    "entangle": "корни",
    "shield": "щит",
    "shield_flat": "прочность щита",
    "shield_hp": "прочность щита",
    "dodge_percent": "уклонение",
    "damage_percent": "урон",
    "damage_buff_percent": "усиление урона",
    "incoming_damage_percent": "снижение входящего урона",
    "crit_chance_percent": "шанс критического удара",
    "crit_damage_percent": "критический урон",
    "hits": "удары",
    "summon": "призыв",
    "summon_spirit": "призыв лесного духа",
    "spirit_hp": "здоровье духа",
    "spirit_dodge": "уклонение духа",
    "heal_max_hp_percent": "лечение от максимального HP",
    "wisdom_damage": "урон за мудрость",
    "intellect_damage": "урон за интеллект",
    "wisdom_hp": "щит за мудрость",
    "intellect_shield": "щит за интеллект",
    "crit_chance_guarantee": "гарантированный крит",
    "no_miss": "без промаха",
    "element": "стихия",
}


_ELEMENT_REACTIONS = (
    {
        "name": "Реакция: огонь + вода",
        "description": "Снижает урон срабатывающей реакции до половины исходного.\n"
                       "Формула: урон реакции = ⌊урон × 0,5⌋.",
    },
    {
        "name": "Реакция: огонь + холод",
        "description": "Снижает урон срабатывающей реакции до одной пятой.\n"
                       "Формула: урон реакции = ⌊урон × 0,2⌋.",
    },
    {
        "name": "Реакция: огонь + электричество",
        "description": "Наносит ответный урон и ослепляет цель на 1 ход.\n"
                       "Формула: ⌊урон × (1,3 + Гармония × 0,01)⌋ + Гармония; "
                       "ослепление снижает шанс попадания на 20%.",
    },
    {
        "name": "Реакция: вода + электричество",
        "description": "Усиливает урон электричества и наносит 40% этого урона повторно.\n"
                       "Формула: основной урон = ⌊урон × (1,1 + Гармония × 0,01)⌋; "
                       "дополнительный урон = ⌊основной урон × 0,4⌋.",
    },
    {
        "name": "Реакция: вода + холод",
        "description": "Замораживает противника на 1 ход: он может разыграть на 1 карту меньше.",
    },
    {
        "name": "Реакция: электричество + холод",
        "description": "Создаёт щит и даёт иммунитет к повторной реакции на 1 ход.\n"
                       "Формула щита: ⌊урон реакции × 0,3⌋.",
    },
    {
        "name": "Реакция: воздух + стихия",
        "description": "Сокращает оставшуюся длительность других стихийных статусов на 1 ход.",
    },
)


def _effect_formula(card):
    data = card.effect_data or {}
    formulas = []
    if data.get("dice"):
        formulas.append(
            f"Урон атаки: бросок {data['dice']} + Сила + фиксированный урон оружия; "
            "затем применяются бафы, защита, блок и крит."
        )
    elif data.get("damage"):
        formulas.append(
            f"Урон: {data['damage']}"
            + (" + Мудрость" if data.get("wisdom_damage") else "")
            + (" + Интеллект × " + str(data["intellect_damage"])
               if data.get("intellect_damage") else "")
            + (" + урон оружия." if card.effect_type.startswith("mage_") else ".")
        )
    if any(data.get(key) for key in (
        "heal_flat", "heal_endurance", "heal_agility_multiplier", "heal_max_hp_percent",
        "heal_percent", "heal_per_turn",
    )):
        formula = [str(int(data.get("heal_flat", 0)))]
        if data.get("heal_endurance"):
            formula.append(f"+ Выносливость × {data['heal_endurance']}")
        if data.get("heal_agility_multiplier"):
            formula.append(f"+ Ловкость × {data['heal_agility_multiplier']}")
        if data.get("heal_max_hp_percent"):
            formula.append(f"+ ⌈макс. HP × {data['heal_max_hp_percent']}%⌉")
        if data.get("heal_percent"):
            formula.append(f"+ ⌈недостающее HP × {data['heal_percent']}%⌉")
        if data.get("heal_per_turn"):
            formula.append(
                f"{data['heal_per_turn']} + Выносливость × "
                f"{data.get('endurance_heal', 0)} за ход"
            )
        formulas.append(f"Лечение: {' '.join(formula)}.")
    if data.get("status"):
        formulas.append(
            f"Статус «{data['status']}»: {data.get('stacks', 1)} заряд(а/ов), "
            f"{data.get('status_duration') or card.effect_duration or 1} ход(а/ов)."
        )
    if data.get("damage_buff_percent"):
        formulas.append(
            f"Баф урона: +{data['damage_buff_percent']}% на "
            f"{data.get('buff_duration') or data.get('duration') or card.effect_duration or 1} ход(а/ов)."
        )
    if data.get("incoming_damage_percent"):
        formulas.append(
            f"Защитный баф: входящий урон −{data['incoming_damage_percent']}% "
            f"на {data.get('duration') or card.effect_duration or 1} ход(а/ов)."
        )
    if data.get("crit_chance_percent"):
        formulas.append(f"Баф критического шанса: +{data['crit_chance_percent']}%.")
    if data.get("crit_damage_percent"):
        formulas.append(f"Баф критического урона: +{data['crit_damage_percent']}%.")
    if data.get("poison"):
        formulas.append("Яд: заряды наносят периодический урон, обычно 2% макс. HP за заряд.")
    if data.get("bleed_percent"):
        formulas.append(
            f"Кровотечение: ⌈макс. HP цели × {data['bleed_percent']}% / 2⌉ "
            f"за тик на {data.get('duration') or 2} хода."
        )
    if data.get("summon_spirit"):
        formulas.append(
            f"Лесной дух: {data.get('spirit_hp', 30)} HP; поддержка союзников в радиусе 3 гексов."
        )
    return formulas


def _item_entry(item):
    """Запись справочника из элемента каталога предметов, присланного сервером."""
    effects = item.get("effects") or {}
    effect_type = effects.get("type", "")
    if item.get("can_use"):
        use_text = "Можно использовать вне боя."
    elif effect_type.startswith("battle_"):
        use_text = "Используется в бою."
    else:
        use_text = "Материал или экипировка; прямое использование не предусмотрено."
    description = (
        f"Тип: {item.get('item_type', '')}. Редкость: {item.get('rarity', '')}.\n"
        f"Цена: {format_coins(item.get('price', 0))}.\n"
        f"{item.get('description', '')}\n{use_text}"
    )
    if any(key != "type" for key in effects):
        description += "\nПараметры эффекта: " + ", ".join(
            f"{_CARD_FIELDS.get(key, key.replace('_', ' '))}: {value}"
            for key, value in effects.items()
            if key != "type"
        )
    return {"name": item.get("name", "?"), "description": description}


def _card_description(card):
    resource_names = {
        "mana": "мана",
        "rage": "ярость",
        "accuracy": "меткость",
        "concentration": "концентрация",
    }
    details = [
        f"Класс и специализация: {card.group_name}",
        f"Цена розыгрыша: {card.resource_cost} "
        f"{resource_names.get(card.resource_type, card.resource_type)}.",
        f"Тип механики: {card.effect_type}.",
    ]
    effect = card.effect_data or {}
    translated = [
        f"{_CARD_FIELDS.get(key, key.replace('_', ' '))}: "
        f"{'да' if value is True else 'нет' if value is False else value}"
        for key, value in effect.items()
    ]
    if translated:
        details.append("Параметры эффекта:\n" + "\n".join(translated))
    if card.effect_duration:
        details.append(f"Длительность эффекта: {card.effect_duration} ход(а/ов).")
    formulas = _effect_formula(card)
    if formulas:
        details.append("Расчёт эффекта:\n" + "\n".join(formulas))
    if card.effect_type in ("damage", "mage_damage", "mage_damage_status"):
        details.append(
            "Критический удар: шанс берётся из класса и активных бафов; "
            "множитель урона = 1,5 + бонус класса + Интуиция × 0,05."
        )
    return "\n".join(details)


def _creature_entry(name, hp, mp, description, deck=(), dodge=0):
    card_lines = []
    for card in deck:
        actions = []
        if card.damage:
            actions.append(f"{card.damage} урона")
        if card.heal_percent:
            actions.append(f"лечение {card.heal_percent:.0%} от максимального здоровья")
        if card.stun_turns:
            actions.append(f"оглушение {card.stun_turns} ход.")
        if card.root_turns:
            actions.append(f"корни {card.root_turns} ход.")
        if card.aoe_radius:
            actions.append(f"область радиуса {card.aoe_radius}")
        if card.summon_wolf:
            actions.append("призывает волка")
        if card.summon_kind:
            actions.append(f"призывает: {card.summon_kind}")
        if card.damage_taken_bonus_percent:
            actions.append(f"следующий урон по цели +{card.damage_taken_bonus_percent}%")
        if card.heal_allies_percent_of_caster_hp:
            actions.append(f"лечит союзников на {card.heal_allies_percent_of_caster_hp:.0%} текущего HP")
        if card.sacrifice_heal_percent:
            actions.append(f"жертва лечит союзника на {card.sacrifice_heal_percent:.0%} макс. HP")
        if card.teleport_behind:
            actions.append("прыжок за спину цели")
        if card.range is not None:
            actions.append(f"дальность {card.range}")
        if card.cooldown_turns:
            actions.append(f"перезарядка {card.cooldown_turns} ход.")
        card_lines.append(f"• {card.name}: {', '.join(actions) or 'особое действие'}")
    cards = "\n".join(card_lines)
    stats = f"Здоровье: {hp}." if hp is not None else ""
    if mp is not None:
        stats += f" Мана: {mp}." if stats else f"Мана: {mp}."
    if dodge:
        stats += f" Уклонение: {dodge}%." if stats else f"Уклонение: {dodge}%."
    return {"name": name, "description": f"{stats}\n{description}\n{cards}".strip()}


class LibraryWindow:
    WIDTH = 1120
    HEIGHT = 640
    CATEGORIES = ("Существа", "Предметы", "Карты", "Классы", "Эффекты")

    def __init__(self, scene):
        self.scene = scene
        self.is_open = False
        self.rect = pygame.Rect(0, 0, min(self.WIDTH, settings.WIDTH - 32),
                                min(self.HEIGHT, settings.HEIGHT - 32))
        self.rect.center = (settings.WIDTH // 2, settings.HEIGHT // 2)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 26, bold=True)
        self.font = pygame.font.SysFont(settings.FONT_NAME, 18)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 15)
        self.close_rect = pygame.Rect(self.rect.right - 42, self.rect.top + 12, 30, 30)
        self.search_rect = pygame.Rect(self.rect.left + 24, self.rect.top + 58,
                                       self.rect.width - 48, 34)
        self.category_rects = []
        tab_top = self.rect.top + 102
        tab_width = (self.rect.width - 48) // len(self.CATEGORIES)
        for index, _ in enumerate(self.CATEGORIES):
            self.category_rects.append(pygame.Rect(
                self.rect.left + 24 + index * tab_width, tab_top, tab_width - 6, 36
            ))
        self.list_rect = pygame.Rect(self.rect.left + 24, tab_top + 50, 360,
                                     self.rect.bottom - tab_top - 74)
        self.detail_rect = pygame.Rect(self.list_rect.right + 18, self.list_rect.top,
                                       self.rect.right - self.list_rect.right - 42,
                                       self.list_rect.height)
        self.category_index = 0
        self.selected_index = 0
        self.search_text = ""
        self.detail_scroll = 0
        self.data = self._catalogue()
        self.items_message = None

    def _catalogue(self):
        creatures = [
            _creature_entry("Кобольд", KOBOLD_MAX_HP, None,
                            "Обычный противник леса.", KOBOLD_DECK),
            _creature_entry("Древний энт", ANCIENT_ENT_MAX_HP, ANCIENT_ENT_MAX_MP,
                            "Босс арены; призывает волков.", ANCIENT_ENT_DECK),
            _creature_entry("Волк", WOLF_MAX_HP, None,
                            "Призыв Древнего энта; перемещается на 4 гекса за ход.", WOLF_DECK),
            _creature_entry("Скелет", SKELETON_MAX_HP, SKELETON_MAX_MP,
                            "Противник кладбища. Держится близко, прыгает за спину, оглушает и помечает цель.",
                            SKELETON_DECK, dodge=20),
            _creature_entry("Некромансер", NECROMANCER_MAX_HP, NECROMANCER_MAX_MP,
                            "Держит дистанцию 3–4 гекса; призывает череп, скелета и костяного пса, "
                            "опутывает и лечит союзников.",
                            NECROMANCER_DECK),
            _creature_entry("Череп", SKULL_MAX_HP, 0,
                            "Призыв некромансера. При приближении взрывается, нанося 14 урона в радиусе 2."),
            _creature_entry("Костяной пёс", BONE_DOG_MAX_HP, BONE_DOG_MAX_MP,
                            "Призыв некромансера; перемещается на 4 гекса. При 15% здоровья жертвует собой и лечит союзника.",
                            BONE_DOG_DECK),
            _creature_entry("Лесной дух", 30, None,
                            "Призыв-союзник: лечит, усиливает урон и даёт щит союзникам в радиусе 3."),
            _creature_entry("Голем", None, None,
                            "Призыв-союзник, здоровье зависит от карты и характеристики Мудрость; принимает часть входящего урона."),
            _creature_entry("Громовая туча", None, None,
                            "Воздушный призыв без отдельного HP: наносит периодический урон и электрический статус, затем рассеивается."),
        ]
        cards = [
            {"name": card.name, "description": _card_description(card)}
            for card in BASE_CARDS
        ]
        classes = []
        for profession_type, data in PROFESSIONS.items():
            classes.append({
                "name": data["name"],
                "description": (
                    f"Тип: {profession_type}.\nБазовое здоровье: {data['hp']}.\n"
                    f"Базовая мана: {data['mana']}.\n"
                    f"Уникальный ресурс: {data['unique_resource_name']}."
                ),
            })
        effects = [
            {"name": "Физический урон", "description": "Базовая формула: максимум кубиков карты + Сила + урон оружия. "
             "Затем применяются бонусы урона, защита, щит и блок. Крит умножает урон."},
            {"name": "Магический урон", "description": "Базовый урон карты усиливается Мудростью, параметрами карты, "
             "оружием и магическими бафами; затем применяются сопротивления и щиты."},
            {"name": "Критический удар", "description": "Шанс = базовый шанс класса + бонусы карты и бафов "
             "(итог не выше 95%). Множитель = 1,5 + бонус крит. урона класса + Интуиция × 0,05."},
            {"name": "Уклонение", "description": "Формула шанса: базовое уклонение класса + Ловкость × 2% + "
             "бонус экипировки и бафов. Шанс ограничен 70%; успешный уворот отменяет урон и эффекты атаки."},
            {"name": "Огонь", "description": "Наносит периодический урон; стаки огня обрабатываются в конце хода. "
             "Огонь участвует в реакциях стихий."},
            {"name": "Яд", "description": "Стаки накапливаются на цели и наносят периодический урон. "
             "Формула тика: 2% максимального HP цели за заряд; карта может менять силу или предел стаков."},
            {"name": "Кровотечение", "description": "Урон в конце хода.\n"
             "Формула тика: ⌈макс. HP цели × (процент карты + бонус кровотечения) / 100 / 2⌉; "
             "длительность задаётся картой."},
            {"name": "Корни", "description": "Запрещают перемещение на время эффекта. Длительность задаёт карта."},
            {"name": "Оглушение", "description": "Цель пропускает ход; длительность и возможность сопротивления "
             "зависят от карты и текущей защиты."},
            {"name": "Уязвимость", "description": "Увеличивает следующий полученный урон на заданный картой процент; "
             "после срабатывания бонус снимается."},
            {"name": "Щит", "description": "Поглощает входящий урон: фактический урон = max(0, урон − прочность щита). "
             "Прочность уменьшается на поглощённую величину."},
            {"name": "Заморозка", "description": "Сокращает число карт, которые цель может разыграть в свой ход; "
             "вода и холод вызывают заморозку на 1 ход."},
            {"name": "Электричество", "description": "Стихийный статус; участвует в реакциях с огнём, водой и холодом."},
            {"name": "Вода", "description": "Стихийный статус: снижает уклонение цели на 15% и участвует в реакциях."},
            {"name": "Слепота", "description": "Снижает шанс попадания атакующей стороны на 20% на 1 ход."},
            {"name": "Лечение", "description": "Восстановление ограничено недостающим здоровьем. Формула конкретной "
             "карты указана в её записи: базовое лечение + бонусы характеристик и/или процент недостающего HP."},
            {"name": "Усиление урона", "description": "Увеличивает наносимый урон на процент бафа на его срок. "
             "Модификаторы урона применяются последовательно после базового урона и критического множителя."},
        ]
        effects.extend(_ELEMENT_REACTIONS)
        known_effects = {entry["name"].casefold() for entry in effects}
        for effect_type in sorted({card.effect_type for card in BASE_CARDS}):
            if effect_type.casefold() in known_effects:
                continue
            examples = [card.name for card in BASE_CARDS if card.effect_type == effect_type][:4]
            effects.append({
                "name": f"Механика карты: {effect_type}",
                "description": f"Тип эффекта карт. Примеры: {', '.join(examples)}.",
            })
        status_names = set()
        for card in BASE_CARDS:
            for key, value in (card.effect_data or {}).items():
                if key in {"status", "status_name", "status_to_apply"} and isinstance(value, str):
                    status_names.add(value)
                elif key in {"statuses", "status_names"} and isinstance(value, (list, tuple)):
                    status_names.update(str(item) for item in value)
        known_effects = {entry["name"].casefold() for entry in effects}
        for status_name in sorted(status_names):
            if status_name.casefold() not in known_effects:
                effects.append({
                    "name": f"Статус: {status_name}",
                    "description": "Статус, накладываемый боевыми картами; его действие зависит от карты.",
                })
        return {
            "Существа": creatures,
            "Предметы": [],
            "Карты": cards,
            "Классы": classes,
            "Эффекты": effects,
        }

    @property
    def category(self):
        return self.CATEGORIES[self.category_index]

    def filtered_entries(self):
        entries = self.data[self.category]
        query = self.search_text.casefold().strip()
        if not query:
            return entries
        return [
            entry for entry in entries
            if query in entry["name"].casefold() or query in entry["description"].casefold()
        ]

    def open(self):
        self.is_open = True
        client = getattr(self.scene.session, "client", None)
        try:
            catalog = client.list_item_catalog()
        except (ServerError, AttributeError, OSError) as error:
            self.items_message = f"Каталог предметов недоступен: {error}"
            return
        self.items_message = None
        self.data["Предметы"] = [_item_entry(item) for item in catalog]

    def close(self):
        self.is_open = False

    def handle_event(self, event):
        if not self.is_open:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.close()
            elif event.key == pygame.K_BACKSPACE:
                self.search_text = self.search_text[:-1]
                self.selected_index = self.detail_scroll = 0
            elif event.key == pygame.K_UP:
                self.selected_index = max(0, self.selected_index - 1)
                self.detail_scroll = 0
            elif event.key == pygame.K_DOWN:
                self.selected_index = min(
                    max(0, len(self.filtered_entries()) - 1), self.selected_index + 1
                )
                self.detail_scroll = 0
            elif event.unicode and event.unicode.isprintable():
                self.search_text += event.unicode
                self.selected_index = self.detail_scroll = 0
            return True
        if event.type == pygame.MOUSEWHEEL:
            if self.detail_rect.collidepoint(pygame.mouse.get_pos()):
                self.detail_scroll = max(0, self.detail_scroll - event.y)
            else:
                self.selected_index = max(
                    0, min(len(self.filtered_entries()) - 1, self.selected_index - event.y)
                )
            return True
        if event.type not in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            return False
        if event.type == pygame.MOUSEBUTTONUP or event.button != 1:
            return True
        if self.close_rect.collidepoint(event.pos) or not self.rect.collidepoint(event.pos):
            self.close()
            return True
        for index, rect in enumerate(self.category_rects):
            if rect.collidepoint(event.pos):
                self.category_index = index
                self.selected_index = self.detail_scroll = 0
                return True
        if self.list_rect.collidepoint(event.pos):
            row_height = 32
            index = (event.pos[1] - self.list_rect.top) // row_height
            self.selected_index = min(
                max(0, len(self.filtered_entries()) - 1), self.first_visible_index() + index
            )
            self.detail_scroll = 0
        return True

    def first_visible_index(self):
        visible = max(1, self.list_rect.height // 32)
        return max(0, min(
            self.selected_index - visible + 1,
            self.selected_index,
        ))

    @staticmethod
    def _wrap(text, font, width):
        lines = []
        for paragraph in text.splitlines() or [""]:
            words = paragraph.split()
            if not words:
                lines.append("")
                continue
            current = words[0]
            for word in words[1:]:
                candidate = f"{current} {word}"
                if font.size(candidate)[0] <= width:
                    current = candidate
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
        return lines

    def draw(self, screen):
        if not self.is_open:
            return
        shade = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        screen.blit(shade, (0, 0))
        pygame.draw.rect(screen, (29, 31, 38), self.rect, border_radius=10)
        pygame.draw.rect(screen, (145, 145, 175), self.rect, 2, border_radius=10)
        screen.blit(self.title_font.render("Библиотека мира", True, (225, 225, 245)),
                    (self.rect.left + 24, self.rect.top + 16))
        pygame.draw.rect(screen, (80, 54, 58), self.close_rect, border_radius=5)
        screen.blit(self.font.render("×", True, (255, 255, 255)),
                    self.font.render("×", True, (255, 255, 255)).get_rect(center=self.close_rect.center))
        pygame.draw.rect(screen, (20, 22, 28), self.search_rect, border_radius=5)
        pygame.draw.rect(screen, (95, 100, 120), self.search_rect, 1, border_radius=5)
        search_label = f"Поиск: {self.search_text or 'введите название или эффект…'}"
        screen.blit(self.small_font.render(search_label, True, (200, 205, 220)),
                    (self.search_rect.left + 10, self.search_rect.top + 8))

        for index, (category, rect) in enumerate(zip(self.CATEGORIES, self.category_rects)):
            draw_button(screen, rect, category, self.small_font,
                        color=(90, 92, 125) if index == self.category_index else (48, 51, 64),
                        hover_color=(105, 108, 145))
        pygame.draw.rect(screen, (22, 24, 30), self.list_rect, border_radius=6)
        pygame.draw.rect(screen, (75, 78, 91), self.list_rect, 1, border_radius=6)
        entries = self.filtered_entries()
        visible_rows = max(1, self.list_rect.height // 32)
        first = self.first_visible_index()
        for row, entry_index in enumerate(range(first, min(first + visible_rows, len(entries)))):
            rect = pygame.Rect(self.list_rect.left + 4, self.list_rect.top + row * 32,
                               self.list_rect.width - 8, 30)
            selected = entry_index == self.selected_index
            if selected:
                pygame.draw.rect(screen, (63, 66, 83), rect, border_radius=4)
            label = entries[entry_index]["name"]
            available_width = rect.width - 14
            while label and self.small_font.size(label)[0] > available_width:
                label = label[:-2] + "…"
            screen.blit(self.small_font.render(label, True, (235, 235, 240)),
                        (rect.left + 7, rect.top + 6))

        pygame.draw.rect(screen, (22, 24, 30), self.detail_rect, border_radius=6)
        pygame.draw.rect(screen, (75, 78, 91), self.detail_rect, 1, border_radius=6)
        if not entries:
            description = "По запросу ничего не найдено."
            if self.category == "Предметы" and self.items_message:
                description = self.items_message
            title = "Нет записей"
        else:
            selected_index = min(self.selected_index, len(entries) - 1)
            entry = entries[selected_index]
            title, description = entry["name"], entry["description"]
        screen.blit(self.title_font.render(title, True, (225, 225, 245)),
                    (self.detail_rect.left + 18, self.detail_rect.top + 16))
        lines = self._wrap(description, self.font, self.detail_rect.width - 36)
        line_height = 24
        max_lines = max(1, (self.detail_rect.height - 64) // line_height)
        self.detail_scroll = min(self.detail_scroll, max(0, len(lines) - max_lines))
        for index, line in enumerate(lines[self.detail_scroll:self.detail_scroll + max_lines]):
            screen.blit(self.font.render(line, True, (205, 208, 220)),
                        (self.detail_rect.left + 18, self.detail_rect.top + 60 + index * line_height))
        if len(lines) > max_lines:
            footer = "Колесо мыши — прокрутка выбранной записи"
            screen.blit(self.small_font.render(footer, True, (135, 140, 158)),
                        (self.detail_rect.left + 18, self.detail_rect.bottom - 24))
