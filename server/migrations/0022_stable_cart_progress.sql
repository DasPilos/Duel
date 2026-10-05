CREATE TABLE stable_cart_progress (
    world_id INTEGER NOT NULL,
    faction TEXT NOT NULL,
    building TEXT NOT NULL DEFAULT 'stable' CHECK (building = 'stable'),
    grade INTEGER NOT NULL CHECK (grade IN (1, 2)),
    blueprint_owned BOOLEAN NOT NULL DEFAULT FALSE,
    body_owned BOOLEAN NOT NULL DEFAULT FALSE,
    wood_deposited INTEGER NOT NULL DEFAULT 0 CHECK (wood_deposited >= 0),
    silver_deposited INTEGER NOT NULL DEFAULT 0 CHECK (silver_deposited >= 0),
    upgrades_json JSONB NOT NULL DEFAULT '{"wheels":0,"sides":0,"axles":0}'::jsonb,
    PRIMARY KEY (world_id, faction, building, grade),
    FOREIGN KEY (world_id, faction, building)
        REFERENCES building_states(world_id, faction, building) ON DELETE CASCADE
);