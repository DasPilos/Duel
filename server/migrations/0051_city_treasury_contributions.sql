CREATE TABLE city_treasury_contributions (
    world_id INTEGER NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    faction TEXT NOT NULL,
    character_id BIGINT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    contributed_copper BIGINT NOT NULL DEFAULT 0 CHECK (contributed_copper >= 0),
    PRIMARY KEY (world_id, faction, character_id),
    FOREIGN KEY (world_id, faction)
        REFERENCES city_population_state(world_id, faction) ON DELETE CASCADE
);
