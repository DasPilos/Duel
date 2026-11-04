import time
import uuid


MESSAGES = []


def add_message(sender, recipient_id, text, location):
    message = {
        "id": str(uuid.uuid4()),
        "sender": sender["name"],
        "sender_id": sender["character_id"],
        "recipient_id": recipient_id,
        "text": text,
        "location": location,
        "created_at": time.time(),
    }
    MESSAGES.append(message)
    del MESSAGES[:-100]
    return message


def messages_for(character_id, location):
    return [
        message for message in MESSAGES
        if message["location"] == location
        and (message["recipient_id"] is None or message["recipient_id"] == character_id)
    ][-50:]