"""The shape of the game's data classes, read from its own .NET assemblies.

The content files store objects member by member with no names, in the order
the class declares them, so decoding one needs the class layout. We read it
from the player's installed StardewValley.GameData.dll (dnfile parses .NET
metadata) — nothing about the classes is written into this project.

Serialized members follow the XNA content rules: base class first, then public
read/write properties, then public fields; [ContentSerializer] opts a member in,
[ContentSerializerIgnore] out.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import dnfile

PRIMITIVES = {
    0x02: "System.Boolean", 0x03: "System.Char", 0x04: "System.SByte", 0x05: "System.Byte",
    0x06: "System.Int16", 0x07: "System.UInt16", 0x08: "System.Int32", 0x09: "System.UInt32",
    0x0A: "System.Int64", 0x0B: "System.UInt64", 0x0C: "System.Single", 0x0D: "System.Double",
    0x0E: "System.String", 0x1C: "System.Object",
}
CONSTANT_FORMAT = {0x02: "<?", 0x04: "<b", 0x05: "<B", 0x06: "<h", 0x07: "<H", 0x08: "<i", 0x09: "<I",
                   0x0A: "<q", 0x0B: "<Q"}


@dataclass(frozen=True)
class TypeSig:
    """A member's type: a name, generic arguments, and whether it's a struct (read without a type tag)."""

    name: str
    args: tuple[TypeSig, ...] = ()
    value_type: bool = False
    array: bool = False


@dataclass
class ClassInfo:
    name: str
    base: str | None
    members: list[tuple[str, TypeSig]] = field(default_factory=list)
    enum: dict[int, str] | None = None  # value -> name, for enums
    value_type: bool = False


class _Reader:
    def __init__(self, blob: bytes):
        self.b, self.i = blob, 0

    def byte(self) -> int:
        v = self.b[self.i]
        self.i += 1
        return v

    def compressed(self) -> int:
        b0 = self.byte()
        if b0 & 0x80 == 0:
            return b0
        if b0 & 0xC0 == 0x80:
            return ((b0 & 0x3F) << 8) | self.byte()
        return ((b0 & 0x1F) << 24) | (self.byte() << 16) | (self.byte() << 8) | self.byte()


class Assembly:
    """One .NET assembly's type definitions."""

    def __init__(self, path: Path):
        self.pe = dnfile.dnPE(str(path))
        self.md = self.pe.net.mdtables

    @cached_property
    def _nested_parent(self) -> dict[int, int]:
        return {int(n.NestedClass.row_index): int(n.EnclosingClass.row_index) for n in self.md.NestedClass or []}

    def typedef_name(self, index: int) -> str:
        t = self.md.TypeDef[index - 1]
        if index in self._nested_parent:
            return f"{self.typedef_name(self._nested_parent[index])}+{t.TypeName}"
        ns = str(t.TypeNamespace)
        return f"{ns}.{t.TypeName}" if ns else str(t.TypeName)

    def typeref_name(self, row) -> str:
        scope = row.ResolutionScope
        if scope is not None and scope.table is not None and scope.table.name == "TypeRef":
            return f"{self.typeref_name(scope.row)}+{row.TypeName}"
        ns = str(row.TypeNamespace)
        return f"{ns}.{row.TypeName}" if ns else str(row.TypeName)

    def coded_type_name(self, coded: int) -> str:
        table, index = coded & 3, coded >> 2
        if table == 0:
            return self.typedef_name(index)
        if table == 1:
            return self.typeref_name(self.md.TypeRef[index - 1])
        raise ValueError("TypeSpec base types are not supported")

    def sig(self, r: _Reader) -> TypeSig:
        et = r.byte()
        if et in PRIMITIVES:
            name = PRIMITIVES[et]
            return TypeSig(name, value_type=name not in ("System.String", "System.Object"))
        if et in (0x11, 0x12):  # VALUETYPE / CLASS
            return TypeSig(self.coded_type_name(r.compressed()), value_type=et == 0x11)
        if et == 0x15:  # GENERICINST
            kind = r.byte()
            base = self.coded_type_name(r.compressed())
            args = tuple(self.sig(r) for _ in range(r.compressed()))
            return TypeSig(base, args, value_type=kind == 0x11)
        if et == 0x1D:  # SZARRAY
            return TypeSig("[]", (self.sig(r),), array=True)
        raise ValueError(f"unsupported element type 0x{et:02x}")

    @cached_property
    def _attributes(self) -> dict[tuple[str, int], set[str]]:
        """(table, row index) -> attribute type names on it."""
        out: dict[tuple[str, int], set[str]] = {}
        for ca in self.md.CustomAttribute or []:
            ctor = ca.Type.row
            cls = getattr(ctor, "Class", None)
            name = str(cls.row.TypeName) if cls is not None and hasattr(cls.row, "TypeName") else ""
            key = (str(ca.Parent.table.name), int(ca.Parent.row_index))
            out.setdefault(key, set()).add(name)
        return out

    @cached_property
    def _properties(self) -> dict[int, list[int]]:
        """TypeDef index -> its Property row indexes, in order."""
        return {int(pm.Parent.row_index): [int(p.row_index) for p in pm.PropertyList]
                for pm in self.md.PropertyMap or []}

    @cached_property
    def _accessors(self) -> dict[int, dict[str, int]]:
        """Property index -> {"get": MethodDef index, "set": ...}."""
        out: dict[int, dict[str, int]] = {}
        for ms in self.md.MethodSemantics or []:
            if ms.Association.table.name != "Property":
                continue
            kind = "get" if ms.Semantics.msGetter else "set" if ms.Semantics.msSetter else None
            if kind:
                out.setdefault(int(ms.Association.row_index), {})[kind] = int(ms.Method.row_index)
        return out

    @cached_property
    def _constants(self) -> dict[int, object]:
        """Field index -> literal value (enum members)."""
        out = {}
        for c in self.md.Constant or []:
            if c.Parent.table.name == "Field" and c.Type in CONSTANT_FORMAT:
                out[int(c.Parent.row_index)] = struct.unpack(CONSTANT_FORMAT[c.Type], bytes(c.Value.value))[0]
        return out

    def classes(self) -> dict[str, ClassInfo]:
        out = {}
        for i, t in enumerate(self.md.TypeDef, start=1):
            name = self.typedef_name(i)
            base = None
            if t.Extends is not None and t.Extends.row is not None:
                base = self.typeref_name(t.Extends.row) if t.Extends.table.name == "TypeRef" else \
                    self.typedef_name(int(t.Extends.row_index))
            info = ClassInfo(name, None if base in ("System.Object", "System.ValueType") else base,
                             value_type=base in ("System.ValueType", "System.Enum"))
            fields = [(int(f.row_index), f.row) for f in t.FieldList]
            if base == "System.Enum":
                info.enum = {self._constants[fi]: str(f.Name) for fi, f in fields if fi in self._constants}
                info.base = None
                out[name] = info
                continue
            members = []
            for pi in self._properties.get(i, []):
                p = self.md.Property[pi - 1]
                attrs = self._attributes.get(("Property", pi), set())
                if "ContentSerializerIgnoreAttribute" in attrs:
                    continue
                acc = self._accessors.get(pi, {})
                if "get" not in acc or "set" not in acc:
                    continue  # read-only: not serialized
                getter = self.md.MethodDef[acc["get"] - 1]
                if getter.Flags.mdStatic:
                    continue
                public = getter.Flags.mdPublic
                if not public and "ContentSerializerAttribute" not in attrs:
                    continue
                r = _Reader(bytes(p.Type.value))
                r.byte()  # PROPERTY (+HASTHIS)
                if r.compressed():  # indexer
                    continue
                members.append((str(p.Name), self.sig(r)))
            for fi, f in fields:
                if f.Flags.fdStatic or f.Flags.fdLiteral:
                    continue
                attrs = self._attributes.get(("Field", fi), set())
                if "ContentSerializerIgnoreAttribute" in attrs:
                    continue
                if not f.Flags.fdPublic and "ContentSerializerAttribute" not in attrs:
                    continue
                r = _Reader(bytes(f.Signature.value))
                r.byte()  # FIELD
                members.append((str(f.Name), self.sig(r)))
            info.members = members
            out[name] = info
        return out


class Schema:
    """All the data classes the content files may name, from the game's assemblies."""

    def __init__(self, dlls: list[Path]):
        self.dlls = list(dlls)

    @cached_property
    def classes(self) -> dict[str, ClassInfo]:
        """Loaded on first use: plain string tables never need them."""
        out: dict[str, ClassInfo] = {}
        for dll in self.dlls:
            if dll.is_file():
                out.update(Assembly(dll).classes())
        return out

    def members(self, name: str) -> list[tuple[str, TypeSig]]:
        """Serialized members, base class first."""
        info = self.classes[name]
        inherited = self.members(info.base) if info.base and info.base in self.classes else []
        return inherited + info.members
