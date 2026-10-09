ALTER TABLE building_states
    ADD COLUMN farm_upgrades_json JSONB NOT NULL
        DEFAULT '{"ration_plots": [], "wooden_plough": false}'::jsonb,
    ADD COLUMN farm_upgrade_id TEXT,
    ADD COLUMN farm_upgrade_plot_index INTEGER,
    ADD COLUMN farm_upgrade_finish_at DOUBLE PRECISION;