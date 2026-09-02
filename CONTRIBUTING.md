# Рекомендации для разработчиков

⚠️ **ЧИТАЙТЕ СНАЧАЛА:**
1. [ARCHITECTURE_DUAL_SYSTEM.md](./ARCHITECTURE_DUAL_SYSTEM.md) - как работает единая БД
2. [MAGE_DEVELOPER_GUIDE.md](./MAGE_DEVELOPER_GUIDE.md) - для второго разработчика

## 🎯 АРХИТЕКТУРА ДВОЙНОЙ СИСТЕМЫ

### Валюта и инвентарь (ОБЩИЕ для всех типов персонажей)

```python
# ✅ ПРАВИЛЬНО: Используй методы БД
from server.database import Database
db = Database()

# Добавить деньги (работает для воина и мага)
db.add_currency(character_id=1, copper=10)
db.add_currency(character_id=2, copper=20)  # может быть маг

# Вычесть деньги (проверяет достаточность)
success = db.subtract_currency(character_id=1, copper=20)
if success:
    print("Деньги вычтены!")
else:
    print("Недостаточно средств!")

# Инвентарь (ОБЩИЙ для всех)
db.add_to_inventory(character_id=1, item_id="drink_ale", quantity=1)

# ❌ НЕПРАВИЛЬНО: Не считай на клиенте
character.copper -= 20  # ОПАСНО! локальная переменная
inventory.append(item)  # ОПАСНО! не сохранится на сервере
```

### Разделение кода

#### Оператор 1 (Воины) - ваша собственность:
```
✅ scenes/duel_scene.py         - боевая система воинов
✅ core/character/warrior.py    - класс Warrior
✅ core/stats/warrior_stats.py  - статистика воинов
✅ ui/character_card.py         - карточка воина
```

**НЕ трогайте:**
- `core/character/mage.py` - это для ОП2
- `scenes/mage_duel_scene.py` - это для ОП2
- `core/magic/*` - это для ОП2

#### Оператор 2 (Маги) - ваша собственность:
```
✅ scenes/mage_duel_scene.py    - боевая система магов
✅ core/character/mage.py       - класс Mage
✅ core/magic/spell.py          - заклинания
✅ core/magic/element.py        - элементы
✅ core/magic/spellbook.py      - гримуар
✅ ui/mage_card.py              - карточка мага
```

**НЕ трогайте:**
- `core/character/warrior.py` - это для ОП1
- `scenes/duel_scene.py` - это для ОП1
- `core/stats/warrior_stats.py` - это для ОП1

#### Общее (оба разработчика, но осторожно!):
```
⚠️ server/database.py  - добавляйте методы, не меняйте существующие
⚠️ server/main.py      - добавляйте endpoints
⚠️ ui/shop.py          - может адаптироваться для обоих
⚠️ ui/inventory.py     - может адаптироваться для обоих
```

**Правило:** Если нужно менять общий файл - создайте новый метод, не меняйте существующие!

## 🚀 Быстрый старт

### 1. Подготовка окружения

```bash
# Клонировать репозиторий
git clone https://github.com/DasPilos/Duel.git
cd Duel

# Создать и активировать виртуальное окружение
python -m venv .venv
.venv\Scripts\activate  # Windows
# или
source .venv/bin/activate  # Linux/Mac

# Установить зависимости
pip install -r requirements.txt
```

### 2. Запустить локально

```bash
# Локальный режим (без сервера)
python main.py

# Или с сервером (два терминала)
# Терминал 1:
python -m server.main

# Терминал 2:
python main.py --online
```

## 📋 Git workflow

### Создание ветки для новой фичи

```bash
# Обновить main
git checkout main
git pull origin main

# Создать новую ветку
git checkout -b feature/описание-фичи
# или для багов:
git checkout -b bugfix/описание-бага
```

### Примеры названий ветвей

