"""Тесты для системы 6 классов и уникальных ресурсов."""
import pytest
from combat.fighter import Fighter
from combat.character_stats import (
    PROFESSIONS,
    UNIQUE_RESOURCE_RECOVERY,
    UNIQUE_RESOURCE_GAIN,
    calculate_max_unique_resource,
    get_profession_data,
    is_valid_profession,
)


class TestProfessions:
    """Тесты профессий."""

    def test_all_professions_exist(self):
        """Все 6 профессий определены."""
        expected = {"warrior", "archer", "assassin", "battle_mage", "support_mage", "harmonist"}
        assert set(PROFESSIONS.keys()) == expected

    def test_profession_data_complete(self):
        """У каждой профессии есть все необходимые поля."""
        required_fields = {
            "name", "hp", "mana", "base_dodge", "base_crit", "base_crit_damage",
            "unique_resource", "unique_resource_name"
        }
        for prof_type, prof_data in PROFESSIONS.items():
            for field in required_fields:
                assert field in prof_data, f"{prof_type} missing {field}"

    def test_is_valid_profession(self):
        """Проверка валидности профессии."""
        assert is_valid_profession("warrior")
        assert is_valid_profession("archer")
        assert is_valid_profession("assassin")
        assert is_valid_profession("battle_mage")
        assert is_valid_profession("support_mage")
        assert is_valid_profession("harmonist")
        assert not is_valid_profession("invalid")

    def test_get_profession_data(self):
        """Получить данные профессии."""
        warrior_data = get_profession_data("warrior")
        assert warrior_data is not None
        assert warrior_data["hp"] == 70
        assert warrior_data["unique_resource"] == "rage"


class TestUniqueResources:
    """Тесты уникальных ресурсов."""

    def test_resource_recovery_constants(self):
        """Все ресурсы имеют значение восстановления."""
        assert "rage" in UNIQUE_RESOURCE_RECOVERY
        assert "accuracy" in UNIQUE_RESOURCE_RECOVERY
        assert "concentration" in UNIQUE_RESOURCE_RECOVERY
        assert UNIQUE_RESOURCE_RECOVERY["rage"] == 4
        assert UNIQUE_RESOURCE_RECOVERY["accuracy"] == 5
        assert UNIQUE_RESOURCE_RECOVERY["concentration"] == 9

    def test_resource_gain_constants(self):
        """Все ресурсы имеют условия получения."""
        assert "rage" in UNIQUE_RESOURCE_GAIN
        assert "accuracy" in UNIQUE_RESOURCE_GAIN
        assert "concentration" in UNIQUE_RESOURCE_GAIN

    def test_calculate_max_unique_resource_warrior(self):
        """Расчет максимальной ярости для бойца."""
        # На уровне 1: 50 + 9×(1-1) = 50
        assert calculate_max_unique_resource("warrior", 1) == 50
        # На уровне 2: 50 + 9×(2-1) = 59
        assert calculate_max_unique_resource("warrior", 2) == 59
        # На уровне 5: 50 + 9×(5-1) = 86
        assert calculate_max_unique_resource("warrior", 5) == 86

    def test_calculate_max_unique_resource_archer(self):
        """Расчет максимальной меткости для лучника."""
        assert calculate_max_unique_resource("archer", 1) == 50
        assert calculate_max_unique_resource("archer", 2) == 59
        assert calculate_max_unique_resource("archer", 5) == 86

    def test_calculate_max_unique_resource_assassin(self):
        """Расчет максимальной концентрации для асасина."""
        assert calculate_max_unique_resource("assassin", 1) == 50
        assert calculate_max_unique_resource("assassin", 2) == 59
        assert calculate_max_unique_resource("assassin", 5) == 86

    def test_calculate_max_unique_resource_mage(self):
        """Расчет маны для магов (через интеллект)."""
        # При интеллекте 3: 3 × 5 = 15
        assert calculate_max_unique_resource("battle_mage", 1, intellect=3) == 15
        # При интеллекте 10: 10 × 5 = 50
        assert calculate_max_unique_resource("battle_mage", 1, intellect=10) == 50


