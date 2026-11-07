"""The tBIN map reader, on a map built by hand."""

import struct

from valley_planner.xnb.tbin import read_tbin


def s(text):
    b = text.encode()
    return struct.pack("<i", len(b)) + b


def props(**kv):
    out = struct.pack("<i", len(kv))
    for k, v in kv.items():
        out += s(k) + (bytes([3]) + s(v) if isinstance(v, str) else bytes([1]) + struct.pack("<i", v))
    return out


def test_reads_tile_properties_through_every_tile_kind():
    sheet = s("outdoors") + s("") + s("img") + struct.pack("<8i", 16, 16, 16, 16, 0, 0, 0, 0) + props()
    row0 = b"T" + s("outdoors") + b"S" + struct.pack("<iB", 5, 0) + props(Action="LockedDoorWarp 6 29 SeedShop 900 2100") \
        + b"N" + struct.pack("<i", 2)
    anim = b"A" + struct.pack("<ii", 250, 2) + b"T" + s("outdoors") + b"S" + struct.pack("<iB", 1, 0) + props() \
        + b"S" + struct.pack("<iB", 2, 0) + props() + props(Action="Message x")
    row1 = b"N" + struct.pack("<i", 1) + anim + b"S" + struct.pack("<iB", 3, 0) + props()
    layer = s("Buildings") + b"\x01" + s("") + struct.pack("<4i", 3, 2, 16, 16) + props() + row0 + row1
    data = b"tBIN10" + s("Town") + s("") + props(Outdoors="T", Light=3) + struct.pack("<i", 1) + sheet \
        + struct.pack("<i", 1) + layer
    m = read_tbin(data)
    assert m.id == "Town" and m.properties == {"Outdoors": "T", "Light": 3}
    tiles = m.layers["Buildings"].tile_properties
    assert tiles == {(0, 0): {"Action": "LockedDoorWarp 6 29 SeedShop 900 2100"}, (1, 1): {"Action": "Message x"}}


def test_keeps_tile_sheets_and_every_tile_when_asked():
    def sheet(sid, image, cols, rows):
        return s(sid) + s("") + s(image) + struct.pack("<8i", cols, rows, 16, 16, 0, 0, 0, 0) + props()

    row0 = b"T" + s("a") + b"S" + struct.pack("<iB", 7, 0) + props() + b"T" + s("b") + b"S" + struct.pack("<iB", 3, 0) \
        + props()
    anim = b"A" + struct.pack("<ii", 250, 2) + b"T" + s("a") + b"S" + struct.pack("<iB", 9, 0) + props() \
        + b"S" + struct.pack("<iB", 10, 0) + props() + props()
    row1 = b"N" + struct.pack("<i", 1) + anim
    layer = s("Back") + b"\x01" + s("") + struct.pack("<4i", 2, 2, 16, 16) + props() + row0 + row1
    data = b"tBIN10" + s("Tiny") + s("") + props() + struct.pack("<i", 2) + sheet("a", "spring_town", 32, 72) \
        + sheet("b", "../TileSheets/x", 4, 4) + struct.pack("<i", 1) + layer
    m = read_tbin(data, tiles=True)
    assert [(sh.id, sh.image, sh.columns, sh.rows, sh.tile_width) for sh in m.sheets] == \
        [("a", "spring_town", 32, 72, 16), ("b", "../TileSheets/x", 4, 4, 16)]
    # row by row: sheet a tile 7, sheet b tile 3; nothing, then the animation's first frame (sheet a, tile 9)
    assert m.layers["Back"].tiles == [7, (1 << 16) | 3, -1, 9]
    assert read_tbin(data).layers["Back"].tiles is None  # not kept unless asked
