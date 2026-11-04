"""Карточный backend Колоды, подключаемый центральным сервером.

Обычный запуск проекта — `python -m server.main`: маршруты Колоды доступны на том же
порту под `/kaloda`, а её игровые таблицы остаются в отдельной схеме PostgreSQL `kaloda`.

Для отдельного локального запуска backend (режим разработки):
    KALODA_WORLD_ID=<id мира с кодом kaloda…> python -m kaloda.server.main

Для объединённого процесса `KALODA_WORLD_ID` по умолчанию равен 5; для другого
ID заранее создайте мир с кодом, начинающимся на `kaloda`. `KALODA_PORT` и
`KALODA_PUBLIC_URL` нужны только при отдельном локальном запуске. Также
поддерживаются `KALODA_SCHEMA`, `KALODA_SHARED_SCHEMA`, `KALODA_DATA_DIR` и
`DATABASE_URL` (пароль — только в pgpass).
"""
