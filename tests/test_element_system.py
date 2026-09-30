"""Тесты системы элементов и реакций (Фаза 6)."""
import pytest
from combat.fighter import Fighter
from combat.card_battle import CardBattle


class TestElementSystem:
    """Тесты системы элементов и реакций."""

    def test_check_element_reaction_fire_water(self):
        """Проверка реакции Огонь + Вода."""
        player = Fighter("Магнус", level=5, profession_type="battle_mage")
        enemy = Fighter("Враг", level=5, profession_type="battle_mage")
        battle = CardBattle(player, enemy)
        battle.mage_mode = True

        # Добавить статус огня
        battle.mage_statuses["enemy"] = [{"name": "огонь", "remaining": 2, "stacks": 1, "applied_turn": 1}]

        # Проверить реакцию
        reaction, affected = battle._check_element_reaction("enemy", "вода")
        assert reaction == "fire_water"
        assert set(affected) == {"огонь", "вода"}

    def test_check_element_reaction_fire_electric(self):
        """Проверка реакции Огонь + Электро."""
        player = Fighter("Магнус", level=5, profession_type="battle_mage")
        enemy = Fighter("Враг", level=5, profession_type="battle_mage")
        battle = CardBattle(player, enemy)
        battle.mage_mode = True

        battle.mage_statuses["enemy"] = [{"name": "огонь", "remaining": 2, "stacks": 1, "applied_turn": 1}]
        reaction, affected = battle._check_element_reaction("enemy", "электро")
        assert reaction == "fire_electric"
        assert set(affected) == {"огонь", "электро"}

    def test_check_element_reaction_water_cold(self):
        """Проверка реакции Вода + Холод."""
        player = Fighter("Магнус", level=5, profession_type="battle_mage")
        enemy = Fighter("Враг", level=5, profession_type="battle_mage")
        battle = CardBattle(player, enemy)
        battle.mage_mode = True

        battle.mage_statuses["enemy"] = [{"name": "вода", "remaining": 2, "stacks": 0, "applied_turn": 1}]
        reaction, affected = battle._check_element_reaction("enemy", "холод")
        assert reaction == "water_cold"
        assert affected == []  # Статусы НЕ снимаются

    def test_apply_status_effect(self):
        """Тест применения статуса элемента."""
        player = Fighter("Магнус", level=5, profession_type="battle_mage")
        enemy = Fighter("Враг", level=5, profession_type="battle_mage")
        battle = CardBattle(player, enemy)
        battle.mage_mode = True

        # Применить статус огня
        battle._apply_status_effect("player", "огонь", duration=2)

        assert len(battle.mage_statuses["player"]) == 1
        assert battle.mage_statuses["player"][0]["name"] == "огонь"
        assert battle.mage_statuses["player"][0]["remaining"] == 2

    def test_apply_reaction_effect_fire_water(self):
        """Тест применения эффекта реакции Огонь + Вода."""
        player = Fighter("Магнус", level=5, profession_type="battle_mage")
        enemy = Fighter("Враг", level=5, profession_type="battle_mage")
        battle = CardBattle(player, enemy)
        battle.mage_mode = True

        initial_hp = enemy.hp
        damage = 100

        # Применить реакцию огонь + вода (apply_reaction_effect наносит урон opposite_side)
        reaction_damage = battle._apply_reaction_effect("player", "fire_water", damage)

        # Урон должен быть 50% от оригинала
        assert reaction_damage == int(damage * 0.5)
        # enemy получает урон когда реакция на player
        assert enemy.hp < initial_hp

    def test_apply_reaction_effect_water_cold(self):
        """Тест применения эффекта реакции Вода + Холод (заморозка)."""
        player = Fighter("Магнус", level=5, profession_type="battle_mage")
        enemy = Fighter("Враг", level=5, profession_type="battle_mage")
        battle = CardBattle(player, enemy)
        battle.mage_mode = True

        initial_freeze = battle.mage_freeze.get("enemy", 0)

        # Применить реакцию вода + холод (к enemy)
        battle._apply_reaction_effect("player", "water_cold", 100)

        # Проверить что заморозка установлена для enemy
        assert battle.mage_freeze.get("enemy", 0) > initial_freeze

    def test_process_status_turn_effects_fire_damage(self):
        """Тест обработки урона от огня в конце хода."""
        player = Fighter("Магнус", level=5, profession_type="battle_mage")
        enemy = Fighter("Враг", level=5, profession_type="battle_mage")
        battle = CardBattle(player, enemy)
        battle.mage_mode = True

        initial_hp = enemy.hp

        # Добавить статус огня с 3 стеками
        battle.mage_statuses["enemy"] = [{"name": "огонь", "remaining": 2, "stacks": 3, "applied_turn": 1}]

        # Обработать эффекты
        battle._process_status_turn_effects()

        # Огонь наносит 2 HP × стеки = 6 HP
        expected_damage = 3 * 2
        assert enemy.hp == initial_hp - expected_damage

    def test_process_status_turn_effects_electric_stun(self):
        """Тест стана от электро после 3 ходов."""
        player = Fighter("Магнус", level=5, profession_type="battle_mage")
        enemy = Fighter("Враг", level=5, profession_type="battle_mage")
        battle = CardBattle(player, enemy)
        battle.mage_mode = True

        # Добавить статус электро, примененный 3 хода назад
        battle.turn = 4
        battle.mage_statuses["player"] = [{"name": "электро", "remaining": 2, "stacks": 0, "applied_turn": 1}]

        # Обработать эффекты
        battle._process_status_turn_effects()

        # Проверить что добавлен стан
        assert battle.mage_stuns.get("player", 0) > 0

        # Проверить что добавлена иммунитет на стан
        stun_immunity = next((s for s in battle.mage_statuses["player"] if s["name"] == "stun_immunity"), None)
        assert stun_immunity is not None
        assert stun_immunity["remaining"] == 2

    def test_remove_expired_statuses(self):
        """Тест удаления истекших статусов."""
        player = Fighter("Магнус", level=5, profession_type="battle_mage")
        enemy = Fighter("Враг", level=5, profession_type="battle_mage")
        battle = CardBattle(player, enemy)
        battle.mage_mode = True

        # Добавить несколько статусов
        battle.mage_statuses["player"] = [
            {"name": "огонь", "remaining": 3, "stacks": 1, "applied_turn": 1},
            {"name": "вода", "remaining": 2, "stacks": 0, "applied_turn": 1},
        ]

        # Удалить истекшие (уменьшает remaining и удаляет если <= 0)
        battle._remove_expired_statuses()

        # После первого вызова remaining уменьшится на 1
        assert len(battle.mage_statuses["player"]) == 2
        assert battle.mage_statuses["player"][0]["remaining"] == 2
        assert battle.mage_statuses["player"][1]["remaining"] == 1

    def test_reaction_without_matching_element(self):
        """Тест что реакции не срабатывают без соответствующих элементов."""
        player = Fighter("Магнус", level=5, profession_type="battle_mage")
        enemy = Fighter("Враг", level=5, profession_type="battle_mage")
        battle = CardBattle(player, enemy)
        battle.mage_mode = True

        # Добавить только огонь
        battle.mage_statuses["enemy"] = [{"name": "огонь", "remaining": 2, "stacks": 1, "applied_turn": 1}]

        # Попытаться применить электро (огонь + электро = реакция)
        # но если применить холод без воды - реакции не будет
        reaction, affected = battle._check_element_reaction("enemy", "холод")
        assert reaction == "fire_cold"  # Это IS реакция

        # Проверить что без элементов реакции нет
        battle.mage_statuses["enemy"] = []
        reaction, affected = battle._check_element_reaction("enemy", "холод")
        assert reaction is None

    def test_electric_replaces_electric(self):
        """Тест что новый электро заменяет старый."""
        player = Fighter("Магнус", level=5, profession_type="battle_mage")
        enemy = Fighter("Враг", level=5, profession_type="battle_mage")
        battle = CardBattle(player, enemy)
        battle.mage_mode = True

        # Применить электро дважды
        battle._apply_status_effect("player", "электро", duration=2)
        assert len(battle.mage_statuses["player"]) == 1

        # Применить еще один электро
        battle._apply_status_effect("player", "электро", duration=3)

        # Должно остаться только 1 электро с новой длительностью
        electric_statuses = [s for s in battle.mage_statuses["player"] if s["name"] == "электро"]
        assert len(electric_statuses) == 1
        assert electric_statuses[0]["remaining"] == 3
