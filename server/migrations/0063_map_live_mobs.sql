CREATE TABLE map_live_mobs (
    world_id INTEGER NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    x INTEGER NOT NULL CHECK (x >= 0),
    y INTEGER NOT NULL CHECK (y >= 0),
    PRIMARY KEY (world_id, x, y)
);

ALTER TABLE map_world_publish ADD COLUMN mode TEXT NOT NULL DEFAULT 'tower';
