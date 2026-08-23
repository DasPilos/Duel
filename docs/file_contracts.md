markdown
 Copy code

# Контракты файлов

## `main.py`

### Контракт

Запускает приложение и главный цикл Pygame.

### Импорты

- `pygame`;
- `scenes.duel_scene.DuelScene`.

### Публичная функция

#### `main()`

Инициализирует Pygame, создаёт окно, запускает цикл и завершает Pygame после выхода.

---

## `combat/fighter.py`

## Класс `Fighter`

### Конструктор

ython
Fighter(name, level=1)


 Copy code


Создаёт бойца с указанным именем и уровнем.

### Поля

- `name`;
- `level`;
- `max_hp`;
- `hp`;
- `max_mp`;
- `mp`;
- `attack`;
- `defense`;
- `xp`.

### Методы

#### `is_dead()`

Возвращает `True`, если HP меньше или равно нулю.

#### `take_damage(amount)`

Уменьшает HP, но не позволяет ему стать отрицательным.

#### `gain_xp(amount)`

Добавляет указанное количество XP.

#### `try_level_up()`

Повышает уровень при наличии минимум `60 XP`.

Возвращает `True`, если уровень был повышен, иначе `False`.

---

## `combat/zones.py`

### `ZONES`

Словарь допустимых зон атаки и защиты.

Ключи этого словаря используются для валидации выбора в `Battle`.

---

## `combat/battle.py`

## Класс `Battle`

### Конструктор

ython
Battle(player, enemy)


 Copy code


Принимает два объекта `Fighter`.

### Поля

- `player`;
- `enemy`;
- `turn`;
- `player_attack_zone`;
- `player_defense_zones`;
- `history`;
- `last_player_attack`;
- `last_player_hit`;
- `last_player_damage`;
- `last_enemy_attack`;
- `last_enemy_hit`;
- `last_enemy_damage`.

### Методы

#### `is_over()`

Возвращает `True`, если погиб игрок или противник.

#### `choose_player_zones(attack_zone, defense_zones)`

Проверяет выбор игрока.

Ошибки:

- неизвестная зона атаки;
- количество зон защиты не равно двум;
- неизвестная зона защиты;
- повторяющиеся зоны защиты.

#### `enemy_choose_zones()`

Возвращает случайные зону атаки и две зоны защиты противника.

#### `calc_damage(attacker, defender, defender_is_defending=False)`

Рассчитывает урон с учётом атаки, защиты и блокировки.

#### `resolve_turn()`

Рассчитывает и применяет один ход.

Если бой завершён или зона атаки не выбрана, метод ничего не делает.

---

## `combat/comments.py`

### Контракт

Хранит готовые тексты комментариев.

- `ATTACK_COMMENTS` индексируется зоной атаки и результатом попадания.
- `DEFENSE_COMMENTS` индексируется результатом защиты.

Логика выбора комментариев находится в `DuelScene`.

---

## `scenes/duel_scene.py`

## Класс `DuelScene`

### Конструктор

Создаёт бойцов, `Battle`, шрифты, кнопки, комментарии и `DuelRenderer`.

### Основные поля

- `player`;
- `enemy`;
- `battle`;
- `phase`;
- `attack_zone`;
- `defense_zones`;
- `comments`;
- `ui_logs`;
- `active_floating_texts`;
- `renderer`.

### Методы

#### `restart()`

Начинает новый бой, сохраняя текущий уровень игрока.

#### `handle_event(event)`

Обрабатывает:

- выбор зон мышью;
- подтверждение хода;
- кнопку нового боя;
- клавишу `R`.

#### `update(dt)`

Обновляет временные подфазы `resolve`.

#### `calculate_turn()`

Однократно запускает расчёт хода и создаёт:

- запись UI-лога;
- всплывающий урон.

#### `get_random_comment(key, options)`

Выбирает случайный комментарий, по возможности не повторяя предыдущий.

#### `add_combat_comments()`

Добавляет комментарии о результате атаки и защиты.

#### `draw(screen)`

Передаёт отрисовку объекту `DuelRenderer`.

---

## `ui/duel_renderer.py`

## Класс `DuelRenderer`

### Конструктор

ython
DuelRenderer(scene)


 Copy code


Получает объект сцены для чтения её состояния.

### Методы

- `draw(screen)` — рисует весь экран;
- `draw_header(screen)` — рисует заголовок;
- `draw_fighter_panel(...)` — рисует панель бойца;
- `draw_choice_area(screen)` — рисует выбор зон;
- `draw_resolve_overlay(screen)` — рисует экран расчёта;
- `draw_logs(screen)` — рисует журнал действий;
- `draw_comments(screen)` — рисует комментарии.

Модуль не изменяет правила боя.

---

## `ui/hud.py`

### Функции

- `draw_text(...)` — рисует текст;
- `draw_bar(...)` — рисует полосу значения;
- `draw_button(...)` — рисует кнопку и возвращает состояние наведения;
- `draw_silhouette(...)` — рисует силуэт;
- `update_and_draw_floating_texts(...)` — обновляет и рисует всплывающие тексты.

## Класс `FloatingText`

Показывает текст, движущийся вверх и постепенно исчезающий.

Методы:

- `update()` — изменяет позицию и длительность;
- `draw(screen)` — рисует текст.

---

## Правила зависимостей

- `combat` не импортирует Pygame.
- `combat` не зависит от `ui`.
- `ui` использует Pygame.
- `DuelScene` может использовать и `combat`, и `ui`.
- `main.py` создаёт сцену и управляет главным циклом.
- `Battle` не должен заниматься кнопками, шрифтами или отрисовкой.