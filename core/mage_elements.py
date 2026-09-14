"""Elemental rules shared by the mage card battle."""

ELEMENTS = ("Огонь", "Вода", "Земля", "Электричество", "Воздух", "Холод")
STATUS_DURATION_LOSS_PER_TURN = 1
FIRE_DAMAGE_PER_STACK = 2
WATER_DODGE_PENALTY = 15
ELECTRIC_STUN_AFTER_TURNS = 3

REACTIONS = {
    frozenset(("Огонь", "Вода")): {
        "damage_multiplier": 0.5,
        "duration_loss": 1,
    },
    frozenset(("Огонь", "Электричество")): {
        "damage_multiplier": 1.3,
        "harmony_damage_percent": 1,
        "blind_percent": 20,
        "consume": True,
    },
    frozenset(("Огонь", "Холод")): {"damage_multiplier": 0.2, "consume": True},
    frozenset(("Вода", "Электричество")): {
        "damage_multiplier": 1.1,
        "harmony_damage_percent": 1,
        "spread_percent": 40,
        "water_remains": True,
    },
    frozenset(("Вода", "Холод")): {"freeze": True, "consume": False},
    frozenset(("Электричество", "Холод")): {"damage_multiplier": 0.3, "consume": True},
    frozenset(("Воздух", "Огонь")): {"duration_loss": 1},
    frozenset(("Воздух", "Вода")): {"duration_loss": 1},
    frozenset(("Воздух", "Электричество")): {"duration_loss": 1},
}


def reaction_for(first_element, second_element):
    return REACTIONS.get(frozenset((first_element, second_element)))


def fire_damage(stack_count):
    return max(0, int(stack_count)) * FIRE_DAMAGE_PER_STACK
