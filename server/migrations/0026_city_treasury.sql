ALTER TABLE city_population_state
    ADD COLUMN IF NOT EXISTS treasury_copper BIGINT NOT NULL DEFAULT 0
    CHECK (treasury_copper >= 0);