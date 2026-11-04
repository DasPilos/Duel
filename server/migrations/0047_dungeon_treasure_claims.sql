CREATE TABLE character_dungeon_treasure_claims (
    character_id BIGINT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    request_id UUID NOT NULL,
    rewards_json TEXT NOT NULL,
    created_at DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (character_id, request_id)
);
