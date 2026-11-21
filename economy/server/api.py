"""HTTP surface and request implementations owned by Economy worlds."""

import time

from core.production_buildings import BUILDINGS
from economy.server.city_population import CityPopulation, DEFAULT_FACTION
from economy.server.city_upgrade import city_upgrade_payload
from economy.server.forge import Forge
from economy.server.production_buildings import ProductionBuildings
from economy.server.transport import TransportService
from server.mode_api import COMMON_API_ROUTES, ModeRequestHandler
from server.structures import city_structures
from server.world_map import terrain_payload


class EconomyRequestHandler(ModeRequestHandler):
    API_ROUTES = {
        **COMMON_API_ROUTES,
        "GET": COMMON_API_ROUTES["GET"] + (
            "/api/map/terrain",
            "/api/city/structures",
            "/api/buildings/*",
            "/api/forge/*",
            "/api/castle/*",
            "/api/world/traveling-citizens",
            "/api/world/traveling-convoys",
            "/api/drinks",
        ),
        "POST": COMMON_API_ROUTES["POST"] + (
            "/api/buildings/*",
            "/api/forge/*",
            "/api/castle/*",
            "/api/character/buy_drink",
            "/api/character/use_drink",
            "/api/server/restart-notice",
            "/api/server/client-reload",
        ),
        "PUT": COMMON_API_ROUTES["PUT"],
    }

    def _dispatch_mode_api(self, method, path, body=None):
        if method == "GET":
            return self._dispatch_economy_get(path)
        if method == "POST":
            return self._dispatch_economy_post(path, body or {})
        return False

    def _dispatch_economy_get(self, path):
        if path == "/api/map/terrain":
            self.database.user_id_by_token(self._token())
            with self.database.connection() as connection:
                row = connection.execute(
                    "SELECT city_level FROM city_population_state WHERE world_id=%s AND faction=%s",
                    (self.database.world_id, DEFAULT_FACTION),
                ).fetchone()
                city_level = 1 if row is None else int(row["city_level"])
                visual_state = city_upgrade_payload(
                    connection, (self.database.world_id, DEFAULT_FACTION), time.time()
                )
            result = terrain_payload(city_level)
            result["city_visual_state"] = visual_state
            self._send(200, {"terrain": result})
            return True
        if path == "/api/city/structures":
            self.database.user_id_by_token(self._token())
            self._send(200, {"city": city_structures()})
            return True
        if path.startswith("/api/buildings/player-work/"):
            parts = path.split("/")
            if len(parts) != 5:
                raise ValueError("Некорректный путь производственной работы")
            user_id = self.database.user_id_by_token(self._token())
            character_id = int(parts[4])
            if not self.database.character_belongs_to_user(user_id, character_id):
                raise ValueError("Персонаж не найден")
            work = ProductionBuildings(self.database).active_player_work(character_id)
            self._send(200, {"work": work})
            return True
        if path.startswith("/api/forge/"):
            parts = path.split("/")
            if len(parts) != 4 or parts[3] == "orders":
                raise ValueError("Некорректный путь кузницы")
            user_id = self.database.user_id_by_token(self._token())
            character_id = int(parts[3])
            if not self.database.character_belongs_to_user(user_id, character_id):
                raise ValueError("Персонаж не найден")
            self._send(200, Forge(self.database, self.items_database).get_state(character_id))
            return True
        if path.startswith("/api/buildings/"):
            parts = path.split("/")
            if len(parts) != 5 or parts[3] not in BUILDINGS:
                self._send(404, {"error": "Здание не найдено"})
                return True
            building, character_id = parts[3], int(parts[4])
            user_id = self.database.user_id_by_token(self._token())
            if not self.database.character_belongs_to_user(user_id, character_id):
                self._send(404, {"error": "Персонаж не найден"})
            else:
                state = ProductionBuildings(self.database).get_state(character_id, building)
                self._send(200, {"building": state})
            return True
        if path.startswith("/api/castle/"):
            parts = path.split("/")
            if len(parts) != 5 or parts[4] != "population":
                self._send(404, {"error": "Путь замка не найден"})
                return True
            user_id = self.database.user_id_by_token(self._token())
            character_id = int(parts[3])
            if not self.database.character_belongs_to_user(user_id, character_id):
                raise ValueError("Персонаж не найден")
            self._send(200, {"population": CityPopulation(self.database).get_state(character_id)})
            return True
        if path == "/api/world/traveling-citizens":
            user_id = self.database.user_id_by_token(self._token())
            character_id = int(self._query().get("character_id", [0])[0])
            if not self.database.character_belongs_to_user(user_id, character_id):
                raise ValueError("Персонаж не найден")
            travelers = CityPopulation(self.database).get_traveling_citizens(character_id)
            self._send(200, {"citizens": travelers})
            return True
        if path == "/api/world/traveling-convoys":
            user_id = self.database.user_id_by_token(self._token())
            character_id = int(self._query().get("character_id", [0])[0])
            if not self.database.character_belongs_to_user(user_id, character_id):
                raise ValueError("Персонаж не найден")
            convoys = TransportService(self.database).get_world_convoys(character_id)
            self._send(200, {"convoys": convoys})
            return True
        if path == "/api/drinks":
            self.database.user_id_by_token(self._token())
            self._send(200, {"drinks": self.database.get_drinks_list()})
            return True
        return False

    def _dispatch_economy_post(self, path, body):
        if path.startswith("/api/castle/"):
            parts = path.split("/")
            if len(parts) == 5 and parts[4] in ("treasury", "treasury-edict"):
                user_id = self.database.user_id_by_token(self._token())
                character_id = int(parts[3])
                if not self.database.character_belongs_to_user(user_id, character_id):
                    raise ValueError("Персонаж не найден")
                population = CityPopulation(self.database)
                if parts[4] == "treasury":
                    state = population.transfer_treasury(
                        character_id, body.get("direction"), body.get("amount_copper")
                    )
                else:
                    state = population.start_treasury_edict(character_id)
                self._send(200, {"population": state})
                return True
            if len(parts) == 6 and parts[4] == "upgrades":
                user_id = self.database.user_id_by_token(self._token())
                character_id = int(parts[3])
                if not self.database.character_belongs_to_user(user_id, character_id):
                    raise ValueError("Персонаж не найден")
                state = CityPopulation(self.database).start_castle_upgrade(character_id, parts[5])
                self._send(200, {"population": state})
                return True
            if len(parts) == 7 and parts[4] == "citizens":
                user_id = self.database.user_id_by_token(self._token())
                character_id, citizen_id = int(parts[3]), int(parts[5])
                if not self.database.character_belongs_to_user(user_id, character_id):
                    raise ValueError("Персонаж не найден")
                population = CityPopulation(self.database)
                if parts[6] == "assign":
                    state = population.assign_citizen(
                        character_id, citizen_id, body.get("building"), body.get("slot_index")
                    )
                elif parts[6] == "recall":
                    state = population.recall_citizen(character_id, citizen_id)
                else:
                    return False
                self._send(200, {"population": state})
                return True
        if path.startswith("/api/forge/"):
            parts = path.split("/")
            if not (
                (len(parts) == 5 and parts[4] == "orders")
                or (len(parts) == 7 and parts[4] == "orders" and parts[6] == "collect")
            ):
                raise ValueError("Некорректный путь кузницы")
            user_id = self.database.user_id_by_token(self._token())
            character_id = int(parts[3])
            if not self.database.character_belongs_to_user(user_id, character_id):
                raise ValueError("Персонаж не найден")
            forge = Forge(self.database, self.items_database)
            if len(parts) == 5:
                order_id = forge.create_order(character_id, body.get("item_id"))
                self._send(201, {"order_id": order_id, **forge.get_state(character_id)})
            else:
                forge.collect_order(character_id, int(parts[5]))
                self._send(200, forge.get_state(character_id))
            return True
        if path.startswith("/api/buildings/"):
            parts = path.split("/")
            if len(parts) < 6 or parts[3] not in BUILDINGS:
                raise ValueError("Некорректный путь здания")
            building, character_id = parts[3], int(parts[4])
            user_id = self.database.user_id_by_token(self._token())
            if not self.database.character_belongs_to_user(user_id, character_id):
                raise ValueError("Персонаж не найден")
            buildings = ProductionBuildings(self.database)
            action = "/".join(parts[5:])
            if action == "workers/hire":
                state = buildings.hire_worker(character_id, building, body.get("slot_index"), body.get("worker_id"))
            elif action == "workers/fire":
                state = buildings.fire_worker(character_id, building, body.get("slot_index"))
            elif action == "workers/player/toggle":
                state = buildings.toggle_player_worker(character_id, building, body.get("slot_index"))
            elif action == "storage/deposit":
                state = buildings.deposit_to_storage(character_id, building, body.get("resource"), body.get("quantity", 0))
            elif action == "storage/withdraw":
                state = buildings.withdraw_from_storage(character_id, building, body.get("resource"), body.get("quantity", 0))
            elif action == "upgrade/deposit":
                state = buildings.deposit_material(character_id, building, body.get("item_id", 0), body.get("quantity", 0), source=body.get("source", "warehouse"))
            elif action == "upgrade/start":
                state = buildings.start_upgrade(character_id, building)
            elif action == "farm/upgrade" and building == "farm":
                state = buildings.purchase_farm_upgrade(character_id, body.get("upgrade_id"))
            elif action == "lumber-camp/upgrade" and building == "lumber_camp":
                state = buildings.purchase_lumber_camp_upgrade(character_id, body.get("upgrade_id"))
            elif action == "stall-upgrade/contribute" and building == "stable":
                state = buildings.contribute_stall_upgrade(character_id, body.get("upgrade_id"), body.get("resource"), body.get("quantity", 0), source=body.get("source"))
            elif action == "stall-upgrade/purchase" and building == "stable":
                state = buildings.purchase_stall_upgrade(character_id, body.get("upgrade_id"))
            elif action == "cart/contribute" and building == "stable":
                state = buildings.contribute_cart(character_id, body.get("resource"), body.get("quantity", 0), source=body.get("source"))
            elif action == "cart/purchase" and building == "stable":
                state = buildings.purchase_cart(character_id, body.get("grade", 1))
            elif action == "cart/repair" and building == "stable":
                state = buildings.repair_cart(character_id, body.get("cart_id", ""))
            elif action == "cart/rename" and building == "stable":
                state = buildings.rename_cart(character_id, body.get("cart_id", ""), body.get("name", ""))
            elif action == "cart/auto_repair" and building == "stable":
                state = buildings.set_cart_auto_repair(character_id, body.get("cart_id", ""), body.get("mode"))
            elif action == "transport/dispatch" and building == "stable":
                convoy = TransportService(self.database).dispatch(character_id, body)
                state = buildings.get_state(character_id, "stable")
                self._send(201, {"building": state, "convoy": convoy})
                return True
            elif action == "transport/pin" and building == "stable":
                TransportService(self.database).set_pinned(character_id, body.get("convoy_id"), body.get("pinned", False))
                state = buildings.get_state(character_id, "stable")
            elif action == "horse/purchase" and building == "stable":
                state = buildings.purchase_horse(character_id, body.get("slot_index"))
            else:
                raise ValueError("Неизвестное действие здания")
            self._send(200, {"building": state})
            return True
        return False
