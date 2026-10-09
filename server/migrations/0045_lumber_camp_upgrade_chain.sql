ALTER TABLE building_states
    ADD COLUMN lumber_camp_upgrades_json JSONB NOT NULL
        DEFAULT '{"bonus_plots": [], "strong_handle": false}'::jsonb,
    ADD COLUMN lumber_camp_upgrade_id TEXT,
    ADD COLUMN lumber_camp_upgrade_plot_index INTEGER,
    ADD COLUMN lumber_camp_upgrade_finish_at DOUBLE PRECISION;