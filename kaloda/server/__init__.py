"""Сервер мира Колоды.

С Оператором 1 нас связывают только база PostgreSQL (учётные записи, сессии, список миров) и лобби.
Всё игровое — персонажи, предметы, колоды, чат, бои — лежит в нашей схеме `kaloda`.

Запуск одного мира (из корня репозитория):
    KALODA_WORLD_ID=<id мира с кодом kaloda…> python -m kaloda.server.main

Переменные окружения: KALODA_WORLD_ID (обязательна), KALODA_PORT (по умолчанию 8766),
KALODA_PUBLIC_URL (адрес, который увидит лобби), KALODA_SCHEMA (по умолчанию kaloda),
KALODA_SHARED_SCHEMA (по умолчанию public), KALODA_DATA_DIR (состояние ботов, по умолчанию data/kaloda),
DATABASE_URL (пароль — только в pgpass).
"""
