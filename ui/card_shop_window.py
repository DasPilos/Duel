"""Окно карточной лавки."""

import pygame

from core import settings
from client.network import ServerError
from ui.card_tooltip import card_from_catalog, draw_card_tooltip
from ui.hud import draw_button


CARD_CATEGORIES = (
    ("all", "Все"),
    ("movement", "Передвижение"),
    ("traps", "Ловушки"),
    ("damage", "Урон"),
    ("healing", "Лечение/ресурс"),
    ("defense", "Защита"),
    ("summons", "Призывы"),
    ("control", "Контроль"),
)

CARD_CLASSES = (
    ("all", "Все классы"),
    ("mage", "Маг"),
    ("warrior", "Воин"),
    ("archer", "Лучник"),
    ("assassin", "Ассасин"),
    ("necromancer", "Некромант"),
)
CARD_RARITIES = (
    ("common", "Обычная"),
    ("rare", "Редкая"),
    ("epic", "Эпическая"),
    ("legendary", "Легендарная"),
)
CARD_CLASS_LABELS = dict(CARD_CLASSES)
CARD_RARITY_LABELS = {
    "common": "Обычная",
    "rare": "Редкая",
    "epic": "Эпическая",
    "legendary": "Легендарная",
}

CARD_CATEGORY_BY_KEY = {
    "universal_dash": "movement",
    "universal_trap": "traps",
    "universal_roots_trap": "traps",
    "universal_knockback": "damage",
    "universal_bonebreaker": "control",
    "universal_resource_recovery": "healing",
    "universal_necrotic_activity": "healing",
    "universal_barricade": "defense",
    "universal_wolf": "summons",
    "universal_divine_healing": "healing",
    "universal_dreadful_corruption": "damage",
    "universal_unstable_elixir": "healing",
    "universal_evolution": "healing",
    "universal_teleport": "movement",
    "mage_shift": "movement",
    "mage_mana_charge": "damage",
    "mage_mana_burst": "damage",
    "mage_mana_shield": "defense",
    "mage_heal": "healing",
    "mage_force_push": "damage",
    "mage_flow": "healing",
    "mage_next_attack": "damage",
    "mage_arcane_beam": "damage",
    "warrior_lunge": "damage",
    "warrior_power_attack": "damage",
    "warrior_circular_sweep": "damage",
    "warrior_bandages": "healing",
    "warrior_block": "defense",
    "warrior_adaptation": "healing",
    "warrior_vulnerability_strike": "damage",
    "warrior_dash_strike": "damage",
    "archer_shot": "damage",
    "archer_aimed_shot": "damage",
    "archer_arrow_hail": "damage",
    "archer_bandages": "healing",
    "archer_agility": "defense",
    "archer_heightened_attention": "healing",
    "archer_weak_point": "damage",
    "archer_lightning_shot": "damage",
    "assassin_throw_blade": "damage",
    "assassin_hidden_lunge": "damage",
    "assassin_dagger_hail": "damage",
    "assassin_healing": "healing",
    "assassin_stealth": "defense",
    "assassin_observation": "healing",
    "assassin_experience": "damage",
    "assassin_fatal_strike": "damage",
    "necromancer_skull_throw": "damage",
    "necromancer_otherworldly_beam": "damage",
    "necromancer_area_of_suffering": "damage",
    "necromancer_bond": "healing",
    "necromancer_fear_shield": "defense",
    "necromancer_fear_sense": "healing",
    "necromancer_max_health": "defense",
    "necromancer_torment": "damage",
}


