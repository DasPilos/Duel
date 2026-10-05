ALTER TABLE city_citizens
    ADD COLUMN IF NOT EXISTS travel_direction TEXT;

UPDATE city_citizens
SET travel_direction = 'outbound'
WHERE working = TRUE AND arrival_at IS NOT NULL AND travel_direction IS NULL;