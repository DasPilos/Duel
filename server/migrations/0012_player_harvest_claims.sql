CREATE TABLE building_player_resources (
    world_id INTEGER NOT NULL,
    faction TEXT NOT NULL,
    building TEXT NOT NULL,
    character_id BIGINT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    resource TEXT NOT NULL,
    buffered INTEGER NOT NULL DEFAULT 0 CHECK (buffered >= 0),
    claimable INTEGER NOT NULL DEFAULT 0 CHECK (claimable >= 0),
    PRIMARY KEY (world_id, faction, building, character_id, resource),
    FOREIGN KEY (world_id, faction, building)
        REFERENCES building_states(world_id, faction, building) ON DELETE CASCADE,
    FOREIGN KEY (world_id, faction, building, resource)
        REFERENCES building_resources(world_id, faction, building, resource) ON DELETE CASCADE
);