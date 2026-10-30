ALTER TABLE map_world_publish DROP COLUMN draft_id;
ALTER TABLE map_world_publish ADD COLUMN name TEXT NOT NULL DEFAULT '';

DROP TABLE map_meta;
DROP TABLE map_cells;
DROP TABLE map_draft_cells;
DROP TABLE map_drafts;
