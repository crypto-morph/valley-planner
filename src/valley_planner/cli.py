"""valley-planner: a planner for your own Stardew Valley save. Run it and it opens in your browser."""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import webbrowser

from .discover import find_game, find_saves_root, list_saves

DEFAULT_PORT = 8765


def free_port(preferred: int, tries: int = 20) -> int | None:
    """The preferred port if nothing is listening on it, else the next free one."""
    for port in range(preferred, preferred + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    return None


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

    port = free_port(args.port)
    if port is None:
        print(f"Ports {args.port}-{args.port + 19} are all in use; pick another with --port")
        return 1
    if port != args.port:
        print(f"Port {args.port} is in use by something else, so using {port}")
    url = f"http://127.0.0.1:{port}/"
    config = uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    def open_when_ready() -> None:
        for _ in range(100):
            if server.started:
                print(f"Valley Planner is running at {url} (Ctrl+C to stop)")
                if not args.no_browser:
                    webbrowser.open(url)
                return
            threading.Event().wait(0.1)

    threading.Thread(target=open_when_ready, daemon=True).start()
    server.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
