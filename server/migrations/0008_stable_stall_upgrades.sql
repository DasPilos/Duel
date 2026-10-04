CREATE TABLE stable_stall_upgrades (
    world_id INTEGER NOT NULL,
    faction TEXT NOT NULL,
    building TEXT NOT NULL DEFAULT 'stable' CHECK (building = 'stable'),
    upgrade_id TEXT NOT NULL CHECK (upgrade_id IN ('wooden_stalls', 'hayloft')),
    purchased_by BIGINT REFERENCES characters(id) ON DELETE SET NULL,
    purchased_at DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (world_id, faction, building, upgrade_id),
    FOREIGN KEY (world_id, faction, building)
        REFERENCES building_states(world_id, faction, building) ON DELETE CASCADE
);