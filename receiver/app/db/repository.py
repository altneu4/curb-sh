from datetime import datetime, timezone

from .pool import get_pool


async def upsert_device(serial_number: str, hub_id: str | None = None, secret: str | None = None) -> None:
    pool = get_pool()
    await pool.execute(
        """
        INSERT INTO devices (serial_number, hub_id, last_secret, last_seen_at)
        VALUES ($1, $2, $3, now())
        ON CONFLICT (serial_number) DO UPDATE SET
            hub_id = COALESCE(EXCLUDED.hub_id, devices.hub_id),
            last_secret = COALESCE(EXCLUDED.last_secret, devices.last_secret),
            last_seen_at = now()
        """,
        serial_number, hub_id, secret,
    )


def _is_empty_channel(channel) -> bool:
    # sampler.lua/config.lua represent an unpopulated clamp slot as the
    # string "none" rather than omitting it, so groups always report a
    # fixed number of channels regardless of how many clamps are attached.
    return channel is None or channel == "none"


def build_sample_rows(serial_number: str, samples: list[dict]) -> tuple[list[tuple], list[tuple]]:
    """
    Pure transform from decoded device sample objects to
    (group_rows, circuit_rows) ready for executemany(). Split out from
    insert_samples() so it's testable without a live database connection.
    """
    circuit_rows = []
    group_rows = []

    for sample in samples:
        if "t" not in sample:
            # streamer.lua itself drops samples missing "t" as a deprecated
            # format before posting -- mirror that rather than crash on them.
            continue

        ts = datetime.fromtimestamp(sample["t"], tz=timezone.utc)
        period = sample.get("p")

        for group_idx, group in enumerate(sample.get("g", [])):
            group_rows.append((
                ts, serial_number, group_idx, period,
                group.get("t"), group.get("tg"), group.get("ts"),
                group.get("v"), group.get("f"),
            ))
            for circuit_idx, channel in enumerate(group.get("c", [])):
                if _is_empty_channel(channel):
                    continue
                circuit_rows.append((
                    ts, serial_number, group_idx, circuit_idx,
                    channel.get("i"), channel.get("w"), channel.get("var"), channel.get("p"),
                ))

    return group_rows, circuit_rows


async def insert_samples(serial_number: str, samples: list[dict]) -> None:
    pool = get_pool()
    group_rows, circuit_rows = build_sample_rows(serial_number, samples)

    async with pool.acquire() as conn:
        async with conn.transaction():
            if group_rows:
                await conn.executemany(
                    """
                    INSERT INTO group_samples
                        (time, serial_number, group_idx, period_secs,
                         apparent_power_kva, true_power_kw, true_power_sum_kw,
                         voltage, frequency)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    group_rows,
                )
            if circuit_rows:
                await conn.executemany(
                    """
                    INSERT INTO circuit_samples
                        (time, serial_number, group_idx, circuit_idx,
                         current_a, watts, var, power_factor)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    circuit_rows,
                )


async def insert_diagnostics(serial_number: str, diag: dict) -> None:
    pool = get_pool()
    await pool.execute(
        """
        INSERT INTO diagnostics
            (time, serial_number, hardware_version, software_version, os_version, plc_connection)
        VALUES (now(), $1, $2, $3, $4, $5)
        """,
        serial_number,
        diag.get("hardwareVersion"),
        diag.get("softwareVersion"),
        diag.get("osVersion"),
        diag.get("plcConnection"),
    )