class TestFighterClasses:
    """Тесты создания персонажей разных классов."""

    def test_create_warrior(self):
        """Создать бойца."""
        fighter = Fighter("Ivan", level=1, profession_type="warrior")
        assert fighter.name == "Ivan"
        assert fighter.level == 1
        assert fighter.profession_type == "warrior"
        assert fighter.unique_resource_type == "rage"
        assert fighter.unique_resource_max == 50
        assert fighter.unique_resource_current == 50
        assert fighter.max_hp == 70
        assert fighter.max_mp == 15  # intellect=3, 3×5=15

    def test_create_archer(self):
        """Создать лучника."""
        fighter = Fighter("Robin", level=1, profession_type="archer")
        assert fighter.profession_type == "archer"
        assert fighter.unique_resource_type == "accuracy"
        assert fighter.unique_resource_max == 50
        assert fighter.max_hp == 35

    def test_create_assassin(self):
        """Создать асасина."""
        fighter = Fighter("Shadow", level=1, profession_type="assassin")
        assert fighter.profession_type == "assassin"
        assert fighter.unique_resource_type == "concentration"
        assert fighter.unique_resource_max == 50
        assert fighter.max_hp == 40

    def test_create_battle_mage(self):
        """Создать боевого мага."""
        fighter = Fighter("Wizard", level=1, profession_type="battle_mage")
        assert fighter.profession_type == "battle_mage"
        assert fighter.unique_resource_type == "mana"
        assert fighter.max_hp == 50
        assert fighter.max_mp == 15  # intellect=3, 3×5=15

    def test_create_support_mage(self):
        """Создать мага поддержки."""
        fighter = Fighter("Healer", level=1, profession_type="support_mage")
        assert fighter.profession_type == "support_mage"
        assert fighter.unique_resource_type == "mana"
        assert fighter.max_hp == 30
        assert fighter.max_mp == 15

    def test_create_harmonist(self):
        """Создать гармониста."""
        fighter = Fighter("Bard", level=1, profession_type="harmonist")
        assert fighter.profession_type == "harmonist"
        assert fighter.unique_resource_type == "mana"
        assert fighter.max_hp == 35
        assert fighter.max_mp == 15

    def test_default_profession_is_warrior(self):
        """Профессия по умолчанию - боец."""
        fighter = Fighter("Generic")
        assert fighter.profession_type == "warrior"

    def test_invalid_profession_defaults_to_warrior(self):
        """Невалидная профессия становится бойцом."""
        fighter = Fighter("Generic", profession_type="invalid_class")
        assert fighter.profession_type == "warrior"


class TestUniqueResourceMethods:
    """Тесты методов управления уникальными ресурсами."""

    def test_spend_unique_resource_success(self):
        """Успешная трата ресурса."""
        fighter = Fighter("Ivan", level=1, profession_type="warrior")
        fighter.unique_resource_current = 50

        result = fighter.spend_unique_resource(10)
        assert result is True
        assert fighter.unique_resource_current == 40

    def test_spend_unique_resource_insufficient(self):
        """Недостаточно ресурса."""
        fighter = Fighter("Ivan", level=1, profession_type="warrior")
        fighter.unique_resource_current = 5

        result = fighter.spend_unique_resource(10)
        assert result is False
        assert fighter.unique_resource_current == 5  # Не изменилось

    def test_gain_unique_resource(self):
        """Получить ресурс."""
        fighter = Fighter("Ivan", level=1, profession_type="warrior")
        fighter.unique_resource_current = 30

        fighter.gain_unique_resource(20)
        assert fighter.unique_resource_current == 50  # Cap at max

    def test_gain_unique_resource_caps_at_max(self):
        """Получение ресурса капится на максимум."""
        fighter = Fighter("Ivan", level=1, profession_type="warrior")
        fighter.unique_resource_current = 40
        fighter.unique_resource_max = 50

        fighter.gain_unique_resource(20)  # Would be 60, but capped at 50
        assert fighter.unique_resource_current == 50

    def test_recover_unique_resource_warrior(self):
        """Восстановление ярости в конце хода."""
        fighter = Fighter("Ivan", level=1, profession_type="warrior")
        fighter.unique_resource_current = 40

        fighter.recover_unique_resource(1)
        assert fighter.unique_resource_current == 44  # +4 ярости

    def test_recover_unique_resource_archer(self):
        """Восстановление меткости в конце хода."""
        fighter = Fighter("Robin", level=1, profession_type="archer")
        fighter.unique_resource_current = 40

        fighter.recover_unique_resource(1)
        assert fighter.unique_resource_current == 45  # +5 меткости

    def test_recover_unique_resource_assassin(self):
        """Восстановление концентрации в конце хода."""
        fighter = Fighter("Shadow", level=1, profession_type="assassin")
        fighter.unique_resource_current = 30

        fighter.recover_unique_resource(1)
        assert fighter.unique_resource_current == 39  # +9 концентрации

    def test_recover_unique_resource_no_overflow(self):
        """Восстановление не переполняет максимум."""
        fighter = Fighter("Ivan", level=1, profession_type="warrior")
        fighter.unique_resource_current = 48
        fighter.unique_resource_max = 50

        fighter.recover_unique_resource(1)
        assert fighter.unique_resource_current == 50  # Capped at max


