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

## Проверка после изменений

Сначала выполните тесты:

```powershell
python -m unittest discover -s tests -v
```

Затем проверьте синтаксис:

```powershell
python -m compileall -q main.py combat core scenes ui tests
```
