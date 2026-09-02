"""
АФК система для боев - сохранение состояния при отключении
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class AFKBattleManager:
    """
    Управляет АФК статусом персонажа в боях
    
    Примечание: АФК персонаж НЕ выполняет автоматические действия!
    Только управляется игроком когда он подключен.
    АФК персонаж просто стоит и получает урон.
    """

    @staticmethod
    def can_player_act_if_afk() -> bool:
        """
        Определяет может ли персонаж действовать когда отключен
        
        Returns:
            False - АФК персонаж не может действовать
        """
        # АФК персонаж не может делать ходы автоматически
        # Только игрок может управлять персонажем
        return False

    @staticmethod
    def should_receive_damage_while_afk() -> bool:
        """
        Определяет получает ли АФК персонаж урон
        
        Returns:
            True - АФК персонаж получает урон как обычно
        """
        # АФК персонаж получает урон как любой другой персонаж
        return True

    @staticmethod
    def should_regenerate_during_afk() -> bool:
        """
        Определяет восстанавливает ли АФК персонаж HP во время боя
        
        Returns:
            False - АФК персонаж не регенерирует HP во время боя
        """
        # АФК персонаж НЕ регенерирует HP во время боя
        return False


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
