-- Сколько единиц каждого ресурса уже учтено у горожанина (один горожанин может давать несколько ресурсов).
ALTER TABLE building_worker_slots ADD COLUMN credited JSONB NOT NULL DEFAULT '{}'::jsonb;
