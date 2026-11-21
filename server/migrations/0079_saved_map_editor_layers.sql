ALTER TABLE map_saved
    ADD COLUMN editor_layers_json TEXT NOT NULL DEFAULT '[]';
