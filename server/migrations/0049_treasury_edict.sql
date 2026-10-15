ALTER TABLE city_population_state
    ADD COLUMN treasury_edict_finish_at DOUBLE PRECISION,
    ADD COLUMN treasury_edict_done BOOLEAN NOT NULL DEFAULT FALSE;
