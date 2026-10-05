ALTER TABLE city_citizens
    ADD COLUMN IF NOT EXISTS satiety_updated_at DOUBLE PRECISION NOT NULL DEFAULT 0;

UPDATE city_citizens
SET satiety_updated_at = created_at
WHERE satiety_updated_at = 0;