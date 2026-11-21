-- Колонка редакторских слоёв карты для центральной базы: корневая 0079_saved_map_editor_layers после 0078
-- не применялась к центру. IF NOT EXISTS делает повтор безопасным.
ALTER TABLE map_saved ADD COLUMN IF NOT EXISTS editor_layers_json TEXT NOT NULL DEFAULT '[]';
