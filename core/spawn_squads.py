"""Отряды волны точки спауна Front Line: один расчёт для сервера и для превью в редакторе карт."""


def planned_squad_ticks(count, squad_min, squad_max):
    """Примерное число отправлений волны: 2 × мобов ÷ (минимум + максимум)."""
    return max(1, round(2 * count / (squad_min + squad_max)))


def squad_size(tick, planned_ticks, squad_min, squad_max, remaining):
    """Размер отряда на отправлении tick: от минимума к максимуму.

    Последний отряд забирает весь остаток: если после текущего отряда останется меньше, чем он сам,
    в этом же отправлении уходят все оставшиеся мобы.
    """
    if planned_ticks <= 1 or tick >= planned_ticks - 1:
        size = squad_max
    else:
        size = squad_min + (squad_max - squad_min) * tick // (planned_ticks - 1)
    size = min(size, remaining)
    if remaining - size < size:
        size = remaining
    return size


def plan_squads(count, squad_min, squad_max):
    """Размеры всех отправлений волны по порядку."""
    planned = planned_squad_ticks(count, squad_min, squad_max)
    remaining, tick, sizes = count, 0, []
    while remaining > 0:
        size = squad_size(tick, planned, squad_min, squad_max, remaining)
        sizes.append(size)
        remaining -= size
        tick += 1
    return sizes


def _bounded_int(body, key, default, maximum):
    value = body.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= maximum:
        raise ValueError(f"{key} должен быть целым числом от 1 до {maximum}")
    return value


def preview(body, maximum):
    """Превью для редактора: сколько отправлений и сколько мобов в каждом."""
    if not isinstance(body, dict):
        raise ValueError("Настройки отряда должны быть объектом")
    count = _bounded_int(body, "count", 1, maximum)
    squad_min = _bounded_int(body, "squad_min", 1, maximum)
    squad_max = _bounded_int(body, "squad_max", squad_min, maximum)
    if squad_max < squad_min:
        raise ValueError("Отряд: максимум не меньше минимума")
    sizes = plan_squads(count, squad_min, squad_max)
    return {"ticks": len(sizes), "sizes": sizes}
