-- Здания общие для всех игроков фракции в мире (а не у каждого персонажа свои).
-- Из прежних личных состояний переносится самое развитое для каждого здания.
ALTER TABLE building_upgrade_materials RENAME TO legacy_building_upgrade_materials;
ALTER TABLE building_worker_slots RENAME TO legacy_building_worker_slots;
ALTER TABLE building_resources RENAME TO legacy_building_resources;
ALTER TABLE building_states RENAME TO legacy_building_states;

CREATE TABLE building_states (
    world_id INTEGER NOT NULL REFERENCES worlds(id),
    faction TEXT NOT NULL,
    building TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
    cycle_start_time DOUBLE PRECISION NOT NULL,
    upgrade_finish_at DOUBLE PRECISION,
    PRIMARY KEY (world_id, faction, building)
);

CREATE TABLE building_resources (
    world_id INTEGER NOT NULL,
    faction TEXT NOT NULL,
    building TEXT NOT NULL,
    resource TEXT NOT NULL,
    storage INTEGER NOT NULL DEFAULT 0,
    buffer INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (world_id, faction, building, resource),
    FOREIGN KEY (world_id, faction, building) REFERENCES building_states(world_id, faction, building) ON DELETE CASCADE
);

CREATE TABLE building_worker_slots (
    world_id INTEGER NOT NULL,
    faction TEXT NOT NULL,
    building TEXT NOT NULL,
    slot_index INTEGER NOT NULL,
    occupied INTEGER NOT NULL DEFAULT 0,
    worker_id TEXT,
    hire_time DOUBLE PRECISION,
    credited JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (world_id, faction, building, slot_index),
    FOREIGN KEY (world_id, faction, building) REFERENCES building_states(world_id, faction, building) ON DELETE CASCADE
);

CREATE TABLE building_upgrade_materials (
    world_id INTEGER NOT NULL,
    faction TEXT NOT NULL,
    building TEXT NOT NULL,
    item_id INTEGER NOT NULL REFERENCES items_catalog(id),
    quantity INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (world_id, faction, building, item_id),
    FOREIGN KEY (world_id, faction, building) REFERENCES building_states(world_id, faction, building) ON DELETE CASCADE
);

-- Пока во всех мирах одна фракция: 'light'
CREATE TEMPORARY TABLE chosen_buildings ON COMMIT DROP AS
SELECT DISTINCT ON (characters.world_id, legacy.building)
    characters.world_id, legacy.building, legacy.character_id
FROM legacy_building_states AS legacy
JOIN characters ON characters.id = legacy.character_id
ORDER BY characters.world_id, legacy.building, legacy.level DESC, legacy.cycle_start_time;

INSERT INTO building_states (world_id, faction, building, level, cycle_start_time, upgrade_finish_at)
SELECT chosen.world_id, 'light', chosen.building, legacy.level, legacy.cycle_start_time, legacy.upgrade_finish_at
FROM chosen_buildings AS chosen
JOIN legacy_building_states AS legacy USING (character_id, building);

INSERT INTO building_resources (world_id, faction, building, resource, storage, buffer)
SELECT chosen.world_id, 'light', chosen.building, legacy.resource, legacy.storage, legacy.buffer
FROM chosen_buildings AS chosen
JOIN legacy_building_resources AS legacy USING (character_id, building);

INSERT INTO building_worker_slots (world_id, faction, building, slot_index, occupied, worker_id, hire_time, credited)
SELECT chosen.world_id, 'light', chosen.building, legacy.slot_index, legacy.occupied, legacy.worker_id,
       legacy.hire_time, legacy.credited
FROM chosen_buildings AS chosen
JOIN legacy_building_worker_slots AS legacy USING (character_id, building);

INSERT INTO building_upgrade_materials (world_id, faction, building, item_id, quantity)
SELECT chosen.world_id, 'light', chosen.building, legacy.item_id, legacy.quantity
FROM chosen_buildings AS chosen
JOIN legacy_building_upgrade_materials AS legacy USING (character_id, building);

DROP TABLE legacy_building_upgrade_materials;
DROP TABLE legacy_building_worker_slots;
DROP TABLE legacy_building_resources;
DROP TABLE legacy_building_states;
