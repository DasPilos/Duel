CREATE TABLE npc_kill_xp_receipts (
    character_id BIGINT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    request_id UUID NOT NULL,
    encounter_id TEXT NOT NULL,
    xp_awarded INTEGER NOT NULL,
    created_at DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (character_id, request_id)
);
