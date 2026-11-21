# Устранение проблем

## `ModuleNotFoundError: No module named 'pygame'`

Установите зависимости из корня проекта:

```powershell
python -m pip install -r requirements.txt
```

## Игра сразу закрывается или не открывает окно

Проверьте запуск из корня проекта:

```powershell
cd E:\python\game
python main.py
```

Убедитесь, что используется Python 3.13 или новее и установлен Pygame.

## Нет изображения бойца

Проверьте наличие файла:

```text
assets/fighters/base/fighter.png
```

При отсутствии файла игра использует силуэт.

## Godot не пускает на вход: несовместимость версий

Проверьте ответ сервера вручную:

```text
http://127.0.0.1:8765/api/version?app=client&version=1.0.0&protocol=1
```

В поле `compatibility.compatible` должно быть `true`. Если `false`, сравните `minimum_client_version` и `protocol_version` с `godot_client/scripts/api_client.gd` (`CLIENT_VERSION`, `PROTOCOL_VERSION`). Версии должны совпадать с сервером (`server/build_info.py`).

## Godot: «Укажите полный адрес сервера»

Введите адрес с протоколом и портом, например `http://127.0.0.1:8765`.

## Тесты падают: нет колонки `game_nickname`

Миграция `0085_game_nickname` лежит в `server/migrations/central/`. Тестовая схема (`tests/fixtures.py`) применяет только файлы верхнего уровня, поэтому колонки нет. Это известная проблема тестовой базы, а не ошибка игры. Рабочий сервер применяет центральные миграции при запуске.

## Godot-сцена не запускается из терминала

Используйте консольный исполняемый файл Godot 4.7.1 (`..._console.exe`) и путь `--path godot_client`, а не открытие проекта в редакторе. Команда и пример вывода: `docs/testing.md`, раздел «Тесты Godot-клиента».

## Проверка после изменений

Сначала выполните тесты:

```powershell
python -m unittest discover -s tests -v
```

Затем проверьте синтаксис:

```powershell
python -m compileall -q main.py combat core scenes ui tests
```
