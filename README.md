# Valley Planner

An unofficial, save-driven planner for **Stardew Valley** (1.6). Each morning it reads your save and tells you
what to do today, what's coming up, what to plant and sell, and the path to finishing the Community Center
by the deadline you choose.

> Valley Planner is a fan-made tool. It is **not affiliated with or endorsed by ConcernedApe**.
> Stardew Valley® is a trademark of ConcernedApe LLC.

## Your game, your data

- **Nothing from the game ships with Valley Planner.** On first run it reads the game data it needs
  (crops, prices, shops, schedules…) from **your own installed copy**, and keeps the result in a local cache.
- **Your save never leaves your computer.** The planner reads it locally; there is no server and no upload.
- **Vanilla.** No mods needed — it never changes your game or your saves.

It finds Steam (any library folder) and GOG installs, and your saves, on Windows, macOS, Linux and WSL.
If yours are somewhere unusual, set `VALLEY_PLANNER_GAME` (the install folder) or `VALLEY_PLANNER_SAVES`
(the `Saves` folder).

## Install

**Windows, the easy way:** download `valley-planner.exe` from the
[latest release](https://github.com/crypto-morph/valley-planner/releases/latest) and double-click it. A small
window shows where it's running and the planner opens in your browser; close that window to stop it. Windows
may warn about an unrecognised app the first time (it isn't signed): choose "More info", then "Run anyway".

It finds Steam installs and your saves on its own. If yours are somewhere else, set `VALLEY_PLANNER_GAME` to
the game folder or `VALLEY_PLANNER_SAVES` to the Saves folder. `valley-planner --check` shows what it found.

**With Python ([uv](https://docs.astral.sh/uv/)):**

```bash
uvx valley-planner
```

Your to-do lists are kept in your own data folder (`%LOCALAPPDATA%\ValleyPlanner` on Windows); the game's
decoded data is cached beside it, per game version. Nothing leaves your computer.

## Using it while you play

Stardew only saves when you sleep, so the planner always shows the *morning* of the day you're on. Play a
day, go to bed, refresh the page.

## Development

```bash
uv sync
uv run pytest           # tests that need the game are skipped when it isn't installed
uv run ruff check .
uv run valley-planner --dev   # http://127.0.0.1:8765, restarts when the Python changes
```

The page, script and styles are read from disk on every request, so a browser refresh shows those changes.

A Windows `.exe` is built only when asked for: run the CI workflow by hand (Actions → CI → Run workflow, or
`gh workflow run ci.yml`) and download `valley-planner-windows` from that run. Pushing a `v*` tag builds the
`.exe` and the Python package and attaches them to a GitHub release (a tag with a suffix, like
`v0.1.0-beta.2`, is published as a pre-release).

Rules the planner relies on are checked against the game's own behaviour, and each is described in our own
words; no game code, text or files are kept in this repository.

## Licence

[MIT](LICENSE).
