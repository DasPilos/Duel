"""Особые эффекты карт бойца, лучника и асасина (ярость, меткость, концентрация).

Бой 1 на 1: «всем целям» и «нескольким целям» бьют единственного противника.
Длительность «N ходов» = текущий размен и ещё N-1 следующих.
"""
import math

from combat.mechanics import (
    get_block_chance,
    get_critical_chance,
    get_critical_damage_multiplier,
    get_dodge_chance,
)

PHYSICAL_RESOURCES = ("rage", "accuracy", "concentration")
BLEED_TURNS = 2
POISON_TURNS = 2
POISON_DAMAGE = 2
SPIRIT_TURNS = 3


def _other(side):
    return "enemy" if side == "player" else "player"


class PhysicalEffectsMixin:
    def _init_physical_effects(self):
        self.phys_buffs = {"player": [], "enemy": []}
        self.bleeds = {"player": [], "enemy": []}
        self.poisons = {"player": [], "enemy": []}
        self.delayed_hp_loss = {"player": [], "enemy": []}
        self.phys_state = {
            side: {"guaranteed_crits": 0, "no_crit_attacks": 0, "dodge_stacks": 0, "hit_counter": 0}
            for side in ("player", "enemy")
        }

    def _fighter_for(self, side):
        return self.player if side == "player" else self.enemy

    def _add_buff(self, side, duration, **values):
        self.phys_buffs[side].append({"remaining": max(1, int(duration or 1)), **values})

    def _buff(self, side, key):
        return sum(buff.get(key, 0) for buff in self.phys_buffs[side])

    def _max_buff(self, side, key):
        return max((buff.get(key, 0) for buff in self.phys_buffs[side]), default=0)

    def _stun(self, side):
        # Счётчик уменьшается на границе хода, поэтому 2 = оглушение на следующий ход
        self.mage_stuns[side] = max(self.mage_stuns.get(side, 0), 2)

    def _heal(self, side, amount):
        """Лечение с учётом «кражи благословения»: часть уходит наложившему её противнику."""
        amount = max(0, int(amount))
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

            poison_damage = 0
            for poison in self.poisons[side]:
                dealt = self._lose_hp(side, poison["damage"])
                poison_damage += dealt
                self.stats[poison["source"]]["damage"] += dealt
                poison["remaining"] -= 1
            self.poisons[side] = [poison for poison in self.poisons[side] if poison["remaining"] > 0]
            if poison_damage:
                events.append({"side": _other(side), "card": "Яд", "damage": poison_damage, "healed": 0})

            for loss in self.delayed_hp_loss[side]:
                loss["remaining"] -= 1
                if loss["remaining"] <= 0:
                    lost = self._lose_hp(side, loss["amount"])
                    if lost:
                        events.append({"side": side, "card": loss["card"], "damage": 0, "healed": 0, "effect_text": f"-{lost} HP"})
            self.delayed_hp_loss[side] = [loss for loss in self.delayed_hp_loss[side] if loss["remaining"] > 0]

            for buff in self.phys_buffs[side]:
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
        duration = int(data.get("duration") or card.effect_duration or 1)
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
            self._add_buff(side, SPIRIT_TURNS, dodge_percent=data.get("spirit_dodge", 15), damage_percent=10)
            texts.append("ЛЕСНОЙ ДУХ")
        if data.get("full_heal"):
            healed = self._heal(side, attacker.max_hp - attacker.hp)
            event["healed"] += healed
            if healed:
                self.delayed_hp_loss[side].append({"amount": healed, "remaining": duration + 1, "card": card.name})
            texts.append("ПОЛНОЕ ИСЦЕЛЕНИЕ")
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
        if data.get("mark_damage"):
            bonus = int(data["mark_damage"]) + attacker.strength // 4 * int(data.get("mark_strength", 1))
            self._add_buff(target_side, 2, mark_damage=bonus)
            texts.append(f"МЕТКА +{bonus}")
        return texts

    def _resolve_physical_card(self, side, card, event):
        data = card.effect_data
        target_side = _other(side)
        attacker = self._fighter_for(side)
        defender = self._fighter_for(target_side)
        texts = []

        if data.get("hp_percent"):
            lost = self._lose_hp(side, attacker.max_hp * data["hp_percent"] / 100)
            texts.append(f"-{lost} HP")
        if data.get("mana_percent"):
            attacker.mp = max(0, int(attacker.mp) - int(attacker.max_mp * data["mana_percent"] / 100))
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
                self._add_buff(side, 2, crit_chance=2 * stacks, crit_damage=4 * stacks)
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
            self._add_poison(side, int(data["poison"]))
            texts.append(f"ЯД x{data['poison']}")

        execution_stacks = len(self.poisons[target_side]) if data.get("poison_damage_multiplier") else 0
        if data.get("dice") or execution_stacks:
            self._physical_attack(side, card, event, execution_stacks)
            event["attack"] = True
            if event["hits"] and data.get("poison") and data.get("dice"):
                self._add_poison(side, int(data["poison"]))
                texts.append(f"ЯД x{data['poison']}")
        elif data.get("poison_damage_multiplier"):
            texts.append("НЕТ ЯДОВ НА ЦЕЛИ")

        if burned or data.get("burn_mana_percent") or data.get("burn_mana"):
            if int(defender.mp) == 0 and data.get("burn_damage_percent"):
                extra = math.ceil(defender.hp * data["burn_damage_percent"] / 100)
                defender.take_damage(extra)
                self._fighter_took_damage(target_side, extra)
                event["damage"] += extra
                texts.append(f"+{extra} ЗА ПУСТУЮ МАНУ")

        if not event["attack"] and not texts:
            texts.append(card.name.upper())
        event["effect_text"] = " ".join(text for text in [event.get("effect_text", "")] + texts if text)
        return event

    def _add_poison(self, side, stacks):
        target_side = _other(side)
        damage = POISON_DAMAGE + self._fighter_for(side).level // 5
        for _ in range(max(0, stacks)):
            self.poisons[target_side].append({"damage": damage, "remaining": POISON_TURNS, "source": side})

    def _physical_attack(self, side, card, event, execution_stacks=0):
        data = card.effect_data
        target_side = _other(side)
        attacker = self._fighter_for(side)
        defender = self._fighter_for(target_side)
        state = self.phys_state[side]
        hits = int(data.get("hits", 1))
        if hits > 1:
            hits += self._buff(side, "extra_hits")
        total_damage = 0
        any_crit = False
        for index in range(hits):
            dodge = get_dodge_chance(attacker, defender)
            dodge += defender.temporary_dodge_chance_modifier
            dodge += self._buff(target_side, "dodge_percent")
            dodge -= data.get("hit_bonus", 0)
            dodge -= index * data.get("hit_bonus_scale", 0)
            if data.get("no_miss"):
                dodge = 0
            if self.rng.random() * 100 < max(0, dodge):
                event["dodged"] = True
                self._fighter_dodged(target_side)
                self._on_dodge(target_side, side, data)
                continue
            event["hits"] += 1
            block_chance = get_block_chance(defender)
            if block_chance and self.rng.random() * 100 < block_chance:
                event["blocked"] = True
                event["block_count"] = event.get("block_count", 0) + 1
                event["effect_text"] = (event.get("effect_text", "") + " БЛОКИРОВКА").strip()
                continue
            if execution_stacks:
                damage = execution_stacks * int(data["poison_damage_multiplier"])
            else:
                from combat.card_battle import roll_dice
                damage = roll_dice(data["dice"], self.rng)
            damage += attacker.strength + self._weapon_roll(attacker)
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
            if state["guaranteed_crits"] > 0:
                critical = True
                state["guaranteed_crits"] -= 1
            elif state["no_crit_attacks"] > 0:
                critical = False
            else:
                critical = self.rng.random() * 100 < max(0, chance)
            if critical:
                any_crit = True
                event["critical"] = True
                self._fighter_critical_hit(side)
                bonus = self._buff(side, "crit_damage") + execution_stacks * data.get("poison_crit_damage_percent", 0)
                if int(defender.mp) == 0:
                    bonus += data.get("crit_on_no_mana", 0)
                damage = math.ceil(damage * (crit_multiplier + bonus / 100))
            total_damage += damage

            regen = self._buff(side, "regen_per_hit_percent")
            if regen:
                event["healed"] += self._heal(side, math.ceil(attacker.max_hp * regen / 100))
            if self._buff(side, "stun_after_hits"):
                state["hit_counter"] += 1
                if state["hit_counter"] >= self._max_buff(side, "stun_after_hits"):
                    state["hit_counter"] = 0
                    self._stun(target_side)
                    event["effect_text"] = (event.get("effect_text", "") + " ОГЛУШЕНИЕ").strip()
        if state["no_crit_attacks"] > 0 and not state["guaranteed_crits"]:
            state["no_crit_attacks"] -= 1

        percent = self._buff(side, "damage_percent")
        percent += state["dodge_stacks"] * self._max_buff(side, "dodge_damage_bonus")
        state["dodge_stacks"] = 0
        total_damage = math.floor(total_damage * max(0, 100 + percent) / 100)
        defender.take_damage(total_damage)
        if total_damage > 0:
            self._fighter_took_damage(target_side, total_damage)
        event["damage"] += total_damage

        if event["hits"]:
            bleed_percent = data.get("bleed_percent", 0)
            if bleed_percent:
                self._add_bleed(side, bleed_percent, int(data.get("duration") or BLEED_TURNS))
            if data.get("follow_up_bleed"):
                self._add_bleed(side, data["follow_up_bleed"], BLEED_TURNS + 1)
            if data.get("heal_percent"):
                missing = attacker.max_hp - attacker.hp
                event["healed"] += self._heal(side, math.ceil(missing * data["heal_percent"] / 100))
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
        parts.append(f"Урон {data['dice']} + Сила" + (f", {hits} удара" if hits > 1 else "") + ".")
    if data.get("poison_damage_multiplier"):
        parts.append(f"Урон {data['poison_damage_multiplier']} за каждый яд на цели.")
    if data.get("bleed_percent"):
        parts.append(f"Кровотечение {data['bleed_percent']}% макс. HP цели за {int(data.get('duration') or BLEED_TURNS)} хода.")
    if data.get("poison"):
        parts.append(f"Яд x{data['poison']} ({POISON_DAMAGE} урона за ход, {POISON_TURNS} хода).")
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
        parts.append("Снимает все яды с врага: +2% крита и +4% крит. урона за каждый на 2 хода.")
    if data.get("full_heal"):
        parts.append("Полностью лечит, позже вылеченное HP теряется (остаётся минимум 1).")
    if data.get("summon_spirit"):
        parts.append(f"Лесной дух на {SPIRIT_TURNS} хода: +{data.get('spirit_dodge', 15)}% уворота, +10% урона.")
    duration = data.get("duration") or card.effect_duration
    if duration and card.effect_type != "damage":
        parts.append(f"Длительность: {duration} ход.")
    if data.get("ultimate"):
        parts.append("УЛЬТА.")
    names = {"rage": "ярости", "accuracy": "меткости", "concentration": "концентрации"}
    parts.append(f"Стоимость: {card.resource_cost} {names.get(card.resource_type, '')}.")
    return " ".join(parts)
