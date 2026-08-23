import random

ZONES = {
    "head": "Голова",
    "body": "Туловище",
    "waist": "Пояс",
    "thigh": "Бедро",
    "shin": "Голень",
}

class Battle:
    def __init__(self, player, enemy):
        self.player = player
        self.enemy = enemy
        self.turn = 0
        self.player_attack_zone = None
        self.player_defense_zones = []
        
        # История ходов для логов (до 4 последних действий)
        self.history = []
        
        # Переменные для отслеживания результатов последнего хода
        self.last_player_attack = None
        self.last_player_hit = False
        self.last_player_damage = 0
        
        self.last_enemy_attack = None
        self.last_enemy_hit = False
        self.last_enemy_damage = 0

    def is_over(self):
        return self.player.is_dead() or self.enemy.is_dead()

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
        attack_zone = random.choice(zones)
        defense_zones = random.sample(zones, 2)
        return attack_zone, defense_zones

    def calc_damage(self, attacker, defender, defender_is_defending=False):
        damage = attacker.attack - defender.defense
        if defender_is_defending:
            damage = max(1, damage // 2)
        return max(1, damage)

    def resolve_turn(self):
        if self.is_over() or self.player_attack_zone is None:
            return

        self.turn += 1

        enemy_attack, enemy_defense = self.enemy_choose_zones()

        player_attack_name = ZONES.get(self.player_attack_zone)
        enemy_attack_name = ZONES.get(enemy_attack)

        enemy_defense_names = [ZONES.get(zone) for zone in enemy_defense]
        player_defense_names = [ZONES.get(zone) for zone in self.player_defense_zones]

        # Флаги успешности атак
        player_blocked = self.player_attack_zone in enemy_defense
        enemy_blocked = enemy_attack in self.player_defense_zones
        
        player_damage = self.calc_damage(self.player, self.enemy, player_blocked)
        enemy_damage = self.calc_damage(self.enemy, self.player, enemy_blocked)

        # Запоминаем для UI
        self.last_player_attack = self.player_attack_zone
        self.last_player_hit = not player_blocked
        self.last_player_damage = player_damage
        
        self.last_enemy_attack = enemy_attack
        self.last_enemy_hit = not enemy_blocked
        self.last_enemy_damage = enemy_damage

        # Записываем историю хода
        turn_data = {
            "turn": self.turn,
            "player_log": [
                f"Атака: {player_attack_name}",
                f"Защита: {' и '.join(player_defense_names)}"
            ],
            "enemy_log": [
                f"Атака: {enemy_attack_name}",
                f"Защита: {' и '.join(enemy_defense_names)}"
            ]
        }
        self.history.append(turn_data)
        
        # Храним только 4 последних хода
        if len(self.history) > 4:
            self.history.pop(0)

        self.enemy.take_damage(player_damage)

        if not self.enemy.is_dead():
            self.player.take_damage(enemy_damage)
        else:
            self.player.gain_xp(30)
            self.player.try_level_up()

        self.player_attack_zone = None
        self.player_defense_zones = []
