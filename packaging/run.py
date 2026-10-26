"""Entry point for the single-file build (PyInstaller needs a script, not a package module)."""

from valley_planner.cli import main

raise SystemExit(main())
