# 🚀 Инструкция для Operator 2 - Как присоединиться к проекту Duel

## ШАГ 1: Клонировать репозиторий

Второй разработчик должен выполнить эту команду в терминале/PowerShell:

```bash
git clone https://github.com/DasPilos/Duel.git
cd Duel
```

Это загрузит весь проект на его компьютер.

---

## ШАГ 2: Установить Python зависимости

```bash
pip install pygame
```

Проверить что всё установилось:
```bash
python -c "import pygame; print('OK')"
```

---

## ШАГ 3: Настроить Git (первый раз)

Если он первый раз работает с Git, нужно установить его имя и email:

```bash
git config --global user.name "Его Имя"
git config --global user.email "его_email@example.com"
```

Проверить:
```bash
git config --list
```

---

## ШАГ 4: Создать свою ветку для работы

**ВАЖНО:** Не работать в `main` ветке! Создать отдельную ветку для магов:

```bash
git checkout -b feature/mage-system
```

Теперь он работает в своей ветке и не мешает основной коду.

---

## ШАГ 5: Запустить сервер (для тестирования)

В одном терминале:
```bash
cd Duel
python -m server.main
```

Сервер запустится на `http://localhost:8765`

---

## ШАГ 6: Запустить клиент (для тестирования)

В другом терминале:
```bash
cd Duel
python main.py --online
```

Клиент запустится, можно зарегистрироваться и создать персонажа.

---

## ШАГ 7: Прочитать документацию проекта

**ОБЯЗАТЕЛЬНО прочитать эти файлы в таком порядке:**

1. **`OPERATOR2_GUIDE.md`** ← ГЛАВНЫЙ ГАЙД для магов
   - Описание архитектуры
   - Как работает БД
   - Какие файлы нужно создавать
   - Запрещенные практики

2. **`FEATURE_DELETE_CHARACTER.md`** 
   - Как реализована функция удаления персонажа
   - Пример безопасной архитектуры

3. **`README.md`**
   - Общая информация о проекте
   - Структура файлов

4. **`DEPLOYMENT_CHECKLIST.md`**
   - Как всё развертывается
   - Требования к системе

---

## ШАГ 8: Понять структуру проекта

Ключевые файлы которые он будет использовать:

```
Duel/
├── server/
│   ├── main.py              ← HTTP сервер, эндпоинты API
│   └── database.py          ← БД SQLite, методы для магов
│
├── client/
│   ├── session.py           ← Сессия игрока, методы магии
│   └── network.py           ← HTTP клиент для запросов
│
├── scenes/
│   ├── character_scene.py   ← Экран выбора персонажа (можно не трогать)
│   ├── profession_select_scene.py ← Выбор класса (нужно понять логику)
│   ├── tavern_scene.py      ← Таверна (шаблон для academy)
│   ├── academy/             ← НОВАЯ ПАПКА для школы магии
│   │   └── academy_scene.py ← Школа магии (скопировать tavern_scene.py)
│   └── ...
│
├── combat/
│   ├── fighter.py           ← Боец (шаблон для mage.py)
│   ├── mage.py              ← НОВЫЙ файл для магов
│   └── ...
│
└── docs/
    ├── OPERATOR2_GUIDE.md   ← ЧИТАй ЭТОТ ФАЙЛ ПЕРВЫМ!
    └── ...
```

---

## ШАГ 9: Первое задание - Создание Academy (Школа магии)

Когда он готов писать код:

### 9.1 Создать папку academy
```bash
mkdir scenes/academy
```

### 9.2 Скопировать шаблон
Скопировать содержимое `scenes/tavern_scene.py` в `scenes/academy/academy_scene.py`

### 9.3 Изменить класс
```python
# Было:
class TavernScene:

# Стало:
class AcademyScene:
```

### 9.4 Адаптировать для магов
- Изменить текст кнопок (не "Эль", а заклинания)
- Изменить координаты UI под магию
- Добавить магические способности вместо боевых

---

## ШАГ 10: Первый коммит

Когда написал первый код:

```bash
# 1. Проверить что всё работает
python main.py --online

# 2. Посмотреть какие файлы изменились
git status

# 3. Добавить файлы для коммита
git add scenes/academy/academy_scene.py
git add combat/mage.py
# (и остальные новые файлы)

# 4. Создать коммит
git commit -m "Add academy scene and mage combat system foundation

- Create academy_scene.py for mage training location
- Create mage.py with spell casting mechanics
- Implement mage-specific UI and interactions
- Setup integration with main game flow"

# 5. Запушить в свою ветку
git push origin feature/mage-system
```

---

## ШАГ 11: Создать Pull Request

После первого коммита:

1. Открыть GitHub репозиторий
2. Нажать "Compare & pull request"
3. Написать описание что он сделал
4. Первый разработчик (ты) проверит и смержит

---

## ⚠️ ВАЖНЫЕ ПРАВИЛА

### ✅ ДЕЛАТЬ:
- ✅ Работать в своей ветке (`feature/mage-system`)
- ✅ Делать коммиты часто (каждый логический блок)
- ✅ Писать понятные сообщения коммитов
- ✅ Тестировать перед коммитом
- ✅ Читать комментарии в `server/database.py`
- ✅ Использовать те же стили кода что и текущий проект

### ❌ НЕ ДЕЛАТЬ:
- ❌ Не работать в `main` ветке
- ❌ Не менять БД структуру без согласования
- ❌ Не создавать отдельную БД для магов
- ❌ Не хардкодить ID персонажей
- ❌ Не писать пароли в коде
- ❌ Не коммитить `server_data.sqlite3` и `cards.sqlite3`

---

## 🚨 ЕСЛИ ЧТО-ТО НЕ РАБОТАЕТ

### Git ошибка "refusing to merge unrelated histories"
```bash
git pull origin main --allow-unrelated-histories
```

### Python ошибка "ModuleNotFoundError"
```bash
# Убедиться что в папке Duel
cd Duel
python main.py --online
```

### Сервер не запускается
```bash
# Проверить что сервер работает
curl http://localhost:8765/api/login

# Если не работает, перезапустить
# Остановить все Python процессы и запустить заново
```

### БД не создается
Просто запустить сервер - БД создастся автоматически:
```bash
python -m server.main
```

---

## 📋 Чек-лист для Operator 2

```
[ ] 1. Зарегистрироваться на GitHub ✓ (уже сделано)
[ ] 2. Клонировать репозиторий: git clone
[ ] 3. Установить Python и pygame
[ ] 4. Настроить Git (имя и email)
[ ] 5. Создать свою ветку: git checkout -b feature/mage-system
[ ] 6. Запустить сервер: python -m server.main
[ ] 7. Запустить клиент: python main.py --online
[ ] 8. Прочитать OPERATOR2_GUIDE.md полностью
[ ] 9. Создать папку scenes/academy
[ ] 10. Написать academy_scene.py
[ ] 11. Написать combat/mage.py
[ ] 12. Добавить интеграцию в main.py
[ ] 13. Протестировать что всё работает
[ ] 14. Сделать первый коммит
[ ] 15. Запушить в свою ветку
[ ] 16. Создать Pull Request
```

---

## 📞 Контакт

Если есть вопросы - описать проблему и создать Issue на GitHub или написать комментарий в PR.

---

**Добро пожаловать в команду разработки Duel! 🎮✨**

Удачи с разработкой системы магии!
