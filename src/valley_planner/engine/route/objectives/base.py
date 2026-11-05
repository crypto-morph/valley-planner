"""What an objective is: one goal the route can plan, kept in its own module.

A module registers its objectives with `objective(...)`. `plan` gives (requirements, gold that's simply paid,
notes) for a Router, and `done` says whether the save has it. `needs` names the goals that must come first:
choosing a goal brings them into the plan ahead of it, and its steps wait for them. Adding a goal means adding a
module here and a line in ORDER; nothing in the Router changes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

REGISTRY: dict[str, Objective] = {}


@dataclass(frozen=True)
class Objective:
    id: str
    label: str
    days: int  # default deadline, as days into the year
    plan: Callable
    done: Callable
    needs: tuple[str, ...] = ()


def objective(oid: str, label: str, days: int, *, done: Callable, needs: tuple[str, ...] = ()) -> Callable:
    def add(plan: Callable) -> Callable:
        REGISTRY[oid] = Objective(oid, label, days, plan, done, needs)
        return plan
    return add
