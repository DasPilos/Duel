"""Standalone HTTP server entrypoint for one Tower world."""

from server.main import run_mode_server
from tower.server.api import TowerRequestHandler
from tower.server.world_mobs import WorldService


def run():
    run_mode_server(
        "tower",
        TowerRequestHandler,
        world_factory=lambda database, items: WorldService(database, items),
    )


if __name__ == "__main__":
    run()
