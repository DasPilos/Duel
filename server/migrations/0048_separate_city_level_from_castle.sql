ALTER TABLE city_population_state
    ADD COLUMN city_level INTEGER NOT NULL DEFAULT 1 CHECK (city_level >= 1);

UPDATE city_population_state SET city_level = castle_level;

UPDATE city_population_state SET castle_level = 1;
