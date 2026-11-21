ALTER TABLE map_saved ADD COLUMN crystal_settings_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE map_saved ADD COLUMN harvest_enabled BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE map_world_publish ADD COLUMN crystal_settings_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE map_world_publish ADD COLUMN harvest_enabled BOOLEAN NOT NULL DEFAULT FALSE;
