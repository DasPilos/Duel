import math
import random

DASH_RANGE = 500.0  # максимальная длина рывка, px
DASH_HIT_RADIUS = 60.0  # мобы в этом радиусе от линии рывка получают урон, px
DASH_DAMAGE_MIN = 12
DASH_DAMAGE_MAX = 18
DASH_COOLDOWN = 40.0  # секунд до следующего рывка
DASH_TRAIL_DURATION = 5.0  # сколько секунд висит след вихря
DASH_SPEED = 500.0  # px/с
DASH_MIN_LENGTH = 8.0  # короче этого рывок не запускается


WHIRL_STRIKE_RADIUS = 80.0  # круговой удар в конце рывка, px от персонажа
WHIRL_STRIKE_DAMAGE_MIN = 20
WHIRL_STRIKE_DAMAGE_MAX = 25


def dash_end_point(start, target, max_range=DASH_RANGE):
    """Точка назначения рывка: полная дальность по направлению на цель (курсор задаёт только направление)."""
    dx = target[0] - start[0]
    dy = target[1] - start[1]
    distance = math.hypot(dx, dy)
    if distance == 0:
        return (float(start[0]), float(start[1]))
    scale = max_range / distance
    return (start[0] + dx * scale, start[1] + dy * scale)


def point_segment_distance(point, a, b):
    """Расстояние от точки до отрезка ab."""
    px, py = point
    ax, ay = a
    dx = b[0] - ax
    dy = b[1] - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def dash_damage_roll(rng=random):
    return rng.randint(DASH_DAMAGE_MIN, DASH_DAMAGE_MAX)


def whirl_strike_damage_roll(rng=random):
    return rng.randint(WHIRL_STRIKE_DAMAGE_MIN, WHIRL_STRIKE_DAMAGE_MAX)
