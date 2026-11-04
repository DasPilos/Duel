ALTER TABLE character_card_grants
    ADD COLUMN IF NOT EXISTS starter_cards_version INTEGER NOT NULL DEFAULT 1;
