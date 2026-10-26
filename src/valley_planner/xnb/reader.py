"""Read an .xnb content file into plain Python data (dicts, lists, strings, numbers).

Container (XNA 4 / MonoGame): "XNB", platform, version 5, flags (0x80 LZX),
file size, then — when compressed — the decompressed size and the LZX stream.
The payload lists the type readers it uses, then the asset. Each object is a
7-bit reader index (0 = null) and that reader's data; structs and primitives
inside other objects are written bare. Class layouts come from Schema.
Output matches the usual JSON form of these assets (enums as names).
"""

from __future__ import annotations

import struct
from pathlib import Path

from .lzx import decompress_xnb
from .schema import Schema, TypeSig

XNA = "Microsoft.Xna.Framework."
STRUCTS = {  # XNA structs: their fields, all int32 unless noted
    XNA + "Point": ("X", "Y"),
    XNA + "Rectangle": ("X", "Y", "Width", "Height"),
}
PRIMITIVE_READS = {
    "System.Boolean": ("<?", 1), "System.Byte": ("<B", 1), "System.SByte": ("<b", 1),
    "System.Int16": ("<h", 2), "System.UInt16": ("<H", 2), "System.Int32": ("<i", 4), "System.UInt32": ("<I", 4),
    "System.Int64": ("<q", 8), "System.UInt64": ("<Q", 8), "System.Single": ("<f", 4), "System.Double": ("<d", 8),
}
VALUE_NAMES = set(PRIMITIVE_READS) | set(STRUCTS) | {"System.Char", XNA + "Vector2", XNA + "Color"}


class XnbError(ValueError):
    pass


def parse_type_name(text: str) -> TypeSig:
    """'Dictionary`2[[System.String, mscorlib, ...],[Foo, Bar, ...]]' -> TypeSig. Assembly parts are dropped."""
    text = text.strip()
    if text.endswith("[]"):
        return TypeSig("[]", (parse_type_name(text[:-2]),), array=True)
    i = text.find("[[")
    if i < 0:
        return TypeSig(text.split(",")[0].strip())
    name, rest = text[:i], text[i + 1:]
    args, depth, start = [], 0, 0
    for j, ch in enumerate(rest):
        if ch == "[":
            depth += 1
            if depth == 1:
                start = j + 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                args.append(parse_type_name(_strip_assembly(rest[start:j])))
            if depth < 0:
                break
    return TypeSig(name, tuple(args))


def _strip_assembly(qualified: str) -> str:
    """'System.String, mscorlib, Version=…' -> 'System.String', keeping generic brackets intact."""
    depth = 0
    for k, ch in enumerate(qualified):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        elif ch == "," and depth == 0:
            return qualified[:k]
    return qualified


class _Stream:
    def __init__(self, data: bytes):
        self.b, self.i = data, 0

    def take(self, n: int) -> bytes:
        v = self.b[self.i:self.i + n]
        if len(v) != n:
            raise XnbError("unexpected end of data")
        self.i += n
        return v

    def unpack(self, fmt: str, n: int):
        return struct.unpack(fmt, self.take(n))[0]

    def int7(self) -> int:
        result = shift = 0
        while True:
            b = self.take(1)[0]
            result |= (b & 0x7F) << shift
            if not b & 0x80:
                return result
            shift += 7

    def string(self) -> str:
        return self.take(self.int7()).decode("utf-8")


