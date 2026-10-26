"""The game-data cache: decode once, serve from the per-version cache, resolve localized names."""

import struct
from pathlib import Path

from xnbtools import CONTENT, int7, string, xnb

from valley_planner.discover import GameInstall
from valley_planner.gamedata import GameData, cache_root

DICT = CONTENT + "DictionaryReader`2[[System.String, mscorlib],[System.String, mscorlib]]"


def write_dict(path: Path, values: dict[str, str]) -> None:
    body = int7(1) + struct.pack("<i", len(values))
    for k, v in values.items():
        body += int7(2) + string(k) + int7(2) + string(v)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(xnb([DICT, CONTENT + "StringReader"], body))


def fake_install(tmp_path: Path) -> GameInstall:
    root = tmp_path / "game"
    (root / "Content").mkdir(parents=True)
    (root / "StardewValley.GameData.dll").write_bytes(b"not really a dll")
    return GameInstall(root, root / "Content", root)


def test_cache_root_per_platform(tmp_path):
    assert cache_root({"LOCALAPPDATA": "C:/Local"}, "win32") == Path("C:/Local/ValleyPlanner/cache")
    assert cache_root({"XDG_CACHE_HOME": str(tmp_path)}, "linux") == tmp_path / "valley-planner"
    assert cache_root({"VALLEY_PLANNER_CACHE": str(tmp_path)}, "darwin") == tmp_path


def test_decode_once_then_cache(tmp_path):
    install = fake_install(tmp_path)
    write_dict(install.content / "Strings/Objects.xnb", {"Parsnip_Name": "Parsnip"})
    data = GameData(install, tmp_path / "cache")
    assert data.version.startswith("unknown-")  # not a real game: falls back to file size and date
    assert data.text("[LocalizedText Strings\\Objects:Parsnip_Name]") == "Parsnip"
    assert data.text("Plain") == "Plain"
    (install.content / "Strings/Objects.xnb").unlink()  # still served: it's cached now
    again = GameData(install, tmp_path / "cache")
    assert again.asset("Strings/Objects") == {"Parsnip_Name": "Parsnip"}
