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
        self.regen_accumulator = 0.0

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

    def create_character(self, name):
        self.character = self.client.create_character(name)
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

    def passive_regenerate(self, dt, in_tavern=False):
        self.last_regen_amount = 0
        character = self.character
        if character is None or character["hp"] >= character["max_hp"]:
            self.regen_accumulator = 0.0
            return character
        full_regen_seconds = settings.TAVERN_FULL_REGEN_SECONDS if in_tavern else settings.FULL_REGEN_SECONDS
        self.regen_accumulator += character["max_hp"] / full_regen_seconds * max(0.0, float(dt))
        amount = int(self.regen_accumulator)
        if amount <= 0:
            return character
        self.regen_accumulator -= amount
        previous_hp = character["hp"]
        result = self.regenerate_character(amount)
        self.last_regen_amount = max(0, result["hp"] - previous_hp)
        return result

    def update_presence(self, location):
        return self.client.update_presence(self.character["id"], location)

    def list_occupants(self, location):
        return self.client.list_occupants(location)

    def list_messages(self, location, before_id=None, limit=50):
        return self.client.list_messages(location, self.character["id"], before_id, limit)

    def social_snapshot(self, location):
        return self.client.social_snapshot(location, self.character["id"])

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

    def disconnect(self, fighter=None):
        if self.client.token is None:
            return
        if fighter is not None:
            self.save_fighter(fighter)
        self.client.disconnect()
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
