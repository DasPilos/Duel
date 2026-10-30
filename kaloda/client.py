"""Клиент и сессия Колоды: расширяют общие классы вызовами карточной игры (/api/kaloda/...)."""

import uuid
from urllib.parse import quote, urlencode

from client.network import GameClient, ServerError
from client.session import OnlineSession

API_PREFIX = "/api/kaloda"


class KalodaClient(GameClient):
    def _kaloda(self, method, path, payload=None, **options):
        return self._request(method, f"{API_PREFIX}{path}", payload, authenticated=True, **options)

    # ------------------------------------------------------------ магазины и награды

    def get_game_info(self):
        """Визитка сервера мира: по ней лобби узнаёт, что этот мир играется по правилам Колоды."""
        return self._kaloda("GET", "/info")

    def get_supplies_shop_catalog(self):
        return self._kaloda("GET", "/supplies-shop")["items"]

    def buy_supplies_item(self, character_id, item_id):
        return self._kaloda("POST", "/supplies-shop/buy", {"character_id": character_id, "item_id": item_id})

    def get_card_shop_catalog(self):
        return self._kaloda("GET", "/card-shop")["cards"]

    def buy_card(self, character_id, card_key):
        return self._kaloda("POST", "/card-shop/buy", {"character_id": character_id, "card_key": card_key})

    def get_dungeon_card_shop_catalog(self):
        return self._kaloda("GET", "/dungeon/card-shop")["cards"]

    def buy_dungeon_card(self, character_id, card_key):
        return self._kaloda("POST", "/dungeon/card-shop/buy", {"character_id": character_id, "card_key": card_key})

    def claim_dungeon_treasure(self, character_id, request_id):
        return self._kaloda("POST", "/dungeon/treasure", {"character_id": character_id, "request_id": request_id})

    def claim_npc_kill_xp(self, character_id, encounter_id, defeated_types, request_id):
        return self._kaloda("POST", "/npc-kills", {
            "character_id": character_id,
            "encounter_id": encounter_id,
            "defeated_types": list(defeated_types),
            "request_id": request_id,
        })

    def claim_guild_quest_reward(self, character_id, quest_id, request_id):
        return self._kaloda("POST", "/guild/quest-reward", {
            "character_id": character_id,
            "quest_id": quest_id,
            "request_id": request_id,
        })

    def list_item_catalog(self):
        """Весь каталог предметов для справочника (в отличие от get_item_catalog по id)."""
        return self._kaloda("GET", "/items")["items"]

    def get_map_terrain(self):
        return self._kaloda("GET", "/map/terrain", timeout=max(self.timeout, 15))["terrain"]

    def list_drinks(self):
        """Напитки таверны: общая для миров логика, поэтому пути без префикса Колоды."""
        return self._request("GET", "/api/drinks", authenticated=True).get("drinks", [])

    def buy_drink(self, character_id, drink_id):
        return self._request(
            "POST", "/api/character/buy_drink",
            {"character_id": character_id, "drink_id": drink_id}, authenticated=True,
        )

    # ------------------------------------------------------------ персонаж, колоды, бой

    def choose_character_talent(self, character_id, level, choice_id):
        return self._kaloda("POST", "/talents/choose", {
            "character_id": character_id,
            "level": level,
            "choice_id": choice_id,
        })["character"]

    def get_card_collection(self, character_id):
        return self._kaloda("GET", f"/card-collection/{int(character_id)}")["collection"]

    def get_decks(self, character_id):
        return self._kaloda("GET", f"/decks/{int(character_id)}")["decks"]

    def create_deck(self, character_id, name, cards):
        return self._kaloda("POST", "/decks", {"character_id": character_id, "name": name, "cards": cards})["deck"]

    def delete_deck(self, character_id, deck_id):
        return self._kaloda("DELETE", f"/decks/{int(deck_id)}", {"character_id": character_id})

    def award_battle_card(self, character_id, card_keys):
        return self._kaloda("POST", "/battle/card-reward", {
            "character_id": character_id,
            "card_keys": list(card_keys),
        })["reward"]

    def report_battle_result(self, character_id, outcome, opponent_level, hp, mp,
                             opponent_id=None, opponent_hp=None, opponent_mp=None,
                             battle_record=None, battle_id=None):
        if battle_id is None:
            battle_id = ":".join(map(str, (character_id, outcome, opponent_level, hp, mp)))
        payload = {
            "character_id": character_id,
            "outcome": outcome,
            "opponent_level": opponent_level,
            "hp": hp,
            "mp": mp,
            "battle_id": str(battle_id),
        }
        if opponent_id is not None:
            payload.update({
                "opponent_id": int(opponent_id),
                "opponent_hp": int(opponent_hp),
                "opponent_mp": int(opponent_mp),
            })
        if battle_record is not None:
            payload["battle_record"] = battle_record
        return self._kaloda("POST", "/battle/result", payload)

    def list_opponents(self):
        return self._kaloda("GET", "/opponents")["opponents"]

    def save_opponent(self, opponent):
        return self._kaloda("PUT", f"/opponents/{opponent['id']}", opponent)["opponent"]

    # ------------------------------------------------------------ PvP: заявки и групповые бои

    def social_snapshot(self, location, character_id, position=None):
        """Присутствующие, сообщения и заявки на дуэли комнаты Колоды одним запросом."""
        query = {"location": location, "character_id": int(character_id)}
        if position:
            for key in ("position_x", "position_y", "position_direction"):
                if key in position:
                    query[key] = position[key]
        return self._kaloda("GET", f"/social/snapshot?{urlencode(query)}")

    def offer_duel(self, character_id, location, target_id):
        return self._kaloda("POST", "/social/duel-offers", {
            "character_id": character_id, "location": location, "target_id": target_id,
        })

    def create_duel_application(self, character_id, location, ttl=120):
        return self._kaloda("POST", "/social/duel-applications", {
            "character_id": character_id, "location": location, "ttl": ttl,
        })

    def cancel_duel_application(self, character_id, location):
        return self._kaloda("POST", "/social/duel-applications/cancel", {
            "character_id": character_id, "location": location,
        })

    def duel_board(self, location="backyard"):
        return self._kaloda("GET", f"/social/offers?location={quote(location)}")

    def list_duel_offers(self, location="backyard"):
        return self.duel_board(location)["offers"]

    def respond_duel_offer(self, character_id, offer_id, accepted):
        return self._kaloda("POST", "/social/duel-offers/respond", {
            "character_id": character_id, "offer_id": offer_id, "accepted": accepted,
        })

    def list_group_battles(self):
        return self._kaloda("GET", "/social/group-battles")["offers"]

    def create_group_battle(self, character_id, location="backyard", ttl=120, max_participants=10):
        return self._kaloda("POST", "/social/group-battles", {
            "character_id": character_id,
            "location": location,
            "ttl": ttl,
            "max_participants": max_participants,
        })

    def join_group_battle(self, offer_id, character_id, location="backyard"):
        return self._kaloda("POST", f"/social/group-battles/{offer_id}/join", {
            "character_id": character_id, "location": location,
        })

    def leave_group_battle(self, offer_id, character_id):
        return self._kaloda("POST", f"/social/group-battles/{offer_id}/leave", {"character_id": character_id})


