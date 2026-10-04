UPDATE drinks
SET price_copper = price_copper + price_silver * 100 + price_gold * 10000;

ALTER TABLE drinks DROP COLUMN price_silver;
ALTER TABLE drinks DROP COLUMN price_gold;