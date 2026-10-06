from client.network import GameClient, ServerError
from core import settings


class OnlineSession:
    def __init__(self, username, password, character_name, server_url):
        self.client = GameClient(server_url)
        self.username = username
        self.password = password
        self.character_name = character_name
        self.user = None
        self.character = None
        self.selected_deck = None
        self.regen_accumulator = 0.0
        self.regen_mp_accumulator = 0.0

    def connect(self):
        try:
            self.client.register(self.username, self.password)
        except ServerError as error:
            if "уже существует" not in str(error):
                raise

        self.user = self.client.login(self.username, self.password)
        return self.user

    def register_account(self):
        self.client.register(self.username, self.password)
        self.user = self.client.login(self.username, self.password)
        return self.user

    def list_characters(self):
        return self.client.list_characters()

    def select_character(self, character):
        self.character = character
        return self.character
    
    def refresh_character(self):
        """Перезагружает персонажа с сервера"""
        if self.character is None:
            return None
        self.character = self.client.load_character(self.character["id"])
        return self.character

    def create_character(self, name, profession_type="warrior"):
        self.character = self.client.create_character(name, profession_type=profession_type)
        return self.character
    
    def delete_character(self, character_id):
        """Delete a character"""
        return self.client.delete_character(character_id)
    
    def delete_character_with_password(self, character_id, password):
        """Delete a character with password confirmation"""
        return self.client.delete_character_with_password(character_id, password)
    
    def update_character_profession(self, character_id, profession_type):
        """Update character profession"""
        self.character = self.client.update_character_profession(character_id, profession_type)
        return self.character

    def list_opponents(self):
        return self.client.list_opponents()

    def save_opponent(self, opponent):
        return self.client.save_opponent(opponent)

    def regenerate_character(self, amount):
        if self.character is None or self.character["hp"] >= self.character["max_hp"]:
            return self.character
        self.character["hp"] = min(
            self.character["max_hp"],
            self.character["hp"] + max(0, int(amount)),
        )
        return self.client.save_character(self.character)

    def passive_regenerate(self, dt, in_tavern=False, full_regen_seconds=None):
        self.last_regen_amount = 0
        self.last_mp_regen_amount = 0
        character = self.character
        if character is None or (
            character["hp"] >= character["max_hp"]
            and character.get("mp", character.get("max_mp", 0)) >= character.get("max_mp", 0)
        ):
            self.regen_accumulator = 0.0
            self.regen_mp_accumulator = 0.0
            return character
        full_regen_seconds = full_regen_seconds or (settings.TAVERN_FULL_REGEN_SECONDS if in_tavern else settings.FULL_REGEN_SECONDS)
        dt = max(0.0, float(dt))
        self.regen_accumulator += character["max_hp"] / full_regen_seconds * dt
        self.regen_mp_accumulator += character.get("max_mp", 0) / full_regen_seconds * dt
        hp_amount = int(self.regen_accumulator)
        mp_amount = int(self.regen_mp_accumulator)
        if hp_amount <= 0 and mp_amount <= 0:
            return character
        self.regen_accumulator -= hp_amount
        self.regen_mp_accumulator -= mp_amount
        previous_hp = character["hp"]
        previous_mp = character.get("mp", 0)
        character["hp"] = min(character["max_hp"], character["hp"] + hp_amount)
        character["mp"] = min(character.get("max_mp", 0), character.get("mp", 0) + mp_amount)
        result = self.client.save_character(character)
        self.character = result
        self.last_regen_amount = max(0, result["hp"] - previous_hp)
        self.last_mp_regen_amount = max(0, result.get("mp", 0) - previous_mp)
        return result

    def update_presence(self, location):
        return self.client.update_presence(self.character["id"], location)

    def list_occupants(self, location):
        return self.client.list_occupants(location)

    def list_messages(self, location, before_id=None, limit=50):
        return self.client.list_messages(location, self.character["id"], before_id, limit)

    def social_snapshot(self, location, position=None):
        return self.client.social_snapshot(location, self.character["id"], position=position)

    def mark_chat_read(self, location, message_id):
        return self.client.mark_chat_read(self.character["id"], location, message_id)

    def unread_count(self, location):
        return self.client.unread_count(self.character["id"], location)

    def report_message(self, message_id, reason):
        return self.client.report_message(self.character["id"], message_id, reason)

    def delete_message(self, message_id):
        return self.client.delete_message(message_id)

    def mute_character(self, muted_character_id, seconds=600):
        return self.client.mute_character(self.character["id"], muted_character_id, seconds)

    def send_message(self, location, text, recipient_id=None):
        return self.client.send_message(self.character["id"], location, text, recipient_id)

    def offer_duel(self, location, target_id):
        return self.client.offer_duel(self.character["id"], location, target_id)

    def create_duel_application(self, location, ttl=120):
        return self.client.create_duel_application(self.character["id"], location, ttl)

    def cancel_duel_application(self, location):
        return self.client.cancel_duel_application(self.character["id"], location)

    def duel_board(self, location="tavern"):
        return self.client.duel_board(location)

    def list_duel_offers(self, location="tavern"):
        return self.client.list_duel_offers(location)

    def respond_duel_offer(self, offer_id, accepted):
        return self.client.respond_duel_offer(self.character["id"], offer_id, accepted)

    def list_group_battles(self):
        return self.client.list_group_battles()

    def create_group_battle(self, location="backyard", ttl=120, max_participants=10):
        return self.client.create_group_battle(self.character["id"], location, ttl, max_participants)

    def join_group_battle(self, offer_id, location="backyard"):
        return self.client.join_group_battle(offer_id, self.character["id"], location)

    def leave_group_battle(self, offer_id):
        return self.client.leave_group_battle(offer_id, self.character["id"])

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

    def report_battle_result(self, fighter, outcome, opponent_level, opponent=None):
        """Опыт и деньги за бой начисляет сервер; боец синхронизируется с его ответом."""
        opponent_id = (opponent or {}).get("character_id", (opponent or {}).get("id"))
        if opponent_id is not None and not str(opponent_id).lstrip("-").isdigit():
            opponent_id = None
        result = self.client.report_battle_result(
            self.character["id"], outcome, opponent_level, int(fighter.hp), int(fighter.mp),
            opponent_id=opponent_id,
            opponent_hp=(opponent or {}).get("hp"),
            opponent_mp=(opponent or {}).get("mp"),
        )
        self.character = result["character"]
        for field in ("level", "xp", "stat_points", "hp", "mp"):
            setattr(fighter, field, self.character[field])
        fighter.stats = dict(self.character["stats"])
        fighter.recalculate_parameters()
        return result

    def save_fighter(self, fighter):
        if self.character is None:
            return None
        payload = {
            **self.character,
            **self._fighter_payload(fighter),
        }
        self.character = self.client.save_character(payload)
        return self.character

    def save_character_profile(self, profile):
        if self.character is None:
            return None
        payload = {
            **self.character,
            **profile,
            "stats": dict(profile["stats"]),
        }
        self.character = self.client.save_character(payload)
        return self.character

    def disconnect(self, fighter=None, character=None):
        if self.client.token is None:
            return
        if fighter is not None:
            self.save_fighter(fighter)
        if character is not None and self.character is not None:
            self.character.update(character)
        self.client.disconnect(self.character)
        self.character = None
        self.user = None
    
    def add_currency(self, copper=0, silver=0, gold=0):
        """Add currency to character and save"""
        from core.currency import Currency
        
        if self.character is None:
            return None
        
        current = Currency.from_dict(self.character)
        current.add(copper, silver, gold)
        self.character.update(current.to_dict())
        
        return self.client.save_character(self.character)
    
    def subtract_currency(self, copper=0, silver=0, gold=0):
        """Subtract currency from character, returns True if successful"""
        from core.currency import Currency
        
        if self.character is None:
            return False
        
        current = Currency.from_dict(self.character)
        if not current.has_enough(copper, silver, gold):
            return False
        
        current.subtract(copper, silver, gold)
        self.character.update(current.to_dict())
        self.client.save_character(self.character)
        return True
    
    def get_currency(self):
        """Get current character currency"""
        if self.character is None:
            return None
        
        from core.currency import Currency
        return Currency.from_dict(self.character)
    
    def get_drinks_list(self):
        """Get available drinks"""
        return self.client.get("drinks")
    
    def buy_drink(self, drink_id):
        """Buy a drink"""
        if self.character is None:
            return None
        
        result = self.client.post("character/buy_drink", {
            "character_id": self.character["id"],
            "drink_id": drink_id
        })
        if result:
            self.character = result
        return result
    
    def get_inventory(self):
        """Get character inventory"""
        if self.character is None:
            return None
        
        return self.client.get(f"character/{self.character['id']}/inventory")

    def refresh_carrying_state(self):
        """Refresh carried weight and equipment from the authoritative inventory API."""
        if self.character is None:
            return None
        try:
            state = self.client.get_inventory(self.character["id"])
        except ServerError:
            return None
        self.character["carried_weight_kg"] = float(state.get("carried_weight_kg", 0))
        self.character["equipment"] = dict(state.get("equipment", {}))
        self.character["equipment_bonuses"] = dict(state.get("bonuses", {}))
        return self.character["carried_weight_kg"]

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
    
    def use_drink(self, inventory_item_id):
        """Use a drink from inventory"""
        if self.character is None:
            return None
        
        result = self.client.post("character/use_drink", {
            "character_id": self.character["id"],
            "inventory_item_id": inventory_item_id
        })
        if result:
            self.character = result
        return result

    def get_forge_state(self):
        if self.character is None:
            return {"queue": [], "queue_count": 0, "queue_limit": 5, "queue_total_seconds": 0, "warehouse": []}
        return self.client.get_forge_state(self.character["id"])

    def order_forge_item(self, item_id):
        if self.character is None:
            return None
        return self.client.order_forge_item(self.character["id"], item_id)

    def collect_forge_order(self, order_id):
        if self.character is None:
            return None
        return self.client.collect_forge_order(self.character["id"], order_id)
