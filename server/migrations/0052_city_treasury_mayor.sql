ALTER TABLE city_population_state
    ADD COLUMN IF NOT EXISTS mayor_character_id BIGINT REFERENCES characters(id) ON DELETE SET NULL;
