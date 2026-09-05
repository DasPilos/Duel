import math
import random
import re

from combat.card_database import load_cards
from combat.mechanics import get_critical_chance, get_dodge_chance
from combat.progression import apply_xp, battle_xp


STAT_NAMES = ("strength", "intuition", "agility", "endurance")
# Карты, наносящие урон; остальные типы считаются баффами и применяются до них.
ATTACK_EFFECT_TYPES = (
    "damage",
    "damage_dodge",
    "damage_recoil",
    "damage_reduce",
    "damage_stat_debuff",
    "damage_critical_debuff",
    "damage_dodge_debuff",
    "damage_dodge_critical_debuff",
)
def build_battle_deck(cards, player_level, enemy_level, rng=None):
    if not cards:
        return []
    rng = random if rng is None else rng
    deck = list(cards)
    rng.shuffle(deck)
    return deck


def points_from_stat(value, rng=None):
    rng = random if rng is None else rng
    guaranteed, remainder = divmod(max(0, int(value)), 4)
    return guaranteed + int(rng.random() < remainder * 0.25)


def roll_dice(expression, rng=None):
    rng = random if rng is None else rng
    match = re.fullmatch(r"(\d+)d(\d+)", expression)
    if match is None:
        raise ValueError(f"Некорректная запись броска: {expression}")
    count, sides = (int(part) for part in match.groups())
    return sum(rng.randint(1, sides) for _ in range(count))


