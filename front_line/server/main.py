"""Standalone HTTP server entrypoint for the automatic Front Line world."""

from server.main import run_mode_server
from front_line.server.api import FrontLineRequestHandler
from front_line.server.world import FrontLineWorldService


def run():
    run_mode_server(
        "front_line",
        FrontLineRequestHandler,
        world_factory=lambda database, items: FrontLineWorldService(database, items),
    )


if __name__ == "__main__":
    run()
