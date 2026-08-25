class ClientState:
    def __init__(self):
        self.user = None
        self.character = None
        self.connected = False


class ChatState:
    def __init__(self):
        self.channels = ["tavern", "backyard"]
        self.messages_by_channel = {channel: [] for channel in self.channels}
        self.unread_by_channel = {channel: 0 for channel in self.channels}
        self.connection_status = "disconnected"
        self.pending_message_ids = set()

    def replace_messages(self, channel, messages):
        merged = self.messages_by_channel.get(channel, [])[:]
        known = {message["id"] for message in merged}
        for message in messages:
            if message["id"] not in known:
                merged.append(message)
                known.add(message["id"])
        merged.sort(key=lambda message: (message["created_at"], message["id"]))
        self.messages_by_channel[channel] = merged[-100:]

    def add_message(self, channel, message):
        self.replace_messages(channel, [message])
        self.pending_message_ids.discard(message["id"])

    def set_connected(self, user):
        self.user = user
        self.connected = True

    def set_character(self, character):
        self.character = character

    def clear(self):
        self.user = None
        self.character = None
        self.connected = False
