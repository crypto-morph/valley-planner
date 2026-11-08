"""Artifact and seed spots: the draw order of a dig, with a made-up drop table, then the real one when it's here."""

import pytest
from shared import shared_data

from valley_planner.facts import artifact_spots as a
from valley_planner.facts.rng import NetRandom, day_save_random

GAME = 453557957

# A made-up table in the game's shape: Default's entries, and one place's own.
LOCATIONS = {
    "Default": {"ArtifactSpots": [
        {"Id": "book", "ItemId": "LOST_BOOK_OR_ITEM (O)B", "Chance": 0.2, "Precedence": -100,
         "Condition": "!PLAYER_LOCATION_NAME Current Farm"},
        {"Id": "arch", "ItemId": "RANDOM_ARTIFACT_FOR_DIG_SPOT", "Precedence": -100},
        {"Id": "winter", "ItemId": "(O)W", "Chance": 0.5, "Precedence": -100,
         "Condition": "LOCATION_SEASON Here Winter, RANDOM 0.4"},
        {"Id": "note", "ItemId": "SECRET_NOTE_OR_ITEM (O)S", "Chance": 0.11, "Precedence": 100},
        {"Id": "last", "ItemId": "(O)C", "MinStack": 1, "MaxStack": 3, "Precedence": 100},
    ]},
    "Village": {"ArtifactSpots": [{"Id": "own", "ItemId": "(O)V", "Chance": 0.3}]},
    "Farm_Standard": {"ArtifactSpots": [{"Id": "farm", "ItemId": "(O)F", "Chance": 0.5}]},
    "Farm_Beach": {"ArtifactSpots": [{"Id": "beach farm", "ItemId": "(O)G", "Chance": 0.5}]},
}
OBJECTS = {
    "A1": {"Name": "Old Thing", "Type": "Arch", "ArtifactSpotChances": {"Village": 0.03999999910593033}},
    "A2": {"Name": "Older Thing", "Type": "Arch", "ArtifactSpotChances": {"Village": 0.019999999552965164}},
    "M1": {"Name": "Shiny", "Type": "Minerals", "ArtifactSpotChances": {"Village": 1.0}},  # not Arch: never
}


def digger(**kw):
    base = dict(days_played=40, game_id=GAME, season="summer", day=5, lost_books=21)
    return a.Digger(**{**base, **kw})


def ids(drops):
    return [d.id for d in drops]


def trace(x, y, d, *, rare=True):
    """The dig worked by hand, for the made-up table in the Village, summer, no mail: the order the game draws in."""
    r = day_save_random(d.days_played, d.game_id, x * 2000, y, d.totems * 777)
    if rare:
        if r.next_double() < 0.018 or r.next_double() < 0.0054:
            return None  # a cosmetic item or a skill book: let the caller pick another tile
    if r.next_double() < 0.2:  # Default's lost book entry (condition passes off the Farm), a query: Next(1)
        r.next(1)
        return ["(O)B"]
    for chance in (0.03999999910593033, 0.019999999552965164):  # the Arch objects, in data order
        if r.next_double() < chance:
            r.next(1)
            return ["(O)A1" if chance > 0.03 else "(O)A2"]
    if r.next_double() < 0.5:  # winter entry: chance drawn, then the season fails before RANDOM draws
        pass
    if r.next_double() < 0.3:
        return ["(O)V"]
    if r.next_double() < 0.11:
        r.next(1)
        return ["(O)S"]
    return ["(O)C"]


def test_draw_order_matches_a_hand_trace():
    d = digger()
    checked = 0
    for x in range(40):
        for y in range(10):
            want = trace(x, y, d)
            if want is None:
                continue
            drops, sure, _ = a.dig_artifact("Village", x, y, d, LOCATIONS, OBJECTS)
            if drops and drops[0].id.startswith("(O)SkillBook"):
                continue
            assert ids(drops) == want, (x, y)
            assert sure
            checked += 1
    assert checked > 300


def test_clay_like_last_entry_draws_its_stack():
    d = digger()
    counts = set()
    for x in range(60):
        drops, _, _ = a.dig_artifact("Village", x, 3, d, LOCATIONS, OBJECTS)
        counts |= {dr.count for dr in drops if dr.id == "(O)C"}
    assert counts == {1, 2, 3}


def test_precedence_sorts_default_and_own_entries_together():
    own_first = {**LOCATIONS, "Village": {"ArtifactSpots": [{"Id": "own", "ItemId": "(O)V", "Precedence": -500}]}}
    for x in range(30):
        drops, _, _ = a.dig_artifact("Village", x, 1, digger(), own_first, OBJECTS)
        assert ids(drops)[-1] in ("(O)V", "")  # Chance 1 and first in line: always, unless a cosmetic item stops it


