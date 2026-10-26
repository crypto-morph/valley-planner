"""Villager schedules: the game's key order and its schedule language, on small fake schedules."""

from valley_planner.facts.conditions import When
from valley_planner.facts.schedules import Schedules, Situation, time_label


class Data:
    def __init__(self, schedules: dict[str, dict], characters: dict | None = None, festivals: dict | None = None):
        self.tables = {f"Characters/schedules/{k}": v for k, v in schedules.items()}
        self.tables["Data/Characters"] = characters or {}
        self.tables["Data/PassiveFestivals"] = festivals or {}

    def asset(self, name):
        return self.tables[name]

    def has(self, name):
        return name in self.tables


HOME = {"Pat": {"Home": [{"Location": "PatHouse", "Tile": {"X": 3, "Y": 4}}]}}


def day(season="spring", d=10, *, mail=(), events=(), dp=None, hearts=None):
    return When(season, d, 1, dp if dp is not None else d, mail=set(mail), events_seen=set(events),
                hearts=hearts or {})


def stops(schedule):
    return [(s.time, s.location, s.x, s.y) for s in schedule.stops]


def test_key_order_hearts_and_first_existing_wins():
    data = Data({"Pat": {"spring_Wed_4": "900 Town 1 1", "Wed_2": "900 Beach 1 1", "spring": "900 Forest 1 1",
                         "10": ""}}, HOME)
    s = Schedules(data)
    assert s.today("Pat", Situation(day(d=3), hearts=5))[0].key == "spring"  # 5 hearts tries 5, 3, 1: never _4 or Wed_2
    keys = s.candidates("Pat", Situation(day(d=3), hearts=5))
    assert keys[:7] == ["spring_3", "3_5", "3_4", "3_3", "3_2", "3_1", "3"]  # day-and-hearts goes down one at a time
    i = keys.index("spring_Wed_5")
    assert keys[i:i + 4] == ["spring_Wed_5", "spring_Wed_3", "spring_Wed_1", "spring_Wed"]  # weekday ones by two
    assert s.today("Pat", Situation(day(d=3), hearts=4))[0].key == "spring_Wed_4"
    empty = s.today("Pat", Situation(day(d=10)))[0]
    assert empty.key == "10" and empty.stops == ()  # the first key that exists wins, even if empty


def test_rain_is_a_coin_flip():
    data = Data({"Pat": {"rain2": "900 Library 1 1", "rain": "900 Home 1 1", "spring": "900 Town 1 1"}}, HOME)
    both = Schedules(data).today("Pat", Situation(day(), raining=True))
    assert [(d.key, d.chance) for d in both] == [("rain2", 0.5), ("rain", 0.5)]


def test_entry_format():
    data = Data({"Pat": {"spring": "0 Town 5 5/a1200 Saloon 8 9 3 pat_sit/1400 10 11/2530 bed"}}, HOME)
    sched = Schedules(data).today("Pat", Situation(day()))[0]
    first, second, third = sched.stops
    assert first.arrive_by and (first.location, first.x, first.y, first.facing, first.behavior) == ("Saloon", 8, 9, 3, "pat_sit")
    assert (second.location, second.x, second.y, second.facing) == ("Saloon", 10, 11, 2)  # location and facing left out
    assert third.location == "PatHouse" and third.time == 2530  # bed: home, when 'default'/'spring' doesn't say
    assert time_label(2530) == "1:30 AM" and time_label(1330) == "1:30 PM" and time_label(600) == "6:00 AM"


def test_goto_mail_and_not_friendship():
    sched = {"spring": "900 Town 1 1", "summer": "900 Beach 1 1", "Sun": "GOTO season",
             "Mon": "MAIL saloonSportsRoom/GOTO spring/1100 Saloon 1 1", "Tue": "NOT friendship Leah 6/900 Forest 1 1",
             "Wed": "GOTO no_schedule"}
    s = Schedules(Data({"Pat": sched}, HOME))
    assert stops(s.today("Pat", Situation(day("summer", 7)))[0]) == [(900, "Beach", 1, 1)]  # Sunday: GOTO season
    assert stops(s.today("Pat", Situation(day(d=8)))[0]) == [(900, "Town", 1, 1)]  # no mail: the next command
    assert stops(s.today("Pat", Situation(day(d=8, mail={"saloonSportsRoom"})))[0]) == [(1100, "Saloon", 1, 1)]
    assert stops(s.today("Pat", Situation(day(d=9)))[0]) == [(900, "Forest", 1, 1)]
    assert stops(s.today("Pat", Situation(day(d=9, hearts={"Leah": 6})))[0]) == [(900, "Town", 1, 1)]  # -> spring
    assert s.today("Pat", Situation(day(d=10)))[0].stops == ()  # no_schedule


def test_closed_places():
    sched = {"spring": "900 Town 1 1", "default": "900 Home 2 2", "Mon": "900 JojaMart 5 5",
             "JojaMart_Replacement": "Town 7 7 2", "Tue": "900 CommunityCenter 5 5/1200 Saloon 1 1",
             "Wed": "900 Railroad 5 5"}
    s = Schedules(Data({"Pat": sched}, HOME))
    restored = {"191393"}
    assert stops(s.today("Pat", Situation(day(d=1)))[0]) == [(900, "JojaMart", 5, 5)]
    assert stops(s.today("Pat", Situation(day(d=1, events=restored)))[0]) == [(900, "Town", 7, 7)]  # stand-in spot
    assert stops(s.today("Pat", Situation(day(d=2)))[0]) == [(900, "Home", 2, 2)]  # CC not restored: whole day -> default
    assert stops(s.today("Pat", Situation(day("summer", 3, dp=31)))[0]) == [(900, "Home", 2, 2)]  # Railroad: DaysPlayed > 31
    assert stops(s.today("Pat", Situation(day("summer", 3, dp=32)))[0]) == [(900, "Railroad", 5, 5)]


def test_passive_festival_keys():
    fest = {"DesertFestival": {"Season": "Spring", "StartDay": 15, "EndDay": 17, "Condition": "LOCATION_ACCESSIBLE Desert"}}
    s = Schedules(Data({"Pat": {"spring": "900 Town 1 1", "DesertFestival_2": "900 Desert 1 1"}}, HOME, fest))
    assert s.today("Pat", Situation(day(d=16)))[0].key == "spring"  # the desert isn't open
    assert s.today("Pat", Situation(day(d=16, mail={"ccVault"})))[0].key == "DesertFestival_2"
