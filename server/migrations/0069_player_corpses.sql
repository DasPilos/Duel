CREATE TABLE world_player_corpses (
    id BIGSERIAL PRIMARY KEY,
    world_id INTEGER NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    x DOUBLE PRECISION NOT NULL,
    y DOUBLE PRECISION NOT NULL,
    copper BIGINT NOT NULL CHECK (copper > 0),
    created_at DOUBLE PRECISION NOT NULL
);

CREATE INDEX world_player_corpses_character_idx ON world_player_corpses (world_id, character_id);
