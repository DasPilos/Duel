ALTER TABLE map_catalog
    ADD COLUMN editor_layer INTEGER NOT NULL DEFAULT 3
    CHECK (editor_layer BETWEEN 1 AND 8);

CREATE TABLE map_palette_settings (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    version INTEGER NOT NULL DEFAULT 1,
    overrides_json TEXT NOT NULL DEFAULT '{}'
);

INSERT INTO map_palette_settings (singleton, version, overrides_json)
VALUES (TRUE, 1, '{}')
ON CONFLICT (singleton) DO NOTHING;
