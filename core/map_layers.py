"""Слои карты: 0 — вода, 1 — дорога и земля, 2 — трава, 3 — листва и возвышенность, 4 — камни и горы.

Слой тайла задаёт блок образца палитры, в котором он лежит: всё в блоке дороги — слой 1, всё в блоке травы — слой 2
(в том числе переходные тайлы). Тайлы вне образцов определяются категорией. Объекты вне слоёв.
"""
import functools

from core.map_catalog import palette_group_layers, palette_groups

LAYER_BY_CATEGORY = {
    "water": 0,
    "road": 1,
    "floor": 1,
    "grass": 2,
    "leaves": 3,
    "rock": 4,
}
# Блоки образца палитры по позициям: дорога и её декор и малые тайлы дороги — слой 1, трава — 2,
# возвышенность — 3, реки — 0 (вода), горы — 4 (камни и горы)
LAYER_BY_BLOCK_ROLE = {
    "ground": 1, "ground_decor": 1, "ground_small": 1,
    "grass": 2, "grass_decor": 2, "grass_small": 2,
    "elevation": 3,
    "river": 0, "mountain": 4,
}
LAYER_NAMES = {0: "вода", 1: "дорога и земля", 2: "трава", 3: "листва и возвышенность", 4: "камни и горы"}


@functools.cache
def block_layers():
    """{ключ тайла: слой} для всех тайлов, лежащих внутри блоков образцов палитры (по позициям в образце)."""
    layers = {}
    for group in palette_groups():
        for block in palette_group_layers(group):
            layer = LAYER_BY_BLOCK_ROLE.get(block["role"])
            if layer is None:
                continue
            for key in block["cells"].values():
                layers.setdefault(key, layer)
    return layers


def layer_of(item):
    """Номер слоя элемента каталога или None для объектов и элементов без слоя."""
    if item.get("kind") != "ground":
        return None
    key = item.get("item_key")
    if key in block_layers():
        return block_layers()[key]
    return LAYER_BY_CATEGORY.get(item.get("category"))
