"""The calendar: festivals, birthdays, derbies, bookseller, green rain, Queen of Sauce — on small fake data."""

from valley_planner.facts.calendar import (
    BOOKSELLER_DAYS,
    GREEN_RAIN_DAYS,
    Calendar,
    bookseller_days,
    green_rain_day,
    qos_rerun_episode,
    qos_sunday_episode,
)
from valley_planner.facts.conditions import When


class Data:
    tables = {
        "Data/Festivals/FestivalDates": {"spring13": "Egg Festival"},
        "Data/Festivals/spring13": {"name": "Egg Festival", "conditions": "Town/900 1400"},
        "Data/PassiveFestivals": {
            "DesertFestival": {"DisplayName": "Desert Festival", "Condition": "LOCATION_ACCESSIBLE Desert",
                               "ShowOnCalendar": True, "Season": "Spring", "StartDay": 15, "EndDay": 17,
                               "StartTime": 1000},
            "TroutDerby": {"DisplayName": "", "ShowOnCalendar": False, "Season": "Summer", "StartDay": 20,
                           "EndDay": 21, "StartTime": 610}},
        "Data/Characters": {
            "Pat": {"DisplayName": "Pat", "BirthSeason": "Spring", "BirthDay": 4},
            "Kent": {"DisplayName": "Kent", "BirthSeason": "Spring", "BirthDay": 4, "UnlockConditions": "YEAR 2"},
            "Sandy": {"DisplayName": "Sandy", "BirthSeason": "Spring", "BirthDay": 5, "Calendar": "HiddenUntilMet"}},
        "Data/TV/CookingChannel": {str(i): f"Recipe {i}/text" for i in range(1, 33)},
    }

    def asset(self, name):
        return self.tables[name]

    def text(self, value):
        return "Trout Derby" if value and "TroutDerby" in value else value


def kinds(events):
    return [(e.kind, e.label) for e in events]


def test_festivals_birthdays_and_who_is_shown():
    c = Calendar(Data())
    egg = c.day(When("spring", 13, 1, 13))
    assert egg[0].label == "Egg Festival" and (egg[0].detail, egg[0].start, egg[0].end) == ("Town", 900, 1400)
    assert c.birthdays(When("spring", 4, 1, 4)) == ["Pat"]  # Kent isn't in the valley until Year 2
    assert c.birthdays(When("spring", 4, 2, 116)) == ["Pat", "Kent"]
    assert c.birthdays(When("spring", 5, 1, 5)) == []  # hidden until met
    assert c.birthdays(When("spring", 5, 1, 5, hearts={"Sandy": 0})) == ["Sandy"]


def test_passive_festivals_and_derbies():
    c = Calendar(Data())
    assert ("passive", "Desert Festival") not in kinds(c.day(When("spring", 16, 1, 16)))  # desert closed
    assert ("passive", "Desert Festival") in kinds(c.day(When("spring", 16, 1, 16, mail={"ccVault"})))
    assert ("derby", "Trout Derby") in kinds(c.day(When("summer", 20, 1, 48)))


def test_queen_of_sauce():
    assert qos_sunday_episode(7) == 1 and qos_sunday_episode(224) == 32 and qos_sunday_episode(231) == 1
    weeks = {i: f"Recipe {i}" for i in range(1, 33)}
    # Wednesday the 10th (day 10): weeks 1 (aired by day 7) only; known or not, it's week 1
    assert qos_rerun_episode(10, 1, set(), weeks) == 1
    assert qos_rerun_episode(10, 1, {"Recipe 1"}, weeks) == 1
    ep = qos_rerun_episode(66, 452453427, {"Recipe 2", "Recipe 3"}, weeks)
    assert ep in set(range(1, 10)) - {2, 3}  # an aired episode you don't know
    tv = [e for e in Calendar(Data()).day(When("spring", 3, 1, 3)) if e.kind == "tv"]
    assert tv == []  # no rerun in the first week


def test_seeded_days_come_from_the_lists():
    for year in (1, 2, 3):
        assert green_rain_day(year, 452453427) in GREEN_RAIN_DAYS
        for season, days in BOOKSELLER_DAYS.items():
            a, b = bookseller_days(season, year, 452453427)
            i = days.index(a)
            assert b == days[(i + len(days) // 2) % len(days)]


def test_later_reruns_assume_sunday_shows_are_watched():
    c = Calendar(Data())
    start = When("spring", 6, 1, 6, game_id=1)
    reruns = [(w.day, e) for w, ev in c.days(start, 26) for e in ev if e.label.startswith("Queen of Sauce rerun")]
    assert reruns and all(not e.sure for _, e in reruns)
    day10 = next(e for d, e in reruns if d == 10)
    assert day10.label.endswith("Recipe 1")


def test_seen_in_a_real_game():
    """Reported by a player on 1.6.15 (game id 452453427): green rain on Summer 18 Year 1, bookseller on Fall 4."""
    assert green_rain_day(1, 452453427) == 18
    assert 4 in bookseller_days("fall", 1, 452453427)
