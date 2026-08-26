-- Optional friendly name for a circuit (e.g. "Kitchen", "Garage Sub-Panel"),
-- shown on the dashboards in place of "Group X Circuit Y" wherever a label
-- has been set -- see grafana/dashboards/*.json's
-- COALESCE(cc.label, concat('G', ...)) fallbacks, and config-portal/app.py,
-- which is where this gets set. A plain .sql file (unlike
-- 002_circuit_config.sh) because nothing here needs a secret substituted in.
ALTER TABLE circuit_config ADD COLUMN IF NOT EXISTS label TEXT;

-- Extend the config-portal's restricted role to also write this one
-- additional column -- still nothing beyond SELECT on the whole table and
-- UPDATE on these two specific columns (invert_display, label).
GRANT UPDATE (label) ON circuit_config TO circuit_portal;
