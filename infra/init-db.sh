#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=runtime_password="$ADRIVA_RUNTIME_PASSWORD" <<'SQL'
CREATE ROLE adriva LOGIN PASSWORD :'runtime_password';
GRANT CONNECT ON DATABASE adriva TO adriva;
GRANT USAGE ON SCHEMA public TO adriva;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO adriva;
SQL
