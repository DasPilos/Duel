CREATE TABLE map_meta (
    world_id INTEGER PRIMARY KEY REFERENCES worlds(id) ON DELETE CASCADE,
    name TEXT NOT NULL DEFAULT '',
    published_name TEXT NOT NULL DEFAULT '',
    published_at DOUBLE PRECISION
);

CREATE TABLE map_live_cells (
    world_id INTEGER NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    layer TEXT NOT NULL CHECK (layer IN ('ground', 'object')),
    x INTEGER NOT NULL CHECK (x >= 0),
    y INTEGER NOT NULL CHECK (y >= 0),
    item_key TEXT NOT NULL REFERENCES map_catalog(item_key),
    PRIMARY KEY (world_id, layer, x, y)
);
