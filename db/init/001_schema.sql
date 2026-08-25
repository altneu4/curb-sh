-- curb-selfhosted schema
--
-- Mirrors the real Curb sample JSON shape (documented in curbed's
-- docs/FINDINGS.md and PROTOCOL.md in this repo):
--   { t: unix_ts, p: period_secs, g: [ { t: kva, f: hz, tg: kw, v: volts,
--     ts: kw_sum, c: [ { i: amps, w: kwh, var: kvarh, p: power_factor }, ... ] },
--   ... ] }
--
-- "g" (group) = one leg of the split-phase panel. "c" (circuit) = one clamp
-- within that group. Flattened here into two hypertables -- one per-circuit,
-- one per-group -- rather than kept as nested JSON, so Grafana can query
-- them with plain SQL/aggregates instead of JSON path expressions.

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS devices (
    serial_number       TEXT PRIMARY KEY,
    hub_id               TEXT,
    model_number          TEXT,
    hardware_version      TEXT,
    software_version      TEXT,
    -- Basic Auth "secret" the device sends alongside its serial number.
    -- Stored only so you can notice if it ever changes; the real firmware
    -- doesn't validate it server-side either, so treat this as an identity
    -- hint, not an access control.
    last_secret           TEXT,
    first_seen_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at           TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS circuit_samples (
    time            TIMESTAMPTZ NOT NULL,
    serial_number   TEXT NOT NULL REFERENCES devices(serial_number),
    group_idx       SMALLINT NOT NULL,
    circuit_idx     SMALLINT NOT NULL,
    current_a       DOUBLE PRECISION,
    watts           DOUBLE PRECISION,
    var             DOUBLE PRECISION,
    power_factor    DOUBLE PRECISION
);

SELECT create_hypertable('circuit_samples', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS circuit_samples_serial_time_idx
    ON circuit_samples (serial_number, time DESC);

CREATE TABLE IF NOT EXISTS group_samples (
    time                    TIMESTAMPTZ NOT NULL,
    serial_number           TEXT NOT NULL REFERENCES devices(serial_number),
    group_idx               SMALLINT NOT NULL,
    period_secs             INT,
    apparent_power_kva      DOUBLE PRECISION,
    true_power_kw           DOUBLE PRECISION,
    true_power_sum_kw       DOUBLE PRECISION,
    voltage                 DOUBLE PRECISION,
    frequency               DOUBLE PRECISION
);

SELECT create_hypertable('group_samples', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS group_samples_serial_time_idx
    ON group_samples (serial_number, time DESC);

CREATE TABLE IF NOT EXISTS diagnostics (
    time                TIMESTAMPTZ NOT NULL,
    serial_number       TEXT NOT NULL REFERENCES devices(serial_number),
    hardware_version    TEXT,
    software_version    TEXT,
    os_version          TEXT,
    plc_connection      DOUBLE PRECISION
);

SELECT create_hypertable('diagnostics', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS diagnostics_serial_time_idx
    ON diagnostics (serial_number, time DESC);
