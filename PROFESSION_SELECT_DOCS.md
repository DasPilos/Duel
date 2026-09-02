## Profession Selection System - Документация

### Описание
В игре реализована система выбора профессии при создании персонажа. Игрок может выбрать между **Воином (Warrior)** и **Магом (Mage)**, что определяет его стартовые навыки, статы и дальнейшее развитие.

### Архитектура

#### 1. Frontend (Client)
- **ProfessionSelectScene** (`scenes/profession_select_scene.py`)
  - Новый экран выбора между Воином и Магом
  - Интерактивные кнопки с описанием каждой профессии
  - Ввод имени персонажа
  - Отправка выбора на сервер

#### 2. Backend (Server)
- **Database Schema**: Добавлена колонка `type` в таблицу `characters`
  - `type TEXT NOT NULL DEFAULT 'warrior'` - тип персонажа ('warrior' или 'mage')
  
- **API Endpoint**: `POST /api/characters`
  - Теперь требует параметр `profession_type` (optional, default='warrior')
  - Валидирует значение: только 'warrior' или 'mage'
  - Создает персонажа с соответствующей статистикой

#### 3. Character Creation Flow
```
TitleScene (вход) 
    ↓
CharacterScene (список персонажей)
    ↓
ProfessionSelectScene (НОВОЕ - выбор профессии)
    ↓
TavernScene (основная игра)
```

### Реализованные изменения

#### Файлы добавлены:
- `scenes/profession_select_scene.py` - Scene выбора профессии

#### Файлы изменены:
- `main.py` - Добавлен импорт ProfessionSelectScene и переход
- `client/session.py` - Обновлен метод `create_character()` для передачи profession_type
- `client/network.py` - Обновлен метод `create_character()` для отправки profession_type
- `server/main.py` - Обновлен POST /api/characters для обработки profession_type
- `server/database.py` - Обновлены методы `initialize()` и `create_character()` для работы с type
- `scenes/character_scene.py` - Обновлен вызов `create_character()` с профессией 'warrior'

### Стартовая статистика

#### Warrior (Воин)
```json
{
  "strength": 3,
  "agility": 3,
  "intuition": 3,
  "endurance": 4
}
```

#### Mage (Маг)
```json
{
  "wisdom": 3,
  "spirituality": 3,
  "endurance": 4
}
```

### UI/UX
- Экран с двумя большими карточками (Воин и Маг)
- Каждая карточка содержит:
  - Эмодзи (⚔️ для воина, 🧙 для мага)
  - Название профессии
  - Краткое описание способностей
  - Подсвечивается при наведении мыши
  - Выделяется при выборе
- Кнопка "Создать" активна только после выбора профессии и ввода имени
- Красная ошибка если возникает проблема создания

### Примеры использования API

#### Создать Warrior
```http
POST /api/characters HTTP/1.1
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Артур",
  "profession_type": "warrior"
}
```

#### Создать Mage
```http
POST /api/characters HTTP/1.1
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Мерлин",
  "profession_type": "mage"
}
```

#### Ответ успеха
```json
{
  "character": {
    "id": 42,
    "user_id": 1,
    "name": "Артур",
    "type": "warrior",
    "level": 1,
    "xp": 0,
    "hp": 40,
    "max_hp": 40,
    "mp": 50,
    "max_mp": 50,
    "stats_json": "{\"strength\": 3, \"agility\": 3, \"intuition\": 3, \"endurance\": 4}",
    "stat_points": 3,
    "zone": "tavern",
    "copper": 1000,
    "silver": 0,
    "gold": 0,
    "updated_at": 1704067200.0
  }
}
```

### Database Migration
Если работаете с существующей БД, нужно добавить колонку:
```sql
ALTER TABLE characters ADD COLUMN type TEXT NOT NULL DEFAULT 'warrior';
```

### Для Operator 2 (Разработка Mag системы)

Запомните основные точки расширения:

1. **Создание Mage боевой логики**: Текущая боевая система жестко привязана к warrior stats. Для магов нужно:
   - Создать адаптированную версию Fighter для магов
   - Реализовать систему заклинаний (spells)
   - Обрабатывать mana вместо some warrior механик

2. **Рекомендуемое расширение**:
   ```python
   # core/magic/fighter.py - новый файл
   class MageFighter(Fighter):
       # Адаптация для магов
       # Использование wisdom вместо strength
       # Использование spirituality для mana
   ```

3. **API endpoints для магов**:
   - Персонажи с type='mage' могут использовать магию
   - Нужно добавить endpoints для выбора элементов, заклинаний и т.д.

4. **Тестирование**:
   ```bash
   # Создать тестового мага и проверить его в базе
   python -c "
   from server.database import Database
   db = Database()
   user = db.register('testmage', 'password123')
   char = db.create_character(user['id'], 'TestMage', 'mage')
   print(char)
   "
   ```

### Известные ограничения
- Боевая система пока только для Warriors
- Маги могут быть созданы и сохранены, но боевая логика требует доработки
- UI на character_select_scene не показывает тип персонажа (можно добавить позже)

### Тестирование

#### Локальное тестирование:
```bash
cd E:\python\game
python main.py --online --username testuser --password testpass123 --server http://127.0.0.1:8765
```

1. Залогиньтесь
2. Попадете на экран списка персонажей
3. Нажмите кнопку создания (если пусто)
4. Увидите экран выбора профессии
5. Выберите Warrior или Mage
6. Введите имя и создайте персонажа
7. Персонаж отправится на таверну

### Контрольный список для OP2
- [ ] Прочитать этот документ
- [ ] Посмотреть ARCHITECTURE_DUAL_SYSTEM.md для понимания БД
- [ ] Посмотреть MAGE_DEVELOPER_GUIDE.md для полной спецификации
- [ ] Запустить игру и создать мага для проверки работы
- [ ] Проверить, что маг создается в БД с type='mage'
- [ ] Начать работу над Phase 1 (Mage class + core stats)
