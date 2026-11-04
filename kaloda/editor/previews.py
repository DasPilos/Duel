"""Картинки мобов для редактора: процедурные фигуры Колоды с арены, нарисованные на прозрачном холсте."""
import functools

import pygame

from kaloda.ui.arena_overlay import draw_ancient_ent, draw_kobold, draw_necromancer, draw_skeleton

PREVIEW_SIDE = 112
PREVIEW_TILE = 48
# Ноги стоят у нижней части холста: фигуры рисуются от центра (cx, cy) тайла 48 px, как на арене
PREVIEW_CENTER = (56, 70)
# Лагерь: сначала дальний кобольд, затем ближние, чтобы ближние перекрывали дальних
CAMP_OFFSETS = ((0, -8), (-14, 6), (14, 4))

_DRAWERS = {
    "kobold": draw_kobold,
    "ancient_ent": draw_ancient_ent,
    "skeleton": draw_skeleton,
    "necromancer": draw_necromancer,
}


def draw_mob(screen, kind, cx, cy, tile):
    """Рисует вид моба на экране: лагерь кобольдов — три кобольда, остальные виды — одна фигура."""
    if kind == "kobold_camp":
        scale = tile / PREVIEW_TILE
        for dx, dy in CAMP_OFFSETS:
            draw_kobold(screen, cx + round(dx * scale), cy + round(dy * scale), tile)
        return
    _DRAWERS[kind](screen, cx, cy, tile)


@functools.cache
def mob_image(kind, side):
    """Квадрат side×side с видом моба. Рисуется один раз и кэшируется; неизвестный вид — ValueError."""
    if kind != "kobold_camp" and kind not in _DRAWERS:
        raise ValueError(f"Нет картинки для моба «{kind}»")
    canvas = pygame.Surface((PREVIEW_SIDE, PREVIEW_SIDE), pygame.SRCALPHA)
    draw_mob(canvas, kind, *PREVIEW_CENTER, PREVIEW_TILE)
    if side == PREVIEW_SIDE:
        return canvas
    return pygame.transform.smoothscale(canvas, (side, side))
