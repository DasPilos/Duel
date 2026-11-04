# Тестирование

## Окружение

Тесты используют Python 3.13, Pygame и временные PostgreSQL-схемы. Укажите
`TEST_DATABASE_URL` на отдельную disposable-БД; не запускайте тесты против Z440.
`tests/fixtures.py` создаёт и удаляет схему на каждый тестовый набор.

## Полная проверка

```powershell
python -m unittest discover -s tests -q
git diff --check
```

Некоторые UI-тесты создают скрытое окно Pygame; предупреждения профиля libpng
безвредны.

## Основные наборы

```powershell
python -m unittest tests.test_world_terrain -q
python -m unittest tests.test_server.ServerPersistenceTests.test_removed_city_progression_tables_are_absent tests.test_server.ServerPersistenceTests.test_retired_city_api_is_closed_but_map_terrain_is_available -q
```

Тесты проверяют спавн у кристалла возрождения, доступность глобальной карты,
сохранение нужных городских точек интереса и отключение API удалённых систем.
Старые тесты населения, городских улучшений, производства, кузницы, конюшни и
перевозок помечены пропущенными вместе с удалённой игровой механикой.

## Ручная проверка интерфейса

Запустите игру:

```powershell
python main.py
```

Проверьте спавн и возвращение к кристаллу, а также открытие гильдии, карточной
лавки, магазина припасов и библиотеки.
