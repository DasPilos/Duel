ALTER TABLE building_states
    ALTER COLUMN farm_upgrades_json SET DEFAULT
        '{"ration_plots": [], "wooden_plough": false, "wooden_handle": false}'::jsonb;

UPDATE building_states
SET farm_upgrades_json = farm_upgrades_json || '{"wooden_handle": false}'::jsonb
WHERE building = 'farm' AND NOT (farm_upgrades_json ? 'wooden_handle');