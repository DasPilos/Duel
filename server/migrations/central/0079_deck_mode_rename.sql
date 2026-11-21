DO $$
BEGIN
    IF to_regnamespace('kaloda') IS NOT NULL AND to_regnamespace('deck') IS NOT NULL THEN
        RAISE EXCEPTION 'Both legacy Kaloda and Deck schemas exist; refusing to choose a data source';
    ELSIF to_regnamespace('kaloda') IS NOT NULL THEN
        ALTER SCHEMA kaloda RENAME TO deck;
    END IF;

    IF to_regclass('public.worlds') IS NOT NULL THEN
        UPDATE public.worlds SET mode = 'deck' WHERE mode = 'kaloda';
        UPDATE public.worlds
        SET code = 'deck' || substring(code FROM length('kaloda') + 1)
        WHERE code LIKE 'kaloda%';
    END IF;

    IF to_regclass('deck.map_saved') IS NOT NULL THEN
        UPDATE deck.map_saved SET mode = 'deck' WHERE mode = 'kaloda';
        ALTER TABLE deck.map_saved ALTER COLUMN mode SET DEFAULT 'deck';
    END IF;

    IF to_regclass('deck.map_world_publish') IS NOT NULL THEN
        UPDATE deck.map_world_publish SET mode = 'deck' WHERE mode = 'kaloda';
        ALTER TABLE deck.map_world_publish ALTER COLUMN mode SET DEFAULT 'deck';
    END IF;
END;
$$;
