ALTER TABLE map_world_publish ADD COLUMN saved_id INTEGER REFERENCES map_saved(id) ON DELETE SET NULL;
