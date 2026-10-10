ALTER TABLE city_population_state
    ADD COLUMN population_capacity_bonus INTEGER NOT NULL DEFAULT 0
        CHECK (population_capacity_bonus >= 0);
