"""Finding the install and the saves, on fake folders laid out like each platform."""

from pathlib import Path

from valley_planner.discover import as_install, find_game, list_saves, save_roots, steam_libraries, wsl_path


def make_game(root: Path, mac: bool = False) -> Path:
    content = root / ("Contents/Resources/Content" if mac else "Content")
    (content / "Data").mkdir(parents=True)
    (content / "Data" / "Crops.xnb").write_bytes(b"XNB")
    dlls = root / "Contents/MacOS" if mac else root
    dlls.mkdir(parents=True, exist_ok=True)
    (dlls / "StardewValley.GameData.dll").write_bytes(b"MZ")
    return root


def test_wsl_path():
    assert wsl_path(r"D:\SteamLibrary") == Path("/mnt/d/SteamLibrary")
    assert wsl_path("C:\\") == Path("/mnt/c")


def test_linux_default_steam(tmp_path):
    game = make_game(tmp_path / ".local/share/Steam/steamapps/common/Stardew Valley")
    found = find_game(env={}, home=tmp_path, platform="linux", wsl=False)
    assert found and found.root == game


def test_second_steam_library(tmp_path):
    steam = tmp_path / ".local/share/Steam"
    (steam / "steamapps").mkdir(parents=True)
    lib = tmp_path / "games"
    (steam / "steamapps/libraryfolders.vdf").write_text(f'"libraryfolders" {{ "1" {{ "path" "{lib}" }} }}')
    make_game(lib / "steamapps/common/Stardew Valley")
    assert steam_libraries(steam)[1] == lib
    assert find_game(env={}, home=tmp_path, platform="linux", wsl=False).root == lib / "steamapps/common/Stardew Valley"


def test_mac_bundle_layout(tmp_path):
    game = make_game(tmp_path / "Library/Application Support/Steam/steamapps/common/Stardew Valley", mac=True)
    found = find_game(env={}, home=tmp_path, platform="darwin", wsl=False)
    assert found and found.content == game / "Contents/Resources/Content"


def test_env_override(tmp_path):
    game = make_game(tmp_path / "anywhere")
    assert find_game(env={"VALLEY_PLANNER_GAME": str(game)}, home=tmp_path, platform="linux", wsl=False).root == game
    assert as_install(tmp_path) is None


def test_save_roots_and_listing(tmp_path):
    roots = save_roots(env={"APPDATA": str(tmp_path / "Roaming")}, home=tmp_path, platform="win32", wsl=False)
    assert roots[-1] == tmp_path / "Roaming/StardewValley/Saves"
    saves = tmp_path / "Saves"
    for name in ("Farm_1", "Farm_2"):
        (saves / name).mkdir(parents=True)
        (saves / name / name).write_text("<SaveGame/>")
    (saves / "not_a_save").mkdir()
    assert {p.name for p in list_saves(saves)} == {"Farm_1", "Farm_2"}
