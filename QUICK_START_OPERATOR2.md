# ⚡ Quick Start для Operator 2

## За 5 минут в проект

### 1️⃣ Клонировать (1 минута)
```bash
git clone https://github.com/DasPilos/Duel.git
cd Duel
```

### 2️⃣ Установить зависимости (2 минуты)
```bash
pip install pygame
```

### 3️⃣ Настроить Git (первый раз)
```bash
git config --global user.name "Твое Имя"
git config --global user.email "твой_email@example.com"
```

### 4️⃣ Создать свою ветку
```bash
git checkout -b feature/mage-system
```

### 5️⃣ Запустить и проверить (2 минуты)

**Терминал 1 - Сервер:**
```bash
python -m server.main
```

**Терминал 2 - Клиент:**
```bash
python main.py --online
```

---

## 📚 Что прочитать (обязательно!)

1. **`OPERATOR2_GUIDE.md`** - Архитектура проекта и правила
2. **`OPERATOR2_SETUP_GUIDE.md`** - Полная инструкция (этот файл)
3. **`README.md`** - Общая информация

---

## 🎯 Первое задание

Создать экран школы магии (Academy):

1. Скопировать `scenes/tavern_scene.py` в `scenes/academy/academy_scene.py`
2. Переименовать класс `TavernScene` в `AcademyScene`
3. Адаптировать для магов
4. Сделать коммит

---

## 🚀 Готово!

Теперь можно начать писать код для системы магии! 

**Вопросы?** Читай `OPERATOR2_GUIDE.md` или создай Issue на GitHub.
