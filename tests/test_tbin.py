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
