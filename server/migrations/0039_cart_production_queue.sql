CREATE TABLE stable_cart_production_orders (
    id BIGSERIAL PRIMARY KEY,
    world_id INTEGER NOT NULL,
    faction TEXT NOT NULL,
    building TEXT NOT NULL DEFAULT 'stable' CHECK (building = 'stable'),
    grade INTEGER NOT NULL CHECK (grade IN (1, 2)),
    created_at DOUBLE PRECISION NOT NULL,
    finish_at DOUBLE PRECISION NOT NULL,
    FOREIGN KEY (world_id, faction, building, grade)
        REFERENCES stable_cart_progress(world_id, faction, building, grade) ON DELETE CASCADE
);

CREATE INDEX stable_cart_production_queue_idx
    ON stable_cart_production_orders(world_id, faction, building, finish_at, id);

INSERT INTO stable_cart_production_orders
    (world_id, faction, building, grade, created_at, finish_at)
SELECT world_id, faction, building, grade, body_finish_at - 2400, body_finish_at
FROM stable_cart_progress
WHERE body_finish_at IS NOT NULL;

UPDATE stable_cart_progress SET body_finish_at = NULL WHERE body_finish_at IS NOT NULL;