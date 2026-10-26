"""valley-planner: a planner for your own Stardew Valley save. Run it and it opens in your browser."""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser

from .discover import find_game, find_saves_root, list_saves

DEFAULT_PORT = 8765


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="valley-planner", description=__doc__)
    parser.add_argument("--check", action="store_true", help="just show where the game and saves were found")
    parser.add_argument("--read", metavar="ASSET", help="print one content file as JSON, e.g. Data/Crops")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"port to serve on (default {DEFAULT_PORT})")
    parser.add_argument("--no-browser", action="store_true", help="don't open a browser window")
    args = parser.parse_args(argv)

    game = find_game()
    saves_root = find_saves_root()
    print(f"Game:  {game.root if game else 'not found: set VALLEY_PLANNER_GAME to the install folder'}")
    print(f"Saves: {saves_root or 'not found: set VALLEY_PLANNER_SAVES to the Saves folder'}")
    if args.check or args.read:
        if saves_root:
            for save in list_saves(saves_root)[:10]:
                print(f"  - {save.name}")
        if args.read and game:
            import json

            from .gamedata import GameData

            print(json.dumps(GameData(game).asset(args.read), indent=2, ensure_ascii=False))
        return 0 if game and saves_root else 1
    if not game:
        return 1

    import uvicorn

    from .app import create_app

    url = f"http://127.0.0.1:{args.port}/"
    print(f"Valley Planner is running at {url} (Ctrl+C to stop)")
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    uvicorn.run(create_app(), host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
