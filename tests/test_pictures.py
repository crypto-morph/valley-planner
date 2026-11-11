"""Map pictures: textures to PNG, tile sheets by season, the save's sprites, and what may be served."""

import struct
import zlib

import pytest
from fastapi.testclient import TestClient
from xnbtools import int7, string, xnb

from valley_planner.app import create_app
from valley_planner.discover import find_game
from valley_planner.pictures import NotAllowed, Textures, clean_asset, layer_order, map_asset, seasonal_name
from valley_planner.views.scene import Scene, crop_source, standard_rect
from valley_planner.xnb.reader import XnbError
from valley_planner.xnb.texture import encode_png, read_texture

TEXTURE_READER = "Microsoft.Xna.Framework.Content.Texture2DReader, Microsoft.Xna.Framework.Graphics"


def texture_xnb(w, h, pixels: bytes, fmt=0) -> bytes:
    body = int7(1) + struct.pack("<iIII", fmt, w, h, 1) + struct.pack("<I", len(pixels)) + pixels
    return xnb([TEXTURE_READER], body)


def png_pixels(png: bytes) -> tuple[int, int, bytes]:
    """A minimal reader for what encode_png writes (one IDAT, filter 0)."""
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, size = 8, b"", None
    while pos < len(png):
        n = struct.unpack(">I", png[pos:pos + 4])[0]
        kind, body = png[pos + 4:pos + 8], png[pos + 8:pos + 8 + n]
        assert struct.unpack(">I", png[pos + 8 + n:pos + 12 + n])[0] == zlib.crc32(kind + body)
        if kind == b"IHDR":
            size = struct.unpack(">II", body[:8])
            assert body[8:10] == bytes([8, 6])  # 8-bit RGBA
        elif kind == b"IDAT":
            idat += body
        pos += 12 + n
    w, h = size
    raw = zlib.decompress(idat)
    rows = [raw[y * (w * 4 + 1):(y + 1) * (w * 4 + 1)] for y in range(h)]
    assert all(r[0] == 0 for r in rows)
    return w, h, b"".join(r[1:] for r in rows)


def test_texture_decodes_and_undoes_premultiplied_alpha():
    pixels = bytes([255, 0, 0, 255,   0, 0, 0, 0,   50, 0, 100, 128,   0, 255, 0, 255])  # 2x2
    w, h, px = read_texture(texture_xnb(2, 2, pixels))
    assert (w, h) == (2, 2)
    assert px[:8] == pixels[:8] and px[12:] == pixels[12:]
    assert px[8:12] == bytes([99, 0, 199, 128])  # 50 * 255 / 128, 100 * 255 / 128


def test_png_round_trips():
    px = bytes(range(4 * 3 * 2))
    assert png_pixels(encode_png(3, 2, px)) == (3, 2, px)
    with pytest.raises(ValueError):
        encode_png(3, 3, px)


def test_texture_refuses_other_formats_and_other_assets():
    with pytest.raises(XnbError):
        read_texture(texture_xnb(1, 1, bytes(8), fmt=4))  # a compressed format
    with pytest.raises(XnbError):
        read_texture(xnb(["Microsoft.Xna.Framework.Content.StringReader"], int7(1) + string("hi")))


@pytest.mark.parametrize("bad", ["../secret", "Maps/../../secret", "/etc/passwd", "Maps//x", "C:/x", "", ".",
                                 "Maps/./x", "Maps\\..\\..\\x", "Maps/x\0"])
def test_asset_names_cannot_leave_the_content_folder(bad):
    with pytest.raises(NotAllowed):
        clean_asset(bad)


def test_asset_names_that_are_fine():
    assert clean_asset("Maps\\spring_town") == "Maps/spring_town"
    assert clean_asset("Buildings/Shipping Bin.png") == "Buildings/Shipping Bin"
    assert map_asset("Farm", 1) == "Maps/Farm_Fishing" and map_asset("Town") == "Maps/Town"
    with pytest.raises(NotAllowed):
        map_asset("../Data/Crops")


