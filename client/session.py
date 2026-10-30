from client.network import GameClient, ServerError


class OnlineSession:
    def __init__(self, username, password, character_name, server_url):
        self.client = GameClient(server_url)
        self.username = username
        self.password = password
        self.character_name = character_name
        self.user = None
        self.character = None

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

    def create_character(self, name, profession_type="warrior", stats=None):
        self.character = self.client.create_character(name, profession_type=profession_type, stats=stats)
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

    def disconnect(self, character=None):
        if self.client.token is None:
            return
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
