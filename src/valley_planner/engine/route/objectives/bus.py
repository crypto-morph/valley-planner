"""The bus to the Desert: Pam's bus is repaired with the Community Center's Vault."""

from __future__ import annotations

from ....facts.bundles import VAULT
from ..model import VAULT_STEP, Req
from .base import objective


def _running(r) -> bool:
    return r.planner.unlocks.get("place:Desert").done


@objective("bus", "The bus to the Desert", 112, done=_running)
def bus(r):
    if r.vault_day is not None:
        r.info.append("The bus comes with the Vault, already planned for another goal")
        return [Req(VAULT_STEP, r.vault_day, r.end, [], 0)], 0, []
    paid = sum(b.gold or 0 for b in r.farm.bundles.in_area(VAULT) if not b.done)
    r.info.append(f"The bus to the Desert only runs once the Community Center's Vault is done: {paid:,}g in its "
                  f"bundles, planned here (the Community Center goal shares it). You can pay it once you can read "
                  f"the Junimos' notes")
    return [], paid, []