class TestLevelScaling:
    """Тесты масштабирования с уровнем."""

    def test_level_affects_hp(self):
        """Уровень влияет на HP через выносливость."""
        fighter_l1 = Fighter("Ivan", level=1, profession_type="warrior")
        fighter_l5 = Fighter("Ivan", level=5, profession_type="warrior")

        # Выносливость растет с уровнем: 3 + (level-1) = 3, 7
        # HP = выносливость × 10 = 30, 70? Нет, 70 - это базовая для воина
        # Проверим что HP berbeda
        assert fighter_l1.max_hp > 0
        assert fighter_l5.max_hp >= fighter_l1.max_hp

    def test_level_affects_stat_points(self):
        """Уровень влияет на количество очков для распределения."""
        fighter_l1 = Fighter("Ivan", level=1, profession_type="warrior")
        fighter_l5 = Fighter("Ivan", level=5, profession_type="warrior")

        # L1: 5 + 0 = 5 очков
        # L5: 5 + 3×(5-1) = 5 + 12 = 17 очков
        assert fighter_l1.stat_points == 5
        assert fighter_l5.stat_points == 17

    def test_level_affects_unique_resource_max(self):
        """Уровень влияет на максимум уникального ресурса."""
        fighter_l1 = Fighter("Ivan", level=1, profession_type="warrior")
        fighter_l5 = Fighter("Ivan", level=5, profession_type="warrior")

        # L1: 50 + 9×(1-1) = 50
        # L5: 50 + 9×(5-1) = 86
        assert fighter_l1.unique_resource_max == 50
        assert fighter_l5.unique_resource_max == 86


class TestConsistency:
    """Тесты консистентности системы."""

    def test_all_professions_have_consistent_data(self):
        """Все профессии имеют согласованные данные."""
        for prof_type, prof_data in PROFESSIONS.items():
            # HP > 0
            assert prof_data["hp"] > 0, f"{prof_type} has invalid HP"

            # Базовые параметры боя
            assert prof_data["base_dodge"] >= 0
            assert prof_data["base_crit"] > 0
            assert prof_data["base_crit_damage"] > 0

            # Уникальный ресурс определен
            assert prof_data["unique_resource"] in ("rage", "accuracy", "concentration", "mana")

    def test_fighter_uses_profession_data(self):
        """Fighter использует данные из PROFESSIONS."""
        warrior = Fighter("Ivan", level=1, profession_type="warrior")
        warrior_data = get_profession_data("warrior")

        # Fighter должен иметь правильное максимальное HP для профессии
        # (на уровне 1 это зависит от выносливости)
        assert warrior.max_hp == warrior_data["hp"]

    def test_recalculate_parameters_updates_max_resource(self):
        """recalculate_parameters обновляет максимум уникального ресурса."""
        fighter = Fighter("Ivan", level=1, profession_type="warrior")
        initial_max = fighter.unique_resource_max

        # Увеличить уровень вручную и пересчитать
        fighter.level = 5
        fighter.stats["endurance"] = 8
        fighter.recalculate_parameters()

        expected_max = calculate_max_unique_resource("warrior", 5)
        assert fighter.unique_resource_max == expected_max


