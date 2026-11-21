CREATE TABLE IF NOT EXISTS world_crystal_state (
    world_id INTEGER NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    tile_x INTEGER NOT NULL,
    tile_y INTEGER NOT NULL,
    published_at DOUBLE PRECISION NOT NULL,
    color TEXT NOT NULL,
    stage INTEGER NOT NULL,
    elapsed DOUBLE PRECISION NOT NULL DEFAULT 0,
    harvested BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (world_id, tile_x, tile_y)
);
