"""Особые эффекты карт бойца, лучника и асасина (ярость, меткость, концентрация).

Бой 1 на 1: «всем целям» и «нескольким целям» бьют единственного противника.
Длительность «N ходов» = текущий размен и ещё N-1 следующих.
"""
import math
import re

from kaloda.combat.mechanics import (
    get_block_chance,
    get_critical_chance,
    get_critical_damage_multiplier,
    get_dodge_chance,
)

PHYSICAL_RESOURCES = ("rage", "accuracy", "concentration")
BLEED_TURNS = 2
POISON_DAMAGE_PERCENT = 2


def max_dice_damage(expression):
    if isinstance(expression, int):
        return expression
    match = re.fullmatch(r"(\d+)d(\d+)", str(expression))
    if match is None:
        raise ValueError(f"Некорректная запись урона: {expression}")
    count, sides = (int(part) for part in match.groups())
    return count * sides


def _other(side):
    return "enemy" if side == "player" else "player"


class PhysicalEffectsMixin:
    def _init_physical_effects(self):
        self.phys_buffs = {"player": [], "enemy": []}
        self.bleeds = {"player": [], "enemy": []}
        self.poisons = {"player": [], "enemy": []}
        self.phys_shields = {"player": 0, "enemy": 0}
        self.phys_spirits = {"player": None, "enemy": None}
        self.delayed_hp_loss = {"player": [], "enemy": []}
        self.delayed_heals = {"player": [], "enemy": []}
        self.regenerations = {"player": [], "enemy": []}
        self.invulnerable = {"player": False, "enemy": False}
        self.invulnerability_targets = {"player": None, "enemy": None}
        self.skip_next_turn = {"player": False, "enemy": False}
        self.skip_turn_armed = {"player": False, "enemy": False}
        self.phys_state = {
            side: {"guaranteed_crits": 0, "no_crit_attacks": 0, "guaranteed_dodges": 0, "dodge_stacks": 0, "hit_counter": 0}
            for side in ("player", "enemy")
        }

    def _fighter_for(self, side):
        return self.player if side == "player" else self.enemy

    def _add_buff(self, side, duration, **values):
        self.phys_buffs[side].append({"remaining": max(1, int(duration or 1)), "fresh": True, **values})

    def _buff(self, side, key):
        return sum(buff.get(key, 0) for buff in self.phys_buffs[side])

    def _max_buff(self, side, key):
        return max((buff.get(key, 0) for buff in self.phys_buffs[side]), default=0)

    def _stun(self, side):
        self.mage_stuns[side] = max(self.mage_stuns.get(side, 0), 1)

    def _heal(self, side, amount):
        """Лечение с учётом «кражи благословения»: часть уходит наложившему её противнику."""
        amount = max(0, int(amount))
        if self._buff(side, "healing_blocked"):
            return 0
        if not amount:
            return 0
        stolen = int(amount * min(100, self._buff(side, "steal_healing_percent")) / 100)
        fighter = self._fighter_for(side)
        before = fighter.hp
        fighter.hp = min(fighter.max_hp, fighter.hp + amount - stolen)
        if stolen:
            thief = self._fighter_for(_other(side))
            thief_before = thief.hp
            thief.hp = min(thief.max_hp, thief.hp + stolen)
            self.stats[_other(side)]["healed"] += thief.hp - thief_before
        return fighter.hp - before

    def _lose_hp(self, side, amount):
        """Потеря HP от жертв и периодического урона: не убивает, оставляет 1 HP."""
        fighter = self._fighter_for(side)
        amount = min(max(0, int(amount)), max(0, fighter.hp - 1))
        if amount:
            fighter.take_damage(amount)
            self._fighter_took_damage(side, amount)
        return amount

    def _tick_poison(self, side):
        if not self.poisons[side] or any(
            status["name"] == "холод" for status in self.mage_statuses.get(side, [])
        ):
            return []
        poison = self.poisons[side].pop(0)
        damage = self._lose_hp(
            side,
            math.ceil(self._fighter_for(side).max_hp * POISON_DAMAGE_PERCENT / 100),
        )
        self.stats[poison["source"]]["damage"] += damage
        events = []
        if damage:
            events.append({"side": _other(side), "card": "Яд", "damage": damage, "healed": 0})
        return events

    # ---------- начало хода ----------

    def _tick_physical_effects(self):
        for side in ("player", "enemy"):
            events = []
            bleed_damage = 0
            for bleed in self.bleeds[side]:
                dealt = self._lose_hp(side, bleed["damage"])
                bleed_damage += dealt
                source = bleed["source"]
                self.stats[source]["damage"] += dealt
                heal_percent = self._buff(source, "bleed_heal_percent")
                if dealt and heal_percent:
                    healed = self._heal(source, math.ceil(dealt * heal_percent / 100))
                    if healed:
                        events.append({"side": source, "card": "Багровая жатва", "damage": 0, "healed": healed})
                bleed["remaining"] -= 1
            self.bleeds[side] = [bleed for bleed in self.bleeds[side] if bleed["remaining"] > 0]
            if bleed_damage:
                events.append({"side": _other(side), "card": "Кровотечение", "damage": bleed_damage, "healed": 0})

            fighter = self._fighter_for(side)
            for regeneration in self.regenerations[side]:
                if regeneration.pop("fresh", False):
                    continue
                amount = regeneration["heal_per_turn"] + (
                    int(fighter.stats.get("endurance", 0)) * regeneration["endurance_heal"]
                )
                healed = self._heal(side, amount)
                self.stats[side]["healed"] += healed
                if healed:
                    events.append({"side": side, "card": regeneration["card"], "damage": 0, "healed": healed})
                regeneration["remaining"] -= 1
            self.regenerations[side] = [item for item in self.regenerations[side] if item["remaining"] > 0]

            for delayed in self.delayed_heals[side]:
                delayed["remaining"] -= 1
                if delayed["remaining"] <= 0:
                    healed = self._heal(side, delayed["amount"])
                    self.stats[side]["healed"] += healed
                    if healed:
                        events.append({"side": side, "card": delayed["card"], "damage": 0, "healed": healed})
            self.delayed_heals[side] = [item for item in self.delayed_heals[side] if item["remaining"] > 0]

            for loss in self.delayed_hp_loss[side]:
                loss["remaining"] -= 1
                if loss["remaining"] <= 0:
                    lost = self._lose_hp(side, loss["amount"])
                    if lost:
                        events.append({"side": side, "card": loss["card"], "damage": 0, "healed": 0, "effect_text": f"-{lost} HP"})
            self.delayed_hp_loss[side] = [loss for loss in self.delayed_hp_loss[side] if loss["remaining"] > 0]

            for buff in self.phys_buffs[side]:
                if buff.get("forest_spirit") and self.phys_spirits[side]:
                    continue
                if buff.pop("fresh", False):
                    continue
                buff["remaining"] -= 1
            self.phys_buffs[side] = [buff for buff in self.phys_buffs[side] if buff["remaining"] > 0]
            if not self._buff(side, "dodge_damage_bonus"):
                self.phys_state[side]["dodge_stacks"] = 0
            if not self._buff(side, "stun_after_hits"):
                self.phys_state[side]["hit_counter"] = 0
            if events:
                self.history.append({"turn": self.turn, "events": events})

    def _mana_regen_ratio(self, side):
        return max(0, 100 - self._buff(side, "mana_regen_debuff")) / 100

    # ---------- розыгрыш карты ----------

    def _burn_mana(self, side, data, card):
        target_side = _other(side)
        target = self._fighter_for(target_side)
        # У баффов burn_mana_percent — усиление будущих выжиганий, а не выжигание сейчас
        if card.effect_type == "damage_buff" or not any(key in data for key in ("burn_mana", "burn_mana_percent")):
            return 0
        burn = int(data.get("burn_mana", 0))
        burn += int(target.mp * data.get("burn_mana_percent", 0) / 100)
        burn += int(target.max_mp * self._buff(side, "burn_bonus_max_percent") / 100)
        burn += int(target.mp * self._buff(side, "burn_bonus_current_percent") / 100)
        burned = min(int(target.mp), max(0, burn))
        target.mp = int(target.mp) - burned
        return burned

    def _apply_self_buffs(self, side, card, event):
        data = card.effect_data
        duration = int(data.get("buff_duration") or data.get("duration") or card.effect_duration or 1)
        attacker = self._fighter_for(side)
        texts = []
        mapping = {
            "bleed_healing_percent": ("bleed_heal_percent", "ЛЕЧЕНИЕ ОТ КРОВОТЕЧЕНИЯ"),
            "bleed_increase": ("bleed_bonus_percent", "КРОВОТЕЧЕНИЕ СИЛЬНЕЕ"),
            "extra_hits": ("extra_hits", "+1 УДАР"),
            "regen_percent": ("regen_per_hit_percent", "ЛЕЧЕНИЕ ЗА УДАР"),
            "missing_hp_damage": ("missing_hp_damage", "УРОН ЗА ПОТЕРЯННОЕ HP"),
            "damage_buff_percent": ("damage_percent", None),
            "dodge_percent": ("dodge_percent", None),
            "stun_after_hits": ("stun_after_hits", "ОГЛУШИТ ПОСЛЕ СЕРИИ"),
            "crit_damage_conversion": ("crit_conversion", "КРИТ ОТ КРИТ. УРОНА"),
            "incoming_damage_percent": ("incoming_damage_percent", "ВХОДЯЩИЙ УРОН СНИЖЕН"),
            "hit_chance_bonus": ("hit_bonus", "ПОПАДАНИЕ ВЫШЕ"),
            "agility_bonus": ("agility_bonus", "ЛОВКОСТЬ ВЫШЕ"),
        }
        for data_key, (buff_key, text) in mapping.items():
            if data.get(data_key):
                self._add_buff(side, duration, **{buff_key: data[data_key]})
                if text:
                    texts.append(text)
        if data.get("damage_buff_percent"):
            texts.append(f"+{data['damage_buff_percent']}% УРОНА")
        if data.get("dodge_percent"):
            texts.append(f"+{data['dodge_percent']}% УВОРОТА")
        if data.get("dodge_stun"):
            self._add_buff(side, duration, dodge_stun=1)
            texts.append("ОГЛУШЕНИЕ ПРИ УВОРОТЕ")
        if data.get("guaranteed_dodge"):
            self.phys_state[side]["guaranteed_dodges"] += int(data["guaranteed_dodge"])
            texts.append("ГАРАНТИРОВАННЫЙ УВОРОТ")
        if data.get("shield_flat"):
            agility = attacker.agility + self._buff(side, "agility_bonus")
            shield = int(data["shield_flat"]) + agility * int(data.get("shield_agility", 0))
            self.phys_shields[side] += shield
            texts.append(f"ЩИТ +{shield}")
        if data.get("cleanse"):
            self._cleanse_negative_effects(side)
            texts.append("ОТРИЦАТЕЛЬНЫЕ ЭФФЕКТЫ СНЯТЫ")
        if data.get("dodge_damage_bonus"):
            if data.get("dodge_stacks"):
                self._add_buff(side, duration, dodge_damage_bonus=data["dodge_damage_bonus"], dodge_stack_limit=data["dodge_stacks"])
                texts.append("УСИЛЕНИЕ ПОСЛЕ УВОРОТА")
            else:
                self._add_buff(side, duration, dodge_stun=1)
                texts.append("ОГЛУШЕНИЕ ПРИ УВОРОТЕ")
        if data.get("accuracy_strength"):
            gain = int(data.get("accuracy_bonus", 1)) + attacker.agility // int(data["accuracy_strength"])
            self._add_buff(side, duration, accuracy_gain=gain)
            texts.append(f"+{gain} МЕТКОСТИ ЗА ИСТОЧНИК")
        if card.effect_type == "damage_buff" and data.get("burn_mana_percent"):
            key = "burn_bonus_max_percent" if card.resource_type == "accuracy" else "burn_bonus_current_percent"
            self._add_buff(side, duration, **{key: data["burn_mana_percent"]})
            texts.append("ВЫЖИГАНИЕ СИЛЬНЕЕ")
        is_buff_card = card.effect_type == "damage_buff"
        if (is_buff_card or card.effect_duration) and data.get("crit_chance_percent") and "poison_extraction" not in data:
            self._add_buff(side, duration, crit_chance=data["crit_chance_percent"])
            texts.append(f"+{data['crit_chance_percent']}% КРИТА")
        if card.effect_duration and data.get("crit_damage_percent") and "poison_extraction" not in data:
            self._add_buff(side, duration, crit_damage=data["crit_damage_percent"])
            texts.append(f"+{data['crit_damage_percent']}% КРИТ. УРОНА")
        if data.get("crit_chance_guarantee"):
            self.phys_state[side]["guaranteed_crits"] = 1
            self.phys_state[side]["no_crit_attacks"] = int(data.get("next_hits_no_crit", 0))
            texts.append("СЛЕДУЮЩИЙ УДАР — КРИТ")
        if data.get("summon_spirit"):
            spirit_hp = max(1, 20 + attacker.agility)
            self.phys_spirits[side] = {
                "hp": spirit_hp,
                "max_hp": spirit_hp,
            }
            self._add_buff(
                side,
                1,
                dodge_percent=data.get("spirit_dodge", 15),
                damage_percent=10,
                forest_spirit=True,
            )
            texts.append("ЛЕСНОЙ ДУХ")
        if data.get("full_heal"):
            healed = self._heal(side, attacker.max_hp - attacker.hp)
            event["healed"] += healed
            if healed:
                self.delayed_hp_loss[side].append({"amount": healed, "remaining": duration + 1, "card": card.name})
            texts.append("ПОЛНОЕ ИСЦЕЛЕНИЕ")
        if data.get("invulnerable"):
            self.invulnerable[side] = True
            self.invulnerability_targets[side] = _other(side)
            texts.append("НЕУЯЗВИМОСТЬ ДО ХОДА СОПЕРНИКА")
        if data.get("skip_next_turn"):
            self.skip_next_turn[side] = True
            self.skip_turn_armed[side] = True
            texts.append("СЛЕДУЮЩИЙ ХОД ПРОПУСКАЕТСЯ")
        return texts

    def _apply_enemy_debuffs(self, side, card):
        data = card.effect_data
        target_side = _other(side)
        attacker = self._fighter_for(side)
        duration = int(data.get("duration") or card.effect_duration or 1)
        texts = []
        if data.get("steal_healing_percent"):
            self._add_buff(target_side, duration, steal_healing_percent=data["steal_healing_percent"])
            texts.append("КРАЖА ЛЕЧЕНИЯ")
        if data.get("mana_regen_debuff"):
            self._add_buff(target_side, duration, mana_regen_debuff=data["mana_regen_debuff"])
            texts.append(f"-{data['mana_regen_debuff']}% ВОССТ. МАНЫ")
        if data.get("outgoing_damage_flat"):
            self._add_buff(target_side, 99, outgoing_damage_flat=int(data["outgoing_damage_flat"]), expire_after_turn=True)
            texts.append(f"УРОН ВРАГА -{int(data['outgoing_damage_flat'])}")
        if data.get("mark_damage"):
            bonus = int(data["mark_damage"]) + attacker.strength // 4 * int(data.get("mark_strength", 1))
            self._add_buff(target_side, 2, mark_damage=bonus)
            texts.append(f"МЕТКА +{bonus}")
        if data.get("no_heal_turns"):
            blocked_turns = int(data["no_heal_turns"])
            self._add_buff(target_side, blocked_turns, healing_blocked=1)
            texts.append(f"ЗАПРЕТ ЛЕЧЕНИЯ: {blocked_turns} ХОД.")
        if data.get("forbid_damage_cards"):
            blocked_turns = int(data["forbid_damage_cards"])
            self._add_buff(target_side, blocked_turns, forbid_damage_cards=1)
            texts.append(f"ЗАПРЕТ АТАКУЮЩИХ КАРТ: {blocked_turns} ХОД.")
        if data.get("poison_outgoing_damage_percent"):
            stacks = len(self.poisons[target_side])
            if stacks:
                value = int(data["poison_outgoing_damage_percent"]) * stacks
                self._add_buff(target_side, duration, outgoing_damage_percent=value)
                texts.append(f"ИСХ. УРОН -{value}%")
            else:
                texts.append("ЯДЫ НЕ НАЙДЕНЫ")
        if data.get("poison_cap_bonus"):
            debuff_duration = int(data.get("poison_cap_duration") or duration)
            self._add_buff(target_side, debuff_duration, poison_cap_bonus=int(data["poison_cap_bonus"]))
            texts.append(f"ЛИМИТ ЯДА +{int(data['poison_cap_bonus'])}")
        if data.get("entangle"):
            duration = int(data["entangle"])
            entangles = sum(bool(buff.get("entangled")) for buff in self.phys_buffs[target_side])
            if entangles < 3:
                self._add_buff(
                    target_side,
                    duration,
                    entangled=1,
                    entangle_source=card.key,
                    fresh=False,
                )
                texts.append(f"ОПЛЕТЕНИЕ: {duration} ХОД.")
            else:
                texts.append("ОПЛЕТЕНИЕ: МАКСИМУМ 3 ЭФФЕКТА")
        return texts

    def _cleanse_negative_effects(self, side):
        negative_keys = {
            "steal_healing_percent", "mana_regen_debuff", "outgoing_damage_flat", "outgoing_damage_percent",
            "entangled", "mark_damage", "healing_blocked", "forbid_damage_cards", "poison_cap_bonus",
        }
        self.phys_buffs[side] = [
            {key: value for key, value in buff.items() if key not in negative_keys}
            for buff in self.phys_buffs[side]
            if any(key not in negative_keys and key not in {"remaining", "fresh", "expire_after_turn"} for key in buff)
        ]
        self.bleeds[side].clear()
        self.poisons[side].clear()
        self.mage_statuses[side] = [
            status for status in self.mage_statuses[side]
            if status["name"] == "electric_cold_immunity"
        ]
        self.mage_stuns[side] = 0
        self.mage_freeze[side] = 0
        self.delayed_hp_loss[side].clear()
        self.skip_next_turn[side] = False
        self.skip_turn_armed[side] = False

    def _dispel_one_positive_effect(self, side):
        positive_keys = {
            "bleed_heal_percent", "bleed_bonus_percent", "extra_hits", "regen_per_hit_percent",
            "missing_hp_damage", "damage_percent", "dodge_percent", "stun_after_hits", "crit_conversion",
            "incoming_damage_percent", "hit_bonus", "agility_bonus", "dodge_stun", "accuracy_gain",
            "burn_bonus_max_percent", "burn_bonus_current_percent", "crit_chance", "crit_damage",
            "dodge_damage_bonus", "dodge_stack_limit", "forest_spirit", "poison_cap_bonus",
        }
        for index in range(len(self.phys_buffs[side]) - 1, -1, -1):
            buff = self.phys_buffs[side][index]
            if any(key in buff for key in positive_keys):
                self.phys_buffs[side].pop(index)
                return True
        return False

    def _remove_forest_spirit(self, side):
        self.phys_spirits[side] = None
        self.phys_buffs[side] = [buff for buff in self.phys_buffs[side] if not buff.get("forest_spirit")]

    def _absorb_forest_spirit_damage(self, side, damage):
        spirit = self.phys_spirits.get(side)
        if not spirit or damage <= 0:
            return damage
        absorbed = min(int(damage), int(spirit["hp"]))
        spirit["hp"] -= absorbed
        damage -= absorbed
        if spirit["hp"] <= 0:
            self._remove_forest_spirit(side)
        return damage

    def _resolve_physical_card(self, side, card, event):
        data = card.effect_data
        target_side = _other(side)
        attacker = self._fighter_for(side)
        defender = self._fighter_for(target_side)
        texts = []

        if data.get("hp_current_percent"):
            lost = self._lose_hp(side, attacker.hp * data["hp_current_percent"] / 100)
            texts.append(f"-{lost} HP")
        if data.get("hp_percent"):
            lost = self._lose_hp(side, math.ceil(attacker.max_hp * data["hp_percent"] / 100))
            texts.append(f"-{lost} HP")
        if data.get("heal_max_hp_percent"):
            healed = self._heal(side, math.ceil(attacker.max_hp * data["heal_max_hp_percent"] / 100))
            event["healed"] += healed
        if data.get("delayed_heal_percent"):
            self.delayed_heals[side].append({
                "amount": math.ceil(attacker.max_hp * data["delayed_heal_percent"] / 100),
                "remaining": max(1, int(data.get("delay_turns", 1))),
                "card": card.name,
            })
            texts.append(f"ЛЕЧЕНИЕ ЧЕРЕЗ {data.get('delay_turns', 1)} ХОДА")
        if data.get("heal_per_turn"):
            self.regenerations[side].append({
                "heal_per_turn": int(data["heal_per_turn"]),
                "endurance_heal": int(data.get("endurance_heal", 0)),
                "remaining": max(1, int(data.get("duration", card.effect_duration or 1))),
                "card": card.name,
                "fresh": bool(data.get("regen_starts_next_turn")),
            })
            texts.append("РЕГЕНЕРАЦИЯ")
        if data.get("heal_flat") or data.get("heal_agility_multiplier"):
            amount = int(data.get("heal_flat", 0))
            amount += attacker.endurance * int(data.get("heal_endurance", 0))
            agility = attacker.agility + self._buff(side, "agility_bonus")
            amount += agility * int(data.get("heal_agility_multiplier", 0))
            healed = self._heal(side, amount)
            event["healed"] += healed
            texts.append(f"ЛЕЧЕНИЕ +{healed} HP")
        if data.get("mana_percent"):
            attacker.mp = max(0, int(attacker.mp) - math.ceil(attacker.max_mp * data["mana_percent"] / 100))
        if card.effect_type == "damage_debuff" and data.get("accuracy_bonus") and data.get("hp_percent"):
            # Кровавая жертва: +уворот до конца боя
            self._add_buff(side, 99, dodge_percent=data["accuracy_bonus"])
            texts.append(f"+{data['accuracy_bonus']}% УВОРОТА")
        else:
            texts += self._apply_self_buffs(side, card, event)
        texts += self._apply_enemy_debuffs(side, card)

        if data.get("poison_extraction"):
            stacks = len(self.poisons[target_side])
            self.poisons[target_side] = []
            if stacks:
                self._add_buff(
                    side,
                    int(data.get("extraction_duration", 3)),
                    crit_chance=int(data.get("extraction_crit_chance_per_stack", 2)) * stacks,
                    crit_damage=int(data.get("extraction_crit_damage_per_stack", 4)) * stacks,
                )
            texts.append(f"СНЯТО ЯДОВ: {stacks}")

        burned = self._burn_mana(side, data, card)
        if burned:
            texts.append(f"-{burned} МАНЫ")
            if data.get("mana_restore_percent"):
                attacker.mp = min(attacker.max_mp, int(attacker.mp) + int(burned * data["mana_restore_percent"] / 100))

        if data.get("crit_on_no_mana") is None and data.get("crit_chance_percent") and data.get("burn_mana") and not data.get("dice"):
            # Дренаж крита: если мана врага выжжена до нуля — крит-бафф
            if int(defender.mp) == 0:
                self._add_buff(side, 1, crit_chance=data["crit_chance_percent"], crit_damage=data.get("crit_damage_percent", 0))
                texts.append("КРИТ ЗА ПУСТУЮ МАНУ")

        if data.get("poison") and not data.get("dice"):
            self._add_poison(side, int(data["poison"]), reaction_damage=event["damage"])
            texts.append(f"ЯД x{data['poison']}")

        if data.get("stun_if_poison_at_least"):
            required = int(data["stun_if_poison_at_least"])
            if len(self.poisons[target_side]) >= required:
                self._stun(target_side)
                texts.append("ОГЛУШЕНИЕ")
            else:
                texts.append(f"ТРЕБУЕТСЯ {required} ЯДА")

        execution_stacks = len(self.poisons[target_side]) if data.get("poison_damage_multiplier") else 0
        if data.get("dice") or execution_stacks:
            self._physical_attack(side, card, event, execution_stacks)
            event["attack"] = True
            if event["hits"] and data.get("poison") and data.get("dice"):
                if data.get("poison_per_hit"):
                    poison_added = int(event.get("poison_added", 0))
                else:
                    poison_added = self._add_poison(side, int(data["poison"]), reaction_damage=event["damage"])
                if poison_added:
                    texts.append(f"ЯД x{poison_added}")
        elif data.get("poison_damage_multiplier"):
            texts.append("НЕТ ЯДОВ НА ЦЕЛИ")

        if burned or data.get("burn_mana_percent") or data.get("burn_mana"):
            if int(defender.mp) == 0 and data.get("burn_damage_percent"):
                extra = math.ceil(defender.hp * data["burn_damage_percent"] / 100)
                defender.take_damage(extra)
                self._fighter_took_damage(target_side, extra)
                event["damage"] += extra
                texts.append(f"+{extra} ЗА ПУСТУЮ МАНУ")

        if data.get("dispel_positive_effect") and event["hits"]:
            if self._dispel_one_positive_effect(target_side):
                texts.append("ПОЛОЖИТЕЛЬНЫЙ ЭФФЕКТ СНЯТ")
            else:
                texts.append("НЕТ ПОЛОЖИТЕЛЬНЫХ ЭФФЕКТОВ")

        if not event["attack"] and not texts:
            texts.append(card.name.upper())
        event["effect_text"] = " ".join(text for text in [event.get("effect_text", "")] + texts if text)
        return event

    def _add_poison(self, side, stacks, reaction_damage=0, apply_reactions=True):
        target_side = _other(side)
        if any(status["name"] == "холод" for status in self.mage_statuses.get(target_side, [])):
            return 0
        max_stacks = 5 + int(self._buff(target_side, "poison_cap_bonus"))
        added = min(max(0, int(stacks)), max_stacks - len(self.poisons[target_side]))
        for _ in range(added):
            self.poisons[target_side].append({"source": side})
        if added and apply_reactions:
            elements = {status["name"] for status in self.mage_statuses.get(target_side, [])}
            for element in ("огонь", "вода", "электро", "воздух"):
                if element in elements:
                    self._apply_poison_reaction(
                        target_side,
                        element,
                        {"damage": reaction_damage, "effect_text": ""},
                    )
                    break
        return added

    def _apply_poison_reaction(self, target_side, element, event):
        """Resolve an elemental interaction with poison already on its target."""
        poisons = self.poisons[target_side]
        if not poisons:
            return False
        if element == "огонь":
            poisons.clear()
        elif element == "вода":
            self._add_poison(target_side, 1, apply_reactions=False)
        elif element == "электро":
            reaction_damage = math.ceil(max(0, int(event.get("damage", 0))) * 0.3)
            if reaction_damage:
                self._mage_take_damage(target_side, reaction_damage)
                event["damage"] += reaction_damage
            poisons.clear()
            self.mage_statuses[target_side] = [
                status for status in self.mage_statuses.get(target_side, [])
                if status["name"] != "электро"
            ]
        elif element == "воздух":
            poisons.pop(0)
        else:
            return False
        event["effect_text"] = (event.get("effect_text", "") + f" РЕАКЦИЯ: ЯД + {element.upper()}").strip()
        return True

    def _physical_attack(self, side, card, event, execution_stacks=0):
        data = card.effect_data
        target_side = _other(side)
        attacker = self._fighter_for(side)
        defender = self._fighter_for(target_side)
        from kaloda.combat.character_stats import normalize_profession_type

        assassin_passive_stacks = 0
        if normalize_profession_type(getattr(attacker, "profession_type", "")) == "assassin":
            assassin_passive_stacks = len(self.poisons[target_side])
        state = self.phys_state[side]
        hits = int(data.get("hits", 1))
        if hits > 1:
            hits += self._buff(side, "extra_hits")
        hit_results = [] if hits > 1 else None
        if hit_results is not None:
            event["hit_results"] = hit_results
        total_damage = 0
        any_crit = False
        damage_percent = self._buff(side, "damage_percent")
        damage_percent += state["dodge_stacks"] * self._max_buff(side, "dodge_damage_bonus")
        state["dodge_stacks"] = 0
        for index in range(hits):
            dodge = get_dodge_chance(attacker, defender)
            dodge += defender.temporary_dodge_chance_modifier
            dodge += self._buff(target_side, "dodge_percent")
            dodge += self._buff(target_side, "agility_bonus") * 2
            dodge += sum(
                int(status.get("miss_chance", 0))
                for status in self.mage_statuses.get(side, [])
                if status["name"] == "blinding"
            )
            if any(status["name"] == "вода" for status in self.mage_statuses.get(target_side, [])):
                dodge -= 15
            dodge -= data.get("hit_bonus", 0)
            dodge -= index * data.get("hit_bonus_scale", 0)
            if data.get("no_miss"):
                dodge = 0
            guaranteed_dodge = self.phys_state[target_side]["guaranteed_dodges"] > 0
            if guaranteed_dodge:
                self.phys_state[target_side]["guaranteed_dodges"] -= 1
            if guaranteed_dodge or self.rng.random() * 100 < max(0, dodge):
                event["dodged"] = True
                self._fighter_dodged(target_side)
                self._on_dodge(target_side, side, data)
                if hit_results is not None:
                    hit_results.append({"damage": 0, "dodged": True, "blocked": False, "critical": False})
                continue
            event["hits"] += 1
            block_chance = get_block_chance(defender)
            if block_chance and self.rng.random() * 100 < block_chance:
                event["blocked"] = True
                event["block_count"] = event.get("block_count", 0) + 1
                event["effect_text"] = (event.get("effect_text", "") + " БЛОКИРОВКА").strip()
                if hit_results is not None:
                    hit_results.append({"damage": 0, "dodged": False, "blocked": True, "critical": False})
                continue
            if execution_stacks and data.get("poison_strength_per_stack"):
                damage = execution_stacks * (int(data["poison_damage_multiplier"]) + attacker.strength)
                damage += self._weapon_roll(attacker)
            elif execution_stacks:
                damage = execution_stacks * int(data["poison_damage_multiplier"])
                damage += attacker.strength + self._weapon_roll(attacker)
            else:
                damage = max_dice_damage(data["dice"])
                damage += attacker.strength + self._weapon_roll(attacker)
            damage += attacker.intuition * int(data.get("intuition_damage", 0))
            damage += self._buff(target_side, "mark_damage")
            missing_ratio = (attacker.max_hp - attacker.hp) / max(1, attacker.max_hp)
            damage += self._buff(side, "missing_hp_damage") * int(missing_ratio * 10)

            crit_multiplier = get_critical_damage_multiplier(attacker)
            chance = get_critical_chance(attacker, defender)
            chance += attacker.temporary_critical_chance_modifier
            chance += self._buff(side, "crit_chance")
            chance += index * data.get("crit_bonus_scale", 0)
            chance += self._buff(side, "crit_conversion") * (crit_multiplier - 1) * 100
            chance += execution_stacks * data.get("poison_crit_percent", 0)
            chance += assassin_passive_stacks * 2
            if state["guaranteed_crits"] > 0:
                critical = True
                state["guaranteed_crits"] -= 1
            elif state["no_crit_attacks"] > 0:
                critical = False
                state["no_crit_attacks"] -= 1
            else:
                critical = self.rng.random() * 100 < max(0, chance)
            if critical:
                any_crit = True
                event["critical"] = True
                self._fighter_landed_critical(side)
                bonus = self._buff(side, "crit_damage") + execution_stacks * data.get("poison_crit_damage_percent", 0)
                bonus += assassin_passive_stacks * 4
                if int(defender.mp) == 0:
                    bonus += data.get("crit_on_no_mana", 0)
                damage = math.ceil(damage * (crit_multiplier + bonus / 100))
            damage = math.floor(damage * max(0, 100 + damage_percent) / 100)
            incoming_reduction = min(100, max(0, self._buff(target_side, "incoming_damage_percent")))
            damage = math.floor(damage * (100 - incoming_reduction) / 100)
            outgoing_reduction = min(100, max(0, self._buff(side, "outgoing_damage_percent")))
            damage = math.floor(damage * (100 - outgoing_reduction) / 100)
            damage = max(0, damage - self._buff(side, "outgoing_damage_flat"))
            if self.invulnerable[target_side]:
                damage = 0
            else:
                damage_bonus = max(
                    0, int(getattr(defender, "next_damage_taken_bonus_percent", 0))
                )
                if damage > 0 and damage_bonus:
                    damage = math.floor(damage * (100 + damage_bonus) / 100)
                    defender.next_damage_taken_bonus_percent = 0
                damage = max(0, damage - self._buff(target_side, "incoming_damage_flat"))
                damage = self._absorb_forest_spirit_damage(target_side, damage)
                shield = min(self.phys_shields[target_side], damage)
                self.phys_shields[target_side] -= shield
                damage -= shield
            defender.take_damage(damage)
            if damage > 0:
                self._fighter_took_damage(target_side, damage)
            total_damage += damage
            event["damage"] += damage
            if hit_results is not None:
                hit_results.append({
                    "damage": damage,
                    "dodged": False,
                    "blocked": False,
                    "critical": critical,
                })

            if data.get("poison_per_hit") and data.get("poison"):
                event["poison_added"] = event.get("poison_added", 0) + self._add_poison(
                    side,
                    int(data["poison"]),
                    reaction_damage=damage,
                )

            if data.get("heal_percent") and damage > 0:
                missing = attacker.max_hp - attacker.hp
                event["healed"] += self._heal(side, math.ceil(missing * data["heal_percent"] / 100))

            regen = self._buff(side, "regen_per_hit_percent")
            if regen:
                event["healed"] += self._heal(side, math.ceil(attacker.max_hp * regen / 100))
            if self._buff(side, "stun_after_hits"):
                state["hit_counter"] += 1
                if state["hit_counter"] >= self._max_buff(side, "stun_after_hits"):
                    state["hit_counter"] = 0
                    self._stun(target_side)
                    event["effect_text"] = (event.get("effect_text", "") + " ОГЛУШЕНИЕ").strip()
        if event["hits"]:
            bleed_percent = data.get("bleed_percent", 0)
            if bleed_percent:
                self._add_bleed(side, bleed_percent, int(data.get("duration") or BLEED_TURNS))
            if data.get("follow_up_bleed"):
                self._add_bleed(side, data["follow_up_bleed"], BLEED_TURNS + 1)
            if data.get("crit_guarantee"):
                if any_crit:
                    self._add_buff(side, 2, crit_damage=data.get("crit_damage_buff", 20))
                else:
                    self._add_buff(side, 2, crit_chance=10)
        elif data.get("stun_on_dodge"):
            self._stun(target_side)
            event["effect_text"] = (event.get("effect_text", "") + " ОГЛУШЕНИЕ").strip()

    def _add_bleed(self, side, percent, turns):
        target_side = _other(side)
        target = self._fighter_for(target_side)
        percent += self._buff(side, "bleed_bonus_percent")
        damage = max(1, round(target.max_hp * percent / 100 / BLEED_TURNS))
        self.bleeds[target_side].append({"damage": damage, "remaining": max(1, turns), "source": side})

    def _on_dodge(self, dodger_side, attacker_side, data):
        state = self.phys_state[dodger_side]
        limit = self._max_buff(dodger_side, "dodge_stack_limit")
        if limit:
            state["dodge_stacks"] = min(limit, state["dodge_stacks"] + 1)
        if self._buff(dodger_side, "dodge_stun"):
            self._stun(attacker_side)


