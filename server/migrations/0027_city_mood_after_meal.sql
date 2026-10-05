UPDATE city_citizens
SET satisfaction = 'satisfied', hunger_streak = 0
WHERE satiety >= 100 AND satisfaction <> 'satisfied';