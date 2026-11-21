ALTER TABLE map_saved
    DROP CONSTRAINT map_saved_map_w_check,
    DROP CONSTRAINT map_saved_map_h_check,
    ADD CONSTRAINT map_saved_map_w_check CHECK (map_w BETWEEN 16 AND 1600),
    ADD CONSTRAINT map_saved_map_h_check CHECK (map_h BETWEEN 16 AND 1600);

ALTER TABLE map_world_publish
    DROP CONSTRAINT map_world_publish_map_w_check,
    DROP CONSTRAINT map_world_publish_map_h_check,
    ADD CONSTRAINT map_world_publish_map_w_check CHECK (map_w BETWEEN 16 AND 1600),
    ADD CONSTRAINT map_world_publish_map_h_check CHECK (map_h BETWEEN 16 AND 1600);
