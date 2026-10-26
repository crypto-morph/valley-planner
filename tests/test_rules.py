"""The rule registry stays honest: unique ids, known statuses, and every cited test exists."""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = json.loads((ROOT / "rules" / "registry.json").read_text(encoding="utf-8"))
STATUSES = {"verified", "to fix", "planning choice", "unverifiable"}


def test_ids_unique_and_statuses_known():
    ids = [r["id"] for r in REGISTRY["rules"]]
    assert len(ids) == len(set(ids))
    assert {r["status"] for r in REGISTRY["rules"]} <= STATUSES
    assert all(r["summary"].strip() for r in REGISTRY["rules"])


def test_cited_tests_exist():
    defined: dict[str, set[str]] = {}
    for rule in REGISTRY["rules"]:
        for node in rule.get("tests", []):
            file, _, name = node.partition("::")
            if file not in defined:
                tree = ast.parse((ROOT / file).read_text(encoding="utf-8"))
                defined[file] = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
            assert name in defined[file], f"{rule['id']} cites missing test {node}"


def test_fixed_rules_have_no_open_fix():
    for rule in REGISTRY["rules"]:
        if rule["status"] == "verified":
            assert "fix" not in rule, rule["id"]
