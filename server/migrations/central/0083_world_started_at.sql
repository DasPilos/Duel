-- Колонка уже есть в тестовых схемах после основной миграции 0082; IF NOT EXISTS делает повтор безопасным.
ALTER TABLE worlds ADD COLUMN IF NOT EXISTS started_at DOUBLE PRECISION;
