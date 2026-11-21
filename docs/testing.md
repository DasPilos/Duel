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
python -m unittest tests.test_city_population tests.test_city_storage -q
python -m unittest tests.test_production_buildings tests.test_production_building_window -q
python -m unittest tests.test_transport tests.test_castle_window -q
```

Фермерские проверки покрывают уровень 1/2, склад 500/800, места каждого поля,
отдельные бонусы плуга `+5%` и рукояти `+8%`, накопительный таймер `122` секунды,
серверные требования улучшений и Governor income. UI-тесты проверяют видимость
карточек по уровню и прикрепление слота к правильному полю.

## Тесты Godot-клиента

Сцены `godot_client/tests/*.tscn` запускаются без окна. Укажите консольный исполняемый файл Godot 4.7.1:

```powershell
& "<путь-к-Godot>\Godot_v4.7.1-stable_win64_console.exe" --headless --path godot_client --scene res://tests/tower_entity_smoke_test.tscn
```

Успех: строка `<имя>: OK (N checks)`. Ошибки выводятся как `ERROR:` с номером проверки. Всего 103 сцены. На момент передачи падают `map_editor_spawns_smoke_test`, `map_editor_seed_smoke_test` и `deck_player_sprite_smoke_test`. Подробности: `docs/CLIENT_MIGRATION_OPERATOR2.md`, шаг 8.

## Ручная проверка интерфейса

Запустите игру:

```powershell
python main.py
```

Проверьте город и замок, свободные/занятые места, вкладку фермы, общие склады,
конюшню и рейсы. Не тестируйте операции записи на production-данных.
