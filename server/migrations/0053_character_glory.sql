CREATE TABLE character_glory (
    world_id INTEGER NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    character_id BIGINT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    points BIGINT NOT NULL DEFAULT 0 CHECK (points >= 0),
    PRIMARY KEY (world_id, character_id)
);
