"""Content-file reader: hand-built .xnb files, plus — when the game is installed — every real data file."""

import json
import struct

import pytest

from valley_planner.discover import find_game
from valley_planner.xnb.reader import XnbReader, parse_type_name
from valley_planner.xnb.schema import ClassInfo, Schema, TypeSig

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


def empty_schema() -> Schema:
    return Schema([])


def test_parse_type_name_nested_generics():
    t = parse_type_name(CONTENT + "DictionaryReader`2[[System.String, mscorlib, Version=4.0.0.0],"
                        "[System.Collections.Generic.List`1[[System.String, mscorlib]], mscorlib]]")
    assert t.name == CONTENT + "DictionaryReader`2"
    assert t.args[0].name == "System.String"
    assert t.args[1].name == "System.Collections.Generic.List`1" and t.args[1].args[0].name == "System.String"


def test_dictionary_of_strings(tmp_path):
    readers = [CONTENT + "DictionaryReader`2[[System.String, mscorlib],[System.String, mscorlib]]",
               CONTENT + "StringReader"]
    body = int7(1) + struct.pack("<i", 1) + int7(2) + string("610") + int7(2) + string("900 Town 10 10 2")
    f = tmp_path / "schedule.xnb"
    f.write_bytes(xnb(readers, body))
    assert XnbReader(empty_schema()).read(f) == {"610": "900 Town 10 10 2"}


def test_class_with_enum_struct_and_null(tmp_path):
    schema = empty_schema()
    schema.classes["Game.Season"] = ClassInfo("Game.Season", None, enum={0: "Spring", 1: "Summer"})
    schema.classes["Game.Crop"] = ClassInfo("Game.Crop", None, members=[
        ("Days", TypeSig("System.Int32", value_type=True)),
        ("Season", TypeSig("Game.Season", value_type=True)),
        ("Tile", TypeSig("Microsoft.Xna.Framework.Point", value_type=True)),
        ("Note", TypeSig("System.String")),
    ])
    readers = [CONTENT + "ReflectiveReader`1[[Game.Crop, Game]]"]
    body = int7(1) + struct.pack("<iiii", 4, 1, 3, 5) + int7(0)
    f = tmp_path / "crop.xnb"
    f.write_bytes(xnb(readers, body))
    assert XnbReader(schema).read(f) == {"Days": 4, "Season": "Summer", "Tile": {"X": 3, "Y": 5}, "Note": None}


GAME = find_game()
needs_game = pytest.mark.skipif(GAME is None, reason="Stardew Valley isn't installed here")


@pytest.mark.game
@needs_game
def test_real_data_files_decode():
    reader = XnbReader(Schema([GAME.dll_dir / "StardewValley.GameData.dll"]))
    crops = reader.read(GAME.content / "Data" / "Crops.xnb")
    parsnip = crops["472"]  # Parsnip Seeds
    assert parsnip["Seasons"] == ["Spring"] and sum(parsnip["DaysInPhase"]) == 4
    schedule = reader.read(GAME.content / "Characters" / "schedules" / "Abigail.xnb")
    assert all(isinstance(v, str) for v in schedule.values())


@pytest.mark.game
@needs_game
def test_matches_an_unpacked_copy_when_there_is_one():
    unpacked = GAME.root / "Content (unpacked)"
    if not unpacked.is_dir():
        pytest.skip("no StardewXnbHack output to compare with")
    reader = XnbReader(Schema([GAME.dll_dir / "StardewValley.GameData.dll"]))
    for name in ("Objects", "Shops", "Fish", "Locations", "NPCGiftTastes", "Bundles", "Characters", "Machines"):
        ours = reader.read(GAME.content / "Data" / f"{name}.xnb")
        theirs = json.loads((unpacked / "Data" / f"{name}.json").read_text(encoding="utf-8-sig"))
        assert float32(ours) == float32(theirs), name


def float32(x):
    """Floats are stored as 32-bit: 0.1 reads back as 0.100000001…, so compare at that precision."""
    if isinstance(x, dict):
        return {k: float32(v) for k, v in x.items()}
    if isinstance(x, list):
        return [float32(v) for v in x]
    return float(f"{x:.6g}") if isinstance(x, float) else x