def test_a_location_draws_its_own_map():
    class Data:
        def asset(self, name):
            return {"IslandNorth": {"CreateOnLoad": {"MapPath": "Maps\\Island_N"}}}

    assert map_asset("IslandNorth", 0, Data()) == "Maps/Island_N"
    assert map_asset("Town", 0, Data()) == "Maps/Town"


@pytest.fixture
def content(tmp_path):
    root = tmp_path / "Content"
    (root / "Maps").mkdir(parents=True)
    (root / "Maps/tiny.xnb").write_bytes(texture_xnb(1, 1, bytes([1, 2, 3, 255])))
    (tmp_path / "secret.xnb").write_bytes(texture_xnb(1, 1, bytes(4)))
    (root / "Maps/escape.xnb").symlink_to(tmp_path / "secret.xnb")
    return root


def test_textures_serve_only_inside_content(content, tmp_path):
    tex = Textures(content, tmp_path / "cache")
    assert png_pixels(tex.png("Maps/tiny"))[2] == bytes([1, 2, 3, 255])
    assert (tmp_path / "cache/pictures/Maps/tiny.png").is_file()  # cached outside the game's folder
    assert tex.png("maps/TINY") == tex.png("Maps/tiny")  # the data's names don't always match the files' case
    assert tex.url("Maps/tiny").startswith("/api/tex/Maps/tiny.png?v=")
    with pytest.raises(NotAllowed):
        tex.png("Maps/escape")  # a link out of the folder
    with pytest.raises(FileNotFoundError):
        tex.png("Maps/missing")


def test_texture_endpoint(content, tmp_path):
    class Planner:
        textures = Textures(content, None)

    client = TestClient(create_app(Planner()))
    ok = client.get("/api/tex/Maps/tiny.png?v=1")
    assert ok.status_code == 200 and ok.headers["content-type"] == "image/png"
    assert "immutable" in ok.headers["cache-control"]
    for bad in ["/api/tex/Maps/..%2F..%2Fsecret.png", "/api/tex/..%2Fsecret.png", "/api/tex/Maps/escape.png"]:
        assert client.get(bad).status_code == 400, bad
    assert client.get("/api/tex/Maps/missing.png").status_code == 404
    assert client.get("/api/tex/Maps/tiny").status_code == 404


def test_seasonal_tile_sheets_and_layer_order():
    assert seasonal_name("spring_outdoorsTileSheet", "fall") == "fall_outdoorsTileSheet"
    assert seasonal_name("../TileSheets/winter_x", "summer") == "../TileSheets/summer_x"
    assert seasonal_name("paths", "fall") == "paths"
    ids = ["Paths", "Front", "Back2", "AlwaysFront", "Buildings", "Back", "Front-1", "BackGround", "AlwaysFront2"]
    assert layer_order(ids) == [("Back", "Back"), ("Back2", "Back"), ("Buildings", "Buildings"),
                                ("Front-1", "Front"), ("Front", "Front"), ("AlwaysFront", "AlwaysFront"),
                                ("AlwaysFront2", "AlwaysFront")]


# --- the save's sprites ---------------------------------------------------------------------------

def test_crop_source_rect_by_phase():
    # Parsnip: row 0. A seed shows column 0 or 1 by the tile (x * 7 + y * 11 even or odd).
    assert crop_source(0, 0, number=2) == [0, 0, 16, 32]
    assert crop_source(0, 0, number=3) == [16, 0, 16, 32]
    assert crop_source(0, 2) == [48, 0, 16, 32]
    # Strawberry: row 36 (even: left half of the sheet, 18 rows of 32 down); ready 6, regrowing 7
    assert crop_source(36, 5, full_grown=True, day_of_phase=0) == [96, 576, 16, 32]
    assert crop_source(36, 5, full_grown=True, day_of_phase=3) == [112, 576, 16, 32]
    # odd rows sit on the right half of the sheet
    assert crop_source(5, 1) == [128 + 32, 64, 16, 32]
    assert crop_source(5, 1, phase_to_show=3) == [128 + 64, 64, 16, 32]
    assert crop_source(5, 4, dead=True, number=7) == [192 + 48, 384, 16, 32]
    assert crop_source(40, 1, harvest="771", season="fall") == crop_source(41, 1)


