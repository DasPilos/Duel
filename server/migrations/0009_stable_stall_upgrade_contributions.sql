CREATE TABLE stable_stall_upgrade_contributions (
    world_id INTEGER NOT NULL,
    faction TEXT NOT NULL,
    building TEXT NOT NULL DEFAULT 'stable' CHECK (building = 'stable'),
    upgrade_id TEXT NOT NULL CHECK (upgrade_id IN ('wooden_stalls', 'hayloft')),
    wood_deposited INTEGER NOT NULL DEFAULT 0 CHECK (wood_deposited >= 0),
    silver_deposited INTEGER NOT NULL DEFAULT 0 CHECK (silver_deposited >= 0),
    PRIMARY KEY (world_id, faction, building, upgrade_id),
    FOREIGN KEY (world_id, faction, building)
        REFERENCES building_states(world_id, faction, building) ON DELETE CASCADE
);