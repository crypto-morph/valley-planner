"""Pictures: the game's Texture2D content files, turned into PNG for the browser.

A Texture2D asset (after the usual .xnb container, see reader.py) is: one type reader (Texture2DReader), no shared
resources, the object's reader index, then a 32-bit surface format, width, height and mip level count, and for
each level a 32-bit byte count and the pixels. Stardew's are all format 0 (Color: 8-bit R, G, B, A per pixel,
row by row) with one level. The colours are stored premultiplied by alpha (the content pipeline's default), so
half-see-through pixels (shadows, water edges) are turned back to straight alpha for a PNG.

The PNG writer is the smallest the format allows: signature, IHDR (8-bit RGBA), one zlib-compressed IDAT with
filter 0 on every row, IEND.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

from .reader import XnbError, XnbReader, _Stream

COLOR = 0  # SurfaceFormat.Color


def read_texture(raw: bytes) -> tuple[int, int, bytes]:
    """An .xnb file's bytes -> (width, height, straight-alpha RGBA pixels) for its first mip level."""
    s = _Stream(XnbReader(None).payload(raw))
    names = []
    for _ in range(s.int7()):
        names.append(s.string())
        s.take(4)
    if not names or "Texture2DReader" not in names[0]:
        raise XnbError("not a texture")
    if s.int7():
        raise XnbError("shared resources are not supported")
    s.int7()  # the object's reader index
    fmt, width, height, levels = struct.unpack("<iIII", s.take(16))
    if fmt != COLOR or levels < 1:
        raise XnbError(f"unsupported texture format {fmt}")
    size = s.unpack("<I", 4)
    if size != width * height * 4:
        raise XnbError("texture size doesn't match its pixels")
    return width, height, unpremultiply(s.take(size))


def unpremultiply(px: bytes) -> bytes:
    """Premultiplied RGBA -> straight RGBA. Only partly see-through pixels change (most are 0 or 255 alpha)."""
    out = bytearray(px)
    alphas = out[3::4]
    for k, a in enumerate(alphas):
        if 0 < a < 255:
            i = k * 4
            out[i] = min(255, out[i] * 255 // a)
            out[i + 1] = min(255, out[i + 1] * 255 // a)
            out[i + 2] = min(255, out[i + 2] * 255 // a)
    return bytes(out)


def encode_png(width: int, height: int, rgba: bytes) -> bytes:
    if len(rgba) != width * height * 4:
        raise ValueError("pixel count doesn't match the size")

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    stride = width * 4
    rows = b"".join(b"\0" + rgba[y * stride:(y + 1) * stride] for y in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 6)) + chunk(b"IEND", b""))


def texture_png(path: Path) -> tuple[int, int, bytes]:
    """(width, height, PNG bytes) for a Texture2D .xnb file."""
    w, h, px = read_texture(Path(path).read_bytes())
    return w, h, encode_png(w, h, px)