def _card_description(card):
    data = card.get("effect_data") or {}
    key = card.get("key")
    descriptions = {
        "universal_trap": "Ловушка: 19 урона без крита при наступании врага",
        "universal_barricade": "Баррикада на 3 гекса, 8 ходов; блокирует движение и карты",
        "universal_dash": "Перемещение на 3 гекса",
        "universal_wolf": "Призывает волка с характеристиками волка Древнего ента",
        "universal_roots_trap": "Ловушка: 8 урона и корни на 2 хода",
        "universal_resource_recovery": "Восстанавливает 15% ресурса; следующий урон +25%",
        "universal_knockback": "12 урона без крита и отбрасывание на 3 гекса",
        "mage_mana_charge": "Урон 5",
        "mage_mana_burst": "Урон 10 по области",
        "mage_mana_shield": "Щит 8 HP + Интеллект",
        "mage_heal": "Лечение 12 HP",
        "mage_force_push": "Урон 8 и отбрасывание на 1 гекс",
        "mage_flow": "+10 маны",
        "mage_next_attack": "Следующая атака +5 урона",
        "mage_arcane_beam": "Линейная атака: 22 урона",
        "warrior_lunge": "Урон 6",
        "warrior_power_attack": "Урон 11",
        "warrior_circular_sweep": "Урон 6 вокруг бойца",
        "warrior_bandages": "Лечение 13 HP",
        "warrior_block": "Щит 8 HP + Выносливость",
        "warrior_adaptation": "+6 ярости и 5 HP",
        "warrior_vulnerability_strike": "Следующая атака +5 урона",
        "warrior_dash_strike": "Рывок и урон 18 по области",
        "archer_shot": "Урон 6",
        "archer_aimed_shot": "Урон 11",
        "archer_arrow_hail": "Урон 6 по области",
        "archer_bandages": "Лечение 10 HP",
        "archer_agility": "+15% уклонения на 2 хода",
        "archer_heightened_attention": "+11 меткости",
        "archer_weak_point": "Следующая атака +5 урона",
        "archer_lightning_shot": "Урон 29 по всей арене, нельзя увернуться",
        "assassin_throw_blade": "Урон 6",
        "assassin_hidden_lunge": "Урон 11",
        "assassin_dagger_hail": "Урон 7 по области",
        "assassin_healing": "Лечение 10 HP",
        "assassin_stealth": "+8% уклонения на 3 хода",
        "assassin_observation": "+6 концентрации, следующая атака +2 урона",
        "assassin_experience": "Следующая атака: +10% шанса крита и +25% крит. урона",
        "assassin_fatal_strike": "Урон 18, усиленный критический удар",
        "necromancer_skull_throw": "Урон 5",
        "necromancer_otherworldly_beam": "Урон 10",
        "necromancer_area_of_suffering": "Урон 7 по области",
        "necromancer_bond": "Лечение союзников на 6 HP",
        "necromancer_fear_shield": "Щит 8 HP + Интеллект",
        "necromancer_fear_sense": "+10 некротизма",
        "necromancer_max_health": "Максимальное HP +7 + Гармония",
        "necromancer_torment": "Урон 10 и 2 зелёного огня",
    }
    description = descriptions.get(key, card.get("name", "Карта"))
    card_range = data.get("range")
    range_text = (
        "Дальность: вся арена"
        if card_range is None and key in {"archer_lightning_shot", "necromancer_bond"}
        else f"Дальность: {card_range} гекс."
        if card_range is not None
        else ""
    )
    details = [part for part in (description, range_text) if part]
    return f"{'. '.join(details)}; ресурс: {card.get('resource_cost', 0)}"