def test_farm_uses_its_farm_type_entry_and_never_the_lost_book():
    seen_std, seen_beach = set(), set()
    for x in range(80):
        seen_std |= set(ids(a.dig_artifact("Farm", x, 2, digger(lost_books=0), LOCATIONS, OBJECTS)[0]))
        seen_beach |= set(ids(a.dig_artifact("Farm", x, 2, digger(farm_key="Beach"), LOCATIONS, OBJECTS)[0]))
    assert "(O)F" in seen_std and "(O)G" not in seen_std and "(O)102" not in seen_std
    assert "(O)G" in seen_beach and "(O)F" not in seen_beach


def test_lost_books_until_21_found():
    early = [ids(a.dig_artifact("Village", x, 4, digger(lost_books=5), LOCATIONS, OBJECTS)[0]) for x in range(80)]
    late = [ids(a.dig_artifact("Village", x, 4, digger(lost_books=21), LOCATIONS, OBJECTS)[0]) for x in range(80)]
    assert any("(O)102" in got for got in early) and not any("(O)B" in got for got in early)
    assert any("(O)B" in got for got in late) and not any("(O)102" in got for got in late)
    assert early == [[("(O)102" if i == "(O)B" else i) for i in got] for got in late]  # same draws either way


def test_winter_entry_draws_its_random_only_in_winter():
    """In summer the condition fails on the season before RANDOM draws, so dropping the entry changes nothing."""
    without = {**LOCATIONS, "Default": {"ArtifactSpots": [e for e in LOCATIONS["Default"]["ArtifactSpots"]
                                                          if e["Id"] != "winter"]}}
    winter_free = [ids(a.dig_artifact("Village", x, 5, digger(), without, OBJECTS)[0]) for x in range(60)]
    summer = [ids(a.dig_artifact("Village", x, 5, digger(), LOCATIONS, OBJECTS)[0]) for x in range(60)]
    assert winter_free != summer  # its Chance is still drawn...
    winter = [ids(a.dig_artifact("Village", x, 5, digger(season="winter"), LOCATIONS, OBJECTS)[0]) for x in range(200)]
    assert any("(O)W" in got for got in winter) and not any("(O)W" in got for got in summer)


def test_secret_note_is_unsure_only_with_the_glass_and_notes_left():
    def note_spots(**kw):
        out = []
        for x in range(300):
            drops, sure, notes = a.dig_artifact("Village", x, 6, digger(**kw), LOCATIONS, OBJECTS)
            if "(O)S" in ids(drops):
                out.append((drops, sure, notes))
        return out
    plain = note_spots()
    assert plain and all(sure for _, sure, _ in plain)
    glass = note_spots(mail=frozenset({"HasMagnifyingGlass"}), notes_left=3)
    assert glass and all(not sure and ids(drops)[-2:] == ["(O)79", "(O)S"] for drops, sure, _ in glass)
    done = note_spots(mail=frozenset({"HasMagnifyingGlass"}), notes_left=0)
    assert [ids(d) for d, _, _ in done] == [ids(d) for d, _, _ in plain]


def test_archaeologist_doubles_artifact_chances():
    def rate(arch):
        hits = sum(any(i in ("(O)A1", "(O)A2") for i in ids(a.dig_artifact("Village", x, y, digger(archaeologist=arch),
                                                                            LOCATIONS, OBJECTS)[0]))
                   for x in range(80) for y in range(50))
        return hits / 4000
    assert 1.6 < rate(True) / rate(False) < 2.4


def test_generous_hoe_adds_a_second_copy_sometimes():
    extra = 0
    for x in range(100):
        plain = a.dig_artifact("Village", x, 7, digger(), LOCATIONS, OBJECTS)[0]
        gen = a.dig_artifact("Village", x, 7, digger(generous=True), LOCATIONS, OBJECTS)[0]
        assert ids(gen)[:len(plain)] == ids(plain)  # the coin flip comes after the first item
        extra += len(gen) > len(plain)
    assert 25 < extra < 75


def test_cosmetic_item_stops_the_forecast():
    d = digger()
    for x in range(400):
        drops, sure, notes = a.dig_artifact("Village", x, 8, d, LOCATIONS, OBJECTS)
        if any(dr.id == "" for dr in drops):
            assert not sure and drops[-1].id == "" and notes
            return
    pytest.fail("no cosmetic item in 400 tiles")


def test_qi_plane_mail_draws_first():
    d = digger(mail=frozenset({"sawQiPlane"}))
    boxes = [a.dig_artifact("Village", x, 9, d, LOCATIONS, OBJECTS)[0] for x in range(400)]
    with_box = [b for b in boxes if b and b[0].id == "(O)MysteryBox"]
    assert 5 < len(with_box) < 40 and all(b[0].count in (1, 2) for b in with_box)


