ALTER TABLE worlds
    ADD COLUMN IF NOT EXISTS mode TEXT NOT NULL DEFAULT 'tower',
    ADD COLUMN IF NOT EXISTS test_only BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS server_url TEXT,
    ADD COLUMN IF NOT EXISTS opens_at DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS closes_at DOUBLE PRECISION;

INSERT INTO worlds (id, code, name, status, created_at, mode, test_only)
VALUES (5, 'kaloda1', 'Колода', 'open', extract(epoch FROM now()), 'tower', FALSE)
ON CONFLICT (id) DO NOTHING;
