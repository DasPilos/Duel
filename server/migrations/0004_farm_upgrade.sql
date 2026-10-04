-- Улучшение поселения: сданные игроком материалы и время окончания стройки.
ALTER TABLE farm_states ADD COLUMN upgrade_finish_at DOUBLE PRECISION;

CREATE TABLE farm_upgrade_materials (
    character_id BIGINT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES items_catalog(id),
    quantity INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (character_id, item_id)
);