```
feature/drinks-system          # Новая фича
feature/inventory-ui           # UI улучшения
bugfix/currency-normalization  # Исправление бага
docs/api-documentation         # Документация
refactor/duel-scene-cleanup    # Рефакторинг
```

### Коммиты

```bash
# Просмотр статуса
git status

# Добавить файлы
git add .
# или конкретные файлы:
git add файл1.py файл2.py

# Создать коммит с хорошим описанием
git commit -m "Добавить систему напитков с магазином

- Реализовать API endpoints для напитков
- Добавить UI магазина с hover эффектами
- Реализовать проверку баланса и вычисление цены
- Добавить tooltip с описанием эффектов"
```

### Правила для комментариев (commit messages)

✅ **Хорошо:**
```
Добавить систему напитков в таверне

- Реализовано GET /api/drinks endpoint
- Добавлены hover эффекты в UI
- Реализована проверка баланса игрока
- Добавлено сообщение об ошибке
```

❌ **Плохо:**
```
fix bug
изменил файл
update
```

### Push на GitHub

```bash
# Отправить ветку
git push origin feature/описание-фичи

# Создать Pull Request на GitHub
# (GitHub покажет кнопку "Create Pull Request")
```

## 🏗️ Архитектурные принципы

### Разделение ответственности

1. **Scenes** (`scenes/`) - Управление состоянием и логикой сцены
2. **UI** (`ui/`) - Отрисовка и обработка пользовательского ввода
3. **Server** (`server/`) - Backend логика и БД
4. **Client** (`client/`) - Сетевое взаимодействие
5. **Core** (`core/`) - Общие утилиты и модели данных

### Пример добавления новой фичи

**Сценарий:** Добавить новый напиток "Зелье маны"

#### 1. Backend (server/database.py)

```python
# В _initialize_drinks():
drinks = [
    {
        'name': 'Эль',
        'description': 'восстанавливает 50 HP',
        'price_copper': 20,
        'effect': 'recovery',
        'effect_value': 50
    },
    {
        'name': 'Зелье маны',
        'description': 'восстанавливает 30 MP',
        'price_copper': 30,
        'effect': 'mana',
        'effect_value': 30
    }
]
```

#### 2. Frontend (ui/tavern_shop.py)

```python
# Автоматически загружается с сервера через:
def load_drinks(self):
    drinks = self.session.get_drinks_list()
    self.drinks = drinks
```

#### 3. Использование (scenes/tavern_scene.py)

```python
# Обработка применения эффекта
def _use_drink(self, drink):
    if drink['effect'] == 'recovery':
        self.character['hp'] = min(
            self.character['hp'] + drink['effect_value'],
            self.character['max_hp']
        )
    elif drink['effect'] == 'mana':
        self.character['mp'] = min(
            self.character['mp'] + drink['effect_value'],
            self.character['max_mp']
        )
```

## 💾 Работа с БД

### Структура файла database.py

```python
class Database:
    def __init__(self, db_path):
        # Инициализация БД
        
    def initialize(self):
        # Создание таблиц и инициализация данных
        
    def get_character(self, user_id, character_id):
        # Получить персонажа
        
    def save_character(self, user_id, character_id, character_data):
        # Сохранить персонажа
        
    # ... другие методы
```

### Добавление новой таблицы

```python
# В методе initialize():
cursor.execute('''
    CREATE TABLE IF NOT EXISTS new_table (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
''')

# Добавить метод для работы с таблицей:
def get_new_data(self, user_id):
    cursor = self.connection.cursor()
    cursor.execute('SELECT * FROM new_table WHERE user_id = ?', (user_id,))
    return cursor.fetchall()
```

## 🎮 Работа со Scenes

### Структура сцены

```python
class MyScene:
    def __init__(self, session):
        self.session = session
        self.finished = False
        
    def handle_event(self, event):
        # Обработка пользовательского ввода
        pass
    
    def update(self, dt):
        # Обновление логики (dt - дельта времени)
        pass
    
    def draw(self, screen):
        # Отрисовка на экран
        pass
    
    def close(self):
        # Очистка ресурсов
        pass
```

