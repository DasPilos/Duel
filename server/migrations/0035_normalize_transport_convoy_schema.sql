DO $migration$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema=current_schema() AND table_name='transport_convoys'
          AND column_name='cargo_json'
    ) THEN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema=current_schema() AND table_name='transport_convoys'
              AND column_name='resource_id'
        ) AND EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema=current_schema() AND table_name='transport_convoys'
              AND column_name='cargo_quantity'
        ) THEN
            ALTER TABLE transport_convoys ADD COLUMN cargo_json JSONB;
            UPDATE transport_convoys
            SET cargo_json = CASE
                WHEN resource_id IS NULL OR cargo_quantity <= 0 THEN '[]'::jsonb
                ELSE jsonb_build_array(jsonb_build_object(
                    'resource_id', resource_id,
                    'quantity', cargo_quantity,
                    'unit_weight_kg', cargo_weight_kg / cargo_quantity
                ))
            END;
        ELSE
            RAISE EXCEPTION 'Cannot normalize transport_convoys: legacy cargo columns are missing';
        END IF;
    END IF;

    UPDATE transport_convoys SET cargo_json='[]'::jsonb WHERE cargo_json IS NULL;
    ALTER TABLE transport_convoys ALTER COLUMN cargo_json SET DEFAULT '[]'::jsonb;
    ALTER TABLE transport_convoys ALTER COLUMN cargo_json SET NOT NULL;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='transport_convoys'::regclass
          AND conname='transport_convoys_cargo_json_check'
    ) THEN
        ALTER TABLE transport_convoys
            ADD CONSTRAINT transport_convoys_cargo_json_check
            CHECK (jsonb_typeof(cargo_json)='array');
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema=current_schema() AND table_name='transport_convoys'
          AND column_name='cargo_quantity'
    ) THEN
        ALTER TABLE transport_convoys DROP COLUMN cargo_quantity;
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema=current_schema() AND table_name='transport_convoys'
          AND column_name='resource_id'
    ) THEN
        ALTER TABLE transport_convoys DROP COLUMN resource_id;
    END IF;
END
$migration$;

ALTER TABLE transport_convoys DROP CONSTRAINT IF EXISTS transport_convoys_status_check;
ALTER TABLE transport_convoys
    ADD CONSTRAINT transport_convoys_status_check
    CHECK (status IN ('outbound','blocked','arrived'));

DROP INDEX IF EXISTS transport_convoys_active_cart;
DROP INDEX IF EXISTS transport_convoys_active_driver;
CREATE UNIQUE INDEX transport_convoys_active_cart
    ON transport_convoys (world_id,faction,cart_id)
    WHERE status IN ('outbound','blocked');
CREATE UNIQUE INDEX transport_convoys_active_driver
    ON transport_convoys (world_id,faction,driver_citizen_id)
    WHERE status IN ('outbound','blocked');