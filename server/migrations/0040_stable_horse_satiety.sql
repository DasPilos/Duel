ALTER TABLE stable_horses
    ADD COLUMN satiety SMALLINT NOT NULL DEFAULT 100 CHECK (satiety BETWEEN 0 AND 100),
    ADD COLUMN satiety_progress DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (satiety_progress >= 0),
    ADD COLUMN satiety_updated_at DOUBLE PRECISION NOT NULL DEFAULT 0;

UPDATE stable_horses SET satiety_updated_at = purchased_at;