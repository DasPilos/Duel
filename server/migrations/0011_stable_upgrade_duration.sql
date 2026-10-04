ALTER TABLE stable_stall_upgrades
    ADD COLUMN finish_at DOUBLE PRECISION;

UPDATE stable_stall_upgrades
SET finish_at = purchased_at;