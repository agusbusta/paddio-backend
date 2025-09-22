-- Limpiar todas las tablas excepto users
DROP TABLE IF EXISTS pregame_turns CASCADE;
DROP TABLE IF EXISTS turns CASCADE;
DROP TABLE IF EXISTS bookings CASCADE;
DROP TABLE IF EXISTS matches CASCADE;
DROP TABLE IF EXISTS courts CASCADE;
DROP TABLE IF EXISTS clubs CASCADE;
DROP TABLE IF EXISTS match_players CASCADE;
DROP TABLE IF EXISTS user_ratings CASCADE;

-- Verificar que solo queden users y alembic_version
\dt
