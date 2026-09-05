# 👋 Добро пожаловать в команду разработки Duel!

Это полный гайд для второго разработчика (Operator 2) как присоединиться к проекту и начать разработку системы магии.

## 🎯 Твоя задача

**Разработать систему магии для игры Duel**, включая:
- Школу магии (Academy)
- Боевую систему для магов
- Заклинания и магические способности
- UI для магов

## 📋 Шаги подключения

### Шаг 1: Клонировать репозиторий (1 мин)

Открыть терминал/PowerShell и выполнить:

```bash
git clone https://github.com/DasPilos/Duel.git
cd Duel
```

### Шаг 2: Установить зависимости (2 мин)

```bash
pip install pygame
```

Проверить:
```bash
python -c "import pygame; print('Pygame установлен!')"
```

### Шаг 3: Настроить Git (первый раз)

```bash
git config --global user.name "Твое Имя"
git config --global user.email "твой_email@example.com"
```

### Шаг 4: Создать свою ветку

**ВАЖНО:** Не работай в `main` ветке! Создай свою:

```bash
git checkout -b feature/mage-system
```

### Шаг 5: Запустить сервер (для тестирования)

Открыть терминал и выполнить:

```bash
python -m server.main
```

Сервер запустится на `http://localhost:8765`

### Шаг 6: Запустить клиент (в другом терминале)

```bash
python main.py --online
```

Теперь можешь зарегистрироваться и протестировать игру.

### Шаг 7: Прочитать документацию

📄 **ОБЯЗАТЕЛЬНО прочитай:**

1. **`OPERATOR2_GUIDE.md`** ← ГЛАВНЫЙ документ
   - Как устроена система
   - Архитектура БД
   - Какие файлы создавать
   - Запрещенные практики

2. **`FEATURE_DELETE_CHARACTER.md`** 
   - Пример безопасной реализации функции

3. **`README.md`**
   - Общая информация

## 🏗️ Структура проекта

```
Duel/
├── server/
│   ├── main.py              ← HTTP сервер (туда добавлять эндпоинты для магии)
│   └── database.py          ← БД (туда добавлять методы для магов)
│
├── client/
│   ├── session.py           ← Сессия (сюда добавлять методы магии)
│   └── network.py           ← HTTP клиент
│
├── scenes/
│   ├── tavern_scene.py      ← Таверна для воинов (шаблон для academy)
│   ├── academy/             ← НОВАЯ папка для магов
│   │   └── academy_scene.py ← Школа магии (создаст ОП2)
│   ├── character_scene.py   ← Выбор персонажа
│   └── ...
│
├── combat/
│   ├── fighter.py           ← Боевая система воинов (шаблон)
│   ├── mage.py              ← НОВЫЙ файл для магов (создаст ОП2)
│   └── ...
│
├── docs/
│   ├── OPERATOR2_GUIDE.md              ← Прочитай первым
│   ├── OPERATOR2_SETUP_GUIDE.md        ← Полная инструкция
│   ├── QUICK_START_OPERATOR2.md        ← Быстрый старт
│   └── ...
└── ...
```

## 💡 Ключевые моменты

### ✅ ДЕЛАТЬ:
- ✅ Работать в ветке `feature/mage-system`
- ✅ Часто делать коммиты (каждый логический блок)
- ✅ Тестировать перед коммитом
- ✅ Писать понятные сообщения коммитов
- ✅ Читать коды в `server/database.py`

### ❌ НЕ ДЕЛАТЬ:
- ❌ Не работать в `main` ветке
- ❌ Не менять существующие таблицы БД
- ❌ Не создавать отдельную БД для магов
- ❌ Не писать пароли и секреты в коде
- ❌ Не коммитить бинарные файлы БД

## 🚀 Первое задание

### 1. Создать папку для Academy
```bash
mkdir scenes/academy
```

### 2. Скопировать tavern_scene.py
Скопировать содержимое `scenes/tavern_scene.py` в новый файл `scenes/academy/academy_scene.py`

### 3. Переименовать класс
```python
# Было:
class TavernScene:

# Стало:
class AcademyScene:
```

### 4. Адаптировать для магов
- Изменить текст и кнопки
- Добавить магические способности
- Создать UI для заклинаний

### 5. Сделать коммит
```bash
git add scenes/academy/academy_scene.py
git commit -m "Add academy scene foundation for mage training

- Create academy_scene.py based on tavern template
- Implement mage-specific training mechanics
- Add spell selection UI"
git push origin feature/mage-system
```

## 📞 Если что-то не работает

### Git не работает
```bash
# Переинициализировать Git
git init
git add .
git commit -m "Initial commit"
```

### Python не находит модули
```bash
# Убедиться что находишься в папке Duel
cd Duel
pip install pygame
```

### Сервер не запускается
```bash
# Проверить что слушает на порту
# Остановить все Python процессы и запустить заново
python -m server.main
```

## ✅ Чек-лист для начала

```
[ ] 1. Клонировать репозиторий
[ ] 2. Установить pygame
[ ] 3. Настроить Git (имя и email)
[ ] 4. Создать ветку feature/mage-system
[ ] 5. Запустить сервер и клиент
[ ] 6. Прочитать OPERATOR2_GUIDE.md
[ ] 7. Протестировать игру
[ ] 8. Создать папку scenes/academy
[ ] 9. Создать academy_scene.py
[ ] 10. Сделать первый коммит
```

## 📞 Контакты

Если вопросы:
- Читай `OPERATOR2_GUIDE.md`
- Пиши комментарии в Pull Request
- Создавай Issues на GitHub

## 🎉 Добро пожаловать!

Готов ли ты начать разработку? Удачи! 🚀✨

**Читай `OPERATOR2_GUIDE.md` перед тем как начать писать код!**
