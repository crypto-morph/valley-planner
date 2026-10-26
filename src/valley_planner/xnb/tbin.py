"""Maps: the tIDE binary map format ("tBIN10") the game's Maps/*.xnb hold, read for properties.

Layout, in our words: a magic "tBIN10"; the map's id and description; its
properties; its tile sheets; then its layers, each with an id, a visible
flag, a description, size and tile size, properties and its tiles row by
row. A row is a run of commands: 'T' switch tile sheet (by id), 'N' skip n
empty tiles, 'S' a static tile (index, blend mode, properties), 'A' an
animated tile (frame interval, frame count, the frames as T/S commands, then
properties). Strings are a 32-bit length then UTF-8; numbers little-endian.
A property is a key, a type byte (0 bool, 1 int, 2 float, 3 string) and a
value.

We keep the map's properties and, per layer, the tiles that have properties
— that's where tile actions (doors, shops…) live.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field


class TbinError(ValueError):
    pass


@dataclass
class Layer:
    id: str
    width: int
    height: int
    properties: dict
    tile_properties: dict[tuple[int, int], dict] = field(default_factory=dict)


@dataclass
class Map:
    id: str
    properties: dict
    layers: dict[str, Layer]

    def as_dict(self) -> dict:
        """Plain data: {"Id", "Properties", "Layers": {id: {"Width", "Height", "Properties",
        "Tiles": {"x,y": props}}}}."""
        return {"Id": self.id, "Properties": self.properties, "Layers": {
            lid: {"Width": layer.width, "Height": layer.height, "Properties": layer.properties,
                  "Tiles": {f"{x},{y}": p for (x, y), p in layer.tile_properties.items()}}
            for lid, layer in self.layers.items()}}


class _Reader:
    def __init__(self, data: bytes):
        self.data, self.pos = data, 0

    def take(self, n: int) -> bytes:
        if self.pos + n > len(self.data):
            raise TbinError("map data ends early")
        b = self.data[self.pos:self.pos + n]
        self.pos += n
        return b

    def i32(self) -> int:
        return struct.unpack("<i", self.take(4))[0]

    def byte(self) -> int:
        return self.take(1)[0]

    def string(self) -> str:
        return self.take(self.i32()).decode("utf-8")

    def properties(self) -> dict:
        out = {}
        for _ in range(self.i32()):
            key, kind = self.string(), self.byte()
            if kind == 0:
                out[key] = self.byte() != 0
            elif kind == 1:
                out[key] = self.i32()
            elif kind == 2:
                out[key] = struct.unpack("<f", self.take(4))[0]
            elif kind == 3:
                out[key] = self.string()
            else:
                raise TbinError(f"unknown property type {kind}")
        return out


def read_tbin(data: bytes) -> Map:
    r = _Reader(data)
    if r.take(6) != b"tBIN10":
        raise TbinError("not a tBIN10 map")
    map_id = r.string()
    r.string()  # description
    props = r.properties()
    for _ in range(r.i32()):  # tile sheets
        r.string(), r.string(), r.string()  # id, description, image
        r.take(4 * 8)  # sheet size, tile size, margin, spacing
        r.properties()
    layers = {}
    for _ in range(r.i32()):
        lid = r.string()
        r.byte()  # visible
        r.string()  # description
        w, h = r.i32(), r.i32()
        r.take(8)  # tile size
        layer = Layer(lid, w, h, r.properties())
        for y in range(h):
            x = 0
            while x < w:
                cmd = chr(r.byte())
                if cmd == "T":
                    r.string()
                elif cmd == "N":
                    x += r.i32()
                elif cmd == "S":
                    r.take(5)  # index, blend mode
                    p = r.properties()
                    if p:
                        layer.tile_properties[(x, y)] = p
                    x += 1
                elif cmd == "A":
                    r.take(4)  # frame interval
                    frames = r.i32()
                    while frames:
                        c = chr(r.byte())
                        if c == "T":
                            r.string()
                        elif c == "S":
                            r.take(5)
                            r.properties()
                            frames -= 1
                        else:
                            raise TbinError(f"bad animated frame command {c!r}")
                    p = r.properties()
                    if p:
                        layer.tile_properties[(x, y)] = p
                    x += 1
                else:
                    raise TbinError(f"bad tile command {cmd!r} at {lid} {x},{y}")
        layers[lid] = layer
    return Map(map_id, props, layers)
