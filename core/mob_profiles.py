"""Профили бесов карты: название и подписи в логе боя. Общие для сервера и клиента.

Характеристики и экипировку задаёт карточка моба в редакторе карт (core/mob_modes.py).
"""
from core.npc_catalog import NPC_CATALOG
from core.mob_catalog import PALETTE_MOB_CATALOG

NPC_KEYS = frozenset(npc["key"] for npc in NPC_CATALOG)


def npc_profiles():
    """Профили бесов для MOB_PROFILES: название, описание и подписи в логе боя."""
    return {
        npc["key"]: {
            "name": npc["name"],
            "desc": "Крылатый бес из адских земель.",
            "stats": {},  # заполняется из файла режима
            "log_names": {"nom": "Бес", "dat": "бесу", "gen": "беса"},
        }
        for npc in NPC_CATALOG
    }


def mob_profiles():
    """Profiles for all editor palette mobs, including their source-pack variants."""
    profiles = npc_profiles()
    for mob in PALETTE_MOB_CATALOG:
        name = mob["name"]
        profiles[mob["key"]] = {
            "name": name,
            "desc": "Моб из палитры Front Line.",
            "stats": {},
            "log_names": {"nom": name, "dat": name, "gen": name},
        }
    return profiles
