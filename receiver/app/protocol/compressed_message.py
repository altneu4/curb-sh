"""
Decoder for the Curb device's "compressed message" wire format, used for the
/v3/samples and /v3/diagnostics POST bodies.

Reverse of payload/lamarr/compressed-message.lua's compressedMessage.create()
in the curbed repo:

    packed     = MessagePack.pack(payload)
    compressed = zlib.compress(packed)
    return compressed .. <4-byte big-endian CRC32 of compressed>

The device computes that CRC32 with a hand-rolled bit-by-bit implementation
(Lua has no zlib.crc32 built in), but it uses the standard CRC-32/ISO-HDLC
polynomial (0xEDB88320, reflected) with the standard init/final XOR -- the
same algorithm zlib.crc32() implements -- so no custom logic is needed here.
"""

import struct
import zlib

import msgpack


class DecodeError(Exception):
    """Raised when a compressed-message body can't be decoded."""


def decode(raw: bytes, verify_crc: bool = False) -> dict:
    if len(raw) < 5:
        raise DecodeError("payload too short to contain a CRC32 trailer")

    compressed, crc_trailer = raw[:-4], raw[-4:]
    (expected_crc,) = struct.unpack(">I", crc_trailer)

    if verify_crc:
        actual_crc = zlib.crc32(compressed) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise DecodeError(
                f"CRC32 mismatch (computed {actual_crc:#010x}, "
                f"device sent {expected_crc:#010x})"
            )

    try:
        decompressed = zlib.decompress(compressed)
    except zlib.error as exc:
        raise DecodeError(f"zlib decompression failed: {exc}") from exc

    try:
        return msgpack.unpackb(decompressed, raw=False)
    except Exception as exc:  # msgpack can raise several distinct exception types
        raise DecodeError(f"MessagePack decode failed: {exc}") from exc
