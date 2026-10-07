ALTER TABLE transport_convoys
    ADD COLUMN phase TEXT NOT NULL DEFAULT 'outbound'
        CHECK (phase IN (
            'outbound', 'loading', 'returning', 'unloading', 'resting',
            'waiting_for_resources', 'complete'
        ));

UPDATE transport_convoys
SET phase = 'waiting_for_resources'
WHERE waiting_for_resources = TRUE
  AND status IN ('outbound', 'blocked');