class XnbReader:
    def __init__(self, schema: Schema):
        self.schema = schema

    # --- container -----------------------------------------------------------------

    def payload(self, raw: bytes) -> bytes:
        if raw[:3] != b"XNB" or raw[4] != 5:
            raise XnbError("not an XNA 4 content file")
        flags = raw[5]
        size = struct.unpack_from("<I", raw, 6)[0]
        if flags & 0x80:
            return decompress_xnb(raw[14:size], struct.unpack_from("<I", raw, 10)[0])
        if flags & 0x40:
            raise XnbError("LZ4-compressed content is not supported")
        return raw[10:size]

    def read(self, path: Path):
        s = _Stream(self.payload(Path(path).read_bytes()))
        self.readers = []
        for _ in range(s.int7()):
            self.readers.append(parse_type_name(s.string()))
            s.take(4)  # reader version
        if s.int7():
            raise XnbError("shared resources are not supported")
        return self.object(s)

    # --- objects -------------------------------------------------------------------

    def object(self, s: _Stream):
        """A reference: reader index, then that reader's data."""
        idx = s.int7()
        if idx == 0:
            return None
        reader = self.readers[idx - 1]
        return self.by_reader(s, reader)

    def by_reader(self, s: _Stream, reader: TypeSig):
        name = reader.name.rsplit(".", 1)[-1]
        if name == "StringReader":
            return s.string()
        if name.startswith(("ListReader", "ArrayReader")):
            return self.list(s, reader.args[0])
        if name.startswith("DictionaryReader"):
            return self.dict(s, *reader.args)
        if name.startswith(("ReflectiveReader", "EnumReader", "NullableReader")):
            return self.value(s, reader.args[0]) if not name.startswith("ReflectiveReader") else \
                self.reflective(s, reader.args[0].name)
        simple = {"Int32Reader": "System.Int32", "BooleanReader": "System.Boolean", "SingleReader": "System.Single",
                  "DoubleReader": "System.Double", "CharReader": "System.Char", "Int64Reader": "System.Int64",
                  "UInt32Reader": "System.UInt32", "ByteReader": "System.Byte", "Int16Reader": "System.Int16",
                  "PointReader": XNA + "Point", "RectangleReader": XNA + "Rectangle", "Vector2Reader": XNA + "Vector2",
                  "ColorReader": XNA + "Color"}
        if name in simple:
            return self.value(s, TypeSig(simple[name], value_type=True))
        raise XnbError(f"unsupported reader {reader.name}")

    def is_value(self, t: TypeSig) -> bool:
        if t.array or t.name == "System.String":
            return False
        if t.value_type or t.name in VALUE_NAMES or t.name == "System.Nullable`1":
            return True
        if t.name.startswith("System."):
            return False  # other System types (Object, collections) are references
        info = self.schema.classes.get(t.name)
        return bool(info and (info.enum is not None or info.value_type))

    def element(self, s: _Stream, t: TypeSig):
        """A member or element: bare if it's a struct/primitive, else a reference."""
        return self.value(s, t) if self.is_value(t) else self.object(s)

    def list(self, s: _Stream, t: TypeSig) -> list:
        return [self.element(s, t) for _ in range(s.unpack("<i", 4))]

    def dict(self, s: _Stream, k: TypeSig, v: TypeSig) -> dict:
        out = {}
        for _ in range(s.unpack("<i", 4)):
            key = self.element(s, k)
            out[key if isinstance(key, str) else str(key)] = self.element(s, v)
        return out

    def value(self, s: _Stream, t: TypeSig):
        if t.name in PRIMITIVE_READS:
            return s.unpack(*PRIMITIVE_READS[t.name])
        if t.name == "System.Char":
            return _read_char(s)
        # The usual JSON form of XNA structs: Point and Rectangle as objects, Vector2 and Color as "X, Y" text
        if t.name in STRUCTS:
            return {f: s.unpack("<i", 4) for f in STRUCTS[t.name]}
        if t.name == XNA + "Vector2":
            return ", ".join(f"{s.unpack('<f', 4):g}" for _ in range(2))
        if t.name == XNA + "Color":
            return ", ".join(str(v) for v in s.take(4))
        if t.name == "System.Nullable`1":
            return self.value(s, t.args[0]) if s.unpack("<?", 1) else None
        info = self.schema.classes.get(t.name)
        if info is not None and info.enum is not None:
            return _enum_name(info.enum, s.unpack("<i", 4))
        if info is not None:
            return self.reflective(s, t.name)
        raise XnbError(f"unknown value type {t.name}")

    def reflective(self, s: _Stream, class_name: str) -> dict:
        if class_name not in self.schema.classes:
            raise XnbError(f"class {class_name} isn't in the game's data assemblies")
        return {name: self.element(s, t) for name, t in self.schema.members(class_name)}


def _read_char(s: _Stream) -> str:
    b0 = s.b[s.i]
    n = 1 if b0 < 0x80 else 2 if b0 < 0xE0 else 3 if b0 < 0xF0 else 4
    return s.take(n).decode("utf-8")


def _enum_name(names: dict[int, str], value: int) -> str | int:
    if value in names:
        return names[value]
    parts = [n for v, n in names.items() if v and value & v == v]  # [Flags] enums
    return ", ".join(parts) if parts else value