class CardBattle:
    MAX_PLAYED_CARDS = 2
    MAX_HAND_SIZE = 6
    STARTING_TABLE_SIZE = 10
    STARTING_PICK_LIMIT = 3
    REDRAFT_TABLE_SIZE = 6
    REDRAFT_PICK_LIMIT = 2

    def __init__(self, player, enemy, cards=None, rng=None):
        self.player = player
        self.enemy = enemy
        self.rng = random if rng is None else rng
        self.cards = list(cards if cards is not None else load_cards())
        self.discard = []
        self.table = []
        self.hands = {"player": [], "enemy": []}
        self.selected = {"player": [], "enemy": []}
        self.instant_played = {"player": [], "enemy": []}
        self.instant_events = {"player": [], "enemy": []}
        self.confirmed = {"player": False, "enemy": False}
        self.action_points = {
            "player": {stat: 0 for stat in STAT_NAMES},
            "enemy": {stat: 0 for stat in STAT_NAMES},
        }
        self.turn = 0
        self.history = []
        self.last_exchange = []
        self.last_played_cards = {"player": [], "enemy": []}
        self.starting_reserved_keys = set()
        self.starting_bonus_awarded = False
        self.starting_bonus_side = None
        self.draft_mode = "starting"
        self.redraft_picks = {"player": 0, "enemy": 0}
        self.redraft_pick_limits = {
            "player": self.REDRAFT_PICK_LIMIT,
            "enemy": self.REDRAFT_PICK_LIMIT,
        }
        self.draft_bonus_awarded = False
        self.second_chance_used = {"player": False, "enemy": False}
        self.turn_points = {"player": {}, "enemy": {}}
        self.regen_effects = {"player": [], "enemy": []}
        self.timed_stat_effects = {"player": [], "enemy": []}
        self.timed_critical_effects = {"player": [], "enemy": []}
        self.timed_dodge_effects = {"player": [], "enemy": []}
        self.reward_card_keys = ()
        self.stats = {
            "player": {"cards_played": 0, "damage": 0, "healed": 0, "critical": 0, "dodges": 0, "hits": 0, "cards": [], "card_damage": {}},
            "enemy": {"cards_played": 0, "damage": 0, "healed": 0, "critical": 0, "dodges": 0, "hits": 0, "cards": [], "card_damage": {}},
        }
        self._xp_awarded_applied = False
        if not self.cards:
            self.deck = []
            return
        if len(self.cards) < self.STARTING_TABLE_SIZE:
            self.deck = []
            return

        self.deck = build_battle_deck(self.cards, player.level, enemy.level, self.rng)
        if len(self.deck) < self.STARTING_TABLE_SIZE:
            self.deck = []
            return
        self.reward_card_keys = tuple(dict.fromkeys(card.key for card in self.deck))
        self._prepare_starting_table()

    def _prepare_starting_table(self):
        if not self.deck:
            self.table = []
            return
        self.rng.shuffle(self.deck)
        self.table = [self._draw_card() for _ in range(self.STARTING_TABLE_SIZE)]

    def _draw_card(self):
        if not self.deck:
            return None
        return self.deck.pop()

    def _shuffle_discard_into_deck(self):
        self.deck.extend(self.discard)
        self.discard.clear()
        self.rng.shuffle(self.deck)

    def choose_starting_card(self, side, card_key):
        self._validate_side(side)
        if self.turn or len(self.hands[side]) >= self.STARTING_PICK_LIMIT:
            raise ValueError("Стартовая раздача уже завершена")
        card = next((item for item in self.table if item.key == card_key), None)
        if card is None:
            raise ValueError("Карты нет на столе")
        if side == "enemy":
            self.starting_reserved_keys.add(card.key)
        self.table.remove(card)
        self.hands[side].append(card)

    def finish_starting_deal(self):
        if self.turn or any(len(self.hands[side]) < self.STARTING_PICK_LIMIT for side in self.hands):
            raise ValueError("Каждый боец должен выбрать минимум три карты")
        stronger_side = self._stronger_side("agility")
        if not self.starting_bonus_awarded and stronger_side is not None and self.table:
            bonus_card = self.table.pop(self.rng.randrange(len(self.table)))
            self.hands[stronger_side].append(bonus_card)
            self.starting_bonus_awarded = True
            self.starting_bonus_side = stronger_side
        self.deck.extend(card for card in self.table if card.key not in self.starting_reserved_keys)
        self.starting_reserved_keys.clear()
        self.table.clear()
        self.draft_mode = None
        self._start_turn(draw_cards=False)

    def starting_deal_complete(self):
        return all(len(self.hands[side]) >= self.STARTING_PICK_LIMIT for side in self.hands)

    def finish_afk_starting_deal(self):
        if self.turn:
            raise ValueError("Стартовая раздача уже завершена")
        self.hands["player"].clear()
        while len(self.hands["enemy"]) < self.STARTING_PICK_LIMIT and self.table:
            self.choose_starting_card("enemy", self.table[0].key)
        self.deck.extend(self.table)
        self.table.clear()
        self.starting_reserved_keys.clear()
        self.draft_mode = None
        self._start_turn(draw_cards=False)

    def can_prepare_redraft(self):
        return (
            self.draft_mode is None
            and not self.deck
            and len(self.discard) >= self.REDRAFT_TABLE_SIZE
        )

    def draft_first_side(self):
        return self._stronger_side("intuition") or "player"

    def prepare_redraft(self):
        if not self.can_prepare_redraft():
            return False
        self._shuffle_discard_into_deck()
        self.table = [
            self._draw_card()
            for _ in range(self.REDRAFT_TABLE_SIZE)
        ]
        self.redraft_picks = {"player": 0, "enemy": 0}
        self.redraft_pick_limits = {
            side: min(
                self.REDRAFT_PICK_LIMIT,
                self.MAX_HAND_SIZE - len(self.hands[side]),
            )
            for side in ("player", "enemy")
        }
        self.draft_bonus_awarded = False
        self.draft_mode = "redraft"
        return True

    def choose_redraft_card(self, side, card_key):
        self._validate_side(side)
        if self.draft_mode != "redraft":
            raise ValueError("Повторный драфт сейчас не проводится")
        if self.redraft_picks[side] >= self.redraft_pick_limits[side]:
            raise ValueError("Рука заполнена или игрок уже выбрал доступные карты")
        card = next((item for item in self.table if item.key == card_key), None)
        if card is None:
            raise ValueError("Карты нет на столе")
        self.table.remove(card)
        self.hands[side].append(card)
        self.redraft_picks[side] += 1

    def current_draft_complete(self):
        if self.draft_mode == "starting":
            return self.starting_deal_complete()
        if self.draft_mode == "redraft":
            return all(
                self.redraft_picks[side] >= self.redraft_pick_limits[side]
                for side in ("player", "enemy")
            )
        return False

    def take_draft_bonus_card(self):
        if (
            not self.current_draft_complete()
            or self.draft_bonus_awarded
            or not self.table
        ):
            return None
        stronger_side = self._stronger_side("agility")
        if (
            stronger_side is None
            or len(self.hands[stronger_side]) >= self.MAX_HAND_SIZE
        ):
            self.draft_bonus_awarded = True
            return None
        bonus_card = self.table.pop(self.rng.randrange(len(self.table)))
        self.draft_bonus_awarded = True
        return stronger_side, bonus_card

    def finish_redraft(self):
        if self.draft_mode != "redraft" or not self.current_draft_complete():
            raise ValueError("Повторный драфт ещё не завершён")
        self.deck.extend(self.table)
        self.table.clear()
        self.draft_mode = None
        return self._start_turn(draw_cards=False)

    def finish_afk_redraft(self):
        if self.draft_mode != "redraft":
            raise ValueError("Повторный драфт сейчас не проводится")
        side = self.draft_first_side()
        while not self.current_draft_complete():
            if self.redraft_picks[side] < self.redraft_pick_limits[side]:
                card = self.table[self.rng.randrange(len(self.table))]
                self.choose_redraft_card(side, card.key)
            side = "enemy" if side == "player" else "player"
        bonus = self.take_draft_bonus_card()
        if bonus is not None:
            side, card = bonus
            self.hands[side].append(card)
        return self.finish_redraft()

    def _auto_finish_redraft(self):
        if not self.prepare_redraft():
            return None
        return self.finish_afk_redraft()

    def _start_turn(self, draw_cards=True):
        self.turn += 1
        if draw_cards:
            self.draw_next_turn_card("player")
            self.draw_next_turn_card("enemy")
        gained_points = {"player": {}, "enemy": {}}
        for side, fighter in (("player", self.player), ("enemy", self.enemy)):
            fighter.card_dodge_bonus = 0
            fighter.card_anti_dodge_bonus = 0
            fighter.card_critical_bonus = 0
            fighter.card_damage_ratio = 1
            fighter.card_damage_reduce = 0
            for stat in STAT_NAMES:
                gained = points_from_stat(getattr(fighter, stat), self.rng)
                self.action_points[side][stat] += gained
                gained_points[side][stat] = gained
        self.turn_points = {side: dict(values) for side, values in gained_points.items()}
        for side, fighter in (("player", self.player), ("enemy", self.enemy)):
            for effect in self.regen_effects[side][:]:
                before = fighter.hp
                fighter.hp = min(fighter.max_hp, fighter.hp + roll_dice(effect["dice"], self.rng))
                effect["remaining"] -= 1
                if fighter.hp > before:
                    self.history.append({"turn": self.turn, "events": [{"side": side, "card": "Регенерация", "damage": 0, "healed": fighter.hp - before}]})
                if effect["remaining"] <= 0:
                    self.regen_effects[side].remove(effect)
        self.selected = {"player": [], "enemy": []}
        self.instant_played = {"player": [], "enemy": []}
        self.instant_events = {"player": [], "enemy": []}
        self.confirmed = {"player": False, "enemy": False}
        return gained_points

    def select_card(self, side, card_key):
        self._validate_side(side)
        if (
            self.confirmed[side]
            or self._cards_used_this_exchange(side) >= self.MAX_PLAYED_CARDS
        ):
            return False
        card = next((item for item in self.hands[side] if item.key == card_key), None)
        if card is None or card in self.selected[side] or not self.can_select(side, card):
            return False
        self.selected[side].append(card)
        return True

    def deselect_card(self, side, card_key):
        self._validate_side(side)
        for card in self.selected[side]:
            if card.key == card_key:
                self.selected[side].remove(card)
                return True
        return False

    def can_play(self, side, card):
        self._validate_side(side)
        return all(self.action_points[side][stat] >= cost for stat, cost in card.costs.items())

    def can_select(self, side, card):
        self._validate_side(side)
        if (
            card.effect_type.startswith("instant_")
            or self._cards_used_this_exchange(side) >= self.MAX_PLAYED_CARDS
        ):
            return False
        used = {stat: sum(item.costs[stat] for item in self.selected[side]) for stat in STAT_NAMES}
        return all(self.action_points[side][stat] - used[stat] >= cost for stat, cost in card.costs.items())

    def can_activate_instant(self, side, card):
        self._validate_side(side)
        if (
            self.confirmed[side]
            or not card.effect_type.startswith("instant_")
            or card not in self.hands[side]
            or card in self.selected[side]
            or self._cards_used_this_exchange(side) >= self.MAX_PLAYED_CARDS
        ):
            return False
        reserved = {
            stat: sum(item.costs[stat] for item in self.selected[side])
            for stat in STAT_NAMES
        }
        return all(
            self.action_points[side][stat] - reserved[stat] >= cost
            for stat, cost in card.costs.items()
        )

    def activate_instant_card(self, side, card_key):
        self._validate_side(side)
        card = next(
            (item for item in self.hands[side] if item.key == card_key),
            None,
        )
        if card is None or not self.can_activate_instant(side, card):
            return None

        self._spend_points(side, card)
        if card.effect_type == "instant_action_points":
            stat_name = card.effect_data["stat"]
            if stat_name not in STAT_NAMES:
                raise ValueError(f"Неизвестный тип очков действия: {stat_name}")
            amount = max(0, int(card.effect_data["amount"]))
            self.action_points[side][stat_name] += amount
            effect_text = f"+{amount} {self._stat_label(stat_name)}"
        else:
            raise ValueError(f"Неизвестный тип мгновенной карты: {card.effect_type}")

        event = {
            "side": side,
            "card": card.name,
            "damage": 0,
            "healed": 0,
            "dodge_bonus": 0,
            "effect_text": effect_text,
            "critical": False,
            "dodged": False,
            "hits": 0,
            "attack": False,
            "instant": True,
        }
        self.hands[side].remove(card)
        self.discard.append(card)
        self.instant_played[side].append(card)
        self.instant_events[side].append(event)
        stats = self.stats[side]
        stats["cards_played"] += 1
        stats["cards"].append(card.name)
        stats["card_damage"].setdefault(card.name, 0)
        return event

    def _cards_used_this_exchange(self, side):
        return len(self.selected[side]) + len(self.instant_played[side])

    def remaining_card_slots(self, side):
        self._validate_side(side)
        return max(
            0,
            self.MAX_PLAYED_CARDS - self._cards_used_this_exchange(side),
        )

    def confirm_selection(self, side):
        self._validate_side(side)
        self.confirmed[side] = True
        return True

    def resolve_turn(self):
        if self.is_over() or not all(self.confirmed.values()):
            return []
        order = ("player", "enemy") if self.player.agility >= self.enemy.agility else ("enemy", "player")
        self.last_exchange = [
            event
            for side in ("player", "enemy")
            for event in self.instant_events[side]
        ]
        self.last_played_cards = {
            "player": list(self.instant_played["player"]) + list(self.selected["player"]),
            "enemy": list(self.instant_played["enemy"]) + list(self.selected["enemy"]),
        }
        for side in ("player", "enemy"):
            if not self.selected[side] and not self.instant_events[side]:
                self.last_exchange.append({
                    "side": side,
                    "card": None,
                    "damage": 0,
                    "healed": 0,
                    "critical": False,
                    "dodged": False,
                    "skipped": True,
                })
        for side in order:
            defender_side = "enemy" if side == "player" else "player"
            played_cards = list(self.selected[side])
            # Сначала все карты-эффекты (баффы/дебафы), потом все карты-атаки — независимо от порядка
            # клика, чтобы все статы хода складывались в один размен.
            buff_cards = [card for card in played_cards if card.effect_type not in ATTACK_EFFECT_TYPES]
            attack_cards = [card for card in played_cards if card.effect_type in ATTACK_EFFECT_TYPES]
            events_by_key = {}
            for card in buff_cards + attack_cards:
                events_by_key[card.key] = self._resolve_card(side, card)
            side_events = [events_by_key[card.key] for card in played_cards]
            for card, event in zip(played_cards, side_events):
               stats = self.stats[side]
               stats["cards_played"] += 1
               stats["damage"] += event["damage"]
               stats["healed"] += event["healed"]
               stats["critical"] += int(event["critical"])
               # dodged означает, что атаку увернулся защищающийся, а не атакующий.
               if event["dodged"]:
                   self.stats[defender_side]["dodges"] += 1
               stats["hits"] += event.get("hits", 0)
               card_name = event["card"]
               stats["cards"].append(card_name)
               # Сохраняем урон каждой карты (может быть > 1 для комбо)
               if card_name not in stats["card_damage"]:
                   stats["card_damage"][card_name] = 0
               stats["card_damage"][card_name] += event["damage"]
               if card in self.hands[side]:
                   self.hands[side].remove(card)
               self.discard.append(card)
            # Обнуляем бонусы ПОСЛЕ всех карт стороны
            attacker = self.player if side == "player" else self.enemy
            attacker.card_critical_bonus = 0
            attacker.card_anti_dodge_bonus = 0
            if side_events:
               self.last_exchange.append({
                   "side": side,
                   "card": " + ".join(event["card"] for event in side_events),
                   "damage": sum(event["damage"] for event in side_events),
                   "healed": sum(event["healed"] for event in side_events),
                   "dodge_bonus": sum(event.get("dodge_bonus", 0) for event in side_events),
                    "effect_text": " + ".join(event.get("effect_text", "") for event in side_events if event.get("effect_text")),
                    "effect_cards": [
                        event["card"] for event in side_events
                        if event.get("dodge_bonus", 0) or event.get("effect_text")
                    ],
                    "critical": any(event["critical"] for event in side_events),
                    "dodged": all(event["dodged"] for event in side_events),
                    "critical_attack": any(event.get("attack") and event["critical"] for event in side_events),
                    "attack_dodged": any(event.get("attack") and event["dodged"] for event in side_events),
                    "cards": [event["card"] for event in side_events],
                })
        for side in ("player", "enemy"):
            for card in self.last_played_cards[side]:
                if card in self.hands[side]:
                    self.hands[side].remove(card)
                    self.discard.append(card)
        self._expire_timed_stat_effects()
        self.history.append({"turn": self.turn, "events": list(self.last_exchange)})
        if self.is_over():
            self.outcome()
        return self.last_exchange

    def start_next_turn(self):
        if self.is_over():
            return {"player": {}, "enemy": {}}
        redraft_points = self._auto_finish_redraft()
        if redraft_points is not None:
            return redraft_points
        return self._start_turn(draw_cards=True)

    def begin_next_turn(self):
        if self.is_over():
            return {"player": {}, "enemy": {}}
        return self._start_turn(draw_cards=False)

    def draw_next_turn_card(self, side):
        self._validate_side(side)
        if len(self.hands[side]) >= self.MAX_HAND_SIZE:
            return None
        card = self._draw_card()
        if card is not None:
            self.hands[side].append(card)
        return card

    def can_draw_next_turn_card(self, side):
        self._validate_side(side)
        return bool(self.deck) and len(self.hands[side]) < self.MAX_HAND_SIZE

    def redraft_pick_limit(self, side):
        self._validate_side(side)
        return self.redraft_pick_limits[side]

    def peek_card(self):
        return self.deck[-1] if self.deck else None

    def _resolve_card(self, side, card):
        attacker = self.player if side == "player" else self.enemy
        defender = self.enemy if side == "player" else self.player
        data = card.effect_data
        event = {"side": side, "card": card.name, "damage": 0, "healed": 0, "dodge_bonus": 0, "effect_text": "", "critical": False, "dodged": False, "hits": 0, "attack": card.effect_type in ATTACK_EFFECT_TYPES}
        self._spend_points(side, card)

        if card.effect_type == "heal":
            before = attacker.hp
            attacker.hp = min(attacker.max_hp, attacker.hp + roll_dice(data["dice"], self.rng))
            event["healed"] = attacker.hp - before
            return event
        if card.effect_type == "heal_duration":
            before = attacker.hp
            attacker.hp = min(attacker.max_hp, attacker.hp + roll_dice(data["dice"], self.rng))
            event["healed"] = attacker.hp - before
            self.regen_effects[side].append({
                "dice": data["dice"],
                "remaining": max(0, card.effect_duration - 1),
            })
            return event
        if card.effect_type == "extra_action_points":
            if not self.second_chance_used[side]:
                for stat, points in self.turn_points[side].items():
                    self.action_points[side][stat] += points
                self.second_chance_used[side] = True
                event["effect_text"] = "ОЧКИ ХОДА ПОВТОРНО"
            else:
                event["effect_text"] = "ОЧКИ ХОДА УЖЕ ИСПОЛЬЗОВАНЫ"
            return event
        if card.effect_type == "dodge":
            attacker.card_dodge_bonus = getattr(attacker, "card_dodge_bonus", 0) + data["bonus"]
            event["dodge_bonus"] = data["bonus"]
            return event
        if card.effect_type == "anti_dodge":
            attacker.card_anti_dodge_bonus = getattr(attacker, "card_anti_dodge_bonus", 0) + data["bonus"]
            attacker.card_critical_bonus = getattr(attacker, "card_critical_bonus", 0) + data.get("critical_bonus", 0)
            effect_parts = [f"-{data['bonus']}% УВОРОТ"]
            if data.get("critical_bonus", 0):
                effect_parts.append(f"+{data['critical_bonus']}% КРИТ")
            event["effect_text"] = " ".join(effect_parts)
            return event
        if card.effect_type == "damage_dodge":
            attacker.card_dodge_bonus = getattr(attacker, "card_dodge_bonus", 0) + data["bonus"]
            event["dodge_bonus"] = data["bonus"]
            data = {**data, "dice": data["dice"]}
        if card.effect_type == "critical":
            attacker.card_critical_bonus = getattr(attacker, "card_critical_bonus", 0) + data["bonus"]
            event["effect_text"] = f"+{data['bonus']}% КРИТ"
            return event
        if card.effect_type == "damage_resistance":
            attacker.card_damage_ratio = min(getattr(attacker, "card_damage_ratio", 1), data["ratio"])
            event["effect_text"] = f"-{int((1 - data['ratio']) * 100)}% УРОН"
            return event
        if card.effect_type == "damage_reduce":
            attacker.card_damage_reduce = max(getattr(attacker, "card_damage_reduce", 0), data.get("reduce", 0))
            event["effect_text"] = f"-{data.get('reduce', 0)} УРОН"
            return event

        total_damage = 0
        for _ in range(data.get("hits", 1)):
            dodge_chance = get_dodge_chance(attacker, defender)
            dodge_chance += getattr(defender, "card_dodge_bonus", 0)
            dodge_chance += defender.temporary_dodge_chance_modifier
            dodge_chance -= getattr(attacker, "card_anti_dodge_bonus", 0) + data.get("anti_dodge", 0)
            dodge_chance = max(0, dodge_chance)
            if self.rng.random() * 100 < dodge_chance:
                event["dodged"] = True
                continue
            event["hits"] += 1
            damage = roll_dice(data["dice"], self.rng) + attacker.strength * 2
            critical_chance = get_critical_chance(attacker, defender)
            critical_chance += getattr(attacker, "card_critical_bonus", 0) + data.get("critical_bonus", 0)
            critical_chance += attacker.temporary_critical_chance_modifier
            critical_chance = max(0, critical_chance)
            if getattr(attacker, "card_critical_bonus", 0) >= 100 or self.rng.random() * 100 < critical_chance:
                event["critical"] = True
                damage = math.ceil(damage * 1.5)
                damage = math.ceil(damage * data.get("critical_multiplier", 1))
                damage += data.get("critical_bonus_damage", 0)
            total_damage += damage

        total_damage = math.floor(total_damage * getattr(defender, "card_damage_ratio", 1))
        reduction = getattr(defender, "card_damage_reduce", 0)
        if reduction:
            total_damage = max(0, total_damage - reduction)
            defender.card_damage_reduce = 0
        total_damage = max(0, total_damage - math.floor(defender.endurance * 0.5))
        defender.take_damage(total_damage)
        if card.effect_type == "damage_stat_debuff" and event["hits"] > 0:
            stat_name = data["stat"]
            amount = max(0, int(data["amount"]))
            duration = max(1, card.effect_duration)
            defender_side = "enemy" if side == "player" else "player"
            applied_amount = self._add_timed_stat_effect(
                defender_side,
                stat_name,
                -amount,
                duration,
            )
            stat_label = self._stat_label(stat_name)
            exchange_label = "РАЗМЕН" if duration == 1 else "РАЗМЕНА"
            event["effect_text"] = (
                f"{stat_label} ВРАГА {applied_amount} НА {duration} {exchange_label}"
            )
        if card.effect_type == "damage_critical_debuff" and event["hits"] > 0:
            amount = max(0, int(data["amount"]))
            duration = max(1, card.effect_duration)
            defender_side = "enemy" if side == "player" else "player"
            self._add_timed_critical_effect(defender_side, -amount, duration)
            exchange_label = "РАЗМЕН" if duration == 1 else "РАЗМЕНА"
            event["effect_text"] = (
                f"КРИТ ВРАГА -{amount}% НА {duration} {exchange_label}"
            )
        if card.effect_type == "damage_dodge_debuff" and event["hits"] > 0:
            amount = max(0, int(data["amount"]))
            duration = max(1, card.effect_duration)
            defender_side = "enemy" if side == "player" else "player"
            self._add_timed_dodge_effect(defender_side, -amount, duration)
            exchange_label = "РАЗМЕН" if duration == 1 else "РАЗМЕНА"
            event["effect_text"] = (
                f"УВОРОТ ВРАГА -{amount}% НА {duration} {exchange_label}"
            )
        if (
            card.effect_type == "damage_dodge_critical_debuff"
            and event["hits"] > 0
        ):
            dodge_amount = max(0, int(data["dodge_amount"]))
            critical_amount = max(0, int(data["critical_amount"]))
            duration = max(1, card.effect_duration)
            defender_side = "enemy" if side == "player" else "player"
            self._add_timed_dodge_effect(
                defender_side,
                -dodge_amount,
                duration,
            )
            self._add_timed_critical_effect(
                defender_side,
                -critical_amount,
                duration,
            )
            exchange_label = "РАЗМЕН" if duration == 1 else "РАЗМЕНА"
            event["effect_text"] = (
                f"УВОРОТ ВРАГА -{dodge_amount}%, "
                f"КРИТ ВРАГА -{critical_amount}% "
                f"НА {duration} {exchange_label}"
            )
        if card.effect_type == "damage_recoil" and not event["critical"]:
            attacker.take_damage(data["recoil"])
        event["damage"] = total_damage
        return event

    def _add_timed_stat_effect(self, side, stat_name, amount, duration):
        self._validate_side(side)
        fighter = self.player if side == "player" else self.enemy
        amount = int(amount)
        if amount < 0:
            amount = max(amount, -getattr(fighter, stat_name))
        if amount == 0:
            return 0
        fighter.adjust_temporary_stat(stat_name, amount)
        self.timed_stat_effects[side].append({
            "stat": stat_name,
            "amount": amount,
            "expires_after_turn": self.turn + max(1, int(duration)) - 1,
        })
        return amount

    def _expire_timed_stat_effects(self):
        for side, fighter in (("player", self.player), ("enemy", self.enemy)):
            for effect in self.timed_stat_effects[side][:]:
                if effect["expires_after_turn"] > self.turn:
                    continue
                fighter.adjust_temporary_stat(
                    effect["stat"],
                    -effect["amount"],
                )
                self.timed_stat_effects[side].remove(effect)
            for effect in self.timed_critical_effects[side][:]:
                if effect["expires_after_turn"] > self.turn:
                    continue
                fighter.temporary_critical_chance_modifier -= effect["amount"]
                self.timed_critical_effects[side].remove(effect)
            for effect in self.timed_dodge_effects[side][:]:
                if effect["expires_after_turn"] > self.turn:
                    continue
                fighter.temporary_dodge_chance_modifier -= effect["amount"]
                self.timed_dodge_effects[side].remove(effect)

    def _add_timed_critical_effect(self, side, amount, duration):
        self._validate_side(side)
        fighter = self.player if side == "player" else self.enemy
        fighter.temporary_critical_chance_modifier += int(amount)
        self.timed_critical_effects[side].append({
            "amount": int(amount),
            "expires_after_turn": self.turn + max(1, int(duration)) - 1,
        })

    def _add_timed_dodge_effect(self, side, amount, duration):
        self._validate_side(side)
        fighter = self.player if side == "player" else self.enemy
        fighter.temporary_dodge_chance_modifier += int(amount)
        self.timed_dodge_effects[side].append({
            "amount": int(amount),
            "expires_after_turn": self.turn + max(1, int(duration)) - 1,
        })

    @staticmethod
    def _stat_label(stat_name):
        labels = {
            "strength": "СИЛА",
            "intuition": "ИНТУИЦИЯ",
            "agility": "ЛОВКОСТЬ",
            "endurance": "ВЫНОСЛИВОСТЬ",
        }
        if stat_name not in labels:
            raise ValueError(f"Неизвестная характеристика: {stat_name}")
        return labels[stat_name]

    def _spend_points(self, side, card):
        for stat, cost in card.costs.items():
            self.action_points[side][stat] -= cost

    def _stronger_side(self, stat):
        player_value = getattr(self.player, stat)
        enemy_value = getattr(self.enemy, stat)
        if player_value == enemy_value:
            return None
        return "player" if player_value > enemy_value else "enemy"

    @staticmethod
    def _validate_side(side):
        if side not in ("player", "enemy"):
            raise ValueError(f"Неизвестная сторона: {side}")

    def is_over(self):
        return self.player.is_dead() or self.enemy.is_dead()

    def outcome(self):
        if self.player.is_dead() and self.enemy.is_dead():
            outcome = "draw"
        elif self.enemy.is_dead():
            outcome = "win"
        elif self.player.is_dead():
            outcome = "loss"
        else:
            return None
        if not self._xp_awarded_applied:
            self.xp_awarded = battle_xp(self.player.level, self.enemy.level, outcome)
            apply_xp(self.player, self.xp_awarded, restore_hp=False)
            enemy_outcome = {"win": "loss", "loss": "win", "draw": "draw"}[outcome]
            self.enemy_xp_awarded = battle_xp(self.enemy.level, self.player.level, enemy_outcome)
            apply_xp(self.enemy, self.enemy_xp_awarded, restore_hp=False)
            self._xp_awarded_applied = True
        return outcome

    def winner_name(self):
        return {"draw": "Ничья", "win": self.player.name, "loss": self.enemy.name}.get(self.outcome())