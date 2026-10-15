CREATE TABLE castle_upgrade_state (
    world_id INTEGER NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    faction TEXT NOT NULL,
    castle_level INTEGER NOT NULL CHECK (castle_level >= 1),
    upgrade_id TEXT NOT NULL,
    finish_at DOUBLE PRECISION,
    done BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (world_id, faction, castle_level, upgrade_id),
    FOREIGN KEY (world_id, faction)
        REFERENCES city_population_state(world_id, faction) ON DELETE CASCADE
);

INSERT INTO castle_upgrade_state (world_id, faction, castle_level, upgrade_id, finish_at, done)
SELECT world_id, faction, castle_level, 'treasury_edict', treasury_edict_finish_at, treasury_edict_done
FROM city_population_state
WHERE treasury_edict_done OR treasury_edict_finish_at IS NOT NULL;

ALTER TABLE city_population_state
    DROP COLUMN treasury_edict_finish_at,
    DROP COLUMN treasury_edict_done;
