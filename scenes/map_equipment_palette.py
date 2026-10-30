"""Палитра экипировки в редакторе карт: предметы по слотам, иконки в размер тайла палитры объектов.

Интерфейс как у scenes/map_palette.Palette (высота, зум, попадание мыши, отрисовка), чтобы вкладка «Экипировка»
прокручивалась и масштабировалась так же, как объекты.
"""
from bisect import bisect_right
from dataclasses import dataclass, field

import pygame

from scenes.map_palette import (
    BLOCK_PAD,
    BLOCK_X,
    CELL_BG,
    CLUSTER_GAP,
    GRID_COLOR,
    HEADER_BG,
    HEADER_H,
    PANEL_MARGIN,
    PALETTE_TILE_MAX,
    PALETTE_TILE_MIN,
    SELECT_COLOR,
    TEXT,
    TEXT_DIM,
)
from ui.catalog_icons import draw_item_icon

CELL_GAP = 4
CAPTION_H = 26
# Порядок слотов как у куклы персонажа
EQUIP_SLOT_ORDER = (
    "head", "ears", "neck", "back", "body", "hands", "weapon", "shield", "belt", "ring", "ring_2", "legs", "feet",
)
EQUIP_SLOT_TITLES = {
    "head": "Голова", "ears": "Серьги", "neck": "Шея", "back": "Плащ", "body": "Доспех", "hands": "Руки",
    "weapon": "Правая рука (оружие)", "shield": "Левая рука (щит)", "belt": "Пояс",
    "ring": "Кольцо 1", "ring_2": "Кольцо 2", "legs": "Ноги", "feet": "Обувь",
}


def equipment_key(item):
    """Ключ предмета в палитре: отдельное пространство имён, чтобы не путать с объектами карты."""
    return f"eq:{int(item['id'])}"


@dataclass
class _Row:
    kind: str  # header, caption или cells
    top: int
    height: int
    title: str = ""
    cells: list = field(default_factory=list)  # [(rect относительно строки, предмет)]


class EquipmentPalette:
    def __init__(self, items, font, small, width, tile):
        self.font = font
        self.small = small
        self.width = width
        self.tile = tile
        self.count = len(items)
        self._items = {equipment_key(item): item for item in items}
        self._sections = []
        for slot in EQUIP_SLOT_ORDER:
            slot_items = sorted((item for item in items if item.get("equip_slot") == slot), key=lambda i: int(i["id"]))
            self._sections.append((EQUIP_SLOT_TITLES[slot], slot_items))
        self._layout()

    def columns(self):
        return max(1, (self.width - PANEL_MARGIN) // (self.tile + CELL_GAP))

    def panel_width(self):
        return self.width

    def set_tile(self, tile):
        tile = max(PALETTE_TILE_MIN, min(PALETTE_TILE_MAX, tile))
        if tile == self.tile:
            return
        self.tile = tile
        self._layout()

    def item(self, key):
        return self._items.get(key)

    def _layout(self):
        self.rows = []
        top = 0
        cols = self.columns()
        row_h = self.tile + CELL_GAP + 2 * BLOCK_PAD
        for title, items in self._sections:
            self._add(_Row("header", top, HEADER_H, title=title))
            top += HEADER_H
            if not items:
                self._add(_Row("caption", top, CAPTION_H, title="нет предметов в базе"))
                top += CAPTION_H + CLUSTER_GAP
                continue
            for start in range(0, len(items), cols):
                cells = []
                for column, item in enumerate(items[start:start + cols]):
                    rect = pygame.Rect(BLOCK_X + column * (self.tile + CELL_GAP), BLOCK_PAD, self.tile, self.tile)
                    cells.append((rect, item))
                self._add(_Row("cells", top, row_h, cells=cells))
                top += row_h
            top += CLUSTER_GAP
        self.height = top

    def _add(self, row):
        self.rows.append(row)
        self._tops = [r.top for r in self.rows]

    def item_at(self, x, y):
        """Ключ предмета под точкой (x, y) в координатах содержимого палитры (без прокрутки) или None."""
        index = bisect_right(self._tops, y) - 1
        if index < 0:
            return None
        row = self.rows[index]
        if row.kind != "cells" or y >= row.top + row.height:
            return None
        local_x, local_y = x, y - row.top
        for rect, item in row.cells:
            if rect.collidepoint(local_x, local_y):
                return equipment_key(item)
        return None

    def draw(self, screen, view, scroll, selected, marquee=None, hovered=None, ticks=0):
        previous_clip = screen.get_clip()
        screen.set_clip(view)
        first = max(0, bisect_right(self._tops, scroll) - 1)
        for row in self.rows[first:]:
            y = view.top + row.top - scroll
            if y >= view.bottom:
                break
            if y + row.height <= view.top:
                continue
            if row.kind == "header":
                pygame.draw.rect(screen, HEADER_BG, (view.x, y + 2, view.w, row.height - 4))
                title = self.font.render(row.title, True, TEXT)
                screen.blit(title, (view.x + BLOCK_X, y + (row.height - title.get_height()) // 2))
            elif row.kind == "caption":
                screen.blit(self.small.render(row.title, True, TEXT_DIM), (view.x + BLOCK_X, y + 4))
            else:
                for rect, item in row.cells:
                    cell = rect.move(view.x, y)
                    key = equipment_key(item)
                    pygame.draw.rect(screen, CELL_BG, cell)
                    if draw_item_icon(screen, item, cell.topleft, self.tile) is None:
                        letter = self.small.render(item["name"][:1], True, TEXT)
                        screen.blit(letter, letter.get_rect(center=cell.center))
                    pygame.draw.rect(screen, GRID_COLOR, cell, 1)
                    if key == selected:
                        pygame.draw.rect(screen, SELECT_COLOR, cell, 2)
                    elif key == hovered:
                        pygame.draw.rect(screen, TEXT_DIM, cell, 1)
        screen.set_clip(previous_clip)
