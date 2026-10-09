ALTER TABLE stable_cart_progress
    ADD COLUMN cart_wear_json JSONB NOT NULL DEFAULT '{}'::jsonb;