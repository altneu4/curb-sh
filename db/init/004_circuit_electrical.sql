-- Circuit electrical properties set manually via the config-portal (not
-- knowable from the sample stream itself):
--
-- breaker_amps -- the breaker's rated amperage, used to compute a "% of
-- breaker capacity" panel on Curb Circuit Detail
-- (current_a / breaker_amps * 100). NULL until set; that panel simply shows
-- no data for a circuit until it has a value here.
--
-- is_240v_single_clamp -- true when a 240V circuit (a dryer, oven, or large
-- HVAC unit, say) only has a CT clamp on ONE of its two legs rather than
-- one per leg. A 240V load draws the same current on both legs
-- simultaneously, so a single-leg clamp only "sees" half the circuit's real
-- power draw -- this flag doubles the computed watts (and therefore
-- kWh/cost) to correct for it. Deliberately does NOT affect current_a
-- (already the true per-leg current) or power_factor (a ratio -- doubling
-- both the real and apparent power it's derived from leaves it unchanged).
ALTER TABLE circuit_config ADD COLUMN IF NOT EXISTS breaker_amps DOUBLE PRECISION
    CONSTRAINT circuit_config_breaker_amps_positive CHECK (breaker_amps IS NULL OR breaker_amps > 0);
ALTER TABLE circuit_config ADD COLUMN IF NOT EXISTS is_240v_single_clamp BOOLEAN NOT NULL DEFAULT false;

-- Extend the config-portal's restricted role to these two new columns --
-- still nothing beyond SELECT on the whole table and UPDATE on these
-- specific columns (invert_display, label, and now these two).
GRANT UPDATE (breaker_amps, is_240v_single_clamp) ON circuit_config TO circuit_portal;
