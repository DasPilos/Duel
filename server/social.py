"""Compatibility facade for the focused server social modules."""

from server import bot_chat, chat_cache, presence


PRESENCE_TTL = presence.PRESENCE_TTL
PRESENCE = presence.PRESENCE
MESSAGES = chat_cache.MESSAGES
BOT_TAVERN_REPLIES = bot_chat.BOT_TAVERN_REPLIES


update_presence = presence.update_presence
mark_afk = presence.mark_afk
get_character_presence = presence.get_character_presence
remove_character_presence = presence.remove_character_presence
update_afk_character = presence.update_afk_character
occupants = presence.occupants

add_message = chat_cache.add_message
messages_for = chat_cache.messages_for

record_bot_tavern_reply = bot_chat.record_bot_tavern_reply
