CREATE TABLE map_catalog (
    item_key TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('ground', 'object')),
    category TEXT NOT NULL,
    asset TEXT NOT NULL,
    footprint_w INTEGER NOT NULL CHECK (footprint_w >= 1),
    footprint_h INTEGER NOT NULL CHECK (footprint_h >= 1),
    blocks BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE map_cells (
    world_id INTEGER NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    layer TEXT NOT NULL CHECK (layer IN ('ground', 'object')),
    x INTEGER NOT NULL CHECK (x >= 0),
    y INTEGER NOT NULL CHECK (y >= 0),
    item_key TEXT NOT NULL REFERENCES map_catalog(item_key),
    PRIMARY KEY (world_id, layer, x, y)
);
