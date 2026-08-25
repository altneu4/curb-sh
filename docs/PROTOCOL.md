# The Curb Hub Protocol

This documents the wire protocol the receiver implements, reverse-engineered
from the real `/data/lamarr/*.lua` application source pulled off a rooted
Curb Energy Monitor. Credit to [`curbed`](https://github.com/codearranger/curbed)
(the companion repo for rooting the device) and its `docs/FINDINGS.md`,
where the hardware/firmware side of this was originally documented.

None of this is authenticated in any meaningful sense -- there's a
`serialNumber`/`secret` pair sent as Basic Auth on every request, but the
real cloud service never validated it server-side, and this receiver
doesn't either. Don't expose it beyond your own LAN without putting
something else (a reverse proxy, a VPN) in front of it.

## Where the target URLs come from

The device loads `/data/hub-config.json` at startup (`config.lua`) and never
validates the URL scheme -- `endpoints.samples`, `.messages`, `.hub_config`,
and `.diagnostics` are used exactly as written. Pointing a device at this
receiver is a config edit, not a firmware change -- see `SETUP.md`. Using
`http://` instead of `https://` sidesteps TLS entirely (the original
endpoints use HTTPS with real certificate verification enabled -- no
`verifypeer`-style override exists anywhere in the Lua source -- but nothing
requires HTTPS specifically; it's just what the original URLs happened to
use).

## The "compressed message" body format

Used by `POST /v3/samples` and `POST /v3/diagnostics`. Built by
`compressed-message.lua`:

```
packed     = MessagePack.pack(payload)
compressed = zlib.compress(packed)
body       = compressed .. <4-byte big-endian CRC32 of compressed>
```

The device computes that CRC32 with a hand-rolled bit-by-bit loop (Lua has
no built-in one), but it's the standard CRC-32/ISO-HDLC algorithm --
`zlib.crc32()` in any other language produces the same value. The receiver
decodes this in `receiver/app/protocol/compressed_message.py`; CRC
verification is optional (`CURB_VERIFY_CRC`) since it's a data-integrity
check, not a security one.

Headers on these requests:

```
Content-Type: application/octet-stream
Content-Encoding: deflate
Authorization: Basic base64(serialNumber:secret)
```

## Endpoints

### `POST /v3/samples/<serial>`

Body: compressed-message-encoded `{ ver, h, s }` where `h` is the hub ID and
`s` is an array of sample objects, each shaped:

```json
{
  "t": 1774201980,
  "p": 60,
  "g": [
    {
      "t": 3.884,
      "f": 59.993,
      "tg": 3.860,
      "v": 123.08,
      "ts": 3.874,
      "c": [
        { "i": 11.706, "w": 0.3684, "var": -0.1101, "p": 0.9597 }
      ]
    }
  ]
}
```

`g` = groups (one per leg of the split-phase panel), `c` = circuits within a
group. An unpopulated clamp slot is the string `"none"`, not omitted --
groups always report a fixed channel count. Field meanings: `t` (sample
level) = Unix timestamp, `p` = period in seconds; `t`/`f`/`tg`/`v`/`ts` at
the group level = apparent power (kVA), line frequency (Hz), true power
(kW), voltage (V RMS), true power sum (kW); `i`/`w`/`var`/`p` at the circuit
level = current (A RMS), real power (kWh over the period), reactive power
(kVARh), power factor.

Expected response: `200` with a JSON body containing a `messages` count
(how many hub messages are queued for the device -- see below). Any other
code and the device just retries later from its own offline queue.

### `POST /v3/diagnostics/<serial>`

Body: compressed-message-encoded diagnostics object --
`hubId`/`hardwareVersion`/`modelNumber`/`osVersion`/`softwareVersion`/`plcConnection`.
Only the response *code* is checked (`200` = success), the body is ignored.

### `GET /v3/hub_config/<serial>?config_version=3.1`

Polled every 5 minutes by `streamer.lua`. A `200` response with a JSON body
containing a higher `revision` than the device's current one gets written
back to `/data/hub-config.json` and applied immediately (other Lamarr
processes are signalled via `SIGUSR1`). Any other response code leaves the
device's existing config untouched. **This receiver never returns 200
here** -- see `docs/SETUP.md` for why manual config edits are the
recommended path instead of remote config push.

### `GET /v3/messages/<serial>?get_count=true`

Polled every 5 seconds. Expects `{"number_of_available_hub_messages": N}`.
If `N > 0`, the device follows up with `GET /v3/messages/<serial>` (no query
string) up to 10 times, expecting JSON messages shaped `{"type": "..."}`
where `type` is `config` (re-check config now), `update` (run
`/usr/local/sbin/update.sh`), or `reboot`. **This receiver always reports
zero** -- there's no legitimate reason a monitoring platform needs the
ability to remotely reboot or update someone's device, so that capability
is deliberately not implemented.

### `POST /v3/messages/<serial>`

The reverse direction (`HubMessaging:post()`) -- not exercised anywhere in
the current `streamer.lua` flow as far as we've found, but accepted and
logged rather than erroring if something does call it.
