"""Карточный backend режима Deck, подключаемый центральным сервером.

Обычный запуск — `python -m server.central_main`; игровые маршруты Deck доступны
на выделенном сервере мира по `/api/deck`, данные хранятся в PostgreSQL-схеме `deck`.

Для локального запуска отдельного сервера мира Deck:
    DECK_WORLD_ID=<id мира с кодом deck…> python -m deck.server.main

`DECK_WORLD_ID` задаёт ID уже созданного мира с mode `deck` и кодом, начинающимся на `deck`.
`DECK_PORT`, `DECK_PUBLIC_URL`, `DECK_SCHEMA`, `DECK_SHARED_SCHEMA`, `DECK_DATA_DIR` и
`DATABASE_URL` (пароль — только в pgpass).
"""
