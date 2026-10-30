CREATE TABLE map_live_spawns (
    world_id INTEGER NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    x INTEGER NOT NULL CHECK (x >= 0),
    y INTEGER NOT NULL CHECK (y >= 0),
    PRIMARY KEY (world_id, x, y)
);

ALTER TABLE map_saved ADD COLUMN spawns_json TEXT NOT NULL DEFAULT '[]';
