-- Стартовый набор карт класса выдаётся персонажу один раз.
CREATE TABLE character_card_grants (
    character_id BIGINT PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
    starter_cards_at DOUBLE PRECISION NOT NULL
);
