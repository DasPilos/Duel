DO $migration$
DECLARE
    stack RECORD;
    remaining_quantity INTEGER;
    stack_quantity INTEGER;
    inventory_slot INTEGER;
    storage_slot INTEGER;
BEGIN
    FOR stack IN
        SELECT id, character_id, item_id, quantity, created_at
        FROM character_items
        WHERE item_id = 60 AND quantity > 10
        ORDER BY character_id, id
        FOR UPDATE
    LOOP
        remaining_quantity := stack.quantity - 10;
        UPDATE character_items SET quantity = 10 WHERE id = stack.id;

        WHILE remaining_quantity > 0 LOOP
            stack_quantity := LEAST(10, remaining_quantity);
            inventory_slot := NULL;
            SELECT slots.slot_index INTO inventory_slot
            FROM generate_series(0, 49) AS slots(slot_index)
            WHERE NOT EXISTS (
                SELECT 1 FROM character_items
                WHERE character_id = stack.character_id
                  AND slot_index = slots.slot_index
            )
            ORDER BY slots.slot_index
            LIMIT 1;

            IF inventory_slot IS NOT NULL THEN
                INSERT INTO character_items (character_id, item_id, quantity, slot_index, created_at)
                VALUES (stack.character_id, stack.item_id, stack_quantity, inventory_slot, stack.created_at);
            ELSE
                storage_slot := NULL;
                SELECT slots.slot_index INTO storage_slot
                FROM generate_series(0, 99) AS slots(slot_index)
                WHERE NOT EXISTS (
                    SELECT 1 FROM character_storage
                    WHERE character_id = stack.character_id
                      AND storage_type = 'chest1'
                      AND slot_index = slots.slot_index
                )
                ORDER BY slots.slot_index
                LIMIT 1;

                IF storage_slot IS NULL THEN
                    RAISE EXCEPTION 'No free inventory or chest slot for wood stack on character %', stack.character_id;
                END IF;

                INSERT INTO character_storage
                    (character_id, storage_type, item_id, quantity, slot_index, created_at)
                VALUES
                    (stack.character_id, 'chest1', stack.item_id, stack_quantity,
                     storage_slot, stack.created_at);
            END IF;

            remaining_quantity := remaining_quantity - stack_quantity;
        END LOOP;
    END LOOP;
END
$migration$;