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

## Ручная проверка интерфейса

Запустите игру:

```powershell
python main.py
```

Проверьте город и замок, свободные/занятые места, вкладку фермы, общие склады,
конюшню и рейсы. Не тестируйте операции записи на production-данных.
