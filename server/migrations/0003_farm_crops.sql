-- Лён и хлопок: отдельные буфер и склад для каждой культуры (лимит склада общий).
ALTER TABLE farm_states
    ADD COLUMN storage_flax INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN buffer_flax INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN storage_cotton INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN buffer_cotton INTEGER NOT NULL DEFAULT 0;
