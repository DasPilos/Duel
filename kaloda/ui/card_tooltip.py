import pygame

from kaloda.combat.card_database import SALE_PRICE_COINS, Card
from kaloda.combat.physical_effects import describe_physical_card
from kaloda.currency import format_coins
from kaloda.ui.renderers.card_area import CardAreaRenderer


UNIVERSAL_CARD_DESCRIPTIONS = {
    "universal_trap": (
        "Размещает скрытую ловушку. Она срабатывает только когда на неё наступает "
        "противник, и наносит 19 урона без критического удара."
    ),
    "universal_barricade": (
        "Создаёт препятствие размером в 3 гекса на 8 ходов. Сквозь него нельзя "
        "перемещаться и применять карты."
    ),
    "universal_dash": "Перемещает персонажа на 3 гекса.",
    "universal_wolf": "Призывает волка с характеристиками волка Древнего энта.",
    "universal_roots_trap": (
        "Размещает ловушку. Наступивший на неё противник получает 8 урона и "
        "корни на 2 хода."
    ),
    "universal_resource_recovery": (
        "Восстанавливает 15% уникального ресурса. Следующий полученный урон "
        "увеличивается на 25%."
    ),
    "universal_knockback": "Наносит 12 урона без критического удара и отбрасывает цель на 3 гекса.",
    "universal_bonebreaker": (
        "Накладывает на цель сломанные кости на 2 хода. За каждое перемещение "
        "цель теряет 4% максимального здоровья."
    ),
    "universal_divine_healing": (
        "Восстанавливает выбранному союзнику 10 HP в начале каждого хода "
        "в течение 7 ходов (всего до 70 HP)."
    ),
    "universal_dreadful_corruption": (
        "Накладывает на врагов в радиусе 2 гексов: 4 огня, 4 яда, зелёный огонь, "
        "слабость (-20% исходящего урона), хрупкость (+20% входящего урона), "
        "потерю 10% уникального ресурса и оглушение."
    ),
    "universal_unstable_elixir": (
        "Трижды разыгрывает случайный положительный эффект и трижды случайный "
        "отрицательный: лечение/урон 10 HP (30%), случайное перемещение на 2 "
        "гекса (30%), щит 12 HP/защита -30% на 2 хода (15%), ресурс +/-10% "
        "(10%), регенерация 20 HP/коррозия 15 HP за 4 хода (5%). Эффекты "
        "могут повторяться; каждый бросок также может ничего не дать."
    ),
    "universal_evolution": (
        "Выберите союзника или призыв: максимальное HP увеличивается на 35 "
        "(призыву — на 20), затем он восстанавливает 5 HP в начале хода "
        "в течение 3 ходов."
    ),
    "universal_teleport": (
        "Телепортирует владельца на выбранный свободный гекс. Стоимость — "
        "3 маны за каждый пройденный гекс."
    ),
}

NECROMANCER_CARD_DESCRIPTIONS = {
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

RESOURCE_NAMES = {
    "mana": "маны",
    "rage": "ярости",
    "accuracy": "меткости",
    "concentration": "концентрации",
    "unique": "уникального ресурса",
}


def card_from_catalog(card_data):
    return Card(
        key=str(card_data.get("key", "")),
        name=str(card_data.get("name", "Карта")),
        group_name=str(card_data.get("group_name", "")),
        resource_type=str(card_data.get("resource_type", "unique")),
        resource_cost=int(card_data.get("resource_cost", 0)),
        effect_type=str(card_data.get("effect_type", "")),
        effect_data=dict(card_data.get("effect_data") or {}),
        effect_duration=int(card_data.get("effect_duration", 0) or 0),
        rarity=str(card_data.get("rarity", "unassigned")),
    )


def card_tooltip_lines(card):
    description = UNIVERSAL_CARD_DESCRIPTIONS.get(card.key)
    if description is None:
        if card.key in NECROMANCER_CARD_DESCRIPTIONS:
            description = NECROMANCER_CARD_DESCRIPTIONS[card.key]
        elif card.resource_type in ("rage", "accuracy", "concentration"):
            description = describe_physical_card(card)
        else:
            description = CardAreaRenderer._card_description(card)
    lines = [description]
    distance = card.effect_data.get("range")
    if distance is not None:
        lines.append(f"Дальность: {distance} гекс.")
    resource = (
        "некротизма" if card.group_name.startswith("Некромант:")
        else RESOURCE_NAMES.get(card.resource_type, card.resource_type)
    )
    lines.append(f"Стоимость розыгрыша: {card.resource_cost} {resource}.")
    rarity_labels = {
        "basic": "Базовая",
        "common": "Обычная",
        "rare": "Редкая",
        "epic": "Эпическая",
        "legendary": "Легендарная",
    }
    if card.rarity in rarity_labels:
        sale_price = format_coins(SALE_PRICE_COINS[card.rarity])
        lines.append(
            f"Редкость: {rarity_labels[card.rarity]}. Цена продажи: {sale_price}."
        )
    return lines


def _wrap_text(font, text, max_width):
    wrapped = []
    for paragraph in str(text).splitlines() or [""]:
        line = ""
        for word in paragraph.split():
            candidate = f"{line} {word}".strip()
            if line and font.size(candidate)[0] > max_width:
                wrapped.append(line)
                line = word
            else:
                line = candidate
        wrapped.append(line)
    return wrapped


def draw_card_tooltip(screen, card, position, font, max_width=420):
    body_lines = [
        line
        for paragraph in card_tooltip_lines(card)
        for line in _wrap_text(font, paragraph, max_width - 24)
    ]
    title_font = pygame.font.SysFont(None, font.get_height() + 4, bold=True)
    title = title_font.render(card.name, True, (255, 235, 180))
    line_height = font.get_linesize()
    padding = 12
    width = min(max_width, screen.get_width() - padding * 2)
    height = padding * 2 + title.get_height() + 6 + len(body_lines) * line_height
    x = position[0] + 16
    y = position[1] + 16
    if x + width > screen.get_width() - 6:
        x = position[0] - width - 16
    if y + height > screen.get_height() - 6:
        y = screen.get_height() - height - 6
    x = max(6, x)
    y = max(6, y)

    background = pygame.Surface((width, height), pygame.SRCALPHA)
    background.fill((28, 24, 38, 248))
    screen.blit(background, (x, y))
    pygame.draw.rect(screen, (185, 140, 220), pygame.Rect(x, y, width, height), 2, border_radius=6)
    screen.blit(title, (x + padding, y + padding))
    text_y = y + padding + title.get_height() + 6
    for line in body_lines:
        image = font.render(line, True, (230, 225, 238))
        screen.blit(image, (x + padding, text_y))
        text_y += line_height
