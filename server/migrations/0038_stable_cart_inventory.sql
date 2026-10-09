ALTER TABLE stable_cart_progress
    ADD COLUMN body_count INTEGER NOT NULL DEFAULT 0 CHECK (body_count >= 0);

UPDATE stable_cart_progress
SET body_count = CASE WHEN body_owned THEN 1 ELSE 0 END;

UPDATE stable_cart_progress
SET wood_deposited = 0, silver_deposited = 0
WHERE body_owned = TRUE AND body_finish_at IS NULL;