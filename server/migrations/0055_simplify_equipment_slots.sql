CREATE TEMP TABLE equipment_slot_candidates ON COMMIT DROP AS
SELECT id, character_id, item_id, equipped_at,
       CASE
         WHEN slot IN ('hands', 'head', 'body', 'legs', 'feet', 'artifact') THEN slot
         WHEN slot IN ('weapon', 'shield') THEN 'hands'
         ELSE NULL
       END AS target_slot,
       CASE
         WHEN slot IN ('hands', 'head', 'body', 'legs', 'feet', 'artifact') THEN 0
         WHEN slot = 'weapon' THEN 1
         WHEN slot = 'shield' THEN 2
         ELSE 3
       END AS priority
FROM character_equipment
WHERE item_id NOT IN (90, 91, 92, 93);

CREATE TEMP TABLE equipment_slot_keeps ON COMMIT DROP AS
SELECT id, character_id, item_id, target_slot, equipped_at
FROM (
    SELECT candidates.*,
           ROW_NUMBER() OVER (
               PARTITION BY character_id, target_slot
               ORDER BY priority, equipped_at, id
           ) AS slot_rank
    FROM equipment_slot_candidates AS candidates
    WHERE target_slot IS NOT NULL
) AS ranked
WHERE slot_rank = 1;

CREATE TEMP TABLE equipment_slot_returns ON COMMIT DROP AS
SELECT equipment.character_id, equipment.item_id, equipment.equipped_at
FROM character_equipment AS equipment
LEFT JOIN equipment_slot_keeps AS kept ON kept.id = equipment.id
WHERE equipment.item_id NOT IN (90, 91, 92, 93)
  AND kept.id IS NULL;

DO $migration$
BEGIN
    IF EXISTS (
        SELECT returns.character_id
        FROM equipment_slot_returns AS returns
        GROUP BY returns.character_id
        HAVING COUNT(*) > (
            SELECT COUNT(*)
            FROM generate_series(0, 49) AS slots(slot_index)
            WHERE NOT EXISTS (
                SELECT 1
                FROM character_items AS inventory
                WHERE inventory.character_id = returns.character_id
                  AND inventory.slot_index = slots.slot_index
                  AND inventory.item_id NOT IN (90, 91, 92, 93)
            )
        )
    ) THEN
        RAISE EXCEPTION 'Невозможно перенести экипировку в рюкзак: освободите место перед обновлением';
    END IF;
END
$migration$;

DELETE FROM character_items WHERE item_id IN (90, 91, 92, 93);
DELETE FROM character_equipment;

INSERT INTO character_equipment (character_id, slot, item_id, equipped_at)
SELECT character_id, target_slot, item_id, equipped_at
FROM equipment_slot_keeps;

WITH free_slots AS (
    SELECT characters.id AS character_id, slots.slot_index,
           ROW_NUMBER() OVER (
               PARTITION BY characters.id ORDER BY slots.slot_index
           ) AS slot_rank
    FROM characters
    CROSS JOIN generate_series(0, 49) AS slots(slot_index)
    WHERE NOT EXISTS (
        SELECT 1
        FROM character_items AS inventory
        WHERE inventory.character_id = characters.id
          AND inventory.slot_index = slots.slot_index
    )
), returned_items AS (
    SELECT character_id, item_id,
           ROW_NUMBER() OVER (
               PARTITION BY character_id ORDER BY equipped_at, item_id
           ) AS item_rank
    FROM equipment_slot_returns
)
INSERT INTO character_items (character_id, item_id, quantity, slot_index, created_at)
SELECT returned_items.character_id, returned_items.item_id, 1,
       free_slots.slot_index, EXTRACT(EPOCH FROM clock_timestamp())
FROM returned_items
JOIN free_slots
  ON free_slots.character_id = returned_items.character_id
 AND free_slots.slot_rank = returned_items.item_rank;