class CardShopWindow:
    WIDTH = 950
    HEIGHT = 670
    ROW_HEIGHT = 48
    ROW_GAP = 5
    CONTENT_TOP = 190
    CONTENT_BOTTOM = HEIGHT - 74

    def __init__(self, scene):
        self.scene = scene
        self.is_open = False
        self.cards = []
        self.collection = []
        self.owned = {}
        self.mode = "buy"
        self.selected_index = 0
        self.selected_category = "all"
        self.selected_class = "all"
        self.selected_rarity = None
        self.price_sort = "ascending"
        self.scroll_offset = 0
        self.message = None
        self.rect = pygame.Rect(0, 0, self.WIDTH, self.HEIGHT)
        self.rect.center = (settings.WIDTH // 2, settings.HEIGHT // 2)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 28, bold=True)
        self.font = pygame.font.SysFont(settings.FONT_NAME, 18)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 15)
        self.close_rect = pygame.Rect(self.rect.right - 46, self.rect.top + 12, 34, 34)
        self.buy_rect = pygame.Rect(self.rect.right - 220, self.rect.bottom - 62, 196, 42)
        self.mode_rect = pygame.Rect(self.rect.left + 20, self.rect.bottom - 62, 180, 42)
        self.price_sort_rect = pygame.Rect(self.rect.right - 250, self.rect.top + 50, 225, 24)
        self.class_rects = self._filter_rects(CARD_CLASSES, self.rect.top + 78)
        self.rarity_rects = self._filter_rects(CARD_RARITIES, self.rect.top + 104)
        self.category_rects = self._category_rects()

    def _filter_rects(self, options, top):
        gap = 4
        width = (self.rect.width - 40 - gap * (len(options) - 1)) // len(options)
        return {
            key: pygame.Rect(
                self.rect.left + 20 + index * (width + gap),
                top,
                width,
                22,
            )
            for index, (key, _) in enumerate(options)
        }

    def _category_rects(self):
        gap = 5
        columns = 4
        width = (self.rect.width - 40 - gap * (columns - 1)) // columns
        return {
            key: pygame.Rect(
                self.rect.left + 20 + index % columns * (width + gap),
                self.rect.top + 130 + index // columns * 26,
                width,
                22,
            )
            for index, (key, _) in enumerate(CARD_CATEGORIES)
        }

    @property
    def filtered_cards(self):
        source = self.cards if self.mode == "buy" else [
            card for card in self.collection
            if int(card.get("sale_price_coins", 0)) > 0
        ]
        filtered = [
            card for card in source
            if (
                self.selected_class == "all"
                or card.get("class_key", "universal") == self.selected_class
            )
            and (
                self.selected_rarity is None
                or card.get("rarity", "unassigned") == self.selected_rarity
            )
            and (
                self.selected_category == "all"
                or CARD_CATEGORY_BY_KEY.get(card.get("key"), "control")
                == self.selected_category
            )
        ]
        return sorted(
            filtered,
            key=lambda card: (
                int(card.get("price_coins" if self.mode == "buy" else "sale_price_coins", 0)) <= 0,
                int(card.get("price_coins" if self.mode == "buy" else "sale_price_coins", 0))
                if self.price_sort == "ascending"
                else -int(card.get("price_coins" if self.mode == "buy" else "sale_price_coins", 0)),
                str(card.get("name", "")),
            ),
        )

    @property
    def visible_row_count(self):
        return max(1, (self.CONTENT_BOTTOM - self.CONTENT_TOP + self.ROW_GAP)
                   // (self.ROW_HEIGHT + self.ROW_GAP))

    def open(self):
        self.is_open = True
        self.message = None
        client = getattr(self.scene.session, "client", None)
        character = getattr(self.scene.session, "character", None)
        try:
            self.cards = client.get_card_shop_catalog()
            self.collection = client.get_card_collection(character["id"])
            self.owned = {
                entry["card_key"]: int(entry.get("quantity", 0))
                for entry in self.collection
            }
        except (ServerError, AttributeError, KeyError, OSError) as error:
            self.cards = []
            self.collection = []
            self.owned = {}
            self.message = f"Не удалось загрузить ассортимент: {error}"
        self.selected_index = min(self.selected_index, max(0, len(self.filtered_cards) - 1))
        self.scroll_offset = 0

    def close(self):
        self.is_open = False

    def item_rows(self):
        count = min(self.visible_row_count, max(0, len(self.filtered_cards) - self.scroll_offset))
        return [
            pygame.Rect(
                self.rect.left + 20,
                self.rect.top + self.CONTENT_TOP + index * (self.ROW_HEIGHT + self.ROW_GAP),
                self.rect.width - 40,
                self.ROW_HEIGHT,
            )
            for index in range(count)
        ]

    def handle_event(self, event):
        if not self.is_open:
            return False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.close()
            return True
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_UP, pygame.K_DOWN):
            self._scroll(-1 if event.key == pygame.K_UP else 1)
            return True
        if event.type == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(pygame.mouse.get_pos()):
                self._scroll(-event.y)
            return True
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL, pygame.KEYDOWN)
        if self.close_rect.collidepoint(event.pos) or not self.rect.collidepoint(event.pos):
            self.close()
            return True
        for category, rect in self.category_rects.items():
            if rect.collidepoint(event.pos):
                self.selected_category = category
                self.selected_index = 0
                self.scroll_offset = 0
                self.message = None
                return True
        for options, rects, attribute in (
            (CARD_CLASSES, self.class_rects, "selected_class"),
            (CARD_RARITIES, self.rarity_rects, "selected_rarity"),
        ):
            for key, rect in rects.items():
                if rect.collidepoint(event.pos):
                    if attribute == "selected_rarity":
                        self.selected_rarity = (
                            None if self.selected_rarity == key else key
                        )
                    else:
                        setattr(self, attribute, key)
                    self.selected_index = 0
                    self.scroll_offset = 0
                    self.message = None
                    return True
        if self.price_sort_rect.collidepoint(event.pos):
            self.price_sort = (
                "descending" if self.price_sort == "ascending" else "ascending"
            )
            self.selected_index = 0
            self.scroll_offset = 0
            return True
        if self.mode_rect.collidepoint(event.pos):
            self.mode = "sell" if self.mode == "buy" else "buy"
            self.selected_index = 0
            self.scroll_offset = 0
            self.message = None
            return True
        for index, rect in enumerate(self.item_rows()):
            if rect.collidepoint(event.pos):
                self.selected_index = self.scroll_offset + index
                self.message = None
                return True
        if self.buy_rect.collidepoint(event.pos):
            self._sell() if self.mode == "sell" else self._buy()
        return True

    def _scroll(self, amount):
        maximum = max(0, len(self.filtered_cards) - self.visible_row_count)
        self.scroll_offset = max(0, min(maximum, self.scroll_offset + int(amount)))
        self.selected_index = max(
            self.scroll_offset,
            min(self.selected_index, max(self.scroll_offset, len(self.filtered_cards) - 1)),
        )

    def _buy(self):
        cards = self.filtered_cards
        if not cards:
            return
        character = getattr(self.scene.session, "character", None)
        if not isinstance(character, dict) or character.get("id") is None:
            self.message = "Персонаж не загружен"
            return
        card = cards[self.selected_index]
        if not card.get("available", False):
            self.message = "Покупка этой карты временно отключена"
            return
        try:
            result = self.scene.session.client.buy_card(character["id"], card["key"])
            character.update(result.get("character") or {})
            self.owned[card["key"]] = self.owned.get(card["key"], 0) + 1
            self.message = f"Куплено: {card['name']}"
        except (ServerError, AttributeError, KeyError, OSError) as error:
            self.message = f"Не удалось купить карту: {error}"

    def _sell(self):
        cards = self.filtered_cards
        if not cards:
            self.message = "Нет карт для продажи"
            return
        character = getattr(self.scene.session, "character", None)
        if not isinstance(character, dict) or character.get("id") is None:
            self.message = "Персонаж не загружен"
            return
        card = cards[self.selected_index]
        try:
            result = self.scene.session.client.sell_card(character["id"], card["key"])
            character.update(result.get("character") or {})
            self.collection = self.scene.session.client.get_card_collection(character["id"])
            self.owned = {
                entry["card_key"]: int(entry.get("quantity", 0))
                for entry in self.collection
            }
            self.selected_index = min(
                self.selected_index, max(0, len(self.filtered_cards) - 1)
            )
            self.scroll_offset = min(
                self.scroll_offset,
                max(0, len(self.filtered_cards) - self.visible_row_count),
            )
            self.message = (
                f"Продано: {card['name']} за "
                f"{int(result.get('sale_price_coins', 0))} монет"
            )
        except (ServerError, AttributeError, KeyError, OSError) as error:
            self.message = f"Не удалось продать карту: {error}"

    def draw(self, screen):
        if not self.is_open:
            return
        shade = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        screen.blit(shade, (0, 0))
        pygame.draw.rect(screen, (30, 24, 40), self.rect, border_radius=10)
        pygame.draw.rect(screen, (170, 115, 210), self.rect, 3, border_radius=10)
        screen.blit(self.title_font.render("Карточная лавка", True, (220, 175, 245)),
                    (self.rect.left + 22, self.rect.top + 16))
        character = getattr(self.scene.session, "character", None)
        balance = int(character.get("coins", 0)) if isinstance(character, dict) else 0
        screen.blit(self.small_font.render(
            f"У вас: {balance} монет", True, (240, 210, 115)
        ), (self.rect.left + 22, self.rect.top + 52))
        sort_label = (
            "ЦЕНА: СНАЧАЛА ДЕШЁВЫЕ"
            if self.price_sort == "ascending"
            else "ЦЕНА: СНАЧАЛА ДОРОГИЕ"
        )
        pygame.draw.rect(screen, (45, 37, 54), self.price_sort_rect, border_radius=5)
        pygame.draw.rect(screen, (95, 75, 110), self.price_sort_rect, 1, border_radius=5)
        sort_surface = self.small_font.render(sort_label, True, (245, 240, 250))
        screen.blit(sort_surface, sort_surface.get_rect(center=self.price_sort_rect.center))
        for options, rects, selected in (
            (CARD_CLASSES, self.class_rects, self.selected_class),
            (CARD_RARITIES, self.rarity_rects, self.selected_rarity),
        ):
            for key, label in options:
                rect = rects[key]
                active = key == selected
                pygame.draw.rect(
                    screen,
                    (95, 60, 125) if active else (45, 37, 54),
                    rect,
                    border_radius=5,
                )
                pygame.draw.rect(
                    screen,
                    (190, 145, 225) if active else (95, 75, 110),
                    rect,
                    1,
                    border_radius=5,
                )
                label_surface = self.small_font.render(label, True, (245, 240, 250))
                screen.blit(label_surface, label_surface.get_rect(center=rect.center))
        for category, label in CARD_CATEGORIES:
            rect = self.category_rects[category]
            active = category == self.selected_category
            pygame.draw.rect(
                screen,
                (95, 60, 125) if active else (45, 37, 54),
                rect,
                border_radius=5,
            )
            pygame.draw.rect(
                screen,
                (190, 145, 225) if active else (95, 75, 110),
                rect,
                1,
                border_radius=5,
            )
            label_surface = self.small_font.render(label, True, (245, 240, 250))
            screen.blit(label_surface, label_surface.get_rect(center=rect.center))
        pygame.draw.rect(screen, (120, 60, 50), self.close_rect, border_radius=6)
        screen.blit(self.font.render("×", True, (255, 255, 255)),
                    self.font.render("×", True, (255, 255, 255)).get_rect(center=self.close_rect.center))
        cards = self.filtered_cards
        rows = self.item_rows()
        hovered_card = None
        mouse_pos = pygame.mouse.get_pos()
        for row_index, (card, row) in enumerate(
            zip(cards[self.scroll_offset:], rows)
        ):
            selected = self.scroll_offset + row_index == self.selected_index
            pygame.draw.rect(screen, (65, 48, 78) if selected else (42, 36, 52), row, border_radius=6)
            pygame.draw.rect(screen, (190, 145, 225) if selected else (95, 75, 110), row, 2, border_radius=6)
            screen.blit(self.font.render(card["name"], True, (245, 240, 250)),
                        (row.left + 10, row.top + 4))
            description = _card_description(card)
            description_surface = self.small_font.render(description, True, (205, 195, 215))
            available_width = row.width - 20
            if description_surface.get_width() > available_width:
                while description and self.small_font.size(description + "…")[0] > available_width:
                    description = description[:-1]
                description += "…"
            screen.blit(self.small_font.render(description, True, (205, 195, 215)),
                        (row.left + 10, row.top + 28))
            owned = self.owned.get(card["key"], 0)
            class_label = CARD_CLASS_LABELS.get(
                card.get("class_key", "universal"), "Универсальные"
            )
            rarity_label = CARD_RARITY_LABELS.get(
                card.get("rarity", "unassigned"), "Не назначена"
            )
            if self.mode == "sell":
                price = f"продажа: {int(card.get('sale_price_coins', 0))} монет"
            else:
                price = (
                    f"{int(card.get('price_coins', 0))} монет"
                    if card.get("available")
                    else "без цены"
                )
            status = f"{class_label} · {rarity_label} · x{owned} · {price}"
            text = self.small_font.render(status, True, (240, 210, 115))
            screen.blit(text, (row.right - text.get_width() - 10, row.top + 7))
            if row.collidepoint(mouse_pos):
                hovered_card = card
        if len(cards) > self.visible_row_count:
            scroll_label = self.small_font.render(
                f"{self.scroll_offset + 1}–{min(len(cards), self.scroll_offset + self.visible_row_count)} / {len(cards)}",
                True,
                (190, 180, 200),
            )
            screen.blit(scroll_label, (self.rect.left + 22, self.rect.bottom - 54))
        draw_button(screen, self.buy_rect, "КУПИТЬ" if self.mode == "buy" else "ПРОДАТЬ", self.font,
                    color=(95, 60, 125) if self.mode == "buy" else (80, 125, 82),
                    hover_color=(125, 80, 160) if self.mode == "buy" else (100, 155, 102))
        draw_button(
            screen,
            self.mode_rect,
            "РЕЖИМ: ПОКУПКА" if self.mode == "buy" else "РЕЖИМ: ПРОДАЖА",
            self.small_font,
            color=(95, 60, 125) if self.mode == "buy" else (80, 125, 82),
            hover_color=(125, 80, 160) if self.mode == "buy" else (100, 155, 102),
        )
        if self.message:
            screen.blit(self.small_font.render(self.message, True, (245, 220, 150)),
                        (self.rect.left + 22, self.rect.bottom - 52))
        if hovered_card is not None:
            draw_card_tooltip(
                screen,
                card_from_catalog(hovered_card),
                mouse_pos,
                self.small_font,
            )
