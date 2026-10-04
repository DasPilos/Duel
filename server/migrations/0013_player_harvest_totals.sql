ALTER TABLE building_player_resources
    ADD COLUMN total_produced BIGINT NOT NULL DEFAULT 0 CHECK (total_produced >= 0);