class KalodaSession(OnlineSession):
    def __init__(self, username, password, character_name, server_url):
        super().__init__(username, password, character_name, server_url)
        self.client = KalodaClient(server_url)

    @classmethod
    def adopt(cls, session):
        """Сессия лобби становится сессией Колоды: тот же вход и персонаж, но клиент с вызовами игры."""
        adopted = cls.__new__(cls)
        adopted.__dict__.update(session.__dict__)
        client = KalodaClient(session.client.base_url, session.client.timeout)
        client.token = session.client.token
        adopted.client = client
        return adopted

    # ------------------------------------------------------------ колоды и коллекция

    def get_card_collection(self):
        if self.character is None:
            return []
        return self.client.get_card_collection(self.character["id"])

    def get_decks(self):
        if self.character is None:
            return []
        return self.client.get_decks(self.character["id"])

    def create_deck(self, name, cards):
        if self.character is None:
            return None
        return self.client.create_deck(self.character["id"], name, cards)

    def delete_deck(self, deck_id):
        if self.character is None:
            return None
        return self.client.delete_deck(self.character["id"], deck_id)

    def award_battle_card(self, card_keys):
        if self.character is None:
            return None
        return self.client.award_battle_card(self.character["id"], card_keys)

    # ------------------------------------------------------------ PvP

    def offer_duel(self, location, target_id):
        self.refresh_character()
        return self.client.offer_duel(self.character["id"], location, target_id)

    def create_duel_application(self, location, ttl=120):
        self.refresh_character()
        return self.client.create_duel_application(self.character["id"], location, ttl)

    def cancel_duel_application(self, location):
        return self.client.cancel_duel_application(self.character["id"], location)

    def duel_board(self, location="backyard"):
        return self.client.duel_board(location)

    def list_duel_offers(self, location="backyard"):
        return self.client.list_duel_offers(location)

    def respond_duel_offer(self, offer_id, accepted):
        if accepted:
            self.refresh_character()
        return self.client.respond_duel_offer(self.character["id"], offer_id, accepted)

    def list_group_battles(self):
        return self.client.list_group_battles()

    def create_group_battle(self, location="backyard", ttl=120, max_participants=10):
        self.refresh_character()
        return self.client.create_group_battle(self.character["id"], location, ttl, max_participants)

    def join_group_battle(self, offer_id, location="backyard"):
        self.refresh_character()
        return self.client.join_group_battle(offer_id, self.character["id"], location)

    def leave_group_battle(self, offer_id):
        return self.client.leave_group_battle(offer_id, self.character["id"])

    # ------------------------------------------------------------ бой и боец

    def list_opponents(self):
        return self.client.list_opponents()

    def save_opponent(self, opponent):
        return self.client.save_opponent(opponent)

    @staticmethod
    def _fighter_payload(fighter):
        return {
            "name": fighter.name,
            "level": fighter.level,
            "xp": fighter.xp,
            "hp": fighter.hp,
            "max_hp": fighter.max_hp,
            "mp": fighter.mp,
            "max_mp": fighter.max_mp,
            "stats": dict(fighter.stats),
            "stat_points": fighter.stat_points,
        }

    def save_fighter(self, fighter):
        if self.character is None:
            return None
        payload = {**self.character, **self._fighter_payload(fighter)}
        self.character = self.client.save_character(payload)
        return self.character

    def report_battle_result(self, fighter, outcome, opponent_level, opponent=None, battle_record=None):
        """Опыт и деньги за бой начисляет сервер; боец синхронизируется с его ответом."""
        opponent = opponent or {}
        opponent_id = opponent.get("character_id", opponent.get("id"))
        if opponent_id is not None and not str(opponent_id).lstrip("-").isdigit():
            opponent_id = None
        result = self.client.report_battle_result(
            self.character["id"], outcome, opponent_level, int(fighter.hp), int(fighter.mp),
            opponent_id=opponent_id,
            opponent_hp=opponent.get("hp"),
            opponent_mp=opponent.get("mp"),
            battle_record=battle_record,
            battle_id=uuid.uuid4().hex,
        )
        self.character = result["character"]
        for field in ("level", "xp", "stat_points", "hp", "mp"):
            setattr(fighter, field, self.character[field])
        fighter.stats = dict(self.character["stats"])
        fighter.recalculate_parameters()
        return result

    def disconnect(self, fighter=None, character=None):
        if self.client.token is None:
            return
        if fighter is not None:
            self.save_fighter(fighter)
        super().disconnect(character)

    def refresh_equipment_state(self):
        """Подтягивает экипировку и бонусы из серверного инвентаря."""
        if self.character is None:
            return None
        try:
            state = self.client.get_inventory(self.character["id"])
        except ServerError:
            return None
        self.character["equipment"] = dict(state.get("equipment", {}))
        self.character["equipment_bonuses"] = dict(state.get("bonuses", {}))
        return state
