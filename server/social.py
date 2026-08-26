"""Compatibility facade for the focused server social modules."""

from server import bot_chat, chat_cache, duel_offers, group_offers, presence


PRESENCE_TTL = presence.PRESENCE_TTL
PRESENCE = presence.PRESENCE
MESSAGES = chat_cache.MESSAGES
DUEL_OFFER_TTL = duel_offers.DUEL_OFFER_TTL
DUEL_OFFERS = duel_offers.DUEL_OFFERS
GROUP_BATTLE_OFFERS = group_offers.GROUP_BATTLE_OFFERS
BOT_TAVERN_REPLIES = bot_chat.BOT_TAVERN_REPLIES


def _cleanup():
    presence.cleanup()
    duel_offers.cleanup()
    group_offers.cleanup()


update_presence = presence.update_presence
occupants = presence.occupants

add_message = chat_cache.add_message
messages_for = chat_cache.messages_for

backyard_duel_error = duel_offers.backyard_duel_error
add_duel_offer = duel_offers.add_duel_offer
offers_for = duel_offers.offers_for
add_public_duel_offer = duel_offers.add_public_duel_offer
pending_public_offer = duel_offers.pending_public_offer
cancel_public_duel_offer = duel_offers.cancel_public_duel_offer
pending_bot_public_offers = duel_offers.pending_bot_public_offers
close_public_offer = duel_offers.close_public_offer
accept_public_offer = duel_offers.accept_public_offer
public_offers = duel_offers.public_offers
respond_duel_offer = duel_offers.respond_duel_offer

has_active_application = duel_offers.has_active_application
create_group_battle_offer = group_offers.create_group_battle_offer
join_group_battle_offer = group_offers.join_group_battle_offer
group_battle_offers = group_offers.group_battle_offers
group_battle_offer = group_offers.group_battle_offer
leave_group_battle_offer = group_offers.leave_group_battle_offer

record_bot_tavern_reply = bot_chat.record_bot_tavern_reply
