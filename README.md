# curb-selfhosted

A self-hosted replacement for Curb Energy Monitor's cloud platform --
receiver, time-series database, and dashboard -- for devices recovered with
[`curbed`](https://github.com/codearranger/curbed).

Curb Inc. shut down its cloud service in February 2026, leaving every Curb
Energy Monitor unable to reach the servers it depends on for both firmware
updates and its actual purpose: reporting per-circuit power data somewhere
you can look at it. `curbed` gets root back on the device. This repo picks
up from there -- an ingest server that speaks the device's real protocol,
a TimescaleDB database, and a Grafana dashboard, so you get your monitoring
platform back without depending on Curb Inc. (or anyone else) ever again.

The two repos are deliberately separate: `curbed` is a one-time recovery
tool you run until you have root and then stop; this is a long-running
service you leave running. Different maintenance concerns, different
lifecycles.

## Why this works without touching your device's firmware

The device's config (`/data/hub-config.json`) just holds four endpoint
URLs, and nothing on the device validates them beyond requiring the file to
be well-formed. Point them at this receiver instead of Curb's dead servers,
and the device's own unmodified `streamer.lua`/`diags.lua` start sending
real data here. No Lua patching, no custom firmware -- see
[`docs/SETUP.md`](docs/SETUP.md) for the exact steps, and
[`docs/PROTOCOL.md`](docs/PROTOCOL.md) for how the wire format was
reverse-engineered and what this receiver does and deliberately doesn't
implement.

## Quick start

```bash
cp .env.example .env
# edit .env: set POSTGRES_PASSWORD and GRAFANA_ADMIN_PASSWORD
docker compose up -d
```

Then follow [`docs/SETUP.md`](docs/SETUP.md) to point a device at it.
Deploying on a NAS through Portainer instead of plain `docker compose`? See
[`docs/NAS.md`](docs/NAS.md) for the extra steps (data path, permissions,
backups).

## Architecture

```
Curb device  --(HTTP, real Curb protocol)-->  receiver  -->  TimescaleDB  <--  Grafana
```

- **`receiver/`** -- FastAPI service implementing `/v3/samples`,
  `/v3/diagnostics`, and stubbed `/v3/hub_config` + `/v3/messages`
  endpoints. Decodes the device's MessagePack+zlib+CRC32 body format and
  writes into Timescale.
- **`db/init/`** -- schema, applied automatically on first boot of the
  `timescaledb` container.
- **`grafana/`** -- pre-provisioned datasource + a starter "Curb Overview"
  dashboard (per-circuit power, per-leg voltage/frequency/power factor,
  device status).
- **`examples/`** -- before/after `hub-config.json` examples and a script
  that safely patches just the `endpoints` block of your device's real
  config, leaving its actual sensor calibration untouched.

## Multiple devices, multiple people

Nothing here is single-device-specific -- every Curb that points its
`hub-config.json` at your receiver shows up as its own row in `devices` and
its own entry in the Grafana device selector. If you're recovering more
than one Curb, or helping someone else recover theirs, one instance of this
stack covers all of them.

## Security notes

The device's Basic Auth header (`serialNumber:secret`) is treated as an
identity hint only -- the real Curb cloud never validated it server-side,
and this receiver doesn't either. Don't expose port 8080 (or Grafana)
beyond your own LAN without putting a reverse proxy or VPN in front of it.
The `/v3/hub_config` and `/v3/messages` endpoints are intentionally stubbed
to never let this platform push config or trigger a reboot/update on your
device -- see `docs/PROTOCOL.md` for why.

## License

MIT -- see [`LICENSE`](LICENSE).
