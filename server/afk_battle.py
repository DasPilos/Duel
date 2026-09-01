"""
АФК система для боев - автоматические действия персонажа при отключении
"""

import random
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class AFKBattleManager:
    """Управляет автоматическими действиями АФК персонажей"""

    @staticmethod
    def select_afk_card(available_cards: list) -> Optional[Dict[str, Any]]:
        """
        Выбирает случайную карту для АФК персонажа
        
        Args:
            available_cards: Список доступных карт из руки
            
        Returns:
            Выбранная карта или None если нет карт
        """
        if not available_cards:
            return None
        return random.choice(available_cards)

    @staticmethod
    def select_afk_attack_zone(valid_zones: list) -> Optional[str]:
        """
        Выбирает случайную зону атаки для АФК персонажа
        
        Args:
            valid_zones: Список доступных зон атаки
            
        Returns:
            Выбранная зона (front/center/back) или None
        """
        if not valid_zones:
            return None
        return random.choice(valid_zones)

    @staticmethod
    def should_regenerate_during_afk() -> bool:
        """
        Определяет, должен ли АФК персонаж восстанавливать HP во время боя
        
        Returns:
            True если нужна регенерация, False если нет
        """
        # АФК персонаж НЕ регенерирует HP во время боя (только между боями)
        return False

    @staticmethod
    def get_afk_strategy() -> str:
        """
        Получает текущую стратегию АФК персонажа
        
        Returns:
            Стратегия ('random', 'aggressive', 'defensive')
        """
        # Простая стратегия - случайные действия
        # В будущем можно добавить более интеллектуальные стратегии
        return 'random'


class AFKBattleHandler:
    """Обработчик боев с участием АФК персонажей"""

    def __init__(self, database):
        """
        Инициализирует обработчик АФК боев
        
        Args:
            database: Экземпляр Database для сохранения состояния
        """
        self.db = database
        self.manager = AFKBattleManager()

    def mark_player_afk(self, player_id: int, opponent_id: int) -> None:
        """Отмечает игрока как АФК в активном боевом сеансе"""
        logger.info(f"Игрок {player_id} отмечен как АФК (противник {opponent_id})")
        self.db.mark_player_afk(player_id, opponent_id, is_afk=True)

    def unmark_player_afk(self, player_id: int, opponent_id: int) -> None:
        """Убирает статус АФК когда игрок переподключается"""
        logger.info(f"Игрок {player_id} переподключился (противник {opponent_id})")
        self.db.mark_player_afk(player_id, opponent_id, is_afk=False)

    def save_battle_state(self, player_id: int, opponent_id: int, battle_data: Dict[str, Any]) -> None:
        """Сохраняет текущее состояние боя в базе данных"""
        self.db.save_active_battle(player_id, opponent_id, battle_data)

    def restore_battle_state(self, player_id: int, opponent_id: int) -> Optional[Dict[str, Any]]:
        """Восстанавливает состояние боя при переподключении"""
        battle = self.db.get_active_battle(player_id, opponent_id)
        if battle:
            logger.info(f"Восстановлено состояние боя для игрока {player_id}")
            return battle
        return None

    def cleanup_battle(self, player_id: int, opponent_id: int) -> None:
        """Очищает данные завершенного боя"""
        self.db.delete_active_battle(player_id, opponent_id)
