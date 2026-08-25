# Setup

## 1. Run the stack

```bash
cp .env.example .env
# edit .env -- at minimum set real POSTGRES_PASSWORD and GRAFANA_ADMIN_PASSWORD
docker compose up -d
```

This starts three services: `timescaledb` (the database), `receiver` (the
HTTP server your Curb devices will talk to), and `grafana` (the dashboard,
pre-provisioned with a Timescale datasource and a starter "Curb Overview"
dashboard). Confirm the receiver is up:

```bash
curl http://localhost:8080/healthz
```

Grafana is at `http://<this-host>:3000` (default port; change with
`GRAFANA_PORT` in `.env`). Log in with `admin` / whatever you set as
`GRAFANA_ADMIN_PASSWORD`.

## 2. Point your Curb device at it

You need root on the device first -- if you haven't done that yet, see the
[`curbed`](https://github.com/codearranger/curbed) repo, which this project
assumes you've already been through.

Edit `/data/hub-config.json` on the device (it's mounted read-write, no
`remount,rw` dance needed) and change the four endpoint URLs to point at
this receiver, over plain HTTP so there's no certificate to worry about:

```json
"endpoints": {
  "hub_config": "http://<this-host>:8080/v3/hub_config",
  "messages": "http://<this-host>:8080/v3/messages",
  "samples": "http://<this-host>:8080/v3/samples",
  "diagnostics": "http://<this-host>:8080/v3/diagnostics"
}
```

Leave everything else in that file alone -- `config.lua`'s loader only
requires a `revision` field to exist, so partial edits are safe.

**Why HTTP instead of HTTPS:** the device's real streamer code
(`samples-message.lua`, `hub-messaging.lua`) uses `curl` with certificate
verification enabled and never disables it -- unlike the firmware-update
mechanism `curbed` spoofs, there's no `--no-check-certificate` equivalent
here. Since nothing in the code actually requires the *scheme* to be
`https://`, switching to plain HTTP sidesteps that requirement entirely
rather than fighting it with a self-signed cert. See `docs/PROTOCOL.md` for
the full reasoning.

**Why not remote config push:** `hub_config.lua`'s revision-based config
download exists so Curb's cloud could push config changes to devices
automatically. This receiver deliberately doesn't implement that (it always
returns a non-200 from `/v3/hub_config`) -- editing the file directly, once,
is simpler and doesn't require trusting a network service with the ability
to rewrite your device's config on every poll.

## 3. Confirm data is arriving

The edit takes effect the next time `streamer.lua` restarts, which happens
automatically -- it self-restarts after 10 minutes without a successful
POST (`DISCONNECTED_RESTART_TIMEOUT_SECS` in the source), so worst case
you're waiting 10 minutes. To force it immediately instead, over SSH on the
device:

```sh
ps | grep streamer
kill <pid>   # hm respawns it in ~2 seconds, picking up the new config
```

Then watch the receiver's logs:

```bash
docker compose logs -f receiver
```

You should see `samples: <serial> posted N sample(s)` lines. Once that's
flowing, open Grafana, select your device's serial number in the "Curb
Overview" dashboard's device dropdown, and you should see live per-circuit
power.

## 4. Multiple devices

Nothing device-specific is hardcoded -- every device that points its
`hub-config.json` at this same receiver shows up as its own row in the
`devices` table and its own option in the Grafana dashboard's device
selector. One receiver instance handles as many Curb units as you point at
it.
