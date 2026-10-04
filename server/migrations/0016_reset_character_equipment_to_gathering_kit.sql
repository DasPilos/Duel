INSERT INTO items_catalog
    (id, name, item_type, rarity, weight, price, description, can_use, effects_json,
     bonuses_json, icon, created_at, equip_slot)
VALUES
    (90, 'Старый серп', 'equipment', 'common', 1.0, 100,
     'Сила: 4. Увеличивает добычу пшеницы на 20%', 0,
     '{"requirements":{"strength":4},"harvest_bonus":{"wheat":20}}', NULL,
     'tool_sickle', EXTRACT(EPOCH FROM clock_timestamp()), 'weapon'),
    (91, 'Топор лесоруба', 'equipment', 'common', 1.0, 100,
     'Сила: 4. Увеличивает добычу древесины на 20%', 0,
     '{"requirements":{"strength":4},"harvest_bonus":{"wood":20}}', NULL,
     'tool_axe', EXTRACT(EPOCH FROM clock_timestamp()), 'weapon'),
    (92, 'Кирка', 'equipment', 'common', 1.0, 100,
     'Сила: 4. Увеличивает добычу железной руды, угля и камня на 20%', 0,
     '{"requirements":{"strength":4},"harvest_bonus":{"iron_ore":20,"coal":20,"stone":20}}', NULL,
     'tool_pickaxe', EXTRACT(EPOCH FROM clock_timestamp()), 'weapon'),
    (93, 'Разделочный нож', 'equipment', 'common', 1.0, 100,
     'Сила: 4. Увеличивает добычу кожи и мяса на 20%', 0,
     '{"requirements":{"strength":4},"harvest_bonus":{"leather":20,"meat":20}}', NULL,
     'tool_butcher_knife', EXTRACT(EPOCH FROM clock_timestamp()), 'weapon')
ON CONFLICT (id) DO NOTHING;

DELETE FROM character_equipment;

DELETE FROM character_items AS inventory
USING items_catalog AS catalog
WHERE inventory.item_id = catalog.id
  AND catalog.item_type = 'equipment';

WITH free_slots AS (
    SELECT characters.id AS character_id,
           slots.slot_index,
           ROW_NUMBER() OVER (PARTITION BY characters.id ORDER BY slots.slot_index) AS kit_order
    FROM characters
    CROSS JOIN generate_series(0, 49) AS slots(slot_index)
    WHERE NOT EXISTS (
        SELECT 1 FROM character_items
        WHERE character_items.character_id = characters.id
          AND character_items.slot_index = slots.slot_index
    )
), kit AS (
    SELECT * FROM (VALUES (1, 90), (2, 91), (3, 92), (4, 93)) AS items(kit_order, item_id)
)
INSERT INTO character_items (character_id, item_id, quantity, slot_index, created_at)
SELECT free_slots.character_id, kit.item_id, 1, free_slots.slot_index,
       EXTRACT(EPOCH FROM clock_timestamp())
FROM free_slots
JOIN kit ON kit.kit_order = free_slots.kit_order;

INSERT INTO character_item_grants (character_id, starter_kit_at)
SELECT characters.id, EXTRACT(EPOCH FROM clock_timestamp())
FROM characters
WHERE (
    SELECT COUNT(DISTINCT character_items.item_id)
    FROM character_items
    WHERE character_items.character_id = characters.id
      AND character_items.item_id IN (90, 91, 92, 93)
) = 4
ON CONFLICT (character_id) DO UPDATE
SET starter_kit_at = EXCLUDED.starter_kit_at;