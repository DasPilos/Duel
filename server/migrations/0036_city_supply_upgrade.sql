ALTER TABLE city_population_state
    ADD COLUMN city_upgrade_last_hour DOUBLE PRECISION NOT NULL DEFAULT -1,
    ADD COLUMN city_upgrade_cycle JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN city_upgrade_last_result JSONB NOT NULL DEFAULT '{}'::jsonb;