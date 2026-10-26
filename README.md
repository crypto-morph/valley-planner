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

**Windows, the easy way:** download `ValleyPlanner.exe` from the latest release and double-click it.
It opens the planner in your browser.

**With Python ([uv](https://docs.astral.sh/uv/)):**

```bash
uvx valley-planner
```

## Using it while you play

Stardew only saves when you sleep, so the planner always shows the *morning* of the day you're on. Play a
day, go to bed, refresh the page.

## Development

```bash
uv sync
uv run pytest           # tests that need the game are skipped when it isn't installed
uv run ruff check .
uv run valley-planner   # serves on http://localhost:8766
```

Rules the planner relies on are checked against the game's own behaviour, and each is described in our own
words; no game code, text or files are kept in this repository.

## Licence

[MIT](LICENSE).
