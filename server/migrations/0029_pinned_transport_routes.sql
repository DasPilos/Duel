ALTER TABLE transport_convoys
    ADD COLUMN pinned BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN resource_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN waiting_for_resources BOOLEAN NOT NULL DEFAULT FALSE,
    ADD CONSTRAINT transport_convoys_resource_ids_json_check
        CHECK (jsonb_typeof(resource_ids_json) = 'array');

UPDATE transport_convoys AS convoy
SET resource_ids_json = (
    SELECT COALESCE(jsonb_agg(resource_id), '[]'::jsonb)
    FROM (
        SELECT DISTINCT cargo_item->>'resource_id' AS resource_id
        FROM jsonb_array_elements(convoy.cargo_json) AS cargo_item
        WHERE cargo_item ? 'resource_id'
        ORDER BY resource_id
    ) AS resources
)
WHERE jsonb_array_length(convoy.cargo_json) > 0;

ALTER TABLE transport_convoys
    DROP CONSTRAINT transport_convoys_cargo_weight_kg_check,
    ADD CONSTRAINT transport_convoys_cargo_weight_kg_check
        CHECK (cargo_weight_kg >= 0);
