CREATE TABLE IF NOT EXISTS map_custom_tile_groups (
    group_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('grass', 'mountain', 'water', 'road', 'forest')),
    tile_rows INTEGER NOT NULL CHECK (tile_rows IN (3, 4, 5)),
    created_by BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS map_custom_tile_assets (
    item_key TEXT PRIMARY KEY,
    group_id TEXT NOT NULL REFERENCES map_custom_tile_groups(group_id) ON DELETE CASCADE,
    tile_x INTEGER NOT NULL CHECK (tile_x BETWEEN 0 AND 2),
    tile_y INTEGER NOT NULL CHECK (tile_y BETWEEN 0 AND 4),
    png_bytes BYTEA NOT NULL,
    UNIQUE (group_id, tile_x, tile_y)
);
