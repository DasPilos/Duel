ALTER TABLE map_live_cells DROP CONSTRAINT map_live_cells_layer_check;
ALTER TABLE map_live_cells ADD CONSTRAINT map_live_cells_layer_check CHECK (layer IN ('ground', 'overlay', 'object'));