def test_island_spots_roll_their_own_extras_first():
    d = digger(coconut_cracked=True)
    first = {a.dig_artifact("IslandSouth", x, 3, d, LOCATIONS, OBJECTS, xsi_type="IslandSouth")[0][0].id
             for x in range(200)}
    assert {"(O)791", "(O)831", "(O)275"} <= first


def test_book_of_defense_roll():
    d = digger(dug=0, digs_today=2)
    r = NetRandom(1)
    assert a.dig_book(r, d) == (False, True) and r.draws == 0  # counts 1 and 2: no roll
    assert a.dig_book(NetRandom(1), digger(dug=1, digs_today=3))[0] is None  # 2 if first, 4 if last
    roll = NetRandom(5).next_double()
    got, drew = a.dig_book(NetRandom(5), digger(dug=10, digs_today=1))
    assert drew and got == (roll < 0.008 + 11 * 0.002)
    got, _ = a.dig_book(NetRandom(5), digger(dug=10, digs_today=1, mail=frozenset({"DefenseBookDropped"})))
    assert got == (roll < 0.013)


def test_seed_spot_seeds_and_count():
    assert a.raccoon_seed("spring", 23) == "(O)CarrotSeeds"
    assert a.raccoon_seed("spring", 24) == "(O)SummerSquashSeeds"
    assert a.raccoon_seed("summer", 21) == "(O)BroccoliSeeds"
    assert a.raccoon_seed("winter", 25) == "(O)CarrotSeeds"
    d = digger(dug=50)
    spot = a.dig("Village", (12, 34), "seed", d, LOCATIONS, OBJECTS)
    r = a.book_roll(12, 34, d)
    r.next_double()  # the book
    n = r.next(2, 4)
    while r.next_double() < 0.1:
        n += 1
    assert spot.drops[-1] == a.Drop("(O)SummerSquashSeeds", "", n)
    counts = {a.dig("Village", (x, 1), "seed", d, LOCATIONS, OBJECTS).drops[-1].count for x in range(200)}
    assert {2, 3, 4} <= counts and min(counts) == 2


def test_first_digs_ever_make_seed_counts_unsure():
    spot = a.dig("Village", (3, 3), "seed", digger(dug=1, digs_today=4), LOCATIONS, OBJECTS)
    assert not spot.sure and spot.notes


def test_reachable():
    d = digger(mail=frozenset({"willyBoatFixed"}), season="spring", day=16)
    fest = {"DesertFestival": {"Season": "Spring", "StartDay": 15, "EndDay": 17}}
    assert a.reachable("Town", d) is True
    assert a.reachable("IslandSouth", d) is True and a.reachable("IslandWest", d) is False
    assert a.reachable("IslandSouth", digger()) is False
    assert a.reachable("DesertFestival", d, fest) is False  # no bus yet
    assert a.reachable("DesertFestival", digger(mail=frozenset({"ccVault"}), season="spring", day=16), fest)
    assert not a.reachable("DesertFestival", digger(mail=frozenset({"ccVault"}), season="spring", day=20), fest)


# --- the real table and saves, when the game is here ----------------------------------------------------------


@pytest.fixture(scope="module")
def data():
    try:
        return shared_data()
    except RuntimeError:
        pytest.skip("no game here")


def test_real_table_rates(data):
    """Town in spring with Lost Books left: every dig gives something; the rare draws come at their rates."""
    locations, objects = data.asset("Data/Locations"), data.asset("Data/Objects")
    d = digger(season="spring", lost_books=0)
    n, books, cosmetic = 0, 0, 0
    for x in range(50):
        for y in range(40):
            drops, sure, _ = a.dig_artifact("Town", x, y, d, locations, objects)
            assert drops
            n += 1
            books += "(O)102" in ids(drops)
            cosmetic += not sure
    assert 0.2 < books / n < 0.33  # Default's 0.2, then Town's own 0.2 further down
    assert 0.008 < cosmetic / n < 0.03  # 0.018


def test_spots_in_real_saves(data):
    from valley_planner.discover import find_saves_root, list_saves
    from valley_planner.save import read_save
    root = find_saves_root()
    if root is None:
        pytest.skip("no saves here")
    found = 0
    for path in list_saves(root):
        try:
            save = read_save(path, data)
        except Exception:  # noqa: BLE001 — old or odd files aren't this test's business
            continue
        if not save.game_version.startswith("1.6"):
            continue
        for spot in a.spots(save, data):
            found += 1
            assert spot.kind in ("artifact", "seed") and spot.drops
            assert all(d.name for d in spot.drops)
            assert spot.sure == (all(d.sure for d in spot.drops) and not spot.notes) or not spot.sure
    if not found:
        pytest.skip("no spots in these saves")