### Переход между сценами

```python
# В main.py:
current_scene = TavernScene(session)

while not current_scene.finished:
    # Обработка событий
    for event in pygame.event.get():
        current_scene.handle_event(event)
    
    # Обновление
    current_scene.update(dt)
    
    # Отрисовка
    current_scene.draw(screen)
    
    # Переход на следующую сцену
    if isinstance(current_scene, TavernScene) and current_scene.navigate:
        if current_scene.navigate == "battle":
            current_scene.close()
            current_scene = DuelScene(session)
```

## 🎨 UI компоненты

### Добавление новой UI панели

```python
class MyPanel:
    def __init__(self, action_font, small_font):
        self.action_font = action_font
        self.small_font = small_font
        self.is_open = False
        self.frame = pygame.Rect(x, y, width, height)
    
    def open(self):
        self.is_open = True
    
    def close(self):
        self.is_open = False
    
    def handle_click(self, position):
        if not self.is_open:
            return None
        # Обработка кликов
        return "action_name"
    
    def draw(self, screen):
        if not self.is_open:
            return
        # Отрисовка панели
```

## 🧪 Тестирование

### Запуск тестов

```bash
# Все тесты
pytest

# Конкретный тест файл
pytest tests/test_currency.py

# С покрытием кода
pytest --cov=core

# Verbose вывод
pytest -v
```

### Написание теста

```python
# tests/test_my_feature.py
import pytest
from core.currency import Currency

def test_currency_normalization():
    currency = Currency(copper=150, silver=0, gold=0)
    currency.normalize()
    
    assert currency.copper == 50
    assert currency.silver == 1
    assert currency.gold == 0
```

## 📊 Профилирование и отладка

### Использование debugger

```python
# В коде:
import pdb
pdb.set_trace()  # Точка останова

# Команды в debugger:
# n - next line
# s - step into
# c - continue
# l - list code
# p <var> - print variable
# q - quit
```

### Чтение логов

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug("Debug сообщение")
logger.info("Информационное сообщение")
logger.warning("Предупреждение")
logger.error("Ошибка")
```

## 📈 Производительность

### Оптимизация рендеринга

```python
# ❌ Плохо - создаёт новый Surface каждый фрейм
def draw(self, screen):
    text = self.font.render("Hello", True, (255, 255, 255))
    screen.blit(text, (0, 0))

# ✅ Хорошо - кэширует результат рендеринга
def __init__(self):
    self.text = self.font.render("Hello", True, (255, 255, 255))

def draw(self, screen):
    screen.blit(self.text, (0, 0))
```

### Профилирование кода

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Ваш код здесь
my_function()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(10)  # Топ 10 функций
```

## 🔍 Код-ревью

Перед созданием PR:

- [ ] Код работает локально без ошибок
- [ ] Нет console.log / print отладочного вывода
- [ ] Следуется PEP 8
- [ ] Добавлены комментарии к сложному коду
- [ ] Обновлена документация если нужно
- [ ] Нет merge конфликтов с main

## 🐛 Отладка common проблем

### Проблема: "ModuleNotFoundError: No module named 'pygame'"
```bash
pip install pygame
```

### Проблема: "Connection refused" при подключении к серверу
```bash
# Убедитесь что сервер запущен:
python -m server.main
```

### Проблема: БД заблокирована
```bash
# Удалить БД и пересоздать:
del server_data.sqlite3
python -m server.main
```

## 📚 Полезные ресурсы

- [Pygame документация](https://www.pygame.org/docs/)
- [Python asyncio](https://docs.python.org/3/library/asyncio.html)
- [SQLite3](https://docs.python.org/3/library/sqlite3.html)
- [Git workflow](https://git-scm.com/book/en/v2)
- [PEP 8 - Python Style Guide](https://www.python.org/dev/peps/pep-0008/)

---

Спасибо за помощь в развитии игры! 🚀
