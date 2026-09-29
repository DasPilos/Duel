# Карточка персонажа-мага
from combat.character_stats import MIN_STAT_VALUE, calculate_max_mana
from core import settings
from ui.character_card import CharacterCard
from ui.character_profile import STAT_ROWS
from ui.hud import FloatingText


class MageCard(CharacterCard):
    """
    Карточка мага — та же CharacterCard: HP/MP, монеты, кукла со слотами и блок
    характеристик рисуются общим кодом, одинаково для всех классов.

    Своё у мага только правила прокачки статов и всплывающий текст регенерации маны.
    """

    # Отдельный реестр: один экземпляр карточки мага на персонажа (по id)
    _REGISTRY = {}

    _stat_names = tuple(key for key, _, _ in STAT_ROWS)

    def show_regen(self, amount):
        """Показать анимацию восстановления маны"""
        self.regen_floating_texts.append(
            FloatingText(
                0,
                0,
                f"+{int(amount)} MP",
                self.small_font,
                color=(60, 140, 220),  # Голубой цвет для маны
                duration=settings.FLOATING_TEXT_DURATION,
            )
        )

    def adjust_stat(self, stat_name, delta):
        """Изменить mage-стат по единым правилам (минимум 3, выносливость только за уровень)."""
        if stat_name not in self._stat_names or delta not in (-1, 1):
            return False
        if stat_name == "endurance" and delta > 0:
            return False
        if delta > 0 and self.state["stat_points"] <= 0:
            return False
        current = int(self.state["stats"].get(stat_name, MIN_STAT_VALUE))
        if delta < 0 and current <= MIN_STAT_VALUE:
            return False
        updated = current + delta
        self.state["stats"][stat_name] = updated
        self.state["stat_points"] -= delta
        if stat_name == "intellect":
            self.state["max_mp"] = calculate_max_mana(updated)
            self.state["mp"] = min(int(self.state["mp"]), self.state["max_mp"])
        return True
