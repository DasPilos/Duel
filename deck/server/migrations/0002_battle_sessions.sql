CREATE TABLE deck_battle_sessions (
    world_id BIGINT NOT NULL,
    session_id TEXT NOT NULL,
    state_json TEXT NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (world_id, session_id)
);

CREATE INDEX deck_battle_sessions_updated_at_idx
    ON deck_battle_sessions (world_id, updated_at);
