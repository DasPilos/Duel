DO $migration$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = current_schema() AND table_name = 'transport_convoys'
      AND column_name = 'cargo_json'
  ) THEN
    EXECUTE $backfill$
      UPDATE transport_convoys
      SET resource_ids_json = jsonb_path_query_array(cargo_json, '$[*].resource_id')
      WHERE jsonb_typeof(cargo_json) = 'array'
        AND jsonb_array_length(cargo_json) > 0
        AND jsonb_array_length(resource_ids_json) = 0
    $backfill$;
  ELSIF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = current_schema() AND table_name = 'transport_convoys'
      AND column_name = 'resource_id'
  ) THEN
    EXECUTE $backfill$
      UPDATE transport_convoys
      SET resource_ids_json = jsonb_build_array(resource_id)
      WHERE resource_id IS NOT NULL AND jsonb_array_length(resource_ids_json) = 0
    $backfill$;
  END IF;
END
$migration$;
