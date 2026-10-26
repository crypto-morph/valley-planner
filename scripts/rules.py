"""Maintainer tool: keep the rule registry honest against the game's own code.

Every game rule the planner relies on is listed in rules/registry.json with
the game methods it was checked against. This script, run on a machine with
the game decompiled locally (never committed), fingerprints those methods:
a SHA-256 of each method's decompiled text with whitespace removed. Only the
hashes are stored (rules/fingerprints.json). After a game update, `check`
names every rule whose methods changed, so it gets re-verified.

    uv run python scripts/rules.py check  --decompiled DIR   # what changed?
    uv run python scripts/rules.py update --decompiled DIR   # after re-verifying
    uv run python scripts/rules.py docs                      # regenerate RULES.md

A method is named "Namespace.Type.Method" (or "...Type.Method/2" to pick the
second overload in file order). DIR is an ILSpy project decompile
(`ilspycmd -p -o DIR "Stardew Valley.dll"`), plus the GameData assembly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "rules" / "registry.json"
FINGERPRINTS = ROOT / "rules" / "fingerprints.json"
DOCS = ROOT / "RULES.md"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _type_file(decompiled: Path, type_name: str) -> Path | None:
    """ILSpy project layout: <assembly>/<Name.Space>/<Type>.cs (nested types live in their parent's file)."""
    parts = type_name.split(".")
    for cut in range(len(parts), 0, -1):  # Namespace.Outer.Inner -> try Outer.cs
        ns, typ = ".".join(parts[:cut - 1]), parts[cut - 1]
        for assembly in (p for p in decompiled.iterdir() if p.is_dir()):
            candidate = (assembly / ns if ns else assembly) / f"{typ}.cs"
            if candidate.is_file():
                return candidate
    return None


def method_text(decompiled: Path, method: str) -> str | None:
    """The decompiled source of one method (signature through closing brace)."""
    name, _, nth = method.partition("/")
    type_name, _, member = name.rpartition(".")
    path = _type_file(decompiled, type_name)
    if path is None:
        return None
    src = path.read_text(encoding="utf-8", errors="replace")
    modifiers = (r"(?:(?:public|private|protected|internal|static|virtual|override|abstract|sealed|new|async"
                 r"|unsafe|extern)\s+)+")
    pattern = re.compile(rf"^[ \t]*{modifiers}[\w<>\[\],.? ]*?\b{re.escape(member)}\s*(?:<[^>]*>)?\s*\(", re.M)
    matches = [m for m in pattern.finditer(src)]
    index = int(nth) - 1 if nth else 0
    if index >= len(matches):
        return None
    start = matches[index].start()
    brace = src.find("{", matches[index].end())
    arrow = src.find("=>", matches[index].end())
    if arrow != -1 and (brace == -1 or arrow < brace):  # expression-bodied
        return src[start:src.find(";", arrow) + 1]
    depth, i = 0, brace
    while i < len(src):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1
    return None


def fingerprint(text: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", "", text).encode("utf-8")).hexdigest()


def methods(registry: dict) -> list[str]:
    return sorted({m for rule in registry.get("rules", []) for m in rule.get("checked_against", [])})


def check(decompiled: Path, update: bool) -> int:
    registry, prints = load(REGISTRY), load(FINGERPRINTS)
    new, missing, changed = {}, [], []
    for m in methods(registry):
        text = method_text(decompiled, m)
        if text is None:
            missing.append(m)
            continue
        new[m] = fingerprint(text)
        if prints.get(m) and prints[m] != new[m]:
            changed.append(m)
    stale = [r["id"] for r in registry.get("rules", []) if set(r.get("checked_against", [])) & set(changed)]
    unprinted = [m for m in new if m not in prints]
    for label, items in (("Methods not found", missing), ("Changed methods", changed),
                         ("Rules to re-verify", stale), ("Not fingerprinted yet", unprinted)):
        if items:
            print(f"{label}:\n  " + "\n  ".join(items))
    if update:
        FINGERPRINTS.parent.mkdir(parents=True, exist_ok=True)
        FINGERPRINTS.write_text(json.dumps(dict(sorted({**prints, **new}.items())), indent=1) + "\n", encoding="utf-8")
        print(f"Fingerprinted {len(new)} methods.")
        return 0 if not missing else 1
    return 1 if (missing or changed or unprinted) else 0


def docs() -> int:
    registry = load(REGISTRY)
    lines = ["# Game rules", "",
             "Every rule the planner relies on, in our own words, and the game code or data it was checked against.",
             f"Checked against Stardew Valley {registry.get('game_version', '?')}. "
             "`scripts/rules.py check` flags any rule whose game code changes in an update.", ""]
    by_area: dict[str, list[dict]] = {}
    for rule in registry.get("rules", []):
        by_area.setdefault(rule["area"], []).append(rule)
    for area, rules in by_area.items():
        lines += [f"## {area}", "", "| Rule | What the game does | Checked against | Status |", "|---|---|---|---|"]
        for r in rules:
            against = "<br>".join(f"`{x}`" for x in r.get("checked_against", []) + r.get("data", []))
            lines.append(f"| `{r['id']}` | {r['summary']} | {against} | {r.get('status', 'unverified')} |")
        lines.append("")
    DOCS.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {DOCS.name}: {sum(len(v) for v in by_area.values())} rules")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["check", "update", "docs"])
    ap.add_argument("--decompiled", type=Path, help="folder holding the local ILSpy decompile")
    args = ap.parse_args()
    if args.command == "docs":
        return docs()
    if not args.decompiled or not args.decompiled.is_dir():
        ap.error("--decompiled DIR is required (a local decompile; never commit it)")
    return check(args.decompiled, update=args.command == "update")


if __name__ == "__main__":
    sys.exit(main())
