import random
from combat.zones import ZONES
from combat.resolver import resolve_attack


class Battle:
    def __init__(self, player, enemy):
        self.player = player
        self.enemy = enemy
        self.turn = 0
        self.history = []

        self.player_attack_zone = None
        self.player_defense_zones = []

        # Последняя атака игрока (нужно для интерфейса/комментатора)
        self.last_player_attack = None
        self.last_player_hit = False
        self.last_player_damage = 0
        self.last_player_dice = (0, 0)
        self.last_player_critical = False
        self.last_player_critical_dice = None
        self.last_player_critical_multiplier = 1
        self.last_player_dodged = False
        self.last_player_combo = 0

        # Последняя атака противника (нужно для интерфейса/комментатора)
        self.last_enemy_attack = None
        self.last_enemy_hit = False
        self.last_enemy_damage = 0
        self.last_enemy_dice = (0, 0)
        self.last_enemy_critical = False
        self.last_enemy_critical_dice = None
        self.last_enemy_critical_multiplier = 1
        self.last_enemy_dodged = False
        self.last_enemy_combo = 0

        self.stats = {
            "player": self._new_fighter_stats(),
            "enemy": self._new_fighter_stats(),
        }

    @staticmethod
    def _new_fighter_stats():
        return {
            "hits": 0,
            "damage": 0,
            "critical": 0,
            "dodges": 0,
            "blocks": 0,
            "combo_sessions": 0,
            "current_combo": 0,
            "max_combo": 0,
        }

    def is_over(self):
        return self.player.is_dead() or self.enemy.is_dead()

    def winner_name(self):
        if self.player.is_dead() and self.enemy.is_dead():
            return "Ничья"
        if self.enemy.is_dead():
            return self.player.name
        if self.player.is_dead():
            return self.enemy.name
        return None

    def choose_player_zones(self, attack_zone, defense_zones):
        if attack_zone not in ZONES:
            raise ValueError("Некорректная зона атаки")
        if len(defense_zones) != 2:
            raise ValueError("Нужно выбрать ровно две зоны защиты")
        if any(zone not in ZONES for zone in defense_zones):
            raise ValueError("Некорректная зона защиты")
        if len(set(defense_zones)) != 2:
            raise ValueError("Зоны защиты не должны повторяться")
        
        self.player_attack_zone = attack_zone
        self.player_defense_zones = list(defense_zones)

    def enemy_choose_zones(self):
        zones = list(ZONES.keys())
        return random.choice(zones), random.sample(zones, 2)

    def _record_attack(self, side, result):
        stats = self.stats[side]
        damage = result["damage"]

        if damage > 0:
            stats["hits"] += 1
            stats["damage"] += damage

            stats["max_combo"] = max(stats["max_combo"], result["combo_level"])

            if result["combo_level"] == 2:
                stats["combo_sessions"] += 1

        if result["critical"]:
            stats["critical"] += 1

        if damage <= 0 or result["dodged"] or result["blocked"]:
            stats["current_combo"] = 0
        elif result["combo_level"] >= 5:
            stats["current_combo"] = 0
        else:
            stats["current_combo"] = result["combo_level"]

    def resolve_turn(self):
        if self.is_over() or self.player_attack_zone is None:
            return

        self.turn += 1
        enemy_attack, enemy_defense = self.enemy_choose_zones()

        player_blocked = self.player_attack_zone in enemy_defense
        enemy_blocked = enemy_attack in self.player_defense_zones

        # Вызов внешней функции расчета атаки из resolver.py
        player_result = resolve_attack(
            self.player, self.enemy, player_blocked, self.stats["player"]["current_combo"]
        )
        enemy_result = resolve_attack(
            self.enemy, self.player, enemy_blocked, self.stats["enemy"]["current_combo"]
        )

        self._record_attack("player", player_result)
        self._record_attack("enemy", enemy_result)

        if player_result["dodged"]:
            self.stats["enemy"]["dodges"] += 1
        elif player_result["blocked"]:
            self.stats["enemy"]["blocks"] += 1

        if enemy_result["dodged"]:
            self.stats["player"]["dodges"] += 1
        elif enemy_result["blocked"]:
            self.stats["player"]["blocks"] += 1

        # Данные атаки игрока для интерфейса
        self.last_player_attack = self.player_attack_zone
        self.last_player_hit = player_result["damage"] > 0
        self.last_player_damage = player_result["damage"]
        self.last_player_dice = player_result["dice"]
        self.last_player_critical = player_result["critical"]
        self.last_player_critical_dice = player_result["critical_dice"]
        self.last_player_critical_multiplier = player_result["critical_multiplier"]
        self.last_player_dodged = player_result["dodged"]
        self.last_player_combo = (
            player_result["combo_level"]
            if self.last_player_hit
            else 0
        )

        # Данные атаки противника для интерфейса
        self.last_enemy_attack = enemy_attack
        self.last_enemy_hit = enemy_result["damage"] > 0
        self.last_enemy_damage = enemy_result["damage"]
        self.last_enemy_dice = enemy_result["dice"]
        self.last_enemy_critical = enemy_result["critical"]
        self.last_enemy_critical_dice = enemy_result["critical_dice"]
        self.last_enemy_critical_multiplier = enemy_result["critical_multiplier"]
        self.last_enemy_dodged = enemy_result["dodged"]
        self.last_enemy_combo = (
            enemy_result["combo_level"]
            if self.last_enemy_hit
            else 0
        )

        # Нанесение урона
        self.enemy.take_damage(self.last_player_damage)

        if not self.enemy.is_dead():
            self.player.take_damage(self.last_enemy_damage)
        else:
            self.player.gain_xp(30)
            self.player.try_level_up()

        # История боя
        self.history.append({
            "turn": self.turn,
            "player_log": [
                f"Атака: {ZONES[self.player_attack_zone]}",
                "Защита: " + " и ".join(ZONES[zone] for zone in self.player_defense_zones),
                f"Урон: {self.last_player_damage}",
            ],
            "enemy_log": [
                f"Атака: {ZONES[enemy_attack]}",
                "Защита: " + " и ".join(ZONES[zone] for zone in enemy_defense),
                f"Урон: {self.last_enemy_damage}",
            ],
            "player_dodged": self.last_enemy_dodged,
            "enemy_dodged": self.last_player_dodged,
            "player_combo": self.last_player_combo,
            "enemy_combo": self.last_enemy_combo,
            "player_critical": self.last_player_critical,
            "enemy_critical": self.last_enemy_critical,
        })

        self.history = self.history[-4:]

        # Подготовка следующего хода
        self.player_attack_zone = None
        self.player_defense_zones = []
