"""Standalone HTTP server entrypoint for one Economy world."""

import traceback

from economy.server.city_population import CityPopulation
from server.main import run_mode_server
from economy.server.api import EconomyRequestHandler
from economy.server.world_events import run_world_event_watcher
from economy.server.world_roads import roads_payload
from server import config


def _prepare_economy(database):
    print("Подготавливаю дороги к загородным постройкам...")
    roads_payload()


def _run_city_population(database, stop_event):
    population = CityPopulation(database)
    while not stop_event.is_set():
        try:
            population.tick_all()
        except Exception:
            traceback.print_exc()
        if stop_event.wait(config.CITY_TICK_INTERVAL_SECONDS):
            break


def run():
    run_mode_server(
        "economy",
        EconomyRequestHandler,
        startup=_prepare_economy,
        background_workers=(
            ("city-population-ticks", _run_city_population),
            ("world-event-watcher", run_world_event_watcher),
        ),
    )


if __name__ == "__main__":
    run()
