DO $$
DECLARE
    source_schema TEXT := current_schema();
    tower_schema TEXT := 'tower';
    economy_schema TEXT := 'economy';
    row_data RECORD;
    definition TEXT;
    parent_schema TEXT;
    sequence_name TEXT;
BEGIN
    IF source_schema <> 'public' THEN
        RETURN;
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.worlds
        WHERE code <> 'lobby' AND mode <> 'tower'
    ) THEN
        RAISE EXCEPTION 'Mode schemas cannot be created while non-Tower worlds remain in the shared schema';
    END IF;

    IF to_regnamespace(tower_schema) IS NOT NULL OR to_regnamespace(economy_schema) IS NOT NULL THEN
        RAISE EXCEPTION 'Mode schema already exists; refusing to move shared game tables again';
    END IF;

    CREATE SCHEMA tower;
    CREATE SCHEMA economy;

    FOR row_data IN
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = source_schema
          AND tablename NOT IN (
              'users', 'worlds', 'sessions', 'schema_migrations',
              'map_catalog', 'map_palette_settings', 'map_saved',
              'map_live_cells', 'map_live_mobs', 'map_live_spawns', 'map_world_publish'
          )
        ORDER BY tablename
    LOOP
        EXECUTE format('ALTER TABLE %I.%I SET SCHEMA %I', source_schema, row_data.tablename, tower_schema);
    END LOOP;

    CREATE TABLE tower.schema_migrations (LIKE public.schema_migrations INCLUDING ALL);
    INSERT INTO tower.schema_migrations SELECT * FROM public.schema_migrations;

    FOR row_data IN
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = tower_schema
          AND tablename <> 'schema_migrations'
        ORDER BY tablename
    LOOP
        EXECUTE format('CREATE TABLE economy.%I (LIKE tower.%I INCLUDING ALL)', row_data.tablename, row_data.tablename);
    END LOOP;

    CREATE TABLE economy.schema_migrations (LIKE tower.schema_migrations INCLUDING ALL);

    FOR row_data IN
        SELECT child.relname AS child_table, constraint_row.oid AS constraint_oid, constraint_row.conname,
               constraint_row.confrelid,
               parent_ns.nspname AS referenced_schema,
               parent.relname AS referenced_table
        FROM pg_constraint constraint_row
        JOIN pg_class child ON child.oid = constraint_row.conrelid
        JOIN pg_namespace child_ns ON child_ns.oid = child.relnamespace
        JOIN pg_class parent ON parent.oid = constraint_row.confrelid
        JOIN pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace
        WHERE constraint_row.contype = 'f' AND child_ns.nspname = tower_schema
        ORDER BY child.relname, constraint_row.conname
    LOOP
        definition := pg_get_constraintdef(row_data.constraint_oid, true);
        parent_schema := CASE
            WHEN row_data.referenced_schema = tower_schema THEN economy_schema
            ELSE row_data.referenced_schema
        END;
        definition := regexp_replace(
            definition,
            'REFERENCES [^ (]+',
            format('REFERENCES %I.%I', parent_schema, row_data.referenced_table),
            ''
        );
        EXECUTE format(
            'ALTER TABLE economy.%I ADD CONSTRAINT %I %s',
            row_data.child_table, row_data.conname, definition
        );
    END LOOP;

    FOR row_data IN
        SELECT trigger_row.tgname, table_row.relname AS table_name,
               pg_get_triggerdef(trigger_row.oid, true) AS trigger_definition
        FROM pg_trigger trigger_row
        JOIN pg_class table_row ON table_row.oid = trigger_row.tgrelid
        JOIN pg_namespace table_ns ON table_ns.oid = table_row.relnamespace
        WHERE table_ns.nspname = tower_schema AND NOT trigger_row.tgisinternal
        ORDER BY table_row.relname, trigger_row.tgname
    LOOP
        definition := regexp_replace(
            row_data.trigger_definition,
            ' ON [^ ]+ ',
            format(' ON economy.%I ', row_data.table_name),
            ''
        );
        EXECUTE definition;
    END LOOP;

    FOR row_data IN
        SELECT table_row.relname AS table_name, attribute_row.attname AS column_name,
               pg_get_expr(default_row.adbin, default_row.adrelid) AS default_expression,
               pg_get_serial_sequence(format('%I.%I', tower_schema, table_row.relname), attribute_row.attname) AS source_sequence
        FROM pg_class table_row
        JOIN pg_namespace table_ns ON table_ns.oid = table_row.relnamespace
        JOIN pg_attribute attribute_row ON attribute_row.attrelid = table_row.oid
        JOIN pg_attrdef default_row ON default_row.adrelid = table_row.oid AND default_row.adnum = attribute_row.attnum
        WHERE table_ns.nspname = tower_schema AND table_row.relkind = 'r'
          AND attribute_row.attnum > 0 AND NOT attribute_row.attisdropped
          AND pg_get_expr(default_row.adbin, default_row.adrelid) LIKE 'nextval(%'
        ORDER BY table_row.relname, attribute_row.attnum
    LOOP
        sequence_name := split_part(row_data.source_sequence, '.', 2);
        sequence_name := replace(sequence_name, '"', '');
        EXECUTE format('CREATE SEQUENCE economy.%I', sequence_name);
        EXECUTE format(
            'ALTER TABLE economy.%I ALTER COLUMN %I SET DEFAULT nextval(%L::regclass)',
            row_data.table_name, row_data.column_name, format('%I.%I', economy_schema, sequence_name)
        );
        EXECUTE format(
            'ALTER SEQUENCE economy.%I OWNED BY economy.%I.%I',
            sequence_name, row_data.table_name, row_data.column_name
        );
    END LOOP;

    INSERT INTO economy.schema_migrations SELECT * FROM tower.schema_migrations;
    INSERT INTO economy.items_catalog SELECT * FROM tower.items_catalog;
    INSERT INTO economy.drinks SELECT * FROM tower.drinks;
END;
$$;
