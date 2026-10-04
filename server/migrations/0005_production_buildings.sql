-- Общие таблицы производственных зданий (поселение, лагерь лесорубов); данные фермы переносятся.
CREATE TABLE building_states (
    character_id BIGINT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    building TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
    cycle_start_time DOUBLE PRECISION NOT NULL,
    upgrade_finish_at DOUBLE PRECISION,
    PRIMARY KEY (character_id, building)
);

CREATE TABLE building_resources (
    character_id BIGINT NOT NULL,
    building TEXT NOT NULL,
    resource TEXT NOT NULL,
    storage INTEGER NOT NULL DEFAULT 0,
    buffer INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (character_id, building, resource),
    FOREIGN KEY (character_id, building) REFERENCES building_states(character_id, building) ON DELETE CASCADE
);

CREATE TABLE building_worker_slots (
    character_id BIGINT NOT NULL,
    building TEXT NOT NULL,
    slot_index INTEGER NOT NULL,
    occupied INTEGER NOT NULL DEFAULT 0,
    worker_id TEXT,
    hire_time DOUBLE PRECISION,
    PRIMARY KEY (character_id, building, slot_index),
    FOREIGN KEY (character_id, building) REFERENCES building_states(character_id, building) ON DELETE CASCADE
);

CREATE TABLE building_upgrade_materials (
    character_id BIGINT NOT NULL,
    building TEXT NOT NULL,
    item_id INTEGER NOT NULL REFERENCES items_catalog(id),
    quantity INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (character_id, building, item_id),
    FOREIGN KEY (character_id, building) REFERENCES building_states(character_id, building) ON DELETE CASCADE
);

INSERT INTO building_states (character_id, building, level, cycle_start_time, upgrade_finish_at)
SELECT character_id, 'farm', level, cycle_start_time, upgrade_finish_at FROM farm_states;

INSERT INTO building_resources (character_id, building, resource, storage, buffer)
SELECT character_id, 'farm', 'wheat', storage_wheat, buffer_wheat FROM farm_states
UNION ALL
SELECT character_id, 'farm', 'flax', storage_flax, buffer_flax FROM farm_states
UNION ALL
SELECT character_id, 'farm', 'cotton', storage_cotton, buffer_cotton FROM farm_states;

INSERT INTO building_worker_slots (character_id, building, slot_index, occupied, worker_id, hire_time)
SELECT character_id, 'farm', slot_index, occupied, worker_id, hire_time FROM farm_worker_slots;

INSERT INTO building_upgrade_materials (character_id, building, item_id, quantity)
SELECT character_id, 'farm', item_id, quantity FROM farm_upgrade_materials;

DROP TABLE farm_upgrade_materials;
DROP TABLE farm_worker_slots;
DROP TABLE farm_states;
