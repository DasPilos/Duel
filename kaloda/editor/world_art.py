"""Размеры листов деревьев и пней для редактора карт: как в мире Оператора 1 и в палитре, без импорта оттуда.

Листы лежат в общей папке assets/map (та же, что у Колоды).
"""

# Листы деревьев художника: кадры по 6 в ряд, всего 10 кадров (анимация покачивания)
MAP_TREE_SHEETS = {"tree1": (160, 256), "tree2": (160, 288), "tree3": (160, 224), "old_tree1": (160, 256), "old_tree2": (160, 288), "old_tree3": (160, 224), "big_tree": (352, 416)}
MAP_TREE_FRAMES = 10
MAP_TREE_FRAMES_PER_ROW = 6
MAP_TREE_COLUMNS = {"big_tree": 5}
MAP_TREE_FRAME_MS = 140
MAP_TREE_SCALE = 0.5
MAP_PROP_SCALE = 0.5
