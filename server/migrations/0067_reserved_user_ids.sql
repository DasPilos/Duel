-- Id пользователей 1-100 зарезервированы под персонал сервера: следующий новый игрок получит id 101 и выше.
SELECT setval(pg_get_serial_sequence('users', 'id'), GREATEST(100, (SELECT COALESCE(MAX(id), 0) FROM users)), true);
