def weapon_damage_range(equipment):
    """(мин, макс) урона надетого оружия или None. Урон хранится в effects["damage"] = [мин, макс]."""
    weapon = (equipment or {}).get("weapon") or {}
    damage = (weapon.get("effects") or {}).get("damage")
    if not damage or damage == [0, 0] or damage == (0, 0):
        shield = (equipment or {}).get("shield") or {}
        shield_damage = (shield.get("effects") or {}).get("damage")
        if shield_damage and shield_damage != [0, 0] and shield_damage != (0, 0):
            damage = shield_damage
    if not damage:
        return None
    if isinstance(damage, (int, float)):
        damage = (damage, damage)
    low, high = int(damage[0]), int(damage[-1])
    return min(low, high), max(low, high)
