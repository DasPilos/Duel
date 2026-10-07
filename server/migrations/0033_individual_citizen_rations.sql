ALTER TABLE city_citizens
    ADD COLUMN alive BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN satiety_progress DOUBLE PRECISION NOT NULL DEFAULT 0
        CHECK (satiety_progress >= 0 AND satiety_progress < 1),
    ADD COLUMN strong_hunger INTEGER NOT NULL DEFAULT 0
        CHECK (strong_hunger BETWEEN 0 AND 100),
    ADD COLUMN strong_hunger_progress DOUBLE PRECISION NOT NULL DEFAULT 0
        CHECK (strong_hunger_progress >= 0 AND strong_hunger_progress < 1);

UPDATE city_citizens
SET satiety_updated_at = extract(epoch FROM clock_timestamp()),
    hunger_streak = 0,
    satisfaction = CASE
        WHEN satiety <= 10 THEN 'starving'
        WHEN satiety <= 30 THEN 'irritated'
        ELSE 'satisfied'
    END;