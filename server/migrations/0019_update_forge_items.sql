UPDATE items_catalog SET
    description = 'Требование: Сила: 6. HP +20',
    effects_json = '{"requirements":{"strength":6},"damage":[3,10]}',
    bonuses_json = '{"hp":20}',
    price = 500,
    weight = 5.0
WHERE id = 23;

UPDATE items_catalog SET
    description = 'Требование: Ловкость: 6. Сила +2. Уворот: +5%',
    effects_json = '{"requirements":{"agility":6},"damage":[4,8],"dodge":5}',
    bonuses_json = '{"strength":2,"dodge":5}',
    price = 400,
    weight = 1.0
WHERE id = 24;

UPDATE items_catalog SET
    description = 'Требование: Ловкость: 6, Интеллект: 4. MP +30',
    effects_json = '{"requirements":{"agility":6,"intellect":4},"damage":[1,4]}',
    bonuses_json = '{"mp":30}',
    price = 500,
    weight = 2.0
WHERE id = 25;
