#!/usr/bin/env bash
# M-8: 建立最小權限應用程式使用者，取代 postgres superuser 直接連線。
# Docker entrypoint 在 container 首次啟動時自動執行此 script。
# 注意：更改此 script 需先 `docker compose down -v` 清除舊 volume 才會重新執行。
set -euo pipefail

APP_USER="${APP_DB_USER:-app_user}"
APP_PASS="${APP_DB_PASSWORD:-changeme_in_production}"

psql -v ON_ERROR_STOP=1 \
     --username "$POSTGRES_USER" \
     --dbname "$POSTGRES_DB" \
     --set APP_USER="$APP_USER" \
     --set APP_PASS="$APP_PASS" \
     --set DBNAME="$POSTGRES_DB" <<'SQL'

DO $$
DECLARE
  v_user text := :'APP_USER';
  v_pass text := :'APP_PASS';
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = v_user) THEN
    EXECUTE format('CREATE USER %I WITH PASSWORD %L', v_user, v_pass);
  END IF;
END
$$;

GRANT ALL PRIVILEGES ON DATABASE :"DBNAME" TO :"APP_USER";
GRANT ALL ON SCHEMA public TO :"APP_USER";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO :"APP_USER";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO :"APP_USER";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO :"APP_USER";

DO $$
DECLARE
  v_user text := :'APP_USER';
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'postgis') THEN
    EXECUTE format('GRANT USAGE ON SCHEMA postgis TO %I', v_user);
  END IF;
END
$$;

SQL