def test_standard_rect():
    assert standard_rect(675, 384) == [675 % 24 * 16, 675 // 24 * 16, 16, 16]
    assert standard_rect(13, 128, 16, 32) == [80, 32, 16, 32]  # a furnace on the craftables sheet


class FakeData:
    def asset(self, name):
        return {"Data/Crops": {"472": {"IsPaddyCrop": False}}}.get(name, {})


class FakeTextures:
    def size(self, name):
        return (384, 624)


def test_scene_dirt_joins_and_crop_sits_on_its_tile():
    import xml.etree.ElementTree as ET
    xsi = 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
    crop = ("<crop><phaseDays><int>1</int><int>1</int><int>99999</int></phaseDays><rowInSpriteSheet>0"
            "</rowInSpriteSheet><phaseToShow>-1</phaseToShow><currentPhase>1</currentPhase><dayOfCurrentPhase>0"
            "</dayOfCurrentPhase><fullGrown>false</fullGrown><flip>true</flip><seedIndex>472</seedIndex>"
            "<indexOfHarvest>24</indexOfHarvest></crop>")

    def dirt(x, y, inner=""):
        return (f'<item><key><Vector2><X>{x}</X><Y>{y}</Y></Vector2></key><value><TerrainFeature xsi:type="HoeDirt">'
                f"<state>0</state>{inner}</TerrainFeature></value></item>")

    loc = ET.fromstring(f"<GameLocation {xsi}><name>Farm</name><terrainFeatures>{dirt(3, 4, crop)}{dirt(4, 4)}"
                        "</terrainFeatures></GameLocation>")
    sprites = Scene(FakeData(), FakeTextures(), "Farm", "spring").read(loc)
    dirt_src = {(s["x"], s["y"]): s["src"] for s in sprites if s["tex"] == "TerrainFeatures/hoeDirt"}
    # east neighbour only -> guide 13 -> (16, 48); west only -> guide 15 -> (48, 48)
    assert dirt_src[(48, 64)] == [16, 48, 16, 16] and dirt_src[(64, 64)] == [48, 48, 16, 16]
    (c,) = [s for s in sprites if s["tex"] == "TileSheets/crops"]
    # phase 1 -> column 2; nudged (3*11 + 4*7) % 10 - 5 = -4 game pixels across, (4*11 + 3*7) % 10 - 5 = 0 down
    assert c["src"] == [32, 0, 16, 32] and c["flip"] is True
    assert (c["x"], c["y"]) == (3 * 16 - 1, 4 * 16 - 16)
    assert sprites[0]["z"] < c["z"]  # dirt under the crop


GAME = find_game()


@pytest.mark.skipif(GAME is None, reason="Stardew Valley isn't installed here")
def test_real_town_map_and_sheet():
    from valley_planner.pictures import map_draw
    tex = Textures(GAME.content, None)
    w, h = tex.size("Maps/spring_outdoorsTileSheet")
    assert (w, h) == (400, 1264)
    town = map_draw(tex, "Maps/Town", "fall")
    assert town["season"] == "fall" and (town["width"], town["height"]) == (130, 110)
    assert "Maps/fall_town" in [s["tex"] for s in town["sheets"]]
    assert [layer["group"] for layer in town["layers"]][:1] == ["Back"]
    assert all(len(layer["tiles"]) == 130 * 110 for layer in town["layers"])
