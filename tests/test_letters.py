"""Story letters (facts/letters.py): what a dated letter will ask for, and which are still to come."""

from types import SimpleNamespace

from valley_planner.facts.letters import coming, letters


class Data:
    ASSETS = {
        "Data/mail": {"summer_20_1": "Hello @...%item quest 104 %%[#]Crop Research", "spring_15_2": "%item quest 116 %%",
                      "winter_21_1": "%item quest 113 %%", "summer_3_1": "%item quest 102 %%", "fall_2": "no quest",
                      "spring_2_1": "%item quest 13 %%"},
        "Data/Quests": {"104": "ItemDelivery/Crop Research/d/o/Demetrius 254/-1/550/-1/true",
                        "116": "ItemDelivery/Granny's Gift/d/o/Evelyn 20/-1/500/-1/true",
                        "113": "ItemDelivery/Robin's Request/d/o/Robin 709 10/-1/500/-1/true",
                        "102": "LostItem/Mayor's Shorts/d/o/Lewis 789 AnimalShop 13 7/-1/750/-1/true",
                        "13": "Basic/Meet/d/o/null/-1/0/-1/false"},
    }

    def asset(self, name):
        return self.ASSETS[name]


def test_letters_are_dated_deliveries_only():
    got = letters(Data())
    assert [(x.title, x.who, x.item, x.count, x.reward, x.days_played) for x in got] == [
        ("Crop Research", "Demetrius", "(O)254", 1, 550, 48),
        ("Robin's Request", "Robin", "(O)709", 10, 500, 105),
        ("Granny's Gift", "Evelyn", "(O)20", 1, 500, 127),
    ]


def test_coming_skips_read_and_past_letters_but_not_unread_mail():
    save = SimpleNamespace(mail={"winter_21_1"}, mailbox=set())
    assert [x.title for x in coming(Data(), save, 30)] == ["Crop Research", "Granny's Gift"]
    assert [x.title for x in coming(Data(), save, 50)] == ["Granny's Gift"]  # Summer 20 has gone by
    waiting = SimpleNamespace(mail=set(), mailbox={"summer_20_1"})
    assert "Crop Research" in [x.title for x in coming(Data(), waiting, 50)]  # still in the mailbox
