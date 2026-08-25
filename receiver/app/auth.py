"""
Parses the Basic Auth header the Curb device sends on every request
(Authorization: Basic base64(serialNumber:secret)).

Note this is an identity hint, not real access control: the real
border.prod.energycurb.com never validated the secret server-side either
(per curbed's docs/FINDINGS.md), and this receiver doesn't either. If you
want actual auth (e.g. exposing this receiver beyond your own LAN), put it
behind a reverse proxy / VPN rather than relying on this header.
"""

import base64

from fastapi import Request


def parse_basic_auth(request: Request) -> tuple[str | None, str | None]:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("basic "):
        return None, None

    try:
        decoded = base64.b64decode(header[6:]).decode("utf-8")
    except Exception:
        return None, None

    serial, sep, secret = decoded.partition(":")
    if not sep:
        return None, None

    return serial, secret