def describe_physical_card(card):
    """Описание карты бойца/лучника/асасина для подсказки."""
    data = card.effect_data
    parts = []
    if data.get("dice"):
        hits = int(data.get("hits", 1))
        parts.append(f"Урон {max_dice_damage(data['dice'])} + Сила" + (f", {hits} удара" if hits > 1 else "") + ".")
    if data.get("poison_damage_multiplier"):
        damage = str(data["poison_damage_multiplier"])
        if data.get("poison_strength_per_stack"):
            damage += " + Сила"
        parts.append(f"Урон {damage} за каждый яд на цели.")
    if data.get("bleed_percent"):
        parts.append(f"Кровотечение {data['bleed_percent']}% макс. HP цели за {int(data.get('duration') or BLEED_TURNS)} хода.")
    if data.get("poison"):
        poison_limit = 5 + int(data.get("poison_cap_bonus", 0))
        parts.append(
            f"Яд x{data['poison']}: 2% максимального HP за ход, максимум {poison_limit} стаков; "
            "в конце хода снимается 1 стак. Холод приостанавливает урон и спад стаков."
        )
    if data.get("burn_mana") or data.get("burn_mana_percent"):
        amount = data.get("burn_mana", 0)
        percent = data.get("burn_mana_percent", 0)
        text = " + ".join(part for part in (f"{amount}" if amount else "", f"{percent}% текущей" if percent else "") if part)
        parts.append(f"Выжигает {text} маны врага.")
    if data.get("burn_damage_percent"):
        parts.append(f"Если у врага 0 маны: +{data['burn_damage_percent']}% его текущего HP урона.")
    if data.get("crit_on_no_mana"):
        parts.append(f"Если у врага 0 маны: +{data['crit_on_no_mana']}% крит. урона.")
    if data.get("heal_percent"):
        parts.append(f"Лечит {data['heal_percent']}% недостающего HP.")
    if data.get("hp_percent"):
        parts.append(f"Стоит {data['hp_percent']}% вашего HP.")
    if data.get("hp_current_percent"):
        parts.append(f"Тратит {data['hp_current_percent']}% текущего HP.")
    if data.get("heal_max_hp_percent"):
        parts.append(f"Лечит {data['heal_max_hp_percent']}% максимального HP.")
    if data.get("delayed_heal_percent"):
        parts.append(
            f"Через {data.get('delay_turns', 1)} хода лечит "
            f"{data['delayed_heal_percent']}% максимального HP."
        )
    if data.get("heal_per_turn"):
        parts.append(
            f"Лечит {data['heal_per_turn']} HP + Выносливость каждый ход "
            f"{data.get('duration', card.effect_duration or 1)} хода."
        )
    if data.get("outgoing_damage_flat"):
        parts.append(f"Урон врага снижается на {data['outgoing_damage_flat']} на его следующий ход.")
    if data.get("incoming_damage_percent"):
        parts.append(f"Получаемый урон снижен на {data['incoming_damage_percent']}%.")
    if data.get("invulnerable"):
        parts.append("Неуязвимость до завершения следующего хода соперника.")
    if data.get("skip_next_turn"):
        parts.append("Следующий свой ход пропускается.")
    if data.get("team_only"):
        parts.append("Только для командного боя.")
    if data.get("hit_bonus") and data.get("dice"):
        parts.append(f"+{data['hit_bonus']}% к попаданию.")
    if data.get("no_miss"):
        parts.append("Нельзя увернуться.")
    if data.get("stun_on_dodge"):
        parts.append("Если враг увернулся — он оглушён на 1 ход.")
    labels = {
        "bleed_healing_percent": "Лечит {}% урона от ваших кровотечений",
        "bleed_increase": "Ваши кровотечения +{}%",
        "extra_hits": "+{} удар у многоударных карт",
        "regen_percent": "Лечит {}% HP за каждый удар",
        "missing_hp_damage": "+{} урона за каждые 10% потерянного HP",
        "damage_buff_percent": "+{}% урона",
        "dodge_percent": "+{}% уворота",
        "stun_after_hits": "Оглушает врага после {} ударов",
        "steal_healing_percent": "Враг отдаёт вам {}% своего лечения",
        "mana_regen_debuff": "Восстановление маны врага -{}%",
        "crit_chance_percent": "+{}% шанса крита",
        "crit_damage_percent": "+{}% крит. урона",
    }
    for key, label in labels.items():
        if data.get(key):
            parts.append(label.format(data[key]) + ".")
    if data.get("mark_damage"):
        parts.append(f"Метка: +{data['mark_damage']} урона по цели (+1 за 4 Силы) на 2 хода.")
    if data.get("dodge_damage_bonus"):
        if data.get("dodge_stacks"):
            parts.append(f"После уворота следующая атака +{data['dodge_damage_bonus']}% (до {data['dodge_stacks']} раз).")
        else:
            parts.append("При вашем увороте атакующий оглушён.")
    if data.get("crit_chance_guarantee"):
        parts.append(f"Следующий удар — крит, затем {data.get('next_hits_no_crit', 0)} атаки без крита.")
    if data.get("poison_extraction"):
        parts.append(
            "Снимает все яды с врага: "
            f"+{data.get('extraction_crit_chance_per_stack', 2)}% крита и "
            f"+{data.get('extraction_crit_damage_per_stack', 4)}% крит. урона "
            f"за каждый на {data.get('extraction_duration', 3)} хода."
        )
    if data.get("full_heal"):
        parts.append("Полностью лечит, позже вылеченное HP теряется (остаётся минимум 1).")
    if data.get("summon_spirit"):
        parts.append(
            "Лесной дух (20 HP + Ловкость призывателя) живёт, пока его не убьют: "
            f"+{data.get('spirit_dodge', 15)}% уворота и +10% урона, пока он жив."
        )
    if data.get("heal_flat") or data.get("heal_endurance") or data.get("heal_agility_multiplier"):
        formula = [str(data.get("heal_flat", 0))] if data.get("heal_flat") else []
        if data.get("heal_endurance"):
            formula.append(f"{data['heal_endurance']} × Выносливость")
        if data.get("heal_agility_multiplier"):
            formula.append(f"{data['heal_agility_multiplier']} × Ловкость")
        parts.append(f"Лечит {' + '.join(formula)} HP.")
    if data.get("entangle"):
        parts.append(f"Оплетение: цель может разыграть только 1 карту за ход, {data['entangle']} хода.")
    if data.get("no_heal_turns"):
        parts.append(f"Запрещает лечение на {data['no_heal_turns']} хода.")
    if data.get("stun_if_poison_at_least"):
        parts.append(f"Оглушает, если на цели минимум {data['stun_if_poison_at_least']} стаков яда.")
    if data.get("forbid_damage_cards"):
        parts.append(f"Противник не может разыгрывать атакующие карты {data['forbid_damage_cards']} хода.")
    if data.get("poison_cap_bonus"):
        parts.append(
            f"Повышает лимит яда на цели до {5 + int(data['poison_cap_bonus'])} "
            f"на {data.get('poison_cap_duration', 3)} хода."
        )
    if data.get("poison_outgoing_damage_percent"):
        parts.append(
            f"Снижает исходящий урон врага на {data['poison_outgoing_damage_percent']}% "
            "за каждый стак яда."
        )
    if data.get("dispel_positive_effect"):
        parts.append("Снимает 1 положительный эффект с противника.")
    if data.get("shield_flat"):
        parts.append(f"Щит {data['shield_flat']} HP + {data.get('shield_agility', 0)} × Ловкость.")
    if data.get("cleanse"):
        parts.append("Снимает с вас все отрицательные эффекты.")
    if data.get("guaranteed_dodge"):
        parts.append("Гарантированно уклоняется от следующей атаки.")
    if data.get("agility_bonus"):
        parts.append(f"+{data['agility_bonus']} Ловкости на {data.get('duration', 1)} хода.")
    if data.get("hit_chance_bonus"):
        parts.append(f"+{data['hit_chance_bonus']}% к попаданию на {data.get('buff_duration', 1)} хода.")
    if data.get("dodge_stun"):
        parts.append("При вашем уклонении атакующий оглушается на 1 ход.")
    duration = data.get("duration") or card.effect_duration
    if duration and card.effect_type != "damage":
        parts.append(f"Длительность: {duration} ход.")
    if data.get("ultimate"):
        parts.append("УЛЬТА.")
    names = {"rage": "ярости", "accuracy": "меткости", "concentration": "концентрации"}
    parts.append(f"Стоимость: {card.resource_cost} {names.get(card.resource_type, '')}.")
    return " ".join(parts)
