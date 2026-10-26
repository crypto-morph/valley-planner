"""valley-planner: find the game and your saves. (The planner itself is being ported in.)"""

from __future__ import annotations

import argparse
import sys

from .discover import find_game, find_saves_root, list_saves


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="valley-planner", description=__doc__)
    parser.add_argument("--read", metavar="ASSET", help="print one content file as JSON, e.g. Data/Crops")
    args = parser.parse_args(argv)

    game = find_game()
    saves_root = find_saves_root()
    print(f"Game:  {game.root if game else 'not found — set VALLEY_PLANNER_GAME to the install folder'}")
    print(f"Saves: {saves_root or 'not found — set VALLEY_PLANNER_SAVES to the Saves folder'}")
    if saves_root:
        for save in list_saves(saves_root)[:10]:
            print(f"  - {save.name}")

    if args.read:
        if not game:
            return 1
        import json

        from .xnb.reader import XnbReader
        from .xnb.schema import Schema

        reader = XnbReader(Schema([game.dll_dir / "StardewValley.GameData.dll"]))
        print(json.dumps(reader.read(game.content / f"{args.read}.xnb"), indent=2, ensure_ascii=False))
    return 0 if game and saves_root else 1


if __name__ == "__main__":
    sys.exit(main())
