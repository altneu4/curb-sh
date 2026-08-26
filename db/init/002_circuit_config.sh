#!/bin/sh
# Runs as part of TimescaleDB's own first-boot init sequence (alongside
# 001_schema.sql) on a BRAND NEW database only -- Postgres only executes
# /docker-entrypoint-initdb.d on an empty data directory. If you're applying
# this to an already-running curb-selfhosted deployment, docs/NAS.md has the
# one-time manual migration command; this file won't run again for you.
#
# A .sh file here is only needed (instead of a plain .sql file like
# 001_schema.sql) because the portal role's password has to come from an
# environment variable rather than being hardcoded -- shell gives us that
# interpolation, plain SQL files don't.
set -e

: "${PORTAL_DB_PASSWORD:?PORTAL_DB_PASSWORD must be set (see .env.example)}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- One row per circuit ever seen, holding whether its display should be
    -- sign-flipped (a CT clamp wired backwards reports negative watts for
    -- real positive draw, permanently -- see docs/NAS.md). This table is
    -- the single source of truth the dashboards read from, and the small
    -- config-portal service is the only thing that writes to it.
    CREATE TABLE IF NOT EXISTS circuit_config (
        serial_number  TEXT NOT NULL,
        group_idx      SMALLINT NOT NULL,
        circuit_idx    SMALLINT NOT NULL,
        invert_display BOOLEAN NOT NULL DEFAULT false,
        first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (serial_number, group_idx, circuit_idx)
    );

    -- Auto-discovery: the first time a (serial_number, group_idx,
    -- circuit_idx) combination shows up in circuit_samples, add a row here
    -- with the default (uninverted) flag. ON CONFLICT DO NOTHING means this
    -- never overwrites a flag someone has already set via the portal -- it
    -- only ever adds rows for genuinely new circuits.
    CREATE OR REPLACE FUNCTION register_circuit_config() RETURNS TRIGGER AS \$\$
    BEGIN
        INSERT INTO circuit_config (serial_number, group_idx, circuit_idx)
        VALUES (NEW.serial_number, NEW.group_idx, NEW.circuit_idx)
        ON CONFLICT (serial_number, group_idx, circuit_idx) DO NOTHING;
        RETURN NEW;
    END;
    \$\$ LANGUAGE plpgsql;

    DROP TRIGGER IF EXISTS trg_register_circuit_config ON circuit_samples;
    CREATE TRIGGER trg_register_circuit_config
        AFTER INSERT ON circuit_samples
        FOR EACH ROW
        EXECUTE FUNCTION register_circuit_config();

    -- Backfill: harmless no-op on a genuinely brand-new database (no
    -- circuit_samples rows yet), but matters when this same block is run
    -- by hand against an existing deployment's database that already has
    -- data -- see docs/NAS.md.
    INSERT INTO circuit_config (serial_number, group_idx, circuit_idx)
    SELECT DISTINCT serial_number, group_idx, circuit_idx FROM circuit_samples
    ON CONFLICT (serial_number, group_idx, circuit_idx) DO NOTHING;

    -- Restricted role for the config-portal service: can see every circuit
    -- and flip invert_display, and that is *all* it can do. Enforced by
    -- Postgres itself via column-level GRANT, not by trusting the portal's
    -- own code to behave -- it has no privileges on circuit_samples,
    -- group_samples, devices, or diagnostics at all, and no INSERT/DELETE
    -- rights even on circuit_config.
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'circuit_portal') THEN
            CREATE ROLE circuit_portal LOGIN PASSWORD '${PORTAL_DB_PASSWORD}';
        ELSE
            ALTER ROLE circuit_portal LOGIN PASSWORD '${PORTAL_DB_PASSWORD}';
        END IF;
    END
    \$\$;

    GRANT CONNECT ON DATABASE "$POSTGRES_DB" TO circuit_portal;
    GRANT SELECT ON circuit_config TO circuit_portal;
    GRANT UPDATE (invert_display) ON circuit_config TO circuit_portal;
EOSQL
