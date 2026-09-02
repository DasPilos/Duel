# Обновления UI - Refactoring Character Creation Flow

## Что было изменено

### 1. ✅ Опущена таблица персонажей на 70 пикселей
- CharacterScene list: Y=240 → Y=310
- Continue button: Y=1000 → Y=920
- Delete button: Y=1070 → Y=990
- Character card: Y=180 → Y=100

### 2. ✅ Удалена надпись "ПЕРСОНАЖИ"
- Убрана title из draw() метода
- Убрана подсказка "Выберите героя или создайте нового"

### 3. ✅ Переделана логика создания персонажа

**Было:**
```
CharacterScene (список + форма создания)
  ↓
ProfessionSelectScene
  ↓
TavernScene
```

**Теперь:**
```
CharacterScene (только список + кнопка "Создать персонажа")
  ↓ (при нажатии "Создать")
CreateCharacterScene (ввод имени + выбор класса)
  ├─ Персонаж НЕ создается в БД до нажатия кнопки "Создать"
  ├─ Кнопка "Назад" возвращает в CharacterScene БЕЗ создания
  └─ Кнопка "Создать" добавляет персонажа в БД
      ↓
    ProfessionSelectScene
      ├─ Кнопка "Назад" удаляет персонажа и возвращает в CharacterScene
      └─ Выбор класса → TavernScene
```

## Файлы

### Модифицировано:
- **scenes/character_scene.py** - убрана форма создания, оставлен только список
- **main.py** - обновлены переходы между сценами

### Создано:
- **scenes/create_character_scene.py** - новый экран для создания персонажа

## Преимущества новой архитектуры

✅ Персонаж создается в БД только при финальном подтверждении
✅ "Назад" работает правильно - не создает "зомби" персонажей в БД
✅ Четкое разделение экранов:
  - CharacterScene = список персонажей
  - CreateCharacterScene = процесс создания
  - ProfessionSelectScene = выбор класса
✅ Уменьшилась сложность каждого экрана
✅ Проще добавлять новые функции

## Тестирование

Протестировать следующие сценарии:
1. ✓ Выбор существующего персонажа и вход в таверну
2. ✓ Нажатие "Создать персонажа" → переход в CreateCharacterScene
3. ✓ Нажатие "Назад" в CreateCharacterScene → возврат в CharacterScene (персонаж не создан)
4. ✓ Создание персонажа → переход в ProfessionSelectScene
5. ✓ Нажатие "Назад" в ProfessionSelectScene → удаление персонажа и возврат в CharacterScene
6. ✓ Выбор класса в ProfessionSelectScene → вход в TavernScene

## Git Commit

```
b44c25b Refactor character creation flow - separate creation screen with proper transitions
```
