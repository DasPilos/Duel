"""Independent loot rolls for the skeleton king's treasure chest."""

import random


DUNGEON_TREASURE_ITEMS = (
    (901, "Карта скелета-стража", 70, 1),
    (902, "Статуя короля скелетов", 60, 1),
    (901, "Карта скелета-стража", 50, 2),
    (903, "Копьё скелета-стража", 25, 1),
    (904, "Карта короля скелетов", 10, 1),
    (905, "Корона короля скелетов", 5, 1),
    (906, "Наследие павшего короля", 1, 1),
)


def roll_dungeon_treasure(rng=None):
    """Roll every listed reward independently; the same chest can grant all rewards."""
    rng = random if rng is None else rng
    items = []
    for item_id, name, chance_percent, quantity in DUNGEON_TREASURE_ITEMS:
        if rng.random() * 100 < chance_percent:
            items.append({"item_id": item_id, "name": name, "quantity": quantity})
    return {"coins": 830, "items": items}
