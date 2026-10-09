# Changelog

## 2026-10-09 — City production, farm progression, and transport

- Added PostgreSQL-backed city population, citizen hunger/rations, free-first worker
  selection, and server validation for occupied slots.
- Added Governor hourly resource income/expense and per-resource trend indicators.
- Production output from all workers now goes to shared building storage. Removed
  personal harvest shares; only unlocked resources appear or transfer.
- Farm level 1 has 500 storage. Samozakhvat adds one slot to field one; the +5%
  plough and Samozakhvat are required for level 2. Level 2 has 800 storage and a
  second field with two places. Level-two ration adds one place to field two; the
  wooden handle adds +8% wheat speed, stacking with the plough to +13%.
- Added persistent cart durability, 2 wood/hour maintenance during active routes,
  zero idle maintenance, broken-cart dispatch protection, wood-funded repairs, and
  a horizontal cart fleet view.
- Added city supply upgrades, battle archive/Hall of Fame, and migrations for city,
  transport, carts, farm progression, and shared production storage.
- Added integration and UI regression coverage. See
  [release notes](RELEASE_NOTES_2026-10-09.md) for the comparison baseline.

## 2026-09-05 — Карточный бой, повторный драфт и статусы

- Боевая колода теперь включает все доступные карты без временных лимитов по
  уровням.
- Добавлен полный цикл колоды и сброса: после опустошения колоды текущий размен
  завершается, затем на следующем ходу сброс перемешивается и запускается
  повторный драфт из шести карт.
- Начальный и повторный драфты используют приоритет Интуиции; дополнительная
  карта назначается по Ловкости.
- Размер руки ограничен шестью картами. Добор, драфт и бонусная карта не
  превышают этот предел.
- Добавлены мгновенные карты, активируемые двойным ЛКМ и занимающие одно из двух
  мест текущего размена.
- Формула карточного урона использует бросок карты и `Сила × 2`.
- Добавлены временные модификаторы характеристик, Уворота, Крита и лечения.
  Производные показатели, урон и приоритеты используют эффективные значения.
  Характеристики и шансы не опускаются ниже нуля.
- Колода и сброс постоянно отображаются на столе со счётчиками.
- Обновлён интерфейс карт: индивидуальные изображения лиц, стоимость шрифтом 21
  с белым свечением, название и описание в подсказке.
- Индикаторы очков уменьшены до 60×60 и привязаны к столу. Таймер хода заменён
  горизонтальной полосой без цифрового текста.
- Панели характеристик имеют постоянную ширину под шесть карт и показывают
  активные усиления и ослабления цветом.
- Добавлены регрессионные тесты колоды, драфта, лимита руки, мгновенных карт,
  формулы урона, временных эффектов и геометрии интерфейса.

## Актуальная версия

Сводка изменений относительно общей базовой ревизии репозитория и Z440 находится
в [release notes 2026-10-09](RELEASE_NOTES_2026-10-09.md). Актуальные инструкции
разработки, тестирования и деплоя — в `DEVELOPER_GUIDE.md`, `docs/testing.md` и
`DEPLOYMENT_CHECKLIST.md`.
