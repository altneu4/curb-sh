"""
curb-selfhosted receiver

Implements enough of the real Curb hub<->cloud protocol (documented in
docs/PROTOCOL.md, reverse-engineered in the sibling curbed repo's
docs/FINDINGS.md) that an unmodified Curb device can be pointed here just by
editing its /data/hub-config.json endpoint URLs -- no firmware/Lua changes
required on the device. See docs/SETUP.md for that step.

Two endpoints do real work (ingest samples + diagnostics into Timescale);
the other two are safe stubs -- see their docstrings for why.
"""

import logging
import os

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from .auth import parse_basic_auth
from .db import repository
from .db.pool import close_pool, init_pool
from .protocol.compressed_message import DecodeError, decode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("curb-receiver")

VERIFY_CRC = os.environ.get("CURB_VERIFY_CRC", "false").strip().lower() in ("1", "true", "yes")

app = FastAPI(title="curb-selfhosted receiver")


@app.on_event("startup")
async def startup() -> None:
    await init_pool()
    logger.info("DB pool ready (CURB_VERIFY_CRC=%s)", VERIFY_CRC)


@app.on_event("shutdown")
async def shutdown() -> None:
    await close_pool()


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.post("/v3/samples/{serial_number}")
async def post_samples(serial_number: str, request: Request):
    _, secret = parse_basic_auth(request)
    body = await request.body()

    try:
        payload = decode(body, verify_crc=VERIFY_CRC)
    except DecodeError as exc:
        logger.warning("samples decode failed for %s: %s", serial_number, exc)
        return JSONResponse(status_code=400, content={"error": str(exc)})

    samples = payload.get("s", [])
    logger.info("samples: %s posted %d sample(s)", serial_number, len(samples))

    await repository.upsert_device(serial_number, hub_id=payload.get("h"), secret=secret)
    await repository.insert_samples(serial_number, samples)

    # The real endpoint returns how many hub messages are queued for this
    # device; we never queue any (see get_messages below), so this is
    # always 0. streamer.lua only reads this field, doesn't require it.
    return JSONResponse(status_code=200, content={"messages": 0})


@app.post("/v3/diagnostics/{serial_number}")
async def post_diagnostics(serial_number: str, request: Request):
    _, secret = parse_basic_auth(request)
    body = await request.body()

    try:
        diag = decode(body, verify_crc=VERIFY_CRC)
    except DecodeError as exc:
        logger.warning("diagnostics decode failed for %s: %s", serial_number, exc)
        return JSONResponse(status_code=400, content={"error": str(exc)})

    logger.info("diagnostics: %s -> %s", serial_number, diag)

    await repository.upsert_device(serial_number, secret=secret)
    await repository.insert_diagnostics(serial_number, diag)

    # diags.lua only checks the response code, ignores the body.
    return Response(status_code=200)


@app.get("/v3/hub_config/{serial_number}")
async def get_hub_config(serial_number: str):
    """
    Stub. config.lua's checkForNewConfig() treats any non-200 response as
    "no update available" and keeps whatever's already in the device's own
    /data/hub-config.json -- which is where you should point the endpoints
    directly (docs/SETUP.md) rather than relying on this platform to push
    config remotely. Implementing real config push is a reasonable future
    addition if you want it; it's out of scope for a monitoring receiver.
    """
    return Response(status_code=204)


@app.get("/v3/messages/{serial_number}")
async def get_messages(serial_number: str, get_count: bool | None = None):
    """
    Stub. Always reports zero queued messages, so the device's
    processHubMessages() loop -- which can trigger update/reboot commands,
    see docs/PROTOCOL.md -- never fires. Deliberately conservative: this
    receiver should never be able to make your Curb do anything but talk.
    """
    return JSONResponse(status_code=200, content={"number_of_available_hub_messages": 0})


@app.post("/v3/messages/{serial_number}")
async def post_messages(serial_number: str, request: Request):
    # HubMessaging:post() -- not exercised by the current streamer.lua flow,
    # but accept it rather than error if something does call it.
    body = await request.body()
    logger.info("hub message posted by %s (%d bytes)", serial_number, len(body))
    return Response(status_code=201)
