ALTER TABLE city_citizens
    ADD COLUMN return_progress DOUBLE PRECISION NOT NULL DEFAULT 1
        CHECK (return_progress >= 0 AND return_progress <= 1),
    ADD COLUMN return_started_at DOUBLE PRECISION;
