"""Build tiny .xnb content files for tests (uncompressed, so no game files are needed)."""

import struct

CONTENT = "Microsoft.Xna.Framework.Content."


def int7(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def string(text: str) -> bytes:
    raw = text.encode("utf-8")
    return int7(len(raw)) + raw


def xnb(readers: list[str], body: bytes) -> bytes:
    payload = int7(len(readers)) + b"".join(string(r) + b"\0\0\0\0" for r in readers) + int7(0) + body
    return b"XNBw\x05\x00" + struct.pack("<I", 10 + len(payload)) + payload
