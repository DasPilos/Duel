-- Run as superuser: psql -U postgres -h 127.0.0.1 -f deploy/postgres/create_database.sql
\set ON_ERROR_STOP on

CREATE ROLE game LOGIN;
\echo 'Enter a new password for database user "game":'
\password game

-- Builtin C.UTF-8 makes sorting and case rules identical on Windows and Linux.
CREATE DATABASE game
    OWNER game
    TEMPLATE template0
    ENCODING 'UTF8'
    LOCALE 'C'
    LOCALE_PROVIDER builtin
    BUILTIN_LOCALE 'C.UTF-8';

\connect game
SELECT current_database() AS database,
       pg_encoding_to_char(encoding) AS encoding,
       datlocprovider AS provider,
       datlocale AS locale
FROM pg_database
WHERE datname = current_database();