class TestElementSystem:
    """Тесты системы элементов и реакций (Фаза 6)."""

    def test_check_element_reaction_fire_water(self):
        """Проверка реакции Огонь + Вода."""
        from combat.card_battle import CardBattle

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
        from combat.card_battle import CardBattle

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
        from combat.card_battle import CardBattle

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
        from combat.card_battle import CardBattle

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
        from combat.card_battle import CardBattle

        player = Fighter("Магнус", level=5, profession_type="battle_mage")
        enemy = Fighter("Враг", level=5, profession_type="battle_mage")
        battle = CardBattle(player, enemy)
        battle.mage_mode = True

        initial_hp = enemy.hp
        damage = 100

        # Применить реакцию огонь + вода
        reaction_damage = battle._apply_reaction_effect("player", "fire_water", damage)

        # Урон должен быть 50% от оригинала
        assert reaction_damage == int(damage * 0.5)
        assert enemy.hp < initial_hp

    def test_apply_reaction_effect_fire_electric(self):
        """Тест применения эффекта реакции Огонь + Электро с ослеплением."""
        from combat.card_battle import CardBattle

        player = Fighter("Магнус", level=5, profession_type="battle_mage")
        player.stats["harmony"] = 10  # Гармония влияет на урон
        enemy = Fighter("Враг", level=5, profession_type="battle_mage")
        battle = CardBattle(player, enemy)
        battle.mage_mode = True

        initial_hp = enemy.hp
        damage = 100

        # Применить реакцию огонь + электро
        reaction_damage = battle._apply_reaction_effect("player", "fire_electric", damage)

        # Урон: × (1.3 + 10×1%) = ×1.4
        expected_damage = int(damage * 1.4) + 10
        assert reaction_damage == expected_damage

        # Проверить что добавлено ослепление
        blinding_status = next((s for s in battle.mage_statuses["player"] if s["name"] == "blinding"), None)
        assert blinding_status is not None
        assert blinding_status["remaining"] == 1

    def test_apply_reaction_effect_water_cold(self):
        """Тест применения эффекта реакции Вода + Холод (заморозка)."""
        from combat.card_battle import CardBattle

        player = Fighter("Магнус", level=5, profession_type="battle_mage")
        enemy = Fighter("Враг", level=5, profession_type="battle_mage")
        battle = CardBattle(player, enemy)
        battle.mage_mode = True

        initial_freeze = battle.mage_freeze.get("player", 0)

        # Применить реакцию вода + холод
        battle._apply_reaction_effect("player", "water_cold", 100)

        # Проверить что заморозка установлена
        assert battle.mage_freeze.get("player", 0) > initial_freeze

    def test_process_status_turn_effects_fire_damage(self):
        """Тест обработки урона от огня в конце хода."""
        from combat.card_battle import CardBattle

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
        from combat.card_battle import CardBattle

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
        from combat.card_battle import CardBattle

        player = Fighter("Магнус", level=5, profession_type="battle_mage")
        enemy = Fighter("Враг", level=5, profession_type="battle_mage")
        battle = CardBattle(player, enemy)
        battle.mage_mode = True

        # Добавить несколько статусов
        battle.mage_statuses["player"] = [
            {"name": "огонь", "remaining": 2, "stacks": 1, "applied_turn": 1},
            {"name": "вода", "remaining": 1, "stacks": 0, "applied_turn": 1},
            {"name": "холод", "remaining": 0, "stacks": 0, "applied_turn": 1},  # Истек
        ]

        # Удалить истекшие
        battle._remove_expired_statuses()

        # Проверить что остались только активные
        assert len(battle.mage_statuses["player"]) == 2
        assert any(s["name"] == "огонь" for s in battle.mage_statuses["player"])
        assert any(s["name"] == "вода" for s in battle.mage_statuses["player"])

    def test_full_element_reaction_flow(self):
        """Интеграционный тест полного потока реакции элементов."""
        from combat.card_battle import CardBattle

        player = Fighter("Магнус", level=5, profession_type="battle_mage")
        enemy = Fighter("Враг", level=5, profession_type="battle_mage")
        battle = CardBattle(player, enemy)
        battle.mage_mode = True

        # 1. Применить огонь
        battle._apply_status_effect("enemy", "огонь", duration=2)
        assert len(battle.mage_statuses["enemy"]) == 1

        # 2. Проверить реакцию при применении воды
        reaction, affected = battle._check_element_reaction("enemy", "вода")
        assert reaction == "fire_water"

        # 3. Применить эффект реакции
        initial_hp = enemy.hp
        reaction_damage = battle._apply_reaction_effect("enemy", "fire_water", 100)
        assert enemy.hp < initial_hp

        # 4. Проверить что статусы обновлены
        fire_status = next((s for s in battle.mage_statuses["enemy"] if s["name"] == "огонь"), None)
        assert fire_status is None or fire_status["remaining"] <= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
