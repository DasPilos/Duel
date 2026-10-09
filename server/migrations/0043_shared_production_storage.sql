UPDATE building_player_resources
SET claimable = 0, buffered = 0
WHERE claimable <> 0 OR buffered <> 0;