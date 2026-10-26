"""Community Center bundles: parsing, matching, progress flags, notes and the held-item plan."""

from types import SimpleNamespace

from valley_planner.facts.bundles import Bundles, parse_bundle

DATA = {
    "Pantry/0": "Spring Crops/O 465 20/24 1 0 188 1 0 190 1 0 192 1 0/0///Spring Crops",
    "Pantry/4": "Animal/BO 16 1/186 1 0 182 1 0 -5 1 2 438 1 0/4/3//Animal",
    "Crafts Room/13": "Spring Foraging/O 495 30/16 1 0 18 1 0 20 1 0 22 1 0/0///Spring Foraging",
    "Boiler Room/20": "Blacksmith's/BO 13 1/334 1 0 335 1 0 336 1 0/2///Blacksmith's",
    "Vault/23": "2,500g/O 220 3/-1 2500 2500/4///2,500g",
    "Bulletin Board/35": "Fodder/BO 104 1/262 10 0 178 10 0 613 3 0/3///Fodder",
    "Abandoned Joja Mart/36": "The Missing//348 1 1 807 1 0/1/5//The Missing",
}


def item(iid, stack=1, quality=0, category=None):
    return SimpleNamespace(qualified_id=f"(O){iid}", stack=stack, quality=quality, category=category)


def save(slots=None, events=()):
    return SimpleNamespace(bundle_data=DATA, bundle_slots=slots or {}, events_seen=set(events))


def test_parse_and_match():
    b = parse_bundle("Pantry/4", DATA["Pantry/4"], [False] * 12)
    assert (b.room, b.area, b.slots, b.reward, b.reward_count) == ("Pantry", 0, 3, "(BC)16", 1)
    egg = b.ingredients[2]
    assert egg.category == -5 and egg.item is None
    assert egg.accepts("(O)176", -5, 2) and not egg.accepts("(O)176", -5, 1)  # gold quality asked
    assert egg.accepts("(O)107", -20, 2)  # a Dinosaur Egg counts as an egg
    assert b.ingredients[1].accepts("(O)182", -5, 0) and not b.ingredients[1].accepts("(O)174", -5, 0)


def test_done_versus_counted_and_notes():
    slots = {0: [True] * 12, 23: [True, False, False], 20: [True, True, True] + [False] * 6}
    bs = Bundles.from_save(save(slots))
    spring, vault, smith = bs.by_key["Pantry/0"], bs.by_key["Vault/23"], bs.by_key["Boiler Room/20"]
    assert spring.done and spring.counts_as_complete
    assert vault.done and not vault.counts_as_complete and vault.gold == 2500  # paid: only the first flag
    assert smith.done and not smith.counts_as_complete  # all 3 given shows done, but the rest of its list is false: not counted
    assert bs.complete_count() == 1
    assert bs.notes_shown(1) and bs.notes_shown(0) and not bs.notes_shown(3)  # Boiler Room needs 2
    assert not bs.notes_shown(6)  # the Joja bundle only after the ceremony
    assert Bundles.from_save(save(slots, events={"191393"})).notes_shown(6)


def test_fits_and_plan():
    bs = Bundles.from_save(save({0: [True] * 12}))
    assert [f.bundle.key for f in bs.fits("(O)262", -75, 0)] == []  # Fodder's note isn't up yet
    assert [f.bundle.key for f in bs.fits("(O)262", -75, 0, shown_only=False)] == ["Bulletin Board/35"]
    held = [item(176, 2, 2, -5), item(176, 1, 0, -5), item(186), item(16), item(262, 4, 0, -75)]
    plan = bs.plan(held)
    assert plan.reserved[("Pantry/4", 2)] == [("(O)176", 2, 1)]  # gold egg goes to the gold slot first
    assert plan.reserved[("Pantry/4", 0)] == [("(O)186", 0, 1)]
    assert plan.reserved[("Crafts Room/13", 0)] == [("(O)16", 0, 1)]
    assert plan.partial[("Bulletin Board/35", 0)] == 4  # 4 of 10 Wheat: noted, not reserved
