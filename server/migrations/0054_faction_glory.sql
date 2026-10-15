CREATE TABLE faction_glory (
    world_id INTEGER NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    faction TEXT NOT NULL,
    points BIGINT NOT NULL DEFAULT 0 CHECK (points >= 0),
    PRIMARY KEY (world_id, faction),
    FOREIGN KEY (world_id, faction)
        REFERENCES city_population_state(world_id, faction) ON DELETE CASCADE
);
