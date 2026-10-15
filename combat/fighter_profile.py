from combat.character_stats import BASE_STAT_VALUE


def apply_fighter_profile(fighter, profile):
    """Заполняет Fighter данными персонажа: характеристики, экипировка, HP и MP."""
    fighter.set_profession(profile.get("type"))
    fighter.name = profile.get("name", fighter.name)
    fighter.level = profile.get("level", fighter.level)
    fighter.xp = profile.get("xp", 0)
    fighter.stats = dict(profile.get("stats", {}))
    # Единый набор из 7 статов для всех персонажей — подстраховка для старых
    # сохранений, где часть характеристик ещё не была сохранена.
    for stat_name in fighter.STAT_NAMES:
        fighter.stats.setdefault(stat_name, BASE_STAT_VALUE)
    fighter.stat_points = profile.get("stat_points", 0)
    fighter.character_id = profile.get("id", profile.get("character_id"))
    fighter.equipment_stat_modifiers = {
        stat_name: int(value)
        for stat_name, value in profile.get("equipment_bonuses", {}).items()
        if stat_name in fighter.STAT_NAMES or stat_name in ("hp", "mp", "dodge", "block")
    }
    fighter.equipment = dict(profile.get("equipment", {}))
    fighter.recalculate_parameters()
    # Бой начинается с полным ресурсом класса для текущего уровня
    fighter.unique_resource_current = fighter.unique_resource_max
    hp = profile.get("hp", fighter.max_hp)
    if hp >= profile.get("max_hp", hp):
        # Полное здоровье остаётся полным и с бонусом выносливости от экипировки
        hp = fighter.max_hp
    fighter.hp = min(hp, fighter.max_hp)
    fighter.mp = min(profile.get("mp", fighter.max_mp), fighter.max_mp)
