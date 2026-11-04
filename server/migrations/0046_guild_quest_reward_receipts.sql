CREATE TABLE IF NOT EXISTS guild_quest_reward_receipts (
    character_id BIGINT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    request_id TEXT NOT NULL,
    quest_id TEXT NOT NULL,
    created_at DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (character_id, request_id)
);
