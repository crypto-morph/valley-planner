"""Your quests: the quest log (Help Wanted from the board, the letters' requests, the story's), what each needs,
whether you hold it and where, and the days left; plus the special orders taken and what's on Lewis's board.

Wording comes from the game's own data at runtime (Data/Quests: type/title/description/objective/...; a delivery's
fifth field is "who item", a lost item's is "who item where x y"; Strings/SpecialOrderStrings for orders).
"""

from __future__ import annotations

from .farm import Farm
from .morning import HOMES, special_orders

TYPES = {"ItemDeliveryQuest": "deliver", "LostItemQuest": "lost", "SlayMonsterQuest": "slay", "FishingQuest": "fish",
         "ResourceCollectionQuest": "gather", "SocializeQuest": "social", "Quest": "story"}


def view(farm: Farm) -> dict:
    data = farm.data.asset("Data/Quests") or {}
    out = []
    for q in farm.save.quests:
        if q["completed"]:
            continue
        raw = (data.get(q["id"]) or "").split("/")
        objective = raw[3] if len(raw) > 3 and raw[3] else ""
        extra = raw[4].split() if len(raw) > 4 else []
        who = q["target"] or (extra[0] if extra and q["type"] in ("ItemDeliveryQuest", "LostItemQuest") else "")
        item = q["item_id"] or (extra[1].removeprefix("(O)") if len(extra) > 1 else "")
        row = {"id": q["id"], "kind": TYPES.get(q["type"], "story"), "title": q["title"], "who": who,
               "objective": objective, "reward": q["reward"], "daily": q["daily"],
               "days_left": q["days_left"] if q["daily"] or q["days_left"] > 0 else None,
               "item": farm.name(f"(O){item}") if item else "", "have": 0, "where": [], "deliver_to": "", "hint": ""}
        if item and q["type"] == "ItemDeliveryQuest":
            qid = f"(O){item}"
            row["have"] = farm.held().get(qid, 0)
            row["where"] = farm.where_held(qid)
            if row["have"] >= q["count"]:
                row["deliver_to"] = HOMES.get(who, who)
        if q["type"] == "LostItemQuest" and len(extra) > 2:
            row["hint"] = f"it's at {farm.place(extra[2])}"
        out.append(row)
    out.sort(key=lambda r: (r["days_left"] is None, r["days_left"] or 0, not r["deliver_to"]))
    taken = {o["key"] for o in getattr(farm.save, "special_orders", [])}
    strings = farm.data.asset("Strings/SpecialOrderStrings") or {}
    board = [{"name": strings.get(o["name"].strip("[]"), o["name"]), "who": o["requester"], "reward": o["money"]}
             for o in getattr(farm.save, "special_orders_board", [])
             if o["key"] not in taken and o["type"] not in ("Qi", "QiChallenge")]
    return {"quests": out, "orders": special_orders(farm), "board": board}
